"""Self-test: drives every page with a fake emulator and saves screenshots.

    OddsBreaker.exe --selftest OUTDIR

Nothing touches your real hunts (it uses a temporary data folder) and no
keys are sent anywhere. Exit code 0 means every step worked.
"""

import json
import os
import shutil
import sys
import tempfile
import time
import traceback

import tkinter as tk

from . import APP_NAME, __version__, paths
from .config import IS_WIN
from .imaging import save_frame_png


class Ev(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)


class Driver(object):
    """Pokes the UI the way a mouse and keyboard would."""

    def __init__(self, app, outdir=None):
        self.app = app
        self.root = app.root
        self.outdir = outdir
        self.log = []
        self.grabber = None
        if outdir:
            os.makedirs(outdir, exist_ok=True)
            self.grabber = make_grabber()

    def note(self, msg):
        self.log.append(msg)
        print(msg)
        sys.stdout.flush()

    def pump(self, sec=0.1):
        t = time.time()
        while time.time() - t < sec:
            self.root.update()
            time.sleep(0.008)

    def ev(self, x, y, ui=None, state=0):
        ui = ui or self.app.ui
        S = ui.S
        cx, cy = int(x * S + S // 2), int(y * S + S // 2)
        return Ev(x=cx, y=cy, x_root=ui.root.winfo_rootx() + cx, y_root=ui.root.winfo_rooty() + cy,
                  state=state, delta=0, widget=ui.cv, keysym="", char="")

    def click(self, x, y, wait=0.15, ui=None):
        ui = ui or self.app.ui
        ui._motion(self.ev(x, y, ui))
        ui._press(self.ev(x, y, ui))
        ui._release(self.ev(x, y, ui))
        self.pump(wait)

    def click_w(self, w, dx=None, dy=None, wait=0.15):
        """Click the middle of a widget."""
        self.click(w.ax() + (w.w // 2 if dx is None else dx), w.ay() + (w.h // 2 if dy is None else dy),
                   wait)

    def rclick_w(self, w):
        self.app.ui._rpress(self.ev(w.ax() + 3, w.ay() + 3))
        self.pump(0.1)

    def drag(self, x0, y0, x1, y1, steps=8):
        ui = self.app.ui
        ui._motion(self.ev(x0, y0))
        ui._press(self.ev(x0, y0))
        for i in range(1, steps + 1):
            ui._drag(self.ev(x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps))
            self.pump(0.02)
        ui._release(self.ev(x1, y1))
        self.pump(0.15)

    def wheel(self, x, y, d):
        e = self.ev(x, y)
        e.delta = 120 * d
        self.app.ui._wheel(e)
        self.pump(0.05)

    def key(self, keysym, char="", state=0, up=False, ui=None):
        ui = ui or self.app.ui
        e = Ev(keysym=keysym, char=char, state=state, widget=ui.cv)
        (ui.keyup if up else ui.key)(e)
        self.pump(0.03)

    def typ(self, text):
        for ch in text:
            self.key(ch if ch.isalnum() else {" ": "space"}.get(ch, ch), ch)

    def wait_for(self, cond, timeout=8.0):
        t = time.time()
        while time.time() - t < timeout:
            if cond():
                return True
            self.pump(0.05)
        return cond()

    def shot(self, name, win=None, settle=0.3):
        self.pump(settle)
        if not self.grabber:
            return None
        win = win or self.root
        try:
            x, y = win.winfo_rootx(), win.winfo_rooty()
            w, h = win.winfo_width(), win.winfo_height()
            path = os.path.join(self.outdir, name + ".png")
            self.grabber(x, y, w, h, path)
            return path
        except Exception:
            self.note("  (screenshot %s failed: %s)" % (name, traceback.format_exc().splitlines()[-1]))
            return None


def make_grabber():
    """A function (x, y, w, h, path) that saves a screenshot, or None."""
    if IS_WIN:
        from .system import WinPlatform
        wp = WinPlatform()

        def grab(x, y, w, h, path):
            save_frame_png(wp.capture(x, y, w, h), path)
        return grab
    try:
        from PIL import ImageGrab
    except ImportError:
        return None

    def grab(x, y, w, h, path):
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h), xdisplay=os.environ.get("DISPLAY"))
        img.save(path)
    return grab


def tab_key(app, key):
    return app.tab_btns[key]


