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

    # 2b. The CMS still runs.
    #
    # On 2026-08-14 the Google Analytics sweep removed 657 lines from admin.html
    # in one pass, including the </script> that closed its only script block. The
    # CMS was dead - no publishing, no editing - and it shipped, because every
    # check this repo had reads PAGES and admin.html is a program. The typography
    # freeze already reads the article templates, so the one thing nobody was
    # asking was whether the file was still a working program at all.
    #
    # Cheap version of that question: the script blocks must be balanced and the
    # article templates must still be in there.
    admin = ROOT / 'admin.html'
    if not admin.exists():
        FAIL.append('admin.html is missing')
    else:
        text = admin.read_text(encoding='utf-8')
        # Counting <script> against </script> does NOT work here, and the reason
        # is the whole bug: the article templates contain unescaped <script>
        # opens with escaped <\/script> closes, so the tags are legitimately
        # unbalanced as text. Only a close that is not escaped ends a real block.
        blocks = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)(?<!\\)</script>',
                            text, re.S)
        if not blocks:
            FAIL.append('admin.html has no complete <script> block: its closing '
                        'tag was consumed, so the CMS would not run at all')
        elif text.count('article-body') < 2:
            FAIL.append(f'admin.html carries {text.count("article-body")} article '
                        f'template reference(s); it publishes with two')
        else:
            src = ROOT / 'research' / '.admin-check.js'
            src.write_text('\n;\n'.join(blocks), encoding='utf-8')
            r = subprocess.run(['node', '--check', str(src)],
                               capture_output=True, text=True)
            src.unlink(missing_ok=True)
            if r.returncode == 127 or 'not found' in (r.stderr or ''):
                print('  ..  CMS: node unavailable, syntax not checked')
            elif r.returncode != 0:
                FAIL.append('admin.html does not parse as JavaScript - the CMS '
                            'would not run: '
                            + (r.stderr or '').strip().splitlines()[-1:][0]
                            if (r.stderr or '').strip() else 'syntax error')
            else:
                print(f'  ok  CMS: parses, {text.count("article-body")} article '
                      f'template references')

    # 2c. SEO / entity due diligence, as a standing gate.
    #
    # GPT 2026-08-15: this is a continuous system, not a one-off project.
    # Generated pages, canonicals, templates, redirects and the sitemap can all
    # drift independently, and every one of those drifts is invisible on any
    # single page.
    #
    # seo_dd skips its sitemap checks when it cannot reach the live one, which
    # is the case here: generate-sitemap.js runs AFTER this script in the build
    # command, so the committed copy is a build behind. It still checks links,
    # canonicals, metadata, social cards, entity wording and template drift.
    r = subprocess.run([sys.executable, str(ROOT / 'research' / 'seo_dd.py'),
                        '--check'], capture_output=True, text=True)
    if r.returncode:
        tail = [l for l in (r.stdout or '').splitlines() if l.startswith('!')]
        FAIL.append('seo_dd found a fault that misleads a crawler:\n      '
                    + '\n      '.join(tail or ['see python3 research/seo_dd.py']))
    else:
        print('  ok  seo: canonicals, links, social cards, entity, templates')

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

    # 5a. The instrument data still has the shape the pages read, and the
    #     pages still draw. Catches an upstream schema change before a visitor
    #     does. The render half needs a browser, so it self-skips on Vercel and
    #     gives full coverage locally before a commit.
    r = subprocess.run([sys.executable, str(ROOT / 'research' / 'instrument_health.py')],
                       capture_output=True, text=True)
    if r.returncode:
        FAIL.append('instrument health failed:\n      '
                    + '\n      '.join(l.strip() for l in (r.stdout or '').splitlines()
                                       if l.strip() and not l.startswith('INSTRUMENT')))
    else:
        print('  ok  instrument data matches the contract the pages read')

    # 5a2. Somebody is waiting on the other end of the submission queue.
    r = subprocess.run([sys.executable, str(ROOT / 'research' / 'dpp_queue_report.py'),
                        '--check'], capture_output=True, text=True)
    if r.returncode:
        FAIL.append('DPP submission queue:\n      '
                    + '\n      '.join(l.strip() for l in (r.stdout or '').splitlines()
                                       if l.strip() and not l.startswith('DPP SUBMISSION')))
    else:
        print((r.stdout or '').rstrip() or '  ok  submission queue')

    # 5b. Every instrument declares and honours its update model.
    #     Three instruments disagreed with themselves on 15 Aug 2026 - one said
    #     weekly while a cron refreshed it daily, two promised weekly and were
    #     eighteen days stale behind a "Live" badge. Nothing was checking.
    r = subprocess.run([sys.executable, str(ROOT / 'research' / 'cadence_check.py')],
                       capture_output=True, text=True)
    if r.returncode:
        FAIL.append('cadence check failed:\n      '
                    + '\n      '.join(l.strip() for l in (r.stdout or '').splitlines()
                                       if l.strip() and not l.strip().startswith('..')))
    else:
        print('  ok  instruments declare and honour their update model')

    # 6. Every page's social card exists, and no page has drifted back to a
    #    June card. The eleven -v2 files stay on disk as the historical
    #    boundary, so a page still pointing at one is a page a sweep missed.
    cards = ROOT / 'og' / 'cards'
    missing, june = [], []
    for f in ROOT.glob('**/*.html'):
        if '.git' in f.parts or 'node_modules' in f.parts:
            continue
        text = f.read_text(encoding='utf-8', errors='ignore')
        for m in re.finditer(r'og:image" content="[^"]*?/og/([^"]+)"', text):
            ref = m.group(1)
            if re.match(r'og-.*-v2\.png$', ref):
                june.append(str(f.relative_to(ROOT)))
            elif ref.startswith('cards/') and not (cards / ref[len('cards/'):]).exists():
                missing.append(f'{f.relative_to(ROOT)} -> {ref}')
    if missing:
        FAIL.append(f'{len(missing)} page(s) point at a social card that does '
                    f'not exist, e.g. {missing[0]} - run research/gen_og.py')
    if june:
        FAIL.append(f'{len(june)} page(s) are back on a June -v2 card, '
                    f'e.g. {june[0]} - run research/wire_og.py')
    # The CMS builds its og:image by concatenation, so the literal tag never
    # appears and the scan above cannot see it. Read its card URLs directly -
    # this is exactly how a fallback pointing at insights.png, a file that
    # never existed, reached production.
    for f in (ROOT / 'admin.html',):
        if not f.exists():
            continue
        for ref in re.findall(r'/og/cards/([A-Za-z0-9._-]+\.png)', f.read_text(encoding='utf-8')):
            if not (cards / ref).exists():
                missing.append(f'{f.name} -> cards/{ref}')
    if missing:
        FAIL.append(f'{len(missing)} social card reference(s) do not resolve, '
                    f'e.g. {missing[-1]}')
    if not missing and not june:
        print(f'  ok  every social card resolves ({len(list(cards.glob("*.png")))} cards)')

    # 7. No control that looks like a link and is not one.
    #
    # ON 2026-08-17 A VISITOR EMAILED TO SAY THE HOMEPAGE BUTTONS DID NOT WORK.
    # Four of them were anchors with no href attribute:
    #
    #     <a class="btn">Explore our platforms →</a>
    #
    # An <a> with no href is not a link. It takes the button styling, and it
    # does nothing when clicked. Every destination existed and returned 200 the
    # whole time; nothing pointed at them.
    #
    # WHY NOTHING CAUGHT IT. Every check in this repo, and seo_dd and site_audit
    # too, asks whether a link points somewhere valid. An element with no href
    # is not a link, so there was nothing to validate and nothing to report. The
    # gap was not in the rules; it was in what counted as a subject.
    #
    # site_audit's dead-control check looks for href="#", which is the OTHER way
    # to write a control that goes nowhere. This is the missing half, and it is
    # here rather than there because site_audit is a tool somebody runs and this
    # is the gate that runs on every deploy.
    dead: list[str] = []
    for path in sorted(ROOT.glob('*.html')) + sorted(ROOT.glob('*/*.html')):
        rel = path.relative_to(ROOT).as_posix()
        if rel in ('admin.html',):          # a program, not a page
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        for m in re.finditer(r'<a\b(?![^>]*\bhref=)([^>]*)>(.*?)</a>', text, re.S):
            attrs, inner = m.group(1), m.group(2)
            # An anchor used purely as a scroll target carries a name or an id
            # and no text. Only a control a visitor can SEE and press is a fault.
            if 'name=' in attrs or 'onclick' in attrs:
                continue
            label = re.sub(r'<[^>]+>', '', inner)
            label = ' '.join(label.split())
            if not label:
                continue
            line = text[:m.start()].count('\n') + 1
            dead.append(f'{rel}:{line}  "{label[:52]}"')

    if dead:
        FAIL.append('anchors with no href - these render as buttons and do '
                    f'nothing when clicked ({len(dead)}):')
        FAIL.extend('    ' + d for d in dead)
    else:
        print('  ok  no anchor renders as a control and goes nowhere')

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
