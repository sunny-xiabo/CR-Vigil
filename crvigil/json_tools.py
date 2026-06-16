#!/usr/bin/env python3
"""JSON validation and repair helpers for CR-Vigil data files."""

from __future__ import annotations

import json
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None


class JsonRepairError(ValueError):
    """Raised when a JSON file cannot be parsed or repaired."""


def strip_json_noise(text: str) -> str:
    return text.lstrip("\ufeff").strip()


def fallback_repair(text: str) -> str:
    """Repair a small set of common hand-editing JSON mistakes.

    This fallback is intentionally conservative. Full repair is delegated to
    the optional third-party `json_repair` package when it is installed.
    """

    repaired = strip_json_noise(text)
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    return repaired


def repair_json_text(text: str) -> str:
    try:
        from json_repair import repair_json  # type: ignore

        repaired = repair_json(text)
        if isinstance(repaired, str):
            return repaired
        return json.dumps(repaired, ensure_ascii=False)
    except Exception:
        return fallback_repair(text)


def parse_json_text(text: str, *, repair: bool = True) -> tuple[Any, bool]:
    cleaned = strip_json_noise(text)
    try:
        return json.loads(cleaned), False
    except json.JSONDecodeError as first_error:
        if not repair:
            raise JsonRepairError(str(first_error)) from first_error
        repaired_text = repair_json_text(cleaned)
        try:
            return json.loads(repaired_text), True
        except json.JSONDecodeError as second_error:
            raise JsonRepairError(
                f"JSON 格式无效，自动修复失败：{second_error.msg} (line {second_error.lineno}, column {second_error.colno})"
            ) from second_error


def load_json_file(path: Path, *, repair: bool = True) -> tuple[Any, bool]:
    text = path.read_text(encoding="utf-8")
    return parse_json_text(text, repair=repair)


def save_json_file(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as handle:
        temp_path = Path(handle.name)
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temp_path.replace(path)


@contextmanager
def json_file_lock(path: Path):
    """Lock a JSON file's sibling lockfile for read-modify-write sequences."""

    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.parent / f".{path.name}.lock"
    with lock_path.open("w", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def validate_json_file(path: Path, *, repair: bool = False, write: bool = False) -> dict[str, Any]:
    with json_file_lock(path):
        data, repaired = load_json_file(path, repair=repair)
        if write and repaired:
            save_json_file(path, data)
    return {
        "path": str(path),
        "valid": True,
        "repaired": repaired,
        "written": bool(write and repaired),
    }
