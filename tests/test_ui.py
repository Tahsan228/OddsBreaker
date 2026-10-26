"""Full UI walk-through (needs a display; CI runs it under xvfb)."""

import os

import pytest


def have_display():
    if os.name == "nt":
        return True
    if not os.environ.get("DISPLAY"):
        return False
    try:
        import tkinter
        r = tkinter.Tk()
        r.destroy()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not have_display(), reason="no display")
def test_selftest(tmp_path):
    from oddsbreaker.selftest import run_selftest
    out = str(tmp_path)
    code = run_selftest(out)
    report = open(os.path.join(out, "selftest.txt"), encoding="utf-8").read()
    assert code == 0, report
    assert "ALL STEPS PASSED" in report


@pytest.mark.skipif(not have_display(), reason="no display")
def test_first_run_offers_shinydex_import(tmp_path, monkeypatch):
    """A brand-new install finds an old ShinyDex save and imports it."""
    import json
    import tkinter as tk
    from oddsbreaker import paths
    from oddsbreaker.app import App
    from oddsbreaker.selftest import Driver
    from oddsbreaker.system import StubPlatform
    from test_store import V1_SAVE
    home = os.path.join(str(tmp_path), "home")
    old = os.path.join(home, "Downloads", "Untitled", "ShinyDex_data")
    os.makedirs(old)
    with open(os.path.join(old, "profiles.json"), "w") as f:
        json.dump(V1_SAVE, f)
    monkeypatch.setenv("HOME", home)
    monkeypatch.setenv("USERPROFILE", home)
    data_dir = os.path.join(str(tmp_path), "data")
    keep = paths.DATA_DIR
    paths.init(data_dir)
    root = tk.Tk()
    try:
        app = App(root, StubPlatform(), check_updates=False)
        d = Driver(app)
        assert d.wait_for(lambda: app.overlay_open(), 8), "the import offer should appear"
        assert "WELCOME BACK" in app.ov_title.text
        yes = [b for b in app.ov_btns if b.visible and b.label == "IMPORT"][0]
        d.click_w(yes)
        d.pump(0.3)
        names = [p["name"] for p in app.data["profiles"]]
        assert names == ["Bulbasaur"], names
        assert app.profile["encounters"] == 321
        assert app.settings["legacy_checked"]
        app.on_close()
        with open(os.path.join(data_dir, "profiles.json")) as f:
            assert json.load(f)["profiles"][0]["name"] == "Bulbasaur"
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
        paths.init(keep)


@pytest.mark.skipif(not have_display(), reason="no display")
def test_start_hotkey_label_follows_settings(tmp_path):
    """The START button and status texts name whatever start key you picked."""
    import tkinter as tk
    from oddsbreaker import paths
    from oddsbreaker.app import App
    from oddsbreaker.system import StubPlatform
    keep = paths.DATA_DIR
    paths.init(str(tmp_path))
    root = tk.Tk()
    try:
        app = App(root, StubPlatform(), check_updates=False)
        assert app.start_key() == "F8" and "F8" in app.start_btn.hint
        app.set_hotkey("toggle", "f7")
        assert app.start_key() == "F7" and "F7" in app.start_btn.hint
        app.set_hotkey("toggle", "")
        assert app.start_key() == "" and "works anywhere" not in app.start_btn.hint
        app.on_close()
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass
        paths.init(keep)


def make_app(tmp_path, effects="FULL", name="data"):
    import tkinter as tk
    from oddsbreaker import paths
    from oddsbreaker.app import App
    from oddsbreaker.store import Store
    from oddsbreaker.system import StubPlatform
    paths.init(os.path.join(str(tmp_path), name))
    st = Store()
    data = st.fresh()
    data["settings"].update(legacy_checked=True, updates=False, effects=effects)
    data["welcomed"] = True
    st.save(data)
    root = tk.Tk()
    return root, App(root, StubPlatform(), check_updates=False)


@pytest.mark.skipif(not have_display(), reason="no display")
def test_boot_show_opens_and_can_be_skipped(tmp_path):
    from oddsbreaker import paths
    from oddsbreaker.selftest import Driver
    keep = paths.DATA_DIR
    try:
        root, app = make_app(tmp_path)
        d = Driver(app)
        assert app.booting and app.boot.lid_item is not None, "starts with the lid shut"
        assert d.wait_for(lambda: not app.booting, 6), "the show ends by itself"
        assert app.boot.lid_item is None and not app.boot.g_splash.visible
        app.on_close()

        root, app = make_app(tmp_path, name="data2")
        d = Driver(app)
        d.pump(0.1)
        d.click(100, 100)
        assert not app.booting, "a click skips it"
        assert app.boot.lid_item is None
        app.on_close()

        root, app = make_app(tmp_path, effects="LITE", name="data3")
        assert app.booting and app.boot.lid_item is None, "LITE: no lid, just the power-on"
        app.on_close()

        root, app = make_app(tmp_path, effects="OFF", name="data4")
        assert app.boot is None and not app.booting
        app.on_close()
    finally:
        paths.init(keep)


@pytest.mark.skipif(not have_display(), reason="no display")
def test_update_check_runs_at_start_and_offers_the_download(tmp_path, monkeypatch):
    import tkinter as tk
    from oddsbreaker import app as app_mod, paths
    from oddsbreaker.store import Store
    from oddsbreaker.selftest import Driver
    from oddsbreaker.system import StubPlatform
    calls, opened = [], []
    monkeypatch.setattr(app_mod, "check_for_update", lambda q: calls.append(q))
    monkeypatch.setattr(app_mod, "open_url", lambda url: opened.append(url))
    keep = paths.DATA_DIR
    paths.init(os.path.join(str(tmp_path), "upd"))
    st = Store()
    data = st.fresh()
    data["settings"].update(legacy_checked=True, effects="OFF", last_update_check="2099-01-01")
    data["welcomed"] = True
    st.save(data)
    root = tk.Tk()
    try:
        app = app_mod.App(root, StubPlatform(), check_updates=True)
        d = Driver(app)
        assert d.wait_for(lambda: calls, 4), "checks for updates every time it starts"
        app.q.put((None, "update", "v9.9.9", "https://example.com/v9.9.9"))
        assert d.wait_for(lambda: app.overlay_open(), 3), "a new version gets a prompt"
        assert "UPDATE" in app.ov_title.text
        get = [b for b in app.ov_btns if b.visible and b.label == "DOWNLOAD"][0]
        later = [b for b in app.ov_btns if b.visible and b.label == "LATER"][0]
        assert get.visible and app.tab_btns["more"].badge
        d.click_w(later)
        assert not app.overlay_open() and app.settings["update_snoozed"] == "v9.9.9"
        app.q.put((None, "update", "v9.9.9", "https://example.com/v9.9.9"))
        d.pump(0.4)
        assert not app.overlay_open(), "LATER means no prompt for that version again"
        app.q.put((None, "update", "v9.9.10", "https://example.com/v9.9.10"))
        assert d.wait_for(lambda: app.overlay_open(), 3), "but a newer one asks again"
        d.click_w([b for b in app.ov_btns if b.visible and b.label == "DOWNLOAD"][0])
        assert opened == ["https://example.com/v9.9.10"]
        app.on_close()
    finally:
        paths.init(keep)
