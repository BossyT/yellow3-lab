#!/usr/bin/env python3
"""
Bake the research instruments into HTML that a crawler can read.

THE PROBLEM THIS FIXES. robots.txt explicitly invites GPTBot, Claude-Web,
anthropic-ai, PerplexityBot, Google-Extended, CCBot and Cohere-ai. When they
arrive at the instruments - the original measurement that is the whole
differentiator - they are served "Loading register" and "The instrument data
could not be loaded". The essays, which are opinion and the most substitutable
thing on the site, index perfectly. The least substitutable half is invisible.

WHAT THIS IS NOT. Not a rendering framework and not a rewrite. The data is
already in the page: the register inlines 190 rows as JSON in #registerData,
and the AI Act instrument fetches a JSON file that lives in this repo. The rows
simply never become HTML. This writes them as HTML, once, at sweep time.

PROGRESSIVE, NOT REPLACING. The static rows sit exactly where the script writes
its own, so on a normal visit JavaScript overwrites them with the interactive
version and nothing changes. Without JavaScript - which is every crawler, and
some readers - the content is simply there.

    python3 research/prerender_instruments.py            # report
    python3 research/prerender_instruments.py --apply
"""
import html, json, pathlib, re, sys

APPLY = '--apply' in sys.argv
ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = '/research/digital-product-passport/suppliers/'

OPEN = '<!-- prerendered:start -->'
CLOSE = '<!-- prerendered:end -->'

def esc(v) -> str:
    return html.escape(str(v if v is not None else ''), quote=True)

# --------------------------------------------------------------- the register
def register_rows(page: str) -> str:
    """The directory, as the script would draw it, minus the interactivity."""
    m = re.search(r'<script id="registerData"[^>]*>(.*?)</script>', page, re.S)
    rows = json.loads(m.group(1))

    out = []
    for r in rows:
        tone = 'verified' if r.get('basis') == 'verified' else 'claimed'
        status = (f"{r['findings']} capability findings" if r.get('findings')
                  else 'Capability research pending')
        # Raw, matching the script. Like `hq`, these carry the register's own
        # footnote markers for what it could not establish; escaped, a crawler
        # read "&lt;sup&gt;2&lt;/sup&gt;" as part of the sector name. Names stay
        # escaped, exactly as the script escapes them - those can be
        # company-supplied.
        chips = ''.join(f'<i>{x}</i>' for x in (r.get('sectors') or [])) \
                or '<i class="empty">No public sector focus</i>'
        facts = r.get('facts') or 0
        out.append(
            f'<article class="supplier" data-row="{esc(r["id"])}">'
            f'<a class="supplier-main" href="{BASE}{esc(r["id"])}">'
            f'<span class="edge {tone}"></span>'
            f'<span class="supplier-name"><span class="avatar">{esc(r.get("initials",""))}</span>'
            f'<span><b>{esc(r["name"])}</b><small>View profile</small></span></span>'
            f'<span><em>{esc(r.get("type",""))}</em></span>'
            # RAW, exactly as the script inserts it. This field carries the
            # register's own footnote markup for a country it could not
            # establish; escaping it printed the tags as visible text.
            f'<span class="hq">{r.get("hq","")}</span>'
            f'<span class="chips">{chips}</span>'
            f'<span class="evidence-cell"><b>{facts} public fact'
            f'{"" if facts == 1 else "s"}</b><small>{esc(status)}</small></span>'
            f'<span class="date">{esc(r.get("date",""))}</span>'
            f'<span class="go" aria-hidden="true"></span></a></article>')
    return '\n'.join(out), len(rows)

# ------------------------------------------------------------- the AI Act book
def ai_act_blocks() -> dict:
    """
    The instrument's own three readable parts: what changed, the record book,
    and the obligation status. Exactly the figures the page draws, in the same
    words, so the static text and the rendered text cannot disagree.
    """
    data = json.loads((ROOT / 'research' / 'eu-ai-act.json').read_text(encoding='utf-8'))
    out = {}

    changed = data.get('what_changed')
    if changed:
        out['changed'] = f'<p class="prerendered-note">{esc(changed)}</p>'

    book = data.get('record_book') or []
    if book:
        cells = ''.join(
            f'<li><strong>{esc(r.get("value",""))}</strong> '
            f'<span>{esc(r.get("label",""))}</span> '
            f'<small>{esc(r.get("caption",""))}</small></li>' for r in book)
        out['records'] = (f'<ul class="prerendered-record-book">{cells}</ul>')

    obligations = data.get('obligations') or []
    if obligations:
        rows = ''.join(
            f'<tr><td>{esc(o.get("label",""))}</td><td>{esc(o.get("note",""))}</td>'
            f'<td>{esc(str(o.get("status","")).replace("_"," "))}</td>'
            f'<td>{esc(o.get("effective",""))}</td></tr>' for o in obligations)
        out['obligations'] = (
            '<table class="prerendered-obligations">'
            '<caption>EU AI Act obligations, status as measured by yellow3 lab.</caption>'
            '<thead><tr><th>Obligation</th><th>Article</th><th>Status</th>'
            '<th>Effective</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>')
    return out

