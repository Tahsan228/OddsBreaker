"""Talking to the operating system: windows, screen capture, keyboard input,
global hotkeys and a fake platform for tests."""

import ctypes
import os
import re
import subprocess
import sys
import threading
import webbrowser

from . import APP_NAME, OWN_TITLES
from .config import (EXTENDED_SCANCODES, IS_WIN, SCANCODES, detect_emulator,
                     emulator_preset, hotkey_parts)
from .imaging import Frame

if IS_WIN:
    from ctypes import wintypes as W

    ULONG_PTR = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", W.WORD), ("wScan", W.WORD), ("dwFlags", W.DWORD),
                    ("time", W.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", W.LONG), ("dy", W.LONG), ("mouseData", W.DWORD),
                    ("dwFlags", W.DWORD), ("time", W.DWORD),
                    ("dwExtraInfo", ULONG_PTR)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", W.DWORD), ("wParamL", W.WORD), ("wParamH", W.WORD)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", W.DWORD), ("u", _INPUTUNION)]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG),
                    ("biPlanes", W.WORD), ("biBitCount", W.WORD),
                    ("biCompression", W.DWORD), ("biSizeImage", W.DWORD),
                    ("biXPelsPerMeter", W.LONG), ("biYPelsPerMeter", W.LONG),
                    ("biClrUsed", W.DWORD), ("biClrImportant", W.DWORD)]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", W.DWORD * 3)]

    class FLASHWINFO(ctypes.Structure):
        _fields_ = [("cbSize", W.UINT), ("hwnd", W.HWND), ("dwFlags", W.DWORD),
                    ("uCount", W.UINT), ("dwTimeout", W.DWORD)]

    WNDENUMPROC = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)


def find_window_in(windows, pattern):
    """Match a window by title. `pattern` may hold alternatives split by |."""
    pats = [p.strip().lower() for p in (pattern or "").split("|") if p.strip()]
    if not pats:
        return None
    wins = [(h, t) for (h, t) in windows if not is_own_title(t)]
    for pat in pats:
        for h, t in wins:
            if t.lower() == pat:
                return h
        for h, t in wins:
            if t.lower().startswith(pat):
                return h
        for h, t in wins:
            if pat in t.lower():
                return h
    return None


def is_own_title(title):
    return any(title.startswith(n) for n in OWN_TITLES)


def window_pattern_for(title):
    """A title pattern that keeps matching when the emulator renames itself."""
    emu = detect_emulator(title)
    if emu:
        return emulator_preset(emu)[1]
    t = title.strip()
    t = re.sub(r"\(\s*\d+(\.\d+)?\s*fps\s*\)", "", t, flags=re.I).strip()
    for sep in (" - ", " | ", " : "):
        if sep in t:
            parts = [p.strip() for p in t.split(sep) if p.strip()]
            if parts:
                return parts[-1] if len(parts[-1]) >= 3 else parts[0]
    return t


