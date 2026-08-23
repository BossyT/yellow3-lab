#!/usr/bin/env python3
"""
SEO / entity / technical due diligence for yellow3.io.

Scope is this repo only. naffe.ai is a different site and is explicitly out of
scope - no findings about it are reported here beyond how yellow3.io links to it.

WHY A SCRIPT. The site is 640 files and most of them are generated. Anything
found by hand today is found again by hand next month, and the faults this repo
actually ships - a sitemap that advertises a redirect, a template that quietly
reverts a site-wide correction, a page nothing links to - are all counting
problems. They are invisible one page at a time and obvious across all of them.

Every check answers a question a crawler or a reader would ask:

    indexation     is the set of pages we tell Google about the same as the set
                   of pages we actually serve and allow?
    canonicals     does every page name itself, once, at the URL it is served
                   from?
    metadata       does every indexable page have a title and a description, and
                   are they distinct?
    entity         does the site say one thing about who the company is?
    routes         does every internal link reach something, without a detour?
    orphans        can a crawler reach every page we want indexed?
    structured     is the JSON-LD valid, and is there exactly one Organization?
    templates      do the generators still carry the corrections the pages carry?

    python3 research/seo_dd.py            report everything
    python3 research/seo_dd.py --check    exit non-zero if a blocking fault exists
"""

import json
import os
import re
import sys
import urllib.request
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = "https://www.yellow3.io"
SKIP_DIRS = {"node_modules", ".git", ".vercel", "Autonomous ai software"}
# admin.html is the CMS: a program, not a public page, and deliberately noindex.
NOT_PUBLIC = {"admin.html", "google4b600ad4155228a3.html"}

# Positioning that has been retired by the current entity contracts. Each is
# here because a package explicitly ruled it out, not because it reads oddly.
# Files that hold the retired phrases because their job is to find them.
GUARDS = {"site_nav.py", "seo_dd.py", "port_approved_css.py"}

RETIRED = {
    "Copenhagen AI Lab": "retired company definition",
    "yellow3 lab ApS": "wrong legal entity - it is yellow3 ApS",
    "yellow3 Inc": "retired US entity",
    "Building outcome infrastructure for the AI era": "retired tagline",
}


def pages():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(files):
            if name.endswith(".html"):
                path = os.path.join(base, name)
                yield os.path.relpath(path, ROOT), path


def url_for(rel):
    """The clean URL a file is served at."""
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[: -len("/index.html")] + "/"
    return "/" + rel[: -len(".html")]


def file_for(url):
    """The file a clean URL resolves to, or None."""
    url = url.split("#")[0].split("?")[0]
    if url in ("/", ""):
        return "index.html"
    url = url.lstrip("/")
    for candidate in (url + ".html", os.path.join(url, "index.html"),
                      url.rstrip("/") + ".html",
                      os.path.join(url.rstrip("/"), "index.html")):
        if os.path.exists(os.path.join(ROOT, candidate)):
            return candidate
    if url.endswith(".html") and os.path.exists(os.path.join(ROOT, url)):
        return url
    return None


def load():
    docs = {}
    for rel, path in pages():
        text = open(path, encoding="utf-8", errors="ignore").read()
        # generate-sitemap.js rewrites the bare host to www across every static
        # file at build time, so the repo and the deployed page differ. Audit
        # what SHIPS: apply the same transform here. The source-level question -
        # which generators still rely on that backstop - is asked separately
        # below, because the 30 July policy is that generators emit www
        # themselves and the normaliser only covers hand-written pages.
        text = text.replace("https://yellow3.io", HOST)
        title = re.search(r"<title[^>]*>(.*?)</title>", text, re.S)
        desc = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', text)
        canon = re.search(r'<link\s+rel="canonical"\s+href="([^"]*)"', text)
        # THE PAGE'S OWN CANONICAL IS ITS URL; the filename is the fallback.
        # generate-sitemap.js submits the canonical, so deriving a different URL
        # here makes this file disagree with the sitemap it audits - and it
        # reported three healthy pages as "missing from the sitemap" the moment
        # the two derivations diverged. The divergence is real and correct:
        # weekly-briefing/index.html canonicalises to /weekly-briefing while its
        # filename implies /weekly-briefing/, and insights/index.html
        # canonicalises to /insights/ and matches. Reading the canonical is what
        # makes both of those true at once.
        canon_path = url_for(rel)
        if canon:
            href = canon.group(1).strip()
            for prefix in (HOST, "https://yellow3.io"):
                if href.startswith(prefix):
                    href = href[len(prefix):]
                    break
            if href.startswith("/"):
                canon_path = href

        docs[rel] = {
            "path": path,
            "text": text,
            "url": canon_path,
            "derived_url": url_for(rel),
            "title": (title.group(1).strip() if title else None),
            "desc": (desc.group(1).strip() if desc else None),
            "canonical": (canon.group(1) if canon else None),
            "canonicals": len(re.findall(r'rel="canonical"', text)),
            "noindex": "noindex" in text,
            "public": rel not in NOT_PUBLIC,
        }
    return docs


