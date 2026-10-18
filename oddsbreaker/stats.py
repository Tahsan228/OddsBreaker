"""Odds maths and number formatting."""

import datetime
import math


def fmt_int(n):
    return "{:,}".format(int(n))


def fmt_time(sec):
    sec = int(max(0, sec))
    return "%d:%02d:%02d" % (sec // 3600, (sec % 3600) // 60, sec % 60)


def fmt_dur(sec):
    """Short human duration: 45S, 12M, 6H 12M, 3D 4H."""
    sec = int(max(0, sec))
    if sec < 60:
        return "%dS" % sec
    if sec < 3600:
        return "%dM" % (sec // 60)
    if sec < 86400:
        h, m = sec // 3600, (sec % 3600) // 60
        return "%dH %dM" % (h, m) if m else "%dH" % h
    d, h = sec // 86400, (sec % 86400) // 3600
    return "%dD %dH" % (d, h) if h else "%dD" % d


def chance(n, odds):
    """Chance of at least one shiny in n tries at 1/odds."""
    if odds <= 1:
        return 1.0
    return 1.0 - math.exp(n * math.log1p(-1.0 / odds))


def resets_for(p, odds):
    """Tries needed to reach probability p of at least one shiny."""
    if odds <= 1 or p <= 0:
        return 0
    return int(math.ceil(math.log1p(-min(p, 0.999999)) / math.log1p(-1.0 / odds)))


def luck(n, odds):
    """Found after n tries: share of hunters (0..1) who would need longer."""
    if odds <= 1:
        return 0.0
    return math.exp(n * math.log1p(-1.0 / odds))


def rate(count, seconds):
    if seconds < 20 or count <= 0:
        return None
    return count * 3600.0 / seconds


def eta(now_count, target_count, per_hour):
    """Seconds until target_count at per_hour, or None."""
    if not per_hour or target_count <= now_count:
        return 0 if target_count <= now_count else None
    return (target_count - now_count) / per_hour * 3600.0


def daily_series(p, days=14, end=None):
    """[(date, count)] for the last `days` days, oldest first."""
    end = end or datetime.date.today()
    d = p.get("daily") or {}
    out = []
    for i in range(days - 1, -1, -1):
        day = (end - datetime.timedelta(days=i)).isoformat()
        out.append((day, int(d.get(day, 0))))
    return out


def hunt_rate(p, session_count=0, session_time=0.0):
    """Best guess at resets per hour for a hunt."""
    r = rate(session_count, session_time)
    if r:
        return r
    if p.get("loop_avg"):
        return 3600.0 / max(0.5, p["loop_avg"])
    return rate(p.get("encounters", 0), p.get("seconds", 0))
