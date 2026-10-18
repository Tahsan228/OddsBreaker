"""Palette, colour themes and the hand-made pixel fonts."""


def hexc(h, a=255):
    return bytes((int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16), a))


def mix(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return bytes(int(a + (b - a) * t) for a, b in zip(c1[:3], c2[:3])) + b"\xff"


def to_hex(c):
    return "#%02X%02X%02X" % (c[0], c[1], c[2])


KEY_COLOR = "#FF00FF"  # window transparency key: never used in the art

PAL = dict((k, hexc(v)) for k, v in {
    # shell (recoloured by the theme)
    "outline": "#2A0A12",
    "red_hi": "#FF6E7E", "red": "#E3263F", "red_md": "#C41A33", "red_dk": "#93122A",
    "red_xd": "#5E0B19",
    # keys on the shell (recoloured by the theme)
    "btn": "#3D7DF0", "btn_hi": "#86B3FF", "btn_dk": "#2350AE", "btn_xd": "#0F2A66",
    "btn_lit": "#BFE0FF",
    # bezel, plastic and glass
    "white": "#F7F7F7", "bezel": "#DCDCE6", "bezel_hi": "#FFFFFF", "bezel_sh": "#A5A5B6",
    "bezel_xd": "#7A7A8E",
    "gray": "#8A8A99", "dgray": "#4B4B58", "black": "#1B1B22", "black_hi": "#3A3A46",
    "black_md": "#2A2A33",
    "blue_xl": "#A9E6FF", "blue_lt": "#55B6FF", "blue": "#2382E8", "blue_dk": "#1553AA",
    "blue_xd": "#0B2F66",
    # main screen
    "scr": "#E9F6E0", "scr2": "#D9EECF", "scr_line": "#DDEFD3", "scr_ink": "#1D3A1D",
    "scr_dim": "#6E8F63", "scr_frame": "#3B4A3B", "scr_base": "#A9D69A", "scr_base2": "#8CC27C",
    "scr_base3": "#C7E8BC",
    # LCD
    "lcd": "#9BBC0F", "lcd2": "#8BAC0F", "lcd3": "#306230", "lcd4": "#0F380F", "lcd5": "#88A80E",
    # dark UI on the right-hand screen
    "dark": "#0B1220", "dark2": "#131D2E", "dark3": "#1C2A40", "dark4": "#273A57",
    "dark5": "#33507A", "line": "#31476A", "ink": "#EAF2FF", "dim": "#8299B8",
    "faint": "#4F6788", "night": "#070C16",
    # accents
    "cyan": "#5CE1E6", "cyan_dk": "#1E8C99", "green": "#7CF07C", "green_dk": "#1E6B3B",
    "yellow": "#FFD93B", "pink": "#FF7AB6", "orange": "#FF9F43", "bad": "#FF5A6A",
    "bad_dk": "#8E1023", "purple": "#B48CFF",
    "gold": "#FFD93B", "gold_hi": "#FFF5A8", "gold_md": "#F2B51C", "gold_dk": "#B8860B",
    "gold_xd": "#6B4A00",
    # lights
    "led_r": "#FF3B4F", "led_r_off": "#6A1A24", "led_y": "#FFD43B",
    "led_y_off": "#5E5014", "led_g": "#4BE35A", "led_g_off": "#1A4D22",
    "status_bg": "#0B1611", "status_ink": "#8FF0A0", "status_dim": "#4F8C61",
    "shadow": "#140508",
}.items())

# Shell colour themes: (outline, hi, base, mid, dark, xdark) + key colours.
_KEYS_BLUE = ("#3D7DF0", "#86B3FF", "#2350AE", "#0F2A66", "#BFE0FF")
_KEYS_RED = ("#E3263F", "#FF7A88", "#93122A", "#4A0812", "#FFC2CA")
_KEYS_GOLD = ("#EFB21A", "#FFE07A", "#A87A06", "#4D3500", "#FFF3C2")
_KEYS_TEAL = ("#19B3A6", "#7FEDE2", "#0E7A71", "#05332F", "#C2FFF8")
THEMES = [
    ("RED", ("#2A0A12", "#FF6E7E", "#E3263F", "#C41A33", "#93122A", "#5E0B19"), _KEYS_BLUE),
    ("BLUE", ("#08142E", "#7FB2FF", "#2E6FE0", "#2459C2", "#183E8F", "#0C2557"), _KEYS_GOLD),
    ("ONYX", ("#060609", "#6B6B7A", "#34343F", "#2B2B34", "#1E1E26", "#121218"), _KEYS_RED),
    ("GOLD", ("#2B1E00", "#FFF1A6", "#E8B923", "#CC9A12", "#946A06", "#5C4003"), _KEYS_BLUE),
    ("GREEN", ("#06210E", "#8CF0A0", "#2EAD55", "#23913F", "#186A2C", "#0D3F19"), _KEYS_BLUE),
    ("PURPLE", ("#170A2E", "#D2A6FF", "#8A4FE0", "#723CC4", "#522891", "#2F1659"), _KEYS_TEAL),
    ("PINK", ("#2E0A1A", "#FFB3D6", "#F0609E", "#D14684", "#9C2F61", "#5E1A3A"), _KEYS_BLUE),
    ("SILVER", ("#1C1C26", "#FFFFFF", "#CFD3DE", "#B5BAC8", "#8A90A3", "#5A6075"), _KEYS_RED),
]
THEME_NAMES = [t[0] for t in THEMES]
SHELL_KEYS = ("outline", "red_hi", "red", "red_md", "red_dk", "red_xd")
KEY_KEYS = ("btn", "btn_hi", "btn_dk", "btn_xd", "btn_lit")
_current_theme = ["RED"]


def apply_theme(name):
    """Recolour the shell and its keys. Widgets pick it up when re-drawn."""
    for tname, shell, keys in THEMES:
        if tname == name:
            break
    else:
        tname, shell, keys = THEMES[0]
    for k, v in zip(SHELL_KEYS, shell):
        PAL[k] = hexc(v)
    for k, v in zip(KEY_KEYS, keys):
        PAL[k] = hexc(v)
    _current_theme[0] = tname
    return tname


def current_theme():
    return _current_theme[0]


# ---------------------------------------------------------------------------
# Fonts: "char rows" where rows are split by | and # is a lit pixel.
# ---------------------------------------------------------------------------
FONT5_TABLE = r"""
A .###.|#...#|#...#|#####|#...#|#...#|#...#
B ####.|#...#|#...#|####.|#...#|#...#|####.
C .###.|#...#|#....|#....|#....|#...#|.###.
D ####.|#...#|#...#|#...#|#...#|#...#|####.
E #####|#....|#....|####.|#....|#....|#####
F #####|#....|#....|####.|#....|#....|#....
G .###.|#...#|#....|#.###|#...#|#...#|.####
H #...#|#...#|#...#|#####|#...#|#...#|#...#
I ###|.#.|.#.|.#.|.#.|.#.|###
J ..###|...#.|...#.|...#.|...#.|#..#.|.##..
K #...#|#..#.|#.#..|##...|#.#..|#..#.|#...#
L #....|#....|#....|#....|#....|#....|#####
M #...#|##.##|#.#.#|#.#.#|#...#|#...#|#...#
N #...#|#...#|##..#|#.#.#|#..##|#...#|#...#
O .###.|#...#|#...#|#...#|#...#|#...#|.###.
P ####.|#...#|#...#|####.|#....|#....|#....
Q .###.|#...#|#...#|#...#|#.#.#|#..#.|.##.#
R ####.|#...#|#...#|####.|#.#..|#..#.|#...#
S .####|#....|#....|.###.|....#|....#|####.
T #####|..#..|..#..|..#..|..#..|..#..|..#..
U #...#|#...#|#...#|#...#|#...#|#...#|.###.
V #...#|#...#|#...#|#...#|#...#|.#.#.|..#..
W #...#|#...#|#...#|#.#.#|#.#.#|#.#.#|.#.#.
X #...#|#...#|.#.#.|..#..|.#.#.|#...#|#...#
Y #...#|#...#|.#.#.|..#..|..#..|..#..|..#..
Z #####|....#|...#.|..#..|.#...|#....|#####
a .....|.....|.###.|....#|.####|#...#|.####
b #....|#....|#.##.|##..#|#...#|#...#|####.
c ....|....|.###|#...|#...|#...|.###
d ....#|....#|.##.#|#..##|#...#|#...#|.####
e .....|.....|.###.|#...#|#####|#....|.###.
f ..##|.#..|###.|.#..|.#..|.#..|.#..
g .....|.....|.####|#...#|#...#|.####|....#|.###.
h #....|#....|#.##.|##..#|#...#|#...#|#...#
i .#.|...|##.|.#.|.#.|.#.|###
j ..#|...|.##|..#|..#|..#|#.#|.#.
k #...|#...|#..#|#.#.|##..|#.#.|#..#
l ##.|.#.|.#.|.#.|.#.|.#.|###
m .....|.....|##.#.|#.#.#|#.#.#|#.#.#|#...#
n .....|.....|#.##.|##..#|#...#|#...#|#...#
o .....|.....|.###.|#...#|#...#|#...#|.###.
p .....|.....|####.|#...#|#...#|####.|#....|#....
q .....|.....|.####|#...#|#...#|.####|....#|....#
r ....|....|#.##|##..|#...|#...|#...
s .....|.....|.####|#....|.###.|....#|####.
t .#..|.#..|###.|.#..|.#..|.#.#|..#.
u .....|.....|#...#|#...#|#...#|#..##|.##.#
v .....|.....|#...#|#...#|#...#|.#.#.|..#..
w .....|.....|#...#|#...#|#.#.#|#.#.#|.#.#.
x .....|.....|#...#|.#.#.|..#..|.#.#.|#...#
y .....|.....|#...#|#...#|#...#|.####|....#|.###.
z .....|.....|#####|...#.|..#..|.#...|#####
0 .###.|#...#|#..##|#.#.#|##..#|#...#|.###.
1 ..#..|.##..|..#..|..#..|..#..|..#..|.###.
2 .###.|#...#|....#|...#.|..#..|.#...|#####
3 #####|...#.|..#..|...#.|....#|#...#|.###.
4 ...#.|..##.|.#.#.|#..#.|#####|...#.|...#.
5 #####|#....|####.|....#|....#|#...#|.###.
6 ..##.|.#...|#....|####.|#...#|#...#|.###.
7 #####|....#|...#.|..#..|.#...|.#...|.#...
8 .###.|#...#|#...#|.###.|#...#|#...#|.###.
9 .###.|#...#|#...#|.####|....#|...#.|.##..
. .|.|.|.|.|.|#
, ..|..|..|..|..|.#|.#|#.
: .|#|.|.|.|#|.
; ..|.#|..|..|..|.#|.#|#.
! #|#|#|#|#|.|#
? .###.|#...#|....#|...#.|..#..|.....|..#..
' #|#|.|.|.|.|.
" #.#|#.#|...|...|...|...|...
- ....|....|....|####|....|....|....
+ .....|..#..|..#..|#####|..#..|..#..|.....
= ....|....|####|....|####|....|....
/ ....#|....#|...#.|..#..|.#...|#....|#....
\ #....|#....|.#...|..#..|...#.|....#|....#
( ..#|.#.|#..|#..|#..|.#.|..#
) #..|.#.|..#|..#|..#|.#.|#..
[ ###|#..|#..|#..|#..|#..|###
] ###|..#|..#|..#|..#|..#|###
< ...#|..#.|.#..|#...|.#..|..#.|...#
> #...|.#..|..#.|...#|..#.|.#..|#...
_ .....|.....|.....|.....|.....|.....|#####
* .....|#.#.#|.###.|#####|.###.|#.#.#|.....
# .#.#.|.#.#.|#####|.#.#.|#####|.#.#.|.#.#.
% ##...|##..#|...#.|..#..|.#...|#..##|...##
& .##..|#..#.|#.#..|.#...|#.#.#|#..#.|.##.#
@ .###.|#...#|#.###|#.#.#|#.###|#....|.####
~ .....|.....|.#...|#.#.#|...#.|.....|.....
$ ..#..|.####|#.#..|.###.|..#.#|####.|..#..
^ ..#..|.#.#.|#...#|.....|.....|.....|.....
PIPE #|#|#|#|#|#|#
★ ...#...|..###..|#######|.#####.|..###..|.##.##.|.#...#.
▶ #...|##..|###.|####|###.|##..|#...
◀ ...#|..##|.###|####|.###|..##|...#
▲ .......|.......|...#...|..###..|.#####.|#######|.......
▼ .......|#######|.#####.|..###..|...#...|.......|.......
✓ .....|....#|...##|#.##.|###..|.#...|.....
× .....|#...#|.#.#.|..#..|.#.#.|#...#|.....
· .|.|.|#|.|.|.
♀ .###.|#...#|#...#|.###.|..#..|.###.|..#..
♂ ..###|...##|..#.#|.##..|#..#.|#..#.|.##..
é ...#.|..#..|.###.|#...#|#####|#....|.###.
● .....|.###.|#####|#####|#####|.###.|.....
○ .....|.###.|#...#|#...#|#...#|.###.|.....
■ #####|#####|#####|#####|#####|#####|#####
… .....|.....|.....|.....|.....|.....|#.#.#
← .....|..#..|.#...|#####|.#...|..#..|.....
→ .....|..#..|...#.|#####|...#.|..#..|.....
↑ ..#..|.###.|#.#.#|..#..|..#..|..#..|..#..
↓ ..#..|..#..|..#..|..#..|#.#.#|.###.|..#..
♪ ..##|..#.|..#.|..#.|.##.|###.|.#..
↻ .###.|#...#|....#|.#.##|..###|...#.|.....
"""

FONT3_TABLE = r"""
A .#.|#.#|###|#.#|#.#
B ##.|#.#|##.|#.#|##.
C .##|#..|#..|#..|.##
D ##.|#.#|#.#|#.#|##.
E ###|#..|##.|#..|###
F ###|#..|##.|#..|#..
G .##|#..|#.#|#.#|.##
H #.#|#.#|###|#.#|#.#
I ###|.#.|.#.|.#.|###
J ..#|..#|..#|#.#|.#.
K #.#|#.#|##.|#.#|#.#
L #..|#..|#..|#..|###
M #...#|##.##|#.#.#|#...#|#...#
N #..#|##.#|#.##|#..#|#..#
O .#.|#.#|#.#|#.#|.#.
P ##.|#.#|##.|#..|#..
Q .#.|#.#|#.#|##.|.##
R ##.|#.#|##.|#.#|#.#
S .##|#..|.#.|..#|##.
T ###|.#.|.#.|.#.|.#.
U #.#|#.#|#.#|#.#|###
V #.#|#.#|#.#|#.#|.#.
W #...#|#...#|#.#.#|#.#.#|.#.#.
X #.#|#.#|.#.|#.#|#.#
Y #.#|#.#|.#.|.#.|.#.
Z ###|..#|.#.|#..|###
0 ###|#.#|#.#|#.#|###
1 .#.|##.|.#.|.#.|###
2 ##.|..#|.#.|#..|###
3 ##.|..#|.#.|..#|##.
4 #.#|#.#|###|..#|..#
5 ###|#..|##.|..#|##.
6 .##|#..|###|#.#|###
7 ###|..#|.#.|.#.|.#.
8 ###|#.#|###|#.#|###
9 ###|#.#|###|..#|##.
. .|.|.|.|#
, .|.|.|#|#
: .|#|.|#|.
- ...|...|###|...|...
+ ...|.#.|###|.#.|...
/ ..#|..#|.#.|#..|#..
% #.#|..#|.#.|#..|#.#
! #|#|#|.|#
? ##.|..#|.#.|...|.#.
( .#|#.|#.|#.|.#
) #.|.#|.#|.#|#.
' #|#|.|.|.
= ...|###|...|###|...
_ ...|...|...|...|###
· .|.|#|.|.
× ...|#.#|.#.|#.#|...
★ ..#..|#####|.###.|.#.#.|.....
▶ #..|##.|###|##.|#..
◀ ..#|.##|###|.##|..#
▲ .....|..#..|.###.|#####|.....
▼ .....|#####|.###.|..#..|.....
✓ ...|..#|#.#|.#.|...
# .#.#.|#####|.#.#.|#####|.#.#.
< ..#|.#.|#..|.#.|..#
> #..|.#.|..#|.#.|#..
~ .....|.#..#|#.##.|.....|.....
* ...|#.#|.#.|#.#|...
● .##.|####|####|.##.
○ .##.|#..#|#..#|.##.
■ ###|###|###
… .....|.....|.....|.....|#.#.#
"""


class Glyph(object):
    __slots__ = ("w", "pts")

    def __init__(self, w, pts):
        self.w, self.pts = w, pts


class Font(object):
    def __init__(self, table, height, space, line_h, upper_only=False):
        self.glyphs = {}
        self.height, self.space, self.line_h = height, space, line_h
        self.upper_only = upper_only
        for line in table.strip("\n").splitlines():
            if not line.strip():
                continue
            if line.startswith("PIPE "):
                ch, rest = "|", line[5:]
            else:
                ch, rest = line[0], line[2:]
            rows = rest.strip().split("|")
            cols = [x for row in rows for x, c in enumerate(row) if c == "#"]
            if ch.isdigit():
                left, right = 0, max(len(r) for r in rows) - 1
            else:
                left, right = (min(cols), max(cols)) if cols else (0, 0)
            pts = [(x - left, y) for y, row in enumerate(rows) for x, c in enumerate(row) if c == "#"]
            self.glyphs[ch] = Glyph(right - left + 1, pts)
        self.fallback = self.glyphs.get("?")

    def get(self, ch):
        if self.upper_only:
            ch = ch.upper()
        g = self.glyphs.get(ch)
        if g is None:
            g = self.glyphs.get(ch.upper()) or self.fallback
        return g

    def width(self, s, scale=1, spacing=1):
        w = 0
        for ch in s:
            if ch == " ":
                w += self.space * scale
            else:
                w += (self.get(ch).w + spacing) * scale
        if s and s[-1] != " ":
            w -= spacing * scale
        return max(0, w)


FONT = Font(FONT5_TABLE, 7, 3, 10)
TINY = Font(FONT3_TABLE, 5, 2, 7, upper_only=True)


def draw_text(bmp, x, y, s, c, font=None, scale=1, spacing=1, shadow=None, clip=None):
    """Draw text; returns the width drawn. clip=(y0, y1) keeps rows in range."""
    font = font or FONT
    cx = x
    for ch in s:
        if ch == " ":
            cx += font.space * scale
            continue
        g = font.get(ch)
        if shadow is not None:
            _glyph(bmp, g, cx + scale, y + scale, shadow, scale, clip)
        _glyph(bmp, g, cx, y, c, scale, clip)
        cx += (g.w + spacing) * scale
    if s and s[-1] != " ":
        cx -= spacing * scale
    return max(0, cx - x)


def _glyph(bmp, g, x, y, c, scale, clip):
    if scale == 1:
        for (px, py) in g.pts:
            yy = y + py
            if clip is None or clip[0] <= yy < clip[1]:
                bmp.px(x + px, yy, c)
    else:
        for (px, py) in g.pts:
            yy = y + py * scale
            if clip is None:
                bmp.rect(x + px * scale, yy, scale, scale, c)
            else:
                y0, y1 = max(yy, clip[0]), min(yy + scale, clip[1])
                if y1 > y0:
                    bmp.rect(x + px * scale, y0, scale, y1 - y0, c)


def draw_text_outlined(bmp, x, y, s, fill, outline, font=None, scale=1, drop=True):
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
        draw_text(bmp, x + dx, y + dy, s, outline, font, scale)
    if drop:
        draw_text(bmp, x + 1, y + 2, s, outline, font, scale)
    return draw_text(bmp, x, y, s, fill, font, scale)


def draw_text_grad(bmp, x, y, s, colors, font=None, scale=1):
    """Text with horizontal colour bands from top to bottom (metallic look)."""
    font = font or FONT
    h = font.height * scale
    n = len(colors)
    w = 0
    for i, c in enumerate(colors):
        y0 = y + h * i // n
        y1 = y + h * (i + 1) // n
        w = draw_text(bmp, x, y, s, c, font, scale, clip=(y0, y1))
    return w


def ellipsize(s, maxw, font=None, scale=1):
    font = font or FONT
    if font.width(s, scale) <= maxw:
        return s
    dots = "…" if "…" in font.glyphs else ".."
    while s and font.width(s + dots, scale) > maxw:
        s = s[:-1]
    return s.rstrip() + dots


def wrap_text(s, maxw, font=None):
    font = font or FONT
    lines = []
    for para in s.split("\n"):
        words = para.split(" ")
        cur = ""
        for wd in words:
            t = (cur + " " + wd) if cur else wd
            if font.width(t) <= maxw or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = wd
        lines.append(cur)
    return lines
