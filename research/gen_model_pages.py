#!/usr/bin/env python3
"""
yellow3 research - Model Explorer page generator.

Reads the derived per-model data + curated registries emitted by build.py and
writes one static, SEO-complete HTML page per model under research/model-adoption/.
Pure standard library (no template engine) so the daily build stays dependency-free.

The pages are the research layer: a permanent, accumulating record for each model -
weekly rank/share history, movement, milestones, and (later) sourced analysis.

Run standalone (uses whatever build.py last wrote):
    python3 research/gen_model_pages.py
Or it is called at the end of build.py's run.
"""
import og_card
import os
import re
import sys
import json
import html
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(HERE, "model-adoption")
DATA_DIR = os.path.join(PAGES_DIR, "_data")
MAIN_JSON = os.path.join(HERE, "model-adoption-data.json")

HOST = "https://www.yellow3.io"     # emit www at the source. The build
                                    # still normalises hand-written pages,
                                    # but a generator that relies on that
                                    # ships a redirecting canonical between
                                    # a regeneration and the next build -
                                    # which is what happened to 187
                                    # register profiles on 2026-07-30.
BASE = "/research/model-adoption"

# New model-research origin palette (aubergine / navy / ochre / graphite).
REGION_HEX = {"Asia": "#4d146c", "US": "#003268", "Europe": "#ffba02", "Other": "#828383"}
UP, DOWN, FLAT = "#2E9D78", "#b3402e", "#9a9a95"


def esc(s):
    return html.escape(str(s), quote=True) if s is not None else ""


def D(iso):
    try:
        return dt.date.fromisoformat(iso).strftime("%-d %b %Y")
    except Exception:
        return iso or ""


def D_short(iso):
    try:
        return dt.date.fromisoformat(iso).strftime("%-d %b")
    except Exception:
        return iso or ""


# --------------------------------------------------------------- components --

# Items and footer architecture from research/site_nav.py - one definition
# for the whole site, so a
# regeneration cannot restore a menu the site has moved on from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from site_nav import render as _nav, sweep_footer as _foot  # noqa: E402

NAV = """  <nav class="site-nav">
    <a href="/" class="brand"><img src="/logo.png" alt="yellow3" /></a>
    <div class="nav-mid" id="navMid">""" + _nav(active="/research") + """</div>
    <a href="#" onclick="window.location.href='mailto:'+'hello'+String.fromCharCode(64)+'yellow3.io';return false;" class="nav-cta">Get in touch <span>&#8594;</span></a>
    <button class="nav-toggle" aria-label="Menu" aria-expanded="false" onclick="var o=this.classList.toggle('open');document.getElementById('navMid').classList.toggle('open');this.setAttribute('aria-expanded',o)"><span></span><span></span><span></span></button>
  </nav>"""

FOOTER = _foot("""  <footer class="site-footer">
    <div class="inner">
      <div class="foot-top">
        <div class="foot-brand">
          <img src="/logo.png" alt="yellow3" />
          <div class="fb-lab">yellow3 lab</div>
          <p>We use emerging technology to make business less complicated.</p>
        </div>
        <div class="foot-col">
          <h4>Work</h4>
          <a href="https://naffe.ai/">naffe.ai</a>
          <a href="/research/digital-product-passport">Digital Product Passports</a>
          <a href="/advisory">Advisory</a>
        </div>
        <div class="foot-col">
          <h4>Research</h4>
          <a href="/research/model-adoption">yellow3 Model Intelligence</a>
          <a href="/research/model-adoption/reports">The Model Adoption Report</a>
          <a href="/research/eu-ai-act">EU AI Act</a>
          <a href="/research/digital-product-passport/suppliers">DPP Supplier Register</a>
        </div>
        <div class="foot-col">
          <h4>Company</h4>
          <a href="/about">About</a>
          <a href="/insights/">Thinking</a>
          <a href="/contact">Contact</a>
        </div>
        <div class="foot-contact">
          <h4>Get in touch</h4>
          <a href="#" onclick="window.location.href='mailto:'+'hello'+String.fromCharCode(64)+'yellow3.io';return false;" class="mail">Email us</a>
          <div class="loc">Copenhagen, Denmark</div>
        </div>
      </div>
      <div class="foot-bottom">
        <span class="copy">&copy; 2026 yellow3 ApS. All rights reserved.</span>
        <div class="foot-legal">
          <a href="/privacy">Privacy</a>
          <a href="/terms">Terms</a>
          <a href="/cookies">Cookies</a>
        </div>
      </div>
    </div>
  </footer>""")


def provider_tile(provider):
    """Verified logo if present, else a neutral initials tile."""
    name = provider.get("name", "")
    logo = provider.get("logo_path")
    if logo:
        return f'<span class="ptile"><img src="{esc(logo)}" alt="{esc(name)} logo" /></span>'
    initials = "".join(w[0] for w in re.split(r"[\s.\-]+", name) if w)[:2].upper() or "?"
    return f'<span class="ptile ptile-fallback" aria-hidden="true">{esc(initials)}</span>'


def region_badge(region):
    hexc = REGION_HEX.get(region, REGION_HEX["Other"])
    return f'<span class="rbadge" style="--rc:{hexc}">{esc(region)}</span>'


def movement_cell(rank_change):
    if rank_change is None:
        return '<span class="mv mv-new">NEW</span>'
    if rank_change > 0:
        return f'<span class="mv mv-up" style="color:{UP}">&#9650; {rank_change}<span class="sr">places up</span></span>'
    if rank_change < 0:
        return f'<span class="mv mv-down" style="color:{DOWN}">&#9660; {abs(rank_change)}<span class="sr">places down</span></span>'
    return f'<span class="mv mv-flat" style="color:{FLAT}">&ndash;<span class="sr">no change</span></span>'


def streak_text(m):
    parts = []
    if m["weeks_ranked"]:
        parts.append(f'{m["weeks_ranked"]} week{"s" if m["weeks_ranked"] != 1 else ""} ranked')
    if m["weeks_top3"]:
        parts.append(f'{m["weeks_top3"]} in top 3')
    elif m["weeks_top10"]:
        parts.append(f'{m["weeks_top10"]} in top 10')
    return " &middot; ".join(parts) or "&ndash;"


