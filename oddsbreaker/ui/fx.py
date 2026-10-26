"""Pixel-art effects: particles, dissolves, blinds, a CRT power-on, a scan
line and screen shake. Everything is either a pre-rendered frame sequence or
a few plain canvas rectangles, so it stays cheap."""

import math
import random
import time

from ..pixel import PAL, to_hex


def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_out_back(t, s=1.7):
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


def bounce(t):
    if t < 1 / 2.75:
        return 7.5625 * t * t
    if t < 2 / 2.75:
        t -= 1.5 / 2.75
        return 7.5625 * t * t + 0.75
    if t < 2.5 / 2.75:
        t -= 2.25 / 2.75
        return 7.5625 * t * t + 0.9375
    t -= 2.625 / 2.75
    return 7.5625 * t * t + 0.984375


class Particles(object):
    """Square pixel particles with gravity. Coordinates in art pixels."""

    def __init__(self, ui, limit=160):
        self.ui = ui
        self.parts = []
        self.limit = limit
        self.last = None

    def _add(self, x, y, vx, vy, life, colors, size, gravity, drag):
        if len(self.parts) >= self.limit:
            return
        S = self.ui.S
        s = size * S
        col = colors[0]
        it = self.ui.cv.create_rectangle(x * S, y * S, x * S + s, y * S + s,
                                         fill=col, outline="", width=0)
        self.parts.append({"it": it, "x": x, "y": y, "vx": vx, "vy": vy, "t0": time.monotonic(),
                           "life": life, "colors": colors, "ci": 0, "s": s, "g": gravity,
                           "drag": drag})

    def _start(self):
        if self.last is None:
            self.last = time.monotonic()
            self.ui.anims.append(self.step)

    def burst(self, x, y, n=40, colors=None, speed=(40, 120), life=(0.6, 1.3), gravity=140,
              size=(1, 2), angle=None, spread=math.pi * 2, drag=0.0):
        colors = colors or [[PAL["gold_hi"], PAL["gold"], PAL["gold_dk"]],
                            [PAL["white"], PAL["gold_hi"], PAL["gold"]],
                            [PAL["pink"], PAL["red_hi"], PAL["red_md"]],
                            [PAL["cyan"], PAL["blue_lt"], PAL["blue"]]]
        for _ in range(n):
            a = (angle if angle is not None else 0) + random.uniform(-spread / 2, spread / 2)
            if angle is None:
                a = random.uniform(0, math.pi * 2)
            sp = random.uniform(*speed)
            cs = random.choice(colors)
            self._add(x, y, math.cos(a) * sp, math.sin(a) * sp, random.uniform(*life),
                      [to_hex(c) for c in cs], random.choice(size if isinstance(size, tuple) else (size,)),
                      gravity, drag)
        self._start()

    def rain(self, x0, x1, y, n=40, colors=None, life=(1.2, 2.2)):
        colors = colors or [[PAL["gold_hi"], PAL["gold"]], [PAL["pink"], PAL["red_md"]],
                            [PAL["cyan"], PAL["blue"]], [PAL["green"], PAL["green_dk"]],
                            [PAL["white"], PAL["bezel_sh"]]]
        for _ in range(n):
            cs = random.choice(colors)
            self._add(random.uniform(x0, x1), y - random.uniform(0, 40), random.uniform(-18, 18),
                      random.uniform(15, 60), random.uniform(*life), [to_hex(c) for c in cs],
                      random.choice((2, 2, 3)), 70, 0.0)
        self._start()

    def step(self, now):
        if not self.ui.alive:
            return False
        dt = min(0.05, now - (self.last or now))
        self.last = now
        S = self.ui.S
        cv = self.ui.cv
        keep = []
        for p in self.parts:
            age = now - p["t0"]
            if age >= p["life"]:
                cv.delete(p["it"])
                continue
            p["vy"] += p["g"] * dt
            if p["drag"]:
                k = max(0.0, 1.0 - p["drag"] * dt)
                p["vx"] *= k
                p["vy"] *= k
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            ci = min(len(p["colors"]) - 1, int(age / p["life"] * len(p["colors"])))
            if ci != p["ci"]:
                p["ci"] = ci
                cv.itemconfig(p["it"], fill=p["colors"][ci])
            px, py = int(p["x"]) * S, int(p["y"]) * S
            cv.coords(p["it"], px, py, px + p["s"], py + p["s"])
            keep.append(p)
        self.parts = keep
        if not keep:
            self.last = None
            return False
        return "fast"

    def clear(self):
        for p in self.parts:
            self.ui.cv.delete(p["it"])
        self.parts = []


