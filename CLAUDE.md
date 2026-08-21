# yellow3-lab — yellow3.io

The public site and the DPP Supplier Register. Static HTML, Python generators,
Vercel Blob. **Public repo** — nothing secret belongs in it. A LinkedIn launch
points here, so anything that breaks, breaks in front of an audience.

## The gate

```
python3 research/build_check.py
```

**It IS the Vercel build command.** A failing gate does not mean a warning — it
means the site does not deploy and production silently keeps serving the last
good build. That happened for three days in August 2026 and nobody noticed from
outside.

Run it before every commit and **again after a rebase** — a rebase is a new
tree, and skipping that step is exactly how a broken build shipped once.

Other gates, all in `research/`: `site_nav`, `site_audit`, `seo_dd`,
`platforms_freeze`, `instrument_health`, `type_freeze`, `cadence_check`,
`dpp_intake_spec_test`.

## Audit production, not the repo

`generate-sitemap.js` rewrites the bare host to `www` across every static file
at deploy and regenerates `sitemap.xml`, so the committed copies are always one
build behind. Checking them produced 48 findings that did not exist live.

Measure the artefact. And **check your checkout is current** before raising an
alarm — a stale local tree produced two confident, wrong findings in one morning.

## The register is PUBLIC on purpose

Free, CC BY 4.0, 190 organisations, providers never pay. Company descriptions,
logos, sectors and dates being world-readable **is the product**, not a leak.
Do not "fix" it.

What genuinely does not belong in public objects is a **person**. `api/supplied.js`
stores `updated_by_domain` and `licence.granted_by_domain` — the domain, never
the address. Claiming already requires a work email matching the row's domain,
so the domain carries the whole audit property and the local part proves nothing.

The public blob store is `tdkaavtl8194sgs0.public.blob.vercel-storage.com`.
**The index is not the store**: `dpp/supplied/_index.json` listed four ids while
the store held five. Anything that sweeps it must walk `list(prefix:)`.

To write to it without handling a token: `vercel login`, then
`vercel blob put <file> --pathname <path> --allow-overwrite`. The dashboard has
no in-place replace, but delete-then-upload achieves the same thing. **Two
stores are connected** — target `store_TDKaAvtl8194sGs0` explicitly, or default
resolution writes to the other one.

## Company text is the company's words

Never pass register descriptions through a renderer, a text extractor or an
editor. One round-trip through a page-to-text pipeline silently turned a curly
apostrophe straight and collapsed a double space. "Nearly what they wrote" is a
different product from "what they wrote". Upload files from disk and byte-compare
afterwards — checking only for the thing you meant to fix will not tell you what
else moved.

## The register queue

`/api/queue-status` returns counts only, by design: the intake runbook forbids a
public list of companies that were not recorded. So when a gate fires on a
count, **go and read the rows before you believe the noun** — the build blocked
for three days over "a company has been waiting 23 days" that turned out to be
Thomas's own test submission plus a probe on a reserved TLD.

Our own domains and RFC 2606/6761 reserved TLDs are never counted as a company.

## Design and copy

ChatGPT designs, this repo integrates. The public site is design-frozen: fix
defects, change no copy or layout without Thomas or GPT asking. Brand is
lowercase — "yellow3 lab", "naffe.ai".

## The specs live beside the code

`research/dpp-intake-runbook.md`, `research/dpp-sweep.md`,
`research/GATING-SETUP.md`, and long headers on `api/claim.js`, `api/supplied.js`
and every generator in `research/`. Read the runbook and the module header
before investigating, changing, or telling anyone something is broken.