def adoption_chart(series):
    """Inline SVG line chart of weekly routed share, plus embedded data for the
    period controls. All-time is pre-rendered so it works with JS disabled."""
    W, H = 720, 300
    padL, padR, padT, padB = 46, 20, 24, 40
    pts = [(s["week_ending"], s["routed_share"]) for s in series]
    n = len(pts)
    ymax = max((p[1] for p in pts), default=1) or 1
    ymax = max(1, ymax)
    # round the axis up to a tidy ceiling
    step = 1 if ymax <= 5 else (2 if ymax <= 10 else 5)
    ytop = step * ((int(ymax) // step) + 1)

    def X(i):
        if n <= 1:
            return padL
        return padL + (W - padL - padR) * i / (n - 1)

    def Y(v):
        return padT + (H - padT - padB) * (1 - v / ytop)

    gridlines = []
    ylab = 0
    while ylab <= ytop:
        y = Y(ylab)
        gridlines.append(f'<line x1="{padL}" y1="{y:.1f}" x2="{W-padR}" y2="{y:.1f}" class="grid" />'
                         f'<text x="{padL-8}" y="{y+4:.1f}" class="yl">{ylab}%</text>')
        ylab += step
    poly = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, (_, v) in enumerate(pts))
    dots = "".join(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="3" class="pt"><title>{esc(D(d))}: {v:.2f}%</title></circle>'
                   for i, (d, v) in enumerate(pts))
    # x labels: show a handful to avoid crowding
    every = max(1, n // 6)
    xlabs = "".join(f'<text x="{X(i):.1f}" y="{H-padB+18:.1f}" class="xl">{esc(D_short(d))}</text>'
                    for i, (d, _) in enumerate(pts) if i % every == 0 or i == n - 1)
    last = pts[-1] if pts else ("", 0)
    lastlab = (f'<text x="{X(n-1)-6:.1f}" y="{Y(last[1])-10:.1f}" class="last">{last[1]:.2f}%</text>'
               if n else "")
    span_note = (f'<div class="chart-span">All {n} tracked weeks &middot; '
                 f'{esc(D_short(pts[0][0]))} to {esc(D_short(pts[-1][0]))}. '
                 f'Longer periods open as the record grows.</div>' if n else "")
    return f'''<div class="chart-wrap">
  <svg viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Weekly routed share over time. The underlying figures are in the rank history table below.">
    <g class="grids">{''.join(gridlines)}</g>
    <polyline class="line" points="{poly}" />
    {lastlab}
    <g class="dots">{dots}</g>
    <g class="xlabs">{xlabs}</g>
  </svg>
  {span_note}
</div>'''


def rank_history_rows(series):
    rows = []
    for s in reversed(series):  # newest first
        dsh = s["share_change_pp"]
        dsh_txt = f'{dsh:+.2f}' if dsh is not None else "&ndash;"
        rows.append(
            f'<tr><td>{esc(D(s["week_ending"]))}</td>'
            f'<td class="num">#{s["global_rank"]}</td>'
            f'<td class="num">{s["routed_share"]:.2f}%</td>'
            f'<td class="num">{dsh_txt}</td>'
            f'<td>{movement_cell(s["rank_change"])}</td>'
            f'<td class="num">{("#" + str(s["region_rank"])) if s["region_rank"] else "&ndash;"}</td>'
            f'<td><span class="stat stat-{s["status"].lower().replace(" ", "").replace("-", "")}">{esc(s["status"])}</span></td></tr>'
        )
    return "".join(rows)


def at_a_glance(m, provider, meta):
    def row(label, value, raw=False):
        if value in (None, "", []):
            return f'<div class="glance-row"><dt>{esc(label)}</dt><dd class="undisclosed">Not publicly disclosed</dd></div>'
        val = value if raw else esc(value)
        return f'<div class="glance-row"><dt>{esc(label)}</dt><dd>{val}</dd></div>'

    def head(label):
        return f'<div class="glance-head">{esc(label)}</div>'

    ow = meta.get("open_weight")
    ow_txt = None if ow is None else ("Open weight" if ow else "Proprietary")
    region_html = esc(m["region"]) + (f' &middot; {esc(m["country"])}' if m["country"] else "")
    modalities = meta.get("modalities")
    if isinstance(modalities, list):
        modalities = ", ".join(modalities)
    return "".join([
        head("Observed by yellow3"),
        row("Current rank", f'#{m["current"]["global_rank"]}'),
        row("Peak rank", f'#{m["peak_rank"]}'),
        row("Routed share", f'{m["current"]["routed_share"]:.2f}%'),
        row("Peak share", f'{m["peak_share"]:.2f}%'),
        row("Weeks ranked", m["weeks_ranked"]),
        row("First tracked", D(m["first_tracked"])),
        row("Region of origin", region_html, raw=True),
        head("Model facts"),
        row("Provider", provider.get("name")),
        row("Model family", meta.get("model_family")),
        row("Release date", D(meta["release_date"]) if meta.get("release_date") else None),
        row("Type", meta.get("model_type")),
        row("Modalities", modalities),
        row("Context window", meta.get("context_window")),
        row("Weights", ow_txt),
        row("License", meta.get("license")),
    ])


def why_moving(m):
    cur = m["current"]
    rc = cur["rank_change"]
    if rc is None:
        move = "entered the ranking this week"
    elif rc > 0:
        move = f"rose {rc} place{'s' if rc != 1 else ''} to #{cur['global_rank']}"
    elif rc < 0:
        move = f"fell {abs(rc)} place{'s' if abs(rc) != 1 else ''} to #{cur['global_rank']}"
    else:
        move = f"held at #{cur['global_rank']}"
    trend = ""
    if len(m["series"]) >= 3:
        first = m["series"][0]["routed_share"]
        lastv = m["series"][-1]["routed_share"]
        d = lastv - first
        if abs(d) >= 0.05:
            trend = (f" Over {len(m['series'])} tracked weeks its routed share has moved "
                     f"from {first:.2f}% to {lastv:.2f}% ({d:+.2f} pp).")
    observed = (f"In the week ending {D(cur['week_ending'])}, {esc(m['name'])} {move} "
                f"with {cur['routed_share']:.2f}% of routed tokens and a peak rank of "
                f"#{m['peak_rank']}.{trend}")
    return f'''<div class="analysis-block">
      <div class="ab-label ab-observed">Observed data</div>
      <p>{observed}</p>
    </div>
    <div class="analysis-block">
      <div class="ab-label ab-analysis">yellow3 analysis</div>
      <p class="pending">A sourced weekly interpretation of what is driving this model's routing
      is added as the record accumulates. yellow3 does not publish a reason for movement
      unless the routed-traffic data or a cited source supports it.</p>
    </div>'''


def milestones_list(m):
    items = []
    for ms in m["milestones"]:
        val = f' <span class="ms-val">{esc(ms["value"])}</span>' if ms.get("value") else ""
        items.append(
            f'<li class="ms"><span class="ms-date">{esc(D(ms["date"]))}</span>'
            f'<span class="ms-title">{esc(ms["title"])}{val}</span>'
            f'<span class="ms-src">Derived from yellow3 routed-traffic data</span></li>')
    return "".join(items)


def sources_section(m, provider, meta):
    links = []
    off = meta.get("official_url") or provider.get("official_url")
    if off:
        label = "Official model page" if meta.get("official_url") else f'{provider.get("name")} (official site)'
        links.append(f'<li><a href="{esc(off)}" target="_blank" rel="noopener noreferrer">{esc(label)} &#8599;</a> <span class="src-primary">primary</span></li>')
    for key, label in (("technical_report_url", "Technical report"),
                       ("repository_url", "Official repository")):
        if meta.get(key):
            links.append(f'<li><a href="{esc(meta[key])}" target="_blank" rel="noopener noreferrer">{esc(label)} &#8599;</a> <span class="src-primary">primary</span></li>')
    links.append(f'<li><a href="{BASE}#methodology">yellow3 AI Model Adoption methodology</a></li>')
    links.append('<li><a href="https://openrouter.ai/rankings" target="_blank" rel="noopener noreferrer">OpenRouter routing rankings (routed-traffic source) &#8599;</a></li>')
    return "".join(links)


def explore_other(m, models_by_slug, page_slugs):
    """Restrained internal links: same provider, same region, nearest in rank."""
    me = m["slug"]
    pool = [models_by_slug[s] for s in page_slugs if s in models_by_slug and s != me]
    same_provider = [x for x in pool if x["developer"] == m["developer"]][:3]
    same_region = [x for x in pool if x["region"] == m["region"] and x["developer"] != m["developer"]][:3]
    my_rank = m["current"]["global_rank"]
    nearest = sorted([x for x in pool if x.get("currently_ranked")],
                     key=lambda x: abs(x["current"]["global_rank"] - my_rank))[:4]

    def links(lst):
        return " &middot; ".join(
            f'<a href="{BASE}/{esc(x["slug"])}">{esc(x["name"])}</a>' for x in lst) or "&ndash;"
    blocks = []
    if same_provider:
        blocks.append(f'<div class="xo-row"><span class="xo-h">From {esc(m["provider_name"])}</span><span>{links(same_provider)}</span></div>')
    if same_region:
        blocks.append(f'<div class="xo-row"><span class="xo-h">From {esc(m["region"])}</span><span>{links(same_region)}</span></div>')
    if nearest:
        blocks.append(f'<div class="xo-row"><span class="xo-h">Nearby in the ranking</span><span>{links(nearest)}</span></div>')
    return "".join(blocks)


# ------------------------------------------------------------------- head --

def head(m, provider, meta, updated_iso):
    name = m["name"]
    url = f"{HOST}{BASE}/{m['slug']}"
    title = f"{name} Adoption, Ranking and Market Share | yellow3"
    desc = (f"Track {name}'s global AI adoption, routed-token share, weekly ranking, "
            f"historical movement, milestones and primary sources. A live yellow3 research record.")
    og_img = og_card.url(url)
    breadcrumb = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Research", "item": f"{HOST}/research"},
            {"@type": "ListItem", "position": 2, "name": "AI model adoption", "item": f"{HOST}{BASE}"},
            {"@type": "ListItem", "position": 3, "name": name, "item": url},
        ],
    }
    webpage = {
        "@context": "https://schema.org", "@type": "WebPage",
        "name": title, "description": desc, "url": url,
        "dateModified": updated_iso,
        "isPartOf": {"@type": "WebSite", "name": "yellow3 lab", "url": HOST},
    }
    dataset = {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": f"{name} routed-adoption history",
        "description": (f"Weekly global rank and routed-token share for {name}, measured from "
                        f"OpenRouter routing traffic by yellow3 lab."),
        "url": url,
        "temporalCoverage": f"{m['first_tracked']}/{m['current']['week_ending']}",
        "variableMeasured": ["global rank", "routed-token share", "weekly rank change"],
        "creator": {"@type": "Organization", "name": "yellow3 lab", "url": HOST},
        "isAccessibleForFree": True,
    }
    org = {
        "@context": "https://schema.org", "@type": "Organization",
        "name": provider.get("name"),
    }
    if provider.get("official_url"):
        org["url"] = provider["official_url"]
    jsonld = "\n".join(
        f'  <script type="application/ld+json">{json.dumps(o, ensure_ascii=False)}</script>'
        for o in (webpage, breadcrumb, dataset, org))
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}" />
  <link rel="canonical" href="{url}" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <link rel="stylesheet" href="{BASE}/model.css" />
  <meta property="og:type" content="article" />
  <meta property="og:site_name" content="yellow3 lab" />
  <meta property="og:title" content="{esc(title)}" />
  <meta property="og:description" content="{esc(desc)}" />
  <meta property="og:url" content="{url}" />
  <meta property="og:image" content="{og_img}" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="twitter:card" content="summary_large_image" />
  <meta property="twitter:image" content="{og_img}" />
{jsonld}
</head>
<body>'''


# ------------------------------------------------------------------ page --

# ------------------------------------------------------------- economics --

def fmt_m(v):
    """A per-token price formatted as $ per 1M tokens."""
    if v is None:
        return None
    pm = v * 1e6
    if pm == 0:
        return "$0.00"
    if pm < 0.1:
        return f"${pm:.3f}"
    return f"${pm:.2f}"


def econ_tiles(e):
    def tile(label, value, sub="/ 1M tokens"):
        return (f'<div class="etile"><div class="et-l">{esc(label)}</div>'
                f'<div class="et-v">{value}</div><div class="et-s">{esc(sub)}</div></div>')
    ctx = e.get("context")
    ctx_txt = f'{round(ctx/1000)}K' if ctx and ctx < 1_000_000 else (f'{ctx/1_000_000:.1f}M'.replace('.0M', 'M') if ctx else '&mdash;')
    weights = "Open weights" if e.get("open_weight") else "Proprietary"
    return "".join([
        tile("Input", fmt_m(e["in"]) or "&mdash;"),
        tile("Output", fmt_m(e["out"]) or "&mdash;"),
        tile("Cached input", fmt_m(e["cache_read"]) or '<span class="et-na">Not published</span>'),
        tile("Free tier", '<span class="et-yes">Available</span>' if e.get("free_tier") else '<span class="et-na">&mdash;</span>', "on OpenRouter"),
        tile("Context window", ctx_txt, "tokens"),
        tile("Weights", weights, "license basis"),
    ])


def calculator_html(e):
    return '''<div class="calc" id="calc">
  <div class="calc-panel">
    <div class="wl-tabs" role="group" aria-label="Workload preset">
      <button type="button" class="wl-tab" data-wl="customer-support" aria-pressed="false">Customer support</button>
      <button type="button" class="wl-tab" data-wl="document-analysis" aria-pressed="false">Document analysis</button>
      <button type="button" class="wl-tab active" data-wl="coding-agent" aria-pressed="true">Coding agent</button>
    </div>
    <div class="calc-fields">
      <label class="cf">Monthly tasks<input type="number" id="c-tasks" min="0" step="100"></label>
      <label class="cf">Input tokens / task<input type="number" id="c-inp" min="0" step="1000"></label>
      <label class="cf">Output tokens / task<input type="number" id="c-outp" min="0" step="1000"></label>
      <label class="cf cf-slider">Cached input <b><span id="c-cached-v">70</span>%</b>
        <input type="range" id="c-cached" min="0" max="100" step="5" value="70"></label>
    </div>
  </div>
  <div class="calc-out">
    <div class="co-l">Estimated monthly cost</div>
    <div class="co-total" id="c-total">$0</div>
    <div class="co-row"><span>Input (uncached)</span><span id="c-unc">$0</span></div>
    <div class="co-row"><span>Cached input</span><span id="c-cac">$0</span></div>
    <div class="co-row"><span>Output</span><span id="c-out">$0</span></div>
    <div class="co-per" id="c-per">$0 per completed task</div>
  </div>
