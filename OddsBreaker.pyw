#!/usr/bin/env python3
"""Run OddsBreaker from the source code (double-click on Windows)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oddsbreaker.main import run  # noqa: E402

if __name__ == "__main__":
    run()
