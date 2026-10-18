import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Never touch a real data folder while testing.
os.environ["ODDSBREAKER_DATA"] = tempfile.mkdtemp(prefix="oddsbreaker-tests-")

from oddsbreaker import paths  # noqa: E402

paths.init()