class WinPlatform(object):
    name = "windows"
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008

    def __init__(self):
        u = ctypes.WinDLL("user32", use_last_error=True)
        g = ctypes.WinDLL("gdi32")
        k = ctypes.WinDLL("kernel32")
        self.u, self.g, self.k = u, g, k
        try:
            self.dwm = ctypes.WinDLL("dwmapi")
        except OSError:
            self.dwm = None
        H, HDC, HB, HG = W.HWND, W.HDC, W.HBITMAP, W.HGDIOBJ
        u.GetDC.argtypes = [H]
        u.GetDC.restype = HDC
        u.ReleaseDC.argtypes = [H, HDC]
        g.CreateCompatibleDC.argtypes = [HDC]
        g.CreateCompatibleDC.restype = HDC
        g.CreateCompatibleBitmap.argtypes = [HDC, ctypes.c_int, ctypes.c_int]
        g.CreateCompatibleBitmap.restype = HB
        g.SelectObject.argtypes = [HDC, HG]
        g.SelectObject.restype = HG
        g.BitBlt.argtypes = [HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                             ctypes.c_int, HDC, ctypes.c_int, ctypes.c_int, W.DWORD]
        g.GetDIBits.argtypes = [HDC, HB, W.UINT, W.UINT, ctypes.c_void_p,
                                ctypes.POINTER(BITMAPINFO), W.UINT]
        g.DeleteObject.argtypes = [HG]
        g.DeleteDC.argtypes = [HDC]
        u.EnumWindows.argtypes = [WNDENUMPROC, W.LPARAM]
        u.IsWindowVisible.argtypes = [H]
        u.IsWindow.argtypes = [H]
        u.IsIconic.argtypes = [H]
        u.GetWindowTextLengthW.argtypes = [H]
        u.GetWindowTextW.argtypes = [H, W.LPWSTR, ctypes.c_int]
        u.GetWindowRect.argtypes = [H, ctypes.POINTER(W.RECT)]
        u.GetClientRect.argtypes = [H, ctypes.POINTER(W.RECT)]
        u.ClientToScreen.argtypes = [H, ctypes.POINTER(W.POINT)]
        u.GetForegroundWindow.restype = H
        u.SetForegroundWindow.argtypes = [H]
        u.BringWindowToTop.argtypes = [H]
        u.ShowWindow.argtypes = [H, ctypes.c_int]
        u.GetAncestor.argtypes = [H, W.UINT]
        u.GetAncestor.restype = H
        u.GetParent.argtypes = [H]
        u.GetParent.restype = H
        u.GetWindowLongW.argtypes = [H, ctypes.c_int]
        u.GetWindowLongW.restype = ctypes.c_long
        u.SetWindowLongW.argtypes = [H, ctypes.c_int, ctypes.c_long]
        u.SetWindowLongW.restype = ctypes.c_long
        u.GetWindowThreadProcessId.argtypes = [H, ctypes.POINTER(W.DWORD)]
        u.GetWindowThreadProcessId.restype = W.DWORD
        u.AttachThreadInput.argtypes = [W.DWORD, W.DWORD, W.BOOL]
        u.SendInput.argtypes = [W.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        u.SendInput.restype = W.UINT
        u.GetSystemMetrics.argtypes = [ctypes.c_int]
        u.FlashWindowEx.argtypes = [ctypes.POINTER(FLASHWINFO)]
        k.GetCurrentThreadId.restype = W.DWORD

    # -- windows ------------------------------------------------------------
    def _cloaked(self, hwnd):
        if not self.dwm:
            return False
        val = ctypes.c_int(0)
        try:
            self.dwm.DwmGetWindowAttribute(W.HWND(hwnd), 14, ctypes.byref(val), 4)
        except Exception:
            return False
        return bool(val.value)

    def list_windows(self):
        out = []
        u = self.u

        def cb(hwnd, lp):
            try:
                if not u.IsWindowVisible(hwnd):
                    return True
                n = u.GetWindowTextLengthW(hwnd)
                if n <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(n + 1)
                u.GetWindowTextW(hwnd, buf, n + 1)
                if not u.IsIconic(hwnd):
                    r = W.RECT()
                    u.GetWindowRect(hwnd, ctypes.byref(r))
                    if r.right - r.left < 80 or r.bottom - r.top < 60:
                        return True
                if self._cloaked(hwnd):
                    return True
                out.append((hwnd, buf.value))
            except Exception:
                pass
            return True

        proc = WNDENUMPROC(cb)
        u.EnumWindows(proc, 0)
        return out

    def find_window(self, pattern):
        return find_window_in(self.list_windows(), pattern)

    def window_exists(self, hwnd):
        return bool(hwnd) and bool(self.u.IsWindow(hwnd))

    def is_minimized(self, hwnd):
        return bool(self.u.IsIconic(hwnd))

    def client_origin(self, hwnd):
        p = W.POINT(0, 0)
        self.u.ClientToScreen(hwnd, ctypes.byref(p))
        return p.x, p.y

    def client_size(self, hwnd):
        r = W.RECT()
        self.u.GetClientRect(hwnd, ctypes.byref(r))
        return max(1, r.right - r.left), max(1, r.bottom - r.top)

    def focus(self, hwnd):
        u, k = self.u, self.k
        try:
            if u.IsIconic(hwnd):
                u.ShowWindow(hwnd, 9)  # SW_RESTORE
            fg = u.GetForegroundWindow()
            cur = k.GetCurrentThreadId()
            fgt = u.GetWindowThreadProcessId(fg, None) if fg else 0
            attached = False
            if fgt and fgt != cur:
                attached = bool(u.AttachThreadInput(cur, fgt, True))
            u.BringWindowToTop(hwnd)
            u.SetForegroundWindow(hwnd)
            if attached:
                u.AttachThreadInput(cur, fgt, False)
        except Exception:
            pass

    def is_foreground(self, hwnd):
        fg = self.u.GetForegroundWindow()
        if not fg:
            return False
        if fg == hwnd:
            return True
        return self.u.GetAncestor(fg, 3) == self.u.GetAncestor(hwnd, 3)

    # -- our own window -------------------------------------------------------
    def tk_hwnd(self, tkwin):
        try:
            return self.u.GetParent(tkwin.winfo_id()) or tkwin.winfo_id()
        except Exception:
            return None

    def make_app_window(self, tkwin):
        """Give a borderless window a taskbar button."""
        hwnd = self.tk_hwnd(tkwin)
        if not hwnd:
            return False
        ex = self.u.GetWindowLongW(hwnd, -20)
        ex = (ex & ~0x00000080) | 0x00040000  # -TOOLWINDOW +APPWINDOW
        self.u.SetWindowLongW(hwnd, -20, ex)
        return True

    def minimize(self, tkwin):
        hwnd = self.tk_hwnd(tkwin)
        if hwnd:
            self.u.ShowWindow(hwnd, 6)  # SW_MINIMIZE
            return True
        return False

    def restore(self, tkwin):
        hwnd = self.tk_hwnd(tkwin)
        if hwnd and self.u.IsIconic(hwnd):
            self.u.ShowWindow(hwnd, 9)

    def flash(self, tkwin):
        hwnd = self.tk_hwnd(tkwin)
        if not hwnd:
            return
        fi = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 3 | 12, 0, 0)
        try:
            self.u.FlashWindowEx(ctypes.byref(fi))
        except Exception:
            pass

    # -- screen ---------------------------------------------------------------
    def virtual_screen(self):
        gm = self.u.GetSystemMetrics
        return gm(76), gm(77), gm(78), gm(79)

    def capture(self, x, y, w, h):
        w, h = max(1, int(w)), max(1, int(h))
        u, g = self.u, self.g
        sdc = u.GetDC(None)
        mdc = g.CreateCompatibleDC(sdc)
        bmp = g.CreateCompatibleBitmap(sdc, w, h)
        old = g.SelectObject(mdc, bmp)
        try:
            g.BitBlt(mdc, 0, 0, w, h, sdc, int(x), int(y), 0x00CC0020)
            g.SelectObject(mdc, old)
            bmi = BITMAPINFO()
            hdr = bmi.bmiHeader
            hdr.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            hdr.biWidth, hdr.biHeight = w, -h
            hdr.biPlanes, hdr.biBitCount, hdr.biCompression = 1, 32, 0
            buf = ctypes.create_string_buffer(w * h * 4)
            g.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
            return Frame(w, h, buf.raw)
        finally:
            g.DeleteObject(bmp)
            g.DeleteDC(mdc)
            u.ReleaseDC(None, sdc)

    # -- keyboard -----------------------------------------------------------
    def _send(self, key, up):
        if key in EXTENDED_SCANCODES:
            sc = EXTENDED_SCANCODES[key]
            flags = self.KEYEVENTF_SCANCODE | self.KEYEVENTF_EXTENDEDKEY
        else:
            sc = SCANCODES[key]
            flags = self.KEYEVENTF_SCANCODE
        if up:
            flags |= self.KEYEVENTF_KEYUP
        inp = INPUT()
        inp.type = 1
        inp.ki = KEYBDINPUT(0, sc, flags, 0, 0)
        self.u.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def key_down(self, key):
        self._send(key, False)

    def key_up(self, key):
        self._send(key, True)

    def hotkeys(self, bindings, q):
        """Start a global hotkey listener (see HotkeyThread)."""
        t = HotkeyThread(bindings, q)
        t.start()
        t.ready.wait(2.0)
        return t


