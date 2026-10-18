"""Hunt scripts: the list of steps OddsBreaker plays over and over.

Text form, one step per line:
    press A x5 gap 0.8 hold 0.1     tap a button (or A+B+START together)
    hold UP 1.5                     keep a button down
    wait 2   /   wait 1~2.5         pause (a range = random wait)
    check 5                         look for the shiny for up to 5 seconds
    # note                          a comment
"""

import re

from .config import BUTTONS, TEMPLATES, key_label, norm_key


class SeqError(ValueError):
    pass


DEF_GAP, DEF_HOLD = 0.25, 0.08


def fmt_num(v):
    s = ("%.2f" % float(v)).rstrip("0").rstrip(".")
    return s or "0"


def parse_time(tok):
    try:
        v = float(tok.lower().rstrip("s"))
    except ValueError:
        raise SeqError('"%s" is not a number of seconds' % tok)
    if v < 0 or v > 600:
        raise SeqError("time must be between 0 and 600 seconds")
    return v


def parse_range(tok):
    m = re.match(r"^([\d.]+)s?\s*[~-]\s*([\d.]+)s?$", tok)
    if m:
        lo, hi = parse_time(m.group(1)), parse_time(m.group(2))
        return min(lo, hi), max(lo, hi)
    v = parse_time(tok)
    return v, v


def norm_combo(combo):
    """Validate "a+B+start" -> "A+B+START" (raw keys become key:name)."""
    out = []
    for part in (combo or "").split("+"):
        part = part.strip()
        if not part:
            raise SeqError('bad button combo "%s"' % combo)
        up = part.upper()
        if up in BUTTONS:
            tok = up
        elif part.lower().startswith("key:"):
            k = norm_key(part[4:])
            if not k:
                raise SeqError('unknown key "%s"' % part[4:])
            tok = "key:" + k
        else:
            k = norm_key(part)
            if not k:
                raise SeqError('unknown button "%s"' % part)
            tok = "key:" + k
        if tok not in out:
            out.append(tok)
    return "+".join(out)


def combo_label(combo):
    out = []
    for tok in (combo or "").split("+"):
        out.append(key_label(tok[4:]) if tok.startswith("key:") else tok)
    return "+".join(out)


def parse_script(text):
    """Text -> (rows, errors). Full-line comments become NOTE rows."""
    rows, errors = [], []
    for ln, raw in enumerate((text or "").splitlines(), 1):
        s = raw.strip()
        if not s:
            continue
        if s.startswith("#"):
            note = s.lstrip("#").strip()
            if note:
                rows.append({"op": "note", "text": note[:48]})
            continue
        line = s.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        cmd, args = parts[0].lower(), parts[1:]
        try:
            if cmd in ("press", "tap"):
                if not args:
                    raise SeqError('press needs a button, like "press A"')
                btn = norm_combo(args[0])
                times, gap, hold = 1, DEF_GAP, DEF_HOLD
                i = 1
                while i < len(args):
                    a = args[i].lower()
                    if re.match(r"^x\d+$", a):
                        times = int(a[1:])
                        if not 1 <= times <= 500:
                            raise SeqError("repeat count must be 1-500")
                    elif a in ("gap", "every", "hold"):
                        if i + 1 >= len(args):
                            raise SeqError("%s needs a number of seconds" % a)
                        v = parse_time(args[i + 1])
                        i += 1
                        if a == "hold":
                            hold = v
                        else:
                            gap = v
                    else:
                        gap = parse_time(a)
                    i += 1
                rows.append({"op": "press", "btn": btn, "times": times, "gap": gap, "hold": hold})
            elif cmd == "hold":
                if len(args) < 2:
                    raise SeqError('hold needs a button and seconds, like "hold UP 1.5"')
                rows.append({"op": "hold", "btn": norm_combo(args[0]), "dur": parse_time(args[1])})
            elif cmd in ("wait", "sleep"):
                if not args:
                    raise SeqError('wait needs seconds, like "wait 2" or "wait 1~3"')
                lo, hi = parse_range("".join(args))
                rows.append({"op": "wait", "lo": lo, "hi": hi})
            elif cmd in ("check", "watch"):
                dur = parse_time(args[0]) if args else 4.0
                rows.append({"op": "check", "dur": max(0.2, dur)})
            else:
                raise SeqError('unknown command "%s" (use press, hold, wait, check)' % cmd)
        except SeqError as e:
            errors.append("Line %d: %s" % (ln, e))
    return rows, errors


