#!/usr/bin/env python3
"""
Prove the instruments still render, and that their data still has the shape the
pages expect.

WHY THIS EXISTS. On 16 August 2026 Thomas reported /research/model-adoption/live
showing "The instrument data could not be loaded." It did not reproduce, and the
reason it could not be diagnosed is the reason it must not happen again: every
render function ran inside one .then() behind a single .catch(), so ANY fault -
a schema change, a null, a typo in one section - blanked the whole instrument
and blamed the data. Nothing was logged. The only way we would ever learn about
it was somebody looking at the page.

Two checks, because they catch different things:

  --schema   pure Python, no browser. Asserts the dataset still carries every
             field the page reads. This is what catches OpenRouter changing
             shape under us, which is the failure most likely to happen while
             nobody is watching. Always runs, including in the Vercel build.

  (default)  also loads each page in headless Chrome and asserts the instrument
             actually drew: no fault attribute, error box hidden, real rows on
             the page. Skipped automatically where Chrome is unavailable.

No analytics, no third-party error service - Analytics stays off until consent
is designed, and that rule does not get bent for our own convenience. The page
announces faults on <html data-instrument-fault>, and this reads it.

    python3 research/instrument_health.py --schema
    python3 research/instrument_health.py
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
PORT = int(os.environ.get("HEALTH_PORT", "8791"))

# Field -> why the page needs it. Written as a contract so a failure says what
# broke rather than "KeyError".
CONTRACT = {
    "research/model-adoption-data.json": {
        "page": "research/model-adoption/live.html",
        # y3-share replaced sb-row in the v2 redesign, 1 Sep 2026. The
        # threshold and the property are unchanged - four regions must
        # actually draw - only the class the rail renders with moved.
        "min_rendered": {"y3-share": 4, "node": 3},
        "fields": {
            "share": "the regional share rail and the map nodes",
            "leaderboard": "the ranked model table",
            "regions": "the filter pills",
            "region_colors": "the region colour tokens",
            "as_of": "the data date shown in the live bar",
            "window": "the seven-day measurement window",
            "source": "the attribution line",
            "update_policy": "the cadence copy and the freshness gate",
        },
        "rows": {
            "share": ["region", "pct", "delta_pp", "models"],
            "leaderboard": ["name"],
        },
    },
}


def fail(msgs, m):
    msgs.append(m)


def check_schema():
    msgs = []
    for path, spec in CONTRACT.items():
        full = os.path.join(ROOT, path)
        if not os.path.exists(full):
            fail(msgs, f"{path}: missing entirely")
            continue
        try:
            data = json.load(open(full, encoding="utf-8"))
        except Exception as e:
            fail(msgs, f"{path}: is not valid JSON ({e})")
            continue
        for field, why in spec["fields"].items():
            if field not in data:
                fail(msgs, f"{path}: no '{field}' - the page needs it for {why}")
        for field, keys in spec.get("rows", {}).items():
            rows = data.get(field)
            if not isinstance(rows, list) or not rows:
                fail(msgs, f"{path}: '{field}' is empty or not a list")
                continue
            for key in keys:
                if key not in rows[0]:
                    fail(msgs, f"{path}: '{field}' rows lost '{key}' - upstream "
                               f"shape changed, the page will render blanks")
    return msgs


def chrome_available():
    return bool(CHROME) and os.path.exists(CHROME)


def check_render():
    """Load each instrument page and assert it actually drew something."""
    msgs = []
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT)],
                           cwd=ROOT, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.2)
        for path, spec in CONTRACT.items():
            page = spec["page"]
            url = f"http://127.0.0.1:{PORT}/{page}"
            r = subprocess.run(
                [CHROME, "--headless=new", "--disable-gpu",
                 "--virtual-time-budget=15000", "--dump-dom", url],
                capture_output=True, text=True, timeout=180)
            dom = r.stdout or ""
            if not dom:
                fail(msgs, f"{page}: headless Chrome returned nothing")
                continue
            m = re.search(r'data-instrument-fault="([^"]+)"', dom)
            if m:
                d = re.search(r'data-instrument-fault-detail="([^"]*)"', dom)
                fail(msgs, f"{page}: reported a {m.group(1)} fault - "
                           f"{d.group(1) if d else 'no detail'}")
            if re.search(r'id="err"[^>]*style="[^"]*display:\s*block', dom):
                fail(msgs, f"{page}: the error box is visible to readers")
            for marker, least in spec["min_rendered"].items():
                got = len(re.findall(r'class="[^"]*\b%s\b' % re.escape(marker), dom))
                if got < least:
                    fail(msgs, f"{page}: only {got} '{marker}' elements rendered, "
                               f"expected at least {least} - the instrument is "
                               f"loading but not drawing")
    finally:
        srv.terminate()
    return msgs


def main():
    schema_only = "--schema" in sys.argv
    msgs = check_schema()
    if not schema_only:
        if chrome_available():
            msgs += check_render()
        else:
            print("  ..  Chrome unavailable, render check skipped")

    if msgs:
        print("\nINSTRUMENT HEALTH FAILED\n")
        for m in msgs:
            print(f"  {m}")
        return 1
    print("  ok  instrument data matches the contract the pages read"
          + ("" if schema_only else ", and the pages render"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
