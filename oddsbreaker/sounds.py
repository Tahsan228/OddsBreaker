"""Chiptune sound effects, synthesised in memory and played with low lag.

On Windows the sounds go through a few waveOut "voices" that stay open for
the whole session. PlaySound (what winsound uses) opens the sound device on
every call, which is what made clicks feel late; an open voice starts
playing within a few milliseconds. If the sound device can't be opened,
PlaySound with small WAV files is the fallback.
"""

import math
import os
import random
import struct
import threading
import time
import wave

from . import paths
from .config import IS_WIN

RATE = 22050

# (frequency or (f1, f2...) for a chord, milliseconds, wave) ; 0 = rest
# waves: "sq" square, "sq25" thin square, "tri" triangle, "noise"
SOUND_DEFS = {
    "click": [(1800, 16, "sq25")],
    "tick": [(2400, 10, "sq25")],
    "open": [(660, 28, "sq25"), (880, 28, "sq25"), (1320, 50, "sq25")],
    "close": [(1320, 28, "sq25"), (880, 28, "sq25"), (660, 50, "sq25")],
    "start": [(523, 50, "sq"), (784, 50, "sq"), ((1047, 1568), 120, "sq25")],
    "stop": [(784, 50, "sq"), (523, 50, "sq"), ((392, 262), 120, "sq25")],
    "error": [(196, 70, "sq"), (0, 30, "sq"), (185, 120, "sq")],
    "ok": [(988, 40, "sq25"), (1319, 90, "sq25")],
    "boot": [(262, 40, "tri"), (392, 40, "tri"), (523, 40, "tri"), (784, 40, "tri"),
             ((1047, 1319, 1568), 260, "sq25")],
    "lid": [(98, 18, "noise"), (147, 24, "sq"), (0, 20, "sq"), (196, 30, "tri")],
    "power": [(330, 30, "tri"), (494, 30, "tri"), (659, 30, "tri"), (988, 60, "sq25")],
    "milestone": [(784, 60, "sq25"), (1047, 60, "sq25"), (1319, 60, "sq25"),
                  ((1568, 2093), 200, "sq25")],
    "notify": [(1568, 50, "tri"), (2093, 110, "tri")],
    "shiny": [(1047, 55, "sq25"), (1319, 55, "sq25"), (1568, 55, "sq25"), (2093, 90, "sq25"),
              (0, 35, "sq"), (1568, 55, "sq25"), (2093, 55, "sq25"),
              ((2637, 3136), 140, "sq25"), ((2637, 3136), 60, "tri"), (3520, 40, "tri"),
              (4186, 160, "tri")],
}
VOLUMES = {"LOW": 0.10, "MED": 0.20, "HIGH": 0.32}
# sounds that may cut each other off; the rest each get their own voice
SHORT = ("click", "tick")


def _osc(kind, phase):
    if kind == "tri":
        return 1.0 - 4.0 * abs(phase - 0.5)
    if kind == "sq25":
        return 1.0 if phase < 0.25 else -1.0
    if kind == "noise":
        return random.uniform(-1.0, 1.0)
    return 1.0 if phase < 0.5 else -1.0


def synth(notes, rate=RATE, vol=0.2):
    """-> 16-bit mono PCM bytes."""
    out = bytearray()
    for note in notes:
        freq, ms, kind = note[0], note[1], (note[2] if len(note) > 2 else "sq")
        n = int(rate * ms / 1000.0)
        freqs = freq if isinstance(freq, tuple) else (freq,)
        if not freqs or freqs[0] <= 0:
            out += b"\x00\x00" * n
            continue
        gain = vol / math.sqrt(len(freqs))
        attack = max(1, int(rate * 0.003))
        for i in range(n):
            env = min(1.0, i / float(attack)) * (1.0 - 0.75 * i / float(n))
            v = 0.0
            for f in freqs:
                v += _osc(kind, (i * f / float(rate)) % 1.0)
            s = int(max(-1.0, min(1.0, v * gain * env)) * 32767)
            out += struct.pack("<h", s)
    return bytes(out)


def make_wav(notes, path, rate=RATE, vol=0.2):
    w = wave.open(path, "wb")
    try:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(synth(notes, rate, vol))
    finally:
        w.close()


