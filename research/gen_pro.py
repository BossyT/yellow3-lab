#!/usr/bin/env python3
"""
yellow3 - Model Intelligence "Professional" dashboard (preview of the paid tier).

A layout-only funnel/preview page built from real data - subscriber briefing,
featured monthly report, a demo watchlist, real data-derived alerts, and an
adoption-vs-cost economics scatter. No payments or accounts here (that's a
business layer Thomas owns); the watchlist is a demo set and there are no fake
event timestamps. Served at /research/model-adoption/pro.
"""
import os
import json
import datetime as dt

from gen_model_pages import esc, D, HOST, BASE, GA_ID, FOOTER

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(HERE, "model-adoption")
DATA_DIR = os.path.join(PAGES_DIR, "_data")

# pricing (from Thomas): launch Professional at an early-member 49, later 79.
PRO_MONTH, PRO_YEAR, PRO_LAUNCH = 79, 790, 49


def _load(path, default=None):
    try:
        return json.load(open(path))
    except (FileNotFoundError, ValueError):
        return default if default is not None else {}


def money(v):
    if v is None:
        return "n/a"
    return f"${v:,.0f}" if v >= 100 else f"${v:,.2f}"


def build_alerts(lb, econ, models, as_of):
    """Real, data-derived alerts - no fabricated timestamps; labelled by type + week."""
    out = []
    for r in lb:
        e = econ.get(r["slug"], {})
        for h in (e.get("price_history") or []):
            if h.get("change_pct") and h["change_pct"] < 0:
                out.append(("PRICE", f'{r["name"]} cut output price {abs(h["change_pct"]):.0f}%', r["slug"]))
                break
    movers = sorted([r for r in lb if r.get("prev_rank")], key=lambda r: -((r["prev_rank"] or r["rank"]) - r["rank"]))
    for r in movers[:2]:
        j = (r["prev_rank"] or r["rank"]) - r["rank"]
        if j > 0:
            out.append(("RANKING", f'{r["name"]} rose {j} place(s) to #{r["rank"]}', r["slug"]))
    for r in lb:
        if r.get("new"):
            out.append(("NEW MODEL", f'{r["name"]} entered the ranking at #{r["rank"]}', r["slug"]))
    return out[:6]


