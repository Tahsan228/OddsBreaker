"""Hunts, settings and everything that gets saved to disk."""

import base64
import copy
import csv
import datetime
import glob
import json
import os
import shutil
import uuid
import zlib

from . import paths
from .config import (BUTTONS, EMU_NAMES, HOTKEY_DEFAULTS, LEGACY_EMU, TEMPLATE_NAMES,
                     emulator_preset, match_game)
from .detect import default_detect
from .script import parse_script, template_rows

SAVE_VERSION = 3
SHARE_PREFIX = "OB1-"


def now_iso():
    return datetime.datetime.now().replace(microsecond=0).isoformat(sep=" ")


def today():
    return datetime.date.today().isoformat()


def default_profile(name="New Hunt", pokemon="", emulator="mGBA",
                    game="FIRERED / LEAFGREEN", odds=8192):
    keys, hint = emulator_preset(emulator)
    return {"id": uuid.uuid4().hex[:12], "name": name, "pokemon": pokemon,
            "game": game, "odds": odds, "emulator": emulator, "window": hint,
            "keys": keys, "script": template_rows(TEMPLATE_NAMES[0]),
            "template": TEMPLATE_NAMES[0], "detect": default_detect(),
            "encounters": 0, "seconds": 0.0, "phases": [], "found": None,
            "created": now_iso(), "daily": {}, "sessions": [], "scores": [],
            "loop_avg": None}


def fix_profile(p):
    """Fill in anything missing (old saves, hand edits, share codes)."""
    base = default_profile()
    if "script" not in p:
        rows, _errs = parse_script(p.get("sequence") or "")
        p["script"] = rows if rows else base["script"]
    p.pop("sequence", None)
    for k, v in base.items():
        if k not in p:
            p[k] = v
    if not isinstance(p.get("detect"), dict):
        p["detect"] = default_detect()
    for k, v in default_detect().items():
        p["detect"].setdefault(k, v)
    if not isinstance(p.get("keys"), dict):
        p["keys"] = dict(base["keys"])
    for b in BUTTONS:
        p["keys"].setdefault(b, "")
    p["emulator"] = LEGACY_EMU.get(p.get("emulator"), p.get("emulator"))
    if p["emulator"] not in EMU_NAMES:
        p["emulator"] = "Custom"
    p["game"] = match_game(p.get("game"))
    try:
        p["odds"] = max(2, int(p["odds"]))
    except Exception:
        p["odds"] = 8192
    try:
        p["encounters"] = max(0, int(p["encounters"]))
        p["seconds"] = max(0.0, float(p["seconds"]))
    except Exception:
        p["encounters"], p["seconds"] = 0, 0.0
    for k, t in (("daily", dict), ("sessions", list), ("scores", list), ("phases", list)):
        if not isinstance(p.get(k), t):
            p[k] = t()
    p["name"] = str(p.get("name") or "New Hunt")[:24]
    return p


SETTINGS_DEFAULT = {
    "scale": 0, "topmost": False, "sound": "ALL", "frame": "POKEDEX", "pos": None,
    "theme": "RED", "effects": "FULL", "volume": "MED", "hotkeys": dict(HOTKEY_DEFAULTS), "autostop": 0,
    "updates": True, "last_update_check": "", "discord": "", "discord_shot": True,
    "ntfy": "", "notify_errors": True, "notify_every": 0, "stream": False,
    "mini_pos": None, "legacy_checked": False,
}


