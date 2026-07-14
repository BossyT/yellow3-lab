#!/usr/bin/env python3
"""
yellow3 research - model adoption instrument builder.

One scheduled run per day:
  1. Pull OpenRouter rankings-daily (30-day rolling window of routed token totals).
  2. Store each day as an immutable snapshot under research/snapshots/.
  3. Apply the yellow3 region layer (research/model-origins.json).
  4. Compute the weekly regional share, leaderboard, week-over-week movement
     and the record book from the full stored history.
  5. Keep the weekly edition in step (research/editions.json), appending a
     draft stub when a new Wednesday has rolled over.
  6. Emit research/model-adoption-data.json for the static page to fetch.

The OpenRouter key is read from the OPENROUTER_API_KEY environment variable.
It is never written to any file, snapshot or output. Do not hardcode it.

Built reusable: a second instrument needs its own data source and compute
block, but reuses the snapshot store, region layer and edition machinery.
"""

import os
import re
import sys
import json
import glob
import time
import argparse
import datetime as dt
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP_DIR = os.path.join(HERE, "snapshots")
ORIGINS = os.path.join(HERE, "model-origins.json")
EDITIONS = os.path.join(HERE, "editions.json")
OUT = os.path.join(HERE, "model-adoption-data.json")
PAGES_DIR = os.path.join(HERE, "model-adoption")          # generated per-model pages
DATA_DIR = os.path.join(PAGES_DIR, "_data")               # derived + curated data
MODELS_JSON = os.path.join(DATA_DIR, "models.json")       # derived, regenerated
PROVIDERS_JSON = os.path.join(DATA_DIR, "providers.json")  # curated (logos/urls), merged
META_JSON = os.path.join(DATA_DIR, "model-meta.json")     # curated facts, merged
PAGES_JSON = os.path.join(DATA_DIR, "pages.json")         # append-only page set
ECON_JSON = os.path.join(DATA_DIR, "economics.json")      # pricing + capabilities


def position_to_adoption(pos, trend):
    """Combine cost tier x adoption trend into a plain-language position label."""
    low, prem = pos == "Low cost", pos == "Premium"
    if low and trend == "rising":
        return "High-growth challenger"
    if low:
        return "Value play"
    if prem and trend == "rising":
        return "Premium leader"
    if prem and trend == "falling":
        return "Under pressure"
    if trend == "rising":
        return "Momentum builder"
    if trend == "falling":
        return "Losing ground"
    return "Holding position"

DATASET_URL = "https://openrouter.ai/api/v1/datasets/rankings-daily"
THESIS = ("See which AI models the world is actually using, where they were "
          "built, and how the balance is changing. The live chart updates as new "
          "routed traffic is recorded, so rankings and regional shares can shift "
          "at any time. Return regularly to follow the movement.")
REGION_ORDER = ["Asia", "Europe", "US", "Other"]
REGION_COLORS = {"Asia": "#c0613a", "Europe": "#c9a227", "US": "#3b6ea5", "Other": "#a8a6a1"}

# Developer slug -> display name for the leaderboard.
DEV_DISPLAY = {
    "openai": "OpenAI", "anthropic": "Anthropic", "google": "Google",
    "meta-llama": "Meta", "x-ai": "xAI", "nvidia": "NVIDIA",
    "perplexity": "Perplexity", "arcee-ai": "Arcee", "poolside": "Poolside",
    "mistralai": "Mistral", "deepseek": "DeepSeek", "qwen": "Qwen",
    "z-ai": "Z.ai", "moonshotai": "Moonshot", "minimax": "MiniMax",
    "tencent": "Tencent", "xiaomi": "Xiaomi", "stepfun": "StepFun",
    "inclusionai": "inclusionAI", "openrouter": "OpenRouter",
    "cohere": "Cohere", "baai": "BAAI", "bytedance-seed": "ByteDance",
    "nex-agi": "NEX-AGI",
}

# Developer slug -> headquarters country (structured, from model-origins.json
# developer_notes). Region still comes from the origins layer; this is only for
# the model-page "origin" line. Empty when the HQ is not publicly known.
COUNTRY_BY_DEV = {
    "openai": "United States", "anthropic": "United States", "google": "United States",
    "meta-llama": "United States", "x-ai": "United States", "nvidia": "United States",
    "perplexity": "United States", "arcee-ai": "United States", "poolside": "United States",
    "mistralai": "France", "deepseek": "China", "qwen": "China", "z-ai": "China",
    "moonshotai": "China", "minimax": "China", "tencent": "China", "xiaomi": "China",
    "stepfun": "China", "inclusionai": "China", "cohere": "Canada", "baai": "China",
    "bytedance-seed": "China",
}


