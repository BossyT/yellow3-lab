#!/usr/bin/env python3
"""
The build gate: nothing ships that a crawler cannot read.

WHY THIS EXISTS. The instruments spent months serving "Loading register" and
"The instrument data could not be loaded" to every crawler robots.txt invites
in, and nothing anywhere noticed, because nothing was checking. A prerender that
silently stops running is worse than never having had one: the pages look fine
to a person, the failure is invisible, and it decays quietly.

So the sweep now runs the generators and then asserts their output. It exits
non-zero on failure, which fails the Vercel build, which is the point - a
deployment that cannot produce readable instruments should not replace one that
could.

    python3 research/build_check.py
"""
import json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAIL = []

def run(script: str, *args: str) -> None:
    r = subprocess.run([sys.executable, str(ROOT / 'research' / script), *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        FAIL.append(f'{script} exited {r.returncode}: '
                    f'{(r.stderr or r.stdout).strip().splitlines()[-1:]}')

def readable(path: pathlib.Path) -> int:
    """Characters of text a crawler gets from the prerendered blocks."""
    s = path.read_text(encoding='utf-8')
    blocks = re.findall(r'<!-- prerendered:[^>]*-->(.*?)<!-- /prerendered', s, re.S)
    return len(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', ' '.join(blocks))).strip())

def main() -> int:
    # 1. Regenerate. The data changes weekly; a stale prerender is a lie with a
    #    timestamp on it.
    run('prerender_instruments.py', '--apply')
    run('dpp_dataset_export.py')

    # 2. Assert the output. Thresholds are deliberately far below current values
    #    so ordinary movement never trips them, and a collapse always does.
    checks = [
        ('research/digital-product-passport/suppliers.html', 5000,
         'supplier directory rows'),
        ('research/digital-product-passport.html', 300, 'DPP instrument'),
        ('research/eu-ai-act.html', 300, 'EU AI Act instrument'),
    ]
    for rel, floor, what in checks:
        p = ROOT / rel
        if not p.exists():
            FAIL.append(f'{rel} is missing'); continue
        n = readable(p)
        if n < floor:
            FAIL.append(f'{what}: only {n} characters readable without JavaScript '
                        f'(expected at least {floor}) - the prerender did not run '
                        f'or produced nothing')
        else:
            print(f'  ok  {what}: {n} characters readable')

    # 3. The dataset, and that it agrees with the register it came from.
    src = json.loads((ROOT / 'research' / 'dpp-suppliers.json').read_text(encoding='utf-8'))
    expected = len(src['suppliers'])
    ds = ROOT / 'research' / 'digital-product-passport' / 'suppliers.json'
    csv = ROOT / 'research' / 'digital-product-passport' / 'suppliers.csv'
    if not ds.exists() or not csv.exists():
        FAIL.append('dataset export missing (suppliers.csv / suppliers.json)')
    else:
        got = json.loads(ds.read_text(encoding='utf-8'))
        rows = len(csv.read_text(encoding='utf-8').strip().splitlines()) - 1
        if got.get('record_count') != expected or rows != expected:
            FAIL.append(f'dataset disagrees with the register: register has '
                        f'{expected}, json says {got.get("record_count")}, '
                        f'csv has {rows} rows')
        elif not got.get('licence') or not got.get('citation'):
            FAIL.append('dataset is missing its licence or citation')
        else:
            print(f'  ok  dataset: {expected} organisations, licensed, citable')

    # 4. The schema that makes it findable.
    page = (ROOT / 'research/digital-product-passport/suppliers.html').read_text(encoding='utf-8')
    if '"@type": "Dataset"' not in page:
        FAIL.append('Dataset JSON-LD missing from the supplier directory')
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            json.loads(m.group(1))
        except Exception as e:
            FAIL.append(f'invalid JSON-LD on the supplier directory: {e}')

    # 5. Analytics stays off until consent is designed.
    back = [str(f.relative_to(ROOT)) for f in ROOT.glob('**/*.html')
            if '.git' not in f.parts and 'node_modules' not in f.parts
            and ('googletagmanager' in f.read_text(encoding='utf-8')
                 or 'gtag(' in f.read_text(encoding='utf-8'))]
    if back:
        FAIL.append(f'Google Analytics is back on {len(back)} page(s), '
                    f'e.g. {back[0]} - it stays off until consent is designed')
    else:
        print('  ok  no analytics anywhere')

    if FAIL:
        print('\nBUILD REFUSED\n')
        for f in FAIL:
            print(f'  {f}')
        print('\nFix the above, or ship a site whose research nobody can read.\n')
        return 1
    print('\n  build checks passed\n')
    return 0

if __name__ == '__main__':
    sys.exit(main())
