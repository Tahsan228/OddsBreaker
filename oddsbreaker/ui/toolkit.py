"""A small pixel-art widget kit drawn on a Tk canvas.

Every widget renders itself into a Bitmap (in art pixels) which is shown as
a PhotoImage zoomed by S. Widgets live in Groups that move and hide together.
"""

import re
import time
import traceback

import tkinter as tk

from ..config import IS_WIN, MODIFIER_KEYS, key_label, tk_keysym_to_key
from ..imaging import CLEAR, Bitmap
from ..pixel import FONT, PAL, TINY, draw_text, ellipsize, hexc, mix, wrap_text


class Group(object):
    """A set of widgets that move and show/hide together."""
    _n = [0]

    def __init__(self, ui, parent=None, x=0, y=0, visible=True):
        Group._n[0] += 1
        self.ui, self.parent = ui, parent
        self.x, self.y, self.visible = x, y, visible
        self.tag = "grp%d" % Group._n[0]
        self.children, self.widgets = [], []
        if parent is not None:
            parent.children.append(self)

    def tags(self):
        out, g = [], self
        while g is not None:
            out.append(g.tag)
            g = g.parent
        return tuple(out)

    def ox(self):
        return self.x + (self.parent.ox() if self.parent is not None else 0)

    def oy(self):
        return self.y + (self.parent.oy() if self.parent is not None else 0)

    def shown(self):
        return self.visible and (self.parent.shown() if self.parent is not None else True)

    def all_widgets(self):
        out = list(self.widgets)
        for c in self.children:
            out.extend(c.all_widgets())
        return out

    def set_visible(self, v):
        v = bool(v)
        if v == self.visible:
            return
        self.visible = v
        for w in self.all_widgets():
            w.apply_state()
            if not w.shown() and w is self.ui.focus:
                self.ui.set_focus(None)

    def move_to(self, x, y):
        dx, dy = x - self.x, y - self.y
        if not dx and not dy:
            return
        self.x, self.y = x, y
        S = self.ui.S
        self.ui.cv.move(self.tag, dx * S, dy * S)


class UI(object):
    """Owns the canvas, routes mouse/keyboard events and runs the frame loop."""

    def __init__(self, root, S, w, h, bg, app):
        self.root, self.S, self.app = root, S, app
        self.cv = tk.Canvas(root, width=w * S, height=h * S, bg=bg, highlightthickness=0,
                            bd=0, takefocus=1)
        self.cv.place(x=0, y=0)
        self.widgets = []
        self.hover = self.capture = self.focus = None
        self.anims = []
        self.win_drag = None
        self.last_px = (0, 0)
        self.alive = True
        self.now = time.monotonic()
        self.top = Group(self)
        cv = self.cv
        cv.bind("<Motion>", self._motion)
        cv.bind("<Leave>", self._leave)
        cv.bind("<ButtonPress-1>", self._press)
        cv.bind("<B1-Motion>", self._drag)
        cv.bind("<ButtonRelease-1>", self._release)
        cv.bind("<Double-Button-1>", self._double)
        cv.bind("<ButtonPress-3>", self._rpress)
        cv.bind("<MouseWheel>", self._wheel)
        cv.bind("<Button-4>", lambda e: self._wheel(e, 120))
        cv.bind("<Button-5>", lambda e: self._wheel(e, -120))

    def destroy(self):
        self.alive = False
        try:
            self.cv.destroy()
        except tk.TclError:
            pass

    # widgets -----------------------------------------------------------------
    def register(self, w):
        self.widgets.append(w)
        w.group.widgets.append(w)

    def unregister(self, w):
        if w in self.widgets:
            self.widgets.remove(w)
        if w in w.group.widgets:
            w.group.widgets.remove(w)
        for attr in ("hover", "capture", "focus"):
            if getattr(self, attr) is w:
                setattr(self, attr, None)

    def hit(self, x, y):
        for w in reversed(self.widgets):
            if w.interactive and w.enabled and w.shown() and w.contains(x, y):
                return w
        return None

    def set_focus(self, w):
        if w is self.focus:
            return
        old, self.focus = self.focus, w
        if old is not None:
            old.focused = False
            old.on_blur()
        if w is not None:
            w.focused = True
            w.on_focus()

    # mouse ---------------------------------------------------------------------
    def _pt(self, e):
        self.last_px = (e.x, e.y)
        return e.x / float(self.S), e.y / float(self.S)

    def _set_hover(self, w):
        if w is self.hover:
            return
        old, self.hover = self.hover, w
        if old is not None:
            old.hovered = False
            old.on_hover(False)
        if w is not None:
            w.hovered = True
            w.on_hover(True)
            self.cv.config(cursor=w.cursor)
            self.app.hint(w.hint)
        else:
            self.cv.config(cursor="")
            self.app.hint(None)

    def _motion(self, e):
        x, y = self._pt(e)
        if self.capture is not None:
            return
        w = self.hit(x, y)
        self._set_hover(w)
        if w is not None:
            w.on_move(x - w.ax(), y - w.ay())

    def _leave(self, e):
        if self.capture is None:
            self._set_hover(None)

    def _press(self, e):
        x, y = self._pt(e)
        try:
            self.cv.focus_set()
        except tk.TclError:
            pass
        w = self.hit(x, y)
        if w is not None and w.focusable:
            try:
                self.root.focus_force()
                self.cv.focus_set()
            except tk.TclError:
                pass
        self.set_focus(w if (w is not None and w.focusable) else None)
        self.win_drag = None
        if w is not None:
            self._set_hover(w)
            self.capture = w
            w.pressed = True
            w.refresh()
            w.on_press(x - w.ax(), y - w.ay())
        elif self.app.can_drag(x, y):
            self.win_drag = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())

    def _drag(self, e):
        x, y = self._pt(e)
        w = self.capture
        if w is not None:
            inside = w.contains(x, y)
            if inside != w.hovered:
                w.hovered = inside
                w.refresh()
            w.on_drag(x - w.ax(), y - w.ay())
        elif self.win_drag:
            sx, sy, wx, wy = self.win_drag
            self.root.geometry("+%d+%d" % (wx + e.x_root - sx, wy + e.y_root - sy))

    def _release(self, e):
        x, y = self._pt(e)
        w, self.capture = self.capture, None
        if w is not None:
            w.pressed = False
            w.refresh()
            inside = w.shown() and w.contains(x, y)
            w.on_release(x - w.ax(), y - w.ay(), inside)
        if self.win_drag:
            sx, sy, wx, wy = self.win_drag
            self.win_drag = None
            if (self.root.winfo_x(), self.root.winfo_y()) != (wx, wy):
                self.app.window_moved()
        self._set_hover(self.hit(x, y))

    def _double(self, e):
        x, y = self._pt(e)
        w = self.hit(x, y)
        if w is None and self.app.can_drag(x, y) and hasattr(self.app, "double_click_shell"):
            self.app.double_click_shell()
            return
        self._press(e)

    def _rpress(self, e):
        x, y = self._pt(e)
        w = self.hit(x, y)
        if w is not None:
            w.on_rclick(x - w.ax(), y - w.ay())

    def _wheel(self, e, delta=None):
        x, y = self._pt(e)
        d = delta if delta is not None else e.delta
        if not d:
            return
        step = 1 if d > 0 else -1
        w = self.hit(x, y)
        while w is not None:
            if w.on_wheel(step, e.state):
                return
            w = w.wheel_parent

    # keys --------------------------------------------------------------------
    def key(self, e):
        if isinstance(e.widget, (tk.Text, tk.Entry)):
            return None
        f = self.focus
        if f is not None and f.shown() and f.on_key(e):
            return "break"
        return self.app.on_key(e)

    def keyup(self, e):
        if isinstance(e.widget, (tk.Text, tk.Entry)):
            return None
        f = self.focus
        if f is not None and f.shown() and f.on_keyup(e):
            return "break"
        return None

    # frame loop ----------------------------------------------------------------
    def start(self):
        self._tick()

    def _tick(self):
        if not self.alive:
            return
        now = self.now = time.monotonic()
        fast = False
        for fn in list(self.anims):
            try:
                r = fn(now)
                if r is False:
                    if fn in self.anims:
                        self.anims.remove(fn)
                elif r == "fast":
                    fast = True
            except Exception:
                traceback.print_exc()
                if fn in self.anims:
                    self.anims.remove(fn)
        for w in self.widgets:
            if w.dirty and w.shown():
                try:
                    w.sync()
                except Exception:
                    traceback.print_exc()
                    w.dirty = False
        try:
            self.root.after(16 if fast else 33, self._tick)
        except tk.TclError:
            self.alive = False