# ---------------------------------------------------------------- data in --

def fetch_dataset():
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        sys.exit("OPENROUTER_API_KEY is not set. Refusing to run without it.")
    req = urllib.request.Request(
        DATASET_URL,
        headers={"Authorization": "Bearer " + key, "Accept": "application/json"},
    )
    attempts = 3
    payload = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                payload = json.load(r)
            break
        except urllib.error.HTTPError as e:
            # 429/5xx are transient; anything else (e.g. 401 auth) will not self-heal.
            if e.code not in (429, 500, 502, 503, 504) or attempt == attempts:
                sys.exit(f"OpenRouter request failed: HTTP {e.code} {e.reason}")
            wait = 5 * attempt
            print(f"OpenRouter HTTP {e.code}; retrying in {wait}s "
                  f"({attempt}/{attempts - 1})...", file=sys.stderr)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == attempts:
                sys.exit(f"OpenRouter request failed after {attempts} attempts: {e}")
            wait = 5 * attempt
            print(f"OpenRouter fetch error ({e}); retrying in {wait}s "
                  f"({attempt}/{attempts - 1})...", file=sys.stderr)
            time.sleep(wait)
    rows = payload.get("data", payload if isinstance(payload, list) else [])
    if not rows:
        sys.exit("OpenRouter returned no rows.")
    return rows


def load_input(path):
    with open(path) as f:
        payload = json.load(f)
    return payload.get("data", payload)


# ----------------------------------------------------------------- storage --

def store_snapshots(rows, fetched_utc):
    """Write one immutable file per date. Idempotent (same date -> same data)."""
    os.makedirs(SNAP_DIR, exist_ok=True)
    by_date = {}
    for r in rows:
        by_date.setdefault(r["date"], []).append(
            {"model_permaslug": r["model_permaslug"], "total_tokens": str(r["total_tokens"])}
        )
    written = 0
    for date, day_rows in by_date.items():
        path = os.path.join(SNAP_DIR, f"{date}.json")
        if os.path.exists(path):
            continue
        with open(path, "w") as f:
            json.dump({"date": date, "fetched_utc": fetched_utc, "rows": day_rows},
                      f, indent=2)
        written += 1
    return written


def load_history():
    """Every stored day, oldest first: {date: {permaslug: tokens_int}}."""
    history = {}
    for path in sorted(glob.glob(os.path.join(SNAP_DIR, "*.json"))):
        snap = json.load(open(path))
        history[snap["date"]] = {row["model_permaslug"]: int(row["total_tokens"])
                                 for row in snap["rows"]}
    return history


# ------------------------------------------------------------- region layer --

def load_region_layer():
    om = json.load(open(ORIGINS))
    return om, om["regions_by_developer"], om.get("model_overrides", {})


def classify(slug, dev_map, overrides, unmapped):
    if slug in overrides:
        return overrides[slug]
    dev = slug.split("/")[0] if "/" in slug else slug
    if dev in dev_map:
        return dev_map[dev]
    unmapped.setdefault(dev, slug)  # flag, do not drop
    return "Other"


def date_frag(t):
    # a token that looks like a date fragment: YYYYMMDD, YYMMDD, a 20xx year,
    # MMDD or a 2-digit day/month. Used to strip date suffixes from slugs.
    return t.isdigit() and (len(t) in (6, 8)
                            or (len(t) == 4 and (t.startswith("20") or True))
                            or len(t) == 2)


def _model_parts(slug):
    """Shared slug parsing: (dev, cleaned_parts, is_free). Drops the date suffix
    and a leading token that just repeats the developer name."""
    dev = slug.split("/")[0] if "/" in slug else ""
    rest = slug.split("/", 1)[1] if "/" in slug else slug
    free = rest.endswith(":free")
    rest = rest[:-5] if free else rest
    parts = rest.split("-")
    while len(parts) > 1 and date_frag(parts[-1]):
        parts.pop()
    if parts and parts[0].lower() == dev.lower():
        parts = parts[1:]
    return dev, [p for p in parts if p], free


def pretty_name(slug):
    if slug == "other":
        return "Other models (aggregated)"
    dev, parts, free = _model_parts(slug)
    label = " ".join(p.upper() if p in ("gpt", "glm", "vl", "oss", "moe", "ai")
                      else p.capitalize() for p in parts)
    head = DEV_DISPLAY.get(dev, dev.capitalize() if dev else "")
    name = (head + " " + label).strip()
    return name + (" (free)" if free else "")


