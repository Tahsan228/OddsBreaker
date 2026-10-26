"""The start-up show: the closed Pokedex swings open, the lights come on and
the screen boots. Click or press any key to skip it."""

import math
import time

from . import __version__
from .art import BOOT_BAR, BOOT_SEGS, HINGE_X, SCREEN, boot_bar, boot_screen, lid_bitmap, lid_frame
from .ui import fx
from .ui.toolkit import Frames, Group, Pic

LID_STEPS = 6


def ease_in_out(t):
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))


class Boot(object):
    """Runs once when the app opens (not after a theme or size change).

    Times are in seconds. With the lid (FULL effects) the lid holds for HOLD,
    swings open over SWING, then the power-on part runs; LITE skips the lid.
    """
    HOLD, SWING = 0.35, 0.45
    LEDS_END = 0.62          # LED test pattern, from power-on
    CRT_AT = 0.12            # the screen turns on
    BAR_AT, BAR_END = 0.62, 1.22
    FINISH = 1.32

    def __init__(self, app, lid=True):
        self.app = app
        self.ui = ui = app.ui
        self.t0 = self.p0 = time.monotonic()   # p0: when the power-on part starts
        self.done = False
        self.leds = {"r": 0, "y": 0, "g": 0}
        self.lens = 0
        self.crt = None
        self.flags = set()
        g = app.g_left
        S = ui.S
        sx, sy, sw, sh = SCREEN
        cv = ui.cv
        # the screen stays dark until it powers on
        self.off = cv.create_rectangle((g.ox() + sx) * S, (g.oy() + sy) * S, (g.ox() + sx + sw) * S,
                                       (g.oy() + sy + sh) * S, fill="#0A0F0A", outline="", width=0,
                                       tags=g.tags())
        self.g_splash = Group(ui, g, visible=False)
        Pic(ui, self.g_splash, sx, sy, boot_screen(sw, sh, __version__))
        self.bar = Frames(ui, self.g_splash, sx + (sw - BOOT_BAR[0]) // 2 + 2, sy + 76,
                          [boot_bar(k) for k in range(BOOT_SEGS + 1)])
        # the lid: frame 0 now, the swing frames while it holds
        self.lid_item = None
        self.lid_base = None
        self.lid_photos = []
        if lid:
            self.lid_base = lid_bitmap()
            self.lid_photos = [self.lid_base.photo(S)]
            self.lid_item = cv.create_image((g.ox()) * S, (g.oy()) * S, anchor="nw",
                                            image=self.lid_photos[0], tags=g.tags())
        cv.tag_raise(self.off)
        if self.lid_item is not None:
            cv.tag_raise(self.lid_item)
        ui.anims.append(self.step)

    # -- helpers ------------------------------------------------------------------
    def once(self, key):
        if key in self.flags:
            return False
        self.flags.add(key)
        return True

    def show_lid(self, i):
        S = self.ui.S
        g = self.app.g_left
        photo = self.lid_photos[i]
        w = photo.width() // S
        cv = self.ui.cv
        cv.itemconfig(self.lid_item, image=photo)
        cv.coords(self.lid_item, (g.ox() + HINGE_X - w) * S, g.oy() * S)

    def drop_lid(self):
        if self.lid_item is not None:
            self.ui.cv.delete(self.lid_item)
            self.lid_item = None
            self.lid_photos = []

    # -- the show -------------------------------------------------------------------
    def step(self, now):
        if self.done or not self.ui.alive:
            return False
        app = self.app
        if self.lid_item is not None:
            t = now - self.t0
            if len(self.lid_photos) <= LID_STEPS:
                # make one swing frame per tick while the lid is still shut
                k = len(self.lid_photos)
                self.lid_photos.append(lid_frame(self.lid_base, k, LID_STEPS).photo(self.ui.S))
                if t >= self.HOLD:
                    self.t0 = now - self.HOLD   # wait for the frames, then swing
                return "fast"
            if t < self.HOLD:
                return "fast"
            st = t - self.HOLD
            if st < self.SWING:
                if self.once("lid"):
                    app.sound("lid")
                k = ease_in_out(st / self.SWING)
                self.show_lid(min(LID_STEPS, int(k * (LID_STEPS + 1))))
                return "fast"
            self.drop_lid()
            self.p0 = now
        self.power(now - self.p0)
        return "fast"

    def power(self, p):
        app = self.app
        if self.once("power"):
            app.sound("power")
        # LEDs: red, yellow, green, all off, all on
        if p < self.LEDS_END:
            k = int(p / 0.1)
            self.leds = {"r": 2 if k in (0, 1, 2, 5) else 0, "y": 2 if k in (1, 2, 5) else 0,
                         "g": 2 if k in (2, 5) else 0}
        else:
            self.leds = None
        # the lens warms up and settles
        self.lens = min(5, int(p * 12)) if p < 0.5 else max(0, 5 - int((p - 0.5) * 10))
        if p >= self.CRT_AT and self.once("crt"):
            sx, sy, sw, sh = SCREEN
            self.ui.cv.delete(self.off)
            self.g_splash.set_visible(True)
            self.crt = fx.CRT(self.ui, app.g_left, sx, sy, sw, sh)
        if p >= self.CRT_AT + 0.08 and self.once("lcd"):
            app.lcd.self_test(0.7)
        if p >= self.BAR_AT:
            k = int((p - self.BAR_AT) / (self.BAR_END - self.BAR_AT) * BOOT_SEGS) + 1
            self.bar.set_frame(min(BOOT_SEGS, k))
        if p >= self.FINISH:
            self.finish(chime=True)

    def finish(self, chime=False):
        """End the show (also used to skip it)."""
        if self.done:
            return
        self.done = True
        app = self.app
        self.drop_lid()
        try:
            self.ui.cv.delete(self.off)
        except Exception:
            pass
        if self.crt is not None:
            self.crt.finish()
        self.g_splash.set_visible(False)
        self.leds = None
        app.refresh_screen()
        if app.fx_on("full"):
            app.fizzle.play(app.screen_color(), 0.35)
        if chime:
            app.sound("boot")
        app.boot_finished()