class Widget(object):
    interactive = False
    focusable = False
    cursor = "hand2"

    def __init__(self, ui, group, x, y, w, h, hint=""):
        self.ui, self.group = ui, group
        self.x, self.y, self.w, self.h = x, y, w, h
        self.hint = hint
        self.visible = self.enabled = True
        self.hovered = self.pressed = self.focused = False
        self.dirty = True
        self.photo = None
        self._last = None
        self.wheel_parent = None
        S = ui.S
        self.item = ui.cv.create_image(self.ax() * S, self.ay() * S, anchor="nw", tags=group.tags())
        ui.register(self)
        if not self.shown():
            ui.cv.itemconfig(self.item, state="hidden")

    def ax(self):
        return self.group.ox() + self.x

    def ay(self):
        return self.group.oy() + self.y

    def shown(self):
        return self.visible and self.group.shown()

    def show(self, v=True):
        v = bool(v)
        if v != self.visible:
            self.visible = v
            self.apply_state()

    def items(self):
        return (self.item,)

    def apply_state(self):
        st = "normal" if self.shown() else "hidden"
        for it in self.items():
            self.ui.cv.itemconfig(it, state=st)

    def refresh(self):
        self.dirty = True

    def set_enabled(self, v):
        if bool(v) != self.enabled:
            self.enabled = bool(v)
            self.refresh()

    def sync(self):
        self.dirty = False
        bmp = self.render()
        if bmp is None:
            self.photo = None
            self._last = None
            self.ui.cv.itemconfig(self.item, image="")
            return
        sig = (bmp.w, bmp.h, bytes(bmp.buf))
        if sig == self._last and self.photo is not None:
            return
        self._last = sig
        self.photo = bmp.photo(self.ui.S)
        self.ui.cv.itemconfig(self.item, image=self.photo)

    def render(self):
        return None

    def move(self, x, y):
        self.x, self.y = x, y
        S = self.ui.S
        self.ui.cv.coords(self.item, self.ax() * S, self.ay() * S)

    def contains(self, px, py):
        ax, ay = self.ax(), self.ay()
        return ax <= px < ax + self.w and ay <= py < ay + self.h

    def destroy(self):
        for it in self.items():
            self.ui.cv.delete(it)
        self.ui.unregister(self)

    # events (coordinates are relative to the widget, in art pixels)
    def on_move(self, x, y):
        pass

    def on_press(self, x, y):
        pass

    def on_drag(self, x, y):
        pass

    def on_release(self, x, y, inside):
        pass

    def on_rclick(self, x, y):
        pass

    def on_wheel(self, step, state):
        return False

    def on_key(self, e):
        return False

    def on_keyup(self, e):
        return False

    def on_hover(self, on):
        self.refresh()

    def on_focus(self):
        self.refresh()

    def on_blur(self):
        self.refresh()


class Pic(Widget):
    """A fixed bitmap."""

    def __init__(self, ui, group, x, y, bmp, hint=""):
        self.bmp = bmp
        Widget.__init__(self, ui, group, x, y, bmp.w, bmp.h, hint)

    def set(self, bmp):
        self.bmp = bmp
        self.w, self.h = bmp.w, bmp.h
        self.refresh()

    def render(self):
        return self.bmp


class Blocker(Pic):
    """Swallows clicks so overlays work like little dialogs."""
    interactive = True
    cursor = ""


class Frames(Widget):
    """Flips between pre-rendered frames (cheap animation)."""

    def __init__(self, ui, group, x, y, bitmaps, hint=""):
        self.photos = [b.photo(ui.S) for b in bitmaps]
        self.index = 0
        Widget.__init__(self, ui, group, x, y, bitmaps[0].w, bitmaps[0].h, hint)

    def set_frame(self, i):
        i = max(0, min(len(self.photos) - 1, int(i)))
        if i != self.index:
            self.index = i
            self.refresh()

    def sync(self):
        self.dirty = False
        self.ui.cv.itemconfig(self.item, image=self.photos[self.index])


