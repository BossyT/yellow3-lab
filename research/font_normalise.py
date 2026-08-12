#!/usr/bin/env python3
"""Move public yellow3.io off DM Sans and onto Arial, and nothing else.

Approved 2026-08-12: the public site uses ONE primary sans family,
`Arial, Helvetica, sans-serif` - the family already used by /platforms v2 and
the DPP Supplier Register.

WHAT THIS TOUCHES, AND NOTHING MORE:
  - font-family declarations that name DM Sans      -> the target stack
  - the Google Fonts <link> that loads DM Sans      -> removed
  - fonts.googleapis / fonts.gstatic preconnects    -> removed ONLY from files
                                                       with no remaining
                                                       Google font request

It does not touch sizes, weights, line heights, tracking, transforms, spacing,
widths, grids, breakpoints, colour, copy or markup. Every rewrite is asserted
against that afterwards: a changed line that is not a font line is a bug in
this script, not a decision.

WHAT IT DELIBERATELY LEAVES: Georgia and Newsreader serif, the monospace
stacks, Manrope and Inter. The contract is explicit that this migration removes
DM Sans as the competing public sans - it does not flatten every semantic type
treatment into one family.

    python3 research/font_normalise.py            what would change
    python3 research/font_normalise.py --apply    change it
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = "Arial, Helvetica, sans-serif"
SKIP_DIRS = {"node_modules", ".git", ".vercel", "Autonomous ai software", "img"}
# Only the review folder at the repo ROOT is skipped. `reports` as a bare name
# also matches research/model-adoption/reports, which is public content - it
# was skipped on the first pass and its DM Sans survived silently.
SKIP_ROOT_DIRS = {"reports"}
# The CMS is not a public page and holds a token; it is changed only on an
# explicit go-ahead.
SKIP_FILES = {"admin.html"}

# A font-family value that names DM Sans, however it is quoted or spaced.
FAMILY = re.compile(r"""(font-family\s*:\s*)([^;{}"']*['"]?DM\s*Sans['"]?[^;{}]*)""", re.I)
# A CUSTOM PROPERTY holding the family. This is the shared-token case the
# migration contract asks for first: --font-sans on /research/eu-ai-act drives
# the whole page, and no `font-family:` line names DM Sans there at all.
TOKEN = re.compile(r"""(--[\w-]*font[\w-]*\s*:\s*)([^;{}"']*['"]?DM\s*Sans['"]?[^;{}]*)""", re.I)
# Chart.js and friends naming the family for canvas text.
JS_FAMILY = re.compile(
    r"""(family\s*:\s*)("[^"]*DM\s*Sans[^"]*"|'[^']*DM\s*Sans[^']*')""", re.I)
# A Google Fonts URL asking for SEVERAL families, one of them DM Sans. The
# whole link cannot go - Newsreader on the report pages is intentional - so
# only the DM Sans segment is removed.
MIXED_URL = re.compile(r"(fonts\.googleapis\.com/css2\?)([^\"']*)")
# The stylesheet link that loads DM Sans, with its whole line.
DM_LINK = re.compile(r"^[ \t]*<link[^>]*fonts\.googleapis\.com[^>]*DM\+Sans[^>]*>[ \t]*\n",
                     re.I | re.M)
# The same thing inside a Python generator's HTML string.
PRECONNECT = re.compile(r"^[ \t]*<link[^>]*rel=[\"']preconnect[\"'][^>]*fonts\.(googleapis|gstatic)\.com[^>]*>[ \t]*\n",
                        re.I | re.M)
ANY_GOOGLE_FONT = re.compile(r"fonts\.googleapis\.com/css2\?family=", re.I)


def rewrite(text):
    """Returns (new_text, notes). Only font declarations and font loading."""
    notes = []

    def swap(m):
        notes.append("family")
        return m.group(1) + TARGET

    out = FAMILY.sub(swap, text)

    def swap_token(m):
        notes.append("token")
        return m.group(1) + TARGET
    out = TOKEN.sub(swap_token, out)

    def swap_js(m):
        notes.append("js-family")
        return m.group(1) + '"Arial, Helvetica, sans-serif"'
    out = JS_FAMILY.sub(swap_js, out)

    def trim_url(m):
        query = m.group(2)
        if "DM+Sans" not in query:
            return m.group(0)
        families = [f for f in query.split("&") if f.startswith("family=")]
        if len(families) <= 1:
            return m.group(0)                     # DM Sans only: the whole link goes
        kept = [p for p in query.split("&")
                if not (p.startswith("family=") and "DM+Sans" in p)]
        notes.append("url-trim")
        return m.group(1) + "&".join(kept)
    out = MIXED_URL.sub(trim_url, out)

    n_link = len(DM_LINK.findall(out))
    if n_link:
        out = DM_LINK.sub("", out)
        notes += ["dm-link"] * n_link

    # Preconnects go only when this file no longer asks Google for any font.
    if not ANY_GOOGLE_FONT.search(out):
        n_pre = len(PRECONNECT.findall(out))
        if n_pre:
            out = PRECONNECT.sub("", out)
            notes += ["preconnect"] * n_pre

    return out, notes


def changed_lines_are_font_lines(before, after):
    """The guarantee. Any changed line must be a font line."""
    b, a = before.split("\n"), after.split("\n")
    import difflib
    bad = []
    for line in difflib.unified_diff(b, a, n=0, lineterm=""):
        if line.startswith(("+++", "---", "@@")) or not line[:1] in "+-":
            continue
        body = line[1:]
        if not body.strip():
            continue
        if re.search(r"font-family|--[\w-]*font[\w-]*\s*:|family\s*:|"
                     r"fonts\.googleapis|fonts\.gstatic|DM\s*Sans", body, re.I):
            continue
        bad.append(body.strip()[:120])
    return bad


def main():
    apply_changes = "--apply" in sys.argv
    total = {"files": 0, "family": 0, "token": 0, "js-family": 0,
             "url-trim": 0, "dm-link": 0, "preconnect": 0}
    unsafe = []

    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS
                   and not (base == ROOT and d in SKIP_ROOT_DIRS)]
        for name in sorted(files):
            if not name.endswith((".html", ".css", ".py", ".js")) or name in SKIP_FILES:
                continue
            if name == os.path.basename(__file__):
                continue
            path = os.path.join(base, name)
            text = open(path, encoding="utf-8", errors="replace").read()
            # `DM[\s+]*Sans`, not `DM\s*Sans`: the stylesheet URL spells it
            # `family=DM+Sans`, and a filter that misses the plus skips every
            # page whose only reference is the font load - which was 574 of
            # them on the first run of this script.
            if not re.search(r"DM[\s+]*Sans", text, re.I):
                continue

            new, notes = rewrite(text)
            if new == text:
                continue

            bad = changed_lines_are_font_lines(text, new)
            if bad:
                unsafe.append((os.path.relpath(path, ROOT), bad))
                continue

            total["files"] += 1
            for n in notes:
                total[n] = total.get(n, 0) + 1
            if apply_changes:
                open(path, "w", encoding="utf-8").write(new)

    verb = "changed" if apply_changes else "would change"
    print(f"{verb} {total['files']} files")
    print(f"  {total['family']} font-family declarations -> {TARGET}")
    print(f"  {total['dm-link']} DM Sans stylesheet links removed")
    print(f"  {total['token']} typography tokens (--font-*) -> {TARGET}")
    print(f"  {total['js-family']} chart/JS family strings -> the same stack")
    print(f"  {total['url-trim']} multi-family font URLs trimmed (other families kept)")
    print(f"  {total['preconnect']} now-unused Google Fonts preconnects removed")

    if unsafe:
        print(f"\nREFUSED {len(unsafe)} file(s) - a non-font line would have moved:")
        for path, lines in unsafe[:10]:
            print(f"  {path}")
            for l in lines[:3]:
                print(f"      {l}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
