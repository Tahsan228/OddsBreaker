"""Static tables: keyboard keys, emulators, games, odds and script templates."""

import re
import sys

IS_WIN = sys.platform.startswith("win")

# ---------------------------------------------------------------------------
# Keyboard: names -> hardware scancodes (set 1). Scancodes work with
# DirectInput, SDL, Qt and raw-input emulators alike.
# ---------------------------------------------------------------------------
SCANCODES = {
    "esc": 0x01, "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
    "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0A, "0": 0x0B, "-": 0x0C,
    "=": 0x0D, "backspace": 0x0E, "tab": 0x0F, "q": 0x10, "w": 0x11,
    "e": 0x12, "r": 0x13, "t": 0x14, "y": 0x15, "u": 0x16, "i": 0x17,
    "o": 0x18, "p": 0x19, "[": 0x1A, "]": 0x1B, "enter": 0x1C, "ctrl": 0x1D,
    "a": 0x1E, "s": 0x1F, "d": 0x20, "f": 0x21, "g": 0x22, "h": 0x23,
    "j": 0x24, "k": 0x25, "l": 0x26, ";": 0x27, "'": 0x28, "`": 0x29,
    "shift": 0x2A, "\\": 0x2B, "z": 0x2C, "x": 0x2D, "c": 0x2E, "v": 0x2F,
    "b": 0x30, "n": 0x31, "m": 0x32, ",": 0x33, ".": 0x34, "/": 0x35,
    "rshift": 0x36, "nummul": 0x37, "alt": 0x38, "space": 0x39,
    "capslock": 0x3A, "f1": 0x3B, "f2": 0x3C, "f3": 0x3D, "f4": 0x3E,
    "f5": 0x3F, "f6": 0x40, "f7": 0x41, "f8": 0x42, "f9": 0x43, "f10": 0x44,
    "numlock": 0x45, "scrolllock": 0x46, "num7": 0x47, "num8": 0x48,
    "num9": 0x49, "numminus": 0x4A, "num4": 0x4B, "num5": 0x4C, "num6": 0x4D,
    "numplus": 0x4E, "num1": 0x4F, "num2": 0x50, "num3": 0x51, "num0": 0x52,
    "numdot": 0x53, "f11": 0x57, "f12": 0x58,
}
EXTENDED_SCANCODES = {
    "rctrl": 0x1D, "ralt": 0x38, "up": 0x48, "down": 0x50, "left": 0x4B,
    "right": 0x4D, "insert": 0x52, "delete": 0x53, "home": 0x47, "end": 0x4F,
    "pageup": 0x49, "pagedown": 0x51, "numenter": 0x1C, "numdiv": 0x35,
}
KEY_ALIASES = {
    "return": "enter", "escape": "esc", "control": "ctrl", "lctrl": "ctrl",
    "lshift": "shift", "lalt": "alt", "del": "delete", "pgup": "pageup",
    "pgdn": "pagedown", "spacebar": "space", "ins": "insert",
    "arrowup": "up", "arrowdown": "down", "arrowleft": "left",
    "arrowright": "right", "minus": "-", "equals": "=", "comma": ",",
    "period": ".", "slash": "/", "semicolon": ";", "backslash": "\\",
    "bksp": "backspace",
}
TK_KEYSYMS = {
    "Return": "enter", "BackSpace": "backspace", "Escape": "esc", "Tab": "tab",
    "space": "space", "Shift_L": "shift", "Shift_R": "rshift",
    "Control_L": "ctrl", "Control_R": "rctrl", "Alt_L": "alt", "Alt_R": "ralt",
    "Up": "up", "Down": "down", "Left": "left", "Right": "right",
    "Insert": "insert", "Delete": "delete", "Home": "home", "End": "end",
    "Prior": "pageup", "Next": "pagedown", "minus": "-", "equal": "=",
    "bracketleft": "[", "bracketright": "]", "semicolon": ";",
    "apostrophe": "'", "grave": "`", "backslash": "\\", "comma": ",",
    "period": ".", "slash": "/", "KP_Enter": "numenter", "KP_Add": "numplus",
    "KP_Subtract": "numminus", "KP_Multiply": "nummul", "KP_Divide": "numdiv",
    "KP_Decimal": "numdot", "Caps_Lock": "capslock",
}
for _i in range(10):
    TK_KEYSYMS["KP_%d" % _i] = "num%d" % _i
MODIFIER_KEYS = ("ctrl", "rctrl", "shift", "rshift", "alt", "ralt")

