import json
import os
import wave

from oddsbreaker import __version__, paths
from oddsbreaker.config import hotkey_parts, key_label, match_game
from oddsbreaker.dexnames import dex_no, poke_display, suggest_names
from oddsbreaker.notify import (StreamFiles, multipart, ntfy_url, parse_version,
                                valid_discord_url)
from oddsbreaker.sounds import SOUND_DEFS, make_wav
from oddsbreaker.stats import chance, eta, fmt_dur, luck, resets_for
from oddsbreaker.system import find_window_in, window_pattern_for


def test_names():
    assert dex_no("Mr. Mime") == 122 and dex_no("Ho-Oh") == 250 and dex_no("pecharunt") == 1025
    assert dex_no("zzz") is None and dex_no("25") == 25
    assert poke_display("mr-mime") == "MR MIME" and poke_display("ho-oh") == "HO-OH"
    assert suggest_names("pika")[0] == "pikachu"


def test_windows_and_games():
    assert window_pattern_for("mGBA - POKEMON FIRE (59.9 fps)") == "mGBA"
    assert window_pattern_for("DeSmuME 0.9.13 x64 SSE2 | Pokemon Platinum") == "DeSmuME"
    assert window_pattern_for("Azahar 2121.2 | Pokemon X") == "Azahar|Citra|Lime3DS"
    assert window_pattern_for("SomeEmu - My Game") == "My Game"
    wins = [(1, "OddsBreaker"), (2, "mGBA - POKEMON FIRE"), (3, "Azahar 2121"), (4, "ShinyDex")]
    assert find_window_in(wins, "mGBA") == 2 and find_window_in(wins, "Citra|Azahar") == 3
    assert find_window_in(wins, "oddsbreaker") is None and find_window_in(wins, "shinydex") is None
    assert match_game("FireRed / LeafGreen") == "FIRERED / LEAFGREEN"
    assert key_label("ctrl+r") == "CTRL+R" and key_label("num5") == "NUM 5"


def test_hotkey_parts():
    assert hotkey_parts("f8") == (0, 0x77)
    assert hotkey_parts("ctrl+shift+f9") == (0x2 | 0x4, 0x78)
    assert hotkey_parts("a") == (0, 0x41)
    assert hotkey_parts("") is None and hotkey_parts("ctrl") is None


def test_stats_maths():
    assert abs(chance(8192, 8192) - 0.632) < 0.001
    assert resets_for(0.5, 8192) == 5678
    assert 0.99 < luck(10, 8192) <= 1.0
    assert eta(0, 3600, 3600.0) == 3600.0 and eta(10, 5, 100) == 0
    assert fmt_dur(59) == "59S" and fmt_dur(3720) == "1H 2M" and fmt_dur(90000) == "1D 1H"


def test_notify_helpers(tmp_path):
    assert valid_discord_url("https://discord.com/api/webhooks/123/abc-DEF_9")
    assert valid_discord_url("https://canary.discord.com/api/webhooks/1/x")
    assert not valid_discord_url("https://evil.example/api/webhooks/1/x")
    assert ntfy_url("my-topic_1") == "https://ntfy.sh/my-topic_1"
    assert ntfy_url("bad topic!") is None and ntfy_url("https://ntfy.example/t") == "https://ntfy.example/t"
    body, ctype = multipart({"payload_json": json.dumps({"a": 1})}, {"f": ("x.png", b"PNG", "image/png")})
    boundary = ctype.split("boundary=")[1]
    assert body.count(boundary.encode()) == 3 and b'filename="x.png"' in body
    assert parse_version("v1.2.3") == (1, 2, 3) and parse_version("1.0") == (1, 0, 0)
    assert parse_version("v0.9") < parse_version("1.0.0") <= parse_version(__version__)
    old = paths.DATA_DIR
    try:
        paths.init(str(tmp_path))
        sf = StreamFiles()
        assert sf.update({"encounters": "1,234", "pokemon": "Mew"})
        assert open(os.path.join(paths.OBS_DIR, "encounters.txt")).read() == "1,234"
    finally:
        paths.init(old)


def test_sounds(tmp_path):
    path = os.path.join(str(tmp_path), "s.wav")
    for name in ("shiny", "boot", "click"):
        make_wav(SOUND_DEFS[name], path)
        wf = wave.open(path)
        assert wf.getnframes() > 100 and wf.getsampwidth() == 2
        wf.close()


def test_sprites_come_out_about_the_same_size():
    import math
    from oddsbreaker.sprites import MAIN_TARGET, sprite_scale
    # real Gen 5 sprite sizes, from a tiny Ralts to a huge Gholdengo
    sizes = [(23, 39), (36, 37), (43, 36), (41, 42), (51, 38), (38, 55), (50, 46), (65, 37),
             (47, 64), (57, 54), (74, 74), (90, 69), (103, 88), (110, 98), (119, 105)]
    for S in (2, 3):
        for w, h in sizes:
            k = sprite_scale(w, h, S, MAIN_TARGET, 140, 82)
            side = math.sqrt(w * h) * k / S
            assert 0.75 * MAIN_TARGET <= side <= 1.2 * MAIN_TARGET, (S, w, h, k, side)
            assert w * k <= 140 * S and h * k <= 82 * S, "always fits the screen"
    assert sprite_scale(400, 300, 1, MAIN_TARGET, 140, 82) == 0.25, "huge pictures shrink to fit"


def test_sprite_downloads_retry_after_a_failure(monkeypatch):
    import queue
    from oddsbreaker import sprites

    def offline(url, *a, **k):
        raise OSError("no internet")

    monkeypatch.setattr(sprites, "http_get", offline)
    cache = sprites.SpriteCache(queue.Queue())
    cache._fetch_anim(9999, True)
    cache._fetch(9999)
    assert (9999, True) in cache.anim_failed and 9999 in cache.failed
    # not straight away...
    assert cache.anim(9999, True) is None and not cache.anim_pending
    assert cache.lookup("") is None
    # ...but once the wait is over it tries again
    cache.anim_failed[(9999, True)] -= sprites.RETRY_AFTER + 1
    assert sprites.SpriteCache.may_try(cache.anim_failed, (9999, True))


def test_folders_can_be_made_twice_at_once(tmp_path, monkeypatch):
    # two download threads both see "no folder" and both create it
    folder = tmp_path / "anim"
    folder.mkdir()
    real, calls = os.path.isdir, []

    def isdir_late(p):
        # the other thread made the folder just after this one looked
        calls.append(p)
        return False if len(calls) == 1 else real(p)

    monkeypatch.setattr(paths.os.path, "isdir", isdir_late)
    assert paths.ensure(str(folder)) == str(folder)