# ------------------------------------------------------------------ insertion
def replace_block(page: str, anchor: str, block: str) -> str:
    """
    Put the block immediately inside `anchor`, wrapped in markers keyed to that
    anchor so regenerating one block never eats another. Idempotent: running
    this twice produces the same file.
    """
    key = re.sub(r'[^a-z0-9]+', '-', anchor.lower())[:60].strip('-')
    o, c = f'<!-- prerendered:{key} -->', f'<!-- /prerendered:{key} -->'
    page = re.sub(re.escape(o) + r'.*?' + re.escape(c) + r'\n?', '', page, flags=re.S)
    # No newline straight after the anchor: the removal above cannot take one
    # back, so adding one each run grew the file by a blank line every sweep.
    return page.replace(anchor, f'{anchor}{o}\n{block}\n{c}\n', 1)

# --------------------------------------------------- the model-adoption view
def model_adoption_blocks() -> dict:
    """The live instrument's substance: the regional split and the ranking.

    THIS PAGE WAS THE LOUDEST CASE OF THE PROBLEM IN THE HEADER ABOVE, and it
    was never covered here. With JavaScript off,
    /research/model-adoption/live was 1,925 characters of navigation carrying
    exactly one sentence of content:

        "The instrument data could not be loaded. Please try again shortly."

    That is #err, which is display:none, so no reader ever saw it - but it is
    what Google's non-JS pass and every LLM text extractor read. No rankings,
    no shares, no model names, no data date, no attribution. The page most
    likely to be quoted on where AI demand is flowing was telling machines the
    instrument had failed.

    No prose is invented here: every figure, name and date is read straight out
    of model-adoption-data.json, and the blocks sit in the containers the
    script overwrites, so a normal visit is unchanged.
    """
    data = json.loads((ROOT / 'research' / 'model-adoption-data.json')
                      .read_text(encoding='utf-8'))
    out = {}

    src = data.get('source') or {}
    asof = esc(data.get('as_of_pretty') or data.get('as_of'))
    win = (data.get('window') or {}).get('current') or []
    window = f' Measured over {esc(win[0])} to {esc(win[1])}.' if len(win) == 2 else ''
    out['live-bar'] = (
        f'<p class="prerendered-note">Data as of {asof}.{window} '
        f'Source: {esc(src.get("name", ""))}'
        + (f' ({esc(src.get("url"))})' if src.get('url') else '') + '.</p>')

    rows = []
    for s in data.get('share') or []:
        delta = s.get('delta_pp')
        move = '' if delta in (None, 0) else f' ({delta:+.2f}pp week on week)'
        n = s.get('models') or 0
        # "0 of the top 30 models" is true and reads as "this region has no
        # models". Europe has one - Mistral Nemo - and it sits at #47 of the 61
        # measured, which is a different statement and the accurate one. Where a
        # region does hold the board, naming what leads it says more than the
        # count does.
        lead = s.get('lead') or {}
        if lead.get('name') and lead.get('rank'):
            led = (f' Led by {esc(lead["name"])}, ranked {esc(lead["rank"])} of '
                   f'{esc(lead.get("of"))} models measured.')
        else:
            led = ''
        board = (f'{esc(n)} of the top 30 models' if n
                 else 'no model in the published top 30')
        rows.append(f'<li>{esc(s.get("region"))}: {esc(s.get("pct"))}% of routed '
                    f'tokens{move}, {board}.{led}</li>')
    # ALWAYS EMIT THE KEY, even with nothing to put in it. Returning fewer
    # keys leaves the PREVIOUS sweep's block sitting in the page, so a
    # collapsed data pull would keep serving last week's numbers under a "Live"
    # badge and build_check's readable-character floor would score them as
    # healthy. Emitting an empty block clears the stale content and lets the
    # floor fail, which is the behaviour the gate exists for.
    out['sb-rows'] = ('<p class="prerendered-note">Regional share of routed '
                      'tokens, by where the model was built.</p><ul>'
                      + ''.join(rows) + '</ul>') if rows else ''

    # THE NO-JAVASCRIPT BASELINE IS THE APPROVED CARD, not a list.
    #
    # The v2 handoff is explicit: "The server-rendered page must expose the full
    # 30-card list and internal links without requiring JavaScript." This block
    # is what a crawler and a reader without JS actually get, so it emits the
    # same anchors, the same routes and the same facts the script renders - and
    # the script overwrites it on a normal visit, so nothing is drawn twice.
    #
    # Only the twelve supplied provider marks are used. A developer this map
    # does not know renders the neutral mark, which is the truthful answer for
    # a stealth model rather than an invented logo.
    LOGO_DIR = '/img/model-adoption/provider-logos/'
    LOGO_MAP = {'deepseek': 'deepseek', 'openai': 'openai', 'z.ai': 'z-ai', 'zai': 'z-ai',
                'xiaomi': 'xiaomi', 'tencent': 'tencent', 'nvidia': 'nvidia',
                'google': 'google', 'minimax': 'minimax', 'moonshot': 'moonshot',
                'anthropic': 'anthropic', 'poolside': 'poolside', 'upstage': 'upstage'}
    REGION_LABEL = {'US': 'United States'}
    rows30 = (data.get('leaderboard') or [])[:30]
    top = max([r.get('pct') or 0 for r in rows30] + [1])
    cards = []
    for r in rows30:
        key = str(r.get('developer') or '').strip().lower()
        asset = LOGO_MAP.get(key)
        logo = (f'<img src="{LOGO_DIR}{asset}.svg" alt="" width="32" height="32">'
                if asset else '?')
        prev, rank = r.get('prev_rank'), r.get('rank')
        if r.get('new') or prev is None:
            move = '<span class="y3-card-move y3-new">New</span>'
        elif prev - rank > 0:
            move = f'<span class="y3-card-move y3-up">&#9650; {prev - rank}</span>'
        elif prev - rank < 0:
            move = f'<span class="y3-card-move y3-down">&#9660; {rank - prev}</span>'
        else:
            move = '<span class="y3-card-move">&ndash; Unchanged</span>'
        region = REGION_LABEL.get(r.get('region'), r.get('region'))
        width = round((r.get('pct') or 0) / top * 100, 1)
        cards.append(
            f'<a class="y3-model-card{" is-leader" if rank == 1 else ""}" '
            f'href="/research/model-adoption/{esc(r.get("slug"))}" '
            f'aria-label="Open {esc(r.get("name"))} model record">'
            f'<span class="y3-card-top"><span class="y3-card-rank">Rank {esc(rank)}</span>'
            f'{move}</span>'
            f'<span class="y3-model-id"><span class="y3-model-logo'
            f'{"" if asset else " is-undisclosed"}">{logo}</span>'
            f'<span><span class="y3-card-name">{esc(r.get("name"))}</span>'
            f'<span class="y3-card-meta">{esc(r.get("developer"))} / {esc(region)}</span>'
            f'</span></span>'
            f'<span class="y3-card-signal"><span>'
            f'<span class="y3-card-share">{esc(r.get("pct"))}%</span>'
            f'<span class="y3-card-share-label">Routed share</span></span>'
            f'<span class="y3-card-open">Open model record &#8594;</span></span>'
            f'<span class="y3-track"><span class="y3-fill" style="width:{width}%"></span></span>'
            f'</a>')
    out['ranking'] = ''.join(cards)
    out['lb-sub'] = (f'{len(rows30)} model cards ranked by routed share for the seven '
                     f'days ending {asof}. Open any card for its economics, '
                     f'capabilities, history and evidence.') if rows30 else ''
    return out


