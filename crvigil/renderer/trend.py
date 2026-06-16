from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..utils import number, parse_time
from ..config import section_enabled
from .helpers import (
    today,
    read_template,
    write_report,
    replace_placeholders,
    as_list,
    require_stage1_complete,
    progress_bar,
)


def score_for_gate(prs: list[dict[str, Any]], gate: str, max_score: int) -> int:
    active = [pr for pr in prs if pr.get("gates_summary", {}).get(gate) != "N/A"]
    if not active:
        return max_score
    passing = sum(1 for pr in active if pr.get("gates_summary", {}).get(gate) in {"PASS", "WARN"})
    return int(passing / len(active) * max_score)


def ai_declaration_score(prs: list[dict[str, Any]]) -> int:
    used = [pr for pr in prs if pr.get("ai_usage", {}).get("used")]
    if not used:
        return 20
    declared = sum(1 for pr in used if pr.get("ai_usage", {}).get("declared"))
    return int(declared / len(used) * 20)


def weekly_row(day: datetime, total: int, admitted: int, rejected: int, conditional: int, rate: float) -> str:
    return f"| {day.strftime('%Y-%m-%d')} | {total} | {admitted} | {rejected} | {conditional} | {rate:.1f}% |"


def weekly_empty_row(day: datetime) -> str:
    return f"| {day.strftime('%Y-%m-%d')} | 暂无历史数据 | 暂无历史数据 | 暂无历史数据 | 暂无历史数据 | 暂无历史数据 |"


def top_blocking_issue(prs: list[dict[str, Any]]) -> str:
    reasons = Counter(reason for pr in prs for reason in pr.get("blocking_reasons", []))
    return reasons.most_common(1)[0][0] if reasons else "无"


def top_tool(prs: list[dict[str, Any]]) -> str:
    tools = Counter(tool for pr in prs for tool in as_list(pr.get("ai_usage", {}).get("tools")) if tool != "未知")
    return tools.most_common(1)[0][0] if tools else "暂无数据"


def ai_tool_rows(prs: list[dict[str, Any]]) -> str:
    tool_to_pcts: dict[str, list[float]] = defaultdict(list)
    for pr in prs:
        pct = number(pr.get("ai_usage", {}).get("percentage", 0))
        for tool in as_list(pr.get("ai_usage", {}).get("tools")) or ["未知"]:
            tool_to_pcts[tool].append(pct)
    if not tool_to_pcts:
        return "| 暂无数据 | 0 | 0% |"
    return "\n".join(
        f"| {tool} | {len(pcts)} | {sum(pcts) / len(pcts):.1f}% |" for tool, pcts in sorted(tool_to_pcts.items())
    )


def top_blocking_rows(prs: list[dict[str, Any]]) -> str:
    reasons = Counter(reason for pr in prs for reason in pr.get("blocking_reasons", []))
    if not reasons:
        return "| 1 | 无 | 0 | 无 | 0 天 |"
    rows = []
    for rank, (reason, count) in enumerate(reasons.most_common(5), start=1):
        involved = [pr.get("pr_id") for pr in prs if reason in pr.get("blocking_reasons", [])]
        rows.append(f"| {rank} | {reason} | {count} | {'、'.join(involved)} | 暂无历史数据 |")
    return "\n".join(rows)


def reviewer_rows(prs: list[dict[str, Any]]) -> str:
    stats: dict[str, list[int]] = defaultdict(list)
    for pr in prs:
        reviewer = pr.get("review", {}).get("reviewer") or "未找到"
        stats[reviewer].append(int(number(pr.get("review", {}).get("substantive_comments", 0))))
    return "\n".join(
        f"| {reviewer} | {len(values)} | {sum(values) / len(values):.1f} | 0 | 暂无历史数据 |"
        for reviewer, values in sorted(stats.items())
    )


def violation_rows(prs: list[dict[str, Any]]) -> str:
    authors: dict[str, int] = defaultdict(int)
    for pr in prs:
        authors[str(pr.get("author") or "未知")] += int(number(pr.get("violations", 0)))
    if not authors:
        return "| 无 | 0 | 0 | 无 | 无 |"
    return "\n".join(
        f"| {author} | {count} | {count} | {'第 3 级' if count >= 3 else ('第 2 级' if count == 2 else '第 1 级')} | 按违规升级机制处理 |"
        for author, count in sorted(authors.items())
        if count > 0
    ) or "| 无 | 0 | 0 | 无 | 无 |"


