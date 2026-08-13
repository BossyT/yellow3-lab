#!/usr/bin/env python3
"""
Remove Google Analytics from the public DPP Supplier Register.

WHY, AND WHY ONLY HERE. The register loads GA4 unconditionally - no consent
gate of any kind - and the DPP Group post is about to drive suppliers to it to
claim their profiles. Analytics cookies set for EU visitors before consent is
an ePrivacy problem that disclosure does not cure, and the approved decision is
to remove GA from the register rather than build a consent manager under
campaign pressure.

The rest of yellow3.io is deliberately untouched: that is a separate decision
about the company's analytics, not a launch blocker, and quietly switching it
off everywhere would be a business change nobody asked for.

    python3 research/ga_remove_register.py           # report
    python3 research/ga_remove_register.py --apply
"""
import re, sys, pathlib

APPLY = '--apply' in sys.argv
ROOT = pathlib.Path(__file__).resolve().parent.parent

# The register: the section page, the directory, and every supplier profile.
TARGETS = sorted(set(
    list(ROOT.glob('research/digital-product-passport.html')) +
    list(ROOT.glob('research/digital-product-passport/**/*.html'))
))

# The loader and the inline config that follows it, as a single block.
BLOCK = re.compile(
    r'[ \t]*<script async src="https://www\.googletagmanager\.com/gtag/js\?[^"]*"></script>\s*'
    r'<script>\s*window\.dataLayer[^<]*?</script>\s*\n?',
    re.S)
LOOSE = re.compile(r'[ \t]*<script[^>]*googletagmanager[^>]*>.*?</script>\s*\n?', re.S)

changed, already, missed = [], [], []
for f in TARGETS:
    html = f.read_text(encoding='utf-8')
    if 'googletagmanager' not in html and 'gtag(' not in html:
        already.append(f); continue
    out = BLOCK.sub('', html)
    if 'googletagmanager' in out:
        out = LOOSE.sub('', out)
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
