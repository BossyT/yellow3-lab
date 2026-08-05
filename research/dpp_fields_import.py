#!/usr/bin/env python3
"""Fill missing sectors and headquarters on rows already in the register.

Same principle as dpp_intake.py: the agent supplies the source URL and the
sentence it read, the script decides what gets recorded. The failure mode here
is subtler than a wrong URL - it is an agent that "knows" a company does
textiles and writes it down without the company ever saying so. So:

  sectors     the agent NEVER names the sector. It supplies the sentence in
              which the company describes the industries it serves, and the
              mapping from the company's words to our eleven-sector vocabulary
              happens below, identically every run. A quote that maps to
              nothing is refused, not silently dropped - blank stays blank and
              the profile says so honestly.

  hq_country  evidenced, exactly as in intake: URL plus a quote that actually
  hq_city     contains the value. A country_source of "not_found <date>" is a
              dated finding and may only be replaced by a real source.

Usage:
  python3 research/dpp_fields_import.py fills.csv          # validate only
  python3 research/dpp_fields_import.py fills.csv --apply  # merge and write

CSV columns: supplier_id, hq_country, hq_city, sector_quote, source_url, quote,
             ownership_url (required only when source_url is off-domain)
Leave a column blank to leave that field alone.
"""

import argparse
import collections
import csv
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "dpp-suppliers.json")

MIN_QUOTE = 25

# The company's words on the left, our vocabulary on the right. This is the
# whole point of the script: the mapping is fixed, reviewable and applied the
# same way to every row, so a sector is never a judgement made in the moment.
#
# Matched on word boundaries, never as bare substrings - "entire" contains
# "tire" and would otherwise file half this register under tyres. Most of these
# suppliers are European and describe themselves in their own language, so the
# common German, Italian, French and Spanish terms are here too.
SECTOR_PATTERNS = {
    "textiles": r"textil\w*|tessil\w*|apparel|fashion|garment\w*|clothing|"
                r"footwear|shoes?|leather|denim|sportswear|abbigliamento|"
                r"bekleidung|v[êe]tements?|calzature|moda",
    "electronics": r"electronic\w*|elektronik|elettronic\w*|electr[óo]nic\w*|"
                   r"electrical|semiconductor\w*|white goods|appliances?|"
                   r"photovoltaic\w*|solar panels?",
    "batteries": r"batter\w*|batteri\w*|bater[íi]a\w*|accumulator\w*|"
                 r"cell manufactur\w*|energy storage|energiespeicher\w*",
    "construction": r"construction|construcci[óo]n|costruzion\w*|edilizia|"
                    r"b[âa]timent|baustoff\w*|building materials?|"
                    r"building products?|cement|concrete|insulation",
    "tyres": r"tyres?|tires?|reifen|pneumatic\w*|pneus|neum[áa]tico\w*",
    "furniture": r"furniture|furnishings?|m[öo]bel|mobili|arredamento|meubles|"
                 r"muebles|mattress\w*|materass\w*|matratzen",
    "food": r"food|foods|beverages?|agri\w*|wines?|vin[oi]?|wein|coffee|caff[èe]|"
            r"kaffee|seafood|dairy|fmcg|grocery|lebensmittel|alimentar\w*|"
            r"agroaliment\w*",
    "chemicals": r"chemicals?|chemie|chimic\w*|chimie|qu[íi]mic\w*|plastics?|"
                 r"plastica|plastique|kunststoff\w*|polymers?|paints?|coatings?|"
                 r"detergents?|resins?|packaging materials?",
    "automotive": r"automotive|automobil\w*|automoci[óo]n|vehicles?|veicol\w*|"
                  r"v[ée]hicules?|fahrzeug\w*|e-mobility|mobility|"
                  r"car manufactur\w*",
    "cosmetics": r"cosmetics?|cosmetici|cosm[ée]tique\w*|kosmetik|beauty|"
                 r"personal care|fragrances?|skincare",
    "general": r"cross[- ]industry|any industry|all industries|any sector|"
               r"all sectors|industry[- ]agnostic|sector[- ]agnostic|"
               r"multi[- ]sector|every industry|regardless of industry|"
               r"branchen[üu]bergreifend|jede branche|ogni settore|tutti i settori",
}
VOCAB = list(SECTOR_PATTERNS)
_RX = {s: re.compile(r"\b(?:%s)\b" % p, re.I | re.U) for s, p in SECTOR_PATTERNS.items()}


