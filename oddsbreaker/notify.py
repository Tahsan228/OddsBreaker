"""Telling the outside world: Discord and phone (ntfy) alerts, text files for
OBS stream overlays, and the update check."""

import json
import os
import re
import threading
import urllib.request
import uuid

from . import APP_NAME, LATEST_API, REPO, __version__, paths

AVATAR_URL = "https://raw.githubusercontent.com/%s/main/assets/icon-256.png" % REPO


def _ascii(s):
    return re.sub(r"[^\x20-\x7e]", "", s or "")


def _request(url, data=None, headers=None, method=None, timeout=15):
    h = {"User-Agent": "%s/%s" % (APP_NAME, __version__)}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def multipart(fields, files):
    """Build a multipart/form-data body. files: {name: (filename, bytes, type)}"""
    boundary = "----OddsBreaker" + uuid.uuid4().hex
    out = bytearray()
    for name, value in fields.items():
        out += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n" % (boundary, name)).encode()
        out += value.encode("utf-8") + b"\r\n"
    for name, (fname, blob, ctype) in files.items():
        out += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                "Content-Type: %s\r\n\r\n" % (boundary, name, fname, ctype)).encode()
        out += blob + b"\r\n"
    out += ("--%s--\r\n" % boundary).encode()
    return bytes(out), "multipart/form-data; boundary=%s" % boundary


def valid_discord_url(url):
    return bool(re.match(r"^https://([a-z]+\.)?discord(app)?\.com/api/webhooks/\d+/[\w-]+", url or ""))


def discord_send(url, title, text, color=0xFFD93B, image_png=None):
    embed = {"title": title, "description": text, "color": color,
             "footer": {"text": "%s %s" % (APP_NAME, __version__)}}
    payload = {"username": APP_NAME, "avatar_url": AVATAR_URL, "embeds": [embed]}
    if image_png:
        embed["image"] = {"url": "attachment://shiny.png"}
        body, ctype = multipart({"payload_json": json.dumps(payload)},
                                {"files[0]": ("shiny.png", image_png, "image/png")})
    else:
        body, ctype = json.dumps(payload).encode("utf-8"), "application/json"
    status, _ = _request(url, body, {"Content-Type": ctype}, "POST")
    return 200 <= status < 300


def ntfy_url(topic):
    t = (topic or "").strip()
    if not t:
        return None
    if t.startswith("http://") or t.startswith("https://"):
        return t
    if not re.match(r"^[\w-]{1,64}$", t):
        return None
    return "https://ntfy.sh/" + t


def ntfy_send(topic, title, text, image_png=None, priority="high"):
    url = ntfy_url(topic)
    if not url:
        raise ValueError("bad ntfy topic")
    headers = {"Title": _ascii(title), "Tags": "sparkles", "Priority": priority}
    if image_png:
        headers["Filename"] = "shiny.png"
        headers["Message"] = _ascii(text)
        status, _ = _request(url, image_png, headers, "PUT")
    else:
        status, _ = _request(url, _ascii(text).encode("utf-8"), headers, "POST")
    return 200 <= status < 300


class Notifier(object):
    """Sends alerts in the background; results come back on the app queue as
    (None, "notify_result", channel, ok, detail)."""

    def __init__(self, q):
        self.q = q

    def send(self, settings, title, text, image_png=None, color=0xFFD93B, only=None):
        jobs = []
        url = (settings.get("discord") or "").strip()
        if url and only in (None, "discord"):
            shot = image_png if settings.get("discord_shot", True) else None
            jobs.append(("discord", lambda: discord_send(url, title, text, color, shot)))
        topic = (settings.get("ntfy") or "").strip()
        if topic and only in (None, "ntfy"):
            jobs.append(("ntfy", lambda: ntfy_send(topic, title, text, image_png)))
        for name, fn in jobs:
            t = threading.Thread(target=self._run, args=(name, fn), name="notify")
            t.daemon = True
            t.start()
        return len(jobs)

    def _run(self, name, fn):
        try:
            ok = fn()
            self.q.put((None, "notify_result", name, bool(ok), ""))
        except Exception as e:
            self.q.put((None, "notify_result", name, False, str(e)[:120]))


class StreamFiles(object):
    """Plain text files an OBS "Text (GDI+)" source can read from file."""

    def __init__(self):
        self.last = {}

    def folder(self):
        return paths.OBS_DIR

    def update(self, values):
        try:
            paths.ensure(paths.OBS_DIR)
            for name, text in values.items():
                if self.last.get(name) == text:
                    continue
                path = os.path.join(paths.OBS_DIR, name + ".txt")
                with open(path + ".tmp", "w", encoding="utf-8") as f:
                    f.write(text)
                os.replace(path + ".tmp", path)
                self.last[name] = text
            return True
        except Exception:
            return False

    def write_image(self, name, png):
        try:
            paths.ensure(paths.OBS_DIR)
            path = os.path.join(paths.OBS_DIR, name)
            with open(path + ".tmp", "wb") as f:
                f.write(png)
            os.replace(path + ".tmp", path)
        except Exception:
            pass


def parse_version(s):
    nums = re.findall(r"\d+", s or "")
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - len(nums[:3]))


def check_for_update(q, timeout=8):
    """Ask GitHub for the newest release in the background. Posts
    (None, "update", tag, page_url) when it is newer than this version."""

    def run():
        try:
            status, body = _request(LATEST_API, headers={"Accept": "application/vnd.github+json"},
                                    timeout=timeout)
            info = json.loads(body.decode("utf-8"))
            tag = info.get("tag_name") or ""
            if parse_version(tag) > parse_version(__version__) and not info.get("draft"):
                q.put((None, "update", tag, info.get("html_url") or ""))
            else:
                q.put((None, "update_none", tag))
        except Exception as e:
            q.put((None, "update_fail", str(e)[:120]))

    t = threading.Thread(target=run, name="update-check")
    t.daemon = True
    t.start()
    return t
