"""Storage helpers for CR-Vigil registry and per-MR records."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .json_tools import load_json_file, save_json_file
from .utils import ROOT


def workspace_root_for_registry(registry_path: Path) -> Path:
    if registry_path.parent.name == "data":
        return registry_path.parent.parent
    return registry_path.parent


def safe_record_name(pr_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", pr_id.strip())
    return safe.strip("-") or "unknown-pr"


def mrs_dir(root: Path = ROOT) -> Path:
    return root / "data" / "mrs"


def mr_record_path(pr_id: str, root: Path = ROOT) -> Path:
    return mrs_dir(root) / f"{safe_record_name(pr_id)}.json"


def relative_record_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def attach_record_path(pr: dict[str, Any], root: Path) -> dict[str, Any]:
    pr_id = str(pr.get("pr_id") or "")
    if not pr_id:
        return pr
    path = mr_record_path(pr_id, root=root)
    pr["record_path"] = relative_record_path(path, root)
    return pr


def write_mr_record(pr: dict[str, Any], root: Path = ROOT) -> Path:
    pr = attach_record_path(dict(pr), root)
    path = mr_record_path(str(pr.get("pr_id") or ""), root=root)
    save_json_file(path, pr)
    return path


def write_mr_records(registry: dict[str, Any], root: Path = ROOT) -> list[Path]:
    paths = []
    for pr in registry.get("prs", []):
        if pr.get("pr_id"):
            attach_record_path(pr, root)
            paths.append(write_mr_record(pr, root=root))
    return paths


def registry_index_pr(pr: dict[str, Any], root: Path) -> dict[str, Any]:
    attach_record_path(pr, root)
    return {
        "pr_id": pr.get("pr_id"),
        "title": pr.get("title", ""),
        "author": pr.get("author", ""),
        "status": pr.get("status", ""),
        "url": pr.get("url", ""),
        "verdict": pr.get("verdict", "PENDING"),
        "gates_summary": pr.get("gates_summary", {}),
        "blocking_reasons_count": len(pr.get("blocking_reasons", [])),
        "last_updated": pr.get("last_updated", ""),
        "record_path": pr.get("record_path", ""),
    }


def registry_index(registry: dict[str, Any], root: Path) -> dict[str, Any]:
    return {
        "updated_at": registry.get("updated_at", ""),
        "storage_version": 2,
        "storage_mode": "index",
        "prs": [registry_index_pr(pr, root) for pr in registry.get("prs", []) if pr.get("pr_id")],
    }


def load_mr_record(entry: dict[str, Any], root: Path) -> dict[str, Any]:
    record_path = entry.get("record_path")
    path = root / record_path if record_path else mr_record_path(str(entry.get("pr_id") or ""), root=root)
    if path.exists():
        data, _ = load_json_file(path, repair=True)
        if isinstance(data, dict):
            attach_record_path(data, root)
            return data
    return attach_record_path(dict(entry), root)


def hydrate_registry(registry: dict[str, Any], root: Path) -> dict[str, Any]:
    hydrated = dict(registry)
    hydrated["prs"] = [load_mr_record(pr, root) for pr in registry.get("prs", [])]
    return hydrated


def load_registry_with_records(path: Path) -> dict[str, Any]:
    registry, _ = load_json_file(path, repair=True)
    return hydrate_registry(registry, workspace_root_for_registry(path))


def save_registry_index(path: Path, registry: dict[str, Any]) -> None:
    root = workspace_root_for_registry(path)
    write_mr_records(registry, root=root)
    save_json_file(path, registry_index(registry, root))