class FramePlayer(object):
    """Plays a Frames widget once (or looping) at a fixed rate, then hides it."""

    def __init__(self, ui, frames_widget):
        self.ui = ui
        self.w = frames_widget
        self.seq = []
        self.t0 = 0.0
        self.fps = 30
        self.loop = False
        self.running = False
        self.on_done = None
        frames_widget.show(False)

    def play(self, seq=None, fps=30, loop=False, on_done=None):
        self.seq = list(seq) if seq is not None else list(range(len(self.w.photos)))
        self.fps, self.loop, self.on_done = fps, loop, on_done
        self.t0 = time.monotonic()
        self.w.set_frame(self.seq[0])
        self.w.show(True)
        if not self.running:
            self.running = True
            self.ui.anims.append(self.step)

    def stop(self):
        self.running = False
        self.w.show(False)

    def step(self, now):
        if not self.running or not self.ui.alive:
            self.running = False
            return False
        k = int((now - self.t0) * self.fps)
        if k >= len(self.seq):
            if self.loop:
                self.t0 = now
                k = 0
            else:
                self.running = False
                self.w.show(False)
                if self.on_done:
                    self.on_done()
                return False
        self.w.set_frame(self.seq[k])
        return "fast"


class BlockDissolve(object):
    """Retro 'fizzle': a grid of solid blocks covers the screen, then blinks away
    in a scattered order to reveal what's underneath. Plain rectangles, so it
    stays fast (overlays with see-through pixels are slow in Tk)."""
    _n = [0]

    def __init__(self, ui, group, x, y, w, h, block=7, seed=11):
        BlockDissolve._n[0] += 1
        self.ui, self.group = ui, group
        self.tag = "fizz%d" % BlockDissolve._n[0]
        tags = group.tags() + (self.tag,)
        self.cells = []
        for j in range(0, h, block):
            for i in range(0, w, block):
                it = ui.cv.create_rectangle(0, 0, 0, 0, fill="#000000", outline="", width=0,
                                            state="hidden", tags=tags)
                self.cells.append((it, x + i, y + j, min(block, w - i), min(block, h - j)))
        self.order = list(range(len(self.cells)))
        random.Random(seed).shuffle(self.order)
        self.running = False
        self.t0 = 0.0
        self.dur = 0.3
        self.hidden = 0

    def _place(self):
        S = self.ui.S
        gx, gy = self.group.ox(), self.group.oy()
        cv = self.ui.cv
        for it, x0, y0, bw, bh in self.cells:
            cv.coords(it, (gx + x0) * S, (gy + y0) * S, (gx + x0 + bw) * S, (gy + y0 + bh) * S)

    def play(self, color, dur=0.3):
        cv = self.ui.cv
        self._place()
        cv.itemconfig(self.tag, fill=to_hex(color), state="normal")
        cv.tag_raise(self.tag)
        self.t0 = time.monotonic()
        self.dur = dur
        self.hidden = 0
        if not self.running:
            self.running = True
            self.ui.anims.append(self.step)

    def step(self, now):
        if not self.ui.alive:
            return False
        t = (now - self.t0) / self.dur
        n = len(self.cells) if t >= 1.0 else int(len(self.cells) * ease_out(max(0.0, t)))
        cv = self.ui.cv
        while self.hidden < n:
            cv.itemconfig(self.cells[self.order[self.hidden]][0], state="hidden")
            self.hidden += 1
        if t >= 1.0:
            self.running = False
            return False
        return "fast"


class Blinds(object):
    """Horizontal bands that shrink away to reveal a page."""

    def __init__(self, ui, group, x, y, w, h, color, bands=8):
        self.ui = ui
        self.x, self.y, self.w, self.h = x, y, w, h
        self.group = group
        self.bands = bands
        S = ui.S
        self.items = [ui.cv.create_rectangle(0, 0, 0, 0, fill=to_hex(color), outline="", width=0,
                                             state="hidden", tags=group.tags())
                      for _ in range(bands)]
        self.t0 = 0.0
        self.dur = 0.18
        self.running = False
        self.S = S

    def play(self, dur=0.18):
        self.dur = dur
        self.t0 = time.monotonic()
        for it in self.items:
            self.ui.cv.itemconfig(it, state="normal")
            self.ui.cv.tag_raise(it)
        self._place(0.0)
        if not self.running:
            self.running = True
            self.ui.anims.append(self.step)

    def _place(self, t):
        S = self.S
        gx, gy = self.group.ox(), self.group.oy()
        bh = self.h / float(self.bands)
        for i, it in enumerate(self.items):
            # stagger: lower bands finish a little later
            local = max(0.0, min(1.0, (t * 1.6) - i * 0.6 / self.bands))
            hh = bh * (1.0 - ease_out(local))
            y0 = self.y + i * bh
            self.ui.cv.coords(it, (gx + self.x) * S, (gy + y0) * S,
                              (gx + self.x + self.w) * S, (gy + y0) * S + int(hh) * S)

    def step(self, now):
        if not self.ui.alive:
            return False
        t = (now - self.t0) / self.dur
        if t >= 1.0:
            for it in self.items:
                self.ui.cv.itemconfig(it, state="hidden")
            self.running = False
            return False
        self._place(t)
        return "fast"


