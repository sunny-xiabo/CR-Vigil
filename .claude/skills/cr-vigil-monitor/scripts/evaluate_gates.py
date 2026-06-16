#!/usr/bin/env python3
"""Compatibility wrapper for the CR-Vigil evaluator."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crvigil.evaluator import main


if __name__ == "__main__":
    raise SystemExit(main())
