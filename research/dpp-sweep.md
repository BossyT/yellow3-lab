# DPP instrument - weekly sweep runbook

The Digital Product Passport instrument is labelled **"Live · updated weekly"**.
This is the routine that makes that true. Unlike Model adoption (a clean
OpenRouter API, fully automated), the DPP sources are regulatory web pages that
need reading and judgement, so the sweep is an **agent- or human-run routine**
with a deterministic helper, not a silent cron. A clean candidate to hand to a
naffe-operated agent later.

Cadence: **once a week** (and immediately when a call's resolution date passes).

Everything renders from `research/digital-product-passport.json`. The page holds
no hard-coded figures - change the JSON, the page changes.

---

## The five steps

**1. Re-check the sources.** Walk the list below; note any status change,
new date, or new evidence URL. Update the relevant milestone / signal in the
JSON (`status`, `delivered_date`, `count`, `value`, `evidence_url`,
`last_checked`).

| What | Where |
|---|---|
| ESPR base regulation, registry & customs articles | EUR-Lex - Reg. (EU) 2024/1781, Art. 13-14 |
| DPP service-provider delegated act (m4 / c2) | EUR-Lex "delegated acts" + Commission "Have your say" |
| Registry implementing regulation (m1 / c1) | Commission ESPR / DG GROW pages |
| DPP system standards, EN status (m2a / s4) | CEN-CENELEC JTC 24 work programme |
| Standards harmonised in the OJ (m2b / c3b) | EUR-Lex Official Journal (C series) |
| Product-group acts: iron & steel, textiles… (m5-m9) | ESPR Working Plan 2025-2030 |
| Customs interconnection (m3) | DG TAXUD |
| Industry signals (s1-s3) | CIRPASS-2; vendor mapping; GS1 Sunrise 2027 |

**2. Resolve any dated calls.** If a call's `resolution_date` has passed, grade
it HIT or MISS from the evidence - do not leave it open. The helper flags these
as **DUE FOR GRADING**.

**3. Recompute the scores.** The helper does this deterministically from the
milestones and signals, so the headline numbers can never drift from the data
beneath them.

**4. Rewrite "this week's read."** One honest headline + a short body on what
actually moved. Pass via `--headline` / `--body` or edit the JSON directly.

**5. Append, never overwrite.** The helper writes one line per sweep to
`research/dpp-changelog.md`. History is the credibility - it stays append-only.

---

## The helper

`research/dpp_sweep.py` (standard library only) does the mechanical parts:
recomputes Score_A / Score_B / call-record, flags due calls and past-date
milestones, stamps `week_of` + `last_checked`, and appends the changelog. It
does **not** scrape sources or decide outcomes - that judgement is steps 1, 2
and 4 above.

```bash
# dry-run report - changes nothing, just shows the state + what's due:
python3 research/dpp_sweep.py

# a normal weekly sweep once you've edited statuses/values in the JSON:
python3 research/dpp_sweep.py --write

# grade a call and refresh the read in one go:
python3 research/dpp_sweep.py \
    --grade c2=miss \
    --note c2="Resolution date passed with the service-provider delegated act still a draft; not adopted." \
    --evidence c2=https://eur-lex.europa.eu/... \
    --headline "First call graded: the EU missed its own service-provider deadline." \
    --write
```

`--date YYYY-MM-DD` overrides "today" (useful for testing or back-dating a sweep).

---

## Scheduled action - c2, 30 June 2026

Call **c2** ("the DPP service-provider delegated act will be adopted by
30 June 2026", lean `will_miss`) resolves on **30 June 2026**. Unless the act is
unexpectedly adopted, this is the instrument's **first graded call - a MISS**.
On/after that date, run the `--grade c2=miss` command above; the helper bumps
the public record to **0-1** and the changelog gets its first graded entry.

## Score model (reference)

- **Score_A** = `100 × Σ(weightᵢ × stateᵢ) / Σ(weightᵢ)` over *due* milestones
  (`target_date ≤ today`). State: delivered_on_time = 1.0, delivered_late = 0.5,
  slipped/missed = 0.0. Upcoming / in_progress are excluded until their date passes.
- **Score_B** = `100 × ` weighted mean of `value / ceiling` over signals that
  have a value. Signals with `value: null` are excluded. Tagged provisional
  until the proprietary onboarding signal replaces the basket.
- **Call record** = HITS-MISSES over resolved calls.
