#!/usr/bin/env python3
"""/platforms v2 is frozen. This says so in a way a machine can check.

Thomas signed the page off on 12 August 2026. Frozen means it does not change
until a new design package arrives from ChatGPT - not for a tidy-up, not for a
heading fix, not for a class rename.

A note in a handover cannot enforce that. This can: it fingerprints the two
things the sign-off covers - the content inside `.y3-platforms` and the
page-scoped CSS - and fails if either moves.

    python3 research/platforms_freeze.py            did anything move?
    python3 research/platforms_freeze.py --reseal   record a NEW approved state

`--reseal` is deliberately a separate act. If you are running it, you should be
able to name the package that authorised the change.
"""

import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "platforms.html")
SEAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "platforms_freeze.json")


def surfaces():
    html = open(PAGE, encoding="utf-8").read()
    content = html[html.index('<div class="y3-platforms">'):
                   html.index('<footer class="site-footer">')]
    css = html[html.index("/* ---- /platforms"):html.index("</style>")]
    return {
        "content": hashlib.sha256(content.encode()).hexdigest(),
        "css": hashlib.sha256(css.encode()).hexdigest(),
    }


def main():
    now = surfaces()

    if "--reseal" in sys.argv:
        note = " ".join(a for a in sys.argv[1:] if a != "--reseal") or "unspecified"
        json.dump({**now, "authorised_by": note}, open(SEAL, "w"), indent=1)
        print(f"resealed /platforms\n  authorised by: {note}")
        return 0

    if not os.path.exists(SEAL):
        print("no seal recorded - run --reseal with the package that approved this state")
        return 1

    sealed = json.load(open(SEAL))
    moved = [k for k in ("content", "css") if sealed.get(k) != now[k]]
    if not moved:
        print(f"/platforms matches the frozen state\n  approved by: "
              f"{sealed.get('authorised_by', 'unknown')}")
        return 0

    print("/platforms HAS CHANGED and it is frozen.\n")
    for k in moved:
        print(f"  {k}: sealed {sealed.get(k, '-')[:16]}  now {now[k][:16]}")
    print(f"\n  frozen state approved by: {sealed.get('authorised_by', 'unknown')}")
    print("\nIf a new design package authorised this, reseal with its name:")
    print("  python3 research/platforms_freeze.py --reseal <package>")
    return 1


if __name__ == "__main__":
    sys.exit(main())
