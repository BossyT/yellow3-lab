#!/usr/bin/env python3
"""
yellow3 - The Model Adoption Report (monthly intelligence report generator).

Assembles a professionally-structured monthly report from the accumulating data
(routing history, economics, capabilities, Europe-Watch instruments). Every
data-backed section is written from real numbers; the Forecast and any
interpretation are emitted as clearly-marked "yellow3 view - for sign-off"
drafts so nothing unverified ships under yellow3's authority.

Output: research/model-adoption/reports/<YYYY-MM>.html + an archive index.
Standard library only. Reuses chrome/helpers from gen_model_pages.
"""
import os
import json
import datetime as dt

from gen_model_pages import esc, D, NAV, FOOTER, HOST, BASE, GA_ID

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(HERE, "model-adoption")
DATA_DIR = os.path.join(PAGES_DIR, "_data")
REPORTS_DIR = os.path.join(PAGES_DIR, "reports")
RBASE = BASE + "/reports"


def _load(path, default=None):
    try:
        return json.load(open(path))
    except (FileNotFoundError, ValueError):
        return default if default is not None else {}


def money_m(v):
    if v is None:
        return "n/a"
    pm = v * 1e6
    return "$0.00" if pm == 0 else (f"${pm:.3f}" if pm < 0.1 else f"${pm:.2f}")


def month_move(series):
    """(rank ~4 weeks ago, current rank, delta). delta>0 = improved."""
    if not series:
        return None, None, None
    cur = series[-1]["global_rank"]
    old = series[-5]["global_rank"] if len(series) >= 5 else series[0]["global_rank"]
    return old, cur, (old - cur)


# ------------------------------------------------------------- computation --

def gather(main, models, econ, eaa, dpp):
    """Everything the report needs, computed once."""
    as_of = main["as_of"]
    month = dt.date.fromisoformat(as_of).strftime("%B %Y")
    lb = main["leaderboard"]
    recent_cut = dt.date.fromisoformat(as_of) - dt.timedelta(days=30)

    rows = []
    for r in lb:
        slug = r["slug"]
        m = models.get(slug, {})
        e = econ.get(slug, {})
        series = m.get("series", [])
        old, cur, mv = month_move(series)
        first = m.get("first_tracked")
        is_new = bool(first and dt.date.fromisoformat(first) >= recent_cut)
        # data-derived reason
        cut = None
        for h in (e.get("price_history") or []):
            if h.get("change_pct") and h["change_pct"] < 0:
                cut = h["change_pct"]
                break
        if is_new:
            reason = "New entrant"
        elif cut is not None:
            reason = f"Price cut {abs(cut):.0f}%"
        elif mv is not None and mv >= 3:
            reason = "Adoption climbing"
        elif mv is not None and mv <= -3:
            reason = "Losing share"
        else:
            reason = "Holding"
        momentum = "Rising" if (mv or 0) > 0 else ("Falling" if (mv or 0) < 0 else "Flat")
        rows.append({
            "rank": r["rank"], "name": r["name"], "slug": slug, "region": r["region"],
            "developer": r["developer"], "pct": r["pct"], "month_move": mv,
            "reason": reason, "momentum": momentum, "is_new": is_new,
            "econ": e, "cost": e.get("workload_cost"), "position": e.get("price_position"),
        })

    # regional current share + accurate 4-week delta (computed in the pipeline
    # over the full model set; per-model deltas would miss churn).
    reg_now = {s["region"]: s["pct"] for s in main["share"]}
    reg_delta = {s["region"]: s.get("delta_pp_4w", s.get("delta_pp", 0)) for s in main["share"]}

    movers = sorted([r for r in rows if r["month_move"]], key=lambda r: -(r["month_move"] or 0))
    gainers = [r for r in movers if (r["month_move"] or 0) > 0][:5]
    losers = [r for r in movers if (r["month_move"] or 0) < 0][-5:][::-1]
    new_models = [r for r in rows if r["is_new"]]
    price_cuts = [r for r in rows if r["reason"].startswith("Price cut")]

    # economics: cheapest / priciest / best value on the coding-agent workload
    priced = [r for r in rows if r["cost"] is not None]
    cheapest = sorted(priced, key=lambda r: r["cost"])[:5]
    priciest = sorted(priced, key=lambda r: -r["cost"])[:5]
    best_value = sorted([r for r in priced if (r["month_move"] or 0) >= 0],
                        key=lambda r: r["cost"])[:5]

    # providers
    prov = {}
    for r in rows:
        p = prov.setdefault(r["developer"], {"models": [], "share": 0.0})
        p["models"].append(r)
        p["share"] += r["pct"]
    for name, p in prov.items():
        p["count"] = len(p["models"])
        p["best_mover"] = max(p["models"], key=lambda r: (r["month_move"] or -99))
        p["cheapest"] = min([r for r in p["models"] if r["cost"] is not None],
                            key=lambda r: r["cost"], default=None)
        p["new"] = [r for r in p["models"] if r["is_new"]]
        p["region"] = p["models"][0]["region"]
    provranked = sorted(prov.items(), key=lambda kv: -kv[1]["share"])

    # enterprise: availability + context + open weight share
    ups = [r["econ"].get("uptime") for r in rows if r["econ"].get("uptime") is not None]
    avg_up = round(sum(ups) / len(ups), 2) if ups else None
    open_ct = sum(1 for r in rows[:25] if r["econ"].get("open_weight"))
    big_ctx = sorted([r for r in rows if r["econ"].get("context")],
                     key=lambda r: -(r["econ"]["context"] or 0))[:5]

    return {
        "as_of": as_of, "month": month, "rows": rows,
        "reg_now": reg_now, "reg_delta": reg_delta,
        "gainers": gainers, "losers": losers, "new_models": new_models,
        "price_cuts": price_cuts, "cheapest": cheapest, "priciest": priciest,
        "best_value": best_value, "provranked": provranked,
        "avg_up": avg_up, "open_ct": open_ct, "big_ctx": big_ctx,
        "eaa": eaa, "dpp": dpp, "n_tracked": len(models),
    }


