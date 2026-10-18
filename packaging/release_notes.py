"""Print the CHANGELOG section for one version (used as the GitHub release text).

    python packaging/release_notes.py v1.0.0
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOWNLOADS = """
## Download

| File | What it is |
| --- | --- |
| **OddsBreaker-{v}-Setup.exe** | Installer (recommended). Start Menu shortcut, uninstaller, no admin needed. |
| **OddsBreaker-{v}.exe** | The whole app in one file. Just run it. |
| **OddsBreaker-{v}-Portable.zip** | Single file plus `portable.txt`, so your hunts are saved next to the app (USB sticks, shared PCs). |

Windows may say "Windows protected your PC" the first time, because the app isn't code-signed yet.
Click **More info** and then **Run anyway**. `SHA256SUMS.txt` lets you check the downloads.
"""


def notes(version):
    v = version.lstrip("v")
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
        text = f.read()
    parts = re.split(r"(?m)^## ", text)
    body = ""
    for part in parts[1:]:
        head, _, rest = part.partition("\n")
        if re.match(r"\[?v?%s\]?\b" % re.escape(v), head.strip()):
            body = rest.strip()
            break
    if not body:
        body = "See the changelog for details."
    return body + "\n" + DOWNLOADS.format(v=v)


if __name__ == "__main__":
    sys.stdout.write(notes(sys.argv[1] if len(sys.argv) > 1 else ""))
