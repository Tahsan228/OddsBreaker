"""Make the README pictures: screenshots, the colour sheet and the demo GIF.

Needs Pillow, internet (for the sprites) and a display:

    xvfb-run -a -s "-screen 0 1600x1000x24" python tools/screenshots.py docs

A fake emulator draws a FireRed-style wild battle with real sprites, so the
pictures look like a real hunt without needing a game.
"""

import datetime
import os
import random
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["ODDSBREAKER_DATA"] = tempfile.mkdtemp(prefix="ob-shots-")

import tkinter as tk  # noqa: E402

from PIL import Image, ImageChops, ImageDraw, ImageGrab  # noqa: E402

from oddsbreaker import paths  # noqa: E402

paths.init()

from oddsbreaker import app as app_mod, mini as mini_mod, pages_more  # noqa: E402
from oddsbreaker.app import App  # noqa: E402
from oddsbreaker.art import DEX_H, LEFT_W, PANEL_W, PSCREEN  # noqa: E402
from oddsbreaker.detect import make_ref  # noqa: E402
from oddsbreaker.imaging import Bitmap, Frame  # noqa: E402
from oddsbreaker.pixel import FONT, KEY_COLOR, THEME_NAMES, draw_text  # noqa: E402
from oddsbreaker.script import parse_script  # noqa: E402
from oddsbreaker.selftest import Driver  # noqa: E402
from oddsbreaker.sprites import BASE, http_get  # noqa: E402
from oddsbreaker.stats import rate  # noqa: E402
from oddsbreaker.store import Store, default_profile  # noqa: E402
from oddsbreaker.system import StubPlatform  # noqa: E402

BG = (0x1B, 0x1B, 0x22)          # backdrop for the demo GIF (and the mini window here)
KEY = (0xFF, 0x00, 0xFF)         # the see-through colour around the Windows device
FRLG = "versions/generation-iii/firered-leafgreen/"
EMERALD = "versions/generation-iii/emerald/"
PLAT = "versions/generation-iv/platinum/"
REGION = [144, 12, 64, 62]       # watch area inside the 240x160 game screen
LOOP = "press A hold 0.02\nwait 0.3\ncheck 0.5\n"

# finished hunts for the log: pokemon, dex no, sprite set, game, emulator,
# date, resets, hours, type
HISTORY = [
    ("ralts", 280, EMERALD, "EMERALD", "mGBA", "2026-09-02 21:14:09", 2911, 14.6, "Caught"),
    ("gible", 443, PLAT, "DIAMOND/PEARL/PLAT", "DeSmuME", "2026-09-20 16:40:51", 6140, 30.2, "Caught"),
    ("pidgey", 16, FRLG, "FIRERED / LEAFGREEN", "mGBA", "2026-10-05 19:02:33", 1880, 9.4, "Phase"),
]


# ---------------------------------------------------------------- fake game
def sprite(folder, dex, shiny=False, back=False):
    """A cropped RGBA sprite from PokeAPI's sprite collection."""
    sub = folder + ("back/" if back else "") + ("shiny/" if shiny else "")
    cache = os.path.join(paths.DATA_DIR, "shot-sprites")
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(cache, "%s%d.png" % (sub.replace("/", "_"), dex))
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(http_get(BASE + "%s%d.png" % (sub, dex)))
    img = Image.open(path).convert("RGBA")
    return img.crop(img.getbbox())


def text(img, x, y, s, color, shadow):
    b = Bitmap(FONT.width(s) + 2, FONT.line_h + 2)
    draw_text(b, 0, 0, s, bytes(color) + b"\xff", FONT, shadow=bytes(shadow) + b"\xff")
    img.alpha_composite(Image.frombytes("RGBA", (b.w, b.h), bytes(b.buf)), (x, y))


def hp_box(img, x, y, name, level, frac, hp=None):
    d = ImageDraw.Draw(img)
    ink, shade = (64, 64, 64), (216, 208, 176)
    h = 34 if hp else 25
    d.rounded_rectangle([x, y, x + 100, y + h], radius=5, fill=(248, 248, 216), outline=(72, 88, 72), width=2)
    text(img, x + 7, y + 4, name, ink, shade)
    lv = "Lv%d" % level
    text(img, x + 94 - FONT.width(lv), y + 4, lv, ink, shade)
    d.rounded_rectangle([x + 30, y + 16, x + 94, y + 21], radius=2, fill=(72, 88, 80))
    d.rectangle([x + 32, y + 17, x + 32 + int(60 * frac), y + 20], fill=(112, 248, 168))
    d.rectangle([x + 18, y + 16, x + 27, y + 21], fill=(232, 160, 48))
    if hp:
        text(img, x + 94 - FONT.width(hp), y + 23, hp, ink, shade)