class Store(object):
    def __init__(self, path=None):
        self.path = path or paths.SAVE_FILE

    def fresh(self):
        p = default_profile("Charmander", "charmander")
        return {"version": SAVE_VERSION, "active": p["id"], "profiles": [p], "log": [],
                "settings": copy.deepcopy(SETTINGS_DEFAULT), "welcomed": False}

    def exists(self):
        return os.path.exists(self.path) or os.path.exists(self.path + ".bak")

    def load(self):
        data = None
        for path in (self.path, self.path + ".bak"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("profiles"):
                    break
            except Exception:
                data = None
        if not isinstance(data, dict) or not data.get("profiles"):
            data = self.fresh()
        return normalize(data)

    def save(self, data):
        d = os.path.dirname(self.path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        if os.path.exists(self.path):
            os.replace(self.path, self.path + ".bak")
        os.replace(tmp, self.path)
        self.daily_backup()

    def daily_backup(self, keep=14):
        """One copy of the save per day in backups/ (newest 14 kept)."""
        try:
            folder = os.path.join(os.path.dirname(self.path), "backups")
            dest = os.path.join(folder, "profiles-%s.json" % today())
            if os.path.exists(dest) or not os.path.exists(self.path):
                return
            if not os.path.isdir(folder):
                os.makedirs(folder)
            shutil.copyfile(self.path, dest)
            old = sorted(glob.glob(os.path.join(folder, "profiles-*.json")))
            for f in old[:-keep]:
                os.remove(f)
        except Exception:
            pass


def normalize(data):
    for p in data["profiles"]:
        fix_profile(p)
    if not isinstance(data.get("log"), list):
        data["log"] = []
    s = data.get("settings")
    if not isinstance(s, dict):
        s = data["settings"] = {}
    for k, v in SETTINGS_DEFAULT.items():
        s.setdefault(k, copy.deepcopy(v))
    if not isinstance(s.get("hotkeys"), dict):
        s["hotkeys"] = dict(HOTKEY_DEFAULTS)
    for k, v in HOTKEY_DEFAULTS.items():
        s["hotkeys"].setdefault(k, v)
    data["version"] = SAVE_VERSION
    ids = [p["id"] for p in data["profiles"]]
    if data.get("active") not in ids:
        data["active"] = ids[0]
    return data


# ---------------------------------------------------------------------------
# Stats bookkeeping
# ---------------------------------------------------------------------------
def record_count(p, n=1):
    d = p.setdefault("daily", {})
    t = today()
    d[t] = max(0, d.get(t, 0) + n)
    if len(d) > 120:
        for k in sorted(d)[:-120]:
            del d[k]


def record_session(p, start, seconds, resets):
    if resets <= 0 and seconds < 30:
        return
    s = p.setdefault("sessions", [])
    s.append({"start": start, "seconds": round(seconds), "resets": resets})
    del s[:-60]


def record_score(p, score, keep=40):
    if score is None:
        return
    s = p.setdefault("scores", [])
    s.append(round(float(score), 2))
    del s[:-keep]


def record_loop(p, seconds):
    a = p.get("loop_avg")
    p["loop_avg"] = seconds if not a else a * 0.85 + seconds * 0.15


# ---------------------------------------------------------------------------
# Share codes: a hunt's setup as one line of text
# ---------------------------------------------------------------------------
SHARE_KEYS = ("name", "pokemon", "game", "odds", "emulator", "window", "keys", "script", "template")


def export_code(p):
    out = dict((k, p.get(k)) for k in SHARE_KEYS)
    det = dict(p.get("detect") or {})
    det.pop("refs", None)
    out["detect"] = det
    blob = zlib.compress(json.dumps(out, separators=(",", ":")).encode("utf-8"), 9)
    return SHARE_PREFIX + base64.urlsafe_b64encode(blob).decode("ascii").rstrip("=")


def import_code(text):
    """Share code -> a new profile dict. Raises ValueError if it isn't one."""
    t = "".join((text or "").split())
    i = t.find(SHARE_PREFIX)
    if i < 0:
        raise ValueError("That isn't an OddsBreaker hunt code.")
    body = t[i + len(SHARE_PREFIX):]
    body += "=" * (-len(body) % 4)
    try:
        raw = json.loads(zlib.decompress(base64.urlsafe_b64decode(body.encode("ascii"))))
    except Exception:
        raise ValueError("The hunt code looks cut off or broken.")
    if not isinstance(raw, dict):
        raise ValueError("The hunt code looks cut off or broken.")
    p = default_profile()
    for k in SHARE_KEYS:
        if k in raw:
            p[k] = raw[k]
    if isinstance(raw.get("detect"), dict):
        det = default_detect()
        det.update(raw["detect"])
        det["refs"] = []
        p["detect"] = det
    p["id"] = uuid.uuid4().hex[:12]
    p["created"] = now_iso()
    return fix_profile(p)


# ---------------------------------------------------------------------------
# Bringing hunts over from ShinyDex (the old name of this app)
# ---------------------------------------------------------------------------
def legacy_candidates():
    home = os.path.expanduser("~")
    roots = [paths.app_dir()]
    for sub in ("Downloads", "Desktop", "Documents", os.path.join("OneDrive", "Desktop"),
                os.path.join("OneDrive", "Documents")):
        roots.append(os.path.join(home, sub))
    found = []
    for r in roots:
        if not os.path.isdir(r):
            continue
        for pat in ("ShinyDex_data", os.path.join("*", "ShinyDex_data"),
                    os.path.join("*", "*", "ShinyDex_data")):
            for d in glob.glob(os.path.join(r, pat)):
                f = os.path.join(d, "profiles.json")
                if os.path.isfile(f) and f not in found:
                    found.append(f)
    return found


def merge_legacy(data, path):
    """Copy hunts and shiny log entries from an old ShinyDex save into data.
    Returns how many hunts were added."""
    old = Store(path).load()
    have = set(p["id"] for p in data["profiles"])
    names = set((p["name"], p.get("pokemon")) for p in data["profiles"])
    stamps = set((p["name"], p.get("pokemon"), p.get("created")) for p in data["profiles"])
    added = 0
    for p in old["profiles"]:
        if p["id"] in have or (p["name"], p.get("pokemon"), p.get("created")) in stamps:
            continue  # imported before
        if (p["name"], p.get("pokemon")) in names and p["encounters"] == 0:
            continue
        p = fix_profile(copy.deepcopy(p))
        data["profiles"].append(p)
        have.add(p["id"])
        added += 1
    seen = set((e.get("date"), e.get("pokemon")) for e in data["log"])
    for e in old.get("log", []):
        if (e.get("date"), e.get("pokemon")) not in seen:
            data["log"].append(e)
    data["log"].sort(key=lambda e: e.get("date") or "")
    return added


def drop_untouched_starter(data):
    """After an import, remove the blank starter hunt nobody has used."""
    keep = [p for p in data["profiles"]
            if not (p["encounters"] == 0 and not p["detect"].get("region")
                    and p["name"] == "Charmander" and p["seconds"] == 0)]
    if keep and len(keep) < len(data["profiles"]):
        data["profiles"] = keep
        if data["active"] not in [p["id"] for p in keep]:
            data["active"] = keep[0]["id"]


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------
def export_csv(data, folder):
    if not os.path.isdir(folder):
        os.makedirs(folder)
    hunts = os.path.join(folder, "hunts.csv")
    with open(hunts, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "pokemon", "game", "odds", "resets", "hours", "phases",
                    "caught", "caught_on", "created"])
        for p in data["profiles"]:
            fd = p.get("found") or {}
            w.writerow([p["name"], p.get("pokemon", ""), p.get("game", ""), p["odds"],
                        p["encounters"], round(p["seconds"] / 3600.0, 2), len(p.get("phases") or []),
                        "yes" if fd else "no", fd.get("date", ""), p.get("created", "")])
    shinies = os.path.join(folder, "shinies.csv")
    with open(shinies, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "pokemon", "type", "hunt", "game", "resets", "hours", "picture"])
        for e in data["log"]:
            w.writerow([e.get("date", ""), e.get("pokemon", ""), e.get("type", ""),
                        e.get("profile", ""), e.get("game", ""), e.get("encounters", 0),
                        round((e.get("seconds") or 0) / 3600.0, 2), e.get("image", "")])
    return hunts, shinies
