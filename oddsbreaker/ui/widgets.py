"""Bigger widgets: the LCD counter, the step editor, the watch-area picker,
stat cards and charts."""

import base64
import time

from ..imaging import Bitmap, frame_photo
from ..pixel import FONT, PAL, TINY, draw_text, ellipsize, hexc, mix, wrap_text
from ..script import combo_label, fmt_num
from ..stats import fmt_int, fmt_time
from .toolkit import Widget, step_time


class LCD(Widget):
    """The green Game Boy style counter screen."""

    def __init__(self, ui, group, x, y, w, h):
        self.count = 0
        self.roll_from = None
        self.roll_t0 = 0.0
        self.pops = []
        self.test_until = 0.0
        self.invert_until = 0.0
        self.vals = {"left": "RESETS", "right": "", "time": 0, "rate": None,
                     "odds": 8192, "chance": 0.0, "mult": 0.0}
        Widget.__init__(self, ui, group, x, y, w, h)
        ui.anims.append(self._anim)

    def update(self, **kw):
        ch = False
        for k, v in kw.items():
            if self.vals.get(k) != v:
                self.vals[k] = v
                ch = True
        if ch:
            self.refresh()

    def self_test(self, dur=0.6):
        self.test_until = time.monotonic() + dur
        self.refresh()

    def blink(self, dur=0.5):
        self.invert_until = time.monotonic() + dur
        self.refresh()

    def set_count(self, n, animate=True):
        if n == self.count:
            return
        now = time.monotonic()
        if animate and n == self.count + 1 and len(fmt_int(n)) == len(fmt_int(self.count)):
            self.roll_from, self.roll_t0 = self.count, now
        else:
            self.roll_from = None
        if animate and n > self.count:
            self.pops.append(now)
        self.count = n
        self.refresh()

    def _anim(self, now):
        if not self.ui.alive:
            return False
        busy = False
        if self.roll_from is not None:
            if now - self.roll_t0 > 0.2:
                self.roll_from = None
            busy = True
        if self.pops:
            self.pops = [t for t in self.pops if now - t < 0.6]
            busy = True
        if self.test_until and now < self.test_until + 0.05:
            busy = True
        elif self.test_until:
            self.test_until = 0.0
            busy = True
        if self.invert_until:
            busy = True
            if now > self.invert_until:
                self.invert_until = 0.0
        if busy:
            self.refresh()
            return "fast"
        return True

    def render(self):
        P = PAL
        w, h = self.w, self.h
        b = Bitmap(w, h)
        ink, mid, light, ghost = P["lcd4"], P["lcd3"], P["lcd2"], P["lcd5"]
        now = time.monotonic()
        testing = now < self.test_until
        if self.invert_until and now < self.invert_until and int(now * 10) % 2 == 0:
            b.rect(0, 0, w, h, P["lcd3"])
            ink, mid, light, ghost = P["lcd"], P["lcd2"], P["lcd4"], P["lcd3"]
        v = self.vals
        draw_text(b, 3, 2, v["left"], mid, TINY)
        rl = ellipsize(v["right"], 70, TINY)
        draw_text(b, w - 3 - TINY.width(rl), 2, rl, mid, TINY)
        y0, H = 9, 14
        new = fmt_int(self.count)
        ghost_s = "888,888" if len(new) <= 7 else "8,888,888"
        right = 3 + FONT.width(ghost_s, 2)
        draw_text(b, 3, y0, ghost_s, ink if testing else ghost, FONT, 2)
        if not testing:
            x = right - FONT.width(new, 2)
            if self.roll_from is not None:
                old = fmt_int(self.roll_from)
                t = min(1.0, (now - self.roll_t0) / 0.2)
                t = 1 - (1 - t) ** 2
                for co, cn in zip(old, new):
                    g = FONT.get(cn)
                    if co == cn:
                        draw_text(b, x, y0, cn, ink, FONT, 2)
                    else:
                        draw_text(b, x, y0 - int(t * H), co, ink, FONT, 2, clip=(y0, y0 + H))
                        draw_text(b, x, y0 + int((1 - t) * H), cn, ink, FONT, 2, clip=(y0, y0 + H))
                    x += (g.w + 1) * 2
            else:
                draw_text(b, x, y0, new, ink, FONT, 2)
        for t0 in self.pops[-1:]:
            dt = now - t0
            draw_text(b, right + 4, y0 + 8 - int(dt * 14), "+1", mid, TINY, clip=(y0 - 2, y0 + H))
        tt = "TIME " + fmt_time(v["time"])
        draw_text(b, 3, 27, tt, ink)
        rate = ("%s/HR" % fmt_int(v["rate"])) if v["rate"] else "--/HR"
        draw_text(b, w - 3 - FONT.width(rate), 27, rate, ink)
        draw_text(b, 3, 37, "ODDS 1/%d" % v["odds"], ink)
        ch = "%.1f%%" % (v["chance"] * 100)
        draw_text(b, w - 3 - FONT.width(ch), 37, ch, ink)
        lab = "CHANCE"
        draw_text(b, w - 3 - FONT.width(ch) - TINY.width(lab) - 3, 39, lab, mid, TINY)
        bw = w - 6
        b.rect(3, 46, bw, 2, light)
        b.rect(3, 46, int(bw * max(0.0, min(1.0, v["chance"]))), 2, mid)
        b.rect(3 + bw // 2, 45, 1, 4, mid)
        return b


OP_COLORS = {"press": "btn", "hold": "purple", "wait": "orange", "check": "pink"}


class ScriptEditor(Widget):
    """Visual step list: click a step to edit, arrows / wheel change numbers."""
    interactive = True
    ROW = 12

    def __init__(self, ui, group, x, y, w, h, app):
        self.app = app
        self.rows = []
        self.sel = -1
        self.scroll = 0
        self.targets = []
        self.hot = None
        self.press_t = None
        self.repeat_at = None
        self.running_row = None
        Widget.__init__(self, ui, group, x, y, w, h)

    def set_rows(self, rows):
        self.rows = rows
        if self.sel >= len(rows):
            self.sel = len(rows) - 1
        self.refresh()

    def set_running(self, i):
        if i != self.running_row:
            self.running_row = i
            if i is not None and 0 <= i < len(self.rows):
                self.ensure_visible(i)
            self.refresh()

    # layout ------------------------------------------------------------------
    def row_h(self, i):
        r = self.rows[i]
        return self.ROW * 2 + 1 if (i == self.sel and r.get("op") != "note") else self.ROW

    def content_h(self):
        return sum(self.row_h(i) for i in range(len(self.rows)))

    def max_scroll(self):
        return max(0, self.content_h() - self.h)

    def ensure_visible(self, i):
        y = sum(self.row_h(j) for j in range(i))
        hh = self.row_h(i) if 0 <= i < len(self.rows) else 0
        if y < self.scroll:
            self.scroll = y
        elif y + hh > self.scroll + self.h:
            self.scroll = y + hh - self.h
        self.scroll = max(0, min(self.max_scroll(), self.scroll))

    @staticmethod
    def summary(r):
        op = r.get("op")
        if op == "press":
            s = combo_label(r["btn"])
            if r["times"] > 1:
                s += " ×%d" % r["times"]
            return s
        if op == "hold":
            return "%s  %ss" % (combo_label(r["btn"]), fmt_num(r["dur"]))
        if op == "wait":
            if abs(r["lo"] - r["hi"]) < 1e-9:
                return "%ss" % fmt_num(r["lo"])
            return "%s - %ss" % (fmt_num(r["lo"]), fmt_num(r["hi"]))
        if op == "check":
            return "up to %ss" % fmt_num(r["dur"])
        return r.get("text", "")

    @staticmethod
    def pills(r):
        op = r.get("op")
        if op == "press":
            return [("times", "×%d" % r["times"]), ("gap", "GAP %ss" % fmt_num(r["gap"])),
                    ("hold", "HOLD %ss" % fmt_num(r["hold"]))]
        if op == "hold":
            return [("dur", "%ss" % fmt_num(r["dur"]))]
        if op == "wait":
            return [("lo", "MIN %ss" % fmt_num(r["lo"])), ("hi", "MAX %ss" % fmt_num(r["hi"]))]
        if op == "check":
            return [("dur", "UP TO %ss" % fmt_num(r["dur"]))]
        return []

    def render(self):
        P = PAL
        w, h = self.w, self.h
        b = Bitmap(w, h)
        self.targets = []
        y = -self.scroll
        ms = self.max_scroll()
        cw = w - 5 if ms > 0 else w
        for i, r in enumerate(self.rows):
            rh = self.row_h(i)
            if y + rh > 0 and y < h:
                self._draw_row(b, i, r, y, cw, rh)
            y += rh
        if not self.rows:
            draw_text(b, 4, 6, "No steps yet. Add some below,", P["dim"], TINY)
            draw_text(b, 4, 14, "or LOAD a ready-made script.", P["dim"], TINY)
        if ms > 0:
            th = max(10, int(h * h / float(h + ms)))
            ty = int((h - th) * self.scroll / float(ms))
            b.rrect(w - 3, 0, 3, h, 1, P["dark2"])
            b.rrect(w - 3, ty, 3, th, 1, P["dim"])
        return b

    def _target(self, x0, y0, x1, y1, kind, i, param=None):
        self.targets.append((x0, y0, x1, y1, kind, i, param))

    def _draw_row(self, b, i, r, y, cw, rh):
        P = PAL
        op = r.get("op")
        sel = i == self.sel
        hot = self.hot
        if sel:
            b.rrect(0, y, cw, rh - 1, 3, P["dark3"])
        elif hot and hot[4] == "row" and hot[5] == i:
            b.rrect(0, y, cw, rh - 1, 3, P["dark2"])
        self._target(0, y, cw, y + rh, "row", i)
        if self.running_row == i:
            draw_text(b, 2, y + 3, "▶", P["green"], TINY)
        else:
            draw_text(b, 2, y + 3, "%d" % (i + 1), P["faint"], TINY)
        if op == "note":
            txt = ellipsize("# " + r.get("text", ""), cw - 44 if sel else cw - 14, TINY)
            draw_text(b, 12, y + 4, txt, P["dim"], TINY)
        else:
            col = PAL[OP_COLORS.get(op, "btn")]
            b.rrect(12, y + 1, 31, 10, 3, col)
            b.rect(14, y + 1, 27, 1, mix(col, P["white"], 0.4))
            lab = op.upper()
            draw_text(b, 12 + (31 - TINY.width(lab)) // 2, y + 4, lab, P["night"], TINY)
            if sel and op in ("press", "hold"):
                lab = ellipsize(combo_label(r["btn"]), cw - 92)
                pw = FONT.width(lab) + 10
                is_hot = hot and hot[4] == "btn" and hot[5] == i
                b.rrect(46, y + 1, pw, 10, 3, P["cyan"] if is_hot else P["line"])
                b.rrect(47, y + 2, pw - 2, 8, 2, P["night"])
                draw_text(b, 51, y + 3, lab, P["ink"])
                self._target(46, y + 1, 46 + pw, y + 11, "btn", i)
            else:
                txt = ellipsize(self.summary(r), cw - 50 - (30 if sel else 0))
                draw_text(b, 47, y + 3, txt, P["ink"])
        if sel:
            for k, (kind, g) in enumerate((("up", "▲"), ("down", "▼"), ("del", "×"))):
                x0 = cw - 29 + k * 9
                is_hot = hot and hot[4] == kind and hot[5] == i
                col = (P["bad"] if kind == "del" else P["cyan"]) if is_hot else P["dim"]
                if is_hot:
                    b.rrect(x0, y + 1, 8, 10, 2, P["dark4"])
                if kind == "del":
                    gw = FONT.get(g).w
                    draw_text(b, x0 + (8 - gw) // 2, y + 3, g, col)
                else:
                    gw = TINY.get(g).w
                    draw_text(b, x0 + (8 - gw) // 2, y + 4, g, col, TINY)
                self._target(x0, y, x0 + 8, y + 11, kind, i)
            if op != "note":
                x = 12
                py = y + self.ROW + 1
                for key, lab in self.pills(r):
                    pw = TINY.width(lab) + 20
                    is_hot = hot and hot[4] == "pill" and hot[5] == i and hot[6][0] == key
                    b.rrect(x, py, pw, 10, 3, P["cyan"] if is_hot else P["line"])
                    b.rrect(x + 1, py + 1, pw - 2, 8, 2, P["night"])
                    lc = P["cyan"] if (is_hot and hot[6][1] < 0) else P["dim"]
                    rc = P["cyan"] if (is_hot and hot[6][1] > 0) else P["dim"]
                    draw_text(b, x + 3, py + 3, "◀", lc, TINY)
                    draw_text(b, x + pw - 6, py + 3, "▶", rc, TINY)
                    draw_text(b, x + 10, py + 3, lab, P["ink"], TINY)
                    self._target(x, py, x + 9, py + 10, "pill", i, (key, -1))
                    self._target(x + pw - 9, py, x + pw, py + 10, "pill", i, (key, 1))
                    self._target(x + 9, py, x + pw - 9, py + 10, "pill", i, (key, 0))
                    x += pw + 3

    # interaction -------------------------------------------------------------
    def target_at(self, x, y):
        best = None
        for t in self.targets:
            if t[0] <= x < t[2] and t[1] <= y < t[3]:
                if best is None or t[4] != "row":
                    best = t
        return best

    def on_move(self, x, y):
        t = self.target_at(x, y)
        key = t[4:] if t else None
        if key != (self.hot[4:] if self.hot else None):
            self.hot = t
            self.refresh()

    def on_hover(self, on):
        if not on:
            self.hot = None
        self.refresh()

    def on_press(self, x, y):
        t = self.target_at(x, y)
        self.press_t = t
        if t and t[4] == "pill" and t[6][1] != 0:
            self.adjust(t[5], t[6][0], t[6][1])
            self.repeat_at = time.monotonic() + 0.4
            self.ui.anims.append(self._repeat)

    def _repeat(self, now):
        if not self.pressed or self.repeat_at is None or not self.press_t:
            self.repeat_at = None
            return False
        if now >= self.repeat_at:
            t = self.press_t
            self.adjust(t[5], t[6][0], t[6][1], quiet=True)
            self.repeat_at = now + 0.07
        return True

    def on_release(self, x, y, inside):
        self.repeat_at = None
        t, pt = self.target_at(x, y), self.press_t
        self.press_t = None
        if not inside or not t or not pt or t[4:6] != pt[4:6]:
            return
        kind, i = t[4], t[5]
        if kind == "row":
            if self.sel != i:
                self.sel = i
                self.ensure_visible(i)
                self.app.sound("tick")
                self.refresh()
        elif kind == "up" and i > 0:
            self.rows[i - 1], self.rows[i] = self.rows[i], self.rows[i - 1]
            self.sel = i - 1
            self.ensure_visible(self.sel)
            self.app.script_changed()
        elif kind == "down" and i < len(self.rows) - 1:
            self.rows[i + 1], self.rows[i] = self.rows[i], self.rows[i + 1]
            self.sel = i + 1
            self.ensure_visible(self.sel)
            self.app.script_changed()
        elif kind == "del":
            del self.rows[i]
            self.sel = min(i, len(self.rows) - 1)
            self.app.sound("close")
            self.app.script_changed()
        elif kind == "btn":
            self.app.open_picker(i)
        self.refresh()

    def on_wheel(self, step, state):
        t = self.hot
        if t and t[4] == "pill":
            self.adjust(t[5], t[6][0], step, fast=bool(state & 1))
            return True
        ms = self.max_scroll()
        if ms <= 0:
            return False
        self.scroll = max(0, min(ms, self.scroll - step * self.ROW))
        self.refresh()
        return True

    def adjust(self, i, key, d, fast=False, quiet=False):
        if not (0 <= i < len(self.rows)) or d == 0:
            return
        r = self.rows[i]
        for _ in range(10 if fast else 1):
            if key == "times":
                r["times"] = max(1, min(99, int(r["times"]) + d))
            elif key in ("gap", "hold", "dur", "lo", "hi"):
                lo_lim = {"hold": 0.02, "dur": 0.05}.get(key, 0.0)
                if r.get("op") == "check" and key == "dur":
                    v = round(max(0.5, min(60.0, r["dur"] + 0.5 * d)), 2)
                else:
                    v = max(lo_lim, min(120.0, step_time(r[key], d)))
                r[key] = v
                if key == "lo" and r["lo"] > r["hi"]:
                    r["hi"] = r["lo"]
                if key == "hi" and r["hi"] < r["lo"]:
                    r["lo"] = r["hi"]
        if not quiet:
            self.app.sound("tick")
        self.app.script_changed()
        self.refresh()


class AreaSelector(Widget):
    """Snapshot of the emulator window; drag a box to choose the watch area."""
    interactive = True
    cursor = "crosshair"

    def __init__(self, ui, group, x, y, w, h, on_box, on_drag=None):
        self.on_box = on_box
        self.on_drag_cb = on_drag
        self.img = None
        self.fsize = None
        self.left = self.top = 0
        self.factor = 1.0
        self.box = None
        self.mode = None
        self.old = None
        self.message = "No picture yet"
        Widget.__init__(self, ui, group, x, y, w, h,
                        "Drag a box around the Pokemon. Drag inside to move, corners to resize.")
        cv, tags = ui.cv, group.tags()
        S = ui.S
        self.r_dark = cv.create_rectangle(0, 0, 0, 0, outline="#000000", width=S + 2, tags=tags)
        self.r_box = cv.create_rectangle(0, 0, 0, 0, outline="#FFD93B", width=S, tags=tags)
        self.handles = [cv.create_rectangle(0, 0, 0, 0, fill="#FFD93B", outline="#000000", tags=tags)
                        for _ in range(4)]
        self.phase = 0
        self.apply_state()
        ui.anims.append(self._anim)

    def items(self):
        return (self.item, self.r_dark, self.r_box) + tuple(self.handles)

    def apply_state(self):
        Widget.apply_state(self)
        self.place_box()

    def _anim(self, now):
        ph = int(now * 3) % 2
        if ph != self.phase and self.box and self.shown():
            self.phase = ph
            self.ui.cv.itemconfig(self.r_box, outline="#FFD93B" if ph else "#FFFFFF")
            for hd in self.handles:
                self.ui.cv.itemconfig(hd, fill="#FFD93B" if ph else "#FFFFFF")
        return self.ui.alive

    def set_message(self, text):
        self.img = None
        self.fsize = None
        self.message = text
        self.dirty = True
        self.place_box()

    def set_snapshot(self, frame):
        S = self.ui.S
        img, zoom, step = frame_photo(frame, self.w * S, self.h * S)
        self.img = img
        self.factor = float(zoom) if step == 1 else 1.0 / step
        self.left = (self.w * S - img.width()) // 2
        self.top = (self.h * S - img.height()) // 2
        self.fsize = (frame.w, frame.h)
        self.message = ""
        self.ui.cv.itemconfig(self.item, image=img)
        self.ui.cv.coords(self.item, self.ax() * S + self.left, self.ay() * S + self.top)
        self.place_box()

    def set_box(self, box):
        self.box = list(box) if box else None
        self.place_box()

    def sync(self):
        self.dirty = False
        if self.img is not None:
            return
        P = PAL
        b = Bitmap(self.w, self.h)
        b.rrect(0, 0, self.w, self.h, 4, P["line"])
        b.rrect(1, 1, self.w - 2, self.h - 2, 3, P["dark2"])
        lines = wrap_text(self.message, self.w - 20)[:5]
        y = (self.h - len(lines) * 10) // 2
        for line in lines:
            draw_text(b, (self.w - FONT.width(line)) // 2, y, line, P["dim"])
            y += 10
        self.photo = b.photo(self.ui.S)
        S = self.ui.S
        self.ui.cv.itemconfig(self.item, image=self.photo)
        self.ui.cv.coords(self.item, self.ax() * S, self.ay() * S)

    def origin(self):
        S = self.ui.S
        return self.ax() * S + self.left, self.ay() * S + self.top

    def to_client(self, sx, sy):
        x0, y0 = self.origin()
        return (sx - x0) / self.factor, (sy - y0) / self.factor

    def to_canvas(self, cx, cy):
        x0, y0 = self.origin()
        return x0 + cx * self.factor, y0 + cy * self.factor

    def place_box(self):
        cv = self.ui.cv
        show = self.shown() and self.box is not None and self.img is not None
        st = "normal" if show else "hidden"
        for it in (self.r_dark, self.r_box) + tuple(self.handles):
            cv.itemconfig(it, state=st)
        if not show:
            return
        x, y, w, h = self.box
        x0, y0 = self.to_canvas(x, y)
        x1, y1 = self.to_canvas(x + w, y + h)
        cv.coords(self.r_dark, x0, y0, x1, y1)
        cv.coords(self.r_box, x0, y0, x1, y1)
        hs = max(3, self.ui.S * 2)
        for hd, (cx, cy) in zip(self.handles, ((x0, y0), (x1, y0), (x0, y1), (x1, y1))):
            cv.coords(hd, cx - hs, cy - hs, cx + hs, cy + hs)

    def _clamp_pt(self, cx, cy):
        fw, fh = self.fsize
        return max(0, min(fw, cx)), max(0, min(fh, cy))

    def on_press(self, x, y):
        if self.img is None:
            return
        sx, sy = self.ui.last_px
        cx, cy = self._clamp_pt(*self.to_client(sx, sy))
        self.old = list(self.box) if self.box else None
        if self.box:
            bx, by, bw, bh = self.box
            corners = ((bx, by), (bx + bw, by), (bx, by + bh), (bx + bw, by + bh))
            grab = 7.0 / self.factor
            for (kx, ky) in corners:
                if abs(cx - kx) <= grab and abs(cy - ky) <= grab:
                    ox = bx + bw if kx == bx else bx
                    oy = by + bh if ky == by else by
                    self.mode = ("resize", ox, oy)
                    return
            if bx <= cx <= bx + bw and by <= cy <= by + bh:
                self.mode = ("move", cx - bx, cy - by)
                return
        self.mode = ("new", cx, cy)
        self.box = [int(cx), int(cy), 0, 0]
        self.place_box()

    def on_drag(self, x, y):
        if self.img is None or not self.mode:
            return
        sx, sy = self.ui.last_px
        cx, cy = self._clamp_pt(*self.to_client(sx, sy))
        fw, fh = self.fsize
        kind = self.mode[0]
        if kind in ("new", "resize"):
            ax_, ay_ = self.mode[1], self.mode[2]
            x0, x1 = sorted((ax_, cx))
            y0, y1 = sorted((ay_, cy))
            self.box = [int(x0), int(y0), max(1, int(x1 - x0)), max(1, int(y1 - y0))]
        else:
            bw, bh = self.box[2], self.box[3]
            nx = max(0, min(fw - bw, cx - self.mode[1]))
            ny = max(0, min(fh - bh, cy - self.mode[2]))
            self.box = [int(nx), int(ny), bw, bh]
        self.place_box()
        if self.on_drag_cb:
            self.on_drag_cb(self.box)

    def on_release(self, x, y, inside):
        if self.img is None or not self.mode:
            return
        self.mode = None
        if self.box and self.box[2] >= 6 and self.box[3] >= 6:
            self.on_box(list(self.box))
        else:
            self.box = self.old
            self.place_box()


class Swatches(Widget):
    interactive = True

    def __init__(self, ui, group, x, y, w, h, on_remove, hint="Click a colour to remove it"):
        self.colors = []
        self.on_remove = on_remove
        self.hot = -1
        Widget.__init__(self, ui, group, x, y, w, h, hint)

    def set_colors(self, colors):
        self.colors = [list(c) for c in colors]
        self.refresh()

    def _index(self, x, y):
        i = int(y // 12) * 6 + int(x // 11)
        return i if 0 <= i < len(self.colors) and x < 66 else -1

    def on_move(self, x, y):
        i = self._index(x, y)
        if i != self.hot:
            self.hot = i
            self.refresh()

    def on_release(self, x, y, inside):
        i = self._index(x, y)
        if inside and i >= 0:
            self.on_remove(i)

    def render(self):
        P = PAL
        b = Bitmap(self.w, self.h)
        if not self.colors:
            draw_text(b, 0, 2, "NONE YET", P["faint"], TINY)
            draw_text(b, 0, 10, "CLICK THE", P["faint"], TINY)
            draw_text(b, 0, 18, "PICTURE", P["faint"], TINY)
        for i, (r, g, bl) in enumerate(self.colors[:18]):
            x, y = (i % 6) * 11, (i // 6) * 12
            b.rrect(x, y, 10, 10, 2, P["white"] if i == self.hot else P["line"])
            b.rrect(x + 1, y + 1, 8, 8, 1, bytes((r, g, bl, 255)))
            if i == self.hot:
                draw_text(b, x + 4, y + 3, "×", P["white"], TINY)
        return b


class Thumbs(Widget):
    """Saved NORMAL reference frames; click one to delete it."""
    interactive = True

    def __init__(self, ui, group, x, y, w, h, on_remove):
        self.refs = []
        self.bmps = []
        self.hot = -1
        self.on_remove = on_remove
        Widget.__init__(self, ui, group, x, y, w, h, "Saved normal frames. Click one to delete it.")

    def set_refs(self, refs):
        self.refs = list(refs)
        self.bmps = [self._thumb(r) for r in self.refs[:3]]
        self.refresh()

    @staticmethod
    def _thumb(ref, tw=30, th=22):
        gw, gh = ref.get("gw", 0), ref.get("gh", 0)
        try:
            data = base64.b64decode(ref["data"])
        except Exception:
            return None
        if not gw or not gh or len(data) < gw * gh * 3:
            return None
        k = max(gw / float(tw), gh / float(th))
        w, h = max(1, int(gw / k)), max(1, int(gh / k))
        b = Bitmap(w, h)
        for j in range(h):
            for i in range(w):
                o = (int(j * k) * gw + int(i * k)) * 3
                b.px(i, j, bytes((data[o], data[o + 1], data[o + 2], 255)))
        return b

    def _index(self, x):
        i = int(x // 35)
        return i if 0 <= i < len(self.bmps) else -1

    def on_move(self, x, y):
        i = self._index(x)
        if i != self.hot:
            self.hot = i
            self.refresh()

    def on_release(self, x, y, inside):
        i = self._index(x)
        if inside and i >= 0:
            self.on_remove(i)

    def render(self):
        P = PAL
        b = Bitmap(self.w, self.h)
        for i in range(3):
            x = i * 35
            b.rrect(x, 0, 33, 25, 3, P["bad"] if i == self.hot else P["line"])
            b.rrect(x + 1, 1, 31, 23, 2, P["night"])
            if i < len(self.bmps) and self.bmps[i] is not None:
                t = self.bmps[i]
                b.blit(t, x + 1 + (31 - t.w) // 2, 1 + (23 - t.h) // 2)
                if i == self.hot:
                    b.rrect(x + 22, 2, 9, 9, 2, P["bad"])
                    draw_text(b, x + 25, 4, "×", P["white"], TINY)
            else:
                draw_text(b, x + 14, 10, "-", P["faint"], TINY)
        return b


class EmbedText(Widget):
    """A real Tk Text box (for TEXT mode in the step editor)."""

    def __init__(self, ui, group, x, y, w, h, widget):
        Widget.__init__(self, ui, group, x, y, w, h)
        S = ui.S
        ui.cv.delete(self.item)
        self.item = ui.cv.create_window(self.ax() * S, self.ay() * S, window=widget, anchor="nw",
                                        width=w * S, height=h * S, tags=group.tags())
        self.forced_hidden = False
        self.apply_state()

    def apply_state(self):
        st = "normal" if (self.shown() and not self.forced_hidden) else "hidden"
        self.ui.cv.itemconfig(self.item, state=st)

    def sync(self):
        self.dirty = False


class StatCard(Widget):
    """A little rounded card: caption on top, big value below."""

    def __init__(self, ui, group, x, y, w, h, caption, hint=""):
        self.caption = caption
        self.value = "-"
        self.color = None
        self.sub = ""
        Widget.__init__(self, ui, group, x, y, w, h, hint)

    def set(self, value, color=None, sub=""):
        if (value, color, sub) != (self.value, self.color, self.sub):
            self.value, self.color, self.sub = value, color, sub
            self.refresh()

    def render(self):
        P = PAL
        w, h = self.w, self.h
        b = Bitmap(w, h)
        b.rrect(0, 0, w, h, 4, P["dark3"])
        b.rrect(1, 1, w - 2, h - 2, 3, P["dark2"])
        b.rect(4, 1, w - 8, 1, P["dark4"])
        draw_text(b, 5, 4, self.caption, P["dim"], TINY)
        val = ellipsize(self.value, w - 10)
        draw_text(b, 5, 12, val, self.color or P["ink"])
        if self.sub:
            draw_text(b, w - 5 - TINY.width(self.sub), 4, ellipsize(self.sub, w // 2, TINY),
                      P["faint"], TINY)
        return b


class BarChart(Widget):
    """Resets per day as little bars; the last bar is today."""
    interactive = True
    cursor = ""

    def __init__(self, ui, group, x, y, w, h, hint=""):
        self.data = []
        self.hot = -1
        Widget.__init__(self, ui, group, x, y, w, h, hint)

    def set_data(self, data):
        if data != self.data:
            self.data = list(data)
            self.refresh()

    def _index(self, x):
        n = len(self.data)
        if not n:
            return -1
        bw = (self.w - 4) / float(n)
        i = int((x - 2) / bw)
        return i if 0 <= i < n else -1

    def on_move(self, x, y):
        i = self._index(x)
        if i != self.hot:
            self.hot = i
            self.refresh()
            if 0 <= i < len(self.data):
                day, n = self.data[i]
                self.ui.app.hint("%s: %s RESETS" % (day[5:].replace("-", "/"), fmt_int(n)))

    def on_hover(self, on):
        if not on:
            self.hot = -1
        self.refresh()

    def render(self):
        P = PAL
        w, h = self.w, self.h
        b = Bitmap(w, h)
        b.rrect(0, 0, w, h, 4, P["dark3"])
        b.rrect(1, 1, w - 2, h - 2, 3, P["dark2"])
        n = len(self.data)
        if not n:
            return b
        top = max(1, max(v for _d, v in self.data))
        ch = h - 14
        bw = (w - 4) / float(n)
        for k in range(1, 3):
            gy = 3 + ch - ch * k // 3
            for gx in range(3, w - 3, 3):
                b.px(gx, gy, P["dark3"])
        for i, (_day, v) in enumerate(self.data):
            x0 = 2 + int(i * bw) + 1
            x1 = 2 + int((i + 1) * bw) - 1
            bh = int(round(ch * v / float(top)))
            col = P["cyan"] if i == n - 1 else P["cyan_dk"]
            if i == self.hot:
                col = P["gold"]
            if bh > 0:
                b.rrect(x0, 3 + ch - bh, max(1, x1 - x0), bh, 1, col)
                if bh > 1:
                    b.rect(x0, 3 + ch - bh, max(1, x1 - x0), 1, mix(col, P["white"], 0.4))
            else:
                b.rect(x0, 2 + ch, max(1, x1 - x0), 1, P["dark4"])
        draw_text(b, 3, h - 8, self.data[0][0][5:].replace("-", "/"), P["faint"], TINY)
        lab = "TODAY"
        draw_text(b, w - 3 - TINY.width(lab), h - 8, lab, P["dim"], TINY)
        if max(v for _d, v in self.data) > 0:
            mx = "MAX " + fmt_int(top)
            draw_text(b, (w - TINY.width(mx)) // 2, h - 8, mx, P["faint"], TINY)
        else:
            mx = "NO RESETS YET"
            draw_text(b, (w - TINY.width(mx)) // 2, (h - 10) // 2, mx, P["faint"], TINY)
        return b


class Sparkline(Widget):
    """Scores of recent normal checks, with the red line."""

    def __init__(self, ui, group, x, y, w, h, hint=""):
        self.scores = []
        self.mark = 15.0
        self.maxv = 60.0
        Widget.__init__(self, ui, group, x, y, w, h, hint)

    def set(self, scores, mark, maxv):
        key = (tuple(scores), mark, maxv)
        if key != (tuple(self.scores), self.mark, self.maxv):
            self.scores, self.mark, self.maxv = list(scores), mark, maxv
            self.refresh()

    def render(self):
        P = PAL
        w, h = self.w, self.h
        b = Bitmap(w, h)
        b.rrect(0, 0, w, h, 3, P["dark3"])
        b.rrect(1, 1, w - 2, h - 2, 2, P["night"])
        ch = h - 4
        my = 2 + ch - int(ch * min(1.0, self.mark / self.maxv))
        for gx in range(2, w - 2, 2):
            b.px(gx, my, P["bad"])
        n = len(self.scores)
        if not n:
            draw_text(b, 5, (h - 5) // 2, "NO CHECKS YET", P["faint"], TINY)
            return b
        bw = max(1, (w - 4) // max(1, n))
        x = w - 2 - bw * n
        for s in self.scores:
            v = min(1.0, max(0.0, s / self.maxv))
            bh = max(1, int(round(ch * v)))
            col = P["gold"] if s > self.mark else P["green"]
            b.rect(max(2, x), 2 + ch - bh, max(1, bw - 1), bh, col)
            x += bw
        return b


def hexcolor(c):
    return "#%02X%02X%02X" % (c[0], c[1], c[2])


__all__ = ["LCD", "ScriptEditor", "AreaSelector", "Swatches", "Thumbs", "EmbedText",
           "StatCard", "BarChart", "Sparkline", "hexcolor", "hexc"]
