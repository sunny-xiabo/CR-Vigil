from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..utils import ROOT
from ..config import load_config
from ..evaluator import load_registry
from .admission import render_admission
from .digest import render_digest
from .trend import render_trend

__all__ = [
    "render_admission",
    "render_digest",
    "render_trend",
    "main",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render CR-Vigil reports.")
    parser.add_argument("report_type", choices=["admission", "digest", "trend"])
    parser.add_argument("--registry", default="data/pr-registry.json")
    parser.add_argument("--pr-id", help="Required for admission reports")
    parser.add_argument("--output-root", default="reports")
    parser.add_argument("--config", default="cr-vigil.yml")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry = load_registry(Path(args.registry))
    output_root = Path(args.output_root)
    config = load_config(Path(args.config))
    try:
        if args.report_type == "admission":
            if not args.pr_id:
                print("ERROR: admission reports require --pr-id", file=sys.stderr)
                return 1
            path = render_admission(registry, args.pr_id, output_root, config=config)
        elif args.report_type == "digest":
            path = render_digest(registry, output_root, config=config)
        else:
            path = render_trend(registry, output_root, config=config)
        print(f"Report rendered: {path}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
