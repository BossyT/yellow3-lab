#!/usr/bin/env python3
"""
Freeze one week of the AI Model Adoption instrument into a snapshot the AI Top 10
graphic is rendered from.

THE POINT OF PERSISTING IT. The graphic and the live page must never disagree.
If the renderer re-fetched, a graphic made on Tuesday would show different
numbers from the page it cites, and the first person to notice would be someone
checking our work. So the snapshot is written once, and both the PNG and the
archive entry for that week read only from it. A snapshot is never rewritten.

Everything is derived from data already on disk:

    research/model-adoption-data.json        the authoritative current pull
    research/model-adoption/_data/models.json  origin country, weekly series
    research/snapshots/YYYY-MM-DD.json       immutable daily totals, for sparklines

    python3 research/top10_snapshot.py            write the current window
    python3 research/top10_snapshot.py --dry-run  print it, write nothing
"""

import datetime
import glob
import re
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "research", "model-adoption-data.json")
MODELS = os.path.join(ROOT, "research", "model-adoption", "_data", "models.json")
SNAP_DIR = os.path.join(ROOT, "research", "snapshots")
OUT_DIR = os.path.join(ROOT, "research", "model-adoption", "top10")

TOP_N = 10
# Below this the movement is noise rather than signal, and a rank built on it
# would flap week to week. Stated on the graphic, not just here.
MIN_SHARE_PCT = 0.1
SPARK_DAYS = 7


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def edition_id(window_end):
    """ISO year-week of the window's last day, e.g. 2026-33."""
    d = datetime.date.fromisoformat(window_end)
    iso = d.isocalendar()
    return "%04d-%02d" % (iso[0], iso[1])


def daily_shares(days):
    """Routed share per model per day, from the immutable daily snapshots."""
    out = {}
    for path in days:
        day = load(path)
        rows = day.get("rows") or []
        total = sum(float(r.get("total_tokens") or 0) for r in rows)
        if not total:
            continue
        for r in rows:
            slug = r.get("model_permaslug")
            if not slug:
                continue
            out.setdefault(slug, {})[day["date"]] = \
                round(float(r.get("total_tokens") or 0) / total * 100, 4)
    return out


