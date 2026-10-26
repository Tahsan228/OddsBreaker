"""The five setup pages: HUNT, KEYS, STEPS, AREA and CHECK."""

import re

import tkinter as tk

from .art import PSCREEN
from .config import (EMU_NAMES, GAME_NAMES, GAMES, ODDS, TEMPLATE_NAMES, detect_emulator,
                     emulator_preset, norm_key)
from .detect import (is_shiny_score, make_ref, matching_refs, score_frame, suggest_threshold,
                     usable_refs)
from .dexnames import POKEDEX_IDS, norm_poke_name, poke_display, suggest_names
from .imaging import Bitmap, frame_photo
from .pixel import PAL, TINY, draw_text, ellipsize
from .script import (DEF_HOLD, combo_label, compile_script, estimate_loop, fmt_num, parse_script,
                     script_to_text, template_rows)
from .stats import fmt_int
from .system import find_window_in, is_own_title, window_pattern_for
from .ui.toolkit import (Blocker, Button, Cycler, Group, ImageBox, KeySlot, Label, ListBox, Meter,
                         Pic, Stepper, TextBlock, TextInput, row_highlight, step_pct)
from .ui.widgets import AreaSelector, EmbedText, ScriptEditor, Sparkline, Swatches, Thumbs

X0, W0 = 24, 188      # page content: left edge and width (art pixels)
X1 = X0 + W0          # right edge


def frame_box(w, h, col):
    b = Bitmap(w, h)
    b.rframe(0, 0, w, h, 3, col)
    return b


