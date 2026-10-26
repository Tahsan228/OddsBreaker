"""The OddsBreaker window: the device on the left, the setup panel on the right."""

import copy
import datetime
import math
import os
import queue
import re
import sys
import time
import traceback

import tkinter as tk

from . import APP_NAME, RELEASES_URL, __version__, paths
from .art import (CONTENT, DEX_H, DPAD_XY, FACE_XY, KEY_GAP, KEY_H, KEY_W, KEY_X0, KEYS_Y, LCD_IN,
                  LEDS, LEFT_W, LENS_C, MINIS, PANEL_W, PSCREEN, SCREEN, START_C, STATUS, app_icon,
                  battle_base, draw_left_shell, draw_right_shell, icon_bitmap, led_bitmap, lens_glass,
                  lens_glint, logo_frames, placeholder_bitmap, ray_frames, screen_bg, star_bitmap,
                  start_ring_frames)
from .config import IS_WIN, key_label
from .detect import usable_refs
from .dexnames import dex_no, poke_display
from .hunter import Hunter
from .imaging import Bitmap, frame_photo, frame_png, save_frame_png
from .notify import Notifier, StreamFiles, check_for_update
from .pages_more import MorePages
from .pages_setup import SetupPages
from .pixel import FONT, KEY_COLOR, PAL, TINY, apply_theme, draw_text, draw_text_grad, hexc
from .script import compile_script, keys_used
from .sounds import Sounds
from .sprites import MAIN_TARGET, SpriteCache, sprite_scale
from .stats import chance, fmt_int, fmt_time, hunt_rate
from .store import (Store, now_iso, record_count, record_loop, record_score, record_session)
from .system import open_url
from .ui import fx
from .ui.toolkit import (Button, DialogBox, DPad, Frames, Group, IconButton, ImageBox,
                         Label, Marquee, MenuBox, MiniScreen, Pic, RoundButton, Sparkles,
                         StartButton, TextBlock, UI)
from .ui.widgets import LCD

TABS = [("hunt", "HUNT"), ("keys", "KEYS"), ("script", "STEPS"), ("area", "AREA"),
        ("check", "CHECK"), ("dex", "DEX"), ("stats", "STATS"), ("log", "LOG"),
        ("alert", "ALERT"), ("more", "MORE")]
TAB_TITLES = {"hunt": "HUNT SETUP", "keys": "EMULATOR KEYS", "script": "STEPS",
              "area": "WATCH AREA", "check": "SHINY CHECK", "dex": "MY HUNTS",
              "stats": "STATS", "log": "SHINY LOG", "alert": "ALERTS", "more": "OPTIONS"}
TAB_HINTS = {
    "hunt": "1. Pokemon, game and emulator window",
    "keys": "2. Your emulator's keyboard keys",
    "script": "3. Steps: the reset loop OddsBreaker plays",
    "area": "4. Where the Pokemon shows up",
    "check": "5. Teach it the normal colours",
    "dex": "All your hunts",
    "stats": "Pace, odds and history",
    "log": "Every shiny you've found",
    "alert": "Discord, phone and stream alerts",
    "more": "Size, colours, sound, hotkeys",
}
STEP_TABS = ["hunt", "keys", "script", "area", "check"]
TAB_ICON = {"script": "script", "more": "more"}


