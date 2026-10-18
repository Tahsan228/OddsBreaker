"""Start-up: command line, logging, crash reports and the single-instance check."""

import argparse
import os
import sys
import traceback

from . import APP_NAME, __version__, paths
from .config import IS_WIN


def parse_args(argv):
    ap = argparse.ArgumentParser(prog=APP_NAME, description="Automatic shiny hunter for any emulator.")
    ap.add_argument("--classic", action="store_true", help="use a normal window frame")
    ap.add_argument("--data", metavar="DIR", help="keep hunts and settings in this folder")
    ap.add_argument("--selftest", metavar="OUTDIR", help="drive every page with a fake emulator, "
                                                        "save screenshots there and exit")
    ap.add_argument("--stub", action="store_true", help="use the fake emulator (for testing)")
    ap.add_argument("--multi", action="store_true", help="allow a second copy to run")
    ap.add_argument("--version", action="version", version="%s %s" % (APP_NAME, __version__))
    args, _unknown = ap.parse_known_args(argv)
    return args


def setup_logging():
    """Without a console (pythonw or the .exe) errors go to <data>/logs/oddsbreaker.log."""
    exe = os.path.basename(sys.executable).lower()
    if sys.stderr is not None and not getattr(sys, "frozen", False) and "pythonw" not in exe:
        return None
    try:
        paths.ensure(paths.LOG_DIR)
        path = os.path.join(paths.LOG_DIR, "oddsbreaker.log")
        if os.path.exists(path) and os.path.getsize(path) > 512 * 1024:
            os.replace(path, path + ".old")
        f = open(path, "a", encoding="utf-8", buffering=1)
        import tkinter
        from .store import now_iso
        f.write("\n=== %s %s started %s (Python %s, Tk %s) ===\n" % (
            APP_NAME, __version__, now_iso(), sys.version.split()[0], tkinter.TkVersion))
        sys.stderr = f
        if sys.stdout is None:
            sys.stdout = f
        return path
    except Exception:
        return None


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.data:
        paths.init(args.data)
    setup_logging()
    from .system import SingleInstance, StubPlatform, WinPlatform, set_app_id, set_dpi_awareness
    set_dpi_awareness()
    set_app_id()
    if args.selftest:
        from .selftest import run_selftest
        return run_selftest(args.selftest)
    inst = SingleInstance()
    if inst.already and not args.multi:
        inst.wake_other()
        return 0
    import tkinter as tk
    from .app import App
    root = tk.Tk()
    plat = WinPlatform() if (IS_WIN and not args.stub) else StubPlatform()
    App(root, plat, classic=args.classic)
    root.mainloop()
    return 0


def crash_report(err):
    try:
        paths.ensure(paths.LOG_DIR)
        from .store import now_iso
        with open(os.path.join(paths.LOG_DIR, "crash.log"), "a", encoding="utf-8") as f:
            f.write("\n[%s] %s %s\n%s" % (now_iso(), APP_NAME, __version__, err))
    except Exception:
        pass
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror(APP_NAME, "%s hit a problem and has to close.\n\n%s\n\nA crash report "
                                       "was saved in:\n%s\n\nIf it keeps happening, start it with "
                                       "--classic or report it on GitHub." %
                             (APP_NAME, err[-900:], paths.LOG_DIR))
        r.destroy()
    except Exception:
        print(err)


def run():
    try:
        code = main()
    except SystemExit:
        raise
    except Exception:
        crash_report(traceback.format_exc())
        code = 1
    sys.exit(code or 0)
