"""DEX, STATS, LOG, ALERT and OPTIONS pages, plus the help / about overlay."""

import copy
import math
import os
import uuid

import tkinter as tk

from . import APP_NAME, AUTHOR, RELEASES_URL, REPO, REPO_URL, __version__, paths
from .art import PSCREEN
from .config import HOTKEY_ACTIONS, IS_WIN
from .dexnames import POKEDEX_IDS, dex_no, norm_poke_name, poke_display
from .imaging import Bitmap
from .notify import ntfy_url, valid_discord_url
from .pixel import FONT, PAL, THEME_NAMES, TINY, apply_theme, draw_text, ellipsize
from .stats import (chance, daily_series, eta, fmt_dur, fmt_int, fmt_time, hunt_rate, luck,
                    resets_for)
from .store import (default_profile, drop_untouched_starter, export_code, export_csv, import_code,
                    legacy_candidates, merge_legacy, now_iso)
from .system import open_path, open_url
from .ui.toolkit import (Blocker, Button, Cycler, Group, IconButton, ImageBox, KeySlot, Label,
                         ListBox, Pic, TextBlock, TextInput, Toggle, row_highlight)
from .ui.widgets import BarChart, StatCard

X0, W0 = 24, 188      # page content: left edge and width (art pixels)
X1 = X0 + W0          # right edge

HELP = {
    "hunt": ["@HUNT SETUP\nType the Pokemon you're hunting. The game sets the shiny odds, and you can "
             "change them if you have the Shiny Charm or use Masuda.\n\nPick your emulator so its usual "
             "keys load, then pick its window from the list. It has to be open."],
    "keys": ["@EMULATOR KEYS\nEach game button needs the keyboard key your emulator uses for it. "
             "Click a slot, then press the key. Right-click clears a slot.\n\nNot sure? Open your "
             "emulator's input or controls settings and copy what it says."],
    "script": ["@STEPS\nThe steps run top to bottom, over and over.\nPRESS taps buttons.\nHOLD keeps "
               "one down.\nWAIT pauses. MIN and MAX make a random wait, so every reset gets new RNG."
               "\nCHECK looks for the shiny. Each CHECK is one encounter.",
               "@EDITING\nClick a step to edit it. Click the arrows or roll the mouse wheel on a "
               "number (hold Shift for big jumps).\n\nTEST plays the steps once without counting, "
               "so you can watch it work.\n\nTEXT lets you type the steps instead, like:\n"
               "press A x5 gap 0.8\nwait 1~2.5\ncheck 5"],
    "area": ["@WATCH AREA\nThis is a live picture of your emulator. Drag a box around the spot where "
             "the Pokemon appears in battle.\n\nDrag inside the box to move it and drag a corner to "
             "resize it. It saves as soon as you let go.\n\nFREEZE the picture if the game is moving "
             "too much."],
    "check": ["@SHINY CHECK\nCOMPARE: pause your game while the NORMAL Pokemon is on screen and press "
              "ADD FRAME. Animated sprite? Add 2 or 3 frames.\n\nThe live bar shows how different the "
              "screen looks right now. Anything past the red line counts as shiny.",
              "@THE RED LINE\nPut the red line a bit above what a normal one scores.\n\nAfter a few "
              "resets the little chart shows your real scores. SUGGEST moves the line to a safe spot "
              "for you.\n\nCOLOURS mode is the other way around: click colours only the shiny has."],
    "dex": ["@MY HUNTS\nEvery Pokemon gets its own hunt with its own counter, timer, keys, steps and "
            "area.\n\nNEW starts one (keys and steps are copied). SHARE copies a hunt code you can "
            "send a friend, and PASTE adds a hunt from a code."],
    "stats": ["@STATS\nPER HOUR is your real pace. CHANCE is how likely you were to have found it by "
              "now. VS ODDS compares your count to the odds.\n\nEvery reset is a fresh roll, so being "
              "past the odds doesn't make a shiny more likely. It just means you're due some luck."],
    "log": ["@SHINY LOG\nEvery shiny you mark as CAUGHT or PHASE lands here with a screenshot.\n\n"
            "CSV saves your hunts and shinies as spreadsheets."],
    "alert": ["@DISCORD\nIn your server: Server Settings > Integrations > Webhooks > New Webhook > "
              "Copy URL. Paste it here (Ctrl+V) and press TEST.",
              "@PHONE PUSH\nInstall the free ntfy app, subscribe to a topic with a name only you know "
              "(like shiny-hunt-7731) and type the same name here.\n\n@OBS\nTurn on counter files and "
              "add a Text source in OBS that reads from file. encounters.txt holds the count."],
    "more": ["@OPTIONS\nWINDOW SIZE makes the whole device bigger or smaller. SHELL COLOUR changes the "
             "plastic. EFFECTS LITE or OFF helps on slow PCs.\n\nHOTKEYS work from anywhere, even "
             "while your emulator has focus. Pick keys your emulator doesn't use."],
    "general": ["@HOW IT WORKS\n%s plays your game for you: it resets, walks into the battle and looks "
                "at the Pokemon. When the colours look shiny it stops and plays a jingle.\n\n@SET UP "
                "ONCE PER HUNT\n1 HUNT  2 KEYS  3 STEPS  4 AREA  5 CHECK\nThen press START." %
                APP_NAME,
                "@WHILE HUNTING\nIt only presses keys while your emulator is the active window. "
                "Click away and it pauses.\n\nOn a shiny it stops, saves a picture and asks: CAUGHT, "
                "PHASE or NOT SHINY.",
                "@TROUBLESHOOTING\nKeys do nothing: check KEYS. Emulator running as admin? Run "
                "%s as admin too.\nBlack picture: turn off exclusive fullscreen.\nStops on normal "
                "ones: raise the red line.\nNever stops: lower it." % APP_NAME],
}


