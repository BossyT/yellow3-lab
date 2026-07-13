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
import os
import re
import json
import html
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(HERE, "model-adoption")
DATA_DIR = os.path.join(PAGES_DIR, "_data")
MAIN_JSON = os.path.join(HERE, "model-adoption-data.json")

HOST = "https://yellow3.io"          # build rewrites to www at deploy
BASE = "/research/model-adoption"
GA_ID = "G-K3JXMM2VG5"

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

NAV = """  <nav class="site-nav">
    <a href="/" class="brand"><img src="/logo.png" alt="yellow3" /></a>
    <div class="nav-mid" id="navMid">
      <a href="/naffe">Work</a>
      <a href="/research" class="active">Research</a>
      <a href="/insights/">Thinking</a>
      <a href="/advisory">Advisory</a>
      <a href="/about">About</a>
      <a href="/#contact">Contact</a>
    </div>
    <a href="#" onclick="window.location.href='mailto:'+'hello'+String.fromCharCode(64)+'yellow3.io';return false;" class="nav-cta">Get in touch <span>&#8594;</span></a>
    <button class="nav-toggle" aria-label="Menu" onclick="this.classList.toggle('open');document.getElementById('navMid').classList.toggle('open')"><span></span><span></span><span></span></button>
  </nav>"""

FOOTER = """  <footer class="site-footer">
    <div class="inner">
      <div class="foot-top">
        <div class="foot-brand">
          <img src="/logo.png" alt="yellow3" />
          <div class="fb-lab">Copenhagen AI Lab</div>
          <p>Building outcome infrastructure for the AI era.</p>
        </div>
        <div class="foot-col">
          <h4>Work</h4>
          <a href="/naffe">naffe.ai</a>
          <a href="/research/digital-product-passport">Digital Product Passports</a>
          <a href="/advisory">Advisory</a>
        </div>
        <div class="foot-col">
          <h4>Research</h4>
          <a href="/research">Research areas</a>
          <a href="/research/model-adoption">Model adoption</a>
          <a href="/research/eu-ai-act">EU AI Act</a>
        </div>
        <div class="foot-col">
          <h4>Company</h4>
          <a href="/about">About</a>
          <a href="/insights/">Thinking</a>
          <a href="#" onclick="window.location.href='mailto:'+'hello'+String.fromCharCode(64)+'yellow3.io';return false;">Contact</a>
        </div>
        <div class="foot-contact">
          <h4>Get in touch</h4>
          <a href="#" onclick="window.location.href='mailto:'+'hello'+String.fromCharCode(64)+'yellow3.io';return false;" class="mail">Email us</a>
          <div class="loc">Copenhagen, Denmark</div>
        </div>
      </div>
      <div class="foot-bottom">
        <span class="copy">&copy; 2026 yellow3 lab ApS. All rights reserved.</span>
        <div class="foot-legal">
          <a href="/privacy">Privacy</a>
          <a href="/terms">Terms</a>
          <a href="/cookies">Cookies</a>
        </div>
      </div>
    </div>
  </footer>"""


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
    links.append(f'<li><a href="{BASE}#methodology">yellow3 Model Adoption methodology</a></li>')
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
    og_img = f"{HOST}/og/og-model-adoption-v2.png"
    breadcrumb = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Research", "item": f"{HOST}/research"},
            {"@type": "ListItem", "position": 2, "name": "Model adoption", "item": f"{HOST}{BASE}"},
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
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{GA_ID}');</script>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}" />
  <link rel="canonical" href="{url}" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet" />
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

