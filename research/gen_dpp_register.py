#!/usr/bin/env python3
"""
DPP Supplier Register - complete system, ported from the supplied handoff.

The handoff (Next.js 16 / React 19) is the binding design reference. yellow3.io
is static HTML, so each view is ported to the same DOM, class names, copy and
interaction model - not reinterpreted.

  app/page.tsx              -> the map-led catalogue, top of /suppliers
  app/directory/page.tsx    -> the directory, same page
  app/supplier/<id>         -> /suppliers/<id>
  app/claim/<id>            -> /suppliers/<id>/claim
  app/globals.css           -> register.css, byte-identical minus the tailwind
                               import (nothing in it uses @apply)

Production routes:

  /research/digital-product-passport/suppliers
  /research/digital-product-passport/suppliers/<id>
  /research/digital-product-passport/suppliers/<id>/claim

Data comes from the live register (research/dpp-suppliers.json) and the live
capability findings (research/dpp-capability.json) through a field adapter. The
demonstration records in the handoff are presentation fixtures and are NOT used.

The layer separation is structural, not stylistic: independently researched
yellow3 evidence and company-supplied statements are held in separate data and
separate DOM, and a company submission can never write into the evidence layer.
"""

import json, os, re, html, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "digital-product-passport", "suppliers")
DATA = os.path.join(HERE, "dpp-suppliers.json")
CAP = os.path.join(HERE, "dpp-capability.json")
GEO = "/research/dpp-map-geometry.json"
VERCEL = os.path.join(ROOT, "vercel.json")

NON_COMMERCIAL = {"project-consortium", "standards-body", "not-a-supplier"}

TYPE_LABEL = {
    "platform": "Platform", "middleware": "Middleware",
    "identity-carrier": "Identity carrier", "erp-pim-plm": "ERP · PIM · PLM",
    "consultancy": "Consultancy", "standards-body": "Standards body",
    "project-consortium": "Project consortium", "not-a-supplier": "Not a supplier",
}

SECTOR_LABEL = {
    "textiles": "Textiles", "electronics": "Electronics", "batteries": "Batteries",
    "construction": "Construction", "tyres": "Tyres", "furniture": "Furniture",
    "food": "Food", "chemicals": "Chemicals", "automotive": "Automotive",
    "cosmetics": "Cosmetics", "general": "General",
}

CRITERIA = ["Standards mapping", "Evidence architecture", "Identity portability",
            "Model / batch / item", "Clean export", "Regulatory pace",
            "EU DPP Registry", "Passport afterlife", "Role-based disclosure",
            "Resolver uptime"]

EUROPE = {"Austria","Belgium","Croatia","Czech Republic","Denmark","Estonia","Finland","France",
          "Germany","Greece","Hungary","Iceland","Ireland","Italy","Latvia","Lithuania","Luxembourg",
          "Malta","Netherlands","Norway","Poland","Portugal","Romania","San Marino","Slovakia",
          "Slovenia","Spain","Sweden","Switzerland","Turkey","United Kingdom","Bulgaria","Cyprus"}
ASIA = {"China","India","Indonesia","Japan","Malaysia","Singapore","South Korea","Taiwan",
        "Thailand","Vietnam"}


def e(s):
    return html.escape(str(s or ""), quote=True)


def region_of(c):
    if c == "USA":
        return "usa"
    if c in EUROPE:
        return "europe"
    if c in ASIA:
        return "asia"
    return "other"


def initials(name):
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
    try:
        return datetime.date.fromisoformat(iso).strftime("%-d %b %Y")
    except Exception:
        return iso or ""


def source_state(v):
    """url | not_found (with its date) | none. The third is 'nobody looked yet'."""
    v = (v or "").strip()
    if v.startswith("http"):
        return "url", v, ""
    if v.lower().startswith("not_found"):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", v)
        return "not_found", "", pretty_date(m.group(1)) if m else ""
    return "none", "", ""


def fact_count(r):
    n = 0
    for f in ("website", "hq_country", "hq_city", "founded_year", "ownership", "sectors",
              "total_disclosed_funding", "funding_stage"):
        if (r.get(f) or "").strip():
            n += 1
    return n


def profile_state(r, findings):
    """The five states the design draws."""
    if r["entity_type"] in NON_COMMERCIAL:
        return "non-supplier"
    if r.get("company_supplied"):
        return "claimed"
    facts = fact_count(r)
    if facts >= 6 or findings:
        return "rich"
    if facts >= 3:
        return "typical"
    return "sparse"


def load():
    with open(DATA, encoding="utf-8") as fh:
        payload = json.load(fh)
    cap = {}
    if os.path.exists(CAP):
        with open(CAP, encoding="utf-8") as fh:
            for row in json.load(fh).get("results", []):
                cap.setdefault(row["supplier_id"], {})[row["check_id"]] = row
    return payload["suppliers"], payload["counts"], cap


# ---------------------------------------------------------------- shell

def page(title, desc, canonical, body, script="", og_extra=""):
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
  <meta property="og:type" content="website" />{og_extra}
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/research/digital-product-passport/register.css" />
</head>
<body>
{body}
{script}
</body>
</html>
"""


# The real site nav, identical to every other page on yellow3.io, using the
# genuine logo asset. The handoff shipped its own wordmark treatment and a
# generated logo file; neither is used - a mark we did not draw is not ours to
# redraw, and the shared component is what rule 1 of the handoff asks for.
SITE_NAV = """  <nav class="site-nav y3nav">
    <a href="/" class="brand"><img src="/logo.png" alt="yellow3" /></a>
    <div class="nav-mid" id="navMid">
      <a href="/naffe">Work</a>
      <a href="/research" class="active">Research</a>
      <a href="/insights/">Thinking</a>
      <a href="/advisory">Advisory</a>
      <a href="/about">About</a>
      <a href="/#contact">Contact</a>
    </div>
    <a href="/advisory" class="nav-cta y3cta">Work with us <span>&#8594;</span></a>
    <button class="nav-toggle" aria-label="Menu" onclick="this.classList.toggle('open');document.getElementById('navMid').classList.toggle('open')"><span></span><span></span><span></span></button>
  </nav>
