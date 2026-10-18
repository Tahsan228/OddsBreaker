"""Release housekeeping: the changelog, the version and the packaging agree."""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "packaging"))

from oddsbreaker import APP_NAME, AUTHOR, __version__  # noqa: E402


def test_changelog_has_this_version():
    from release_notes import notes
    text = notes("v" + __version__)
    assert "See the changelog" not in text, "add a ## [%s] section to CHANGELOG.md" % __version__
    assert "%s-%s-Setup.exe" % (APP_NAME, __version__) in text


def test_version_and_credits_in_packaging():
    assert re.match(r"^\d+\.\d+\.\d+$", __version__)
    assert AUTHOR == "Tahsan"
    with open(os.path.join(ROOT, "packaging", "installer.nsi"), encoding="utf-8") as f:
        nsi = f.read()
    assert '!define PUBLISHER "%s"' % AUTHOR in nsi
    with open(os.path.join(ROOT, "LICENSE"), encoding="utf-8") as f:
        assert "Copyright (c) 2026 %s" % AUTHOR in f.read()
