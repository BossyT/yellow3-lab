#!/usr/bin/env python3
"""
Responsive WebP derivatives for the homepage proof screenshots.

WHY. The two real product screenshots on the homepage are 522KB and 1,215KB of
PNG, served at every viewport - the site audit has flagged the pair for a while.
They are the page's evidence, so they cannot be dropped or degraded; they can be
delivered at the size the layout actually uses.

WHAT THIS DOES NOT DO. It does not touch the originals. The PNGs stay canonical
on disk and stay the <img src>, so anything that cannot negotiate WebP still
gets the real screenshot. The DPP image is cropped in CSS for presentation, and
these derivatives are deliberately NOT pre-cropped: baking the crop into the
files would make it permanent, and "presentation only" was the ruling.

Widths are the ones GPT specified. Measured layout widths on the live page are
677 and 655 CSS px at desktop and full-bleed below 800, so 1365 covers a 2x
display at desktop and 420 covers a 1x phone.

    python3 research/gen_webp.py            # write any missing/stale derivative
    python3 research/gen_webp.py --check    # fail if one is missing or stale
"""

import os
import sys

try:
    from PIL import Image
except ImportError:
    raise SystemExit("Pillow is needed: python3 -m pip install Pillow")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
IMG = os.path.join(ROOT, "img", "homepage")

WIDTHS = (420, 720, 1024, 1365)
QUALITY = 85          # screenshots carry small text; below ~80 it starts to fur
METHOD = 6            # slowest encode, smallest file - these are built once

SOURCES = ("dpp-buyer-platform-stage4.png", "model-adoption-interface.png")


def derivative(name, width):
    return os.path.join(IMG, "%s-%d.webp" % (os.path.splitext(name)[0], width))


def build(check_only):
    stale, made, total_png, total_webp = [], [], 0, 0
    for name in SOURCES:
        src = os.path.join(IMG, name)
        if not os.path.exists(src):
            raise SystemExit("missing source: %s" % name)
        total_png += os.path.getsize(src)
        with Image.open(src) as im:
            im = im.convert("RGB")
            for width in WIDTHS:
                out = derivative(name, width)
                fresh = (os.path.exists(out)
                         and os.path.getmtime(out) >= os.path.getmtime(src))
                if fresh:
                    total_webp += os.path.getsize(out)
                    continue
                if check_only:
                    stale.append(os.path.relpath(out, ROOT))
                    continue
                height = round(im.height * width / im.width)
                im.resize((width, height), Image.LANCZOS).save(
                    out, "WEBP", quality=QUALITY, method=METHOD)
                total_webp += os.path.getsize(out)
                made.append((os.path.relpath(out, ROOT), os.path.getsize(out)))

    if check_only:
        if stale:
            print("%d derivative(s) missing or older than their source:" % len(stale))
            for s in stale:
                print("   " + s)
            print("\nRun: python3 research/gen_webp.py")
            return 1
        print("webp: %d derivatives, all current" % (len(SOURCES) * len(WIDTHS)))
        return 0

    for path, size in made:
        print("  %-52s %6.1f KB" % (path, size / 1024))
    print("\n  %d source PNG, %.0f KB, untouched and still canonical"
          % (len(SOURCES), total_png / 1024))
    print("  %d derivatives, %.0f KB total"
          % (len(SOURCES) * len(WIDTHS), total_webp / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(build("--check" in sys.argv))
