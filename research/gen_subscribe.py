#!/usr/bin/env python3
"""
The three latest entries on /insights/subscribe, from the records that make
/feed.xml.

WHY THIS EXISTS. 05-CONTENT-CONTRACT.md and Lock 07 of the approved v1.0
handover are explicit: the latest-entry list is dynamic, it comes from the
publication records, and the prototype's sample issues must not ship. Lock 07
also forbids a second publication dataset, so this reads feed.xml itself - the
document /feed.xml serves - rather than assembling a parallel list that could
disagree with it. If the feed says it, the page says it, and there is no third
place for the two to drift apart.

Implementation map section 4 rules out fetching the feed from the browser when
the records are already inside the application. They are: feed.xml is in this
repo. So the rows are written into the page at build time, which is also what
04-INTERACTIONS-AND-STATES.md asks for - the page must not need client-side
loading before its primary copy appears, and there are no skeleton cards.

THE ISSUE LABEL IS READ, NOT INVENTED. The feed carries no issue number, but
the article each item links to does, in its header meta - `<span>Issue 33</span>`
- and that article is the same publication record. Three of the thirty-six
articles have no issue label, so a missing one omits the line rather than
inventing a number, which is what 03-RSS-BROWSER-SPEC.md requires of an absent
optional field.

    python3 research/gen_subscribe.py            write the rows
    python3 research/gen_subscribe.py --check    fail if the page is stale
"""

import html
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEED = os.path.join(ROOT, "feed.xml")
PAGE = os.path.join(ROOT, "insights", "subscribe.html")
HOST = "https://www.yellow3.io"

BEGIN = ("<!-- prerendered:latest-entries - written by research/gen_subscribe.py"
         " from feed.xml. Do not hand-edit. -->")
END = "<!-- /prerendered:latest-entries -->"

# 04-INTERACTIONS-AND-STATES.md, "Empty feed": the hero, the address and the
# how-it-works content stay, the rows are replaced by one restrained line, and
# VIEW ALL INSIGHTS stays. That link lives in the page, not in this block.
EMPTY = "No published Insights are currently available in the feed."

COUNT = 3


def issue_label(link):
    """The issue label from the article this feed item points at, or None.

    Read from the publication record, never derived from the slug: Lock 07 and
    the RSS spec both forbid deriving display copy from a filename.
    """
    path = link.split("#")[0].split("?")[0]
    if path.startswith(HOST):
        path = path[len(HOST):]
    if not path.startswith("/insights/"):
        return None
    f = os.path.join(ROOT, path.lstrip("/"))
    if not f.endswith(".html"):
        f += ".html"
    if not os.path.exists(f):
        return None
    text = open(f, encoding="utf-8", errors="replace").read()
    m = re.search(r'<div class="meta">\s*<span>(Issue\s+\d+)</span>', text)
    return m.group(1).upper() if m else None


def items():
    """Published items, in the order the feed supplies them."""
    if not os.path.exists(FEED):
        return None                      # feed unavailable - not an empty feed
    try:
        channel = ET.parse(FEED).getroot().find("channel")
    except ET.ParseError as e:
        raise SystemExit("feed.xml does not parse: %s" % e)
    if channel is None:
        raise SystemExit("feed.xml has no <channel>")

    out = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        # One malformed item must not take the page down, and an item with no
        # title or no canonical link is not something to render a row for.
        if not title or not link.startswith("https://"):
            continue
        out.append({"title": title, "link": link, "desc": desc,
                    "issue": issue_label(link)})
    return out


def text(s):
    """Escape a text node, and only what a text node needs.

    Not html.escape's default: that also turns a straight apostrophe into
    &#x27;, and this repo's rule is that a company's - or an author's - words
    survive the round trip as the characters they were written with. & and the
    angle brackets are the only three that change meaning here.
    """
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def rows(entries):
    if not entries:
        return ['          <article><p class="issue-label">%s</p></article>'
                % text(EMPTY)]
    out = []
    for e in entries:
        parts = ["          <article>"]
        if e["issue"]:
            parts.append('<p class="issue-label">%s</p>' % text(e["issue"]))
        parts.append('<h3><a href="%s">%s</a></h3>'
                     % (html.escape(e["link"], quote=True), text(e["title"])))
        if e["desc"]:
            parts.append("<p>%s</p>" % text(e["desc"]))
        parts.append("</article>")
        out.append("".join(parts))
    return out


def block():
    entries = items()
    if entries is None:
        # 04: a temporary read failure must not claim the feed has no entries.
        raise SystemExit("feed.xml is missing - refusing to write an empty list")
    return "\n".join([BEGIN] + rows(entries[:COUNT]) + [END])


def main():
    page = open(PAGE, encoding="utf-8").read()
    if BEGIN not in page or END not in page:
        raise SystemExit("%s: prerender markers missing" % PAGE)
    start, stop = page.index(BEGIN), page.index(END) + len(END)
    fresh = block()

    if "--check" in sys.argv:
        if page[start:stop] != fresh:
            raise SystemExit("insights/subscribe.html is stale - "
                             "run python3 research/gen_subscribe.py")
        n = fresh.count("<article>")
        print("  ok  subscribe: %d latest entr%s, live from feed.xml"
              % (n, "y" if n == 1 else "ies"))
        return 0

    if page[start:stop] != fresh:
        open(PAGE, "w", encoding="utf-8").write(page[:start] + fresh + page[stop:])
        print("insights/subscribe.html: %d entries written" % fresh.count("<article>"))
    else:
        print("insights/subscribe.html: current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
