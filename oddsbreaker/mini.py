"""Mini mode: a small always-on-top counter to keep next to the game."""

import re

import tkinter as tk

from . import APP_NAME
from .art import (MINI_BTNS, MINI_H, MINI_LCD, MINI_SCREEN, MINI_START, MINI_W, battle_base,
                  draw_mini_shell, screen_bg)
from .dexnames import dex_no, poke_display
from .imaging import Bitmap
from .pixel import FONT, KEY_COLOR, PAL, TINY, draw_text, ellipsize
from .sprites import MINI_TARGET
from .stats import fmt_int, fmt_time, hunt_rate
from .ui.toolkit import UI, Button, ImageBox, Pic, StartButton, Widget


class MiniLCD(Widget):
    def __init__(self, ui, group, x, y, w, h):
        self.vals = {"name": "", "count": 0, "time": 0, "rate": None, "state": "stopped", "blink": 0}
        Widget.__init__(self, ui, group, x, y, w, h)

    def update(self, **kw):
        ch = False
        for k, v in kw.items():
            if self.vals.get(k) != v:
                self.vals[k] = v
                ch = True
        if ch:
            self.refresh()

    def render(self):
        P = PAL
        w, h = self.w, self.h
        b = Bitmap(w, h)
        ink, mid, ghost = P["lcd4"], P["lcd3"], P["lcd5"]
        v = self.vals
        draw_text(b, 2, 2, ellipsize(v["name"], w - 14, TINY), mid, TINY)
        st = v["state"]
        if st == "running" or (st == "paused" and v["blink"]):
            b.circle(w - 5, 4, 2, ink)
        elif st == "paused":
            b.circle(w - 5, 4, 2, mid)
        s = fmt_int(v["count"])
        ghost_s = "888,888" if len(s) <= 7 else "8,888,888"
        right = 2 + FONT.width(ghost_s, 2)
        if right > w - 2:
            right = w - 2
        else:
            draw_text(b, 2, 9, ghost_s, ghost, FONT, 2)
        draw_text(b, right - FONT.width(s, 2), 9, s, ink, FONT, 2)
        draw_text(b, 2, 26, fmt_time(v["time"]), ink)
        rate = ("%s/HR" % fmt_int(v["rate"])) if v["rate"] else "--/HR"
        draw_text(b, w - 2 - TINY.width(rate), 28, rate, mid, TINY)
        return b


