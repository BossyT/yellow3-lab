# yellow3.io - revenue and growth plan, September 2026

Written 1 September 2026 from the repository, the Stripe account, the Vercel
project, the Ahrefs site-audit mail, the shared inbox and the public web. It is
a plan to follow, not an essay. Section 4 is the brief to hand to Cowork.

What could not be checked from here: buyer.yellow3.io and naffe.ai were not
reachable from the sandbox, live HTTP status of the legacy URLs in section 1.5
was not confirmed, and the Ahrefs backlink profile was not exported. Each is a
morning task in section 4, not an assumption in this document.

---

## 1. Where yellow3.io stands today

### 1.1 The assets

| Asset | State | Why it matters commercially |
|---|---|---|
| DPP Supplier Register | 191 organisations, 172 commercial suppliers, 33 countries, CC BY 4.0 CSV + JSON, 195 URLs in the sitemap | The only public, evidence-led dataset of the DPP supplier market. The most linkable thing yellow3 owns. |
| DPP Buyer Platform (buyer.yellow3.io) | Live, self-serve, Stripe prices set (Micro to Enterprise), free readiness entry | The recurring-revenue product for the DPP side. |
| AI Model Adoption instrument | Daily pull since June, weekly edition, monthly free briefing, gated monthly report | A quotable weekly statistic (Europe's routed share) that journalists already write about using the same source. |
| Monday Briefing | Weekly DPP video with presenter, transcript and sourced records, two issues published | The only recurring DPP audience touchpoint yellow3 has. |
| EU AI Act record, DPP delivery record | Living instruments | Secondary citation assets. |
| Insights | 36 articles, 17 in the feed, 5 published in August, last on 13 August | The cadence dropped in the second half of August. |
| Advisory page | Strategic Advisory at EUR 5,000/month published; EU Desk marked "coming soon, no pricing" | Sellable today, but see the mismatch in 1.3. |

### 1.2 The product catalogue that exists in Stripe (live mode)

| Product | Price | Purchase path today |
|---|---|---|
| DPP Buyer Platform Micro / Small / Medium / Enterprise | EUR 99 / 249 / 599 / 1,499 per month, annual at 10x | buyer.yellow3.io/start |
| Digital Product Passport Market Readiness (EU Desk) | EUR 4,900 one-off | No public path. The advisory page says EU Desk has no pricing or availability. |
| yellow3 lab Advisory Session | EUR 490 one-off | Not linked from the site. |
| Executive Briefing (90 min) | EUR 1,500 | Not linked from the site. |
| Board Briefing (2 hours) | EUR 3,000 | Not linked from the site. |
| Leadership Workshop (half day) | EUR 4,500 | Not linked from the site. |
| Model Intelligence Professional | EUR 79/month or 790/year | Stripe payment links on /research/model-adoption, magic-link access works. |
| Model Intelligence Team (5 seats) | EUR 249/month or 2,490/year | Same page. |

Booked recurring revenue as of 1 September: none. The one subscription in the
account was an internal test and was refunded. Everything above is built and
priced. Nothing above has been sold. That is the whole diagnosis: the problem
is distribution and conversion, not product.

### 1.3 Demand signals that already exist

- **Suppliers are claiming register profiles without being asked.** Six
  companies claimed their profile between 31 July and 24 August, two suggested
  themselves for research, and two more attempted claims from unrecorded
  domains. That is roughly one organic supplier engagement every three days
  with zero promotion.
- **A standards-body co-chair sent a two-page correction letter on 4 August.**
  It said the correction path was broken (fixed since, the anchor exists) and,
  more importantly, that the ten capability checks mostly return "no public
  evidence", so the layer measures how far the crawl reached rather than what
  suppliers can do. A recount of `research/dpp-capability.json` on 1 September
  confirms it: 1,530 checks over 154 suppliers, of which 1,216 (79 percent)
  are `not_found`, 280 (18 percent) are `company_states` and 44 (3 percent)
  are `verified`. Buyers will read that as a capability signal. This is the
  one product fix that blocks selling "evidence-based selection" with a
  straight face.
- **Inbound to the shared inbox is vendors selling to yellow3**, not buyers.
  No real founding-buyer application has arrived; the ones in the inbox are
  test submissions.
- **LinkedIn reach is about 3,600 impressions a week** on the founder's posts.
  Small, but it is the only owned channel with an audience.

### 1.4 Measurement: the site is currently blind

- Google Analytics was removed on 14 August. The consent gate in consent.js is
  built and gates nothing.
- Vercel Web Analytics is not enabled on the project.
- Google Search Console is verified (the verification file is in the repo) and
  is the only source of organic data right now.
- Ahrefs Site Audit runs weekly on the domain: health score 96, 22 errors,
  3 orphan pages, 92 meta descriptions too long, 38 external redirects. The
  backlink profile has not been exported to anything in this repo.

You cannot run a revenue plan on zero traffic data. Fixing this is task 1.

### 1.5 SEO state: the old site is still in Google

Google still indexes at least eight URLs from the previous yellow3.io, when the
company sold NFC-enabled passports:

```
/digitalproductpassport
/digital-product-passport-furniture
/nfc-tags
/products
/post/rfid-technology-and-the-future-of-digital-product-passports
/industries-categories/environment
/privacypolicy
/masterclass            (this one already redirects to /advisory)
```

None of the first seven exists in the repo and, until 2 September, none had a
redirect in vercel.json. Cowork's check on 2 September found the paths return
404 on the Vercel deployment URL but 200 on www.yellow3.io, serving the retired
Wix site, which would mean every path the old site ever had is still reachable
under the brand. That mechanism is not confirmed from the repository: DNS for
www points at Vercel, the project holds the domain, and vercel.json has no
rewrites. Confirm with the response headers before assuming an extra origin:

```
curl -sI https://www.yellow3.io/nfc-tags | grep -iE '^(HTTP|server|x-vercel|x-wix)'
curl -sI https://yellow3-orcin.vercel.app/nfc-tags | grep -iE '^(HTTP|server)'
```

Either way the fix is the same and is now on this branch: ten 301s in
vercel.json, including two catch-alls for `/post/` and
`/industries-categories/` and one for `/blog/`, so the project answers every
legacy path itself. Whatever inbound links those pages earned are recovered
once this deploys, and the brand search result stops describing yellow3 as a
passport vendor once Google recrawls. A third-party data broker lists the
company as founded 2023 in the Netherlands, and Google Business Profile still
carries the retired "yellow3 Inc" entity. The Organization JSON-LD on the
homepage has an empty sameAs array, so nothing on the site tells a crawler
which LinkedIn, Crunchbase or GitHub profile is the same entity.

---

## 2. Revenue: what to sell first, and to whom

### 2.1 The ranking, by time to cash

| Rank | Offer | Price | Why first |
|---|---|---|---|
| 1 | DPP Market Readiness review | EUR 4,900 fixed scope | Highest price with the lowest build cost: a person, ten working days, the buyer platform as the deliverable. Two sales is EUR 9,800. |
| 2 | Advisory Session | EUR 490 | The low-friction door into rank 1 and rank 4. Book from a Stripe link, deliver on a call. |
| 3 | Buyer Platform Micro / Small | EUR 99 / 249 per month | Recurring, self-serve, already live. Needs a measured funnel from free readiness to paid. |
| 4 | Executive Briefing / Board Briefing / Workshop | EUR 1,500 / 3,000 / 4,500 | Nordic boards facing the February 2027 battery deadline. Sold from LinkedIn and the Monday Briefing. |
| 5 | Model Intelligence Pro / Team | EUR 79 / 249 per month | Lowest fit: the audience is developers who can read OpenRouter for free. Keep it, do not spend selling effort on it. Use the instrument as the press and backlink engine instead. |

Do not add products. Eleven SKUs exist and none has a customer. The work is
to put three of them in front of the right people every week.

### 2.2 Who buys, and where they are

The buyer is a company that makes, imports or sells physical products into the
EU and has a dated obligation. In order of urgency:

1. **Batteries**: EV, industrial above 2 kWh, e-bike and e-scooter batteries.
   The QR and passport date is 18 February 2027. This is the only sector whose
   deadline is inside a normal procurement cycle from today.
2. **Textiles and footwear**, then **iron and steel**, **furniture**, **tyres**:
   the ESPR working plan sectors with delegated acts in progress.
3. **Nordic mid-caps and importers** generally, because the founder's network,
   language and LinkedIn audience are there.

Where they are, in the channels yellow3 already has:

- The register's own visitors. Buyers browse supplier lists. Every register
  page already links to the free readiness start. This is the warmest traffic
  the site has and it is currently unmeasured.
- The Monday Briefing audience. Each edition should end on one sentence and one
  link: "If this affects your products, start the free readiness."
- LinkedIn, weekly, with the register's numbers and the briefing's stories.
- Outbound: a named list of 50 battery and textile companies with EU exposure,
  each sent the readiness offer, the deadline that applies to them, and one
  register finding about a supplier they might be talking to.

### 2.3 Targets

| Horizon | Target | What it takes |
|---|---|---|
| 30 days | EUR 10,000 booked | Two readiness reviews, or one review plus briefings and sessions. |
| 60 days | EUR 2,500 monthly recurring | Ten Buyer Platform Micro or four Small, from the readiness funnel. |
| 90 days | EUR 5,000 monthly recurring plus EUR 20,000 one-off | Recurring from the platform, one-off from readiness and board work. |

### 2.4 Fixes that block selling (do these before the outreach lands)

1. **The capability layer.** Relabel the ten checks as what they are, "what
   yellow3 could find in public sources on the date shown", or fold the
   "no public evidence found" state into a neutral "not assessed from public
   sources". A buyer who reads 81 percent "no evidence" as 81 percent
   incapable will distrust the register, and the register is the reason to
   trust the platform.
2. **Disclose participation.** The register must say, once and plainly, that
   yellow3 also sells buyer-side services in the market it catalogues. The
   correction letter asked for exactly this, and it costs nothing.
3. **EU Desk copy versus Stripe.** The advisory page says "no signup, pricing
   or current availability". Stripe has a EUR 4,900 readiness product. Either
   the page names the price and a route to it, or the product is not sellable
   from the site. Copy is design-frozen, so this is a GPT ruling to request
   tomorrow, not a unilateral edit.
4. **Unlinked products.** Advisory Session, Executive Briefing, Board
   Briefing and Workshop exist only in Stripe. They need a Stripe payment link
   each and a place on the advisory page. Same ruling.
5. **Insights cadence.** Nothing since 13 August. One article a week, with the
   register or the instrument as its data, is the minimum for the press
   strategy in section 3 to work.

---

## 3. Backlinks: where, how, and what to say

### 3.1 Principles

- Backlinks come from being cited. yellow3 has three things worth citing: the
  register dataset, the weekly model-adoption statistic, and the dated DPP
  delivery record. Every outreach message offers one of these, never "a link".
- No paid links, no link exchanges, no directory spam, no guest-post farms. A
  research lab whose product is being checkable cannot be seen buying links.
- Suppliers linking to their own register profile is editorially natural and
  is never a condition of anything. The register stays free and unranked.
- Copy on the public site is design-frozen. Anything below that changes a page
  goes to GPT as a request with the reason attached.

### 3.2 The linkable assets and their canonical URLs

| Asset | URL to give people |
|---|---|
| Register landing | https://www.yellow3.io/research/digital-product-passport/suppliers |
| Register dataset CSV | https://www.yellow3.io/research/digital-product-passport/suppliers.csv |
| Register dataset JSON | https://www.yellow3.io/research/digital-product-passport/suppliers.json |
| Model adoption live | https://www.yellow3.io/research/model-adoption |
| Model adoption free briefing | https://www.yellow3.io/research/model-adoption/briefing |
| DPP delivery record | https://www.yellow3.io/research/digital-product-passport |
| Monday Briefing | https://www.yellow3.io/research/digital-product-passport/weekly-briefing |
| RSS | https://www.yellow3.io/feed.xml |

### 3.3 Tier A: reclaim what exists (day 1)

1. **Redirect the legacy URLs.** Add 301s in vercel.json for the seven URLs in
   section 1.5, each to the nearest live page (DPP pages to
   /research/digital-product-passport, the blog post to
   /research/digital-product-passport/suppliers, /products to /platforms,
   /privacypolicy to /privacy). Before that, export Ahrefs Site Explorer
   "Best by links" and "Broken backlinks" for yellow3.io so every URL that
   ever earned a link gets a redirect, not just the eight Google showed.
2. **Fix the entity.** Google Business Profile: retire "yellow3 Inc", assert
   yellow3 ApS, Copenhagen. Crunchbase, LinkedIn company page and the data
   brokers: founded 2024, Copenhagen. Fill sameAs in the homepage JSON-LD with
   the LinkedIn company page, the founder's LinkedIn, Crunchbase and GitHub.
   The seo_dd gate already checks for exactly one Organization; keep it that
   way.
3. **Unlinked mentions.** Ahrefs Content Explorer for "yellow3" and
   "yellow3 lab", minus the own domain. Every mention without a link gets a
   one-line request with the canonical URL.

### 3.4 Tier B: the suppliers (the largest lever, already warm)

172 commercial suppliers each have a website. Six have already claimed. A
supplier linking to its own independently researched profile is the most
natural link on the web.

- Add one paragraph to the claim-confirmation email and to the company-layer
  editor: "Your profile is public at [URL]. If you want to reference it,
  here is a plain link and a one-line description you can use." Provide the
  HTML snippet. No badge image, no reciprocal wording, no incentive.
- Email the six companies that already claimed, thank them, give them the
  link, and ask one question: what would make the profile more useful to
  their buyers. That reply is product research and a relationship.
- Answer the correction letter of 4 August and take the call it offered. It
  came from someone who helps maintain the GS1 standards the register cites.
  That conversation is worth more than fifty cold emails, and a corrected
  record with the open-source sources it named is a public example of the
  register working.
- Every future correction gets a reply with the profile URL. Every profile
  that reaches "company-supplied layer present" gets the same paragraph.

### 3.5 Tier C: reference pages, directories and dataset registries (DPP)

Ask for inclusion as a research resource, offering the dataset and the
licence. In priority order:

| Target | Why | The ask |
|---|---|---|
| Zenodo | Gives the dataset a DOI, a landing page and a citation format; academic and consultancy citations follow the DOI back | Deposit suppliers.csv and suppliers.json with the CC BY 4.0 licence and the register URL as the related identifier. Re-deposit each quarter as a new version. |
| Google Dataset Search | The Dataset JSON-LD is already generated; confirm it is indexed | Search the register name; if absent, submit the sitemap in Search Console and check the structured-data report. |
| Hugging Face Datasets, Kaggle | Mirrors with mandatory attribution; the README links back | Publish the CSV with the licence text and the canonical URL. |
| GitHub | A public dataset repository with a README | Release the export there with the same licence; developers link to GitHub more readily than to a website. |
| Wikipedia "EU Digital Product Passport", Wikidata | External links and a Wikidata item for the register | Do not self-add. Propose on the article talk page as an independent dataset; create the Wikidata item with the URL and licence. |
| CIRPASS-2 resources, GS1 Denmark, GS1 in Europe DPP page | The reference pages every DPP search lands on | Offer the dataset as a resource for their members; ask for listing under resources. |
| Battery Pass consortium, Global Battery Alliance | Battery is the first deadline | Offer a battery-sector cut of the register. |
| Textile Exchange, Fashion for Good, Policy Hub | Textiles is the largest sector in the register | Offer a textile-sector cut. |
| Dansk Industri, Dansk Erhverv, Lifestyle & Design Cluster, Erhvervsstyrelsen, Danish Design Centre | Danish resource pages on DPP | Offer the register and a Danish-language summary. |
| productipedia.com compliance resources, circularise.com "organisations driving DPP", oneclicklca DPP guide, dppindex.eu, digital-product-passport.pro | Pages that already list DPP resources and directories | Ask for inclusion as an independent register; for dppindex.eu specifically, as a research resource rather than a provider. |

### 3.6 Tier D: press, DPP

The pitch is a number from the register, not a company story. Candidate
headlines: "191 organisations now sell Digital Product Passport capability,
and 33 countries", "Germany has 37 DPP suppliers, France 13, Denmark [n]",
"Only [n] of 172 suppliers publish evidence for [check]". Each release is a
short page on yellow3.io with the chart, the CSV link and the method.

| Outlet | Desk / angle |
|---|---|
| Table.Briefings ESG.Table | Already covers DPP delegated acts; German supplier count |
| Ecotextile News, Just Style, Vogue Business, FashionUnited, Drapers | Textile DPP; supplier landscape for brands |
| ESG Today, Sustainable Brands, edie, Circular Online | Sustainability trade; the dataset |
| Euractiv circular economy, Packaging Europe, electronica.de industry portal | EU policy and electronics |
| Børsen, Finans, Ingeniøren, Dansk Mode & Textil | Danish business and trade press; the Copenhagen research lab angle |
| Podcasts: Scandinavian MIND, Innovation Forum, Digital Product Passport Insights (4TheRecord), WGSN Create Tomorrow, Beyond Threads | Founder as guest; the show notes link is the backlink |

### 3.7 Tier E: press and roundups, AI model adoption

Everyone writing "Chinese models overtake US on OpenRouter" is using the same
source yellow3 measures daily. yellow3's differentiated statistic is origin
region and, specifically, Europe's routed share. Offer the weekly figure, the
top-10 image, and an embeddable chart with an attribution link.

| Target | Why |
|---|---|
| trendingtopics.eu, Sifted, Tech.eu, The Decoder, Heise, Golem | European tech press already covering the Chinese-share story; the Europe number is the missing paragraph |
| Merics, CEIBS, Bruegel | Think tanks citing token share; they cite datasets, and cite them for years |
| CNBC Europe, The Register | Ran the story in July; offer the weekly update |
| aicost.org, digitalapplied.com, macgpu.com, nodemini, zukcloud, tokenmaxxing, wandabuilds, tech-insider | Monthly OpenRouter roundup bloggers; offer the data feed and the embed, ask for attribution |
| Hacker News "Show HN", r/LocalLLaMA | The live instrument as a launch post, once, with the method |

### 3.8 Tier F: expert-source platforms

Register the founder on two of Qwoted, Featured.com and Help a B2B Writer.
Answer only DPP and AI-market questions, always with a register or instrument
number. Each placement is a link from a publication that would never answer a
cold pitch.

### 3.9 Templates

**Supplier, profile live**

> Subject: Your [Company] profile on the yellow3 DPP Supplier Register
>
> Your claim went through and the profile is public at [URL]. The independent
> research and your company-supplied information stay on separate layers, and
> you can edit yours at any time. If it is useful to reference the profile,
> here is a plain link: `<a href="[URL]">[Company] on the yellow3 DPP Supplier
> Register</a>`. One question, if you have a minute: what would make the
> profile more useful to the buyers you talk to?

**Resource page or organisation**

> Subject: An open dataset of the Digital Product Passport supplier market
>
> yellow3 lab publishes an independent register of organisations supplying
> Digital Product Passport capability: 191 organisations across 33 countries,
> each headquarters sourced and dated, released as CSV and JSON under
> CC BY 4.0. Suppliers cannot pay to appear or rank. Your [resources page]
> lists [what they list]; the register may be useful beside it. Landing page:
> [URL]. Happy to provide a [sector] cut if that is more useful to your members.

**Journalist**

> Subject: [Number] in one line, with the data behind it
>
> [One sentence with the number.] It comes from [instrument], which yellow3
> lab updates [cadence] with the method and sources published. The chart, the
> CSV and the method are at [URL]. If it fits a piece, I can give you the
> [sector or region] breakdown by return.

---

## 4. The Cowork brief for tomorrow morning

Every task names its tool, its output, and what "done" looks like. Tasks 1 to
6 are the morning. Nothing below changes site copy without a GPT ruling.

| # | Task | Tool | Output | Done when |
|---|---|---|---|---|
| 1 | Enable Vercel Web Analytics on project `yellow3` and load its script only from consent.js, behind consent. This is not optional: build_check.py asserts "analytics loads only from consent.js", and that script is the Vercel build command, so a tag dropped straight into a page fails the build and production silently keeps the last good deploy. | Vercel dashboard, repo | Analytics on, behind consent | Pageviews visible for the register and the readiness CTA after consent |
| 2 | Export Google Search Console: last 90 days, pages and queries, plus the coverage report | Search Console | `research/seo/gsc-2026-09-02.csv` | Top 50 pages by clicks known |
| 3 | Export Ahrefs Site Explorer for yellow3.io: referring domains, "Best by links", "Broken backlinks", and Content Explorer unlinked mentions | Ahrefs | One spreadsheet, four tabs | Every URL that ever earned a link is listed with its status |
| 4 | Ten legacy 301s are written, gated and pushed on this branch (see 1.5). Remaining: merge, then verify each on production, and add a redirect for every further URL the Ahrefs broken-backlink export in task 3 turns up. | Repo | Redirects live | Each legacy URL returns 301 to a live page on www.yellow3.io |
| 5 | Entity clean-up: Google Business Profile, Crunchbase, LinkedIn company page, the data-broker listing; draft the sameAs list for the homepage JSON-LD and send to GPT as a request. Decided by Thomas on 2 September: Copenhagen is the location yellow3 states everywhere people read. The Hørsholm address in the privacy notice is the registered office (CVR 44954087) and stays only where the law requires it: privacy, terms, invoices. "Hørsholm" never appears in narrative copy or on listings. Google Business Profile pins the address it is given, so either use a Copenhagen address or set the profile as a service-area business with the address hidden and Copenhagen as the area. | Browser, repo | Checklist with status | No public listing says Inc, Netherlands or 2023, and every listing carries the same address |
| 6 | Write and send the supplier "profile live" email to the six companies that already claimed; draft the paragraph for the claim-confirmation email and the editor, and send it to GPT for a ruling | Gmail, repo | Six emails sent, one copy request | Replies logged |
| 7 | Reply to the 4 August correction letter and propose a call this week. Prepare by reading the company's row in `research/dpp-capability.json` against the sources the letter lists. | Gmail | Reply sent | Call booked |
| 8 | Deposit the dataset on Zenodo (CC BY 4.0, related identifier = register URL); publish the same files to a public GitHub repository and to Hugging Face Datasets with the licence and canonical URL in the README | Zenodo, GitHub, Hugging Face | Three URLs, one DOI | DOI resolves; each README links to the register |
| 9 | Build the outreach sheet: 40 targets from sections 3.5 to 3.7 with the named page, a contact, the asset offered, the template used, send date, outcome | Sheet | `outreach-2026-09.csv` | Every row has a contact and an angle |
| 10 | Send the first 15 outreach emails (5 resource pages, 5 DPP press, 5 AI press) using the templates in 3.9, personalised with one line about the target's page | Gmail | 15 sent | Logged in the sheet |
| 11 | Build the buyer outbound list: 50 companies in batteries and textiles with EU exposure, the deadline that applies to each, and one register finding relevant to a supplier they may be evaluating | Sheet, register | `buyers-2026-09.csv` | 50 rows with a named contact |
| 12 | Draft the readiness-review offer email and the LinkedIn post that goes with the next Monday Briefing; send both to Thomas for approval | Docs | Two drafts | Approved |
| 13 | Request the GPT rulings needed for section 2.4: capability-check labelling, participation disclosure, EU Desk price and route, payment links for the four advisory products | Docs | One request document with the four items and the reason for each | Sent |
| 14 | Register the founder on two expert-source platforms and set alerts for "digital product passport" and "AI model usage" queries | Qwoted, Featured.com | Accounts live | First answer submitted |
| 15 | Weekly scorecard (section 5) as a single file updated every Monday | Repo | `research/growth-scorecard.md` | Week 1 row filled |

Week 2 onward: one insight a week built on register or instrument data, one
press release page per month, the next 15 outreach emails each week, replies
handled within a day, and the scorecard filled every Monday.

---

## 5. Measurement

| Metric | Source | Cadence |
|---|---|---|
| Referring domains, new backlinks | Ahrefs Site Explorer | Weekly |
| Organic clicks and impressions, top queries | Search Console | Weekly |
| Pageviews on the register, the readiness CTA, the plans page | Vercel Web Analytics | Weekly |
| Free readiness starts, paid conversions | buyer.yellow3.io, Stripe | Weekly |
| Sessions, briefings, readiness reviews booked | Stripe | Weekly |
| Supplier claims and corrections | Shared inbox | Weekly |
| Outreach sent, replies, links won | Outreach sheet | Weekly |
| Insights published | feed.xml | Weekly |

If a number cannot be filled in on Monday, that is the finding for the week.

---

## 6. Thirty, sixty, ninety days

**By 1 October.** Analytics on. Legacy URLs redirected. Entity consistent.
Dataset on Zenodo with a DOI. Six supplier emails and the correction call
done. 45 outreach emails sent, first links from resource pages. Buyer outbound
list sent. EUR 10,000 booked from readiness reviews and sessions.

**By 1 November.** Two press placements citing the register. First
journalist using the Europe routed-share figure. Ten or more new referring
domains. Readiness funnel measured end to end. EUR 2,500 monthly recurring
from the Buyer Platform.

**By 1 December.** A quarterly register release with a press page. Twenty-five
new referring domains. EUR 5,000 monthly recurring plus EUR 20,000 one-off.
A decision, with data, on whether Model Intelligence stays a product or
becomes purely the press engine.

---

## 7. What was not verified, and how to verify it

| Claim in this document | How to confirm |
|---|---|
| The seven legacy URLs return 404 on production | `curl -sI https://www.yellow3.io/nfc-tags` and the others |
| buyer.yellow3.io free readiness and paid flows work end to end | Walk them as a new user with a test email |
| The Ahrefs backlink profile size and quality | Site Explorer export, task 3 |
| Register pages are the most visited part of the site | Only after task 1 or from Search Console |
