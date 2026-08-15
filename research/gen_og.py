#!/usr/bin/env python3
"""
Generate every yellow3 Open Graph card from one frame.

Design authority: GPT. OG Master Frame v1.2, frozen 2026-08-15, plus the
standard fallback panel copy frozen by Thomas the same day. This file makes no
design decisions - it applies the frozen rules and reports anything they do not
cover.

Why it exists: the eleven cards in /og were drawn by hand on 24 June and the
generators only ever wrote a hardcoded filename into the og:image tag. When the
site was redesigned in August the cards could not follow, so all eleven kept a
retired typeface and three kept retired positioning. A frame regenerates.

Fitting is done in the browser, not estimated. Chrome measures real Arial line
breaking at each candidate size and the largest that fits within three lines
wins. Nothing is ever truncated and no ellipsis is ever added.

    python3 research/gen_og.py            render all 290 + QA report
    python3 research/gen_og.py --check    QA only, no PNGs written

Nothing here touches a page's og:image tag. Wiring is a separate step and only
after the contact sheet is reviewed.
"""

import concurrent.futures
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAME = os.path.join(ROOT, "research", "og_frame.html")
LOGO = os.path.join(ROOT, "logo.png")
BUILD = os.environ.get("OG_BUILD_DIR", "/private/tmp/claude-501/-Users-tcm/"
                       "955bf7f5-bb89-4855-831f-fad554739c52/scratchpad/ogbuild")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = int(os.environ.get("OG_PORT", "8732"))

SKIP_DIRS = {"node_modules", ".git", ".vercel", "Autonomous ai software"}
NOT_PUBLIC = {"admin.html", "google4b600ad4155228a3.html"}

# v1.2 section 1 and 2 - the ladders. Largest that fits, max 3 lines, no floor
# below these. 42px is the headline floor by ruling: a card that cannot fit at
# 42px fails and needs an explicit headline override rather than 36px type.
HEAD_LADDER = [64, 56, 48, 42]
SUPPORT_LADDER = [21, 19, 17]
MAX_LINES = 3

# v1.2 section 1 - an unusually long editorial title must not quietly shrink the
# whole system. Add a page here to give it a purpose-written social headline.
HEADLINE_OVERRIDES = {}
# v1.2 section 2 - reserved: lets an important page carry shorter social copy
# without corrupting its SEO description.
SUPPORT_OVERRIDES = {}

FALLBACK_PANEL = ('<div class="fb-1">Research. Experiment. Build.</div>'
                  '<div class="fb-rule"></div>'
                  '<div class="fb-2">Emerging technology made useful.</div>')


# --------------------------------------------------------------- collection

