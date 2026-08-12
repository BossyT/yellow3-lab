# yellow3.io review - 2026-08-12

First review since the 2026-08-11 nav/footer change and the new `/platforms`
page. Scope: `python3 research/site_audit.py`, `python3 research/site_nav.py`,
and a full read of `index.html`, `platforms.html`, `research.html`,
`about.html`, `advisory.html`, `naffe.html`, `insights/index.html`, plus the
DPP Supplier Register and the two commercial-boundary questions in the brief.

I cannot see the site. Everything below is read from markup, CSS and JSON-LD
in the repo, not from pixels in a browser.

## What a visitor hits

Nothing broken. `site_audit.py` found 0 dead links, 0 missing images, 0
missing titles across 632 pages, and `site_nav.py` reports all 631 pages match
the one nav definition. The mechanical sweep the site depends on worked.

Two `rel=noopener` gaps (does not block anything, but a linked page can
control `window.opener`):

- `insights/eu-ai-exposure.html:347` - `target="_blank"` to ec.europa.eu, no `rel=noopener`
- `insights/eu-ai-exposure.html:348` - `target="_blank"` to ilo.org, no `rel=noopener`

## What reads wrong

**1. The page the renamed "Insights" nav item opens still calls itself
"Thinking" everywhere a reader or a search engine sees it.** The nav sweep
only rewrote the nav-mid block and the footer; it never touched
`insights/index.html`'s own content, so the page a visitor lands on
contradicts the label they clicked:

- `insights/index.html:14` - `<title>Thinking - yellow3 lab</title>`
- `insights/index.html:174,177` - og:title / twitter:title `Thinking - yellow3 lab`
- `insights/index.html:185` - breadcrumb JSON-LD `"name": "Thinking"`
- `insights/index.html:193` - CollectionPage JSON-LD `"name": "Thinking - yellow3 lab"`
- `insights/index.html:225` - on-page, visible: `<div class="hero-eyebrow">Thinking</div>`
- `insights/index.html:231` - visible link text `Subscribe to thinking →`

A visitor who clicks "Insights" in the nav arrives on a page whose browser
tab, hero, and subscribe link all say "Thinking." Anyone who shares the page
gets a social-preview card that says "Thinking - yellow3 lab" too. This is the
single most visible leftover from the rename - it is the destination of the
new nav item, not a buried template.

Sixteen individual insight articles carry the same stale value in their own
breadcrumb JSON-LD (`"name": "Thinking"` for the `/insights/` node) -
invisible on the page but it is what a search result's breadcrumb can show.
Full list on request; representative example: `insights/a-400-escape-route.html:68`.

**2. The homepage still describes yellow3 lab as building Digital Product
Passport infrastructure - which is the thing the site now explicitly says
yellow3 lab does not do.** Two cells on the homepage:

- `index.html:358-360` - "What we build" grid: **"Digital Product Passport
  infrastructure"** / "Verifiable product data infrastructure for trust,
  compliance, and transparency at scale." Links to `/research/eu-ai-act`.
- `index.html:432-436` - "Research areas" grid: **"Digital Product
  Passports"** / "Building the data layer for trust, compliance, and
  circularity." Also links to `/research/eu-ai-act`.

Compare that to what the site says everywhere else the boundary is stated:
`platforms.html:641` - "**yellow3 lab does not operate Digital Product
Passports.** The platform works for the organisation buying and implementing
them" - and `research/digital-product-passport/suppliers.html` - "**We do not
operate Digital Product Passports.** We do not host, issue, resolve, maintain
or publish them. The suppliers in this register do that." The homepage copy
("we build... infrastructure... at scale," "we build the data layer") reads
as exactly the claim the rest of the site goes out of its way to deny. This
predates the nav change, but it is live on the homepage today and it is the
boundary the brief asked me to check.

Both cells also point to the wrong page: a reader clicking "Digital Product
Passport infrastructure" or "Digital Product Passports" lands on the EU AI
Act instrument, not on `/research/digital-product-passport` or `/platforms`.
That is an independent link/label mismatch, not just a wording problem.

**3. The homepage's own Insights section still says "Thinking."** Separately
from finding 1: `index.html:450` - `<div class="section-label">Thinking</div>`
and `index.html:451` - `<a href="/insights/" class="view-all">View all
thinking →</a>`. The nav two lines above this section correctly says
"Insights"; the section immediately below it says "Thinking" twice. Same page,
two names for the same thing.

## Boundary checks (from the brief)

