"""All the artwork, drawn in code (1 art pixel = S screen pixels)."""

import math

from .imaging import BAYER4, Bitmap
from .pixel import FONT, PAL, TINY, draw_text, draw_text_grad, hexc, mix

# ---------------------------------------------------------------------------
# Layout of the device (art pixels)
# ---------------------------------------------------------------------------
LEFT_W, PANEL_W, DEX_H = 192, 220, 352
HINGE_X = 176
LENS_C, LENS_R = (31, 30), 23
LEDS = (("r", 68, 12), ("y", 82, 12), ("g", 96, 12))
BEZEL = (10, 62, 162, 152)          # x, y, w, h of the white screen bezel
SCREEN = (21, 74, 140, 112)          # the main screen
LCD_BOX = (10, 220, 162, 58)
LCD_IN = (14, 224, 154, 50)
START_C, START_R = (31, 305), 17
DPAD_XY = (138, 288)
STATUS = (10, 332, 162, 12)

# right half
PSCREEN = (12, 52, 196, 196)         # the setup screen
CONTENT = (20, 74, 180, 172)          # where page widgets go (x, y, w, h)
KEYS_Y = (258, 277)
MINIS = ((10, 304, 98, 28), (112, 304, 98, 28))

# mini mode
MINI_W, MINI_H = 184, 64


def bevel_box(b, x, y, w, h, r, outline, hi, face, sh):
    """Outlined box with a 1px light top-left and dark bottom-right edge."""
    b.rrect(x, y, w, h, r, outline)
    b.rrect(x + 1, y + 1, w - 2, h - 2, max(0, r - 1), sh)
    b.rrect(x + 1, y + 1, w - 3, h - 3, max(0, r - 1), hi)
    b.rrect(x + 2, y + 2, w - 4, h - 4, max(0, r - 2), face)


def sunken_box(b, x, y, w, h, r, outline, face, edge_dark, edge_light):
    b.rrect(x, y, w, h, r, outline)
    b.rrect(x + 1, y + 1, w - 2, h - 2, max(0, r - 1), edge_light)
    b.rrect(x + 1, y + 1, w - 3, h - 3, max(0, r - 1), edge_dark)
    b.rrect(x + 2, y + 2, w - 4, h - 4, max(0, r - 2), face)


def screw(b, x, y):
    P = PAL
    b.circle(x, y, 2, P["red_xd"])
    b.px(x - 1, y - 1, P["red_dk"])
    b.rect(x - 1, y, 3, 1, P["red_md"])
    b.px(x, y - 1, P["red_hi"])


def cylinder(b, x, y, w, h):
    """A shaded hinge knuckle."""
    P = PAL
    cols = [P["red_xd"], P["red_dk"], P["red_md"], P["red"], P["red_hi"], P["red_hi"],
            P["red"], P["red"], P["red_md"], P["red_dk"], P["red_dk"], P["red_xd"]]
    b.rrect(x, y, w, h, 3, P["outline"])
    for i in range(1, w - 1):
        c = cols[min(len(cols) - 1, int((i - 1) * len(cols) / float(max(1, w - 2))))]
        b.rect(x + i, y + 2, 1, h - 4, c)
    b.rect(x + 2, y + 1, w - 4, 1, P["red_dk"])
    b.rect(x + 2, y + h - 2, w - 4, 1, P["red_xd"])
    for k in range(y + 6, y + h - 6, 6):
        b.rect(x + 2, k, w - 4, 1, P["red_dk"])


def shell_body(b, x, y, w, h, r):
    """The red plastic with soft edge shading."""
    P = PAL
    bevel_box(b, x, y, w, h, r, P["outline"], P["red_hi"], P["red"], P["red_dk"])
    # lighter band on the left, darker on the right and bottom (dithered)
    b.dither_level(x + 3, y + r, 3, h - 2 * r, P["red_hi"], 6)
    b.dither_level(x + w - 7, y + r, 4, h - 2 * r, P["red_md"], 10)
    b.dither_level(x + r, y + h - 8, w - 2 * r, 5, P["red_md"], 8)


