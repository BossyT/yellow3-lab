#!/usr/bin/env python3
"""
Render the AI Top 10 graphic from a persisted snapshot.

EVERY NUMBER COMES FROM THE SNAPSHOT. This script never reads the live dataset
and never fetches anything. That is the whole reason the snapshot exists: a
graphic made on Tuesday must show exactly what the page showed for that window,
or the first person to check our work finds us disagreeing with ourselves.

HTML template rendered through headless Chrome, the same approach as the social
cards, so a design change is a code change rather than a new file from someone's
image editor.

    python3 research/top10_render.py                 latest snapshot
    python3 research/top10_render.py 2026-33         a specific edition

Outputs, per edition:
    research/model-adoption/top10/{YYYY-WW}.png       1080 x 1620, portrait
    research/model-adoption/top10/{YYYY-WW}-og.png    1200 x 630
    research/model-adoption/top10/latest.png          alias of the newest
"""

import glob
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "research", "model-adoption", "top10")
def _find_chrome():
    """Chrome is somewhere else on a CI runner than on a Mac."""
    for c in (os.environ.get("CHROME_PATH"),
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
              "/usr/bin/chromium-browser", "/usr/bin/chromium"):
        if c and os.path.exists(c):
            return c
    return ""


CHROME = _find_chrome()
PORT = int(os.environ.get("TOP10_PORT", "8793"))

GOLD = "#ffe500"
INK = "#08080a"


def esc(v):
    return html.escape(str(v if v is not None else ""))


def spark_svg(values, w=132, h=34, colour="#8a8a93"):
    """A 7-day sparkline. Flat line if the series is degenerate."""
    if not values or len(values) < 2:
        return '<svg width="%d" height="%d"></svg>' % (w, h)
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = w / (len(values) - 1)
    pts = " ".join("%.1f,%.1f" % (i * step, h - 3 - (v - lo) / span * (h - 6))
                   for i, v in enumerate(values))
    last_x = w
    last_y = h - 3 - (values[-1] - lo) / span * (h - 6)
    return ('<svg width="%d" height="%d" viewBox="0 0 %d %d">'
            '<polyline points="%s" fill="none" stroke="%s" stroke-width="1.6" '
            'stroke-linejoin="round" stroke-linecap="round"/>'
            '<circle cx="%.1f" cy="%.1f" r="2.4" fill="%s"/></svg>'
            % (w, h, w, h, pts, colour, last_x - 1, last_y, GOLD))


def delta_cell(d):
    if d is None:
        return '<span class="d flat">no prior week</span>'
    if d > 0.005:
        return '<span class="d up">&#9650; +%.2f pp</span>' % d
    if d < -0.005:
        return '<span class="d down">&#9660; %.2f pp</span>' % d
    return '<span class="d flat">0.00 pp</span>'


def rank_note(row):
    prev = row.get("prev_rank")
    if row.get("new") or prev is None:
        return "new entry"
    if prev == row["rank"]:
        return "held at %02d" % prev
    return "was %02d" % prev


def human_tokens(n):
    n = float(n or 0)
    for unit, size in (("trillion", 1e12), ("billion", 1e9), ("million", 1e6)):
        if n >= size:
            return "%.1f %s" % (n / size, unit)
    return "%.0f" % n


