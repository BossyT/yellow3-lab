#!/usr/bin/env python3
"""
DPP Supplier Register - static site generator.

  register CSV  ->  research/dpp-suppliers.json  ->  HTML

Writes, all under the single DPP url:

  research/digital-product-passport/suppliers.html      the directory
  research/digital-product-passport/<id>.html           one card per organisation

Design rules this generator enforces, because they are the product:

  * white = verified by yellow3, pale yellow = supplied by the company. The two
    layers are never blended.
  * absence is a dated finding, never an empty cell. "Not yet assessed" carries
    NO date (nobody has looked); "not found" carries one (somebody looked).
  * every verified fact links its source.
  * no scores, no ranking, no badge that could read as an endorsement.
  * `notes` are written for us, not for readers - they are never published.

Zero dependencies, Python stdlib only, same as the other research generators.

  python3 research/gen_dpp_suppliers.py --csv ~/Documents/yellow3/dpp-directory/dpp-supplier-register-v2.csv
  python3 research/gen_dpp_suppliers.py            # regenerate from the committed JSON
"""

import csv, json, os, argparse, html, datetime, re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "dpp-suppliers.json")
OUTDIR = os.path.join(HERE, "digital-product-passport")

PUBLIC_FIELDS = [
    "id", "name", "website", "domain", "alias_domains", "hq_country", "hq_city", "country_source",
    "entity_type", "sectors", "founded_year", "ownership", "funding_stage",
    "total_disclosed_funding", "last_funding_date", "funding_source", "status",
    "evidence_url", "source", "source_date", "confidence",
]

NON_COMMERCIAL = {"project-consortium", "standards-body", "not-a-supplier"}

TYPE_LABEL = {
    "platform": "Platform",
    "middleware": "Middleware",
    "identity-carrier": "Identity carrier",
    "erp-pim-plm": "ERP / PIM / PLM",
    "consultancy": "Consultancy",
    "standards-body": "Standards body",
    "project-consortium": "Project / consortium",
    "not-a-supplier": "Not a supplier",
}

NON_COMMERCIAL_NOTE = {
    "project-consortium": "EU-funded or industry project &middot; not a commercial supplier",
    "standards-body": "Standards body &middot; not a commercial supplier",
    "not-a-supplier": "Not a commercial DPP supplier &middot; retained for transparency",
}

# The ten checks. Order is the published order.
CRITERIA = [
    ("Standards mapping", "A field-by-field mapping to the JTC 24 standards, not a logo on a website."),
    ("Evidence architecture", "Claims, documentation and third-party verification held apart, not merged behind a checkmark."),
    ("Identity portability", "Existing GTINs preserved, GS1 Digital Link supported, a resolver that survives changing vendor."),
    ("Model / batch / item", "Real granularity in the data model today, not on a roadmap slide."),
    ("Clean export", "Full data export in a standard format, in writing."),
    ("Regulatory pace", "Concrete examples of absorbing the most recent delegated acts, with dates."),
    ("EU DPP Registry", "A passport registered in the EU registry, live since 20 July 2026."),
    ("Passport afterlife", "What happens to passports already in the wild if the vendor fails."),
    ("Role-based disclosure", "Distinct views for consumers, repairers, recyclers, customs and market surveillance."),
    ("Resolver uptime", "Availability published as measured history, not promised in a contract."),
]

# Region rule, reusing the Model Intelligence palette rather than inventing a second one.
REGION_COLOR = {"europe": "#c1972b", "asia": "#5b2b4d", "us": "#223a5e", "other": "#565a60"}
EUROPE = {"Austria","Belgium","Croatia","Czech Republic","Denmark","Estonia","Finland","France",
          "Germany","Greece","Hungary","Iceland","Ireland","Italy","Latvia","Lithuania","Luxembourg",
          "Malta","Netherlands","Norway","Poland","Portugal","Romania","San Marino","Slovakia",
          "Slovenia","Spain","Sweden","Switzerland","Turkey","United Kingdom","Bulgaria","Cyprus"}
ASIA = {"China","India","Indonesia","Japan","Malaysia","Singapore","South Korea","Taiwan","Thailand","Vietnam"}


def region_of(country):
    if not country:
        return "other"
    if country in EUROPE:
        return "europe"
    if country in ASIA:
        return "asia"
    if country in ("USA", "United States"):
        return "us"
    return "other"


def fact_count(r):
    """Facts we recorded WITH a source. Not a score - a count of what is on the record."""
    n = 0
    for f in ("website", "hq_country", "hq_city", "founded_year", "ownership", "sectors"):
        if (r.get(f) or "").strip():
            n += 1
    if (r.get("total_disclosed_funding") or "").strip():
        n += 1
    if (r.get("funding_stage") or "").strip():
        n += 1
    return n


SECTOR_LABEL = {
    "textiles": "Textiles", "electronics": "Electronics", "batteries": "Batteries",
    "construction": "Construction", "tyres": "Tyres", "furniture": "Furniture",
    "food": "Food", "chemicals": "Chemicals", "automotive": "Automotive",
    "cosmetics": "Cosmetics", "general": "General",
}


def e(s):
    return html.escape(str(s or ""), quote=True)


def g(row, field):
    return (row.get(field) or "").strip()


def initials(name):
    """BeoPass -> BP, Blue Room Innovation -> BR, osapiens -> OS.

    CamelCase counts as a word break, because these names are usually two words
    the founder shoved together.
    """
    clean = re.sub(r"^\(unnamed\)\s*", "", name).strip()
    words = [w for w in re.split(r"[\s\-\._/]+", re.sub(r"[^\w\s\-\._/]", "", clean)) if w]
    if not words:
        return "??"
    if len(words) == 1:
        parts = re.findall(r"[A-Z][a-z0-9]*|[a-z0-9]+", words[0])
        if len(parts) > 1:
            return (parts[0][0] + parts[1][0]).upper()
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def pretty_date(iso):
    """2026-07-28 -> 28 Jul 2026"""
    try:
        return datetime.date.fromisoformat(iso).strftime("%-d %b %Y")
    except Exception:
        return iso


def source_state(value):
    """A source cell is either a URL, a dated not_found, or nothing at all.

    Returns (kind, url, date) where kind is 'url' | 'not_found' | 'none'.
    The distinction between not_found and none is the whole point: one means we
    looked, the other means we have not got there yet.
    """
    v = (value or "").strip()
    if v.startswith("http"):
        return "url", v, ""
    if v.lower().startswith("not_found"):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", v)
        return "not_found", "", pretty_date(m.group(1)) if m else ""
    return "none", "", ""


# ---------------------------------------------------------------- data

