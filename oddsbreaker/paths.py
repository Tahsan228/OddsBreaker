"""Where OddsBreaker keeps its files.

Normal install:  %APPDATA%\\OddsBreaker  (Windows) or ~/.local/share/OddsBreaker
Portable:        an "OddsBreaker_data" folder next to the app, used when that
                 folder or a file called "portable.txt" exists there.
Override:        the ODDSBREAKER_DATA environment variable or --data DIR.
"""

import os
import sys

from . import APP_NAME
from .config import IS_WIN

DATA_DIR = SAVE_FILE = SHINY_DIR = SPRITE_DIR = SOUND_DIR = None
BACKUP_DIR = OBS_DIR = LOG_DIR = None
PORTABLE = False


def app_dir():
    """Folder holding the .exe (frozen) or the project checkout (source)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_dir():
    """Bundled read-only files (PyInstaller unpacks them to sys._MEIPASS)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return base
    return app_dir()


def default_data_dir():
    env = os.environ.get("ODDSBREAKER_DATA")
    if env:
        return os.path.abspath(env), False
    here = app_dir()
    local = os.path.join(here, APP_NAME + "_data")
    if os.path.exists(os.path.join(here, "portable.txt")) or os.path.isdir(local):
        return local, True
    if IS_WIN:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_NAME), False
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, APP_NAME), False


def init(path=None):
    """Point every data path at `path` (or the default location)."""
    global DATA_DIR, SAVE_FILE, SHINY_DIR, SPRITE_DIR, SOUND_DIR
    global BACKUP_DIR, OBS_DIR, LOG_DIR, PORTABLE
    if path:
        DATA_DIR, PORTABLE = os.path.abspath(path), False
    else:
        DATA_DIR, PORTABLE = default_data_dir()
    SAVE_FILE = os.path.join(DATA_DIR, "profiles.json")
    SHINY_DIR = os.path.join(DATA_DIR, "shinies")
    SPRITE_DIR = os.path.join(DATA_DIR, "sprites")
    SOUND_DIR = os.path.join(DATA_DIR, "sounds")
    BACKUP_DIR = os.path.join(DATA_DIR, "backups")
    OBS_DIR = os.path.join(DATA_DIR, "stream")
    LOG_DIR = os.path.join(DATA_DIR, "logs")
    return DATA_DIR


def ensure(folder):
    # exist_ok: two download threads may create the same folder at once
    if folder and not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
    return folder


init()
