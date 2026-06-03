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
import sys
import json
import glob
import argparse
import datetime as dt
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP_DIR = os.path.join(HERE, "snapshots")
ORIGINS = os.path.join(HERE, "model-origins.json")
EDITIONS = os.path.join(HERE, "editions.json")
OUT = os.path.join(HERE, "model-adoption-data.json")

DATASET_URL = "https://openrouter.ai/api/v1/datasets/rankings-daily"
THESIS = ("Where AI adoption actually sits, by region of origin, measured in "
          "real routed traffic, and how fast the lead changes.")
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
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.load(r)
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


def pretty_name(slug):
    if slug == "other":
        return "Other models (aggregated)"
    dev = slug.split("/")[0] if "/" in slug else ""
    rest = slug.split("/", 1)[1] if "/" in slug else slug
    free = rest.endswith(":free")
    rest = rest[:-5] if free else rest
    parts = rest.split("-")
    # drop trailing date fragments (YYYYMMDD, YYMMDD, a 20xx year, MMDD or a
    # 2-digit day/month), stopping at the first token that is not date-shaped
    def date_frag(t):
        return t.isdigit() and (len(t) in (6, 8)
                                or (len(t) == 4 and (t.startswith("20") or True))
                                or len(t) == 2)
    while len(parts) > 1 and date_frag(parts[-1]):
        parts.pop()
    # drop a leading model token that just repeats the developer name
    if parts and parts[0].lower() == dev.lower():
        parts = parts[1:]
    label = " ".join(p.upper() if p in ("gpt", "glm", "vl", "oss", "moe", "ai")
                      else p.capitalize() for p in parts if p)
    head = DEV_DISPLAY.get(dev, dev.capitalize() if dev else "")
    name = (head + " " + label).strip()
    return name + (" (free)" if free else "")


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
    current = eds[-1]
    prior = eds[-2] if len(eds) >= 2 else None
    index = [{"number": e["number"], "date": e["date"], "title": e["title"],
              "status": e["status"]} for e in reversed(eds)]
    return current, prior, index


# -------------------------------------------------------------------- main --

AGG_CTX = None  # (dev_map, overrides, unmapped) set in main


def main():
    global AGG_CTX
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="local JSON instead of hitting the API")
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

    share = []
    for rg in REGION_ORDER:
        cs = 100 * creg[rg] / ctot
        ps = 100 * preg[rg] / ptot
        share.append({"region": rg, "pct": round(cs, 2), "delta_pp": round(cs - ps, 2)})

    crk, citems = ranked(cmod)
    prk, _ = ranked(pmod)
    leaderboard = []
    for slug, tok in citems[:20]:
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
            "model": slug, "name": pretty_name(slug),
            "developer": DEV_DISPLAY.get(slug.split("/")[0], slug.split("/")[0]),
            "region": classify(slug, dev_map, overrides, unmapped),
            "pct": round(100 * tok / ctot, 2),
        })

    records = build_records(history, dev_map, overrides, unmapped)

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
