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
    # The Insights subscription experience, approved v1.0, 23 Aug 2026. The
    # three latest entries on /insights/subscribe are rebuilt from feed.xml on
    # every deploy for the same reason the instruments are: the moment they are
    # allowed to go stale they become a list that says "latest" and is not.
    run('gen_subscribe.py')
    run('gen_feed_xsl.py')

    # 2. Assert the output. Thresholds are deliberately far below current values
    #    so ordinary movement never trips them, and a collapse always does.
    checks = [
        ('research/digital-product-passport/suppliers.html', 5000,
         'supplier directory rows'),
        ('research/digital-product-passport.html', 300, 'DPP instrument'),
        ('research/eu-ai-act.html', 300, 'EU AI Act instrument'),
        # Added 2026-08-23. This page was never covered and had NO prerendered
        # content at all: with JavaScript off it was 1,925 characters of
        # navigation whose only sentence was "The instrument data could not be
        # loaded". Floor set far below the ~2,500 it now carries, so ordinary
        # movement in the rankings never trips it and a collapse always does.
        ('research/model-adoption/live.html', 800, 'model adoption instrument'),
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

    # 2b2. The feed is still a feed, and the subscription page is still live.
    #
    # /feed.xml carries a human presentation now (feed.xsl, applied by the
    # browser). The whole design depends on that being a LAYER: a reader asking
    # for the feed must still get valid RSS 2.0, and if the stylesheet ever
    # failed to load the XML would still be there. So the things worth asserting
    # are the ones that would silently stop being true - the feed parsing as
    # RSS, its items keeping the fields a subscriber needs, the stylesheet
    # reference surviving, and the page's "latest" list actually being latest.
    #
    # And the one thing a copy-paste would reintroduce: the prototype's sample
    # issues. Lock 07 forbids them shipping, so they are named here rather than
    # trusted to have been deleted.
    feed = ROOT / 'feed.xml'
    if not feed.exists():
        FAIL.append('feed.xml is missing - it is the canonical RSS address')
    else:
        raw = feed.read_text(encoding='utf-8')
        try:
            import xml.etree.ElementTree as ET
            channel = ET.parse(feed).getroot().find('channel')
        except Exception as e:
            channel = None
            FAIL.append(f'feed.xml does not parse as XML: {e} - every reader '
                        f'subscribed to it is now getting nothing')
        if '<?xml-stylesheet' not in raw or 'feed.xsl' not in raw:
            FAIL.append('feed.xml has lost its stylesheet reference - the '
                        'browser presentation is gone and humans get raw XML')
        if channel is not None:
            items = channel.findall('item')
            bad = [i for i in items
                   if not (i.findtext('title') or '').strip()
                   or not (i.findtext('link') or '').startswith('https://')
                   or not (i.findtext('guid') or '').strip()
                   or not (i.findtext('pubDate') or '').strip()]
            if not items:
                FAIL.append('feed.xml has no items at all')
            elif bad:
                FAIL.append(f'{len(bad)} feed item(s) are missing a title, an '
                            f'absolute https link, a guid or a pubDate, '
                            f'e.g. "{(bad[0].findtext("title") or "")[:48]}"')
            else:
                print(f'  ok  feed: {len(items)} items, RSS 2.0, styled for browsers')

    sub = ROOT / 'insights' / 'subscribe.html'
    if not sub.exists():
        FAIL.append('insights/subscribe.html is missing - the human route into '
                    'the feed is the whole point of the v1.0 handover')
    else:
        text = sub.read_text(encoding='utf-8')
        # Copy that exists ONLY in the design prototype.
        #
        # THIS LIST USED TO HOLD THE EXPANDED ISSUE 31 TITLE, and that stopped
        # being a tell on 2026-08-23: GPT ruled in handover v1.1 that "The
        # Digital Product Passport Deadline You Already Missed" IS the published
        # title, so the string that once proved the prototype's sample array had
        # come back now appears legitimately in the live record. Left in, it
        # refused the build for doing exactly what the ruling asked.
        #
        # The load-bearing guard against sample entries was never this list
        # anyway - it is gen_subscribe.py --check below, which proves every row
        # on the page is the row feed.xml holds. A hardcoded sample cannot
        # survive that. What stays here is the one string with no legitimate
        # production reading: the prototype's tertiary link, which
        # 02-SUBSCRIBE-PAGE-SPEC says must not ship.
        for phrase in ('VIEW THE APPROVED BROWSER PRESENTATION',):
            if phrase in text:
                FAIL.append(f'insights/subscribe.html still carries prototype '
                            f'content: "{phrase[:52]}"')
        if '/feed-preview' in text:
            FAIL.append('insights/subscribe.html links to /feed-preview - Lock '
                        '02: that route exists only in the design prototype')
        r = subprocess.run([sys.executable, str(ROOT / 'research' / 'gen_subscribe.py'),
                            '--check'], capture_output=True, text=True)
        if r.returncode:
            FAIL.append('the subscribe page\'s latest entries are stale:\n      '
                        + (r.stdout or r.stderr).strip())
        else:
            print((r.stdout or '').rstrip())
        r = subprocess.run([sys.executable, str(ROOT / 'research' / 'gen_feed_xsl.py'),
                            '--check'], capture_output=True, text=True)
        if r.returncode:
            FAIL.append('feed.xsl has drifted from the approved package:\n      '
                        + (r.stdout or r.stderr).strip())
        else:
            print((r.stdout or '').rstrip())
        r = subprocess.run([sys.executable, str(ROOT / 'research' / 'port_approved_css.py'),
                            'insights-subscribe'], capture_output=True, text=True)
        if r.returncode:
            FAIL.append('the approved subscribe stylesheet has drifted:\n      '
                        + (r.stdout or r.stderr).strip())
        else:
            print('  ok  subscribe: stylesheet matches the approved package')

    # 2b3. The two acceptance checks that replaced the feed view's old
    #      "no menu, no footer" boundary.
    #
    # GPT ratified the shell on /feed.xml as handover v1.1 on 2026-08-23,
    # superseding 03-RSS-BROWSER-SPEC's visual boundary for that page only, and
    # retired the two checks that used to pass by ABSENCE. Their replacements
    # are:
    #
    #   the presentation renders exactly one EXISTING yellow3 top menu and one
    #   EXISTING yellow3 footer
    #
    #   no substitute shell, duplicated shell or altered shell styling
    #
    # Both are asserted here rather than left to a reading, because "existing"
    # is the whole condition. A hand-written menu that merely looks right would
    # satisfy a screenshot and fail the ruling. So the markup on the feed view
    # is compared against the markup insights/index.html actually carries -
    # whitespace normalised, because the XSLT is indented differently, and
    # entity normalised, because &copy; has to be numeric to survive XML.
    shell_src = ROOT / 'insights' / 'index.html'
    feed_xsl = ROOT / 'feed.xsl'
    if not feed_xsl.exists():
        FAIL.append('feed.xsl is missing - /feed.xml would serve raw XML to '
                    'every human who opens it')
    else:
        xsl_text = feed_xsl.read_text(encoding='utf-8')
        navs = xsl_text.count('<nav class="site-nav">')
        foots = xsl_text.count('<footer class="site-footer">')
        if navs != 1 or foots != 1:
            FAIL.append(f'the RSS browser presentation carries {navs} top '
                        f'menu(s) and {foots} footer(s); v1.1 requires exactly '
                        f'one of each')
        else:
            def _norm(s):
                return re.sub(r'\s+', ' ', s.replace('&#169;', '&copy;')).strip()

            def _shell(text):
                n = re.search(r'(<nav class="site-nav">.*?</nav>)', text, re.S)
                f = re.search(r'(<footer class="site-footer">.*?</footer>)',
                              text, re.S)
                return (_norm(n.group(1)) if n else None,
                        _norm(f.group(1)) if f else None)

            want = _shell(shell_src.read_text(encoding='utf-8'))
            got = _shell(xsl_text)
            if want[0] is None or want[1] is None:
                FAIL.append('insights/index.html no longer carries the shell '
                            'this check reads as the reference')
            elif got[0] != want[0]:
                FAIL.append('the top menu on /feed.xml is not the site\'s own - '
                            'it has been substituted or altered rather than '
                            'inherited (v1.1 condition 1)')
            elif got[1] != want[1]:
                FAIL.append('the footer on /feed.xml is not the site\'s own - '
                            'it has been substituted or altered rather than '
                            'inherited (v1.1 condition 1)')
            else:
                # Condition 4: no package token may repaint the menu or footer.
                # The package's own :root must never reach document level here;
                # every one of its rules is scoped beneath .fv1.
                stray = re.search(r'(?<![\w.-])(:root|html|body)\s*\{[^}]*--yellow\s*:\s*#ffe500',
                                  xsl_text, re.I)
                if stray:
                    FAIL.append('the package palette has escaped .fv1 on '
                                '/feed.xml - it would repaint the existing menu '
                                'and footer (v1.1 condition 4)')
                elif '--yellow: #ffe500' not in xsl_text:
                    FAIL.append('signal yellow #FFE500 is missing from the feed '
                                'presentation (v1.1 condition 3)')
                else:
                    print('  ok  feed view: one inherited menu, one inherited '
                          'footer, palette scoped')

    # 2b4. Every charting developer has a region somebody decided on.
    #
    # The region layer falls back to "Other" for a developer it does not know,
    # and that fallback was silent: classify() collected the unmapped ones under
    # a comment reading "flag, do not drop", and nothing ever read the flag.
    # Upstage - Seoul - sat unmapped while Solar Pro4 charted at #25, so the
    # published top 30 labelled a Korean model "Other" and 0.64pp of routed
    # share sat outside Asia. It is not findable by eye: the fallback is silent,
    # the total still sums to 100, and Other is a legitimate answer for some
    # developers, so a wrong one looks identical to a right one.
    #
    # A developer under the floor is left alone deliberately - a long tail of
    # one-off listings should not block a deploy over a rounding error.
    origins = ROOT / 'research' / 'model-origins.json'
    madata = ROOT / 'research' / 'model-adoption-data.json'
    if origins.exists() and madata.exists():
        layer = json.loads(origins.read_text(encoding='utf-8'))
        known = set(layer.get('regions_by_developer') or {})
        overrides = layer.get('model_overrides') or {}
        rows = json.loads(madata.read_text(encoding='utf-8')).get('leaderboard') or []
        FLOOR = 0.10          # percent of routed tokens
        stray = {}
        for r in rows:
            model = r.get('model', '')
            if model in overrides:
                continue
            dev = model.split('/')[0] if '/' in model else model
            if dev and dev not in known:
                stray[dev] = stray.get(dev, 0) + (r.get('pct') or 0)
        material = {d: p for d, p in stray.items() if p >= FLOOR}
        if material:
            FAIL.append(
                'model-origins.json has no region for '
                + ', '.join(f'{d} ({p:.2f}% of routed tokens)'
                            for d, p in sorted(material.items(), key=lambda kv: -kv[1]))
                + ' - it is being published as "Other" by default. Add it to '
                  'regions_by_developer with a developer_note, or record Other '
                  'as the decision.')
        else:
            print(f'  ok  model origins: every charting developer above '
                  f'{FLOOR:.2f}% has a region')

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

    # 5. Analytics loads in ONE place, behind consent, and nowhere else.
    #
    # This rule used to be "no GA at all", which was right while consent was
    # undesigned. Consent now exists and GA4 loads from consent.js, so the rule
    # changes shape rather than relaxing - the same LOADING vs USING split that
    # scripts/check-analytics.js makes in the buyer repo.
    #
    # IT ALSO HAD A HOLE, found while changing it: it globbed *.html only. A
    # tag added from any .js file would have passed untouched, which is exactly
    # how this change was made. Scripts are scanned now.
    #
    #   HTML         no GA, ever. A page carrying its own tag is a tag nobody
    #                gated, and it is how a sweep would reintroduce one.
    #   consent.js   the one permitted loader. Must check consent before it
    #                loads, and must check the hostname, because this file is
    #                byte-identical on buyer.yellow3.io where the Next app
    #                loads its own tag - without that check every buyer
    #                page_view would be counted twice.
    #   other .js    refused.
    GA = ('googletagmanager', 'gtag(')
    LOADER = 'consent.js'

    pages = [str(f.relative_to(ROOT)) for f in ROOT.glob('**/*.html')
             if '.git' not in f.parts and 'node_modules' not in f.parts
             and any(n in f.read_text(encoding='utf-8') for n in GA)]
    if pages:
        FAIL.append(f'Google Analytics is inline on {len(pages)} page(s), '
                    f'e.g. {pages[0]} - the tag loads from {LOADER}, never from a page')

    scripts = [str(f.relative_to(ROOT)) for f in ROOT.glob('**/*.js')
               if '.git' not in f.parts and 'node_modules' not in f.parts
               and f.name != LOADER
               and any(n in f.read_text(encoding='utf-8') for n in GA)]
    if scripts:
        FAIL.append(f'Google Analytics loads from {scripts[0]} - it belongs in '
                    f'{LOADER}, which is the only file that checks consent first')

    loader = ROOT / LOADER
    if not loader.exists():
        FAIL.append(f'{LOADER} is missing - the consent gate and the tag both live there')
    else:
        raw = loader.read_text(encoding='utf-8')
        # STRIP COMMENTS BEFORE ASSERTING. The first version of this check
        # passed while the guards were deleted, because consent.js documents
        # its own API in a header comment - `window.y3Consent.granted(...)`
        # and the hostname both appear in prose. A check satisfied by a comment
        # describing the code is a check that cannot fail.
        code = re.sub(r'/\*.*?\*/', '', raw, flags=re.S)
        code = re.sub(r'^\s*//.*$', '', code, flags=re.M)
        code = re.sub(r'^\s*\*.*$', '', code, flags=re.M)

        if not any(n in code for n in GA):
            print('  ok  no analytics anywhere (the tag is not loaded at all)')
        else:
            if "granted('analytics')" not in code:
                FAIL.append(f'{LOADER} loads analytics without checking consent first')
            # Not `'location.hostname' in code` - that string is also in the
            # cookie-clearing helper, so it is true whether or not the tag is
            # guarded. Count the guard itself: defined once, called at least
            # once. Deleting the call drops it to one.
            if code.count('isPublicSite') < 2:
                FAIL.append(f'{LOADER} loads analytics without the isPublicSite() host '
                            'guard - the same file ships on buyer.yellow3.io, which '
                            'loads its own tag, so every page_view there would be '
                            'counted twice')
            if not FAIL:
                print('  ok  analytics loads only from consent.js, behind consent')

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
        # THE ADVICE USED TO BE "run research/gen_og.py" AND THAT DOES NOT FIX
        # IT. gen_og.py renders into a build directory and stops - wiring is a
        # separate step by design. So the operator runs exactly what they were
        # told, sees "rendered 299/299" with no error, and the gate refuses
        # again. Found on a dry run of briefing edition 002; the full sequence
        # is research/briefing-publish-runbook.md.
        FAIL.append(f'{len(missing)} page(s) point at a social card that does '
                    f'not exist, e.g. {missing[0]}\n'
                    f'      run research/gen_og.py, THEN copy the card from '
                    f'$OG_BUILD_DIR/out/ into og/cards/ - gen_og.py renders to '
                    f'the build dir and does not write og/cards itself')
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
