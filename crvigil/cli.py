"""Command line interface for CR-Vigil."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .utils import ROOT
from .json_tools import validate_json_file
from .workflow import admit, admit_file, declare, digest, emit, evaluate_one, trend


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m crvigil", description="CR-Vigil unified Python entrypoint.")
    parser.add_argument("--registry", default=str(ROOT / "data" / "pr-registry.json"))
    parser.add_argument("--output-root", default=str(ROOT / "reports"))
    parser.add_argument("--config", default=str(ROOT / "cr-vigil.yml"), help="Path to report configuration")
    parser.add_argument("--no-sync", action="store_true", help="Skip git pull/push even in team mode")

    subparsers = parser.add_subparsers(dest="command", required=True)
    admit_parser = subparsers.add_parser("admit", help="Collect, evaluate, and render one MR admission report")
    add_common_options(admit_parser)
    admit_parser.add_argument("mr_url")

    admit_file_parser = subparsers.add_parser("admit-file", help="Evaluate and render admission reports from a markdown file")
    add_common_options(admit_file_parser)
    admit_file_parser.add_argument("file_path")

    evaluate_parser = subparsers.add_parser("evaluate", help="Evaluate one PR already present in the registry")
    add_common_options(evaluate_parser)
    evaluate_parser.add_argument("--pr-id", required=True)
    evaluate_parser.add_argument("--write", action="store_true")

    digest_parser = subparsers.add_parser("digest", help="Evaluate open PRs and render daily digest")
    add_common_options(digest_parser)
    trend_parser = subparsers.add_parser("trend", help="Render weekly trend report")
    add_common_options(trend_parser)

    validate_parser = subparsers.add_parser("validate", help="Validate registry JSON")
    add_common_options(validate_parser)
    validate_parser.add_argument("--repair", action="store_true")
    validate_parser.add_argument("--write", action="store_true")

    declare_parser = subparsers.add_parser("declare", help="Generate pre-filled declaration template for a MR")
    add_common_options(declare_parser)
    declare_parser.add_argument("mr_url")
    return parser


def add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--registry", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    parser.add_argument("--output-root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    parser.add_argument("--config", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    parser.add_argument("--no-sync", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry_path = Path(args.registry)
    output_root = Path(args.output_root)
    config_path = Path(args.config)
    try:
        if args.command == "admit":
            result = admit(args.mr_url, registry_path, output_root, no_sync=args.no_sync, config_path=config_path)
        elif args.command == "admit-file":
            result = admit_file(Path(args.file_path), registry_path, output_root, no_sync=args.no_sync, config_path=config_path)
        elif args.command == "evaluate":
            result = evaluate_one(registry_path, args.pr_id, write=args.write, config=load_cli_config(config_path))
        elif args.command == "digest":
            result = digest(registry_path, output_root, no_sync=args.no_sync, config_path=config_path)
        elif args.command == "trend":
            result = trend(registry_path, output_root, no_sync=args.no_sync, config_path=config_path)
        elif args.command == "validate":
            result = validate_json_file(registry_path, repair=args.repair, write=args.write)
        elif args.command == "declare":
            result = declare(args.mr_url)
        else:  # pragma: no cover
            raise ValueError(f"未知命令: {args.command}")
        print(emit(result) if isinstance(result, dict) else json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "command": args.command, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


def load_cli_config(config_path: Path) -> dict:
    from .config import load_config

    return load_config(config_path)