KEY_LABELS = {
    "enter": "ENTER", "backspace": "BKSP", "rshift": "RSHIFT", "shift": "SHIFT",
    "ctrl": "CTRL", "rctrl": "RCTRL", "alt": "ALT", "ralt": "RALT",
    "space": "SPACE", "up": "▲", "down": "▼", "left": "◀",
    "right": "▶", "esc": "ESC", "tab": "TAB", "pageup": "PGUP",
    "pagedown": "PGDN", "delete": "DEL", "insert": "INS", "home": "HOME",
    "end": "END", "capslock": "CAPS", "numenter": "NUM ENT",
    "numplus": "NUM +", "numminus": "NUM -", "nummul": "NUM *",
    "numdiv": "NUM /", "numdot": "NUM .", "numlock": "NUMLK",
    "scrolllock": "SCRLK",
}

# Windows virtual-key codes, used for global hotkeys (RegisterHotKey).
VK_CODES = {
    "backspace": 0x08, "tab": 0x09, "enter": 0x0D, "numenter": 0x0D, "pause": 0x13,
    "capslock": 0x14, "esc": 0x1B, "space": 0x20, "pageup": 0x21, "pagedown": 0x22,
    "end": 0x23, "home": 0x24, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "insert": 0x2D, "delete": 0x2E, "nummul": 0x6A, "numplus": 0x6B, "numminus": 0x6D,
    "numdot": 0x6E, "numdiv": 0x6F, "numlock": 0x90, "scrolllock": 0x91,
    ";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE, "/": 0xBF, "`": 0xC0,
    "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE,
}
for _i in range(26):
    VK_CODES[chr(ord("a") + _i)] = 0x41 + _i
for _i in range(10):
    VK_CODES[str(_i)] = 0x30 + _i
    VK_CODES["num%d" % _i] = 0x60 + _i
for _i in range(1, 13):
    VK_CODES["f%d" % _i] = 0x6F + _i
HOTKEY_MODS = {"ctrl": 0x2, "rctrl": 0x2, "alt": 0x1, "ralt": 0x1, "shift": 0x4, "rshift": 0x4}

HOTKEY_ACTIONS = (("toggle", "START / STOP"), ("plus", "COUNT +1"), ("minus", "COUNT -1"),
                  ("mini", "MINI MODE"))
HOTKEY_DEFAULTS = {"toggle": "f8", "plus": "f9", "minus": "", "mini": ""}


def norm_key(name):
    k = (name or "").strip().lower()
    k = KEY_ALIASES.get(k, k)
    if k in SCANCODES or k in EXTENDED_SCANCODES:
        return k
    return None


def tk_keysym_to_key(keysym):
    if keysym in TK_KEYSYMS:
        return TK_KEYSYMS[keysym]
    if len(keysym) == 1:
        return norm_key(keysym)
    if re.match(r"^F\d{1,2}$", keysym):
        return norm_key(keysym)
    return None


def key_label(combo):
    if not combo:
        return ""
    out = []
    for k in combo.split("+"):
        k = k.strip().lower()
        if k.startswith("num") and len(k) == 4 and k[3].isdigit():
            out.append("NUM " + k[3])
        else:
            out.append(KEY_LABELS.get(k, k.upper()))
    return "+".join(out)


def hotkey_parts(combo):
    """'ctrl+f8' -> (modifier flags, virtual key) or None."""
    mods, vk = 0, None
    for k in (combo or "").lower().split("+"):
        k = k.strip()
        if not k:
            continue
        if k in HOTKEY_MODS:
            mods |= HOTKEY_MODS[k]
        elif k in VK_CODES:
            vk = VK_CODES[k]
        else:
            return None
    if vk is None:
        return None
    return mods, vk


# Game buttons used in scripts, mapped per profile to keyboard keys.
BUTTONS = ["A", "B", "X", "Y", "L", "R", "START", "SELECT",
           "UP", "DOWN", "LEFT", "RIGHT", "RESET", "LOADSTATE"]
_ARROWS = {"UP": "up", "DOWN": "down", "LEFT": "left", "RIGHT": "right"}


def _preset(a, b, x, y, l, r, start, select, reset, load, arrows=None):
    d = {"A": a, "B": b, "X": x, "Y": y, "L": l, "R": r, "START": start,
         "SELECT": select, "RESET": reset, "LOADSTATE": load}
    d.update(arrows if arrows is not None else _ARROWS)
    return d


# name, default keys, window-title pattern, words that identify it in a title
EMULATORS = [
    ("mGBA", _preset("x", "z", "", "", "a", "s", "enter", "backspace", "ctrl+r", "f1"),
     "mGBA", ("mgba",)),
    ("VBA-M", _preset("z", "x", "", "", "a", "s", "enter", "backspace", "ctrl+r", "f1"),
     "VisualBoyAdvance", ("visualboyadvance", "vba-m", "vbam")),
    ("DeSmuME", _preset("x", "z", "s", "a", "q", "w", "enter", "rshift", "", "f1"),
     "DeSmuME", ("desmume",)),
    ("melonDS", _preset("x", "z", "s", "a", "q", "w", "enter", "rshift", "", "f1"),
     "melonDS", ("melonds",)),
    ("Azahar/Citra", _preset("a", "s", "z", "x", "q", "w", "m", "n", "f6", "",
                             {"UP": "t", "DOWN": "g", "LEFT": "f", "RIGHT": "h"}),
     "Azahar|Citra|Lime3DS", ("azahar", "citra", "lime3ds")),
    ("RetroArch", _preset("x", "z", "s", "a", "q", "w", "enter", "rshift", "h", "f4"),
     "RetroArch", ("retroarch",)),
    ("Custom", _preset("", "", "", "", "", "", "", "", "", "",
                       {"UP": "", "DOWN": "", "LEFT": "", "RIGHT": ""}), "", ()),
]
EMU_NAMES = [e[0] for e in EMULATORS]
LEGACY_EMU = {"VisualBoyAdvance-M": "VBA-M", "Azahar / Citra / Lime3DS": "Azahar/Citra"}


def emulator_preset(name):
    for n, keys, hint, words in EMULATORS:
        if n == name:
            return dict(keys), hint
    return dict(EMULATORS[0][1]), EMULATORS[0][2]


def detect_emulator(title):
    t = (title or "").lower()
    for n, keys, hint, words in EMULATORS:
        if any(w in t for w in words):
            return n
    return None


GAMES = [
    ("GOLD/SILVER/CRYSTAL", 8192), ("RUBY / SAPPHIRE", 8192),
    ("EMERALD", 8192), ("FIRERED / LEAFGREEN", 8192),
    ("DIAMOND/PEARL/PLAT", 8192), ("HEARTGOLD/SOULSILVER", 8192),
    ("BLACK / WHITE", 8192), ("BLACK 2 / WHITE 2", 8192), ("X / Y", 4096),
    ("OMEGA R / ALPHA S", 4096), ("SUN / MOON", 4096),
    ("ULTRA SUN / U.MOON", 4096), ("LET'S GO", 4096),
    ("SWORD / SHIELD", 4096), ("B.DIAMOND / S.PEARL", 4096),
    ("LEGENDS: ARCEUS", 4096), ("SCARLET / VIOLET", 4096),
    ("LEGENDS: Z-A", 4096), ("ROM HACK / OTHER", 8192),
]
GAME_NAMES = [g for g, _ in GAMES]
ODDS = [
    (8192, "1/8192  FULL ODDS 2-5"), (4096, "1/4096  FULL ODDS 6+"),
    (2731, "1/2731  CHARM GEN 5"), (1365, "1/1365  CHARM GEN 6+"),
    (1024, "1/1024  BOOSTED"), (683, "1/683  MASUDA 6+"),
    (512, "1/512  MASUDA+CHARM"),
]


def match_game(name):
    """Map old or loosely typed game names onto the GAMES list."""
    if name in GAME_NAMES:
        return name
    key = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    if not key:
        return GAME_NAMES[3]
    for g in GAME_NAMES:
        gk = re.sub(r"[^a-z0-9]", "", g.lower())
        if gk == key or gk.startswith(key[:6]) or key.startswith(gk[:6]):
            return g
    return name


TEMPLATES = [
    ("GBA SOFT RESET", """\
# Soft reset (works in every GB / GBA game)
press A+B+START+SELECT hold 0.3
wait 3
# Title screen, then CONTINUE
press A x5 gap 0.8
# Random wait = new RNG every reset
wait 1~2.5
# Talk to the Pokemon
press A x3 gap 0.9
# Battle intro: look for the shiny
wait 2
check 5
"""),
    ("DS SOFT RESET", """\
# Soft reset (works in every DS Pokemon game)
press L+R+START+SELECT hold 0.3
wait 4
# Title screen, then CONTINUE
press A x6 gap 0.9
wait 1~2.5
# Talk to the Pokemon
press A x3 gap 1
# Battle intro: look for the shiny
wait 2.5
check 6
"""),
    ("3DS SOFT RESET", """\
# Soft reset (L+R+START in 3DS games)
press L+R+START hold 0.4
wait 8
# Title screen, then CONTINUE
press A x6 gap 1.2
wait 1~2.5
# Talk to the Pokemon
press A x3 gap 1.2
# Battle intro: look for the shiny
wait 4
check 8
"""),
    ("EMULATOR RESET KEY", """\
# Emulator reset hotkey (set RESET on the KEYS page)
press RESET
wait 3
# Title screen, then CONTINUE
press A x5 gap 0.8
wait 1~2.5
# Talk to the Pokemon
press A x3 gap 0.9
# Battle intro: look for the shiny
wait 2
check 5
"""),
    ("SAVE STATE LOOP", """\
# Make a save state in front of the Pokemon first
press LOADSTATE
# Random wait = new RNG (best for Gen 3)
wait 0.3~2
press A x2 gap 0.8
# Battle intro: look for the shiny
wait 2
check 5
"""),
]
TEMPLATE_NAMES = [t[0] for t in TEMPLATES]
