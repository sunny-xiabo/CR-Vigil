from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from datetime import datetime

from ..utils import ROOT, number, parse_time, pass_fail
from ..config import section_enabled
from ..evaluator import CHECKLIST_KEYS, evaluate_pr, verdict_label, find_pr

VALID_VERDICTS = {"ADMITTED", "REJECTED", "CONDITIONAL", "PENDING"}

STATUS_LABELS = {
    "PASS": "PASS",
    "FAIL": "FAIL",
    "WARN": "WARN",
    "N/A": "N/A",
    "READY": "READY",
    "PENDING": "PENDING",
}

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


def today() -> datetime:
    return datetime.now().astimezone()


def read_template(name: str) -> str:
    return (TEMPLATES_DIR / name).read_text(encoding="utf-8")


def write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def replace_placeholders(template: str, values: dict[str, Any], default: str = "暂无数据") -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(values.get(key, default))

    return re.sub(r"\{([A-Z0-9_]+)\}", replace, template)


def pr_url(pr: dict[str, Any]) -> str:
    return str(pr.get("url") or "#")


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value:
        return [str(value)]
    return []


def yes_no(value: Any) -> str:
    return "是" if bool(value) else "否"


def status(value: Any) -> str:
    val = STATUS_LABELS.get(str(value or "PENDING"), str(value or "PENDING"))
    emoji_map = {
        "PASS": "🟢 PASS",
        "FAIL": "🔴 FAIL",
        "WARN": "🟡 WARN",
        "N/A": "⚪ N/A",
        "READY": "🔵 READY",
        "PENDING": "🟠 PENDING",
        "ADMITTED": "🟢 ADMITTED",
        "REJECTED": "🔴 REJECTED",
        "CONDITIONAL": "🟡 CONDITIONAL",
    }
    return emoji_map.get(val, val)


def progress_bar(score: int) -> str:
    filled = int(score / 10)
    bar = "█" * filled + "░" * (10 - filled)
    emoji = "🟢" if score >= 80 else ("🟡" if score >= 60 else "🔴")
    return f"{emoji} {score} `[{bar}]`"


def gate_summary(pr: dict[str, Any], gate_key: str) -> str:
    gate = pr.get("gates", {}).get(gate_key, {})
    details = gate.get("details", {})
    if not details:
        return status(gate.get("status"))
    return "；".join(f"{key}={value}" for key, value in details.items())


def stage1_complete(pr: dict[str, Any]) -> bool:
    verdict = pr.get("verdict")
    summary = pr.get("gates_summary", {})
    gate_statuses = [summary.get("gate_1"), summary.get("gate_2"), summary.get("gate_3")]
    has_effective_gate = any(status in {"PASS", "FAIL", "WARN", "N/A"} for status in gate_statuses)
    all_pending = gate_statuses and all(status == "PENDING" for status in gate_statuses)
    return verdict in VALID_VERDICTS and has_effective_gate and not all_pending


def require_stage1_complete(prs: list[dict[str, Any]]) -> None:
    incomplete = [str(pr.get("pr_id") or "UNKNOWN") for pr in prs if not stage1_complete(pr)]
    if incomplete:
        joined = "、".join(incomplete)
        raise ValueError(f"阶段 1 未完成，禁止生成报告。请先执行 evaluate_gates.py --write：{joined}")


def checklist_status(pr: dict[str, Any], key: str) -> str:
    value = pr.get("review", {}).get("checklist", {}).get(key)
    if value is True:
        return "PASS"
    if value is False:
        return "FAIL"
    return "PENDING"


def completed_checklist_count(pr: dict[str, Any]) -> int:
    checklist = pr.get("review", {}).get("checklist", {})
    return sum(1 for key in CHECKLIST_KEYS if checklist.get(key) is True)
