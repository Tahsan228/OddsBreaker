import io
import os
import struct

import pytest

from oddsbreaker.art import icon_set
from oddsbreaker.imaging import (Bitmap, Frame, crop_frames, gif_decode, make_ico, png_decode,
                                 png_rgb)
from oddsbreaker.pixel import FONT, PAL, TINY, draw_text, ellipsize, wrap_text

PIL = pytest.importorskip("PIL.Image")


def pil_png(mode, size, fill, extra=None):
    img = PIL.new(mode, size, fill)
    if mode == "P":
        img.putpalette([0, 0, 0, 255, 255, 255, 200, 30, 30, 30, 200, 90] + [0] * 756)
    if extra:
        extra(img)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue(), img


@pytest.mark.parametrize("mode", ["RGBA", "RGB", "P", "L", "LA"])
def test_png_decode_matches_pillow(mode):
    def paint(img):
        for x in range(0, 17, 2):
            img.putpixel((x, x % 9), 3 if mode in ("P", "L") else ((x * 13) % 256,) * len(mode))
    data, img = pil_png(mode, (17, 9), 0 if mode in ("P", "L") else (10,) * len(mode), paint)
    w, h, rgba = png_decode(data)
    assert (w, h) == img.size
    assert bytes(rgba) == img.convert("RGBA").tobytes()


def test_png_encode_round_trip():
    f = Frame(3, 2, bytes([1, 2, 3, 255, 4, 5, 6, 255, 7, 8, 9, 255] * 2))
    rgb, w, h = f.rgb()
    data = png_rgb(w, h, rgb)
    img = PIL.open(io.BytesIO(data))
    assert img.size == (3, 2) and img.getpixel((0, 0)) == (3, 2, 1)


def test_gif_decode_matches_pillow(tmp_path):
    frames = []
    for i in range(4):
        im = PIL.new("P", (20, 16), 0)
        im.putpalette([0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255] + [0] * 756)
        for x in range(i * 3, i * 3 + 6):
            for y in range(4, 10):
                im.putpixel((x, y), 1 + i % 3)
        frames.append(im)
    path = os.path.join(str(tmp_path), "a.gif")
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=80, loop=0,
                   transparency=0, disposal=2)
    w, h, out = gif_decode(open(path, "rb").read())
    ref = PIL.open(path)
    assert (w, h) == ref.size and len(out) == ref.n_frames
    ref.seek(2)
    assert bytes(out[2][0].buf) == ref.convert("RGBA").tobytes()
    cropped = crop_frames(out)
    assert len(set((b.w, b.h) for b, _d in cropped)) == 1 and cropped[0][0].w < w


def test_bitmap_helpers():
    b = Bitmap(20, 10)
    b.rect(-5, -5, 10, 10, PAL["red"])
    assert b.get(4, 4) == PAL["red"] and b.get(5, 5) == b"\x00\x00\x00\x00"
    r = Bitmap(20, 10)
    r.rrect(0, 0, 20, 10, 4, PAL["blue"])
    assert r.alpha(0, 0) == 0 and r.get(10, 5) == PAL["blue"]
    s = b.scaled(3)
    assert (s.w, s.h) == (60, 30) and s.get(31, 16) == b.get(10, 5)
    o = Bitmap(4, 4)
    o.px(1, 1, PAL["white"])
    ol = o.outlined(PAL["black"])
    assert ol.get(2, 1) == PAL["black"] and ol.get(2, 2) == PAL["white"]


def test_fonts():
    b = Bitmap(40, 10)
    w = draw_text(b, 0, 0, "Hi!", PAL["ink"])
    assert w == FONT.width("Hi!")
    assert FONT.width("0") == FONT.width("1")
    assert all(ch in FONT.glyphs for ch in "★▶◀▲▼✓×·●…")
    assert all(ch in TINY.glyphs for ch in "★▶◀▲▼✓×·●")
    assert ellipsize("A very long sentence here", 40).endswith("…")
    assert len(wrap_text("one two three four five six seven", 50)) > 1


def test_ico():
    data = make_ico(icon_set())
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind, count) == (0, 1, 6)
    img = PIL.open(io.BytesIO(data))
    assert img.format == "ICO"