# ---------------------------------------------------------------------------
# Left half
# ---------------------------------------------------------------------------
def draw_left_shell():
    P = PAL
    b = Bitmap(LEFT_W, DEX_H)
    shell_body(b, 0, 0, LEFT_W, DEX_H, 12)
    # top cap
    b.rect(3, 3, HINGE_X - 6, 1, P["red_hi"])
    b.dither_level(4, 4, HINGE_X - 8, 2, P["red_hi"], 6)
    b.rect(3, 57, HINGE_X - 3, 1, P["outline"])
    b.rect(3, 58, HINGE_X - 3, 1, P["red_xd"])
    b.rect(3, 59, HINGE_X - 3, 1, P["red_hi"])
    # hinge
    hx = HINGE_X
    b.rect(hx, 57, 1, DEX_H - 66, P["outline"])
    b.rect(hx + 1, 57, LEFT_W - hx - 3, DEX_H - 66, P["red_dk"])
    for y0, hh in ((66, 64), (148, 86), (252, 82)):
        cylinder(b, hx + 1, y0, LEFT_W - hx - 3, hh)
    # big lens: white ring and dark socket (the glass is its own widget)
    cx, cy = LENS_C
    R = LENS_R
    b.circle(cx + 1, cy + 2, R, P["red_xd"])
    b.circle(cx, cy, R, P["outline"])
    b.circle(cx, cy, R - 1, P["bezel_sh"])
    b.circle(cx - 1, cy - 1, R - 2, P["white"])
    b.circle(cx, cy, R - 5, P["bezel_xd"])
    b.circle(cx, cy, R - 6, P["outline"])
    # LED sockets
    for _k, x, y in LEDS:
        b.circle(x, y + 1, 6, P["red_xd"])
        b.circle(x, y, 6, P["outline"])
    # screws in the cap
    screw(b, 167, 50)
    screw(b, 62, 50)

    # screen bezel with the cut corner
    x, y, w, h = BEZEL
    cut = 18
    pts = [(x, y), (x + w, y), (x + w, y + h), (x + cut, y + h), (x, y + h - cut)]
    b.poly([(px + 1, py + 2) for px, py in pts], P["red_xd"])
    b.poly(pts, P["outline"])
    b.poly([(x + 1, y + 1), (x + w - 1, y + 1), (x + w - 1, y + h - 1), (x + cut, y + h - 1),
            (x + 1, y + h - cut)], P["bezel_sh"])
    b.poly([(x + 1, y + 1), (x + w - 2, y + 1), (x + w - 2, y + h - 2), (x + cut, y + h - 2),
            (x + 1, y + h - cut - 1)], P["bezel_hi"])
    b.poly([(x + 2, y + 2), (x + w - 2, y + 2), (x + w - 2, y + h - 2), (x + cut + 1, y + h - 2),
            (x + 2, y + h - cut)], P["bezel"])
    # glossy diagonal on the bezel
    for i in range(6):
        b.line(x + 120 + i, y + 2, x + 108 + i, y + 9, P["bezel_hi"])
    for dx in (82, 100):
        b.circle(dx, y + 6, 2, P["outline"])
        b.px(dx, y + 6, P["red"])
        b.px(dx - 1, y + 5, P["red_hi"])
    # the screen well
    sx, sy, sw, sh = SCREEN
    b.rect(sx - 2, sy - 2, sw + 4, sh + 4, P["bezel_sh"])
    b.rect(sx - 1, sy - 1, sw + 2, sh + 2, P["scr_frame"])
    b.rect(sx, sy, sw, sh, P["scr"])
    # view button socket, model text and speaker
    b.circle(31, 200, 7, P["bezel_sh"])
    draw_text(b, 50, 197, "MODEL OB-1", P["bezel_sh"], TINY)
    for i in range(4):
        b.rrect(128, 193 + i * 4, 34, 2, 1, P["dgray"])
        b.rect(129, 195 + i * 4, 32, 1, P["bezel_hi"])

    # LCD
    lx, ly, lw, lh = LCD_BOX
    sunken_box(b, lx, ly, lw, lh, 4, P["outline"], P["lcd"], P["lcd4"], P["red_hi"])
    ix, iy, iw, ih = LCD_IN
    b.rect(ix - 2, iy - 2, iw + 4, ih + 4, P["lcd4"])
    b.rect(ix - 1, iy - 1, iw + 2, ih + 2, P["lcd3"])
    b.rect(ix, iy, iw, ih, P["lcd"])
    # START socket, D-pad socket
    scx, scy = START_C
    b.circle(scx + 1, scy + 2, START_R + 1, P["red_xd"])
    b.circle(scx, scy, START_R + 1, P["outline"])
    dx, dy = DPAD_XY
    b.rrect(dx - 1, dy + 11, 36, 14, 3, P["red_xd"])
    b.rrect(dx + 10, dy - 1, 14, 37, 3, P["red_xd"])
    # status strip
    x, y, w, h = STATUS
    sunken_box(b, x, y, w, h, 3, P["outline"], P["status_bg"], hexc("#050A07"), P["red_hi"])
    b.rect(x + 2, y + 2, w - 4, h - 4, P["status_bg"])
    return b