"""


# The site's real footer, same component as every other page.
SITE_FOOTER = """  <footer class="site-footer y3foot">
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
        <div class="foot-legal"><a href="/privacy">Privacy</a><a href="/terms">Terms</a></div>
      </div>
    </div>
  </footer>
"""


def register_nav(counts, active=""):
    """The register bar, as drawn: brand, counts, Search / Method."""
    return f"""  <header class="profile-nav">
    <div><strong>yellow3 lab &middot; DPP Supplier Register</strong>
      <span><b>{counts['organisations']}</b> organisations</span>
      <span><b>{counts['commercial_suppliers']}</b> commercial suppliers</span>
      <span><b>{counts['countries']}</b> countries</span></div>
    <nav><a href="/research/digital-product-passport/suppliers">Search</a><a href="/research/digital-product-passport/suppliers#method">Method</a></nav>
  </header>
"""


# ---------------------------------------------------------------- profile

def profile_html(r, counts, cap):
    results = cap.get(r["id"], {})
    findings = sum(1 for v in results.values() if v.get("state"))
    nc = r["entity_type"] in NON_COMMERCIAL
    kind, curl, cdate = source_state(r["country_source"])
    checked = cdate or pretty_date(datetime.date.today().isoformat())
    sid = r["id"]

    # website line
    if r["website"]:
        site = (f'<a href="{e(r["website"])}" target="_blank" rel="noopener">{e(r["domain"])}</a>'
                f'<sup>1</sup> &#8599;')
    elif kind == "not_found":
        site = 'No official website established<sup>1</sup> &#8599;'
    else:
        site = 'Not yet assessed'

    # country line, and the provenance drawer that belongs to it
    if r["hq_country"]:
        place = ", ".join([x for x in (r["hq_city"], r["hq_country"]) if x])
        country_line = f'{e(place)}<sup>2</sup> &middot; checked {e(checked)}'
        pop_find = "Confirmed from a primary source" if kind == "url" else "Stated by the company"
    elif kind == "not_found":
        country_line = f'Not publicly established<sup>2</sup> &middot; checked {e(checked)}'
        pop_find = "No public country source found"
    else:
        country_line = 'Not yet assessed'
        pop_find = "Not yet assessed"
    pop_link = (f'<a href="{e(curl)}" target="_blank" rel="noopener">View search record &#8599;</a>'
                if curl else '<a href="#evidence">View search record &#8599;</a>')

    # at a glance - absence is a dated finding, never an empty cell
    def glance(label, value, src=""):
        k, u, d = source_state(src)
        if value:
            tail = f' &middot; <a href="{e(u)}" target="_blank" rel="noopener">source</a>' if k == "url" else ""
            return f"<div><strong>{label}</strong><span>{e(value)}{tail}</span></div>"
        if k == "not_found":
            return (f"<div><strong>{label}</strong><span>No public disclosure found"
                    f"<br />checked {e(d)}</span></div>")
        return f"<div><strong>{label}</strong><span>Not yet assessed</span></div>"

    sectors = ", ".join(SECTOR_LABEL.get(s, s.title()) for s in r.get("sectors_list", []))
    glance_grid = "".join([
        glance("Sectors", sectors),
        glance("Founded", r["founded_year"]),
        glance("Ownership", r["ownership"]),
        glance("Funding stage", r["funding_stage"].replace("-", " ")),
        glance("Disclosed funding", r["total_disclosed_funding"], r["funding_source"]),
    ])

    # capability: ten rows, or one honest sentence when nobody has looked
    if nc:
        capability = ""
    elif not results:
        capability = (
            '<div class="capability-block"><h3>Capability evidence</h3>'
            '<p>Ten independent checks. No composite score.</p>'
            '<p>Not yet assessed for this supplier.<br />Assessments are published as they are completed.</p>'
            '<a href="/research/digital-product-passport/suppliers#framework">View assessment framework &#8599;</a></div>')
    else:
        LABEL = {"verified": "Verified", "company_states": "Company states", "not_found": "Not found"}
        rows_html = ""
        for i, name in enumerate(CRITERIA, 1):
            rec = results.get(f"c{i:02d}")
            if not rec:
                rows_html += (f'<div class="capability-row"><span>{i}</span><strong>{e(name)}</strong>'
                              f'<em class="cap-na">Not yet assessed</em></div>')
                continue
            st = rec.get("state", "")
            link = (f' <a href="{e(rec["evidence_url"])}" target="_blank" rel="noopener" '
                    f'title="{e(rec.get("artifact",""))}">evidence &#8599;</a>') if rec.get("evidence_url") else ""
            rows_html += (f'<div class="capability-row"><span>{i}</span><strong>{e(name)}</strong>'
                          f'<em class="cap-{st}">{LABEL.get(st, "Not yet assessed")}'
                          f'<i>{e(pretty_date(rec.get("checked_date","")))}</i>{link}</em></div>')
        capability = (
            '<div class="capability-block"><h3>Capability evidence</h3>'
            '<p>Ten independent checks. No composite score.</p>'
            f'<div class="capability-rows">{rows_html}</div>'
            f'<a href="/research/digital-product-passport/suppliers#framework">View assessment framework &#8599;</a></div>')

    # company layer - never merged with the evidence layer above
    company = "" if nc else f"""
          <section class="company-layer">
            <span class="layer-rule yellow"></span>
            <h3>Supplied by {e(r["name"])}</h3>
            <p>No company-supplied profile received</p>
            <a href="/research/digital-product-passport/suppliers/{e(sid)}/claim">Claim this profile &#8599;</a>
          </section>"""

    src_cell = (f'<a href="{e(r["evidence_url"])}" target="_blank" rel="noopener">{e(r["source"])} &#8599;</a>'
                if r["evidence_url"] else e(r["source"]) or "Not recorded")
    claim_foot = ("" if nc else
                  f'<a href="/research/digital-product-passport/suppliers/{e(sid)}/claim">Claim this profile &#8599;</a>')

    body = f"""{SITE_NAV}<main class="profile-shell">
  <a class="back-link" href="/research/digital-product-passport/suppliers">&#8249; <span>All suppliers</span></a>

  <div class="profile-layout">
    <article class="profile-record">
      <header class="profile-identity">
        <span class="profile-monogram">{e(initials(r["name"]))}</span>
        <div>
          <div class="profile-name-line"><h1>{e(r["name"])}</h1><span>{e(TYPE_LABEL.get(r["entity_type"], r["entity_type"]))}</span></div>
          <p>{site}<small>checked {e(checked)}</small></p>
          <button type="button" id="provToggle" aria-expanded="false">{country_line} <i>&#9432;</i></button>
        </div>
        <b class="vertical-label">Supplier profile</b>
        <div class="profile-popover" id="prov" hidden><strong>Country check</strong><span>{e(pop_find)}</span><span>Checked {e(checked)}</span>{pop_link}</div>
      </header>

      <section class="verified-layer">
        <span class="layer-rule yellow"></span>
        <h2>Verified by yellow3</h2>
        <h3>At a glance</h3>
        <div class="glance-grid">{glance_grid}</div>
        {capability}
      </section>
{company}
      <footer class="register-evidence" id="evidence">
        <h3>Register evidence</h3>
        <div><strong>Source</strong><span>{src_cell}</span></div>
        <div><strong>First recorded</strong><span>{e(pretty_date(r["source_date"]))}</span></div>
        <div><strong>Last checked</strong><span>{e(checked)}</span></div>
        <a href="/research/digital-product-passport/suppliers#method">Research method &#8599;</a>
        <a href="/research/digital-product-passport/suppliers#corrections">Suggest a correction &#8599;</a>
        {claim_foot}
      </footer>
    </article>

    <aside class="profile-legend">
      <section><span class="layer-rule black"></span><h3>Evidence layer</h3><p>Independently verified by yellow3 through public sources.</p></section>
      <section class="company"><span class="layer-rule yellow"></span><h3>Company layer</h3><p>Information supplied by the company. Currently absent.</p></section>
      <section><span class="layer-rule grey"></span><h3>Source drawer</h3><p>Provenance and research details for this profile.</p></section>
    </aside>
  </div>
