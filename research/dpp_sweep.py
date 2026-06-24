#!/usr/bin/env python3
"""
Digital Product Passport (DPP) instrument - weekly sweep helper.

What this does (the deterministic, no-judgement part):
  - recomputes Score_A (regulator delivery) and Score_B (industry readiness)
    from the data, so the displayed scores can never drift from the milestones
    and signals beneath them;
  - recomputes call_record (hits-misses) from the graded calls;
  - flags calls whose resolution_date has passed but are still ungraded;
  - flags milestones whose target_date has passed but are still upcoming /
    in_progress (i.e. they need a status decision: delivered / slipped);
  - stamps week_of + last_checked;
  - appends an entry to research/dpp-changelog.md (append-only).

What this does NOT do (the judgement part - that stays with the operator,
see research/dpp-sweep.md): it does not scrape EUR-Lex / the Commission /
CEN-CENELEC, and it does not decide whether a call is a HIT or a MISS. You
read the sources, decide, and pass the decision in with --grade / --status.

Scoring (single source of truth):
  Score_A = 100 * sum(weight_i * state_i for DUE milestones) / sum(weight_i for DUE)
            state: delivered_on_time=1.0  delivered_late=0.5  slipped/missed=0.0
            "due" = target_date <= as-of date; upcoming/in_progress excluded.
  Score_B = 100 * mean over signals with a value of (value / ceiling), weighted.

Usage:
  # dry-run report (default - changes nothing):
  python3 research/dpp_sweep.py
  python3 research/dpp_sweep.py --date 2026-06-30

  # record the first graded call on/after 30 Jun and write everything:
  python3 research/dpp_sweep.py --date 2026-06-30 \
      --grade c2=miss \
      --note c2="Resolution date passed with the service-provider delegated act still a draft; not adopted." \
      --evidence c2=https://eur-lex.europa.eu/... \
      --headline "First call graded: the EU missed its own service-provider deadline." \
      --write
"""
import json, sys, argparse, datetime, os

HERE = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(HERE, "digital-product-passport.json")
LOG_PATH = os.path.join(HERE, "dpp-changelog.md")

STATE_SCORE = {"delivered_on_time": 1.0, "delivered_late": 0.5, "slipped": 0.0, "missed": 0.0}
DUE_BUT_OPEN = {"upcoming", "in_progress"}


def score_a(milestones, asof):
    num = den = 0.0
    for m in milestones:
        td = datetime.date.fromisoformat(m["target_date"])
        if td <= asof and m["status"] in STATE_SCORE:
            num += m["weight"] * STATE_SCORE[m["status"]]
            den += m["weight"]
    return round(100 * num / den) if den else 0


def score_b(signals):
    counted = [s for s in signals if s.get("value") is not None]
    if not counted:
        return 0
    num = sum((s["value"] / s["ceiling"]) * s.get("weight", 1) for s in counted)
    den = sum(s.get("weight", 1) for s in counted)
    return round(100 * num / den)


def call_record(calls):
    hits = sum(1 for c in calls if c.get("resolved") and c.get("outcome") == "hit")
    misses = sum(1 for c in calls if c.get("resolved") and c.get("outcome") == "miss")
    return {"hits": hits, "misses": misses}