</div>
<p class="calc-note">An estimate from published per-token pricing and your assumptions. Actual costs vary by provider and usage tier.</p>'''


def compare_html(e):
    rows = "".join(
        f'<div class="cmp-row" data-slug="{esc(c["slug"])}"><span class="cmp-name{" cmp-you" if c.get("you") else ""}">{esc(c["name"])}{" (You)" if c.get("you") else ""}</span>'
        f'<span class="cmp-bar"><span class="cmp-fill{" cmp-fill-you" if c.get("you") else ""}"></span></span>'
        f'<span class="cmp-val">$0</span></div>'
        for c in (e.get("compare") or []))
    return f'<div class="compare" id="compare">{rows}</div><p class="calc-note">Same workload as the calculator above, at each model\'s current price. Monthly USD.</p>'


def speed_html(e):
    up = e.get("uptime")
    if up is None:
        return ('<p class="sec-sub">Availability monitoring is derived from OpenRouter provider uptime; '
                'it refreshes with the daily build. Latency and throughput are not exposed by the data source, '
                'so we do not report them rather than estimate.</p>')
    err = round(100 - up, 3)
    return (f'<div class="status-strip speed-strip">'
            f'<div class="ss"><span class="ss-v">{up:.2f}%</span><span class="ss-l">Availability (30d)</span></div>'
            f'<div class="ss"><span class="ss-v">{err:.2f}%</span><span class="ss-l">Error / downtime</span></div>'
            f'</div>'
            f'<p class="src-note">Median provider uptime across OpenRouter endpoints, last 30 days. '
            f'Latency and throughput are not published by the source and are not estimated here.</p>')


def cap_row(label, ok, note=None):
    if ok is True:
        mark, txt = '<span class="cap-yes">&#10003;</span>', note or "Supported"
    elif ok is False:
        mark, txt = '<span class="cap-no">&mdash;</span>', note or "Not supported"
    else:
        mark, txt = '', note or "Not publicly disclosed"
    return f'<tr><td>{esc(label)}</td><td>{mark} {txt}</td></tr>'


def capabilities_html(e):
    ctx = e.get("context")
    ctx_txt = f'{round(ctx/1000)}K' if ctx and ctx < 1_000_000 else (f'{ctx/1_000_000:.1f}M'.replace('.0M', 'M') if ctx else 'Not disclosed')
    rows = [
        f'<tr><td>Context window</td><td>{ctx_txt}</td></tr>',
        cap_row("Reasoning", e.get("reasoning")),
        cap_row("Tool calling", e.get("tools")),
        cap_row("Structured output", e.get("structured")),
        cap_row("Image input", e.get("image_in")),
        cap_row("Audio input", e.get("audio_in")),
        cap_row("Video input", e.get("video_in")),
        cap_row("Open weights", e.get("open_weight"), "Yes" if e.get("open_weight") else "Proprietary"),
        '<tr><td>API availability</td><td><span class="cap-yes">&#10003;</span> Yes</td></tr>',
        '<tr><td>Commercial license</td><td>Verify terms with the provider</td></tr>',
    ]
    return f'<table class="cap-table"><tbody>{"".join(rows)}</tbody></table>'


def price_history_html(e):
    hist = e.get("price_history") or []
    body = ""
    for r in hist:
        chg = r.get("change_pct")
        if chg is None:
            chg_html = '<span class="ph-flat">&mdash;</span>'
        elif chg < 0:
            chg_html = f'<span class="ph-down">&#9660; {abs(chg):.0f}%</span>'
        else:
            chg_html = f'<span class="ph-up">&#9650; {chg:.0f}%</span>'
        body += (f'<tr><td>{esc(D(r["date"]))}</td><td class="num">{fmt_m(r["in"])}</td>'
                 f'<td class="num">{fmt_m(r["out"])}</td><td>{chg_html}</td>'
                 f'<td>OpenRouter listed price</td></tr>')
    note = ""
    if len(hist) <= 1:
        note = ('<p class="src-note">Price history begins when yellow3 started tracking this model and '
                'accrues one point per change from here. Only real, observed price changes are recorded.</p>')
    return (f'<div class="table-scroll"><table class="rank-history"><thead><tr>'
            f'<th>Date</th><th>Input / 1M</th><th>Output / 1M</th><th>Change</th><th>Source</th>'
            f'</tr></thead><tbody>{body}</tbody></table></div>{note}')


def econ_script(e):
    payload = {
        "you": {"in": e["in"], "out": e["out"], "cache_read": e["cache_read"]},
        "compare": e.get("compare") or [],
        "workloads": e.get("_workloads") or {},
    }
    return f'<script>window.__ECON={json.dumps(payload)};</script>'



# ---------------------------------------------------------------------------
# THE APPROVED INDIVIDUAL MODEL RECORD, v1 (1 September 2026).
#
# One data-driven template for every canonical slug - the package is explicit
# that the DeepSeek page is a reference instance, not a page to copy. Markup is
# scoped under #y3-model-record-redesign so the approved stylesheet applies
# verbatim and cannot reach the shared nav and footer this generator emits.
#
# Every value below comes from the production feed. Where a field is absent the
# record says which KIND of absence it is - not disclosed, not on record, or
# explicitly unsupported - because the data contract forbids turning missing
# data into a negative finding.
# ---------------------------------------------------------------------------

LOGO_DIR = "/img/model-adoption/provider-logos/"
LOGO_MAP = {"deepseek": "deepseek", "openai": "openai", "z.ai": "z-ai", "zai": "z-ai",
            "xiaomi": "xiaomi", "tencent": "tencent", "nvidia": "nvidia",
            "google": "google", "minimax": "minimax", "moonshot": "moonshot",
            "anthropic": "anthropic", "poolside": "poolside", "upstage": "upstage"}

NOT_DISCLOSED = "Not publicly disclosed"
NOT_ON_RECORD = "Not yet on record"


def logo_for(developer):
    return LOGO_MAP.get(str(developer or "").strip().lower())


def r_logo(m, provider):
    """Identity logo. Meaningful alt here - the record names the provider once."""
    key = logo_for(m.get("provider_name") or provider.get("name"))
    if not key:
        return '<span class="y3r-logo y3r-logo-none" aria-hidden="true">?</span>'
    name = esc(m.get("provider_name") or "")
    return (f'<span class="y3r-logo"><img src="{LOGO_DIR}{key}.svg" '
            f'alt="{name} logo" width="32" height="32"></span>')


def r_move(change):
    """Movement carries a symbol and a number, never colour alone."""
    if change is None:
        return '<span class="y3r-stat-value">New</span>'
    if change > 0:
        return f'<span class="y3r-stat-value y3r-up">&#9650; {change}</span>'
    if change < 0:
        return f'<span class="y3r-stat-value y3r-down">&#9660; {abs(change)}</span>'
    return '<span class="y3r-stat-value">&ndash; Held</span>'


def r_hero(m, provider, meta, e, updated):
    cur = m["current"]
    rank = cur.get("global_rank")
    origin = " &middot; ".join([x for x in [esc(m.get("region")), esc(m.get("country"))] if x])
    verified = f' &middot; Pricing verified {esc(D(updated))}' if (e and e.get("or_url")) else ""
    official = meta.get("official_url") or provider.get("official_url")
    off = (f'<a class="y3r-link" href="{esc(official)}" target="_blank" rel="noopener noreferrer">'
           f'Official model page &#8599;</a>'
           if official else f'<p>Official model page {NOT_ON_RECORD.lower()}</p>')
    pricing = (f'<a class="y3r-link" href="{esc(e["or_url"])}" target="_blank" '
               f'rel="noopener noreferrer">Official pricing &#8599;</a>'
               if e and e.get("or_url") else "")
    ctx = ("Current leader across the tracked routed-model set." if rank == 1
           else f'Ranked {esc(rank)} of the tracked routed-model set.')
    top3 = f'Ranked &middot; {esc(m.get("weeks_top3") or 0)} in top 3'
    price_stat = (f'<div class="y3r-stat"><span class="y3r-stat-value">{esc(e["price_position"])}</span>'
                  f'<span class="y3r-stat-label">Price position</span></div>'
                  if e and e.get("price_position") else "")
    return f'''  <section class="y3r-hero">
    <div class="y3r-wrap">
      <div class="y3r-hero-head">
        <div class="y3r-provider">
          {r_logo(m, provider)}
          <div>
            <div class="y3r-eyebrow">Model provider / {esc(m.get("provider_name"))}</div>
            <h1>{esc(m["name"])}</h1>
            <p class="y3r-meta">{origin} &middot; First tracked {esc(D(m["first_tracked"]))}{verified}</p>
          </div>
        </div>
        <div class="y3r-official">{off}{pricing}</div>
      </div>
      <div class="y3r-signal" aria-label="Current {esc(m["name"])} adoption signal">
        <div class="y3r-primary-signal">
          <span class="y3r-signal-label">Global rank</span>
          <div class="y3r-rank">#{esc(rank)}</div>
          <p class="y3r-rank-context">{ctx}</p>
        </div>
        <div class="y3r-secondary-signals">
          <div class="y3r-stat"><span class="y3r-stat-value">{cur.get("routed_share", 0):.2f}%</span><span class="y3r-stat-label">Routed share</span></div>
          <div class="y3r-stat">{r_move(cur.get("rank_change"))}<span class="y3r-stat-label">Place this week</span></div>
          <div class="y3r-stat"><span class="y3r-stat-value">{esc(m.get("weeks_ranked"))} weeks</span><span class="y3r-stat-label">{top3}</span></div>
          {price_stat}
        </div>
      </div>
      <div class="y3r-freshness"><strong>Live model record</strong><span>Trailing seven days ending {esc(D(updated))} &middot; refreshed daily</span></div>
    </div>
  </section>'''



def r_current_read(m, e):
    """The three evidence-led columns. Values only - no qualitative claim is
    generated to fill a column, per the data contract. Each figure already
    appears elsewhere in the record; this section groups them.

    THE HEADING IS ONE NEUTRAL SENTENCE FOR ALL 53 RECORDS, ratified by GPT on
    1 September 2026: "What the evidence shows today." The approved visual
    carried bespoke prose written for the reference model, which is true of it
    and false of most of the rest. No rank-based branching and no headline
    variants in v1 - that would be an unapproved qualitative-claim generator.
    The three columns below carry the model-specific facts, and "Why it is
    moving" remains the place for evidence-bound interpretation."""
    cur = m["current"]
    weeks = m.get("weeks_ranked") or 0
    series = m.get("series") or []

    if len(series) >= 2:
        first, now = series[0]["routed_share"], series[-1]["routed_share"]
        adoption_v = f"{now - first:+.2f} percentage points"
        adoption_c = (f"Routed share moved from {first:.2f}% to {now:.2f}% "
                      f"across {len(series)} tracked weeks.")
    else:
        adoption_v = f"{cur['routed_share']:.2f}% routed share"
        adoption_c = "Movement needs a second observation before it can be reported."

    if e and e.get("in") is not None and e.get("out") is not None:
        econ_v = f"{fmt_price(e['in'])} in &middot; {fmt_price(e['out'])} out"
        cached = fmt_price(e.get("cache_read"))
        econ_c = ("Per one million tokens. Cached input is listed at " + cached + "."
                  if cached else
                  "Per one million tokens. Cached input is " + NOT_DISCLOSED.lower() + ".")
    else:
        econ_v, econ_c = NOT_ON_RECORD, "No pricing source is recorded for this model."

    bits = []
    if e and e.get("context"):
        c = e["context"]
        bits.append(f"{c // 1_000_000}M context" if c >= 1_000_000 else f"{c // 1000}K context")
    if e and e.get("open_weight"):
        bits.append("open weights")
    fit_v = " &middot; ".join(bits) if bits else NOT_DISCLOSED
    caps = [n for n, k in (("Reasoning", "reasoning"), ("tool calling", "tools"),
                           ("structured output", "structured")) if e and e.get(k)]
    if len(caps) > 1:
        fit_c = ", ".join(caps[:-1]) + " and " + caps[-1] + " are supported."
    elif caps:
        fit_c = caps[0] + " is supported."
    else:
        fit_c = "Supported capabilities are " + NOT_DISCLOSED.lower() + "."

    return f'''    <section class="y3r-section y3r-soft" id="read">
      <div class="y3r-wrap">
        <div class="y3r-section-head">
          <div><div class="y3r-kicker">The current read</div><h2>What the evidence shows today.</h2></div>
          <p class="y3r-lede">The page leads with what has been observed, then separates price, capability and history so a buyer can see both the signal and its limits.</p>
        </div>
        <div class="y3r-readout">
          <div class="y3r-readout-item"><span class="y3r-readout-label">Adoption</span><div class="y3r-readout-value">{adoption_v}</div><p class="y3r-readout-copy">{adoption_c}</p></div>
          <div class="y3r-readout-item"><span class="y3r-readout-label">Economics</span><div class="y3r-readout-value">{econ_v}</div><p class="y3r-readout-copy">{econ_c}</p></div>
          <div class="y3r-readout-item"><span class="y3r-readout-label">Operating fit</span><div class="y3r-readout-value">{fit_v}</div><p class="y3r-readout-copy">{fit_c}</p></div>
        </div>
      </div>
    </section>'''


def fmt_price(v):
    """Per-million price from a per-token figure. None stays None - the data
    contract forbids showing zero in place of a missing price."""
    if v is None:
        return None
    mm = v * 1_000_000
    return ("$%.3f" % mm).rstrip("0").rstrip(".") if mm < 1 else "$%.2f" % mm


def render_page(m, provider, meta, models_by_slug, page_slugs, site, econ=None):
    updated = site["as_of"]
    cur = m["current"]
    name = esc(m["name"])
    origin = " &middot; ".join([x for x in [esc(m["region"]), esc(m["country"])] if x])
    official = meta.get("official_url") or provider.get("official_url")
    official_link = (f'<a class="official" href="{esc(official)}" target="_blank" rel="noopener noreferrer">Official model page <span>&#8599;</span></a>'
                     if official else '<span class="official official-none">Official model page not yet on record</span>')

    e = econ or None
    ss_price = econ_js = sec_econ = sec_speed_caps = sec_price_hist = ""
    pos_box = pricing_link = pricing_meta = ""
    if e:
        if e.get("or_url"):
            pricing_link = (f'<a class="official official-pricing" href="{esc(e["or_url"])}" '
                            f'target="_blank" rel="noopener noreferrer">Official pricing <span>&#8599;</span></a>')
            pricing_meta = f' &middot; Pricing verified {esc(D(updated))}'
        if e.get("price_position"):
            ss_price = (f'<div class="ss"><span class="ss-v ss-price">{esc(e["price_position"])}</span>'
                        f'<span class="ss-l">Price position</span></div>')
        sec_econ = f'''    <section class="y3r-section" id="economics">
      <div class="y3r-wrap">
        <div class="y3r-section-head">
          <div><div class="y3r-kicker">Model economics</div><h2>Published price, translated into a workload.</h2></div>
          <p class="y3r-lede">Live per-token pricing via OpenRouter, verified {esc(D(updated))}. Batch and long-context tiers are not published in the feed, so they are omitted rather than estimated.</p>
        </div>
        <div class="etiles">{econ_tiles(e)}</div>
        {calculator_html(e)}
        <div class="y3r-subhead">Compare the same workload</div>
        {compare_html(e)}
      </div>
    </section>'''
        sec_speed_caps = f'''    <section class="y3r-section" id="profile">
      <div class="y3r-wrap">
        <div class="y3r-section-head">
          <div><div class="y3r-kicker">Operating profile</div><h2>What it supports, and what remains undisclosed.</h2></div>
          <p class="y3r-lede">Verified support, explicit non-support and missing disclosure read differently on purpose. A blank is never made to look like a negative finding.</p>
        </div>
        <div class="y3r-profile-grid">
          <div>
            <div class="y3r-subhead">Capabilities</div>
            {capabilities_html(e)}
          </div>
          <div>
            <div class="y3r-subhead">Model facts</div>
            <dl class="glance">{at_a_glance(m, provider, meta)}</dl>
            {speed_html(e)}
          </div>
        </div>
      </div>
    </section>'''
        sec_price_hist = f'''
      <section class="mx-sec">
        <div class="sec-label">Price history</div>
        {price_history_html(e)}
      </section>'''
        if e.get("position_label"):
            pos_box = (f'<div class="pos-box"><div class="pos-h">Price-to-adoption position</div>'
                       f'<div class="pos-label">{esc(e["position_label"])}</div>'
                       f'<p class="pos-sub">{esc(e.get("price_position") or "")} &middot; adoption {esc(e.get("adoption_trend") or "flat")}. '
                       f'Observed relationship, not proof of causation.</p></div>')
        e["_workloads"] = site.get("workloads", {})
        econ_js = econ_script(e)

    price_hist_inner = ('<div class="y3r-subhead">Price history</div>'
                        + price_history_html(e)) if e else ""
    parts = [head(m, provider, meta, updated), NAV]
    parts.append(f'''  <div id="y3-model-record-redesign">
    <div class="y3r-wrap">
      <nav class="y3r-breadcrumb" aria-label="Breadcrumb">
        <a href="/research">Research</a> <span>/</span>
        <a href="{BASE}">AI model adoption</a> <span>/</span>
        <strong aria-current="page">{name}</strong>
      </nav>
    </div>
{r_hero(m, provider, meta, e, updated)}
{r_current_read(m, e)}
{sec_econ}
    <section class="y3r-section y3r-soft" id="adoption">
      <div class="y3r-wrap">
        <div class="y3r-section-head">
          <div><div class="y3r-kicker">Price and adoption</div><h2>Every point is an observed week.</h2></div>
          <p class="y3r-lede">Routed-token share over time, with no interpolation presented as evidence. A price line joins it as real changes are recorded.</p>
        </div>
        {adoption_chart(m["series"])}
        {pos_box}
      </div>
    </section>
{sec_speed_caps}
    <section class="y3r-section y3r-analysis" id="analysis">
      <div class="y3r-wrap">
        <div class="y3r-analysis-grid">
          <div><div class="y3r-kicker">Why it is moving</div><h2>Observed first. Interpreted only when sourced.</h2></div>
          <div class="y3r-analysis-copy">{why_moving(m)}</div>
        </div>
      </div>
    </section>

    <section class="y3r-section" id="history">
      <div class="y3r-wrap">
        <div class="y3r-section-head">
          <div><div class="y3r-kicker">History and evidence</div><h2>The record behind the headline.</h2></div>
          <p class="y3r-lede">The current position stays connected to every observed week, price change and milestone.</p>
        </div>
        <div class="y3r-table-scroll">
          <table class="y3r-table rank-history">
            <caption class="y3r-visually-hidden">Weekly rank and routed-share history for {name}</caption>
            <thead><tr><th>Week ending</th><th>Rank</th><th>Routed share</th><th>&Delta; share</th><th>Movement</th><th>Region rank</th><th>Status</th></tr></thead>
            <tbody>{rank_history_rows(m["series"])}</tbody>
          </table>
        </div>
        <div class="y3r-history-grid">
          <div>{price_hist_inner}</div>
          <div>
            <div class="y3r-subhead">Milestones</div>
            <ul class="milestones">{milestones_list(m)}</ul>
          </div>
        </div>
      </div>
    </section>

    <section class="y3r-section y3r-soft" id="sources">
      <div class="y3r-wrap">
        <div class="y3r-section-head">
          <div><div class="y3r-kicker">Sources and methodology</div><h2>Every claim keeps its route back to evidence.</h2></div>
          <div>
            <ul class="sources">{sources_section(m, provider, meta)}</ul>
            <p class="y3r-note">Region reflects where the model's developer is headquartered.
            Figures are OpenRouter routing traffic, aggregated over a trailing seven days -
            developer routing behaviour, not the whole market.</p>
            <p><a class="y3r-link" href="/research/framework">Read the research framework &#8594;</a></p>
          </div>
        </div>
        <div class="y3r-explore">
          <div class="y3r-subhead">Explore other models</div>
          <div class="explore-other">{explore_other(m, models_by_slug, page_slugs)}</div>
        </div>
      </div>
    </section>

    <section class="y3r-final">
      <div class="y3r-wrap y3r-final-grid">
        <div>
          <div class="y3r-kicker">Public research / Paid intelligence</div>
          <h2>Follow the model, not the launch cycle.</h2>
          <p>The public record shows today's evidence. yellow3 Model Intelligence adds longer history, watchlists, alerts, comparisons and decision reporting.</p>
        </div>
        <a class="y3r-button" href="{BASE}">Explore Model Intelligence &#8594;</a>
      </div>
    </section>
  </div>
{FOOTER}
{econ_js}
  <script src="{BASE}/model.js" defer></script>
  <!-- yellow3 is an EU entity, so consent applies wherever the visitor is. -->
  <script src="/consent.js" defer></script>
