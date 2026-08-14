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
