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
    rows = payload["suppliers"]

    # Every public total is computed from the rows, never read from the file.
    # A stored counts block goes stale the moment a supplier is added - which is
    # exactly what happened when four researched rows landed and the header kept
    # announcing the old figure.
    def sourced(r):
        return str(r.get("country_source", "")).startswith("http")
    counts = {
        "organisations": len(rows),
        "commercial_suppliers": sum(1 for r in rows if r["entity_type"] not in NON_COMMERCIAL),
        "countries": len({r["hq_country"] for r in rows if r.get("hq_country")}),
        "countries_primary_sourced": len({r["hq_country"] for r in rows
                                          if r.get("hq_country") and sourced(r)}),
        "verified": sum(1 for r in rows if r.get("confidence") == "verified"),
        "with_disclosed_funding": sum(1 for r in rows if r.get("total_disclosed_funding")),
    }
    return rows, counts, cap


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
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="yellow3 lab" />
  <meta property="og:image" content="https://yellow3.io/og/og-digital-product-passport-v2.png" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />{og_extra}
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

STATUS_LABEL = {
    "verified": "Public evidence found",
    "company": "Company states",
    "not-found": "No public evidence found",
    "unassessed": "Not yet assessed",
}


def profile_html(r, counts, cap):
    """Supplier profile, built to the approved v4 handoff.

    Two layers behind two tabs: what yellow3 lab established from public sources,
    and what the company says about itself. They never merge, and the company
    layer cannot alter a single researched field."""
    results = cap.get(r["id"], {})
    nc = r["entity_type"] in NON_COMMERCIAL
    kind, curl, cdate = source_state(r["country_source"])
    # A date on this page means a human looked on that date. Never today's date:
    # rebuilding the site is not research, and stamping the build date here would
    # silently re-date 183 provenance claims every time the generator runs.
    checked = cdate or pretty_date(r.get("source_date") or "") or "Not recorded"
    sid = r["id"]
    name = r["name"]

    site = (f'<a class="website" href="{e(r["website"])}" target="_blank" rel="noopener">{e(r["domain"])} &#8599;</a>'
            if r["website"] else
            '<span class="website">No official website established</span>' if kind == "not_found" else
            '<span class="website">Website not yet assessed</span>')

    if r["hq_country"]:
        place = ", ".join([x for x in (r["hq_city"], r["hq_country"]) if x])
        hq_note = "Primary source" if kind == "url" else "Stated by the company"
    elif kind == "not_found":
        place, hq_note = "Not publicly established", "No public source found"
    else:
        place, hq_note = "Not yet assessed", "No check recorded"

    # Four facts. Absence is a dated research finding, never an empty cell and
    # never a negative.
    def fact(label, value, note_present, note_absent, src=""):
        k, u, d = source_state(src)
        if value:
            note = (f'<small><a href="{e(u)}" target="_blank" rel="noopener">Source &#8599;</a></small>'
                    if k == "url" else f"<small>{e(note_present)}</small>")
            return f"<article><span>{e(label)}</span><strong>{e(value)}</strong>{note}</article>"
        if k == "not_found":
            return (f"<article><span>{e(label)}</span><strong>Not disclosed</strong>"
                    f"<small>Checked {e(d)}</small></article>")
        return (f"<article><span>{e(label)}</span><strong>{e(note_absent)}</strong>"
                f"<small>No public disclosure found</small></article>")

    sector_names = [SECTOR_LABEL.get(s, s.title()) for s in r.get("sectors_list", [])]
    sector_head = " &middot; ".join(sector_names[:2]) if sector_names else ""
    sector_tail = ("Also " + ", ".join(sector_names[2:]).lower()) if len(sector_names) > 2 else "As recorded"

    facts = "".join([
        f'<article><span>Headquarters</span><strong>{e(place)}</strong><small>{e(hq_note)}</small></article>',
        (f'<article><span>Sectors</span><strong>{sector_head}</strong><small>{e(sector_tail)}</small></article>'
         if sector_names else
         '<article><span>Sectors</span><strong>Not recorded</strong><small>No public disclosure found</small></article>'),
        # the data stores these lower case; only the presentation changes
        fact("Ownership", (r["ownership"][:1].upper() + r["ownership"][1:]) if r["ownership"] else "",
             "Independently recorded", "Not disclosed"),
        fact("Funding", r["total_disclosed_funding"] or r["funding_stage"].replace("-", " ").capitalize(),
             "Independently recorded", "Not disclosed", r["funding_source"]),
    ])

    # ---- capability: ten checks, each carrying its own evidence record
    STATE_CLASS = {"verified": "verified", "company_states": "company", "not_found": "not-found"}
    checks = []
    for i, cname in enumerate(CRITERIA, 1):
        rec = results.get(f"c{i:02d}") or {}
        st = rec.get("state", "")
        checks.append({
            "n": i,
            "name": cname,
            "state": STATE_CLASS.get(st, "unassessed"),
            "date": pretty_date(rec.get("checked_date", "")) or "",
            "artifact": rec.get("artifact", "") or "",
            "note": rec.get("note", "") or "",
            "url": rec.get("evidence_url", "") or "",
        })

    if nc or not results:
        capability = ""
    else:
        rows = ""
        for c in checks:
            rows += (
                f'<button type="button" class="capability-row" data-check="{c["n"] - 1}">'
                f'<span class="row-number">{c["n"]:02d}</span>'
                f'<strong>{e(c["name"])}</strong>'
                f'<span class="status status-{c["state"]}"><span class="status-dot"></span>'
                f'<span>{STATUS_LABEL[c["state"]]}</span><time>{e(c["date"])}</time></span>'
                f'<span class="row-arrow">&#8599;</span></button>')
        capability = f"""
        <section class="capability-section">
          <header>
            <div>
              <p class="eyebrow"><i></i> Capability evidence</p>
              <h2>Ten independent checks</h2>
            </div>
            <p>No composite score. Select a row to inspect the finding.</p>
          </header>
          <div class="capability-layout">
            <div class="capability-list">{rows}</div>
            <aside class="evidence-panel" id="evidencePanel">
              <p class="panel-kicker" id="panelKicker">Selected finding &middot; 01</p>
              <h3 id="panelName">{e(checks[0]["name"])}</h3>
              <div class="status status-{checks[0]["state"]}" id="panelStatus">
                <span class="status-dot"></span><span>{STATUS_LABEL[checks[0]["state"]]}</span>
                <time>{e(checks[0]["date"])}</time></div>
              <div class="panel-rule"></div>
              <span class="panel-label">What was checked</span>
              <p>Public product pages, technical documentation, standards references and
              relevant company disclosures.</p>
              <span class="panel-label">Finding</span>
              <p id="panelFinding"></p>
              <a id="panelLink" href="/research/digital-product-passport/suppliers#framework">View search record &#8599;</a>
            </aside>
          </div>
        </section>"""

    unassessed_note = "" if (nc or results) else """
        <section class="capability-section">
          <header>
            <div>
              <p class="eyebrow"><i></i> Capability evidence</p>
              <h2>Not yet assessed</h2>
            </div>
            <p>Ten independent checks. No composite score.</p>
          </header>
          <p class="intro-copy">No check has been run against this supplier yet. Assessments
          are published as they are completed, each with its own source and date. An absent
          assessment is not a finding about the company.</p>
        </section>"""

    claim_href = f"/research/digital-product-passport/suppliers/{e(sid)}/claim"
    company_tab = "" if nc else (
        f'<button type="button" class="company-tab" data-tab="company">'
        f'<span>02</span> Supplied by {e(name)}</button>')

    company_panel = "" if nc else f"""
        <section class="company-layer" id="companyPanel" data-supplier="{e(sid)}" hidden>
          <p class="eyebrow yellow"><i></i> Supplied by {e(name)}</p>
          <div class="company-content" id="companyBody">
            <div>
              <h2>No company-supplied profile received.</h2>
              <p>This layer is reserved for information provided directly by {e(name)}. It
              never changes yellow3 lab's independent research.</p>
            </div>
            <a class="claim-button" href="{claim_href}">Claim this profile &#8594;</a>
          </div>
        </section>"""

    src_cell = (f'<a href="{e(r["evidence_url"])}" target="_blank" rel="noopener">{e(r["source"])} &#8599;</a>'
                if r["evidence_url"] else e(r["source"]) or "Not recorded")
    claim_foot = "" if nc else f'<a href="{claim_href}">Claim this profile &#8599;</a>'

    body = f"""{SITE_NAV}<main class="dpp-profile">
  <div class="page-shell">
    <a class="back-link" href="/research/digital-product-passport/suppliers">&#8592; All suppliers</a>

    <section class="profile-hero">
      <div class="identity">
        <div class="monogram" id="profileMonogram">{e(initials(name))}</div>
        <div>
          <div class="title-line">
            <h1>{e(name)}</h1>
            <span class="type-chip">{e(TYPE_LABEL.get(r["entity_type"], r["entity_type"]))}</span>
          </div>
          {site}
          <p class="checked">Research record checked {e(checked)}</p>
        </div>
      </div>
      <div class="hero-meta">
        <span>Supplier profile</span>
        <strong>{e(r["hq_country"] or "Not established")}</strong>
        <span>First recorded {e(pretty_date(r["source_date"]))}</span>
      </div>
    </section>

    <nav class="layer-tabs" aria-label="Profile layers">
      <button type="button" class="active" data-tab="research"><span>01</span> yellow3 lab research</button>
      {company_tab}
    </nav>

    <div id="researchPanel">
      <section class="research-intro">
        <div>
          <p class="eyebrow"><i></i> Independently researched</p>
          <h2>A public evidence record,<br />not a supplier score.</h2>
        </div>
        <p class="intro-copy">Ten independent checks show what yellow3 lab could establish
        from public sources on the date shown. Every finding keeps its provenance.</p>
      </section>

      <section class="facts-grid">{facts}</section>
      {capability}{unassessed_note}
    </div>
{company_panel}
    <footer class="register-footer">
      <div><span>Register evidence</span><strong>{src_cell}</strong></div>
      <div><span>First recorded</span><strong>{e(pretty_date(r["source_date"]))}</strong></div>
      <div><span>Last checked</span><strong>{e(checked)}</strong></div>
      <a href="/research/digital-product-passport/suppliers#method">Research method &#8599;</a>
      <a href="/research/digital-product-passport/suppliers#corrections">Suggest a correction &#8599;</a>
      {claim_foot}
    </footer>
  </div>
</main>
""" + SITE_FOOTER

    checks_json = json.dumps(checks, ensure_ascii=False, separators=(",", ":"))
    script = ("""
<script id="checkData" type="application/json">""" + checks_json + """</script>
<script>
(function(){
  var CHECKS=JSON.parse(document.getElementById('checkData').textContent);
  var LABEL={verified:'Public evidence found',company:'Company states',
             'not-found':'No public evidence found',unassessed:'Not yet assessed'};

  // ---- layers
  var tabs=document.querySelectorAll('.layer-tabs button'),
      research=document.getElementById('researchPanel'),
      company=document.getElementById('companyPanel');
  Array.prototype.forEach.call(tabs,function(b){
    b.addEventListener('click',function(){
      var want=b.dataset.tab;
      Array.prototype.forEach.call(tabs,function(x){ x.classList.toggle('active',x===b); });
      if(research) research.hidden = want!=='research';
      if(company) company.hidden = want!=='company';
    });
  });

  // ---- capability rows and their evidence record
  var rows=document.querySelectorAll('.capability-row'),
      kicker=document.getElementById('panelKicker'), pname=document.getElementById('panelName'),
      pstatus=document.getElementById('panelStatus'), pfind=document.getElementById('panelFinding'),
      plink=document.getElementById('panelLink');
  function pad(n){ return (n<10?'0':'')+n; }
  function finding(c){
    // the real artifact and note first; the state sentence only when we have neither
    if(c.artifact && c.note) return c.artifact+'. '+c.note;
    if(c.artifact) return c.artifact;
    if(c.note) return c.note;
    if(c.state==='verified') return 'A specific public disclosure was located and recorded in the research trail.';
    if(c.state==='company') return 'The capability is described by the company. Independent supporting documentation was not established in this check.';
    if(c.state==='not-found') return 'No specific public disclosure was located during this research check. This is a dated finding, not a claim of absence.';
    return 'This check has not been run against this supplier yet.';
  }
  function select(i){
    var c=CHECKS[i]; if(!c||!pname) return;
    kicker.textContent='Selected finding \\u00b7 '+pad(c.n);
    pname.textContent=c.name;
    pstatus.className='status status-'+c.state;
    pstatus.innerHTML='';
    var dot=document.createElement('span'); dot.className='status-dot'; pstatus.appendChild(dot);
    var lab=document.createElement('span'); lab.textContent=LABEL[c.state]||LABEL.unassessed; pstatus.appendChild(lab);
    var t=document.createElement('time'); t.textContent=c.date; pstatus.appendChild(t);
    pfind.textContent=finding(c);
    plink.href=c.url||'/research/digital-product-passport/suppliers#framework';
    plink.textContent=c.url?'View search record \\u2197':'View assessment framework \\u2197';
    Array.prototype.forEach.call(rows,function(x){ x.classList.toggle('selected', x.dataset.check==String(i)); });
  }
  Array.prototype.forEach.call(rows,function(b){
    b.addEventListener('click',function(){ select(Number(b.dataset.check)); });
  });
  if(rows.length) select(0);

  // ---- the company's own layer, written by the company, fetched at runtime
  if(company){
    var sid=company.dataset.supplier, box=document.getElementById('companyBody'),
        mono=document.getElementById('profileMonogram'), tab=document.querySelector('.company-tab');
    fetch('/api/supplied?id='+encodeURIComponent(sid)).then(function(r){return r.json();})
      .then(function(d){
        var s=d&&d.supplied; if(!s) return;
        if(mono && s.logo_url){
          var mi=document.createElement('img'); mi.src=s.logo_url; mi.alt='';
          mono.textContent=''; mono.appendChild(mi);
        }
        var left=document.createElement('div');
        if(s.description){ var h=document.createElement('h2'); h.textContent=s.description; left.appendChild(h); }
        if(s.sectors&&s.sectors.length){
          var p=document.createElement('p'); p.textContent='Sectors: '+s.sectors.join(', '); left.appendChild(p);
        }
        var stamp=document.createElement('p');
        stamp.textContent='Supplied by the company'+(s.updated_at?', updated '+s.updated_at:'')
          +'. Not verified by yellow3 lab.';
        left.appendChild(stamp);
        box.textContent=''; box.appendChild(left);
        if(s.contact_url){
          var a=document.createElement('a'); a.className='claim-button'; a.href=s.contact_url;
          a.target='_blank'; a.rel='noopener nofollow'; a.textContent='Contact this company \\u2192';
          box.appendChild(a);
        }
        if(tab) tab.classList.add('has-content');
      }).catch(function(){});
  }
})();
</script>
""")

    jsonld = ('\n  <script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "ProfilePage",
        "name": f"{name} - DPP Supplier Register",
        "url": f"https://yellow3.io/research/digital-product-passport/suppliers/{sid}",
        "isPartOf": {"@type": "Dataset", "name": "yellow3 DPP Supplier Register",
                     "url": "https://yellow3.io/research/digital-product-passport/suppliers"},
        "about": {k: v for k, v in {
            "@type": "Organization", "name": name,
            "url": r["website"] or None,
            "address": ({"@type": "PostalAddress", "addressCountry": r["hq_country"],
                         **({"addressLocality": r["hq_city"]} if r["hq_city"] else {})}
                        if r["hq_country"] and kind == "url" else None),
        }.items() if v},
        "publisher": {"@type": "Organization", "name": "yellow3 lab", "url": "https://yellow3.io"},
    }, ensure_ascii=False, separators=(",", ":")) + "</script>")

    out = page(f"{name} - DPP Supplier Register - yellow3",
               f"{name}: Digital Product Passport supplier profile. Independently sourced "
               f"identity, headquarters and evidence, recorded by yellow3 lab.",
               f"https://yellow3.io/research/digital-product-passport/suppliers/{sid}",
               body, script, jsonld)
    return out.replace(
        '<link rel="stylesheet" href="/research/digital-product-passport/register.css" />',
        '<link rel="stylesheet" href="/research/digital-product-passport/register.css" />\n'
        '  <link rel="stylesheet" href="/research/digital-product-passport/profile-v4.css" />')


