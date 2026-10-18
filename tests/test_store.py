import json
import os

import pytest

from oddsbreaker import paths
from oddsbreaker.script import compile_script
from oddsbreaker.store import (SAVE_VERSION, Store, default_profile, drop_untouched_starter,
                               export_code, export_csv, import_code, merge_legacy, record_count,
                               record_score, record_session)

V1_SAVE = {
    "version": 1, "active": "abc123def456",
    "profiles": [{
        "id": "abc123def456", "name": "Bulbasaur", "pokemon": "bulbasaur",
        "game": "FireRed / LeafGreen", "odds": 8192, "emulator": "VisualBoyAdvance-M",
        "window": "VisualBoyAdvance",
        "keys": {"A": "z", "B": "x", "X": "", "Y": "", "L": "a", "R": "s", "START": "enter",
                 "SELECT": "backspace", "RESET": "ctrl+r", "LOADSTATE": "f1", "UP": "up",
                 "DOWN": "down", "LEFT": "left", "RIGHT": "right"},
        "sequence": "# 1. Soft reset\npress A+B+START+SELECT hold 0.3\nwait 3\n# 2. Title\n"
                    "press A x5 gap 0.8\nwait 1~2.5   # random\npress A x3 gap 0.9\nwait 2\ncheck 5\n",
        "detect": {"mode": "compare", "region": None, "relative": True, "refs": [],
                   "pixel_tol": 40, "threshold": 15.0, "colors": [], "color_tol": 28,
                   "color_pct": 3.0, "fps": 12},
        "encounters": 321, "seconds": 999.5, "phases": [], "found": None,
        "created": "2026-10-15 09:38:31"}],
    "log": [{"date": "2026-10-15 10:00:00", "pokemon": "pidgey", "type": "Phase", "encounters": 10}],
    "settings": {"topmost": False, "pos": "+1190+331"},
}


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def test_v1_migration(tmp_path):
    path = os.path.join(str(tmp_path), "old", "profiles.json")
    write(path, V1_SAVE)
    data = Store(path).load()
    p = data["profiles"][0]
    assert data["version"] == SAVE_VERSION
    assert "sequence" not in p and len(p["script"]) >= 8
    assert p["script"][0]["op"] == "note"
    assert p["game"] == "FIRERED / LEAFGREEN" and p["emulator"] == "VBA-M"
    assert p["keys"]["A"] == "z" and p["encounters"] == 321
    steps, cerr = compile_script(p["script"], p["keys"])
    assert not cerr and any(s["op"] == "check" for s in steps)
    s = data["settings"]
    assert s["pos"] == "+1190+331" and s["sound"] == "ALL" and s["hotkeys"]["toggle"] == "f8"


def test_save_backup_and_recovery(tmp_path):
    path = os.path.join(str(tmp_path), "profiles.json")
    st = Store(path)
    data = st.fresh()
    data["profiles"][0]["encounters"] = 42
    st.save(data)
    st.save(data)
    assert os.path.exists(path + ".bak")
    backups = os.listdir(os.path.join(str(tmp_path), "backups"))
    assert len(backups) == 1 and backups[0].startswith("profiles-")
    with open(path, "w") as f:
        f.write("{broken")
    assert Store(path).load()["profiles"][0]["encounters"] == 42, "falls back to .bak"
    fresh = Store(os.path.join(str(tmp_path), "nope", "x.json")).load()
    assert fresh["profiles"][0]["pokemon"] == "charmander" and not fresh.get("welcomed")


def test_share_code_round_trip():
    p = default_profile("Gible hunt", "gible", "melonDS", "DIAMOND/PEARL/PLAT")
    p["detect"]["region"] = [10, 20, 30, 40]
    p["detect"]["refs"] = [{"w": 30, "h": 40, "data": "AAAA"}]
    p["encounters"] = 999
    code = export_code(p)
    assert code.startswith("OB1-") and len(code) < 2000
    q = import_code("hey, try my setup:\n" + code + "\n")
    assert q["pokemon"] == "gible" and q["emulator"] == "melonDS"
    assert q["detect"]["region"] == [10, 20, 30, 40] and q["detect"]["refs"] == []
    assert q["encounters"] == 0 and q["id"] != p["id"]
    with pytest.raises(ValueError):
        import_code("nothing here")
    with pytest.raises(ValueError):
        import_code(code[:-8])


def test_merge_legacy_and_starter(tmp_path):
    old = os.path.join(str(tmp_path), "ShinyDex_data", "profiles.json")
    write(old, V1_SAVE)
    data = Store(os.path.join(str(tmp_path), "new.json")).fresh()
    added = merge_legacy(data, old)
    assert added == 1 and len(data["profiles"]) == 2
    drop_untouched_starter(data)
    assert [p["name"] for p in data["profiles"]] == ["Bulbasaur"]
    assert data["active"] == data["profiles"][0]["id"]
    assert len(data["log"]) == 1
    assert merge_legacy(data, old) == 0, "importing twice adds nothing"


def test_stats_records_and_csv(tmp_path):
    p = default_profile()
    record_count(p, 3)
    record_count(p)
    assert sum(p["daily"].values()) == 4
    for i in range(50):
        record_score(p, i)
    assert len(p["scores"]) == 40 and p["scores"][-1] == 49
    record_session(p, "2026-10-16 10:00:00", 120, 30)
    assert p["sessions"][0]["resets"] == 30
    data = Store(os.path.join(str(tmp_path), "x.json")).fresh()
    data["log"].append({"date": "2026-10-16", "pokemon": "mew", "type": "Caught", "encounters": 5})
    hunts, shinies = export_csv(data, str(tmp_path))
    assert "charmander" in open(hunts).read() and "mew" in open(shinies).read()


def test_paths_override(tmp_path):
    old = paths.DATA_DIR
    try:
        paths.init(str(tmp_path))
        assert paths.SAVE_FILE == os.path.join(str(tmp_path), "profiles.json")
        assert paths.OBS_DIR.startswith(str(tmp_path))
    finally:
        paths.init(old)


def test_legacy_candidates_finds_downloads_subfolder(tmp_path, monkeypatch):
    from oddsbreaker.store import legacy_candidates
    home = os.path.join(str(tmp_path), "home")
    save = os.path.join(home, "Downloads", "Untitled", "ShinyDex_data", "profiles.json")
    write(save, V1_SAVE)
    monkeypatch.setenv("HOME", home)
    monkeypatch.setenv("USERPROFILE", home)
    assert save in legacy_candidates()
