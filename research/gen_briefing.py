#!/usr/bin/env python3
"""
yellow3 Research Intelligence - Monday Briefing.

Renders the FROZEN briefing template from research/briefings.json.

    /research/digital-product-passport/weekly-briefing              latest
    /research/digital-product-passport/weekly-briefing/YYYY-MM-DD   archive

THE DESIGN IS LOCKED AND THIS FILE DOES NOT OWN IT. The composition, hierarchy,
interaction model and colour come from the approved handover (v1.1, locked
21 Aug 2026, runtime amendment 23 Aug 2026, design owner ChatGPT, approved by
Thomas). This generator ports that design class for class into the static site:
every class name in the approved CSS survives unchanged, so a future design
revision can be diffed against the source rather than re-derived from here.

WHAT WAS ADAPTED, AND WHY IT CHANGES NO PIXEL OF THE APPROVED RENDER:

  the harness      The prototype styles `html`, `body` and a bare `h1`, and
                   centres the frame on a grey page with a drop shadow. That is
                   its standalone demo wrapper, not the design - 01-DESIGN-SPEC
                   puts the briefing "inside the existing yellow3.io content
                   shell" and locks the page surface to #ffffff. Element
                   selectors are therefore scoped under .briefing so they cannot
                   reach the site header, footer or the rest of the page.
  React -> DOM     yellow3.io is static HTML. The player is the same state
                   machine written in vanilla JS against the same class names.
  media            Each edition's video is served from the public Vercel Blob
                   store rather than committed. A 33 MB recording every Monday
                   would add over 1.5 GB a year to a public git repository, and
                   05-ROUTE-AND-INTEGRATION leaves delivery to production.

THE ONE OPEN DESIGN QUESTION IS FLAGGED, NOT DECIDED. See DEVIATIONS below.

WHAT THIS REFUSES TO PUBLISH. 04-WEEKLY-CONTENT-CONTRACT makes these blocking,
and 07-QA-ACCEPTANCE makes shipping any of them an immediate rejection:

  - no issue number, or the literal TBC
  - no research note number
  - no media duration, or a duration not read from the edition's own media
  - fewer than four numeric timing markers
  - an empty or incomplete transcript
  - an empty source list, or a source missing publisher, title, URL or checked
    timestamp

AND IT REFUSES THE SAMPLE VALUES SPECIFICALLY. The handover ships a 53.527
second reference recording with markers at 0/14/27/41. Those belong to a
different script. If an edition arrives carrying them, that is a copy-paste and
not a measurement, so the generator stops. This is the rule the QA document
calls out twice: "no sample duration or sample timing marker is used as a
production fallback".

    python3 research/gen_briefing.py            write the pages
    python3 research/gen_briefing.py --check    validate only, write nothing
    python3 research/gen_briefing.py --preview  render a draft edition to
                                                research/.preview/ for QA
                                                screenshots. NEVER publishes.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / 'research' / 'briefings.json'
OUT_DIR = ROOT / 'research' / 'digital-product-passport' / 'weekly-briefing'
PREVIEW_DIR = ROOT / 'research' / '.preview'
BASE = 'https://www.yellow3.io'
ROUTE = '/research/digital-product-passport/weekly-briefing'

# The reference recording shipped for player testing. Never an edition value.
SAMPLE_DURATION = 53.527
SAMPLE_MARKERS = [0, 14, 27, 41]


# ---------------------------------------------------------------------------
# Site shell. Copied from the existing research pages so the briefing carries
# the standard menu and footer - see the public-shell rule. site_nav.py sweeps
# these after generation and is the authority if they ever drift.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# THE SITE SHELL IS TAKEN FROM /research, NEVER WRITTEN HERE.
#
# The first build copied the header and footer out of the Digital Product
# Passport hub page, which carries an OLDER shell, and then styled them by hand.
# The result differed from the rest of the site in ways nobody authorised:
#
#     footer background   #ffffff instead of #0e0e0e, with dark text
#     header CTA          "Work with us" -> /advisory, instead of "Get in touch"
#     footer Research     "The method" inserted, "EU AI Act" dropped
#
# GPT's correction order, 23 Aug: reuse the shared shell, do not copy, recreate
# or locally restyle it. This site is static HTML with no include mechanism, so
# "reuse" means the generator READS research.html on every run and takes the
# nav, the footer and the shell CSS out of it verbatim. Drift is then not
# something a check has to notice - it cannot happen, because there is only one
# copy and it is read at build time.
#
# If research.html is restyled tomorrow, this page follows on the next generate.

SHELL_PAGE = ROOT / 'research.html'

# Every selector that belongs to the shell rather than to an instrument. A rule
# is kept when its selector list mentions one of these; everything else in
# research.html stays behind, because this page is not that page.
SHELL_SELECTORS = (
    # The universal reset belongs to the shell too. Leaving it out left the
    # browser's default 8px body margin in place, and the frame sat inset by
    # 8px at 390 and 320 instead of full bleed - a visible deviation from the
    # approved mobile treatment that the footer comparison could not see,
    # because it only looked at the footer.
    '*', ':root', 'html', 'body', 'img', '.site-nav', '.brand', '.nav-mid', '.nav-cta',
    '.nav-toggle', '.site-footer', '.foot-top', '.foot-brand', '.fb-lab',
    '.foot-col', '.foot-contact', '.foot-social', '.foot-bottom', '.foot-legal',
    '.inner',
)


def _rules(css: str):
    """Yield (selector, body) for top-level rules, and (@media ..., inner) blocks."""
    i, n = 0, len(css)
    while i < n:
        brace = css.find('{', i)
        if brace == -1:
            return
        sel = css[i:brace].strip()
        depth, j = 1, brace + 1
        while j < n and depth:
            if css[j] == '{':
                depth += 1
            elif css[j] == '}':
                depth -= 1
            j += 1
        yield sel, css[brace + 1:j - 1]
        i = j


def _wanted(selector: str) -> bool:
    parts = [p.strip() for p in selector.split(',')]
    return any(any(tok in p for tok in SHELL_SELECTORS) for p in parts)


def shell() -> tuple[str, str, str]:
    """(nav markup, footer markup, shell css) lifted from /research."""
    page = SHELL_PAGE.read_text(encoding='utf-8')

    nav = re.search(r'<nav class="site-nav".*?</nav>', page, re.S)
    foot = re.search(r'<footer class="site-footer".*?</footer>', page, re.S)
    style = re.search(r'<style>(.*?)</style>', page, re.S)
    if not (nav and foot and style):
        raise SystemExit('could not read the shell out of research.html - it has '
                         'changed shape, and this page must not invent one.')

    out: list[str] = []
    for sel, body in _rules(style.group(1)):
        if sel.startswith('@media'):
            inner = [f'    {s} {{{b}}}' for s, b in _rules(body) if _wanted(s)]
            if inner:
                out.append(f'    {sel} {{\n' + '\n'.join(inner) + '\n    }')
        elif sel.startswith('@'):
            continue
        elif _wanted(sel):
            out.append(f'    {sel} {{{body}}}')

    return ('  ' + nav.group(0).strip() + '\n',
            '  ' + foot.group(0).strip() + '\n',
            '\n'.join(out))


def e(value: str) -> str:
    """Escape for HTML text. Approved copy is never otherwise transformed."""
    return html.escape(str(value), quote=True)


def mmss(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f'{seconds // 60:02d}:{seconds % 60:02d}'


def iso8601(seconds: float) -> str:
    """ISO 8601 duration for the VideoObject, from the real media length."""
    total = int(round(seconds))
    return f'PT{total // 60}M{total % 60}S'


# ---------------------------------------------------------------------------
# Publication gate
# ---------------------------------------------------------------------------

def blockers(ed: dict) -> list[str]:
    """Everything that must be resolved before this edition can be published."""
    out: list[str] = []
    slug = ed.get('slug', '?')

    def unresolved(v) -> bool:
        return v is None or (isinstance(v, str) and v.strip().upper() in ('', 'TBC'))

    if unresolved(ed.get('issueNumber')):
        out.append(f'{slug}: issueNumber is unresolved')
    if unresolved(ed.get('researchNote')):
        out.append(f'{slug}: researchNote is unresolved')

    # NO FUTURE EVIDENCE TIMESTAMP. The first build published
    # "CHECKED 24 AUG 2026 06:30 CET" while the source records said 23 August -
    # a PLANNED publication time standing in for an evidence time, and in the
    # future at the moment it deployed. An instrument whose whole claim is that
    # the evidence was checked cannot date that check tomorrow.
    checked = ed.get('checkedAt')
    if unresolved(checked):
        out.append(f'{slug}: checkedAt is unset. It must be a real completed check, '
                   'ISO 8601 with offset - never a planned publication time.')
    else:
        try:
            when = dt.datetime.fromisoformat(str(checked))
        except ValueError:
            out.append(f'{slug}: checkedAt is not ISO 8601 with an offset: {checked!r}')
        else:
            if when.tzinfo is None:
                out.append(f'{slug}: checkedAt has no UTC offset: {checked!r}')
            elif when > dt.datetime.now(dt.timezone.utc):
                out.append(f'{slug}: checkedAt {checked} is in the FUTURE. That is a '
                           'planned time, not a completed check.')
            else:
                for i, src in enumerate(ed.get('sources') or [], 1):
                    try:
                        sw = dt.datetime.fromisoformat(str(src.get('checkedAt')))
                    except (ValueError, TypeError):
                        continue
                    if sw > when + dt.timedelta(minutes=1):
                        out.append(f'{slug}: source {i} was checked {src["checkedAt"]}, '
                                   f'AFTER the edition\'s own checkedAt {checked} - the '
                                   'footer and the source records disagree.')

    video = ed.get('video') or {}
    if unresolved(video.get('src')):
        out.append(f'{slug}: no media source')
    if unresolved(video.get('poster')):
        out.append(f'{slug}: no poster frame')

    duration = video.get('durationSeconds')
    if not isinstance(duration, (int, float)) or duration <= 0:
        out.append(f'{slug}: durationSeconds must be measured from the edition media')
    elif abs(float(duration) - SAMPLE_DURATION) < 0.01:
        out.append(f'{slug}: durationSeconds is the handover sample ({SAMPLE_DURATION}s). '
                   'That is the reference recording, not this edition.')

    stories = ed.get('stories') or []
    if len(stories) != 4:
        out.append(f'{slug}: exactly four reporting sections are required, found {len(stories)}')
    marks = [s.get('startSeconds') for s in stories]
    if any(not isinstance(m, (int, float)) for m in marks):
        out.append(f'{slug}: all four timing markers must be numeric, found {marks}')
    elif marks == SAMPLE_MARKERS:
        out.append(f'{slug}: timing markers are the handover sample {SAMPLE_MARKERS}. '
                   'Markers are measured from this edition\'s own recording.')
    elif isinstance(duration, (int, float)):
        if marks != sorted(marks):
            out.append(f'{slug}: timing markers are not in order: {marks}')
        if marks and marks[0] != 0:
            out.append(f'{slug}: story 01 must be active from zero, found {marks[0]}')
        if marks and marks[-1] >= duration:
            out.append(f'{slug}: last marker {marks[-1]}s is beyond the media duration {duration}s')

    # A HUMAN MUST HAVE HEARD THE MARKERS. GPT's issue 001 ruling, 23 Aug 2026:
    # "The calculation method is credible, but the contract requires the markers
    # to match Astrid's audible spoken transitions... Do not convert algorithmic
    # agreement into human approval." Four numeric markers that agree with a
    # word-share estimate are a measurement, not an approval, and this gate
    # exists so that distinction survives the week somebody is in a hurry.
    if not ed.get('markersConfirmed'):
        out.append(f'{slug}: timing markers are not confirmed - somebody has to LISTEN to '
                   'the recording and set markersConfirmed. Measured is not approved.')

    transcript = ed.get('transcript') or []
    if not transcript or not any(str(p).strip() for p in transcript):
        out.append(f'{slug}: transcript is empty')

    sources = ed.get('sources') or []
    if not sources:
        out.append(f'{slug}: source list is empty - every material claim needs a verified source')
    for i, s in enumerate(sources, 1):
        for field in ('publisher', 'title', 'url', 'checkedAt'):
            if unresolved(s.get(field)):
                out.append(f'{slug}: source {i} has no {field}')
        url = str(s.get('url', ''))
        if url and not url.startswith('https://'):
            out.append(f'{slug}: source {i} url is not a direct public https link')

    for story in stories:
        text = ' '.join(str(story.get(k, '')) for k in ('headline', 'consequence'))
        if re.search(r'\bDPP\b', text):
            out.append(f'{slug}: story {story.get("number")} uses the standalone term DPP '
                       'in public copy - the full phrase is required')

    return out


# ---------------------------------------------------------------------------
# The locked design, ported class for class from briefing-reference.css
# ---------------------------------------------------------------------------

BRIEFING_CSS = """
    /* ------------------------------------------------------------------
       MONDAY BRIEFING - FROZEN TEMPLATE.
       Ported class for class from the approved handover v1.1. Do not
       restyle. A design change comes from ChatGPT as a new handover, is
       applied to this block, and the pages are regenerated.

       The approved signal yellow is #ffe500 and is NOT the site token
       --yellow (#ffe000). DESIGN_LOCK calls #ffe500 exact, so it is
       scoped to this component rather than changed site-wide.
       ------------------------------------------------------------------ */
    .briefing {
      --yellow: #ffe500;
      --black: #090909;
      --b-ink: #171717;
      --b-grey: #6b6b6b;
      --b-line: #cfcfcf;
      --soft: #f1f3f3;
      --stage: #e9eeee;
      width: min(1360px, 100%);
      margin: 0 auto;
      background: #fff;
      color: var(--b-ink);
      font-family: Arial, Helvetica, sans-serif;
      line-height: normal;
      overflow: hidden;
    }
    .briefing *, .briefing *::before, .briefing *::after { box-sizing: border-box; }
    .briefing button, .briefing input { font: inherit; }
    .briefing button { color: inherit; }
    .briefing p { margin: 0; }

    .briefing .yellow-signal { height: 7px; background: var(--yellow); }

    .briefing .masthead {
      min-height: 69px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 24px;
      padding: 12px 26px 11px;
      border-bottom: 1px solid var(--black);
    }
    .briefing .eyebrow,
    .briefing .section-kicker,
    .briefing .date-label,
    .briefing .story-meta,
    .briefing .story-marker > span,
    .briefing .signal-cell span,
    .briefing .footer-meta span {
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.14em;
    }
    .briefing .issue { margin-top: 8px; color: var(--b-grey); font-size: 11px; }
    .briefing .date-block { text-align: right; }
    .briefing .date-label { color: var(--b-grey); font-size: 9px; }
    .briefing .date-value { margin-top: 8px; font-size: 13px; font-weight: 700; }

    .briefing .briefing-grid { display: grid; grid-template-columns: 400px minmax(0, 1fr); }
    .briefing .presenter { min-width: 0; background: var(--stage); }

    .briefing .video-stage {
      position: relative;
      height: 510px;
      overflow: hidden;
      background: var(--stage);
    }
    .briefing .astrid-video {
      display: block;
      width: 100%;
      height: 100%;
      object-fit: contain;
      background: var(--stage);
    }
    .briefing .video-topline {
      position: absolute;
      inset: 0 0 auto 0;
      z-index: 2;
      min-height: 36px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 0 18px;
      background: rgba(0, 0, 0, 0.86);
      color: #fff;
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.1em;
    }
    .briefing .stage-play {
      position: absolute;
      left: 50%;
      bottom: 26px;
      z-index: 3;
      transform: translateX(-50%);
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 175px;
      justify-content: center;
      padding: 13px 16px;
      border: 0;
      background: var(--black);
      color: #fff;
      cursor: pointer;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.12em;
    }
    .briefing .stage-play:hover,
    .briefing .stage-play:focus-visible { background: #222; }
    .briefing .stage-play[disabled] { cursor: progress; opacity: 0.85; }
    .briefing .stage-message {
      position: absolute;
      left: 50%;
      bottom: 26px;
      z-index: 3;
      transform: translateX(-50%);
      width: calc(100% - 36px);
      padding: 13px 16px;
      background: var(--black);
      color: #fff;
      text-align: center;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.06em;
    }

    .briefing .play-triangle,
    .briefing .mini-triangle {
      width: 0;
      height: 0;
      border-top: 6px solid transparent;
      border-bottom: 6px solid transparent;
      border-left: 10px solid var(--yellow);
    }
    .briefing .mini-triangle { border-top-width: 5px; border-bottom-width: 5px; border-left-width: 8px; }
    .briefing .pause-bars { width: 8px; height: 11px; border-left: 3px solid var(--yellow); border-right: 3px solid var(--yellow); }

    .briefing .transport {
      min-height: 50px;
      display: grid;
      grid-template-columns: auto minmax(80px, 1fr) auto auto;
      align-items: center;
      gap: 14px;
      padding: 0 18px;
      background: var(--black);
      color: #fff;
    }
    .briefing .transport-button,
    .briefing .sound-button {
      display: flex;
      align-items: center;
      gap: 9px;
      padding: 0;
      border: 0;
      background: transparent;
      color: #fff;
      cursor: pointer;
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.1em;
    }
    .briefing .sound-button { color: var(--yellow); }
    .briefing .progress-label { display: flex; }
    .briefing .progress {
      --progress: 0%;
      width: 100%;
      height: 3px;
      margin: 0;
      border: 0;
      border-radius: 0;
      -webkit-appearance: none;
      appearance: none;
      background: linear-gradient(to right, var(--yellow) var(--progress), #4b4b4b var(--progress));
      cursor: pointer;
    }
    .briefing .progress::-webkit-slider-thumb {
      width: 10px; height: 10px; -webkit-appearance: none; appearance: none;
      border: 0; border-radius: 50%; background: var(--yellow);
    }
    .briefing .progress::-moz-range-thumb {
      width: 10px; height: 10px; border: 0; border-radius: 50%; background: var(--yellow);
    }
    .briefing .timecode { white-space: nowrap; font-size: 10px; font-variant-numeric: tabular-nums; }

    .briefing .stories { min-width: 0; background: #fff; }
    .briefing .stories-intro {
      min-height: 100px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 32px;
      padding: 16px 28px;
      border-bottom: 1px solid var(--black);
    }
    .briefing .section-kicker { color: var(--b-grey); }
    .briefing .briefing-title {
      margin: 10px 0 0;
      font-size: clamp(27px, 2.6vw, 38px);
      font-weight: 700;
      line-height: 1;
      letter-spacing: -0.035em;
      color: var(--b-ink);
    }
    .briefing .intro-note { flex: 0 0 auto; color: var(--b-grey); text-align: right; font-size: 13px; line-height: 1.45; }
    .briefing .intro-note strong { color: var(--b-ink); }

    .briefing .story-list { height: 460px; display: grid; grid-template-rows: repeat(4, 1fr); }
    .briefing .story-row {
      position: relative;
      min-width: 0;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 105px;
      align-items: center;
      gap: 26px;
      padding: 14px 28px;
      border: 0;
      border-bottom: 1px solid var(--b-line);
      background: #fff;
      text-align: left;
      cursor: pointer;
      font-family: inherit;
    }
    .briefing .story-row:last-child { border-bottom: 0; }
    .briefing .story-row:hover,
    .briefing .story-row:focus-visible { background: #f7f8f8; }
    .briefing .story-row.active { background: var(--soft); }
    .briefing .story-row.active::before {
      content: "";
      position: absolute;
      inset: 0 auto 0 0;
      width: 6px;
      background: var(--yellow);
    }
    .briefing .story-main { min-width: 0; display: block; }
    .briefing .story-meta { display: block; color: var(--b-grey); font-size: 10px; }
    .briefing .story-meta strong { margin-right: 8px; color: var(--b-grey); }
    .briefing .story-headline {
      display: block;
      margin-top: 10px;
      font-size: clamp(16px, 1.45vw, 20px);
      font-weight: 700;
      line-height: 1.15;
    }
    .briefing .story-detail { display: block; margin-top: 7px; color: var(--b-grey); font-size: 13px; line-height: 1.25; }
    .briefing .story-marker { align-self: start; padding-top: 3px; text-align: right; }
    .briefing .story-marker > span { display: block; color: var(--b-grey); font-size: 8px; letter-spacing: 0.08em; }
    .briefing .story-marker strong { display: block; margin-top: 16px; font-size: 12px; }

    .briefing .signal-strip {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      margin-left: 400px;
      background: var(--black);
      color: #fff;
    }
    .briefing .signal-cell {
      min-height: 50px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 0 20px;
      border-left: 1px solid #4a4a4a;
    }
    .briefing .signal-cell:first-child { border-left: 0; }
    .briefing .signal-cell span { color: #b7b7b7; font-size: 8px; }
    .briefing .signal-cell strong { color: var(--yellow); font-size: 18px; }

    .briefing .evidence-footer {
      min-height: 94px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 30px;
      padding: 15px 26px;
    }
    .briefing .evidence-statement { display: flex; flex-direction: column; gap: 13px; font-size: 14px; }
    .briefing .footer-rule { width: 70px; height: 5px; background: var(--yellow); }
    .briefing .footer-meta { display: flex; flex-direction: column; gap: 10px; text-align: right; font-size: 10px; }
    .briefing .footer-meta span { color: var(--b-grey); font-size: 8px; }

    .briefing .sr-only {
      position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
      overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
    }

    @media (max-width: 1050px) {
      .briefing .briefing-grid { grid-template-columns: 330px minmax(0, 1fr); }
      .briefing .video-stage { height: 470px; }
      .briefing .story-list { height: 420px; }
      .briefing .signal-strip { margin-left: 330px; }
      .briefing .story-row { grid-template-columns: minmax(0, 1fr) 86px; gap: 14px; padding-inline: 20px; }
      .briefing .story-detail { font-size: 12px; }
      .briefing .sound-button { display: none; }
      .briefing .transport { grid-template-columns: auto minmax(70px, 1fr) auto; }
    }

    @media (max-width: 760px) {
      .briefing { width: 100%; }
      .briefing .masthead { padding-inline: 18px; }
      .briefing .briefing-grid { display: flex; flex-direction: column; }
      .briefing .video-stage { height: min(124vw, 570px); }
      .briefing .stories-intro { min-height: 112px; align-items: flex-end; padding: 20px 18px; }
      .briefing .briefing-title { font-size: 30px; }
      .briefing .intro-note { display: none; }
      .briefing .story-list { height: auto; display: block; }
      .briefing .story-row { min-height: 132px; grid-template-columns: minmax(0, 1fr) 72px; padding: 18px; }
      .briefing .story-headline { font-size: 17px; }
      .briefing .signal-strip { grid-template-columns: repeat(2, 1fr); margin-left: 0; }
      .briefing .signal-cell:nth-child(3) { border-left: 0; border-top: 1px solid #4a4a4a; }
      .briefing .signal-cell:nth-child(4) { border-top: 1px solid #4a4a4a; }
      .briefing .evidence-footer { align-items: flex-start; flex-direction: column; padding: 22px 18px; }
      .briefing .footer-meta { text-align: left; }
    }

    @media (max-width: 430px) {
      .briefing .eyebrow,
      .briefing .date-value { font-size: 10px; }
      .briefing .issue { font-size: 9px; }
      .briefing .date-label,
      .briefing .date-value { white-space: nowrap; }
      .briefing .transport { gap: 10px; padding-inline: 14px; }
      .briefing .timecode { font-size: 9px; }
    }

    @media (prefers-reduced-motion: reduce) {
      .briefing * { transition: none !important; animation: none !important; }
    }

    /* ------------------------------------------------------------------
       EDITION RECORD - below the locked frame, in the existing research
       page language. 08-DESIGN-DECISIONS: "visually quiet, square
       geometry and thin rules, no cards, badges or new colour."
       ------------------------------------------------------------------ */
    .edition-record { max-width: 1360px; margin: 0 auto; padding: 64px 0 20px; }
    @media (max-width: 760px) { .edition-record { padding: 44px 18px 20px; } .briefing-page .breadcrumb { padding: 0 18px; } }
    .edition-record .rec-head { font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--muted); font-weight: 600; margin-bottom: 22px; }
    .edition-record .edition-cols { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(0, 1fr); gap: 56px; align-items: start; }
    .edition-record .transcript h2, .edition-record .sources h2 { font-size: 22px; font-weight: 400; letter-spacing: -0.02em; margin-bottom: 18px; padding-bottom: 12px; border-bottom: 1px solid var(--line); }
    .edition-record .transcript p { font-size: 16px; line-height: 1.7; color: var(--body); margin-bottom: 16px; }
    .edition-record .sources ol { list-style: none; counter-reset: src; }
    .edition-record .sources li { counter-increment: src; padding: 14px 0; border-bottom: 1px solid var(--line); font-size: 14px; }
    .edition-record .sources li::before { content: counter(src, decimal-leading-zero); display: block; font-size: 10px; letter-spacing: 0.14em; color: var(--muted); font-weight: 700; margin-bottom: 6px; }
    .edition-record .sources .src-pub { display: block; font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted); font-weight: 700; margin-bottom: 5px; }
    .edition-record .sources a { color: var(--ink); text-decoration: none; border-bottom: 1px solid var(--line); overflow-wrap: anywhere; }
    .edition-record .sources a:hover { border-bottom-color: var(--ink); }
    .edition-record .sources .src-checked { display: block; margin-top: 6px; font-size: 11px; color: var(--muted); }
    .edition-record .correction { margin-top: 32px; padding: 18px 22px; border-left: 3px solid var(--yellow); background: var(--panel); font-size: 14px; color: var(--body); }
    .edition-record .edition-nav { display: flex; justify-content: space-between; gap: 24px; margin-top: 48px; padding-top: 22px; border-top: 1px solid var(--line); font-size: 12px; letter-spacing: 0.06em; text-transform: uppercase; font-weight: 600; }
    .edition-record .edition-nav a { color: var(--ink); text-decoration: none; }
    .edition-record .edition-nav a:hover { color: var(--muted); }
    .edition-record .edition-nav .spacer { color: var(--muted); }

    @media (max-width: 900px) {
      .edition-record .edition-cols { grid-template-columns: 1fr; gap: 44px; }
      .edition-record { padding-top: 44px; }
    }
"""


PLAYER_JS = r"""
  (function () {
    var root = document.querySelector('.briefing');
    if (!root) return;
    var video = root.querySelector('.astrid-video');
    var stagePlay = root.querySelector('.stage-play');
    var transport = root.querySelector('.transport-button');
    var transportIcon = transport ? transport.querySelector('.transport-icon') : null;
    var transportText = transport ? transport.querySelector('.transport-text') : null;
    var sound = root.querySelector('.sound-button');
    var progress = root.querySelector('.progress');
    var elapsed = root.querySelector('.timecode-elapsed');
    var total = root.querySelector('.timecode-total');
    var toplineTotal = root.querySelector('.topline-total');
    var rows = Array.prototype.slice.call(root.querySelectorAll('.story-row'));
    if (!video) return;

    // Markers come from the edition, never from a constant in this file.
    var marks = rows.map(function (r) { return parseFloat(r.getAttribute('data-at')); });
    var preparing = false;

    function fmt(v) {
      var s = isFinite(v) && v > 0 ? Math.floor(v) : 0;
      return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
    }

    // The duration shown is the media's own. Until the browser reports it the
    // display stays '--:--' rather than borrowing a previous edition's number.
    function showDuration() {
      var d = video.duration;
      var text = isFinite(d) && d > 0 ? fmt(d) : '--:--';
      if (total) total.textContent = text;
      if (toplineTotal) toplineTotal.textContent = text;
      if (progress && isFinite(d) && d > 0) progress.max = String(d);
    }

    function activeIndex(t) {
      var active = 0;
      for (var i = 0; i < marks.length; i++) { if (t >= marks[i]) active = i; }
      return active;
    }

    function paint() {
      var t = video.currentTime || 0;
      var d = video.duration;
      if (elapsed) elapsed.textContent = fmt(t);
      if (progress) {
        progress.value = String(Math.min(t, isFinite(d) && d > 0 ? d : t));
        progress.style.setProperty('--progress',
          (isFinite(d) && d > 0 ? (t / d) * 100 : 0) + '%');
      }
      var idx = activeIndex(t);
      rows.forEach(function (row, i) {
        var on = i === idx;
        row.classList.toggle('active', on);
        if (on) { row.setAttribute('aria-current', 'true'); }
        else { row.removeAttribute('aria-current'); }
      });
    }

    function setPlayingUI(playing) {
      if (transportIcon) transportIcon.className = 'transport-icon ' + (playing ? 'pause-bars' : 'mini-triangle');
      if (transportText) transportText.textContent = playing ? 'PAUSE' : (video.ended ? 'REPLAY' : 'PLAY');
      if (transport) transport.setAttribute('aria-label', playing ? 'Pause briefing' : 'Play briefing');
      if (stagePlay) stagePlay.hidden = playing;
    }

    function toggle() {
      if (preparing) return;
      if (video.paused) {
        if (video.ended) video.currentTime = 0;
        preparing = true;
        if (stagePlay) stagePlay.disabled = true;
        var p = video.play();
        if (p && p.then) {
          p.then(function () { preparing = false; if (stagePlay) stagePlay.disabled = false; })
           .catch(function () { preparing = false; if (stagePlay) stagePlay.disabled = false; fail(); });
        } else { preparing = false; if (stagePlay) stagePlay.disabled = false; }
      } else {
        video.pause();
      }
    }

    // The written briefing is the non-video alternative and must survive a
    // media failure intact - rows, evidence footer, transcript and sources all
    // stay exactly where they are.
    function fail() {
      if (!stagePlay || stagePlay.dataset.failed === '1') return;
      stagePlay.dataset.failed = '1';
      var note = document.createElement('p');
      note.className = 'stage-message';
      note.setAttribute('role', 'status');
      note.textContent = 'Video unavailable. Read this week’s briefing.';
      stagePlay.replaceWith(note);
      stagePlay = null;
    }

    video.addEventListener('loadedmetadata', function () { showDuration(); paint(); });
    video.addEventListener('durationchange', showDuration);
    video.addEventListener('timeupdate', paint);
    video.addEventListener('play', function () { setPlayingUI(true); });
    video.addEventListener('pause', function () { setPlayingUI(false); });
    video.addEventListener('ended', function () { setPlayingUI(false); });
    video.addEventListener('error', fail);

    if (stagePlay) stagePlay.addEventListener('click', toggle);
    if (transport) transport.addEventListener('click', toggle);

    if (sound) {
      sound.addEventListener('click', function () {
        video.muted = !video.muted;
        sound.textContent = video.muted ? 'SOUND OFF' : 'SOUND ON';
        sound.setAttribute('aria-pressed', video.muted ? 'false' : 'true');
      });
    }

    if (progress) {
      progress.addEventListener('input', function () {
        video.currentTime = parseFloat(progress.value) || 0;
        paint();
      });
    }

    rows.forEach(function (row) {
      row.addEventListener('click', function () {
        video.currentTime = parseFloat(row.getAttribute('data-at')) || 0;
        paint();
        if (video.paused) toggle();
      });
    });

    showDuration();
    paint();
    setPlayingUI(false);
  })();
"""


def render_briefing(ed: dict) -> str:
    """The locked frame. Nothing here varies except edition content."""
    v = ed['video']
    pub = ed['publicationDate']
    topline_left = ed['toplineLabel']
    stories_html = []
    for s in ed['stories']:
        stories_html.append(f"""            <button class="story-row" type="button" data-at="{s['startSeconds']}">
              <span class="story-main">
                <span class="story-meta"><strong>{e(s['number'])}</strong> {e(s['category'].upper())}</span>
                <span class="story-headline">{e(s['headline'])}</span>
                <span class="story-detail">{e(s['consequence'])}</span>
              </span>
              <span class="story-marker">
                <span>{e(s['markerLabel'].upper())}</span>
                <strong>{e(s['markerValue'])}</strong>
              </span>
            </button>""")

    cells = []
    for s in ed['stories']:
        cells.append(f"""          <div class="signal-cell">
            <span>{e(s['category'].upper())}</span>
            <strong>01</strong>
          </div>""")

    return f"""  <section class="briefing" aria-label="yellow3 Research Intelligence Monday briefing">
    <div class="yellow-signal" aria-hidden="true"></div>

    <header class="masthead">
      <div>
        <p class="eyebrow">RESEARCH INTELLIGENCE</p>
        <p class="issue">MONDAY BRIEFING &middot; {e(ed['issueNumber'])}</p>
      </div>
      <div class="date-block">
        <p class="date-label">WEEK COVERED</p>
        <p class="date-value">{e(ed['weekLabelDisplay'])}</p>
      </div>
    </header>

    <div class="briefing-grid">
      <section class="presenter" aria-label="Astrid video briefing">
        <div class="video-stage">
          <video class="astrid-video" src="{e(v['src'])}" poster="{e(v['poster'])}"
                 preload="metadata" playsinline
                 aria-label="Astrid presents the Digital Product Passport briefing for {e(ed['publicationDateDisplay'])}"></video>
          <div class="video-topline">
            <span>{e(topline_left)}</span>
            <span>{e(v['presenter'].upper())} &middot; <span class="topline-total">--:--</span></span>
          </div>
          <button class="stage-play" type="button">
            <span class="play-triangle" aria-hidden="true"></span>
            <span>PLAY WITH SOUND</span>
          </button>
        </div>

        <div class="transport">
          <button class="transport-button" type="button" aria-label="Play briefing">
            <span class="transport-icon mini-triangle" aria-hidden="true"></span>
            <span class="transport-text">PLAY</span>
          </button>
          <label class="progress-label">
            <span class="sr-only">Video position</span>
            <input class="progress" type="range" min="0" max="{v['durationSeconds']:.3f}" step="0.05" value="0" />
          </label>
          <span class="timecode"><span class="timecode-elapsed">00:00</span> / <span class="timecode-total">--:--</span></span>
          <button class="sound-button" type="button" aria-pressed="true">SOUND ON</button>
        </div>
      </section>

      <section class="stories" aria-label="This week's briefing points">
        <div class="stories-intro">
          <div>
            <p class="section-kicker">DIGITAL PRODUCT PASSPORT</p>
            <p class="briefing-title">What changed this week.</p>
          </div>
          <p class="intro-note">{e(ed['framing']['lineOne'])}<br /><strong>{e(ed['framing']['lineTwo'])}</strong></p>
        </div>

        <div class="story-list">
{chr(10).join(stories_html)}
        </div>
      </section>
    </div>

    <div class="signal-strip" aria-label="Briefing categories">
{chr(10).join(cells)}
    </div>

    <footer class="evidence-footer">
      <div class="evidence-statement">
        <span class="footer-rule" aria-hidden="true"></span>
        <strong>Evidence checked before publication.</strong>
      </div>
      <div class="footer-meta">
        <strong>CHECKED {e(ed['checkedDisplay'])}</strong>
        <span>RESEARCH NOTE {e(ed['researchNote'])}</span>
      </div>
    </footer>
  </section>
"""


def render_record(ed: dict, prev_ed: dict | None, next_ed: dict | None) -> str:
    """Transcript, verified sources, correction and archive navigation."""
    paras = '\n'.join(f'          <p>{e(p)}</p>' for p in ed['transcript'])

    sources = []
    for s in ed['sources']:
        sources.append(f"""            <li>
              <span class="src-pub">{e(s['publisher'])}</span>
              <a href="{e(s['url'])}" target="_blank" rel="noopener">{e(s['title'])}</a>
              <span class="src-checked">Checked {e(s['checkedDisplay'])}</span>
            </li>""")

    correction = ''
    if ed.get('correction'):
        c = ed['correction']
        correction = (f'\n        <div class="correction"><strong>Correction '
                      f'{e(c["date"])}.</strong> {e(c["note"])}</div>')

    nav_parts = []
    if prev_ed:
        nav_parts.append(f'<a href="{ROUTE}/{e(prev_ed["slug"])}">&#8592; {e(prev_ed["weekLabelDisplay"])}</a>')
    else:
        nav_parts.append('<span class="spacer">Earliest edition</span>')
    if next_ed:
        nav_parts.append(f'<a href="{ROUTE}/{e(next_ed["slug"])}">{e(next_ed["weekLabelDisplay"])} &#8594;</a>')
    else:
        nav_parts.append(f'<a href="{ROUTE}">Latest edition &#8594;</a>')

    return f"""  <div class="briefing-wrap">
    <section class="edition-record" aria-label="Edition record">
      <p class="rec-head">Edition record &middot; {e(ed['publicationDateDisplay'])}</p>
      <div class="edition-cols">
        <div class="transcript">
          <h2>Transcript</h2>
{paras}{correction}
        </div>
        <div class="sources">
          <h2>Verified sources</h2>
          <ol>
{chr(10).join(sources)}
          </ol>
        </div>
      </div>
      <nav class="edition-nav" aria-label="Edition archive">
        {nav_parts[0]}
        {nav_parts[1]}
      </nav>
    </section>
  </div>
"""


def render_page(ed: dict, canonical: str, prev_ed, next_ed, latest: bool) -> str:
    v = ed['video']
    title = 'Digital Product Passport Weekly Briefing | yellow3'
    if not latest:
        title = (f'Digital Product Passport Weekly Briefing, '
                 f'{ed["publicationDateDisplay"]} | yellow3')
    # The permanent route and the dated edition are the same content today, so a
    # shared description makes them read as duplicates to a crawler - seo_dd
    # flags exactly that. The archive edition names its own date instead.
    desc = ('Watch the weekly Digital Product Passport briefing from yellow3 Research '
            'Intelligence, covering regulatory, standards and implementation developments.')
    if not latest:
        desc = (f'The Digital Product Passport briefing for {ed["publicationDateDisplay"]} '
                'from yellow3 Research Intelligence: what changed this week in '
                'regulatory, deadline, implementation and standards developments.')

    video_ld = {
        '@context': 'https://schema.org',
        '@type': 'VideoObject',
        'name': f'Digital Product Passport Weekly Briefing, {ed["publicationDateDisplay"]}',
        'description': desc,
        'thumbnailUrl': [v['poster']],
        'uploadDate': ed['publicationDate'],
        'duration': iso8601(v['durationSeconds']),
        'contentUrl': v['src'],
        'transcript': '\n\n'.join(ed['transcript']),
        'publisher': {'@type': 'Organization', 'name': 'yellow3',
                      'url': 'https://www.yellow3.io'},
    }

    # The card name is the page's own path, which is what research/gen_og.py
    # derives from every page in the site. index and each dated edition get
    # their own card, so a shared edition link shows that edition.
    nav, foot, shell_css = shell()
    card = ('research-digital-product-passport-weekly-briefing-'
            + ('index' if latest else ed['slug']))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{e(title)}</title>
  <meta name="description" content="{e(desc)}" />
  <link rel="canonical" href="{e(canonical)}" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <meta property="og:type" content="video.other" />
  <meta property="og:title" content="{e(title)}" />
  <meta property="og:description" content="{e(desc)}" />
  <meta property="og:url" content="{e(canonical)}" />
  <meta property="og:image" content="{BASE}/og/cards/{card}.png" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:site" content="@yellow3HQ" />
  <meta name="twitter:image" content="{BASE}/og/cards/{card}.png" />
  <script type="application/ld+json">{json.dumps(video_ld, ensure_ascii=False)}</script>
  <style>
{shell_css}
{PAGE_CSS}
{BRIEFING_CSS}
  </style>
</head>
<body>
{nav}  <main class="briefing-page">
    <div class="briefing-wrap">
      <p class="breadcrumb"><a href="/research">Research</a> / <a href="/research/digital-product-passport">Digital Product Passport</a> / Weekly Briefing</p>
    </div>
{render_briefing(ed)}
{render_record(ed, prev_ed, next_ed)}
  </main>
{foot}  <script src="/consent.js" defer></script>
  <script>
{PLAYER_JS}
  </script>
</body>
</html>
"""


# The site page frame: nav, footer, wrap and tokens, matching the other
# research pages. Kept separate from BRIEFING_CSS so the locked block can be
# replaced wholesale when a new design handover arrives.
PAGE_CSS = """    /* Page-level rules for the briefing route ONLY.
       The header, the footer and every global (body, a, img, *, :root) come
       from research.html via shell() and are not written here. Nothing in this
       block may touch .site-nav, .site-footer, .foot-*, .nav-* or .brand. */
    .briefing-page { padding: 116px 28px 0; }
    .briefing-wrap { width: min(1360px, 100%); margin: 0 auto; }
    .briefing-page .breadcrumb { font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--muted); font-weight: 600; margin-bottom: 26px; }
    .briefing-page .breadcrumb a { color: var(--muted); text-decoration: none; }
    .briefing-page .breadcrumb a:hover { color: var(--ink); }
    @media (max-width: 900px) {
      .briefing-page { padding: 92px 0 0; }
      .briefing-page .breadcrumb { padding: 0 18px; }
    }
"""


def prepare(ed: dict) -> dict:
    """Derived display values. Nothing here invents content."""
    import datetime as dt
    ed = dict(ed)
    d = dt.date.fromisoformat(ed['publicationDate'])
    ed['publicationDateDisplay'] = d.strftime('%-d %B %Y')
    ed['toplineLabel'] = d.strftime('%A · %-d %b').upper()
    ed['weekLabelDisplay'] = ed['weekLabel'].upper()
    checked = dt.datetime.fromisoformat(ed['checkedAt'])
    ed['checkedDisplay'] = checked.strftime('%-d %b %Y · %H:%M').upper() + ' CET'
    for s in ed.get('sources', []):
        c = dt.datetime.fromisoformat(s['checkedAt'])
        s['checkedDisplay'] = c.strftime('%-d %B %Y')
    return ed


def main() -> int:
    args = set(sys.argv[1:])
    check_only = '--check' in args
    preview = '--preview' in args
    # --data lets QA render the frame from a scratch edition without editing
    # the real source of truth. It cannot publish: --data implies --preview.
    data = DATA
    out_dir = PREVIEW_DIR
    for a in sys.argv[1:]:
        if a.startswith('--data='):
            data = pathlib.Path(a.split('=', 1)[1])
            preview = True
        if a.startswith('--out='):
            # QA renders go OUTSIDE the site tree by default. A preview inside
            # it would be globbed by build_check and walked by the sitemap, and
            # a page carrying the word PREVIEW must never be reachable.
            out_dir = pathlib.Path(a.split('=', 1)[1])
            preview = True

    doc = json.loads(data.read_text(encoding='utf-8'))
    editions = sorted(doc['editions'], key=lambda x: x['slug'])

    publishable, blocked = [], []
    for ed in editions:
        b = blockers(ed)
        (blocked if b else publishable).append((ed, b))

    if preview:
        # QA rendering of a blocked edition, to produce the parity screenshots
        # the handover asks for. It writes outside the site tree and can never
        # be served: research/.preview is git-ignored and not in the sitemap.
        if not editions:
            print('nothing to preview')
            return 1
        ed = prepare(editions[-1])
        v = ed['video']
        if not v.get('src'):
            print('PREVIEW REFUSED: the edition has no media yet. Point video.src at a '
                  'local file to render the frame.')
            return 1
        out_dir.mkdir(parents=True, exist_ok=True)
        ed.setdefault('issueNumber', 'PREVIEW')
        ed['issueNumber'] = ed['issueNumber'] or 'PREVIEW'
        ed['researchNote'] = ed['researchNote'] or 'PREVIEW / 2026'
        for i, s in enumerate(ed['stories']):
            if s['startSeconds'] is None:
                s['startSeconds'] = 0
        (out_dir / 'weekly-briefing.html').write_text(
            render_page(ed, BASE + ROUTE, None, None, True), encoding='utf-8')
        print(f'  preview  {out_dir / "weekly-briefing.html"}')
        print('  NOT PUBLISHABLE - preview only, values marked PREVIEW are not content.')
        return 0

    for ed, b in blocked:
        print(f'  BLOCKED  {ed["slug"]}')
        for line in b:
            print(f'      {line}')

    if not publishable:
        print(f'\n  no publishable edition ({len(blocked)} blocked). '
              f'Nothing written; any existing pages are left as they are.')
        return 1 if check_only else 0

    if check_only:
        print(f'  ok  {len(publishable)} edition(s) publishable, {len(blocked)} blocked')
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ready = [prepare(ed) for ed, _ in publishable]
    for i, ed in enumerate(ready):
        prev_ed = ready[i - 1] if i > 0 else None
        next_ed = ready[i + 1] if i + 1 < len(ready) else None
        path = OUT_DIR / f'{ed["slug"]}.html'
        path.write_text(render_page(ed, f'{BASE}{ROUTE}/{ed["slug"]}', prev_ed, next_ed, False),
                        encoding='utf-8')
        print(f'  wrote  {path.relative_to(ROOT)}')

    latest = ready[-1]
    (OUT_DIR / 'index.html').write_text(
        render_page(latest, BASE + ROUTE, ready[-2] if len(ready) > 1 else None, None, True),
        encoding='utf-8')
    print(f'  wrote  {(OUT_DIR / "index.html").relative_to(ROOT)}  (latest: {latest["slug"]})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