# ---------------------------------------------------------------- claim

def claim_html(r, counts):
    """The claim page, built to the approved v1 handoff.

    The design's own client-side check is NOT the authorisation: the server
    decides, and answers identically either way so the form cannot be used to
    work out who works where. That behaviour predates this design and the
    handoff asks for it to be preserved."""
    sid = r["id"]
    name = r["name"]
    dom = r["domain"]

    # 5 commercial rows have no domain on record. The approved card shows the
    # domain and the state beside it; with nothing on record it says so rather
    # than promising a check we cannot run.
    if dom:
        domain_line = (f'<p class="domain"><span class="domain-dot"></span>{e(dom)}</p>')
        domain_state = "DOMAIN ON RECORD"
        field_help = f"It must end in @{e(dom)}"
        placeholder = f"you@{e(dom)}"
        lede = (f"Confirm that you represent {e(name)} using your company email. If the domain "
                f"matches our research record, access is granted immediately.")
    else:
        domain_line = '<p class="domain"><span class="domain-dot no-domain"></span>No domain recorded yet</p>'
        domain_state = "NO DOMAIN ON RECORD"
        field_help = "Use your company email, not a personal mailbox"
        placeholder = "you@yourcompany.com"
        lede = (f"We have no domain on record for {e(name)} yet, so this claim cannot be "
                f"confirmed automatically. Send your company email and it reaches us directly: "
                f"we verify it by hand and record the domain.")

    body = f"""{SITE_NAV}<main class="dpp-claim">
  <div class="page-shell">
    <a class="back-link" href="/research/digital-product-passport/suppliers/{e(sid)}"><span>&#8592;</span> Back to profile</a>
    <section class="claim-grid" aria-labelledby="claim-title">
      <div class="main-column">
        <div class="title-block">
          <p class="eyebrow">SUPPLIER CLAIM</p>
          <h1 id="claim-title">Claim {e(name)}</h1>
          <p class="lede">{lede}</p>
        </div>

        <section class="claim-card">
          <div class="company-row">
            <div class="company-mark">{e(initials(name))}</div>
            <div>
              <p class="field-kicker">PROFILE TO CLAIM</p>
              <h2>{e(name)}</h2>
              {domain_line}
            </div>
            <span class="domain-state">{domain_state}</span>
          </div>
          <div class="card-rule"></div>

          <div class="success" role="status" id="claimSuccess" hidden>
            <span class="success-icon">&#10003;</span>
            <div>
              <p class="success-title" id="successTitle">Work email received</p>
              <p id="successBody"></p>
            </div>
          </div>

          <form id="claimForm" novalidate>
            <label for="work-email">Your work email</label>
            <p class="field-help">{field_help}</p>
            <div class="input-row">
              <div class="input-wrap" id="inputWrap">
                <span>@</span>
                <input id="work-email" type="email" placeholder="{placeholder}" autocomplete="email" />
              </div>
              <button type="submit">Claim this profile <span>&#8594;</span></button>
            </div>
            <p class="privacy-note">No account setup and no manual approval when the domain matches.</p>
            <p class="error" role="alert" id="claimError" hidden></p>
          </form>
        </section>

        <div class="assurance-grid">
          <article><span class="number">01</span><h3>Immediate domain check</h3>
            <p>We match your work email to the company domain already recorded in the register.</p></article>
          <article><span class="number">02</span><h3>Your layer stays labelled</h3>
            <p>Anything you add appears separately as company-supplied information, with its own date.</p></article>
          <article><span class="number">03</span><h3>Our research stays ours</h3>
            <p>Independent findings and sources cannot be overwritten. Corrections remain reviewable.</p></article>
        </div>
      </div>

      <aside class="side-column">
        <section class="what-next">
          <p class="side-eyebrow">AFTER YOU CLAIM</p>
          <h2>Add {e(name)}&#8217;s own information</h2>
          <p class="side-copy">A claimed supplier can add a logo, a concise description, a public
          contact link and sectors.</p>
          <div class="preview-card">
            <span class="supplied-label">SUPPLIED BY {e(name.upper())}</span>
            <div class="preview-company">
              <div class="mini-mark">{e(initials(name))}</div>
              <div><strong>{e(name)}</strong><span>Company information layer</span></div>
            </div>
            <div class="preview-lines"><span></span><span></span></div>
          </div>
        </section>
        <section class="boundary">
          <p class="side-eyebrow">EVIDENCE BOUNDARY</p>
          <div class="key-row"><i class="white-key"></i><span>Researched independently by yellow3 lab</span></div>
          <div class="key-row"><i class="yellow-key"></i><span>Supplied directly by {e(name)}</span></div>
          <p class="boundary-note">The two layers remain separate on the public profile.</p>
        </section>
        <p class="support">The domain is wrong or you cannot access a company inbox?
          <a href="#" id="claimSupport">Contact register support &#8594;</a></p>
      </aside>
    </section>
  </div>
</main>
""" + SITE_FOOTER

    script = """
<script>
(function(){
  var PUBLIC=['gmail.com','googlemail.com','outlook.com','hotmail.com','live.com','yahoo.com',
    'yahoo.co.uk','icloud.com','me.com','mac.com','aol.com','proton.me','protonmail.com',
    'gmx.com','gmx.net','msn.com','yandex.com','zoho.com','fastmail.com','hey.com'];
  var f=document.getElementById('claimForm'), i=document.getElementById('work-email'),
      wrap=document.getElementById('inputWrap'), err=document.getElementById('claimError'),
      ok=document.getElementById('claimSuccess'), okBody=document.getElementById('successBody'),
      id=document.body.dataset.supplier, noDomain=!!document.body.dataset.nodomain;

  function fail(t){ err.hidden=false; err.textContent=t; wrap.classList.add('has-error'); }
  function clear(){ err.hidden=true; wrap.classList.remove('has-error'); }

  f.addEventListener('submit',function(ev){
    ev.preventDefault();
    var email=(i.value||'').trim().toLowerCase(), domain=email.split('@')[1];
    if(!domain||email.indexOf('@')<1){ fail('Enter a valid work email address.'); return; }
    if(PUBLIC.indexOf(domain)>-1){ fail('Personal mailboxes are not accepted. Use your company email.'); return; }
    clear();
    // The server decides, and answers the same either way, so this form cannot
    // be used to find out who works where. The prototype's client-side domain
    // test is deliberately not the gate.
    fetch('/api/claim',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email:email,supplier:id})})
      .then(function(){
        okBody.textContent = noDomain
          ? 'We will verify it by hand, record the domain, and be in touch.'
          : 'If ' + domain + ' is the domain on record for this company, a link to the '
            + 'Company Information Editor is on its way. If it is not, nothing was sent.';
        f.hidden=true; ok.hidden=false;
      })
      .catch(function(){ fail('Something went wrong. Please try again.'); });
  });

  document.getElementById('claimSupport').addEventListener('click',function(ev){
    ev.preventDefault();
    window.location.href='mailto:'+'hello'+String.fromCharCode(64)+'yellow3.io'
      +'?subject='+encodeURIComponent('DPP Supplier Register claim: '+document.title.split(' - ')[0]);
  });
})();
</script>
"""
    out = page(f"Claim {name} - DPP Supplier Register - yellow3",
               f"Claim the {name} profile on the yellow3 DPP Supplier Register. "
               f"Confirmed by work email domain, no account required.",
               f"https://yellow3.io/research/digital-product-passport/suppliers/{sid}/claim",
               body, script)
    out = out.replace(
        '<link rel="stylesheet" href="/research/digital-product-passport/register.css" />',
        '<link rel="stylesheet" href="/research/digital-product-passport/register.css" />\n'
        '  <link rel="stylesheet" href="/research/digital-product-passport/claim-v1.css" />')
    nod = '' if dom else ' data-nodomain="1"'
    out = out.replace("<body>", f'<body data-supplier="{e(sid)}"{nod}>')
    # a company action, not research - keep it out of the index
    return out.replace('<meta property="og:type" content="website" />',
                       '<meta property="og:type" content="website" />\n  <meta name="robots" content="noindex,follow" />')