def clean(frag):
    """Flatten a fragment to the words a card should carry.

    A <br> is a word boundary and must become a space: /platforms sets its H1 as
    "Three products.<br>Built to do the work." and stripping tags without it
    produced "Three products.Built to do the work." on the card. Inline tags
    must NOT become spaces - five H1s wrap a word in a <span> to highlight it,
    and a space there gives "improve decisions , not to inform."
    """
    frag = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", frag, flags=re.S | re.I)
    frag = re.sub(r"<br\s*/?>", " ", frag, flags=re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", frag))).strip()


def route_for(rel):
    """v1.2 section 5 - yellow3.io/path. No www, no scheme, no trailing slash."""
    p = rel[:-len(".html")] if rel.endswith(".html") else rel
    if p.endswith("/index"):
        p = p[:-len("/index")]
    if p == "index":
        return "yellow3.io"
    return "yellow3.io/" + p


def category_for(rel, page_html):
    """v1.2 section 4 - the frozen vocabulary. Never invented from the body."""
    exact = {
        "index.html": "AI + EMERGING TECHNOLOGY",
        "about.html": "ABOUT YELLOW3 LAB",
        "advisory.html": "ADVISORY · YELLOW3 LAB",
        "platforms.html": "PLATFORMS",
        "research.html": "YELLOW3 RESEARCH",
        "software.html": "A YELLOW3 LAB PLATFORM · COMING SOON",
        "contact.html": "CONTACT",
        "research/eu-ai-act.html": "EU AI ACT · LIVING RECORD",
        "research/framework.html": "YELLOW3 RESEARCH · METHOD",
        "insights/index.html": "YELLOW3 INSIGHTS",
        # Model Intelligence report and archive, not per-model Explorer pages.
        "research/model-adoption/reports/index.html": "YELLOW3 MODEL INTELLIGENCE",
        "research/model-adoption/briefing.html": "YELLOW3 MODEL INTELLIGENCE",
    }
    if rel in exact:
        return exact[rel]
    if rel.startswith("research/digital-product-passport/suppliers"):
        return "YELLOW3 DPP SUPPLIER REGISTER"
    if rel.startswith("research/digital-product-passport"):
        return "DIGITAL PRODUCT PASSPORT"
    if rel.startswith("research/model-adoption"):
        return "MODEL ADOPTION · UPDATED WEEKLY"
    if rel.startswith("insights/"):
        m = re.search(r'class="[^"]*\btag\b[^"]*"[^>]*>([^<]{2,40})<', page_html)
        tag = clean(m.group(1)).upper() if m else ""
        return "YELLOW3 INSIGHTS · " + tag if tag else "YELLOW3 INSIGHTS"
    return "YELLOW3 LAB"


def proof_for(rel, page_html):
    """v1.2 section 6 - real page visual first, standard panel otherwise.

    Editorial photography covers the box. Product and research interfaces are
    contained, because cropping interface text to fill a box is exactly what
    the house rule on real interfaces forbids.
    """
    if rel.startswith("insights/"):
        m = re.search(r'og:image" content="[^"]*(/insights/hero-[^"]+)"', page_html)
        if m:
            return m.group(1), "cover"
    # A listing page has no visual of its own. /insights is a grid of article
    # cards, so taking the first image on it made the index card look like one
    # particular article - the closest thing in the set to inventing proof
    # media, which section 6 forbids. Listings take the standard panel. The
    # homepage is not a listing and keeps its own product visual.
    if rel.endswith("/index.html"):
        return None, None
    body = page_html.split("</header>")[-1]
    for src in re.findall(r'<img[^>]+src="([^"]+)"', body):
        if "logo" in src.lower() or not src.startswith("/"):
            continue
        if not os.path.exists(os.path.join(ROOT, src.lstrip("/"))):
            continue
        return src, "contain"
    return None, None


def collect():
    pages = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in sorted(files):
            if not f.endswith(".html"):
                continue
            rel = os.path.relpath(os.path.join(base, f), ROOT)
            if rel in NOT_PUBLIC or rel.startswith("research/og_frame"):
                continue
            s = open(os.path.join(base, f), encoding="utf-8", errors="ignore").read()
            if "noindex" in s:
                continue
            m = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
            h1 = clean(m.group(1)) if m else ""
            d = re.search(r'<meta name="description" content="([^"]*)"', s)
            desc = html.unescape(d.group(1)).strip() if d else ""
            src, fit = proof_for(rel, s)
            pages.append({
                "rel": rel,
                "h1": HEADLINE_OVERRIDES.get(rel, h1),
                "desc": SUPPORT_OVERRIDES.get(rel, desc),
                "category": category_for(rel, s),
                "route": route_for(rel),
                "proof": src,
                "fit": fit,
                "slug": re.sub(r"[^a-z0-9]+", "-", rel[:-5].lower()).strip("-"),
            })
    return pages


# ------------------------------------------------------------------ fitting

PROBE_JS = r"""
(function(){
  const rows = __ROWS__;
  const HEAD = __HEAD__, SUP = __SUP__, MAX = __MAX__;
  const track = s => s === 64 ? '-.055em' : '-.05em';
  const box = document.createElement('div');
  box.style.cssText = 'position:absolute;left:-9999px;top:0;visibility:hidden;'
    + 'font-family:Arial,Helvetica,sans-serif;white-space:normal;';
  document.body.appendChild(box);

  function lines(text, size, lh, width, ls){
    box.style.width = width + 'px';
    box.style.fontSize = size + 'px';
    box.style.lineHeight = String(lh);
    box.style.letterSpacing = ls;
    box.style.fontWeight = '400';
    box.textContent = text;
    return Math.round(box.offsetHeight / (size * lh));
  }
  function firstSentence(t){
    const m = t.match(/^.*?[.!?](?=\s|$)/);
    return m ? m[0].trim() : null;
  }

  const out = [];
  for (const r of rows){
    let hs = null, hl = null;
    for (const s of HEAD){
      const n = lines(r.h1, s, 0.95, 665, track(s));
      if (n <= MAX){ hs = s; hl = n; break; }
    }
    let ss = null, sl = null, mode = 'full', text = r.desc;
    if (!r.desc){ mode = 'none'; text = ''; }
    else {
      for (const s of SUP){
        const n = lines(r.desc, s, 1.30, 640, 'normal');
        if (n <= MAX){ ss = s; sl = n; break; }
      }
      if (ss === null){
        const fs = firstSentence(r.desc);
        if (fs && fs !== r.desc){
          for (const s of SUP){
            const n = lines(fs, s, 1.30, 640, 'normal');
            if (n <= MAX){ ss = s; sl = n; mode = 'sentence'; text = fs; break; }
          }
        }
        if (ss === null){ mode = 'omitted'; text = ''; }
      }
    }
    out.push({rel:r.rel, headSize:hs, headLines:hl,
              supSize:ss, supLines:sl, supMode:mode, supText:text});
  }
  document.title = 'done';
  document.getElementById('probe-out').textContent = '@@' + JSON.stringify(out) + '@@';
})();
"""


def probe(pages):
    """Measure every headline and support line in the real engine."""
    frame = open(FRAME, encoding="utf-8").read()
    js = (PROBE_JS
          .replace("__ROWS__", json.dumps([{"rel": p["rel"], "h1": p["h1"],
                                            "desc": p["desc"]} for p in pages]))
          .replace("__HEAD__", json.dumps(HEAD_LADDER))
          .replace("__SUP__", json.dumps(SUPPORT_LADDER))
          .replace("__MAX__", str(MAX_LINES)))
    page = frame.replace("</body>", '<pre id="probe-out"></pre><script>%s</script></body>' % js)
    path = os.path.join(BUILD, "_probe.html")
    open(path, "w", encoding="utf-8").write(page)
    dom = chrome_dump("http://127.0.0.1:%d/_probe.html" % PORT)
    m = re.search(r"@@(\[.*?\])@@", dom, re.S)
    if not m:
        sys.exit("probe produced no result - Chrome returned %d bytes" % len(dom))
    raw = html.unescape(m.group(1))
    return {r["rel"]: r for r in json.loads(raw)}


# ------------------------------------------------------------------ render

def chrome_dump(url):
    """Read a measured result back out of the page.

    Deliberately minimal flags. --dump-dom returns an empty document the moment
    --window-size or --user-data-dir is present, which cost an hour to find, so
    do not add flags here for symmetry with the screenshot path. The probe
    measures against explicit widths and never reads the viewport, so it does
    not need a window size.
    """
    r = subprocess.run([CHROME, "--headless=new", "--disable-gpu",
                        "--virtual-time-budget=8000", "--dump-dom", url],
                       capture_output=True, text=True, timeout=180)
    return r.stdout


def chrome_shot(url, png, height=630):
    """Write one screenshot.

    No --user-data-dir: on this machine that flag hangs Chrome outright, for
    screenshots as well as --dump-dom. Without it concurrent instances fight
    over the default profile and only one in six survives, so cards are
    rendered ten to a sheet and sliced instead of one Chrome per card.
    """
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=1",
                    "--window-size=1200,%d" % height,
                    "--virtual-time-budget=6000", "--screenshot=" + png, url],
                   capture_output=True, text=True, timeout=180)