def row_to_text(r):
    op = r.get("op")
    if op == "note":
        return "# " + r.get("text", "")
    if op == "press":
        s = "press " + r["btn"]
        if r.get("times", 1) > 1:
            s += " x%d" % r["times"]
        if r.get("times", 1) > 1 or abs(r.get("gap", DEF_GAP) - DEF_GAP) > 1e-9:
            s += " gap " + fmt_num(r.get("gap", DEF_GAP))
        if abs(r.get("hold", DEF_HOLD) - DEF_HOLD) > 1e-9:
            s += " hold " + fmt_num(r["hold"])
        return s
    if op == "hold":
        return "hold %s %s" % (r["btn"], fmt_num(r["dur"]))
    if op == "wait":
        if abs(r["lo"] - r["hi"]) < 1e-9:
            return "wait " + fmt_num(r["lo"])
        return "wait %s~%s" % (fmt_num(r["lo"]), fmt_num(r["hi"]))
    if op == "check":
        return "check " + fmt_num(r["dur"])
    return ""


def script_to_text(rows):
    return "\n".join(row_to_text(r) for r in rows) + "\n"


def resolve_btn(combo, km):
    keys = []
    for tok in combo.split("+"):
        if tok.startswith("key:"):
            sub = [norm_key(tok[4:])]
        else:
            mapped = km.get(tok.upper(), "")
            if not mapped:
                raise SeqError("%s has no key yet (KEYS page)" % tok.upper())
            sub = [norm_key(m) for m in mapped.split("+")]
            if None in sub:
                raise SeqError('%s uses an unknown key "%s"' % (tok, mapped))
        for k in sub:
            if k and k not in keys:
                keys.append(k)
    if not keys:
        raise SeqError("no keys to press")
    return keys


def compile_script(rows, keymap):
    """Script rows + key map -> (runnable steps, errors)."""
    km = dict((k.upper(), (v or "").strip().lower()) for k, v in (keymap or {}).items())
    steps, errors = [], []
    for i, r in enumerate(rows or [], 1):
        op = r.get("op")
        try:
            if op == "press":
                steps.append({"op": "press", "keys": resolve_btn(r["btn"], km),
                              "times": max(1, int(r["times"])), "gap": max(0.0, float(r["gap"])),
                              "hold": max(0.0, float(r["hold"])), "row": i})
            elif op == "hold":
                steps.append({"op": "hold", "keys": resolve_btn(r["btn"], km),
                              "dur": max(0.0, float(r["dur"])), "row": i})
            elif op == "wait":
                lo, hi = float(r["lo"]), float(r["hi"])
                steps.append({"op": "wait", "lo": min(lo, hi), "hi": max(lo, hi), "row": i})
            elif op == "check":
                steps.append({"op": "check", "dur": max(0.2, float(r["dur"])), "row": i})
        except SeqError as e:
            errors.append("Step %d: %s" % (i, e))
        except (KeyError, TypeError, ValueError):
            errors.append("Step %d is broken" % i)
    return steps, errors


def estimate_loop(rows):
    """Rough seconds per loop (checks usually end early on a normal one)."""
    t = 0.0
    for r in rows or []:
        op = r.get("op")
        if op == "press":
            t += r["times"] * (r["hold"] + r["gap"] + 0.02)
        elif op == "hold":
            t += r["dur"] + 0.02
        elif op == "wait":
            t += (r["lo"] + r["hi"]) / 2.0
        elif op == "check":
            t += r["dur"] * 0.6
    return t


def template_rows(name):
    for n, text in TEMPLATES:
        if n == name:
            return parse_script(text)[0]
    return parse_script(TEMPLATES[0][1])[0]


def keys_used(rows, keymap):
    """Every keyboard key the script would press (for hotkey clash warnings)."""
    steps, _errs = compile_script(rows, keymap)
    out = set()
    for s in steps:
        out.update(s.get("keys", []))
    return out