# ---------------------------------------------------------------- add

def add_html(counts):
    """"Add your company" - approved v1 handoff.

    For a company NOT in the register asking to be researched. Nothing submitted
    here is published; the backend queues it as a research lead. The prototype's
    knownProfiles demo map is removed: whether a domain is already recorded comes
    from the backend, which discloses it only for domains the register already
    publishes."""
    body = f"""{SITE_NAV}<main class="dpp-add">
  <section class="page-intro">
    <div class="intro-inner">
      <a class="back-link" href="/research/digital-product-passport/suppliers">
        <span aria-hidden="true">&#8592;</span> Back to supplier directory</a>
      <p class="breadcrumb">Research / Digital Product Passport / Supplier Register / Add your company</p>
      <div class="intro-grid">
        <div>
          <h1>Put your company<br />forward for research.</h1>
        </div>
        <div class="intro-copy">
          <p>Not in the DPP Supplier Register? Tell us the company name and use a work email.
          That starts a research request, not a listing.</p>
          <p class="plain-note">Nothing you submit is published.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="request-section">
    <div class="request-grid">
      <div class="request-content">
        <div class="section-heading">
          <span>01</span>
          <div>
            <p class="eyebrow">THE REQUEST</p>
            <h2>Two details. One honest research queue.</h2>
          </div>
        </div>
        <div class="expectation-list">
          <article><span>01</span><div><h3>You suggest the company</h3>
            <p>The work email establishes the company domain. It is never typed twice, and
            personal mailboxes are refused.</p></div></article>
          <article><span>02</span><div><h3>We research it ourselves</h3>
            <p>We look for public evidence of DPP capability. A suggestion does not create a
            profile and does not move anyone ahead.</p></div></article>
          <article><span>03</span><div><h3>We reply either way</h3>
            <p>If the evidence supports an entry, we add it. If it does not, we tell you.
            There is no fee and no paid priority.</p></div></article>
        </div>
      </div>

      <div class="request-card-wrap">
        <form class="request-card" id="addForm" novalidate>
          <div class="card-heading">
            <p class="eyebrow">COMPANY-SUPPLIED REQUEST</p>
            <span>2 fields</span>
          </div>
          <h2>Add your company</h2>
          <p class="card-lede">We use these details only to identify the company and reply to
          the request.</p>

          <div class="field">
            <label for="company">Company name</label>
            <input id="company" type="text" placeholder="Your company" autocomplete="organization" />
          </div>

          <div class="field">
            <label for="work-email">Work email</label>
            <input id="work-email" type="email" placeholder="you@company.com"
                   autocomplete="email" aria-describedby="email-help form-error" />
            <div class="field-meta">
              <span id="email-help">Personal email addresses are refused.</span>
              <strong id="domainEcho" hidden></strong>
            </div>
          </div>

          <div class="form-error" id="formError" role="alert" hidden>
            <span>!</span><p id="formErrorText"></p>
          </div>

          <button class="submit-button" type="submit">
            <span>Send for research</span><span aria-hidden="true">&#8594;</span></button>
          <p class="form-note">Free to suggest. Free to be listed. No verification product is
          being sold.</p>
        </form>

        <section class="result-card queued-card" id="queuedCard" aria-live="polite" hidden>
          <div class="result-label">QUEUED FOR RESEARCH</div>
          <p class="result-number">01</p>
          <h2 id="queuedName">Your company is in the next research pass.</h2>
          <p class="result-lede">Your suggestion is not a listing. We add a company only when
          we can establish it from public evidence ourselves.</p>
          <div class="help-box">
            <span>WHAT HELPS MOST</span>
            <p>A public product page describing DPP capability, technical documentation, an
            example passport, or a named customer pilot.</p>
          </div>
          <div class="result-footer">
            <p>We reply either way. We never charge a company to be included.</p>
            <button type="button" data-reset>Submit another company</button>
          </div>
        </section>

        <section class="result-card existing-card" id="existingCard" aria-live="polite" hidden>
          <div class="result-label">PROFILE ALREADY RECORDED</div>
          <p class="result-number">01</p>
          <h2>We already hold a profile for this domain.</h2>
          <p class="result-lede">It may be recorded under a name you did not recognise in the
          directory.</p>
          <article class="existing-profile">
            <div class="profile-initials" id="existingInitials"></div>
            <div>
              <span>EXISTING REGISTER PROFILE</span>
              <h3 id="existingName"></h3>
              <p id="existingDomain"></p>
            </div>
          </article>
          <a class="claim-button" id="existingClaim" href="#">
            <span>Claim this profile</span><span aria-hidden="true">&#8594;</span></a>
          <div class="result-footer">
            <p>Claiming proves control of the domain. It does not change yellow3 lab's
            independent research.</p>
            <button type="button" data-reset>Use another email</button>
          </div>
        </section>
      </div>
    </div>
  </section>

  <section class="meaning-section">
    <div class="meaning-inner">
      <div class="section-heading">
        <span>02</span>
        <div>
          <p class="eyebrow">WHAT INCLUSION MEANS</p>
          <h2>Evidence first. Company voice second.</h2>
        </div>
      </div>
      <div class="meaning-grid">
        <article class="research-layer">
          <div class="layer-title"><i class="key-white"></i><span>INDEPENDENT RESEARCH</span></div>
          <h3>Every fact sourced, dated and inspectable.</h3>
          <p>yellow3 lab establishes the identity, headquarters, ownership, funding and
          capability findings from public evidence. Blank space remains blank when evidence
          is absent.</p>
        </article>
        <article class="company-layer">
          <div class="layer-title"><i class="key-yellow"></i><span>COMPANY-SUPPLIED INFORMATION</span></div>
          <h3>Your information stays visibly yours.</h3>
          <p>After a profile is claimed, the company can add its own information in a separate
          pale-yellow layer. It never overwrites or becomes yellow3 lab research.</p>
        </article>
      </div>
      <div class="evidence-key" aria-label="Information layers">
        <div><i class="key-white"></i><span>Researched independently by yellow3 lab</span></div>
        <div><i class="key-yellow"></i><span>Supplied directly by the company</span></div>
      </div>
    </div>
  </section>

  <section class="independence-section">
    <div class="independence-inner">
      <p class="eyebrow">THE INDEPENDENCE RULE</p>
      <blockquote>No fee to be listed. No paid priority for asking. Nothing sold that
      resembles verification.</blockquote>
      <a href="/research/digital-product-passport/suppliers#method">Read the research method
        <span aria-hidden="true">&#8594;</span></a>
    </div>
  </section>
</main>
""" + SITE_FOOTER

    script = r"""
<script>
(function(){
  var PUBLIC=['gmail.com','googlemail.com','outlook.com','hotmail.com','live.com','yahoo.com',
    'yahoo.co.uk','icloud.com','me.com','mac.com','aol.com','proton.me','protonmail.com',
    'gmx.com','gmx.net','msn.com','yandex.com','zoho.com','fastmail.com','hey.com'];
  var f=document.getElementById('addForm'),
      company=document.getElementById('company'), email=document.getElementById('work-email'),
      echo=document.getElementById('domainEcho'), err=document.getElementById('formError'),
      errText=document.getElementById('formErrorText'),
      queued=document.getElementById('queuedCard'), queuedName=document.getElementById('queuedName'),
      existing=document.getElementById('existingCard');

  function domainOf(v){
    var p=String(v||'').trim().toLowerCase().split('@');
    return (p.length===2 && p[1].indexOf('.')>0) ? p[1] : '';
  }
  function fail(t){ err.hidden=false; errText.textContent=t; email.classList.add('has-error'); }
  function clear(){ err.hidden=true; email.classList.remove('has-error'); }
  function show(card){ f.hidden=true; queued.hidden=true; existing.hidden=true; card.hidden=false; }

  email.addEventListener('input',function(){
    clear();
    var d=domainOf(email.value);
    echo.hidden=!d; echo.textContent = d ? 'Domain: '+d : '';
  });
  company.addEventListener('input',clear);

  Array.prototype.forEach.call(document.querySelectorAll('[data-reset]'),function(b){
    b.addEventListener('click',function(){
      company.value=''; email.value=''; echo.hidden=true; clear();
      queued.hidden=true; existing.hidden=true; f.hidden=false; company.focus();
    });
  });

  f.addEventListener('submit',function(ev){
    ev.preventDefault();
    var name=(company.value||'').trim(), addr=(email.value||'').trim().toLowerCase();
    if(!name){ fail('Enter the company name.'); return; }
    if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(addr)){ fail('Enter a valid work email address.'); return; }
    var dom=domainOf(addr);
    if(PUBLIC.indexOf(dom)>-1){
      fail('Use your company email. Personal mailboxes cannot be used because a work domain '
        + 'is how we prevent unauthorised submissions.'); return;
    }
    clear();
    // The register decides. There is no client-side lookup: whether a domain is
    // already recorded comes back from the server, and only for domains the
    // register already publishes.
    fetch('/api/suggest',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({company:name,email:addr})})
      .then(function(r){ return r.json(); })
      .then(function(d){
        if(d && d.existing){
          document.getElementById('existingName').textContent=d.existing.name;
          document.getElementById('existingDomain').textContent=dom;
          document.getElementById('existingClaim').href=d.existing.claim_url;
          // the register draws a two-letter mark everywhere; a one-word name must
          // not become a single letter only on this page
          var parts=d.existing.name.split(/[\s.\-_/]+/).filter(Boolean);
          document.getElementById('existingInitials').textContent=(parts.length>1
            ? parts[0][0]+parts[1][0]
            : (parts[0]||'??').slice(0,2)).toUpperCase();
          show(existing); return;
        }
        queuedName.textContent=name+' is in the next research pass.';
        show(queued);
      })
      .catch(function(){ fail('Something went wrong. Please try again.'); });
  });
})();
</script>
"""
    out = page("Add your company - DPP Supplier Register - yellow3",
               "Ask yellow3 lab to research your company for the DPP Supplier Register. "
               "Two details, no fee, and nothing is published without public evidence.",
               "https://yellow3.io/research/digital-product-passport/suppliers/add",
               body, script)
    return out.replace(
        '<link rel="stylesheet" href="/research/digital-product-passport/register.css" />',
        '<link rel="stylesheet" href="/research/digital-product-passport/register.css" />\n'
        '  <link rel="stylesheet" href="/research/digital-product-passport/add-v1.css" />')