</main>
""" + SITE_FOOTER
    script = """
<script>
(function(){
  var b=document.getElementById('provToggle'), p=document.getElementById('prov');
  if(!b||!p) return;
  b.addEventListener('click',function(){
    var open=p.hasAttribute('hidden');
    if(open){p.removeAttribute('hidden');}else{p.setAttribute('hidden','');}
    b.setAttribute('aria-expanded',open?'true':'false');
  });
})();
</script>
"""
    jsonld = ('\n  <script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "ProfilePage",
        "name": f"{r['name']} - DPP Supplier Register",
        "url": f"https://yellow3.io/research/digital-product-passport/suppliers/{sid}",
        "isPartOf": {"@type": "Dataset", "name": "yellow3 DPP Supplier Register",
                     "url": "https://yellow3.io/research/digital-product-passport/suppliers"},
        "about": {k: v for k, v in {
            "@type": "Organization", "name": r["name"],
            "url": r["website"] or None,
            "address": ({"@type": "PostalAddress", "addressCountry": r["hq_country"],
                         **({"addressLocality": r["hq_city"]} if r["hq_city"] else {})}
                        if r["hq_country"] and kind == "url" else None),
        }.items() if v},
        "publisher": {"@type": "Organization", "name": "yellow3 lab", "url": "https://yellow3.io"},
    }, ensure_ascii=False, separators=(",", ":")) + "</script>")

    return page(f"{r['name']} - DPP Supplier Register - yellow3",
                f"{r['name']}: Digital Product Passport supplier profile. Independently sourced "
                f"identity, headquarters and evidence, recorded by yellow3 lab.",
                f"https://yellow3.io/research/digital-product-passport/suppliers/{sid}",
                body, script, jsonld)


# ---------------------------------------------------------------- claim

def claim_html(r, counts):
    sid = r["id"]
    body = f"""{SITE_NAV}<main class="claim-shell">

  <section class="claim-body">
    <a class="claim-back" href="/research/digital-product-passport/suppliers/{e(sid)}">&#8249; Back to profile</a>

    <section class="claim-content">
      <h1>Claim {e(r["name"])}</h1>
      <p class="claim-intro">Enter your work email. If it is at the domain on record for this company,
      the claim is confirmed straight away, no account, no waiting for approval.</p>
      <form id="claimForm">
        <label><span class="sr-only">Work email</span>
          <input id="claimEmail" type="email" placeholder="you@yourcompany.com" autocomplete="email" /></label>
        <button type="submit">Claim this profile <span>&#8594;</span></button>
      </form>
      <p class="claim-message" role="status" id="claimMsg" hidden></p>

      <div class="claim-principles">
        <article><h2>What you can supply</h2><p>A logo, a one-line description, a contact link, and
        your answers to the ten capability checks. It appears in its own layer on your profile,
        marked as coming from you, and dated.</p></article>
        <article><h2>What stays ours</h2><p>Everything we verified independently, with the source and
        the date we checked it. Company-supplied content never overwrites it. If something we
        published is wrong, send the correction with a source and we will fix it and log the
        change.</p></article>
        <article><h2>Why a work email</h2><p>The register is keyed on company domains, so an address
        at the company domain is proof enough. Personal mailboxes are not accepted, which is what
        keeps anyone from claiming a company they do not work for.</p></article>
      </div>
    </section>
  </section>
