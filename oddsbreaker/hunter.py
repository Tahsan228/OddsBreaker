"""The hunting loop. Runs in a background thread and reports to the app
through a queue as (hunter, event, *args) tuples."""

import random
import threading
import time
import traceback

from .detect import score_frame


class HuntError(Exception):
    pass


class Hunter(threading.Thread):
    """Plays the compiled steps over and over until a CHECK sees a shiny.

    Events: state(running|paused|stopped), step(row), checking(bool),
    check(score, shiny, samples), count, loop(seconds), shiny(payload),
    error(text). In test mode it plays the steps once and sends
    test_check(score, shiny) and test_done(info) instead of counting.
    """

    def __init__(self, plat, hwnd, steps, det, refs_raw, profile, out, test=False):
        threading.Thread.__init__(self, name="hunter")
        self.daemon = True
        self.plat, self.hwnd, self.steps = plat, hwnd, steps
        self.det, self.refs_raw, self.profile, self.out = det, refs_raw, profile, out
        self.test = test
        self.stop_ev = threading.Event()
        self.held = []
        self.state = None
        self.last_sent = {}
        self.lock = threading.Lock()

    def stop(self):
        self.stop_ev.set()

    def emit(self, *args):
        self.out.put((self,) + args)

    def set_state(self, s):
        if s != self.state:
            self.state = s
            self.emit("state", s)

    def sleep(self, t):
        """Sleep, but wake up at once on stop. Returns False if stopped."""
        return not self.stop_ev.wait(max(0.0, t))

    def gate(self):
        """Only press keys while the emulator is the active window."""
        while not self.stop_ev.is_set():
            if not self.plat.window_exists(self.hwnd):
                raise HuntError("The emulator window was closed.")
            if self.plat.is_foreground(self.hwnd):
                self.set_state("running")
                return True
            self.set_state("paused")
            self.stop_ev.wait(0.25)
        return False

    def sent_recently(self, key, within=0.6):
        with self.lock:
            t = self.last_sent.get(key)
        return t is not None and time.monotonic() - t < within

    def tap(self, keys, hold):
        if not self.gate():
            return False
        now = time.monotonic()
        with self.lock:
            for k in keys:
                self.last_sent[k] = now
        for k in keys:
            self.plat.key_down(k)
            self.held.append(k)
            time.sleep(0.012)
        self.sleep(hold)
        self.release()
        return not self.stop_ev.is_set()

    def release(self):
        while self.held:
            k = self.held.pop()
            try:
                self.plat.key_up(k)
            except Exception:
                pass
            with self.lock:
                self.last_sent[k] = time.monotonic()

    def run(self):
        try:
            self.set_state("running")
            while not self.stop_ev.is_set():
                t_loop = time.monotonic()
                scores = []
                for st in self.steps:
                    if self.stop_ev.is_set():
                        break
                    op = st["op"]
                    self.emit("step", st.get("row", 0))
                    if op == "press":
                        for _ in range(st["times"]):
                            if not self.tap(st["keys"], st["hold"]):
                                break
                            if not self.sleep(st["gap"]):
                                break
                    elif op == "hold":
                        self.tap(st["keys"], st["dur"])
                    elif op == "wait":
                        self.sleep(random.uniform(st["lo"], st["hi"]))
                    elif op == "check":
                        res = self.check(st["dur"])
                        if res is None:
                            break
                        scores.append(res)
                        if res[1] and not self.test:
                            return
                if self.stop_ev.is_set():
                    break
                took = time.monotonic() - t_loop
                self.emit("loop", took)
                if self.test:
                    self.emit("test_done", {"seconds": took, "checks": scores})
                    break
        except HuntError as e:
            self.emit("error", str(e))
        except Exception:
            self.emit("error", traceback.format_exc())
        finally:
            self.release()
            self.set_state("stopped")

    def region_abs(self):
        x, y, w, h = self.det["region"]
        if self.det.get("relative", True):
            ox, oy = self.plat.client_origin(self.hwnd)
            return ox + x, oy + y, w, h
        return x, y, w, h

    def check(self, dur):
        """Watch the area for up to `dur` seconds. -> (score, shiny) or None if stopped."""
        d = self.det
        if not self.plat.window_exists(self.hwnd):
            raise HuntError("The emulator window was closed.")
        self.emit("checking", True)
        mode = d["mode"]
        interval = 1.0 / max(1, int(d.get("fps", 12)))
        best = None
        best_frame = None
        shiny = False
        samples = 0
        try:
            t_end = time.monotonic() + dur
            while True:
                ax, ay, w, h = self.region_abs()
                frame = self.plat.capture(ax, ay, w, h)
                samples += 1
                s = score_frame(frame, d, self.refs_raw)
                if mode == "color":
                    if best is None or s > best:
                        best, best_frame = s, frame
                    if s >= d["color_pct"]:
                        shiny = True
                        break
                else:
                    if best is None or s < best:
                        best = s
                    best_frame = frame
                    if s <= d["threshold"]:
                        shiny = False
                        break
                if time.monotonic() >= t_end:
                    # compare mode: never looked like the normal Pokemon -> shiny
                    shiny = mode != "color"
                    break
                if self.stop_ev.wait(interval):
                    return None
        finally:
            self.emit("checking", False)
        if self.test:
            self.emit("test_check", best, shiny)
            return best, shiny
        self.emit("check", best, shiny, samples)
        self.emit("count")
        if shiny:
            full = None
            try:
                if d.get("relative", True):
                    ox, oy = self.plat.client_origin(self.hwnd)
                    cw, ch = self.plat.client_size(self.hwnd)
                    full = self.plat.capture(ox, oy, cw, ch)
            except Exception:
                full = None
            self.emit("shiny", {"score": best, "frame": best_frame, "full": full})
        return best, shiny