def battle(folder, dex, name, level, shiny):
    """A 240x160 FireRed-style wild battle, as an RGBA image."""
    img = Image.new("RGBA", (240, 160), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    for y in range(112):
        if y < 50:
            t = y / 49.0
            c = (int(184 + 56 * t), int(224 + 22 * t), int(248 - 16 * t))
        else:
            c = (160, 216, 120) if (y // 3) % 2 else (152, 208, 112)
        d.line([(0, y), (239, y)], fill=c)
    for box in ([128, 60, 224, 82], [6, 98, 122, 124]):
        d.ellipse(box, fill=(112, 168, 80), outline=(88, 136, 64))
        d.ellipse([box[0] + 5, box[1] + 1, box[2] - 5, box[3] - 6], fill=(176, 224, 128))
    foe = sprite(folder, dex, shiny)
    fx, fy = 176 - foe.width // 2, 73 - foe.height
    img.alpha_composite(foe, (fx, fy))
    if shiny:
        star = (255, 255, 200)
        for sx, sy, r in ((fx - 4, fy + 6, 4), (fx + foe.width + 2, fy + 14, 3),
                          (fx + foe.width // 2 + 6, fy - 4, 3), (fx + 2, fy + foe.height - 6, 2)):
            d.line([(sx - r, sy), (sx + r, sy)], fill=star)
            d.line([(sx, sy - r), (sx, sy + r)], fill=star)
            d.point([(sx, sy)], fill=(255, 255, 255))
    me = sprite(FRLG, 25, back=True)
    img.alpha_composite(me, (64 - me.width // 2, 116 - me.height))
    hp_box(img, 12, 14, name, level, 1.0)
    hp_box(img, 128, 74, "PIKACHU", 18, 0.82, "41/ 50")
    d.rectangle([0, 112, 239, 159], fill=(40, 48, 72))
    d.rounded_rectangle([3, 115, 236, 156], radius=5, fill=(48, 96, 128), outline=(224, 232, 240), width=2)
    text(img, 13, 124, "Wild %s appeared!" % name, (248, 248, 248), (104, 112, 120))
    return img


def to_bgra(img):
    r, g, b = img.convert("RGB").split()
    return Image.merge("RGBA", (b, g, r, Image.new("L", img.size, 255))).tobytes()


class BattlePlatform(StubPlatform):
    """Stub emulator showing a wild Charmander (shiny when .shiny is set)."""

    def __init__(self):
        StubPlatform.__init__(self)
        self.windows = [(1, "mGBA - Pokemon FireRed Version"), (2, "Notes.txt - Notepad")]
        self.scenes = {}

    def warm(self):
        """Build both scenes now, so the sprites are never fetched mid-film."""
        for key in (False, True):
            if key not in self.scenes:
                self.scenes[key] = to_bgra(battle(FRLG, 4, "CHARMANDER", 5, key))

    def scene(self):
        key = bool(self.shiny)
        if key not in self.scenes:
            self.scenes[key] = to_bgra(battle(FRLG, 4, "CHARMANDER", 5, key))
        return self.scenes[key]

    def capture(self, x, y, w, h):
        x, y, w, h = int(x), int(y), max(1, int(w)), max(1, int(h))
        gw, gh = self.size
        ox, oy = self.origin
        scene = self.scene()
        dark = b"\x1e\x1e\x1e\xff"
        rows = []
        for j in range(h):
            gy = y + j - oy
            if not 0 <= gy < gh:
                rows.append(dark * w)
                continue
            gx0 = x - ox
            a, b = max(0, gx0), min(gw, gx0 + w)
            left = max(0, min(w, -gx0))
            mid = scene[(gy * gw + a) * 4:(gy * gw + b) * 4] if b > a else b""
            rows.append(dark * left + mid + dark * (w - left - len(mid) // 4))
        return Frame(w, h, b"".join(rows))


# ---------------------------------------------------------------- the save
def make_save(plat, loop=None):
    """A believable save: a long Charmander hunt, two finished hunts and a log.
    loop replaces the hunt's steps (the demo uses a very short one)."""
    st = Store()
    data = st.fresh()
    data["settings"].update(legacy_checked=True, updates=False)
    data["welcomed"] = True
    p = data["profiles"][0]
    p.update(encounters=4271, seconds=21 * 3600 + 17 * 60, loop_avg=17.6)
    p["window"] = "mGBA"
    p["detect"]["region"] = list(REGION)
    p["detect"]["threshold"] = 6.0
    ox, oy = plat.origin
    p["detect"]["refs"] = [make_ref(plat.capture(ox + REGION[0], oy + REGION[1], REGION[2], REGION[3]))]
    if loop:
        p["script"] = parse_script(loop)[0]
    rnd = random.Random(7)
    today = datetime.date.today()
    per_day = [310, 0, 260, 455, 380, 120, 0, 290, 410, 335, 205, 470, 360, 180]
    for i, n in enumerate(per_day):
        p["daily"][(today - datetime.timedelta(days=13 - i)).isoformat()] = n
    p["scores"] = [round(rnd.uniform(0.3, 3.4), 2) for _ in range(30)]
    p["sessions"] = [{"start": "%s 19:%02d:00" % (today - datetime.timedelta(days=12 - i * 2), i * 7),
                      "seconds": 3600 * rnd.choice((1.5, 2, 2.5, 3)), "resets": 300 + rnd.randint(0, 220)}
                     for i in range(6)]
    os.makedirs(paths.SHINY_DIR, exist_ok=True)
    for name, dex, folder, game, emu, date, resets, hours, kind in HISTORY:
        path = os.path.join(paths.SHINY_DIR, "%s_%s.png" % (name, date[:10]))
        battle(folder, dex, name.upper(), rnd.randint(4, 14), True).convert("RGB").save(path)
        data["log"].append({"date": date, "profile": name.title(), "pokemon": name, "game": game,
                            "encounters": resets, "seconds": round(hours * 3600), "image": path,
                            "score": 31.5, "type": kind})
        if kind == "Phase":
            p["phases"].append({"date": date, "encounters": resets, "image": path})
            continue
        q = default_profile(name.title(), name, emu, game, 8192)
        q.update(encounters=resets, seconds=round(hours * 3600))
        q["found"] = {"date": date, "encounters": resets, "seconds": q["seconds"], "image": path}
        data["profiles"].append(q)
    q = default_profile("Shinx", "shinx", "DeSmuME", "DIAMOND/PEARL/PLAT", 8192)
    q.update(encounters=1312, seconds=round(6.4 * 3600))
    data["profiles"].append(q)
    st.save(data)


# ---------------------------------------------------------------- pictures
def grab(win, w=None, h=None):
    x, y = win.winfo_rootx(), win.winfo_rooty()
    w, h = w or win.winfo_width(), h or win.winfo_height()
    return ImageGrab.grab(bbox=(x, y, x + w, y + h), xdisplay=os.environ.get("DISPLAY")).convert("RGB")


def cut_bg(img):
    """Make the window background around the shell see-through."""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()
    edge = ([(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)] +
            [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)])
    for xy in edge:
        if px[xy][:3] in (KEY, BG) and px[xy][3]:
            ImageDraw.floodfill(img, xy, (0, 0, 0, 0), thresh=0)
    return img


def backdrop(img, n, color=BG):
    """The device on a plain backdrop with n pixels of room around it."""
    mask = ImageChops.difference(img, Image.new("RGB", img.size, KEY)).convert("L")
    img = img.copy()
    img.paste(color, mask=mask.point(lambda v: 255 if v == 0 else 0))
    out = Image.new("RGB", (img.width + 2 * n, img.height + 2 * n), color)
    out.paste(img, (n, n))
    return out


class ShotApp(App):
    """The Windows look: a frameless device with its own mini, minimise and
    close buttons. X has no colour-key windows, so the magenta around the
    shell is cut out of the pictures afterwards."""

    def setup_window(self):
        self.borderless = False
        App.setup_window(self)
        self.borderless = True
        self.root.configure(bg=KEY_COLOR)


def save_gif(frames, path, pad_px):
    """frames: [(RGB image, seconds shown)]. One shared palette, so unchanged
    pixels stay identical and Pillow only stores what moved."""
    imgs = [backdrop(f, pad_px) for f, _ in frames]
    step = max(1, len(imgs) // 24)
    sample = imgs[::step]
    sheet = Image.new("RGB", (sample[0].width, sample[0].height * len(sample)))
    for i, im in enumerate(sample):
        sheet.paste(im, (0, i * im.height))
    pal = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    out = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in imgs]
    ms = [max(20, int(round(sec * 100)) * 10) for _, sec in frames]
    out[0].save(path, save_all=True, append_images=out[1:], duration=ms, loop=0, optimize=False,
                disposal=1)
    return os.path.getsize(path)


def long_run_rate(p, *_session):
    """The demo loop is far faster than a real reset, so show the pace the
    whole hunt has averaged instead of the demo's."""
    return rate(p.get("encounters", 0), p.get("seconds", 0))


def open_app(plat):
    root = tk.Tk()
    app = ShotApp(root, plat, check_updates=False)
    # the pretend emulator sits right of the window, so the app never covers it
    plat.origin = (app.win_x + (LEFT_W + PANEL_W) * app.S + 24, 40)
    return root, app, Driver(app)


def close(app):
    """Quit cleanly, so the next window's event loop doesn't run old timers."""
    for job in app.root.tk.splitlist(app.root.tk.call("after", "info")):
        app.root.after_cancel(job)
    app.on_close()


def main(out):
    shots = os.path.join(out, "screens")
    os.makedirs(shots, exist_ok=True)
    for mod in (app_mod, mini_mod, pages_more):
        mod.hunt_rate = long_run_rate
    plat = BattlePlatform()
    plat.warm()

    def save(img, name):
        img = cut_bg(img)
        img.save(os.path.join(shots, name + ".png"))
        print("saved", name, img.size)

    # --- stills, mid-hunt
    make_save(plat)
    root, app, d = open_app(plat)
    S = app.S
    dev = (LEFT_W * S, DEX_H * S)
    ready = d.wait_for(lambda: (app.sprites.anim(4, False) and app.sprites.anim(4, True)
                                and app.sprites.lookup("charmander")), 60)
    assert ready, "the Charmander sprites did not download"
    d.pump(3.0)
    app.start_hunt()
    d.pump(2.0)
    px, py, pw, ph = PSCREEN   # the panel's screen, with a little of the shell around it
    page = tuple(v * S for v in (LEFT_W + px - 6, py - 6, LEFT_W + px + pw + 6, py + ph + 6))
    for tab in ("stats", "script", "check", "alert", "dex", "log", "more"):
        if app.panel_open:
            app.open_tab(tab)
        else:
            app.open_panel(tab)
        d.pump(1.2)
        img = grab(root)
        if tab == "stats":
            save(img, "hero")
        else:
            save(img.crop(page), "page-" + tab)
    app.close_panel()
    d.pump(0.6)
    app.enter_mini()
    assert d.wait_for(lambda: app.mini.anim, 10), "the mini window has no sprite"
    d.pump(1.5)
    save(grab(app.mini.top), "mini")
    app.exit_mini()
    app.stop_hunt()
    d.pump(0.3)
    close(app)
    keep = [app]  # its Tk images must outlive the next window

    # --- the demo: the lid opens, start, hunt, shiny, caught
    plat.shiny = False
    make_save(plat, LOOP)
    root, app, d = open_app(plat)
    frames = []

    def film(sec, until=None, fps=12):
        t_end = time.monotonic() + sec
        while time.monotonic() < t_end:
            t = time.monotonic()
            frames.append([grab(root, *dev), 0.0])
            if until is not None and until():
                break
            while time.monotonic() - t < 1.0 / fps:
                root.update()
                time.sleep(0.003)
            frames[-1][1] = time.monotonic() - t

    d.pump(0.1)
    film(6.0, until=lambda: not app.booting)   # the lid opens and the screen boots
    assert not app.booting, "the start-up show did not finish"
    film(1.2)
    while frames and max(frames[0][0].convert("L").getextrema()) < 40:
        frames.pop(0)  # window not drawn yet
    d.click_w(app.start_btn, wait=0)
    app.ui._leave(None)
    film(3.0)
    plat.shiny = True
    film(8, until=lambda: app.alert is not None)
    assert app.alert is not None, "the shiny was not spotted"
    film(3.4)
    film(4, until=lambda: app.menu.visible)
    film(0.8)
    plat.shiny = False
    app.alert_pick("caught")
    film(3.2)
    size = save_gif(frames, os.path.join(out, "demo.gif"), 6 * S)
    print("saved demo.gif: %d frames, %.1f MB" % (len(frames), size / 1e6))

    # --- every shell colour, showing the shiny it just caught
    tiles = []
    for name in THEME_NAMES:
        app.settings["theme"] = name
        app.rebuild(S)
        d.pump(2.0)
        tiles.append(cut_bg(grab(root, *dev)).resize((dev[0] // S, dev[1] // S), Image.NEAREST))
    tw, th = tiles[0].size
    gap, cols = 12, 4
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * tw + (cols - 1) * gap, rows * th + (rows - 1) * gap), (0, 0, 0, 0))
    for i, t in enumerate(tiles):
        sheet.alpha_composite(t, ((i % cols) * (tw + gap), (i // cols) * (th + gap)))
    sheet.save(os.path.join(shots, "themes.png"))
    print("saved themes", sheet.size)
    app.settings["theme"] = "RED"
    close(app)
    keep.append(app)
    sys.stdout.flush()
    os._exit(0)  # skip Tk image clean-up noise at exit


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs"))