def card_block(p, fit, body_tpl):
    if p["proof"]:
        proof = '<img class="%s" src="%s" alt="">' % (fit_class(p), p["proof"])
        pclass = ""
    else:
        proof = FALLBACK_PANEL
        pclass = "fallback"
    out = body_tpl
    out = out.replace("{{CATEGORY}}", html.escape(p["category"]))
    out = out.replace("{{TITLE_CLASS}}", "s%d" % fit["headSize"])
    out = out.replace("{{TITLE}}", html.escape(p["h1"]))
    out = out.replace("{{PROOF_CLASS}}", pclass)
    out = out.replace("{{PROOF}}", proof)
    out = out.replace("{{SUPPORT_CLASS}}", "t%d" % fit["supSize"] if fit["supSize"] else "t17")
    out = out.replace("{{SUPPORT}}", html.escape(fit["supText"]))
    out = out.replace("{{ROUTE}}", html.escape(p["route"]))
    return out


def fit_class(p):
    return p["fit"] or "contain"


SHEET = 10  # cards per Chrome launch


def render_all(pages, fits, outdir):
    """Render every card and slice them out of the sheets."""
    from PIL import Image
    frame = open(FRAME, encoding="utf-8").read()
    head = frame[frame.index("<head>") + 6:frame.index("</head>")]
    body_tpl = frame[frame.index("<body>") + 6:frame.index("</body>")].strip()

    todo = [(p, fits[p["rel"]]) for p in pages if fits[p["rel"]]["headSize"] is not None]
    written = []
    for start in range(0, len(todo), SHEET):
        batch = todo[start:start + SHEET]
        blocks = "\n".join(card_block(p, f, body_tpl) for p, f in batch)
        sheet = ("<!doctype html><html><head>%s</head><body>%s</body></html>"
                 % (head, blocks))
        # the frame pins html/body to one card; a sheet holds several
        sheet = sheet.replace("width:1200px;\n  height:630px;\n  overflow:hidden;",
                              "width:1200px;\n  overflow:hidden;", 1)
        name = "_sheet%03d" % (start // SHEET)
        open(os.path.join(BUILD, name + ".html"), "w", encoding="utf-8").write(sheet)
        shot = os.path.join(BUILD, name + ".png")
        chrome_shot("http://127.0.0.1:%d/%s.html" % (PORT, name), shot,
                    height=630 * len(batch))
        if not os.path.exists(shot):
            print("    sheet %s failed to render" % name, flush=True)
            continue
        im = Image.open(shot)
        for i, (p, _f) in enumerate(batch):
            card = im.crop((0, i * 630, 1200, (i + 1) * 630))
            out = os.path.join(outdir, (p["slug"] or "index") + ".png")
            card.save(out)
            written.append(((p["slug"] or "index"), True))
        os.remove(shot)
        print("    rendered %d/%d" % (len(written), len(todo)), flush=True)
    return written


# ------------------------------------------------- brand contract at renderer

def logo_reference():
    """v1.2 section 7 - no PNG is written unless the canonical logo resolves."""
    from PIL import Image
    if not os.path.exists(LOGO):
        sys.exit("BRAND CONTRACT: /logo.png is missing. No cards written.")
    im = Image.open(LOGO)
    w = max(1, round(im.size[0] * 47 / im.size[1]))
    im = im.convert("RGBA").resize((w, 47), Image.LANCZOS)
    flat = Image.new("RGB", (w, 47), "white")
    flat.paste(im, (0, 0), im)
    ink = sum(1 for px in flat.convert("L").getdata() if px < 200)
    if ink < 200:
        sys.exit("BRAND CONTRACT: /logo.png decoded but carries no ink.")
    return w, ink


def verify_logo(png, w, expect):
    from PIL import Image
    im = Image.open(png).convert("L").crop((64, 46, 64 + w, 46 + 47))
    ink = sum(1 for px in im.getdata() if px < 200)
    return abs(ink - expect) <= max(40, expect * 0.15), ink


# ------------------------------------------------------------ contact sheet

def contact_sheet(pages, outdir, path, cols=5, thumb=340):
    from PIL import Image, ImageDraw
    shots = [(p, os.path.join(outdir, (p["slug"] or "index") + ".png")) for p in pages]
    shots = [(p, s) for p, s in shots if os.path.exists(s)]
    th = round(thumb * 630 / 1200)
    rows = (len(shots) + cols - 1) // cols
    pad, cap = 16, 22
    sheet = Image.new("RGB", (cols * (thumb + pad) + pad,
                              rows * (th + cap + pad) + pad), "#e9e9e6")
    d = ImageDraw.Draw(sheet)
    for i, (p, s) in enumerate(shots):
        x = pad + (i % cols) * (thumb + pad)
        y = pad + (i // cols) * (th + cap + pad)
        sheet.paste(Image.open(s).resize((thumb, th), Image.LANCZOS), (x, y))
        d.text((x, y + th + 6), p["route"][:52], fill="#444")
    sheet.save(path)
    return len(shots), sheet.size


# ------------------------------------------------------------------ driver

def serve():
    """Serve a build root that resolves /logo.png, /img/... and /insights/...

    Symlinks rather than copies, so the cards render against the real assets
    and the repo stays clean.
    """
    os.makedirs(BUILD, exist_ok=True)
    for asset in ("logo.png", "img", "insights", "og", "research"):
        link = os.path.join(BUILD, asset)
        if not os.path.lexists(link):
            os.symlink(os.path.join(ROOT, asset), link)
    p = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT)],
                         cwd=BUILD, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    import time
    for _ in range(40):
        try:
            import urllib.request
            urllib.request.urlopen("http://127.0.0.1:%d/logo.png" % PORT, timeout=1).read(1)
            return p
        except Exception:
            time.sleep(0.25)
    p.terminate()
    sys.exit("could not serve the build root on port %d" % PORT)