def build_html(s, variant="portrait"):
    # The OG card is a different job from the poster. At 1200x630 ten rows plus
    # two callouts and a stat band simply do not fit - the first attempt cut off
    # at rank 09 - so the card shows the top five and the headline movement, and
    # sends the reader to the instrument for the rest.
    portrait = (variant == "portrait")
    shown = s["rows"] if portrait else s["rows"][:5]
    rows = ""
    for r in shown:
        rows += """
      <div class="row">
        <div class="rk">%02d</div>
        <div class="who"><b>%s</b><span>%s &middot; %s</span></div>
        <div class="spark">%s</div>
        <div class="pct">%.2f%%</div>
        <div class="chg">%s<em>%s</em></div>
      </div>""" % (
            r["rank"], esc(r["name"]), esc(r.get("developer") or ""),
            esc(r.get("country") or ""), spark_svg(r.get("spark") or []),
            r["pct"], delta_cell(r.get("delta_pp")), esc(rank_note(r)))

    mover = s.get("biggest_mover")
    mover_line = ""
    if mover:
        d = mover["delta_pp"]
        mover_line = ("%s %s %.2f pp, the largest move in the ten."
                      % (esc(mover["name"]), "gains" if d > 0 else "loses", abs(d)))

    call = s.get("call") or {}
    grade = (call.get("last_week_grade") or "").strip()
    t = s["totals"]

    return """<!doctype html>
<html><head><meta charset="utf-8"><title>%(edition)s</title><style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:%(W)dpx;height:%(H)dpx;background:%(INK)s;color:#f4f4f6;
  font-family:Arial,Helvetica,sans-serif;overflow:hidden}
.sheet{width:%(W)dpx;height:%(H)dpx;padding:%(pad)dpx;display:flex;flex-direction:column}
.kicker{font-size:%(kick)dpx;letter-spacing:.16em;font-weight:700;color:%(GOLD)s;text-transform:uppercase}
.rule{width:78px;height:5px;background:%(GOLD)s;margin:14px 0 %(rulegap)dpx}
h1{font-size:%(h1)dpx;line-height:.94;letter-spacing:-.035em;font-weight:400}
.sub{font-size:%(sub)dpx;color:#b9b9c2;margin-top:%(submt)dpx}
.win{font-size:%(win)dpx;color:#8a8a93;margin-top:6px;letter-spacing:.02em}
.rows{margin-top:%(rowsmt)dpx;flex:1}
.row{display:grid;grid-template-columns:%(cols)s;align-items:center;gap:%(gap)dpx;
  padding:%(rowpad)dpx 0;border-top:1px solid #1e1e24}
.row:first-child{border-top:0}
.rk{font-size:%(rk)dpx;font-weight:400;color:%(GOLD)s;letter-spacing:-.04em;line-height:1}
.who b{display:block;font-size:%(name)dpx;font-weight:400;letter-spacing:-.02em}
.who span{display:block;font-size:%(meta)dpx;color:#8a8a93;margin-top:3px}
.pct{font-size:%(pct)dpx;font-weight:400;text-align:right;letter-spacing:-.03em}
.chg{text-align:right}
.chg .d{font-size:%(chg)dpx;font-weight:700;white-space:nowrap}
.chg .up{color:#46d091}.chg .down{color:#ff7a63}.chg .flat{color:#8a8a93}
.chg em{display:block;font-style:normal;font-size:%(meta)dpx;color:#6f6f78;margin-top:3px}
.callout{margin-top:%(comt)dpx;border-left:4px solid %(GOLD)s;padding:%(copad)dpx 0 %(copad)dpx 16px;background:#0f0f13}
.callout b{display:block;font-size:%(colab)dpx;letter-spacing:.14em;text-transform:uppercase;color:%(GOLD)s}
.callout p{font-size:%(cotxt)dpx;margin-top:6px;line-height:1.35}
.callout p.small{font-size:%(meta)dpx;color:#8a8a93;margin-top:6px}
.grade{display:inline-block;font-size:%(meta)dpx;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;color:%(INK)s;background:%(GOLD)s;padding:2px 8px;border-radius:3px}
.band{margin-top:%(bandmt)dpx;display:grid;grid-template-columns:repeat(4,1fr);
  gap:1px;background:#1e1e24;border-top:1px solid #1e1e24;border-bottom:1px solid #1e1e24}
.band div{background:%(INK)s;padding:%(bandpad)dpx 0}
.band b{display:block;font-size:%(bandnum)dpx;font-weight:400;letter-spacing:-.02em}
.band span{display:block;font-size:%(meta)dpx;color:#8a8a93;margin-top:4px}
.foot{margin-top:%(footmt)dpx;font-size:%(meta)dpx;color:#6f6f78;line-height:1.45}
.foot b{color:#b9b9c2;font-weight:700}
</style></head><body><div class="sheet">
  <div class="kicker">Weekly edition &middot; %(edition)s</div>
  <span class="rule"></span>
  <h1>THE AI TOP 10</h1>
  <p class="sub">Most-routed AI models right now</p>
  <p class="win">%(window)s</p>
  <div class="rows">%(rows)s</div>
  %(blocks)s
  <p class="foot"><b>Data:</b> %(source)s &middot; %(url)s%(methodline)s</p>
</div></body></html>""" % {
        "W": 1080 if variant == "portrait" else 1200,
        "H": 1620 if variant == "portrait" else 630,
        "INK": INK, "GOLD": GOLD,
        "pad": 64 if variant == "portrait" else 44,
        "kick": 17 if variant == "portrait" else 14,
        "rulegap": 22 if variant == "portrait" else 12,
        "h1": 86 if variant == "portrait" else 58,
        "sub": 27 if variant == "portrait" else 19,
        "submt": 16 if variant == "portrait" else 8,
        "win": 18 if variant == "portrait" else 14,
        "rowsmt": 24 if variant == "portrait" else 14,
        "cols": ("70px 1fr 124px 128px 168px" if variant == "portrait"
                 else "54px 1fr 96px 104px 150px"),
        "gap": 18 if variant == "portrait" else 12,
        "rowpad": 12 if variant == "portrait" else 9,
        "rk": 40 if variant == "portrait" else 24,
        "name": 25 if variant == "portrait" else 19,
        "meta": 15 if variant == "portrait" else 11,
        "pct": 34 if variant == "portrait" else 22,
        "chg": 19 if variant == "portrait" else 13,
        "comt": 20 if variant == "portrait" else 10,
        "copad": 14 if variant == "portrait" else 8,
        "colab": 13 if variant == "portrait" else 11,
        "cotxt": 21 if variant == "portrait" else 14,
        "bandmt": 26 if variant == "portrait" else 10,
        "bandpad": 20 if variant == "portrait" else 10,
        "bandnum": 30 if variant == "portrait" else 19,
        "footmt": 20 if variant == "portrait" else 10,
        "blocks": ((
            '<div class="callout"><b>Biggest mover</b><p>%(mover)s</p></div>'
            '<div class="callout"><b>This week\'s call</b><p>%(call)s</p>'
            '<p class="small">Last week: %(lastcall)s %(gradehtml)s</p></div>'
            '<div class="band">'
            '<div><b>%(models)d</b><span>models tracked</span></div>'
            '<div><b>%(tokens)s</b><span>routed tokens, latest day</span></div>'
            '<div><b>%(regionpct).2f%%</b><span>%(region)s share</span></div>'
            '<div><b>7 days</b><span>measurement window</span></div>'
            '</div>') if portrait else (
            '<div class="callout"><b>Biggest mover</b><p>%(mover)s</p>'
            '<p class="small">%(region)s holds %(regionpct).2f percent of routed tokens. '
            'Full ranking of %(models)d models on the instrument.</p></div>')) % {
                "mover": mover_line or "No prior week to compare.",
                "call": esc(call.get("this_week") or "No call on the record this week."),
                "lastcall": esc(call.get("last_week") or "none"),
                "gradehtml": ('<span class="grade">%s</span>' % esc(grade)) if grade else "",
                "models": t["models_tracked"],
                "tokens": human_tokens(t["routed_tokens_day"]),
                "regionpct": t["top_region_pct"],
                "region": esc(t["top_region"]),
            },
        "methodline": ("<br>" + esc(s["methodology"])) if portrait else "",
        "edition": esc(s["edition"]),
        "window": esc(s["window"]["label"]),
        "rows": rows,
        "mover": mover_line or "No prior week to compare.",
        "call": esc(call.get("this_week") or "No call on the record this week."),
        "lastcall": esc(call.get("last_week") or "none"),
        "gradehtml": ('<span class="grade">%s</span>' % esc(grade)) if grade else "",
        "models": t["models_tracked"],
        "tokens": human_tokens(t["routed_tokens_day"]),
        "regionpct": t["top_region_pct"],
        "region": esc(t["top_region"]),
        "source": esc(s["source"]),
        "url": esc(s["url"]),
        "method": esc(s["methodology"]),
    }


