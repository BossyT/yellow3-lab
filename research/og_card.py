#!/usr/bin/env python3
"""
Resolve the Open Graph card for a page, from its canonical URL.

One definition, imported by every generator, so a regenerated supplier profile
or model page cannot drift back to a hand-named card the way the June set did.

The cards themselves are built by research/gen_og.py from research/og_frame.html.
This module only answers "which card does this URL get".
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS = os.path.join(ROOT, "og", "cards")
HOST = "https://www.yellow3.io"

# Every page that has a card of its own gets it. A page that does not - a
# noindex claim or add flow under a supplier profile - inherits its parent's,
# which is about its subject rather than about the company. Last resort is the
# homepage card, which always exists.
FALLBACK = "index"


def slug_for_path(path):
    path = path.strip("/")
    if path.endswith(".html"):
        path = path[:-len(".html")]
    if path.endswith("/index"):
        path = path[:-len("/index")]
    if not path or path == "index":
        return "index"
    return re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")


def exists(slug):
    return os.path.exists(os.path.join(CARDS, slug + ".png"))


def slug_for(canonical):
    path = re.sub(r"^https?://[^/]+", "", canonical)
    slug = slug_for_path(path)
    if exists(slug):
        return slug
    parts = [p for p in path.strip("/").split("/") if p]
    if len(parts) > 1:
        parent = slug_for_path("/".join(parts[:-1]))
        if exists(parent):
            return parent
    return FALLBACK


def url(canonical):
    return "%s/og/cards/%s.png" % (HOST, slug_for(canonical))
