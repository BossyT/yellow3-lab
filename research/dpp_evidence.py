#!/usr/bin/env python3
"""
Verify that a quoted sentence actually appears on the page it cites.

WHY THIS HAD TO EXIST BEFORE THE INTAKE COULD RUN UNATTENDED. dpp_intake.py
decides well, but it never opened the URL. It checked that a quote supported a
value and that the value was allowed - it took on trust that the quote came from
the page at all. Its own docstring names the risk: "the register has already
been bitten once by a real, live URL cited for something the page did not say -
which is exactly the failure an unattended pipeline would repeat at scale."

A human reading a page and typing what it says is unlikely to invent a sentence.
A pipeline is perfectly capable of it, cheerfully, at scale, and the register's
whole value is that a reader can check any claim. So the quote is now fetched
and matched before anything is recorded.

    python3 research/dpp_evidence.py payload.json        verify, print, exit 1 on any failure
    python3 research/dpp_evidence.py payload.json --prune  drop unverifiable fields, write back

Matching is deliberately forgiving about presentation and strict about words.
HTML entities, collapsed whitespace, curly quotes and soft hyphens all normalise
away; the words themselves must be there, in order.
"""

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.request

UA = "yellow3-register-intake (+https://www.yellow3.io/research/digital-product-passport/suppliers)"
TIMEOUT = 25
# Below this a "quote" is a label, not evidence. Same threshold the decider uses.
MIN_QUOTE = 25


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "text/html,*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read(3_000_000)
        charset = r.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def visible_text(doc):
    """What a reader sees. Scripts, styles and tags removed, entities resolved."""
    doc = re.sub(r"(?is)<(script|style|noscript|template)[^>]*>.*?</\1>", " ", doc)
    doc = re.sub(r"(?s)<!--.*?-->", " ", doc)
    doc = re.sub(r"(?s)<[^>]+>", " ", doc)
    return html.unescape(doc)


def normalise(s):
    """Fold away presentation so wording is what is compared."""
    s = html.unescape(str(s))
    s = s.replace("­", "")                      # soft hyphen
    s = re.sub(r"[‘’‚‛']", "'", s)
    s = re.sub(r"[“”„‟\"]", '"', s)
    s = re.sub(r"[‐-―−]", "-", s)     # dashes of every width
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def appears(quote, page_text):
    """Is the quoted wording on the page?

    Exact normalised containment first. Failing that, allow the quote to have
    been taken across an element boundary - a heading and its paragraph, say -
    by requiring every word in order rather than one unbroken run.
    """
    q, p = normalise(quote), normalise(page_text)
    if not q:
        return False, "empty quote"
    if q in p:
        return True, "exact"
    words = [w for w in re.split(r"[^\w']+", q) if w]
    if not words:
        return False, "no words in quote"
    pattern = r"[^\w']+".join(re.escape(w) for w in words)
    if re.search(pattern, p):
        return True, "words in order"
    # say how badly it missed, so a human reading the log can tell a typo from
    # an invention
    present = sum(1 for w in set(words) if w in p)
    return False, "%d of %d words present" % (present, len(set(words)))


def verify_candidate(cand, get=fetch):
    """Check every piece of evidence on one candidate. Returns (ok, findings)."""
    findings, cache = [], {}
    for field, ev in sorted((cand.get("evidence") or {}).items()):
        url = (ev or {}).get("url") or ""
        quote = (ev or {}).get("quote") or ""
        if not url:
            findings.append((field, False, "no url"))
            continue
        if len(quote) < MIN_QUOTE:
            findings.append((field, False, "quote shorter than %d characters" % MIN_QUOTE))
            continue
        if url not in cache:
            try:
                cache[url] = visible_text(get(url))
            except urllib.error.HTTPError as e:
                cache[url] = None
                findings.append((field, False, "HTTP %s" % e.code))
                continue
            except Exception as e:
                cache[url] = None
                findings.append((field, False, "unreachable: %s" % e))
                continue
        if cache[url] is None:
            findings.append((field, False, "page could not be read"))
            continue
        ok, how = appears(quote, cache[url])
        findings.append((field, ok, how))
    return all(ok for _, ok, _ in findings) if findings else True, findings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("payload")
    ap.add_argument("--prune", action="store_true",
                    help="drop fields whose quote cannot be found, and write back")
    args = ap.parse_args()

    cands = json.load(open(args.payload, encoding="utf-8"))
    if isinstance(cands, dict):
        cands = [cands]

    bad = 0
    for cand in cands:
        name = cand.get("company") or cand.get("domain") or "?"
        ok, findings = verify_candidate(cand)
        print("  %s" % name)
        for field, good, how in findings:
            print("     %-26s %s  %s" % (field, "ok  " if good else "FAIL", how))
            if not good:
                bad += 1
                if args.prune:
                    cand["evidence"].pop(field, None)
                    (cand.get("values") or {}).pop(field, None)
        if not ok and not args.prune:
            print("     -> this candidate must not be recorded as it stands")

    if args.prune:
        with open(args.payload, "w", encoding="utf-8") as fh:
            json.dump(cands, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print("\n  pruned %d unverifiable field(s); payload rewritten" % bad)
        return 0

    if bad:
        print("\n  %d piece(s) of evidence could not be found on the page cited." % bad)
        return 1
    print("\n  every quote was found on the page it cites")
    return 0


if __name__ == "__main__":
    sys.exit(main())
