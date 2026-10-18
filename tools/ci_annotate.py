"""Show test failures as GitHub Actions annotations, so they can be read on
the run's summary page without digging through the log.

    python tools/ci_annotate.py junit.xml                   pytest --junitxml report
    python tools/ci_annotate.py --tail selftest.txt TITLE   last lines of a text file
"""

import sys
import xml.etree.ElementTree as ET

MAX_LINES = 45
MAX_CHARS = 4000


def esc_data(s):
    return s.replace("%", "%25").replace("\r", "").replace("\n", "%0A")


def esc_prop(s):
    return esc_data(s).replace(":", "%3A").replace(",", "%2C")


def error(title, text):
    lines = text.strip().splitlines()[-MAX_LINES:]
    body = "\n".join(lines)[-MAX_CHARS:]
    print("::error title=%s::%s" % (esc_prop(title), esc_data(body)))
    sys.stdout.flush()


def from_junit(path):
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as e:
        print("::warning::No test report to read (%s)" % e)
        return 0
    n = 0
    for case in root.iter("testcase"):
        for kind in ("failure", "error"):
            el = case.find(kind)
            if el is None:
                continue
            name = "%s %s" % (case.get("classname", ""), case.get("name", ""))
            error("%s: %s" % (kind, name.strip()), (el.get("message") or "") + "\n" + (el.text or ""))
            n += 1
            if n >= 10:  # GitHub keeps 10 error annotations per step
                return n
    return n


def from_tail(path, title):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            error(title, f.read())
    except OSError as e:
        print("::warning::Couldn't read %s (%s)" % (path, e))


def main(argv):
    if len(argv) >= 2 and argv[0] == "--tail":
        from_tail(argv[1], argv[2] if len(argv) > 2 else argv[1])
    elif argv:
        print("%d failing test(s)" % from_junit(argv[0]))
    else:
        print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
