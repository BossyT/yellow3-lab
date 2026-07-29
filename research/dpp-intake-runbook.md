# DPP Supplier Register - intake runbook

The procedure a scheduled agent follows to turn submissions into register rows, with
no human in the loop. A human reads `dpp-intake-log.md` afterwards; a human does not
process anything.

`dpp_intake.py` decides. This runbook says how to feed it. **Do not exercise judgement
the script does not ask for** - if you find yourself arguing for a value the script
rejected, the script is right and the evidence is thin.

---

## 1. Take the queue

Pending submissions live in Blob under `dpp/suggestions/<domain>.json`, written by
`api/suggest.js`. Each is:

```json
{"domain":"acme.com","company":"Acme","email":"anna@acme.com",
 "submitted_at":"2026-07-29","status":"queued"}
```

Read them with `BLOB_PUBLIC_RW_TOKEN` (Vercel env). Skip any with `status` other than
`queued`.

## 2. Research each company - read, do not infer

For each domain, open **the site itself**. Never a directory, never an aggregator,
never a press release repackaging someone else's claim.

Fetch, in this order, stopping when you have what you need:

1. the homepage
2. the product or platform page
3. the imprint / legal notice / terms / privacy page - this is where identity lives
4. any page whose URL or title mentions "digital product passport"

For every value you intend to record, capture **the URL and the sentence on that page
that states it**. Not a paraphrase. The exact sentence. The script compares the two and
drops anything the quote does not support - a paraphrase will be rejected, correctly.

### The gate

Is there a public sentence in which **the company describes capability it supplies**?

- "Our platform generates Digital Product Passports" - yes
- "A Digital Product Passport is a digital record linked to a product" - **no.** That
  describes the regulation, not their product. This is the exact mistake that put a
  company in the register under the wrong entity type on 29 Jul 2026.

If the only DPP mentions are explanatory, educational or about the 2027 deadline, the
outcome is `not_recorded`. That is a finding about the evidence, not about the company.

### Entity type - what they actually do, from their own words

| type | it is this when |
|---|---|
| `platform` | they generate, host or manage passports |
| `middleware` | they move or integrate passport data between systems |
| `identity-carrier` | they carry or present identity at the product - QR, NFC, tags |
| `erp-pim-plm` | passports are a feature of a larger product-data system |
| `consultancy` | they advise on DPP; the deliverable is services |
| `project-consortium` / `standards-body` / `not-a-supplier` | not a commercial supplier |

Presenting a passport someone else generates is `identity-carrier`, not `platform`.

## 3. Build the payload

```json
[{"domain":"acme.com","company":"Acme","submitted_email":"anna@acme.com",
  "values":{"hq_city":"Berlin","hq_country":"Germany","entity_type":"platform",
            "sectors_list":["textiles"]},
  "evidence":{
    "dpp_capability":{"url":"https://acme.com/product","quote":"<exact sentence>"},
    "hq_city":{"url":"https://acme.com/imprint","quote":"<exact sentence>"},
    "hq_country":{"url":"https://acme.com/imprint","quote":"<exact sentence>"}}}]
```

Every evidenced field needs its own `url` + `quote`. Reusing one imprint quote for both
city and country is fine - quote it under both.

Omit anything you could not source. Blank beats a guess, and the profile says so.

## 4. Run it

```
python3 research/dpp_intake.py payload.json          # dry run, read the reasons
python3 research/dpp_intake.py payload.json --apply  # write the register
python3 research/gen_dpp_register.py                 # rebuild the pages
```

Read the dry run. Every dropped field is telling you the evidence was weaker than you
thought. Do not work around it - go back and find a better source, or leave it blank.

## 5. Tell the company, then close the submission

- `recorded` -> **Letter A**, with the real profile and claim URLs
- `not_recorded` -> **Letter B**, with the pages you opened and what was missing
- `already_listed` -> point them at the existing profile and its claim link

Letters: `~/Documents/yellow3/dpp-directory/register-reply-letters.md`. Send with the
facts filled in; do not rewrite them. Same letter every time is the point.

Then set the submission's `status` to the outcome so it is not processed twice.

## 6. Commit

```
git add -A
git commit    # say which companies, which outcome, and why for each not_recorded
git fetch origin && git rebase origin/main && git push
```

The commit message is the audit trail a human reads later. Name the companies and the
reason for every refusal.

---

## What must never happen

- A value recorded without the sentence that supports it
- A country inferred from a domain ending, a company name or a legal suffix
- `verified` from anything but the company's own legal or registration statement
- A row created because someone asked, or asked twice
- A public list of companies that were not recorded - those replies are private
- Money involved in any of it, in either direction