def compute_gate_metrics(prs: list[dict[str, Any]]) -> dict[str, int]:
    metrics = {
        "g1_active": sum(1 for pr in prs if pr.get("gates_summary", {}).get("gate_1") != "N/A"),
        "g1_na": sum(1 for pr in prs if pr.get("gates_summary", {}).get("gate_1") == "N/A"),
        "g1_fail": sum(1 for pr in prs if pr.get("gates_summary", {}).get("gate_1") == "FAIL"),
        "g1_ut": 0,
        "g1_cov": 0,
        "g1_static": 0,
        "g1_smoke": 0,

        "g2_fail": sum(1 for pr in prs if pr.get("gates_summary", {}).get("gate_2") == "FAIL"),
        "g2_undeclared": 0,
        "g2_reviewer": 0,
        "g2_comments": 0,
        "g2_checklist": 0,

        "g3_fail": sum(1 for pr in prs if pr.get("gates_summary", {}).get("gate_3") == "FAIL"),
        "g3_ci_proof": 0,
        "g3_cr_link": 0,
        "g3_self": 0,
    }
    for pr in prs:
        gates = pr.get("gates", {})
        
        # Gate 1 details
        g1_details = gates.get("gate_1", {}).get("details", {})
        if isinstance(g1_details, dict):
            if g1_details.get("unit_test") == "FAIL": metrics["g1_ut"] += 1
            if g1_details.get("incremental_coverage") == "FAIL": metrics["g1_cov"] += 1
            if g1_details.get("static_scan") == "FAIL": metrics["g1_static"] += 1
            if g1_details.get("smoke_test") == "FAIL": metrics["g1_smoke"] += 1
            
        # Gate 2 details
        g2_details = gates.get("gate_2", {}).get("details", {})
        if isinstance(g2_details, dict):
            if g2_details.get("ai_declared") == "FAIL": metrics["g2_undeclared"] += 1
            if g2_details.get("reviewer_qualified") == "FAIL": metrics["g2_reviewer"] += 1
            if g2_details.get("substantive_comments") == "FAIL": metrics["g2_comments"] += 1
            if g2_details.get("checklist_complete") == "FAIL": metrics["g2_checklist"] += 1

        # Gate 3 details
        g3_details = gates.get("gate_3", {}).get("details", {})
        if isinstance(g3_details, dict):
            if g3_details.get("ci_proof") == "FAIL": metrics["g3_ci_proof"] += 1
            if g3_details.get("cr_link") == "FAIL": metrics["g3_cr_link"] += 1
            if g3_details.get("self_inspection") == "FAIL": metrics["g3_self"] += 1

    return metrics