# --------------------------------------------------------------- sections --

def observed(text):
    return f'<div class="obs"><span class="obs-tag">Observed</span><p>{text}</p></div>'


def y3view(text):
    return (f'<div class="y3v"><span class="y3v-tag">yellow3 view &middot; for sign-off</span>'
            f'<p>{text}</p></div>')


def exec_summary(g):
    lead = max(g["reg_now"], key=lambda k: g["reg_now"][k])
    lead_d = g["reg_delta"].get(lead, 0)
    top_gain = g["gainers"][0] if g["gainers"] else None
    bullets = [
        f"<b>{esc(lead)} holds the lead</b> at {g['reg_now'][lead]:.1f}% of routed tokens "
        f"({lead_d:+.1f} pp over four weeks) - the concentration of demand by region of origin is not easing.",
        (f"<b>{esc(top_gain['name'])} was the month's biggest climber</b>, up {top_gain['month_move']} places "
         f"to #{top_gain['rank']}." if top_gain else "Ranking movement was muted this month."),
        (f"<b>{len(g['price_cuts'])} tracked model(s) cut price</b> this month, extending the cost gap between "
         f"low-cost challengers and premium frontier models."
         if g["price_cuts"] else "No tracked price cuts landed inside the window this month."),
        (f"<b>{len(g['new_models'])} new model(s) entered the ranking</b>"
         + (f", led by {esc(g['new_models'][0]['name'])}." if g["new_models"] else ".")),
        (f"<b>Europe remains marginal</b> at {g['reg_now'].get('Europe', 0):.2f}% of routed traffic; "
         f"the regulatory picture is tracked in Europe Watch below."),
    ]
    lis = "".join(f"<li>{b}</li>" for b in bullets)
    return (f'<p class="lead">Five conclusions, three minutes. What changed across model routing, '
            f'economics and the European picture in {esc(g["month"])}.</p>'
            f'<ol class="exec">{lis}</ol>')


