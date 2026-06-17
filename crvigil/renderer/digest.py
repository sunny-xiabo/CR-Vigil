from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ..utils import number, parse_time
from ..config import section_enabled
from .helpers import (
    today,
    read_template,
    write_report,
    replace_placeholders,
    yes_no,
    gate_summary,
    require_stage1_complete,
    status,
)


def active_prs(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return [pr for pr in registry.get("prs", []) if pr.get("status") == "open"]


def pr_row(pr: dict[str, Any]) -> str:
    gates = pr.get("gates_summary", {})
    return (
        f"| {pr.get('pr_id')} | {pr.get('title')} | {pr.get('author')} | "
        f"{pr.get('ai_usage', {}).get('percentage', pr.get('ai_percentage', 0))}% | "
        f"{status(gates.get('gate_1', 'PENDING'))} | {status(gates.get('gate_2', 'PENDING'))} | "
        f"{status(gates.get('gate_3', 'PENDING'))} | {status(pr.get('verdict', 'PENDING'))} |"
    )


def list_prs(prs: list[dict[str, Any]], empty_text: str) -> str:
    if not prs:
        return empty_text
    return "\n".join(f"- {pr.get('pr_id')}：{pr.get('title')}（{pr.get('author')}）" for pr in prs)


def render_digest(registry: dict[str, Any], output_root: Path, config: dict[str, Any] | None = None) -> Path:
    config = config or {}
    now = today()
    prs = active_prs(registry)
    require_stage1_complete(prs)
    admitted = [pr for pr in prs if pr.get("verdict") == "ADMITTED"]
    blocked = [pr for pr in prs if pr.get("verdict") == "REJECTED"]
    pending = [pr for pr in prs if pr.get("verdict") == "PENDING"]
    gate_fail_counter = Counter()
    gate_fail_prs: dict[str, list[str]] = defaultdict(list)
    for pr in prs:
        for gate in ["gate_1", "gate_2", "gate_3"]:
            if pr.get("gates_summary", {}).get(gate) == "FAIL":
                gate_fail_counter[gate] += 1
                gate_fail_prs[gate].append(pr.get("pr_id", ""))

    avg_ai = sum(number(pr.get("ai_usage", {}).get("percentage", 0)) for pr in prs) / len(prs) if prs else 0
    top_gate = gate_fail_counter.most_common(1)[0][0] if gate_fail_counter else "无"

    yesterday_active_count = "暂无历史数据"
    active_change = "暂无历史数据"
    yesterday_admitted_count = "暂无历史数据"
    admitted_change = "暂无历史数据"
    yesterday_blocked_count = "暂无历史数据"
    blocked_change = "暂无历史数据"

    from ..snapshots import load_yesterday_snapshot
    yesterday = load_yesterday_snapshot(now)
    if yesterday and "summary" in yesterday:
        y_summary = yesterday["summary"]
        y_active = y_summary.get("active_pr_count", 0)
        y_admitted = y_summary.get("admitted_count", 0)
        y_blocked = y_summary.get("rejected_count", 0)

        yesterday_active_count = str(y_active)
        yesterday_admitted_count = str(y_admitted)
        yesterday_blocked_count = str(y_blocked)

        def format_diff(d: int) -> str:
            return f"+{d}" if d > 0 else str(d)

        active_change = format_diff(len(prs) - y_active)
        admitted_change = format_diff(len(admitted) - y_admitted)
        blocked_change = format_diff(len(blocked) - y_blocked)

    durations = []
    for pr in prs:
        created = parse_time(pr.get("created_at"))
        approved = parse_time(pr.get("review", {}).get("review_approved_at"))
        if created and approved:
            durations.append((approved - created).total_seconds() / 86400.0)
    avg_review_days_str = f"{sum(durations) / len(durations):.1f}" if durations else "暂无历史数据"

    values = {
        "DATE": now.strftime("%Y-%m-%d"),
        "TIMESTAMP": now.strftime("%Y-%m-%d %H:%M:%S %z"),
        "ACTIVE_PR_COUNT": len(prs),
        "ADMITTED_COUNT": len(admitted),
        "BLOCKED_COUNT": len(blocked),
        "YESTERDAY_ACTIVE_PR_COUNT": yesterday_active_count,
        "ACTIVE_PR_COUNT_CHANGE": active_change,
        "YESTERDAY_ADMITTED_COUNT": yesterday_admitted_count,
        "ADMITTED_COUNT_CHANGE": admitted_change,
        "YESTERDAY_BLOCKED_COUNT": yesterday_blocked_count,
        "BLOCKED_COUNT_CHANGE": blocked_change,
        "TOP_BLOCKING_GATE": top_gate,
        "AVG_AI_PERCENTAGE": f"{avg_ai:.1f}",
        "AVG_REVIEW_DAYS": avg_review_days_str,
        "PR_STATUS_ROWS": "\n".join(pr_row(pr) for pr in prs) or "| 无 | 无 | 无 | 0% | N/A | N/A | N/A | PENDING |",
        "ADMITTED_PR_LIST": list_prs(admitted, "当前没有 PR 通过测试准入。"),
        "BLOCKED_PR_LIST": list_prs(blocked, "当前没有 PR 被阻塞，所有活跃 PR 均可进入测试。"),
        "PENDING_PR_LIST": list_prs(pending, "当前没有 PR 等待评估。")
        if section_enabled(config, "daily", "pending_prs", False)
        else "按配置隐藏待评估 PR。",
        "G1_FAIL_COUNT": gate_fail_counter.get("gate_1", 0),
        "G1_NA_COUNT": sum(1 for pr in prs if pr.get("gates_summary", {}).get("gate_1") == "N/A"),
        "G1_FAIL_PRS": "、".join(gate_fail_prs.get("gate_1", [])) or "无",
        "G2_FAIL_COUNT": gate_fail_counter.get("gate_2", 0),
        "G2_FAIL_PRS": "、".join(gate_fail_prs.get("gate_2", [])) or "无",
        "G3_FAIL_COUNT": gate_fail_counter.get("gate_3", 0),
        "G3_NA_COUNT": sum(1 for pr in prs if pr.get("gates_summary", {}).get("gate_3") == "N/A"),
        "G3_FAIL_PRS": "、".join(gate_fail_prs.get("gate_3", [])) or "无",
        "GATE1_FAILURE_DETAILS": failure_details(prs, "gate_1")
        if section_enabled(config, "daily", "detailed_gate_reasons", False)
        else "按配置隐藏详细门禁原因，详见单 MR 提测报告。",
        "GATE2_FAILURE_DETAILS": failure_details(prs, "gate_2")
        if section_enabled(config, "daily", "detailed_gate_reasons", False)
        else "按配置隐藏详细门禁原因，详见单 MR 提测报告。",
        "GATE3_FAILURE_DETAILS": failure_details(prs, "gate_3")
        if section_enabled(config, "daily", "detailed_gate_reasons", False)
        else "按配置隐藏详细门禁原因，详见单 MR 提测报告。",
        "VIOLATION_ALERTS": recurrence_alerts(prs),
        "ACTION_ITEMS": action_items(blocked)
        if section_enabled(config, "daily", "action_items", True)
        else "按配置隐藏行动项。",
        "NEXT_DIGEST_TIME": "下一次 /loop 24h 触发时间",
    }
    content = replace_placeholders(read_template("daily-digest-template.md"), values)
    path = output_root / "digests" / f"daily-digest-{now.strftime('%Y-%m-%d')}.md"
    write_report(path, content)
    return path


_GATE_PREFIX = {
    "gate_1": "门禁一：",
    "gate_2": "门禁二：",
    "gate_3": "门禁三：",
}


def failure_details(prs: list[dict[str, Any]], gate: str) -> str:
    failed = [pr for pr in prs if pr.get("gates_summary", {}).get(gate) == "FAIL"]
    if not failed:
        return "无"
    prefix = _GATE_PREFIX.get(gate, "")
    rows = []
    for pr in failed:
        if pr.get("blocking_reasons"):
            reasons = "；".join(r for r in pr["blocking_reasons"] if r.startswith(prefix))
        else:
            reasons = ""
        rows.append(f"- {pr.get('pr_id')}：{reasons or gate_summary(pr, gate)}")
    return "\n".join(rows)


def recurrence_alerts(prs: list[dict[str, Any]]) -> str:
    repeated = [pr for pr in prs if number(pr.get("violations")) >= 2]
    if not repeated:
        return "今日未检测到复现违规。"
    return "\n".join(f"- {pr.get('author')} 在 {pr.get('pr_id')} 已累计违规 {pr.get('violations')} 次" for pr in repeated)


def action_items(blocked: list[dict[str, Any]]) -> str:
    if not blocked:
        return "无阻塞行动项。"
    return "\n".join(f"- {pr.get('pr_id')}：开发需处理阻塞原因后重新提测。" for pr in blocked)
