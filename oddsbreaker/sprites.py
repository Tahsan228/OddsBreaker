"""Pokemon sprites, downloaded once from the PokeAPI sprite collection and
cached in the data folder. Nothing is bundled with the app."""

import os
import threading
import urllib.error
import urllib.request

from . import APP_NAME, __version__, paths
from .dexnames import dex_no
from .imaging import crop_frames, gif_decode, load_png_bitmap

BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/"


def http_get(url, timeout=10, headers=None):
    h = {"User-Agent": "%s/%s" % (APP_NAME, __version__)}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    return urllib.request.urlopen(req, timeout=timeout).read()


class SpriteCache(object):
    """Static sprites (PNG) and Gen 5 style moving sprites (GIF).

    lookup() and anim() return at once; missing sprites download in the
    background and a (None, "sprite", dex_no) message arrives on the queue
    when they are ready.
    """
    URL = BASE + "%s%d.png"
    ANIM_URLS = (
        BASE + "versions/generation-v/black-white/animated/%s%d.gif",
        BASE + "other/showdown/%s%d.gif",
    )

    def __init__(self, q):
        self.q = q
        self.mem = {}
        self.pending = set()
        self.failed = set()
        self.anim_mem = {}
        self.anim_pending = set()
        self.anim_failed = set()

    dex_no = staticmethod(dex_no)

    @staticmethod
    def paths(pid):
        return (os.path.join(paths.SPRITE_DIR, "%d.png" % pid),
                os.path.join(paths.SPRITE_DIR, "%d_shiny.png" % pid))

    @staticmethod
    def anim_path(pid, shiny):
        return os.path.join(paths.SPRITE_DIR, "anim", "%d%s.gif" % (pid, "_shiny" if shiny else ""))

    # -- still sprites -------------------------------------------------------
    def lookup(self, name):
        """(dex_no, normal_bitmap, shiny_bitmap) when ready, else None."""
        pid = dex_no(name)
        if not pid:
            return None
        if pid in self.mem:
            nb, sb = self.mem[pid]
            return pid, nb, sb
        pn, ps = self.paths(pid)
        if os.path.exists(pn) and os.path.exists(ps):
            try:
                with open(pn, "rb") as f:
                    nb = load_png_bitmap(f.read())
                with open(ps, "rb") as f:
                    sb = load_png_bitmap(f.read())
                self.mem[pid] = (nb, sb)
                return pid, nb, sb
            except Exception:
                for path in (pn, ps):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
        if pid not in self.pending and pid not in self.failed:
            self.pending.add(pid)
            t = threading.Thread(target=self._fetch, args=(pid,), name="sprite")
            t.daemon = True
            t.start()
        return None

    def loading(self, name):
        pid = dex_no(name)
        return bool(pid) and (pid in self.pending or pid in self.anim_pending)

    def _fetch(self, pid):
        try:
            paths.ensure(paths.SPRITE_DIR)
            for shiny, path in zip(("", "shiny/"), self.paths(pid)):
                if not os.path.exists(path):
                    blob = http_get(self.URL % (shiny, pid))
                    with open(path + ".part", "wb") as f:
                        f.write(blob)
                    os.replace(path + ".part", path)
            self.q.put((None, "sprite", pid))
        except Exception as e:
            self.failed.add(pid)
            self.q.put((None, "sprite_fail", pid, str(e)))
        finally:
            self.pending.discard(pid)

    # -- moving sprites ------------------------------------------------------
    def anim(self, pid, shiny):
        """Moving sprite as [(Bitmap, delay_ms), ...], or None if not ready."""
        key = (pid, bool(shiny))
        if key in self.anim_mem:
            return self.anim_mem[key] or None
        if key not in self.anim_pending and key not in self.anim_failed:
            self.anim_pending.add(key)
            t = threading.Thread(target=self._fetch_anim, args=key, name="sprite-anim")
            t.daemon = True
            t.start()
        return None

    def _fetch_anim(self, pid, shiny):
        key = (pid, shiny)
        try:
            path = self.anim_path(pid, shiny)
            paths.ensure(os.path.dirname(path))
            if os.path.exists(path + ".none"):
                self.anim_mem[key] = []
                return
            if not os.path.exists(path):
                blob, missing = None, 0
                for url in self.ANIM_URLS:
                    try:
                        blob = http_get(url % ("shiny/" if shiny else "", pid))
                        if blob[:3] == b"GIF":
                            break
                        blob = None
                    except urllib.error.HTTPError as e:
                        if e.code != 404:
                            raise
                        missing += 1
                if blob is None:
                    if missing == len(self.ANIM_URLS):
                        open(path + ".none", "w").close()
                    self.anim_mem[key] = []
                    return
                with open(path + ".part", "wb") as f:
                    f.write(blob)
                os.replace(path + ".part", path)
            with open(path, "rb") as f:
                _w, _h, frames = gif_decode(f.read())
            self.anim_mem[key] = crop_frames(frames) if frames else []
            self.q.put((None, "sprite", pid))
        except Exception:
            self.anim_failed.add(key)
        finally:
            self.anim_pending.discard(key)