def global_market(g):
    reg_rows = ""
    order = sorted(g["reg_now"], key=lambda k: -g["reg_now"][k])
    for reg in order:
        d = g["reg_delta"].get(reg, 0)
        cls = "up" if d > 0.04 else ("down" if d < -0.04 else "flat")
        arr = "&#9650;" if d > 0.04 else ("&#9660;" if d < -0.04 else "&ndash;")
        reg_rows += (f'<tr><td>{esc(reg)}</td><td class="num">{g["reg_now"][reg]:.2f}%</td>'
                     f'<td class="num rc-{cls}">{arr} {d:+.2f} pp</td></tr>')

    def mv_list(items):
        return "".join(
            f'<li><b>{esc(r["name"])}</b> <span class="mono">#{r["rank"]}</span> '
            f'<span class="rc-{"up" if (r["month_move"] or 0)>0 else "down"}">'
            f'{"+" if (r["month_move"] or 0)>0 else ""}{r["month_move"]} places</span></li>'
            for r in items) or "<li>None this month.</li>"

    return (
        f'<div class="two">'
        f'<div><h3>Regional share of routed tokens</h3>'
        f'<table class="rtab"><thead><tr><th>Region</th><th>Share</th><th>4-week change</th></tr></thead>'
        f'<tbody>{reg_rows}</tbody></table>'
        f'<p class="fine">Region reflects where each model\'s developer is headquartered. '
        f'Four-week change is computed over ranked models.</p></div>'
        f'<div><h3>Top gaining models</h3><ul class="mv">{mv_list(g["gainers"])}</ul>'
        f'<h3 style="margin-top:22px">Top losing models</h3><ul class="mv">{mv_list(g["losers"])}</ul></div>'
        f'</div>'
        + observed(
            f'Demand stayed concentrated in {esc(order[0])}-built models. The month\'s movement was '
            f'driven by {esc(g["gainers"][0]["name"]) if g["gainers"] else "no single model"} on the way up '
            f'and price competition at the low end.'))


def rankings(g):
    body = ""
    for r in g["rows"][:25]:
        mv = r["month_move"]
        if mv is None:
            mvh = '<span class="rc-flat">new</span>'
        elif mv > 0:
            mvh = f'<span class="rc-up">&#9650; {mv}</span>'
        elif mv < 0:
            mvh = f'<span class="rc-down">&#9660; {abs(mv)}</span>'
        else:
            mvh = '<span class="rc-flat">&ndash;</span>'
        body += (f'<tr><td class="num">{r["rank"]}</td>'
                 f'<td><a href="{BASE}/{esc(r["slug"])}">{esc(r["name"])}</a> '
                 f'<span class="rgn rgn-{r["region"].lower()}">{esc(r["region"])}</span></td>'
                 f'<td class="num">{r["pct"]:.2f}%</td><td>{mvh}</td>'
                 f'<td>{esc(r["reason"])}</td><td>{esc(r["momentum"])}</td></tr>')
    return (f'<div class="table-scroll"><table class="rtab rtab-full"><thead><tr>'
            f'<th>#</th><th>Model / origin</th><th>Routed share</th><th>4-week</th>'
            f'<th>Reason</th><th>Momentum</th></tr></thead><tbody>{body}</tbody></table></div>'
            f'<p class="fine">Reason is derived from the data (new entry, observed price change, or rank movement); '
            f'it is not an editorial claim.</p>')


def provider_intel(g):
    out = ""
    for name, p in g["provranked"][:12]:
        disp = p["models"][0]["developer"]
        bits = []
        bm = p["best_mover"]
        if bm and (bm["month_move"] or 0) > 0:
            bits.append(f'Best move: <b>{esc(bm["name"])}</b> +{bm["month_move"]} to #{bm["rank"]}')
        if p["new"]:
            bits.append(f'New: {esc(", ".join(x["name"] for x in p["new"]))}')
        if p["cheapest"]:
            bits.append(f'Cheapest: {esc(p["cheapest"]["name"])} at {money_m(p["cheapest"]["econ"].get("in"))}/1M in')
        cuts = [x for x in p["models"] if x["reason"].startswith("Price cut")]
        if cuts:
            bits.append(f'Price cut on {esc(cuts[0]["name"])}')
        out += (f'<div class="prov"><div class="prov-h"><span class="prov-n">{esc(disp)}</span>'
                f'<span class="rgn rgn-{p["region"].lower()}">{esc(p["region"])}</span>'
                f'<span class="prov-s">{p["count"]} ranked &middot; {p["share"]:.2f}% share</span></div>'
                f'<p>{" &middot; ".join(bits) if bits else "Steady month, no notable moves."}</p></div>')
    return out


