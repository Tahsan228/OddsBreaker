"""The low-lag sound player: voices are reused sensibly and cleaned up."""

import ctypes
import os
import types

import pytest

from oddsbreaker import sounds


def fake_winmm():
    log = []
    handles = iter(range(100, 200))

    def waveOutOpen(ph, dev, fmt, cb, inst, flags):
        ph._obj.value = next(handles)
        log.append(("open", ph._obj.value))
        return 0

    def op(name):
        def f(h, *a):
            log.append((name, h.value if hasattr(h, "value") else h))
            return 0
        return f

    w = types.SimpleNamespace(
        waveOutOpen=waveOutOpen, waveOutPrepareHeader=op("prepare"),
        waveOutUnprepareHeader=op("unprepare"), waveOutWrite=op("write"),
        waveOutReset=op("reset"), waveOutClose=op("close"))
    return w, log


def buf(n=200):
    return ctypes.create_string_buffer(b"\x00" * n, n)


def test_voices_keep_long_sounds_playing():
    w, log = fake_winmm()
    out = sounds.WaveOut(voices=3, winmm=w)
    assert [e for e in log if e[0] == "open"] == [("open", 100), ("open", 101), ("open", 102)]
    jingle = buf()
    out.play("shiny", jingle, 200, 5.0)
    shiny_voice = [v for v in out.voices if v["name"] == "shiny"][0]["h"].value
    for _ in range(6):
        out.play("click", buf(), 200, 0.02)
    resets = [h for name, h in log if name == "reset"]
    assert shiny_voice not in resets, "clicks must not cut off the shiny jingle"
    clicks = [v for v in out.voices if v["name"] == "click"]
    assert len(clicks) == 1, "repeated clicks reuse one voice"
    out.close()
    assert sorted(h for name, h in log if name == "close") == [100, 101, 102]
    assert out.voices == []


def test_no_sound_device_falls_back_quietly():
    w, _log = fake_winmm()
    w.waveOutOpen = lambda *a: 2  # MMSYSERR_BADDEVICEID
    with pytest.raises(OSError):
        sounds.WaveOut(winmm=w)
    s = sounds.Sounds()
    s.engine = None
    s.ws = None
    s.play("click")  # nothing to play through, and no error either


def test_sounds_are_made_once_and_never_stall():
    s = sounds.Sounds()
    click = s._pcm("MED", "click")
    assert s._pcm("MED", "click") is click, "made once, then reused"
    assert s._pcm("MED", "no such sound") is None
    played = []
    s.ws = types.SimpleNamespace(PlaySound=lambda *a: played.append(a), SND_FILENAME=1, SND_ASYNC=2,
                                 SND_NODEFAULT=4)
    s.warming = True
    s.play("click")
    assert played == [], "no slow PlaySound while the fast device is still opening"
    w, log = fake_winmm()
    s.engine = sounds.WaveOut(voices=2, winmm=w)
    s.play("open")
    assert [e[0] for e in log].count("write") == 1 and played == []
    assert ("MED", "open") in s.pcm, "a sound the warm-up hasn't made yet is made on the spot"


@pytest.mark.skipif(os.name != "nt", reason="Windows struct layout")
def test_windows_struct_sizes():
    from ctypes import wintypes
    assert ctypes.sizeof(wintypes.DWORD) == 4
    out = sounds.WaveOut.__new__(sounds.WaveOut)
    try:
        sounds.WaveOut.__init__(out, voices=1)
    except OSError:
        pass  # no sound card on the build machine is fine
    if hasattr(out, "WAVEHDR"):
        assert ctypes.sizeof(out.WAVEHDR) == (48 if ctypes.sizeof(ctypes.c_void_p) == 8 else 32)
        out.close()


def test_every_sound_synthesises():
    for name, notes in sounds.SOUND_DEFS.items():
        pcm = sounds.synth(notes)
        assert pcm and len(pcm) % 2 == 0, name
