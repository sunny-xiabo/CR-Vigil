from __future__ import annotations

from pathlib import Path
from typing import Any

from ..utils import number, pass_fail
from ..evaluator import evaluate_pr, verdict_label, find_pr, CHECKLIST_KEYS
from .helpers import (
    today,
    read_template,
    write_report,
    replace_placeholders,
    pr_url,
    as_list,
    yes_no,
    gate_summary,
    require_stage1_complete,
    checklist_status,
    completed_checklist_count,
)


def admission_values(pr: dict[str, Any]) -> dict[str, Any]:
    evaluation = evaluate_pr(pr)
    gates = evaluation["gates"]
    ai_usage = pr.get("ai_usage", {})
    review = pr.get("review", {})
    ci = pr.get("ci", {})
    declaration = pr.get("declaration", {})
    self_inspection = declaration.get("self_inspection", {})
    checks = self_inspection.get("checks", {})
    now = today()
    completed = completed_checklist_count(pr)
    verdict = evaluation["verdict"]
    blocking = evaluation["blocking_reasons"]
    ai_pct = ai_usage.get("percentage", pr.get("ai_percentage", 0))
    modules = as_list(ai_usage.get("modules")) or ["未采集"]
    ai_distribution = "\n".join(f"| {module} | {ai_pct}% |" for module in modules)

    gate1_status = gates["gate_1"]["status"]
    gate1_section = (
        "该项目未检测到 CI 数据，门禁一按 N/A 处理，不参与准入判定。"
        if gate1_status == "N/A"
        else "\n".join(
            [
                "| 检查项 | 实际值 | 状态 |",
                "|------|------|------|",
                f"| 单元测试通过率 | {ci.get('unit_test', {}).get('pass_rate', 0)}% | {gates['gate_1']['details'].get('unit_test')} |",
                f"| 增量覆盖率 | {ci.get('coverage', {}).get('incremental_coverage_pct', 0)}% | {gates['gate_1']['details'].get('incremental_coverage')} |",
                f"| 静态扫描 Blocker/Critical | {ci.get('static_scan', {}).get('blocker_count', 0)}/{ci.get('static_scan', {}).get('critical_count', 0)} | {gates['gate_1']['details'].get('static_scan')} |",
                f"| 冒烟测试通过率 | {ci.get('smoke_test', {}).get('pass_rate', 0)}% | {gates['gate_1']['details'].get('smoke_test')} |",
            ]
        )
    )

    recommendations = {
        "ADMITTED": "建议测试团队按正常流程排期，并重点关注 AI 生成模块的边界条件。",
        "CONDITIONAL": "建议允许进入测试，但需同步 TL 关注 WARN 项，并在测试记录中标注风险。",
        "REJECTED": "建议开发先处理阻塞问题，补齐材料后重新发起提测准入评估。",
        "PENDING": "建议补齐缺失数据后重新执行评估。",
    }.get(verdict, "建议重新执行评估。")

    return {
        "PR_TITLE": pr.get("title", ""),
        "PR_ID": pr.get("pr_id", ""),
        "DATE": now.strftime("%Y-%m-%d"),
        "TIMESTAMP": now.strftime("%Y-%m-%d %H:%M:%S %z"),
        "PR_URL": pr_url(pr),
        "AUTHOR": pr.get("author", ""),
        "AI_PERCENTAGE": ai_pct,
        "REVIEWER": review.get("reviewer") or "未找到",
        "CI_MODE_LABEL": pr.get("ci_mode", "auto"),
        "VERDICT_LABEL": f"{verdict}（🟢 {verdict_label(verdict)}）" if verdict == "ADMITTED" else (f"{verdict}（🟡 {verdict_label(verdict)}）" if verdict == "CONDITIONAL" else (f"{verdict}（🔴 {verdict_label(verdict)}）" if verdict == "REJECTED" else f"{verdict}（🟠 {verdict_label(verdict)}）")),
        "VERDICT_SUMMARY": "无阻塞问题。" if not blocking else "存在阻塞问题，暂不建议进入测试。",
        "GATE1_REQUIREMENT": "UT 100%、覆盖率 >= 70%、静态扫描无阻断/严重问题、冒烟 100%",
        "GATE1_STATUS": gate1_status,
        "GATE1_SUMMARY": gate_summary({"gates": gates}, "gate_1"),
        "GATE2_STATUS": gates["gate_2"]["status"],
        "GATE2_SUMMARY": gate_summary({"gates": gates}, "gate_2"),
        "GATE3_REQUIREMENT": "CI 证明、CR 批准链接、自检声明",
        "GATE3_STATUS": gates["gate_3"]["status"],
        "GATE3_SUMMARY": gate_summary({"gates": gates}, "gate_3"),
        "CHANGES_COUNT": pr.get("changes_count", "未采集"),
        "ADDITIONS": pr.get("additions", "未采集"),
        "DELETIONS": pr.get("deletions", "未采集"),
        "NET_ADDITIONS": pr.get("net_additions", "未采集"),
        "CHANGE_SCALE_RATING": "未采集",
        "SCALE_RISK_WARNING": "未采集变更规模数据，建议结合 MR diff 人工确认。",
        "AI_DISTRIBUTION_TABLE": "| 模块 | AI 占比 |\n|------|------|\n" + ai_distribution,
        "AI_USAGE_RISK_LEVEL": "高" if number(ai_pct) >= 60 else ("中" if number(ai_pct) >= 30 else "低"),
        "AI_USAGE_RISK_DESC": f"AI 代码占比 {ai_pct}%。",
        "CHANGE_SCALE_RISK_LEVEL": "待确认",
        "CHANGE_SCALE_RISK_DESC": "当前数据未包含 diff 规模。",
        "CR_QUALITY_RISK_LEVEL": "低" if gates["gate_2"]["status"] == "PASS" else gates["gate_2"]["status"],
        "CR_QUALITY_RISK_DESC": gate_summary({"gates": gates}, "gate_2"),
        "MODULE_SENSITIVITY_RISK_LEVEL": "待确认",
        "MODULE_SENSITIVITY_RISK_DESC": "需结合业务模块敏感度人工确认。",
        "OVERALL_RISK_LEVEL": "高" if verdict == "REJECTED" else ("中" if verdict == "CONDITIONAL" else "低"),
        "OVERALL_RISK_DESC": verdict_label(verdict),
        "TESTING_RECOMMENDATIONS": recommendations,
        "GATE1_SECTION_CONTENT": gate1_section,
        "AI_USED": yes_no(ai_usage.get("used")),
        "AI_DECLARED": yes_no(ai_usage.get("declared")),
        "AI_TOOLS": "、".join(as_list(ai_usage.get("tools")) or ["未采集"]),
        "AI_MODULES": "、".join(modules),
        "REVIEWER_LEVEL": review.get("reviewer_level") or "未知",
        "IS_SELF_REVIEW": yes_no(review.get("reviewer") == pr.get("author")),
        "SUBSTANTIVE_COMMENTS_COUNT": review.get("substantive_comments", 0),
        "COMMENT_QUALITY": "有效" if gates["gate_2"]["details"].get("substantive_comments") == "PASS" else "不足",
        "CHECKLIST_COMPLETED_COUNT": completed,
        "CHECKLIST_COMPLETION_PCT": int(completed / len(CHECKLIST_KEYS) * 100),
        "GATE2_VERDICT": gates["gate_2"]["status"],
        "GATE2_DETAIL_NOTES": gate_summary({"gates": gates}, "gate_2"),
        "CI_PROOF_REQUIREMENT": "Gate1=N/A 时不强制" if gate1_status == "N/A" else "必须提供 CI 通过证明",
        "CI_PROOF_PROVIDED": "N/A" if gate1_status == "N/A" else yes_no(declaration.get("ci_proof_provided")),
        "CI_PROOF_STATUS": gates["gate_3"]["details"].get("ci_proof"),
        "CR_LINK_PROVIDED": yes_no(declaration.get("cr_approval_link")),
        "CR_LINK_STATUS": gates["gate_3"]["details"].get("cr_link"),
        "SELF_INSPECTION_PROVIDED": yes_no(self_inspection.get("submitted")),
        "SELF_INSPECTION_STATUS": gates["gate_3"]["details"].get("self_inspection"),
        "SI01_REQUIREMENT": "本次提测代码已通过 CI 全部质量门禁",
        "SI01_STATUS": "N/A" if gate1_status == "N/A" else pass_fail(checks.get("ci_passed") is True),
        "SI02_STATUS": pass_fail(checks.get("cr_completed") is True),
        "SI03_STATUS": pass_fail(checks.get("boundary_verified") is True),
        "SI04_STATUS": pass_fail(checks.get("self_tested") is True),
        "SI05_STATUS": pass_fail(checks.get("no_known_blockers") is True),
        "GATE3_VERDICT": gates["gate_3"]["status"],
        "GATE3_DETAIL_NOTES": gate_summary({"gates": gates}, "gate_3"),
        "GATE4_STATUS": gates["gate_4"]["status"],
        "BLOCKING_ISSUES_LIST": "\n".join(f"- {item}" for item in blocking) if blocking else "无阻塞问题。",
        "RECOMMENDATIONS": recommendations,
        "HISTORY_ENTRIES": "\n".join(
            f"| {item.get('timestamp', '')} | {item.get('event', '')}：{item.get('details', '')} |"
            for item in pr.get("history", [])
        )
        or "| 暂无 | 暂无历史记录 |",
        **{f"CK{i:02d}_STATUS": checklist_status(pr, f"ck_{i:02d}") for i in range(1, 13)},
    }


def render_admission(registry: dict[str, Any], pr_id: str, output_root: Path, config: dict[str, Any] | None = None) -> Path:
    _, pr = find_pr(registry, pr_id)
    require_stage1_complete([pr])
    template = read_template("admission-report-template.md")
    content = replace_placeholders(template, admission_values(pr))
    path = output_root / "admissions" / f"{pr_id}-admission-{today().strftime('%Y-%m-%d')}.md"
    write_report(path, content)
    return path