class MorePages(object):
    # ------------------------------------------------------------ DEX
    def build_tab_dex(self):
        ui, t, P = self.ui, self.tabs["dex"], PAL
        self.cap(t, X0, 80, "CLICK A HUNT TO SWITCH TO IT", 120)
        self.lb_dex_count = Label(ui, t, X1 - 68, 80, 68, 6, "", P["dim"], TINY, align="right")
        self.dex_list = ListBox(ui, t, X0, 90, W0, 126, 14, self.draw_dex_row, self.click_dex_row,
                                "Click a hunt to switch to it")
        self.g_dexbtn = Group(ui, t)
        g = self.g_dexbtn
        q = (W0 - 12) // 4          # four buttons with 4px gaps
        Button(ui, g, X0, 224, q, 15, "+ NEW", self.dex_new, "go", "Start a new hunt")
        Button(ui, g, X0 + (q + 4), 224, q, 15, "COPY", self.dex_copy, "dark",
               "Copy this hunt's setup (keys, steps, area) to a new hunt")
        Button(ui, g, X0 + 2 * (q + 4), 224, q, 15, "RENAME", self.dex_rename, "dark", "Rename this hunt")
        self.btn_del = Button(ui, g, X0 + 3 * (q + 4), 224, q, 15, "DELETE", self.dex_delete, "danger",
                              "Delete this hunt")
        r3 = (W0 - 8) // 3          # three buttons
        self.btn_reset = Button(ui, g, X0, 244, r3, 15, "RESET", self.dex_reset, "dark",
                                "Start this hunt over from zero")
        Button(ui, g, X0 + r3 + 4, 244, r3, 15, "SHARE", self.dex_share, "dark",
               "Copy a hunt code (keys, steps, area) to send to a friend")
        Button(ui, g, X0 + 2 * (r3 + 4), 244, r3, 15, "PASTE", self.dex_paste, "dark",
               "Add a hunt from a hunt code you copied")
        self.g_ask = Group(ui, t, visible=False)
        self.lb_ask = Label(ui, self.g_ask, X0, 224, W0, 6, "", P["cyan"], TINY)
        self.in_ask = TextInput(ui, self.g_ask, X0, 233, W0 - 46, 15, maxlen=24, on_enter=self.ask_done)
        Button(ui, self.g_ask, X1 - 42, 233, 42, 15, "OK", lambda: self.ask_done(self.in_ask.text), "go")
        Button(ui, self.g_ask, X0, 252, 56, 14, "CANCEL", self.ask_cancel, "dark", "")

    def refresh_dex(self):
        profs = self.data["profiles"]
        ids = [p["id"] for p in profs]
        sel = ids.index(self.profile["id"]) if self.profile["id"] in ids else -1
        self.dex_list.set_items(profs, sel)
        found = sum(1 for p in profs if p.get("found"))
        self.lb_dex_count.set("%d HUNT%s · %d ★" % (len(profs), "" if len(profs) == 1 else "S", found))

    def draw_dex_row(self, b, i, p, hover, sel):
        P = PAL
        active = p["id"] == self.data["active"]
        if active:
            row_highlight(b, P["dark3"])
            b.rect(0, 2, 2, b.h - 5, P["cyan"])
        elif hover:
            row_highlight(b, P["dark2"])
        pid = dex_no(p.get("pokemon") or "")
        draw_text(b, 6, 5, ("%03d" % pid) if pid else "---", P["dim"] if not active else P["cyan"], TINY)
        name = ellipsize(p["name"].upper(), 86)
        draw_text(b, 24, 4, name, P["ink"] if (active or hover) else P["dim"])
        right = fmt_int(p["encounters"])
        col = P["dim"]
        if p.get("found"):
            right += " ★"
            col = P["gold"]
        draw_text(b, b.w - 4 - FONT.width(right), 4, right, col)

    def click_dex_row(self, i, x, y):
        p = self.data["profiles"][i]
        if p["id"] == self.data["active"]:
            return
        if self.hunter is not None:
            self.sound("error")
            self.say("Stop the hunt before switching.", "bad", duration=2.5)
            return
        self.sound("ok")
        self.set_active(p["id"])

    def set_active(self, pid):
        if self.hunter is not None:
            return
        self.data["active"] = pid
        self.view = "normal"
        self.live_photo = None
        self.last_score = None
        self.session_count = 0
        self.session_time = 0.0
        self.changed()
        self.load_profile_ui()
        self.transition("day")

    def switch_profile(self, step):
        if self.hunter is not None:
            self.say("Stop the hunt before switching.", "bad", duration=2.5)
            return
        ids = [p["id"] for p in self.data["profiles"]]
        if len(ids) < 2:
            self.say("Only one hunt so far. Add more on DEX.", "info", duration=2.5)
            return
        i = ids.index(self.profile["id"])
        self.set_active(ids[(i + step) % len(ids)])
        self.say("Switched to %s." % self.profile["name"], "info", duration=1.5)

    def ask(self, what, prompt, initial=""):
        self.asking = what
        self.lb_ask.set(prompt)
        self.in_ask.set(initial)
        self.g_dexbtn.set_visible(False)
        self.g_ask.set_visible(True)
        self.ui.set_focus(self.in_ask)

    def ask_cancel(self):
        self.asking = None
        self.g_ask.set_visible(False)
        self.g_dexbtn.set_visible(True)
        self.ui.set_focus(None)

    def ask_done(self, text):
        text = (text or "").strip()
        what = self.asking
        if not text:
            self.ask_cancel()
            return
        cur = self.profile
        if what == "new":
            key = norm_poke_name(text)
            poke = key if key in POKEDEX_IDS else text
            p = default_profile(poke_display(poke).title()[:24], poke, cur["emulator"], cur["game"],
                                cur["odds"])
            p["keys"] = dict(cur["keys"])
            p["window"] = cur["window"]
            p["script"] = copy.deepcopy(cur["script"])
            p["template"] = cur.get("template")
            self.data["profiles"].append(p)
            self.ask_cancel()
            self.set_active(p["id"])
            self.say("New hunt: %s! Keys and steps copied." % p["name"], "good")
        elif what == "rename":
            cur["name"] = text[:24]
            self.changed()
            self.ask_cancel()
            self.refresh_dex()
            self.update_lcd(animate=False)
        self.save()

    def dex_new(self):
        if self.hunter is not None:
            self.say("Stop the hunt first.", "bad", duration=2)
            return
        self.ask("new", "NEW HUNT: WHICH POKEMON?")

    def dex_copy(self):
        if self.hunter is not None:
            self.say("Stop the hunt first.", "bad", duration=2)
            return
        p = copy.deepcopy(self.profile)
        p.update({"id": uuid.uuid4().hex[:12], "name": (p["name"] + " 2")[:24], "encounters": 0,
                  "seconds": 0.0, "phases": [], "found": None, "created": now_iso(), "daily": {},
                  "sessions": [], "scores": []})
        self.data["profiles"].append(p)
        self.set_active(p["id"])
        self.save()
        self.say("Copied! Change the Pokemon on HUNT.", "good")

    def dex_rename(self):
        self.ask("rename", "NEW NAME FOR THIS HUNT:", self.profile["name"])

    def dex_delete(self):
        if self.hunter is not None:
            self.say("Stop the hunt first.", "bad", duration=2)
            return
        if len(self.data["profiles"]) < 2:
            self.say("That's your only hunt!", "bad")
            return
        if not self.confirmed("del", self.btn_del):
            return
        p = self.profile
        self.data["profiles"] = [q for q in self.data["profiles"] if q["id"] != p["id"]]
        self.set_active(self.data["profiles"][0]["id"])
        self.save()
        self.say("Deleted. The shiny log keeps its entries.", "info")

    def dex_reset(self):
        if self.hunter is not None:
            self.say("Stop the hunt first.", "bad", duration=2)
            return
        if not self.confirmed("reset", self.btn_reset):
            return
        self.reset_counter(self.profile)
        self.say("Counter and time are back to zero.", "info")

    def reset_counter(self, p):
        p["encounters"] = 0
        p["seconds"] = 0.0
        p["phases"] = []
        p["found"] = None
        self.session_count = 0
        self.session_time = 0.0
        self.changed()
        self.save()
        self.refresh_screen()
        self.update_lcd(animate=False)
        self.refresh_dex()

    def dex_share(self):
        code = export_code(self.profile)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            self.say("Hunt code copied! Paste it anywhere to share this setup.", "good", duration=3.5)
        except tk.TclError:
            self.say("Couldn't reach the clipboard.", "bad")

    def dex_paste(self):
        if self.hunter is not None:
            self.say("Stop the hunt first.", "bad", duration=2)
            return
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            text = ""
        try:
            p = import_code(text)
        except ValueError as e:
            self.sound("error")
            self.say("%s Copy a code first, then press PASTE." % e, "bad", duration=5)
            return
        self.data["profiles"].append(p)
        self.set_active(p["id"])
        self.save()
        self.say("Added %s from the code! Check KEYS and AREA for your setup." % p["name"], "good",
                 duration=5)

    # ------------------------------------------------------------ STATS
    def build_tab_stats(self):
        ui, t, P = self.ui, self.tabs["stats"], PAL
        self.cards = {}
        specs = [("resets", "RESETS", "Encounters so far"), ("time", "HUNT TIME", "Time spent hunting"),
                 ("rate", "PER HOUR", "Your real pace"), ("chance", "CHANCE", "How likely you were to "
                                                                             "have found it by now"),
                 ("mult", "VS ODDS", "Resets compared to the odds"),
                 ("avg", "PER RESET", "Seconds per reset")]
        cw = (W0 - 8) // 3
        for i, (key, cap, hint) in enumerate(specs):
            c, r = i % 3, i // 3
            self.cards[key] = StatCard(ui, t, X0 + c * (cw + 4), 80 + r * 29, cw, 25, cap, hint)
        self.cap(t, X0, 144, "RESETS PER DAY · LAST 14 DAYS")
        self.chart = BarChart(ui, t, X0, 153, W0, 50, "Resets per day")
        self.tb_pace = TextBlock(ui, t, X0, 211, W0, 22, "", P["ink"], FONT, 10)
        self.tb_all = TextBlock(ui, t, X0, 239, W0, 26, "", P["dim"], TINY, 8)

    def refresh_stats(self):
        P = PAL
        p = self.profile
        n, secs, odds = p["encounters"], p["seconds"], p["odds"]
        rate = hunt_rate(p, self.session_count, self.session_time)
        self.cards["resets"].set(fmt_int(n), P["ink"])
        self.cards["time"].set(fmt_time(secs))
        self.cards["rate"].set(fmt_int(rate) if rate else "--")
        ch = chance(n, odds)
        self.cards["chance"].set("%.1f%%" % (ch * 100), P["gold"] if ch >= 0.5 else P["ink"])
        mult = n / float(odds)
        self.cards["mult"].set("%.2f×" % mult, P["orange"] if mult >= 1 else P["ink"])
        avg = p.get("loop_avg") or (secs / n if n else None)
        self.cards["avg"].set(("%.1fS" % avg) if avg else "--")
        self.chart.set_data(daily_series(p, 14))
        if p.get("found"):
            f = p["found"]
            fn = f["encounters"]
            lk = luck(fn, odds)
            pct = max(1, min(99, int(round(lk * 100))))
            if lk >= 0.5:
                pace = "@FOUND AT %s (%.2f× ODDS)\nLUCKIER THAN %d%% OF HUNTERS" % (
                    fmt_int(fn), fn / float(odds), pct)
            else:
                pace = "@FOUND AT %s (%.2f× ODDS)\nYOU EARNED THAT ONE!" % (fmt_int(fn), fn / float(odds))
        elif rate:
            parts = []
            for target in (0.5, 0.9):
                need = resets_for(target, odds)
                if n < need:
                    parts.append("%d%% IN ~%s" % (int(target * 100), fmt_dur(eta(n, need, rate))))
            if parts:
                pace = "AT THIS PACE\n" + "  ·  ".join(parts)
            else:
                pace = "PAST 90% CHANCE!\nEVERY RESET IS A FRESH ROLL"
        else:
            pace = "~HUNT FOR A BIT AND YOUR\n~PACE SHOWS UP HERE"
        self.tb_pace.set(pace)
        profs = self.data["profiles"]
        tot_e = sum(q["encounters"] for q in profs)
        tot_s = sum(q["seconds"] for q in profs)
        caught = sum(1 for e in self.data["log"] if e.get("type") == "Caught")
        sess = p.get("sessions") or []
        best = max([s["resets"] * 3600.0 / s["seconds"] for s in sess if s.get("seconds", 0) > 60] or [0])
        self.tb_all.set("ALL HUNTS: %s RESETS · %s · %d %s\nTHIS HUNT: %d SESSION%s%s" % (
            fmt_int(tot_e), fmt_time(tot_s), caught, "SHINY" if caught == 1 else "SHINIES",
            len(sess), "" if len(sess) == 1 else "S",
            ("  ·  BEST PACE %s/HR" % fmt_int(best)) if best else ""))

    # ------------------------------------------------------------ LOG
    def build_tab_log(self):
        ui, t, P = self.ui, self.tabs["log"], PAL
        box = Bitmap(80, 60)
        box.rframe(0, 0, 80, 60, 3, P["line"])
        Pic(ui, t, X0, 80, box)
        self.log_img = ImageBox(ui, t, X0 + 1, 81, 78, 58, cb=lambda x, y: self.log_open(),
                                hint="Click to open the full screenshot")
        self.log_info = TextBlock(ui, t, X0 + 88, 82, W0 - 88, 58, "", P["ink"], TINY, 8)
        self.log_list = ListBox(ui, t, X0, 149, W0, 66, 11, self.draw_log_row, self.click_log_row,
                                "Click an entry to see it")
        self.log_list.empty_text = "Shinies you catch show up here with a screenshot."
        r3 = (W0 - 8) // 3
        Button(ui, t, X0, 223, r3, 15, "PICTURE", self.log_open, "dark", "Open the full screenshot")
        Button(ui, t, X0 + r3 + 4, 223, r3, 15, "FOLDER", self.log_folder, "dark", "Open the shinies folder")
        Button(ui, t, X0 + 2 * (r3 + 4), 223, r3, 15, "CSV", self.log_csv, "dark",
               "Save your hunts and shinies as spreadsheets")
        self.lb_log_sum = TextBlock(ui, t, X0, 247, W0, 16, "", P["dim"], TINY, 8)

    def refresh_log(self):
        log = list(reversed(self.data["log"]))
        self.log_entries = log
        if self.log_sel >= len(log):
            self.log_sel = -1
        if self.log_sel < 0 and log:
            self.log_sel = 0
        self.log_list.set_items(log, self.log_sel)
        caught = sum(1 for e in log if e.get("type") == "Caught")
        phases = sum(1 for e in log if e.get("type") == "Phase")
        self.lb_log_sum.set("%d CAUGHT · %d PHASE%s\nALL HUNTS: %s RESETS" % (
            caught, phases, "" if phases == 1 else "S", fmt_int(sum(p["encounters"] for p in self.data["profiles"]))))
        self.show_log_entry()

    def draw_log_row(self, b, i, e, hover, sel):
        P = PAL
        if sel:
            row_highlight(b, P["dark3"])
        elif hover:
            row_highlight(b, P["dark2"])
        caught = e.get("type") == "Caught"
        draw_text(b, 3, 3, "★" if caught else "·", P["gold"] if caught else P["dim"], TINY)
        draw_text(b, 11, 3, ellipsize(poke_display(e.get("pokemon", "")), 70, TINY), P["ink"], TINY)
        draw_text(b, 86, 3, fmt_int(e.get("encounters", 0)), P["dim"], TINY)
        d = (e.get("date") or "")[:10]
        draw_text(b, b.w - 3 - TINY.width(d), 3, d, P["faint"], TINY)

    def click_log_row(self, i, x, y):
        self.log_sel = i
        self.log_list.selected = i
        self.log_list.refresh()
        self.show_log_entry()

    def show_log_entry(self):
        log = self.log_entries
        if not (0 <= self.log_sel < len(log)):
            self.log_img.set_photo(None)
            self.log_info.set("NO SHINIES YET.\nTHEY SHOW UP HERE\nWITH A PICTURE.", PAL["dim"])
            return
        e = log[self.log_sel]
        info = "%s\n%s\n%s RESETS\n%s\n%s\n%s" % (
            poke_display(e.get("pokemon", "")), (e.get("type") or "").upper(),
            fmt_int(e.get("encounters", 0)), fmt_time(e.get("seconds", 0)),
            (e.get("date") or "")[:16], ellipsize((e.get("game") or "").upper(), 96, TINY))
        self.log_info.set(info, PAL["ink"])
        self.log_photo = None
        path = e.get("image")
        if path and os.path.exists(path):
            try:
                img = tk.PhotoImage(file=path)
                S = self.S
                k = max(1, int(math.ceil(max(img.width() / float(76 * S), img.height() / float(56 * S)))))
                if k > 1:
                    img = img.subsample(k)
                self.log_photo = img
            except tk.TclError:
                self.log_photo = None
        self.log_img.set_photo(self.log_photo)

    def log_open(self):
        log = self.log_entries
        if 0 <= self.log_sel < len(log):
            path = log[self.log_sel].get("image")
            if path and os.path.exists(path):
                open_path(path)
                return
        self.say("No picture for that one.", "info", duration=2)

    def log_folder(self):
        open_path(paths.ensure(paths.SHINY_DIR))

    def log_csv(self):
        try:
            folder = os.path.join(paths.DATA_DIR, "exports")
            export_csv(self.data, folder)
            open_path(folder)
            self.say("Saved hunts.csv and shinies.csv.", "good", duration=3)
        except Exception as e:
            self.say("Couldn't save the CSV files: %s" % e, "bad")

    # ------------------------------------------------------------ ALERT
    def build_tab_alert(self):
        ui, t, P = self.ui, self.tabs["alert"], PAL
        tx = X1 - 34          # toggles line up on the right
        self.cap(t, X0, 80, "DISCORD WEBHOOK", 100)
        self.lb_discord = Label(ui, t, X1 - 88, 80, 88, 6, "", P["dim"], TINY, align="right")
        self.in_discord = TextInput(ui, t, X0, 88, W0 - 44, 15, placeholder="Paste webhook URL (Ctrl+V)",
                                    maxlen=220, on_change=self.set_discord, secret=True,
                                    hint="Discord: Server Settings > Integrations > Webhooks > Copy URL")
        Button(ui, t, X1 - 40, 88, 40, 15, "TEST", lambda: self.test_alert("discord"), "dark",
               "Send a test message to Discord")
        self.cap(t, X0, 112, "PHONE PUSH (NTFY TOPIC)", 100)
        self.lb_ntfy = Label(ui, t, X1 - 88, 112, 88, 6, "", P["dim"], TINY, align="right")
        self.in_ntfy = TextInput(ui, t, X0, 120, W0 - 44, 15, placeholder="A secret topic name",
                                 maxlen=120, on_change=self.set_ntfy,
                                 hint="Subscribe to the same topic in the free ntfy app")
        Button(ui, t, X1 - 40, 120, 40, 15, "TEST", lambda: self.test_alert("ntfy"), "dark",
               "Send a test push to your phone")
        self.cap(t, X0, 150, "SEND THE SCREENSHOT TOO", 140)
        self.tg_shot = Toggle(ui, t, tx, 146, True, lambda v: self.set_setting("discord_shot", v),
                              "Attach a picture of the shiny")
        self.cap(t, X0, 170, "ALERT ME IF A HUNT STOPS", 140)
        self.tg_errs = Toggle(ui, t, tx, 166, True, lambda v: self.set_setting("notify_errors", v),
                              "Get a message if the emulator closes or something breaks")
        self.cap(t, X0, 190, "PROGRESS PING EVERY", 100)
        self.cy_every = Cycler(ui, t, X1 - 84, 186, 84, 15,
                               [(0, "OFF"), (100, "100"), (500, "500"), (1000, "1,000"), (5000, "5,000")],
                               0, lambda v: self.set_setting("notify_every", int(v)),
                               "Send a progress message every so many resets")
        self.cap(t, X0, 210, "OBS COUNTER FILES", 140)
        self.tg_stream = Toggle(ui, t, tx, 206, False, self.set_stream,
                                "Write the count, time and odds to text files for OBS")
        Button(ui, t, X0, 228, W0, 15, "OPEN STREAM FOLDER", self.open_stream_folder, "dark",
               "Text files to use as OBS Text (GDI+) sources")
        TextBlock(ui, t, X0, 252, W0, 12,
                  "~Press ? for how to set up Discord, ntfy and OBS.", P["faint"], TINY, 8)

    def set_setting(self, key, value):
        self.settings[key] = value
        self.changed()

    def set_discord(self, text):
        self.settings["discord"] = text.strip()
        self.changed()
        self.update_alert_labels()

    def set_ntfy(self, text):
        self.settings["ntfy"] = text.strip()
        self.changed()
        self.update_alert_labels()

    def update_alert_labels(self):
        P = PAL
        d = self.settings.get("discord") or ""
        if not d:
            self.lb_discord.set("OFF", P["faint"])
        elif valid_discord_url(d):
            self.lb_discord.set("● ON", P["green"])
        else:
            self.lb_discord.set("CHECK THE URL", P["yellow"])
        n = self.settings.get("ntfy") or ""
        if not n:
            self.lb_ntfy.set("OFF", P["faint"])
        elif ntfy_url(n):
            self.lb_ntfy.set("● ON", P["green"])
        else:
            self.lb_ntfy.set("LETTERS AND - ONLY", P["yellow"])

    def test_alert(self, channel):
        s = self.settings
        if channel == "discord" and not valid_discord_url(s.get("discord") or ""):
            self.say("Paste a Discord webhook URL first (it starts with https://discord.com/api/webhooks/).",
                     "bad", duration=5)
            return
        if channel == "ntfy" and not ntfy_url(s.get("ntfy") or ""):
            self.say("Type an ntfy topic name first.", "bad", duration=3)
            return
        self.testing_alerts = True
        p = self.profile
        self.notifier.send(s, "Test from %s" % APP_NAME,
                           "Alerts work! You'll hear from me the moment a shiny %s shows up." %
                           poke_display(p.get("pokemon") or "Pokemon").title(), color=0x5CE1E6,
                           only=channel)
        self.say("Sending a test...", "info", duration=2)

    def set_stream(self, v):
        self.settings["stream"] = bool(v)
        self.changed()
        if v:
            self.stream.last = {}
            self.update_stream_files()
            self.say("Counter files are on. OPEN STREAM FOLDER to find them.", "good", duration=3)

    def open_stream_folder(self):
        paths.ensure(paths.OBS_DIR)
        self.update_stream_files()
        open_path(paths.OBS_DIR)

    # ------------------------------------------------------------ OPTIONS
    def build_tab_more(self):
        ui, t = self.ui, self.tabs["more"]
        self.more_page = "look"
        half = (W0 - 4) // 2
        self.btn_look = Button(ui, t, X0, 80, half, 15, "LOOK + SOUND", lambda: self.more_flip("look"),
                               "dark", "")
        self.btn_sys = Button(ui, t, X1 - half, 80, half, 15, "HUNT + SYSTEM", lambda: self.more_flip("sys"),
                              "dark", "")
        g1 = self.g_look = Group(ui, t)
        rows = [103 + i * 20 for i in range(8)]
        cx, cw, tx = X1 - 90, 90, X1 - 34      # cyclers and toggles line up on the right

        def row(g, i, text):
            self.cap(g, X0, rows[i] + 5, text, 92)

        row(g1, 0, "WINDOW SIZE")
        self.cy_size = Cycler(ui, g1, cx, rows[0], cw, 15, [(s, "%dX" % s) for s in (1, 2, 3, 4)],
                              self.S, self.set_size, "Make the whole device bigger or smaller")
        row(g1, 1, "SHELL COLOUR")
        self.cy_theme = Cycler(ui, g1, cx, rows[1], cw, 15, [(n, n) for n in THEME_NAMES],
                               self.settings.get("theme", "RED"), self.set_theme, "Paint the device")
        row(g1, 2, "EFFECTS")
        self.cy_fx = Cycler(ui, g1, cx, rows[2], cw, 15, [("FULL", "FULL"), ("LITE", "LITE"),
                                                          ("OFF", "OFF")],
                            self.settings.get("effects", "FULL"), self.set_effects,
                            "Animations. LITE or OFF is easier on slow PCs.")
        row(g1, 3, "SOUND")
        self.cy_sound = Cycler(ui, g1, cx, rows[3], cw, 15,
                               [("ALL", "ALL"), ("SHINY ONLY", "SHINY ONLY"), ("OFF", "OFF")],
                               self.settings.get("sound", "ALL"), self.set_sound,
                               "Beeps and the shiny jingle")
        row(g1, 4, "VOLUME")
        self.cy_vol = Cycler(ui, g1, cx, rows[4], cw, 15, [("LOW", "LOW"), ("MED", "MEDIUM"),
                                                           ("HIGH", "HIGH")],
                             self.settings.get("volume", "MED"), self.set_volume, "How loud")
        row(g1, 5, "KEEP ON TOP")
        self.tg_top = Toggle(ui, g1, tx, rows[5], bool(self.settings.get("topmost")), self.set_topmost,
                             "Keep %s above other windows" % APP_NAME)
        row(g1, 6, "WINDOW STYLE")
        self.cy_frame = Cycler(ui, g1, cx, rows[6], cw, 15, [("POKEDEX", "DEVICE"), ("CLASSIC", "CLASSIC")],
                               self.settings.get("frame", "POKEDEX"), self.set_frame,
                               "DEVICE = shaped window. CLASSIC = normal Windows frame.")
        self.btn_restart = Button(ui, g1, X0, 247, W0, 15, "RESTART TO SWITCH STYLE", self.restart,
                                  "go", "Restart %s now" % APP_NAME)
        self.btn_restart.show(False)
        g2 = self.g_sys = Group(ui, t, visible=False)
        self.hk_slots = {}
        for i, (action, label) in enumerate(HOTKEY_ACTIONS):
            row(g2, i, label + " KEY")
            self.hk_slots[action] = KeySlot(
                ui, g2, cx, rows[i], cw, 15, (self.settings.get("hotkeys") or {}).get(action, ""),
                (lambda v, a=action: self.set_hotkey(a, v)),
                "Works from anywhere. Click, press a key. Right-click clears.")
        row(g2, 4, "AUTO-STOP AFTER")
        self.cy_auto = Cycler(ui, g2, cx, rows[4], cw, 15,
                              [(0, "NEVER"), (1, "1 HOUR"), (2, "2 HOURS"), (4, "4 HOURS"),
                               (8, "8 HOURS"), (12, "12 HOURS")],
                              int(self.settings.get("autostop") or 0), self.set_autostop,
                              "Stop the hunt by itself after this long")
        row(g2, 5, "CHECK FOR UPDATES")
        self.tg_upd = Toggle(ui, g2, tx, rows[5], bool(self.settings.get("updates", True)),
                             lambda v: self.set_setting("updates", bool(v)),
                             "Look for a new version on GitHub every time it starts")
        Button(ui, g2, X0, 227, half, 15, "DATA FOLDER", self.open_data_folder, "dark",
               "Your hunts, shiny pictures, backups and settings")
        Button(ui, g2, X1 - half, 227, half, 15, "IMPORT SAVE", self.import_save_dialog, "dark",
               "Bring hunts over from ShinyDex or another computer")
        Button(ui, g2, X0, 247, half, 15, "HELP", lambda: self.open_help("general"), "dark",
               "How it all works")
        self.btn_about = Button(ui, g2, X1 - half, 247, half, 15, "ABOUT", self.open_about, "dark",
                                "Version, credits and updates")
        self.more_flip("look", quiet=True)

    def more_flip(self, page, quiet=False):
        self.more_page = page
        self.g_look.set_visible(page == "look")
        self.g_sys.set_visible(page == "sys")
        self.btn_look.set_active(page == "look")
        self.btn_sys.set_active(page == "sys")
        if not quiet and self.fx_on("full"):
            self.blinds.play(0.14)

    def set_size(self, s):
        self.settings["scale"] = int(s)
        self.changed()
        self.root.after(60, lambda: self.rebuild(int(s)))

    def set_theme(self, name):
        self.settings["theme"] = name
        self.changed()
        self.root.after(60, lambda: self.rebuild(self.S))

    def rebuild(self, s):
        apply_theme(self.settings.get("theme", "RED"))
        self.S = s
        self.particles.clear()
        self.ui.destroy()
        self.txt.destroy()
        self.rays = None
        self.rays_player = None
        self.build()
        self.apply_geometry()
        if self.panel_open:
            self.open_tab(self.tab, quiet=True)

    def set_effects(self, v):
        self.settings["effects"] = v
        self.changed()

    def set_topmost(self, v):
        self.settings["topmost"] = bool(v)
        try:
            self.root.attributes("-topmost", bool(v))
        except tk.TclError:
            pass
        self.changed()

    def set_sound(self, v):
        self.settings["sound"] = v
        self.sounds.mode = v
        self.changed()
        self.sound("ok")

    def set_volume(self, v):
        self.settings["volume"] = v
        self.sounds.volume = v
        self.changed()
        self.sound("ok")

    def set_frame(self, v):
        self.settings["frame"] = v
        self.changed()
        want = v == "POKEDEX" and IS_WIN
        self.btn_restart.show(want != self.borderless)

    def set_hotkey(self, action, v):
        self.settings.setdefault("hotkeys", {})[action] = v
        self.changed()
        if action == "toggle":
            self.start_btn.hint = self.start_hint()
        self.start_hotkeys()
        self.update_keys_tab()
        if v and action in self.hotkey_failed:
            self.hk_slots[action].set_warn(True)
        else:
            self.hk_slots[action].set_warn(False)

    def set_autostop(self, v):
        self.settings["autostop"] = int(v)
        self.changed()

    def open_data_folder(self):
        open_path(paths.ensure(paths.DATA_DIR))

    def import_save_dialog(self):
        try:
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                parent=self.root, title="Pick a profiles.json to import",
                filetypes=[("Hunt save", "profiles.json"), ("JSON files", "*.json")])
        except Exception:
            path = None
        if path:
            self.import_legacy(path)

    def import_legacy(self, path):
        if self.hunter is not None:
            self.say("Stop the hunt first.", "bad", duration=2)
            return
        try:
            added = merge_legacy(self.data, path)
        except Exception as e:
            self.sound("error")
            self.say("Couldn't read that save: %s" % e, "bad")
            return
        if added:
            drop_untouched_starter(self.data)
        self.settings["legacy_checked"] = True
        self.save()
        self.load_profile_ui()
        self.sound("ok")
        self.say("Imported %d hunt%s! They're on the DEX page." % (added, "" if added == 1 else "s")
                 if added else "Nothing new in that save.", "good", duration=4)

    def offer_legacy_import(self):
        if self.settings.get("legacy_checked"):
            return
        try:
            found = legacy_candidates()
        except Exception:
            found = []
        if not found:
            self.settings["legacy_checked"] = True
            self.changed()
            return
        path = found[0]
        if self.overlay_open() or self.alert:
            self.root.after(2500, self.offer_legacy_import)   # don't talk over another prompt
            return
        if not self.panel_open:
            self.open_panel("dex")

        def yes():
            self.close_overlay()
            self.import_legacy(path)

        def no():
            self.close_overlay()
            self.settings["legacy_checked"] = True
            self.changed()

        short = path if len(path) < 60 else "..." + path[-57:]
        self.show_overlay("WELCOME BACK!",
                          ["I found hunts from ShinyDex, the old version of this app:\n\n~%s\n\n"
                           "Bring them over? Counters, steps, areas and the shiny log all come along."
                           % short.replace("\\", "/")],
                          [("IMPORT", yes, "go"), ("NO THANKS", no, "dark")])

    # ------------------------------------------------------------ overlay (help / about / prompts)
    def build_overlay(self):
        ui, P = self.ui, PAL
        g = self.g_over = Group(ui, self.g_panel, visible=False)
        px, py, pw, ph = PSCREEN
        Blocker(ui, g, px, py, Bitmap(pw, ph, P["night"]))
        bx, by, bw, bh = self.ov_box = (px + 8, py + 8, pw - 16, ph - 16)
        box = Bitmap(bw, bh)
        box.rrect(0, 0, bw, bh, 6, P["cyan_dk"])
        box.rrect(1, 1, bw - 2, bh - 2, 5, P["dark2"])
        box.rect(6, 22, bw - 12, 1, P["line"])
        Blocker(ui, g, bx, by, box)
        self.ov_title = Label(ui, g, bx + 10, by + 8, 120, 8, "", P["cyan"])
        self.ov_page = Label(ui, g, bx + bw - 54, by + 9, 44, 6, "", P["dim"], TINY, align="right")
        self.ov_body = TextBlock(ui, g, bx + 10, by + 30, bw - 20, bh - 70, "", P["ink"], FONT, 10)
        self.ov_prev = IconButton(ui, g, bx + 10, by + bh - 26, "◀", lambda: self.overlay_flip(-1),
                                  "Previous page")
        self.ov_next = IconButton(ui, g, bx + 25, by + bh - 26, "▶", lambda: self.overlay_flip(1), "Next page")
        self.ov_btns = [Button(ui, g, 0, by + bh - 28, 52, 15, "", None, "dark", "") for _ in range(3)]
        self.ov_pages = []
        self.ov_i = 0

    def show_overlay(self, title, pages, buttons, sub=""):
        if not self.panel_open:
            self.open_panel(self.tab)
        self.ov_title.set(title)
        self.ov_pages = pages or [""]
        self.ov_i = 0
        multi = len(self.ov_pages) > 1
        self.ov_prev.show(multi)
        self.ov_next.show(multi)
        bx, by, bw, bh = self.ov_box
        x = bx + bw - 10
        for i, b in enumerate(self.ov_btns):
            if i < len(buttons):
                label, cb, style = buttons[i]
                w = max(44, (FONT.width(label) if FONT.width(label) <= 70 else TINY.width(label)) + 14)
                x -= w
                b.w = w
                b.move(x, by + bh - 28)
                b.set_label(label)
                b.cb = cb
                b.set_style(style)
                b.show(True)
                x -= 4
            else:
                b.show(False)
        self.g_pick.set_visible(False)
        self.txt_box.forced_hidden = True
        self.txt_box.apply_state()
        self.g_over.set_visible(True)
        for b in self.ov_btns:
            if b.visible:
                b.refresh()
        self.overlay_flip(0)
        if self.fx_on("full"):
            self.blinds.play(0.16)

    def overlay_flip(self, d):
        self.ov_i = (self.ov_i + d) % len(self.ov_pages)
        self.ov_body.set(self.ov_pages[self.ov_i])
        n = len(self.ov_pages)
        self.ov_page.set("%d/%d" % (self.ov_i + 1, n) if n > 1 else "")

    def overlay_open(self):
        return self.g_over.visible

    def close_overlay(self):
        if self.g_over.visible:
            self.g_over.set_visible(False)
            if self.text_mode and self.tab == "script":
                self.txt_box.forced_hidden = False
                self.txt_box.apply_state()

    def open_help(self, topic=None):
        topic = topic or self.tab
        pages = HELP.get(topic) or HELP["general"]
        btns = [("GOT IT", self.close_overlay, "go")]
        if topic != "general":
            btns.append(("BASICS", lambda: self.open_help("general"), "dark"))
        self.show_overlay("HELP", pages, btns)

    def open_about(self):
        upd = self.update_info
        text = ("@%s %s\nThe automatic shiny hunter for any emulator.\n\nMade by %s.\n"
                "~GitHub: %s\n\n" % (APP_NAME.upper(), __version__, AUTHOR, REPO))
        if upd:
            text += "!UPDATE READY: %s\n\n" % upd[0]
        text += ("~Sprites come from the PokeAPI sprite project. Pokemon belongs to Nintendo, Game "
                 "Freak and Creatures. This free fan project isn't affiliated with them.")
        btns = [("CLOSE", self.close_overlay, "dark")]
        if upd:
            btns.insert(0, ("GET %s" % upd[0], lambda: open_url(upd[1] or RELEASES_URL), "go"))
        else:
            btns.insert(0, ("CHECK NOW", self.check_updates_now, "dark"))
        btns.insert(1, ("GITHUB", lambda: open_url(REPO_URL), "dark"))
        self.show_overlay("ABOUT", [text], btns)

    def refresh_about(self):
        if self.g_over.visible and self.ov_title.text == "ABOUT":
            self.open_about()

    def check_updates_now(self):
        from .notify import check_for_update
        self.manual_update_check = True
        self.say("Checking GitHub for updates...", "info", duration=2)
        check_for_update(self.q)

    # ------------------------------------------------------------ load
    def load_more_pages(self):
        s = self.settings
        self.refresh_dex()
        self.refresh_stats()
        self.refresh_log()
        self.in_discord.set(s.get("discord") or "")
        self.in_ntfy.set(s.get("ntfy") or "")
        self.tg_shot.set(s.get("discord_shot", True))
        self.tg_errs.set(s.get("notify_errors", True))
        self.cy_every.set_value(int(s.get("notify_every") or 0))
        self.tg_stream.set(bool(s.get("stream")))
        self.update_alert_labels()
        for action, slot in self.hk_slots.items():
            slot.set((s.get("hotkeys") or {}).get(action, ""))
            slot.set_warn(action in self.hotkey_failed)