# ---------------------------------------------------------------- edit

def edit_html(r, counts):
    """The company's own editor, built to the approved v2 handoff design.

    Reached only from the emailed claim link, and the session it carries
    authorises this one row. Nobody at yellow3 approves anything here - that is
    the point of the design. The page carries no menu of its own: the site nav
    above it is the only navigation, as the handoff requires."""
    sid = r["id"]
    name = r["name"]
    type_label = TYPE_LABEL.get(r["entity_type"], r["entity_type"])

    body = f"""{SITE_NAV}<main class="dpp-edit">
  <section class="intro">
    <div class="intro-inner">
      <a class="back-link" href="/research/digital-product-passport/suppliers/{e(sid)}">
        <span aria-hidden="true" class="arrow">&#8592;</span> Back to {e(name)} profile</a>

      <div class="intro-grid">
        <div>
          <p class="eyebrow">COMPANY-SUPPLIED LAYER</p>
          <h1>Add {e(name)}'s<br />own information</h1>
        </div>
        <div class="intro-copy">
          <p>This page publishes only the information {e(name)} supplies. It appears in a
          separately labelled layer on the public profile. yellow3 lab's independent research
          remains unchanged and cannot be edited here.</p>
          <div class="evidence-key" aria-label="Evidence key">
            <div><span class="swatch"></span><span>Researched independently by yellow3 lab</span></div>
            <div><span class="swatch swatch-supplied"></span><span>Supplied directly by {e(name)}</span></div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section class="workspace">
    <div class="workspace-grid">
      <form class="form-panel" id="editForm">
        <div class="panel-heading">
          <span class="panel-index">01</span>
          <div>
            <p class="eyebrow dark">YOUR PUBLIC INFORMATION</p>
            <p class="panel-note">Everything inside this yellow field is published as supplied
            by {e(name)}.</p>
          </div>
        </div>

        <p class="claim-message" role="status" id="editMsg" hidden></p>

        <fieldset>
          <legend><span>A</span>Company identity</legend>
          <div class="field-grid identity-grid">
            <div class="field">
              <label id="logoLabel">Logo</label>
              <input id="edLogo" class="visually-hidden" type="file"
                     accept=".png,.jpg,.jpeg,.webp,.svg" aria-labelledby="logoLabel" />
              <button class="upload" type="button" id="edUploadBtn">
                <span class="upload-mark"><img id="edLogoPrev" alt="" hidden /><span id="edLogoPlus" aria-hidden="true">+</span></span>
                <span class="upload-copy">
                  <strong id="edLogoName">Upload company logo</strong>
                  <small>PNG, JPG, WebP or SVG &middot; Maximum 400 KB</small>
                </span>
                <span class="upload-action"><span id="edUploadVerb">Choose file</span>
                  <span aria-hidden="true" class="arrow">&#8594;</span></span>
              </button>
              <button type="button" class="edit-remove" id="edRemoveLogo" hidden>Remove logo</button>
            </div>

            <div class="field">
              <div class="label-row">
                <label for="edDesc">One-line description</label>
                <span><span id="edCount">0</span> / 160</span>
              </div>
              <textarea id="edDesc" maxlength="160" rows="4"
                        placeholder="What does {e(name)} do?"></textarea>
            </div>
          </div>
        </fieldset>

        <fieldset>
          <legend><span>B</span>Public contact</legend>
          <div class="field-grid">
            <div class="field">
              <label for="edContact">Contact link</label>
              <input id="edContact" type="url" inputmode="url"
                     placeholder="https://yourcompany.com/contact" />
              <small>Must use a secure https address.</small>
            </div>
            <div class="field">
              <div class="label-row">
                <label for="edSectors">Sectors</label>
                <span><span id="edTagCount">0</span> / 8</span>
              </div>
              <div class="tag-entry" id="edTagEntry">
                <input id="edSectors" placeholder="Add a sector" />
              </div>
              <small>Press enter to add. Select a tag to remove it.</small>
            </div>
          </div>
        </fieldset>

        <fieldset class="authorisation-fieldset">
          <legend><span>C</span>Authorisation</legend>
          <label class="check-row">
            <input type="checkbox" id="edLicence" />
            <span class="custom-check" aria-hidden="true" id="edCheckMark"></span>
            <span>I am authorised to supply this logo and company information on behalf of
            {e(name)}, and I grant yellow3 lab permission to display it on this supplier
            profile.</span>
          </label>
        </fieldset>

        <div class="form-action">
          <button class="publish" type="submit" id="edPublish" disabled>
            <span>Publish changes</span><span aria-hidden="true" class="arrow">&#8594;</span></button>
          <p>Published changes appear immediately in {e(name)}'s labelled company-supplied
          layer.</p>
        </div>
      </form>

      <aside class="preview-column">
        <div class="preview-sticky">
          <div class="preview-heading">
            <div>
              <span class="panel-index light">02</span>
              <p class="eyebrow dark">PROFILE PREVIEW</p>
            </div>
            <span class="live-state"><i></i> LIVE</span>
          </div>

          <article class="supplier-card">
            <div class="supplied-ribbon">SUPPLIED BY {e(name.upper())}</div>
            <div class="supplier-identity">
              <div class="supplier-logo" id="pvLogoBox">{e(initials(name))}</div>
              <div>
                <p class="company-type">{e(type_label.upper())}</p>
                <h2>{e(name)}</h2>
              </div>
            </div>
            <p class="description placeholder" id="pvDesc">Your one-line company description
            will appear here.</p>
            <div class="card-details">
              <div>
                <span>PUBLIC CONTACT</span>
                <strong class="muted" id="pvContact">Not yet supplied</strong>
              </div>
              <div>
                <span>SECTORS</span>
                <div class="card-chips" id="pvChips"><strong class="muted">Not yet supplied</strong></div>
              </div>
            </div>
            <footer>
              <span>Company-supplied information</span>
              <span id="pvStamp">Updated on publication</span>
            </footer>
          </article>

          <div class="boundary-card">
            <div class="boundary-heading">
              <span class="swatch"></span>
              <div>
                <p class="eyebrow dark">INDEPENDENT RESEARCH LAYER</p>
                <h3>What {e(name)} cannot edit</h3>
              </div>
            </div>
            <p>Identity, headquarters, ownership, funding, capability findings and every
            independently checked source remain part of the yellow3 lab research layer.</p>
            <a href="#" id="edCorrection">Suggest a correction
              <span aria-hidden="true" class="arrow">&#8594;</span></a>
          </div>
        </div>
      </aside>
    </div>
  </section>

  <section class="principle">
    <div class="principle-inner">
      <p class="eyebrow dark">WHY THIS LAYER IS LABELLED</p>
      <p>Separating what a company says from what has been independently researched is the
      basis of this register. Neither layer pretends to be the other.</p>
      <span>yellow3 lab &middot; Research method 01</span>
    </div>
  </section>
</main>
""" + SITE_FOOTER

    script = r"""
<script>
(function(){
  var sid=document.body.dataset.supplier, name=document.body.dataset.name;
  var form=document.getElementById('editForm'), msg=document.getElementById('editMsg'),
      desc=document.getElementById('edDesc'), contact=document.getElementById('edContact'),
      tagIn=document.getElementById('edSectors'), tagBox=document.getElementById('edTagEntry'),
      file=document.getElementById('edLogo'), upBtn=document.getElementById('edUploadBtn'),
      prev=document.getElementById('edLogoPrev'), plus=document.getElementById('edLogoPlus'),
      logoName=document.getElementById('edLogoName'), verb=document.getElementById('edUploadVerb'),
      rm=document.getElementById('edRemoveLogo'), lic=document.getElementById('edLicence'),
      mark=document.getElementById('edCheckMark'), pub=document.getElementById('edPublish'),
      count=document.getElementById('edCount'), tagCount=document.getElementById('edTagCount'),
      pvLogoBox=document.getElementById('pvLogoBox'), pvDesc=document.getElementById('pvDesc'),
      pvContact=document.getElementById('pvContact'), pvChips=document.getElementById('pvChips'),
      pvStamp=document.getElementById('pvStamp'), initials=pvLogoBox.textContent;
  var sectors=[], pending=null, removeLogo=false, currentLogo='';

  function say(t,bad){ msg.hidden=!t; msg.textContent=t||''; msg.className='claim-message'+(bad?' bad':''); }
  function gate(){ pub.disabled=!lic.checked; }
  lic.addEventListener('change',function(){ mark.textContent=lic.checked?'✓':''; gate(); });

  // ---- live preview, exactly what the public layer will show
  function paint(){
    count.textContent=String(desc.value.length);
    tagCount.textContent=String(sectors.length);
    if(desc.value.trim()){ pvDesc.textContent=desc.value; pvDesc.className='description'; }
    else { pvDesc.textContent='Your one-line company description will appear here.';
           pvDesc.className='description placeholder'; }
    var c=contact.value.trim().replace(/^https?:\/\//,'').replace(/\/$/,'');
    pvContact.textContent=c||'Not yet supplied';
    pvContact.className=c?'':'muted';
    pvChips.textContent='';
    if(sectors.length){ sectors.forEach(function(s){var i=document.createElement('i');i.textContent=s;pvChips.appendChild(i);}); }
    else { var st=document.createElement('strong'); st.className='muted';
           st.textContent='Not yet supplied'; pvChips.appendChild(st); }
    var src=pending?prev.src:(removeLogo?'':currentLogo);
    pvLogoBox.textContent='';
    if(src){ var im=document.createElement('img'); im.src=src; im.alt=name+' logo preview'; pvLogoBox.appendChild(im); }
    else { pvLogoBox.textContent=initials; }
  }
  desc.addEventListener('input',paint);
  contact.addEventListener('input',paint);

  // ---- sector chips
  function drawTags(){
    Array.prototype.slice.call(tagBox.querySelectorAll('.form-chip')).forEach(function(n){n.remove();});
    sectors.forEach(function(s){
      var b=document.createElement('button'); b.type='button'; b.className='form-chip';
      b.setAttribute('aria-label','Remove '+s);
      b.appendChild(document.createTextNode(s+' '));
      var x=document.createElement('span'); x.setAttribute('aria-hidden','true'); x.textContent='×';
      b.appendChild(x);
      b.addEventListener('click',function(){ sectors=sectors.filter(function(t){return t!==s;}); drawTags(); paint(); });
      tagBox.insertBefore(b,tagIn);
    });
    tagIn.placeholder=sectors.length?'':'Add a sector';
    paint();
  }
  function addTag(){
    var v=tagIn.value.trim().replace(/,$/,'');
    if(!v||sectors.length>=8){ tagIn.value=''; return; }
    if(!sectors.some(function(s){return s.toLowerCase()===v.toLowerCase();})) sectors.push(v);
    tagIn.value=''; drawTags();
  }
  tagIn.addEventListener('keydown',function(ev){
    if(ev.key==='Enter'||ev.key===','){ ev.preventDefault(); addTag(); }
    else if(ev.key==='Backspace'&&!tagIn.value&&sectors.length){ sectors.pop(); drawTags(); }
  });
  tagIn.addEventListener('blur',addTag);

  // ---- logo
  upBtn.addEventListener('click',function(){ file.click(); });
  file.addEventListener('change',function(){
    var f=file.files&&file.files[0]; if(!f) return;
    if(f.size>400*1024){ say('That logo is larger than 400 KB.',true); file.value=''; return; }
    var fr=new FileReader();
    fr.onload=function(){
      pending={data:String(fr.result).split(',')[1]||'',contentType:f.type};
      prev.src=fr.result; prev.hidden=false; plus.hidden=true; removeLogo=false;
      logoName.textContent=f.name; verb.textContent='Replace'; rm.hidden=false;
      say(''); paint();
    };
    fr.readAsDataURL(f);
  });
  rm.addEventListener('click',function(){
    pending=null; removeLogo=true; prev.hidden=true; plus.hidden=false; file.value='';
    logoName.textContent='Upload company logo'; verb.textContent='Choose file'; rm.hidden=true;
    paint();
  });

  // correction requests go to a person, never to a form we do not read
  document.getElementById('edCorrection').addEventListener('click',function(ev){
    ev.preventDefault();
    window.location.href='mailto:'+'hello'+String.fromCharCode(64)+'yellow3.io'
      +'?subject='+encodeURIComponent('Correction: '+name+' (DPP Supplier Register)');
  });

  // ---- load what is already published
  fetch('/api/supplied?id='+encodeURIComponent(sid)).then(function(r){return r.json();})
    .then(function(d){
      if(!d.editable){
        form.hidden=true;
        say('This editor opens from the link we email when you claim the profile. That link '
          +'has expired or was not used on this device. Claim the profile again and we will '
          +'send a new one.',true);
        msg.hidden=false;
        return;
      }
      var s=d.supplied||{};
      desc.value=s.description||'';
      contact.value=s.contact_url||'';
      sectors=(s.sectors||[]).slice(0,8);
      if(s.logo_url){ currentLogo=s.logo_url; prev.src=s.logo_url; prev.hidden=false;
        plus.hidden=true; verb.textContent='Replace'; rm.hidden=false;
        logoName.textContent='Current logo'; }
      if(s.updated_at) pvStamp.textContent='Updated '+s.updated_at;
      drawTags();
    }).catch(function(){ say('Could not load your profile. Please try again.',true); });

  // ---- publish
  form.addEventListener('submit',function(ev){
    ev.preventDefault();
    var payload={ description:desc.value, contact_url:contact.value, sectors:sectors, licence:true };
    if(pending) payload.logo=pending;
    if(removeLogo) payload.remove_logo=true;
    pub.disabled=true; say('Publishing…');
    fetch('/api/supplied',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)})
      .then(function(r){return r.json().then(function(j){return {ok:r.ok,j:j};});})
      .then(function(x){
        if(!x.ok||!x.j.ok){
          var m={licence_required:'Tick the authorisation box to publish a logo.',
                 logo_type:'That file type is not supported.',
                 logo_size:'That logo is larger than 400 KB.',
                 logo_store_failed:'The logo could not be stored. Please try again.',
                 store_failed:'Could not save. Please try again.',
                 not_signed_in:'Your link expired. Claim the profile again for a new one.'};
          say(m[x.j&&x.j.error]||'Could not publish. Please try again.',true);
          gate(); return;
        }
        var s=x.j.supplied||{};
        currentLogo=s.logo_url||''; pending=null; removeLogo=false;
        rm.hidden=!currentLogo;
        if(s.updated_at) pvStamp.textContent='Updated '+s.updated_at;
        say('Published. This is live on the public profile now.');
        gate(); paint();
      }).catch(function(){ say('Could not publish. Please try again.',true); gate(); });
  });

  paint();
})();
</script>
"""
    out = page(f"Edit {name} - DPP Supplier Register - yellow3",
               f"Company-supplied profile editor for {name} on the yellow3 DPP Supplier Register.",
               f"https://yellow3.io/research/digital-product-passport/suppliers/{sid}/edit",
               body, script)
    out = out.replace(
        '<link rel="stylesheet" href="/research/digital-product-passport/register.css" />',
        '<link rel="stylesheet" href="/research/digital-product-passport/register.css" />\n'
        '  <link rel="stylesheet" href="/research/digital-product-passport/company-layer.css" />')
    out = out.replace("<body>", f'<body data-supplier="{e(sid)}" data-name="{e(name)}">')
    return out.replace('<meta property="og:type" content="website" />',
                       '<meta property="og:type" content="website" />\n  <meta name="robots" content="noindex,nofollow" />')