def model_slug(slug):
    """Stable URL slug for a model permaslug, frozen even if the display name
    changes. e.g. xiaomi/mimo-v2.5-20260422 -> xiaomi-mimo-v2-5;
    openai/gpt-oss-120b:free -> openai-gpt-oss-120b-free."""
    dev, parts, free = _model_parts(slug)
    base = "-".join([dev] + parts) if dev else "-".join(parts)
    s = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return s + "-free" if free else s


# -------------------------------------------------------------- weekly view --

def week_windows(dates):
    cur = dates[-7:]
    prior = dates[-14:-7]
    return cur, prior


def agg(history, days):
    days = set(days)
    reg = {r: 0 for r in REGION_ORDER}
    mod = {}
    dev_map, overrides, unmapped = AGG_CTX
    for date, models in history.items():
        if date not in days:
            continue
        for slug, tok in models.items():
            mod[slug] = mod.get(slug, 0) + tok
            reg[classify(slug, dev_map, overrides, unmapped)] += tok
    return reg, mod


def ranked(mod):
    items = sorted(((m, v) for m, v in mod.items() if m != "other"),
                   key=lambda x: x[1], reverse=True)
    return {m: i + 1 for i, (m, _) in enumerate(items)}, items


# ------------------------------------------------------------- record book --

def build_records(history, dev_map, overrides, unmapped):
    dates = sorted(history)
    daily_rank, daily_top = {}, {}
    for d in dates:
        order = sorted(((m, v) for m, v in history[d].items() if m != "other"),
                       key=lambda x: x[1], reverse=True)
        daily_rank[d] = {m: i + 1 for i, (m, _) in enumerate(order)}
        daily_top[d] = order[0][0] if order else None

    # longest reign at #1 + current streak
    longest_reign = (None, 0)
    run_model, run_len = None, 0
    for d in dates:
        top = daily_top[d]
        run_len = run_len + 1 if top == run_model else 1
        run_model = top
        if run_len > longest_reign[1]:
            longest_reign = (top, run_len)
    current_streak = (run_model, run_len)

    # weekly movers: latest vs 7 days earlier
    mover = faller = None
    if len(dates) >= 8:
        new_d, old_d = dates[-1], dates[-8]
        rnew, rold = daily_rank[new_d], daily_rank[old_d]
        best_up = best_down = 0
        for m, cr in rnew.items():
            if m in rold:
                jump = rold[m] - cr
                if jump > best_up:
                    best_up, mover = jump, (m, rold[m], cr)
                if -jump > best_down:
                    best_down, faller = -jump, (m, rold[m], cr)
        new_entrants = [m for m in rnew if m not in rold]
    else:
        new_entrants = []

    # Europe high-water daily share
    eu_hi = (0.0, None)
    for d in dates:
        tot = sum(history[d].values())
        if not tot:
            continue
        eu = sum(v for m, v in history[d].items()
                 if classify(m, dev_map, overrides, unmapped) == "Europe")
        share = 100 * eu / tot
        if share > eu_hi[0]:
            eu_hi = (share, d)

    def D(date):
        return dt.date.fromisoformat(date).strftime("%-d %b %Y")

    records = []
    records.append({
        "key": "europe_high_water", "label": "Europe's high-water share",
        "value": f"{eu_hi[0]:.2f}%",
        "detail": f"set {D(eu_hi[1])}" if eu_hi[1] else "no data yet",
        "europe": True,
    })
    if longest_reign[0]:
        records.append({
            "key": "longest_reign", "label": "Longest reign at number one",
            "value": f"{longest_reign[1]} days",
            "detail": pretty_name(longest_reign[0]),
        })
    if current_streak[0]:
        records.append({
            "key": "current_streak", "label": "Current number one",
            "value": pretty_name(current_streak[0]),
            "detail": f"{current_streak[1]} day{'s' if current_streak[1] != 1 else ''} running",
        })
    if mover:
        records.append({
            "key": "biggest_mover", "label": "Biggest weekly mover",
            "value": f"#{mover[1]} → #{mover[2]}",
            "detail": pretty_name(mover[0]),
        })
    if faller:
        records.append({
            "key": "steepest_fall", "label": "Steepest fall",
            "value": f"#{faller[1]} → #{faller[2]}",
            "detail": pretty_name(faller[0]),
        })
    records.append({
        "key": "new_entrants", "label": "New entrants this week",
        "value": str(len(new_entrants)),
        "detail": (pretty_name(new_entrants[0]) + (" and others" if len(new_entrants) > 1 else "")
                   if new_entrants else "none"),
    })
    return records


