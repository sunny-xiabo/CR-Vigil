#!/usr/bin/env python3
"""Deterministic CR-Vigil gate evaluator.

This script is intentionally dependency-free so the Skill can run it in the
same environments that already run the Bash collection scripts.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage import load_registry_with_records, save_registry_index
from .utils import integer, now_iso, number, parse_time, pass_fail


CHECKLIST_KEYS = [f"ck_{i:02d}" for i in range(1, 13)]
SENIOR_LEVELS = {"senior", "staff", "principal", "lead"}


def load_registry(path: Path) -> dict[str, Any]:
    return load_registry_with_records(path)


def save_registry(path: Path, registry: dict[str, Any]) -> None:
    save_registry_index(path, registry)


def find_pr(registry: dict[str, Any], pr_id: str) -> tuple[int, dict[str, Any]]:
    for index, pr in enumerate(registry.get("prs", [])):
        if pr.get("pr_id") == pr_id:
            return index, pr
    raise ValueError(f"未找到 PR: {pr_id}")


def has_ci_data(ci: dict[str, Any]) -> bool:
    return bool(ci.get("pipeline_url")) or integer(ci.get("unit_test", {}).get("total")) > 0 or integer(
        ci.get("smoke_test", {}).get("total")
    ) > 0


def resolve_ci_mode(pr: dict[str, Any]) -> str:
    raw_mode = str(pr.get("ci_mode") or "auto").lower()
    if raw_mode not in {"enabled", "disabled", "auto"}:
        raw_mode = "auto"
    if raw_mode == "auto":
        return "enabled" if has_ci_data(pr.get("ci", {})) else "disabled"
    return raw_mode


def evaluate_gate_1(pr: dict[str, Any], blocking_reasons: list[str]) -> dict[str, Any]:
    ci = pr.get("ci", {})
    mode = resolve_ci_mode(pr)
    if mode == "disabled":
        return {
            "status": "N/A",
            "details": {
                "unit_test": "N/A",
                "incremental_coverage": "N/A",
                "static_scan": "N/A",
                "smoke_test": "N/A",
            },
        }

    unit = ci.get("unit_test", {})
    coverage = ci.get("coverage", {})
    scan = ci.get("static_scan", {})
    smoke = ci.get("smoke_test", {})

    unit_total = integer(unit.get("total"))
    unit_rate = number(unit.get("pass_rate"))
    coverage_pct = number(coverage.get("incremental_coverage_pct"))
    coverage_threshold = number(coverage.get("threshold"), 70)
    blocker_count = integer(scan.get("blocker_count"), -1)
    critical_count = integer(scan.get("critical_count"), -1)
    smoke_total = integer(smoke.get("total"))
    smoke_rate = number(smoke.get("pass_rate"))

    unit_ok = unit_total > 0 and unit_rate == 100
    coverage_ok = coverage_pct >= coverage_threshold
    static_ok = blocker_count == 0 and critical_count == 0
    smoke_ok = smoke_total > 0 and smoke_rate == 100

    if not unit_ok:
        blocking_reasons.append(f"门禁一：单元测试通过率 {unit_rate:g}% 未达到 100%")
    if not coverage_ok:
        blocking_reasons.append(f"门禁一：增量覆盖率 {coverage_pct:g}% 低于阈值 {coverage_threshold:g}%")
    if not static_ok:
        blocking_reasons.append(f"门禁一：静态扫描存在 {blocker_count} 个 Blocker、{critical_count} 个 Critical")
    if not smoke_ok:
        blocking_reasons.append(f"门禁一：冒烟测试通过率 {smoke_rate:g}% 未达到 100%")

    details = {
        "unit_test": pass_fail(unit_ok),
        "incremental_coverage": pass_fail(coverage_ok),
        "static_scan": pass_fail(static_ok),
        "smoke_test": pass_fail(smoke_ok),
    }
    return {"status": "PASS" if all(v == "PASS" for v in details.values()) else "FAIL", "details": details}


def evaluate_gate_2(pr: dict[str, Any], blocking_reasons: list[str]) -> dict[str, Any]:
    ai_usage = pr.get("ai_usage", {})
    review = pr.get("review", {})
    author = str(pr.get("author") or "")
    reviewer = str(review.get("reviewer") or "")
    reviewer_level = str(review.get("reviewer_level") or "").lower()
    checklist = review.get("checklist", {})

    ai_pct = number(ai_usage.get("percentage", pr.get("ai_percentage", 0)))
    ai_declared_ok = ai_pct == 0 or bool(ai_usage.get("declared"))
    reviewer_ok = bool(reviewer) and reviewer != author and reviewer_level in SENIOR_LEVELS
    comments_ok = integer(review.get("substantive_comments")) >= 1
    checklist_ok = all(checklist.get(key) is True for key in CHECKLIST_KEYS)

    if not ai_declared_ok:
        blocking_reasons.append(f"门禁二：AI 使用占比 {ai_pct:g}%，但 PR 中未完成 AI 声明")
    if not reviewer_ok:
        if not reviewer:
            blocking_reasons.append("门禁二：未找到 Code Review 审查人")
        elif reviewer == author:
            blocking_reasons.append(f"门禁二：审查人 {reviewer} 与 PR 作者相同，存在自审")
        else:
            blocking_reasons.append(f"门禁二：审查人 {reviewer} 级别为 {reviewer_level or '未知'}，未达到 senior/staff")
    if not comments_ok:
        blocking_reasons.append("门禁二：实质性审查评论数量少于 1 条")
    if not checklist_ok:
        missing = [key.upper().replace("_", "-") for key in CHECKLIST_KEYS if checklist.get(key) is not True]
        blocking_reasons.append(f"门禁二：AI Code Review Checklist 未完成：{', '.join(missing)}")

    details = {
        "ai_declared": pass_fail(ai_declared_ok),
        "reviewer_qualified": pass_fail(reviewer_ok),
        "substantive_comments": pass_fail(comments_ok),
        "checklist_complete": pass_fail(checklist_ok),
    }

    primary_ok = all(value == "PASS" for value in details.values())
    review_updated_at = parse_time(pr.get("updated_at"))
    approved_at = parse_time(review.get("review_approved_at"))
    timed_out = False
    if primary_ok and review_updated_at and approved_at:
        timed_out = (approved_at - review_updated_at).total_seconds() > 24 * 60 * 60
    details["review_timeliness"] = "WARN" if timed_out else ("PASS" if approved_at else "N/A")

    if not primary_ok:
        status = "FAIL"
    elif timed_out:
        status = "WARN"
    else:
        status = "PASS"
    return {"status": status, "details": details}


def evaluate_gate_3(pr: dict[str, Any], gate_1_status: str, blocking_reasons: list[str]) -> dict[str, Any]:
    declaration = pr.get("declaration", {})
    self_inspection = declaration.get("self_inspection", {})
    checks = self_inspection.get("checks", {})

    ci_required = gate_1_status != "N/A"
    ci_proof_ok = not ci_required or bool(declaration.get("ci_proof_provided"))
    cr_link_ok = bool(str(declaration.get("cr_approval_link") or "").strip())
    required_self_checks = ["ci_passed", "cr_completed", "boundary_verified", "self_tested", "no_known_blockers"]
    if not ci_required:
        required_self_checks = [key for key in required_self_checks if key != "ci_passed"]
    self_ok = bool(self_inspection.get("submitted")) and all(checks.get(key) is True for key in required_self_checks)

    if not ci_proof_ok:
        blocking_reasons.append("门禁三：未提供 CI 通过证明")
    if not cr_link_ok:
        blocking_reasons.append("门禁三：未提供 CR 批准链接")
    if not self_ok:
        blocking_reasons.append("门禁三：开发自检声明未提交或五项确认未全部完成")

    details = {
        "ci_proof": "N/A" if not ci_required else pass_fail(ci_proof_ok),
        "cr_link": pass_fail(cr_link_ok),
        "self_inspection": pass_fail(self_ok),
    }
    status = "PASS" if ci_proof_ok and cr_link_ok and self_ok else "FAIL"
    return {"status": status, "details": details}


def evaluate_gate_4(pr: dict[str, Any]) -> dict[str, Any]:
    ci = pr.get("ci", {})
    review = pr.get("review", {})
    declaration = pr.get("declaration", {})
    ready = bool(ci.get("pipeline_url")) and bool(review.get("reviewer")) and bool(
        declaration.get("self_inspection", {}).get("submitted")
    )
    return {"status": "READY" if ready else "N/A", "details": {"records_available": ready}}


def calculate_verdict(gates: dict[str, Any]) -> str:
    active_statuses = [
        gates["gate_1"]["status"],
        gates["gate_2"]["status"],
        gates["gate_3"]["status"],
    ]
    active_statuses = [status for status in active_statuses if status != "N/A"]
    if any(status == "FAIL" for status in active_statuses):
        return "REJECTED"
    if any(status == "PENDING" for status in active_statuses):
        return "PENDING"
    if any(status == "WARN" for status in active_statuses):
        return "CONDITIONAL"
    return "ADMITTED"


def summarize(pr: dict[str, Any], gates: dict[str, Any], verdict: str, blocking_reasons: list[str]) -> dict[str, Any]:
    ci = pr.get("ci", {})
    declaration = pr.get("declaration", {})
    return {
        "stage": "stage_1_gate_evaluation",
        "stage_status": "COMPLETED",
        "pr_id": pr.get("pr_id"),
        "title": pr.get("title", ""),
        "verdict": verdict,
        "evidence": {
            "mr_url": pr.get("url", ""),
            "pipeline_url": ci.get("pipeline_url", ""),
            "ci_proof_url": declaration.get("ci_proof_url", ""),
            "cr_approval_link": declaration.get("cr_approval_link", ""),
            "reviewer": pr.get("reviewer", ""),
        },
        "gates_summary": {key: value.get("status") for key, value in gates.items()},
        "gates": gates,
        "blocking_reasons": blocking_reasons,
        "report_hint": verdict_label(verdict),
    }


def verdict_label(verdict: str) -> str:
    return {
        "ADMITTED": "准予提测",
        "REJECTED": "拒绝提测",
        "CONDITIONAL": "有条件通过",
        "PENDING": "待评估",
    }.get(verdict, verdict)


def evaluate_pr(pr: dict[str, Any]) -> dict[str, Any]:
    working = copy.deepcopy(pr)
    blocking_reasons: list[str] = []
    gate_1 = evaluate_gate_1(working, blocking_reasons)
    gate_2 = evaluate_gate_2(working, blocking_reasons)
    gate_3 = evaluate_gate_3(working, gate_1["status"], blocking_reasons)
    gate_4 = evaluate_gate_4(working)
    gates = {"gate_1": gate_1, "gate_2": gate_2, "gate_3": gate_3, "gate_4": gate_4}
    verdict = calculate_verdict(gates)
    if verdict != "REJECTED":
        blocking_reasons = []
    return summarize(working, gates, verdict, blocking_reasons)


def apply_evaluation(pr: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(pr)
    previous_verdict = updated.get("verdict")
    verdict = evaluation["verdict"]
    updated["gates"] = evaluation["gates"]
    updated["gates_summary"] = evaluation["gates_summary"]
    updated["verdict"] = verdict
    updated["blocking_reasons"] = evaluation["blocking_reasons"]
    updated["ai_percentage"] = number(updated.get("ai_usage", {}).get("percentage", updated.get("ai_percentage", 0)))
    updated["reviewer"] = updated.get("review", {}).get("reviewer", "")
    if previous_verdict != "REJECTED" and verdict == "REJECTED":
        updated["violations"] = integer(updated.get("violations")) + 1
    updated["last_updated"] = now_iso()
    history = list(updated.get("history", []))
    history.append(
        {
            "timestamp": updated["last_updated"],
            "event": "gate_evaluated",
            "details": f"门禁评估完成 -- {verdict_label(verdict)}（{verdict}）",
        }
    )
    updated["history"] = history
    return updated


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate CR-Vigil gates for one PR in a registry.")
    parser.add_argument("--registry", default="data/pr-registry.json", help="Path to pr-registry.json")
    parser.add_argument("--pr-id", required=True, help="PR ID to evaluate")
    parser.add_argument("--write", action="store_true", help="Write evaluation result back to registry")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry_path = Path(args.registry)
    try:
        registry = load_registry(registry_path)
        index, pr = find_pr(registry, args.pr_id)
        evaluation = evaluate_pr(pr)
        if args.write:
            registry["prs"][index] = apply_evaluation(pr, evaluation)
            registry["updated_at"] = registry["prs"][index]["last_updated"]
            save_registry(registry_path, registry)
            evaluation = evaluate_pr(registry["prs"][index])
        print(json.dumps(evaluation, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # pragma: no cover - CLI safeguard
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