class HotkeyThread(threading.Thread):
    """Global hotkeys with RegisterHotKey. Key presses arrive on the app queue
    as (None, "hotkey", action). Registered keys don't reach other apps."""
    WM_HOTKEY = 0x0312
    WM_QUIT = 0x0012

    def __init__(self, bindings, q):
        threading.Thread.__init__(self, name="hotkeys")
        self.daemon = True
        self.bindings = dict(bindings)
        self.q = q
        self.ready = threading.Event()
        self.failed = []
        self.tid = None

    def run(self):
        try:
            u = ctypes.WinDLL("user32", use_last_error=True)
            k = ctypes.WinDLL("kernel32")
            u.RegisterHotKey.argtypes = [W.HWND, ctypes.c_int, W.UINT, W.UINT]
            u.UnregisterHotKey.argtypes = [W.HWND, ctypes.c_int]
            u.GetMessageW.argtypes = [ctypes.POINTER(W.MSG), W.HWND, W.UINT, W.UINT]
            u.PeekMessageW.argtypes = [ctypes.POINTER(W.MSG), W.HWND, W.UINT, W.UINT, W.UINT]
            k.GetCurrentThreadId.restype = W.DWORD
            msg = W.MSG()
            u.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # make the message queue
            self.tid = k.GetCurrentThreadId()
            ids = {}
            for i, (action, combo) in enumerate(sorted(self.bindings.items()), 1):
                parts = hotkey_parts(combo)
                if not parts:
                    continue
                mods, vk = parts
                if u.RegisterHotKey(None, i, mods | 0x4000, vk):
                    ids[i] = action
                else:
                    self.failed.append(action)
        except Exception:
            self.ready.set()
            return
        self.ready.set()
        try:
            while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == self.WM_HOTKEY:
                    act = ids.get(int(msg.wParam))
                    if act:
                        self.q.put((None, "hotkey", act))
        finally:
            for i in ids:
                u.UnregisterHotKey(None, i)

    def stop(self):
        if self.tid:
            try:
                ctypes.windll.user32.PostThreadMessageW(self.tid, self.WM_QUIT, 0, 0)
            except Exception:
                pass


