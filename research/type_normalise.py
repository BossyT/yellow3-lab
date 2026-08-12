#!/usr/bin/env python3
"""One typographic language across public yellow3.io. Weight and tracking only.

THE PROBLEM, MEASURED RATHER THAN GUESSED. /platforms and /research share a
font family and still read as two design systems. Computed styles at 1440px:

    role   /platforms (approved)            /research
    h1     84px  weight 400  -0.055em       88px  weight 800  -0.03em
    h3     28px  weight 400  -0.025em       24px  weight 800  -0.02em
    nav    12px  weight 500  uppercase      identical
    footer 14px  weight 400                 identical

The family was never the difference. The weight is. The shell already matches
because it is shared.

THE RULE THIS APPLIES, from the approved page and from Thomas's brief: large
display type is LIGHT, and weight belongs to micro labels, small emphasis and
selected CTA text. So:

  - a rule whose type is >= 20px and whose weight is >= 600 becomes weight 400
  - its tracking joins the /platforms scale, by size band:
        >= 60px  ->  -0.055em      36-59px  ->  -0.05em      20-35px -> -0.025em
  - anything under 20px is untouched: eyebrows, labels, nav, footer, buttons
    and CTA text keep the weight they have

Nothing else moves. No size, line-height, transform, colour, spacing, layout or
markup change - and the sweep refuses a file where any other line would change.

    python3 research/type_normalise.py            what would change
    python3 research/type_normalise.py --apply    change it
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"node_modules", ".git", ".vercel", "Autonomous ai software", "img"}
SKIP_ROOT_DIRS = {"reports"}
# admin.html is the CMS chrome. platforms.html is the frozen reference and is
# already correct - touching it would break its seal for no gain.
SKIP_FILES = {"admin.html", "platforms.html", "google4b600ad4155228a3.html",
              "type_normalise.py", "font_normalise.py", "site_audit.py"}

BLOCK = re.compile(r"([^{}]+)\{([^{}]*)\}")
SIZE = re.compile(r"font-size\s*:\s*([^;]+)", re.I)
WEIGHT = re.compile(r"font-weight\s*:\s*(\d{3})", re.I)
TRACK = re.compile(r"letter-spacing\s*:\s*(-?[\d.]+)(em|px)", re.I)
PX = re.compile(r"(-?[\d.]+)px")


def biggest_px(value):
    """The largest px in a size value - clamp(38px, 5.4vw, 76px) is a 76px role."""
    hits = [float(x) for x in PX.findall(value)]
    return max(hits) if hits else None


def tracking_for(size):
    """The /platforms scale, measured from the live page."""
    if size >= 60:
        return "-0.055em"
    if size >= 36:
        return "-0.05em"
    return "-0.025em"


def normalise_css(css):
    """Returns (new_css, changes). Only font-weight and letter-spacing move."""
    changes = []

    def do_block(m):
        selector, body = m.group(1), m.group(2)
        size_m = SIZE.search(body)
        weight_m = WEIGHT.search(body)
        if not size_m or not weight_m:
            return m.group(0)
        size = biggest_px(size_m.group(1))
        if size is None or size < 20:
            return m.group(0)                 # small type keeps its weight
        if int(weight_m.group(1)) < 600:
            return m.group(0)                 # already light

        new_body = WEIGHT.sub("font-weight: 400", body, count=1)
        want = tracking_for(size)
        if TRACK.search(new_body):
            new_body = TRACK.sub("letter-spacing: " + want, new_body, count=1)
        else:
            # No tracking declared: add it next to the weight, so the role
            # matches /platforms rather than sitting at Arial's default.
            new_body = new_body.replace("font-weight: 400",
                                        "font-weight: 400; letter-spacing: " + want, 1)
        changes.append((selector.strip()[:60], size, weight_m.group(1), want))
        return selector + "{" + new_body + "}"

    return BLOCK.sub(do_block, css), changes


def only_type_lines_moved(before, after):
    import difflib
    bad = []
    for line in difflib.unified_diff(before.split("\n"), after.split("\n"), n=0, lineterm=""):
        if line[:3] in ("+++", "---") or line[:2] == "@@" or line[:1] not in "+-":
            continue
        body = line[1:].strip()
        if not body:
            continue
        if re.search(r"font-weight|letter-spacing", body, re.I):
            continue
        bad.append(body[:110])
    return bad


def main():
    apply_changes = "--apply" in sys.argv
    files = 0
    rules = 0
    unsafe = []
    examples = []

    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS
                   and not (base == ROOT and d in SKIP_ROOT_DIRS)]
        for name in sorted(names):
            # Generators carry CSS in string literals. Skipping them would let
            # the next regeneration put the heavy weights back.
            if not name.endswith((".html", ".css", ".py")) or name in SKIP_FILES:
                continue
            path = os.path.join(base, name)
            text = open(path, encoding="utf-8", errors="replace").read()

            if name.endswith((".css", ".py")):
                new, changes = normalise_css(text)
            else:
                # Only inside <style>; never touch markup.
                new, changes = text, []
                for m in re.finditer(r"(<style[^>]*>)([\s\S]*?)(</style>)", text):
                    block, ch = normalise_css(m.group(2))
                    if ch:
                        new = new.replace(m.group(2), block, 1)
                        changes += ch

            if not changes or new == text:
                continue
            bad = only_type_lines_moved(text, new)
            if bad:
                unsafe.append((os.path.relpath(path, ROOT), bad))
                continue

            files += 1
            rules += len(changes)
            if len(examples) < 6:
                examples.append((os.path.relpath(path, ROOT), changes[0]))
            if apply_changes:
                open(path, "w", encoding="utf-8").write(new)

    verb = "changed" if apply_changes else "would change"
    print(f"{verb} {rules} display rules in {files} files")
    print("  weight >=600 -> 400, tracking to the /platforms scale, size >= 20px only\n")
    for path, (sel, size, was, track) in examples:
        print(f"  {path}")
        print(f"      {sel}   {size:.0f}px  weight {was} -> 400  tracking {track}")

    if unsafe:
        print(f"\nREFUSED {len(unsafe)} file(s) - a non-typography line would have moved:")
        for path, lines in unsafe[:8]:
            print(f"  {path}: {lines[0]}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
