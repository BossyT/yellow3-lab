#!/usr/bin/env python3
"""Record WHAT WE LOOKED AT for every `not_found` capability finding.

A `not_found` says "we looked on this date and found nothing public". Until now
the register carried the date and nothing else - no domains, no pages, no terms,
no reason. That is the gap Sven Boeckelmann identified from outside on 2026-08-05,
and it is also what the Decision Engine requires before a not_found can become
`not_established`.

THE RECORD CANNOT BE RECONSTRUCTED. What was searched in July was not written
down, and inventing it now would fabricate exactly the evidence this record
exists to supply. So this sweep looks again, today, and records what it actually
does - dated today, honest about being a fresh look rather than a reconstruction.

It is deliberately a REPORTER. It never changes a finding. Where it turns up
something the July sweep missed, it says so and a human decides.

  python3 research/dpp_search_sweep.py --limit 5      # try it on five suppliers
  python3 research/dpp_search_sweep.py                # the whole assessed set
"""
import argparse
import concurrent.futures as cf
import datetime
import html
import json
import os
import re
import ssl
import subprocess
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Where each check's evidence would live if it existed. These ARE the search
# terms, recorded per finding, so the record says what was looked for.
CHECKS = {
 "c01": ("Standards mapping",
         ["EN 18216", "EN 18219", "EN 18223", "JTC 24", "CEN/CENELEC", "field mapping"],
         ["/standards", "/docs", "/compliance", "/developers", "/documentation"]),
 "c02": ("Evidence architecture",
         ["example passport", "declaration of conformity", "third-party", "notified body",
          "verified by", "certificate"],
         ["/passport", "/demo", "/example", "/docs", "/schema"]),
 "c03": ("Identity portability",
         ["GS1 Digital Link", "resolver", "keep resolving", "after termination", "GTIN"],
         ["/resolver", "/gs1", "/docs", "/terms", "/integrations"]),
 "c04": ("Model / batch / item",
         ["model", "batch", "item", "serial", "lot", "granularity"],
         ["/docs", "/api", "/developers", "/schema"]),
 "c05": ("Clean export",
         ["export", "data export", "JSON", "CSV", "on termination", "bulk"],
         ["/terms", "/docs", "/api", "/legal", "/pricing"]),
 "c06": ("Regulatory pace",
         ["changelog", "release notes", "version", "roadmap"],
         ["/changelog", "/releases", "/updates", "/whats-new", "/roadmap"]),
 "c07": ("EU DPP Registry",
         ["EU DPP Registry", "registered passport", "registry integration"],
         ["/registry", "/compliance", "/espr", "/docs"]),
 "c08": ("Passport afterlife",
         ["retention", "remains accessible", "after cancellation", "archive", "years"],
         ["/terms", "/legal", "/docs", "/trust"]),
 "c09": ("Role-based disclosure",
         ["role", "access level", "restricted", "consumer", "recycler", "customs"],
         ["/docs", "/platform", "/features", "/api"]),
 "c10": ("Resolver uptime",
         ["uptime", "status page", "availability", "incident history", "SLA"],
         ["/status", "/uptime", "/sla", "/trust"]),
}
COMMON = ["", "/docs", "/documentation", "/developers", "/api", "/terms", "/legal",
          "/pricing", "/platform", "/product", "/resources"]


def get(url):
    """Return (status, text). status is an HTTP code, 0 for unreachable."""
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}),
                                   timeout=12, context=CTX)
        body = r.read(500_000).decode(r.headers.get_content_charset() or "utf-8", "replace")
        if len(body) > 2500:
            return r.getcode(), text_of(body)
        code = r.getcode()
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        code = 0
    try:
        o = subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-sandbox",
                            "--virtual-time-budget=7000", "--dump-dom", url],
                           capture_output=True, timeout=40)
        return (code or 200), text_of(o.stdout.decode("utf-8", "replace"))
    except Exception:
        return code, ""


def text_of(h):
    h = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?is)<br\s*/?>|</(p|div|li|h[1-6]|td|tr)>", "\n", h)
    return html.unescape(re.sub(r"(?s)<[^>]+>", " ", h))


def sweep(row):
    """Look at one supplier and produce a search record per open check."""
    site = (row.get("website") or "").rstrip("/")
    if not site:
        return row["id"], {}, {}

    paths, seen = list(COMMON), set()
    for _, _, extra in CHECKS.values():
        paths += extra
    paths = [p for p in paths if not (p in seen or seen.add(p))][:22]

    pages, corpus, blocked = [], [], 0
    for p in paths:
        code, t = get(site + p)
        pages.append({"url": site + p, "status": code})
        if code in (401, 403, 429):
            blocked += 1
        if t:
            corpus.append(t)
    blob = "\n".join(corpus)

    records, candidates = {}, {}
    for cid, (name, terms, _) in CHECKS.items():
        hits = []
        for s in re.split(r"(?<=[.!?])\s+", " ".join(blob.split())):
            if 40 <= len(s) <= 280 and any(t.lower() in s.lower() for t in terms):
                hits.append(s)
            if len(hits) >= 3:
                break
        outcome = ("access_blocked" if blocked >= max(3, len(paths) // 3)
                   else "nothing_public" if not blob
                   else "ambiguous" if hits else "nothing_public")
        records[cid] = {
            "checked_date": datetime.date.today().isoformat(),
            "agent": "yellow3 lab register sweep",
            "domains_inspected": [re.sub(r"^https?://", "", site).split("/")[0]],
            "pages_reviewed": pages,
            "search_terms": terms,
            "outcome": outcome,
            "limitations": ("some pages refused our user agent"
                            if blocked else
                            "own domain only; evidence published elsewhere is not covered here"),
        }
        if hits:
            candidates[cid] = hits
    return row["id"], records, candidates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(HERE, "dpp-search-records.json"))
    args = ap.parse_args()

    sup = {r["id"]: r for r in json.load(
        open(os.path.join(HERE, "dpp-suppliers.json"), encoding="utf-8"))["suppliers"]}
    cap = json.load(open(os.path.join(HERE, "dpp-capability.json"), encoding="utf-8"))["results"]

    open_checks = {}
    for r in cap:
        if r["state"] == "not_found":
            open_checks.setdefault(r["supplier_id"], set()).add(r["check_id"])
    targets = [sup[i] for i in open_checks if i in sup and (sup[i].get("website") or "").strip()]
    if args.limit:
        targets = targets[:args.limit]
    print(f"{len(targets)} suppliers with open checks and a website "
          f"({sum(len(v) for v in open_checks.values())} not_found findings in total)")

    out, review, done = {}, {}, 0
    with cf.ThreadPoolExecutor(max_workers=5) as ex:
        for sid, records, candidates in ex.map(sweep, targets):
            keep = {c: r for c, r in records.items() if c in open_checks.get(sid, ())}
            if keep:
                out[sid] = keep
            hot = {c: h for c, h in candidates.items() if c in open_checks.get(sid, ())}
            if hot:
                review[sid] = hot
            done += 1
            if done % 10 == 0:
                print(f"  {done}/{len(targets)}")

    json.dump({"generated": datetime.date.today().isoformat(), "records": out},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(review, open(args.out.replace(".json", "-review.json"), "w",
                           encoding="utf-8"), ensure_ascii=False, indent=1)
    n = sum(len(v) for v in out.values())
    print(f"\n{n} search records written for {len(out)} suppliers")
    print(f"{sum(len(v) for v in review.values())} findings turned up a candidate sentence "
          f"the July sweep did not record - FOR HUMAN REVIEW, nothing changed")


if __name__ == "__main__":
    main()
