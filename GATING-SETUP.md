# Model Intelligence — report gating: activation guide

Everything is built on branch **`mi-gating`** (preview only — NOT on production).
It stays inert until the env vars below exist, so nothing here can break the live
site before you activate it. No secrets are stored in this repo.

## What's built

- **Magic-link auth** (`api/auth/request|verify|logout`, `api/me`, `api/_lib/util.js`):
  a visitor enters their email → we verify an **active Stripe subscription** (exact
  customer email, or any colleague on a Team buyer's company domain) → email a
  one-time sign-in link → 30-day signed session cookie. No passwords, no database —
  Stripe is the user store.
- **Private report delivery** (`api/report.js`): streams the report PDF **only** to a
  signed-in session, pulling it from private storage. Without a session, no bytes.
- **Pages**: `login.html` (magic-link request) and a gated `access.html` (checks
  `/api/me`, redirects to login if not signed in, shows the report + a Billing panel
  with a "Manage subscription & invoices" button + sign-out).

## Your part — one-time setup

### 1. Vercel env vars (project "yellow3", add to **Preview + Production**)
| Var | What | Where to get it |
|-----|------|-----------------|
| `AUTH_SECRET` | signs sessions | I generated one — paste the value I gave you in chat (or `openssl rand -hex 32`) |
| `STRIPE_SECRET_KEY` | verify subscriptions | Stripe → Developers → API keys → **Create restricted key**, read-only on **Customers** + **Subscriptions**, nothing else |
| `RESEND_API_KEY` | send the sign-in email | Resend → API Keys |
| `FROM_EMAIL` | sender | e.g. `yellow3 Model Intelligence <access@yellow3.io>` |
| `REPORT_URL` | private report location | the Vercel Blob URL from step 3 |
| `BLOB_READ_WRITE_TOKEN` | read the private blob | Vercel → Storage → your Blob store → tokens |

### 2. Resend (sends the sign-in link)
- Create a Resend account, add domain **yellow3.io**, add the DNS records Resend
  shows (SPF/DKIM), wait for "Verified". (If Resend is already set up for naffe, add
  yellow3.io as a second domain — domains are independent.)

### 3. Vercel Blob (private report storage)
- Vercel → Storage → Create a **Blob** store.
- Upload the report PDF to it (I can do this once the store exists, or you drag-drop
  it). Copy its URL → that's `REPORT_URL`. Copy a read/write token → `BLOB_READ_WRITE_TOKEN`.

### 4. Stripe Customer Portal (this is your "invoices + cancel", Dashboard-only)
- Stripe → Settings → Billing → **Customer portal**: turn on **Invoice history** and
  **Cancel subscriptions** (mode: at end of period), enable the **login link**.
- Copy the login-link URL → paste it into `access.html` where it says
  `REPLACE_WITH_YOUR_STRIPE_PORTAL_LINK` (tell me and I'll do it).
- Stripe → Settings → Billing → Invoices: turn on **Email finalized invoices to
  customers** so buyers receive each invoice automatically. (Subscriptions already
  generate an invoice every cycle regardless.)

## Activation (my part, once the above exists)

1. Test the whole flow on the **preview URL**: email → link → session → `/api/report`
   serves the PDF; a non-subscriber email gets nothing.
2. **Make the report truly private** (the cutover): upload the PDF to Blob, then
   remove the public copy so it is gated for real —
   - delete `research/model-adoption/reports/downloads/<month>.pdf` from the repo,
   - retire the public read-online full report: point the archive's Read/Download to
     the access flow, and change `gen_report.py` so the full report HTML is not
     published to a public path (the free **briefing** stays public).
3. Wire the portal URL into `access.html`.
4. Merge `mi-gating` → `main`. Post-checkout, Stripe already redirects buyers to the
   access page, which now sends them through login.

## Notes
- The restricted key is **read-only** — the site never writes to Stripe. The portal
  is Stripe-hosted, so no write key is needed.
- Team access = any colleague on the buyer's company email domain (public mailbox
  domains like gmail/outlook are excluded, so those buyers get exact-email only).
- Product entitlement map (`api/_lib/util.js` PRODUCTS): Professional
  `prod_Usp3qVABNp8n0g`, Team `prod_UspZO2dhBkJTMc` (both verified live 2026-07-20).