def render_trend(registry: dict[str, Any], output_root: Path, config: dict[str, Any] | None = None) -> Path:
    config = config or {}
    now = today()
    require_stage1_complete(registry.get("prs", []))
    week_start = now - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=6)
    prs = registry.get("prs", [])
    total = len(prs)
    admitted = sum(1 for pr in prs if pr.get("verdict") == "ADMITTED")
    conditional = sum(1 for pr in prs if pr.get("verdict") == "CONDITIONAL")
    rejected = sum(1 for pr in prs if pr.get("verdict") == "REJECTED")
    admission_rate = (admitted + conditional) / total * 100 if total else 0
    avg_ai = sum(number(pr.get("ai_usage", {}).get("percentage", 0)) for pr in prs) / total if total else 0

    # Load daily snapshots for this week
    from ..snapshots import load_week_daily_snapshots, load_previous_weekly_snapshot
    snapshots = load_week_daily_snapshots(now)
    snapshot_by_date = {s.get("date"): s for s in snapshots if s.get("date")}

    def row_for_day(day: datetime) -> str:
        date_str = day.strftime("%Y-%m-%d")
        if date_str in snapshot_by_date:
            s = snapshot_by_date[date_str]
            sum_data = s.get("summary", {})
            active_cnt = sum_data.get("active_pr_count", 0)
            adm_cnt = sum_data.get("admitted_count", 0)
            rej_cnt = sum_data.get("rejected_count", 0)
            cond_cnt = sum_data.get("conditional_count", 0)
            rate = (adm_cnt + cond_cnt) / active_cnt * 100 if active_cnt else 0.0
            return weekly_row(day, active_cnt, adm_cnt, rej_cnt, cond_cnt, rate)
        else:
            return weekly_empty_row(day)

    # Compute average time to admit
    durations = []
    for pr in prs:
        if pr.get("verdict") in {"ADMITTED", "CONDITIONAL"}:
            created = parse_time(pr.get("created_at"))
            admitted_time = None
            for event in pr.get("history", []):
                if event.get("event") == "gate_evaluated" and ("ADMITTED" in event.get("details", "") or "CONDITIONAL" in event.get("details", "")):
                    admitted_time = parse_time(event.get("timestamp"))
                    break
            if not admitted_time:
                admitted_time = parse_time(pr.get("review", {}).get("review_approved_at"))
            if created and admitted_time:
                durations.append((admitted_time - created).total_seconds() / 86400.0)
    avg_time_to_admit_str = f"{sum(durations) / len(durations):.1f} 天" if durations else "暂无历史数据"

    # Compute sub-gate violations trend
    this_metrics = compute_gate_metrics(prs)
    last_week_data = load_previous_weekly_snapshot(now)
    last_prs = last_week_data.get("prs", []) if last_week_data else []
    
    if last_prs:
        last_metrics = compute_gate_metrics(last_prs)
        def get_vals(key: str) -> tuple[str, str]:
            t = this_metrics[key]
            l = last_metrics[key]
            d = t - l
            diff_str = f"+{d}" if d > 0 else str(d)
            return str(l), diff_str
            
        avg_ai_last = sum(number(pr.get("ai_usage", {}).get("percentage", 0)) for pr in last_prs) / len(last_prs) if last_prs else 0
        diff_ai = avg_ai - avg_ai_last
        direction = "上升 📈" if diff_ai > 0 else ("下降 📉" if diff_ai < 0 else "持平 ➡️")
        ai_trend_status = f"{direction}（与上周相比 {diff_ai:+.1f}%）"
        avg_ai_pct_last_str = f"{avg_ai_last:.1f}%"
        avg_ai_pct_change_str = f"{diff_ai:+.1f}%"
    else:
        def get_vals(key: str) -> tuple[str, str]:
            return "暂无数据", "暂无数据"
        ai_trend_status = "持平 ➡️（暂无上周数据）"
        avg_ai_pct_last_str = "暂无数据"
        avg_ai_pct_change_str = "暂无数据"

    g1_act_l, g1_act_c = get_vals("g1_active")
    g1_na_l, g1_na_c = get_vals("g1_na")
    g1_fail_l, g1_fail_c = get_vals("g1_fail")
    g1_ut_l, g1_ut_c = get_vals("g1_ut")
    g1_cov_l, g1_cov_c = get_vals("g1_cov")
    g1_static_l, g1_static_c = get_vals("g1_static")
    g1_smoke_l, g1_smoke_c = get_vals("g1_smoke")

    g2_fail_l, g2_fail_c = get_vals("g2_fail")
    g2_undeclared_l, g2_undeclared_c = get_vals("g2_undeclared")
    g2_reviewer_l, g2_reviewer_c = get_vals("g2_reviewer")
    g2_comments_l, g2_comments_c = get_vals("g2_comments")
    g2_checklist_l, g2_checklist_c = get_vals("g2_checklist")

    g3_fail_l, g3_fail_c = get_vals("g3_fail")
    g3_ci_proof_l, g3_ci_proof_c = get_vals("g3_ci_proof")
    g3_cr_link_l, g3_cr_link_c = get_vals("g3_cr_link")
    g3_self_l, g3_self_c = get_vals("g3_self")

    # Dynamic dynamic recommendations
    recommendations = []
    gate_fail_counter = Counter()
    gate_fail_counter["gate_1"] = this_metrics["g1_fail"]
    gate_fail_counter["gate_2"] = this_metrics["g2_fail"]
    gate_fail_counter["gate_3"] = this_metrics["g3_fail"]

    if gate_fail_counter.most_common(1) and gate_fail_counter.most_common(1)[0][1] > 0:
        top_failed_gate = gate_fail_counter.most_common(1)[0][0]
        if top_failed_gate == "gate_1":
            recommendations.append("本周 CI 质量红线门禁失败次数最多。建议开发团队在提测前，于本地运行单元测试并修复静态扫描问题，避免阻塞提测。")
        elif top_failed_gate == "gate_2":
            recommendations.append("本周人工 Code Review 及 AI 声明门禁阻碍较多。请审查人关注评论质量，确保完成 12 项 Checklist 勾选并提供实质性改进建议。")
        elif top_failed_gate == "gate_3":
            recommendations.append("本周测试准入声明门禁存在较多缺失。请开发人员重新对照准入要求，补齐 CI 证明及开发自签自检表后再行提测。")

    formalism_reviewers = []
    for pr in prs:
        reviewer = pr.get("review", {}).get("reviewer")
        comments_count = number(pr.get("review", {}).get("substantive_comments", 0))
        if reviewer and comments_count == 0 and pr.get("review", {}).get("review_approved_at"):
            formalism_reviewers.append(reviewer)
    if formalism_reviewers:
        recommendations.append(f"检测到部分 PR 存在审查形式主义（无实质评论直接 Approve，涉及审核人：{'、'.join(set(formalism_reviewers))}）。建议项目管理人员加强 Code Review 抽查，提升 CR 门禁有效性。")

    if not recommendations:
        recommendations.append("本周提测准入合规情况良好。建议继续保持，并在测试排期中优先测试已准入的 MR。")

    rec_content = "\n\n".join(f"{i}. {rec}" for i, rec in enumerate(recommendations, 1))

    values = {
        "WEEK_START": week_start.strftime("%Y-%m-%d"),
        "WEEK_END": week_end.strftime("%Y-%m-%d"),
        "TIMESTAMP": now.strftime("%Y-%m-%d %H:%M:%S %z"),
        "TOTAL_PR_COUNT": total,
        "OVERALL_ADMISSION_RATE": f"{admission_rate:.1f}",
        "AVG_TIME_TO_ADMIT": avg_time_to_admit_str,
        "TOP_BLOCKING_ISSUE": top_blocking_issue(prs),
        "AI_TREND_STATUS": ai_trend_status,
        "ESCALATION_COUNT": sum(1 for pr in prs if number(pr.get("violations")) >= 3),
        "TEAM_COMPLIANCE_SCORE": progress_bar(int(admission_rate)),
        
        "CI_COMPLIANCE_SCORE": score_for_gate(prs, "gate_1", 30),
        "CI_COMPLIANCE_DESC": "按当前 registry 中 Gate1 状态估算。",
        "CR_COMPLIANCE_SCORE": score_for_gate(prs, "gate_2", 30),
        "CR_COMPLIANCE_DESC": "按当前 registry 中 Gate2 状态估算。",
        "DECLARATION_COMPLIANCE_SCORE": score_for_gate(prs, "gate_3", 20),
        "DECLARATION_COMPLIANCE_DESC": "按当前 registry 中 Gate3 状态估算。",
        "AI_DECLARATION_COMPLIANCE_SCORE": ai_declaration_score(prs),
        "AI_DECLARATION_COMPLIANCE_DESC": "按 AI 使用声明完整性估算。",
        
        "MONDAY_ROW": row_for_day(week_start),
        "TUESDAY_ROW": row_for_day(week_start + timedelta(days=1)),
        "WEDNESDAY_ROW": row_for_day(week_start + timedelta(days=2)),
        "THURSDAY_ROW": row_for_day(week_start + timedelta(days=3)),
        "FRIDAY_ROW": row_for_day(week_start + timedelta(days=4)),
        "SATURDAY_ROW": row_for_day(week_start + timedelta(days=5)),
        "SUNDAY_ROW": row_for_day(week_start + timedelta(days=6)),
        
        # Gate 1 Violations table
        "G1_ACTIVE_COUNT": this_metrics["g1_active"],
        "G1_ACTIVE_LAST": g1_act_l,
        "G1_ACTIVE_CHANGE": g1_act_c,
        "G1_NA_COUNT": this_metrics["g1_na"],
        "G1_NA_LAST": g1_na_l,
        "G1_NA_CHANGE": g1_na_c,
        "G1_THIS_WEEK": this_metrics["g1_fail"],
        "G1_LAST_WEEK": g1_fail_l,
        "G1_CHANGE": g1_fail_c,
        "G1_UT_COUNT": this_metrics["g1_ut"],
        "G1_UT_LAST": g1_ut_l,
        "G1_UT_CHANGE": g1_ut_c,
        "G1_COV_COUNT": this_metrics["g1_cov"],
        "G1_COV_LAST": g1_cov_l,
        "G1_COV_CHANGE": g1_cov_c,
        "G1_STATIC_COUNT": this_metrics["g1_static"],
        "G1_STATIC_LAST": g1_static_l,
        "G1_STATIC_CHANGE": g1_static_c,
        "G1_SMOKE_COUNT": this_metrics["g1_smoke"],
        "G1_SMOKE_LAST": g1_smoke_l,
        "G1_SMOKE_CHANGE": g1_smoke_c,

        # Gate 2 Violations table
        "G2_THIS_WEEK": this_metrics["g2_fail"],
        "G2_LAST_WEEK": g2_fail_l,
        "G2_CHANGE": g2_fail_c,
        "G2_UNDECLARED": this_metrics["g2_undeclared"],
        "G2_UNDECLARED_LAST": g2_undeclared_l,
        "G2_UNDECLARED_CHANGE": g2_undeclared_c,
        "G2_REVIEWER": this_metrics["g2_reviewer"],
        "G2_REVIEWER_LAST": g2_reviewer_l,
        "G2_REVIEWER_CHANGE": g2_reviewer_c,
        "G2_COMMENTS": this_metrics["g2_comments"],
        "G2_COMMENTS_LAST": g2_comments_l,
        "G2_COMMENTS_CHANGE": g2_comments_c,
        "G2_CHECKLIST": this_metrics["g2_checklist"],
        "G2_CHECKLIST_LAST": g2_checklist_l,
        "G2_CHECKLIST_CHANGE": g2_checklist_c,

        # Gate 3 Violations table
        "G3_THIS_WEEK": this_metrics["g3_fail"],
        "G3_LAST_WEEK": g3_fail_l,
        "G3_CHANGE": g3_fail_c,
        "G3_CI_PROOF": this_metrics["g3_ci_proof"],
        "G3_CI_PROOF_LAST": g3_ci_proof_l,
        "G3_CI_PROOF_CHANGE": g3_ci_proof_c,
        "G3_CR_LINK": this_metrics["g3_cr_link"],
        "G3_CR_LINK_LAST": g3_cr_link_l,
        "G3_CR_LINK_CHANGE": g3_cr_link_c,
        "G3_SELF": this_metrics["g3_self"],
        "G3_SELF_LAST": g3_self_l,
        "G3_SELF_CHANGE": g3_self_c,

        "AVG_AI_PCT": f"{avg_ai:.1f}%",
        "AVG_AI_PCT_LAST": avg_ai_pct_last_str,
        "AVG_AI_PCT_CHANGE": avg_ai_pct_change_str,
        "HIGH_AI_COUNT": sum(1 for pr in prs if number(pr.get("ai_usage", {}).get("percentage", 0)) > 50),
        "ANY_AI_COUNT": sum(1 for pr in prs if pr.get("ai_usage", {}).get("used")),
        "UNDECLARED_COUNT": sum(1 for pr in prs if pr.get("ai_usage", {}).get("used") and not pr.get("ai_usage", {}).get("declared")),
        "TOP_TOOL": top_tool(prs),
        "AI_TOOL_ROWS": ai_tool_rows(prs),
        "TOP_BLOCKING_ROWS": top_blocking_rows(prs),
        "REVIEWER_STATS_ROWS": reviewer_rows(prs)
        if section_enabled(config, "weekly", "reviewer_stats", True)
        else "| 按配置隐藏 | 0 | 0 | 0 | 0 |",
        "VIOLATION_RECURRENCE_ROWS": violation_rows(prs)
        if section_enabled(config, "weekly", "recurrence", True)
        else "| 按配置隐藏 | 0 | 0 | 无 | 无 |",
        "INCIDENT_SECTION": "本周无线上故障记录。",
        "WEEK_COMPLIANCE_ROWS": f"| {week_start.strftime('%Y-%m-%d')} | {total} | {admission_rate:.1f}% | 当前周 | 当前周 | 当前周 | {avg_time_to_admit_str} |",
        "RECOMMENDATIONS": rec_content
        if section_enabled(config, "weekly", "recommendations", True)
        else "按配置隐藏建议。",
        "NEXT_WEEK_START": (week_start + timedelta(days=7)).strftime("%Y-%m-%d"),
    }
    content = replace_placeholders(read_template("weekly-trend-template.md"), values)
    path = output_root / "trends" / f"weekly-trend-{week_start.strftime('%Y-%m-%d')}.md"
    write_report(path, content)
    return path