def sectors_from(quote):
    """Map a company's own sentence onto our vocabulary. Order is fixed."""
    q = re.sub(r"\s+", " ", str(quote or ""))
    return [s for s in VOCAB if _RX[s].search(q)]


# A German imprint says "Deutschland", not "Germany". The company is still
# stating its own seat, so the quote supports the value - but only through the
# name the page actually uses, never through a guess about a postcode or a
# phone prefix.
COUNTRY_ALIASES = {
    "germany": ("deutschland",), "italy": ("italia",), "spain": ("españa", "espana"),
    "netherlands": ("nederland",), "sweden": ("sverige",), "denmark": ("danmark",),
    "austria": ("österreich", "osterreich"), "norway": ("norge",),
    "finland": ("suomi",), "poland": ("polska",), "czech republic": ("česko", "cesko"),
    "switzerland": ("schweiz", "suisse", "svizzera"), "belgium": ("belgië", "belgique"),
    "turkey": ("türkiye", "turkiye"), "greece": ("ελλάδα",), "portugal": ("portugal",),
    "france": ("france",), "romania": ("românia", "romania"),
}


def quotes_support(value, quote):
    """The quote has to actually contain the thing being claimed."""
    v, q = str(value).strip().lower(), str(quote).strip().lower()
    if v in COUNTRY_ALIASES and any(a in q for a in COUNTRY_ALIASES[v]):
        return True
    if not v or not q:
        return False
    if v in q:
        return True
    toks = [t for t in re.split(r"[^\w]+", v) if len(t) > 2]
    return bool(toks) and all(t in q for t in toks)


def host(url):
    m = re.match(r"https?://([^/]+)", str(url or "").strip(), re.I)
    return (m.group(1).lower().replace("www.", "") if m else "")