def shoot(path_html, out_png, w, h):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=1", "--window-size=%d,%d" % (w, h),
                    "--virtual-time-budget=6000", "--screenshot=" + out_png,
                    "http://127.0.0.1:%d/%s" % (PORT, os.path.basename(path_html))],
                   capture_output=True, text=True, timeout=120)


def main():
    editions = sorted(glob.glob(os.path.join(DIR, "*.json")))
    if not editions:
        sys.exit("no snapshots in research/model-adoption/top10 - "
                 "run research/top10_snapshot.py first")
    wanted = [a for a in sys.argv[1:] if not a.startswith("-")]
    path = (os.path.join(DIR, wanted[0] + ".json") if wanted else editions[-1])
    if not os.path.exists(path):
        sys.exit("no snapshot for %s" % wanted[0])
    snap = json.load(open(path, encoding="utf-8"))

    if not CHROME:
        sys.exit("no Chrome found. Set CHROME_PATH, or install Chrome, "
                 "or run this where a browser exists - the graphic is rendered, "
                 "not drawn by hand.")
    work = tempfile.mkdtemp(prefix="top10-")
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT)],
                           cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.2)
        for variant, w, h, suffix in (("portrait", 1080, 1620, ""),
                                      ("og", 1200, 630, "-og")):
            f = os.path.join(work, "%s%s.html" % (snap["edition"], suffix))
            open(f, "w", encoding="utf-8").write(build_html(snap, variant))
            out = os.path.join(DIR, "%s%s.png" % (snap["edition"], suffix))
            shoot(f, out, w, h)
            if not os.path.exists(out):
                sys.exit("render failed for %s" % variant)
            print("  wrote %s" % os.path.relpath(out, ROOT))
    finally:
        srv.terminate()
        shutil.rmtree(work, ignore_errors=True)

    if path == editions[-1]:
        shutil.copy2(os.path.join(DIR, snap["edition"] + ".png"),
                     os.path.join(DIR, "latest.png"))
        print("  wrote research/model-adoption/top10/latest.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