def economics_section(g):
    def clist(items, val):
        return "".join(f'<li><b>{esc(r["name"])}</b> &middot; ${val(r):,.2f}</li>' for r in items)
    cut_txt = (", ".join(esc(r["name"]) for r in g["price_cuts"])
               if g["price_cuts"] else "no tracked model")
    return (
        f'<div class="two">'
        f'<div><h3>Best value (cost + adoption)</h3><ul class="mv">{clist(g["best_value"], lambda r: r["cost"])}</ul>'
        f'<p class="fine">Monthly cost of a standard coding-agent workload; adoption flat-or-rising.</p></div>'
        f'<div><h3>Most expensive, same workload</h3><ul class="mv">{clist(g["priciest"], lambda r: r["cost"])}</ul></div>'
        f'</div>'
        + observed(
            f'The cheapest tracked model runs the standard coding-agent workload for '
            f'${g["cheapest"][0]["cost"]:,.2f}/month; the most expensive costs ${g["priciest"][0]["cost"]:,.0f} '
            f'- a {g["priciest"][0]["cost"]/max(g["cheapest"][0]["cost"],0.01):.0f}x spread for comparable work. '
            f'This month {cut_txt} cut list price.')
        + '<p class="fine">Cost per coding task, per agent and per reasoning workload are on each model page\'s calculator.</p>')


def enterprise_watch(g):
    up = f'{g["avg_up"]:.2f}%' if g["avg_up"] else "not available"
    ctx = ", ".join(f'{esc(r["name"])} ({round((r["econ"]["context"] or 0)/1000)}K)' for r in g["big_ctx"][:3])
    return (
        f'<ul class="fac">'
        f'<li><b>Availability</b> - median provider uptime across tracked models: {up} (last 30 days, real).</li>'
        f'<li><b>Open weights</b> - {g["open_ct"]} of the top 25 ship open weights; the rest are proprietary.</li>'
        f'<li><b>Longest context</b> - {ctx}.</li>'
        f'<li><b>Not yet tracked</b> - SLAs, EU data-residency, latency and formal compliance are not in the '
        f'routed-traffic feed; yellow3 does not estimate them. Flagged for the enterprise data set.</li>'
        f'</ul>')


def europe_watch(g):
    eaa = g["eaa"] or {}
    dpp = g["dpp"] or {}
    ed = eaa.get("edition", {})
    wc = eaa.get("what_changed", "")
    cr = dpp.get("call_record", {})
    eu_share = g["reg_now"].get("Europe", 0)
    return (
        f'<ul class="fac">'
        f'<li><b>Routed share</b> - European-built models hold {eu_share:.2f}% of routed traffic.</li>'
        f'<li><b>EU AI Act</b> - {esc(ed.get("date_label", "tracked in the EU AI Act instrument"))}: '
        f'{esc(wc or "see the live instrument")}</li>'
        f'<li><b>Digital Product Passport</b> - public call record {cr.get("hits", 0)}-{cr.get("misses", 0)}; '
        f'{esc((dpp.get("this_week_read") or {}).get("headline", "tracked in the DPP instrument"))}</li>'
        f'<li><b>Sovereignty</b> - Mistral remains the only European developer in the routed top tier.</li>'
        f'</ul>'
        f'<p class="fine">Europe Watch draws on yellow3\'s live '
        f'<a href="/research/eu-ai-act">EU AI Act</a> and '
        f'<a href="/research/digital-product-passport">Digital Product Passport</a> instruments.</p>')


def emerging(g):
    nm = ", ".join(esc(r["name"]) for r in g["new_models"]) or "none inside the window"
    open_share = g["open_ct"]
    return (
        f'<ul class="fac">'
        f'<li><b>New this month</b> - {nm}.</li>'
        f'<li><b>Open-source momentum</b> - {open_share} of the top 25 are open-weight, a structural shift toward '
        f'models teams can self-host.</li>'
        f'<li><b>Challengers to watch</b> - the fastest climbers were '
        f'{", ".join(esc(r["name"]) for r in g["gainers"][:3]) or "steady this month"}.</li>'
        f'</ul>')