- **"yellow3 lab does not operate DPPs":** correctly and explicitly stated on
  `platforms.html` and on the supplier register (`suppliers.html`, "Our
  interest, declared" section). Contradicted by the homepage copy in finding
  2 above.
- **Supplier Register reading as independent, not a sales route into the
  Buyer Platform:** clean. `research/digital-product-passport/suppliers.html`
  contains no link, mention or CTA toward `buyer.yellow3.io` or "Buyer
  Platform" anywhere in the page. The register's own "Our interest, declared"
  section discloses the commercial relationship in more direct language than
  most sites would ("Buyers pay us... Suppliers do not pay us. Ever."). The
  only place the two products sit side by side is `platforms.html`, where
  they are clearly two separate entries under "Area 01," each with its own
  description and its own boundary statement. That reads as intended, not as
  a funnel.

## What is inconsistent

- **Two typefaces on `platforms.html`.** The page loads DM Sans (line 21) for
  its nav and footer, but the `.y3-platforms` wrapper that holds everything
  else sets `font-family: Arial, Helvetica, sans-serif` (`platforms.html:168`).
  A code comment at `platforms.html:154-170` explains this was a deliberate
  choice - the design package names the DPP Supplier Register as its
  typographic reference, and the register runs on Arial by a standing 30 Jul
  rule, so the page was shipped as specified rather than remapped onto DM
  Sans. Flagging it anyway because it is exactly the condition Pass 3 asks me
  to check for (a second typeface on a page that already loads DM Sans), and
  because the nav/footer above and below the Arial content are still DM Sans
  - so the page itself changes typeface twice in one scroll. Worth a second
  look from whoever signed off on the deviation, even though it is
  documented as intentional.
- **Heading hierarchy jumps h1 straight to h3**, skipping h2, on two pages:
  `platforms.html` (h1 headline, then three `h3` method-step headings before
  any `h2` appears) and `research.html`. 52 other pages jump h1 to h4, and
  398 pages jump h2 to h4 - all pre-existing and unrelated to this week's
  change; not re-listing individually, but noting the count since it is a
  site-wide pattern, not one page.
- **Three pages carry two `<h1>` elements each:**
  `research/model-adoption/reports/2026-07.html`,
  `research/model-adoption/reports/2026-08.html`, and
  `research/digital-product-passport/suppliers.html`. Pre-existing, not part
  of this week's change.
- **524 classes render with no CSS rule anywhere the page loads** - site-wide,
  pre-existing, not concentrated on any of the changed pages. Examples:
  `cookies.html:138` (`cookie-table`), `research.html:201` (`ds-l`),
  `research/digital-product-passport.html:379` (`rp-l`).
- **21 images over 400KB**, all pre-existing insight hero images
  (1.3-3.8MB each) plus `about.html:279` (`/thomas.jpg`, 2279KB). None of the
  three new `/img/platforms/*.png` screenshots are in the over-400KB list.
- One page, `research/model-adoption/login.html`, has no meta description;
  five pages have no `og:title`. Pre-existing, unrelated to this change.
- The one "em/en dash" the audit flagged on `digital-product-passport.html`
  is a `–` used as a loading-state placeholder character in a score widget
  (`digital-product-passport.html:330,335`), not prose - not a house-style
  breach, checked and dismissed.

## For ChatGPT

- The Arial/DM Sans split on `platforms.html` (above) is a design decision,
  already made and documented in-code as intentional - flagging for
  awareness, not asking for a redesign.
- `platforms.html`'s heading order (h1 → h3 method steps → h2 area heading)
  is a structural choice in the design package, not a markup slip; worth
  knowing if the package gets revised.

## Checked and clean

- Nav: all 631 public pages match `research/site_nav.py` exactly - Research,
  Platforms, Insights, Advisory, About, Contact, in that order, one active
  item each.
- Footer: every page I opened (`index.html`, `platforms.html`,
  `research.html`, `about.html`, `advisory.html`, `naffe.html`,
  `research/digital-product-passport/suppliers.html`) carries the new
  Platforms / Research / Company column split with Advisory correctly under
  Company and no duplicate Advisory link in the nav.
- Homepage header CTA is `View our research` → `/research`; hero CTA is
  `Explore our platforms` → `/platforms`. Both match the brief.
- naffe.html's nav correctly shows Platforms as active (the old "active item
  moved" mapping in `site_nav.py` works as designed).
- The DPP Supplier Register dataset card sits above the three instruments on
  `research.html`, as described.
- Zero dead links, zero missing images, zero missing page titles across all
  632 pages.
- The Supplier Register does not read as a sales route into the Buyer
  Platform - no mention of it anywhere on the register page.