def check(row, reg):
    """Return (updates, problems) for one CSV row."""
    up, bad = {}, []
    sid = (row.get("supplier_id") or "").strip()
    if sid not in reg:
        return {}, ["supplier_id is not in the register"]
    r = reg[sid]

    url = (row.get("source_url") or "").strip()
    quote = re.sub(r"\s+", " ", (row.get("quote") or "").strip())
    sq = re.sub(r"\s+", " ", (row.get("sector_quote") or "").strip())
    country = (row.get("hq_country") or "").strip()
    city = (row.get("hq_city") or "").strip()

    if not (country or city or sq):
        return {}, []  # nothing asked of this row

    if not url:
        bad.append("a fill needs the source_url it was read from")
    elif r.get("domain") and host(url) and not host(url).endswith(r["domain"]):
        # EVIDENCE OUTSIDE THE COMPANY'S OWN DOMAIN COUNTS.
        #
        # This used to be a flat refusal, and it was wrong. An infrastructure
        # vendor publishing under an open-source organisation, a package registry
        # or a hosted docs site was invisible to the register BY RULE - which is
        # how benelog came to be recorded as having no standards mapping while
        # publishing the most thorough JTC 24 mapping in the market. Reported by
        # Sven Boeckelmann, 2026-08-05, and he was right.
        #
        # What must not slip back in is the opposite error: crediting a company
        # for a repository that is not theirs. So an off-domain source is allowed
        # only when the LINK to the supplier is itself evidenced - normally the
        # supplier's own site linking to it, or the artifact naming the company.
        if not (row.get("ownership_url") or "").strip():
            bad.append(f"source_url is off-domain ({host(url)}); that is allowed, but "
                       f"give ownership_url - a page on {r['domain']} that links to it, "
                       f"or an artifact naming the company - so we are not crediting "
                       f"someone else's work")

    if sq:
        if len(sq) < MIN_QUOTE:
            bad.append("sector_quote is too short to be evidence")
        else:
            secs = sectors_from(sq)
            if not secs:
                bad.append("sector_quote names no industry this register recognises - "
                           "leaving the sector blank is the honest outcome")
            else:
                up["sectors_list"] = secs

    if country or city:
        if len(quote) < MIN_QUOTE:
            bad.append("hq needs the quote it was read from")
        if country and not quotes_support(country, quote):
            bad.append(f"the quote does not mention '{country}'")
        if city and not quotes_support(city, quote):
            bad.append(f"the quote does not mention '{city}'")
        if country:
            up["hq_country"] = country
        if city:
            up["hq_city"] = city
        up["country_source"] = url

    return up, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    data = json.load(open(DATA, encoding="utf-8"))
    reg = {r["id"]: r for r in data["suppliers"]}

    # A supplier may appear on more than one line: sites often list the
    # industries they serve as separate bullets, and one quote each is more
    # honest than picking the single bullet that reads best. Sectors are
    # unioned; a second, contradicting headquarters is refused.
    good, problems = {}, []
    with open(args.csv_path, newline="", encoding="utf-8-sig") as fh:
        for i, row in enumerate(csv.DictReader(fh, restkey="_spill"), start=2):
            sid = (row.get("supplier_id") or "").strip()
            if row.get("_spill"):
                # an unquoted comma silently truncates the quote it was read
                # from, which is the one thing this file must get right
                problems.append((i, sid, ["row has more columns than the header - "
                                          "a quote is probably missing its quotes"]))
                continue
            up, bad = check(row, reg)
            if bad:
                problems.append((i, sid, bad))
                continue
            if not up:
                continue
            prev = good.setdefault(sid, {})
            for f in ("hq_country", "hq_city"):
                if f in up and prev.get(f, up[f]) != up[f]:
                    problems.append((i, sid, [f"conflicting {f}: "
                                              f"'{prev[f]}' then '{up[f]}'"]))
            merged = sorted(set(prev.get("sectors_list", [])) | set(up.get("sectors_list", [])),
                            key=VOCAB.index)
            prev.update(up)
            if merged:
                prev["sectors_list"] = merged

    n_sec = sum(1 for u in good.values() if "sectors_list" in u)
    n_hq = sum(1 for u in good.values() if "hq_country" in u or "hq_city" in u)
    print(f"{len(good)} rows accepted   sectors {n_sec} / headquarters {n_hq}")
    hist = collections.Counter(s for u in good.values() for s in u.get("sectors_list", []))
    if hist:
        print("  sectors mapped: " + ", ".join(f"{k} {v}" for k, v in hist.most_common()))

    if problems:
        print(f"\n{len(problems)} row(s) refused:")
        for line, sid, bad in problems[:60]:
            print(f"  line {line:4} {sid:28} {'; '.join(bad)}")
        if len(problems) > 60:
            print(f"  ... and {len(problems) - 60} more")

    if not args.apply:
        print("\nvalidate only - nothing written.")
        return
    if problems:
        sys.exit("\nrefusing to import while rows are invalid.")

    today = datetime.date.today().isoformat()
    for r in data["suppliers"]:
        u = good.get(r["id"])
        if not u:
            continue
        if "sectors_list" in u:
            r["sectors_list"] = u["sectors_list"]
            r["sectors"] = ",".join(u["sectors_list"])
        for f in ("hq_country", "hq_city", "country_source"):
            if f in u:
                r[f] = u[f]
        r["source_date"] = r.get("source_date") or today

    json.dump(data, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    filled_s = sum(1 for r in data["suppliers"] if r.get("sectors_list"))
    filled_c = sum(1 for r in data["suppliers"] if (r.get("hq_country") or "").strip())
    print(f"\nwritten. register now holds {filled_s} rows with a sector and "
          f"{filled_c} with a country, of {len(data['suppliers'])}.")
    print("now run: python3 research/gen_dpp_register.py")


if __name__ == "__main__":
    main()