class StubPlatform(object):
    """A fake emulator, used by the tests and the self-test on any OS."""
    name = "stub"

    def __init__(self):
        self.shiny = False
        self.log = []
        self.lock = threading.Lock()
        self.origin = (40, 40)
        self.size = (240, 160)
        self.minimized = False
        self.windows = [(1, "mGBA - POKEMON FIRE (stub)"), (2, "Notes.txt - Notepad")]

    def list_windows(self):
        return list(self.windows)

    def find_window(self, pattern):
        return find_window_in(self.list_windows(), pattern)

    def window_exists(self, hwnd):
        return hwnd in [h for h, _t in self.windows]

    def is_minimized(self, hwnd):
        return self.minimized

    def client_origin(self, hwnd):
        return self.origin

    def client_size(self, hwnd):
        return self.size

    def focus(self, hwnd):
        pass

    def is_foreground(self, hwnd):
        return True

    def tk_hwnd(self, tkwin):
        return None

    def make_app_window(self, tkwin):
        return False

    def minimize(self, tkwin):
        return False

    def restore(self, tkwin):
        pass

    def flash(self, tkwin):
        pass

    def virtual_screen(self):
        return 0, 0, 1600, 1000

    def capture(self, x, y, w, h):
        """A fake game screen: sky, ground and a Pokemon-ish blob."""
        w, h = max(1, int(w)), max(1, int(h))
        ox, oy = self.origin
        gw, gh = self.size
        sky = bytes((235, 206, 150, 255))
        ground = bytes((96, 184, 112, 255))
        outside = bytes((30, 30, 30, 255))
        body = bytes((40, 120, 240, 255)) if not self.shiny else bytes((50, 200, 250, 255))
        belly = bytes((120, 200, 250, 255)) if not self.shiny else bytes((90, 230, 250, 255))
        rows = []
        for j in range(h):
            gy = y + j - oy
            row = bytearray()
            for i in range(w):
                gx = x + i - ox
                if not (0 <= gx < gw and 0 <= gy < gh):
                    row += outside
                elif (gx - 170) ** 2 + ((gy - 52) * 1.2) ** 2 < 26 ** 2:
                    row += belly if (gx - 172) ** 2 + (gy - 58) ** 2 < 12 ** 2 else body
                elif gy > 100:
                    row += ground
                else:
                    row += sky
            rows.append(bytes(row))
        return Frame(w, h, b"".join(rows))

    def key_down(self, key):
        with self.lock:
            self.log.append(("down", key))

    def key_up(self, key):
        with self.lock:
            self.log.append(("up", key))

    def hotkeys(self, bindings, q):
        return None


def set_dpi_awareness():
    if not IS_WIN:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def set_app_id():
    """Own taskbar icon and grouping, even when started with pythonw."""
    if not IS_WIN:
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Tahsan.OddsBreaker")
    except Exception:
        pass


class SingleInstance(object):
    """Keeps a second copy from starting (two copies would fight over the save)."""

    def __init__(self):
        self.handle = None
        self.already = False
        if not IS_WIN:
            return
        try:
            k = ctypes.windll.kernel32
            k.CreateMutexW.restype = W.HANDLE
            self.handle = k.CreateMutexW(None, False, "Local\\OddsBreaker.SingleInstance")
            self.already = ctypes.GetLastError() == 183  # ERROR_ALREADY_EXISTS
        except Exception:
            self.already = False

    def wake_other(self):
        """Bring the copy that is already running to the front."""
        if not IS_WIN:
            return False
        try:
            u = ctypes.windll.user32
            u.FindWindowW.restype = W.HWND
            hwnd = u.FindWindowW(None, APP_NAME)
            if hwnd:
                u.ShowWindow(hwnd, 9)
                u.SetForegroundWindow(hwnd)
                return True
        except Exception:
            pass
        return False


def open_path(path):
    """Open a file or folder with the system's default app."""
    try:
        if IS_WIN:
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False


def open_url(url):
    try:
        return webbrowser.open(url)
    except Exception:
        return False
