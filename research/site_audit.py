#!/usr/bin/env python3
"""Walk yellow3.io and report what is broken, inconsistent or off-brand.

WHAT THIS IS FOR. The site is 631 pages, most of them generated, and a person
cannot read them all. This reads all of them and reports only things that are
checkable - a link that resolves or does not, an image with no alt text, a
capital L in "yellow3 lab". Judgement about whether the writing is any good is
NOT in here; that is the reviewer's job, and this exists so the reviewer spends
their attention on judgement rather than on counting.

    python3 research/site_audit.py                 the whole site
    python3 research/site_audit.py --json          machine-readable
    python3 research/site_audit.py --live          also check external links

EVERY FINDING NAMES ITS FILE AND ITS LINE. A report that says "some pages are
missing alt text" cannot be acted on, and a report nobody can act on is one
nobody reads twice.

Severities:
  broken   a visitor hits this - a dead link, a missing image, a dead control
  rule     a house rule is broken - brand casing, em dashes, plaintext email
  thin     something is absent that should be there - no description, no alt
  note     worth a human's eye, may be legitimate
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {"node_modules", ".git", ".vercel", "Autonomous ai software", "img"}
# The CMS holds a token and is not a public page; the verification file is
# Google's, not ours.
SKIP_FILES = {"admin.html", "google4b600ad4155228a3.html"}

findings = []

# A path with a redirect is not a dead link. vercel.json carries 300-odd of
# them - every renamed register profile - and a checker that does not read it
# reports the rename as a fault.
REDIRECTS = set()
try:
    _cfg = json.load(open(os.path.join(ROOT, "vercel.json"), encoding="utf-8"))
    REDIRECTS = {r["source"].rstrip("/") for r in _cfg.get("redirects", [])}
except Exception:
    pass


def add(severity, page, line, what, detail=""):
    findings.append({"severity": severity, "page": page, "line": line,
                     "what": what, "detail": detail})


def pages():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(files):
            if name.endswith(".html") and name not in SKIP_FILES:
                path = os.path.join(base, name)
                yield os.path.relpath(path, ROOT), path


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def visible(html):
    """Text a reader sees. Script, style and tags removed."""
    out = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    out = re.sub(r"<style[\s\S]*?</style>", " ", out, flags=re.I)
    out = re.sub(r"<!--[\s\S]*?-->", " ", out)
    return re.sub(r"<[^>]+>", " ", out)


def resolves(href):
    """Does an internal path exist, under Vercel's cleanUrls?"""
    clean = href.split("#")[0].split("?")[0]
    if clean.rstrip("/") in REDIRECTS:
        return True
    path = clean.strip("/")
    if not path:
        return True                                   # the homepage
    # /api/report is api/report.js - a serverless function, not a page.
    for candidate in (path, path + ".html", path + ".js",
                      os.path.join(path, "index.html")):
        if os.path.exists(os.path.join(ROOT, candidate)):
            return True
    return False


# --------------------------------------------------------------- the checks

def check_links(rel, html):
    for m in re.finditer(r'href="([^"]+)"', html):
        href = m.group(1)
        if href.startswith(("http", "mailto:", "tel:", "#", "javascript:", "data:")):
            continue
        if not href.startswith("/"):
            continue                                  # relative, rare here
        if not resolves(href):
            add("broken", rel, line_of(html, m.start()), "dead link", href)

    for m in re.finditer(r'<a[^>]*target="_blank"[^>]*>', html):
        if "noopener" not in m.group(0):
            add("rule", rel, line_of(html, m.start()),
                "target=_blank without rel=noopener", m.group(0)[:80])


def check_images(rel, html):
    for m in re.finditer(r"<img[^>]*>", html):
        tag = m.group(0)
        line = line_of(html, m.start())
        src = re.search(r'src="([^"]+)"', tag)
        alt = re.search(r'alt="([^"]*)"', tag)
        if not src:
            # `hidden` means a script fills it in - the claim editor's logo
            # preview is the whole of this population. An empty <img> nobody
            # can see is not a broken image.
            if "hidden" not in tag:
                add("broken", rel, line, "img with no src", tag[:80])
            continue
        url = src.group(1)
        if url.startswith("/") and not url.startswith("//"):
            target = os.path.join(ROOT, url.lstrip("/"))
            if not os.path.exists(target):
                add("broken", rel, line, "missing image file", url)
            elif os.path.getsize(target) > 400_000:
                add("note", rel, line, "image over 400KB",
                    f"{url} ({os.path.getsize(target) // 1024}KB)")
        if alt is None:
            add("thin", rel, line, "img with no alt attribute", url)
        elif not alt.group(1).strip():
            add("note", rel, line, "img with empty alt (decorative?)", url)


def check_head(rel, html):
    head = html[:html.index("</head>")] if "</head>" in html else html
    if "<html lang=" not in html:
        add("thin", rel, 1, "no lang on <html>")
    if not re.search(r"<title>[^<]{3,}</title>", head):
        add("thin", rel, 1, "no title")
    if not re.search(r'name="description"\s+content="[^"]{20,}"', head):
        add("thin", rel, 1, "no meta description")
    if not re.search(r'rel="canonical"', head):
        add("thin", rel, 1, "no canonical")
    if not re.search(r'property="og:title"', head):
        add("note", rel, 1, "no og:title - link previews fall back to the title")


