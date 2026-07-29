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
    # A date on this page means a human looked on that date. Never today's date:
    # rebuilding the site is not research, and stamping the build date here would
    # silently re-date 183 provenance claims every time the generator runs.
    checked = cdate or pretty_date(r.get("source_date") or "") or "Not recorded"
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
    # The supplied content arrives at runtime, after the page was built, so this
    # block is filled in the browser from /api/supplied. Absent is the honest
    # default and what search engines see.
    company = "" if nc else f"""
          <section class="company-layer" id="companyLayer" data-supplier="{e(sid)}">
            <span class="layer-rule yellow"></span>
            <h3>Supplied by {e(r["name"])}</h3>
            <div id="companyBody">
              <p>No company-supplied profile received</p>
              <a href="/research/digital-product-passport/suppliers/{e(sid)}/claim">Claim this profile &#8599;</a>
            </div>
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
        <span class="profile-monogram" id="profileMonogram">{e(initials(r["name"]))}</span>
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
      <section class="company" id="companyAside"><span class="layer-rule yellow"></span><h3>Company layer</h3><p id="companyAsideText">Information supplied by the company. Currently absent.</p></section>
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
(function(){
  // Company layer. Everything here is written by the company itself and is
  // labelled as such - it is never merged with what we verified, and it is
  // inserted as text, never as markup.
  var host=document.getElementById('companyLayer'), box=document.getElementById('companyBody');
  if(!host||!box) return;
  var sid=host.dataset.supplier;
  fetch('/api/supplied?id='+encodeURIComponent(sid)).then(function(r){return r.json();})
    .then(function(d){
      var s=d&&d.supplied; if(!s) return;
      var frag=document.createDocumentFragment();
      if(s.logo_url){
        var fig=document.createElement('div'); fig.className='company-logo';
        var img=document.createElement('img'); img.src=s.logo_url; img.alt='';
        img.loading='lazy'; fig.appendChild(img); frag.appendChild(fig);
      }
      if(s.description){
        var p=document.createElement('p'); p.className='company-desc';
        p.textContent=s.description; frag.appendChild(p);
      }
      if(s.sectors&&s.sectors.length){
        var ul=document.createElement('ul'); ul.className='company-tags';
        s.sectors.forEach(function(t){var li=document.createElement('li');li.textContent=t;ul.appendChild(li);});
        frag.appendChild(ul);
      }
      if(s.contact_url){
        var a=document.createElement('a'); a.href=s.contact_url; a.target='_blank';
        a.rel='noopener nofollow'; a.textContent='Contact this company \\u2199';
        a.className='company-contact'; frag.appendChild(a);
      }
      var stamp=document.createElement('p'); stamp.className='company-stamp';
      stamp.textContent='Supplied by the company'+(s.updated_at?', updated '+s.updated_at:'')
        +'. Not verified by yellow3 lab.';
      frag.appendChild(stamp);
      if(d.editable){
        var ed=document.createElement('a'); ed.className='company-contact';
        ed.href='/research/digital-product-passport/suppliers/'+sid+'/edit';
        ed.textContent='Edit your layer \\u2199'; frag.appendChild(ed);
      }
      box.textContent=''; box.appendChild(frag);
      // the sidebar card describes the same layer, so it cannot keep saying absent
      // the identity mark: their logo if they have supplied one, initials if not.
      // only the mark changes - every fact around it stays what we verified.
      var mono=document.getElementById('profileMonogram');
      if(mono && s.logo_url){
        var mi=document.createElement('img'); mi.src=s.logo_url; mi.alt='';
        mono.textContent=''; mono.appendChild(mi);
      }
      var aside=document.getElementById('companyAsideText');
      if(aside){ aside.textContent='Information supplied by the company'
        +(s.updated_at?', updated '+s.updated_at:'')+'. Not verified by yellow3 lab.'; }
    }).catch(function(){});
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
    # 5 commercial rows have no domain on record. Telling those visitors the claim
    # is checked "against the domain on record" promises a check we cannot run, and
    # they would wait for a confirmation that can never come. Their attempt still
    # reaches us as a near miss, which is how the row gets resolved.
    if r["domain"]:
        intro = ("Enter your work email. If it is at the domain on record for this company, "
                 "the claim is confirmed straight away, no account, no waiting for approval.")
    else:
        intro = ("We do not have a domain on record for this company yet, so this claim cannot "
                 "be confirmed automatically. Enter your work email and it reaches us directly: "
                 "we verify it by hand, record the domain, and the profile becomes claimable "
                 "from then on.")
    body = f"""{SITE_NAV}<main class="claim-shell">

  <section class="claim-body">
    <a class="claim-back" href="/research/digital-product-passport/suppliers/{e(sid)}">&#8249; Back to profile</a>

    <section class="claim-content">
      <h1>Claim {e(r["name"])}</h1>
      <p class="claim-intro">{intro}</p>
      <form id="claimForm">
        <label><span class="sr-only">Work email</span>
          <input id="claimEmail" type="email" placeholder="you@yourcompany.com" autocomplete="email" /></label>
        <button type="submit">Claim this profile <span>&#8594;</span></button>
      </form>
      <p class="claim-message" role="status" id="claimMsg" hidden></p>

      <div class="claim-principles">
        <article><h2>What you can supply</h2><p>A logo, a one-line description, a contact link
        and your sectors. It appears in its own layer on your profile, marked as coming from you,
        and dated.</p></article>
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
      .then(function(){ say(document.body.dataset.nodomain
        ? 'Work email received. We will verify it by hand and be in touch.'
        : 'Work email received. If ' + domain + ' is the domain on record for '
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
    nod = '' if r["domain"] else ' data-nodomain="1"'
    out = out.replace("<body>", f'<body data-supplier="{e(sid)}"{nod}>')
    return out.replace('<meta property="og:type" content="website" />',
                       '<meta property="og:type" content="website" />\n  <meta name="robots" content="noindex,follow" />')


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
  function renderDir() {
    var rows = dirFiltered();
    $("profileCount").textContent = rows.length + (rows.length === DATA.length ? " profiles" : " of " + DATA.length + " profiles");
    $("dirRows").innerHTML = rows.map(function (r) {
      var open = openRow === r.id;
      return '<article class="directory-row state-' + r.state + (open ? " is-open" : "") + '" data-row="' + esc(r.id) + '">' +
        '<a class="row-supplier" href="' + BASE + esc(r.id) + '">' +
        (r.state === "non-supplier" ? "<small>Non-supplier<br />entity</small>" : "") +
        '<span class="row-initials">' + mark(r) + '</span><strong>' + esc(r.name) + "</strong><em>&#8599;</em></a>" +
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
    # The most recent date any row was actually researched - not the build date.
    latest = max((r.get("source_date") or "" for r in rows), default="")
    try:
        today = datetime.date.fromisoformat(latest).strftime("%-d %b")
    except Exception:
        today = latest or "-"

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

    n = write_redirects([r["id"] for r in rows])

    print(f"/suppliers                     1 page")
    print(f"/suppliers/<id>              {profiles:3d} profiles")
    print(f"/suppliers/<id>/claim        {claims:3d} claim pages")
    print(f"/suppliers/<id>/edit         {claims:3d} editor pages")
    print(f"removed old flat profiles    {old:3d}")
    print(f"vercel redirects written     {n:3d}")
    print(f"\n  {counts['organisations']} organisations, {counts['commercial_suppliers']} commercial "
          f"suppliers, {counts['countries']} countries")


if __name__ == "__main__":
    main()
