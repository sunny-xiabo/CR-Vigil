#!/usr/bin/env python3
"""Compatibility imports for CR-Vigil JSON helpers."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crvigil.json_tools import *  # noqa: F401,F403