def kvpairs(items):
    out = {}
    for it in items or []:
        if "=" not in it:
            sys.exit("expected ID=VALUE, got: " + it)
        k, v = it.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def main():
    p = argparse.ArgumentParser(description="DPP instrument weekly sweep helper")
    p.add_argument("--date", help="as-of date YYYY-MM-DD (default: today)")
    p.add_argument("--grade", action="append", help="ID=hit|miss (repeatable)")
    p.add_argument("--note", action="append", help="ID=grading note text (repeatable)")
    p.add_argument("--evidence", action="append", help="ID=url (repeatable)")
    p.add_argument("--status", action="append", help="milestoneID=new_status (repeatable)")
    p.add_argument("--headline", help="new this-week headline")
    p.add_argument("--body", help="new this-week body")
    p.add_argument("--write", action="store_true", help="apply changes + append changelog")
    a = p.parse_args()

    asof = datetime.date.fromisoformat(a.date) if a.date else datetime.date.today()
    d = json.load(open(JSON_PATH))
    by_call = {c["id"]: c for c in d["calls"]}
    by_ms = {m["id"]: m for m in d["milestones"]}
    changes = []

    # apply milestone status decisions
    for mid, st in kvpairs(a.status).items():
        if mid not in by_ms:
            sys.exit("unknown milestone: " + mid)
        old = by_ms[mid]["status"]
        by_ms[mid]["status"] = st
        by_ms[mid]["last_checked"] = asof.isoformat()
        changes.append(f"milestone {mid}: status {old} -> {st}")

    # apply call gradings
    grades = kvpairs(a.grade)
    notes = kvpairs(a.note)
    evid = kvpairs(a.evidence)
    for cid, outcome in grades.items():
        if cid not in by_call:
            sys.exit("unknown call: " + cid)
        if outcome not in ("hit", "miss"):
            sys.exit("outcome must be hit|miss, got: " + outcome)
        c = by_call[cid]
        c["resolved"] = True
        c["outcome"] = outcome
        if cid in notes:
            c["grading_note"] = notes[cid]
        if cid in evid:
            c["evidence_url"] = evid[cid]
        changes.append(f"call {cid}: graded {outcome.upper()}")
    for cid, n in notes.items():
        if cid not in grades:
            by_call[cid]["grading_note"] = n
    for cid, u in evid.items():
        if cid not in grades:
            by_call[cid]["evidence_url"] = u

    if a.headline:
        d["this_week_read"]["headline"] = a.headline
        changes.append("this-week headline updated")
    if a.body:
        d["this_week_read"]["body"] = a.body

    # recompute (always)
    A, B = score_a(d["milestones"], asof), score_b(d["signals"])
    rec = call_record(d["calls"])
    if A != d["scores"]["regulator_delivery"]:
        changes.append(f"Score_A {d['scores']['regulator_delivery']} -> {A}")
    if B != d["scores"]["industry_readiness"]:
        changes.append(f"Score_B {d['scores']['industry_readiness']} -> {B}")
    if rec != d["call_record"]:
        changes.append(f"call_record {d['call_record']['hits']}-{d['call_record']['misses']} -> {rec['hits']}-{rec['misses']}")
    d["scores"]["regulator_delivery"] = A
    d["scores"]["industry_readiness"] = B
    d["call_record"] = rec
    d["week_of"] = (asof - datetime.timedelta(days=asof.weekday())).isoformat()
    d["last_checked"] = asof.isoformat()

    # flags that need a human / agent decision
    due_calls = [c["id"] for c in d["calls"]
                 if not c.get("resolved")
                 and datetime.date.fromisoformat(c["resolution_date"]) <= asof]
    due_ms = [m["id"] for m in d["milestones"]
              if m["status"] in DUE_BUT_OPEN
              and datetime.date.fromisoformat(m["target_date"]) <= asof]

    print(f"DPP sweep - as of {asof.isoformat()}  (week_of {d['week_of']})")
    print(f"  Score_A (regulator) : {A}")
    print(f"  Score_B (industry)  : {B}")
    print(f"  Call record         : {rec['hits']}-{rec['misses']}")
    print(f"  Calls DUE FOR GRADING (resolution date passed, still open): {due_calls or 'none'}")
    print(f"  Milestones PAST DATE but still open (decide status)       : {due_ms or 'none'}")
    if changes:
        print("  Changes this run: " + "; ".join(changes))

    if not a.write:
        print("\n(dry run - nothing written. re-run with --write to apply.)")
        return

    json.dump(d, open(JSON_PATH, "w"), indent=2, ensure_ascii=False)
    open(JSON_PATH, "a").write("\n")
    entry = f"- **{asof.isoformat()}** (week_of {d['week_of']}) - " + (
        "; ".join(changes) if changes else "sweep: no material change") + \
        f". Score_A {A}, Score_B {B}, record {rec['hits']}-{rec['misses']}.\n"
    if not os.path.exists(LOG_PATH):
        open(LOG_PATH, "w").write("# DPP instrument - sweep changelog\n\nAppend-only. Newest at the bottom.\n\n")
    open(LOG_PATH, "a").write(entry)
    print(f"\nWritten: {os.path.basename(JSON_PATH)} + appended to {os.path.basename(LOG_PATH)}")


if __name__ == "__main__":
    main()
