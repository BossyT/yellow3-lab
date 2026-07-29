#!/usr/bin/env python3
"""The submission queue, for an agent to drain without a human.

`api/suggest.js` writes each submission to Blob at dpp/suggestions/<domain>.json.
This lists them and closes them. It never decides anything - dpp_intake.py does
that - and it never publishes anything.

  python3 research/dpp_queue.py --pending
  python3 research/dpp_queue.py --close acme.com recorded
  python3 research/dpp_queue.py --close acme.com not_recorded

Needs BLOB_PUBLIC_RW_TOKEN in the environment, the same token the site uses.
Stdlib only, so it runs anywhere the rest of this repo runs.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://blob.vercel-storage.com"
PREFIX = "dpp/suggestions/"
OUTCOMES = ("recorded", "not_recorded", "already_listed")


def token():
    t = os.environ.get("BLOB_PUBLIC_RW_TOKEN") or os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not t:
        sys.exit("BLOB_PUBLIC_RW_TOKEN is not set - it is in the Vercel project env.")
    return t


def public_base():
    parts = token().split("_")
    if len(parts) < 4:
        sys.exit("BLOB token is malformed")
    return "https://" + parts[3] + ".public.blob.vercel-storage.com/"


def req(url, method="GET", data=None, headers=None):
    r = urllib.request.Request(url, method=method, data=data)
    r.add_header("authorization", "Bearer " + token())
    for k, v in (headers or {}).items():
        r.add_header(k, v)
    with urllib.request.urlopen(r, timeout=30) as resp:
        return resp.read()


def listing():
    """Every submission blob, newest listing order not guaranteed."""
    out, cursor = [], ""
    for _ in range(20):
        url = API + "/?prefix=" + PREFIX + "&limit=1000" + (("&cursor=" + cursor) if cursor else "")
        payload = json.loads(req(url))
        out.extend(payload.get("blobs", []))
        cursor = payload.get("cursor") or ""
        if not payload.get("hasMore"):
            break
    return out


def fetch(pathname):
    try:
        return json.loads(req(public_base() + pathname))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def put(pathname, obj):
    req(API + "/" + pathname, method="PUT",
        data=json.dumps(obj).encode("utf-8"),
        headers={"x-api-version": "7", "x-content-type": "application/json",
                 "x-add-random-suffix": "0", "x-cache-control-max-age": "0"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pending", action="store_true", help="list submissions awaiting research")
    ap.add_argument("--all", action="store_true", help="list every submission, any status")
    ap.add_argument("--close", nargs=2, metavar=("DOMAIN", "OUTCOME"),
                    help="mark a submission " + " | ".join(OUTCOMES))
    args = ap.parse_args()

    if args.close:
        domain, outcome = args.close[0].lower().strip(), args.close[1]
        if outcome not in OUTCOMES:
            sys.exit("outcome must be one of: " + ", ".join(OUTCOMES))
        path = PREFIX + domain + ".json"
        rec = fetch(path)
        if not rec:
            sys.exit("no submission for " + domain)
        rec["status"] = outcome
        put(path, rec)
        print(f"{domain} -> {outcome}")
        return

    rows = []
    for b in listing():
        name = b.get("pathname", "")
        if not name.endswith(".json") or name.endswith("_index.json"):
            continue
        rec = fetch(name)
        if not rec:
            continue
        if args.all or rec.get("status") == "queued":
            rows.append(rec)

    if not rows:
        print("nothing queued")
        return
    rows.sort(key=lambda r: r.get("submitted_at", ""))
    print(f"{'submitted':12} {'domain':32} {'status':14} company")
    for r in rows:
        print(f"{r.get('submitted_at',''):12} {r.get('domain',''):32} "
              f"{r.get('status',''):14} {r.get('company','')}")
    print(f"\n{len(rows)} submission(s). Research each per research/dpp-intake-runbook.md, "
          f"then close it.")


if __name__ == "__main__":
    main()