def check_structure(rel, html):
    h1s = re.findall(r"<h1[^>]*>", html)
    if len(h1s) == 0:
        add("thin", rel, 1, "no h1")
    elif len(h1s) > 1:
        add("note", rel, 1, f"{len(h1s)} h1 elements")

    levels = [int(m.group(1)) for m in re.finditer(r"<h([1-6])[^>]*>", html)]
    previous = 0
    for level in levels:
        if previous and level > previous + 1:
            add("note", rel, 1, f"heading jumps h{previous} to h{level}")
            break
        previous = level


BRAND = [
    (re.compile(r"\byellow3 Lab\b"), 'capital L in "yellow3 lab"'),
    (re.compile(r"\bYellow3\b"), 'capital Y in "yellow3"'),
    (re.compile(r"\bNaffe\b"), 'capital N in "naffe.ai"'),
]
EMAIL = re.compile(r"[a-z0-9._%+-]+@yellow3\.io", re.I)


def check_copy(rel, html):
    text = visible(html)
    for pattern, what in BRAND:
        for m in pattern.finditer(text):
            add("rule", rel, 1, what, text[max(0, m.start() - 40):m.end() + 40].strip())

    # Em and en dashes. The house rule is a spaced hyphen. A quotation from a
    # source may legitimately contain one, so this is a note, not a failure.
    dashes = len(re.findall(r"[—–]", text))
    if dashes:
        m = re.search(r".{0,50}[—–].{0,50}", text)
        add("note", rel, 1, f"{dashes} em/en dash(es) - house rule is a spaced hyphen",
            (m.group(0).strip() if m else "")[:110])

    # An address in the markup is an address a scraper reads.
    for m in EMAIL.finditer(html):
        context = html[max(0, m.start() - 60):m.start()]
        if "String.fromCharCode" in context or "+'" in context:
            continue                                  # the obfuscation snippet
        add("rule", rel, line_of(html, m.start()), "plaintext email address",
            m.group(0))


def check_dead_controls(rel, html):
    """Buttons and links that look live and do nothing."""
    scripts = " ".join(re.findall(r"<script[^>]*>([\s\S]*?)</script>", html))
    for m in re.finditer(r'<(a|button)[^>]*href="#"[^>]*>(.*?)</\1>', html, re.S):
        tag = m.group(0)
        if "onclick" in tag or "toggle" in tag:
            continue
        # Bound by id from a script is bound. Only a control nothing reaches is
        # a dead control.
        ident = re.search(r'id="([^"]+)"', tag)
        if ident and ident.group(1) in scripts:
            continue
        label = re.sub(r"\s+", " ", visible(m.group(2))).strip()
        if label:
            add("note", rel, line_of(html, m.start()),
                "link to # with no handler", label[:60])


def check_css(rel, html):
    """Every class the page renders must be defined somewhere it loads."""
    style = "".join(re.findall(r"<style[^>]*>([\s\S]*?)</style>", html))
    for href in re.findall(r'<link[^>]+href="([^"]+\.css)"', html):
        path = os.path.join(ROOT, href.lstrip("/")) if href.startswith("/") else \
            os.path.join(os.path.dirname(os.path.join(ROOT, rel)), href)
        if os.path.exists(path):
            style += open(path, encoding="utf-8", errors="replace").read()
    if not style:
        return
    defined = set(re.findall(r"\.(-?[_a-zA-Z][\w-]*)", style))
    scripts = " ".join(re.findall(r"<script[^>]*>([\s\S]*?)</script>", html))
    # ONE FINDING PER CLASS NAME, not per use. A hook class used 40 times is one
    # thing to look at, and listing it 40 times buries everything else.
    seen = set()
    for m in re.finditer(r'class="([^"{}]+)"', html):
        for cls in m.group(1).split():
            if cls in defined or cls in seen:
                continue
            seen.add(cls)
            if cls in scripts:
                continue                              # a script hook, not styling
            add("note", rel, line_of(html, m.start()),
                "class with no rule anywhere the page loads", cls)


CHECKS = [check_links, check_images, check_head, check_structure,
          check_copy, check_dead_controls, check_css]


def main():
    as_json = "--json" in sys.argv
    counted = 0
    for rel, path in pages():
        html = open(path, encoding="utf-8", errors="replace").read()
        counted += 1
        for check in CHECKS:
            try:
                check(rel, html)
            except Exception as exc:                  # a check must not stop the walk
                add("note", rel, 1, f"check {check.__name__} failed", str(exc)[:120])

    if as_json:
        print(json.dumps({"pages": counted, "findings": findings}, indent=1))
        return 0

    order = ["broken", "rule", "thin", "note"]
    print(f"\nyellow3.io - {counted} pages read\n")
    for severity in order:
        rows = [f for f in findings if f["severity"] == severity]
        if not rows:
            continue
        # Group by what, because 400 pages missing the same tag is ONE problem
        # with 400 instances, and listing it 400 times hides the other three.
        groups = {}
        for row in rows:
            groups.setdefault(row["what"], []).append(row)
        print(f"{severity.upper()}  ({len(rows)})")
        for what, rows in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            print(f"  {len(rows):>4}x  {what}")
            for row in rows[:3]:
                detail = f" - {row['detail']}" if row["detail"] else ""
                print(f"          {row['page']}:{row['line']}{detail}"[:150])
            if len(rows) > 3:
                print(f"          ... and {len(rows) - 3} more")
        print()

    broken = len([f for f in findings if f["severity"] == "broken"])
    print(f"{broken} thing(s) a visitor would hit.\n")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
