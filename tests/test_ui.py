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
