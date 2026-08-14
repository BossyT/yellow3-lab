# Privacy and consent: what is still outstanding

Logged 14 August 2026, after the pre-campaign audit. Not a launch blocker for
the two direct-link campaigns; explicitly deferred by GPT rather than forgotten.

## 1. Google Analytics on the rest of yellow3.io

**State:** the DPP Supplier Register is clean - 535 pages, GA removed and
verified absent on live pages, with `research/ga_remove_register.py --check` as
the regression guard.

**Outstanding:** 99 other pages still load GA4 (`G-K3JXMM2VG5`) unconditionally,
with no consent gate. The homepage, research instruments, platforms, about,
advisory, insights and the legal pages themselves.

**Why it matters:** analytics cookies are set for EU visitors before any
consent. Disclosure in the cookie policy does not cure that under ePrivacy; the
requirement is prior consent for non-essential cookies. It is also inconsistent:
a visitor who lands on the homepage and then reaches the register already
carries GA cookies, so the register is only clean on a direct visit.

**The two ways out, and the choice is commercial:**

  a. Remove GA site-wide, as was done for the register. Costs the analytics.
     `research/ga_remove_register.py` is the pattern; the target list changes.

  b. Keep GA and build a real consent gate: no analytics script until consent,
     a genuine reject option, a stored preference, and a way to withdraw. That
     is a deliberate piece of design, not a banner bolted on before a campaign,
     which is exactly why it was deferred.

**Do not** do half of it. A banner that loads GA before the visitor answers is
worse than no banner, because it documents the problem.

## 2. Cookie policy scope, once (1) is decided

The policy now covers yellow3.io and buyer.yellow3.io and lists the Buyer
Platform's post-sign-in cookies. If GA goes site-wide, the three GA entries come
out with it; if a consent gate lands, the policy needs the withdrawal route.

## 3. Retention, the part that is still theoretical

Founding applications expire at 12 months, enforced in the database and swept by
the cron. Programme retention can now start, because programmes can be closed -
but no programme has ever been closed, so the 24-month path has never run end to
end. Worth a deliberate rehearsal on a scratch programme before any real one
reaches its window.
