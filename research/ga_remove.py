#!/usr/bin/env python3
"""
Remove Google Analytics from yellow3.io.

WHY. GA4 loaded unconditionally on every page - no consent gate of any kind -
which sets analytics cookies for EU visitors before they are asked. Disclosure
does not cure that; the requirement is prior consent.

The register was cleared first, under campaign pressure. The decision then
taken for the rest of the site is the same one: we do not need Google Analytics
badly enough to build a consent system around 99 pages under time pressure.
Search Console remains, and it is the source for impressions, clicks and
queries anyway; Analytics was measuring post-click behaviour nobody was acting
on. Analytics returns when consent is deliberately designed, not before.

    python3 research/ga_remove_register.py           # report
    python3 research/ga_remove_register.py --apply
"""
import re, sys, pathlib

APPLY = '--apply' in sys.argv
ROOT = pathlib.Path(__file__).resolve().parent.parent

# EVERY page. admin.html is included deliberately: the CMS is not a public page
# but it is served from this domain and there is no reason for it to measure
# anything either.
TARGETS = sorted(p for p in ROOT.glob('**/*.html')
                 if 'node_modules' not in p.parts and '.git' not in p.parts)

# The loader and the inline config that follows it, as a single block.
BLOCK = re.compile(
    r'[ \t]*<script async src="https://www\.googletagmanager\.com/gtag/js\?[^"]*"></script>\s*'
    r'<script>\s*window\.dataLayer[^<]*?</script>\s*\n?',
    re.S)
LOOSE = re.compile(r'[ \t]*<script[^>]*googletagmanager[^>]*>.*?</script>\s*\n?', re.S)

# The inline event handlers. 39 pages carry an onclick that fires a GA event,
# guarded by `typeof window.gtag === 'function'`, so with GA gone they are
# already no-ops - but they are dead references to a system that no longer
# exists, and leaving them would make the next person think measurement is
# still wired up. On the buttons where they sit alongside a second onclick they
# never fired at all: a tag may only have one, and the browser keeps the first.
EVENT = re.compile(r'\s*onclick="if\(typeof window\.gtag[^"]*"')

# And the share tracker inside the article script, which is the same guarded
# no-op in JavaScript rather than in an attribute. Removed as a statement, so
# the surrounding share handler keeps working exactly as it did.
SHARE = re.compile(
    r'\s*if\s*\(\s*typeof window\.gtag\s*===?\s*["\']function["\']\s*\)\s*'
    r'\{[^{}]*window\.gtag\([^;]*?\);\s*\}')

changed, already, missed = [], [], []
for f in TARGETS:
    html = f.read_text(encoding='utf-8')
    if 'googletagmanager' not in html and 'gtag(' not in html:
        already.append(f); continue
    out = BLOCK.sub('', html)
    if 'googletagmanager' in out:
        out = LOOSE.sub('', out)
    out = EVENT.sub('', out)
    out = SHARE.sub('', out)
    if 'googletagmanager' in out or 'gtag(' in out:
        missed.append(f); continue
    changed.append(f)
    if APPLY:
        f.write_text(out, encoding='utf-8')

print(f'\nregister pages:      {len(TARGETS)}')
print(f'  carried GA:        {len(changed)}{"  (removed)" if APPLY else "  (would remove)"}')
print(f'  already clean:     {len(already)}')
if missed:
    print(f'  COULD NOT CLEAN:   {len(missed)}')
    for f in missed[:10]:
        print(f'     {f.relative_to(ROOT)}')
    sys.exit(1)
if not APPLY:
    print('\n  dry run. Add --apply to write.')
print()

# ----------------------------------------------------------------- the guard
#
# Run with --check in CI or by hand: exits non-zero if any register page has
# picked GA up again. The register is generated from templates, so "we removed
# it once" is not the same as "it stays removed".
if '--check' in sys.argv:
    back = [f for f in TARGETS
            if 'googletagmanager' in f.read_text(encoding='utf-8')
            or 'gtag(' in f.read_text(encoding='utf-8')]
    if back:
        print(f'REGRESSION: {len(back)} register page(s) load Google Analytics again')
        for f in back[:10]:
            print(f'   {f.relative_to(ROOT)}')
        sys.exit(1)
    print(f'ok  {len(TARGETS)} register pages, no Google Analytics')

    # The line above this guard had it right - the register is generated from
    # templates - and then the guard only ever read the generated pages. It was
    # checking the wrong side. Four generators still carried the snippet, so a
    # single `python3 research/gen_dpp_register.py` put GA back into 536 files;
    # this check was clean right up until the moment someone regenerated.
    #
    # A removal is not finished until the things that write the pages are clean.
    sources = sorted(p for p in (ROOT / 'research').glob('*.py')
                     if p.name not in ('ga_remove.py', 'build_check.py'))
    emitting = [p for p in sources
                if 'googletagmanager' in p.read_text(encoding='utf-8')]
    if emitting:
        print(f'REGRESSION: {len(emitting)} generator(s) would write Google Analytics')
        for p in emitting:
            print(f'   {p.relative_to(ROOT)}')
        sys.exit(1)
    print(f'ok  {len(sources)} generators, none emit Google Analytics')
