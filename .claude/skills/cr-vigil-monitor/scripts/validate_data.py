#!/usr/bin/env python3
"""Validate and optionally repair CR-Vigil JSON data files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crvigil.json_tools import JsonRepairError, validate_json_file  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate CR-Vigil JSON files.")
    parser.add_argument("--registry", default="data/pr-registry.json", help="Path to pr-registry.json")
    parser.add_argument("--repair", action="store_true", help="Attempt json_repair/fallback repair if JSON is invalid")
    parser.add_argument("--write", action="store_true", help="Write repaired JSON back to disk")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = validate_json_file(Path(args.registry), repair=args.repair, write=args.write)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except JsonRepairError as exc:
        print(json.dumps({"path": args.registry, "valid": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