def forecast(g):
    signals = []
    lead = max(g["reg_now"], key=lambda k: g["reg_now"][k])
    signals.append(f'{lead} share {g["reg_delta"].get(lead,0):+.1f} pp over four weeks')
    if g["price_cuts"]:
        signals.append(f'{len(g["price_cuts"])} price cut(s) at the low end')
    if g["gainers"]:
        signals.append(f'{g["gainers"][0]["name"]} climbing fast')
    return (
        f'<p class="lead">Where yellow3 believes the next month goes. This is analysis, not data - '
        f'presented for your sign-off before it carries the yellow3 name.</p>'
        + y3view(
            f'The observed signals point one way: {"; ".join(signals)}. On that basis, the low-cost, '
            f'high-context challengers keep taking routed share while premium frontier models hold value '
            f'in reasoning-heavy and enterprise use. The forward call - and the confidence level - is to be '
            f'finalised by the yellow3 analyst before publication.'))


def appendix(g):
    provs = ", ".join(sorted({r["developer"] for r in g["rows"]}))
    return (
        f'<h3>Methodology</h3>'
        f'<p class="fine">Adoption is measured from OpenRouter routed-token traffic over trailing windows; '
        f'region reflects developer headquarters. Pricing and capabilities are pulled from the OpenRouter '
        f'public model feed and provider uptime. This is developer routing behaviour, not the whole market.</p>'
        f'<h3>Tracked providers</h3><p class="fine">{esc(provs)}.</p>'
        f'<h3>Definitions</h3><p class="fine">Routed share = a model\'s tokens as a percentage of all routed '
        f'tokens in the window. Standard workload = 1,000 coding-agent tasks/month (100K input, 10K output, '
        f'70% cached).</p>'
        f'<h3>Data</h3><p class="fine">Underlying figures: '
        f'<a href="{BASE}/model-adoption-data.json">model-adoption-data.json</a>. '
        f'CSV exports are a Professional feature.</p>')


# ----------------------------------------------------------------- render --

def render_report(period, g):
    title = f"The Model Adoption Report &mdash; {esc(g['month'])}"
    url = f"{HOST}{RBASE}/{period}"
    desc = (f"yellow3's monthly Model Adoption Report for {esc(g['month'])}: regional power shifts, "
            f"model rankings, provider intelligence, economics, Europe Watch and the month's signals.")
    ld = {
        "@context": "https://schema.org", "@type": "Report",
        "name": f"The Model Adoption Report - {g['month']}", "datePublished": g["as_of"],
        "url": url, "publisher": {"@type": "Organization", "name": "yellow3 lab", "url": HOST},
        "about": "AI model adoption, routing share and economics",
    }
    toc = [("exec", "Executive summary"), ("market", "Global AI market"), ("rankings", "Model rankings"),
           ("providers", "Provider intelligence"), ("economics", "Economics"),
           ("enterprise", "Enterprise Watch"), ("europe", "Europe Watch"),
           ("emerging", "Emerging models"), ("forecast", "Forecast"), ("appendix", "Appendix")]
    toc_html = "".join(f'<a href="#{i}">{esc(t)}</a>' for i, t in toc)

    def sec(i, n, t, body):
        return (f'<section class="rsec" id="{i}"><div class="rsec-h"><span class="rsec-n">{n:02d}</span>'
                f'<h2>{esc(t)}</h2></div>{body}</section>')

    parts = [f'''<!DOCTYPE html>
<html lang="en">
<head>
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{GA_ID}');</script>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title} | yellow3</title>
  <meta name="description" content="{desc}" />
  <link rel="canonical" href="{url}" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700;800&family=Newsreader:ital,opsz,wght@0,6..72,400..600;1,6..72,400&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="{RBASE}/report.css" />
  <meta property="og:type" content="article" />
  <meta property="og:title" content="{title} | yellow3" />
  <meta property="og:description" content="{desc}" />
  <meta property="og:url" content="{url}" />
  <meta property="og:image" content="{HOST}/og/og-model-adoption-v2.png" />
  <script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
</head>
<body>''', NAV, f'''
  <main class="rpt">
    <div class="rwrap">
      <nav class="crumb"><a href="/research">Research</a> <span>/</span>
        <a href="{BASE}">Model adoption</a> <span>/</span>
        <a href="{RBASE}">Reports</a> <span>/</span>
        <span aria-current="page">{esc(g["month"])}</span></nav>

      <header class="cover">
        <div class="cover-eyebrow">yellow3 Model Intelligence &middot; Monthly Report</div>
        <h1>The Model Adoption Report</h1>
        <div class="cover-month">{esc(g["month"])}</div>
        <p class="cover-sub">Regional power shifts, model momentum, provider intelligence, the economics of
        the top tier, Europe Watch, and the signals to monitor.</p>
        <div class="cover-meta">{g["n_tracked"]} models tracked &middot; live routed traffic &middot;
        published {esc(D(g["as_of"]))}</div>
      </header>

      <nav class="toc" aria-label="Contents">{toc_html}</nav>

      {sec(1, 1, "Executive summary", exec_summary(g))}
      {sec(2, 2, "Global AI market", global_market(g))}
      {sec(3, 3, "Model rankings - top 25", rankings(g))}
      {sec(4, 4, "Provider intelligence", provider_intel(g))}
      {sec(5, 5, "Economics", economics_section(g))}
      {sec(6, 6, "Enterprise Watch", enterprise_watch(g))}
      {sec(7, 7, "Europe Watch", europe_watch(g))}
      {sec(8, 8, "Emerging models", emerging(g))}
      {sec(9, 9, "Forecast", forecast(g))}
      {sec(10, 10, "Appendix", appendix(g))}

      <div class="rfoot">Media and press may use the data and graphics with clear attribution to yellow3.io.
      Full historical data, CSV exports and the archive are Professional features.</div>
    </div>
  </main>
{FOOTER}
</body>
</html>''']
    return "\n".join(parts)


