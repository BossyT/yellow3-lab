#!/usr/bin/env python3
"""
Keep the capability layer justifiable: coverage, staleness and live citations.

WHY THIS EXISTS. The ten checks are RESEARCH. A person opens a page and records
what it says, and dpp_capability_import.py refuses anything the framework does
not allow. That is the register's whole value and none of it can be automated:
a pipeline is perfectly capable of inventing a finding, cheerfully, at scale,
which is the exact risk research/dpp_evidence.py was written for.

SO THIS SCRIPT NEVER PRODUCES A FINDING. It only asks whether what is already
published still stands up:

    coverage   is every row the framework says is assessable, assessed?
    staleness  how old is the newest research, and the oldest?
    links      does every cited evidence_url still resolve?

That is what makes "checked on <date>" defensible a month later. A dead citation
on a published claim about a named company is the failure that matters, and
nothing was watching for it - the layer was generated on 2026-08-05 and nothing
re-read it afterwards.

WHO IS ASSESSABLE, taken from capability-framework.md rather than inferred:

    rule 5  project consortia, standards bodies and not-a-supplier rows are
            never assessed - the checks do not apply to them
    rule 6  a row with no resolved website is not assessed, because you cannot
            check a product you cannot find. Leave it unassessed rather than
            marking ten not_found.

Status is deliberately NOT part of that test. Five acquired companies carry a
full assessment and their findings are still true; gating on status would have
reported them as spurious.

    python3 research/dpp_capability_check.py              coverage + staleness
    python3 research/dpp_capability_check.py --links      also re-fetch citations
    python3 research/dpp_capability_check.py --check      exit non-zero on a fault
"""

import argparse
import concurrent.futures
import datetime as dt
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTER = ROOT / 'research' / 'dpp-suppliers.json'
CAPABILITY = ROOT / 'research' / 'dpp-capability.json'

# capability-framework.md, rule 5.
EXEMPT_TYPES = {'project-consortium', 'standards-body', 'not-a-supplier'}

# How old the newest research may be before the layer stops being something we
# can call current. A week, because that is the cadence Thomas set for it.
FRESH_DAYS = 7

UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')


def load():
    reg = json.loads(REGISTER.read_text(encoding='utf-8'))['suppliers']
    cap = json.loads(CAPABILITY.read_text(encoding='utf-8'))
    return reg, cap


def assessable(row):
    """Framework rules 5 and 6. Nothing else."""
    return row.get('entity_type') not in EXEMPT_TYPES and bool(row.get('website'))


def coverage(reg, cap):
    assessed = {r['supplier_id'] for r in cap['results']}
    should = [r for r in reg if assessable(r)]
    missing = [r for r in should if r['id'] not in assessed]
    # A row that carries findings while the framework says it should not be
    # assessed is the other direction of the same fault, and worth knowing.
    stray = sorted(assessed - {r['id'] for r in should})
    return should, missing, stray


def staleness(cap, today):
    dates = sorted({r['checked_date'] for r in cap['results'] if r.get('checked_date')})
    if not dates:
        return None, None, None
    oldest = dt.date.fromisoformat(dates[0])
    newest = dt.date.fromisoformat(dates[-1])
    return oldest, newest, (today - newest).days


def fetch(url):
    """curl, not urllib, and that is not a style preference.

    urllib reported three live sites as dead with
    TLSV1_ALERT_PROTOCOL_VERSION - cycle-platform.com, hub.traceaware.io and
    status.retraced.com all load perfectly in a browser and return 200 to curl.
    A citation checker whose false positives look exactly like its true
    positives is worse than no checker: it trains you to skim the output. curl
    negotiates what those hosts actually speak.

    Follows redirects, because a citation that has moved is still a citation
    that resolves.
    """
    r = subprocess.run(
        ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '-L',
         '--max-time', '25', '-A', UA, url],
        capture_output=True, text=True)
    try:
        code = int((r.stdout or '0').strip())
    except ValueError:
        code = 0
    # 403/429 is very often bot protection rather than a dead page. Reported,
    # never counted as broken - the register was bitten once by calling an ISO
    # page dead when a human browser loads it fine.
    note = 'bot protection?' if code in (403, 429) else ''
    return url, code, note


def check_links(cap):
    urls = sorted({r['evidence_url'] for r in cap['results'] if r.get('evidence_url')})
    out = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for url, code, note in ex.map(fetch, urls):
            out.append((url, code, note))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--links', action='store_true',
                    help='re-fetch every cited evidence_url (slow, network)')
    ap.add_argument('--check', action='store_true',
                    help='exit non-zero if a fault is found')
    ap.add_argument('--today', default=None, help='override today, for testing')
    args = ap.parse_args()

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    reg, cap = load()
    faults = []

    print('CAPABILITY LAYER CHECK')
    print('=' * 62)
    print(f'  layer generated {cap.get("generated")}, '
          f'{len(cap["results"])} results over {cap.get("suppliers_assessed")} suppliers')
    print()

    should, missing, stray = coverage(reg, cap)
    print(f'  assessable per the framework   {len(should)}')
    print(f'  assessed                       {len(should) - len(missing)}')
    if missing:
        from collections import Counter
        kinds = Counter(r.get('entity_type') for r in missing)
        faults.append(f'{len(missing)} assessable row(s) have no capability checks: '
                      + ', '.join(f'{n} {k}' for k, n in kinds.most_common()))
        print(f'  NOT ASSESSED                   {len(missing)}')
        for r in missing[:20]:
            print(f'     {r["id"]:<28} {r.get("entity_type","")}')
        if len(missing) > 20:
            print(f'     ... and {len(missing) - 20} more')
    else:
        print('  every assessable row is assessed')
    if stray:
        faults.append(f'{len(stray)} row(s) carry findings the framework says '
                      f'should not be assessed: {", ".join(stray[:5])}')
    print()

    oldest, newest, age = staleness(cap, today)
    if newest is None:
        faults.append('no check carries a date')
    else:
        print(f'  research dates                 {oldest} to {newest}')
        print(f'  newest research is             {age} days old')
        if age > FRESH_DAYS:
            faults.append(f'the newest capability research is {age} days old '
                          f'(over {FRESH_DAYS}); the layer is published as current')
    print()

    if args.links:
        results = check_links(cap)
        dead = [(u, c, n) for u, c, n in results if c == 0 or c >= 400]
        soft = [x for x in dead if x[1] in (403, 429)]
        hard = [x for x in dead if x[1] not in (403, 429)]
        print(f'  citations re-fetched           {len(results)}')
        print(f'  resolved                       {len(results) - len(dead)}')
        if soft:
            print(f'  refused a scripted fetch       {len(soft)} (likely bot protection)')
            for u, c, _ in soft[:8]:
                print(f'     {c}  {u}')
        if hard:
            faults.append(f'{len(hard)} published citation(s) no longer resolve')
            print(f'  BROKEN                         {len(hard)}')
            for u, c, n in hard[:15]:
                print(f'     {c or "ERR"}  {u}  {n}')
    else:
        n = len({r['evidence_url'] for r in cap['results'] if r.get('evidence_url')})
        print(f'  {n} citations not re-fetched (pass --links)')

    print()
    if faults:
        print('FAULTS')
        for f in faults:
            print('  ! ' + f)
        print()
        return 1 if args.check else 0
    print('  the capability layer holds up')
    return 0


if __name__ == '__main__':
    sys.exit(main())
