"""Chiptune sound effects, synthesised into small WAV files on first use."""

import math
import os
import random
import struct
import wave

from . import paths
from .config import IS_WIN

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
    "milestone": [(784, 60, "sq25"), (1047, 60, "sq25"), (1319, 60, "sq25"),
                  ((1568, 2093), 200, "sq25")],
    "notify": [(1568, 50, "tri"), (2093, 110, "tri")],
    "shiny": [(1047, 55, "sq25"), (1319, 55, "sq25"), (1568, 55, "sq25"), (2093, 90, "sq25"),
              (0, 35, "sq"), (1568, 55, "sq25"), (2093, 55, "sq25"),
              ((2637, 3136), 140, "sq25"), ((2637, 3136), 60, "tri"), (3520, 40, "tri"),
              (4186, 160, "tri")],
}
VOLUMES = {"LOW": 0.10, "MED": 0.20, "HIGH": 0.32}


def _osc(kind, phase):
    if kind == "tri":
        return 1.0 - 4.0 * abs(phase - 0.5)
    if kind == "sq25":
        return 1.0 if phase < 0.25 else -1.0
    if kind == "noise":
        return random.uniform(-1.0, 1.0)
    return 1.0 if phase < 0.5 else -1.0


def synth(notes, rate=22050, vol=0.2):
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


def make_wav(notes, path, rate=22050, vol=0.2):
    w = wave.open(path, "wb")
    try:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(synth(notes, rate, vol))
    finally:
        w.close()


class Sounds(object):
    def __init__(self):
        self.mode = "ALL"
        self.volume = "MED"
        self.ready = set()
        self.ws = None
        if IS_WIN:
            try:
                import winsound
                self.ws = winsound
            except ImportError:
                self.ws = None

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
        if not self.ws:
            return
        self.prepare()
        try:
            self.ws.PlaySound(self.path(name),
                              self.ws.SND_FILENAME | self.ws.SND_ASYNC | self.ws.SND_NODEFAULT)
        except Exception:
            pass