def scenario(d):
    """The full walk through. Raises AssertionError on the first problem."""
    from .script import parse_script
    app = d.app
    plat = app.plat
    d.shot("01_boot", settle=0.25)
    d.pump(2.2)
    d.shot("02_device")
    assert d.wait_for(lambda: app.panel_open and app.tab == "hunt", 4), "welcome should open HUNT"
    d.pump(0.6)
    d.note("ok: boot + welcome")

    # HUNT ---------------------------------------------------------------------
    d.click_w(app.in_poke)
    assert app.ui.focus is app.in_poke
    d.key("a", "a", state=4)
    d.typ("mew")
    d.pump(0.2)
    assert app.suggest.visible, "suggestions should show"
    d.shot("03_hunt_typing")
    d.key("Down")
    d.key("Return")
    d.pump(0.3)
    assert app.profile["pokemon"] in ("mew", "mewtwo"), app.profile["pokemon"]
    app.refresh_windows()
    assert app.find_hwnd(fresh=True), "stub emulator window should be found"
    d.shot("04_hunt")
    d.note("ok: HUNT (%s)" % app.profile["pokemon"])

    # KEYS ---------------------------------------------------------------------
    d.click_w(tab_key(app, "keys"))
    assert app.tab == "keys", app.tab
    slot = app.key_slots["A"]
    d.click_w(slot)
    assert app.ui.focus is slot
    d.shot("05_keys_listening")
    d.key("k", "k")
    assert app.profile["keys"]["A"] == "k", app.profile["keys"]["A"]
    s2 = app.key_slots["SELECT"]
    d.click_w(s2)
    d.key("Shift_R")
    d.key("Shift_R", up=True)
    assert app.profile["keys"]["SELECT"] == "rshift", app.profile["keys"]["SELECT"]
    s3 = app.key_slots["RESET"]
    d.click_w(s3)
    d.key("r", "\x12", state=4)
    assert app.profile["keys"]["RESET"] == "ctrl+r", app.profile["keys"]["RESET"]
    d.rclick_w(app.key_slots["Y"])
    d.shot("06_keys")
    d.note("ok: KEYS")

    # STEPS --------------------------------------------------------------------
    d.click_w(tab_key(app, "script"))
    assert app.tab == "script"
    ed = app.editor
    d.click(ed.ax() + 60, ed.ay() + 1 * ed.ROW + 5)
    assert ed.sel == 1, ed.sel
    before = json.dumps(app.profile["script"][ed.sel])
    d.pump(0.1)
    pill = [t for t in ed.targets if t[4] == "pill" and t[6][1] == 1][0]
    d.click(ed.ax() + (pill[0] + pill[2]) // 2, ed.ay() + (pill[1] + pill[3]) // 2)
    assert json.dumps(app.profile["script"][ed.sel]) != before, "pill should change the step"
    d.shot("07_steps")
    press_i = [i for i, r in enumerate(app.profile["script"]) if r["op"] == "press"][0]
    ed.sel = press_i
    ed.ensure_visible(press_i)
    ed.refresh()
    d.pump(0.2)
    bt = [t for t in ed.targets if t[4] == "btn"][0]
    d.click(ed.ax() + bt[0] + 3, ed.ay() + bt[1] + 3)
    assert app.g_pick.visible, "button picker should open"
    d.shot("08_steps_picker")
    d.click_w(app.pick_btns["B"])
    d.click_w(app.pick_btns["B"])
    d.click_w(app.pick_btns["L"])
    ok_btn = [w for w in app.g_pick.widgets if getattr(w, "label", "") == "OK"][0]
    d.click_w(ok_btn)
    assert not app.g_pick.visible
    d.click_w(app.btn_txt)
    assert app.text_mode
    d.pump(0.2)
    d.shot("09_steps_text")
    app.txt.insert("end", "wait 0.5\n")
    app.txt.edit_modified(True)
    app.text_modified()
    d.click_w(app.btn_txt)
    assert not app.text_mode
    d.note("ok: STEPS (%d rows)" % len(app.profile["script"]))

    # AREA ---------------------------------------------------------------------
    d.click_w(tab_key(app, "area"))
    assert app.tab == "area"
    d.pump(0.8)
    a = app.area
    assert a.img is not None, "area snapshot should show"
    x0, y0 = a.ax() + 80, a.ay() + 22
    d.drag(x0, y0, x0 + 50, y0 + 45)
    reg = app.profile["detect"]["region"]
    assert reg and reg[2] > 20 and reg[3] > 20, reg
    d.shot("10_area")
    d.drag(x0 + 25, y0 + 20, x0 + 30, y0 + 25)
    reg2 = app.profile["detect"]["region"]
    assert reg2[2] == reg[2] and reg2[0] != reg[0], (reg, reg2)
    app.close_panel()
    d.pump(0.6)
    assert not app.panel_open
    d.click_w(app.face_btns["setup"])
    d.pump(0.6)
    assert app.panel_open and app.tab == "hunt"
    app.save()
    with open(paths.SAVE_FILE, encoding="utf-8") as f:
        saved = json.load(f)
    assert [p for p in saved["profiles"] if p["detect"]["region"] == reg2], "area must be saved"
    d.note("ok: AREA %s" % (reg2,))

    # CHECK --------------------------------------------------------------------
    d.click_w(tab_key(app, "check"))
    assert app.tab == "check"
    d.pump(0.5)
    d.click_w(app.btn_addref)
    d.pump(0.6)
    assert app.meter_cmp.value is not None and app.meter_cmp.value < 5, app.meter_cmp.value
    d.shot("11_check_normal")
    plat.shiny = True
    d.pump(0.7)
    shiny_score = app.meter_cmp.value
    assert shiny_score is not None and shiny_score > app.profile["detect"]["threshold"], shiny_score
    d.shot("12_check_shiny")
    plat.shiny = False
    m = app.meter_cmp
    d.drag(m.ax() + 40, m.ay() + 7, m.ax() + 55, m.ay() + 7)
    d.click(app.cy_mode.ax() + app.cy_mode.w - 6, app.cy_mode.ay() + 6)
    assert app.profile["detect"]["mode"] == "color"
    d.pump(0.4)
    plat.shiny = True
    d.pump(0.5)
    d.click_w(app.prev_col)
    d.pump(0.4)
    d.shot("13_check_colours")
    plat.shiny = False
    d.click(app.cy_mode.ax() + app.cy_mode.w - 6, app.cy_mode.ay() + 6)
    assert app.profile["detect"]["mode"] == "compare"
    d.note("ok: CHECK (shiny score %.1f%%)" % shiny_score)

    # TEST one loop ---------------------------------------------------------------
    p = app.profile
    p["script"] = parse_script("press A hold 0.02\nwait 0.1\ncheck 0.4\n")[0]
    p["detect"]["threshold"] = 8.0
    p["detect"]["fps"] = 20
    app.load_profile_ui()
    d.click_w(tab_key(app, "script"))
    d.click_w(app.btn_test)
    assert app.hunter is not None and app.testing, "test run should start"
    assert d.wait_for(lambda: app.hunter is None, 6), "test run should finish"
    assert p["encounters"] == 0, "test runs must not count"
    d.shot("14_steps_tested")
    d.note("ok: TEST loop")

    # DEX ----------------------------------------------------------------------
    d.click_w(tab_key(app, "dex"))
    assert app.tab == "dex"
    new_btn = [w for w in app.g_dexbtn.widgets if getattr(w, "label", "") == "+ NEW"][0]
    d.click_w(new_btn)
    assert app.g_ask.visible and app.ui.focus is app.in_ask
    d.typ("Rayquaza")
    d.shot("15_dex_new")
    d.key("Return")
    d.pump(0.3)
    assert app.profile["pokemon"] == "rayquaza", app.profile["pokemon"]
    share = [w for w in app.g_dexbtn.widgets if getattr(w, "label", "") == "SHARE"][0]
    paste = [w for w in app.g_dexbtn.widgets if getattr(w, "label", "") == "PASTE"][0]
    d.click_w(share)
    n0 = len(app.data["profiles"])
    d.click_w(paste)
    assert len(app.data["profiles"]) == n0 + 1, "paste should add a hunt"
    d.shot("16_dex")
    d.click(app.dex_list.ax() + 60, app.dex_list.ay() + 6)
    d.note("ok: DEX (%d hunts, active %s)" % (len(app.data["profiles"]), app.profile["name"]))

    # STATS / LOG / ALERT / MORE ---------------------------------------------------
    d.click_w(tab_key(app, "stats"))
    assert app.tab == "stats"
    d.shot("17_stats")
    d.click_w(tab_key(app, "log"))
    d.shot("18_log_empty")
    d.click_w(tab_key(app, "alert"))
    d.click_w(app.in_ntfy)
    d.typ("shiny-test-123")
    d.key("Return")
    assert app.settings["ntfy"] == "shiny-test-123"
    d.shot("19_alert")
    d.click_w(tab_key(app, "more"))
    d.shot("20_options_look")
    d.click_w(app.btn_sys)
    d.shot("21_options_system")
    d.click_w(app.btn_look)
    d.click(app.cy_theme.ax() + app.cy_theme.w - 6, app.cy_theme.ay() + 6, wait=0.6)
    assert app.settings["theme"] == "BLUE", app.settings["theme"]
    d.pump(0.5)
    d.shot("22_theme_blue")
    app.cy_theme.set_value("RED")
    app.set_theme("RED")
    d.pump(0.6)
    d.note("ok: STATS, LOG, ALERT, OPTIONS, themes")

    # help overlay ----------------------------------------------------------------
    app.open_tab("check")
    d.click_w(app.help_btn)
    assert app.overlay_open()
    d.shot("23_help")
    d.key("Escape")
    assert not app.overlay_open()
    app.open_about()
    d.shot("24_about")
    app.close_overlay()
    d.note("ok: help + about")

    # hunt! -------------------------------------------------------------------------
    app.set_active(app.data["profiles"][0]["id"])
    p = app.profile
    p["script"] = parse_script("press A hold 0.02\nwait 0.1\ncheck 0.4\n")[0]
    p["detect"]["threshold"] = 8.0
    p["detect"]["fps"] = 20
    app.load_profile_ui()
    app.close_panel()
    d.pump(0.6)
    assert not [i for i in app.readiness() if not i[1]], app.readiness()
    d.click_w(app.start_btn)
    d.pump(0.8)
    assert app.hunter is not None, "hunt should start"
    assert d.wait_for(lambda: p["encounters"] >= 3, 8), p["encounters"]
    d.shot("25_hunting", settle=0.2)
    plat.shiny = True
    assert d.wait_for(lambda: app.alert is not None, 8), "shiny alert should fire"
    d.pump(0.5)
    d.shot("26_shiny_celebration", settle=0.05)
    assert d.wait_for(lambda: app.menu.visible, 4), "menu should show after the celebration"
    d.pump(0.6)
    d.shot("27_shiny_menu")
    plat.shiny = False
    d.key("Return")
    d.pump(0.5)
    assert p.get("found"), "should be caught"
    d.pump(0.4)
    d.shot("28_caught", settle=0.1)
    assert app.data["log"] and app.data["log"][-1]["type"] == "Caught"
    assert any("Shiny" in t for t in d.sent), "a shiny alert should go out (%r)" % d.sent
    d.note("ok: hunt -> shiny -> caught after %d resets" % p["encounters"])

    app.open_panel("log")
    d.pump(0.6)
    d.shot("29_log")
    app.open_tab("stats")
    d.pump(0.3)
    d.shot("30_stats_found")

    # mini mode ------------------------------------------------------------------------
    app.enter_mini()
    d.pump(0.8)
    assert app.mini is not None
    d.shot("31_mini", win=app.mini.top)
    app.exit_mini()
    d.pump(0.4)
    assert app.mini is None
    d.note("ok: mini mode")

    # bigger window ----------------------------------------------------------------------
    app.open_tab("more")
    d.pump(0.3)
    cy = app.cy_size
    target = 3 if app.S < 3 else 2
    cy.set_value(target)
    app.set_size(target)
    d.pump(1.0)
    assert app.S == target, app.S
    d.shot("32_scale_%d" % target)
    d.note("ok: window size %dx" % target)
    app.save()


def run_selftest(outdir, keep_data=False):
    outdir = os.path.abspath(outdir)
    os.makedirs(outdir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="oddsbreaker-selftest-")
    old_data = paths.DATA_DIR
    paths.init(tmp)
    report = ["%s %s self-test" % (APP_NAME, __version__), "python %s" % sys.version.split()[0],
              "data dir %s" % tmp]
    code = 1
    root = None
    try:
        from .app import App
        from .store import Store
        from .system import StubPlatform
        st = Store()
        data = st.fresh()
        data["settings"]["legacy_checked"] = True
        data["settings"]["updates"] = False
        st.save(data)
        root = tk.Tk()
        plat = StubPlatform()
        app = App(root, plat, check_updates=False)
        sent = []
        app.notifier.send = lambda settings, title, text, *a, **k: sent.append(title) or 1
        drv = Driver(app, outdir)
        drv.sent = sent
        drv.note("scale %d, tk %s" % (app.S, tk.TkVersion))
        try:
            scenario(drv)
            report.extend(drv.log)
            report.append("ALL STEPS PASSED")
            code = 0
        except Exception:
            report.extend(drv.log)
            report.append("FAILED:\n" + traceback.format_exc())
            drv.shot("zz_failure")
        try:
            app.hunter and app.hunter.stop()
            app.on_close()
        except Exception:
            pass
    except Exception:
        report.append("FAILED TO START:\n" + traceback.format_exc())
    finally:
        try:
            if root is not None:
                root.destroy()
        except Exception:
            pass
        paths.init(old_data)
        if not keep_data:
            shutil.rmtree(tmp, ignore_errors=True)
    with open(os.path.join(outdir, "selftest.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print("\n".join(report[-3:]))
    return code