def render_page(m, provider, meta, models_by_slug, page_slugs, site):
    updated = site["as_of"]
    cur = m["current"]
    name = esc(m["name"])
    origin = " &middot; ".join([x for x in [esc(m["region"]), esc(m["country"])] if x])
    official = meta.get("official_url") or provider.get("official_url")
    official_link = (f'<a class="official" href="{esc(official)}" target="_blank" rel="noopener noreferrer">Official model page <span>&#8599;</span></a>'
                     if official else '<span class="official official-none">Official model page not yet on record</span>')

    parts = [head(m, provider, meta, updated), NAV]
    parts.append(f'''  <main class="mx">
    <div class="wrap">
      <nav class="crumb" aria-label="Breadcrumb">
        <a href="/research">Research</a> <span>/</span>
        <a href="{BASE}">Model adoption</a> <span>/</span>
        <span aria-current="page">{name}</span>
      </nav>

      <header class="mx-head">
        <div class="mx-head-main">
          {provider_tile(provider)}
          <div>
            <div class="mx-provider">Model provider</div>
            <h1>{name}</h1>
            <div class="mx-meta">Built by {esc(m["provider_name"])} &middot; {origin} &middot; First tracked {esc(D(m["first_tracked"]))}</div>
          </div>
        </div>
        {official_link}
      </header>

      <section class="status-strip" aria-label="Current status">
        <div class="ss"><span class="ss-v">#{cur["global_rank"]}</span><span class="ss-l">Global rank</span></div>
        <div class="ss"><span class="ss-v">{cur["routed_share"]:.2f}%</span><span class="ss-l">Routed share</span></div>
        <div class="ss"><span class="ss-v">{movement_cell(cur["rank_change"])}</span><span class="ss-l">This week</span></div>
        <div class="ss"><span class="ss-v">{streak_text(m)}</span><span class="ss-l">Streak</span></div>
        <div class="ss"><span class="ss-v">#{m["peak_rank"]}</span><span class="ss-l">Peak rank</span></div>
      </section>

      <section class="mx-sec">
        <div class="sec-label">Adoption over time</div>
        <p class="sec-sub">Routed-token share, week by week. The figures are in the rank history table below.</p>
        {adoption_chart(m["series"])}
      </section>

      <section class="mx-sec two-col">
        <div>
          <div class="sec-label">At a glance</div>
          <dl class="glance">{at_a_glance(m, provider, meta)}</dl>
        </div>
        <div>
          <div class="sec-label">Why it is moving</div>
          {why_moving(m)}
        </div>
      </section>

      <section class="mx-sec">
        <div class="sec-label">Rank history</div>
        <div class="table-scroll">
          <table class="rank-history">
            <thead><tr><th>Week ending</th><th>Rank</th><th>Routed share</th><th>&Delta; share</th><th>Movement</th><th>Region rank</th><th>Status</th></tr></thead>
            <tbody>{rank_history_rows(m["series"])}</tbody>
          </table>
        </div>
      </section>

      <section class="mx-sec">
        <div class="sec-label">Milestones</div>
        <ul class="milestones">{milestones_list(m)}</ul>
      </section>

      <section class="mx-sec two-col">
        <div>
          <div class="sec-label">Sources &amp; methodology</div>
          <ul class="sources">{sources_section(m, provider, meta)}</ul>
          <p class="src-note">Region reflects where the model's developer is headquartered.
          Figures are OpenRouter routing traffic, aggregated over a trailing seven days -
          developer routing behaviour, not the whole market.</p>
        </div>
        <div>
          <div class="sec-label">Explore other models</div>
          <div class="explore-other">{explore_other(m, models_by_slug, page_slugs)}</div>
        </div>
      </section>
    </div>
  </main>
{FOOTER}
</body>
</html>''')
    return "\n".join(parts)


# ------------------------------------------------------------------- css --

CSS = """*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--paper:#fff;--ink:#0e0e0e;--body:#4b4b4b;--muted:#8a8a8a;--line:#e7e6e2;--yellow:#ffe000;--panel:#f7f6f3;
--up:#2E9D78;--down:#b3402e;--flat:#9a9a95;
--r-asia:#4d146c;--r-us:#003268;--r-europe:#ffba02;--r-other:#828383}
html{scroll-behavior:smooth}
body{background:var(--paper);color:var(--ink);font-family:'DM Sans',system-ui,sans-serif;font-weight:400;line-height:1.6;font-size:16px;-webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}
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
.ptile-fallback{font-weight:700;font-size:20px;color:#3a3a3a;background:var(--panel);letter-spacing:.02em}
.mx-provider{font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);font-weight:600;margin-bottom:4px}
.mx-head h1{font-size:clamp(28px,4vw,40px);font-weight:800;letter-spacing:-.02em;line-height:1.05}
.mx-meta{font-size:14px;color:var(--body);margin-top:6px}
.official{font-size:12px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;text-decoration:none;border-bottom:1.5px solid var(--ink);padding-bottom:2px;white-space:nowrap}
.official span{font-weight:400}.official-none{color:var(--muted);border:none;text-transform:none;letter-spacing:0;font-weight:400}
/* status strip */
.status-strip{display:grid;grid-template-columns:repeat(5,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin:28px 0 8px}
.ss{background:#fff;padding:20px 22px;display:flex;flex-direction:column;gap:6px}
.ss-v{font-size:24px;font-weight:800;letter-spacing:-.01em;line-height:1.1}
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
"""

# --------------------------------------------------------------- generate --

def generate():
    main = json.load(open(MAIN_JSON))
    models = json.load(open(os.path.join(DATA_DIR, "models.json")))["models"]
    providers = json.load(open(os.path.join(DATA_DIR, "providers.json")))
    meta_all = json.load(open(os.path.join(DATA_DIR, "model-meta.json")))
    page_slugs = json.load(open(os.path.join(DATA_DIR, "pages.json")))
    site = {"as_of": main["as_of"], "as_of_pretty": main["as_of_pretty"]}

    os.makedirs(PAGES_DIR, exist_ok=True)
    open(os.path.join(PAGES_DIR, "model.css"), "w").write(CSS)

    written = 0
    for slug in page_slugs:
        m = models.get(slug)
        if not m:
            continue
        provider = providers.get(m["developer"], {"name": m["provider_name"], "region": m["region"], "country": m["country"]})
        meta = meta_all.get(slug, {})
        htmlout = render_page(m, provider, meta, models, page_slugs, site)
        open(os.path.join(PAGES_DIR, f"{slug}.html"), "w").write(htmlout)
        written += 1
    print(f"model pages written: {written} -> {PAGES_DIR}")
    return written


if __name__ == "__main__":
    generate()
