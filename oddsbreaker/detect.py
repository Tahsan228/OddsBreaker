"""Shiny detection: compare the watch area to saved normal frames, or look for
shiny-only colours."""

import base64

GRID_MAX = 64


def default_detect():
    return {"mode": "compare", "region": None, "relative": True, "refs": [],
            "pixel_tol": 40, "threshold": 15.0, "colors": [], "color_tol": 28,
            "color_pct": 3.0, "fps": 12}


def grid_dims(w, h):
    return min(w, GRID_MAX), min(h, GRID_MAX)


def grid_sample(frame):
    """Sample an evenly spaced grid of pixels as RGB bytes."""
    w, h, b = frame.w, frame.h, frame.bgra
    gw, gh = grid_dims(w, h)
    out = bytearray(gw * gh * 3)
    xs = [int((i + 0.5) * w / gw) * 4 for i in range(gw)]
    o = 0
    for j in range(gh):
        row = int((j + 0.5) * h / gh) * w * 4
        for xo in xs:
            i = row + xo
            out[o] = b[i + 2]
            out[o + 1] = b[i + 1]
            out[o + 2] = b[i]
            o += 3
    return bytes(out)


def diff_pct(a, b, tol):
    """% of grid pixels whose colour differs by more than tol on any channel."""
    n = len(a) // 3
    bad = 0
    for i in range(0, len(a), 3):
        if (abs(a[i] - b[i]) > tol or abs(a[i + 1] - b[i + 1]) > tol
                or abs(a[i + 2] - b[i + 2]) > tol):
            bad += 1
    return 100.0 * bad / max(1, n)


def color_pct(a, colors, tol):
    """% of grid pixels that match any of the target colours."""
    n = len(a) // 3
    hit = 0
    for i in range(0, len(a), 3):
        r, g, b = a[i], a[i + 1], a[i + 2]
        for (cr, cg, cb) in colors:
            if abs(r - cr) <= tol and abs(g - cg) <= tol and abs(b - cb) <= tol:
                hit += 1
                break
    return 100.0 * hit / max(1, n)


def make_ref(frame):
    gw, gh = grid_dims(frame.w, frame.h)
    return {"w": frame.w, "h": frame.h, "gw": gw, "gh": gh,
            "data": base64.b64encode(grid_sample(frame)).decode("ascii")}


def matching_refs(det):
    """Saved normal frames that fit the current watch area."""
    reg = det.get("region")
    if not reg:
        return []
    return [r for r in det.get("refs", []) if r.get("w") == reg[2] and r.get("h") == reg[3]]


def usable_refs(det):
    out = []
    for r in matching_refs(det):
        try:
            out.append(base64.b64decode(r["data"]))
        except Exception:
            pass
    return out


def score_frame(frame, det, refs_raw):
    s = grid_sample(frame)
    if det["mode"] == "color":
        return color_pct(s, det["colors"], det["color_tol"])
    best = 100.0
    for ref in refs_raw:
        if len(ref) == len(s):
            best = min(best, diff_pct(s, ref, det["pixel_tol"]))
    return best


def is_shiny_score(det, score):
    if det["mode"] == "color":
        return score >= det["color_pct"]
    return score > det["threshold"]


def suggest_threshold(det, normal_scores):
    """A safe red-line position from the scores of recent normal encounters.
    Returns None until there are enough of them."""
    scores = [s for s in normal_scores if s is not None]
    if len(scores) < 5:
        return None
    top = max(scores)
    if det["mode"] == "color":
        return round(min(30.0, max(1.0, top * 1.5 + 1.5)) * 2) / 2.0
    return round(min(60.0, max(5.0, top * 1.5 + 3.0)) * 2) / 2.0