class CRT(object):
    """Old-TV power-on: a dot, a line, then the picture."""

    def __init__(self, ui, group, x, y, w, h, on_done=None):
        self.ui = ui
        self.group = group
        self.x, self.y, self.w, self.h = x, y, w, h
        self.on_done = on_done
        cv, tags = ui.cv, group.tags()
        self.cover = cv.create_rectangle(0, 0, 0, 0, fill="#0A0F0A", outline="", width=0, tags=tags)
        self.beam = cv.create_rectangle(0, 0, 0, 0, fill="#F4FFF0", outline="", width=0, tags=tags)
        self.t0 = time.monotonic()
        self.running = True
        self._place(0.0)
        ui.anims.append(self.step)

    def _rect(self, it, x, y, w, h):
        S = self.ui.S
        gx, gy = self.group.ox(), self.group.oy()
        self.ui.cv.coords(it, (gx + x) * S, (gy + y) * S, (gx + x + w) * S, (gy + y + h) * S)

    def _place(self, t):
        x, y, w, h = self.x, self.y, self.w, self.h
        self._rect(self.cover, x, y, w, h)
        if t < 0.35:
            k = ease_out(t / 0.35)
            bw = max(2, int(w * k))
            self._rect(self.beam, x + (w - bw) // 2, y + h // 2, bw, 1)
        elif t < 0.7:
            k = ease_out((t - 0.35) / 0.35)
            bh = max(1, int(h * k))
            self._rect(self.beam, x, y + (h - bh) // 2, w, bh)
        else:
            self._rect(self.beam, x, y, w, h)

    def step(self, now):
        if not self.ui.alive or not self.running:
            return False
        t = (now - self.t0) / 0.42
        if t >= 1.0:
            self.finish()
            if self.on_done:
                self.on_done()
            return False
        self._place(t)
        return "fast"

    def finish(self):
        """Stop at once (no on_done)."""
        if self.running:
            self.running = False
            self.ui.cv.delete(self.cover)
            self.ui.cv.delete(self.beam)


class Scanner(object):
    """A glowing line that sweeps up and down the screen while checking."""

    def __init__(self, ui, group, x, y, w, h):
        self.ui = ui
        self.group = group
        self.x, self.y, self.w, self.h = x, y, w, h
        tags = group.tags()
        cv = ui.cv
        self.trail = cv.create_rectangle(0, 0, 0, 0, fill=to_hex(PAL["green_dk"]), outline="",
                                         width=0, state="hidden", tags=tags)
        self.line = cv.create_rectangle(0, 0, 0, 0, fill=to_hex(PAL["green"]), outline="",
                                        width=0, state="hidden", tags=tags)
        self.on = False
        self.t0 = 0.0
        ui.anims.append(self.step)

    def set_on(self, v):
        v = bool(v)
        if v == self.on:
            return
        self.on = v
        self.t0 = time.monotonic()
        st = "normal" if v else "hidden"
        self.ui.cv.itemconfig(self.line, state=st)
        self.ui.cv.itemconfig(self.trail, state=st)
        if v:
            self.ui.cv.tag_raise(self.trail)
            self.ui.cv.tag_raise(self.line)

    def step(self, now):
        if not self.ui.alive:
            return False
        if not self.on or not self.group.shown():
            return True
        S = self.ui.S
        gx, gy = self.group.ox(), self.group.oy()
        period = 1.1
        ph = ((now - self.t0) % period) / period
        tri = ph * 2 if ph < 0.5 else 2 - ph * 2
        yy = self.y + int(tri * (self.h - 2))
        d = 1 if ph < 0.5 else -1
        ty = yy - 3 * d if d > 0 else yy + 1
        x0, x1 = (gx + self.x) * S, (gx + self.x + self.w) * S
        self.ui.cv.coords(self.line, x0, (gy + yy) * S, x1, (gy + yy + 1) * S)
        self.ui.cv.coords(self.trail, x0, (gy + min(ty, ty + 3)) * S, x1, (gy + max(ty, ty + 3)) * S)
        return "fast"


class Shake(object):
    """Jiggles the whole window for a moment (the shiny 'hit')."""

    def __init__(self, app, dur=0.45, amp=4):
        self.app = app
        self.t0 = time.monotonic()
        self.dur, self.amp = dur, amp
        app.ui.anims.append(self.step)

    def step(self, now):
        app = self.app
        if not app.ui.alive:
            return False
        t = (now - self.t0) / self.dur
        if t >= 1.0:
            app.shake_off = (0, 0)
            app.apply_geometry()
            return False
        k = (1 - t) * self.amp * app.S / 2.0
        app.shake_off = (int(math.sin(now * 70) * k), int(math.cos(now * 55) * k * 0.6))
        app.apply_geometry()
        return "fast"