# ------------------------------------------------------- per-model history --

def week_endings(dates):
    """Weekly points stepping back 7 days from the latest date; only full 7-day
    windows that fit inside stored history, oldest first. The newest ending is
    the latest date, so its window matches the live leaderboard window exactly."""
    if not dates:
        return []
    first = dt.date.fromisoformat(dates[0])
    cur = dt.date.fromisoformat(dates[-1])
    out = []
    while cur - dt.timedelta(days=6) >= first:
        start = cur - dt.timedelta(days=6)
        window = [(start + dt.timedelta(days=i)).isoformat() for i in range(7)]
        out.append((cur.isoformat(), window))
        cur -= dt.timedelta(days=7)
    out.reverse()
    return out


def _window_tokens(history, window):
    """Sum tokens per model over a window. Returns (per-model excl. 'other',
    total incl. 'other'). Total matches the instrument's share denominator."""
    mod, total = {}, 0
    for d in window:
        for slug, tok in history.get(d, {}).items():
            total += tok
            if slug != "other":
                mod[slug] = mod.get(slug, 0) + tok
    return mod, (total or 1)


def _trailing_streak(flags):
    """Count of trailing True values in a per-week presence/threshold list."""
    n = 0
    for f in reversed(flags):
        if f:
            n += 1
        else:
            break
    return n


def build_model_series(history, ctx):
    """For every model ever seen: a weekly time series plus derived facts and
    milestones. All derived from the immutable snapshots, so past weeks are
    stable across rebuilds (history is never overwritten)."""
    dev_map, overrides, unmapped = ctx
    endings = week_endings(sorted(history))

    first_seen = {}
    for d in sorted(history):
        for slug in history[d]:
            if slug != "other":
                first_seen.setdefault(slug, d)

    # per-week ranks / region ranks / shares
    weekly = []
    for end, window in endings:
        mod, total = _window_tokens(history, window)
        order = sorted(mod.items(), key=lambda x: -x[1])
        rank = {m: i + 1 for i, (m, _) in enumerate(order)}
        by_region = {}
        for m, _ in order:
            by_region.setdefault(classify(m, dev_map, overrides, unmapped), []).append(m)
        region_rank = {m: i + 1 for ms in by_region.values() for i, m in enumerate(ms)}
        weekly.append({"end": end, "rank": rank, "region_rank": region_rank,
                       "share": {m: round(100 * t / total, 3) for m, t in mod.items()}})

    all_slugs = sorted({m for wk in weekly for m in wk["rank"]})
    out = {}
    for slug in all_slugs:
        series, prev, present_prev, ever = [], None, False, False
        ranked_flags, top10_flags, top3_flags = [], [], []
        for wk in weekly:
            r = wk["rank"].get(slug)
            present = r is not None
            ranked_flags.append(present)
            top10_flags.append(present and r <= 10)
            top3_flags.append(present and r <= 3)
            if not present:
                present_prev = False
                continue
            share = wk["share"][slug]
            status = "NEW" if not ever else ("RE-ENTRY" if not present_prev else "ranked")
            ever = True
            entry = {
                "week_ending": wk["end"],
                "global_rank": r,
                "region_rank": wk["region_rank"].get(slug),
                "routed_share": share,
                "share_change_pp": round(share - prev["routed_share"], 3) if (prev and present_prev) else None,
                "rank_change": (prev["global_rank"] - r) if (prev and present_prev) else None,
                "status": status,
            }
            series.append(entry)
            prev, present_prev = entry, True
        if not series:
            continue

        ranks = [s["global_rank"] for s in series]
        shares = [s["routed_share"] for s in series]
        peak_rank = min(ranks)
        peak_share = max(shares)
        latest = series[-1]
        currently_ranked = ranked_flags[-1]

        # milestones (first crossing, oldest -> newest)
        ms = [{"type": "first_tracked", "title": "First tracked",
               "date": first_seen.get(slug, series[0]["week_ending"]), "value": None}]

        def first_at(pred):
            for s in series:
                if pred(s["global_rank"]):
                    return s["week_ending"]
            return None
        for n, label in ((20, "Entered top 20"), (10, "Entered top 10"),
                         (3, "Entered top 3"), (1, "Reached number one")):
            w = first_at(lambda rk, n=n: rk <= n)
            if w:
                ms.append({"type": f"entered_top_{n}", "title": label, "date": w, "value": None})
        ms.append({"type": "peak_share", "title": "Peak routed share",
                   "date": series[shares.index(peak_share)]["week_ending"],
                   "value": f"{peak_share:.2f}%"})
        rises = [s for s in series if s["rank_change"]]
        if rises:
            best = max(rises, key=lambda s: s["rank_change"])
            worst = min(rises, key=lambda s: s["rank_change"])
            if best["rank_change"] > 0:
                ms.append({"type": "biggest_rise", "title": "Biggest weekly rise",
                           "date": best["week_ending"], "value": f"+{best['rank_change']} places"})
            if worst["rank_change"] < 0:
                ms.append({"type": "biggest_fall", "title": "Biggest weekly fall",
                           "date": worst["week_ending"], "value": f"{worst['rank_change']} places"})
        ms.sort(key=lambda m: (m["date"], m["type"] != "first_tracked"))

        out[slug] = {
            "permaslug": slug,
            "slug": model_slug(slug),
            "name": pretty_name(slug),
            "developer": slug.split("/")[0] if "/" in slug else slug,
            "provider_name": DEV_DISPLAY.get(slug.split("/")[0], (slug.split("/")[0] or slug).capitalize()),
            "region": classify(slug, dev_map, overrides, unmapped),
            "country": COUNTRY_BY_DEV.get(slug.split("/")[0], ""),
            "first_tracked": first_seen.get(slug),
            "currently_ranked": currently_ranked,
            "current": {
                "week_ending": latest["week_ending"],
                "global_rank": latest["global_rank"],
                "region_rank": latest["region_rank"],
                "routed_share": latest["routed_share"],
                "rank_change": latest["rank_change"],
            },
            "peak_rank": peak_rank,
            "peak_share": peak_share,
            "weeks_ranked": _trailing_streak(ranked_flags),
            "weeks_top10": _trailing_streak(top10_flags),
            "weeks_top3": _trailing_streak(top3_flags),
            "series": series,
            "milestones": ms,
        }
    return out