DIR_SCRIPT = r"""
<script>
(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("registerData").textContent);

  // Company-supplied logos arrive at runtime. One index fetch covers every row;
  // until it lands the rows show initials, which is the honest default.
  var SUPPLIED = {};
  function mark(r) {
    var s = SUPPLIED[r.id];
    return (s && s.logo_url)
      ? '<img src="' + esc(s.logo_url) + '" alt="" loading="lazy" />'
      : esc(r.initials);
  }
  fetch("/api/supplied?all=1").then(function (r) { return r.json(); })
    .then(function (d) { SUPPLIED = (d && d.supplied) || {}; render(); })
    .catch(function () {});
  var NON_COMMERCIAL = { "not-a-supplier": 1, "project-consortium": 1, "standards-body": 1 };
  var REGION_COLOR = { europe: "#c1972b", asia: "#5b2b4d", usa: "#223a5e", other: "#565a60" };
  var REGION_TINT  = { europe: "#efe7cf", asia: "#e7dce4", usa: "#dce3ec", other: "#e1e1df" };
  var BASE = "/research/digital-product-passport/suppliers/";
  var SVGNS = "http://www.w3.org/2000/svg";
  var geo = null, selected = "";

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
          return '<a href="' + BASE + esc(s.id) + '" class="supplier-row"><span class="supplier-mark">' + mark(s) +
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
  var PAGE = 25, shown = PAGE, scope = "all";

  function chev(open) {
    return '<svg class="chevron' + (open ? " open" : "") + '" viewBox="0 0 20 20" aria-hidden="true">' +
      '<path d="m6 8 4 4 4-4"/></svg>';
  }

  function renderDir() {
    var all = dirFiltered().filter(function (r) {
      // held out of the supplier results: it has its own research-exception block
      if (r.name.toLowerCase().indexOf("(unnamed") === 0) return false;
      return scope === "all" || r.findings > 0;
    });
    var rows = all.slice(0, shown);
    $("profileCount").textContent = all.length;
    $("showingNote").textContent = "Showing " + rows.length + " of " + all.length +
      (all.length === DATA.length ? " profiles" : " matching profiles");
    $("loadMore").hidden = rows.length >= all.length;

    $("dirRows").innerHTML = rows.map(function (r) {
      var tone = r.basis === "verified" ? "verified" : "claimed";
      var status = r.findings ? r.findings + " capability findings" : "Capability research pending";
      var chips = r.sector_keys && r.sector_keys.length
        ? r.sectors.map(function (x) { return "<i>" + x + "</i>"; }).join("")
        : '<i class="empty">No public sector focus</i>';
      // the row is the link: one press opens the profile, no disclosure step
      return '<article class="supplier" data-row="' + esc(r.id) + '">' +
        '<a class="supplier-main" href="' + BASE + esc(r.id) + '">' +
        '<span class="edge ' + tone + '"></span>' +
        '<span class="supplier-name"><span class="avatar">' + mark(r) + '</span>' +
        '<span><b>' + esc(r.name) + "</b><small>View profile &#8599;</small></span></span>" +
        "<span><em>" + esc(r.type) + "</em></span>" +
        '<span class="hq">' + r.hq + "</span>" +
        '<span class="chips">' + chips + "</span>" +
        '<span class="evidence-cell"><b>' + r.facts + " public fact" + (r.facts === 1 ? "" : "s") +
        "</b><small>" + esc(status) + "</small></span>" +
        '<span class="date">' + esc(r.date) + "</span>" +
        '<span class="go" aria-hidden="true">&#8599;</span></a></article>';
    }).join("");
  }

  $("loadMore").addEventListener("click", function () { shown += PAGE; renderDir(); });
  Array.prototype.forEach.call(document.querySelectorAll(".segmented button"), function (b) {
    b.addEventListener("click", function () {
      scope = b.dataset.view; shown = PAGE;
      Array.prototype.forEach.call(document.querySelectorAll(".segmented button"), function (x) {
        x.classList.toggle("active", x === b);
      });
      renderDir();
    });
  });


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
            "facts": facts, "findings": findings,
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
    # The most recent date any row was actually researched - not the build date.
    latest = max((r.get("source_date") or "" for r in rows), default="")
    try:
        today = datetime.date.fromisoformat(latest).strftime("%-d %b")
    except Exception:
        today = latest or "-"

    opts = lambda vals, lab: "".join(f'<option value="{e(v)}">{e(lab(v))}</option>' for v in vals)

    # values the approved directory markup needs
    latest_pretty = pretty_date(latest) or "Not recorded"
    country_opts = opts(countries, lambda v: v)
    sector_opts = opts(sectors, lambda v: SECTOR_LABEL.get(v, v.title()))
    type_opts = opts(types, lambda v: TYPE_LABEL.get(v, v))
    chev = ('<svg class="chevron" viewBox="0 0 20 20" aria-hidden="true">'
            '<path d="m6 8 4 4 4-4"/></svg>')

    # Research exceptions: rows where no public supplier identity was established.
    # They are held out of the supplier results rather than counted among them.
    featured = ""
    for x in rows:
        if not x["name"].lower().startswith("(unnamed"):
            continue
        label = re.sub(r"^\(unnamed\)\s*", "", x["name"]).strip()
        featured += f'''<div class="featured">
        <div class="featured-label">RESEARCH EXCEPTION</div>
        <div class="featured-body">
          <div class="avatar muted">{e(initials(x["name"]))}</div>
          <div class="identity">
            <h2>{e(label)} <span>&#8599;</span></h2>
            <p>Unnamed entity &middot; retained as market evidence</p>
          </div>
          <div class="exception-note">
            <b>Not a commercial supplier</b>
            <p>This record is separated from the supplier results because no public supplier
            identity was established.</p>
          </div>
          <a class="record-link" href="/research/digital-product-passport/suppliers/{e(x["id"])}">View research record <span>&#8594;</span></a>
        </div>
      </div>'''

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

  <div class="dpp-dir">
    <section class="hero">
      <div class="eyebrow"><span></span>GLOBAL MARKET RESEARCH</div>
      <div class="hero-grid">
        <div>
          <h1>Supplier directory</h1>
          <p>Evidence-led profiles of the global Digital Product Passport market.</p>
        </div>
        <div class="stat">
          <strong>{counts['organisations']}</strong>
          <span>organisations recorded</span>
          <small>Research register &middot; {latest_pretty}</small>
        </div>
      </div>
    </section>

    <section class="directory">
      <div class="search-row">
        <label class="search"><span class="sr-only">Search suppliers</span>
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></svg>
          <input id="dq" placeholder="Search suppliers" aria-label="Search suppliers" /></label>
        <label class="filter"><span class="sr-only">Country</span>
          <select id="dCountry"><option value="">Country</option>{country_opts}</select>{chev}</label>
        <label class="filter"><span class="sr-only">Sector</span>
          <select id="dSector"><option value="">Sector</option>{sector_opts}</select>{chev}</label>
        <label class="filter"><span class="sr-only">Entity type</span>
          <select id="dType"><option value="">Entity type</option>{type_opts}</select>{chev}</label>
        <label class="filter evidence"><span class="sr-only">Capability evidence</span>
          <select id="dCap"><option value="">Capability evidence</option><option value="assessed">Assessed</option><option value="pending">Pending</option></select>{chev}</label>
      </div>

      <div class="toolbar">
        <div class="result"><b id="profileCount">{counts['organisations']}</b> profiles <span>&middot;</span> Last register update {latest_pretty}</div>
        <div class="segmented" role="group" aria-label="Result scope">
          <button type="button" data-view="all" class="active">All suppliers</button>
          <button type="button" data-view="researched">Capability researched</button>
        </div>
      </div>

      {featured}

      <div class="table-head">
        <span>SUPPLIER</span><span>TYPE</span><span>HEADQUARTERS</span><span>SECTORS</span><span>EVIDENCE</span><span>CHECKED</span><span></span>
      </div>
      <div class="rows" id="dirRows"></div>
      <div class="footer-note">
        <span id="showingNote"></span>
        <button type="button" id="loadMore">Load more suppliers &#8595;</button>
        <a href="#method">Research method &#8599;</a>
      </div>
    </section>
  </div>

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
    out = page("Supplier directory - DPP Supplier Register - yellow3",
                f"Evidence-led profiles of the Digital Product Passport market. "
                f"{counts['organisations']} organisations across {counts['countries']} countries, "
                f"every headquarters sourced and dated.",
                "https://yellow3.io/research/digital-product-passport/suppliers",
                body, script)

    return out.replace(
        '<link rel="stylesheet" href="/research/digital-product-passport/register.css" />',
        '<link rel="stylesheet" href="/research/digital-product-passport/register.css" />\n'
        '  <link rel="stylesheet" href="/research/digital-product-passport/directory-v1.css" />')



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

    with open(os.path.join(OUT, "add.html"), "w", encoding="utf-8") as fh:
        fh.write(add_html(counts))

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
            with open(os.path.join(d, "edit.html"), "w", encoding="utf-8") as fh:
                fh.write(edit_html(r, counts))
            claims += 1

    # retire the old flat profile pages now that they redirect
    old = 0
    for r in rows:
        p = os.path.join(HERE, "digital-product-passport", f"{r['id']}.html")
        if os.path.exists(p):
            os.remove(p)
            old += 1

    # The DPP instrument page shows the register's headline numbers. Publish them
    # as data so that page can never quote a total the register no longer holds.
    with open(os.path.join(HERE, "dpp-register-counts.json"), "w", encoding="utf-8") as fh:
        json.dump(counts, fh, ensure_ascii=False, indent=1)

    n = write_redirects([r["id"] for r in rows])

    print(f"/suppliers                     1 page")
    print(f"/suppliers/add                 1 page")
    print(f"/suppliers/<id>              {profiles:3d} profiles")
    print(f"/suppliers/<id>/claim        {claims:3d} claim pages")
    print(f"/suppliers/<id>/edit         {claims:3d} editor pages")
    print(f"removed old flat profiles    {old:3d}")
    print(f"vercel redirects written     {n:3d}")
    print(f"\n  {counts['organisations']} organisations, {counts['commercial_suppliers']} commercial "
          f"suppliers, {counts['countries']} countries")


if __name__ == "__main__":
    main()