def refresh_line() -> str:
    """The header's refresh text, from the same data the script reads."""
    data = json.loads((ROOT / 'research' / 'model-adoption-data.json')
                      .read_text(encoding='utf-8'))
    when = data.get('refreshed_cet')
    asof = data.get('as_of_pretty') or data.get('as_of')
    if not (when or asof):
        return ''
    parts = []
    if when:
        parts.append(f'Refreshed {esc(when)}')
    if asof:
        parts.append(f'data as of {esc(asof)}')
    return ' &middot; '.join(parts)


# ------------------------------------------------ the DPP instrument's signals
def dpp_blocks() -> dict:
    """
    The DPP instrument's readable substance: the thesis, this week's reading,
    and the signals with their calls. Same figures the page draws.
    """
    data = json.loads((ROOT / 'research' / 'digital-product-passport.json')
                      .read_text(encoding='utf-8'))
    out = {}

    thesis = data.get('thesis')
    read = data.get('this_week_read')
    if thesis or read:
        parts = []
        if thesis:
            parts.append(f'<p class="prerendered-note"><strong>{esc(thesis)}</strong></p>')
        if isinstance(read, str) and read:
            parts.append(f'<p class="prerendered-note">{esc(read)}</p>')
        out['thesis'] = '\n'.join(parts)

    signals = data.get('signals') or []
    if signals:
        items = []
        for sg in signals:
            if not isinstance(sg, dict):
                continue
            title = sg.get('title') or sg.get('label') or sg.get('name') or ''
            detail = sg.get('detail') or sg.get('summary') or sg.get('note') or ''
            when = sg.get('date') or sg.get('as_of') or ''
            items.append(f'<li><strong>{esc(title)}</strong>'
                         f'{(" " + esc(detail)) if detail else ""}'
                         f'{(" <small>" + esc(when) + "</small>") if when else ""}</li>')
        if items:
            out['signals'] = ('<ul class="prerendered-signals">'
                              + ''.join(items) + '</ul>')
    return out