def _load_json(path, default):
    try:
        return json.load(open(path))
    except (FileNotFoundError, ValueError):
        return default


# curated per-model descriptive fields (sourced later; null = not yet verified)
META_FIELDS = ["release_date", "model_family", "description", "model_type",
               "modalities", "context_window", "license", "open_weight",
               "api_available", "official_url", "technical_report_url",
               "repository_url", "last_verified_at"]


def emit_model_data(models, leaderboard):
    """Write the derived per-model data plus merge-preserving curated registries.
    Returns the set of slugs that should have a page (top-30 now, union with any
    page created before, so a page persists once a model has ranked)."""
    os.makedirs(DATA_DIR, exist_ok=True)

    # a model qualifies for a page if it is (or has been) in the ranking; exclude
    # non-chat entries like embeddings.
    def eligible(permaslug):
        return "embedding" not in permaslug
    current_top = [row["slug"] for row in leaderboard if eligible(row["model"])]
    prior_pages = _load_json(PAGES_JSON, [])
    page_slugs = sorted(set(prior_pages) | set(current_top))

    # models.json: everything derived, keyed by url slug (only eligible models)
    by_slug = {m["slug"]: m for m in models.values() if eligible(m["permaslug"])}
    json.dump({"generated_from": "snapshots", "models": by_slug},
              open(MODELS_JSON, "w"), indent=2)

    # providers.json: merge-preserving (keep curated logo/url across rebuilds)
    providers = _load_json(PROVIDERS_JSON, {})
    for m in by_slug.values():
        dev = m["developer"]
        p = providers.get(dev, {})
        p.setdefault("slug", dev)
        p["name"] = m["provider_name"]         # derived, safe to refresh
        p["region"] = m["region"]
        p["country"] = m["country"]
        p.setdefault("official_url", None)      # curated
        p.setdefault("logo_path", None)
        p.setdefault("logo_source_url", None)
        p.setdefault("logo_verified_at", None)
        providers[dev] = p
    json.dump(providers, open(PROVIDERS_JSON, "w"), indent=2)

    # model-meta.json: merge-preserving curated descriptive fields per page slug
    meta = _load_json(META_JSON, {})
    for slug in page_slugs:
        entry = meta.get(slug, {})
        for f in META_FIELDS:
            entry.setdefault(f, None)
        meta[slug] = entry
    json.dump(meta, open(META_JSON, "w"), indent=2)

    json.dump(page_slugs, open(PAGES_JSON, "w"), indent=2)
    return page_slugs