class SetupPages(object):
    # ------------------------------------------------------------ HUNT
    def build_tab_hunt(self):
        ui, t, P = self.ui, self.tabs["hunt"], PAL
        self.cap(t, X0, 80, "POKEMON")
        self.in_poke = TextInput(ui, t, X0, 88, W0, 15, placeholder="Type a Pokemon...", maxlen=24,
                                 on_change=self.poke_typed, on_enter=self.poke_enter,
                                 on_keynav=self.poke_nav, hint="Type the Pokemon you're hunting")
        self.in_poke.on_blur_cb = self.poke_blur
        self.cap(t, X0, 111, "GAME")
        self.cy_game = Cycler(ui, t, X0, 119, W0, 15, [], None, self.set_game,
                              "Which game? (sets the shiny odds)")
        self.cap(t, X0, 142, "SHINY ODDS")
        self.cy_odds = Cycler(ui, t, X0, 150, W0, 15, [], None, self.set_odds,
                              "Full odds, Shiny Charm, Masuda...")
        self.cap(t, X0, 173, "EMULATOR")
        self.cy_emu = Cycler(ui, t, X0, 181, W0, 15, [(n, n) for n in EMU_NAMES], None,
                             self.set_emu, "Your emulator (loads its usual keys)")
        self.cap(t, X0, 204, "EMULATOR WINDOW", 100)
        self.lb_win = Label(ui, t, X1 - 88, 204, 88, 6, "", P["dim"], TINY, align="right")
        self.cy_win = Cycler(ui, t, X0, 212, W0 - 42, 15, [], None, self.set_window,
                             "Pick your emulator's window (it needs to be open)")
        Button(ui, t, X1 - 38, 212, 38, 15, "FIND", self.refresh_windows, "dark",
               "Look for open windows again", TINY)
        TextBlock(ui, t, X0, 238, W0, 26,
                  "~Tip: keep OddsBreaker next to your emulator, not on top of the game. Run the "
                  "emulator in a window, not exclusive fullscreen.", P["faint"], TINY, 8)
        self.sugg = []
        self.sugg_sel = 0
        self.suggest = ListBox(ui, t, X0, 104, W0, 55, 11, self.draw_suggest, None)
        self.suggest.on_press = self.suggest_press
        self.suggest.show(False)

    def draw_suggest(self, b, i, name, hover, sel):
        P = PAL
        b.rect(0, 0, b.w, b.h, P["dark3"])
        if hover or i == self.sugg_sel:
            row_highlight(b, P["dark5"])
        draw_text(b, 4, 3, "%03d" % POKEDEX_IDS.get(name, 0), P["dim"], TINY)
        draw_text(b, 22, 2, poke_display(name), P["ink"])

    def poke_typed(self, text):
        self.sugg = suggest_names(text, 5)
        self.sugg_sel = 0
        self.sugg_moved = False
        self.suggest.set_items(self.sugg)
        self.suggest.h = 11 * max(1, len(self.sugg))
        exact = len(self.sugg) == 1 and self.sugg[0] == norm_poke_name(text)
        self.suggest.show(bool(self.sugg) and self.in_poke.focused and not exact)
        if self.suggest.visible:
            self.ui.cv.tag_raise(self.suggest.item)

    def poke_nav(self, ks):
        if not self.sugg:
            return
        if ks == "Down":
            self.sugg_sel = (self.sugg_sel + 1) % len(self.sugg)
            self.sugg_moved = True
        elif ks == "Up":
            self.sugg_sel = (self.sugg_sel - 1) % len(self.sugg)
            self.sugg_moved = True
        elif ks == "Tab":
            self.pick_suggest(self.sugg_sel)
            return
        self.suggest.refresh()

    def suggest_press(self, x, y):
        i = self.suggest.index_at(y)
        if 0 <= i < len(self.sugg):
            self.pick_suggest(i)

    def pick_suggest(self, i):
        name = self.sugg[i]
        self.in_poke.set(poke_display(name))
        self.suggest.show(False)
        self.commit_poke(name)
        self.ui.set_focus(None)
        self.sound("ok")

    def poke_enter(self, text):
        if self.suggest.visible and self.sugg and (getattr(self, "sugg_moved", False)
                                                   or norm_poke_name(text) not in POKEDEX_IDS):
            self.pick_suggest(self.sugg_sel)
            return
        self.suggest.show(False)
        self.commit_poke(text)
        self.ui.set_focus(None)

    def poke_blur(self, text):
        self.suggest.show(False)
        if norm_poke_name(text) in POKEDEX_IDS:
            self.commit_poke(text)
        else:
            p = self.profile
            self.in_poke.set(poke_display(p.get("pokemon")) if p.get("pokemon") else "")

    def commit_poke(self, text):
        p = self.profile
        key = norm_poke_name(text)
        new = key if key in POKEDEX_IDS else text.strip()
        if key in POKEDEX_IDS:
            self.in_poke.set(poke_display(key))
        old = p.get("pokemon") or ""
        if new == old or not new:
            return
        auto = (not p["name"].strip() or p["name"] == "New Hunt"
                or p["name"].strip().lower() == poke_display(old).lower())
        p["pokemon"] = new
        if auto:
            p["name"] = poke_display(new).title()[:24]
        self.changed()
        self.refresh_screen()
        self.transition("day")
        self.refresh_dex()
        self.update_ready()
        self.update_lcd(animate=False)

    def set_game(self, g):
        p = self.profile
        p["game"] = g
        for name, odds in GAMES:
            if name == g:
                p["odds"] = odds
                self.cy_odds.set_value(odds)
        self.changed()
        self.refresh_screen()
        self.update_lcd(animate=False)

    def set_odds(self, o):
        self.profile["odds"] = int(o)
        self.changed()
        self.update_lcd(animate=False)

    def set_emu(self, name):
        p = self.profile
        _old_keys, old_hint = emulator_preset(p["emulator"])
        p["emulator"] = name
        if name != "Custom":
            keys, hint = emulator_preset(name)
            p["keys"] = keys
            if not p["window"] or p["window"] == old_hint:
                p["window"] = hint
            self.say("Loaded the %s keys. Check them on KEYS." % name, "good", duration=3)
        self.changed()
        for n, slot in self.key_slots.items():
            slot.set(p["keys"].get(n, ""))
        self.update_keys_tab()
        self.refresh_windows(quiet=True)
        self.update_script_status()
        self.update_ready()
        self.refresh_screen()

    def refresh_windows(self, quiet=False):
        p = self.profile
        wins = [(h, t) for h, t in self.plat.list_windows() if not is_own_title(t)]
        hwnd = find_window_in(wins, p["window"])
        values = [(t, t) for h, t in wins]
        cur = None
        for h, t in wins:
            if h == hwnd:
                cur = t
        if cur is None:
            values.insert(0, (None, "%s (NOT OPEN)" % (p["window"] or "NONE")))
        self.cy_win.set_values(values, cur)
        if hwnd:
            self.lb_win.set("● FOUND", PAL["green"])
        else:
            self.lb_win.set("× NOT OPEN", PAL["bad"])
        self.win_cache = (0.0, None, None)
        if not quiet:
            self.sound("tick")

    def set_window(self, title):
        if title is None:
            return
        p = self.profile
        p["window"] = window_pattern_for(title)
        emu = detect_emulator(title)
        if emu and emu != p["emulator"]:
            old_keys, _h = emulator_preset(p["emulator"])
            if p["emulator"] == "Custom" or p["keys"] == old_keys:
                p["emulator"] = emu
                p["keys"] = emulator_preset(emu)[0]
                self.cy_emu.set_value(emu)
                for n, slot in self.key_slots.items():
                    slot.set(p["keys"].get(n, ""))
                self.say("Found %s! Loaded its usual keys." % emu, "good", duration=3)
        self.win_cache = (0.0, None, None)
        self.changed()
        self.lb_win.set("● FOUND", PAL["green"])
        self.update_keys_tab()
        self.update_ready()
        self.refresh_screen()

    # ------------------------------------------------------------ KEYS
    def build_tab_keys(self):
        ui, t, P = self.ui, self.tabs["keys"], PAL
        self.lb_keys_emu = Label(ui, t, X0, 80, W0, 6, "", P["dim"], TINY)
        self.key_slots = {}
        cols = (["A", "B", "X", "Y", "L", "R", "START"],
                ["SELECT", "UP", "DOWN", "LEFT", "RIGHT", "RESET", "LOADSTATE"])
        for c, names in enumerate(cols):
            for r, name in enumerate(names):
                y = 92 + r * 20
                lx, sx, sw = (X0, X0 + 30, 52) if c == 0 else (X0 + 92, X0 + 130, W0 - 130)
                Label(ui, t, lx, y + 5, sx - lx - 2, 6, name, P["dim"], TINY)
                self.key_slots[name] = KeySlot(
                    ui, t, sx, y, sw, 15, "", (lambda v, n=name: self.set_key(n, v)),
                    "Click, then press the key your emulator uses for %s. Right-click clears." % name)
        self.btn_keys_reset = Button(ui, t, X0, 236, W0, 15, "LOAD DEFAULTS", self.reset_keys,
                                     "dark", "Put back your emulator's usual keys")
        self.lb_keys_warn = Label(ui, t, X0, 257, W0, 7, "", P["yellow"], TINY)

    def set_key(self, name, value):
        p = self.profile
        p["keys"][name] = value
        self.changed()
        self.update_keys_tab()
        self.update_script_status()
        self.update_ready()

    def update_keys_tab(self):
        P = PAL
        p = self.profile
        self.lb_keys_emu.set("MATCH THESE TO %s'S INPUT SETTINGS" % p["emulator"].upper()
                             if p["emulator"] != "Custom" else "MATCH THESE TO YOUR EMULATOR'S KEYS")
        if p["emulator"] == "Custom":
            self.btn_keys_reset.set_label("CLEAR ALL KEYS")
        else:
            self.btn_keys_reset.set_label("LOAD %s DEFAULTS" % p["emulator"].upper())
        hk = set((v or "").split("+")[-1] for v in (self.settings.get("hotkeys") or {}).values() if v)
        clash = None
        for name, slot in self.key_slots.items():
            k = (p["keys"].get(name) or "").split("+")[-1]
            bad = bool(k) and k in hk
            slot.set_warn(bad)
            if bad:
                clash = name
        steps, errs = compile_script(p["script"], p["keys"])
        kerr = [e for e in errs if "KEYS page" in e]
        if clash:
            self.lb_keys_warn.set("%s CLASHES WITH A HOTKEY (MORE PAGE)" % clash, P["orange"])
        elif kerr:
            self.lb_keys_warn.set(kerr[0].split(": ", 1)[-1].upper(), P["yellow"])
        else:
            self.lb_keys_warn.set("ALL BUTTONS IN YOUR STEPS HAVE KEYS ✓", P["green"])

    def reset_keys(self):
        if not self.confirmed("keys", self.btn_keys_reset):
            return
        p = self.profile
        p["keys"] = emulator_preset(p["emulator"])[0]
        for n, slot in self.key_slots.items():
            slot.set(p["keys"].get(n, ""))
        self.changed()
        self.update_keys_tab()
        self.update_script_status()
        self.update_ready()

    # ------------------------------------------------------------ STEPS
    def build_tab_script(self):
        ui, t, P = self.ui, self.tabs["script"], PAL
        self.cy_tpl = Cycler(ui, t, X0, 80, W0 - 102, 15, [(n, n) for n in TEMPLATE_NAMES],
                             None, None, "Ready-made step lists")
        self.btn_tpl = Button(ui, t, X1 - 98, 80, 30, 15, "LOAD", self.load_template, "dark",
                              "Replace your steps with this template", TINY)
        self.btn_txt = Button(ui, t, X1 - 64, 80, 30, 15, "TEXT", self.toggle_text_mode, "dark",
                              "Edit the steps as text instead", TINY)
        self.btn_test = Button(ui, t, X1 - 30, 80, 30, 15, "TEST", self.test_loop, "go",
                               "Play the steps once to try them (nothing gets counted)", TINY)
        self.editor = ScriptEditor(ui, t, X0, 102, W0, 108, self)
        for i, (lab, op) in enumerate((("+PRESS", "press"), ("+HOLD", "hold"),
                                       ("+WAIT", "wait"), ("+CHECK", "check"))):
            Button(ui, t, X0 + i * 48, 217, 44, 15, lab, (lambda o=op: self.add_step(o)), "dark",
                   "Add a %s step after the selected one" % op.upper(), TINY)
        self.lb_script = Label(ui, t, X0, 241, W0, 7, "", P["green"], TINY)
        self.lb_script2 = Label(ui, t, X0, 252, W0, 7, "", P["dim"], TINY)
        S = self.S
        self.txt = tk.Text(self.root, bg="#070C16", fg="#EAF2FF", insertbackground="#5CE1E6",
                           selectbackground="#273A57", relief="flat", bd=0, highlightthickness=0,
                           font=(self.mono_font(), -max(9, 6 * S)), wrap="none", undo=True,
                           padx=3 * S, pady=3 * S)
        self.txt.tag_configure("cmd", foreground="#5CE1E6")
        self.txt.tag_configure("cmt", foreground="#8299B8")
        self.txt.tag_configure("num", foreground="#FFD93B")
        self.txt.bind("<<Modified>>", self.text_modified)
        self.txt_box = EmbedText(ui, t, X0, 102, W0, 130, self.txt)
        self.txt_box.forced_hidden = True
        self.txt_box.apply_state()

    def mono_font(self):
        try:
            import tkinter.font as tkfont
            fams = set(tkfont.families(self.root))
        except Exception:
            fams = set()
        for f in ("Consolas", "Cascadia Mono", "DejaVu Sans Mono", "Courier New"):
            if f in fams:
                return f
        return "Courier"

    def script_changed(self):
        self.changed()
        self.update_script_status()
        self.update_keys_tab()
        self.update_ready()

    def update_script_status(self):
        P = PAL
        p = self.profile
        steps, errs = compile_script(p["script"], p["keys"])
        has_check = any(s["op"] == "check" for s in steps)
        if errs:
            self.lb_script.set("× " + errs[0].upper(), P["bad"])
        elif not steps:
            self.lb_script.set("ADD SOME STEPS (OR LOAD A TEMPLATE)", P["yellow"])
        elif not has_check:
            self.lb_script.set("ADD A CHECK WHERE THE POKEMON APPEARS", P["yellow"])
        else:
            n = sum(1 for s in steps if s["op"] == "check")
            self.lb_script.set("✓ READY  ·  %d STEPS  ·  %d CHECK%s" %
                               (len(steps), n, "" if n == 1 else "S"), P["green"])
        est = estimate_loop(p["script"])
        if p.get("loop_avg"):
            self.lb_script2.set("REAL PACE %sS PER RESET  ·  ~%s RESETS/HR" %
                                (fmt_num(round(p["loop_avg"], 1)), fmt_int(3600 / max(0.5, p["loop_avg"]))),
                                P["dim"])
        elif est > 0:
            self.lb_script2.set("ABOUT %sS PER RESET  ·  ~%s RESETS/HR" %
                                (fmt_num(round(est, 1)), fmt_int(3600 / max(0.5, est))), P["dim"])
        else:
            self.lb_script2.set("")
        self.editor.refresh()

    def add_step(self, op):
        rows = self.profile["script"]
        new = {"press": {"op": "press", "btn": "A", "times": 1, "gap": 0.5, "hold": DEF_HOLD},
               "hold": {"op": "hold", "btn": "UP", "dur": 1.0},
               "wait": {"op": "wait", "lo": 1.0, "hi": 1.0},
               "check": {"op": "check", "dur": 5.0}}[op]
        i = self.editor.sel + 1 if 0 <= self.editor.sel < len(rows) else len(rows)
        rows.insert(i, new)
        self.editor.sel = i
        self.editor.ensure_visible(i)
        self.editor.refresh()
        self.script_changed()
        if op in ("press", "hold"):
            self.open_picker(i)

    def load_template(self):
        if not self.confirmed("tpl", self.btn_tpl):
            return
        p = self.profile
        name = self.cy_tpl.value()
        p["script"] = template_rows(name)
        p["template"] = name
        p["loop_avg"] = None
        self.editor.sel = -1
        self.editor.scroll = 0
        self.editor.set_rows(p["script"])
        if self.text_mode:
            self.fill_text()
        self.script_changed()
        self.say("Loaded %s. Tweak the waits for your game." % name, "good", duration=3)

    def toggle_text_mode(self):
        p = self.profile
        if not self.text_mode:
            self.text_mode = True
            self.fill_text()
            self.editor.show(False)
            self.txt_box.forced_hidden = False
            self.txt_box.apply_state()
            self.txt.focus_set()
        else:
            rows, errs = parse_script(self.txt.get("1.0", "end"))
            if errs:
                self.sound("error")
                self.say("Fix the steps first: " + errs[0], "bad")
                return
            p["script"] = rows
            self.text_mode = False
            self.txt_box.forced_hidden = True
            self.txt_box.apply_state()
            self.editor.show(True)
            self.editor.set_rows(p["script"])
            self.script_changed()
            self.ui.cv.focus_set()
        self.btn_txt.set_active(self.text_mode)

    def fill_text(self):
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", script_to_text(self.profile["script"]))
        self.txt.edit_modified(False)
        self.highlight_text()

    def highlight_text(self):
        t = self.txt
        for tag in ("cmd", "cmt", "num"):
            t.tag_remove(tag, "1.0", "end")
        lines = t.get("1.0", "end").split("\n")
        for i, line in enumerate(lines, 1):
            s = line.lstrip()
            off = len(line) - len(s)
            if s.startswith("#"):
                t.tag_add("cmt", "%d.%d" % (i, off), "%d.end" % i)
                continue
            m = re.match(r"(press|tap|hold|wait|sleep|check|watch)\b", s, re.I)
            if m:
                t.tag_add("cmd", "%d.%d" % (i, off), "%d.%d" % (i, off + m.end()))
            for nm in re.finditer(r"(?<![A-Za-z])x?\d+(\.\d+)?(~\d+(\.\d+)?)?", line):
                t.tag_add("num", "%d.%d" % (i, nm.start()), "%d.%d" % (i, nm.end()))
            c = line.find("#")
            if c >= 0:
                t.tag_add("cmt", "%d.%d" % (i, c), "%d.end" % i)

    def text_modified(self, e=None):
        if not self.txt.edit_modified():
            return
        self.txt.edit_modified(False)
        self.highlight_text()
        rows, errs = parse_script(self.txt.get("1.0", "end"))
        if errs:
            self.lb_script.set("× " + errs[0].upper(), PAL["bad"])
            return
        self.profile["script"] = rows
        self.editor.set_rows(rows)
        self.script_changed()

    # -- button picker (for PRESS / HOLD steps)
    def build_picker(self):
        ui, P = self.ui, PAL
        g = self.g_pick = Group(ui, self.g_panel, visible=False)
        px, py, pw, ph = PSCREEN
        Blocker(ui, g, px, py, Bitmap(pw, ph, P["night"]))
        bw_, bh_ = pw - 20, ph - 20
        box = Bitmap(bw_, bh_)
        box.rrect(0, 0, bw_, bh_, 6, P["cyan_dk"])
        box.rrect(1, 1, bw_ - 2, bh_ - 2, 5, P["dark2"])
        Blocker(ui, g, px + 10, py + 10, box)
        x0, inner = px + 20, bw_ - 20          # content inside the box
        Label(ui, g, x0, py + 20, 150, 8, "BUTTONS TO PRESS", P["cyan"])
        self.pick_btns = {}
        labels = [("A", "A"), ("B", "B"), ("X", "X"), ("Y", "Y"), ("L", "L"), ("R", "R"),
                  ("START", "START"), ("SELECT", "SELECT"), ("UP", "▲ UP"), ("DOWN", "▼ DOWN"),
                  ("LEFT", "◀ LEFT"), ("RIGHT", "▶ RIGHT"), ("RESET", "RESET"),
                  ("LOADSTATE", "LOADSTATE")]
        cw = (inner - 3 * 4) // 4
        for i, (tok, lab) in enumerate(labels):
            c, r = i % 4, i // 4
            if r < 3:
                bx, bw = x0 + c * (cw + 4), cw
            else:
                bx, bw = x0 + c * (2 * cw + 8), 2 * cw + 4
            self.pick_btns[tok] = Button(ui, g, bx, py + 36 + r * 20, bw, 16, lab,
                                         (lambda k=tok: self.picker_toggle(k)), "dark", "", TINY)
        ky = py + 36 + 4 * 20 + 10
        self.cap(g, x0, ky + 5, "OR ANY KEY:", 50)
        self.pick_key = KeySlot(ui, g, x0 + 52, ky, inner - 52, 15, "", self.picker_rawkey,
                                "Click, then press any keyboard key to add it")
        self.lb_pick = Label(ui, g, x0, ky + 25, inner, 9, "", P["ink"])
        self.lb_pick_hint = Label(ui, g, x0, ky + 38, inner, 6, "PICKED BUTTONS ARE PRESSED TOGETHER",
                                  P["faint"], TINY)
        half = (inner - 6) // 2
        Button(ui, g, x0, py + bh_ - 18, half, 17, "OK", self.picker_ok, "go")
        Button(ui, g, x0 + half + 6, py + bh_ - 18, half, 17, "CANCEL", self.picker_cancel, "dark")

    def open_picker(self, i):
        rows = self.profile["script"]
        if not (0 <= i < len(rows)) or rows[i].get("op") not in ("press", "hold"):
            return
        self.picker_row = i
        self.picker_sel = [t for t in rows[i]["btn"].split("+") if t]
        self.update_picker()
        self.g_pick.set_visible(True)
        self.txt_box.forced_hidden = True
        self.txt_box.apply_state()

    def update_picker(self):
        for tok, b in self.pick_btns.items():
            b.set_active(tok in self.picker_sel)
        lab = combo_label("+".join(self.picker_sel)) if self.picker_sel else "(nothing yet)"
        self.lb_pick.set("= " + lab, PAL["ink"] if self.picker_sel else PAL["faint"])

    def picker_toggle(self, tok):
        if tok in self.picker_sel:
            self.picker_sel.remove(tok)
        else:
            self.picker_sel.append(tok)
        self.update_picker()

    def picker_rawkey(self, v):
        if v:
            for k in v.split("+"):
                tok = "key:" + k
                if norm_key(k) and tok not in self.picker_sel:
                    self.picker_sel.append(tok)
        self.pick_key.set("")
        self.update_picker()

    def picker_ok(self):
        if not self.picker_sel:
            self.sound("error")
            self.lb_pick.set("PICK AT LEAST ONE BUTTON", PAL["bad"])
            return
        rows = self.profile["script"]
        if self.picker_row is not None and 0 <= self.picker_row < len(rows):
            rows[self.picker_row]["btn"] = "+".join(self.picker_sel)
            self.script_changed()
        self.g_pick.set_visible(False)
        self.editor.refresh()

    def picker_cancel(self):
        self.g_pick.set_visible(False)

    # ------------------------------------------------------------ AREA
    def build_tab_area(self):
        ui, t, P = self.ui, self.tabs["area"], PAL
        self.area = AreaSelector(ui, t, X0, 80, W0, 138, self.set_area_box, self.update_area_label)
        self.lb_area = Label(ui, t, X0, 229, W0 - 52, 7, "", P["ink"], TINY)
        self.btn_live = Button(ui, t, X1 - 44, 225, 44, 15, "LIVE", self.toggle_area_live, "dark",
                               "Live picture on/off (freeze it to draw more easily)", TINY)
        TextBlock(ui, t, X0, 248, W0, 18,
                  "~Drag a box around the Pokemon in battle. Drag inside it to move it, or a corner "
                  "to resize.", P["faint"], TINY, 8)

    def toggle_area_live(self):
        self.area_live = not self.area_live
        self.btn_live.set_label("LIVE" if self.area_live else "FROZEN")
        self.btn_live.set_active(not self.area_live)
        if self.area_live:
            self.update_area_snapshot()

    def update_area_snapshot(self):
        if self.area.mode:
            return
        p = self.profile
        hwnd = self.find_hwnd(p)
        if not hwnd:
            self.area.set_message("Can't see your emulator. Open it and pick its window on the HUNT page.")
            self.update_area_label()
            return
        if self.plat.is_minimized(hwnd):
            self.area.set_message("Your emulator is minimized. Bring it back up.")
            return
        try:
            ox, oy = self.plat.client_origin(hwnd)
            cw, ch = self.plat.client_size(hwnd)
            fr = self.plat.capture(ox, oy, cw, ch)
        except Exception:
            self.area.set_message("Couldn't take a picture of the emulator.")
            return
        self.area.set_snapshot(fr)
        self.area.set_box(p["detect"].get("region"))
        self.area_black = fr.mean_level() < 4
        self.update_area_label()

    def update_area_label(self, box=None):
        P = PAL
        reg = box or self.profile["detect"].get("region")
        if self.area_black and self.area.img is not None:
            self.lb_area.set("PICTURE IS BLACK? NO FULLSCREEN", P["yellow"])
        elif reg:
            self.lb_area.set("BOX %d×%d AT %d,%d %s" % (reg[2], reg[3], reg[0], reg[1],
                                                      "" if box else " ✓ SAVED"),
                             P["green"] if not box else P["ink"])
        else:
            self.lb_area.set("NO BOX YET: DRAG ON THE PICTURE", P["yellow"])

    def set_area_box(self, box):
        p = self.profile
        d = p["detect"]
        old = d.get("region")
        if old == box:
            return
        d["region"] = list(box)
        d["relative"] = True
        had_refs = bool(d.get("refs"))
        d["refs"] = []
        p["scores"] = []
        self.changed()
        self.sound("ok")
        self.update_area_label()
        self.thumbs.set_refs([])
        self.update_ready()
        if had_refs:
            self.say("Area saved! Add new normal frames on CHECK.", "good")
        else:
            self.say("Area saved! Next up: the CHECK page.", "good")
        self.timers["live"] = 0

    # ------------------------------------------------------------ CHECK
    def build_tab_check(self):
        ui, t, P = self.ui, self.tabs["check"], PAL
        self.cy_mode = Cycler(ui, t, X0, 80, W0, 15,
                              [("compare", "COMPARE TO NORMAL"), ("color", "LOOK FOR SHINY COLOURS")],
                              "compare", self.set_mode, "How OddsBreaker decides it's shiny")
        sx = X1 - 92          # steppers line up on the right
        tc = self.g_cmp = Group(ui, t)
        Pic(ui, tc, X0, 103, frame_box(78, 58, P["line"]))
        self.prev_cmp = ImageBox(ui, tc, X0 + 1, 104, 76, 56)
        self.cap(tc, X1 - 102, 103, "NORMAL FRAMES", 102)
        self.thumbs = Thumbs(ui, tc, X1 - 104, 111, 104, 25, self.delete_ref)
        self.btn_addref = Button(ui, tc, X1 - 102, 143, 102, 18, "+ ADD FRAME", self.add_ref, "go",
                                 "With the NORMAL Pokemon on screen, click to remember it")
        self.cap(tc, X0, 170, "LIVE DIFFERENCE", 100)
        self.lb_diff = Label(ui, tc, X1 - 60, 170, 60, 6, "", P["ink"], TINY, align="right")
        self.meter_cmp = Meter(ui, tc, X0, 178, W0, 15, 60.0, 15.0, self.meter_threshold, True,
                               "Drag the red line: above it counts as shiny")
        self.cap(tc, X0, 205, "SHINY ABOVE", 86)
        self.st_thr = Stepper(ui, tc, sx, 201, 92, 15, 15.0, 1.0, 60.0, step_pct,
                              lambda v: "%s%%" % fmt_num(v), self.set_threshold,
                              "How different from normal counts as shiny")
        self.cap(tc, X0, 224, "PIXEL TOLERANCE", 86)
        self.st_ptol = Stepper(ui, tc, sx, 220, 92, 15, 40, 5, 150, lambda v, d: int(v) + 5 * d,
                               lambda v: "%d" % v, self.set_ptol,
                               "How much a pixel may change before it counts as different")
        self.spark = Sparkline(ui, tc, X0, 240, W0 - 64, 14,
                               "Scores of your last normal encounters (red line = shiny)")
        self.btn_suggest = Button(ui, tc, X1 - 58, 240, 58, 14, "SUGGEST", self.apply_suggestion, "dark",
                                  "Move the red line to a safe spot based on your last checks", TINY)
        tk_ = self.g_col = Group(ui, t)
        Pic(ui, tk_, X0, 103, frame_box(102, 64, P["line"]))
        self.prev_col = ImageBox(ui, tk_, X0 + 1, 104, 100, 62, cb=self.pick_color,
                                 hint="Click a colour that only the shiny has", cursor="tcross")
        self.cap(tk_, X1 - 78, 103, "SHINY COLOURS", 78)
        self.swatches = Swatches(ui, tk_, X1 - 78, 111, 78, 36, self.remove_color)
        Button(ui, tk_, X1 - 78, 152, 78, 15, "CLEAR", self.clear_colors, "dark", "Remove all colours", TINY)
        self.cap(tk_, X0, 176, "COLOUR MATCH", 100)
        self.lb_match = Label(ui, tk_, X1 - 60, 176, 60, 6, "", P["ink"], TINY, align="right")
        self.meter_col = Meter(ui, tk_, X0, 184, W0, 15, 30.0, 3.0, self.meter_colorpct, False,
                               "Drag the red line: at or above it counts as shiny")
        self.cap(tk_, X0, 211, "SHINY AT", 86)
        self.st_cpct = Stepper(ui, tk_, sx, 207, 92, 15, 3.0, 0.5, 30.0, step_pct,
                               lambda v: "%s%%" % fmt_num(v), self.set_cpct,
                               "How much of the area must be shiny colours")
        self.cap(tk_, X0, 230, "COLOUR TOLERANCE", 86)
        self.st_ctol = Stepper(ui, tk_, sx, 226, 92, 15, 28, 4, 120, lambda v, d: int(v) + 2 * d,
                               lambda v: "%d" % v, self.set_ctol, "How close a colour must be")
        self.lb_verdict = Label(ui, t, X0, 258, W0, 8, "", P["ink"], align="center")

    def update_mode_groups(self):
        mode = self.profile["detect"]["mode"]
        self.g_cmp.set_visible(mode == "compare")
        self.g_col.set_visible(mode == "color")

    def set_mode(self, mode):
        self.profile["detect"]["mode"] = mode
        self.profile["scores"] = []
        self.changed()
        self.update_mode_groups()
        self.update_ready()
        self.timers["check"] = 0

    def matching_refs(self):
        return matching_refs(self.profile["detect"])

    def update_check_history(self):
        p = self.profile
        d = p["detect"]
        scores = (p.get("scores") or [])[-30:]
        if d["mode"] == "compare":
            self.spark.set(scores, d["threshold"], 60.0)
            sug = suggest_threshold(d, scores)
            self.btn_suggest.set_enabled(sug is not None and abs(sug - d["threshold"]) >= 0.5)
            self.btn_suggest.hint = ("Set the red line to %s%%" % fmt_num(sug)) if sug else \
                "Needs 5 normal checks first (run the hunt for a bit)"

    def apply_suggestion(self):
        p = self.profile
        d = p["detect"]
        sug = suggest_threshold(d, p.get("scores") or [])
        if sug is None:
            self.say("Run the hunt for a few resets first, then I can suggest a spot.", "info")
            return
        d["threshold"] = sug
        self.meter_cmp.set_mark(sug)
        self.st_thr.set(sug)
        self.changed()
        self.update_check_history()
        top = max(p["scores"][-30:])
        self.say("Red line set to %s%% (your normal ones peak at %.1f%%)." % (fmt_num(sug), top), "good")

    def update_check_live(self):
        P = PAL
        p = self.profile
        d = p["detect"]
        self.update_check_history()
        fr = self.capture_region(p)
        self.check_frame = fr
        box = self.prev_cmp if d["mode"] == "compare" else self.prev_col
        if fr is None:
            box.set_photo(None)
            msg = "NO WATCH AREA YET (AREA PAGE)" if not d.get("region") else "CAN'T SEE THE EMULATOR"
            self.lb_verdict.set(msg, P["yellow"])
            self.meter_cmp.set_value(None)
            self.meter_col.set_value(None)
            self.lb_diff.set("")
            self.lb_match.set("")
            return
        S = self.S
        photo, zoom, step = frame_photo(fr, box.w * S, box.h * S)
        box.set_photo(photo)
        self.prev_map = (zoom, step)
        if d["mode"] == "compare":
            refs = usable_refs(d)
            if not refs:
                self.meter_cmp.set_value(None)
                self.lb_diff.set("")
                self.lb_verdict.set("PAUSE ON THE NORMAL ONE, ADD FRAME", P["yellow"])
                return
            s = score_frame(fr, d, refs)
            self.meter_cmp.set_value(s)
            self.lb_diff.set("%.1f%%" % s, P["gold"] if s > d["threshold"] else P["green"])
        else:
            if not d.get("colors"):
                self.meter_col.set_value(None)
                self.lb_match.set("")
                self.lb_verdict.set("SHOW A SHINY, CLICK ITS COLOURS", P["yellow"])
                return
            s = score_frame(fr, d, [])
            self.meter_col.set_value(s)
            self.lb_match.set("%.1f%%" % s, P["gold"] if s >= d["color_pct"] else P["green"])
        if is_shiny_score(d, s):
            self.lb_verdict.set("★ LOOKS SHINY ★", P["gold"])
        else:
            self.lb_verdict.set("LOOKS NORMAL ✓", P["green"])

    def add_ref(self):
        p = self.profile
        d = p["detect"]
        fr = self.capture_region(p)
        if fr is None:
            self.sound("error")
            self.say("No picture yet. Draw the AREA and open your emulator.", "bad")
            return
        refs = self.matching_refs()
        refs.append(make_ref(fr))
        d["refs"] = refs[-3:]
        self.changed()
        self.sound("ok")
        self.btn_addref.flash(0.2)
        self.thumbs.set_refs(d["refs"])
        self.update_ready()
        self.timers["check"] = 0
        n = len(d["refs"])
        self.say("Got it! %d normal frame%s saved." % (n, "" if n == 1 else "s"), "good", duration=2.5)

    def delete_ref(self, i):
        d = self.profile["detect"]
        refs = self.matching_refs()
        if 0 <= i < len(refs):
            del refs[i]
            d["refs"] = refs
            self.thumbs.set_refs(refs)
            self.sound("close")
            self.changed()
            self.update_ready()

    def meter_threshold(self, v):
        self.profile["detect"]["threshold"] = v
        self.st_thr.set(v)
        self.changed()

    def set_threshold(self, v):
        self.profile["detect"]["threshold"] = v
        self.meter_cmp.set_mark(v)
        self.changed()

    def set_ptol(self, v):
        self.profile["detect"]["pixel_tol"] = int(v)
        self.changed()

    def meter_colorpct(self, v):
        self.profile["detect"]["color_pct"] = v
        self.st_cpct.set(v)
        self.changed()

    def set_cpct(self, v):
        self.profile["detect"]["color_pct"] = v
        self.meter_col.set_mark(v)
        self.changed()

    def set_ctol(self, v):
        self.profile["detect"]["color_tol"] = int(v)
        self.changed()

    def pick_color(self, x, y):
        fr = self.check_frame
        if fr is None or not self.prev_map:
            return
        zoom, step = self.prev_map
        S = self.S
        sx, sy = self.ui.last_px
        bx = sx - (self.prev_col.ax() * S + self.prev_col.dx)
        by = sy - (self.prev_col.ay() * S + self.prev_col.dy)
        fx_ = int(bx / zoom) if step == 1 else int(bx * step)
        fy_ = int(by / zoom) if step == 1 else int(by * step)
        if not (0 <= fx_ < fr.w and 0 <= fy_ < fr.h):
            return
        c = list(fr.pixel(fx_, fy_))
        cols = self.profile["detect"].setdefault("colors", [])
        if c not in cols and len(cols) < 18:
            cols.append(c)
            self.sound("ok")
        self.swatches.set_colors(cols)
        self.changed()
        self.update_ready()
        self.timers["check"] = 0

    def remove_color(self, i):
        cols = self.profile["detect"].get("colors", [])
        if 0 <= i < len(cols):
            del cols[i]
            self.swatches.set_colors(cols)
            self.changed()
            self.update_ready()

    def clear_colors(self):
        self.profile["detect"]["colors"] = []
        self.swatches.set_colors([])
        self.changed()
        self.update_ready()

    # ------------------------------------------------------------ load
    def load_setup_pages(self):
        p = self.profile
        d = p["detect"]
        self.in_poke.set(poke_display(p.get("pokemon")) if p.get("pokemon") else "")
        games = [(n, n) for n in GAME_NAMES]
        if p["game"] not in GAME_NAMES:
            games.append((p["game"], ellipsize(p["game"].upper(), 140)))
        self.cy_game.set_values(games, p["game"])
        odds = list(ODDS)
        if p["odds"] not in [o for o, _ in ODDS]:
            odds.append((p["odds"], "1/%d  CUSTOM" % p["odds"]))
        self.cy_odds.set_values(odds, p["odds"])
        self.cy_emu.set_value(p["emulator"])
        self.refresh_windows(quiet=True)
        for name, slot in self.key_slots.items():
            slot.set(p["keys"].get(name, ""))
        self.update_keys_tab()
        self.cy_tpl.set_value(p.get("template") or TEMPLATE_NAMES[0])
        self.editor.sel = -1
        self.editor.scroll = 0
        self.editor.set_rows(p["script"])
        if self.text_mode:
            self.fill_text()
        self.update_script_status()
        self.area.set_box(d.get("region"))
        self.update_area_label()
        self.cy_mode.set_value(d["mode"])
        self.update_mode_groups()
        self.meter_cmp.set_mark(d["threshold"])
        self.st_thr.set(d["threshold"])
        self.st_ptol.set(d["pixel_tol"])
        self.meter_col.set_mark(d["color_pct"])
        self.st_cpct.set(d["color_pct"])
        self.st_ctol.set(d["color_tol"])
        self.thumbs.set_refs(self.matching_refs())
        self.swatches.set_colors(d.get("colors", []))
        self.update_check_history()

