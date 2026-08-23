#!/usr/bin/env python3
"""
Every research instrument must declare how it is updated, and prove it.

WHY THIS EXISTS. On 15 August 2026 three instruments disagreed with themselves.
AI Model Adoption said "updated weekly" while a cron job refreshed it daily. The
EU AI Act and Digital Product Passport instruments promised weekly and had not
been touched for eighteen days - two missed editions each - while still showing
a "Live" badge. Nothing was checking, so nothing said anything. The EU AI Act
instrument spent those eighteen days scoring the Commission on missed deadlines.

Thomas's policy, frozen the same day: a regulation tracker should change when
the evidence changes, not because Wednesday arrived. So instruments declare an
update model and the build enforces it.

    live          an automated refresh path and a freshness threshold. Fails
                  when the data is older than the threshold, because a live
                  instrument that has stopped refreshing is the worst case:
                  it looks current and is not.
    scheduled     declares a cadence in days. Fails when stale beyond it.
    event_driven  never fails merely because time has passed - that is the
                  point of it - but MUST publish a last_verified date, so a
                  reader can see the age of the record for themselves.

Rule five, and the one that actually prevents recurrence: the public copy is
rendered from this same metadata, so a page cannot claim one cadence while its
dataset declares another.

    python3 research/cadence_check.py
"""

import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# dataset -> the page that renders it
INSTRUMENTS = {
    "research/model-adoption-data.json": "research/model-adoption/live.html",
    "research/eu-ai-act.json": "research/eu-ai-act.html",
    "research/digital-product-passport.json": "research/digital-product-passport.html",
    # The supplier register is the largest body of research on the site - 190
    # organisations - and had no declared update model at all, so nothing was
    # watching it age.
    "research/dpp-suppliers.json": "research/digital-product-passport/suppliers.html",
}

# Datasets whose currency is COMPUTED from their own rows rather than declared.
# Stronger than a stamped date, which can drift from the evidence it describes.
DERIVED = {"research/dpp-suppliers.json": ("suppliers", "source_date")}

VALID = {"live", "scheduled", "event_driven"}
# a cadence word that appears in prose is a claim; these are the ones that have
# bitten us, and the check refuses any of them on an instrument page
BANNED_PROSE = [
    r"updated weekly", r"Updated weekly", r"Live weekly",
    r"updated daily", r"Updated daily", r"updated monthly", r"Updated monthly",
]


def load(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        return json.load(fh)


def dataset_date(data, policy, path=None):
    """The most recent date the instrument itself claims."""
    if path in DERIVED:
        field, key = DERIVED[path]
        return max((r.get(key) or "" for r in data.get(field, [])), default="") or None
    for key in ("last_verified",):
        if policy.get(key):
            return policy[key]
    for key in ("as_of", "week_of"):
        if isinstance(data.get(key), str):
            return data[key]
    inst = data.get("instrument") or {}
    return inst.get("as_of")


def main():
    today = datetime.date.today()
    fail, note = [], []

    for ds, page in INSTRUMENTS.items():
        name = os.path.basename(ds)
        data = load(ds)
        policy = data.get("update_policy")

        # 1. every instrument declares its update model explicitly
        if not policy or policy.get("model") not in VALID:
            fail.append(f"{name}: no update_policy.model in {sorted(VALID)} - "
                        f"every instrument must declare how it is updated")
            continue
        model = policy["model"]
        if not policy.get("label"):
            fail.append(f"{name}: update_policy has no label; the page renders "
                        f"its cadence copy from this field")

        stamp = dataset_date(data, policy, ds)
        age = None
        if stamp:
            try:
                age = (today - datetime.date.fromisoformat(stamp)).days
            except ValueError:
                fail.append(f"{name}: unreadable date {stamp!r}")

        # 2. scheduled must declare a cadence, and is failed when stale past it
        if model == "scheduled":
            days = policy.get("cadence_days")
            if not days:
                fail.append(f"{name}: model 'scheduled' must declare cadence_days")
            elif age is not None and age > days:
                fail.append(f"{name}: scheduled every {days}d but the data is "
                            f"{age}d old - update it, or change the model")

        # 3. live must have an automated refresh path and a freshness threshold
        if model == "live":
            path = policy.get("refresh_path")
            hours = policy.get("freshness_hours")
            if not path or not os.path.exists(os.path.join(ROOT, path)):
                fail.append(f"{name}: model 'live' needs refresh_path pointing at "
                            f"a real automated job (got {path!r})")
            if not hours:
                fail.append(f"{name}: model 'live' must declare freshness_hours")
            elif age is not None and age * 24 > hours:
                fail.append(f"{name}: labelled live with a {hours}h threshold, but "
                            f"the data is {age * 24}h old - the automated refresh "
                            f"has stopped and the page still says live")

        # 4. event_driven is never failed for age, but must show its last date
        if model == "event_driven":
            if ds in DERIVED:
                if not stamp:
                    fail.append(f"{name}: no {DERIVED[ds][1]} on any row, so the "
                                f"register cannot show how current it is")
                else:
                    note.append(f"{name}: event-driven, newest evidence {age}d old "
                                f"({stamp}), derived from the rows")
            elif not policy.get("last_verified"):
                fail.append(f"{name}: model 'event_driven' must declare "
                            f"last_verified - a reader has no other way to judge "
                            f"the age of the record")
            elif age is not None:
                note.append(f"{name}: event-driven, last verified {age}d ago "
                            f"(not a failure - that is the model)")

        # 5. the page must not carry a cadence claim in prose. The copy comes
        #    from update_policy, so any hardcoded cadence is by definition a
        #    second source of truth that can drift.
        html = open(os.path.join(ROOT, page), encoding="utf-8").read()
        for pattern in BANNED_PROSE:
            if re.search(pattern, html):
                fail.append(f"{page}: hardcoded cadence claim {pattern!r} - render "
                            f"it from update_policy.label instead")
        if policy.get("badge") and "badge" not in html:
            note.append(f"{page}: declares a badge but the page has no badge element")

    for line in note:
        print(f"  ..  {line}")
    if fail:
        print("\nCADENCE CHECK FAILED\n")
        for f in fail:
            print(f"  {f}")
        return 1
    print(f"  ok  {len(INSTRUMENTS)} instruments declare and honour their update model")
    return 0


if __name__ == "__main__":
    sys.exit(main())
