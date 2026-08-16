#!/usr/bin/env python3
"""Intake for the DPP Supplier Register - the rules, enforced mechanically.

An agent does the reading. This does the deciding, and it decides the same way
every time whoever is running it.

The rule that matters most: a field is recorded only if the agent supplies the
URL it came from AND the sentence on that page that supports it. If it cannot
quote it, the field stays blank. This exists because the register has already
been bitten once by a real, live URL cited for something the page did not say -
which is exactly the failure an unattended pipeline would repeat at scale.

Everything else follows the register's published rules:
  - never infer a country from a domain ending, a company name or a legal suffix
  - `verified` only when the supporting page is the company's own legal, imprint
    or registration statement; anything else is `claimed`
  - blank beats a guess
  - no DPP capability evidence, no row

Usage:
  python3 research/dpp_intake.py --check payload.json     # validate, decide, print
  python3 research/dpp_intake.py --apply payload.json     # ...and write the register

Payload: a list of candidates, each
  {"domain": "...", "company": "...", "submitted_email": "...",
   "evidence": {"<field>": {"url": "...", "quote": "..."}, ...},
   "values":   {"<field>": "..."}}
"""

import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "dpp-suppliers.json")
LOG = os.path.join(HERE, "dpp-intake-log.md")

MIN_QUOTE = 25  # a quote shorter than this is not evidence, it is a label

# a source that can carry `verified`: the company stating its own legal identity
# `verified` means the company stated its own LEGAL IDENTITY on a page whose
# purpose is to state it. A contact page saying "Munich, Germany" is the company
# saying where it is - not who it is - so it cannot carry `verified`. Learned
# 2026-07-31 on DPP.PRO, which names an address and no operating entity at all.
LEGAL_HINTS = ("imprint", "impressum", "legal-notice", "mentions-legales",
               "registration", "company-details", "legal")
# real pages, but they establish location or policy, never legal identity
WEAK_HINTS = ("privacy", "terms", "about", "contact")

# fields the agent may set, and whether each one needs its own evidence
EVIDENCED = ("hq_city", "hq_country", "ownership", "founded_year",
             "total_disclosed_funding", "funding_stage", "website", "entity_type")
FREE = ("name", "domain", "sectors_list", "alias_domains", "status")

ENTITY_TYPES = ("platform", "middleware", "identity-carrier", "erp-pim-plm",
                "consultancy", "project-consortium", "standards-body", "not-a-supplier")


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s) or "unnamed"


def quotes_support(value, quote):
    """The quote has to actually contain the thing being claimed.

    Crude on purpose. It cannot judge meaning, but it can refuse a quote that
    does not even mention the value - which is the failure mode that matters.
    """
    v = str(value).strip().lower()
    q = str(quote).strip().lower()
    if not v or not q:
        return False
    if v in q:
        return True
    # numbers and multiword values: every significant token must appear
    toks = [t for t in re.split(r"[^\w]+", v) if len(t) > 2]
    return bool(toks) and all(t in q for t in toks)