class App(SetupPages, MorePages):
    def __init__(self, root, plat, classic=False, store=None, check_updates=True):
        self.root, self.plat = root, plat
        self.store = store or Store()
        self.first_run = not self.store.exists()
        self.data = self.store.load()
        self.settings = self.data["settings"]
        apply_theme(self.settings.get("theme", "RED"))
        self.q = queue.Queue()
        self.sprites = SpriteCache(self.q)
        self.sounds = Sounds()
        self.sounds.mode = self.settings.get("sound", "ALL")
        self.sounds.volume = self.settings.get("volume", "MED")
        self.sounds.start()
        self.notifier = Notifier(self.q)
        self.stream = StreamFiles()
        self.hunter = None
        self.testing = False
        self.hstate = "stopped"
        self.checking = False
        self.view = "normal"
        self.alert = None
        self.celebrating = None
        self.session_count = 0
        self.session_time = 0.0
        self.session_start = None
        self.session_base = 0
        self.session_time_base = 0.0
        self.last_score = None
        self.dirty = False
        self.save_due = None
        self.last_save = time.monotonic()
        self.last_tick = time.monotonic()
        self.hint_text = None
        self.panel_open = False
        self.panel_pos = 0.0
        self.panel_anim = None
        self.panel_shift = 0
        self.shake_off = (0, 0)
        self.tab = "hunt"
        self.text_mode = False
        self.area_live = True
        self.area_black = False
        self.win_cache = (0.0, None, None)
        self.timers = {}
        self.confirm = {}
        self.ready_items = []
        self.sprite_photos = {}
        self.live_photo = None
        self.check_frame = None
        self.prev_map = None
        self.alert_photo = None
        self.picker_row = None
        self.picker_sel = []
        self.log_sel = -1
        self.log_photo = None
        self.log_entries = []
        self.asking = None
        self.bob = 0
        self.anim_frames = None
        self.anim_key = None
        self.anim_i = 0
        self.anim_next = 0.0
        self.shiny_sound_at = 0.0
        self.hotkeys = None
        self.hotkey_failed = []
        self.update_info = None
        self.mini = None
        self.prompt_cb = None
        self.later_msgs = []
        self.testing_alerts = False
        self.manual_update_check = False
        self.idle_next = {"glint": time.monotonic() + 3.0, "logo": time.monotonic() + 1.4}
        self.borderless = (IS_WIN and not classic and self.settings.get("frame") == "POKEDEX")
        self.S = self.pick_scale()
        self.boot = None
        self.after_boot = []
        if self.first_run or not self.data.get("welcomed"):
            self.data["welcomed"] = True
            self.after_boot.append((200, self.welcome))
            self.changed()
        elif not self.settings.get("legacy_checked"):
            self.after_boot.append((400, self.offer_legacy_import))
        if check_updates and self.settings.get("updates", True):
            # every start: a new version shows up the first time you open it
            self.after_boot.append((1200, self.check_updates_on_start))
        self.setup_window()
        self.build(boot=True)
        self.start_hotkeys()
        if self.boot is None:
            self.boot_finished()

    # ------------------------------------------------------------ window
    def pick_scale(self):
        s = int(self.settings.get("scale") or 0)
        sh = self.root.winfo_screenheight()
        if s not in (1, 2, 3, 4):
            dpi = self.root.winfo_fpixels("1i")
            s = 2 if dpi < 130 else (3 if dpi < 200 else 4)
        while s > 1 and DEX_H * s > sh - 50:
            s -= 1
        return s

    def setup_window(self):
        r = self.root
        r.title(APP_NAME)
        r.resizable(False, False)
        try:
            self.icons = [app_icon(32).scaled(2).photo(1), app_icon(32).photo(1), app_icon(16).photo(1)]
            r.iconphoto(True, *self.icons)
        except Exception:
            pass
        if self.borderless:
            try:
                r.overrideredirect(True)
                r.configure(bg=KEY_COLOR)
                r.attributes("-transparentcolor", KEY_COLOR)
                r.update_idletasks()
                if self.plat.make_app_window(r):
                    r.withdraw()
                    r.after(40, r.deiconify)
            except Exception:
                traceback.print_exc()
                self.borderless = False
                try:
                    r.overrideredirect(False)
                except tk.TclError:
                    pass
        if not self.borderless:
            r.configure(bg="#1B1B22")
        try:
            r.attributes("-topmost", bool(self.settings.get("topmost")))
        except tk.TclError:
            pass
        r.protocol("WM_DELETE_WINDOW", self.on_close)
        r.bind("<KeyPress>", lambda e: self.ui.key(e))
        r.bind("<KeyRelease>", lambda e: self.ui.keyup(e))
        vx, vy, vw, vh = self.plat.virtual_screen()
        pos = self.settings.get("pos") or ""
        m = re.match(r"^\+(-?\d+)\+(-?\d+)$", pos)
        x = y = None
        if m:
            x, y = int(m.group(1)), int(m.group(2))
            if not (vx - 40 <= x <= vx + vw - 120 and vy - 10 <= y <= vy + vh - 120):
                x = y = None
        if x is None:
            x = vx + max(0, (r.winfo_screenwidth() - (LEFT_W + PANEL_W) * self.S) // 2)
            y = vy + max(0, (r.winfo_screenheight() - DEX_H * self.S) // 2 - 20)
        self.win_x, self.win_y = x, y
        self.apply_geometry()

    def apply_geometry(self):
        S = self.S
        vis = int(round(PANEL_W * min(1.0, self.panel_pos)))
        x = self.win_x - int(round(self.panel_shift * min(1.0, self.panel_pos))) + self.shake_off[0]
        y = self.win_y + self.shake_off[1]
        try:
            self.root.geometry("%dx%d+%d+%d" % ((LEFT_W + vis) * S, DEX_H * S, x, y))
        except tk.TclError:
            pass

    def window_moved(self):
        self.win_x, self.win_y = self.root.winfo_x(), self.root.winfo_y()
        self.panel_shift = 0
        self.settings["pos"] = "+%d+%d" % (self.win_x, self.win_y)
        self.changed()

    def can_drag(self, x, y):
        ix, iy = int(x), int(y)
        if self.left_shell.bmp.alpha(ix, iy):
            return True
        if self.panel_pos > 0:
            px = ix - int(self.g_panel.ox())
            return bool(self.panel_shell.bmp.alpha(px, iy))
        return False

    def minimize(self):
        if not self.plat.minimize(self.root):
            try:
                self.root.iconify()
            except tk.TclError:
                pass

    def bring_to_front(self):
        try:
            if self.mini is not None:
                self.exit_mini()
            self.plat.restore(self.root)
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(1500, lambda: self.root.attributes(
                "-topmost", bool(self.settings.get("topmost"))))
            self.plat.flash(self.root)
        except tk.TclError:
            pass

    def fx_on(self, level="full"):
        e = self.settings.get("effects", "FULL")
        if e == "OFF":
            return False
        if level == "full":
            return e == "FULL"
        return True

    # ------------------------------------------------------------ build
    def build(self, boot=False):
        bg = KEY_COLOR if self.borderless else "#1B1B22"
        self.ui = UI(self.root, self.S, LEFT_W + PANEL_W, DEX_H, bg, self)
        ui = self.ui
        self.sprite_photos = {}
        self.g_panel = Group(ui, ui.top, x=LEFT_W - PANEL_W + int(round(PANEL_W * self.panel_pos)),
                             visible=self.panel_pos > 0)
        self.g_left = Group(ui, ui.top)
        self.build_panel()
        self.build_left()
        self.particles = fx.Particles(ui)
        ui.anims.append(self.poll)
        self.load_profile_ui()
        if self.panel_pos > 0:
            self.open_tab(self.tab, quiet=True)
        if boot and self.fx_on("lite"):
            from .boot import Boot
            self.boot = Boot(self, lid=self.fx_on("full"))
        ui.start()
        self.root.after(2500, self.prepare_rays)

    @property
    def booting(self):
        return self.boot is not None and not self.boot.done

    def skip_boot(self):
        if self.booting:
            self.boot.finish(chime=True)

    def boot_finished(self):
        """The start-up show is over (or was skipped, or effects are off)."""
        self.idle_next["logo"] = time.monotonic() + 0.4
        tasks, self.after_boot = self.after_boot, []
        for delay, fn in tasks:
            self.root.after(delay, fn)

    def screen_color(self):
        return hexc("#0B1220") if self.screen_mode() == "live" else hexc("#F4FBEF")

    def build_left(self):
        ui, g, P = self.ui, self.g_left, PAL
        shell = draw_left_shell()
        self.left_shell = Pic(ui, g, 0, 0, shell)

        def over_shell(bmp, x, y):
            # Opaque frames (sprite pasted on the plastic behind it) are much
            # cheaper for Tk than images with see-through pixels.
            bg = shell.crop(x, y, bmp.w, bmp.h)
            bg.blit(bmp, 0, 0)
            return bg

        lx, ly = LENS_C[0] - 17, LENS_C[1] - 17
        glass = [lens_glass(i / 5.0) for i in range(6)]
        lens_frames = [over_shell(b, lx, ly) for b in glass]
        for i in range(1, 8):
            f = glass[0].copy()
            f.blit(lens_glint(i), 0, 0)
            lens_frames.append(over_shell(f, lx, ly))
        self.lens = Frames(ui, g, lx, ly, lens_frames)
        self.glint_t0 = None
        self.leds = {}
        for k, x, y in LEDS:
            self.leds[k] = Frames(ui, g, x - 5, y - 5,
                                  [over_shell(led_bitmap(k, i), x - 5, y - 5) for i in range(3)])
        self.logo = Frames(ui, g, 64, 24, [over_shell(b, 64, 24) for b in logo_frames(12)])
        if self.borderless:
            mini_icon = Bitmap(7, 5)
            mini_icon.frame(0, 0, 7, 5, PAL["white"])
            mini_icon.rect(0, 0, 7, 2, PAL["white"])
            Button(ui, g, 141, 4, 13, 11, "", self.enter_mini, "shell", "Mini mode: a small counter",
                   icon=mini_icon)
            Button(ui, g, 156, 4, 13, 11, "-", self.minimize, "shell", "Minimize", TINY)
            Button(ui, g, 171, 4, 13, 11, "×", self.on_close, "shell", "Close " + APP_NAME, TINY)
        else:
            mini_icon = Bitmap(7, 5)
            mini_icon.frame(0, 0, 7, 5, PAL["white"])
            mini_icon.rect(0, 0, 7, 2, PAL["white"])
            Button(ui, g, 171, 4, 13, 11, "", self.enter_mini, "shell", "Mini mode: a small counter",
                   icon=mini_icon)
        sx, sy, sw, sh = SCREEN
        day = screen_bg(sw, sh, "day")
        day_base = day.copy()
        day_base.blit(battle_base(84), (sw - 84) // 2, sh - 25)
        # frames: 0 = day with the battle base, 1 = night (live view), 2 = plain day
        self.scr_bg = Frames(ui, g, sx, sy, [day_base, screen_bg(sw, sh, "night"), day])
        self.rays = None
        self.rays_player = None
        self.sprite = ImageBox(ui, g, sx, sy + 14, sw, sh - 30, cb=lambda x, y: self.cycle_view(),
                               hint="Click: normal / shiny / live view", anchor="bottom")
        stars = [star_bitmap(i, P["gold"], P["white"]) for i in range(4)]
        self.sparkles = Sparkles(ui, g, sx, sy + 10, sw, sh - 22,
                                 [(22, 16), (118, 24), (112, 64), (30, 62), (98, 10), (62, 76)], stars)
        self.scr_head = Label(ui, g, sx + 6, sy + 4, 100, 9, "", P["scr_ink"])
        self.scr_badge = Label(ui, g, sx + sw - 42, sy + 5, 36, 7, "", P["scr_dim"], TINY, align="right")
        self.scr_msg = TextBlock(ui, g, sx + 12, sy + 40, sw - 24, 30, "", P["scr_ink"])
        self.scr_foot = Label(ui, g, sx + 6, sy + sh - 10, sw - 12, 7, "", P["scr_dim"], TINY)
        self.banner = Pic(ui, g, sx + (sw - 92) // 2, sy + 14, self.banner_bitmap())
        self.banner.show(False)
        self.dialog = DialogBox(ui, g, sx + 2, sy + sh - 40, sw - 4, 38)
        self.menu = MenuBox(ui, g, sx + sw - 76, sy + 14, 72, [("caught", "CAUGHT!"), ("phase", "PHASE"),
                                                              ("false", "NOT SHINY")], self.alert_pick)
        self.fizzle = fx.BlockDissolve(ui, g, sx, sy, sw, sh)
        self.scanner = fx.Scanner(ui, g, sx, sy + 11, sw, sh - 22)
        self.view_btn = RoundButton(ui, g, 25, 194, self.cycle_view, "Screen: normal / shiny / live view")
        self.lcd = LCD(ui, g, *LCD_IN)
        rx, ry = START_C[0] - 19, START_C[1] - 19
        self.start_ring = Frames(ui, g, rx, ry, [over_shell(f, rx, ry) for f in start_ring_frames()])
        self.start_ring.show(False)
        self.start_btn = StartButton(ui, g, START_C[0] - 16, START_C[1] - 16, self.toggle_hunt,
                                     self.start_hint(), r=16)
        self.dpad = DPad(ui, g, DPAD_XY[0], DPAD_XY[1], self.on_dpad,
                         "◀ ▶ switch hunt   ▲ add 1   ▼ take 1 off")
        (fx1, fy1), (fx2, fy2), (fx3, fy3), (fx4, fy4) = FACE_XY
        self.face_btns = {
            "setup": Button(ui, g, fx1, fy1, 38, 16, "SETUP", lambda: self.toggle_panel("hunt"),
                            "blue", "Unfold the setup panel for this hunt"),
            "dex": Button(ui, g, fx2, fy2, 38, 16, "DEX", lambda: self.toggle_panel("dex"),
                          "blue", "All your hunts"),
            "log": Button(ui, g, fx3, fy3, 38, 16, "LOG", lambda: self.toggle_panel("log"),
                          "blue", "Shinies you've found"),
            "view": Button(ui, g, fx4, fy4, 38, 16, "VIEW", self.cycle_view,
                           "blue", "Screen: normal / shiny / live view"),
        }
        x, y, w, h = STATUS
        self.status = Marquee(ui, g, x + 3, y + 2, w - 6, h - 4)

    def banner_bitmap(self, text="SHINY!"):
        P = PAL
        w = FONT.width(text, 2) + 8
        b = Bitmap(w, 22)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1),
                       (1, 2), (2, 2), (0, 2), (2, 3), (1, 3)):
            draw_text(b, 3 + dx, 3 + dy, text, P["gold_xd"], FONT, 2)
        draw_text_grad(b, 3, 3, text, [P["white"], P["gold_hi"], P["gold"], P["gold"],
                                       P["gold_md"], P["gold_dk"]], FONT, 2)
        return b

    def build_panel(self):
        ui, g, P = self.ui, self.g_panel, PAL
        self.panel_shell = Pic(ui, g, 0, 0, draw_right_shell())
        # page header
        cx0, _cy0, cw, _ch = CONTENT
        right = cx0 + cw
        self.hdr_icon = Pic(ui, g, cx0, 60, icon_bitmap("hunt", P["cyan"]))
        self.hdr_title = Label(ui, g, cx0 + 11, 60, 120, 8, "", P["cyan"])
        self.hdr_sub = Label(ui, g, right - 86, 61, 54, 6, "", P["dim"], TINY, align="right")
        self.help_btn = IconButton(ui, g, right - 28, 58, "?", self.open_help, "Help for this page")
        self.fold_btn = IconButton(ui, g, right - 13, 58, "×", self.close_panel, "Fold the panel (Esc)")
        line = Bitmap(cw, 1)
        for i in range(cw):
            if i < cw * 2 // 3 or (i % 2 == 0 and i < cw * 8 // 9) or (i % 4 == 0):
                line.px(i, 0, P["line"])
        Pic(ui, g, cx0, 73, line)
        # keys
        self.tab_btns = {}
        for i, (key, label) in enumerate(TABS):
            col, row = i % 5, i // 5
            self.tab_btns[key] = Button(ui, g, KEY_X0 + col * (KEY_W + KEY_GAP), KEYS_Y[row], KEY_W, KEY_H,
                                        label, (lambda k=key: self.open_tab(k)), "blue", TAB_HINTS[key],
                                        FONT)
        (ax, ay, aw, ah), (bx, by, bw, bh) = MINIS
        self.mini_l = MiniScreen(ui, g, ax + 3, ay + 3, aw - 6, ah - 6, cb=self.goto_next_step,
                                 hint="Click to jump to the next setup step")
        self.mini_r = MiniScreen(ui, g, bx + 3, by + 3, bw - 6, bh - 6, cb=lambda: self.open_tab("stats"),
                                 hint="Stats for this hunt")
        self.tabs = {}
        for key, _l in TABS:
            self.tabs[key] = Group(ui, g, visible=False)
        self.build_tab_hunt()
        self.build_tab_keys()
        self.build_tab_script()
        self.build_tab_area()
        self.build_tab_check()
        self.build_tab_dex()
        self.build_tab_stats()
        self.build_tab_log()
        self.build_tab_alert()
        self.build_tab_more()
        self.build_picker()
        self.build_overlay()
        x, y, w, h = PSCREEN
        self.blinds = fx.Blinds(ui, g, x, 75, w, y + h - 75, P["dark"], bands=9)

    # -- helpers for building pages
    def cap(self, group, x, y, text, w=180, color=None, align="left"):
        return Label(self.ui, group, x, y, w, 6, text, color or PAL["dim"], TINY, align=align)

    # ------------------------------------------------------------ data
    @property
    def profile(self):
        for p in self.data["profiles"]:
            if p["id"] == self.data["active"]:
                return p
        return self.data["profiles"][0]

    def changed(self):
        self.dirty = True
        self.save_due = time.monotonic() + 1.2

    def save(self):
        try:
            self.store.save(self.data)
            self.dirty = False
        except Exception:
            traceback.print_exc()
        self.last_save = time.monotonic()
        self.save_due = None

    def load_profile_ui(self):
        """Push the active hunt's values into every widget."""
        self.load_setup_pages()
        self.load_more_pages()
        self.last_score = None
        self.update_ready(force=True)
        self.refresh_screen()
        self.update_lcd(animate=False)

    # ------------------------------------------------------------ main loop
    def poll(self, now):
        if not self.ui.alive:
            return False
        self.drain()
        dt = min(1.0, now - self.last_tick)
        self.last_tick = now
        if self.hstate == "running" and self.hunter is not None and not self.testing:
            self.hunter.profile["seconds"] += dt
            self.session_time += dt
            lim = float(self.settings.get("autostop") or 0)
            if lim > 0 and self.session_time - self.session_time_base >= lim * 3600:
                self.stop_hunt(reason="autostop")
        self.animate(now)
        if self.due("lcd", now, 0.2):
            self.update_lcd()
            self.update_status()
        if self.view == "live" and not self.alert and self.due("live", now, 0.3):
            self.update_live()
        if self.panel_open and self.panel_anim is None:
            if self.tab == "check" and self.due("check", now, 0.25):
                self.update_check_live()
            if self.tab == "area" and self.area_live and self.due("area", now, 0.6):
                self.update_area_snapshot()
            if self.tab == "hunt" and self.due("win", now, 2.5) and not self.in_poke.focused:
                self.refresh_windows(quiet=True)
            if self.tab == "stats" and self.due("stats", now, 1.0):
                self.refresh_stats()
        if self.due("ready", now, 1.0):
            self.update_ready()
        if self.settings.get("stream") and self.due("stream", now, 1.0):
            self.update_stream_files()
        if self.alert and now - self.shiny_sound_at > 3.0:
            self.shiny_sound_at = now
            self.sound("shiny")
        if self.mini is not None:
            self.mini.update(now)
        if self.save_due and now >= self.save_due:
            self.save()
        elif self.hunter is not None and now - self.last_save > 15:
            self.save()
        return True

    def due(self, key, now, every):
        if now >= self.timers.get(key, 0):
            self.timers[key] = now + every
            return True
        return False

    def animate(self, now):
        booting = self.booting
        blink = int(now * 6) % 2 == 0
        lv = {"r": 0, "y": 0, "g": 0}
        if booting:
            lv = self.boot.leds or lv
        elif self.alert or self.celebrating:
            ph = int(now * 10) % 3
            lv = {"r": 2 if ph == 0 else 1, "y": 2 if ph == 1 else 1, "g": 2 if ph == 2 else 1}
        elif self.testing:
            lv["y"] = 2
            lv["r"] = 2 if (self.checking and blink) else 0
        elif self.hstate == "running":
            lv["g"] = 2
            lv["r"] = 2 if (self.checking and blink) else 0
        elif self.hstate == "paused":
            lv["y"] = 2 if blink else 0
            lv["g"] = 1
        elif not [it for it in self.ready_items if not it[1]]:
            lv["g"] = 1 if int(now * 1.2) % 2 == 0 else 0
        for k, w in self.leds.items():
            w.set_frame(lv[k])
        # idle shine on the lens and the logo
        if self.fx_on("lite") and not booting:
            if now >= self.idle_next["glint"]:
                self.idle_next["glint"] = now + 6.5
                if self.hunter is None and not self.alert:
                    self.glint_t0 = now
            if now >= self.idle_next["logo"]:
                self.idle_next["logo"] = now + 9.0
                self.play_logo()
        if booting:
            self.lens.set_frame(self.boot.lens)
        elif self.alert or self.celebrating:
            self.lens.set_frame(5 if blink else 2)
        elif self.hstate == "running":
            self.lens.set_frame(int((math.sin(now * 3.0) + 1) / 2 * 5.99))
        elif self.glint_t0 is not None and now - self.glint_t0 < 7 / 22.0:
            self.lens.set_frame(6 + int((now - self.glint_t0) * 22))
        else:
            self.glint_t0 = None
            self.lens.set_frame(0)
        # start button: pulse when ready, spinning ring while hunting
        running = self.hunter is not None
        self.start_ring.show(running and self.fx_on("lite"))
        if running:
            self.start_ring.set_frame(int(now * 14) % 8)
        ready = not [it for it in self.ready_items if not it[1]]
        self.start_btn.set_glow(1 if (ready and not running and int(now * 1.6) % 2 == 0
                                      and self.fx_on("lite")) else 0)
        # moving sprite
        if self.anim_frames and (not self.alert or self.celebrating) and now >= self.anim_next:
            self.anim_i = (self.anim_i + 1) % len(self.anim_frames)
            photo, delay = self.anim_frames[self.anim_i]
            self.sprite.set_photo(photo)
            self.anim_next = now + delay / 1000.0
        bob = 1 if (int(now * 2.2) % 2 == 0 and self.view in ("normal", "shiny") and not self.alert
                    and not self.anim_frames and not self.celebrating) else 0
        if bob != self.bob:
            self.bob = bob
            self.sprite.set_bob(bob)
        self.scanner.set_on(self.checking and self.view == "live" and not self.alert
                            and self.fx_on("lite"))

    def play_logo(self):
        frames = list(range(1, 13)) + [0]

        def step(now, t0=time.monotonic()):
            k = int((now - t0) * 26)
            if k >= len(frames):
                self.logo.set_frame(0)
                return False
            self.logo.set_frame(frames[k])
            return "fast"
        self.ui.anims.append(step)

    def drain(self):
        for _ in range(500):
            try:
                item = self.q.get_nowait()
            except queue.Empty:
                break
            src, typ, args = item[0], item[1], item[2:]
            try:
                self.handle(src, typ, args)
            except Exception:
                traceback.print_exc()

    def handle(self, src, typ, args):
        stale = src is not None and src is not self.hunter
        if typ == "state":
            if stale:
                return
            if args[0] == "stopped":
                self.hunt_ended()
            else:
                self.hstate = args[0]
            self.start_btn.set_running(self.hunter is not None)
            self.update_status()
        elif typ == "checking":
            if not stale:
                self.checking = args[0]
        elif typ == "step":
            if not stale:
                self.editor.set_running(args[0] - 1 if args[0] else None)
        elif typ == "check":
            self.last_score = args[0]
            if not args[1]:
                record_score(src.profile, args[0])
        elif typ == "count":
            self.on_count(src.profile)
        elif typ == "loop":
            if not src.test:
                record_loop(src.profile, args[0])
        elif typ == "shiny":
            self.on_shiny(src, args[0])
        elif typ == "error":
            self.on_error(args[0])
        elif typ == "test_check":
            self.last_score = args[0]
        elif typ == "test_done":
            self.on_test_done(args[0])
        elif typ in ("sprite", "sprite_fail"):
            self.refresh_screen()
            self.refresh_dex()
            if self.mini is not None:
                self.mini.sprite_changed()
        elif typ == "hotkey":
            self.on_hotkey(args[0])
        elif typ == "notify_result":
            self.on_notify_result(*args)
        elif typ == "update":
            self.on_update_found(args[0], args[1])
        elif typ in ("update_none", "update_fail"):
            self.on_update_none(typ, args)

    # ------------------------------------------------------------ feedback
    def sound(self, name):
        self.sounds.play(name)

    def say(self, text, tone="info", sticky=False, duration=4.0):
        self.dialog.say(text, tone, sticky, duration)

    def hint(self, text):
        self.hint_text = text or None
        self.update_status()

    def update_status(self):
        P = PAL
        p = self.profile
        if self.hint_text:
            self.status.set(self.hint_text, P["cyan"])
            return
        name = poke_display(p.get("pokemon") or p["name"])
        if self.alert:
            self.status.set("SHINY FOUND! GO CHECK YOUR EMULATOR!", P["gold"])
        elif self.testing:
            self.status.set("TEST RUN: PLAYING THE STEPS ONCE...", P["yellow"])
        elif self.hstate == "paused":
            self.status.set("PAUSED: CLICK YOUR EMULATOR TO KEEP GOING", P["yellow"])
        elif self.hstate == "running":
            if self.checking:
                self.status.set("LOOKING FOR A SHINY...", P["status_ink"])
            else:
                last = ("   LAST DIFF %.1f%%" % self.last_score) if self.last_score is not None else ""
                self.status.set("HUNTING %s  #%s%s" % (name, fmt_int(p["encounters"] + 1), last),
                                P["status_ink"])
        elif p.get("found"):
            self.status.set("HUNT COMPLETE! PRESS START FOR A NEW ONE", P["gold"])
        else:
            bad = [it for it in self.ready_items if not it[1]]
            if bad:
                self.status.set(bad[0][3], P["yellow"])
            else:
                k = self.start_key()
                self.status.set("READY! PRESS START" + (" OR %s" % k if k else ""), P["status_ink"])

    # ------------------------------------------------------------ screen
    def fit_photo(self, bmp, fw=None, fh=None, box_w=None, box_h=None, target=MAIN_TARGET):
        """A Pokemon sprite scaled so every species looks about the same size."""
        fw, fh = fw or bmp.w, fh or bmp.h
        k = sprite_scale(fw, fh, self.S, target, box_w or SCREEN[2], box_h or (SCREEN[3] - 30))
        if k == 1.5:
            return bmp.photo(3).subsample(2)
        if k >= 1:
            return bmp.photo(int(k))
        return bmp.photo(1).subsample(int(round(1 / k)))

    def sprite_photo(self, name, shiny):
        """Still sprite photo, or the mystery egg while it downloads."""
        res = self.sprites.lookup(name) if name else None
        if not res:
            key = ("egg", self.S)
            if key not in self.sprite_photos:
                self.sprite_photos[key] = placeholder_bitmap().photo(self.S)
            return self.sprite_photos[key]
        pid, nb, sb = res
        key = (pid, shiny, self.S)
        if key not in self.sprite_photos:
            self.sprite_photos[key] = self.fit_photo(sb if shiny else nb)
        return self.sprite_photos[key]

    def sprite_anim(self, name, shiny):
        pid = dex_no(name) if name else None
        if not pid:
            return None
        frames = self.sprites.anim(pid, shiny)
        if not frames:
            return None
        key = ("anim", pid, bool(shiny), self.S)
        if key not in self.sprite_photos:
            for k in [k for k in self.sprite_photos if k[0] == "anim" and k[1] != pid]:
                del self.sprite_photos[k]
            fw = max(b.w for b, _d in frames)
            fh = max(b.h for b, _d in frames)
            self.sprite_photos[key] = [(self.fit_photo(b, fw, fh), d) for b, d in frames]
        return self.sprite_photos[key]

    def screen_mode(self):
        if self.alert or self.celebrating:
            return "alert"
        v = self.view
        if v == "normal" and self.profile.get("found") and self.hunter is None:
            v = "shiny"
        return v

    def refresh_screen(self):
        P = PAL
        p = self.profile
        name = p.get("pokemon") or ""
        pid = dex_no(name)
        mode = self.screen_mode()
        night = mode == "live"
        if pid:
            # fetch both looks in the background so switching views is instant
            self.sprites.anim(pid, False)
            self.sprites.anim(pid, True)
            self.sprites.lookup(name)
        ink, dim = (P["ink"], P["dim"]) if night else (P["scr_ink"], P["scr_dim"])
        self.scr_head.set(("No.%03d " % pid if pid else "No.--- ") + poke_display(name or p["name"]), ink)
        self.scr_bg.set_frame(1 if night else (2 if mode == "alert" else 0))
        msg = ""
        if mode == "alert":
            self.sprite.anchor = "center"
            anim = self.sprite_anim(name, True) if self.celebrating else None
            if anim:
                akey = ("cele", id(anim))
                if akey != self.anim_key:
                    self.anim_frames, self.anim_key, self.anim_i = anim, akey, 0
                    self.anim_next = time.monotonic() + anim[0][1] / 1000.0
                    self.sprite.set_photo(anim[0][0])
            else:
                self.anim_frames = self.anim_key = None
                photo = self.alert_photo
                if self.celebrating and self.sprites.lookup(name):
                    photo = self.sprite_photo(name, True)
                self.sprite.set_photo(photo)
            self.sprite.set_bob(0)
            self.scr_badge.set("★ SHINY?!", P["gold_dk"])
        elif mode == "live":
            self.anim_frames = self.anim_key = None
            self.sprite.anchor = "center"
            self.sprite.set_bob(0)
            self.scr_badge.set("● LIVE", P["bad"])
            self.sprite.set_photo(self.live_photo)
            if self.live_photo is None:
                msg = self.live_msg()
        else:
            shiny = mode == "shiny"
            self.sprite.anchor = "bottom"
            anim = self.sprite_anim(name, shiny)
            if anim:
                akey = (mode, id(anim))
                if akey != self.anim_key:
                    self.anim_frames, self.anim_key, self.anim_i = anim, akey, 0
                    self.anim_next = time.monotonic() + anim[0][1] / 1000.0
                    self.sprite.set_bob(0)
                    self.sprite.set_photo(anim[0][0])
            else:
                self.anim_frames = self.anim_key = None
                self.sprite.set_photo(self.sprite_photo(name, shiny))
            if p.get("found"):
                self.scr_badge.set("★ CAUGHT", P["gold_dk"])
            else:
                self.scr_badge.set("★ SHINY" if shiny else "NORMAL",
                                   P["gold_dk"] if shiny else P["scr_dim"])
        self.scr_msg.set(msg, ink)
        self.sparkles.set_on(mode in ("shiny", "alert"))
        if p.get("found"):
            f = p["found"]
            n, t = fmt_int(f["encounters"]), fmt_time(f["seconds"])
            options = ("CAUGHT AFTER %s RESETS IN %s" % (n, t), "CAUGHT IN %s RESETS · %s" % (n, t))
        else:
            emu, game = p["emulator"].upper(), p["game"]
            pair = (emu, game) if self.hunter is not None else (game, emu)
            options = ("%s  ·  %s" % pair, "%s · %s" % pair,
                       "%s · %s" % tuple(s.split("/")[0] if s == emu else s for s in pair))
        # the longest wording that fits, so it never ends in "..."
        w = self.scr_foot.w
        self.scr_foot.set(next((s for s in options if TINY.width(s) <= w), options[-1]), dim)

    def transition(self, kind=None):
        """Retro block-fizzle into whatever the screen shows now."""
        if not self.fx_on("full"):
            return
        kind = kind or ("night" if self.screen_mode() == "live" else "day")
        color = {"night": hexc("#0B1220"), "white": PAL["white"]}.get(kind, hexc("#F4FBEF"))
        self.fizzle.play(color, 0.26 if kind != "white" else 0.4)

    def live_msg(self):
        p = self.profile
        if not p["detect"].get("region"):
            return "No watch area yet. SETUP > AREA"
        if not self.find_hwnd(p):
            return "Can't see your emulator window"
        return ""

    def cycle_view(self):
        if self.alert or self.celebrating:
            return
        order = ["normal", "shiny", "live"]
        cur = self.view if self.view in order else "normal"
        if cur == "normal" and self.profile.get("found") and self.hunter is None:
            cur = "shiny"
        self.view = order[(order.index(cur) + 1) % 3]
        self.timers["live"] = 0
        if self.view == "live":
            self.update_live(refresh=False)
        self.refresh_screen()
        self.transition()

    def capture_region(self, p=None):
        """Capture the hunt's watch area; returns a Frame or None."""
        p = p or self.profile
        reg = p["detect"].get("region")
        if not reg:
            return None
        x, y, w, h = reg
        if p["detect"].get("relative", True):
            hwnd = self.find_hwnd(p)
            if not hwnd or self.plat.is_minimized(hwnd):
                return None
            ox, oy = self.plat.client_origin(hwnd)
            x, y = x + ox, y + oy
        try:
            return self.plat.capture(x, y, w, h)
        except Exception:
            return None

    def update_live(self, refresh=True):
        fr = self.capture_region()
        if fr is None:
            self.live_photo = None
        else:
            self.live_photo = frame_photo(fr, SCREEN[2] * self.S, (SCREEN[3] - 24) * self.S)[0]
        if refresh:
            self.refresh_screen()

    def update_lcd(self, animate=True):
        p = self.profile
        n = p["encounters"]
        self.lcd.set_count(n, animate)
        rate = hunt_rate(p, self.session_count, self.session_time) if (
            self.session_time > 20 or p["seconds"] > 60) else None
        odds = p["odds"]
        phases = len(p.get("phases") or [])
        right = ("PHASE %d" % (phases + 1)) if phases else poke_display(p.get("pokemon") or p["name"])
        self.lcd.update(time=int(p["seconds"]), rate=int(round(rate)) if rate else None, odds=odds,
                        chance=chance(n, odds), right=right)
        pid = dex_no(p.get("pokemon") or "")
        # while hunting it saves every 15 s on its own, so that counts as saved
        saved = not self.dirty or (self.hunter is not None and time.monotonic() - self.last_save < 20)
        self.mini_r.set([(("%03d " % pid if pid else "") + poke_display(p.get("pokemon") or p["name"]),
                          PAL["ink"], TINY),
                         ("%s RESETS  %s" % (fmt_int(n), fmt_time(p["seconds"])), PAL["dim"], TINY),
                         (("SAVED ✓" if saved else "SAVING..."),
                          PAL["green"] if saved else PAL["yellow"], TINY)])

    # ------------------------------------------------------------ readiness
    def find_hwnd(self, p=None, fresh=False):
        p = p or self.profile
        t, pat, hwnd = self.win_cache
        now = time.monotonic()
        if (not fresh and pat == p["window"] and now - t < 1.0
                and (hwnd is None or self.plat.window_exists(hwnd))):
            return hwnd
        hwnd = self.plat.find_window(p["window"])
        self.win_cache = (now, p["window"], hwnd)
        return hwnd

    def readiness(self, p=None):
        p = p or self.profile
        d = p["detect"]
        items = []
        hwnd = self.find_hwnd(p)
        items.append(("hunt", bool(hwnd),
                      "Can't find your emulator. Open it, then pick its window on the HUNT page.",
                      "NEXT: OPEN YOUR EMULATOR"))
        steps, errs = compile_script(p["script"], p["keys"])
        key_errs = [e for e in errs if "KEYS page" in e or "unknown key" in e]
        items.append(("keys", not key_errs,
                      (key_errs[0].split(": ", 1)[-1] + ".") if key_errs else "", "NEXT: SET YOUR KEYS"))
        other = [e for e in errs if e not in key_errs]
        has_check = any(s["op"] == "check" for s in steps)
        if other:
            smsg = other[0]
        elif not has_check:
            smsg = "Your steps need a CHECK where the Pokemon appears."
        else:
            smsg = ""
        items.append(("script", not other and has_check and bool(steps), smsg or "Add some steps.",
                      "NEXT: FIX THE STEPS"))
        items.append(("area", bool(d.get("region")),
                      "Draw the watch area: where the Pokemon shows up.", "NEXT: DRAW THE WATCH AREA"))
        if d["mode"] == "compare":
            ok = bool(usable_refs(d))
            msg = "Show me the NORMAL Pokemon: pause on it and press ADD FRAME."
        else:
            ok = bool(d.get("colors"))
            msg = "Pick at least one shiny-only colour."
        items.append(("check", ok, msg, "NEXT: SHOW IT THE NORMAL ONE"))
        return items

    def update_ready(self, force=False):
        self.ready_items = self.readiness()
        P = PAL
        bad = [it for it in self.ready_items if not it[1]]
        if bad:
            nxt = bad[0][0]
            self.mini_l.set([("SETUP %d/5" % (5 - len(bad)), P["yellow"], FONT),
                             ("NEXT: %s ▶" % dict(TABS)[nxt], P["cyan"], TINY)])
        elif self.hunter is not None and not self.testing:
            k = self.start_key()
            self.mini_l.set([("HUNTING ●", P["green"], FONT),
                             (("%s OR START TO STOP" % k) if k else "START TO STOP", P["dim"], TINY)])
        else:
            k = self.start_key()
            self.mini_l.set([("READY ★", P["green"], FONT),
                             ("PRESS START" + (" (%s)" % k if k else ""), P["dim"], TINY)])
        badtabs = set(it[0] for it in bad)
        for key, btn in self.tab_btns.items():
            btn.set_badge(key in badtabs or (key == "more" and bool(self.update_info)))
        self.face_btns["setup"].set_badge(bool(bad))
        self.update_status()

    def start_key(self):
        """The start/stop hotkey as people see it, like 'F8' ('' when unset)."""
        return key_label((self.settings.get("hotkeys") or {}).get("toggle") or "")

    def start_hint(self):
        k = self.start_key()
        return "Start / stop hunting" + (" (%s works anywhere)" % k if k else "")

    def goto_next_step(self):
        bad = [it for it in self.ready_items if not it[1]]
        if bad:
            self.open_tab(bad[0][0])
            self.say(bad[0][2], "info")
        else:
            k = self.start_key()
            self.say("All set! Press START%s to hunt." % (" (or %s)" % k if k else ""), "good")

    # ------------------------------------------------------------ panel
    def toggle_panel(self, tab):
        if self.panel_open and self.tab == tab:
            self.close_panel()
        else:
            self.open_panel(tab)

    def open_panel(self, tab):
        if self.g_pick.visible:
            self.picker_cancel()
        self.open_tab(tab, quiet=True)
        if self.panel_open:
            return
        self.panel_open = True
        self.sound("open")
        vx, vy, vw, vh = self.plat.virtual_screen()
        full = (LEFT_W + PANEL_W) * self.S
        if self.panel_pos == 0:
            self.win_x = self.root.winfo_x()
            self.panel_shift = max(0, self.win_x + full - (vx + vw))
        self.g_panel.set_visible(True)
        self.animate_panel(1.0)

    def close_panel(self):
        if not self.panel_open:
            return
        self.panel_open = False
        self.ui.set_focus(None)
        self.sound("close")
        self.animate_panel(0.0)

    def animate_panel(self, target):
        start = self.panel_pos
        t0 = time.monotonic()
        dur = 0.26 if self.fx_on("lite") else 0.01
        self.txt_box.forced_hidden = True
        self.txt_box.apply_state()

        def step(now):
            if step is not self.panel_anim:
                return False
            t = min(1.0, (now - t0) / dur)
            e = fx.ease_out(t)
            self.set_panel_pos(start + (target - start) * e)
            if t >= 1.0:
                self.panel_anim = None
                if target == 0:
                    self.g_panel.set_visible(False)
                else:
                    self.txt_box.forced_hidden = not (self.text_mode and self.tab == "script")
                    self.txt_box.apply_state()
                    self.on_tab_shown(self.tab)
                    self.key_cascade()
                return False
            return "fast"

        self.panel_anim = step
        self.ui.anims.append(step)

    def key_cascade(self):
        if not self.fx_on("full"):
            return
        t0 = time.monotonic()
        order = [k for k, _l in TABS]

        def step(now):
            k = int((now - t0) / 0.035)
            if k < len(order):
                b = self.tab_btns[order[k]]
                if not b.active:
                    b.flash(0.09)
                return "fast"
            return False
        self.ui.anims.append(step)

    def set_panel_pos(self, pos):
        self.panel_pos = pos
        vis = int(round(PANEL_W * pos))
        self.g_panel.move_to(LEFT_W - PANEL_W + vis, 0)
        self.area.place_box()
        self.apply_geometry()

    def open_tab(self, key, quiet=False):
        if not self.panel_open and not quiet:
            self.open_panel(key)
            return
        changed = key != self.tab
        self.tab = key
        self.ui.set_focus(None)
        self.close_overlay()
        if self.g_pick.visible:
            self.picker_cancel()
        for k, g in self.tabs.items():
            g.set_visible(k == key)
        for k, b in self.tab_btns.items():
            b.set_active(k == key)
        self.hdr_title.set(TAB_TITLES.get(key, key.upper()))
        self.hdr_icon.set(icon_bitmap(TAB_ICON.get(key, key), PAL["cyan"]))
        self.hdr_sub.set("STEP %d/5" % (STEP_TABS.index(key) + 1) if key in STEP_TABS else "")
        self.txt_box.forced_hidden = not (self.text_mode and key == "script" and self.panel_anim is None
                                          and self.panel_pos >= 1)
        self.txt_box.apply_state()
        if self.panel_anim is None and self.panel_pos >= 1:
            self.on_tab_shown(key)
            if changed and not quiet and self.fx_on("full"):
                self.blinds.play()

    def on_tab_shown(self, key):
        self.timers["check"] = self.timers["area"] = 0
        if key == "hunt":
            self.refresh_windows(quiet=True)
        elif key == "area":
            self.update_area_snapshot()
        elif key == "check":
            self.thumbs.set_refs(self.matching_refs())
            self.update_check_live()
        elif key == "dex":
            self.refresh_dex()
        elif key == "stats":
            self.refresh_stats()
        elif key == "log":
            self.refresh_log()
        elif key == "script":
            self.update_script_status()
        elif key == "keys":
            self.update_keys_tab()

    # ------------------------------------------------------------ hunting
    def on_dpad(self, d):
        if d == "up":
            self.bump_manual(1)
        elif d == "down":
            self.bump_manual(-1)
        else:
            self.switch_profile(-1 if d == "left" else 1)

    def bump_manual(self, n):
        p = self.profile
        before = p["encounters"]
        p["encounters"] = max(0, p["encounters"] + n)
        real = p["encounters"] - before
        if real:
            record_count(p, real)
        if n > 0:
            self.session_count += n
        self.changed()
        self.update_lcd()
        if n > 0:
            self.check_milestones(p)

    def on_count(self, p):
        p["encounters"] += 1
        record_count(p, 1)
        self.session_count += 1
        self.changed()
        self.update_lcd()
        self.check_milestones(p)

    def check_milestones(self, p):
        n = p["encounters"]
        every = int(self.settings.get("notify_every") or 0)
        if every and n % every == 0:
            self.notifier.send(self.settings, "%s: %s resets" % (poke_display(p.get("pokemon") or p["name"]),
                                                                fmt_int(n)),
                               "Still hunting. %s so far, %.1f%% chance by now." % (
                                   fmt_time(p["seconds"]), chance(n, p["odds"]) * 100),
                               color=0x5CE1E6)
        if n == p["odds"]:
            self.milestone("%s resets: you hit the odds! Hang in there." % fmt_int(n))
        elif n and n % 1000 == 0:
            self.milestone("%s resets! Keep going!" % fmt_int(n))

    def milestone(self, text):
        self.sound("milestone")
        self.lcd.blink(0.6)
        if self.fx_on("full"):
            x, y, w, h = LCD_IN
            self.particles.burst(x + 40, y + 14, n=24, speed=(30, 80), life=(0.4, 0.9), gravity=90)
        self.say(text, "good", duration=3.5)

    def toggle_hunt(self):
        if self.hunter is not None:
            self.stop_hunt()
        else:
            self.start_hunt()

    def stop_hunt(self, reason=None):
        if self.hunter is None or self.hunter.stop_ev.is_set():
            return
        self.hunter.stop()
        self.sound("stop")
        if reason == "autostop":
            p = self.profile
            self.say("Auto-stop: %s of hunting done. Rest up!" %
                     fmt_time(self.session_time - self.session_time_base), "info", duration=6)
            self.notifier.send(self.settings, "Hunt paused (auto-stop)",
                               "%s: %s resets so far." % (poke_display(p.get("pokemon") or p["name"]),
                                                          fmt_int(p["encounters"])), color=0x7D93A9)

    def hunt_ended(self):
        was_test = self.testing
        h = self.hunter
        self.hunter = None
        self.testing = False
        self.hstate = "stopped"
        self.checking = False
        self.editor.set_running(None)
        if h is not None and not was_test and self.session_start:
            n = self.session_count - self.session_base
            secs = self.session_time - self.session_time_base
            record_session(h.profile, self.session_start, secs, n)
            if n > 0 and not self.alert:
                rate = n * 3600.0 / secs if secs > 30 else 0
                self.say("Session: %s resets in %s%s." % (
                    fmt_int(n), fmt_time(secs), (" (%s/hr)" % fmt_int(rate)) if rate else ""), "info",
                    duration=4)
        self.session_start = None
        self.save()
        if not self.alert and self.view == "live":
            self.view = "normal"
        self.refresh_screen()
        self.start_btn.set_running(False)

    def overlaps_me(self, p, hwnd):
        try:
            x, y, w, h = p["detect"]["region"]
            if p["detect"].get("relative", True):
                ox, oy = self.plat.client_origin(hwnd)
                x, y = x + ox, y + oy
            rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
            rw, rh = self.root.winfo_width(), self.root.winfo_height()
            if not (x + w <= rx or rx + rw <= x or y + h <= ry or ry + rh <= y):
                S = self.S
                for yy in range(max(y, ry), min(y + h, ry + rh), 4):
                    for xx in range(max(x, rx), min(x + w, rx + rw), 4):
                        if self.can_drag((xx - rx) / float(S), (yy - ry) / float(S)):
                            return True
            return False
        except Exception:
            return False

    def start_hunt(self, test=False):
        if self.hunter is not None or self.alert or self.celebrating:
            return
        p = self.profile
        if p.get("found") and not test:
            if not self.confirmed("newhunt"):
                self.say("Already caught! Press START again for a new hunt.", "info")
                return
            self.reset_counter(p)
        self.win_cache = (0.0, None, None)
        items = self.readiness(p)
        need = items if not test else [it for it in items if it[0] in ("hunt", "keys", "script")]
        bad = [it for it in need if not it[1]]
        if bad:
            self.sound("error")
            self.say(bad[0][2], "bad")
            self.open_panel(bad[0][0])
            return
        hwnd = self.find_hwnd(p, fresh=True)
        steps, errs = compile_script(p["script"], p["keys"])
        det = copy.deepcopy(p["detect"])
        refs = usable_refs(det)
        if not test and self.overlaps_me(p, hwnd):
            self.sound("error")
            self.say("I'm covering the watch area! Move me aside.", "bad")
            return
        if test and not det.get("region"):
            steps = [s for s in steps if s["op"] != "check"]
        clash = self.hotkey_clash(p)
        if clash:
            self.say("Heads up: %s is both a game key and a hotkey. Change one on KEYS or MORE." %
                     clash.upper(), "bad", duration=5)
        self.plat.focus(hwnd)
        self.hunter = Hunter(self.plat, hwnd, steps, det, refs, p, self.q, test=test)
        self.testing = test
        self.hstate = "running"
        self.last_tick = time.monotonic()
        if not test:
            self.session_start = now_iso()
            self.session_base = self.session_count
            self.session_time_base = self.session_time
        self.hunter.start()
        self.start_btn.set_running(True)
        self.view = "live"
        self.timers["live"] = 0
        self.sound("start")
        self.dialog.clear()
        self.update_live(refresh=False)
        self.refresh_screen()
        self.transition("night")
        self.update_status()

    def test_loop(self):
        if self.hunter is not None:
            self.say("Stop the hunt first.", "bad", duration=2)
            return
        self.start_hunt(test=True)
        if self.hunter is not None:
            self.say("Test run: playing the steps once. Nothing gets counted.", "info", duration=3)

    def on_test_done(self, info):
        checks = info.get("checks") or []
        secs = info.get("seconds", 0)
        if not checks:
            self.say("Test done: one loop takes about %.1fs. (No CHECK ran: draw the AREA first.)" % secs,
                     "good", duration=6)
        else:
            score, shiny = checks[-1]
            d = self.profile["detect"]
            if d["mode"] == "compare" and not usable_refs(d):
                verdict = "add a normal frame on CHECK next"
            elif shiny:
                verdict = "the CHECK called it SHINY, so check the timing or the red line"
            else:
                verdict = "the CHECK saw a normal one, all good"
            self.say("Test done in %.1fs. Score %.1f%%: %s." % (secs, score or 0, verdict),
                     "good" if not shiny else "bad", duration=8)

    def hotkey_clash(self, p):
        used = keys_used(p["script"], p["keys"])
        for action, combo in (self.settings.get("hotkeys") or {}).items():
            k = (combo or "").split("+")[-1]
            if k and k in used:
                return combo
        return None

    # -- shiny! ---------------------------------------------------------------
    def on_shiny(self, src, payload):
        p = src.profile
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        img_path = None
        png = None
        try:
            paths.ensure(paths.SHINY_DIR)
            base = os.path.join(paths.SHINY_DIR, "%s_%s" % (
                re.sub(r"[^A-Za-z0-9_-]+", "_", p.get("pokemon") or p["name"]), stamp))
            if payload.get("frame") is not None:
                save_frame_png(payload["frame"], base + ".png")
                img_path = base + ".png"
            if payload.get("full") is not None:
                png = frame_png(payload["full"])
                with open(base + "_full.png", "wb") as f:
                    f.write(png)
                img_path = base + "_full.png"
            elif payload.get("frame") is not None:
                png = frame_png(payload["frame"])
        except Exception:
            traceback.print_exc()
        self.alert = {"profile": p, "payload": payload, "image": img_path}
        fr = payload.get("frame")
        self.alert_photo = frame_photo(fr, SCREEN[2] * self.S, (SCREEN[3] - 24) * self.S)[0] \
            if fr is not None else None
        self.dialog.clear()
        self.shiny_sound_at = time.monotonic()
        self.sound("shiny")
        self.save()
        self.bring_to_front()
        name = poke_display(p.get("pokemon") or p["name"])
        self.notifier.send(self.settings, "Shiny %s found!" % name.title(),
                           "After %s resets (%s) in %s." % (fmt_int(p["encounters"]),
                                                             fmt_time(p["seconds"]), p.get("game", "")),
                           png, color=0xFFD93B)
        if self.settings.get("stream"):
            self.stream.update({"status": "SHINY FOUND!"})
        self.celebrate()
        self.update_status()

    def celebrate(self):
        """Flash, rays, a bouncing SHINY! banner and a burst of sparks."""
        sx, sy, sw, sh = SCREEN
        if not self.fx_on("lite"):
            self.show_alert_menu()
            return
        self.celebrating = time.monotonic()
        self.prepare_rays()
        self.rays_player.play(fps=10, loop=True)
        self.refresh_screen()
        self.transition("white")
        self.view = "normal"
        if self.fx_on("full"):
            fx.Shake(self)
            self.particles.burst(sx + sw // 2, sy + sh // 2, n=80, speed=(50, 160), life=(0.7, 1.6),
                                 size=(1, 2, 2, 3))
        bw = self.banner.w
        t0 = time.monotonic()
        self.banner.move(sx + (sw - bw) // 2, sy - 14)
        self.banner.show(True)
        self.scr_head.show(False)
        self.scr_badge.show(False)
        self.ui.cv.tag_raise(self.banner.item)

        def step(now):
            t = (now - t0) / 0.7
            y_to = sy + 3
            if t < 1.0:
                self.banner.move(sx + (sw - bw) // 2, int(sy - 14 + (y_to - sy + 14) * fx.bounce(t)))
            elif now - t0 > 2.2:
                self.banner.show(False)
                self.celebrating = None
                self.show_alert_menu()
                return False
            return "fast"
        self.ui.anims.append(step)

    def prepare_rays(self):
        """The rotating light rays, built ahead of time so a shiny never waits on them."""
        if self.rays is not None or not self.ui.alive:
            return
        sx, sy, sw, sh = SCREEN
        self.rays = Frames(self.ui, self.g_left, sx, sy, ray_frames(sw, sh))
        # keep the rays right above the screen background, under the sprite
        self.ui.cv.tag_lower(self.rays.item, self.sprite.item)
        self.rays_player = fx.FramePlayer(self.ui, self.rays)

    def show_alert_menu(self):
        self.celebrating = None
        self.banner.show(False)
        self.scr_head.show(True)
        self.scr_badge.show(True)
        self.refresh_screen()
        self.menu.sel = 0
        self.menu.show(True)
        self.menu.refresh()
        self.ui.cv.tag_raise(self.menu.item)
        self.dialog.say("WHOA! That looks SHINY! Go check your emulator!", "shiny", sticky=True)
        self.update_status()

    def alert_pick(self, choice):
        a = self.alert
        if not a:
            return
        self.alert = None
        self.menu.show(False)
        self.dialog.clear()
        if self.rays_player is not None:
            self.rays_player.stop()
        p = a["profile"]
        entry = {"date": now_iso(), "profile": p["name"], "pokemon": p.get("pokemon") or p["name"],
                 "game": p.get("game"), "encounters": p["encounters"], "seconds": round(p["seconds"]),
                 "image": a["image"], "score": a["payload"].get("score")}
        if choice == "caught":
            entry["type"] = "Caught"
            p["found"] = {"date": entry["date"], "encounters": p["encounters"],
                          "seconds": p["seconds"], "image": a["image"]}
            self.data["log"].append(entry)
            self.view = "shiny"
            self.sound("ok")
            self.say("Congrats! %s caught after %s resets!" % (poke_display(entry["pokemon"]),
                                                             fmt_int(p["encounters"])), "shiny", duration=6)
            if self.fx_on("full"):
                right = LEFT_W + (PANEL_W if self.panel_open else 0) - 4
                self.particles.rain(4, right, 0, n=110 if self.panel_open else 80)
        elif choice == "phase":
            entry["type"] = "Phase"
            p.setdefault("phases", []).append({"date": entry["date"], "encounters": p["encounters"],
                                               "image": a["image"]})
            self.data["log"].append(entry)
            self.say("Phase logged. Back to hunting!", "info", duration=2)
        else:
            self.say("False alarm. Back to hunting!", "info", duration=2)
        if self.settings.get("stream"):
            self.stream.last.pop("status", None)
        self.changed()
        self.save()
        self.refresh_screen()
        self.transition("day")
        self.refresh_log()
        self.refresh_dex()
        self.update_lcd(animate=False)
        self.update_status()
        if choice in ("phase", "false") and p["id"] == self.profile["id"]:
            self.root.after(600, self.start_hunt)
        for msg in self.later_msgs:
            self.root.after(3000, lambda m=msg: self.say(m, "bad", duration=5))
        self.later_msgs = []

    def on_error(self, msg):
        self.stop_hunt()
        try:
            paths.ensure(paths.DATA_DIR)
            with open(os.path.join(paths.DATA_DIR, "errors.log"), "a", encoding="utf-8") as f:
                f.write("\n[%s]\n%s\n" % (now_iso(), msg))
        except Exception:
            pass
        short = msg.strip().splitlines()[-1] if msg.strip() else "Something went wrong."
        self.sound("error")
        self.say("Hunt stopped: " + short[:90], "bad", duration=6)
        if self.settings.get("notify_errors", True) and not self.testing:
            self.notifier.send(self.settings, "Hunt stopped", short[:200], color=0xFF5A6A)

    # ------------------------------------------------------------ hotkeys
    def start_hotkeys(self):
        if self.hotkeys is not None:
            try:
                self.hotkeys.stop()
            except Exception:
                pass
            self.hotkeys = None
        binds = dict((k, v) for k, v in (self.settings.get("hotkeys") or {}).items() if v)
        try:
            self.hotkeys = self.plat.hotkeys(binds, self.q)
        except Exception:
            traceback.print_exc()
            self.hotkeys = None
        self.hotkey_failed = list(getattr(self.hotkeys, "failed", []) or [])
        for action, slot in getattr(self, "hk_slots", {}).items():
            slot.set_warn(action in self.hotkey_failed)
        if self.hotkey_failed:
            names = ", ".join(self.settings["hotkeys"][a].upper() for a in self.hotkey_failed)
            self.root.after(2500, lambda: self.say(
                "Another app already uses %s. Pick a different hotkey on MORE." % names, "bad",
                duration=6))

    def on_hotkey(self, action):
        combo = (self.settings.get("hotkeys") or {}).get(action) or ""
        key = combo.split("+")[-1]
        if self.hunter is not None and key and self.hunter.sent_recently(key):
            return
        if self.alert is not None:
            return
        if action == "toggle":
            self.toggle_hunt()
        elif action == "plus":
            self.bump_manual(1)
        elif action == "minus":
            self.bump_manual(-1)
        elif action == "mini":
            if self.mini is None:
                self.enter_mini()
            else:
                self.exit_mini()

    def on_key(self, e):
        ks = e.keysym
        if self.alert:
            if ks in ("Up", "Down", "Return", "space", "KP_Enter"):
                if self.menu.visible:
                    self.menu.key_nav(ks)
                return "break"
            return None
        if ks == "Escape":
            if self.overlay_open():
                self.close_overlay()
            elif self.g_pick.visible:
                self.picker_cancel()
            elif self.panel_open:
                self.close_panel()
            return "break"
        if ks == "space":
            self.toggle_hunt()
            return "break"
        if ks in ("plus", "KP_Add", "equal"):
            self.bump_manual(1)
            return "break"
        if ks in ("minus", "KP_Subtract"):
            self.bump_manual(-1)
            return "break"
        if ks in ("Left", "Right") and not self.panel_open:
            self.switch_profile(-1 if ks == "Left" else 1)
            return "break"
        if ks == "F1":
            self.open_help()
            return "break"
        if self.hotkeys is None:
            hk = self.settings.get("hotkeys") or {}
            name = ks.lower()
            for action, combo in hk.items():
                if combo and combo == name:
                    self.on_hotkey(action)
                    return "break"
        return None

    # ------------------------------------------------------------ boot & extras
    def welcome(self):
        self.say("Hi! I'm %s. Let's set up your first hunt!" % APP_NAME, "good")
        self.open_panel("hunt")
        self.root.after(2500, self.offer_legacy_import)

    def update_stream_files(self):
        p = self.profile
        n = p["encounters"]
        name = poke_display(p.get("pokemon") or p["name"]).title()
        rate = hunt_rate(p, self.session_count, self.session_time)
        self.stream.update({
            "encounters": fmt_int(n), "pokemon": name, "time": fmt_time(p["seconds"]),
            "odds": "1/%d" % p["odds"], "chance": "%.1f%%" % (chance(n, p["odds"]) * 100),
            "rate": ("%s/hr" % fmt_int(rate)) if rate else "--/hr",
            "phase": str(len(p.get("phases") or []) + 1),
            "counter": "%s: %s" % (name, fmt_int(n)),
            "status": "SHINY FOUND!" if self.alert else ("Hunting" if self.hunter else "Paused"),
        })
        pid = dex_no(p.get("pokemon") or "")
        if pid and self.stream.last.get("_sprite") != pid:
            path = self.sprites.paths(pid)[0]
            if os.path.exists(path):
                with open(path, "rb") as f:
                    self.stream.write_image("sprite.png", f.read())
                self.stream.last["_sprite"] = pid

    def check_updates_on_start(self):
        """Runs every time the app opens (unless updates are switched off)."""
        if not self.settings.get("updates", True):
            return
        self.settings["last_update_check"] = datetime.date.today().isoformat()
        self.changed()
        check_for_update(self.q)

    def on_update_found(self, tag, url):
        self.update_info = (tag, url)
        self.update_ready()
        self.refresh_about()
        manual, self.manual_update_check = self.manual_update_check, False
        if manual and self.overlay_open():
            return          # the About page now shows a GET button
        quiet = (self.hunter is not None or self.alert or self.celebrating or self.overlay_open()
                 or self.settings.get("update_snoozed") == tag)
        if quiet:
            self.say("Update ready: %s. Get it from MORE > ABOUT." % tag, "good", duration=6)
        else:
            self.offer_update(tag, url)

    def offer_update(self, tag, url):
        def get():
            self.close_overlay()
            open_url(url or RELEASES_URL)

        def later():
            self.settings["update_snoozed"] = tag
            self.changed()
            self.close_overlay()
            self.say("No problem. It's waiting under MORE > ABOUT.", "info", duration=3)

        self.sound("notify")
        self.show_overlay("UPDATE READY!",
                          ["@%s %s IS OUT\n\nDownload it and install it over this one. Your hunts, "
                           "settings and shinies stay right where they are.\n\n~You have %s." %
                           (APP_NAME.upper(), tag.lstrip("vV"), __version__)],
                          [("DOWNLOAD", get, "go"), ("LATER", later, "dark")])

    def on_update_none(self, typ, args):
        if self.manual_update_check:
            self.manual_update_check = False
            if typ == "update_none":
                self.say("You're on the newest version (%s)." % __version__, "good", duration=3)
            else:
                self.say("Couldn't reach GitHub to check for updates.", "bad", duration=3)

    def on_notify_result(self, channel, ok, detail):
        label = {"discord": "Discord", "ntfy": "phone"}.get(channel, channel)
        if ok:
            if self.testing_alerts:
                self.say("Sent a test to %s!" % label, "good", duration=3)
        else:
            msg = "%s alert failed: %s" % (label.title(), detail or "no answer")
            if self.alert or self.celebrating:
                self.later_msgs.append(msg)
            else:
                self.say(msg, "bad", duration=5)
        self.testing_alerts = False

    # ------------------------------------------------------------ mini mode
    def enter_mini(self):
        if self.mini is not None:
            return
        from .mini import MiniWindow
        self.save()
        self.mini = MiniWindow(self)
        try:
            self.root.withdraw()
        except tk.TclError:
            pass

    def exit_mini(self):
        if self.mini is None:
            return
        m, self.mini = self.mini, None
        m.destroy()
        try:
            self.root.deiconify()
            self.root.lift()
        except tk.TclError:
            pass

    # ------------------------------------------------------------ closing
    def on_close(self):
        if self.hunter is not None and not self.testing:
            if not self.confirmed("quit"):
                self.say("Still hunting! Click × again to stop and quit.", "bad", duration=3)
                return
        if self.hunter is not None:
            self.hunter.stop()
            self.hunter.join(1.5)
        if self.hotkeys is not None:
            try:
                self.hotkeys.stop()
            except Exception:
                pass
        try:
            self.settings["pos"] = "+%d+%d" % (self.win_x, self.win_y)
        except Exception:
            pass
        if self.mini is not None:
            try:
                self.settings["mini_pos"] = self.mini.position()
            except Exception:
                pass
        self.save()
        self.ui.alive = False
        self.sounds.close()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def confirmed(self, key, btn=None):
        """First click arms the button ("SURE?"), a second click within 3 s confirms."""
        now = time.monotonic()
        t = self.confirm.get(key)
        if t and now - t[0] < 3.0:
            self.confirm.pop(key, None)
            if btn is not None:
                btn.set_label(t[1])
                btn.set_style(t[2])
            return True
        if btn is not None:
            self.confirm[key] = (now, btn.label, btn.style)
            btn.set_label("SURE?")
            btn.set_style("danger")

            def undo():
                c = self.confirm.get(key)
                if c and time.monotonic() - c[0] >= 2.9:
                    self.confirm.pop(key, None)
                    btn.set_label(c[1])
                    btn.set_style(c[2])
            self.root.after(3000, undo)
        else:
            self.confirm[key] = (now, "", "")
        return False

    def restart(self):
        self.save()
        try:
            import subprocess
            args = [a for a in sys.argv[1:] if a != "--classic"]
            if getattr(sys, "frozen", False):
                cmd = [sys.executable] + args
            else:
                cmd = [sys.executable, "-m", "oddsbreaker"] + args
            subprocess.Popen(cmd, cwd=paths.app_dir())
        except Exception:
            traceback.print_exc()
        self.confirm.pop("quit", None)
        if self.hunter is not None:
            self.hunter.stop()
        self.on_close()

