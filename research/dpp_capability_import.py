#!/usr/bin/env python3
"""Import a capability batch, with the framework's rules enforced.

The capability layer is the register's most exposed claim: ten findings about a
named company, published. So the import refuses anything the framework does not
allow, rather than trusting the researcher - the same reason dpp_intake.py exists.

Rules, from capability-framework.md:
  - three states only: verified | company_states | not_found. Never a fourth.
  - `verified` means we opened an artifact: it needs an evidence_url AND a
    one-line description of what that artifact IS.
  - `company_states` needs the URL where they say it.
  - `not_found` carries a date and NO url - if there is a url, it is not
    "we looked and found nothing".
  - check c02 `not_found` must say which of the two situations applies: no public
    example passport exists at all, or one exists and does not separate claim /
    document / third-party verification.
  - a supplier_id must exist in the register, and non-commercial rows are never
    assessed at all.

Usage:
  python3 research/dpp_capability_import.py batch.csv          # validate only
  python3 research/dpp_capability_import.py batch.csv --apply  # merge and write
"""

import argparse
import collections
import csv
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAP = os.path.join(HERE, "dpp-capability.json")
DATA = os.path.join(HERE, "dpp-suppliers.json")

STATES = ("verified", "company_states", "not_found")
NON_COMMERCIAL = {"project-consortium", "standards-body", "not-a-supplier"}
MIN_ARTIFACT = 15   # "a page" is not a description of an artifact
CHECKS = ["c%02d" % i for i in range(1, 11)]


def load_register():
    rows = json.load(open(DATA, encoding="utf-8"))["suppliers"]
    return {r["id"]: r for r in rows}


def validate(row, reg, seen):
    """Return a list of problems. Empty list means the row may be imported."""
    bad = []
    sid = (row.get("supplier_id") or "").strip()
    cid = (row.get("check_id") or "").strip()
    state = (row.get("state") or "").strip()
    url = (row.get("evidence_url") or "").strip()
    art = (row.get("artifact") or "").strip()
    date = (row.get("checked_date") or "").strip()
    note = (row.get("note") or "").strip()

    if sid not in reg:
        bad.append("supplier_id is not in the register")
    elif reg[sid]["entity_type"] in NON_COMMERCIAL:
        bad.append("non-commercial rows are not assessed")
    if cid not in CHECKS:
        bad.append("check_id must be c01..c10")
    if (sid, cid) in seen:
        bad.append("duplicate row for this supplier and check")

    if state not in STATES:
        bad.append(f"state '{state}' is not one of {', '.join(STATES)}")
        return bad  # everything below depends on a real state

    if state == "verified":
        if not url:
            bad.append("verified needs the evidence_url of the artifact opened")
        if len(art) < MIN_ARTIFACT:
            bad.append("verified needs a one-line description of what the artifact IS")
    if state == "company_states" and not url:
        bad.append("company_states needs the URL where the company says it")
    if state == "not_found" and url:
        bad.append("not_found must not carry an evidence_url")
    if state == "not_found" and cid == "c02" and len(note) < 10:
        bad.append("c02 not_found must say which situation: no public example "
                   "passport at all, or one that does not separate the three")

    try:
        datetime.date.fromisoformat(date)
    except Exception:
        bad.append("checked_date must be YYYY-MM-DD")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    reg = load_register()
    cap = json.load(open(CAP, encoding="utf-8"))
    existing = {(r["supplier_id"], r["check_id"]): r for r in cap["results"]}

    good, problems, seen = [], [], set()
    with open(args.csv_path, newline="", encoding="utf-8-sig") as fh:
        for i, row in enumerate(csv.DictReader(fh), start=2):
            if not (row.get("state") or "").strip():
                continue  # unfilled row, not an error
            bad = validate(row, reg, seen)
            sid = (row.get("supplier_id") or "").strip()
            cid = (row.get("check_id") or "").strip()
            seen.add((sid, cid))
            if bad:
                problems.append((i, sid, cid, bad))
                continue
            good.append({
                "supplier_id": sid, "check_id": cid,
                "check_name": (row.get("check_name") or "").strip(),
                "state": (row.get("state") or "").strip(),
                "evidence_url": (row.get("evidence_url") or "").strip(),
                "artifact": (row.get("artifact") or "").strip(),
                "checked_date": (row.get("checked_date") or "").strip(),
                "note": (row.get("note") or "").strip(),
            })

    by_state = collections.Counter(r["state"] for r in good)
    sups = sorted({r["supplier_id"] for r in good})
    print(f"{len(good)} valid rows across {len(sups)} suppliers   "
          f"verified {by_state['verified']} / company_states {by_state['company_states']} "
          f"/ not_found {by_state['not_found']}")

    incomplete = [s for s in sups if sum(1 for r in good if r["supplier_id"] == s) != 10]
    if incomplete:
        print(f"\nincomplete suppliers (not 10 checks): {', '.join(incomplete)}")

    if problems:
        print(f"\n{len(problems)} row(s) refused:")
        for line, sid, cid, bad in problems[:40]:
            print(f"  line {line:4} {sid:26} {cid}  {'; '.join(bad)}")
        if len(problems) > 40:
            print(f"  ... and {len(problems) - 40} more")

    if not args.apply:
        print("\nvalidate only - nothing written. Fix the refused rows and re-run "
              "with --apply.")
        return
    if problems:
        sys.exit("\nrefusing to import while rows are invalid. Fix them and re-run.")

    for r in good:
        existing[(r["supplier_id"], r["check_id"])] = r
    results = sorted(existing.values(), key=lambda r: (r["supplier_id"], r["check_id"]))
    totals = collections.Counter(r["state"] for r in results)

    cap["results"] = results
    cap["suppliers_assessed"] = len({r["supplier_id"] for r in results})
    cap["checks_run"] = len(results)
    cap["totals"] = {k: totals.get(k, 0) for k in ("not_found", "company_states", "verified")}
    cap["generated"] = datetime.date.today().isoformat()
    json.dump(cap, open(CAP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\nimported. register now holds {cap['suppliers_assessed']} assessed suppliers, "
          f"{cap['checks_run']} checks: {cap['totals']}")
    print("now run: python3 research/gen_dpp_register.py")


if __name__ == "__main__":
    main()