# ---------------------------------------------------------------- editions --

def most_recent_wednesday(today):
    return today - dt.timedelta(days=(today.weekday() - 2) % 7)


def sync_editions(today):
    doc = json.load(open(EDITIONS))
    eds = doc["editions"]
    wed = most_recent_wednesday(today).isoformat()
    if not any(e["date"] == wed for e in eds):
        n = max((e["number"] for e in eds), default=0) + 1
        eds.append({
            "number": n, "date": wed, "status": "draft",
            "byline": "Thomas Chr. Melskens",
            "title": "Draft - to be finalised",
            "dek": "", "body": [
                "Draft edition generated from this week's data. Replace with the "
                "finalised read before it goes out."
            ],
            "call": {"this_week": "", "resolves_on": "", "grade": None, "grade_note": None},
        })
        json.dump(doc, open(EDITIONS, "w"), indent=2)
        json.load(open(EDITIONS))  # validate round-trip
    eds = sorted(eds, key=lambda e: e["number"])
    # Publish the latest FINALISED edition, not the auto-appended draft stub, so
    # an un-finalised week never blanks the read. Fall back to the latest edition
    # only if nothing is final yet (a brand-new instrument).
    finals = [e for e in eds if e.get("status") == "final"]
    if finals:
        current = finals[-1]
        # Prior = the most recent earlier final edition that actually carries a
        # call to grade, skipping empty draft stubs from skipped weeks.
        prior = next((e for e in reversed(finals[:-1])
                      if (e.get("call", {}).get("this_week") or "").strip()), None)
    else:
        current = eds[-1]
        prior = None
    index = [{"number": e["number"], "date": e["date"], "title": e["title"],
              "status": e["status"]} for e in reversed(eds)]
    return current, prior, index


# -------------------------------------------------------------------- main --

AGG_CTX = None  # (dev_map, overrides, unmapped) set in main