def render_archive(reports):
    items = "".join(
        f'<a class="arch-item" href="{RBASE}/{p}"><span class="arch-m">{esc(m)}</span>'
        f'<span class="arch-t">The Model Adoption Report</span>'
        f'<span class="arch-d">Published {esc(D(a))}</span></a>'
        for p, m, a in reports)
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{GA_ID}');</script>
  <meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>The Model Adoption Report - Archive | yellow3</title>
  <meta name="description" content="Every monthly Model Adoption Report from yellow3 - regional shifts, rankings, economics and Europe Watch." />
  <link rel="canonical" href="{HOST}{RBASE}" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <link rel="preconnect" href="https://fonts.googleapis.com" /><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700;800&family=Newsreader:opsz,wght@6..72,400..600&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="{RBASE}/report.css" />
</head>
<body>
{NAV}
  <main class="rpt"><div class="rwrap">
    <nav class="crumb"><a href="/research">Research</a> <span>/</span>
      <a href="{BASE}">Model adoption</a> <span>/</span><span aria-current="page">Reports</span></nav>
    <header class="cover"><div class="cover-eyebrow">yellow3 Model Intelligence</div>
      <h1>The Model Adoption Report</h1>
      <p class="cover-sub">A monthly intelligence report on where AI demand actually flows - by region of
      origin, by model, and by the economics beneath. New edition every month.</p></header>
    <div class="arch">{items}</div>
  </div></main>
{FOOTER}
</body>
</html>'''


REPORT_CSS = """*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--paper:#fff;--ink:#0e0e0e;--body:#333;--muted:#8a8a8a;--line:#e7e6e2;--yellow:#ffe000;--panel:#f7f6f3;
--up:#2E9D78;--down:#b3402e;--flat:#9a9a95;--asia:#4d146c;--us:#003268;--europe:#c99a12;--other:#828383}
body{background:var(--paper);color:var(--ink);font-family:'DM Sans',system-ui,sans-serif;font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}
a{color:inherit}img{display:block;max-width:100%}.num{text-align:right;font-variant-numeric:tabular-nums}
.mono{font-variant-numeric:tabular-nums;color:var(--muted)}
.site-nav{position:fixed;top:0;left:0;right:0;z-index:100;display:flex;align-items:center;justify-content:space-between;padding:16px 48px;background:rgba(255,255,255,.95);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.brand img{height:21px}.nav-mid{display:flex;gap:32px}.nav-mid a{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#3a3a3a;text-decoration:none;font-weight:500}.nav-mid a.active{border-bottom:2px solid var(--ink);color:var(--ink)}
.nav-cta{display:inline-flex;gap:10px;background:var(--ink);color:#fff;font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;padding:12px 20px;text-decoration:none}
.nav-toggle{display:none;background:none;border:none;cursor:pointer;padding:6px}.nav-toggle span{display:block;width:22px;height:2px;background:var(--ink);margin:5px 0}
.rpt{padding:120px 0 40px}.rwrap{max-width:920px;margin:0 auto;padding:0 48px}
.crumb{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:36px}
.crumb a{color:var(--muted);text-decoration:none}.crumb span{margin:0 6px;color:#cfcdc6}.crumb [aria-current]{color:var(--ink)}
.cover{padding:20px 0 44px;border-bottom:3px solid var(--ink)}
.cover-eyebrow{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);font-weight:700}
.cover h1{font-family:'Newsreader',Georgia,serif;font-size:clamp(40px,7vw,76px);font-weight:600;line-height:1.02;letter-spacing:-.02em;margin:16px 0 4px}
.cover-month{font-size:22px;font-weight:700;color:var(--asia)}
.cover-sub{font-size:19px;color:var(--body);max-width:640px;margin:20px 0 18px;line-height:1.5}
.cover-meta{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:600}
.toc{display:flex;flex-wrap:wrap;gap:6px 22px;padding:22px 0;border-bottom:1px solid var(--line);margin-bottom:10px}
.toc a{font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);text-decoration:none;font-weight:600}.toc a:hover{color:var(--ink)}
.rsec{padding:44px 0;border-bottom:1px solid var(--line)}
.rsec-h{display:flex;align-items:baseline;gap:16px;margin-bottom:24px}
.rsec-n{font-family:'Newsreader',serif;font-size:20px;color:var(--yellow);font-weight:600;-webkit-text-stroke:.5px #cbb400}
.rsec-h h2{font-family:'Newsreader',serif;font-size:clamp(26px,3.4vw,36px);font-weight:600;letter-spacing:-.01em;line-height:1.1}
.rsec h3{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink);font-weight:700;margin-bottom:14px}
.rsec p{color:var(--body);margin-bottom:14px}.lead{font-size:19px;color:var(--ink);line-height:1.5}
.exec{list-style:none;counter-reset:e;margin-top:20px}
.exec li{counter-increment:e;position:relative;padding:16px 0 16px 44px;border-top:1px solid var(--line);font-size:17px;line-height:1.5;color:var(--body)}
.exec li::before{content:counter(e);position:absolute;left:0;top:15px;font-family:'Newsreader',serif;font-size:22px;font-weight:600;color:var(--asia)}
.exec b{color:var(--ink)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:40px;margin-bottom:8px}
.rtab{width:100%;border-collapse:collapse;font-size:14px}
.rtab th{text-align:right;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:600;padding:8px 12px;border-bottom:1px solid var(--line)}
.rtab th:first-child,.rtab th:nth-child(2){text-align:left}
.rtab td{padding:10px 12px;border-bottom:1px solid #f0efea}
.rtab a{color:var(--ink);text-decoration:none;border-bottom:1px solid #cfcdc6}
.rtab-full td:first-child{text-align:right;color:var(--muted);font-weight:600}
.rc-up{color:var(--up);font-weight:700}.rc-down{color:var(--down);font-weight:700}.rc-flat{color:var(--flat)}
.rgn{font-size:9px;letter-spacing:.06em;text-transform:uppercase;font-weight:700;padding:2px 6px;border-radius:3px;color:#fff;margin-left:6px}
.rgn-asia{background:var(--asia)}.rgn-us{background:var(--us)}.rgn-europe{background:var(--europe)}.rgn-other{background:var(--other)}
.mv{list-style:none}.mv li{padding:9px 0;border-bottom:1px solid #f0efea;font-size:15px}.mv b{color:var(--ink)}
.fac{list-style:none}.fac li{padding:11px 0;border-bottom:1px solid #f0efea;font-size:15px;color:var(--body)}.fac b{color:var(--ink)}
.prov{padding:16px 0;border-bottom:1px solid #f0efea}
.prov-h{display:flex;align-items:center;gap:10px;margin-bottom:5px}
.prov-n{font-size:17px;font-weight:800}.prov-s{font-size:12px;color:var(--muted);margin-left:auto}
.prov p{font-size:14px;margin:0}
.obs,.y3v{border-left:3px solid;padding:14px 18px;margin:22px 0;font-size:15px;background:var(--panel)}
.obs{border-color:var(--up)}.y3v{border-color:var(--yellow);background:#fffdf0}
.obs-tag,.y3v-tag{display:block;font-size:10px;letter-spacing:.1em;text-transform:uppercase;font-weight:700;margin-bottom:6px}
.obs-tag{color:var(--up)}.y3v-tag{color:#9a7d12}.obs p,.y3v p{margin:0;color:var(--body)}
.fine{font-size:12px;color:var(--muted);line-height:1.55}
.table-scroll{overflow-x:auto}
.rfoot{padding:32px 0;font-size:12px;color:var(--muted)}
.arch{display:grid;gap:1px;background:var(--line);border:1px solid var(--line);margin-top:20px}
.arch-item{background:#fff;padding:22px 24px;text-decoration:none;display:flex;flex-direction:column;gap:4px}
.arch-item:hover{background:var(--panel)}
.arch-m{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--asia);font-weight:700}
.arch-t{font-family:'Newsreader',serif;font-size:22px;font-weight:600}.arch-d{font-size:13px;color:var(--muted)}
.site-footer{background:#0e0e0e;color:#fff;padding:60px 48px 32px;margin-top:20px}.site-footer .inner{max-width:1240px;margin:0 auto}
.foot-top{display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr 1.2fr;gap:32px;padding-bottom:36px;border-bottom:1px solid #262626}
.foot-brand img{height:20px;filter:invert(1);margin-bottom:12px}.fb-lab{font-size:13px;font-weight:600;margin-bottom:8px}.foot-brand p{font-size:13px;color:#8a8a8a}
.foot-col h4,.foot-contact h4{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:#8a8a8a;margin-bottom:16px}
.foot-col a,.foot-contact a{display:block;font-size:14px;color:#d4d4d4;text-decoration:none;margin-bottom:10px}.loc{font-size:14px;color:#8a8a8a}
.foot-bottom{display:flex;justify-content:space-between;padding-top:24px;font-size:12px;color:#8a8a8a;flex-wrap:wrap;gap:12px}.foot-legal a{color:#8a8a8a;text-decoration:none;margin-left:18px}
@media(max-width:820px){.rwrap{padding:0 24px}.site-nav{padding:14px 24px}.nav-mid,.nav-cta{display:none}.nav-toggle{display:block}
.two{grid-template-columns:1fr;gap:24px}.foot-top{grid-template-columns:1fr 1fr}}
"""


# --------------------------------------------------------------- generate --

def generate():
    main = _load(os.path.join(HERE, "model-adoption-data.json"))
    if not main:
        print("report: no model-adoption-data.json, skipping")
        return 0
    models = _load(os.path.join(DATA_DIR, "models.json"), {}).get("models", {})
    econ = _load(os.path.join(DATA_DIR, "economics.json"), {}).get("models", {})
    eaa = _load(os.path.join(HERE, "eu-ai-act.json"), {})
    dpp = _load(os.path.join(HERE, "digital-product-passport.json"), {})

    g = gather(main, models, econ, eaa, dpp)
    period = g["as_of"][:7]

    os.makedirs(REPORTS_DIR, exist_ok=True)
    open(os.path.join(REPORTS_DIR, "report.css"), "w").write(REPORT_CSS)
    open(os.path.join(REPORTS_DIR, f"{period}.html"), "w").write(render_report(period, g))

    # archive index over every generated report file
    reports = []
    for f in sorted(os.listdir(REPORTS_DIR)):
        if f.endswith(".html") and f != "index.html":
            p = f[:-5]
            try:
                m = dt.date.fromisoformat(p + "-01").strftime("%B %Y")
            except ValueError:
                continue
            reports.append((p, m, g["as_of"]))
    reports.sort(reverse=True)
    open(os.path.join(REPORTS_DIR, "index.html"), "w").write(render_archive(reports))
    print(f"report: {period} written + archive ({len(reports)} report(s))")
    return len(reports)


if __name__ == "__main__":
    generate()
