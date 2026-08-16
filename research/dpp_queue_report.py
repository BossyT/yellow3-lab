#!/usr/bin/env python3
"""
Report how many DPP register submissions are waiting, and how long they have
waited. Counts and ages only.

WHY. The register accepts submissions all day: /research/.../suppliers/add is
live, api/suggest.js writes dpp/suggestions/<domain>.json with status "queued",
and the company gets a confirmation. The runbook says a scheduled agent turns
those into rows. Nothing schedules it. The intake log's last entry is 31 July
2026, and on 16 August nobody could say whether anything was waiting, because
nothing looked.

That is the failure worth fixing first. Not the processing - the SILENCE. A
company that submitted and heard nothing is a worse outcome than a slow queue,
and people rely on this register; the Digital Product Passport buyer platform
reads its data.

NO DOMAINS, NO EMAILS, EVER. The runbook is explicit that companies which were
not recorded are told privately and never appear on a public list, and this
file is committed to the repo. So the report carries counts and ages and
nothing that identifies anyone. If you need to know WHICH company, read the
Blob store directly - that is a deliberate extra step.

    python3 research/dpp_queue_report.py            read /api/queue-status
    python3 research/dpp_queue_report.py --check    read the report, no network

No credentials. /api/queue-status runs inside Vercel where the Blob token
already lives, and returns counts and ages only. Nobody has to copy a secret
anywhere for this to work.
"""

import datetime
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "dpp-intake-queue.md")

# A submission older than this means a company has been waiting a long time for
# an answer it was promised. The build says so rather than letting it pass.
STALE_SUBMISSION_DAYS = 21
# If the report itself stops being written, the reporter has died and we are
# blind again - which is the exact condition this exists to prevent.
STALE_REPORT_DAYS = 3


STATUS_URL = os.environ.get(
    "QUEUE_STATUS_URL", "https://www.yellow3.io/api/queue-status")


def read_endpoint():
    req = urllib.request.Request(STATUS_URL, headers={"User-Agent": "yellow3-queue"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def summarise(items, today):
    """Counts and ages by status. Nothing identifying."""
    by_status, ages = {}, []
    for it in items:
        status = (it.get("status") or "unknown").lower()
        by_status[status] = by_status.get(status, 0) + 1
        if status != "queued":
            continue
        stamp = (it.get("submitted_at") or "")[:10]
        try:
            ages.append((today - datetime.date.fromisoformat(stamp)).days)
        except ValueError:
            ages.append(None)
    known = [a for a in ages if a is not None]
    return {
        "generated": today.isoformat(),
        "total": len(items),
        "by_status": by_status,
        "queued": by_status.get("queued", 0),
        "oldest_queued_days": max(known) if known else None,
        "undated_queued": sum(1 for a in ages if a is None),
    }


def write_report(s):
    lines = [
        "# DPP register - submission queue",
        "",
        "Counts and ages only. No domains, no addresses: the intake runbook is",
        "explicit that companies which were not recorded are told privately and",
        "never appear on a public list, and this file is committed.",
        "",
        "Written by research/dpp_queue_report.py.",
        "",
        f"- generated: {s['generated']}",
        f"- submissions in store: {s['total']}",
        f"- submissions still marked queued: {s['queued']}",
        f"- of those, already in the register: {s.get('already_listed_not_closed', 0)}"
        f"  (bookkeeping, not a company waiting)",
        f"- genuinely awaiting research: **{s.get('awaiting_research', s['queued'])}**",
    ]
    if s["oldest_queued_days"] is not None:
        lines.append(f"- oldest queued: **{s['oldest_queued_days']} days**")
    if s["undated_queued"]:
        lines.append(f"- queued with no submitted_at: {s['undated_queued']}")
    if s["by_status"]:
        lines.append("")
        lines.append("| status | count |")
        lines.append("|---|---|")
        for k in sorted(s["by_status"]):
            lines.append(f"| {k} | {s['by_status'][k]} |")
    lines.append("")
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def read_report():
    if not os.path.exists(OUT):
        return None
    out = {}
    for line in open(OUT, encoding="utf-8"):
        line = line.strip()
        if line.startswith("- generated:"):
            out["generated"] = line.split(":", 1)[1].strip()
        if line.startswith("- genuinely awaiting research:"):
            out["queued"] = int(line.rsplit("**", 2)[1])
        if line.startswith("- oldest queued:"):
            out["oldest"] = int(line.rsplit("**", 2)[1].split()[0])
    return out


def check():
    """Read the committed report. No network, so it runs in the Vercel build."""
    r = read_report()
    if not r:
        print("  ..  no queue report yet - the daily job writes one from "
              "/api/queue-status")
        return 0
    today = datetime.date.today()
    faults = []
    try:
        age = (today - datetime.date.fromisoformat(r["generated"])).days
    except Exception:
        faults.append("queue report has no readable generated date")
        age = None
    if age is not None and age > STALE_REPORT_DAYS:
        faults.append(f"the submission queue has not been checked for {age} days "
                      f"- the reporter has stopped and we are blind to it again")
    oldest = r.get("oldest")
    if oldest is not None and r.get("queued", 0) > 0 and oldest > STALE_SUBMISSION_DAYS:
        faults.append(f"a company has been waiting {oldest} days for an answer it "
                      f"was promised on submission")
    if faults:
        print("\nDPP SUBMISSION QUEUE\n")
        for f in faults:
            print("  " + f)
        return 1
    q = r.get("queued")
    print(f"  ok  submission queue checked {age}d ago"
          + (f", {q} queued" if q is not None else "")
          + (f", oldest {oldest}d" if oldest is not None else ""))
    return 0


def main():
    if "--check" in sys.argv:
        return check()
    try:
        s = read_endpoint()
    except urllib.error.HTTPError as e:
        print(f"  /api/queue-status returned HTTP {e.code}. The queue could not be "
              f"read, which is not the same as an empty queue. Nothing written.")
        return 1
    except Exception as e:
        print(f"  could not reach /api/queue-status: {e}. Nothing written.")
        return 1
    if "error" in s:
        print(f"  the endpoint could not read the store: {s.get('detail')}")
        return 1
    s.setdefault("generated", datetime.date.today().isoformat())
    write_report(s)
    print(f"  {s.get('queued', 0)} queued of {s.get('total', 0)} submissions"
          + (f", oldest {s['oldest_queued_days']} days"
             if s.get("oldest_queued_days") is not None else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