</body>
</html>''')
    return "\n".join(parts)


# ------------------------------------------------------------------- css --

CSS = """*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--paper:#fff;--ink:#0e0e0e;--body:#4b4b4b;--muted:#8a8a8a;--line:#e7e6e2;--yellow:#ffe000;--panel:#f7f6f3;
--up:#2E9D78;--down:#b3402e;--flat:#9a9a95;
--r-asia:#4d146c;--r-us:#003268;--r-europe:#ffba02;--r-other:#828383}
html{scroll-behavior:smooth}
body{background:var(--paper);color:var(--ink);font-family:Arial, Helvetica, sans-serif;font-weight:400;line-height:1.6;font-size:16px;-webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}
img{display:block;max-width:100%}a{color:inherit}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.num{font-variant-numeric:tabular-nums;text-align:right}
/* nav */
.site-nav{position:fixed;top:0;left:0;right:0;z-index:100;display:flex;align-items:center;justify-content:space-between;padding:16px 48px;background:rgba(255,255,255,.95);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:baseline;gap:7px;text-decoration:none}.brand img{height:21px;align-self:center}
.nav-mid{display:flex;gap:32px}
.nav-mid a{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#3a3a3a;text-decoration:none;font-weight:500;padding-bottom:3px}
.nav-mid a:hover{color:var(--ink)}.nav-mid a.active{border-bottom:2px solid var(--ink);color:var(--ink)}
.nav-cta{display:inline-flex;align-items:center;gap:10px;background:var(--ink);color:#fff;font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;padding:12px 20px;text-decoration:none}
.nav-toggle{display:none;background:none;border:none;cursor:pointer;padding:6px}
.nav-toggle span{display:block;width:22px;height:2px;background:var(--ink);margin:5px 0}
.wrap{max-width:1080px;margin:0 auto;padding:0 48px}
.mx{padding:132px 0 40px}
/* breadcrumb */
.crumb{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:30px}
.crumb a{color:var(--muted);text-decoration:none}.crumb a:hover{color:var(--ink)}.crumb span{margin:0 6px;color:#cfcdc6}
.crumb [aria-current]{color:var(--ink)}
/* header */
.mx-head{display:flex;align-items:flex-end;justify-content:space-between;gap:24px 32px;padding-bottom:28px;border-bottom:1px solid var(--line);flex-wrap:wrap}
.mx-head-main{display:flex;align-items:center;gap:20px;min-width:0;flex:1 1 auto}
.mx-head-main>div{min-width:0}
.mx-head h1{overflow-wrap:break-word;word-break:break-word}
.ptile{width:60px;height:60px;flex:0 0 60px;border:1px solid var(--line);border-radius:12px;display:flex;align-items:center;justify-content:center;overflow:hidden;background:#fff}
.ptile img{width:78%;height:78%;object-fit:contain}
.ptile-fallback{font-weight: 400;font-size:20px;color:#3a3a3a;background:var(--panel);letter-spacing: -0.025em}
.mx-provider{font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);font-weight:600;margin-bottom:4px}
.mx-head h1{font-size:clamp(28px,4vw,40px);font-weight: 400;letter-spacing: -0.05em;line-height:1.05}
.mx-meta{font-size:14px;color:var(--body);margin-top:6px}
.official{font-size:12px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;text-decoration:none;border-bottom:1.5px solid var(--ink);padding-bottom:2px;white-space:nowrap}
.official span{font-weight:400}.official-none{color:var(--muted);border:none;text-transform:none;letter-spacing:0;font-weight:400}
/* status strip */
.status-strip{display:grid;grid-template-columns:repeat(5,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin:28px 0 8px}
.ss{background:#fff;padding:20px 22px;display:flex;flex-direction:column;gap:6px}
.ss-v{font-size:24px;font-weight: 400;letter-spacing: -0.025em;line-height:1.1}
.ss-l{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:600}
.mv{font-weight:700;font-size:15px;display:inline-flex;align-items:center;gap:4px}
.mv-new{color:var(--up);font-size:12px;letter-spacing:.08em}.mv-flat{color:var(--flat)}
/* sections */
.mx-sec{padding:40px 0;border-bottom:1px solid var(--line)}
.sec-label{font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--ink);margin-bottom:6px;padding-left:12px;border-left:3px solid var(--yellow)}
.sec-sub{font-size:14px;color:var(--muted);margin:0 0 20px 15px}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:48px}
.two-col .sec-label{margin-bottom:18px}
/* chart */
.chart-wrap svg{width:100%;height:auto;overflow:visible}
.chart-wrap .grid{stroke:#efeee9;stroke-width:1}
.chart-wrap .yl{fill:var(--muted);font-size:11px;text-anchor:end}
.chart-wrap .xl{fill:var(--muted);font-size:11px;text-anchor:middle}
.chart-wrap .line{fill:none;stroke:var(--r-asia);stroke-width:2.5;stroke-linejoin:round;stroke-linecap:round}
.chart-wrap .pt{fill:var(--r-asia)}
.chart-wrap .last{fill:var(--ink);font-size:13px;font-weight:700;text-anchor:end}
.chart-span{font-size:12px;color:var(--muted);margin-top:10px}
/* glance */
.glance{border-top:1px solid var(--line)}
.glance-row{display:flex;justify-content:space-between;gap:16px;padding:11px 0;border-bottom:1px solid var(--line);font-size:14px}
.glance-row dt{color:var(--muted)}.glance-row dd{font-weight:600;text-align:right}
.glance-row .undisclosed{color:#b8b6ae;font-weight:400;font-style:italic}
.glance-head{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:700;padding:18px 0 6px}
.glance-head:first-child{padding-top:0}
/* analysis */
.analysis-block{margin-bottom:20px}
.ab-label{font-size:10px;letter-spacing:.12em;text-transform:uppercase;font-weight:700;margin-bottom:6px;display:inline-block;padding:2px 8px;border-radius:3px}
.ab-observed{background:#eef4f1;color:#2E9D78}.ab-analysis{background:var(--panel);color:var(--body)}
.analysis-block p{font-size:15px;line-height:1.65;color:var(--body)}.analysis-block .pending{color:var(--muted)}
/* tables */
.table-scroll{overflow-x:auto}
.rank-history{width:100%;border-collapse:collapse;font-size:14px}
.rank-history th{text-align:right;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:600;padding:10px 14px;border-bottom:1px solid var(--line)}
.rank-history th:first-child{text-align:left}
.rank-history td{padding:11px 14px;border-bottom:1px solid #f0efea}
.rank-history td:first-child{text-align:left}
.stat{font-size:10px;letter-spacing:.06em;text-transform:uppercase;font-weight:600;color:var(--muted)}
.stat-new{color:var(--up)}.stat-reentry{color:var(--r-europe)}
/* milestones */
.milestones{list-style:none;border-left:2px solid var(--line);margin-left:6px}
.ms{position:relative;padding:0 0 22px 26px}
.ms::before{content:"";position:absolute;left:-7px;top:4px;width:12px;height:12px;border-radius:50%;background:var(--ink);border:2px solid #fff}
.ms-date{display:block;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:600}
.ms-title{display:block;font-size:15px;font-weight:600;margin-top:2px}
.ms-val{color:var(--r-asia);font-weight:700}
.ms-src{display:block;font-size:12px;color:var(--muted);margin-top:2px}
/* sources */
.sources{list-style:none;font-size:14px}
.sources li{padding:9px 0;border-bottom:1px solid #f0efea}
.sources a{color:var(--ink);text-decoration:none;border-bottom:1px solid #cfcdc6}.sources a:hover{border-color:var(--ink)}
.src-primary{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--up);font-weight:600;margin-left:6px}
.src-note{font-size:12px;color:var(--muted);margin-top:14px;line-height:1.55}
/* explore other */
.explore-other .xo-row{display:flex;flex-direction:column;gap:3px;padding:12px 0;border-bottom:1px solid #f0efea;font-size:14px}
.xo-h{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:600}
.explore-other a{color:var(--ink);text-decoration:none;border-bottom:1px solid #cfcdc6}.explore-other a:hover{border-color:var(--ink)}
/* region badge */
.rbadge{display:inline-flex;align-items:center;font-size:11px;font-weight:600;color:var(--rc)}
.rbadge::before{content:"";width:8px;height:8px;border-radius:50%;background:var(--rc);margin-right:6px}
/* footer */
.site-footer{background:#0e0e0e;color:#fff;padding:64px 48px 32px;margin-top:20px}
.site-footer .inner{max-width:1240px;margin:0 auto}
.foot-top{display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr 1.2fr;gap:32px;padding-bottom:40px;border-bottom:1px solid #262626}
.foot-brand img{height:20px;filter:invert(1);margin-bottom:12px}
.fb-lab{font-size:13px;font-weight:600;margin-bottom:8px}.foot-brand p{font-size:13px;color:#8a8a8a;line-height:1.5}
.foot-col h4,.foot-contact h4{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:#8a8a8a;margin-bottom:16px;font-weight:600}
.foot-col a,.foot-contact a{display:block;font-size:14px;color:#d4d4d4;text-decoration:none;margin-bottom:10px}
.foot-col a:hover,.foot-contact a:hover{color:#fff}
.loc{font-size:14px;color:#8a8a8a;margin-top:4px}
.foot-bottom{display:flex;justify-content:space-between;padding-top:24px;font-size:12px;color:#8a8a8a;flex-wrap:wrap;gap:12px}
.foot-legal a{color:#8a8a8a;text-decoration:none;margin-left:18px}.foot-legal a:hover{color:#fff}
/* responsive */
@media(max-width:860px){
.wrap{padding:0 24px}.site-nav{padding:14px 24px}.nav-mid,.nav-cta{display:none}.nav-toggle{display:block}
.nav-mid.open{display:flex;position:absolute;top:56px;left:0;right:0;flex-direction:column;gap:0;background:#fff;border-bottom:1px solid var(--line);padding:8px 24px}
.two-col{grid-template-columns:1fr;gap:32px}
.status-strip{grid-template-columns:repeat(2,1fr)}
.mx-head{align-items:flex-start}.official{white-space:normal}
.foot-top{grid-template-columns:1fr 1fr}}
@media(max-width:520px){.status-strip{grid-template-columns:1fr}.foot-top{grid-template-columns:1fr}}
/* economics */
.status-strip{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.ss-price{color:var(--r-asia)}
.mx-head-links{display:flex;flex-direction:column;gap:8px;align-items:flex-end}
.official-pricing{white-space:nowrap}
.etiles{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:var(--line);border:1px solid var(--line)}
.etile{background:#fff;padding:20px 18px}
.et-l{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:600;margin-bottom:10px}
.et-v{font-size:24px;font-weight: 400;letter-spacing: -0.025em;line-height:1.05}
.et-s{font-size:11px;color:var(--muted);margin-top:6px}
.et-yes{color:var(--up)}.et-na{color:#b8b6ae;font-weight:400}
/* calculator */
.calc{display:grid;grid-template-columns:1.3fr 1fr;gap:0;border:1px solid var(--line)}
.calc-panel{padding:22px 24px;border-right:1px solid var(--line)}
.wl-tabs{display:flex;gap:6px;margin-bottom:22px;flex-wrap:wrap}
.wl-tab{font:inherit;font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;padding:8px 12px;border:1px solid var(--line);background:#fff;cursor:pointer;color:var(--body)}
.wl-tab.active{background:var(--ink);color:#fff;border-color:var(--ink)}
.calc-fields{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.cf{display:flex;flex-direction:column;gap:6px;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:600}
.cf input[type=number]{font:inherit;font-size:16px;font-weight:600;color:var(--ink);text-transform:none;letter-spacing:0;padding:9px 11px;border:1px solid var(--line);border-radius:6px;width:100%}
.cf-slider{grid-column:1/-1}.cf-slider b{color:var(--ink)}
.cf input[type=range]{width:100%;accent-color:var(--r-asia)}
.calc-out{padding:24px 26px;background:var(--panel);display:flex;flex-direction:column}
.co-l{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:600}
.co-total{font-size:46px;font-weight: 400;color:var(--r-asia);letter-spacing: -0.05em;line-height:1;margin:8px 0 18px}
.co-row{display:flex;justify-content:space-between;font-size:14px;color:var(--body);padding:7px 0;border-top:1px solid var(--line)}
.co-per{margin-top:14px;font-size:15px;font-weight:700;color:var(--r-asia)}
.calc-note{font-size:12px;color:var(--muted);margin-top:12px}
/* compare */
.compare{display:flex;flex-direction:column;gap:2px}
.cmp-row{display:grid;grid-template-columns:200px 1fr 84px;gap:14px;align-items:center;padding:9px 0}
.cmp-name{font-size:14px;color:var(--body)}.cmp-you{font-weight:800;color:var(--r-asia)}
.cmp-bar{height:14px;background:var(--panel)}
.cmp-fill{display:block;height:100%;background:#3a3a3a;transition:width .3s}.cmp-fill-you{background:var(--r-asia)}
.cmp-val{text-align:right;font-weight:700;font-size:14px}
/* position box */
.pos-box{margin-top:26px;border:1px solid var(--line);padding:22px 24px;max-width:520px}
.pos-h{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:700}
.pos-label{font-size:26px;font-weight: 400;letter-spacing: -0.025em;margin:6px 0 8px;text-transform:uppercase;color:var(--ink)}
.pos-sub{font-size:13px;color:var(--muted);line-height:1.5}
/* speed / capabilities */
.speed-strip{grid-template-columns:1fr 1fr;margin:0 0 6px}
.cap-table{width:100%;border-collapse:collapse;font-size:14px}
.cap-table td{padding:10px 12px;border-bottom:1px solid #f0efea}
.cap-table td:last-child{text-align:right;font-weight:600}
.cap-yes{color:var(--up);font-weight:800}.cap-no{color:#b8b6ae}
.ph-up{color:var(--up);font-weight:700}.ph-down{color:var(--up);font-weight:700}.ph-flat{color:var(--muted)}
@media(max-width:860px){.etiles{grid-template-columns:repeat(3,1fr)}.calc{grid-template-columns:1fr}.calc-panel{border-right:none;border-bottom:1px solid var(--line)}.cmp-row{grid-template-columns:120px 1fr 70px;gap:10px}}
@media(max-width:520px){.etiles{grid-template-columns:repeat(2,1fr)}.calc-fields{grid-template-columns:1fr}.speed-strip{grid-template-columns:1fr}}

/* =====================================================================
   APPROVED INDIVIDUAL MODEL RECORD, v1 (1 September 2026).
   Pasted verbatim from the handoff and left scoped under its own
   #y3-model-record-redesign root, exactly as the package ships it. That
   scope is why it cannot collide with the rules above, which still style
   the shared nav and footer this generator emits.
   ===================================================================== */

    #y3-model-record-redesign {
      --y3r-ink:#11120f;
      --y3r-muted:#696e68;
      --y3r-line:#d9dcd7;
      --y3r-soft:#f3f4f1;
      --y3r-cream:#fffdf2;
      --y3r-yellow:#ffd500;
      --y3r-purple:#5c1a73;
      --y3r-green:#277b60;
      --y3r-red:#a34234;
      width:100%;
      overflow:hidden;
      background:#fff;
      color:var(--y3r-ink);
      font-family:Arial,Helvetica,sans-serif;
      font-size:16px;
      line-height:1.45;
      -webkit-font-smoothing:antialiased;
    }
    #y3-model-record-redesign *, #y3-model-record-redesign *::before, #y3-model-record-redesign *::after { box-sizing:border-box; }
    #y3-model-record-redesign h1, #y3-model-record-redesign h2, #y3-model-record-redesign h3, #y3-model-record-redesign p { margin:0; }
    #y3-model-record-redesign h1, #y3-model-record-redesign h2, #y3-model-record-redesign h3 { font-weight:400; }
    #y3-model-record-redesign a { color:inherit; text-decoration:none; }
    #y3-model-record-redesign button, #y3-model-record-redesign input { font:inherit; }
    #y3-model-record-redesign .y3r-wrap { max-width:1020px; margin:0 auto; padding:0 34px; }
    #y3-model-record-redesign .y3r-breadcrumb { padding:35px 0 0; color:#777c76; font-size:11px; letter-spacing:.02em; }
    #y3-model-record-redesign .y3r-breadcrumb strong { color:var(--y3r-ink); font-weight:400; }
    #y3-model-record-redesign .y3r-hero { padding:50px 0 78px; }
    #y3-model-record-redesign .y3r-hero-head { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:50px; align-items:end; padding-bottom:31px; border-bottom:1px solid var(--y3r-ink); }
    #y3-model-record-redesign .y3r-provider { display:flex; gap:19px; align-items:center; min-width:0; }
    #y3-model-record-redesign .y3r-logo { display:flex; width:64px; height:64px; flex:0 0 auto; align-items:center; justify-content:center; border:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-logo img { display:block; width:44px; height:44px; object-fit:contain; }
    #y3-model-record-redesign .y3r-eyebrow { color:#777c76; font-size:10px; font-weight:500; letter-spacing:.18em; text-transform:uppercase; }
    #y3-model-record-redesign h1 { margin-top:7px; font-size:52px; line-height:.98; letter-spacing:-.052em; }
    #y3-model-record-redesign .y3r-meta { margin-top:12px; color:#555a55; font-size:12px; }
    #y3-model-record-redesign .y3r-official { max-width:210px; text-align:right; }
    #y3-model-record-redesign .y3r-official p { color:#858984; font-size:11px; }
    #y3-model-record-redesign .y3r-link { display:inline-block; min-height:34px; margin-top:8px; padding-top:7px; border-bottom:1px solid var(--y3r-ink); font-size:11px; font-weight:500; letter-spacing:.06em; text-transform:uppercase; }
    #y3-model-record-redesign .y3r-signal { display:grid; grid-template-columns:1.16fr 1.84fr; margin-top:31px; border-top:1px solid var(--y3r-ink); border-left:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-primary-signal { position:relative; min-height:246px; padding:30px 31px 28px; border-right:1px solid var(--y3r-line); border-bottom:1px solid var(--y3r-line); background:var(--y3r-ink); color:#fff; }
    #y3-model-record-redesign .y3r-primary-signal::before { content:""; position:absolute; left:0; right:0; top:0; height:7px; background:var(--y3r-yellow); }
    #y3-model-record-redesign .y3r-signal-label { color:#aeb2ad; font-size:10px; font-weight:500; letter-spacing:.16em; text-transform:uppercase; }
    #y3-model-record-redesign .y3r-rank { margin-top:28px; font-size:104px; line-height:.78; letter-spacing:-.075em; }
    #y3-model-record-redesign .y3r-rank-context { margin-top:27px; color:#d0d3ce; font-size:12px; }
    #y3-model-record-redesign .y3r-secondary-signals { display:grid; grid-template-columns:1fr 1fr; }
    #y3-model-record-redesign .y3r-stat { min-height:123px; padding:25px 25px 22px; border-right:1px solid var(--y3r-line); border-bottom:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-stat-value { display:block; font-size:30px; line-height:1; letter-spacing:-.045em; }
    #y3-model-record-redesign .y3r-stat-value.y3r-up { color:var(--y3r-green); }
    #y3-model-record-redesign .y3r-stat-label { display:block; margin-top:13px; color:#777c76; font-size:9px; font-weight:500; letter-spacing:.14em; text-transform:uppercase; }
    #y3-model-record-redesign .y3r-freshness { display:flex; justify-content:space-between; gap:24px; padding-top:17px; color:#777c76; font-size:11px; }
    #y3-model-record-redesign .y3r-freshness strong { color:var(--y3r-ink); font-weight:500; }
    #y3-model-record-redesign .y3r-section { padding:84px 0; border-top:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-soft { background:var(--y3r-soft); }
    #y3-model-record-redesign .y3r-section-head { display:grid; grid-template-columns:1fr 1fr; gap:62px; align-items:end; margin-bottom:46px; }
    #y3-model-record-redesign .y3r-kicker { margin-bottom:18px; color:#737872; font-size:10px; font-weight:500; letter-spacing:.2em; text-transform:uppercase; }
    #y3-model-record-redesign h2 { max-width:670px; font-size:46px; line-height:1; letter-spacing:-.05em; }
    #y3-model-record-redesign .y3r-lede { max-width:440px; color:#555a55; font-size:16px; line-height:1.5; }
    #y3-model-record-redesign .y3r-readout { display:grid; grid-template-columns:repeat(3,1fr); border-top:1px solid var(--y3r-ink); }
    #y3-model-record-redesign .y3r-readout-item { min-height:188px; padding:25px 28px 27px 0; border-right:1px solid #cfd2ce; border-bottom:1px solid #cfd2ce; }
    #y3-model-record-redesign .y3r-readout-item + .y3r-readout-item { padding-left:28px; }
    #y3-model-record-redesign .y3r-readout-item:last-child { border-right:0; }
    #y3-model-record-redesign .y3r-readout-label { color:#777c76; font-size:9px; font-weight:500; letter-spacing:.14em; text-transform:uppercase; }
    #y3-model-record-redesign .y3r-readout-value { margin-top:23px; font-size:27px; line-height:1.08; letter-spacing:-.035em; }
    #y3-model-record-redesign .y3r-readout-copy { margin-top:12px; color:#666b66; font-size:12px; line-height:1.5; }
    #y3-model-record-redesign .y3r-economics { display:grid; grid-template-columns:.92fr 1.08fr; border-top:1px solid var(--y3r-ink); }
    #y3-model-record-redesign .y3r-price-ledger { display:grid; grid-template-columns:1fr 1fr; align-content:start; border-left:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-price-cell { min-height:132px; padding:22px 20px; border-right:1px solid var(--y3r-line); border-bottom:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-price-label { color:#777c76; font-size:9px; font-weight:500; letter-spacing:.12em; text-transform:uppercase; }
    #y3-model-record-redesign .y3r-price-value { display:block; margin-top:18px; font-size:27px; line-height:1; letter-spacing:-.04em; }
    #y3-model-record-redesign .y3r-price-unit { display:block; margin-top:7px; color:#858984; font-size:10px; }
    #y3-model-record-redesign .y3r-calculator { border-right:1px solid var(--y3r-line); border-bottom:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-scenarios { display:grid; grid-template-columns:repeat(3,1fr); border-bottom:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-scenario { min-height:48px; padding:0 12px; border:0; border-right:1px solid var(--y3r-line); background:#fff; color:#555a55; cursor:pointer; font-size:10px; font-weight:500; letter-spacing:.05em; text-transform:uppercase; }
    #y3-model-record-redesign .y3r-scenario:last-child { border-right:0; }
    #y3-model-record-redesign .y3r-scenario[aria-pressed="true"] { background:var(--y3r-ink); color:#fff; }
    #y3-model-record-redesign .y3r-calc-body { display:grid; grid-template-columns:1fr .8fr; min-height:348px; }
    #y3-model-record-redesign .y3r-fields { display:grid; grid-template-columns:1fr 1fr; gap:18px; align-content:start; padding:24px; border-right:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-field { display:block; }
    #y3-model-record-redesign .y3r-field.y3r-wide { grid-column:1 / -1; }
    #y3-model-record-redesign .y3r-field span { display:block; margin-bottom:7px; color:#777c76; font-size:9px; font-weight:500; letter-spacing:.1em; text-transform:uppercase; }
    #y3-model-record-redesign .y3r-field input[type="number"] { width:100%; height:43px; padding:0 11px; border:1px solid var(--y3r-line); border-radius:0; background:#fff; color:var(--y3r-ink); font-size:14px; }
    #y3-model-record-redesign .y3r-range-head { display:flex; justify-content:space-between; gap:16px; align-items:center; }
    #y3-model-record-redesign .y3r-field input[type="range"] { width:100%; accent-color:var(--y3r-purple); }
    #y3-model-record-redesign .y3r-result { padding:25px 23px; background:var(--y3r-cream); }
    #y3-model-record-redesign .y3r-result-label { color:#777c76; font-size:9px; font-weight:500; letter-spacing:.12em; text-transform:uppercase; }
    #y3-model-record-redesign .y3r-total { margin-top:18px; color:var(--y3r-purple); font-size:43px; line-height:1; letter-spacing:-.05em; }
    #y3-model-record-redesign .y3r-breakdown { margin-top:25px; border-top:1px solid #d8d7cc; }
    #y3-model-record-redesign .y3r-breakdown-row { display:flex; justify-content:space-between; gap:20px; padding:10px 0; border-bottom:1px solid #e2e0d5; color:#555a55; font-size:11px; }
    #y3-model-record-redesign .y3r-task-cost { margin-top:18px; color:var(--y3r-purple); font-size:12px; font-weight:500; }
    #y3-model-record-redesign .y3r-note { margin-top:14px; color:#777c76; font-size:11px; line-height:1.5; }
    #y3-model-record-redesign .y3r-compare { margin-top:42px; border-top:1px solid var(--y3r-ink); }
    #y3-model-record-redesign .y3r-compare-row { display:grid; grid-template-columns:230px 1fr 72px; gap:20px; align-items:center; min-height:51px; border-bottom:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-compare-name { font-size:12px; }
    #y3-model-record-redesign .y3r-compare-name strong { color:var(--y3r-purple); font-weight:500; }
    #y3-model-record-redesign .y3r-compare-track { height:7px; background:#e8e9e6; }
    #y3-model-record-redesign .y3r-compare-fill { display:block; height:100%; background:#3a3c39; }
    #y3-model-record-redesign .y3r-compare-fill.y3r-you { background:var(--y3r-purple); }
    #y3-model-record-redesign .y3r-compare-value { text-align:right; font-size:12px; font-weight:500; }
    #y3-model-record-redesign .y3r-chart-frame { border-top:1px solid var(--y3r-ink); border-bottom:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-chart-head { display:flex; justify-content:space-between; gap:32px; align-items:end; padding:22px 0 12px; }
    #y3-model-record-redesign .y3r-chart-head strong { font-size:16px; font-weight:500; }
    #y3-model-record-redesign .y3r-chart-head span { color:#777c76; font-size:11px; }
    #y3-model-record-redesign .y3r-chart { display:block; width:100%; height:auto; min-height:260px; }
    #y3-model-record-redesign .y3r-chart text { font-family:Arial,Helvetica,sans-serif; }
    #y3-model-record-redesign .y3r-chart-summary { display:grid; grid-template-columns:1fr 1fr; border-bottom:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-chart-summary > div { min-height:120px; padding:22px 24px 22px 0; border-right:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-chart-summary > div:last-child { padding-left:24px; border-right:0; }
    #y3-model-record-redesign .y3r-summary-label { color:#777c76; font-size:9px; font-weight:500; letter-spacing:.13em; text-transform:uppercase; }
    #y3-model-record-redesign .y3r-summary-value { margin-top:13px; font-size:23px; line-height:1.1; letter-spacing:-.03em; }
    #y3-model-record-redesign .y3r-summary-copy { margin-top:8px; color:#777c76; font-size:11px; }
    #y3-model-record-redesign .y3r-profile-grid { display:grid; grid-template-columns:1fr 1fr; border-top:1px solid var(--y3r-ink); }
    #y3-model-record-redesign .y3r-profile-col { border-right:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-profile-col:last-child { border-right:0; }
    #y3-model-record-redesign .y3r-profile-title { min-height:64px; padding:21px 24px; border-bottom:1px solid var(--y3r-line); font-size:17px; font-weight:500; }
    #y3-model-record-redesign .y3r-fact { display:grid; grid-template-columns:1fr 1fr; gap:22px; min-height:54px; padding:15px 24px; border-bottom:1px solid var(--y3r-line); font-size:12px; }
    #y3-model-record-redesign .y3r-fact span:first-child { color:#777c76; }
    #y3-model-record-redesign .y3r-yes { color:var(--y3r-green); font-weight:500; }
    #y3-model-record-redesign .y3r-no { color:#777c76; }
    #y3-model-record-redesign .y3r-analysis { background:var(--y3r-ink); color:#fff; }
    #y3-model-record-redesign .y3r-analysis .y3r-kicker { color:#aeb2ad; }
    #y3-model-record-redesign .y3r-analysis-grid { display:grid; grid-template-columns:.72fr 1.28fr; gap:70px; align-items:start; }
    #y3-model-record-redesign .y3r-analysis h2 { max-width:340px; }
    #y3-model-record-redesign .y3r-analysis-copy { padding-top:4px; }
    #y3-model-record-redesign .y3r-analysis-copy blockquote { margin:0; padding:0 0 30px; border-bottom:1px solid #3d403c; font-size:25px; font-weight:400; line-height:1.34; letter-spacing:-.025em; }
    #y3-model-record-redesign .y3r-analysis-copy p { margin-top:25px; color:#c3c7c1; font-size:14px; line-height:1.6; }
    #y3-model-record-redesign .y3r-analysis-copy strong { color:#fff; font-weight:500; }
    #y3-model-record-redesign .y3r-table-wrap { overflow-x:auto; }
    #y3-model-record-redesign table { width:100%; border-collapse:collapse; text-align:left; }
    #y3-model-record-redesign th { padding:12px 12px 12px 0; border-bottom:1px solid var(--y3r-ink); color:#777c76; font-size:9px; font-weight:500; letter-spacing:.1em; text-transform:uppercase; white-space:nowrap; }
    #y3-model-record-redesign td { padding:16px 12px 16px 0; border-bottom:1px solid var(--y3r-line); font-size:12px; vertical-align:top; }
    #y3-model-record-redesign .y3r-movement-up { color:var(--y3r-green); font-weight:500; }
    #y3-model-record-redesign .y3r-movement-down { color:var(--y3r-red); font-weight:500; }
    #y3-model-record-redesign .y3r-status { font-size:9px; font-weight:500; letter-spacing:.1em; text-transform:uppercase; }
    #y3-model-record-redesign .y3r-history-grid { display:grid; grid-template-columns:1fr 1fr; gap:54px; margin-top:65px; }
    #y3-model-record-redesign .y3r-subhead { display:flex; justify-content:space-between; gap:20px; align-items:end; margin-bottom:18px; padding-bottom:12px; border-bottom:1px solid var(--y3r-ink); }
    #y3-model-record-redesign .y3r-subhead h3 { font-size:23px; line-height:1.1; letter-spacing:-.03em; }
    #y3-model-record-redesign .y3r-subhead span { color:#777c76; font-size:10px; }
    #y3-model-record-redesign .y3r-price-event { display:grid; grid-template-columns:84px 1fr auto; gap:14px; padding:13px 0; border-bottom:1px solid var(--y3r-line); align-items:baseline; font-size:11px; }
    #y3-model-record-redesign .y3r-price-event time { color:#777c76; }
    #y3-model-record-redesign .y3r-price-event strong { font-weight:500; }
    #y3-model-record-redesign details { margin-top:14px; }
    #y3-model-record-redesign summary { min-height:44px; padding-top:12px; cursor:pointer; font-size:11px; font-weight:500; }
    #y3-model-record-redesign .y3r-more-prices { border-top:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-milestones { display:grid; grid-template-columns:repeat(4,1fr); margin-top:42px; border-top:1px solid var(--y3r-ink); }
    #y3-model-record-redesign .y3r-milestone { min-height:160px; padding:21px 19px 22px 0; border-right:1px solid var(--y3r-line); border-bottom:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-milestone:nth-child(4n+2), #y3-model-record-redesign .y3r-milestone:nth-child(4n+3), #y3-model-record-redesign .y3r-milestone:nth-child(4n+4) { padding-left:19px; }
    #y3-model-record-redesign .y3r-milestone:nth-child(4n) { border-right:0; }
    #y3-model-record-redesign .y3r-milestone time { color:#777c76; font-size:9px; font-weight:500; letter-spacing:.1em; text-transform:uppercase; }
    #y3-model-record-redesign .y3r-milestone strong { display:block; margin-top:22px; font-size:16px; font-weight:500; line-height:1.25; }
    #y3-model-record-redesign .y3r-milestone span { display:block; margin-top:9px; color:#858984; font-size:10px; }
    #y3-model-record-redesign .y3r-source-grid { display:grid; grid-template-columns:.8fr 1.2fr; gap:66px; }
    #y3-model-record-redesign .y3r-source-links a { display:block; min-height:47px; padding:14px 0; border-top:1px solid var(--y3r-line); font-size:12px; }
    #y3-model-record-redesign .y3r-source-links a:last-child { border-bottom:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-source-copy { color:#555a55; font-size:14px; line-height:1.6; }
    #y3-model-record-redesign .y3r-explore { margin-top:66px; }
    #y3-model-record-redesign .y3r-explore-grid { display:grid; grid-template-columns:repeat(3,1fr); border-top:1px solid var(--y3r-ink); }
    #y3-model-record-redesign .y3r-explore-group { min-height:150px; padding:22px 23px 22px 0; border-right:1px solid var(--y3r-line); border-bottom:1px solid var(--y3r-line); }
    #y3-model-record-redesign .y3r-explore-group + .y3r-explore-group { padding-left:23px; }
    #y3-model-record-redesign .y3r-explore-group:last-child { border-right:0; }
    #y3-model-record-redesign .y3r-explore-label { color:#777c76; font-size:9px; font-weight:500; letter-spacing:.12em; text-transform:uppercase; }
    #y3-model-record-redesign .y3r-explore-group a { display:block; margin-top:10px; font-size:12px; }
    #y3-model-record-redesign .y3r-final { padding:69px 0; background:var(--y3r-ink); color:#fff; }
    #y3-model-record-redesign .y3r-final-grid { display:grid; grid-template-columns:1.25fr .75fr; gap:70px; align-items:end; }
    #y3-model-record-redesign .y3r-final .y3r-kicker { color:#aeb2ad; }
    #y3-model-record-redesign .y3r-final h2 { max-width:620px; }
    #y3-model-record-redesign .y3r-final p { max-width:560px; margin-top:18px; color:#c5c9c3; font-size:14px; }
    #y3-model-record-redesign .y3r-action { display:inline-flex; min-height:46px; padding:0 18px; align-items:center; justify-content:center; background:var(--y3r-yellow); color:var(--y3r-ink); font-size:11px; font-weight:500; }
    #y3-model-record-redesign .y3r-sr { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }
    @media(max-width:760px) {
      #y3-model-record-redesign .y3r-wrap { padding:0 22px; }
      #y3-model-record-redesign .y3r-hero-head, #y3-model-record-redesign .y3r-section-head, #y3-model-record-redesign .y3r-economics, #y3-model-record-redesign .y3r-analysis-grid, #y3-model-record-redesign .y3r-source-grid, #y3-model-record-redesign .y3r-final-grid { grid-template-columns:1fr; }
      #y3-model-record-redesign .y3r-hero-head { gap:24px; align-items:start; }
      #y3-model-record-redesign .y3r-official { max-width:none; text-align:left; }
      #y3-model-record-redesign h1 { font-size:43px; }
      #y3-model-record-redesign h2 { font-size:37px; }
      #y3-model-record-redesign .y3r-signal { grid-template-columns:1fr; }
      #y3-model-record-redesign .y3r-primary-signal { min-height:210px; }
      #y3-model-record-redesign .y3r-rank { font-size:86px; }
      #y3-model-record-redesign .y3r-section-head { gap:22px; }
      #y3-model-record-redesign .y3r-readout { grid-template-columns:1fr; }
      #y3-model-record-redesign .y3r-readout-item, #y3-model-record-redesign .y3r-readout-item + .y3r-readout-item { min-height:0; padding:22px 0; border-right:0; }
      #y3-model-record-redesign .y3r-calc-body { grid-template-columns:1fr; }
      #y3-model-record-redesign .y3r-fields { border-right:0; border-bottom:1px solid var(--y3r-line); }
      #y3-model-record-redesign .y3r-profile-grid { grid-template-columns:1fr; }
      #y3-model-record-redesign .y3r-profile-col { border-right:0; }
      #y3-model-record-redesign .y3r-history-grid { grid-template-columns:1fr; gap:54px; }
      #y3-model-record-redesign .y3r-milestones { grid-template-columns:1fr 1fr; }
      #y3-model-record-redesign .y3r-milestone:nth-child(n) { padding:21px 18px; }
      #y3-model-record-redesign .y3r-milestone:nth-child(2n) { border-right:0; }
      #y3-model-record-redesign .y3r-explore-grid { grid-template-columns:1fr; }
      #y3-model-record-redesign .y3r-explore-group, #y3-model-record-redesign .y3r-explore-group + .y3r-explore-group { min-height:0; padding:20px 0; border-right:0; }
    }
    @media(max-width:480px) {
      #y3-model-record-redesign .y3r-breadcrumb { padding-top:24px; }
      #y3-model-record-redesign .y3r-hero { padding:38px 0 58px; }
      #y3-model-record-redesign .y3r-section { padding:66px 0; }
      #y3-model-record-redesign .y3r-provider { align-items:flex-start; }
      #y3-model-record-redesign .y3r-logo { width:54px; height:54px; }
      #y3-model-record-redesign .y3r-logo img { width:38px; height:38px; }
      #y3-model-record-redesign h1 { font-size:36px; }
      #y3-model-record-redesign .y3r-meta { line-height:1.6; }
      #y3-model-record-redesign .y3r-secondary-signals { grid-template-columns:1fr; }
      #y3-model-record-redesign .y3r-stat { min-height:100px; }
      #y3-model-record-redesign .y3r-freshness { display:block; }
      #y3-model-record-redesign .y3r-freshness span { display:block; margin-top:4px; }
      #y3-model-record-redesign .y3r-price-ledger { grid-template-columns:1fr; }
      #y3-model-record-redesign .y3r-scenarios { grid-template-columns:1fr; }
      #y3-model-record-redesign .y3r-scenario { border-right:0; border-bottom:1px solid var(--y3r-line); }
      #y3-model-record-redesign .y3r-fields { grid-template-columns:1fr; }
      #y3-model-record-redesign .y3r-field.y3r-wide { grid-column:auto; }
      #y3-model-record-redesign .y3r-compare-row { grid-template-columns:1fr auto; gap:8px; padding:13px 0; }
      #y3-model-record-redesign .y3r-compare-track { grid-column:1 / -1; grid-row:2; }
      #y3-model-record-redesign .y3r-compare-value { grid-column:2; grid-row:1; }
      #y3-model-record-redesign .y3r-chart-head { display:block; }
      #y3-model-record-redesign .y3r-chart-head span { display:block; margin-top:5px; }
      #y3-model-record-redesign .y3r-chart { min-height:210px; }
      #y3-model-record-redesign .y3r-chart-summary { grid-template-columns:1fr; }
      #y3-model-record-redesign .y3r-chart-summary > div, #y3-model-record-redesign .y3r-chart-summary > div:last-child { min-height:0; padding:20px 0; border-right:0; border-bottom:1px solid var(--y3r-line); }
      #y3-model-record-redesign .y3r-fact { grid-template-columns:1fr; gap:4px; }
      #y3-model-record-redesign .y3r-analysis-copy blockquote { font-size:21px; }
      #y3-model-record-redesign .y3r-milestones { grid-template-columns:1fr; }
      #y3-model-record-redesign .y3r-milestone:nth-child(n) { min-height:0; padding:20px 0; border-right:0; }
    }
  
"""


MODEL_JS = """(function(){
  var E=window.__ECON, calc=document.getElementById('calc');
  if(!E||!calc) return;
  var $=function(id){return document.getElementById(id);};
  var tasks=$('c-tasks'),inp=$('c-inp'),outp=$('c-outp'),cached=$('c-cached'),cv=$('c-cached-v');
  function cost(p,w){
    if(!p||p.in==null||p.out==null) return null;
    var itok=w.tasks*w.inp, otok=w.tasks*w.outp;
    var crp=(p.cache_read!=null?p.cache_read:p.in);
    var unc=itok*(1-w.cached)*p.in, cac=itok*w.cached*crp, out=otok*p.out;
    return {total:unc+cac+out,unc:unc,cac:cac,out:out};
  }
  function money(v){ if(v==null) return '\\u2014'; return '$'+(v>=100?v.toFixed(0):v.toFixed(2)); }
  function readW(){ return {tasks:+tasks.value||0,inp:+inp.value||0,outp:+outp.value||0,cached:(+cached.value||0)/100}; }
  function render(){
    var w=readW(); if(cv) cv.textContent=cached.value;
    var r=cost(E.you,w);
    if(r){
      $('c-total').textContent=money(r.total);
      $('c-unc').textContent=money(r.unc); $('c-cac').textContent=money(r.cac); $('c-out').textContent=money(r.out);
      var per=w.tasks>0?r.total/w.tasks:0;
      $('c-per').textContent=(per<1?'$'+per.toFixed(3):money(per))+' per completed task';
    }
    var rows=document.querySelectorAll('#compare .cmp-row'), costs=[];
    (E.compare||[]).forEach(function(c){ var cc=cost(c,w); costs.push(cc?cc.total:null); });
    var valid=costs.filter(function(x){return x!=null;}); var mx=valid.length?Math.max.apply(null,valid):1;
    Array.prototype.forEach.call(rows,function(row,i){
      var t=costs[i], f=row.querySelector('.cmp-fill'), v=row.querySelector('.cmp-val');
      if(f) f.style.width=(t!=null?100*t/mx:0)+'%'; if(v) v.textContent=money(t);
    });
  }
  Array.prototype.forEach.call(document.querySelectorAll('.wl-tab'),function(tab){
    tab.addEventListener('click',function(){
      var w=(E.workloads||{})[tab.getAttribute('data-wl')];
      if(w){ tasks.value=w.tasks; inp.value=w.inp; outp.value=w.outp; cached.value=Math.round(w.cached*100); }
      document.querySelectorAll('.wl-tab').forEach(function(t){t.classList.remove('active');});
      tab.classList.add('active'); render();
    });
  });
  [tasks,inp,outp,cached].forEach(function(el){ if(el) el.addEventListener('input',render); });
  var def=(E.workloads||{})['coding-agent'];
  if(def){ tasks.value=def.tasks; inp.value=def.inp; outp.value=def.outp; cached.value=Math.round(def.cached*100); }
  render();
})();"""

# --------------------------------------------------------------- generate --

def generate():
    main = json.load(open(MAIN_JSON))
    models = json.load(open(os.path.join(DATA_DIR, "models.json")))["models"]
    providers = json.load(open(os.path.join(DATA_DIR, "providers.json")))
    meta_all = json.load(open(os.path.join(DATA_DIR, "model-meta.json")))
    page_slugs = json.load(open(os.path.join(DATA_DIR, "pages.json")))
    econ_doc = {}
    try:
        econ_doc = json.load(open(os.path.join(DATA_DIR, "economics.json")))
    except (FileNotFoundError, ValueError):
        pass
    econ_models = econ_doc.get("models", {})
    site = {"as_of": main["as_of"], "as_of_pretty": main["as_of_pretty"],
            "workloads": econ_doc.get("workloads", {})}

    os.makedirs(PAGES_DIR, exist_ok=True)
    open(os.path.join(PAGES_DIR, "model.css"), "w").write(CSS)
    open(os.path.join(PAGES_DIR, "model.js"), "w").write(MODEL_JS)

    written = 0
    for slug in page_slugs:
        m = models.get(slug)
        if not m:
            continue
        provider = providers.get(m["developer"], {"name": m["provider_name"], "region": m["region"], "country": m["country"]})
        meta = meta_all.get(slug, {})
        htmlout = render_page(m, provider, meta, models, page_slugs, site, econ_models.get(slug))
        open(os.path.join(PAGES_DIR, f"{slug}.html"), "w").write(htmlout)
        written += 1
    print(f"model pages written: {written} -> {PAGES_DIR}")
    return written


if __name__ == "__main__":
    generate()