def main():
    check_only = "--check" in sys.argv
    outdir = os.path.join(BUILD, "out")
    os.makedirs(outdir, exist_ok=True)

    logo_w, logo_ink = logo_reference()
    print("brand contract: /logo.png resolves, renders %dx47, %d ink pixels\n" % (logo_w, logo_ink))

    pages = collect()
    print("collected %d indexable pages" % len(pages))
    srv = serve()
    try:
        fits = probe(pages)
        print("fitted every headline and support line in Chrome\n")

        hard = [p for p in pages if fits[p["rel"]]["headSize"] is None]
        floor = [p for p in pages if fits[p["rel"]]["headSize"] == 42]
        sup17 = [p for p in pages if fits[p["rel"]]["supSize"] == 17]
        sent = [p for p in pages if fits[p["rel"]]["supMode"] == "sentence"]
        omit = [p for p in pages if fits[p["rel"]]["supMode"] in ("omitted", "none")]
        media = [p for p in pages if p["proof"]]

        import collections
        hs = collections.Counter(fits[p["rel"]]["headSize"] for p in pages)
        ss = collections.Counter(fits[p["rel"]]["supSize"] for p in pages)
        print("  headline size   " + "  ".join(
            "%dpx:%d" % (k, v) for k, v in sorted(hs.items(), key=lambda x: -(x[0] or 0))))
        print("  support size    " + "  ".join(
            "%spx:%d" % (k, v) for k, v in sorted(ss.items(), key=lambda x: -(x[0] or 0))))
        print("  proof media %d   fallback panel %d" % (len(media), len(pages) - len(media)))
        print("  headline floor (42px) %d   hard failures %d" % (len(floor), len(hard)))
        print("  support 17px %d   first-sentence %d   omitted %d" % (len(sup17), len(sent), len(omit)))

        report = {
            "pages": len(pages),
            "headline_sizes": {str(k): v for k, v in hs.items()},
            "support_sizes": {str(k): v for k, v in ss.items()},
            "headline_floor_42px": [p["rel"] for p in floor],
            "headline_hard_failures": [p["rel"] for p in hard],
            "support_17px": [p["rel"] for p in sup17],
            "support_first_sentence": [p["rel"] for p in sent],
            "support_omitted": [p["rel"] for p in omit],
            "proof_media": [{"rel": p["rel"], "src": p["proof"], "fit": p["fit"]} for p in media],
            "fallback_panel": len(pages) - len(media),
        }
        json.dump(report, open(os.path.join(BUILD, "qa_report.json"), "w"), indent=1)

        if check_only:
            print("\n--check: no PNGs written")
            return 0

        print("\nrendering %d cards" % (len(pages) - len(hard)))
        done = render_all(pages, fits, outdir)
        missing = [n for n, ok in done if not ok]

        bad = []
        for p in pages:
            png = os.path.join(outdir, (p["slug"] or "index") + ".png")
            if not os.path.exists(png):
                continue
            ok, ink = verify_logo(png, logo_w, logo_ink)
            if not ok:
                bad.append((p["rel"], ink))
                os.remove(png)

        print("\n  rendered %d   failed to write %d" % (len(done) - len(missing), len(missing)))
        print("  canonical logo verified in %d PNGs   removed %d without it"
              % (len(done) - len(missing) - len(bad), len(bad)))
        for rel, ink in bad[:10]:
            print("     BRAND CONTRACT FAILED  %s  (%d ink px)" % (rel, ink))

        n, size = contact_sheet(pages, outdir, os.path.join(BUILD, "contact-sheet.png"))
        print("  contact sheet: %d cards, %dx%d" % (n, size[0], size[1]))
        return 1 if (hard or bad or missing) else 0
    finally:
        srv.terminate()


if __name__ == "__main__":
    sys.exit(main())
