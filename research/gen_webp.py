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
IMG = os.path.join(ROOT, "img")

QUALITY = 85          # screenshots carry small text; below ~80 it starts to fur
METHOD = 6            # slowest encode, smallest file - these are built once

# Per-asset ladders, from measured render widths rather than round numbers.
#
#   homepage proofs   677 and 655 css px at desktop, full-bleed below 800
#   naffe marks       hero 334 desktop / 300 mobile, human logo a fixed 240
#
# The naffe marks are official brand assets: the PNGs are canonical, are never
# altered or overwritten, and stay the <img src> fallback. These are delivery
# derivatives only - no recreation, no tracing, no recolour, no effects.
SOURCES = {
    "homepage/dpp-buyer-platform-stage4.png": (420, 720, 1024, 1365),
    "homepage/model-adoption-interface.png": (420, 720, 1024, 1365),
    "software/naffe-logo-black.png": (240, 340, 480, 720, 1024),
    "software/naffe-logo-white.png": (240, 340, 480, 720, 1024),
}


def derivative(name, width):
    return os.path.join(IMG, "%s-%d.webp" % (os.path.splitext(name)[0], width))


def build(check_only):
    stale, made, total_png, total_webp = [], [], 0, 0
    count = sum(len(w) for w in SOURCES.values())
    for name, widths in SOURCES.items():
        src = os.path.join(IMG, name)
        if not os.path.exists(src):
            raise SystemExit("missing source: %s" % name)
        total_png += os.path.getsize(src)
        with Image.open(src) as im:
            # Preserve transparency where there is any. Today all four
            # sources are RGB, so this is a no-op - but a blanket
            # convert("RGB") would silently put a box behind the first
            # asset that arrives with an alpha channel, and a white mark
            # on a dark section is exactly where that would show.
            im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
            for width in widths:
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
        print("webp: %d derivatives, all current" % count)
        return 0

    for path, size in made:
        print("  %-52s %6.1f KB" % (path, size / 1024))
    print("\n  %d source PNG, %.0f KB, untouched and still canonical"
          % (len(SOURCES), total_png / 1024))
    print("  %d derivatives, %.0f KB total" % (count, total_webp / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(build("--check" in sys.argv))
