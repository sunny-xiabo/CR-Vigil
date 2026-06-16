from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SOURCE_ROOT = Path(__file__).resolve().parents[1]


def _resolve_root() -> Path:
    env = os.environ.get("CRVIGIL_ROOT")
    if env:
        return Path(env).resolve()
    cwd = Path.cwd()
    if (cwd / "cr-vigil.yml").exists() or (cwd / "data" / "pr-registry.json").exists():
        return cwd
    if (_SOURCE_ROOT / "cr-vigil.yml").exists():
        return _SOURCE_ROOT
    return cwd


ROOT = _resolve_root()


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def number(value: Any, default: float = 0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def integer(value: Any, default: int = 0) -> int:
    try:
        return int(number(value, default))
    except (TypeError, ValueError):
        return default


def pass_fail(condition: bool) -> str:
    return "PASS" if condition else "FAIL"


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