def build():
    data = load(DATA)
    models = load(MODELS)["models"]
    window = data["window"]["current"]
    start, end = window[0], window[1]

    # the seven days of the current window, in order, for the sparklines
    days = sorted(p for p in glob.glob(os.path.join(SNAP_DIR, "*.json"))
                  if start <= os.path.basename(p)[:-5] <= end)[-SPARK_DAYS:]
    shares = daily_shares(days)
    day_labels = [os.path.basename(p)[:-5] for p in days]

    by_perma = {m.get("permaslug"): m for m in models.values() if m.get("permaslug")}

    # Per-release pp change, computed from the same immutable daily snapshots.
    #
    # models.json carries share_change_pp per SLUG, which aggregates every dated
    # release of a model. That is right for the Explorer page and wrong here:
    # OpenRouter routes releases separately, so DeepSeek V4 Flash appears twice
    # in this table - 20260731 at rank 1 and 20260423 at rank 4 - and giving
    # both the same aggregate delta would be a made-up number on two rows.
    prior = data["window"]["prior"]
    prior_days = sorted(p for p in glob.glob(os.path.join(SNAP_DIR, "*.json"))
                        if prior[0] <= os.path.basename(p)[:-5] <= prior[1])
    prior_shares = daily_shares(prior_days)

    def mean_share(table, permaslug):
        vals = [v for v in table.get(permaslug, {}).values()]
        return sum(vals) / len(vals) if vals else None

    def delta_for(permaslug):
        now = mean_share(shares, permaslug)
        was = mean_share(prior_shares, permaslug)
        if now is None or was is None:
            return None
        return round(now - was, 3)

    # Two dated releases of one model would otherwise appear as the same name
    # twice with nothing to tell them apart. Disambiguate by release month.
    seen = {}
    for row in data["leaderboard"]:
        seen[row["name"]] = seen.get(row["name"], 0) + 1

    def label(row):
        if seen.get(row["name"], 0) < 2:
            return row["name"]
        m = re.search(r"-(\d{4})(\d{2})(\d{2})$", row["model"] or "")
        if not m:
            return row["name"]
        month = datetime.date(int(m.group(1)), int(m.group(2)), 1).strftime("%b %Y")
        return "%s (%s)" % (row["name"], month)

    excluded = 0
    rows = []
    for row in data["leaderboard"]:
        if row["pct"] < MIN_SHARE_PCT:
            excluded += 1
            continue
        if len(rows) >= TOP_N:
            continue
        meta = by_perma.get(row["model"]) or models.get(row.get("slug")) or {}
        spark = [shares.get(row["model"], {}).get(d) for d in day_labels]
        rows.append({
            "rank": row["rank"],
            "prev_rank": row.get("prev_rank"),
            "move": row.get("move"),
            "new": bool(row.get("new")),
            "name": label(row),
            "developer": row.get("developer"),
            "slug": row.get("slug"),
            "region": row.get("region"),
            "country": meta.get("country") or row.get("region"),
            "pct": row["pct"],
            # change in mean daily share against the prior seven days,
            # computed per release from the same immutable snapshots
            "delta_pp": delta_for(row["model"]),
            "spark": [s for s in spark if s is not None],
        })

    # totals for the footer band
    last_day = load(days[-1]) if days else {"rows": []}
    total_tokens = sum(float(r.get("total_tokens") or 0) for r in last_day.get("rows", []))
    top_region = max(data["share"], key=lambda s: s["pct"])

    movers = [r for r in rows if isinstance(r.get("delta_pp"), (int, float))]
    biggest = max(movers, key=lambda r: abs(r["delta_pp"])) if movers else None

    otr = data.get("on_the_record") or {}
    this_week = (otr.get("this_week") or {}).get("text")
    prior = otr.get("prior") or {}

    snap = {
        "edition": edition_id(end),
        "window": {"start": start, "end": end,
                   "label": "%s to %s" % (pretty(start), pretty(end))},
        "generated_utc": data.get("generated_utc"),
        "as_of": data.get("as_of"),
        "source": "OpenRouter routing data, analysed by yellow3",
        "url": "yellow3.io/research/model-adoption/live",
        "methodology": ("Share of routed tokens over the seven days shown. Change is "
                        "against the mean of the prior seven days. Models below %s "
                        "percent of routed tokens are excluded." % MIN_SHARE_PCT),
        "rows": rows,
        "excluded_below_threshold": excluded,
        "totals": {
            "models_tracked": len([r for r in data["leaderboard"]
                                   if r["pct"] >= MIN_SHARE_PCT]),
            "routed_tokens_day": total_tokens,
            "top_region": top_region["region"],
            "top_region_pct": top_region["pct"],
        },
        "biggest_mover": ({
            "name": biggest["name"],
            "delta_pp": biggest["delta_pp"],
            "rank": biggest["rank"],
        } if biggest else None),
        "call": {
            "this_week": this_week,
            "last_week": prior.get("text"),
            "last_week_grade": prior.get("grade"),
        },
    }
    return snap


def pretty(iso):
    d = datetime.date.fromisoformat(iso)
    return d.strftime("%-d %B %Y") if os.name != "nt" else d.strftime("%d %B %Y")


def main():
    snap = build()
    if "--dry-run" in sys.argv:
        print(json.dumps(snap, indent=2)[:2400])
        print("\n  dry run: nothing written")
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, snap["edition"] + ".json")
    if os.path.exists(path) and "--force" not in sys.argv:
        print("  %s already exists. A snapshot is never rewritten; pass --force "
              "only if you know why." % os.path.basename(path))
        return 0
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("  wrote %s  (%d rows, %d excluded below %s%%)"
          % (os.path.relpath(path, ROOT), len(snap["rows"]),
             snap["excluded_below_threshold"], MIN_SHARE_PCT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