</main>
""" + SITE_FOOTER
    script = """
<script>
(function(){
  var PUBLIC=['gmail.com','googlemail.com','outlook.com','hotmail.com','live.com','yahoo.com',
    'yahoo.co.uk','icloud.com','me.com','mac.com','aol.com','proton.me','protonmail.com',
    'gmx.com','gmx.net','msn.com','yandex.com','zoho.com','fastmail.com','hey.com'];
  var f=document.getElementById('claimForm'), i=document.getElementById('claimEmail'),
      m=document.getElementById('claimMsg'), id=document.body.dataset.supplier;
  function say(t){ m.hidden=false; m.textContent=t; }
  f.addEventListener('submit',function(ev){
    ev.preventDefault();
    var email=(i.value||'').trim().toLowerCase();
    var domain=email.split('@')[1];
    if(!domain||email.indexOf('@')<1){ say('Enter a valid work email.'); return; }
    if(PUBLIC.indexOf(domain)>-1){
      say('Personal mailboxes are not accepted. Use your company email.'); return; }
    say('Checking\\u2026');
    // eligibility is decided on the server against the supplier domain; the
    // browser is never trusted with the answer.
    fetch('/api/claim',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email:email,supplier:id})})
      .then(function(){ say('Work email received. If ' + domain + ' is the domain on record for '
        + 'this company, a confirmation is on its way. If it is not, nothing was sent.'); })
      .catch(function(){ say('Something went wrong. Please try again.'); });
  });
})();
</script>
"""
    out = page(f"Claim {r['name']} - DPP Supplier Register - yellow3",
               f"Claim the {r['name']} profile on the yellow3 DPP Supplier Register. "
               f"Confirmed by work email domain, no account required.",
               f"https://yellow3.io/research/digital-product-passport/suppliers/{sid}/claim",
               body, script)
    # claim pages are a company action, not research - keep them out of the index
    out = out.replace("<body>", f'<body data-supplier="{e(sid)}">')
    return out.replace('<meta property="og:type" content="website" />',
                       '<meta property="og:type" content="website" />\n  <meta name="robots" content="noindex,follow" />')


DIR_SCRIPT = r"""
<script>
(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("registerData").textContent);
  var NON_COMMERCIAL = { "not-a-supplier": 1, "project-consortium": 1, "standards-body": 1 };
  var REGION_COLOR = { europe: "#c1972b", asia: "#5b2b4d", usa: "#223a5e", other: "#565a60" };
  var REGION_TINT  = { europe: "#efe7cf", asia: "#e7dce4", usa: "#dce3ec", other: "#e1e1df" };
  var BASE = "/research/digital-product-passport/suppliers/";
  var SVGNS = "http://www.w3.org/2000/svg";
  var geo = null, selected = "", openRow = "";

  function svg(t, a) { var el = document.createElementNS(SVGNS, t); for (var k in a) if (a[k] != null) el.setAttribute(k, a[k]); return el; }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  var $ = function (id) { return document.getElementById(id); };

  var state = { q: "", scope: "all", type: "all", sector: "all",
                dq: "", dCountry: "", dSector: "", dType: "", dCap: "", dSort: "recent" };

  // ---- map filters
  function mapFiltered() {
    var q = state.q.trim().toLowerCase();
    return DATA.filter(function (r) {
      if (state.scope === "commercial" && NON_COMMERCIAL[r.entity_type]) return false;
      if (state.type !== "all" && r.entity_type !== state.type) return false;
      if (state.sector !== "all" && r.sector_keys.indexOf(state.sector) < 0) return false;
      if (q && [r.name, r.country, r.city, r.entity_type].join(" ").toLowerCase().indexOf(q) < 0) return false;
      return true;
    });
  }
  function groupBy(rows) {
    var m = {};
    rows.forEach(function (r) {
      if (!r.country) return;
      if (!m[r.country]) m[r.country] = { country: r.country, suppliers: [], count: 0 };
      m[r.country].suppliers.push(r); m[r.country].count += 1;
    });
    Object.keys(m).forEach(function (k) { m[k].suppliers.sort(function (a, b) { return a.name.localeCompare(b.name); }); });
    return m;
  }

  function drawBase() {
    var map = $("worldMap");
    map.appendChild(svg("path", { d: geo.sphere, class: "map-sphere" }));
    map.appendChild(svg("path", { d: geo.graticule, class: "map-grid" }));
    var f = document.createDocumentFragment();
    geo.countries.forEach(function (c) { var p = svg("path", { d: c.d, class: "map-country" }); p.dataset.country = c.name; f.appendChild(p); });
    map.appendChild(f);
    map.appendChild(svg("g", { id: "markerLayer" }));
    map.addEventListener("mouseover", function (ev) { var t = ev.target.closest("[data-country]"); if (t && t.classList.contains("has-suppliers")) hover(t.dataset.country); });
    map.addEventListener("mouseout", function (ev) { if (ev.target.closest("[data-country]")) hover(""); });
    map.addEventListener("click", function (ev) { var t = ev.target.closest("[data-country]"); if (t && t.classList.contains("has-suppliers")) { selected = t.dataset.country; render(); } });
  }
  function hover(c) {
    var g = c ? groupBy(mapFiltered())[c] : null;
    $("mapStatus").innerHTML = g
      ? "<strong>" + esc(g.country) + "</strong><span>" + g.count + " " + (g.count === 1 ? "organisation" : "organisations") + "</span>"
      : "<strong>Explore the market</strong><span>Select a country to open its supplier list</span>";
  }

  function renderMap() {
    var rows = mapFiltered(), groups = groupBy(rows), names = Object.keys(groups);
    if (selected && !groups[selected]) selected = "";
    $("resultCount").textContent = rows.length + " organisations shown";
    var mapped = rows.filter(function (r) { return r.country; }).length;
    $("mappedCount").textContent = mapped;
    $("unplacedCount").textContent = rows.length - mapped;

    Array.prototype.forEach.call(document.querySelectorAll("[data-country]"), function (p) {
      var n = p.dataset.country, g = groups[n], sel = selected === n;
      p.classList.toggle("has-suppliers", !!g);
      p.classList.toggle("is-selected", sel);
      p.style.fill = sel ? "#0e0e0e" : g ? REGION_TINT[regionOf(n)] : "#e9e8e4";
    });

    var layer = $("markerLayer"); layer.innerHTML = "";
    names.forEach(function (n) {
      var g = groups[n], pt = geo.points[n]; if (!pt) return;
      var radius = 4.5 + Math.sqrt(g.count) * 2.15, sel = selected === n;
      var grp = svg("g", { class: "map-marker", transform: "translate(" + pt[0] + " " + pt[1] + ")",
        role: "button", tabindex: "0", "aria-label": n + ", " + g.count + " organisations" });
      grp.appendChild(svg("circle", { r: Math.max(radius + 7, 15), fill: "transparent", stroke: "none" }));
      if (sel) grp.appendChild(svg("circle", { r: radius + 5, fill: "none", stroke: "#0e0e0e", "stroke-width": "1.5", class: "marker-pulse" }));
      grp.appendChild(svg("circle", { r: radius, fill: REGION_COLOR[regionOf(n)], stroke: "#ffffff", "stroke-width": "2.5" }));
      if (g.count >= 4) { var t = svg("text", { "text-anchor": "middle", "dominant-baseline": "central", class: "marker-count" }); t.textContent = g.count; grp.appendChild(t); }
      grp.addEventListener("mouseenter", function () { hover(n); });
      grp.addEventListener("mouseleave", function () { hover(""); });
      grp.addEventListener("focus", function () { hover(n); });
      grp.addEventListener("blur", function () { hover(""); });
      grp.addEventListener("click", function () { selected = n; render(); });
      grp.addEventListener("keydown", function (ev) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); selected = n; render(); } });
      layer.appendChild(grp);
    });
    renderPanel(groups, names);
  }
  function regionOf(c) { var r = DATA.filter(function (x) { return x.country === c; })[0]; return r ? r.region : "other"; }

  function renderPanel(groups, names) {
    var panel = $("panel");
    var ranked = names.map(function (n) { return groups[n]; }).sort(function (a, b) { return b.count - a.count || a.country.localeCompare(b.country); });
    if (selected && groups[selected]) {
      var g = groups[selected];
      panel.innerHTML =
        '<div class="panel-title-row"><div><p class="panel-kicker">Country</p><h3>' + esc(g.country) +
        '</h3></div><button type="button" class="panel-close" id="pc" aria-label="Close country details">&times;</button></div>' +
        '<div class="country-summary"><strong>' + g.count + "</strong><span>" + (g.count === 1 ? "organisation" : "organisations") + "<br />in the current view</span></div>" +
        '<div class="supplier-list">' + g.suppliers.map(function (s) {
          return '<a href="' + BASE + esc(s.id) + '" class="supplier-row"><span class="supplier-mark">' + esc(s.initials) +
            '</span><span class="supplier-copy"><strong>' + esc(s.name) + "</strong><small>" +
            (s.city ? esc(s.city) + " &middot; " : "") + esc(s.type) + "</small></span><span class=\"row-arrow\">&#8599;</span></a>";
        }).join("") + "</div>";
      $("pc").addEventListener("click", function () { selected = ""; render(); });
      return;
    }
    var top = ranked[0] ? ranked[0].count : 1;
    panel.innerHTML =
      '<div class="panel-title-row"><div><p class="panel-kicker">Market density</p><h3>Countries</h3></div><span class="panel-total">' + ranked.length + "</span></div>" +
      '<p class="panel-intro">Select a country on the map or use the ranked list below. Counts respond to every filter.</p>' +
      '<div class="country-ranking">' + ranked.map(function (g, i) {
        return '<button type="button" class="country-rank" data-rank="' + esc(g.country) + '"><span class="rank-number">' +
          String(i + 1).padStart(2, "0") + '</span><span class="rank-country">' + esc(g.country) +
          '</span><span class="rank-line"><i style="width:' + Math.max(8, (g.count / top) * 100) + '%"></i></span><strong>' + g.count + "</strong></button>";
      }).join("") + "</div>";
    Array.prototype.forEach.call(panel.querySelectorAll("[data-rank]"), function (b) {
      b.addEventListener("click", function () { selected = b.dataset.rank; render(); });
    });
  }

  // ---- directory
  function dirFiltered() {
    var q = state.dq.trim().toLowerCase();
    var out = DATA.filter(function (r) {
      if (q && (r.name + " " + r.hq + " " + r.type + " " + r.sectors.join(" ")).toLowerCase().indexOf(q) < 0) return false;
      if (state.dCountry && r.country !== state.dCountry) return false;
      if (state.dSector && r.sector_keys.indexOf(state.dSector) < 0) return false;
      if (state.dType && r.entity_type !== state.dType) return false;
      if (state.dCap && r.assessed !== state.dCap) return false;
      return true;
    });
    if (state.dSort === "az") out.sort(function (a, b) { return a.name.localeCompare(b.name); });
    return out;
  }
  function renderDir() {
    var rows = dirFiltered();
    $("profileCount").textContent = rows.length + (rows.length === DATA.length ? " profiles" : " of " + DATA.length + " profiles");
    $("dirRows").innerHTML = rows.map(function (r) {
      var open = openRow === r.id;
      return '<article class="directory-row state-' + r.state + (open ? " is-open" : "") + '" data-row="' + esc(r.id) + '">' +
        '<a class="row-supplier" href="' + BASE + esc(r.id) + '">' +
        (r.state === "non-supplier" ? "<small>Non-supplier<br />entity</small>" : "") +
        '<span class="row-initials">' + esc(r.initials) + '</span><strong>' + esc(r.name) + "</strong><em>&#8599;</em></a>" +
        '<div><span class="type-chip">' + esc(r.type) + "</span></div>" +
        '<div class="row-hq">' + r.hq + "</div>" +
        '<div class="sector-list">' + r.sectors.map(function (x) { return "<span>" + x + "</span>"; }).join("") + "</div>" +
        '<div class="row-evidence"><span>' + r.evidence + "</span>" + (r.basis ? "<small>" + esc(r.basis) + "</small>" : "") + "</div>" +
        '<div class="row-date"><span>' + esc(r.date) + "</span>" +
        (r.state !== "non-supplier" ? '<button aria-label="Toggle ' + esc(r.name) + ' evidence" data-toggle="' + esc(r.id) + '">&#8964;</button>' : "") + "</div>" +
        (open ? '<div class="row-drawer"><strong>Evidence record</strong><span>' + esc(r.drawer) +
          "</span><span>Checked " + esc(r.date) + '</span><a href="' + BASE + esc(r.id) + '">View profile record &#8599;</a></div>' : "") +
        "</article>";
    }).join("");
    Array.prototype.forEach.call($("dirRows").querySelectorAll("[data-toggle]"), function (b) {
      b.addEventListener("click", function () { openRow = openRow === b.dataset.toggle ? "" : b.dataset.toggle; renderDir(); });
    });
  }

  // ---- five profile states, drawn from real rows
  function renderStates() {
    var want = ["rich", "typical", "sparse", "non-supplier", "claimed"];
    var LABEL = { rich: "Rich", typical: "Typical", sparse: "Sparse", "non-supplier": "Not a supplier", claimed: "Claimed" };
    $("stateCards").innerHTML = want.map(function (st) {
      var r = DATA.filter(function (x) { return x.state === st; })[0];
      if (!r) return '<article class="state-card state-' + st + '"><h3>' + LABEL[st] + "</h3><p>No profile is in this state yet.</p></article>";
      var head = '<div class="state-card-head"><span>' + esc(r.initials) + "</span><b>" + esc(r.type) + "</b><small>" + esc(r.basis || "non-commercial entity") + "</small></div>";
      if (st === "non-supplier") {
        return '<article class="state-card state-' + st + '"><h3>' + LABEL[st] + "</h3>" + head +
          "<p>" + r.evidence + "</p><dl><dt>HQ</dt><dd>" + r.hq + "</dd><dt>Last checked</dt><dd>" + esc(r.date) +
          "</dd></dl><footer>Non-commercial entity</footer></article>";
      }
      return '<article class="state-card state-' + st + '"><h3>' + LABEL[st] + "</h3>" + head +
        "<dl><dt>Sectors</dt><dd>" + r.sectors.join(", ") + "</dd><dt>HQ</dt><dd>" + r.hq +
        "</dd><dt>Evidence</dt><dd>" + r.evidence + "</dd><dt>Last checked</dt><dd>" + esc(r.date) +
        "</dd></dl><footer>Verified by yellow3</footer></article>";
    }).join("");
  }

  function render() { if (geo) renderMap(); renderDir(); }

  ["q", "fType", "fSector"].forEach(function (id) {
    var el = $(id); if (!el) return;
    el.addEventListener("input", function () {
      state[id === "q" ? "q" : id === "fType" ? "type" : "sector"] = el.value; render();
    });
    el.addEventListener("change", function () {
      state[id === "q" ? "q" : id === "fType" ? "type" : "sector"] = el.value; render();
    });
  });
  Array.prototype.forEach.call(document.querySelectorAll("[data-scope]"), function (b) {
    b.addEventListener("click", function () {
      state.scope = b.dataset.scope;
      Array.prototype.forEach.call(document.querySelectorAll("[data-scope]"), function (x) { x.classList.toggle("active", x === b); });
      render();
    });
  });
  [["dq", "dq"], ["dCountry", "dCountry"], ["dSector", "dSector"], ["dType", "dType"], ["dCap", "dCap"], ["dSort", "dSort"]].forEach(function (pair) {
    var el = $(pair[0]); if (!el) return;
    var ev = el.tagName === "SELECT" ? "change" : "input";
    el.addEventListener(ev, function () { state[pair[1]] = el.value; renderDir(); });
  });

  renderStates();
  renderDir();
  fetch("/research/dpp-map-geometry.json").then(function (r) { return r.json(); }).then(function (g) { geo = g; drawBase(); renderMap(); })
    .catch(function () { $("resultCount").textContent = DATA.length + " organisations shown"; });
})();
</script>
"""


# ---------------------------------------------------------------- directory

def directory_html(rows, counts, cap):
    """The map-led catalogue and the directory, on one route, as the route plan asks."""
    payload = []
    for r in rows:
        results = cap.get(r["id"], {})
        findings = sum(1 for v in results.values() if v.get("state"))
        kind, curl, cdate = source_state(r["country_source"])
        nc = r["entity_type"] in NON_COMMERCIAL
        facts = fact_count(r)
        if nc:
            evidence = ("Research project &middot; not available for procurement"
                        if r["entity_type"] == "project-consortium" else "Not a commercial supplier")
            basis = ""
        else:
            evidence = (f"{facts} fact{'' if facts == 1 else 's'} &middot; "
                        + (f"{findings} capability findings" if findings else "capability research pending"))
            basis = r["confidence"]
        hq = (", ".join([x for x in (r["hq_city"], r["hq_country"]) if x]) if r["hq_country"]
              else ("Not publicly established<sup>1</sup>" if kind == "not_found" else "Not yet assessed"))
        secs = [SECTOR_LABEL.get(s, s.title()) for s in r.get("sectors_list", [])]
        payload.append({
            "id": r["id"], "initials": initials(r["name"]), "name": r["name"],
            "type": TYPE_LABEL.get(r["entity_type"], r["entity_type"]),
            "entity_type": r["entity_type"],
            "hq": hq, "country": r["hq_country"], "city": r["hq_city"],
            "sectors": secs[:2] or ["No public sector focus found<sup>2</sup>"],
            "sector_keys": r.get("sectors_list", []),
            "evidence": evidence, "basis": basis,
            "date": pretty_date(cdate or r["source_date"]),
            "region": region_of(r["hq_country"]),
            "state": profile_state(r, findings),
            "website": r["website"],
            "drawer": ("No public country source found" if kind == "not_found"
                       else (f"Headquarters source recorded for {hq}" if r["hq_country"]
                             else "Not yet assessed")),
            "assessed": "assessed" if findings else "pending",
        })

    countries = sorted({p["country"] for p in payload if p["country"]})
    sectors = sorted({s for p in payload for s in p["sector_keys"]})
    types = sorted({p["entity_type"] for p in payload})
    today = datetime.date.today().strftime("%-d %b")

    opts = lambda vals, lab: "".join(f'<option value="{e(v)}">{e(lab(v))}</option>' for v in vals)

    body = f"""{SITE_NAV}<main class="registry-shell">
  <section class="hero">
    <div class="wrap">
      <p class="eyebrow">Research / Digital Product Passport / Supplier register</p>
      <div class="hero-grid">
        <div>
          <h1>The global DPP supplier landscape.</h1>
          <p class="lede">A research map of every organisation we could identify supplying Digital
          Product Passport capability. Every headquarters is sourced, dated, and open to inspection.</p>
        </div>
        <div class="hero-stats" aria-label="Register summary">
          <div><strong>{counts['organisations']}</strong><span>organisations</span></div>
          <div><strong>{counts['commercial_suppliers']}</strong><span>commercial suppliers</span></div>
          <div><strong>{counts['countries']}</strong><span>countries</span></div>
          <div><strong>{today}</strong><span>last researched</span></div>
        </div>
      </div>
    </div>
  </section>

  <section class="explorer" id="map">
    <div class="explorer-head">
      <div><p class="section-kicker">Global supplier map</p><h2>Where the market is taking shape</h2></div>
      <p class="result-count" id="resultCount">Loading register</p>
    </div>

    <div class="filter-bar" aria-label="Map filters">
      <label class="search-field"><span class="sr-only">Search organisations or locations</span>
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4.2 4.2" /></svg>
        <input id="q" type="search" placeholder="Search organisation, city or country" /></label>
      <div class="scope-switch" aria-label="Supplier scope">
        <button type="button" data-scope="all" class="active">All organisations</button>
        <button type="button" data-scope="commercial">Commercial only</button></div>
      <label class="select-wrap"><span class="sr-only">Filter by entity type</span>
        <select id="fType"><option value="all">All entity types</option>{opts(types, lambda v: TYPE_LABEL.get(v, v))}</select></label>
      <label class="select-wrap"><span class="sr-only">Filter by sector</span>
        <select id="fSector"><option value="all">All sectors</option>{opts(sectors, lambda v: SECTOR_LABEL.get(v, v.title()))}</select></label>
    </div>

    <div class="explorer-grid">
      <div class="map-stage">
        <div class="map-status" aria-live="polite" id="mapStatus">
          <strong>Explore the market</strong><span>Select a country to open its supplier list</span></div>
        <svg class="world-map" id="worldMap" viewBox="0 0 1100 560" role="img"
             aria-label="World map showing Digital Product Passport suppliers by headquarters country"></svg>
        <div class="map-legend" aria-label="Map region legend">
          <span><i class="legend-dot europe"></i>Europe</span><span><i class="legend-dot asia"></i>Asia</span>
          <span><i class="legend-dot usa"></i>USA</span><span><i class="legend-dot other"></i>Other</span>
          <em>Circle size shows supplier count</em></div>
      </div>
      <aside class="country-panel" id="panel"></aside>
    </div>

    <div class="map-foot">
      <p><strong id="mappedCount">0</strong> organisations have a publicly sourced headquarters
      location. <strong id="unplacedCount">0</strong> remain unplaced because no public
      headquarters source was found.</p>
      <a href="#method">Read the research method <span>&#8594;</span></a>
    </div>
  </section>

  <section class="directory-head">
    <h1>Supplier directory</h1>
    <p>Evidence-led profiles of the global Digital Product Passport market.</p>
  </section>

  <section class="directory-controls" aria-label="Supplier filters">
    <label class="directory-search"><span aria-hidden="true">&#8981;</span>
      <input id="dq" placeholder="Search {counts['organisations']} suppliers" /></label>
    <label><span class="sr-only">Country</span><select id="dCountry"><option value="">Country</option>{opts(countries, lambda v: v)}</select></label>
    <label><span class="sr-only">Sector</span><select id="dSector"><option value="">Sector</option>{opts(sectors, lambda v: SECTOR_LABEL.get(v, v.title()))}</select></label>
    <label><span class="sr-only">Entity type</span><select id="dType"><option value="">Entity type</option>{opts(types, lambda v: TYPE_LABEL.get(v, v))}</select></label>
    <label><span class="sr-only">Capability evidence</span><select id="dCap"><option value="">Capability evidence</option><option value="assessed">Assessed</option><option value="pending">Pending</option></select></label>
    <label class="sort-control"><span class="sr-only">Sort order</span><select id="dSort"><option value="recent">Recently checked</option><option value="az">Supplier A&ndash;Z</option></select></label>
  </section>

  <section class="directory-table">
    <p class="profile-count" id="profileCount"></p>
    <div class="directory-labels"><span>Supplier</span><span>Type</span><span>HQ</span><span>Sectors</span><span>Evidence</span><span>Last checked</span></div>
    <div id="dirRows"></div>
  </section>

  <section class="profile-states" id="about">
    <div class="profile-states-main">
      <h2>Five profile states</h2>
      <div class="state-card-grid" id="stateCards"></div>
    </div>
    <aside class="metadata-key">
      <section><h3>Evidence basis <small>(metadata)</small></h3><p>verified <i>/</i> claimed <i>/</i> unverified</p></section>
      <section><h3>Capability states <small>(metadata)</small></h3><p>&#9675; verified</p><p>&#9651; claimed</p><p>&#215; not found</p></section>
      <section><h3>Region rule <small>(metadata)</small></h3><p><b class="key-line europe"></b>Europe (ochre)</p><p><b class="key-line asia"></b>Asia (aubergine)</p><p><b class="key-line usa"></b>US (navy)</p><p><b class="key-line other"></b>Other / unknown (graphite)</p></section>
      <p>These are metadata, not rankings.</p>
    </aside>
  </section>

  <section class="evidence-band" id="method">
    <div class="evidence-copy">
      <p class="section-kicker">Evidence, not inference</p>
      <h2>Blank space is part of the map.</h2>
      <p>We do not infer a headquarters from a company name, domain ending, legal-form suffix, or
      regional office. If a location is not publicly sourced, the organisation stays off the map
      until it can be proven.</p>
    </div>
    <div class="evidence-rule">
      <div><span>01</span><strong>Every location has a source.</strong></div>
      <div><span>02</span><strong>Every source has a date.</strong></div>
      <div><span>03</span><strong>No ranking. No composite score.</strong></div>
    </div>
  </section>

  <div class="directory-foot"><span><sup>1</sup> No public country source found.</span><span><sup>2</sup> No sector focus statement or case evidence identified.</span><span>&#8599; External link indicates supplier website.</span></div>
