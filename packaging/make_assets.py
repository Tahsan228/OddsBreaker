"""Generate the icon and installer artwork from the app's own pixel art.

    python packaging/make_assets.py [OUTDIR]

Writes icon.ico, icon-256.png, logo.png, banner.png, header.bmp (150x57)
and wizard.bmp (164x314). Everything is drawn in code, so it always matches the app.
"""

import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from oddsbreaker import __version__  # noqa: E402
from oddsbreaker.art import LOGO_H, LOGO_W, app_icon, icon_set, logo_bitmap, star_bitmap  # noqa: E402
from oddsbreaker.imaging import Bitmap, make_ico  # noqa: E402
from oddsbreaker.pixel import FONT, PAL, TINY, draw_text, hexc  # noqa: E402


def write_bmp(bmp, path, bg=(255, 255, 255)):
    """24-bit Windows BMP (what NSIS wants). Transparent pixels become bg."""
    w, h = bmp.w, bmp.h
    row_pad = (4 - (w * 3) % 4) % 4
    rows = []
    for y in range(h - 1, -1, -1):
        row = bytearray()
        for x in range(w):
            r, g, b, a = bmp.get(x, y)
            if a < 128:
                r, g, b = bg
            row += bytes((b, g, r))
        row += b"\x00" * row_pad
        rows.append(bytes(row))
    pixels = b"".join(rows)
    header = struct.pack("<2sIHHI", b"BM", 54 + len(pixels), 0, 0, 54)
    info = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(pixels), 2835, 2835, 0, 0)
    with open(path, "wb") as f:
        f.write(header + info + pixels)


def scaled_into(dst, src, x, y, k):
    dst.blit(src.scaled(k) if k > 1 else src, x, y)


def wizard_art():
    """164x314 picture for the installer's welcome and finish pages."""
    P = PAL
    b = Bitmap(164, 314)
    b.vgrad(0, 0, 164, 314, [hexc("#FF6E7E"), hexc("#E3263F"), hexc("#C41A33"), hexc("#7A0E1F")])
    for y in range(0, 314, 4):
        b.dither_level(0, y, 164, 1, hexc("#93122A"), 3)
    icon = app_icon(32)
    scaled_into(b, icon, (164 - 96) // 2, 46, 3)
    logo = logo_bitmap()
    scaled_into(b, logo, (164 - logo.w) // 2, 160, 1)
    ver = "VERSION %s" % __version__
    draw_text(b, (164 - TINY.width(ver)) // 2, 194, ver, P["gold_hi"], TINY)
    by = "MADE BY TAHSAN"
    draw_text(b, (164 - TINY.width(by)) // 2, 290, by, P["white"], TINY)
    for (x, y, s) in ((26, 30, 3), (136, 64, 2), (30, 128, 2), (128, 136, 3), (82, 230, 1), (24, 250, 2),
                      (140, 240, 1)):
        b.blit(star_bitmap(s, P["gold_hi"], P["white"]), x, y)
    return b


def header_art():
    """150x57 banner shown at the top of the other installer pages."""
    P = PAL
    b = Bitmap(150, 57, P["white"])
    b.rect(0, 54, 150, 3, hexc("#E3263F"))
    icon = app_icon(32)
    scaled_into(b, icon, 112, 12, 1)
    draw_text(b, 8, 16, "ODDS", hexc("#E3263F"), FONT, 2)
    draw_text(b, 58, 23, "BREAKER", hexc("#2A0A12"), FONT, 1)
    draw_text(b, 8, 36, "SHINY HUNTER", hexc("#7D93A9"), TINY)
    return b


def banner_art():
    """Icon and logo side by side, for the top of the README."""
    icon = app_icon(32).scaled(3)
    logo = logo_bitmap().scaled(3)
    gap = 16
    b = Bitmap(icon.w + gap + logo.w + 4, max(icon.h, logo.h) + 4)
    b.blit(icon, 2, (b.h - icon.h) // 2)
    b.blit(logo, 2 + icon.w + gap, (b.h - logo.h) // 2 + 3)
    return b


def main(out):
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "icon.ico"), "wb") as f:
        f.write(make_ico(icon_set()))
    with open(os.path.join(out, "icon-256.png"), "wb") as f:
        f.write(app_icon(32).scaled(8).to_png())
    logo = Bitmap(LOGO_W + 4, LOGO_H + 4)
    logo.blit(logo_bitmap(), 2, 2)
    with open(os.path.join(out, "logo.png"), "wb") as f:
        f.write(logo.scaled(4).to_png())
    with open(os.path.join(out, "banner.png"), "wb") as f:
        f.write(banner_art().to_png())
    write_bmp(wizard_art(), os.path.join(out, "wizard.bmp"))
    write_bmp(header_art(), os.path.join(out, "header.bmp"))
    print("assets written to", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "assets"))
