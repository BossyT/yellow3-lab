#!/usr/bin/env python3
"""
Build the AI Top 10 archive page from the persisted snapshots.

One page listing every edition, newest first, each linking to its graphic and to
the instrument it was cut from. Regenerated from the snapshots rather than
hand-maintained, so an edition cannot exist as a PNG that the archive never
mentions.

The page shell - nav, footer, typography - is lifted from the sibling instrument
page so it matches the site exactly and satisfies the standing rule that every
public page carries the standard menu and footer.

    python3 research/top10_archive.py
"""

import datetime
import glob
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "research", "model-adoption", "top10")
SIBLING = os.path.join(ROOT, "research", "model-adoption", "live.html")
OUT = os.path.join(DIR, "index.html")

HOST = "https://www.yellow3.io"
CANONICAL = HOST + "/research/model-adoption/top10"


def esc(v):
    return html.escape(str(v if v is not None else ""))


def shell():
    """Header and footer exactly as the instrument pages carry them."""
    s = open(SIBLING, encoding="utf-8").read()
    # The SITE nav, not the instrument's page header. <header> on live.html is
    # that page's own hero and carries its H1 - lifting it gave the archive two
    # H1s, "Model adoption" above "The AI Top 10".
    head = re.search(r'(<nav[^>]*class="site-nav".*?</nav>)', s, re.S)
    foot = re.search(r"(<footer.*?</footer>)", s, re.S)
    # The nav and footer carry no styles of their own - those live in the page's
    # <style> block. Lifting the markup without it gave a giant unstyled logo and
    # default blue links. The page's own rules are written after this one, so
    # they win where the two overlap.
    css = re.search(r"<style>(.*?)</style>", s, re.S)
    if not head or not foot or not css:
        sys.exit("could not lift the site nav, footer or styles from live.html")
    return head.group(1), foot.group(1), css.group(1)


def main():
    snaps = []
    for path in sorted(glob.glob(os.path.join(DIR, "*.json")), reverse=True):
        snaps.append(json.load(open(path, encoding="utf-8")))
    if not snaps:
        sys.exit("no snapshots to list - run research/top10_snapshot.py first")

    header, footer, sitecss = shell()
    cards = ""
    for s in snaps:
        top3 = s["rows"][:3]
        lead = " &middot; ".join("%s %s%%" % (esc(r["name"]), ("%.2f" % r["pct"]))
                                 for r in top3)
        mover = s.get("biggest_mover")
        mover_line = ""
        if mover:
            d = mover["delta_pp"]
            mover_line = ("Biggest mover: %s %s %.2f pp."
                          % (esc(mover["name"]), "up" if d > 0 else "down", abs(d)))
        cards += """
        <article class="ed">
          <a class="ed-img" href="/research/model-adoption/top10/%(ed)s.png">
            <img src="/research/model-adoption/top10/%(ed)s.png" alt="The AI Top 10, %(win)s" loading="lazy" />
          </a>
          <div class="ed-body">
            <div class="ed-no">Edition %(ed)s</div>
            <h2>%(win)s</h2>
            <p class="ed-lead">%(lead)s</p>
            <p class="ed-mover">%(mover)s</p>
            <p class="ed-links">
              <a href="/research/model-adoption/top10/%(ed)s.png">Open the graphic</a>
              <a href="/research/model-adoption/live">See the instrument</a>
            </p>
          </div>
        </article>""" % {"ed": esc(s["edition"]), "win": esc(s["window"]["label"]),
                         "lead": lead, "mover": mover_line}

    latest = snaps[0]
    desc = ("The AI Top 10, a weekly ranked edition of the most-routed AI models, "
            "cut from yellow3's live Model Adoption instrument. Archive of every "
            "edition with its measurement window.")

    page = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>The AI Top 10 - archive | yellow3 Model Intelligence</title>
  <meta name="description" content="%(desc)s" />
  <link rel="canonical" href="%(canonical)s" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="yellow3 lab" />
  <meta property="og:title" content="The AI Top 10 - archive | yellow3 Model Intelligence" />
  <meta property="og:description" content="%(desc)s" />
  <meta property="og:url" content="%(canonical)s" />
  <meta property="og:image" content="%(host)s/research/model-adoption/top10/%(latest)s-og.png" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:image" content="%(host)s/research/model-adoption/top10/%(latest)s-og.png" />
  <style>%(sitecss)s</style>
  <style>
    :root{--ink:#0c0c0c;--muted:#696969;--mid:#4a4a4a;--line:#e6e4dd;--yellow:#ffe500;--card:#fbfbf9}
    *{box-sizing:border-box}
    body{margin:0;background:#fff;color:var(--ink);font-family:Arial,Helvetica,sans-serif;line-height:1.5}
    .wrap{max-width:1180px;margin:0 auto;padding:0 40px}
    .head{padding:120px 0 32px;border-bottom:1px solid var(--line)}
    .eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;font-weight:700;color:var(--muted)}
    .rule{display:block;width:64px;height:4px;background:var(--yellow);margin:12px 0 22px}
    h1{font-size:64px;line-height:.98;letter-spacing:-.04em;font-weight:400;margin:0}
    .lede{font-size:20px;color:var(--mid);max-width:60ch;margin:18px 0 0}
    .meta{font-size:13px;color:var(--muted);margin-top:14px}
    .eds{padding:40px 0 80px;display:flex;flex-direction:column;gap:34px}
    .ed{display:grid;grid-template-columns:300px 1fr;gap:30px;align-items:start;
      border-bottom:1px solid var(--line);padding-bottom:34px}
    .ed:last-child{border-bottom:0}
    .ed-img{display:block;border:1px solid var(--line);background:#08080a}
    .ed-img img{display:block;width:100%%;height:auto}
    .ed-no{font-size:11px;letter-spacing:.14em;text-transform:uppercase;font-weight:700;color:var(--muted)}
    .ed h2{font-size:28px;font-weight:400;letter-spacing:-.02em;margin:6px 0 10px}
    .ed-lead{font-size:16px;margin:0 0 6px}
    .ed-mover{font-size:14px;color:var(--muted);margin:0}
    .ed-links{margin:14px 0 0;display:flex;gap:20px}
    .ed-links a{font-size:14px;font-weight:700;color:var(--ink);text-decoration:none;border-bottom:2px solid var(--yellow);padding-bottom:2px}
    @media (max-width:760px){ .ed{grid-template-columns:1fr} h1{font-size:42px} .wrap{padding:0 24px} .head{padding-top:104px} }
  </style>
</head>
<body>
%(header)s

  <section class="head">
    <div class="wrap">
      <p class="eyebrow">yellow3 Model Intelligence</p>
      <span class="rule"></span>
      <h1>The AI Top 10</h1>
      <p class="lede">A weekly ranked edition of the most-routed AI models, cut from
        the live instrument. Each edition is a frozen snapshot of one seven-day
        window, so the graphic and the instrument always agree for that week.</p>
      <p class="meta">%(count)d edition%(plural)s &middot; the instrument itself updates live</p>
    </div>
  </section>

  <div class="wrap">
    <div class="eds">%(cards)s</div>
  </div>

%(footer)s
</body>
</html>
""" % {"desc": esc(desc), "canonical": CANONICAL, "host": HOST,
       "latest": esc(latest["edition"]), "header": header, "footer": footer,
       "sitecss": sitecss,
       "cards": cards, "count": len(snaps), "plural": "" if len(snaps) == 1 else "s"}

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(page)
    print("  wrote %s  (%d edition%s)"
          % (os.path.relpath(OUT, ROOT), len(snaps), "" if len(snaps) == 1 else "s"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
