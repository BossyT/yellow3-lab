#!/usr/bin/env python3
"""
Scope an approved package stylesheet under its page wrapper - mechanically.

Why this exists
---------------
The first port of the /research package was filtered by eye. Rules whose
selectors carried bare names - .wrap, .section, .hero, .kicker, h1, h2, h3, p,
.btn, .link, .actions - read as "site shell", so the whole first line of the
approved stylesheet was dropped and a hand-written block was written in its
place. The page rendered at 0.71 of the approved height: every section lost its
108px padding and its 58px h2, and only .closing survived, because its rules
happened to be named after the component and so looked worth keeping.

A component depends on rules that never mention it. So nothing here decides from
the outside which rules a page needs. Every rule in the approved stylesheet is
carried across in source order, each selector prefixed with the page wrapper;
the document selectors (:root, html, body) become the wrapper itself, since the
wrapper is the content root; and a media query stays a media query - flattening
one is how the homepage broke. Both declaration counts are asserted.

Approved production deviations - the handful of values GPT signs off because the
prototype had no shell to collide with - are NOT folded into the ported block.
They are emitted after it, attributed and dated, so that the port stays
something a machine can verify and a deviation stays something a person decided.

    python3 research/port_approved_css.py --check
    python3 research/port_approved_css.py --write [page]
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PKG = ("/private/tmp/claude-501/-Users-tcm/"
       "955bf7f5-bb89-4855-831f-fad554739c52/scratchpad")

PAGES = {
    "research": {
        "target": "research.html",
        "wrapper": "rs1",
        "package": ("/private/tmp/claude-501/-Users-tcm-Documents-yellow3-lab/"
                    "49c2013d-375c-4871-9a6f-74936638ee45/scratchpad/research1/"
                    "yellow3_research_v1_terminal_handoff/"
                    "APPROVED_RESEARCH_CONTENT.html"),
        # The package ships no assets/ folder. The real interface is already in
        # the repo from Homepage V3 and GPT confirmed it byte-identical to the
        # missing file (SHA 315e266d...). Nothing else is substituted.
        "requires": ["/img/homepage/model-adoption-interface.png"],
        "forbids": ["yellow3_research_v1_assets/model-adoption-real.png"],
        "deviations": [],
    },
    "contact": {
        "target": "contact.html",
        "wrapper": "ct1",
        "package": (PKG + "/contact/yellow3_contact_v1_terminal_handoff/"
                    "APPROVED_CONTACT_CONTENT.html"),
        "requires": ["mailto:hello@yellow3.io"],
        # The 10px yellow bar the prototype opens with is dropped on this route,
        # approved by GPT 2026-08-14: the production nav is fixed, 74.6px tall
        # and 95% opaque, so a bar at y=0 is painted over and never seen. It is
        # dropped from the MARKUP only - the rule stays in the ported block so
        # the port remains a mechanical, checkable transform of the package.
        "forbids": ['<div class="yr">'],
        "deviations": [
            ("@media(max-width:760px)", ".hero", "padding-top:88px",
             "Mobile hero cleared the fixed nav by -9px: the approved 58px top "
             "padding put the kicker behind a 67px nav. GPT approved 88px for "
             "this route on 2026-08-14. Desktop is untouched - its 90px clears "
             "the 74.6px nav."),
            ("", ".eg p", "margin:18px 0",
             ".eg p is the only paragraph in the package that declares no "
             "margin, and the package has no global p reset, so the prototype "
             "rendered it with the browser default 1em - 18px top and bottom at "
             "18px type. The production shell zeroes it through *{margin:0}, "
             "which cost this section exactly 36px at every width. This is not "
             "compensating spacing: it is the explicit declaration of a default "
             "the approved reference depends on. GPT approved 2026-08-14."),
        ],
    },
    "about": {
        "target": "about.html",
        "wrapper": "ab1",
        "package": (PKG + "/about/yellow3_about_v1_terminal_handoff/"
                    "APPROVED_ABOUT_CONTENT.html"),
        # The founder film surface is deliberately reserved. No poster, no stock
        # asset, no autoplay, and nothing that pretends to be a playable control
        # before the video exists - the package is explicit about all four.
        "requires": ["Video slot reserved", "AI avatar film will be added here"],
        # Attribute-precise on purpose: the approved placeholder copy says "No
        # autoplay." in prose, so a bare substring check fails on the very text
        # that proves the rule is being kept.
        "forbids": ["<video", "<iframe", "poster=", "autoplay=", " autoplay>"],
        "deviations": [],
    },
}


def extract_style(html):
    m = re.search(r"<style>(.*?)</style>", html, re.S)
    if not m:
        raise SystemExit("no <style> block in the approved package")
    return m.group(1).strip()


def split_rules(css):
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


def scope(selector, wrapper):
    seen, kept = set(), []
    for part in (p.strip() for p in selector.split(",")):
        if part in (":root", "html", "body"):
            scoped = "." + wrapper
        elif part == "*":
            scoped = ".%s *" % wrapper
        else:
            scoped = ".%s %s" % (wrapper, part)
        if scoped not in seen:
            seen.add(scoped)
            kept.append(scoped)
    return ",".join(kept)


def count_decls(body):
    return len([d for d in body.split(";") if d.strip()])


# The yellow3 Design System Gate, added by GPT on 2026-08-14 after /contact's
# company-identity section came up 36px short at every width.
#
# A prototype has no shell, so it renders with the browser's default margins. The
# production shell opens with *, *::before, *::after { margin: 0; padding: 0 },
# which takes them away. Any spacing the design left to a browser default is
# therefore spacing that silently disappears in production - and it disappears as
# a CONSTANT offset, which is easy to read as a padding mistake and hard to trace
# back to a rule that was never written.
#
# The rule: a package must reset these elements inside its own scope and declare
# the spacing it wants. This check reads the package, not our port, so it catches
# the problem at intake rather than after a render comparison fails.
DEFAULT_MARGIN_ELEMENTS = ("p", "ul", "ol", "figure", "blockquote", "dl")


def design_system_faults(css, markup, cfg):
    """Elements whose spacing the package leaves to a browser default."""
    faults = []
    covered = {sel.strip() for _, sel, _, _ in cfg["deviations"]}
    for tag in DEFAULT_MARGIN_ELEMENTS:
        if not re.search(r"<%s[\s>]" % tag, markup):
            continue
        reset = re.search(r"(?:^|[;}])\s*%s\s*\{[^}]*margin" % tag, css)
        if reset:
            continue
        # No scope-level reset. Every selector targeting this element must then
        # declare its own margin somewhere, or it falls back to the UA default.
        #
        # "Somewhere", not "in this rule": a media query that overrides only the
        # font size of a selector whose base rule sets the margin is fine, and
        # counting each rule separately reports it as a fault. The first version
        # of this check did exactly that on .sc p.
        declared, seen = set(), []
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
            sel, body = m.group(1).strip(), m.group(2)
            for part in (p.strip() for p in sel.split(",")):
                if not re.search(r"\b%s$" % tag, part):
                    continue
                seen.append(part)
                if "margin" in body:
                    declared.add(part)
        for part in dict.fromkeys(seen):
            if part in declared or part in covered:
                continue
            faults.append("%s has no margin and the package has no %s reset - "
                          "it renders on a browser default the shell will remove"
                          % (part, tag))
    return faults


def markers(name, wrapper):
    return (
        "/* >>> APPROVED /%s, scoped under .%s by "
        "research/port_approved_css.py. Do not hand-edit. */" % (name, wrapper),
        "/* <<< end approved /%s */" % name,
    )


def build(name):
    cfg = PAGES[name]
    wrapper = cfg["wrapper"]
    begin, end = markers(name, wrapper)
    approved = extract_style(open(cfg["package"], encoding="utf-8").read())

    lines, ported, source = [begin], 0, 0
    for kind, prelude, body in split_rules(approved):
        if kind == "rule":
            source += count_decls(body)
            ported += count_decls(body)
            lines.append("%s{%s}" % (scope(prelude, wrapper), body))
        else:
            lines.append(prelude + "{")
            for k2, sel2, body2 in split_rules(body):
                if k2 != "rule":
                    raise SystemExit("nested at-rule in %s" % prelude)
                source += count_decls(body2)
                ported += count_decls(body2)
                lines.append("%s{%s}" % (scope(sel2, wrapper), body2))
            lines.append("}")

    if ported != source:
        raise SystemExit("declaration count drifted: %d -> %d" % (source, ported))

    # Approved production deviations, after the port and never inside it.
    for media, sel, decls, why in cfg["deviations"]:
        lines.append("")
        for chunk in re.findall(r".{1,72}(?:\s|$)", why):
            lines.append("/* " + chunk.strip() + " */")
        rule = "%s{%s}" % (scope(sel, wrapper), decls)
        lines.append("%s{%s}" % (media, rule) if media else rule)

    lines.append(end)
    return "\n".join(lines), source, len(cfg["deviations"])


def check_one(name, write):
    cfg = PAGES[name]
    begin, end = markers(name, cfg["wrapper"])
    path = os.path.join(ROOT, cfg["target"])
    block, decls, devs = build(name)
    page = open(path, encoding="utf-8").read()

    if begin not in page or end not in page:
        raise SystemExit("%s: markers missing - insert them first" % cfg["target"])

    start, stop = page.index(begin), page.index(end) + len(end)
    if write:
        if page[start:stop] != block:
            open(path, "w", encoding="utf-8").write(page[:start] + block + page[stop:])
            print("%-9s written    %3d declarations + %d approved deviation(s)"
                  % (name, decls, devs))
        else:
            print("%-9s current    %3d declarations" % (name, decls))
        return

    if page[start:stop] != block:
        raise SystemExit("%s does not match the approved stylesheet.\n"
                         "Run: python3 research/port_approved_css.py --write %s"
                         % (cfg["target"], name))
    for needle in cfg["requires"]:
        if needle not in page:
            raise SystemExit("%s: missing %s" % (cfg["target"], needle))
    for needle in cfg["forbids"]:
        if needle in page:
            raise SystemExit("%s: still contains %s" % (cfg["target"], needle))

    package = open(cfg["package"], encoding="utf-8").read()
    faults = design_system_faults(extract_style(package), package, cfg)
    if faults:
        raise SystemExit("%s fails the design system gate:\n  %s\n"
                         "Either the package declares the spacing, or the "
                         "value goes in `deviations` with GPT's approval."
                         % (name, "\n  ".join(faults)))

    print("%-9s matches    %3d declarations + %d approved deviation(s)"
          % (name, decls, devs))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    names = args or list(PAGES)
    write = "--write" in sys.argv
    for name in names:
        if name not in PAGES:
            raise SystemExit("unknown page: %s" % name)
        check_one(name, write)


if __name__ == "__main__":
    main()