class WaveOut(object):
    """Open waveOut voices (Windows). Each voice plays one sound at a time;
    Windows mixes the voices, so a click never cuts off the shiny jingle."""

    def __init__(self, voices=4, rate=RATE, winmm=None):
        import ctypes
        from ctypes import wintypes
        self.ct = ctypes

        class WAVEFORMATEX(ctypes.Structure):
            _pack_ = 1
            _fields_ = [("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD),
                        ("nSamplesPerSec", wintypes.DWORD), ("nAvgBytesPerSec", wintypes.DWORD),
                        ("nBlockAlign", wintypes.WORD), ("wBitsPerSample", wintypes.WORD),
                        ("cbSize", wintypes.WORD)]

        class WAVEHDR(ctypes.Structure):
            _fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", wintypes.DWORD),
                        ("dwBytesRecorded", wintypes.DWORD), ("dwUser", ctypes.c_size_t),
                        ("dwFlags", wintypes.DWORD), ("dwLoops", wintypes.DWORD),
                        ("lpNext", ctypes.c_void_p), ("reserved", ctypes.c_size_t)]

        self.WAVEHDR = WAVEHDR
        w = self.winmm = winmm or ctypes.WinDLL("winmm")
        H = wintypes.HANDLE
        PH = ctypes.POINTER(WAVEHDR)
        w.waveOutOpen.argtypes = [ctypes.POINTER(H), wintypes.UINT, ctypes.POINTER(WAVEFORMATEX),
                                  ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD]
        w.waveOutOpen.restype = wintypes.UINT
        for fn in (w.waveOutPrepareHeader, w.waveOutUnprepareHeader, w.waveOutWrite):
            fn.argtypes = [H, PH, wintypes.UINT]
            fn.restype = wintypes.UINT
        for fn in (w.waveOutReset, w.waveOutClose):
            fn.argtypes = [H]
            fn.restype = wintypes.UINT
        fmt = WAVEFORMATEX(1, 1, rate, rate * 2, 2, 16, 0)
        self.voices = []
        for _i in range(voices):
            h = H()
            if w.waveOutOpen(ctypes.byref(h), 0xFFFFFFFF, ctypes.byref(fmt), 0, 0, 0) != 0:
                break
            self.voices.append({"h": h, "hdr": None, "until": 0.0, "name": ""})
        if not self.voices:
            raise OSError("no sound device")

    def _free(self, v):
        if v["hdr"] is not None:
            self.winmm.waveOutReset(v["h"])
            self.winmm.waveOutUnprepareHeader(v["h"], self.ct.byref(v["hdr"]),
                                              self.ct.sizeof(self.WAVEHDR))
            v["hdr"] = None

    def play(self, name, buf, nbytes, seconds):
        now = time.monotonic()
        # a short blip reuses the voice of the last blip; anything else
        # takes the voice that's been quiet the longest
        same = [v for v in self.voices if v["name"] == name and name in SHORT]
        v = same[0] if same else min(self.voices, key=lambda v: v["until"])
        self._free(v)
        hdr = self.WAVEHDR()
        hdr.lpData = self.ct.cast(buf, self.ct.c_void_p)
        hdr.dwBufferLength = nbytes
        size = self.ct.sizeof(self.WAVEHDR)
        if self.winmm.waveOutPrepareHeader(v["h"], self.ct.byref(hdr), size) != 0:
            raise OSError("waveOutPrepareHeader failed")
        v["hdr"] = hdr
        if self.winmm.waveOutWrite(v["h"], self.ct.byref(hdr), size) != 0:
            raise OSError("waveOutWrite failed")
        v["until"] = now + seconds
        v["name"] = name

    def close(self):
        for v in self.voices:
            try:
                self._free(v)
                self.winmm.waveOutClose(v["h"])
            except Exception:
                pass
        self.voices = []


class Sounds(object):
    def __init__(self):
        self.mode = "ALL"
        self.volume = "MED"
        self.ready = set()
        self.ws = None
        self.engine = None
        self.warming = False
        self.pcm = {}
        if IS_WIN:
            try:
                import winsound
                self.ws = winsound
            except ImportError:
                self.ws = None

    def start(self):
        """Open the sound device and make the sounds in the background, so
        the first sound is as quick as the rest."""
        if not IS_WIN:
            return
        self.warming = True
        t = threading.Thread(target=self._warm_up, name="sounds")
        t.daemon = True
        t.start()

    def _warm_up(self):
        try:
            self.engine = WaveOut()
            for vol in [self.volume] + [v for v in VOLUMES if v != self.volume]:
                for name in SOUND_DEFS:
                    self._pcm(vol, name)
        except Exception:
            pass  # PlaySound with WAV files takes over
        finally:
            self.warming = False

    def _pcm(self, volume, name):
        """(buffer, bytes, seconds) for one sound at one volume, made once."""
        key = (volume, name)
        snd = self.pcm.get(key)
        if snd is None and name in SOUND_DEFS:
            import ctypes
            data = synth(SOUND_DEFS[name], RATE, VOLUMES.get(volume, 0.2))
            # setdefault keeps whichever copy got here first, so every buffer
            # the sound card is given stays referenced (and alive) in self.pcm
            snd = self.pcm.setdefault(key, (ctypes.create_string_buffer(data, len(data)), len(data),
                                            len(data) / (2.0 * RATE)))
        return snd

    def path(self, name):
        return os.path.join(paths.SOUND_DIR, "%s_%s.wav" % (name, self.volume.lower()))

    def prepare(self):
        if not self.ws or self.volume in self.ready:
            return
        try:
            paths.ensure(paths.SOUND_DIR)
            for name, notes in SOUND_DEFS.items():
                p = self.path(name)
                if not os.path.exists(p):
                    make_wav(notes, p, vol=VOLUMES.get(self.volume, 0.2))
            self.ready.add(self.volume)
        except Exception:
            self.ws = None

    def play(self, name):
        if self.mode == "OFF" or (self.mode == "SHINY ONLY" and name not in ("shiny", "milestone")):
            return
        if self.engine is not None:
            snd = self._pcm(self.volume, name)
            if snd is not None:
                try:
                    self.engine.play(name, *snd)
                    return
                except Exception:
                    self.engine = None
        if self.warming or not self.ws:
            # while the fast device is still opening, skip the sound rather
            # than stall the window making WAV files for PlaySound
            return
        self.prepare()
        try:
            self.ws.PlaySound(self.path(name),
                              self.ws.SND_FILENAME | self.ws.SND_ASYNC | self.ws.SND_NODEFAULT)
        except Exception:
            pass

    def close(self):
        if self.engine is not None:
            self.engine.close()
            self.engine = None