def sitemap_urls():
    """The LIVE sitemap. sitemap.xml in the repo is build output: it is
    regenerated by generate-sitemap.js on every deploy, so the committed copy is
    always one build behind and checking against it invents findings."""
    try:
        with urllib.request.urlopen(HOST + "/sitemap.xml", timeout=20) as r:
            return re.findall(r"<loc>([^<]+)</loc>", r.read().decode()), True
    except Exception:
        p = os.path.join(ROOT, "sitemap.xml")
        if not os.path.exists(p):
            return [], False
        return re.findall(r"<loc>([^<]+)</loc>",
                          open(p, encoding="utf-8").read()), False


def redirect_sources():
    p = os.path.join(ROOT, "vercel.json")
    if not os.path.exists(p):
        return set()
    conf = json.load(open(p, encoding="utf-8"))
    out = set()
    for r in conf.get("redirects", []):
        src = r.get("source", "")
        if ":" not in src and "*" not in src:
            out.add(src)
    return out


def main():
    docs = load()
    smap, smap_live = sitemap_urls()
    redirects = redirect_sources()
    findings = defaultdict(list)

    indexable = {rel: d for rel, d in docs.items()
                 if d["public"] and not d["noindex"]}
    smap_paths = {u[len(HOST):] if u.startswith(HOST) else u for u in smap}

    # ---------------------------------------------------------- indexation
    #
    # Only when the LIVE sitemap was reachable. The committed sitemap.xml is
    # build output and is regenerated after this script runs in the build
    # command, so comparing against it reports pages as missing that the deploy
    # will list. That false reading is what this whole file was corrected for.
    for rel, d in (sorted(indexable.items()) if smap_live else []):
        if d["url"] not in smap_paths:
            findings["indexable page missing from the sitemap"].append(d["url"])
    for rel, d in (sorted(docs.items()) if smap_live else []):
        if d["noindex"] and d["url"] in smap_paths:
            findings["sitemap lists a noindex page"].append(d["url"])
    # A URL in the sitemap with no file behind it is two different faults, and
    # only one of them should stop a deploy.
    #
    # NO FILE AND NO REDIRECT is a 404 advertised to Google. Blocking, as it was.
    #
    # NO FILE BUT A DECLARED REDIRECT is the ordinary, transient state of
    # REPLACING A PAGE WITH A REDIRECT, and blocking it creates a deadlock this
    # repo has already paid for once. The live sitemap is a build behind - it is
    # fetched here, and generate-sitemap.js only runs afterwards - so the commit
    # that deletes the page and adds the redirect is judged against a sitemap
    # that still lists the page. build_check fails, Vercel refuses the deploy,
    # and production keeps serving the very build you are trying to replace.
    # The withdrawal of 2026-08-23 had to be staged across two deploys to get
    # around exactly this.
    #
    # A crawler reaching that URL is not misled: it gets a redirect to a real
    # page, and the entry disappears from the sitemap on the next build. So it
    # is reported, and it does not block. The distinction is the point - the
    # check is not being weakened, it is being told which of the two it found.
    for u in (sorted(smap_paths) if smap_live else []):
        if file_for(u) is None:
            if u in redirects:
                findings["sitemap lists a redirect, and drops it next build"].append(u)
            else:
                findings["sitemap lists a URL that is not a page"].append(u)
    dupes = [u for u, n in Counter(smap).items() if n > 1] if smap_live else []
    for u in sorted(dupes):
        findings["sitemap lists the same URL twice"].append(u)

    # ----------------------------------------------------------- canonicals
    for rel, d in sorted(indexable.items()):
        if not d["canonical"]:
            findings["indexable page has no canonical"].append(d["url"])
            continue
        if d["canonicals"] > 1:
            findings["more than one canonical tag"].append(d["url"])
        # Compare against the URL the FILE is served at, not against d["url"] -
        # d["url"] is now read from this very canonical, so comparing the two
        # would be a check that cannot fail. The trailing slash is still
        # normalised away on both sides, because cleanUrls serves a directory
        # index at "/dir" and "/dir/" alike and a page may legitimately name
        # either as its canonical. What this still catches is a canonical
        # pointing at a DIFFERENT page, which is the fault worth having.
        want = HOST + d["derived_url"]
        if d["canonical"].rstrip("/") != want.rstrip("/"):
            findings["canonical does not point at the page's own URL"].append(
                "%s -> %s" % (d["derived_url"], d["canonical"]))

    # ------------------------------------------------------------- metadata
    titles, descs = defaultdict(list), defaultdict(list)
    for rel, d in sorted(indexable.items()):
        if not d["title"]:
            findings["no title"].append(d["url"])
        else:
            titles[d["title"]].append(d["url"])
        if not d["desc"]:
            findings["no meta description"].append(d["url"])
        else:
            descs[d["desc"]].append(d["url"])
    for t, urls in sorted(titles.items()):
        if len(urls) > 1:
            findings["duplicate title across pages"].append(
                '"%s" on %d pages: %s' % (t[:60], len(urls), ", ".join(urls[:4])))
    for t, urls in sorted(descs.items()):
        if len(urls) > 1:
            findings["duplicate meta description"].append(
                '"%s" on %d pages: %s' % (t[:50], len(urls), ", ".join(urls[:4])))

    # ------------------------------------------------- social metadata
    for rel, d in sorted(indexable.items()):
        # Match the property exactly. A substring test passes on og:image:alt
        # when og:image itself is absent, which is how the first version of
        # this check reported a page as fine while its card had no image.
        missing = [k for k in ("og:title", "og:description", "og:image",
                               "twitter:card")
                   if not re.search(r'(?:property|name)="%s"' % k, d["text"])]
        if missing:
            findings["incomplete social card"].append(
                "%s: no %s" % (d["url"], ", ".join(missing)))

    # --------------------------------------------------------------- entity
    for rel, d in sorted(docs.items()):
        for phrase, why in RETIRED.items():
            if phrase in d["text"]:
                findings["retired positioning still on a page"].append(
                    "%s: %s (%s)" % (d["url"], phrase, why))

    # ---------------------------------------------------- structured data
    orgs = []
    for rel, d in sorted(docs.items()):
        if not d["public"]:
            continue
        for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>',
                             d["text"], re.S):
            try:
                data = json.loads(m.group(1))
            except Exception as exc:
                findings["invalid JSON-LD"].append("%s: %s" % (d["url"], exc))
                continue
            for node in (data.get("@graph") or [data]):
                if not isinstance(node, dict):
                    continue
                name = (node.get("name") or "")
                if (node.get("@type") == "Organization"
                        and "yellow3" in name.lower()
                        and "@id" not in node):
                    orgs.append((d["url"], name))
    for url, name in orgs:
        findings["Organization defined without an @id"].append(
            "%s (%s)" % (url, name))

    # --------------------------------------------------------------- routes
    internal = re.compile(r'href="(/[^"#][^"]*|/)"')
    inbound = Counter()
    for rel, d in sorted(docs.items()):
        if not d["public"]:
            continue
        for m in internal.finditer(d["text"]):
            href = m.group(1)
            target = href.split("#")[0]
            if target.startswith("//") or any(
                    target.endswith(e) for e in
                    (".css", ".js", ".png", ".jpg", ".svg", ".webp", ".xml",
                     ".txt", ".json", ".csv", ".ico", ".pdf", ".mp4")):
                continue
            if target in redirects:
                findings["internal link points at a redirect"].append(
                    "%s -> %s" % (d["url"], target))
                continue
            if target.startswith("/api/") and os.path.exists(
                    os.path.join(ROOT, target.lstrip("/") + ".js")):
                continue          # a serverless function, not a page
            resolved = file_for(target)
            if resolved is None:
                findings["internal link goes nowhere"].append(
                    "%s -> %s" % (d["url"], href))
            else:
                inbound[resolved] += 1

    # -------------------------------------------------------------- orphans
    for rel, d in sorted(indexable.items()):
        if rel == "index.html":
            continue
        if inbound[rel] == 0:
            findings["indexable page nothing links to"].append(d["url"])

    # ------------------------------------------------------------ templates
    gen_dir = os.path.join(ROOT, "research")
    for name in sorted(os.listdir(gen_dir)):
        if not name.endswith(".py"):
            continue
        text = open(os.path.join(gen_dir, name), encoding="utf-8",
                    errors="ignore").read()
        for phrase, why in RETIRED.items():
            # site_nav.py holds these as search patterns, which is its job.
            # Guard files hold the retired phrases as the things they search
            # FOR. site_nav.py sweeps them out of pages, port_approved_css.py
            # forbids them in a built page, and this file reports them. None of
            # the three is a template, and reading them as one turns every new
            # guard into a build failure.
            if name in GUARDS:
                continue
            if phrase in text:
                findings["generator template carries retired positioning"].append(
                    "research/%s: %s" % (name, phrase))

    # ------------------------------------- the canonical host, at source
    #
    # Policy, set on 2026-07-30: a generator emits the www host itself, and the
    # normalisation pass in generate-sitemap.js is only a backstop for
    # hand-written pages. The reason is in that commit: the register generator
    # wrote bare-host self-references, a rebuild between sitemap runs reverted
    # 187 profiles to a canonical that redirects, and it happened days after the
    # sitemap went to Google.
    for name in sorted(os.listdir(gen_dir := os.path.join(ROOT, "research"))):
        if not name.endswith(".py") or name == "seo_dd.py":
            continue
        text = open(os.path.join(gen_dir, name), encoding="utf-8",
                    errors="ignore").read()
        if re.search(r'["\']https://yellow3\.io', text):
            findings["generator emits the bare host, against the 2026-07-30 "
                     "policy"].append("research/" + name)

    # ---------------------------------------------------------------- report
    print("SEO / entity / technical due diligence - yellow3.io")
    print("=" * 66)
    print("  %d html files, %d public, %d indexable, %d in the sitemap (%s)"
          % (len(docs), sum(1 for d in docs.values() if d["public"]),
             len(indexable), len(smap),
             "live" if smap_live else "repo copy, stale - build output"))
    print("  host normalisation applied in memory, as the build does")
    print()

    blocking = ("internal link goes nowhere", "invalid JSON-LD",
                "incomplete social card",
                "generator emits the bare host, against the 2026-07-30 policy",
                "retired positioning still on a page",
                "generator template carries retired positioning",
                "sitemap lists a URL that is not a page",
                "indexable page has no canonical")
    total = 0
    for label in sorted(findings, key=lambda k: -len(findings[k])):
        items = findings[label]
        total += len(items)
        mark = "!" if label in blocking else " "
        print("%s %-46s %4d" % (mark, label, len(items)))
        for item in items[:6]:
            print("      " + item)
        if len(items) > 6:
            print("      ... and %d more" % (len(items) - 6))
        print()

    if not total:
        print("  nothing found")
    print("  %d finding(s); ! marks the ones that mislead a crawler or a reader"
          % total)

    if "--check" in sys.argv:
        hard = sum(len(findings[k]) for k in blocking)
        return 1 if hard else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
