from oddsbreaker.config import EMULATORS, TEMPLATES, emulator_preset
from oddsbreaker.script import (combo_label, compile_script, estimate_loop, keys_used,
                                parse_script, script_to_text, template_rows)


def test_templates_parse_and_round_trip():
    for name, text in TEMPLATES:
        rows, errs = parse_script(text)
        assert not errs, (name, errs)
        assert any(r["op"] == "check" for r in rows), name
        rows2, errs2 = parse_script(script_to_text(rows))
        assert rows2 == rows, name


def test_templates_compile_for_every_emulator():
    for name, text in TEMPLATES:
        rows, _ = parse_script(text)
        for emu, keys, _hint, _words in EMULATORS:
            steps, cerr = compile_script(rows, keys)
            needs_reset = "press RESET" in text and not keys["RESET"]
            needs_load = "press LOADSTATE" in text and not keys["LOADSTATE"]
            if emu == "Custom":
                assert cerr
            elif needs_reset or needs_load:
                assert cerr and "KEYS page" in cerr[0], (emu, name, cerr)
            elif "SELECT" in text and not keys["SELECT"]:
                assert cerr
            else:
                assert not cerr, (emu, name, cerr)


def test_parse_details_and_errors():
    rows, errs = parse_script("press a+b+start+select hold 0.3\nwait 1-2.5\npress key:f5 x3 gap 0.2\n"
                              "hold up 1.5\ncheck 4\nfoo bar\npress Q+\nwait abc")
    assert len(errs) == 3, errs
    assert rows[0]["btn"] == "A+B+START+SELECT" and rows[0]["hold"] == 0.3
    assert rows[1] == {"op": "wait", "lo": 1.0, "hi": 2.5}
    assert rows[2]["btn"] == "key:f5" and rows[2]["times"] == 3 and rows[2]["gap"] == 0.2
    assert combo_label("A+key:ctrl+key:up") == "A+CTRL+▲"


def test_compile_maps_buttons_to_keys():
    rows, _ = parse_script("press a+b+start+select hold 0.3\npress key:f5 x3")
    steps, cerr = compile_script(rows, emulator_preset("mGBA")[0])
    assert not cerr
    assert steps[0]["keys"] == ["x", "z", "enter", "backspace"]
    assert steps[1]["keys"] == ["f5"]
    steps, cerr = compile_script([{"op": "press", "btn": "X", "times": 1, "gap": 0.2, "hold": 0.1}],
                                 emulator_preset("mGBA")[0])
    assert cerr and "KEYS page" in cerr[0]


def test_estimate_and_keys_used():
    rows = template_rows("GBA SOFT RESET")
    assert estimate_loop(rows) > 10
    used = keys_used(rows, emulator_preset("mGBA")[0])
    assert {"x", "z", "enter", "backspace"} <= used