def build_json(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    out = []
    for r in rows:
        rec = {f: g(r, f) for f in PUBLIC_FIELDS}
        rec["sectors_list"] = [s.strip() for s in rec["sectors"].split(",") if s.strip()]
        out.append(rec)
    counts = headline(out)
    payload = {
        "register": "DPP Supplier Register",
        "generated": datetime.date.today().isoformat(),
        "schema": "v1.3",
        "counts": counts,
        "suppliers": out,
    }
    with open(DATA, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    return payload


def headline(rows):
    commercial = [r for r in rows if r["entity_type"] not in NON_COMMERCIAL]
    countries = sorted({r["hq_country"] for r in rows if r["hq_country"]})
    primary = sorted({r["hq_country"] for r in rows
                      if r["hq_country"] and r["country_source"].startswith("http")})
    return {
        "organisations": len(rows),
        "commercial_suppliers": len(commercial),
        "countries": len(countries),
        "countries_primary_sourced": len(primary),
        "verified": sum(1 for r in rows if r["confidence"] == "verified"),
        "with_disclosed_funding": sum(1 for r in rows if r["total_disclosed_funding"]),
    }


# ---------------------------------------------------------------- shell

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
    <a href="/advisory" class="nav-cta">Work with us <span>&#8594;</span></a>
    <button class="nav-toggle" aria-label="Menu" onclick="this.classList.toggle('open');document.getElementById('navMid').classList.toggle('open')"><span></span><span></span><span></span></button>
  </nav>
"""

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
          <a href="/research/framework">The method</a>
          <a href="/research/model-adoption">Model adoption</a>
        </div>
        <div class="foot-col">
          <h4>Company</h4>
          <a href="/about">About</a>
          <a href="/insights/">Thinking</a>
          <a href="/advisory">Contact</a>
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
        </div>
      </div>
    </div>
  </footer>
"""

CSS = """
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --paper:#ffffff; --ink:#0e0e0e; --body:#4b4b4b; --muted:#8a8a8a; --mid:#8a8a8a;
      --line:#e7e6e2; --yellow:#ffe000; --panel:#f7f6f3; --company:#fdf8e3; --companyline:#f0dfa0;
      --green:#2E9D78; --amber:#D89A16; --red:#b3402e;
    }
    html { scroll-behavior: smooth; }
    body { background: var(--paper); color: var(--ink); font-family: 'DM Sans', system-ui, sans-serif; line-height: 1.6; font-size: 16px; -webkit-font-smoothing: antialiased; }
    img { display:block; max-width:100%; }
    a { color: inherit; }
    .wrap { max-width: 1080px; margin: 0 auto; padding: 0 48px; }
    .inner { max-width: 1240px; margin: 0 auto; }

    .site-nav { position: fixed; top:0; left:0; right:0; z-index:100; display:flex; align-items:center; justify-content:space-between; padding:16px 48px; background:rgba(255,255,255,0.95); backdrop-filter:blur(8px); border-bottom:1px solid var(--line); }
    .brand img { height:21px; }
    .nav-mid { display:flex; gap:32px; }
    .nav-mid a { font-size:12px; letter-spacing:0.06em; text-transform:uppercase; color:#3a3a3a; text-decoration:none; font-weight:500; padding-bottom:3px; }
    .nav-mid a.active { border-bottom:2px solid var(--ink); color:var(--ink); }
    .nav-cta { display:inline-flex; align-items:center; gap:10px; background:var(--ink); color:#fff; font-size:11px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; padding:12px 20px; text-decoration:none; }
    .nav-toggle { display:none; background:none; border:none; cursor:pointer; padding:6px; }
    .nav-toggle span { display:block; width:22px; height:2px; background:var(--ink); margin:5px 0; }

    /* register bar */
    .reg-head { padding: 128px 0 0; }
    .reg-bar { display:flex; align-items:baseline; gap:26px; flex-wrap:wrap; padding-bottom:18px; border-bottom:1px solid var(--line); }
    .reg-title { font-size:15px; font-weight:700; letter-spacing:-0.01em; }
    .reg-title span { color:var(--muted); font-weight:500; }
    .reg-counts { display:flex; gap:22px; flex-wrap:wrap; }
    .reg-count { font-size:13px; color:var(--mid); }
    .reg-count b { display:inline-block; min-width:34px; padding:2px 8px; margin-right:7px; border:1px solid var(--line); font-weight:700; color:var(--ink); text-align:center; }
    .reg-nav { margin-left:auto; display:flex; gap:26px; }
    .reg-nav a { font-size:13px; color:var(--body); text-decoration:none; }
    .reg-nav a:hover { color:var(--ink); }
    .crumb { font-size:11px; letter-spacing:0.16em; text-transform:uppercase; color:var(--muted); font-weight:600; padding:22px 0 0; }
    .crumb a { color:var(--muted); text-decoration:none; }
    .crumb a:hover { color:var(--ink); }

    /* card */
    .card-outer { border:1px solid var(--line); margin:22px 0 40px; }
    .card-id { display:grid; grid-template-columns:auto 1fr auto; gap:28px; padding:34px 36px; border-bottom:1px solid var(--line); align-items:start; }
    .mark { width:104px; height:104px; border:1px solid var(--line); display:flex; align-items:center; justify-content:center; font-size:30px; font-weight:600; letter-spacing:0.02em; color:var(--ink); }
    .mark img { width:100%; height:100%; object-fit:contain; padding:14px; }
    .id-name { display:flex; align-items:center; gap:14px; flex-wrap:wrap; margin-bottom:12px; }
    .id-name h1 { font-family:Georgia,'Times New Roman',serif; font-size:clamp(32px,4.4vw,46px); font-weight:400; letter-spacing:-0.02em; line-height:1.05; }
    .tag { font-size:10px; letter-spacing:0.14em; text-transform:uppercase; font-weight:600; border:1px solid var(--line); padding:6px 11px; color:var(--body); white-space:nowrap; }
    /* non-commercial entities are marked in graphite, never in the company yellow -
       pale yellow means one thing only on this site: supplied by the company. */
    .tag.nc { border-color:#c9c9c9; background:#f0efec; color:var(--muted); }
    .id-line { font-size:14px; color:var(--body); margin-bottom:6px; }
    .id-line .k { color:var(--muted); }
    .id-line a { color:var(--ink); }
    .id-sub { font-size:13px; color:var(--muted); margin:-2px 0 10px; }
    .id-line.hq .dated { font-size:12px; }

    /* footnote marker + hover provenance record */
    .fnm { font-size:10px; color:var(--muted); vertical-align:super; line-height:0; margin-left:1px; }
    .fn { position:relative; display:inline-flex; align-items:center; cursor:default; outline:none; vertical-align:middle; margin-left:4px; }
    .fni { width:15px; height:15px; border:1px solid var(--line); border-radius:50%; font-size:9px;
           line-height:13px; text-align:center; color:var(--muted); font-style:italic; }
    .fn:hover .fni, .fn:focus .fni { border-color:var(--ink); color:var(--ink); }
    .pv { position:absolute; left:26px; top:-10px; z-index:20; width:262px; background:#fff;
          border:1px solid var(--line); box-shadow:0 8px 26px rgba(0,0,0,.10); padding:16px 18px;
          display:none; flex-direction:column; text-align:left; }
    .fn:hover .pv, .fn:focus .pv { display:flex; }
    .pv b { font-size:13px; font-weight:600; color:var(--ink); margin-bottom:5px; }
    .pv-f { font-size:12px; color:var(--body); padding-bottom:12px; border-bottom:1px solid var(--line); }
    .pv-d { font-size:12px; color:var(--body); padding:12px 0; border-bottom:1px solid var(--line); }
    .pv-l { padding-top:12px; }
    .pv-l a { font-size:12px; color:var(--ink); text-decoration:none; border-bottom:1px solid var(--line); }
    .pv-l a:hover { border-bottom-color:var(--ink); }
    @media (max-width:880px) { .pv { left:auto; right:0; top:24px; width:236px; } }

    .rail { writing-mode:vertical-rl; font-size:10px; letter-spacing:0.2em; text-transform:uppercase; color:var(--muted); font-weight:600; }

    .layer { padding:32px 36px; }
    .layer-h { font-size:12px; letter-spacing:0.18em; text-transform:uppercase; font-weight:700; color:var(--ink); margin-bottom:26px; padding-top:14px; border-top:3px solid var(--yellow); display:inline-block; }
    .layer.company { background:var(--company); border-top:1px solid var(--companyline); }

    .sub-h { font-size:11px; letter-spacing:0.16em; text-transform:uppercase; color:var(--muted); font-weight:600; margin-bottom:16px; }
    .glance { display:grid; grid-template-columns:repeat(5,1fr); border-top:1px solid var(--line); }
    /* every divider needs a gutter on BOTH sides or the rule sits on the text */
    .gl { padding:20px 26px; border-right:1px solid var(--line); }
    .gl:first-child { padding-left:0; }
    .gl:last-child { border-right:none; padding-right:0; }
    .gl .k { font-size:12px; font-weight:600; color:var(--ink); margin-bottom:7px; }
    .gl .v { font-size:13px; color:var(--body); line-height:1.45; }
    .gl .v.none { color:var(--muted); }
    .gl .v a { color:var(--body); }

    .crit-note { font-size:13px; color:var(--mid); margin-bottom:20px; }
    .crit-empty { font-size:14px; color:var(--body); line-height:1.6; max-width:640px; }
    .crit-empty em { font-style:normal; color:var(--muted); display:block; margin-top:4px; }
    .crit { display:grid; grid-template-columns:26px 1fr auto; gap:14px; align-items:baseline; padding:13px 0; border-top:1px solid var(--line); }
    .crit .n { font-size:12px; color:var(--muted); }
    .crit .l { font-size:14px; }
    .crit .s { font-size:11px; letter-spacing:0.1em; text-transform:uppercase; font-weight:600; color:var(--muted); }
    .crit .s.cs-na { color:#aeaeae; }
    /* verified and not-found sit at the same visual weight on purpose: a found
       result is not a prize, a not-found is not a penalty. Both are findings. */
    .crit .s.cs-v { color:#1C7A5A; }
    .crit .s.cs-c { color:#9C6B0C; }
    .crit .s.cs-n { color:var(--mid); }
    .crit .s .cdate { color:var(--muted); font-weight:400; letter-spacing:0; text-transform:none; margin-left:10px; font-size:11px; }
    .crit .s .src { margin-left:8px; font-weight:400; letter-spacing:0; text-transform:none; }
    .crit-foot { font-size:12px; color:var(--muted); padding-top:14px; border-top:1px solid var(--line); margin-top:2px; }
    .crit-foot a { color:var(--muted); }

    .sup-empty { font-size:14px; color:var(--body); }
    .btn-link { display:inline-block; margin-top:12px; font-size:13px; font-weight:600; color:var(--ink); text-decoration:none; border-bottom:1px solid var(--ink); padding-bottom:2px; }

    .evid { display:flex; flex-wrap:nowrap; align-items:stretch; gap:0; border-top:1px solid var(--line); background:var(--panel); }
    .evid .cell { padding:18px 20px; border-right:1px solid var(--line); min-width:0; flex:0 1 auto; }
    .evid .cell .v { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .evid .cell:last-child { border-right:none; }
    .evid .cell.lab { background:transparent; }
    .evid .cell.lab .k { margin-bottom:0; }
    .evid .cell.act { display:flex; align-items:center; }
    .evid .cell.act { white-space:nowrap; }
    .evid .cell.act a { font-size:13px; color:var(--body); text-decoration:none; border-bottom:1px solid var(--line); }
    .evid .cell.act a:hover { color:var(--ink); border-bottom-color:var(--ink); }
    .evid .k { font-size:10px; letter-spacing:0.14em; text-transform:uppercase; color:var(--muted); font-weight:700; margin-bottom:6px; }
    .evid .v { font-size:13px; color:var(--body); }
    .evid a { color:var(--body); }

    .src { font-size:11px; color:var(--muted); text-decoration:none; border-bottom:1px dotted var(--muted); }
    .src:hover { color:var(--ink); border-bottom-color:var(--ink); }
    .dated { font-size:12px; color:var(--muted); }

    /* directory */
    .dir-intro { padding:30px 0 22px; }
    .dir-intro h1 { font-size:clamp(30px,4vw,42px); font-weight:800; letter-spacing:-0.03em; line-height:1.05; margin-bottom:10px; }
    .dir-sub { font-size:16px; color:var(--body); }
    .filters { display:flex; gap:12px; flex-wrap:wrap; padding:8px 0 14px; align-items:center; }
    .filters select, .filters input { font-family:inherit; font-size:13px; padding:11px 13px; border:1px solid var(--line); background:#fff; color:var(--ink); }
    .filters input { min-width:260px; flex:1 1 260px; }
    .filters select { flex:0 0 auto; }
    .fcount { font-size:13px; color:var(--muted); padding-bottom:10px; }
    table.dir { width:100%; border-collapse:collapse; }
    table.dir th { text-align:left; font-size:10px; letter-spacing:0.14em; text-transform:uppercase; color:var(--muted); font-weight:700; padding:14px 14px 12px 0; border-bottom:1px solid var(--line); }
    table.dir td { padding:16px 14px 16px 0; border-bottom:1px solid var(--line); font-size:14px; vertical-align:middle; }
    table.dir th.bar, table.dir td.bar { width:4px; padding:0; border-bottom:none; }
    table.dir tr.nc td { background:#fafaf8; color:var(--mid); }
    table.dir td.nm { padding-left:16px; }
    .nmw { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
    .avatar { width:38px; height:38px; border:1px solid var(--line); display:inline-flex; align-items:center; justify-content:center; font-size:13px; font-weight:600; color:var(--ink); flex:none; }
    table.dir td.nm a { font-size:17px; font-weight:600; text-decoration:none; letter-spacing:-0.01em; }
    table.dir td.nm a:hover { border-bottom:1px solid var(--ink); }
    .ext { font-size:12px; color:var(--muted); text-decoration:none; }
    .ext:hover { color:var(--ink); }
    .nctag { display:block; font-size:9px; letter-spacing:0.12em; text-transform:uppercase; color:var(--muted); font-weight:700; border:1px solid var(--line); padding:4px 7px; margin-bottom:9px; width:max-content; }
    .pill { font-size:10px; letter-spacing:0.08em; text-transform:uppercase; color:var(--body); border:1px solid var(--line); padding:4px 9px; white-space:nowrap; display:inline-block; margin:2px 4px 2px 0; }
    .evsub { font-size:12px; color:var(--muted); margin-top:3px; }
    .dt { color:var(--mid); white-space:nowrap; }
    .muted { color:var(--muted); }
    table.dir sup { font-size:9px; color:var(--muted); }

    /* legend - metadata, explicitly not a ranking */
    .legend { display:grid; grid-template-columns:repeat(3,1fr); gap:32px; padding:34px 0 10px; border-top:1px solid var(--line); margin-top:6px; }
    .lg-k { font-size:12px; font-weight:600; color:var(--ink); margin-bottom:10px; }
    .lg-k span { color:var(--muted); font-weight:400; }
    .lg-r { font-size:13px; color:var(--body); display:flex; align-items:center; gap:9px; margin-bottom:6px; }
    .lg-r i { width:16px; height:3px; flex:none; }
    .legend .note { grid-column:1 / -1; font-size:13px; color:var(--muted); padding-top:8px; }

    .claim-wrap { padding:36px 0 70px; max-width:760px; }
    .claim-wrap h1 { font-size:clamp(30px,4vw,44px); font-weight:800; letter-spacing:-0.03em; line-height:1.05; margin-bottom:16px; }
    .claim-lead { font-size:17px; color:var(--body); line-height:1.6; border-left:3px solid var(--yellow); padding-left:22px; margin-bottom:32px; }
    .claim-form { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:14px; }
    .claim-form input { font-family:inherit; font-size:15px; padding:15px 16px; border:1px solid var(--line); min-width:320px; flex:1 1 320px; color:var(--ink); }
    .claim-form input:focus { outline:none; border-color:var(--ink); }
    .btn { display:inline-flex; align-items:center; gap:12px; padding:15px 26px; font-size:12px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; text-decoration:none; border:1px solid var(--ink); cursor:pointer; font-family:inherit; }
    .btn-dark { background:var(--ink); color:#fff; }
    .btn-dark:hover { background:#000; }
    .claim-msg { font-size:14px; color:var(--body); line-height:1.6; background:var(--panel); border:1px solid var(--line); padding:16px 18px; margin-bottom:30px; }
    .claim-cols { display:grid; grid-template-columns:repeat(3,1fr); gap:30px; padding-top:34px; border-top:1px solid var(--line); }
    .claim-cols h3 { font-size:14px; font-weight:700; margin-bottom:9px; }
    .claim-cols p { font-size:14px; color:var(--body); line-height:1.6; }
    @media (max-width:880px) { .claim-cols { grid-template-columns:1fr; gap:22px; } .claim-form input { min-width:100%; } }

    .method { padding:52px 0 64px; border-top:1px solid var(--line); }
    .method h2 { font-size:22px; font-weight:800; letter-spacing:-0.02em; margin-bottom:14px; }
    .method p { font-size:15px; color:var(--body); max-width:720px; margin-bottom:14px; }
    .method .states { display:grid; grid-template-columns:repeat(3,1fr); gap:1px; background:var(--line); border:1px solid var(--line); margin:22px 0; }
    .method .st { background:#fff; padding:20px 22px; }
    .method .st b { display:block; font-size:13px; margin-bottom:6px; }
    .method .st span { font-size:13px; color:var(--body); }

    .site-footer { background:#0e0e0e; color:#fff; padding:72px 48px 36px; margin-top:20px; }
    .foot-top { display:grid; grid-template-columns:1.4fr repeat(3,1fr) 1.2fr; gap:40px; padding-bottom:56px; border-bottom:1px solid #262626; }
    .foot-brand img { height:22px; filter:invert(1); margin-bottom:18px; }
    .foot-brand .fb-lab { font-size:11px; letter-spacing:0.16em; text-transform:uppercase; color:rgba(255,255,255,0.5); font-weight:600; margin-bottom:10px; }
    .foot-brand p { font-size:14px; color:rgba(255,255,255,0.55); max-width:220px; }
    .foot-col h4, .foot-contact h4 { font-size:10px; letter-spacing:0.16em; text-transform:uppercase; color:rgba(255,255,255,0.4); font-weight:600; margin-bottom:18px; }
    .foot-col a { display:block; font-size:14px; color:rgba(255,255,255,0.72); text-decoration:none; margin-bottom:11px; }
    .foot-col a:hover { color:#fff; }
    .foot-contact a.mail { font-size:14px; color:#fff; text-decoration:none; display:block; margin-bottom:10px; }
    .foot-contact .loc { font-size:14px; color:rgba(255,255,255,0.55); }
    .foot-bottom { display:flex; align-items:center; justify-content:space-between; padding-top:28px; flex-wrap:wrap; gap:16px; }
    .foot-bottom .copy { font-size:12px; color:rgba(255,255,255,0.4); }
    .foot-legal { display:flex; gap:24px; }
    .foot-legal a { font-size:12px; text-transform:uppercase; color:rgba(255,255,255,0.4); text-decoration:none; }

    @media (max-width: 980px) {
      .glance { grid-template-columns:repeat(2,1fr); }
      .gl { border-right:none; border-bottom:1px solid var(--line); padding-left:0; padding-right:0; }
    }
    @media (max-width: 880px) {
      .site-nav { padding:14px 24px; }
      .nav-mid { display:none; position:absolute; top:100%; left:0; right:0; background:#fff; border-bottom:1px solid var(--line); flex-direction:column; gap:0; padding:12px 24px 20px; }
      .nav-mid.open { display:flex; }
      .nav-cta { display:none; }
      .nav-toggle { display:block; }
      .wrap { padding:0 24px; }
      .reg-head { padding-top:104px; }
      .card-id { grid-template-columns:1fr; gap:18px; padding:26px 22px; }
      .rail { display:none; }
      .layer { padding:26px 22px; }
      .glance { grid-template-columns:1fr; }
      .evid { flex-wrap:wrap; }
      .evid .cell { border-right:none; border-bottom:1px solid var(--line); width:100%; }
      .method .states { grid-template-columns:1fr; }
      .foot-top { grid-template-columns:1fr 1fr; gap:32px; }
      .site-footer { padding:56px 24px 32px; }
      table.dir .hide-s, table.dir .hide-m { display:none; }
      .legend { grid-template-columns:1fr; gap:22px; }
      .filters input, .filters select { flex:1 1 100%; }
    }
    @media (max-width: 560px) { .foot-top { grid-template-columns:1fr; } }
"""


def jsonld(obj):
    return ('<script type="application/ld+json">'
            + json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
            + "</script>")


def profile_jsonld(r):
    """A page ABOUT an organisation, not markup claiming to speak for one.

    Only fields we actually verified go in. An unsourced country is not published
    here any more than it is published on the page.
    """
    org = {"@type": "Organization", "name": r["name"]}
    if r["website"]:
        org["url"] = r["website"]
    if r["hq_country"] and r["country_source"].startswith("http"):
        addr = {"@type": "PostalAddress", "addressCountry": r["hq_country"]}
        if r["hq_city"]:
            addr["addressLocality"] = r["hq_city"]
        org["address"] = addr
    if r["founded_year"]:
        org["foundingDate"] = r["founded_year"]
    return jsonld({
        "@context": "https://schema.org",
        "@type": "ProfilePage",
        "name": f"{r['name']} - DPP Supplier Register",
        "url": f"https://yellow3.io/research/digital-product-passport/{r['id']}",
        "dateModified": datetime.date.today().isoformat(),
        "isPartOf": {
            "@type": "Dataset",
            "name": "yellow3 DPP Supplier Register",
            "url": "https://yellow3.io/research/digital-product-passport/suppliers",
        },
        "about": org,
        "publisher": {"@type": "Organization", "name": "yellow3 lab",
                      "url": "https://yellow3.io"},
    })


def directory_jsonld(counts):
    return jsonld({
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": "yellow3 DPP Supplier Register",
        "description": (f"{counts['organisations']} organisations supplying Digital Product Passport "
                        f"capability, of which {counts['commercial_suppliers']} commercial suppliers "
                        f"across {counts['countries']} countries. Every fact carries the source it came "
                        f"from and the date it was checked."),
        "url": "https://yellow3.io/research/digital-product-passport/suppliers",
        "dateModified": datetime.date.today().isoformat(),
        "creator": {"@type": "Organization", "name": "yellow3 lab", "url": "https://yellow3.io"},
        "isAccessibleForFree": True,
        "keywords": ["Digital Product Passport", "DPP", "ESPR", "product traceability",
                     "supplier register", "EU regulation"],
    })


def page(title, desc, canonical, body, extra_js="", head_extra=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-K3JXMM2VG5"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-K3JXMM2VG5');</script>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{e(title)}</title>
  <meta name="description" content="{e(desc)}" />
  <link rel="canonical" href="{e(canonical)}" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <meta property="og:title" content="{e(title)}" />
  <meta property="og:description" content="{e(desc)}" />
  <meta property="og:url" content="{e(canonical)}" />
  <meta property="og:type" content="website" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet" />
  {head_extra}
  <style>{CSS}</style>
</head>
<body>
{NAV}
{body}
{FOOTER}
{extra_js}
</body>
</html>
"""


def reg_bar(counts, link=True):
    t = ('<a href="/research/digital-product-passport/suppliers" style="text-decoration:none">'
         if link else '<span>')
    tc = "</a>" if link else "</span>"
    return f"""    <div class="reg-bar">
      <div class="reg-title">{t}yellow3 lab <span>&middot; DPP Supplier Register</span>{tc}</div>
      <div class="reg-counts">
        <span class="reg-count"><b>{counts['organisations']}</b>organisations</span>
        <span class="reg-count"><b>{counts['commercial_suppliers']}</b>commercial suppliers</span>
        <span class="reg-count"><b>{counts['countries']}</b>countries</span>
      </div>
      <div class="reg-nav">
        <a href="/research/digital-product-passport/suppliers#top">Search</a>
        <a href="/research/digital-product-passport/suppliers#method">Method</a>
      </div>
    </div>
"""


# ---------------------------------------------------------------- capability

CAP_STATE = {
    # state -> (label, css class). Verified and not-found are deliberately close in
    # weight: a found result is not a prize and a not-found is not a penalty. Both
    # are findings.
    "verified":       ("Verified", "cs-v"),
    "company_states": ("Company states", "cs-c"),
    "not_found":      ("Not found", "cs-n"),
}


def load_capability():
    """Per-supplier capability results, keyed id -> check_id -> record.

    Absent file, or a supplier absent from it, means NOT YET ASSESSED - which is a
    different thing from not found, and must never be rendered as one.
    """
    path = os.path.join(HERE, "dpp-capability.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    out = {}
    for row in data.get("results", []):
        out.setdefault(row["supplier_id"], {})[row["check_id"]] = row
    return out


def capability_block(r, cap):
    """The ten checks, or one honest sentence if nobody has looked yet."""
    if r["entity_type"] in NON_COMMERCIAL:
        return ""

    results = cap.get(r["id"])
    head = ('<div class="sub-h" style="margin-top:38px">Capability evidence</div>'
            '<div class="crit-note">Ten independent checks. No composite score.</div>')

    if not results:
        return head + (
            '<div class="crit-empty">Not yet assessed for this supplier.'
            '<em>Assessments are published as they are completed.</em></div>'
            '<a class="btn-link" href="/research/digital-product-passport/suppliers#method">'
            'View assessment framework &#8599;</a>')

    rows = []
    for i, (name, question) in enumerate(CRITERIA, 1):
        cid = f"c{i:02d}"
        rec = results.get(cid)
        if not rec:
            label, cls, right = "Not yet assessed", "cs-na", ""
        else:
            label, cls = CAP_STATE.get(rec["state"], ("Not yet assessed", "cs-na"))
            when = pretty_date(rec.get("checked_date", ""))
            src = rec.get("evidence_url", "")
            link = (f' <a class="src" href="{e(src)}" target="_blank" rel="noopener" '
                    f'title="{e(rec.get("artifact",""))}">evidence</a>') if src else ""
            right = f'<span class="cdate">{e(when)}</span>{link}'
        rows.append(
            f'<div class="crit"><span class="n">{i}</span>'
            f'<span class="l" title="{e(question)}">{e(name)}</span>'
            f'<span class="s {cls}">{e(label)}{right}</span></div>')

    assessed = sum(1 for v in results.values() if v.get("state"))
    foot = (f'<div class="crit-foot">{assessed} of 10 checked &middot; '
            f'each check independent, each with its own evidence and date. '
            f'<a href="/research/digital-product-passport/suppliers#method">How we verify &#8599;</a></div>')
    return head + "".join(rows) + foot


# ---------------------------------------------------------------- card

def glance_cell(label, value, source, checked_note=True):
    """One at-a-glance tile. Absence is a finding, never an empty cell."""
    kind, url, date = source_state(source)
    if value:
        if kind == "url":
            return (f'<div class="gl"><div class="k">{label}</div>'
                    f'<div class="v">{value} &middot; <a class="src" href="{e(url)}" target="_blank" rel="noopener">source</a></div></div>')
        return f'<div class="gl"><div class="k">{label}</div><div class="v">{value}</div></div>'
    if kind == "not_found" and checked_note:
        return (f'<div class="gl"><div class="k">{label}</div>'
                f'<div class="v none">No public disclosure found<br><span class="dated">checked {e(date)}</span></div></div>')
    return f'<div class="gl"><div class="k">{label}</div><div class="v none">Not yet assessed</div></div>'


def card_html(r, counts, cap):
    name = r["name"]
    nc = r["entity_type"] in NON_COMMERCIAL
    kind, curl, cdate = source_state(r["country_source"])

    today = pretty_date(datetime.date.today().isoformat())
    checked = cdate or today

    def marker(n):
        return f'<sup class="fnm">{n}</sup>'

    def prov(title, finding, when, url):
        """The hover provenance record, anchored at the end of the line."""
        link = (f'<a href="{e(url)}" target="_blank" rel="noopener">View search record &#8599;</a>'
                if url else
                '<a href="/research/digital-product-passport/suppliers#method">How we verify &#8599;</a>')
        return (f'<span class="fn" tabindex="0" role="button" aria-label="{e(title)}">'
                f'<span class="fni">i</span>'
                f'<span class="pv"><b>{e(title)}</b><span class="pv-f">{e(finding)}</span>'
                f'<span class="pv-d">Checked {e(when)}</span><span class="pv-l">{link}</span></span></span>')

    # website line, with its own checked date beneath
    if r["website"]:
        site = (f'<a href="{e(r["website"])}" target="_blank" rel="noopener">'
                f'{e(r["domain"] or r["website"])}</a> &#8599;{marker(1)}')
        site_finding = "Official company website confirmed"
        site_url = r["website"]
    elif kind == "not_found":
        site = f'No official website established{marker(1)}'
        site_finding = "No official website found"
        site_url = ""
    else:
        site = '<span class="muted">Not yet assessed</span>'
        site_finding = site_url = ""
    site_prov = prov("Website check", site_finding, checked, site_url) if site_finding else ""

    # headquarters line
    if r["hq_country"]:
        place = ", ".join([x for x in (r["hq_city"], r["hq_country"]) if x])
        hq = e(place) + marker(2)
        hq_finding = ("Confirmed from a primary source" if kind == "url"
                      else "Stated by the company")
    elif kind == "not_found":
        hq = f'Not publicly established{marker(2)}'
        hq_finding = "No public country source found"
    else:
        hq = '<span class="muted">Not yet assessed</span>'
        hq_finding = ""
    hq_prov = prov("Country check", hq_finding, checked, curl) if hq_finding else ""

    tag = f'<span class="tag{" nc" if nc else ""}">{TYPE_LABEL.get(r["entity_type"], r["entity_type"])}</span>'
    ncline = (f'<div class="id-line" style="color:var(--body)">{NON_COMMERCIAL_NOTE[r["entity_type"]]}</div>'
              if nc else "")

    glance = "".join([
        glance_cell("Sectors",
                    ", ".join(SECTOR_LABEL.get(s, s.title()) for s in r["sectors_list"]),
                    "" if r["sectors_list"] else r["country_source"], checked_note=False),
        glance_cell("Founded", e(r["founded_year"]), ""),
        glance_cell("Ownership", e(r["ownership"]), ""),
        glance_cell("Funding stage", e(r["funding_stage"].replace("-", " ")), ""),
        glance_cell("Disclosed funding", e(r["total_disclosed_funding"]), r["funding_source"]),
    ])

    capability = capability_block(r, cap)

    company = "" if nc else f"""
    <div class="layer company">
      <div class="layer-h">Supplied by {e(name)}</div>
      <div class="sup-empty">No company-supplied profile received.</div>
      <a class="btn-link" href="/research/digital-product-passport/claim?s={e(r['id'])}">Claim this profile &#8599;</a>
    </div>
"""

    _k, _u, _d = source_state(r["country_source"])
    last_checked = _d or pretty_date(datetime.date.today().isoformat())

    src_cell = (f'<a href="{e(r["evidence_url"])}" target="_blank" rel="noopener">{e(r["source"])}</a> &#8599;'
                if r["evidence_url"] else e(r["source"]) or '<span class="muted">Not recorded</span>')

    body = f"""
  <div class="wrap reg-head">
{reg_bar(counts)}
    <div class="crumb"><a href="/research/digital-product-passport/suppliers">&#8249; All suppliers</a></div>

    <div class="card-outer">
      <div class="card-id">
        <div class="mark">{e(initials(name))}</div>
        <div>
          <div class="id-name"><h1>{e(name)}</h1>{tag}</div>
          {ncline}
          <div class="id-line">{site} {site_prov}</div>
          <div class="id-sub">checked {e(checked)}</div>
          <div class="id-line hq"><span class="k">Headquarters</span> &middot; {hq}
            <span class="dated">&middot; checked {e(checked)}</span> {hq_prov}</div>
        </div>
        <div class="rail">Supplier profile</div>
      </div>

      <div class="layer">
        <div class="layer-h">Verified by yellow3</div>
        <div class="sub-h">At a glance</div>
        <div class="glance">{glance}</div>
{capability}
      </div>
{company}
      <div class="evid">
        <div class="cell lab"><div class="k">Register evidence</div></div>
        <div class="cell"><div class="k">Source</div><div class="v">{src_cell}</div></div>
        <div class="cell"><div class="k">First recorded</div><div class="v">{e(pretty_date(r["source_date"]))}</div></div>
        <div class="cell"><div class="k">Last checked</div><div class="v">{e(last_checked)}</div></div>
        <div class="cell act"><a href="/research/digital-product-passport/suppliers#method">Research method &#8599;</a></div>
        <div class="cell act"><a href="/research/digital-product-passport/suppliers#corrections">Suggest a correction &#8599;</a></div>
        <div class="cell act"><a href="/research/digital-product-passport/claim?s={e(r['id'])}">Claim this profile &#8599;</a></div>
      </div>
    </div>

    <p style="font-size:13px;color:var(--muted);max-width:680px;margin-bottom:44px">
      This profile records what yellow3 could verify from public sources on the dates shown.
      Absence of a fact is a statement about our research, not about the company.
      Corrections with a source are welcome and are logged.
    </p>
  </div>
"""
    desc = (f"{name} - Digital Product Passport supplier profile. "
            f"Sourced identity, headquarters and evidence, recorded by yellow3 lab.")
    return page(f"{name} - DPP Supplier Register - yellow3",
                desc,
                f"https://yellow3.io/research/digital-product-passport/{r['id']}",
                body, head_extra=profile_jsonld(r))


# ---------------------------------------------------------------- directory

def directory_html(rows, counts, cap):
    countries = sorted({r["hq_country"] for r in rows if r["hq_country"]})
    sectors = sorted({s for r in rows for s in r["sectors_list"]})
    types = sorted({r["entity_type"] for r in rows})

    trs = []
    for r in sorted(rows, key=lambda x: x["name"].lower()):
        nc = r["entity_type"] in NON_COMMERCIAL
        kind, curl, cdate = source_state(r["country_source"])
        reg = region_of(r["hq_country"])
        checked = cdate or pretty_date(datetime.date.today().isoformat())
        results = cap.get(r["id"]) or {}
        findings = sum(1 for v in results.values() if v.get("state"))
        facts = fact_count(r)

        # HQ, with the footnote where nothing was found
        if r["hq_country"]:
            hq = e(", ".join([x for x in (r["hq_city"], r["hq_country"]) if x]))
        elif kind == "not_found":
            hq = 'Not publicly established<sup>1</sup>'
        else:
            hq = '<span class="muted">Not yet assessed</span>'

        secs = " ".join(f'<span class="pill">{e(SECTOR_LABEL.get(x, x.title()))}</span>'
                        for x in r["sectors_list"][:2]) or 'No public sector focus found<sup>2</sup>'

        # evidence cell
        if nc:
            ev = ('Research project &middot; not available<br>for procurement'
                  if r["entity_type"] == "project-consortium" else
                  'Not a commercial supplier')
            evsub = ""
        else:
            cf = (f'{findings} capability findings' if findings
                  else 'capability research pending')
            ev = f'{facts} fact{"" if facts == 1 else "s"} &middot; {cf}'
            evsub = f'<div class="evsub">{e(r["confidence"])}</div>'

        mark = (f'<span class="avatar">{e(initials(r["name"]))}</span>')
        nclabel = '<span class="nctag">Non-supplier entity</span>' if nc else ''
        site = (f'<a class="ext" href="{e(r["website"])}" target="_blank" rel="noopener" '
                f'aria-label="{e(r["name"])} website">&#8599;</a>') if r["website"] else ''

        trs.append(
            f'<tr class="{"nc" if nc else ""}" data-country="{e(r["hq_country"])}" '
            f'data-sectors="{e(",".join(r["sectors_list"]))}" data-type="{e(r["entity_type"])}" '
            f'data-cap="{"assessed" if findings else "pending"}" '
            f'data-name="{e(r["name"].lower())}">'
            f'<td class="bar" style="background:{REGION_COLOR[reg]}"></td>'
            f'<td class="nm">{nclabel}<div class="nmw">{mark}'
            f'<a href="/research/digital-product-passport/{e(r["id"])}">{e(r["name"])}</a>{site}</div></td>'
            f'<td><span class="pill">{e(TYPE_LABEL.get(r["entity_type"], r["entity_type"]))}</span></td>'
            f'<td class="hide-s">{hq}</td>'
            f'<td class="hide-s">{secs}</td>'
            f'<td class="hide-m">{ev}{evsub}</td>'
            f'<td class="hide-s dt">{e(checked)}</td>'
            f'</tr>')

    opts = lambda vals, lab: "".join(f'<option value="{e(v)}">{e(lab(v))}</option>' for v in vals)

    body = f"""
  <div class="wrap reg-head" id="top">
{reg_bar(counts, link=False)}
    <div class="dir-intro">
      <h1>Supplier directory</h1>
      <p class="dir-sub">Evidence-led profiles of the Digital Product Passport market.</p>
    </div>

    <div class="filters">
      <input id="q" type="search" placeholder="Search {counts['organisations']} suppliers" aria-label="Search suppliers" />
      <select id="fc"><option value="">Country</option>{opts(countries, lambda v: v)}</select>
      <select id="fs"><option value="">Sector</option>{opts(sectors, lambda v: SECTOR_LABEL.get(v, v.title()))}</select>
      <select id="ft"><option value="">Entity type</option>{opts(types, lambda v: TYPE_LABEL.get(v, v))}</select>
      <select id="fe"><option value="">Capability evidence</option><option value="assessed">Assessed</option><option value="pending">Research pending</option></select>
    </div>
    <div class="fcount" id="fcount"></div>

    <table class="dir">
      <thead><tr>
        <th class="bar"></th><th>Supplier</th><th>Type</th><th class="hide-s">HQ</th>
        <th class="hide-s">Sectors</th><th class="hide-m">Evidence</th><th class="hide-s">Last checked</th>
      </tr></thead>
      <tbody id="rows">
{chr(10).join(trs)}
      </tbody>
    </table>

    <div class="legend">
      <div class="lg">
        <div class="lg-k">Region rule <span>(metadata)</span></div>
        <div class="lg-r"><i style="background:{REGION_COLOR['europe']}"></i>Europe (ochre)</div>
        <div class="lg-r"><i style="background:{REGION_COLOR['asia']}"></i>Asia (aubergine)</div>
        <div class="lg-r"><i style="background:{REGION_COLOR['us']}"></i>US (navy)</div>
        <div class="lg-r"><i style="background:{REGION_COLOR['other']}"></i>Other (graphite)</div>
      </div>
      <div class="lg">
        <div class="lg-k">Evidence basis <span>(metadata)</span></div>
        <div class="lg-r">verified &nbsp;/&nbsp; claimed &nbsp;/&nbsp; unverified</div>
        <div class="lg-k" style="margin-top:18px">Capability states <span>(metadata)</span></div>
        <div class="lg-r">verified &nbsp;/&nbsp; company states &nbsp;/&nbsp; not found</div>
      </div>
      <div class="lg">
        <div class="lg-k">Footnotes</div>
        <div class="lg-r"><sup>1</sup> No public country source found.</div>
        <div class="lg-r"><sup>2</sup> No sector focus statement identified.</div>
        <div class="lg-r">&#8599; External link icon indicates the supplier website.</div>
      </div>
      <div class="lg note">These are metadata, not rankings. Nothing here is scored, weighted or ordered by merit.</div>
    </div>

    <div class="method" id="method">
      <h2>How we verify</h2>
      <p>Every value in this register is backed by a page we opened, or it is left blank. A blank
      is not an oversight, it is a finding: it means the fact is not published anywhere we could
      reach on the date shown. Nothing here is inferred from a company name, a domain ending or a
      legal-form suffix.</p>
      <div class="states">
        <div class="st"><b>Verified</b><span>A legal document or register entry names the
          organisation - an imprint, legal notice, terms carrying a registered office, or a
          national business register.</span></div>
        <div class="st"><b>Claimed</b><span>The company states it about itself, and we link where.
          Recorded accurately, not endorsed.</span></div>
        <div class="st"><b>Not found</b><span>We looked on the date shown and the fact was not
          published. Dated, so you can see how fresh the check is.</span></div>
      </div>
      <p>Capability assessments run against ten independent checks, each with its own evidence and
      its own date. There is no composite score and no ranking. A supplier that has not been
      assessed says so; it is never shown as failing a check nobody ran.</p>
      <h2 id="corrections" style="margin-top:34px">Corrections</h2>
      <p>If something here is wrong, send the correction with a source and we will check it, fix it
      and log the change. Corrections are welcome from anyone, and we do not need you to be the
      company to send one.</p>
      <h2 id="claim" style="margin-top:34px">Claiming a profile</h2>
      <p>If you work at one of these organisations you can claim your profile and supply your own
      logo, description and answers. Company-supplied content is shown in its own layer, marked as
      yours, and never overwrites what we verified independently.</p>
      <p style="color:var(--muted);font-size:13px">Register generated {e(pretty_date(datetime.date.today().isoformat()))}
      &middot; {counts['verified']} profiles with a primary-sourced identity
      &middot; {counts['countries_primary_sourced']} countries with a primary-sourced headquarters.</p>
    </div>
  </div>
"""
    js = """
<script>
(function(){
  var ids=['q','fc','fs','ft','fe'], el={};
  ids.forEach(function(i){el[i]=document.getElementById(i);});
  var rows=[].slice.call(document.querySelectorAll('#rows tr')), out=document.getElementById('fcount');
  function apply(){
    var t=(el.q.value||'').toLowerCase(),n=0;
    rows.forEach(function(r){
      var ok=(!t||r.dataset.name.indexOf(t)>-1)
        &&(!el.fc.value||r.dataset.country===el.fc.value)
        &&(!el.fs.value||(','+r.dataset.sectors+',').indexOf(','+el.fs.value+',')>-1)
        &&(!el.ft.value||r.dataset.type===el.ft.value)
        &&(!el.fe.value||r.dataset.cap===el.fe.value);
      r.style.display=ok?'':'none'; if(ok)n++;
    });
    out.textContent=n+(n===rows.length?' profiles':' of '+rows.length+' profiles');
  }
  ids.forEach(function(i){el[i].addEventListener('input',apply);});
  apply();
})();
</script>
"""
    return page("Supplier directory - DPP Supplier Register - yellow3",
                "Evidence-led profiles of the Digital Product Passport market. Every organisation "
                "supplying DPP capability, with the source behind each fact and the date it was checked.",
                "https://yellow3.io/research/digital-product-passport/suppliers",
                body, js, head_extra=directory_jsonld(counts))


def claim_html(counts):
    body = """
  <div class="wrap reg-head">
""" + reg_bar(counts) + """
    <div class="crumb"><a href="/research/digital-product-passport/suppliers">&#8249; All suppliers</a></div>

    <div class="claim-wrap">
      <h1>Claim <span id="cname">your profile</span></h1>
      <p class="claim-lead">Enter your work email. If it is at the domain on record for this
      company, the claim is confirmed straight away - no account, no waiting for approval.</p>

      <form id="cf" class="claim-form" novalidate>
        <input id="cemail" type="email" required placeholder="you@yourcompany.com"
               aria-label="Work email" autocomplete="email" />
        <button class="btn btn-dark" type="submit">Claim this profile <span class="arr">&#8594;</span></button>
      </form>
      <div id="cmsg" class="claim-msg" hidden></div>

      <div class="claim-cols">
        <div>
          <h3>What you can supply</h3>
          <p>A logo, a one-line description, a contact link, and your answers to the ten
          capability checks. It appears in its own layer on your profile, marked as coming
          from you, and dated.</p>
        </div>
        <div>
          <h3>What stays ours</h3>
          <p>Everything we verified independently, with the source and the date we checked it.
          Company-supplied content never overwrites it. If something we published is wrong,
          send the correction with a source and we will fix it and log the change.</p>
        </div>
        <div>
          <h3>Why a work email</h3>
          <p>The register is keyed on company domains, so an address at the company domain is
          proof enough. Personal mailboxes are not accepted, which is what keeps anyone from
          claiming a company they do not work for.</p>
        </div>
      </div>
    </div>
  </div>
"""
    js = """
<script>
(function(){
  var reg = null, id = new URLSearchParams(location.search).get('s') || '';
  var msg = document.getElementById('cmsg');
  fetch('/research/dpp-suppliers.json').then(function(r){return r.json();}).then(function(d){
    reg = (d.suppliers||[]).filter(function(x){return x.id===id;})[0];
    if (reg) {
      document.getElementById('cname').textContent = reg.name;
      document.title = 'Claim ' + reg.name + ' - DPP Supplier Register - yellow3';
    }
  }).catch(function(){});

  document.getElementById('cf').addEventListener('submit', function(ev){
    ev.preventDefault();
    var email = document.getElementById('cemail').value.trim();
    if (!email) return;
    msg.hidden = false;
    msg.textContent = 'Checking\u2026';
    fetch('/api/claim', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ email: email, supplier: id })
    }).then(function(){
      msg.innerHTML = '<b>Check your inbox.</b> If that address is at the domain on record '
        + 'for this company, a confirmation is on its way. If it is not, nothing was sent - '
        + 'write to us and we will sort it out.';
    }).catch(function(){
      msg.textContent = 'Something went wrong. Please try again.';
    });
  });
})();
</script>
"""
    return page("Claim a profile - DPP Supplier Register - yellow3",
                "Claim your organisation's profile on the yellow3 DPP Supplier Register. "
                "Verified by work email domain, no account required.",
                "https://yellow3.io/research/digital-product-passport/claim",
                body, js)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="register CSV to publish from (rebuilds dpp-suppliers.json)")
    args = ap.parse_args()

    if args.csv:
        payload = build_json(os.path.expanduser(args.csv))
        print(f"wrote {os.path.relpath(DATA, HERE)} from {os.path.basename(args.csv)}")
    else:
        with open(DATA, encoding="utf-8") as fh:
            payload = json.load(fh)

    rows, counts = payload["suppliers"], payload["counts"]
    cap = load_capability()
    os.makedirs(OUTDIR, exist_ok=True)

    with open(os.path.join(OUTDIR, "suppliers.html"), "w", encoding="utf-8") as fh:
        fh.write(directory_html(rows, counts, cap))

    with open(os.path.join(OUTDIR, "claim.html"), "w", encoding="utf-8") as fh:
        fh.write(claim_html(counts))

    for r in rows:
        with open(os.path.join(OUTDIR, f"{r['id']}.html"), "w", encoding="utf-8") as fh:
            fh.write(card_html(r, counts, cap))

    print(f"wrote suppliers.html + {len(rows)} profiles into research/digital-product-passport/")
    print(f"  {counts['organisations']} organisations, {counts['commercial_suppliers']} commercial "
          f"suppliers, {counts['countries']} countries "
          f"({counts['countries_primary_sourced']} primary-sourced), {counts['verified']} verified")


if __name__ == "__main__":
    main()