def main() -> int:
    changed = []

    # 1. the supplier directory
    p = ROOT / 'research' / 'digital-product-passport' / 'suppliers.html'
    page = p.read_text(encoding='utf-8')
    rows_html, n = register_rows(page)
    anchor = '<div class="rows" id="dirRows">'
    if anchor not in page:
        print('  register: row container not found, nothing written')
    else:
        new = replace_block(page, anchor, rows_html)
        changed.append((p, new, f'{n} supplier rows'))

    # 2. the AI Act instrument: three containers, three blocks
    p2 = ROOT / 'research' / 'eu-ai-act.html'
    page2 = p2.read_text(encoding='utf-8')
    blocks = ai_act_blocks()
    wrote = []
    for element_id, block in blocks.items():
        m2 = re.search(rf'<[a-z]+[^>]*\bid="{element_id}"[^>]*>', page2)
        if not m2:
            print(f'  eu-ai-act: no #{element_id} container, skipped')
            continue
        page2 = replace_block(page2, m2.group(0), block)
        wrote.append(element_id)
    if wrote:
        changed.append((p2, page2, 'sections: ' + ', '.join(wrote)))

    # 3. the DPP instrument
    p3 = ROOT / 'research' / 'digital-product-passport.html'
    page3 = p3.read_text(encoding='utf-8')
    wrote3 = []
    for element_id, block in dpp_blocks().items():
        m3 = re.search(rf'<[a-z]+[^>]*\bid="{element_id}"[^>]*>', page3)
        if not m3:
            print(f'  digital-product-passport: no #{element_id} container, skipped')
            continue
        page3 = replace_block(page3, m3.group(0), block)
        wrote3.append(element_id)
    if wrote3:
        changed.append((p3, page3, 'sections: ' + ', '.join(wrote3)))

    # 4. the model-adoption instrument. Same containers the script overwrites,
    #    so a normal visit is unchanged and a crawler stops being told the
    #    instrument failed.
    p4 = ROOT / 'research' / 'model-adoption' / 'live.html'
    if not p4.exists():
        print('  model-adoption: live.html is missing, skipped')
    else:
        page4 = p4.read_text(encoding='utf-8')
        wrote4 = []
        for element_id, block in model_adoption_blocks().items():
            m4 = re.search(rf'<[a-z]+[^>]*\bid="{element_id}"[^>]*>', page4)
            if not m4:
                print(f'  model-adoption: no #{element_id} container, skipped')
                continue
            page4 = replace_block(page4, m4.group(0), block)
            wrote4.append(element_id)
        # #refresh is a TEXT placeholder, not an empty container, so it is
        # rewritten in place rather than filled. Left alone it told a crawler
        # "Loading latest refresh..." on a page whose data had been sitting in
        # the repo since 07:09 that morning. A human still gets the script's
        # value a moment later; on a slow connection they now see the last
        # known refresh instead of a spinner's worth of nothing.
        refreshed = refresh_line()
        if refreshed:
            page4, n4 = re.subn(
                r'(<span class="refresh" id="refresh">).*?(</span>)',
                lambda m: m.group(1) + refreshed + m.group(2), page4, count=1, flags=re.S)
            if n4:
                wrote4.append('refresh')
        if wrote4:
            changed.append((p4, page4, 'sections: ' + ', '.join(wrote4)))

    for path, content, what in changed:
        print(f'  {path.relative_to(ROOT)}: {what}'
              + ('  (written)' if APPLY else '  (would write)'))
        if APPLY:
            path.write_text(content, encoding='utf-8')

    if not APPLY:
        print('\n  dry run. Add --apply to write.\n')
    return 0

if __name__ == '__main__':
    sys.exit(main())
