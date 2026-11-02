#!/usr/bin/env python3
"""Draw the DiskGOup application icon.

The icon is a donut chart — "where did the disk space go" — on the app's own
dark squircle, drawn from code so it can be regenerated at any size:

    python3 electron/scripts/make-icon.py

Needs Pillow. Writes:

    electron/build/icon.png    1024x1024  macOS + Linux source
    electron/build/icon.ico    multi-size Windows icon
    electron/build/icon.icns   macOS bundle icon (via iconutil)
    electron/assets/icon.png   512x512   runtime window icon
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
ASSETS = os.path.join(ROOT, "assets")

# The app's own palette (see ui/src/styles.css).
BG_TOP = (22, 27, 34)  # #161b22
BG_BOTTOM = (13, 17, 23)  # #0d1117
SEGMENTS = [
    (55, (88, 166, 255)),  # #58a6ff
    (28, (90, 193, 142)),  # #5ac18e
    (17, (245, 166, 35)),  # #f5a623
]


def squircle_mask(size: int) -> Image.Image:
    """The macOS superellipse — the shape of every modern macOS app icon."""
    try:
        import numpy as np
    except ImportError:  # numpy is optional — fall back to a rounded square
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, size - 1, size - 1], radius=round(size * 0.2237), fill=255
        )
        return mask

    y, x = np.mgrid[0:size, 0:size]
    center = (size - 1) / 2.0
    a = np.abs(x - center) / center
    b = np.abs(y - center) / center
    inside = (a**5 + b**5) <= 1.0
    return Image.fromarray((inside * 255).astype("uint8"), "L")


def render(size: int) -> Image.Image:
    """Draw the icon at `size` pixels, supersampled so the curves are clean."""
    ss = 2
    canvas = size * ss
    center = canvas / 2.0

    # The background is a vertical gradient inside the squircle.
    gradient = Image.new("RGBA", (1, canvas))
    for y in range(canvas):
        t = y / (canvas - 1)
        gradient.putpixel(
            (0, y),
            (*(round(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)), 255),
        )
    gradient = gradient.resize((canvas, canvas))

    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    image.paste(gradient, (0, 0), squircle_mask(canvas))

    # The donut itself: three segments with a small gap between them.
    donut = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(donut)
    outer = canvas * 0.355
    gap = 2.5
    start = -90.0
    for share, color in SEGMENTS:
        sweep = 360.0 * share / 100.0
        draw.pieslice(
            [center - outer, center - outer, center + outer, center + outer],
            start + gap,
            start + sweep - gap,
            fill=(*color, 255),
        )
        start += sweep

    # The hole in the middle — drawn transparent, so the gradient shows through.
    inner = outer * 0.52
    draw.ellipse(
        [center - inner, center - inner, center + inner, center + inner],
        fill=(0, 0, 0, 0),
    )

    image = Image.alpha_composite(image, donut)
    return image.resize((size, size), Image.LANCZOS)


def write_icns(master: Image.Image) -> bool:
    """Pack the icon into an .icns bundle. macOS only — iconutil does the work."""
    iconutil = shutil.which("iconutil")
    if not iconutil:
        print("! iconutil not found — skipping icon.icns (macOS only)")
        return False

    iconset = os.path.join(BUILD, "icon.iconset")
    shutil.rmtree(iconset, ignore_errors=True)
    os.makedirs(iconset)
    for name, px in [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512),
        ("icon_512x512@2x.png", 1024),
    ]:
        render(px).save(os.path.join(iconset, name))
    shutil.copyfile(
        os.path.join(iconset, "icon_512x512@2x.png"),
        os.path.join(iconset, "icon_512x512.png"),
    )

    subprocess.run(
        [iconutil, "-c", "icns", iconset, "-o", os.path.join(BUILD, "icon.icns")],
        check=True,
    )
    shutil.rmtree(iconset, ignore_errors=True)
    return True


def main() -> int:
    os.makedirs(BUILD, exist_ok=True)
    os.makedirs(ASSETS, exist_ok=True)

    master = render(1024)
    master.save(os.path.join(BUILD, "icon.png"))
    print("✓ build/icon.png (1024x1024)")

    master.save(
        os.path.join(BUILD, "icon.ico"),
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print("✓ build/icon.ico")

    render(512).save(os.path.join(ASSETS, "icon.png"))
    print("✓ assets/icon.png (512x512)")

    write_icns(master)
    return 0


if __name__ == "__main__":
    sys.exit(main())