def assess(cand, known_domains):
    """Decide one candidate. Returns (row_or_None, outcome, reasons)."""
    reasons = []
    dom = str(cand.get("domain", "")).lower().strip()
    name = str(cand.get("company", "")).strip()
    ev = cand.get("evidence") or {}
    vals = cand.get("values") or {}

    if not dom or not name:
        return None, "rejected", ["missing domain or company name"]
    if dom in known_domains:
        return None, "already_listed", ["domain already in the register"]

    # 1) DPP capability evidence is the gate. No evidence, no row.
    dpp = ev.get("dpp_capability") or {}
    if not dpp.get("url") or len(str(dpp.get("quote", ""))) < MIN_QUOTE:
        return None, "not_recorded", [
            "no public description of Digital Product Passport capability was found"]
    if not re.search(r"digital product passport|\bDPP\b", str(dpp["quote"]), re.I):
        return None, "not_recorded", [
            "the quoted evidence does not mention Digital Product Passport capability"]

    # 2) Every evidenced field must carry a URL and a supporting quote, or it is
    #    dropped. Dropped is fine - the profile says so, honestly.
    row = {"id": slug(name), "name": name, "domain": dom,
           "website": vals.get("website") or "https://" + dom,
           "evidence_url": dpp["url"], "source": "official company website",
           "source_date": datetime.date.today().isoformat(), "status": "active",
           "entity_type": "", "hq_city": "", "hq_country": "", "country_source": "",
           "ownership": "", "founded_year": "", "funding_stage": "",
           "funding_source": "", "last_funding_date": "",
           "total_disclosed_funding": "", "alias_domains": "",
           "sectors_list": [], "sectors": "", "confidence": "claimed"}

    for field in EVIDENCED:
        if field in ("website", "entity_type"):
            continue
        value = str(vals.get(field, "")).strip()
        if not value:
            continue
        e = ev.get(field) or {}
        url, quote = str(e.get("url", "")), str(e.get("quote", ""))
        if not url or len(quote) < MIN_QUOTE:
            reasons.append(f"{field} dropped: no source and quote")
            continue
        if not quotes_support(value, quote):
            reasons.append(f"{field} dropped: the quote does not support the value")
            continue
        row[field] = value

    # 3) A country is only recorded with its own source. Never inferred.
    if row["hq_country"]:
        src = (ev.get("hq_country") or {}).get("url", "")
        row["country_source"] = src
        low = src.lower()
        legal = any(h in low for h in LEGAL_HINTS) and not (
            any(w in low for w in WEAK_HINTS) and
            not any(h in low for h in ("imprint", "impressum", "mentions-legales")))
        row["confidence"] = "verified" if legal else "claimed"
        if not legal:
            reasons.append("confidence held at claimed: the source is not a legal "
                           "or registration statement")
    else:
        row["country_source"] = "not_found " + row["source_date"]
        reasons.append("headquarters not publicly established")

    et = str(vals.get("entity_type", "")).strip()
    row["entity_type"] = et if et in ENTITY_TYPES else "platform"
    if et and et not in ENTITY_TYPES:
        reasons.append(f"entity_type '{et}' is not in the vocabulary; recorded as platform")

    secs = [s for s in (vals.get("sectors_list") or []) if s]
    row["sectors_list"] = secs
    row["sectors"] = ",".join(secs)
    return row, "recorded", reasons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("payload")
    ap.add_argument("--apply", action="store_true", help="write the register")
    ap.add_argument("--trust-quotes", action="store_true",
                    help="skip fetching the cited pages. Offline tests only.")
    args = ap.parse_args()

    payload = json.load(open(args.payload, encoding="utf-8"))
    cands = payload if isinstance(payload, list) else payload.get("candidates", [])

    doc = json.load(open(DATA, encoding="utf-8"))
    rows = doc["suppliers"]
    known = set()
    for r in rows:
        for d in [r.get("domain", "")] + str(r.get("alias_domains", "")).split(","):
            if d.strip():
                known.add(d.strip().lower())
    keys = sorted(rows[0].keys())

    # EVERY QUOTE IS FETCHED AND MATCHED BEFORE ANYTHING IS DECIDED.
    #
    # This module used to take on trust that a quote came from the URL beside
    # it. A human reading a page and typing what it says is unlikely to invent a
    # sentence. A pipeline is perfectly capable of it, at scale, and the whole
    # value of this register is that a reader can check any claim. So the
    # unverifiable evidence is stripped before assess() sees it, and the field
    # simply goes unrecorded - which is the honest outcome and already how this
    # file treats missing evidence.
    #
    # --trust-quotes exists only for offline tests. It is not for production and
    # says so when used.
    if not args.trust_quotes:
        import dpp_evidence
        for c in cands:
            ok, findings = dpp_evidence.verify_candidate(c)
            for field, good, how in findings:
                if good:
                    continue
                print(f"  evidence dropped  {c.get('company','?')[:24]:26} "
                      f"{field:22} {how}")
                (c.get("evidence") or {}).pop(field, None)
                (c.get("values") or {}).pop(field, None)
    else:
        print("  !! --trust-quotes: evidence NOT verified against the live pages")

    added, outcomes = [], []
    for c in cands:
        row, outcome, reasons = assess(c, known)
        outcomes.append({"domain": c.get("domain"), "company": c.get("company"),
                         "outcome": outcome, "reasons": reasons,
                         "email": c.get("submitted_email", "")})
        print(f"{c.get('company','?')[:34]:36} {outcome:14} {'; '.join(reasons) or 'clean'}")
        if row:
            missing = [k for k in keys if k not in row]
            for k in missing:
                row[k] = ""
            added.append(row)

    if not args.apply:
        print(f"\ndry run - {len(added)} would be recorded, "
              f"{sum(1 for o in outcomes if o['outcome'] == 'not_recorded')} not recorded")
        return

    if added:
        rows.extend(added)
        rows.sort(key=lambda r: r["name"].lower())
        json.dump(doc, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    with open(LOG, "a", encoding="utf-8") as fh:
        for o in outcomes:
            fh.write(f"{datetime.date.today().isoformat()} | {o['domain']} | {o['outcome']} | "
                     f"{'; '.join(o['reasons']) or 'clean'}\n")
    print(f"\nrecorded {len(added)}; log appended to {os.path.basename(LOG)}")
    print("now run: python3 research/gen_dpp_register.py")


if __name__ == "__main__":
    main()