def scatter_svg(rows):
    """Adoption (y, %) vs standardized workload cost (x, log $). One dot per model."""
    W, H = 560, 300
    padL, padR, padT, padB = 44, 14, 16, 38
    import math
    pts = [(r["cost"], r["pct"], r["region"], r["name"]) for r in rows
           if r.get("cost") and r["cost"] > 0]
    if not pts:
        return "<p class='fine'>No priced models.</p>"
    xmin, xmax = 0.5, max(600, max(p[0] for p in pts))
    ymax = max(4, max(p[1] for p in pts) * 1.1)

    def X(c):
        return padL + (W - padL - padR) * (math.log10(max(c, xmin)) - math.log10(xmin)) / (math.log10(xmax) - math.log10(xmin))

    def Y(s):
        return padT + (H - padT - padB) * (1 - s / ymax)

    grid = ""
    for gx in (1, 10, 100, 500):
        x = X(gx)
        grid += (f'<line x1="{x:.0f}" y1="{padT}" x2="{x:.0f}" y2="{H-padB}" class="sg"/>'
                 f'<text x="{x:.0f}" y="{H-padB+16}" class="sx">${gx}</text>')
    for gy in range(0, int(ymax) + 1, max(1, int(ymax) // 4)):
        y = Y(gy)
        grid += f'<line x1="{padL}" y1="{y:.0f}" x2="{W-padR}" y2="{y:.0f}" class="sg"/><text x="{padL-6}" y="{y+3:.0f}" class="sy">{gy}%</text>'
    dots = "".join(
        f'<circle cx="{X(c):.1f}" cy="{Y(s):.1f}" r="5" class="sd sd-{reg.lower()}"><title>{esc(nm)}: {s:.2f}% at {money(c)}/mo</title></circle>'
        for c, s, reg, nm in pts)
    return (f'<svg viewBox="0 0 {W} {H}" class="scatter" role="img" aria-label="Adoption versus standardized workload cost, one point per model">'
            f'<g>{grid}</g>{dots}'
            f'<text x="{(W)/2:.0f}" y="{H-4}" class="sax">Standardized monthly workload cost (log)</text></svg>')


def render(main, econ, models):
    as_of = main["as_of"]
    share = {s["region"]: s for s in main["share"]}
    lb = main["leaderboard"]
    number_one = lb[0] if lb else None
    # biggest mover from records
    biggest = next((r for r in main.get("records", []) if r.get("key") == "biggest_mover"), None)
    rows = []
    for r in lb:
        e = econ.get(r["slug"], {})
        rows.append({**r, "cost": e.get("workload_cost")})

    def stat(v, l, sub=""):
        return (f'<div class="pstat"><div class="pstat-v">{v}</div><div class="pstat-l">{esc(l)}</div>'
                f'{f"<div class=pstat-s>{sub}</div>" if sub else ""}</div>')

    def dpp(x):
        c = "up" if x > 0.04 else ("down" if x < -0.04 else "flat")
        a = "&#9650;" if x > 0.04 else ("&#9660;" if x < -0.04 else "")
        return f'<span class="rc-{c}">{a} {x:+.1f} pp</span>'

    asia, us = share.get("Asia", {}), share.get("US", {})
    # watchlist demo set (real data for these slugs)
    wl_slugs = ["xiaomi-mimo-v2-5", "deepseek-v4-flash", "anthropic-claude-sonnet-5", "google-gemini-3-flash-preview"]
    by_slug = {r["slug"]: r for r in lb}
    wl_rows = ""
    for s in wl_slugs:
        r = by_slug.get(s)
        if not r:
            continue
        e = econ.get(s, {})
        cut = next((h["change_pct"] for h in (e.get("price_history") or []) if h.get("change_pct")), None)
        cut_h = f'<span class="rc-up">{cut:+.0f}%</span>' if cut else "&ndash;"
        mv = (r.get("prev_rank") or r["rank"]) - r["rank"]
        mv_h = (f'<span class="rc-up">&#9650; {mv}</span>' if mv > 0 else
                (f'<span class="rc-down">&#9660; {abs(mv)}</span>' if mv < 0 else '<span class="rc-flat">&ndash;</span>'))
        sig = ("Entered top 3" if r["rank"] <= 3 else ("New API tier" if e.get("free_tier") else "Tracked"))
        wl_rows += (f'<tr><td><a href="{BASE}/{esc(s)}">{esc(r["name"])}</a><div class="wl-dev">{esc(r["developer"])}</div></td>'
                    f'<td class="num">{r["rank"]}</td><td class="num">{r["pct"]:.2f}%</td><td>{mv_h}</td>'
                    f'<td class="num">{cut_h}</td><td class="wl-sig">{esc(sig)}</td></tr>')

    alerts = build_alerts(lb, econ, models, as_of)
    alert_rows = "".join(
        f'<a class="alert" href="{BASE}/{esc(slug)}"><span class="al-t al-{t.split()[0].lower()}">{esc(t)}</span>'
        f'<span class="al-x">{esc(msg)}</span></a>' for t, msg, slug in alerts)

    period = as_of[:7]
    month = dt.date.fromisoformat(as_of).strftime("%B %Y")
    next_month = (dt.date.fromisoformat(as_of).replace(day=1) + dt.timedelta(days=32)).replace(day=1)

    nav_items = [("Today", "#", True), ("Live adoption", BASE, False), ("Models", BASE, False),
                 ("Providers", BASE, False), ("Economics", BASE, False),
                 ("Reports", f"{BASE}/reports", False), ("Watchlists", "#", False),
                 ("Data &amp; exports", f"{BASE}/model-adoption-data.json", False),
                 ("Methodology", f"{BASE}#methodology", False)]
    nav_html = "".join(
        f'<a href="{h}" class="pnav-i{" active" if act else ""}">{n}</a>' for n, h, act in nav_items)

    obs = (f'Low-cost {esc(max(share, key=lambda k: share[k]["pct"]))}-built challengers are gaining adoption '
           f'faster than premium US models. Correlation observed, not proof of causation.')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{GA_ID}');</script>
  <meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Model Intelligence Professional | yellow3</title>
  <meta name="description" content="A live intelligence dashboard for AI model adoption, economics and rankings - subscriber briefing, watchlists, alerts and the monthly report. The yellow3 Professional tier." />
  <link rel="canonical" href="{HOST}{BASE}/pro" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <link rel="preconnect" href="https://fonts.googleapis.com" /><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700;800&family=Newsreader:opsz,wght@6..72,400..600&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="{BASE}/pro.css" />
</head>
<body>
  <div class="app">
    <aside class="side">
      <a href="/" class="side-brand"><img src="/logo.png" alt="yellow3" /></a>
      <div class="side-t">Model Intelligence</div>
      <div class="side-tier">Professional</div>
      <nav class="pnav">{nav_html}</nav>
      <div class="side-foot"><div class="side-user">Guest preview</div>
        <a href="#pricing" class="side-manage">See Professional &#8594;</a></div>
    </aside>
    <main class="main">
      <div class="topbar">
        <span class="live"><span class="dot"></span> Live data</span>
        <span class="tb-m">Updated {esc(main["refreshed_cet"])}</span>
        <span class="tb-sep">&middot;</span>
        <span class="tb-m">Next monthly report: {esc(D(next_month.isoformat()))}</span>
        <a class="tb-btn" href="{BASE}/model-adoption-data.json">Download data</a>
      </div>

      <div class="brief">
        <div class="brief-eyebrow">Subscriber briefing &middot; {esc(D(as_of))}</div>
        <h1>The market moved again.</h1>
        <p class="brief-sub">{esc(max(share, key=lambda k: share[k]["pct"]))} extended its lead, US models lost
        share, and a new price cut is beginning to change the economics of the top tier.</p>
      </div>

      <div class="pstats">
        {stat(f'<span class="v-asia">{asia.get("pct",0):.1f}%</span>', "Asia share", dpp(asia.get("delta_pp",0)))}
        {stat(f'<span class="v-us">{us.get("pct",0):.1f}%</span>', "US share", dpp(us.get("delta_pp",0)))}
        {stat(esc(number_one["name"]) if number_one else "&ndash;", "Number one", "routed this week")}
        {stat(esc((biggest or {}).get("value","&ndash;")), "Biggest move", esc((biggest or {}).get("detail","")))}
      </div>
      <p class="brief-obs">{obs}</p>

      <div class="grid2">
        <div class="card feat">
          <div class="card-h">Featured monthly report</div>
          <div class="feat-body">
            <div class="feat-cover">
              <div class="fc-eyebrow">yellow3 &middot; Monthly</div>
              <div class="fc-title">The Model Adoption Report</div>
              <div class="fc-month">{esc(month)}</div>
            </div>
            <div>
              <div class="feat-title">The Model Adoption Report</div>
              <p class="feat-desc">Regional power shifts, model momentum, provider intelligence, the economics
              of the top tier, Europe Watch, and the signals to monitor.</p>
              <a class="feat-cta" href="{BASE}/reports/{period}">Read full report &#8594;</a>
              <div class="feat-note">Included with Professional &middot; commercial internal use permitted</div>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-h">Your watchlist <span class="card-tag">demo</span></div>
          <table class="wl"><thead><tr><th>Model / provider</th><th>Rank</th><th>Share</th><th>7D</th><th>Price</th><th>Signal</th></tr></thead>
          <tbody>{wl_rows}</tbody></table>
        </div>
      </div>

      <div class="grid3">
        <div class="card">
          <div class="card-h">Alerts <span class="card-tag">this week</span></div>
          <div class="alerts">{alert_rows or '<p class="fine">No new alerts this week.</p>'}</div>
        </div>
        <div class="card">
          <div class="card-h">Model economics &middot; adoption vs cost</div>
          {scatter_svg(rows)}
          <div class="leg"><span class="lg lg-asia">Asia</span><span class="lg lg-us">US</span>
          <span class="lg lg-europe">Europe</span><span class="lg lg-other">Other</span></div>
        </div>
        <div class="card">
          <div class="card-h">Archive &amp; data</div>
          <a class="arch-row" href="{BASE}/reports"><b>Report archive</b><span>Every monthly report</span></a>
          <a class="arch-row" href="{BASE}/model-adoption-data.json"><b>Historical data</b><span>Weekly data since May 2026</span></a>
          <a class="arch-row" href="{BASE}"><b>Live dashboard</b><span>The public instrument</span></a>
        </div>
      </div>

      <section class="pricing" id="pricing">
        <div class="pr-h">Professional includes</div>
        <div class="pr-feats">Full monthly report &middot; Live alerts &middot; Model watchlists &middot; Historical data
        &middot; CSV exports &middot; Cost comparisons &middot; Monthly briefing</div>
        <div class="pr-price"><b>&euro;{PRO_LAUNCH}/month</b> early-member price, locked for the first subscribers
        <span>(then &euro;{PRO_MONTH}/mo or &euro;{PRO_YEAR}/yr)</span></div>
        <div class="pr-note">Team &euro;249/mo (5 seats) &middot; Enterprise from &euro;10,000/yr (API, commercial
        licensing, custom datasets, analyst briefings) &middot; Verified media: free with attribution to yellow3.io</div>
      </section>
    </main>
  </div>
{FOOTER}
</body>
</html>'''


PRO_CSS = """*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--paper:#fff;--ink:#0e0e0e;--body:#4b4b4b;--muted:#8a8a8a;--line:#e7e6e2;--yellow:#ffe000;--panel:#f7f6f3;
--up:#2E9D78;--down:#b3402e;--flat:#9a9a95;--asia:#4d146c;--us:#003268;--europe:#c99a12;--other:#828383}
body{background:var(--panel);color:var(--ink);font-family:'DM Sans',system-ui,sans-serif;font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}
a{color:inherit}.num{text-align:right}.fine{font-size:12px;color:var(--muted)}
.rc-up{color:var(--up);font-weight:700}.rc-down{color:var(--down);font-weight:700}.rc-flat{color:var(--flat)}
.app{display:grid;grid-template-columns:236px 1fr;min-height:100vh;background:#fff}
.side{background:#fff;border-right:1px solid var(--line);padding:26px 22px;position:sticky;top:0;height:100vh;display:flex;flex-direction:column}
.side-brand img{height:20px;margin-bottom:22px}
.side-t{font-size:13px;font-weight:800;letter-spacing:-.01em}.side-tier{font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--asia);font-weight:700;margin-bottom:24px}
.pnav{display:flex;flex-direction:column;gap:2px;flex:1}
.pnav-i{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);text-decoration:none;padding:9px 10px;font-weight:600;border-radius:6px}
.pnav-i:hover{background:var(--panel);color:var(--ink)}.pnav-i.active{background:var(--ink);color:#fff}
.side-foot{border-top:1px solid var(--line);padding-top:16px}.side-user{font-size:12px;font-weight:600}.side-manage{font-size:12px;color:var(--muted);text-decoration:none}
.main{padding:0 34px 40px}
.topbar{display:flex;align-items:center;gap:14px;padding:16px 0;border-bottom:1px solid var(--line);flex-wrap:wrap;font-size:12px}
.live{display:inline-flex;align-items:center;gap:7px;font-size:10px;letter-spacing:.14em;text-transform:uppercase;font-weight:700}
.live .dot{width:7px;height:7px;border-radius:50%;background:var(--up)}
.tb-m{color:var(--muted)}.tb-sep{color:var(--line)}.tb-btn{margin-left:auto;font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--line);padding:8px 14px;text-decoration:none;border-radius:6px}
.brief{padding:30px 0 18px}
.brief-eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:700}
.brief h1{font-family:'Newsreader',Georgia,serif;font-size:clamp(32px,4.6vw,52px);font-weight:600;letter-spacing:-.02em;line-height:1.05;margin:8px 0 12px}
.brief-sub{font-size:18px;color:var(--body);max-width:640px}
.pstats{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin:8px 0}
.pstat{background:#fff;padding:20px 22px}.pstat-v{font-size:28px;font-weight:800;letter-spacing:-.02em;line-height:1.05}
.v-asia{color:var(--asia)}.v-us{color:var(--us)}
.pstat-l{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:600;margin-top:8px}.pstat-s{font-size:12px;color:var(--body);margin-top:4px}
.brief-obs{font-size:13px;color:var(--muted);border-left:3px solid var(--yellow);padding:8px 14px;margin:14px 0 24px}
.grid2{display:grid;grid-template-columns:1.15fr 1fr;gap:16px;margin-bottom:16px}
.grid3{display:grid;grid-template-columns:1fr 1.1fr 1fr;gap:16px}
.card{border:1px solid var(--line);padding:20px 22px;background:#fff}
.card-h{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:700;margin-bottom:16px}
.card-tag{color:var(--asia);margin-left:6px}
.feat-body{display:grid;grid-template-columns:150px 1fr;gap:22px}
.feat-cover{background:linear-gradient(160deg,#faf8f2,#efece3);border:1px solid var(--line);padding:18px 16px;display:flex;flex-direction:column;justify-content:space-between;min-height:190px}
.fc-eyebrow{font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:700}
.fc-title{font-family:'Newsreader',serif;font-size:22px;font-weight:600;line-height:1.05;margin-top:10px}
.fc-month{font-size:12px;color:var(--asia);font-weight:700;margin-top:auto}
.feat-title{font-family:'Newsreader',serif;font-size:22px;font-weight:600;margin-bottom:8px}
.feat-desc{font-size:14px;color:var(--body);margin-bottom:16px}
.feat-cta{display:inline-block;background:var(--ink);color:#fff;font-size:12px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;padding:11px 18px;text-decoration:none}
.feat-note{font-size:11px;color:var(--muted);margin-top:12px}
.wl{width:100%;border-collapse:collapse;font-size:13px}
.wl th{text-align:right;font-size:9px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:600;padding:6px 8px;border-bottom:1px solid var(--line)}
.wl th:first-child{text-align:left}.wl td{padding:9px 8px;border-bottom:1px solid #f0efea}.wl td:first-child{text-align:left}
.wl a{color:var(--ink);text-decoration:none;font-weight:600}.wl-dev{font-size:11px;color:var(--muted)}.wl-sig{font-size:12px;color:var(--body)}
.alerts{display:flex;flex-direction:column}
.alert{display:flex;flex-direction:column;gap:3px;padding:11px 0;border-bottom:1px solid #f0efea;text-decoration:none}
.al-t{font-size:9px;letter-spacing:.1em;text-transform:uppercase;font-weight:700;color:var(--muted)}
.al-price{color:var(--asia)}.al-ranking{color:var(--us)}.al-new{color:var(--up)}
.al-x{font-size:13px;color:var(--ink)}
.scatter{width:100%;height:auto}.scatter .sg{stroke:#f0efea}.scatter .sx,.scatter .sy{fill:var(--muted);font-size:9px}
.scatter .sx{text-anchor:middle}.scatter .sy{text-anchor:end}.scatter .sax{fill:var(--muted);font-size:9px;text-anchor:middle}
.sd-asia{fill:var(--asia)}.sd-us{fill:var(--us)}.sd-europe{fill:var(--europe)}.sd-other{fill:var(--other)}
.leg{display:flex;gap:14px;margin-top:10px}.lg{font-size:11px;color:var(--muted);display:inline-flex;align-items:center}
.lg::before{content:"";width:8px;height:8px;border-radius:50%;margin-right:5px}
.lg-asia::before{background:var(--asia)}.lg-us::before{background:var(--us)}.lg-europe::before{background:var(--europe)}.lg-other::before{background:var(--other)}
.arch-row{display:flex;flex-direction:column;gap:2px;padding:12px 0;border-bottom:1px solid #f0efea;text-decoration:none}
.arch-row b{font-size:14px}.arch-row span{font-size:12px;color:var(--muted)}
.pricing{margin-top:22px;border:1px solid var(--ink);padding:26px 28px;background:#fff}
.pr-h{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:700}
.pr-feats{font-size:14px;color:var(--body);margin:10px 0 18px}
.pr-price{font-size:20px;color:var(--ink)}.pr-price b{color:var(--asia)}.pr-price span{font-size:14px;color:var(--muted);font-weight:400}
.pr-note{font-size:12px;color:var(--muted);margin-top:12px}
.site-footer{background:#0e0e0e;color:#fff;padding:56px 34px 30px;grid-column:1/-1}.site-footer .inner{max-width:1240px;margin:0 auto}
.foot-top{display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr 1.2fr;gap:30px;padding-bottom:34px;border-bottom:1px solid #262626}
.foot-brand img{height:20px;filter:invert(1);margin-bottom:12px}.fb-lab{font-size:13px;font-weight:600}.foot-brand p{font-size:13px;color:#8a8a8a}
.foot-col h4,.foot-contact h4{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:#8a8a8a;margin-bottom:14px}
.foot-col a,.foot-contact a{display:block;font-size:14px;color:#d4d4d4;text-decoration:none;margin-bottom:9px}.loc{font-size:14px;color:#8a8a8a}
.foot-bottom{display:flex;justify-content:space-between;padding-top:22px;font-size:12px;color:#8a8a8a;flex-wrap:wrap;gap:12px}.foot-legal a{color:#8a8a8a;text-decoration:none;margin-left:18px}
@media(max-width:1000px){.app{grid-template-columns:1fr}.side{position:static;height:auto;flex-direction:row;flex-wrap:wrap;align-items:center;gap:12px}.pnav{flex-direction:row;flex-wrap:wrap;flex:1 1 100%}.side-foot{display:none}
.grid2,.grid3{grid-template-columns:1fr}.pstats{grid-template-columns:1fr 1fr}.feat-body{grid-template-columns:1fr}}
@media(max-width:560px){.pstats{grid-template-columns:1fr}.main{padding:0 18px 30px}}
"""


def generate():
    main = _load(os.path.join(HERE, "model-adoption-data.json"))
    if not main:
        print("pro: no data, skipping")
        return 0
    econ = _load(os.path.join(DATA_DIR, "economics.json"), {}).get("models", {})
    models = _load(os.path.join(DATA_DIR, "models.json"), {}).get("models", {})
    os.makedirs(PAGES_DIR, exist_ok=True)
    open(os.path.join(PAGES_DIR, "pro.css"), "w").write(PRO_CSS)
    open(os.path.join(PAGES_DIR, "pro.html"), "w").write(render(main, econ, models))
    print("pro: dashboard written -> model-adoption/pro.html")
    return 1


if __name__ == "__main__":
    generate()
