"""CR-Vigil configuration loading.

The project intentionally avoids runtime dependencies, so this module supports
the small YAML subset used by `cr-vigil.yml`: nested mappings with scalar
strings, booleans, integers, and floats.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import ROOT


DEFAULT_CONFIG: dict[str, Any] = {
    "storage": {
        "history_limit_per_mr": 50,
        "daily_snapshot_retention_days": 30,
        "weekly_snapshot_retention_weeks": 12,
    },
    "sync": {
        "push_retry": 1,
    },
    "reports": {
        "admission": {
            "profile": "detailed",
            "sections": {"gate_details": True, "risk_analysis": True, "recommendations": True},
        },
        "daily": {
            "profile": "standard",
            "sections": {
                "summary": True,
                "admitted_prs": True,
                "blocked_prs": True,
                "pending_prs": False,
                "gate_distribution": True,
                "detailed_gate_reasons": False,
                "action_items": True,
            },
        },
        "weekly": {
            "profile": "standard",
            "sections": {
                "summary": True,
                "admission_trend": True,
                "gate_trend": True,
                "ai_usage": True,
                "reviewer_stats": True,
                "recurrence": True,
                "recommendations": True,
            },
        },
    }
}


def parse_scalar(value: str) -> Any:
    value = value.strip()
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def parse_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value == "":
            node: dict[str, Any] = {}
            parent[key] = node
            stack.append((indent, node))
        else:
            parent[key] = parse_scalar(value)
    return root


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or (ROOT / "cr-vigil.yml")
    if not config_path.exists():
        return DEFAULT_CONFIG
    parsed = parse_simple_yaml(config_path.read_text(encoding="utf-8"))
    return deep_merge(DEFAULT_CONFIG, parsed)


def report_profile(config: dict[str, Any], report_type: str) -> str:
    return str(config.get("reports", {}).get(report_type, {}).get("profile", "standard"))


def section_enabled(config: dict[str, Any], report_type: str, section: str, default: bool = True) -> bool:
    return bool(config.get("reports", {}).get(report_type, {}).get("sections", {}).get(section, default))


def storage_int(config: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(config.get("storage", {}).get(key, default))
    except (TypeError, ValueError):
        return default


def sync_int(config: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(config.get("sync", {}).get(key, default))
    except (TypeError, ValueError):
        return default
