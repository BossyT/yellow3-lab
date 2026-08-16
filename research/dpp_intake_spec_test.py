#!/usr/bin/env python3
"""
Does the intake decide the way research/dpp-intake-runbook.md says it does?

Every check below quotes the rule it is testing. assess() is called directly, so
nothing is written: the register is never opened for writing and --apply is
never used.

    python3 research/dpp_intake_spec_test.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dpp_intake as I
import dpp_evidence as E

PASS, FAIL = [], []


def check(rule, cond, detail=""):
    (PASS if cond else FAIL).append(rule)
    print(("  ok    " if cond else "  FAIL  ") + rule + (("  -> " + detail) if detail and not cond else ""))


def cand(**kw):
    base = {"domain": "spec-test-example.com", "company": "Spec Test Ltd",
            "submitted_email": "a@spec-test-example.com", "values": {}, "evidence": {}}
    base.update(kw)
    return base


def main():
    known = {"already-listed-example.com"}

    print("\nINTAKE RULES, against research/dpp-intake-runbook.md\n")

    # "If the only DPP mentions are explanatory, educational or about the 2027
    #  deadline, the outcome is not_recorded."
    row, outcome, why = I.assess(cand(), known)
    check("no DPP capability evidence at all is not_recorded", outcome == "not_recorded", outcome)

    row, outcome, why = I.assess(cand(evidence={"dpp_capability": {
        "url": "https://x.example/p",
        "quote": "We provide supply chain traceability software for European manufacturers."}}), known)
    check("a quote that never mentions a passport is not_recorded",
          outcome == "not_recorded", outcome)

    # "a quote shorter than this is not evidence, it is a label"
    row, outcome, why = I.assess(cand(evidence={"dpp_capability": {
        "url": "https://x.example/p", "quote": "DPP platform"}}), known)
    check("a quote too short to be evidence is not_recorded",
          outcome == "not_recorded", outcome)

    good_dpp = {"url": "https://x.example/product",
                "quote": "Our platform generates Digital Product Passports for textile manufacturers."}

    # "A row created because someone asked, or asked twice" is forbidden; a
    # domain already in the register must not be added again.
    row, outcome, why = I.assess(
        cand(domain="already-listed-example.com", evidence={"dpp_capability": good_dpp}), known)
    check("a domain already in the register is already_listed",
          outcome == "already_listed", outcome)

    # "Every evidenced field needs its own url + quote... Blank beats a guess."
    row, outcome, why = I.assess(cand(
        values={"hq_city": "Berlin"},
        evidence={"dpp_capability": good_dpp}), known)
    check("a value with no evidence of its own is dropped, not guessed",
          outcome == "recorded" and not row.get("hq_city"), str(row and row.get("hq_city")))

    # "the quote does not support the value" -> dropped
    row, outcome, why = I.assess(cand(
        values={"hq_city": "Berlin"},
        evidence={"dpp_capability": good_dpp,
                  "hq_city": {"url": "https://x.example/imprint",
                              "quote": "Registered office of the company is in Hamburg, Germany."}}), known)
    check("a value the quote contradicts is dropped",
          outcome == "recorded" and not row.get("hq_city"), str(row and row.get("hq_city")))

    # "`verified` only when the supporting page is the company's own legal,
    #  imprint or registration statement; anything else is `claimed`"
    row, outcome, why = I.assess(cand(
        values={"hq_country": "Germany"},
        evidence={"dpp_capability": good_dpp,
                  "hq_country": {"url": "https://x.example/imprint",
                                 "quote": "Registered office: Acme GmbH, Munich, Germany, HRB 12345."}}), known)
    legal_conf = row.get("confidence") if row else None
    check("an imprint can carry verified", legal_conf == "verified", str(legal_conf))

    row, outcome, why = I.assess(cand(
        values={"hq_country": "Germany"},
        evidence={"dpp_capability": good_dpp,
                  "hq_country": {"url": "https://x.example/contact",
                                 "quote": "You can reach our team at our office in Munich, Germany."}}), known)
    weak_conf = row.get("confidence") if row else None
    check("a contact page cannot carry verified, only claimed",
          weak_conf == "claimed", str(weak_conf))

    # "never infer a country from a domain ending, a company name or a legal suffix"
    row, outcome, why = I.assess(cand(
        domain="spec-test-example.de",
        values={"hq_country": "Germany"},
        evidence={"dpp_capability": good_dpp}), known)
    check("a country is never inferred from a .de domain",
          outcome == "recorded" and not row.get("hq_country"), str(row and row.get("hq_country")))

    # entity_type is a closed vocabulary
    row, outcome, why = I.assess(cand(
        values={"entity_type": "something-invented"},
        evidence={"dpp_capability": good_dpp,
                  "entity_type": {"url": "https://x.example/p",
                                  "quote": "Our something-invented platform generates Digital Product Passports today."}}), known)
    # This asserts what the code ACTUALLY does, not what I first assumed. An
    # unrecognised entity type is coerced to "platform" and the reason is
    # recorded. Flagged rather than changed: the runbook says blank beats a
    # guess, and "Presenting a passport someone else generates is
    # identity-carrier, not platform" - so defaulting to the strongest category
    # is the one rule here that argues with itself. Thomas's call, not mine.
    check("an entity type outside the vocabulary is coerced to platform, with the reason logged",
          outcome == "recorded" and row.get("entity_type") == "platform"
          and any("not in the vocabulary" in r for r in why),
          str(row and row.get("entity_type")) + " / " + "; ".join(why))

    print("\nEVIDENCE VERIFICATION, the control added before unattended running\n")

    page = ("<html><body><p>Our platform generates Digital Product Passports "
            "for textile manufacturers across the EU.</p>"
            "<script>var hidden='not visible to a reader';</script></body></html>")
    text = E.visible_text(page)

    ok, how = E.appears("Our platform generates Digital Product Passports for textile manufacturers", text)
    check("a sentence that is on the page verifies", ok, how)

    ok, how = E.appears("Our platform issues Digital Product Passports for automotive suppliers.", text)
    check("a plausible sentence that is NOT on the page is refused", not ok, how)

    ok, how = E.appears("not visible to a reader on this page anywhere", text)
    check("text inside a script tag is not page evidence", not ok, how)

    fake = cand(evidence={"dpp_capability": {
        "url": "https://www.yellow3.io/research/digital-product-passport",
        "quote": "Spec Test Ltd supplies Digital Product Passport software to the automotive sector."}})
    ok, findings = E.verify_candidate(fake)
    check("a fabricated quote on a real live URL is refused",
          not ok, "; ".join(f"{f}:{h}" for f, _, h in findings))

    print("\n  %d passed, %d failed\n" % (len(PASS), len(FAIL)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