</main>
""" + SITE_FOOTER
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    script = ('<script id="registerData" type="application/json">' + data_json + "</script>\n"
              + DIR_SCRIPT)
    return page("Supplier directory - DPP Supplier Register - yellow3",
                f"Evidence-led profiles of the Digital Product Passport market. "
                f"{counts['organisations']} organisations across {counts['countries']} countries, "
                f"every headquarters sourced and dated.",
                "https://yellow3.io/research/digital-product-passport/suppliers",
                body, script)


# ---------------------------------------------------------------- routes

def write_redirects(ids):
    """The old profile URLs are indexed. Move them with explicit 308s.

    A wildcard on /research/digital-product-passport/:id would also swallow
    /suppliers itself, so every id gets its own rule.
    """
    with open(VERCEL, encoding="utf-8") as fh:
        conf = json.load(fh)
    keep = [r for r in conf.get("redirects", [])
            if "/research/digital-product-passport/" not in r["source"]
            or r["source"].endswith("/pro")]
    moved = [{"source": f"/research/digital-product-passport/{i}",
              "destination": f"/research/digital-product-passport/suppliers/{i}",
              "permanent": True} for i in sorted(ids)]
    conf["redirects"] = keep + moved
    with open(VERCEL, "w", encoding="utf-8") as fh:
        json.dump(conf, fh, indent=2)
        fh.write("\n")
    return len(moved)


def main():
    rows, counts, cap = load()
    os.makedirs(OUT, exist_ok=True)

    with open(os.path.join(HERE, "digital-product-passport", "suppliers.html"), "w", encoding="utf-8") as fh:
        fh.write(directory_html(rows, counts, cap))

    profiles = claims = 0
    for r in rows:
        with open(os.path.join(OUT, f"{r['id']}.html"), "w", encoding="utf-8") as fh:
            fh.write(profile_html(r, counts, cap))
        profiles += 1
        if r["entity_type"] not in NON_COMMERCIAL:
            d = os.path.join(OUT, r["id"])
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "claim.html"), "w", encoding="utf-8") as fh:
                fh.write(claim_html(r, counts))
            claims += 1

    # retire the old flat profile pages now that they redirect
    old = 0
    for r in rows:
        p = os.path.join(HERE, "digital-product-passport", f"{r['id']}.html")
        if os.path.exists(p):
            os.remove(p)
            old += 1

    n = write_redirects([r["id"] for r in rows])

    print(f"/suppliers                     1 page")
    print(f"/suppliers/<id>              {profiles:3d} profiles")
    print(f"/suppliers/<id>/claim        {claims:3d} claim pages")
    print(f"removed old flat profiles    {old:3d}")
    print(f"vercel redirects written     {n:3d}")
    print(f"\n  {counts['organisations']} organisations, {counts['commercial_suppliers']} commercial "
          f"suppliers, {counts['countries']} countries")


if __name__ == "__main__":
    main()
