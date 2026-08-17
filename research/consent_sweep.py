#!/usr/bin/env python3
"""Put the consent script on every page, and prove it is there.

WHY. yellow3 is an EU entity, so the consent rules apply to it wherever the
visitor is. Today no page on this site stores anything - verified in a clean
browser before this was written: zero cookies, zero localStorage, zero
sessionStorage on arrival - which is why there was nothing to consent to. That
is the state Google Analytics was removed to reach on 14 August.

This is the gate that has to exist before anything comes back. It is one script
tag, one line, on every page, and consent.js does the rest.

    python3 research/consent_sweep.py            report
    python3 research/consent_sweep.py --apply    write it

TWO GUARDS, BOTH BECAUSE OF 14 AUGUST. A site-wide sweep destroyed the CMS that
day: it removed 657 lines from admin.html including the </script> that closed
its only script block, and it shipped, because every check this repo had reads
PAGES and admin.html is a program.

  1. A MAX-CHANGE CEILING. A sweep that wants to rewrite more files than exist
     as pages is not a sweep, it is a bug, and it stops rather than asking.
  2. VALIDATION BY FILE TYPE. Pages are parsed as pages. admin.html is skipped
     entirely - it is the CMS, it holds a token, and it is not a public page.

WHAT IT WILL NOT DO. It never edits a <head>, never touches a stylesheet, and
never reorders anything. It inserts one line immediately before </body> and
nothing else, so a page that already carries it is left completely alone.
"""

import pathlib
import re
import sys

APPLY = '--apply' in sys.argv
ROOT = pathlib.Path(__file__).resolve().parent.parent

TAG = '<script src="/consent.js" defer></script>'

# Not public pages. admin.html is the CMS and holds a PAT; the Google
# verification file is Google's; anything under .git or node_modules is not a
# page at all.
SKIP_NAMES = {'admin.html'}
SKIP_PARTS = {'.git', 'node_modules', '.vercel'}

# A ceiling, not a target. There are ~640 pages; a sweep asking to rewrite more
# than this has misunderstood something.
MAX_CHANGES = 800


def pages():
    for p in sorted(ROOT.glob('**/*.html')):
        if SKIP_PARTS & set(p.parts):
            continue
        if p.name in SKIP_NAMES:
            continue
        yield p


def looks_like_a_page(text: str) -> bool:
    """A page has a body to insert before. A fragment or a program does not."""
    return '</body>' in text.lower() and '<html' in text.lower()


def main() -> int:
    missing, already, skipped, changed = [], [], [], []

    for path in pages():
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding='utf-8', errors='replace')

        if not looks_like_a_page(text):
            skipped.append(rel)
            continue
        if TAG in text:
            already.append(rel)
            continue
        missing.append((path, rel, text))

    if len(missing) > MAX_CHANGES:
        print(f'REFUSED: {len(missing)} files want the tag, ceiling is '
              f'{MAX_CHANGES}. That is not a sweep, that is a bug.')
        return 1

    if not APPLY:
        print(f'consent: {len(already)} page(s) carry the tag, '
              f'{len(missing)} do not, {len(skipped)} skipped (not pages)')
        for _, rel, _ in missing[:15]:
            print(f'  missing  {rel}')
        if len(missing) > 15:
            print(f'  ... and {len(missing) - 15} more')
        return 1 if missing else 0

    for path, rel, text in missing:
        # Before the LAST </body>, so a page that mentions the string in copy or
        # in a script does not get the tag in the wrong place.
        idx = text.lower().rfind('</body>')
        out = text[:idx] + TAG + '\n' + text[idx:]

        # The one assertion that matters after an edit: it is still a page, and
        # it gained exactly the line we meant to add.
        if not looks_like_a_page(out) or out.count(TAG) != 1:
            print(f'REFUSED: writing {rel} would not leave a valid page')
            return 1
        if len(out) - len(text) != len(TAG) + 1:
            print(f'REFUSED: {rel} changed by more than one line')
            return 1

        path.write_text(out, encoding='utf-8')
        changed.append(rel)

    print(f'consent: {len(changed)} page(s) given the tag, '
          f'{len(already)} already had it, {len(skipped)} skipped')
    return 0


if __name__ == '__main__':
    sys.exit(main())