# ---------------------------------------------------------------------------
# Right half
# ---------------------------------------------------------------------------
def draw_right_shell():
    P = PAL
    b = Bitmap(PANEL_W, DEX_H)
    shell_body(b, -14, 40, PANEL_W + 14, DEX_H - 40, 12)
    b.rect(0, 41, 1, DEX_H - 42, P["outline"])
    b.rect(1, 41, 2, DEX_H - 43, P["red_xd"])
    b.rect(3, 41, 1, DEX_H - 43, P["red_dk"])
    # setup screen
    x, y, w, h = PSCREEN
    b.rrect(x - 4, y - 4, w + 8, h + 8, 6, P["outline"])
    b.rrect(x - 3, y - 3, w + 6, h + 6, 5, P["black_md"])
    b.rect(x - 1, y - 3, w + 2, 1, P["black_hi"])
    b.rect(x - 1, y - 1, w + 2, h + 2, P["night"])
    b.rect(x, y, w, h, P["dark"])
    for gy in range(y + 4, y + h, 8):
        for gx in range(x + 4, x + w, 8):
            b.px(gx, gy, P["dark2"])
    br = P["cyan_dk"]
    for (cx, cy, sx, sy) in ((x + 2, y + 2, 1, 1), (x + w - 3, y + 2, -1, 1),
                             (x + 2, y + h - 3, 1, -1), (x + w - 3, y + h - 3, -1, -1)):
        b.rect(min(cx, cx + sx * 4), cy, 5, 1, br)
        b.rect(cx, min(cy, cy + sy * 4), 1, 5, br)
    # recess behind the ten keys
    b.rrect(6, 255, 208, 42, 5, P["red_xd"])
    b.rrect(7, 256, 206, 40, 4, P["red_dk"])
    b.rect(10, 295, 200, 1, P["red_md"])
    # two mini screens
    for (mx, my, mw, mh) in MINIS:
        b.rrect(mx, my, mw, mh, 4, P["outline"])
        b.rrect(mx + 1, my + 1, mw - 2, mh - 2, 3, P["black_md"])
        b.rect(mx + 2, my + 2, mw - 4, mh - 4, P["night"])
        b.rect(mx + 3, my + 3, mw - 6, mh - 6, P["dark"])
    # details: two pills, a light and screws
    for px_ in (14, 38):
        b.rrect(px_, 339, 20, 7, 3, P["outline"])
        b.rrect(px_ + 1, 340, 18, 5, 2, P["bezel"])
        b.rect(px_ + 3, 340, 14, 1, P["white"])
    b.circle(204, 342, 3, P["outline"])
    b.circle(204, 342, 2, P["led_y"])
    b.px(203, 341, P["white"])
    screw(b, 186, 342)
    return b


# ---------------------------------------------------------------------------
# Mini mode
# ---------------------------------------------------------------------------
MINI_SCREEN = (8, 8, 48, 48)
MINI_LCD = (62, 8, 84, 34)


def draw_mini_shell():
    P = PAL
    b = Bitmap(MINI_W, MINI_H)
    shell_body(b, 0, 0, MINI_W, MINI_H, 10)
    x, y, w, h = MINI_SCREEN
    b.rrect(x - 3, y - 3, w + 6, h + 6, 4, P["outline"])
    b.rrect(x - 2, y - 2, w + 4, h + 4, 3, P["bezel"])
    b.rect(x - 1, y - 1, w + 2, h + 2, P["scr_frame"])
    b.rect(x, y, w, h, P["scr"])
    x, y, w, h = MINI_LCD
    sunken_box(b, x - 3, y - 3, w + 6, h + 6, 3, P["outline"], P["lcd"], P["lcd4"], P["red_hi"])
    b.rect(x - 1, y - 1, w + 2, h + 2, P["lcd3"])
    b.rect(x, y, w, h, P["lcd"])
    b.circle(167, 22, 13, P["red_xd"])
    b.circle(166, 21, 13, P["outline"])
    return b


