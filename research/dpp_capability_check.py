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
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTER = ROOT / 'research' / 'dpp-suppliers.json'
CAPABILITY = ROOT / 'research' / 'dpp-capability.json'

# capability-framework.md, rule 5.
EXEMPT_TYPES = {'project-consortium', 'standards-body', 'not-a-supplier'}

# NO FRESHNESS THRESHOLD, AND THAT IS A CORRECTION.
#
# This file shipped with FRESH_DAYS = 7 and failed every Monday because the
# research was 19 days old. That rule was invented here: the register declares
# `event_driven` - "Updated when the evidence changes" - and the capability
# layer declares no cadence at all. "Run a check once a week" meant run the
# CHECK weekly, not re-do the research weekly, which is a manual batch and
# never was weekly.
#
# A gate that fails every week for a condition nobody agreed to is the gate
# that teaches you to ignore the gate. The age is reported as a measured fact.
# If the layer ever declares a cadence, honour that one rather than this file's
# opinion.
DECLARED_CADENCE_DAYS = None

UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')

# THE ONLY CODES THAT SAY THE PAGE IS NOT THERE.
#
# This set is what turns the weekly job red, so it has to mean exactly what it
# says. 404 and 410 are the server asserting absence. Every other 4xx is the
# server refusing THIS CLIENT, which is a different sentence and not one we can
# fix by editing the register.
#
# It used to be "any 4xx that is not 403 or 429", and on 31 August 2026 that
# failed the job on a live page. The Worldline citation returned 406 from the
# GitHub runner and the report read "the page is gone, not merely unreachable".
# MEASURED the same morning: with this module's own UA the page returns 200 and
# serves the article; only curl's default UA gets 406, and the runner is
# refused on top of that because it fetches from a datacentre range. Nothing
# about the citation had changed.
#
# The module's own docstring is the argument for keeping this narrow: "A
# citation checker whose false positives look exactly like its true positives
# is worse than no checker: it trains you to skim the output."
GONE_CODES = (404, 410)


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
    # 30 SECONDS, MEASURED, NOT PICKED. peftrust.com answers in 16 to 18
    # seconds; at 25 under eight-way contention it tipped over and reported a
    # live page as dead. The timeout is set above the slowest citation we
    # actually publish, not at a round number that felt generous.
    def once():
        r = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '-L',
             '--max-time', '30', '-A', UA, url],
            capture_output=True, text=True)
        try:
            return int((r.stdout or '0').strip())
        except ValueError:
            return 0

    code = once()

    # ONE TRANSIENT FAILURE IS NOT A DEAD CITATION, and this check publishes an
    # alarm about a named company. Running 215 fetches eight at a time makes a
    # slow host time out sometimes: two peftrust.com URLs returned 0 in one
    # sweep and 200 on the very next request. Without a retry this reports
    # "4 DEAD" one run and "2 DEAD" the next, which is the same flakiness that
    # makes a checker unreadable.
    #
    # A 404 is definitive and is not retried - the page is gone, asking again
    # cannot change that. Only a connection failure, a rate limit or a server
    # error gets a second chance.
    if code == 0 or code == 429 or code >= 500:
        time.sleep(2)
        second = once()
        if second != code:
            code = second

    # A 4xx that is not 404/410 is very often bot protection or content
    # negotiation rather than a dead page. Reported, never counted as broken -
    # the register was bitten once by calling an ISO page dead when a human
    # browser loads it fine, and again on 31 Aug 2026 by a 406 on a live page.
    note = ('refused this client?' if 400 <= code < 500 and code not in GONE_CODES
            else '')
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
        print(f'  newest research is             {age} days old'
              + ('' if DECLARED_CADENCE_DAYS else '   (no cadence declared)'))
        if DECLARED_CADENCE_DAYS and age > DECLARED_CADENCE_DAYS:
            faults.append(f'the newest capability research is {age} days old, '
                          f'past the declared {DECLARED_CADENCE_DAYS} days')
    print()

    if args.links:
        results = check_links(cap)
        bad = [(u, c, n) for u, c, n in results if c == 0 or c >= 400]
        soft = [x for x in bad if 400 <= x[1] < 500 and x[1] not in GONE_CODES]
        # A 5xx or a connection failure means the HOST is failing right now. It
        # does not establish that the evidence was removed, and we cannot fix
        # somebody else's outage. fabacus.com returned 500 on both citations
        # AND on its own root domain the morning this was written - the site
        # was down, the pages were not gone.
        unreachable = [x for x in bad if x[1] == 0 or x[1] >= 500]
        # Only a code that ASSERTS ABSENCE says the page itself is gone.
        hard = [x for x in bad if x[1] in GONE_CODES]
        print(f'  citations re-fetched           {len(results)}')
        print(f'  resolved                       {len(results) - len(bad)}')
        if soft:
            print(f'  refused a scripted fetch       {len(soft)} '
                  '(bot protection or content negotiation; the page is not gone)')
            for u, c, _ in soft[:8]:
                print(f'     {c}  {u}')
        if unreachable:
            print(f'  host unreachable today         {len(unreachable)}')
            for u, c, n in unreachable[:10]:
                root = re.match(r'(https?://[^/]+)', u)
                whole = ''
                if root:
                    rc = fetch(root.group(1))[1]
                    whole = ('  (the whole site is down: root also '
                             f'{rc})') if rc == 0 or rc >= 500 else '  (root responds)'
                print(f'     {c or "ERR"}  {u}{whole}')
            print('     Reported, not counted as dead: a server error is the '
                  'host failing, not the evidence removed.')
        if hard:
            faults.append(f'{len(hard)} published citation(s) return 4xx - the '
                          f'page is gone, not merely unreachable')
            print(f'  GONE                           {len(hard)}')
            for u, c, n in hard[:15]:
                print(f'     {c}  {u}  {n}')
    else:
        n = len({r['evidence_url'] for r in cap['results'] if r.get('evidence_url')})
        print(f'  {n} citations not re-fetched (pass --links)')

    print()

    # WHAT MAKES THIS JOB GO RED, and why the list is short.
    #
    # A red run must mean "something is wrong that we can fix". The coverage
    # gap is an open research decision - whether the ten checks apply to a
    # consultancy - and failing on it every Monday until somebody rules would
    # train everyone to ignore the mail. It is reported, loudly, and it does
    # not go red.
    #
    # Red is reserved for: a page we cite has GONE, or the layer carries
    # findings the framework says it should not. Both are ours, both are
    # fixable, and neither can be ignored.
    blocking = [f for f in faults
                if 'page is gone' in f or 'should not be assessed' in f]
    reported = [f for f in faults if f not in blocking]

    if reported:
        print('REPORTED, not failing')
        for f in reported:
            print('  .. ' + f)
        print()
    if blocking:
        print('FAULTS')
        for f in blocking:
            print('  ! ' + f)
        print()
        return 1 if args.check else 0
    print('  no published citation has gone, and no exempt row carries findings')
    return 0


if __name__ == '__main__':
    sys.exit(main())
