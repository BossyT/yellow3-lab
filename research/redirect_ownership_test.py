#!/usr/bin/env python3
"""
Can one generator delete another generator's routes from vercel.json?

    python3 research/redirect_ownership_test.py

WHY THIS FILE EXISTS. Two generators write redirects into the same vercel.json:
gen_dpp_register.py moves indexed supplier profiles, and gen_briefing.py owns
the Monday Briefing's permanent shortcut. Until 2 September 2026 the register
decided what it owned by the path a redirect STARTED with, so every run deleted
everything under /research/digital-product-passport/ - including both briefing
rules. The briefing's permanent route 404ed in production from launch, and the
only reason anyone noticed was a link checker in an unrelated gate.

That is the failure this file exists to make loud. It runs the real
write_redirects() against a real copy of vercel.json and reads the result. It
never writes to the repo's own vercel.json.

Ruled by GPT on 2 September 2026: "That failure must not be able to return
silently."
"""

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_dpp_register as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERCEL = os.path.join(ROOT, "vercel.json")

PASS, FAIL = [], []


def check(rule, cond, detail=""):
    (PASS if cond else FAIL).append(rule)
    print(("  ok    " if cond else "  FAIL  ") + rule
          + (("\n          -> " + detail) if detail and not cond else ""))


def briefing_rules(redirects):
    """The permanent shortcuts, in either language: the undated routes.

    Derived, never hardcoded, so a new locale is covered the day it ships
    rather than the day someone remembers to edit this file.
    """
    out = {}
    for r in redirects:
        src = r.get("source", "")
        if "weekly-briefing" not in src:
            continue
        tail = src.rstrip("/").rsplit("/", 1)[-1]
        if tail == "weekly-briefing":          # undated: the permanent shortcut
            out[src] = r
    return out


def run(seed, ids):
    """write_redirects() against a throwaway vercel.json. Returns the result."""
    fd, tmp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(seed, fh, indent=2)
        real, R.VERCEL = R.VERCEL, tmp
        try:
            R.write_redirects(ids)
        finally:
            R.VERCEL = real
        with open(tmp, encoding="utf-8") as fh:
            return json.load(fh)
    finally:
        os.unlink(tmp)


def main():
    print("\nREDIRECT OWNERSHIP: can the register delete a route it does not own?\n")

    with open(VERCEL, encoding="utf-8") as fh:
        live = json.load(fh)

    # ---- 1. the real file, the real generator -----------------------------
    # The register regenerates on every research pull. The briefing's permanent
    # routes must come out the other side untouched.
    before = briefing_rules(live.get("redirects", []))
    check("vercel.json currently carries the briefing's permanent shortcut",
          len(before) >= 1,
          "no undated weekly-briefing redirect found - either the briefing has "
          "never been published, or something has already eaten it")

    ids = {r["source"].rsplit("/", 1)[-1]
           for r in live.get("redirects", [])
           if r.get("destination", "").startswith(
               "/research/digital-product-passport/suppliers/")}
    after = briefing_rules(run(live, ids).get("redirects", []))

    check("register regeneration preserves every briefing route",
          set(before) == set(after),
          f"lost {sorted(set(before) - set(after))}")
    check("and preserves them byte for byte, target included",
          all(before[s] == after.get(s) for s in before),
          "; ".join(f"{s}: {json.dumps(before[s])} -> {json.dumps(after.get(s))}"
                    for s in before if before[s] != after.get(s)))

    # ---- 2. a synthetic file, so the rules are visible ---------------------
    # Everything the register must keep, and the one thing it must replace.
    briefing = {"source": "/research/digital-product-passport/weekly-briefing",
                "destination": "/research/digital-product-passport/weekly-briefing/2026-08-31",
                "permanent": False}
    pro = {"source": "/research/model-adoption/pro",
           "destination": "/research/model-adoption", "permanent": True}
    stale = {"source": "/research/digital-product-passport/gone-away",
             "destination": "/research/digital-product-passport/suppliers/gone-away",
             "permanent": True}
    unrelated = {"source": "/old-thing", "destination": "/new-thing",
                 "permanent": True}

    out = run({"redirects": [briefing, pro, stale, unrelated]}, {"acme", "beta"})
    got = out.get("redirects", [])
    srcs = {r["source"] for r in got}

    check("a sibling generator's route survives", briefing in got)
    check("an unrelated redirect survives", unrelated in got)
    check("the /pro exception survives", pro in got)
    check("a stale supplier redirect is dropped",
          stale["source"] not in srcs or stale not in got,
          "a profile that left the register kept its redirect")
    check("current supplier profiles get their redirect",
          {"/research/digital-product-passport/acme",
           "/research/digital-product-passport/beta"} <= srcs,
          f"missing from {sorted(srcs)}")
    check("nothing is duplicated",
          len(srcs) == len(got), "the same source is written twice")

    print(f"\n  {len(PASS)} passed, {len(FAIL)} failed\n")
    if FAIL:
        print("  A generator is deleting routes it does not own. Ownership is\n"
              "  decided by where a redirect POINTS, not where it starts:\n"
              "  see write_redirects() in research/gen_dpp_register.py.\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