# ---------------------------------------------------------------------------
# Small parts
# ---------------------------------------------------------------------------
def lens_glass(level, r=17):
    """Inner glass of the big lens; level 0..1 makes it glow."""
    P = PAL
    d = 2 * r + 1
    b = Bitmap(d, d)
    c = r
    b.circle(c, c, r, P["blue_xd"])
    b.circle(c, c, r - 1, mix(P["blue_dk"], P["blue"], level * 0.7))
    b.circle(c - 1, c - 1, r - 3, mix(P["blue"], P["blue_lt"], level * 0.7))
    b.circle(c - 3, c - 3, r - 9, mix(P["blue_lt"], P["blue_xl"], 0.25 + level * 0.6))
    b.dither_level(c - r + 3, c + 2, d - 6, r - 4, P["blue_dk"], 5)
    b.rect(c - 10, c - 9, 4, 2, P["white"])
    b.rect(c - 11, c - 7, 2, 3, P["white"])
    b.px(c - 6, c - 10, P["white"])
    b.rect(c + 6, c + 8, 3, 2, mix(P["blue_lt"], P["white"], 0.4))
    b.px(c + 10, c + 4, P["blue_lt"])
    return b


def lens_glint(step, steps=8, r=17):
    """A white streak sweeping across the lens (transparent elsewhere)."""
    d = 2 * r + 1
    b = Bitmap(d, d)
    if step <= 0 or step >= steps:
        return b
    pos = -r + (2.6 * r) * step / float(steps)
    rr = (r - 1.5) ** 2
    for j in range(d):
        for i in range(d):
            u = (i - r) + (j - r)
            if abs(u - pos * 1.4) <= 2.2 and (i - r) ** 2 + (j - r) ** 2 <= rr:
                b.px(i, j, PAL["white"] if abs(u - pos * 1.4) <= 1.2 else PAL["blue_xl"])
    return b


def led_bitmap(key, level):
    """level: 0 off, 1 dim, 2 on."""
    P = PAL
    on_c, off_c = P["led_" + key], P["led_%s_off" % key]
    b = Bitmap(11, 11)
    c = 5
    if level >= 2:
        b.circle(c, c, 5, mix(on_c, P["outline"], 0.35))
        b.circle(c, c, 4, on_c)
        b.circle(c - 1, c - 1, 2, mix(on_c, P["white"], 0.45))
        b.px(c - 2, c - 2, P["white"])
    elif level == 1:
        mid = mix(off_c, on_c, 0.5)
        b.circle(c, c, 5, P["outline"])
        b.circle(c, c, 4, mid)
        b.px(c - 2, c - 2, mix(mid, P["white"], 0.4))
    else:
        b.circle(c, c, 5, P["outline"])
        b.circle(c, c, 4, off_c)
        b.px(c - 2, c - 2, mix(off_c, P["white"], 0.25))
    return b


LOGO_W, LOGO_H = 98, 24


def logo_bitmap(shine=None):
    """ODDS (big, gold) BREAKER (small, white). shine = sweep x position."""
    P = PAL
    b = Bitmap(LOGO_W, LOGO_H)
    o = P["outline"]
    # drop shadow + outline for both words
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1),
                   (1, 2), (2, 2), (0, 2)):
        draw_text(b, 1 + dx, 2 + dy, "ODDS", o, FONT, 2)
        draw_text(b, 52 + dx, 9 + dy, "BREAKER", o, FONT, 1)
    draw_text_grad(b, 1, 2, "ODDS", [P["gold_hi"], P["gold"], P["gold"], P["gold_md"],
                                     P["gold_md"], P["gold_dk"]], FONT, 2)
    draw_text_grad(b, 52, 9, "BREAKER", [P["white"], P["white"], P["bezel"]], FONT, 1)
    # tiny sparkle by the logo
    sp = P["gold_hi"]
    b.rect(91, 3, 1, 5, sp)
    b.rect(89, 5, 5, 1, sp)
    b.px(91, 5, P["white"])
    if shine is not None:
        for j in range(LOGO_H):
            for i in range(LOGO_W):
                u = i + j - shine
                if 0 <= u < 7:
                    c = b.get(i, j)
                    if c[3] and c != o:
                        b.px(i, j, P["white"] if 2 <= u < 5 else P["gold_hi"])
    return b


def logo_frames(n=12):
    frames = [logo_bitmap()]
    for k in range(n):
        frames.append(logo_bitmap(-10 + (LOGO_W + 34) * k / float(n - 1)))
    return frames