class Label(Widget):
    def __init__(self, ui, group, x, y, w, h, text="", color=None, font=None,
                 align="left", scale=1, shadow=None, bg=None, hint=""):
        self.text, self.color = text, color or PAL["ink"]
        self.font, self.align, self.scale = font or FONT, align, scale
        self.shadow, self.bg = shadow, bg
        Widget.__init__(self, ui, group, x, y, w, h, hint)

    def set(self, text, color=None):
        if text != self.text or (color is not None and color != self.color):
            self.text = text
            if color is not None:
                self.color = color
            self.refresh()

    def render(self):
        b = Bitmap(self.w, self.h, self.bg or CLEAR)
        f, s = self.font, self.scale
        txt = ellipsize(self.text, self.w - (1 if self.shadow else 0), f, s)
        tw = f.width(txt, s)
        x = {"left": 0, "center": (self.w - tw) // 2, "right": self.w - tw}[self.align]
        y = max(0, (self.h - f.height * s) // 2)
        draw_text(b, x, y, txt, self.color, f, s, shadow=self.shadow)
        return b


class TextBlock(Widget):
    """Wrapped multi-line text. Lines starting with @ are headings, ! warnings."""

    def __init__(self, ui, group, x, y, w, h, text="", color=None, font=None, line_h=None):
        self.text, self.color, self.font = text, color or PAL["ink"], font or FONT
        self.line_h = line_h or self.font.line_h
        Widget.__init__(self, ui, group, x, y, w, h)

    def set(self, text, color=None):
        if text != self.text or (color and color != self.color):
            self.text = text
            self.color = color or self.color
            self.refresh()

    def render(self):
        b = Bitmap(self.w, self.h)
        y = 0
        for line in wrap_text(self.text, self.w, self.font):
            if y + self.font.height > self.h:
                break
            col = self.color
            if line.startswith("@"):
                line, col = line[1:], PAL["cyan"]
            elif line.startswith("!"):
                line, col = line[1:], PAL["yellow"]
            elif line.startswith("~"):
                line, col = line[1:], PAL["dim"]
            draw_text(b, 0, y, line, col, self.font)
            y += self.line_h
        return b


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------
def btn_style(name):
    P = PAL
    if name == "blue":
        return {"o": P["btn_xd"], "f": P["btn"], "h": P["btn_hi"], "s": P["btn_dk"],
                "i": P["white"], "is": P["btn_xd"], "hf": mix(P["btn"], P["btn_hi"], 0.3),
                "af": P["btn_lit"], "ai": P["btn_xd"], "ah": P["white"]}
    if name == "go":
        return {"o": hexc("#04120A"), "f": hexc("#23824A"), "h": hexc("#5ED68A"),
                "s": hexc("#114526"), "i": hexc("#EAFFEE"), "is": hexc("#0A2E17"),
                "hf": hexc("#2C9A58"), "af": hexc("#3DBA6C"), "ai": P["white"], "ah": hexc("#9CF2BC")}
    if name == "danger":
        return {"o": hexc("#140608"), "f": hexc("#8A2433"), "h": hexc("#D2606E"),
                "s": hexc("#4E111B"), "i": hexc("#FFE1E5"), "is": hexc("#3A0A12"),
                "hf": hexc("#A12D3E"), "af": hexc("#C2334A"), "ai": P["white"], "ah": hexc("#FF9AA6")}
    if name == "gold":
        return {"o": P["gold_xd"], "f": P["gold_md"], "h": P["gold_hi"], "s": P["gold_dk"],
                "i": P["gold_xd"], "is": None, "hf": P["gold"], "af": P["gold_hi"],
                "ai": P["gold_xd"], "ah": P["white"]}
    if name == "shell":
        return {"o": P["outline"], "f": P["red_dk"], "h": P["red_md"], "s": P["red_xd"],
                "i": P["white"], "is": None, "hf": P["red_md"], "af": P["red_md"],
                "ai": P["white"], "ah": P["red_hi"]}
    if name == "white":
        return {"o": P["outline"], "f": hexc("#ECECF2"), "h": P["white"], "s": hexc("#B4B4C2"),
                "i": hexc("#2A2A33"), "is": None, "hf": hexc("#FFFFFF"), "af": P["gold"],
                "ai": hexc("#3A2A00"), "ah": P["white"]}
    # dark (default, used on the setup screen)
    return {"o": P["night"], "f": P["dark4"], "h": P["dark5"], "s": P["dark2"],
            "i": P["ink"], "is": P["night"], "hf": hexc("#30476B"), "af": P["cyan_dk"],
            "ai": P["white"], "ah": P["cyan"]}


def draw_button(w, h, st, down=False, hover=False, active=False, enabled=True, flash=False):
    """A raised, rounded pixel button. Returns (bitmap, face_top, face_h)."""
    b = Bitmap(w, h)
    r = 4 if h >= 14 else 3
    if active or flash:
        face, hi = st["af"], st["ah"]
    elif hover and enabled:
        face, hi = st["hf"], st["h"]
    else:
        face, hi = st["f"], st["h"]
    if not enabled:
        face = mix(face, st["s"], 0.5)
        hi = face
    if down:
        b.rrect(0, 1, w, h - 1, r, st["o"])
        b.rrect(1, 2, w - 2, h - 3, max(0, r - 1), face)
        return b, 2, h - 3
    b.rrect(0, 0, w, h, r, st["o"])
    b.rrect(1, 1, w - 2, h - 2, max(0, r - 1), st["s"])
    b.rrect(1, 1, w - 2, h - 4, max(0, r - 1), face)
    b.rect(1 + r, 2, w - 2 - 2 * r, 1, hi)
    b.rect(2, 1 + r, 1, max(0, h - 6 - 2 * r + 2), hi)
    return b, 1, h - 4


class Button(Widget):
    interactive = True

    def __init__(self, ui, group, x, y, w, h, label, cb, style="dark", hint="",
                 font=None, sound="click", icon=None):
        self.label, self.cb, self.style = label, cb, style
        self.font = font
        self.icon = icon
        self.active = False
        self.badge = False
        self.flash_until = 0.0
        self.sound = sound
        Widget.__init__(self, ui, group, x, y, w, h, hint)

    def set_badge(self, v):
        if bool(v) != self.badge:
            self.badge = bool(v)
            self.refresh()

    def set_label(self, label):
        if label != self.label:
            self.label = label
            self.refresh()

    def set_style(self, style):
        if style != self.style:
            self.style = style
            self.refresh()

    def set_active(self, v):
        if bool(v) != self.active:
            self.active = bool(v)
            self.refresh()

    def flash(self, dur=0.12):
        self.flash_until = time.monotonic() + dur
        self.refresh()
        self.ui.anims.append(self._unflash)

    def _unflash(self, now):
        if now >= self.flash_until:
            self.refresh()
            return False
        return True

    def on_release(self, x, y, inside):
        if inside and self.enabled:
            if self.sound:
                self.ui.app.sound(self.sound)
            self.cb()

    def pick_font(self, text, room):
        if self.font is not None:
            return self.font
        return FONT if FONT.width(text) <= room else TINY

    def render(self):
        st = btn_style(self.style)
        w, h = self.w, self.h
        down = self.pressed and self.hovered
        flash = time.monotonic() < self.flash_until
        b, fy, fh = draw_button(w, h, st, down, self.hovered, self.active, self.enabled, flash)
        ink = st["ai"] if (self.active or flash) else st["i"]
        if not self.enabled:
            ink = mix(ink, st["f"], 0.55)
        room = w - 8
        icon_w = 0
        if self.icon is not None:
            icon_w = self.icon.w + (3 if self.label else 0)
        f = self.pick_font(self.label, room - icon_w)
        txt = ellipsize(self.label, room - icon_w, f)
        tw = f.width(txt) + icon_w
        tx = max(3, (w - tw) // 2)
        ty = fy + (fh - f.height) // 2
        if self.icon is not None:
            ic = self.icon
            b.blit(ic.silhouette(ink), tx, fy + (fh - ic.h) // 2)
            tx += icon_w
        if st.get("is") and not (self.active or flash) and self.enabled and txt:
            draw_text(b, tx, ty + 1, txt, st["is"], f)
        draw_text(b, tx, ty, txt, ink, f)
        if self.badge:
            b.circle(w - 5, 4, 2, st["o"])
            b.circle(w - 5, 4, 1, PAL["yellow"])
            b.px(w - 5, 4, PAL["gold_hi"])
        return b


class IconButton(Widget):
    """A small round button with one glyph (help ?, close x)."""
    interactive = True

    def __init__(self, ui, group, x, y, glyph, cb, hint="", size=11, color=None):
        self.glyph, self.cb, self.color = glyph, cb, color
        Widget.__init__(self, ui, group, x, y, size, size, hint)

    def on_release(self, x, y, inside):
        if inside and self.enabled:
            self.ui.app.sound("click")
            self.cb()

    def render(self):
        P = PAL
        s = self.w
        b = Bitmap(s, s)
        c = s // 2
        down = self.pressed and self.hovered
        b.circle(c, c + (1 if down else 0), c, P["night"])
        face = P["dark5"] if self.hovered else P["dark3"]
        b.circle(c, c + (1 if down else 0), c - 1, face)
        col = self.color or (P["cyan"] if self.hovered else P["dim"])
        g = TINY.get(self.glyph) if self.glyph in TINY.glyphs else FONT.get(self.glyph)
        font = TINY if self.glyph in TINY.glyphs else FONT
        draw_text(b, c - g.w // 2, c - font.height // 2 + (1 if down else 0), self.glyph, col, font)
        return b


# ---------------------------------------------------------------------------
# Fields
# ---------------------------------------------------------------------------
def draw_field(w, h, border, fill=None):
    P = PAL
    b = Bitmap(w, h)
    r = 4 if h >= 14 else 3
    b.rrect(0, 0, w, h, r, border)
    b.rrect(1, 1, w - 2, h - 2, max(0, r - 1), fill or P["night"])
    b.rect(r, 1, w - 2 * r, 1, mix(fill or P["night"], hexc("#000000"), 0.5))
    return b


def arrow_glyph(b, x, y, d, col):
    """Small 3x5 triangle arrow."""
    if d < 0:
        b.px(x, y + 2, col)
        b.rect(x + 1, y + 1, 1, 3, col)
        b.rect(x + 2, y, 1, 5, col)
    else:
        b.rect(x, y, 1, 5, col)
        b.rect(x + 1, y + 1, 1, 3, col)
        b.px(x + 2, y + 2, col)


class Cycler(Widget):
    """◀ value ▶ picker. Click a side or roll the wheel."""
    interactive = True

    def __init__(self, ui, group, x, y, w, h, values, current, on_change, hint="", font=None):
        self.values = list(values)  # list of (value, label)
        self.index = 0
        self.on_change = on_change
        self.font = font or FONT
        self.side = 0
        Widget.__init__(self, ui, group, x, y, w, h, hint)
        self.set_value(current)

    def set_values(self, values, current=None):
        self.values = list(values)
        self.set_value(current)
        self.refresh()

    def set_value(self, v):
        for i, (val, _lab) in enumerate(self.values):
            if val == v:
                if i != self.index:
                    self.index = i
                    self.refresh()
                return True
        return False

    def value(self):
        return self.values[self.index][0] if self.values else None

    def label(self):
        return self.values[self.index][1] if self.values else ""

    def step(self, d):
        if not self.values:
            return
        self.index = (self.index + d) % len(self.values)
        self.refresh()
        self.ui.app.sound("tick")
        if self.on_change:
            self.on_change(self.value())

    def on_move(self, x, y):
        s = -1 if x < self.w / 2.0 else 1
        if s != self.side:
            self.side = s
            self.refresh()

    def on_release(self, x, y, inside):
        if inside:
            self.step(-1 if x < self.w / 2.0 else 1)

    def on_wheel(self, step, state):
        self.step(-step)
        return True

    def render(self):
        P = PAL
        w, h = self.w, self.h
        b = draw_field(w, h, P["dim"] if self.hovered else P["line"])
        ty = (h - 7) // 2
        for side, x in ((-1, 5), (1, w - 8)):
            lit = self.hovered and self.side == side
            if lit:
                b.rrect(x - 3, 2, 9, h - 4, 2, P["dark3"])
            arrow_glyph(b, x, ty + 1, side, P["cyan"] if lit else P["faint"])
        lab = self.label() or "-"
        f = self.font
        if f is FONT and FONT.width(lab) > w - 22:
            f = TINY
        lab = ellipsize(lab, w - 22, f)
        draw_text(b, (w - f.width(lab)) // 2, (h - f.height) // 2, lab, P["ink"], f)
        return b


class Toggle(Widget):
    interactive = True

    def __init__(self, ui, group, x, y, value, on_change, hint=""):
        self.value = bool(value)
        self.on_change = on_change
        Widget.__init__(self, ui, group, x, y, 34, 15, hint)

    def set(self, v):
        if bool(v) != self.value:
            self.value = bool(v)
            self.refresh()

    def on_release(self, x, y, inside):
        if inside:
            self.value = not self.value
            self.refresh()
            self.ui.app.sound("tick")
            self.on_change(self.value)

    def render(self):
        P = PAL
        w, h = self.w, self.h
        b = Bitmap(w, h)
        on = self.value
        b.rrect(0, 0, w, h, 7, P["dim"] if self.hovered else P["line"])
        b.rrect(1, 1, w - 2, h - 2, 6, hexc("#1E6B3B") if on else P["night"])
        kx = w - 14 if on else 1
        b.circle(kx + 6, 7, 6, P["night"])
        b.circle(kx + 6, 7, 5, P["white"] if on else P["dim"])
        b.px(kx + 4, 5, P["white"] if not on else hexc("#FFFFFF"))
        draw_text(b, 4 if on else 16, 5, "ON" if on else "OFF", P["green"] if on else P["faint"], TINY)
        return b


class Stepper(Widget):
    """◀ number ▶ with click, hold-to-repeat, wheel and drag to scrub."""
    interactive = True

    def __init__(self, ui, group, x, y, w, h, value, lo, hi, step_fn, fmt, on_change, hint=""):
        self.value, self.lo, self.hi = value, lo, hi
        self.step_fn, self.fmt, self.on_change = step_fn, fmt, on_change
        self.zone = 0
        self.scrub = None
        self.repeat_at = None
        Widget.__init__(self, ui, group, x, y, w, h, hint)
        self.cursor = "sb_h_double_arrow"

    def set(self, v):
        if v != self.value:
            self.value = v
            self.refresh()

    def bump(self, d, fast=False):
        v = self.value
        for _ in range(10 if fast else 1):
            v = self.step_fn(v, d)
        v = max(self.lo, min(self.hi, v))
        if v != self.value:
            self.value = v
            self.refresh()
            self.on_change(v)

    def _zone(self, x):
        if x < 11:
            return -1
        if x >= self.w - 11:
            return 1
        return 0

    def on_move(self, x, y):
        z = self._zone(x)
        if z != self.zone:
            self.zone = z
            self.refresh()

    def on_press(self, x, y):
        z = self._zone(x)
        if z:
            self.bump(z)
            self.ui.app.sound("tick")
            self.repeat_at = time.monotonic() + 0.4
            self.ui.anims.append(self._repeat)
        else:
            self.scrub = (x, self.value)

    def _repeat(self, now):
        if not self.pressed or self.repeat_at is None:
            self.repeat_at = None
            return False
        if now >= self.repeat_at and self.zone:
            self.bump(self.zone)
            self.repeat_at = now + 0.06
        return True

    def on_drag(self, x, y):
        if self.scrub is not None:
            x0, v0 = self.scrub
            n = int((x - x0) / 3)
            v = v0
            for _ in range(abs(n)):
                v = self.step_fn(v, 1 if n > 0 else -1)
            v = max(self.lo, min(self.hi, v))
            if v != self.value:
                self.value = v
                self.refresh()
                self.on_change(v)

    def on_release(self, x, y, inside):
        self.scrub = None
        self.repeat_at = None

    def on_wheel(self, step, state):
        self.bump(step, fast=bool(state & 1))
        return True

    def render(self):
        P = PAL
        w, h = self.w, self.h
        b = draw_field(w, h, P["dim"] if self.hovered else P["line"])
        ty = (h - 7) // 2
        for z, x in ((-1, 5), (1, w - 8)):
            lit = self.hovered and self.zone == z
            if lit:
                b.rrect(x - 3, 2, 9, h - 4, 2, P["dark3"])
            arrow_glyph(b, x, ty + 1, z, P["cyan"] if lit else P["faint"])
        lab = self.fmt(self.value)
        draw_text(b, (w - FONT.width(lab)) // 2, ty, lab, P["ink"])
        return b


def step_time(v, d):
    if d > 0:
        st = 0.05 if v < 1 - 1e-9 else (0.1 if v < 5 - 1e-9 else (0.5 if v < 20 - 1e-9 else 1.0))
    else:
        st = 0.05 if v <= 1 + 1e-9 else (0.1 if v <= 5 + 1e-9 else (0.5 if v <= 20 + 1e-9 else 1.0))
    return round(max(0.0, v + d * st), 2)


def step_int(v, d):
    return int(v) + d


def step_pct(v, d):
    st = 0.5 if (v < 5 or (v == 5 and d < 0)) else 1.0
    return round(v + d * st, 1)


class TextInput(Widget):
    interactive = True
    focusable = True
    cursor = "xterm"

    def __init__(self, ui, group, x, y, w, h, text="", placeholder="", maxlen=30,
                 on_change=None, on_enter=None, on_keynav=None, hint="", upper=False,
                 secret=False):
        self.text = text
        self.placeholder = placeholder
        self.maxlen = maxlen
        self.on_change, self.on_enter, self.on_keynav = on_change, on_enter, on_keynav
        self.on_blur_cb = None
        self.upper = upper
        self.secret = secret
        self.caret = len(text)
        self.blink = True
        self.scroll = 0
        Widget.__init__(self, ui, group, x, y, w, h, hint)

    def set(self, text):
        if text != self.text:
            self.text = text
            self.caret = min(self.caret, len(text))
            self.refresh()

    def shown_text(self):
        if self.secret and not self.focused and self.text:
            return self.text[:22] + ("…" if len(self.text) > 22 else "")
        return self.text

    def on_focus(self):
        self.caret = len(self.text)
        self.blink = True
        self.ui.anims.append(self._blink)
        self.refresh()

    def on_blur(self):
        self.refresh()
        if self.on_blur_cb:
            self.on_blur_cb(self.text)

    def _blink(self, now):
        if not self.focused:
            return False
        b = int(now * 2.2) % 2 == 0
        if b != self.blink:
            self.blink = b
            self.refresh()
        return True

    def on_press(self, x, y):
        best, bx = len(self.text), None
        for i in range(len(self.text) + 1):
            px = 5 + FONT.width(self.text[:i]) - self.scroll
            if bx is None or abs(px - x) < bx:
                best, bx = i, abs(px - x)
        self.caret = best
        self.refresh()

    def _changed(self):
        self.refresh()
        if self.on_change:
            self.on_change(self.text)

    def on_key(self, e):
        ks, ch = e.keysym, e.char
        ctrl = bool(e.state & 0x4)
        t = self.text
        if ks == "BackSpace":
            if self.caret > 0:
                self.text = t[:self.caret - 1] + t[self.caret:]
                self.caret -= 1
                self._changed()
        elif ks == "Delete":
            if self.caret < len(t):
                self.text = t[:self.caret] + t[self.caret + 1:]
                self._changed()
        elif ks == "Left":
            self.caret = max(0, self.caret - 1)
            self.refresh()
        elif ks == "Right":
            self.caret = min(len(t), self.caret + 1)
            self.refresh()
        elif ks == "Home":
            self.caret = 0
            self.refresh()
        elif ks == "End":
            self.caret = len(t)
            self.refresh()
        elif ks in ("Return", "KP_Enter"):
            if self.on_enter:
                self.on_enter(self.text)
        elif ks in ("Up", "Down", "Tab"):
            if self.on_keynav:
                self.on_keynav(ks)
        elif ks == "Escape":
            self.ui.set_focus(None)
        elif ctrl and ks.lower() == "v":
            try:
                clip = self.ui.root.clipboard_get()
            except tk.TclError:
                clip = ""
            clip = re.sub(r"[\r\n\t]", " ", clip).strip()
            self._insert(clip)
        elif ctrl and ks.lower() == "a":
            self.text = ""
            self.caret = 0
            self._changed()
        elif ch and len(ch) == 1 and ch.isprintable() and not ctrl:
            self._insert(ch)
        else:
            # let the app's hotkeys through (they only reach Tk off Windows)
            hk = getattr(getattr(self.ui, "app", None), "settings", {}).get("hotkeys") or {}
            return tk_keysym_to_key(ks) not in [c for c in hk.values() if c]
        return True

    def _insert(self, s):
        if self.upper:
            s = s.upper()
        room = self.maxlen - len(self.text)
        s = s[:max(0, room)]
        if s:
            self.text = self.text[:self.caret] + s + self.text[self.caret:]
            self.caret += len(s)
            self._changed()

    def render(self):
        P = PAL
        w, h = self.w, self.h
        border = P["cyan"] if self.focused else (P["dim"] if self.hovered else P["line"])
        b = draw_field(w, h, border)
        ty = (h - 7) // 2
        inner = w - 10
        text = self.shown_text()
        cw = FONT.width(text[:self.caret])
        if cw - self.scroll > inner:
            self.scroll = cw - inner
        elif cw - self.scroll < 0:
            self.scroll = cw
        if not self.focused:
            self.scroll = 0
        if not text and not self.focused:
            draw_text(b, 5, ty, ellipsize(self.placeholder, inner), P["faint"])
        else:
            clip = Bitmap(inner + 2, h)
            draw_text(clip, -self.scroll, ty, text if self.focused else ellipsize(text, inner),
                      P["ink"])
            if self.focused and self.blink:
                cx = cw - self.scroll
                clip.rect(min(inner, max(0, cx)), ty - 1, 1, 9, P["cyan"])
            b.blit(clip, 5, 0)
        return b


class KeySlot(Widget):
    """Click, then press a key to bind it. Right-click clears."""
    interactive = True
    focusable = True

    def __init__(self, ui, group, x, y, w, h, value, on_change, hint=""):
        self.value = value or ""
        self.on_change = on_change
        self.pending = None
        self.blink = True
        self.warn = False
        Widget.__init__(self, ui, group, x, y, w, h, hint)

    def set(self, v):
        v = v or ""
        if v != self.value:
            self.value = v
            self.refresh()

    def set_warn(self, v):
        if bool(v) != self.warn:
            self.warn = bool(v)
            self.refresh()

    def on_focus(self):
        self.pending = None
        self.ui.anims.append(self._blink)
        self.refresh()

    def on_blur(self):
        self.pending = None
        self.refresh()

    def _blink(self, now):
        if not self.focused:
            return False
        b = int(now * 3) % 2 == 0
        if b != self.blink:
            self.blink = b
            self.refresh()
        return True

    def _commit(self, v):
        self.value = v
        self.on_change(v)
        self.ui.app.sound("ok")
        self.ui.set_focus(None)

    def on_key(self, e):
        name = tk_keysym_to_key(e.keysym)
        if e.keysym == "Escape":
            self.ui.set_focus(None)
            return True
        if name is None:
            return True
        if name in MODIFIER_KEYS:
            self.pending = name
            return True
        mods = []
        if e.state & 0x4:
            mods.append("ctrl")
        if e.state & 0x1:
            mods.append("shift")
        if (IS_WIN and e.state & 0x20000) or (not IS_WIN and e.state & 0x8):
            mods.append("alt")
        self._commit("+".join(mods + [name]))
        return True

    def on_keyup(self, e):
        name = tk_keysym_to_key(e.keysym)
        if self.pending and name == self.pending:
            self._commit(name)
            return True
        return False

    def on_rclick(self, x, y):
        self.value = ""
        self.on_change("")
        self.ui.set_focus(None)
        self.refresh()

    def render(self):
        P = PAL
        w, h = self.w, self.h
        listening = self.focused
        if listening:
            border = P["yellow"] if self.blink else P["orange"]
        elif self.warn:
            border = P["orange"]
        else:
            border = P["dim"] if self.hovered else P["line"]
        b = draw_field(w, h, border, hexc("#2A2410") if listening else None)
        ty = (h - 7) // 2
        if listening:
            lab, col, f = "PRESS KEY", P["yellow"], FONT
            if FONT.width(lab) > w - 6:
                lab, f = "PRESS", FONT
        elif self.value:
            lab, col, f = key_label(self.value), P["ink"], FONT
        else:
            lab, col, f = "-", P["faint"], FONT
        if f.width(lab) > w - 6:
            f = TINY
        lab = ellipsize(lab, w - 6, f)
        draw_text(b, (w - f.width(lab)) // 2, ty + (1 if f is TINY else 0), lab, col, f)
        return b


class ListBox(Widget):
    """Scrollable rows drawn by a callback."""
    interactive = True

    def __init__(self, ui, group, x, y, w, h, row_h, draw_row, on_click=None, hint=""):
        self.items_ = []
        self.row_h = row_h
        self.draw_row = draw_row
        self.on_click = on_click
        self.scroll = 0
        self.hover_i = -1
        self.selected = -1
        self.press_i = None
        self.empty_text = ""
        Widget.__init__(self, ui, group, x, y, w, h, hint)

    def set_items(self, items, selected=None):
        self.items_ = list(items)
        if selected is not None:
            self.selected = selected
        self.scroll = max(0, min(self.scroll, self.max_scroll()))
        self.refresh()

    def max_scroll(self):
        return max(0, len(self.items_) * self.row_h - self.h)

    def ensure_visible(self, i):
        top, bot = i * self.row_h, (i + 1) * self.row_h
        if top < self.scroll:
            self.scroll = top
        elif bot > self.scroll + self.h:
            self.scroll = bot - self.h
        self.refresh()

    def index_at(self, y):
        i = int((y + self.scroll) // self.row_h)
        return i if 0 <= i < len(self.items_) else -1

    def on_move(self, x, y):
        i = self.index_at(y)
        if i != self.hover_i:
            self.hover_i = i
            self.refresh()

    def on_hover(self, on):
        if not on:
            self.hover_i = -1
        self.refresh()

    def on_press(self, x, y):
        self.press_i = self.index_at(y)

    def on_release(self, x, y, inside):
        i = self.index_at(y)
        if inside and i >= 0 and i == self.press_i and self.on_click:
            self.on_click(i, x, y + self.scroll - i * self.row_h)
        self.press_i = None

    def on_wheel(self, step, state):
        ms = self.max_scroll()
        if ms <= 0:
            return False
        self.scroll = max(0, min(ms, self.scroll - step * self.row_h))
        self.refresh()
        return True

    def render(self):
        P = PAL
        w, h = self.w, self.h
        b = Bitmap(w, h)
        ms = self.max_scroll()
        rw = w - 5 if ms > 0 else w
        first = int(self.scroll // self.row_h)
        y = first * self.row_h - self.scroll
        i = first
        while y < h and i < len(self.items_):
            row = Bitmap(rw, self.row_h)
            self.draw_row(row, i, self.items_[i], i == self.hover_i, i == self.selected)
            b.blit(row, 0, y)
            y += self.row_h
            i += 1
        if not self.items_ and self.empty_text:
            yy = 6
            for line in wrap_text(self.empty_text, w - 8, TINY):
                draw_text(b, 4, yy, line, P["faint"], TINY)
                yy += 8
        if ms > 0:
            th = max(10, int(h * h / float(h + ms)))
            ty = int((h - th) * self.scroll / float(ms))
            b.rrect(w - 3, 0, 3, h, 1, P["dark2"])
            b.rrect(w - 3, ty, 3, th, 1, P["dim"])
        return b


def row_highlight(b, color, r=3):
    b.rrect(0, 0, b.w, b.h - 1, r, color)


class Meter(Widget):
    """Live score bar with a draggable threshold marker."""
    interactive = True
    cursor = "sb_h_double_arrow"

    def __init__(self, ui, group, x, y, w, h, maxv, mark, on_mark, above=True, hint=""):
        self.value = None
        self.maxv, self.mark, self.on_mark, self.above = maxv, mark, on_mark, above
        Widget.__init__(self, ui, group, x, y, w, h, hint)

    def set_value(self, v):
        if v != self.value:
            self.value = v
            self.refresh()

    def set_mark(self, m):
        if m != self.mark:
            self.mark = m
            self.refresh()

    def _x_to_v(self, x):
        v = (x - 3) / float(self.w - 6) * self.maxv
        return round(max(0.5, min(self.maxv, v)) * 2) / 2.0

    def on_press(self, x, y):
        self.on_drag(x, y)

    def on_drag(self, x, y):
        v = self._x_to_v(x)
        if v != self.mark:
            self.mark = v
            self.refresh()
            self.on_mark(v)

    def render(self):
        P = PAL
        w, h = self.w, self.h
        b = Bitmap(w, h)
        b.rrect(0, 3, w, h - 3, 4, P["dim"] if self.hovered else P["line"])
        b.rrect(1, 4, w - 2, h - 5, 3, P["night"])
        inner = w - 6
        if self.value is not None:
            v = max(0.0, min(self.maxv, self.value))
            fill = int(round(inner * v / self.maxv))
            shiny = (v > self.mark) if self.above else (v >= self.mark)
            col = P["gold"] if shiny else P["green"]
            if fill > 0:
                b.rrect(3, 6, fill, h - 9, 2, col)
                b.rect(4, 6, max(0, fill - 2), 1, mix(col, P["white"], 0.55))
        for k in range(1, 4):
            tx = 3 + inner * k // 4
            b.px(tx, h - 3, P["faint"])
        mx = 3 + int(round(inner * self.mark / self.maxv))
        b.rect(mx - 2, 0, 5, 1, P["bad"])
        b.rect(mx - 1, 1, 3, 1, P["bad"])
        b.rect(mx, 2, 1, h - 3, P["bad"])
        return b


class ImageBox(Widget):
    """Shows a Tk photo inside a box (screen-resolution images).
    anchor: "center" or "bottom" (feet on the ground)."""

    def __init__(self, ui, group, x, y, w, h, cb=None, hint="", cursor="hand2", anchor="center"):
        self.cb = cb
        self.interactive = cb is not None
        self.img = None
        self.dx = self.dy = 0
        self.anchor = anchor
        Widget.__init__(self, ui, group, x, y, w, h, hint)
        self.cursor = cursor
        self.bob = 0

    def set_photo(self, photo):
        self.img = photo
        S = self.ui.S
        if photo is None:
            self.ui.cv.itemconfig(self.item, image="")
            return
        pw, ph = photo.width(), photo.height()
        self.dx = (self.w * S - pw) // 2
        if self.anchor == "bottom":
            self.dy = self.h * S - ph
        else:
            self.dy = (self.h * S - ph) // 2
        self._place()
        self.ui.cv.itemconfig(self.item, image=photo)

    def _place(self):
        S = self.ui.S
        self.ui.cv.coords(self.item, self.ax() * S + self.dx, self.ay() * S + self.dy + self.bob * S)

    def set_bob(self, v):
        if v != self.bob:
            self.bob = v
            self._place()

    def move(self, x, y):
        self.x, self.y = x, y
        self._place()

    def sync(self):
        self.dirty = False

    def on_release(self, x, y, inside):
        if inside and self.cb:
            self.cb(x, y)


class Sparkles(Widget):
    def __init__(self, ui, group, x, y, w, h, spots, stars):
        self.spots = spots
        self.on = False
        self.phase = 0
        self.stars = stars
        Widget.__init__(self, ui, group, x, y, w, h)
        ui.anims.append(self._anim)

    def set_on(self, v):
        if v != self.on:
            self.on = v
            self.refresh()

    def _anim(self, now):
        if self.on:
            ph = int(now * 8)
            if ph != self.phase:
                self.phase = ph
                self.refresh()
        return self.ui.alive

    def render(self):
        if not self.on:
            return None
        b = Bitmap(self.w, self.h)
        seq = (0, 1, 2, 3, 2, 1, 0, -1, -1, -1)
        for i, (x, y) in enumerate(self.spots):
            s = seq[(self.phase + i * 3) % len(seq)]
            if s >= 0:
                b.blit(self.stars[s], x - 4, y - 4)
        return b


class DialogBox(Widget):
    """Message box with typed-out text, pages and a pop-in animation."""
    interactive = True

    def __init__(self, ui, group, x, y, w, h):
        self.queue = []
        self.pages = [[""]]
        self.page = 0
        self.lines = []
        self.shown_chars = 0
        self.start = 0.0
        self.pop_t0 = 0.0
        self.hide_at = None
        self.sticky = False
        self.tone = "info"
        self.duration = 4.0
        self.bl = 0
        self.popping = False
        Widget.__init__(self, ui, group, x, y, w, h)
        self.visible = False
        self.apply_state()
        ui.anims.append(self._anim)

    def say(self, text, tone="info", sticky=False, duration=4.0):
        if self.visible and self.sticky:
            self.queue.append((text, tone, sticky, duration))
            return
        self.queue = [(text, tone, sticky, duration)]
        self._next()

    def clear(self):
        self.queue = []
        self.show(False)

    def _next(self):
        if not self.queue:
            self.show(False)
            return
        text, tone, sticky, duration = self.queue.pop(0)
        self.tone, self.sticky, self.duration = tone, sticky, duration
        lines = wrap_text(text, self.w - 14)
        self.pages = [lines[i:i + 2] for i in range(0, len(lines), 2)] or [[""]]
        self.page = 0
        if not self.visible:
            self.pop_t0 = time.monotonic()
            self.popping = True
        self._start_page()

    def _start_page(self):
        self.lines = self.pages[self.page]
        self.shown_chars = 0
        self.start = time.monotonic() + (0.12 if self.popping else 0.0)
        self.hide_at = None
        self.show(True)
        self.refresh()

    def _advance(self):
        if self.page + 1 < len(self.pages):
            self.page += 1
            self._start_page()
        else:
            self._next()

    def total(self):
        return sum(len(l) for l in self.lines)

    def more(self):
        return self.page + 1 < len(self.pages)

    def _anim(self, now):
        if not self.ui.alive:
            return False
        if not self.visible:
            return True
        fast = False
        if self.popping:
            if now - self.pop_t0 > 0.13:
                self.popping = False
            self.refresh()
            fast = True
        n = max(0, min(self.total(), int((now - self.start) * 60)))
        if n != self.shown_chars:
            self.shown_chars = n
            self.refresh()
            fast = True
            if n >= self.total():
                if self.more():
                    self.hide_at = now + 1.8
                elif not self.sticky:
                    self.hide_at = now + self.duration
        if n >= self.total():
            bl = int(now * 2.5) % 2
            if bl != self.bl:
                self.bl = bl
                self.refresh()
        if self.hide_at and now >= self.hide_at:
            self._advance()
        return "fast" if fast else True

    def on_release(self, x, y, inside):
        if not inside:
            return
        if self.shown_chars < self.total():
            self.start = -1e9
        elif self.more() or not self.sticky or self.queue:
            self._advance()

    def render(self):
        w, h = self.w, self.h
        P = PAL
        b = Bitmap(w, h)
        edge = {"info": P["scr_ink"], "bad": P["bad_dk"], "good": hexc("#1E6B3B"),
                "shiny": P["gold_dk"]}.get(self.tone, P["scr_ink"])
        bw = w
        if self.popping:
            t = min(1.0, (time.monotonic() - self.pop_t0) / 0.12)
            bw = max(12, int(w * (0.25 + 0.75 * (1 - (1 - t) ** 2))))
        x0 = (w - bw) // 2
        b.rrect(x0, 0, bw, h, 5, edge)
        b.rrect(x0 + 1, 1, bw - 2, h - 2, 4, P["white"])
        b.rrect(x0 + 2, 2, bw - 4, h - 4, 4, edge)
        b.rrect(x0 + 3, 3, bw - 6, h - 6, 3, hexc("#FBFBF5"))
        if self.popping:
            return b
        left = self.shown_chars
        y = 7
        ink = P["scr_ink"] if self.tone != "bad" else hexc("#7A0E1F")
        for line in self.lines:
            part = line[:max(0, left)]
            left -= len(line)
            draw_text(b, 7, y, part, ink)
            y += 11
        if self.shown_chars >= self.total() and self.bl == 0 and (self.more() or not self.sticky):
            draw_text(b, w - 12, h - 11, "▼", edge)
        return b


class MenuBox(Widget):
    """A little pick-one menu with a blinking ▶ cursor."""
    interactive = True

    def __init__(self, ui, group, x, y, w, options, on_pick):
        self.options = options  # list of (key, label)
        self.on_pick = on_pick
        self.sel = 0
        self.bl = 0
        Widget.__init__(self, ui, group, x, y, w, 10 + 11 * len(options))
        self.visible = False
        self.apply_state()
        ui.anims.append(self._anim)

    def _anim(self, now):
        if not self.ui.alive:
            return False
        if self.visible:
            bl = int(now * 3) % 2
            if bl != self.bl:
                self.bl = bl
                self.refresh()
        return True

    def on_move(self, x, y):
        i = max(0, min(len(self.options) - 1, int((y - 5) // 11)))
        if i != self.sel:
            self.sel = i
            self.ui.app.sound("tick")
            self.refresh()

    def on_release(self, x, y, inside):
        if inside:
            self.on_pick(self.options[self.sel][0])

    def key_nav(self, ks):
        if ks == "Up":
            self.sel = (self.sel - 1) % len(self.options)
        elif ks == "Down":
            self.sel = (self.sel + 1) % len(self.options)
        elif ks in ("Return", "space", "z", "x", "KP_Enter"):
            self.on_pick(self.options[self.sel][0])
            return
        self.refresh()

    def render(self):
        P = PAL
        b = Bitmap(self.w, self.h)
        b.rrect(0, 0, self.w, self.h, 5, P["gold_dk"])
        b.rrect(1, 1, self.w - 2, self.h - 2, 4, P["white"])
        b.rrect(2, 2, self.w - 4, self.h - 4, 4, P["gold_dk"])
        b.rrect(3, 3, self.w - 6, self.h - 6, 3, hexc("#FFFBEA"))
        for i, (_k, lab) in enumerate(self.options):
            y = 6 + i * 11
            if i == self.sel:
                b.rrect(5, y - 2, self.w - 10, 11, 2, hexc("#FFE9A8"))
                if self.bl == 0:
                    draw_text(b, 7, y, "▶", P["red"])
            draw_text(b, 15, y, lab, P["scr_ink"])
        return b


class Marquee(Widget):
    """The scrolling status strip."""

    def __init__(self, ui, group, x, y, w, h):
        self.text = ""
        self.color = PAL["status_ink"]
        self.offset = 0.0
        self.t0 = time.monotonic()
        Widget.__init__(self, ui, group, x, y, w, h)
        ui.anims.append(self._anim)

    def set(self, text, color=None):
        color = color or PAL["status_ink"]
        if text != self.text or color != self.color:
            self.text, self.color = text, color
            self.t0 = time.monotonic()
            self.offset = 0
            self.refresh()

    def _anim(self, now):
        if not self.ui.alive:
            return False
        tw = FONT.width(self.text)
        if tw > self.w - 4:
            loop = tw + 30
            el = now - self.t0
            off = 0 if el < 1.2 else int(((el - 1.2) * 28) % loop)
            if off != self.offset:
                self.offset = off
                self.refresh()
        return True

    def render(self):
        b = Bitmap(self.w, self.h)
        tw = FONT.width(self.text)
        y = (self.h - 7) // 2
        if tw <= self.w - 4:
            draw_text(b, 2, y, self.text, self.color)
        else:
            x = 2 - int(self.offset)
            draw_text(b, x, y, self.text, self.color)
            draw_text(b, x + tw + 30, y, self.text, self.color)
        return b


class StartButton(Widget):
    """The big round black START / STOP button."""
    interactive = True

    def __init__(self, ui, group, x, y, cb, hint="", r=15):
        self.cb = cb
        self.running = False
        self.glow = 0
        self.r = r
        Widget.__init__(self, ui, group, x, y, 2 * r + 1, 2 * r + 1, hint)

    def set_running(self, v):
        if v != self.running:
            self.running = v
            self.refresh()

    def set_glow(self, g):
        if g != self.glow:
            self.glow = g
            self.refresh()

    def on_release(self, x, y, inside):
        if inside:
            self.cb()

    def render(self):
        P = PAL
        r = self.r
        d = 2 * r + 1
        b = Bitmap(d, d)
        down = self.pressed and self.hovered
        c = r
        b.circle(c, c, r, P["outline"])
        b.circle(c, c, r - 1, hexc("#0D0D11"))
        off = 0 if down else 1
        base = P["black_hi"] if (self.hovered and not down) else P["black"]
        b.circle(c - off, c - off, r - 2, base)
        if not down:
            for dx, dy in ((-6, -9), (-8, -7), (-9, -5), (-10, -3), (-4, -10)):
                b.px(c + dx * r // 15, c + dy * r // 15, hexc("#5A5A68"))
        o = 1 if down else 0
        if self.running:
            ink = P["bad"]
            b.rrect(c - 5, c - 5 + o, 10, 10, 2, hexc("#3A0A12"))
            b.rrect(c - 4, c - 4 + o, 8, 8, 1, ink)
            b.rect(c - 3, c - 3 + o, 3, 1, mix(ink, P["white"], 0.5))
        else:
            ink = P["green"] if not self.glow else mix(P["green"], P["white"], 0.45)
            for i in range(6):
                b.rect(c - 3 + i * 2 - 1, c - 6 + i + o, 3, 13 - i * 2, hexc("#08240E"))
            for i in range(5):
                b.rect(c - 3 + i * 2, c - 5 + i + o, 2, 11 - i * 2, ink)
            b.rect(c - 3, c - 5 + o, 1, 9, mix(ink, P["white"], 0.5))
        return b


class DPad(Widget):
    interactive = True

    def __init__(self, ui, group, x, y, cb, hint=""):
        self.cb = cb
        self.zone = None
        Widget.__init__(self, ui, group, x, y, 34, 34, hint)

    def _zone(self, x, y):
        dx, dy = x - 17, y - 17
        if abs(dx) < 4 and abs(dy) < 4:
            return None
        if abs(dx) > abs(dy):
            return "right" if dx > 0 else "left"
        return "down" if dy > 0 else "up"

    def on_move(self, x, y):
        z = self._zone(x, y)
        if z != self.zone:
            self.zone = z
            self.refresh()

    def on_press(self, x, y):
        self.zone = self._zone(x, y)
        self.refresh()

    def on_release(self, x, y, inside):
        z = self._zone(x, y)
        if inside and z:
            self.ui.app.sound("tick")
            self.cb(z)
        self.refresh()

    def render(self):
        P = PAL
        b = Bitmap(34, 34)
        dark, face, hi = P["outline"], P["black"], P["black_hi"]
        b.rrect(0, 11, 34, 12, 3, dark)
        b.rrect(11, 0, 12, 34, 3, dark)
        b.rrect(1, 12, 32, 10, 2, face)
        b.rrect(12, 1, 10, 32, 2, face)
        b.rect(3, 12, 28, 1, hi)
        b.rect(12, 3, 1, 28, hi)
        b.rect(3, 21, 28, 1, hexc("#111117"))
        b.rect(21, 3, 1, 28, hexc("#111117"))
        arrows = {"up": (17, 6, "▲"), "down": (17, 28, "▼"),
                  "left": (6, 17, "◀"), "right": (28, 17, "▶")}
        for z, (x, y, g) in arrows.items():
            lit = self.hovered and self.zone == z
            col = P["white"] if lit else P["gray"]
            if lit and self.pressed:
                b.rrect(x - 4, y - 4, 9, 9, 2, P["black_md"])
            gw = TINY.get(g).w
            draw_text(b, x - gw // 2, y - 2, g, col, TINY)
        b.circle(17, 17, 3, P["black_md"])
        b.px(16, 16, P["black_hi"])
        return b


class RoundButton(Widget):
    """A small round shell button."""
    interactive = True

    def __init__(self, ui, group, x, y, cb, hint="", r=6):
        self.cb = cb
        self.r = r
        Widget.__init__(self, ui, group, x, y, 2 * r + 1, 2 * r + 1, hint)

    def on_release(self, x, y, inside):
        if inside:
            self.ui.app.sound("tick")
            self.cb()

    def render(self):
        P = PAL
        r = self.r
        b = Bitmap(2 * r + 1, 2 * r + 1)
        down = self.pressed and self.hovered
        b.circle(r, r, r, P["outline"])
        b.circle(r, r, r - 1, P["red_dk"])
        o = 0 if down else 1
        b.circle(r - o, r - o, r - 2, P["red_hi"] if (self.hovered and not down) else P["red"])
        if not down:
            b.px(r - 2, r - 3, P["white"])
            b.px(r - 3, r - 2, mix(P["red_hi"], P["white"], 0.5))
        return b


class MiniScreen(Widget):
    """The two small dark screens under the blue keys."""

    def __init__(self, ui, group, x, y, w, h, cb=None, hint=""):
        self.lines = []
        self.cb = cb
        self.interactive = cb is not None
        Widget.__init__(self, ui, group, x, y, w, h, hint)

    def set(self, lines):
        if lines != self.lines:
            self.lines = lines
            self.refresh()

    def on_release(self, x, y, inside):
        if inside and self.cb:
            self.ui.app.sound("click")
            self.cb()

    def render(self):
        b = Bitmap(self.w, self.h)
        if self.hovered and self.cb:
            b.rframe(0, 0, self.w, self.h, 2, PAL["faint"])
        y = 2
        for text, col, font in self.lines:
            draw_text(b, 4, y, ellipsize(text, self.w - 7, font), col, font)
            y += font.line_h
        return b
