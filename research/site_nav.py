"""The site navigation, in one place.

WHY THIS FILE EXISTS. The nav is written into every page of this site - 631 of
them - and into three generators that write more. When it changed on 2026-08-05
(DPP added as a seventh item) it had to be swept across 629 pages by hand. The
same markup authored in four places is the shape of defect this repo has been
bitten by before: a number typed twice, a total that does not match its parts.

So the nav is defined here once. The generators import it, the static pages are
swept from it, and `--check` proves the site agrees with it. A page that drifts
is a failing check rather than something somebody notices in a screenshot.

    python3 research/site_nav.py --check     does every page match?
    python3 research/site_nav.py --apply     rewrite the ones that do not

THE ACTIVE ITEM IS PRESERVED, not guessed. Each page already says which nav item
it is on, and that is information the sweep must not lose - so the current
active item is read out of the page and mapped forward.
"""

import os
import re
import sys

# The menu, in order. Approved 2026-08-11: `Work` and the standalone `DPP` item
# are gone and `Thinking` is now `Insights`. Labels are written in sentence case
# and the stylesheet uppercases them - see .nav-mid a { text-transform:
# uppercase }. Writing them shouted in the markup would put the styling in two
# places and break the brand rule everywhere the CSS does not reach.
NAV_ITEMS = [
    ("/research", "Research"),
    ("/platforms", "Platforms"),
    ("/insights/", "Insights"),
    ("/advisory", "Advisory"),
    ("/about", "About"),
    ("/#contact", "Contact"),
]

# Where a page that was active under the OLD menu belongs under the new one.
# `/naffe` is the only real decision here: naffe.ai is a platform, so a visitor
# reading it is inside Platforms. The DPP register keeps Research, because that
# is where it lives and what it is.
ACTIVE_MOVED = {
    "/naffe": "/platforms",
    "/research/digital-product-passport/suppliers": "/research",
    "/insights/": "/insights/",
}

# The header CTA that the old menu carried on the homepage. Only this one label
# changes; pages that ask for contact, or point at naffe.ai, keep their own.
OLD_CTA = re.compile(
    r'(<a href="/naffe" class="nav-cta">)Explore our work(\s*<span)')
NEW_CTA = r'<a href="/research" class="nav-cta">View our research\2'

NAV_BLOCK = re.compile(r'(<div class="nav-mid"[^>]*>)(.*?)(</div>)', re.S)
ACTIVE_HREF = re.compile(r'<a href="([^"]+)"[^>]*class="active"')

# Pages that are not part of the public site and must not be swept. admin.html
# is the live CMS holding a token; it is changed only with an explicit
# go-ahead.
SKIP = {"admin.html", "google4b600ad4155228a3.html"}
SKIP_DIRS = {"node_modules", ".git", ".vercel", "Autonomous ai software"}


def render(active=None, indent="      "):
    """The nav-mid contents, with one item marked active."""
    out = []
    for href, label in NAV_ITEMS:
        cls = ' class="active"' if href == active else ""
        out.append(f'{indent}<a href="{href}"{cls}>{label}</a>')
    return "\n" + "\n".join(out) + "\n    "


def _html_files(root):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(files):
            if name.endswith(".html") and name not in SKIP:
                yield os.path.join(base, name)


def sweep(root, apply_changes):
    changed, checked = [], 0
    for path in _html_files(root):
        text = open(path, encoding="utf-8").read()
        match = NAV_BLOCK.search(text)
        if not match:
            continue
        checked += 1

        current = ACTIVE_HREF.search(match.group(2))
        active = current.group(1) if current else None
        # A page whose active item was removed moves to where it now belongs;
        # one whose item survived keeps it; one with none stays with none.
        active = ACTIVE_MOVED.get(active, active)
        if active not in [href for href, _ in NAV_ITEMS]:
            active = None

        rebuilt = NAV_BLOCK.sub(
            lambda m: m.group(1) + render(active) + m.group(3), text, count=1)
        rebuilt = OLD_CTA.sub(NEW_CTA, rebuilt)

        if rebuilt != text:
            changed.append(os.path.relpath(path, root))
            if apply_changes:
                open(path, "w", encoding="utf-8").write(rebuilt)
    return checked, changed


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    apply_changes = "--apply" in sys.argv
    checked, changed = sweep(root, apply_changes)

    if apply_changes:
        print(f"nav: {checked} pages checked, {len(changed)} rewritten")
        return 0

    if changed:
        print(f"nav: {len(changed)} of {checked} pages do not match "
              f"research/site_nav.py")
        for name in changed[:20]:
            print("  " + name)
        if len(changed) > 20:
            print(f"  ... and {len(changed) - 20} more")
        print("\nRun: python3 research/site_nav.py --apply")
        return 1

    print(f"nav: {checked} pages, all match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