def star_bitmap(size, color, core):
    """Twinkle sprite: size 0..3."""
    b = Bitmap(9, 9)
    c = 4
    if size <= 0:
        b.px(c, c, color)
    elif size == 1:
        b.rect(c - 1, c, 3, 1, color)
        b.rect(c, c - 1, 1, 3, color)
    elif size == 2:
        b.rect(c - 2, c, 5, 1, color)
        b.rect(c, c - 2, 1, 5, color)
        b.px(c, c, core)
    else:
        b.rect(c - 4, c, 9, 1, color)
        b.rect(c, c - 4, 1, 9, color)
        b.rect(c - 1, c - 1, 3, 3, color)
        b.px(c, c, core)
    return b


def battle_base(w, h=None):
    """Gen 5 style oval platform the Pokemon stands on."""
    P = PAL
    h = h or max(8, w // 5)
    b = Bitmap(w, h + 2)
    cx, cy = w // 2, h // 2
    b.ellipse(cx, cy + 1, w // 2 - 1, h // 2, P["scr_base2"])
    b.ellipse(cx, cy, w // 2 - 1, h // 2, P["scr_base"])
    b.ellipse(cx, cy - 1, w // 2 - 4, max(1, h // 2 - 2), P["scr_base3"])
    b.ellipse(cx, cy, w // 2 - 7, max(1, h // 2 - 3), P["scr_base"])
    return b


def screen_bg(w, h, kind="day"):
    """Backgrounds for the main screen."""
    P = PAL
    b = Bitmap(w, h)
    if kind == "night":
        b.vgrad(0, 0, w, h, [hexc("#10192A"), hexc("#0B1220"), hexc("#070C16")])
        for y in range(1, h, 3):
            b.rect(0, y, w, 1, hexc("#0D1626"))
    elif kind == "gold":
        b.vgrad(0, 0, w, h, [hexc("#FFF8D6"), hexc("#FFE98A"), hexc("#FFD24A")])
    else:
        b.vgrad(0, 0, w, h, [hexc("#F4FBEF"), P["scr"], P["scr2"], hexc("#CDE7C0")])
        for y in range(2, h, 3):
            b.dither_level(0, y, w, 1, P["scr_line"], 8)
    return b


def ray_frames(w, h, n=8, rays=12):
    """Rotating light rays (for the shiny celebration)."""
    P = PAL
    frames = []
    cx, cy = w / 2.0, h / 2.0
    for k in range(n):
        b = Bitmap(w, h, hexc("#FFE98A"))
        off = k / float(n) * (2 * math.pi / rays)
        for j in range(h):
            for i in range(w):
                a = math.atan2(j - cy, i - cx) - off
                seg = int((a % (2 * math.pi)) / (2 * math.pi) * rays * 2)
                if seg % 2 == 0:
                    b.px(i, j, P["gold_hi"])
        b.ellipse(int(cx), int(cy), 26, 22, hexc("#FFF8D6"))
        frames.append(b)
    return frames


def dissolve_frames(w, h, color, steps=8):
    """Overlays from solid to empty in an ordered-dither pattern."""
    out = []
    for k in range(steps):
        level = 16 - int(round(16.0 * (k + 1) / (steps + 1)))
        b = Bitmap(w, h)
        for j in range(h):
            row = BAYER4[j & 3]
            for i in range(w):
                if row[i & 3] < level:
                    b.px(i, j, color)
        out.append(b)
    return out


def placeholder_bitmap():
    """Shown when there's no sprite: a mystery egg with a question mark."""
    P = PAL
    b = Bitmap(30, 36)
    b.ellipse(15, 20, 13, 15, P["scr_ink"])
    b.ellipse(15, 20, 12, 14, hexc("#F3F7EE"))
    b.ellipse(13, 17, 8, 9, P["white"])
    b.dither_level(4, 24, 22, 10, P["scr2"], 8)
    draw_text(b, 12, 15, "?", P["scr_dim"], FONT)
    return b


def start_ring_frames(n=8, r=19):
    """A spinning ring of lights around the START button."""
    P = PAL
    d = 2 * r + 1
    out = []
    for k in range(n):
        b = Bitmap(d, d)
        for s in range(16):
            a = s / 16.0 * 2 * math.pi
            dist = (s - k * 2) % 16
            if dist < 5:
                col = P["green"] if dist == 0 else mix(P["green"], P["red_xd"], dist / 5.0)
                x = int(round(r + math.cos(a) * (r - 1)))
                y = int(round(r + math.sin(a) * (r - 1)))
                b.rect(x - 1, y - 1, 2, 2, col)
        out.append(b)
    return out


# Page icons (7x7)
ICONS = {
    "hunt": "..###..|.#...#.|#..#..#|#.###.#|#..#..#|.#...#.|..###..",
    "keys": ".......|#######|#.#.#.#|#######|#.###.#|#######|.......",
    "script": "##.####|.......|##.###.|.......|##.####|.......|##.##..",
    "area": "##...##|#.....#|.......|...#...|.......|#.....#|##...##",
    "check": ".......|..###..|.#...#.|#..#..#|.#...#.|..###..|.......",
    "dex": ".#####.|#.....#|#.###.#|#.....#|#.###.#|#.....#|.#####.",
    "stats": ".....#.|.....#.|...#.#.|...#.#.|.#.#.#.|.#.#.#.|#######",
    "log": "...#...|..###..|#######|.#####.|..###..|.##.##.|.#...#.",
    "alert": "...#...|..###..|.#####.|.#####.|.#####.|#######|...#...",
    "more": ".#.....|#######|.#.....|.....#.|#######|.....#.|.......",
    "help": ".###.|#...#|....#|...#.|..#..|.....|..#..",
}


def icon_bitmap(name, color):
    rows = ICONS.get(name, ICONS["help"]).split("|")
    b = Bitmap(max(len(r) for r in rows), len(rows))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                b.px(x, y, color)
    return b


# ---------------------------------------------------------------------------
# App icon (window + .exe)
# ---------------------------------------------------------------------------
def app_icon(size=32):
    """The OddsBreaker icon: a red device with a blue lens and a gold star."""
    P = PAL
    if size <= 16:
        b = Bitmap(16, 16)
        bevel_box(b, 0, 0, 16, 16, 3, hexc("#2A0A12"), hexc("#FF6E7E"), hexc("#E3263F"),
                  hexc("#93122A"))
        b.circle(6, 6, 4, hexc("#2A0A12"))
        b.circle(6, 6, 3, P["white"])
        b.circle(6, 6, 2, P["blue"])
        b.px(5, 5, P["white"])
        g = P["gold"]
        b.rect(11, 9, 1, 5, g)
        b.rect(9, 11, 5, 1, g)
        b.px(11, 11, P["white"])
        b.px(12, 3, hexc("#FF3B4F"))
        return b
    b = Bitmap(32, 32)
    bevel_box(b, 1, 1, 30, 30, 7, hexc("#2A0A12"), hexc("#FF6E7E"), hexc("#E3263F"), hexc("#93122A"))
    b.dither_level(4, 22, 24, 6, hexc("#C41A33"), 8)
    b.circle(12, 12, 8, hexc("#2A0A12"))
    b.circle(12, 12, 7, P["white"])
    b.circle(12, 12, 5, hexc("#0B2F66"))
    b.circle(12, 12, 4, P["blue_dk"])
    b.circle(11, 11, 3, P["blue"])
    b.rect(9, 9, 2, 2, P["white"])
    b.circle(24, 6, 2, hexc("#2A0A12"))
    b.circle(24, 6, 1, hexc("#FF3B4F"))
    # gold star sparkle bottom right
    g, gd = P["gold"], hexc("#B8860B")
    b.rect(23, 15, 1, 13, gd)
    b.rect(17, 21, 13, 1, gd)
    b.rect(22, 16, 1, 11, g)
    b.rect(18, 20, 11, 1, g)
    b.rect(21, 19, 3, 3, g)
    b.rect(20, 18, 5, 5, gd)
    b.rect(21, 19, 3, 3, g)
    b.px(22, 20, P["white"])
    b.rect(22, 17, 1, 2, P["gold_hi"])
    return b


def icon_set():
    """Bitmaps for a multi-size .ico."""
    base32 = app_icon(32)
    return [app_icon(16), base32, _fit(base32, 48), base32.scaled(2), base32.scaled(4),
            base32.scaled(8)]


def _fit(b32, size):
    """48px icon: 32px art scaled 1.5x by pixel doubling every other pixel."""
    out = Bitmap(size, size)
    for j in range(size):
        sj = int(j * 32 / float(size))
        for i in range(size):
            si = int(i * 32 / float(size))
            out.px(i, j, b32.get(si, sj))
    return out
