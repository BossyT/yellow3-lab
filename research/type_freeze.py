#!/usr/bin/env python3
"""The public yellow3 typography system, enforced.

Locked by Thomas, 2026-08-12, after the family migration and the weight
normalisation:

  - Arial, Helvetica, sans-serif is the public sans system
  - display type at 20px and above uses the LIGHT editorial weight
  - large display tracking follows the /platforms bands
  - small labels, CTA text, navigation and footer keep their stronger weights
  - /platforms is the canonical reference
  - generators and CMS output must preserve the system
  - no new public font or heavy display treatment without design approval

"Same typography system, not identical page geometry." Sizes may differ page to
page - /platforms is 84px and /research is 88px and that is healthy. What may
not differ is the weight philosophy, the family and the tracking logic.

This is the check that makes that a rule rather than a hope. It reads what is on
disk, including the CSS inside generators and the article templates the CMS
writes, so the next regeneration or the next published insight cannot quietly
reintroduce a heavy display or a second font.

    python3 research/type_freeze.py
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"node_modules", ".git", ".vercel", "Autonomous ai software", "img"}
SKIP_ROOT_DIRS = {"reports"}

# admin.html's own interface is not a public page and keeps Manrope. Its
# ARTICLE TEMPLATES are public output, so they are checked - see below.
CHROME_ONLY = {"admin.html"}

# /platforms carries its own seal (research/platforms_freeze.py), which is the
# stronger guard, and it is the reference this system was measured from. It also
# still holds dead shell CSS copied from about.html - `.hero h1`, `.prose h2`,
# `.founder-name` and friends - for classes no element on that page uses, so
# flagging them here would be noise about rules that cannot render. Reported to
# Thomas rather than edited: the page is frozen.
SEALED = {"platforms.html"}

# Families that are allowed to appear on a public page, and why.
ALLOWED = re.compile(
    r"arial|helvetica|sans-serif|serif|monospace|ui-monospace|inherit|"
    r"georgia|times|newsreader|"                 # deliberate editorial serif
    r"sf mono|menlo|consolas|courier|"           # deliberate monospace
    r"-apple-system|blinkmacsystemfont|system-ui|segoe|roboto|"
    r"var\(--", re.I)

BLOCK = re.compile(r"([^{}]+)\{([^{}]*)\}")
SIZE = re.compile(r"font-size\s*:\s*([^;]+)", re.I)
WEIGHT = re.compile(r"font-weight\s*:\s*(\d{3})", re.I)
FAMILY = re.compile(r"font-family\s*:\s*([^;{}]+)", re.I)
PX = re.compile(r"(-?[\d.]+)px")


def biggest_px(value):
    hits = [float(x) for x in PX.findall(value)]
    return max(hits) if hits else None


def check_css(css, where, faults):
    for m in BLOCK.finditer(css):
        selector, body = m.group(1).strip()[:60], m.group(2)

        fam = FAMILY.search(body)
        if fam and not ALLOWED.search(fam.group(1)):
            faults.append((where, f"new font family: {fam.group(1).strip()[:50]}",
                           selector))

        size_m, weight_m = SIZE.search(body), WEIGHT.search(body)
        if not size_m or not weight_m:
            continue
        size = biggest_px(size_m.group(1))
        if size is None or size < 20:
            continue                       # small type keeps its weight, by design
        if int(weight_m.group(1)) >= 600:
            faults.append((where,
                           f"heavy display: {size:.0f}px at weight {weight_m.group(1)}",
                           selector))


def main():
    faults = []
    checked = 0

    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS
                   and not (base == ROOT and d in SKIP_ROOT_DIRS)]
        for name in sorted(names):
            if not name.endswith((".html", ".css", ".py")):
                continue
            if name in {"type_freeze.py", "type_normalise.py", "font_normalise.py"}:
                continue
            if name in SEALED:
                continue
            path = os.path.join(base, name)
            rel = os.path.relpath(path, ROOT)
            text = open(path, encoding="utf-8", errors="replace").read()
            checked += 1

            if name in CHROME_ONLY:
                # Only the templates it publishes, never its own interface.
                for m in re.finditer(r"const html = ['\"`]<!DOCTYPE([\s\S]{0,20000})", text):
                    check_css(m.group(1), rel + " (article template)", faults)
                continue

            if name.endswith((".css", ".py")):
                check_css(text, rel, faults)
            else:
                for m in re.finditer(r"<style[^>]*>([\s\S]*?)</style>", text):
                    check_css(m.group(1), rel, faults)

    if faults:
        print(f"{len(faults)} typography rule break(s) across {checked} files:\n")
        for where, what, selector in faults[:25]:
            print(f"  {where}\n      {what}   [{selector}]")
        if len(faults) > 25:
            print(f"  ... and {len(faults) - 25} more")
        print("\nThe public system: Arial/Helvetica; display 20px+ stays light;")
        print("weight belongs to labels, CTA text, nav and footer. A new family or")
        print("a heavy display needs design approval - see the handover.")
        return 1

    print(f"typography system intact across {checked} files")
    print("  Arial/Helvetica, light display at 20px+, weight only on small type")
    return 0


if __name__ == "__main__":
    sys.exit(main())
