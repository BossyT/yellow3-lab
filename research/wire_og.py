#!/usr/bin/env python3
"""
Point every page at its own generated Open Graph card.

Run research/gen_og.py first - it writes the PNGs. This only rewrites tags.

    python3 research/wire_og.py --check   verify, change nothing
    python3 research/wire_og.py           rewrite og:image and twitter:image

The June -v2 files in /og are deliberately left in place. They are the
historical boundary: anything still pointing at one is a page this sweep did
not reach, which is exactly what --check looks for.

Noindex pages are included. 342 supplier claim and add flows carried the June
Digital Product Passport card; they are not indexed but they are shared, so
each one inherits its parent supplier profile's card. No extra artwork - the
card already exists for the profile.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS = os.path.join(ROOT, "og", "cards")
HOST = "https://www.yellow3.io"
SKIP_DIRS = {"node_modules", ".git", ".vercel", "Autonomous ai software"}
NOT_PUBLIC = {"admin.html", "google4b600ad4155228a3.html"}


def slug_for(rel):
    return re.sub(r"[^a-z0-9]+", "-", rel[:-len(".html")].lower()).strip("-")


# Pages that publish a better card than the generator can make. The Top 10
# archive points at that week's own edition card, which shows the actual
# ranking; a generated card would replace it with the page's H1 on a frame.
KEEPS_OWN_CARD = ("research/model-adoption/top10/",)


def card_for(rel):
    """The card a page should carry, or None if it has no claim on one."""
    if rel.startswith(KEEPS_OWN_CARD):
        return None
    s = slug_for(rel)
    if os.path.exists(os.path.join(CARDS, s + ".png")):
        return s
    # A noindex child of a supplier profile - claim.html, add.html and the
    # like - takes the profile's card.
    parts = rel.split("/")
    if len(parts) > 1:
        parent = "/".join(parts[:-1]) + ".html"
        ps = slug_for(parent)
        if os.path.exists(os.path.join(CARDS, ps + ".png")):
            return ps
    return None


def pages():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in sorted(files):
            if not f.endswith(".html"):
                continue
            rel = os.path.relpath(os.path.join(base, f), ROOT)
            if rel in NOT_PUBLIC or rel.startswith("research/og_frame"):
                continue
            yield rel


def rewrite(text, url):
    """Point the social image properties at url, leaving everything else."""
    n = 0
    for pat in (r'(<meta property="og:image" content=")([^"]*)(")',
                r'(<meta property="og:image:secure_url" content=")([^"]*)(")',
                r'(<meta name="twitter:image" content=")([^"]*)(")',
                r'(<meta property="twitter:image" content=")([^"]*)(")'):
        text, k = re.subn(pat, lambda m: m.group(1) + url + m.group(3), text)
        n += k
    # width and height are part of the contract; every card is 1200x630
    if 'property="og:image"' in text and 'property="og:image:width"' not in text:
        text = text.replace(
            '<meta property="og:image" content="%s"' % url,
            '<meta property="og:image" content="%s" />\n'
            '  <meta property="og:image:width" content="1200" />\n'
            '  <meta property="og:image:height" content="630"' % url, 1)
        n += 1
    else:
        text = re.sub(r'(<meta property="og:image:width" content=")[^"]*(")',
                      r"\g<1>1200\g<2>", text)
        text = re.sub(r'(<meta property="og:image:height" content=")[^"]*(")',
                      r"\g<1>630\g<2>", text)
    return text, n


def main():
    check = "--check" in sys.argv
    if not os.path.isdir(CARDS):
        sys.exit("no cards at og/cards - run research/gen_og.py first")

    changed = unmatched = already = 0
    stale = []
    for rel in pages():
        path = os.path.join(ROOT, rel)
        s = open(path, encoding="utf-8", errors="ignore").read()
        if "og:image" not in s:
            continue
        card = card_for(rel)
        if not card:
            unmatched += 1
            if re.search(r'og:image" content="[^"]*/og/og-[^"]*-v2\.png"', s):
                stale.append(rel)
            continue
        url = "%s/og/cards/%s.png" % (HOST, card)
        if ('og:image" content="%s"' % url) in s:
            already += 1
            continue
        out, n = rewrite(s, url)
        if out != s:
            changed += 1
            if not check:
                open(path, "w", encoding="utf-8").write(out)

    print("  pages pointed at their own card   %d" % changed)
    print("  already correct                   %d" % already)
    print("  no card, left alone               %d" % unmatched)
    if stale:
        print("\n  STILL ON A JUNE -v2 CARD          %d" % len(stale))
        for r in stale[:10]:
            print("     %s" % r)
    if check and changed:
        print("\n  --check: %d pages would change, nothing written" % changed)
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