class MiniWindow(object):
    def __init__(self, app):
        self.app = app
        S = self.S = app.S
        top = self.top = tk.Toplevel(app.root)
        top.title(APP_NAME + " Mini")
        top.resizable(False, False)
        try:
            top.iconphoto(False, *app.icons)
        except Exception:
            pass
        self.borderless = app.borderless
        if self.borderless:
            try:
                top.overrideredirect(True)
                top.configure(bg=KEY_COLOR)
                top.attributes("-transparentcolor", KEY_COLOR)
                top.update_idletasks()
                if app.plat.make_app_window(top):
                    top.withdraw()
                    top.after(40, top.deiconify)
            except Exception:
                self.borderless = False
        try:
            top.attributes("-topmost", True)
        except tk.TclError:
            pass
        top.protocol("WM_DELETE_WINDOW", self.expand)
        bg = KEY_COLOR if self.borderless else "#1B1B22"
        self.ui = UI(top, S, MINI_W, MINI_H, bg, self)
        top.bind("<KeyPress>", lambda e: self.ui.key(e))
        g = self.ui.top
        self.shell = Pic(self.ui, g, 0, 0, draw_mini_shell())
        x, y, w, h = MINI_SCREEN
        Pic(self.ui, g, x, y, screen_bg(w, h, "day"))
        base = battle_base(42, 8)
        Pic(self.ui, g, x + (w - 42) // 2, y + h - 12, base)
        self.sprite = ImageBox(self.ui, g, x, y + 3, w, h - 8, anchor="bottom",
                               cb=lambda a, b: self.expand(), hint="Back to the full device")
        lx, ly, lw, lh = MINI_LCD
        self.lcd = MiniLCD(self.ui, g, lx, ly, lw, lh)
        cx, cy = MINI_START
        self.start = StartButton(self.ui, g, cx - 12, cy - 12, self.app.toggle_hunt,
                                 "Start / stop hunting", r=12)
        (bx, by), (cx2, cy2) = MINI_BTNS
        Button(self.ui, g, bx, by, 15, 14, "◀", self.expand, "shell", "Back to the full device", TINY)
        Button(self.ui, g, cx2, cy2, 15, 14, "×", self.close_app, "shell", "Close " + APP_NAME, TINY)
        self.hint_text = ""
        self.anim = None
        self.anim_key = None
        self.anim_i = 0
        self.anim_next = 0.0
        self.retry_at = 0.0
        self.place()
        self.sprite_changed()
        self.ui.start()

    # -- the UI calls these on its "app"
    def hint(self, text):
        self.hint_text = text or ""

    def can_drag(self, x, y):
        return bool(self.shell.bmp.alpha(int(x), int(y)))

    def window_moved(self):
        self.app.settings["mini_pos"] = self.position()
        self.app.changed()

    def double_click_shell(self):
        self.expand()

    def on_key(self, e):
        if e.keysym == "space":
            self.app.toggle_hunt()
            return "break"
        if e.keysym == "Escape":
            self.expand()
            return "break"
        return None

    def sound(self, name):
        self.app.sound(name)

    # -- window
    def position(self):
        return "+%d+%d" % (self.top.winfo_x(), self.top.winfo_y())

    def place(self):
        S = self.S
        pos = self.app.settings.get("mini_pos") or ""
        m = re.match(r"^\+(-?\d+)\+(-?\d+)$", pos)
        vx, vy, vw, vh = self.app.plat.virtual_screen()
        if m:
            x, y = int(m.group(1)), int(m.group(2))
            if not (vx - 40 <= x <= vx + vw - 80 and vy - 10 <= y <= vy + vh - 60):
                m = None
        if not m:
            x, y = self.app.win_x, self.app.win_y
        self.top.geometry("%dx%d+%d+%d" % (MINI_W * S, MINI_H * S, x, y))

    def expand(self):
        self.app.settings["mini_pos"] = self.position()
        self.app.exit_mini()

    def close_app(self):
        self.app.settings["mini_pos"] = self.position()
        self.app.exit_mini()
        self.app.on_close()

    def destroy(self):
        self.ui.alive = False
        try:
            self.top.destroy()
        except tk.TclError:
            pass

    # -- content
    def sprite_changed(self):
        app = self.app
        p = app.profile
        name = p.get("pokemon") or ""
        shiny = bool(p.get("found"))
        x, y, w, h = MINI_SCREEN
        pid = dex_no(name)
        frames = app.sprites.anim(pid, shiny) if pid else None
        key = (pid, shiny, bool(frames))
        if key == self.anim_key:
            return
        self.anim_key = key
        if frames:
            fw = max(b.w for b, _d in frames)
            fh = max(b.h for b, _d in frames)
            self.anim = [(app.fit_photo(b, fw, fh, w - 2, h - 8, MINI_TARGET), d) for b, d in frames]
            self.anim_i = 0
            self.sprite.set_photo(self.anim[0][0])
        else:
            self.anim = None
            res = app.sprites.lookup(name) if name else None
            if res:
                bmp = res[2] if shiny else res[1]
                self.photo = app.fit_photo(bmp, box_w=w - 2, box_h=h - 8, target=MINI_TARGET)
            else:
                from .art import placeholder_bitmap
                self.photo = placeholder_bitmap().photo(self.S)
            self.sprite.set_photo(self.photo)

    def update(self, now):
        if not self.ui.alive:
            return
        app = self.app
        p = app.profile
        rate = hunt_rate(p, app.session_count, app.session_time)
        self.lcd.update(name=poke_display(p.get("pokemon") or p["name"]), count=p["encounters"],
                        time=int(p["seconds"]), rate=int(round(rate)) if rate else None,
                        state=app.hstate if app.hunter is not None else "stopped",
                        blink=int(now * 3) % 2)
        self.start.set_running(app.hunter is not None)
        if self.anim and now >= self.anim_next:
            self.anim_i = (self.anim_i + 1) % len(self.anim)
            photo, delay = self.anim[self.anim_i]
            self.sprite.set_photo(photo)
            self.anim_next = now + delay / 1000.0
        if self.anim_key and self.anim_key[0] and not self.anim_key[2] and now >= self.retry_at:
            self.retry_at = now + 2.0
            self.sprite_changed()