def main():
    global AGG_CTX
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="local JSON instead of hitting the API")
    ap.add_argument("--fast", action="store_true", help="skip per-model uptime fetch (local iteration)")
    args = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    fetched_utc = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = load_input(args.input) if args.input else fetch_dataset()

    written = store_snapshots(rows, fetched_utc)
    history = load_history()
    dates = sorted(history)
    as_of = dates[-1]

    om, dev_map, overrides = load_region_layer()
    unmapped = {}
    AGG_CTX = (dev_map, overrides, unmapped)

    cur_days, prior_days = week_windows(dates)
    creg, cmod = agg(history, cur_days)
    preg, pmod = agg(history, prior_days)
    ctot = sum(creg.values()) or 1
    ptot = sum(preg.values()) or 1
    # regional share four weeks ago (the 7-day window ending ~28 days back), for
    # an accurate month-over-month delta in the report. Falls back to the oldest
    # available window if history is shorter than four weeks.
    month_days = dates[-28:-21] if len(dates) >= 28 else dates[:7]
    mreg, _ = agg(history, month_days)
    mtot = sum(mreg.values()) or 1

    share = []
    for rg in REGION_ORDER:
        cs = 100 * creg[rg] / ctot
        ps = 100 * preg[rg] / ptot
        ms = 100 * mreg[rg] / mtot
        share.append({"region": rg, "pct": round(cs, 2), "delta_pp": round(cs - ps, 2),
                      "delta_pp_4w": round(cs - ms, 2)})

    crk, citems = ranked(cmod)
    prk, _ = ranked(pmod)
    leaderboard = []
    for slug, tok in citems[:30]:
        cr = crk[slug]
        pr = prk.get(slug)
        if pr is None:
            move = "new"
        elif pr > cr:
            move = "up"
        elif pr < cr:
            move = "down"
        else:
            move = "flat"
        leaderboard.append({
            "rank": cr, "prev_rank": pr, "move": move, "new": pr is None,
            "model": slug, "name": pretty_name(slug), "slug": model_slug(slug),
            "developer": DEV_DISPLAY.get(slug.split("/")[0], slug.split("/")[0]),
            "region": classify(slug, dev_map, overrides, unmapped),
            "pct": round(100 * tok / ctot, 2),
        })

    records = build_records(history, dev_map, overrides, unmapped)

    # count of top-20 models per region, for the map + regional-share block
    # (the ranking table lists the top 30; the origin map summarises the top 20)
    region_counts = {rg: 0 for rg in REGION_ORDER}
    for row in leaderboard[:20]:
        region_counts[row["region"]] = region_counts.get(row["region"], 0) + 1
    for s in share:
        s["models"] = region_counts.get(s["region"], 0)

    # per-model histories + registries (data foundation for the model pages)
    models = build_model_series(history, AGG_CTX)
    page_slugs = emit_model_data(models, leaderboard)

    # ---- economics layer: real OpenRouter pricing + capabilities + uptime ----
    try:
        import bisect
        import pricing as pr
        by_slug_models = {m["slug"]: m for m in models.values()}
        page_models = {s: by_slug_models[s] for s in page_slugs if s in by_slug_models}
        econ = pr.build_pricing(page_models, with_uptime=not args.fast)
        pr.store_snapshot(econ, as_of)
        phist = pr.load_history()

        wl = pr.WORKLOADS["coding-agent"]
        costs = {s: pr.workload_cost(e, wl) for s, e in econ.items()}
        priced = sorted(c for c in costs.values() if c is not None)

        def position(c):
            if c is None or len(priced) < 2:
                return None
            r = bisect.bisect_left(priced, c) / (len(priced) - 1)
            return "Low cost" if r <= 0.34 else ("Premium" if r >= 0.67 else "Mid cost")

        anchor_order = ["deepseek-v4-flash", "google-gemini-2-5-flash",
                        "anthropic-claude-sonnet-5", "openai-gpt-5-5", "xiaomi-mimo-v2-5"]
        anchors = [a for a in anchor_order if a in econ]
        for s, e in econ.items():
            cur = by_slug_models.get(s, {}).get("current", {})
            rc = cur.get("rank_change") or 0
            trend = "rising" if rc > 0 else ("falling" if rc < 0 else "flat")
            e["workload_cost"] = costs.get(s)
            e["price_position"] = position(costs.get(s))
            e["adoption_trend"] = trend
            e["position_label"] = position_to_adoption(e["price_position"], trend)
            e["price_history"] = pr.price_changes(s, phist)
            comp = [s] + [a for a in anchors if a != s]
            e["compare"] = [
                {"slug": cs, "name": by_slug_models[cs]["name"], "in": econ[cs]["in"],
                 "out": econ[cs]["out"], "cache_read": econ[cs]["cache_read"], "you": cs == s}
                for cs in comp[:4] if cs in econ and econ[cs].get("in") is not None]
        # backfill real descriptive facts from the feed onto model-meta (fills
        # the "Not publicly disclosed" gaps; never overwrites a curated value)
        meta_all = _load_json(META_JSON, {})
        for s, e in econ.items():
            mm = meta_all.setdefault(s, {})
            ctx = e.get("context")
            if ctx and not mm.get("context_window"):
                mm["context_window"] = (f"{round(ctx/1000)}K tokens" if ctx < 1_000_000
                                        else f"{ctx/1_000_000:.1f}M tokens".replace(".0M", "M"))
            if e.get("modalities") and not mm.get("modalities"):
                mm["modalities"] = ", ".join(e["modalities"])
            if mm.get("open_weight") is None and e.get("open_weight") is not None:
                mm["open_weight"] = bool(e["open_weight"])
            if not mm.get("model_type"):
                mm["model_type"] = "Multimodal (text + image)" if e.get("image_in") else "Text"
        json.dump(meta_all, open(META_JSON, "w"), indent=2)

        json.dump({"as_of": as_of, "workloads": pr.WORKLOADS, "models": econ},
                  open(ECON_JSON, "w"), indent=2)
        print(f"economics: priced {len(econ)} models, {len(phist)} pricing snapshot day(s)")
    except Exception as exc:  # noqa: BLE001 - never break the data pull
        print(f"WARNING: economics layer failed: {exc}", file=sys.stderr)

    lead = max(share, key=lambda s: s["pct"])
    eu = next(s for s in share if s["region"] == "Europe")
    payoff = (f"{lead['region']} leads with {lead['pct']:.0f}% of routed tokens "
              f"this week ({lead['delta_pp']:+.1f} points), while Europe sits at "
              f"{eu['pct']:.2f}%.")

    today = most_recent_wednesday(dt.date.today())  # edition cadence anchor
    current_ed, prior_ed, ed_index = sync_editions(dt.date.today())

    on_record = {
        "this_week": {
            "text": current_ed.get("call", {}).get("this_week", ""),
            "resolves_on": current_ed.get("call", {}).get("resolves_on", ""),
        },
        "prior": ({
            "number": prior_ed["number"],
            "text": prior_ed.get("call", {}).get("this_week", ""),
            "grade": prior_ed.get("call", {}).get("grade"),
            "note": prior_ed.get("call", {}).get("grade_note"),
        } if prior_ed else {
            "number": None, "text": None, "grade": None,
            "note": "First edition - no prior call to grade yet.",
        }),
    }

    try:
        from zoneinfo import ZoneInfo
        cet = now.astimezone(ZoneInfo("Europe/Copenhagen"))
    except Exception:
        cet = now
    refreshed_cet = cet.strftime("%-d %b %Y, %H:%M") + " CET"
    as_of_pretty = dt.date.fromisoformat(as_of).strftime("%-d %B %Y")

    methodology = (
        "Region reflects where each model's developer is headquartered, not where "
        "the model is hosted. Open-weight models are attributed to their original "
        "developer. Models we cannot place cleanly in Asia, Europe or the US - "
        "including OpenRouter's own aggregated 'other' row and undisclosed labs - "
        "are counted as Other. The full mapping is versioned at "
        "research/model-origins.json (version " + om["version"] + "). "
        "Figures reflect OpenRouter routing traffic specifically. That traffic is "
        "developer-skewed and cost-sensitive and excludes most direct enterprise "
        "API usage, so this is developer routing behaviour, not the whole market. "
        "Token totals are OpenRouter's combined prompt and completion totals, the "
        "same basis as the public rankings chart, aggregated over a trailing seven "
        "days; week-over-week compares against the seven days before that."
    )

    data = {
        "instrument": "model-adoption",
        "title": "Model adoption",
        "thesis": THESIS,
        "status": "live",
        "as_of": as_of,
        "as_of_pretty": as_of_pretty,
        "generated_utc": fetched_utc,
        "refreshed_cet": refreshed_cet,
        "source": {
            "name": "OpenRouter",
            "url": "https://openrouter.ai/rankings",
            "line": f"Source: OpenRouter (openrouter.ai/rankings), as of {as_of_pretty}.",
        },
        "window": {
            "current": [cur_days[0], cur_days[-1]],
            "prior": [prior_days[0], prior_days[-1]] if prior_days else None,
            "days_history": len(dates),
        },
        "regions": REGION_ORDER,
        "region_colors": REGION_COLORS,
        "payoff": payoff,
        "share": share,
        "leaderboard": leaderboard,
        "records": records,
        "edition": current_ed,
        "on_the_record": on_record,
        "editions_index": ed_index,
        "methodology": methodology,
        "unmapped": [{"developer": d, "example": ex} for d, ex in unmapped.items()],
        "links": current_ed.get("links", {}),
    }

    with open(OUT, "w") as f:
        json.dump(data, f, indent=2)

    # generate the static Model Explorer pages from the derived data. Non-fatal:
    # a rendering error must not lose the day's data pull (pages persist from the
    # last good run and regenerate next time).
    try:
        import gen_model_pages
        gen_model_pages.generate()
    except Exception as e:  # noqa: BLE001
        print(f"WARNING: model page generation failed: {e}", file=sys.stderr)

    # the monthly intelligence report (data-backed sections auto-written)
    try:
        import gen_report
        gen_report.generate()
    except Exception as e:  # noqa: BLE001
        print(f"WARNING: report generation failed: {e}", file=sys.stderr)

    # Retired 2026-07-14: the /pro "coming soon" gate is superseded by the
    # Model Intelligence pricing gateway at /research/model-adoption. The old
    # /research/model-adoption/pro URL now 301-redirects there (vercel.json).
    # gen_pro is no longer generated to avoid regenerating a dead page.

    print(f"snapshots written: {written}  history days: {len(dates)}  as_of: {as_of}")
    print(f"current week: {cur_days[0]} -> {cur_days[-1]}")
    print("share: " + ", ".join(f"{s['region']} {s['pct']}% ({s['delta_pp']:+})" for s in share))
    print(f"leaderboard rows: {len(leaderboard)}  records: {len(records)}  edition: #{current_ed['number']} ({current_ed['status']})")
    if unmapped:
        print("UNMAPPED developers defaulted to Other (add to model-origins.json): "
              + ", ".join(f"{d} (e.g. {ex})" for d, ex in unmapped.items()))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
