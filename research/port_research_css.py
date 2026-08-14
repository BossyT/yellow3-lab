#!/usr/bin/env python3
"""
Scope the approved /research stylesheet under .rs1 - mechanically, never by hand.

Why this exists
---------------
The first port of this package was filtered by eye. Rules whose selectors carried
bare names - .wrap, .section, .hero, .kicker, h1, h2, h3, p, .btn, .link,
.actions - read as "site shell", so the whole first line of the approved
stylesheet was dropped and a hand-written .rs1 block was written in its place.

The page then rendered at 0.71 of the approved height. Every section lost its
108px padding and its 58px h2; only .closing survived, because its rules happened
to be named after the component and so looked worth keeping. That section
measured 1.08 while the other six measured 0.59-0.79, which is what a
proportional shortfall looks like when the cause is missing typography rather
than missing padding.

The lesson, and the reason this file is a script and not a diff: a component
depends on rules that never mention it. Nothing here decides from the outside
which rules /research needs. Every rule in APPROVED_RESEARCH_CONTENT.html is
carried across, in source order, with each selector prefixed .rs1; the document
selectors (:root, html, body) become .rs1 itself, since .rs1 is the content root;
and a media query stays a media query - flattening one is how the homepage broke.

Both declaration counts are asserted, so a rule cannot go missing again quietly.

    python3 research/port_research_css.py --check     # verify research.html
    python3 research/port_research_css.py --write     # regenerate the block
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGET = os.path.join(ROOT, "research.html")

PACKAGE = (
    "/private/tmp/claude-501/-Users-tcm-Documents-yellow3-lab/"
    "49c2013d-375c-4871-9a6f-74936638ee45/scratchpad/research1/"
    "yellow3_research_v1_terminal_handoff/APPROVED_RESEARCH_CONTENT.html"
)

BEGIN = ("/* >>> APPROVED /research V1, scoped under .rs1 by "
         "research/port_research_css.py. Do not hand-edit. */")
END = "/* <<< end approved /research V1 */"

# The approved package ships the flagship screenshot under a relative assets path
# that the package itself does not contain. The real interface is already in the
# repo from the approved Homepage V3 package, and GPT confirmed it byte-identical
# to the missing file (SHA 315e266d...). Nothing else is substituted.
ASSET_SRC = "yellow3_research_v1_assets/model-adoption-real.png"
ASSET_PROD = "/img/homepage/model-adoption-interface.png"


def extract_style(html: str) -> str:
    m = re.search(r"<style>(.*?)</style>", html, re.S)
    if not m:
        raise SystemExit("no <style> block in the approved package")
    return m.group(1).strip()


def split_rules(css: str):
    """(kind, prelude, body) in source order. kind is 'rule' or 'at'."""
    out, i, n = [], 0, len(css)
    while i < n:
        while i < n and css[i].isspace():
            i += 1
        if i >= n:
            break
        brace = css.index("{", i)
        if css[i] == "@":
            depth, k = 1, brace + 1
            while depth:
                if css[k] == "{":
                    depth += 1
                elif css[k] == "}":
                    depth -= 1
                k += 1
            out.append(("at", css[i:brace].strip(), css[brace + 1:k - 1]))
            i = k
        else:
            close = css.index("}", brace)
            out.append(("rule", css[i:brace].strip(), css[brace + 1:close].strip()))
            i = close + 1
    return out


def scope(selector: str) -> str:
    """Prefix every selector in a list with .rs1, mapping document selectors to it."""
    seen, kept = set(), []
    for part in (p.strip() for p in selector.split(",")):
        if part in (":root", "html", "body"):
            scoped = ".rs1"
        elif part == "*":
            scoped = ".rs1 *"
        else:
            scoped = ".rs1 " + part
        if scoped not in seen:
            seen.add(scoped)
            kept.append(scoped)
    return ",".join(kept)


def count_decls(body: str) -> int:
    return len([d for d in body.split(";") if d.strip()])


def build():
    approved = extract_style(open(PACKAGE, encoding="utf-8").read())
    rules = split_rules(approved)

    lines, ported, source = [BEGIN], 0, 0
    for kind, prelude, body in rules:
        if kind == "rule":
            source += count_decls(body)
            ported += count_decls(body)
            lines.append("%s{%s}" % (scope(prelude), body))
        else:
            inner = split_rules(body)
            lines.append(prelude + "{")
            for k2, sel2, body2 in inner:
                if k2 != "rule":
                    raise SystemExit("nested at-rule in %s, not handled" % prelude)
                source += count_decls(body2)
                ported += count_decls(body2)
                lines.append("%s{%s}" % (scope(sel2), body2))
            lines.append("}")
    lines.append(END)

    if ported != source:
        raise SystemExit("declaration count drifted: %d -> %d" % (source, ported))
    return "\n".join(lines), source


def main():
    block, decls = build()
    page = open(TARGET, encoding="utf-8").read()

    if BEGIN not in page or END not in page:
        raise SystemExit("markers missing from research.html - insert them first")

    start = page.index(BEGIN)
    stop = page.index(END) + len(END)
    current = page[start:stop]

    if "--write" in sys.argv:
        if current == block:
            print("approved css already current  %d declarations" % decls)
            return
        open(TARGET, "w", encoding="utf-8").write(page[:start] + block + page[stop:])
        print("approved css written          %d declarations, scoped under .rs1" % decls)
        return

    if current != block:
        raise SystemExit(
            "research.html does not match the approved stylesheet.\n"
            "Run: python3 research/port_research_css.py --write")

    if ASSET_SRC in page:
        raise SystemExit("the package asset path is still in the markup")
    if ASSET_PROD not in page:
        raise SystemExit("the Model Adoption interface asset is missing")

    print("approved css matches package  %d declarations, scoped under .rs1" % decls)


if __name__ == "__main__":
    main()
