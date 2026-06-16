"""Markdown file collector for local CR-Vigil admission experiments."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .gitlab_collect import update_registry
from .utils import now_iso, number


class FileCollectError(RuntimeError):
    pass


def clean_value(value: str) -> str:
    value = value.strip().strip("*").strip()
    value = re.sub(r"（.*?）", "", value).strip()
    value = re.sub(r"\(.*?\)", "", value).strip()
    return value


def bool_zh(value: str, default: bool = False) -> bool:
    value = value.strip()
    if any(token in value for token in ["未", "否", "无", "FAIL", "失败"]):
        return False
    if any(token in value for token in ["是", "已", "提供", "提交", "确认", "勾选", "PASS", "通过"]):
        return True
    return default


def field(section: str, label: str, default: str = "") -> str:
    pattern = rf"^\s*-\s+(?:\*\*)?{re.escape(label)}(?:\*\*)?[：:]\s*(.+)$"
    match = re.search(pattern, section, re.MULTILINE)
    return clean_value(match.group(1)) if match else default


def first_iso(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2}|Z)?", value)
    return match.group(0) if match else None


def first_number(value: str, default: float = 0) -> float:
    match = re.search(r"\d+(?:\.\d+)?", value)
    return float(match.group(0)) if match else default


def parse_count_line(section: str, label: str) -> dict[str, Any]:
    line = field(section, label)
    total = first_number(line, 0)
    passed_match = re.search(r"通过\s*(\d+)", line)
    failed_match = re.search(r"失败\s*(\d+)", line)
    rate_match = re.search(r"通过率\s*([0-9]+(?:\.[0-9]+)?)%", line)
    if total == 0 and rate_match:
        total = 1
    rate = float(rate_match.group(1)) if rate_match else (100 if bool_zh(line) else 0)
    passed = int(passed_match.group(1)) if passed_match else (int(total) if rate == 100 and total else 0)
    failed = int(failed_match.group(1)) if failed_match else (0 if rate == 100 else max(int(total) - passed, 0))
    return {"total": int(total), "passed": passed, "failed": failed, "pass_rate": rate}


def parse_checklist(section: str) -> dict[str, bool | None]:
    if re.search(r"全部\s*12\s*项已勾选", section):
        return {f"ck_{i:02d}": True for i in range(1, 13)}
    checklist = {f"ck_{i:02d}": None for i in range(1, 13)}
    for ck, status in re.findall(r"\|\s*CK-(\d{2})\s*\|[^\n|]*\|\s*([^\n|]+)\|", section):
        checklist[f"ck_{ck}"] = bool_zh(status)
    return checklist


def parse_static_scan(section: str) -> dict[str, Any]:
    return {
        "tool": clean_value(field(section, "工具", "SonarQube")) or "SonarQube",
        "blocker_count": int(first_number(field(section, "阻断性问题"), 0)),
        "critical_count": int(first_number(field(section, "严重问题"), 0)),
        "warning_count": int(first_number(field(section, "警告"), 0)),
    }


def parse_ai_usage(section: str) -> dict[str, Any]:
    percentage = first_number(field(section, "AI 代码占比"), 0)
    tools = field(section, "使用的 AI 工具", "未知")
    modules = field(section, "AI 生成的主要模块", "未知")
    return {
        "used": bool_zh(field(section, "是否使用 AI"), percentage > 0),
        "declared": bool_zh(field(section, "是否已在 PR 中声明")),
        "percentage": percentage,
        "tools": [item.strip() for item in re.split(r"[、,，]", tools) if item.strip()] or ["未知"],
        "modules": [item.strip() for item in re.split(r"[、,，]", modules) if item.strip()] or ["未知"],
    }


def parse_review(section: str, author: str) -> dict[str, Any]:
    reviewer = field(section, "审查人")
    comments = int(first_number(field(section, "实质性评论数量"), 0))
    if re.search(r"形式主义.*不通过|LGTM", section, re.I) and comments <= 1:
        comments = 0
    return {
        "reviewer": reviewer,
        "reviewer_level": field(section, "审查人级别", "junior").lower(),
        "substantive_comments": comments,
        "review_approved_at": first_iso(field(section, "审查批准时间")),
        "checklist": parse_checklist(section),
    }


def parse_declaration(section: str, gate_1_has_ci: bool) -> dict[str, Any]:
    all_provided = "三项材料均已提供" in section
    self_checks_confirmed = "五项全部确认" in section
    submitted = bool_zh(field(section, "已提交"), all_provided or self_checks_confirmed)
    cr_approval_link = field(section, "CR 批准链接")
    if not bool_zh(cr_approval_link, bool(cr_approval_link)):
        cr_approval_link = ""
    return {
        "ci_proof_provided": bool_zh(field(section, "CI 通过证明"), all_provided or not gate_1_has_ci),
        "ci_proof_url": field(section, "流水线链接"),
        "cr_approval_link": cr_approval_link or ("file://local-review" if all_provided else ""),
        "self_inspection": {
            "submitted": submitted,
            "signed_by": field(section, "签字人"),
            "signed_date": first_iso(field(section, "签字日期")),
            "checks": {
                "ci_passed": bool_zh(field(section, "SI-01（CI 已通过）"), self_checks_confirmed),
                "cr_completed": bool_zh(field(section, "SI-02（CR 已完成）"), self_checks_confirmed),
                "boundary_verified": bool_zh(field(section, "SI-03（边界已验证）"), self_checks_confirmed),
                "self_tested": bool_zh(field(section, "SI-04（已自测）"), self_checks_confirmed),
                "no_known_blockers": bool_zh(field(section, "SI-05（无已知阻断缺陷）"), self_checks_confirmed),
            },
        },
    }


def parse_ci(section: str) -> tuple[str, dict[str, Any]]:
    pipeline_url = field(section, "流水线链接")
    unit_test = parse_count_line(section, "单元测试")
    smoke_test = parse_count_line(section, "冒烟测试")
    ci = {
        "pipeline_url": pipeline_url,
        "unit_test": unit_test,
        "coverage": {"incremental_coverage_pct": first_number(field(section, "增量代码覆盖率"), 0), "threshold": 70},
        "static_scan": parse_static_scan(section),
        "smoke_test": smoke_test,
    }
    has_ci = bool(pipeline_url) or unit_test["total"] > 0 or smoke_test["total"] > 0
    return ("enabled" if has_ci else "disabled"), ci


def split_pr_sections(text: str) -> list[tuple[str, str, str]]:
    matches = list(re.finditer(r"^##\s+([A-Za-z]+-\d+)[：:]\s*(.+)$", text, re.MULTILINE))
    sections: list[tuple[str, str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1), clean_value(match.group(2)), text[match.end() : end]))
    return sections


def build_records_from_markdown(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileCollectError(f"文件不存在: {path}")
    text = path.read_text(encoding="utf-8")
    sections = split_pr_sections(text)
    if not sections:
        raise FileCollectError(f"未在文件中找到 PR 片段: {path}")
    records = []
    timestamp = now_iso()
    for pr_id, fallback_title, section in sections:
        title = field(section, "标题", fallback_title)
        author = field(section, "开发人员")
        ci_mode, ci = parse_ci(section)
        review = parse_review(section, author)
        record = {
            "pr_id": pr_id,
            "title": title,
            "author": author,
            "url": field(section, "链接", str(path)),
            "created_at": first_iso(field(section, "创建时间")) or "",
            "updated_at": first_iso(field(section, "更新时间")) or "",
            "status": field(section, "状态", "open"),
            "source": "file",
            "ci_mode": ci_mode,
            "ai_usage": parse_ai_usage(section),
            "review": review,
            "ci": ci,
            "declaration": parse_declaration(section, ci_mode == "enabled"),
            "gates": {
                "gate_1": {"status": "PENDING", "details": {}},
                "gate_2": {"status": "PENDING", "details": {}},
                "gate_3": {"status": "PENDING", "details": {}},
                "gate_4": {"status": "N/A", "details": {}},
            },
            "gates_summary": {"gate_1": "PENDING", "gate_2": "PENDING", "gate_3": "PENDING", "gate_4": "N/A"},
            "verdict": "PENDING",
            "blocking_reasons": [],
            "ai_percentage": number(parse_ai_usage(section).get("percentage")),
            "reviewer": review["reviewer"],
            "violations": 0,
            "last_updated": timestamp,
            "history": [{"timestamp": timestamp, "event": "file_collected", "details": f"Data collected from {path}"}],
        }
        records.append(record)
    return records


def collect_file(path: Path, registry_path: Path) -> dict[str, Any]:
    records = build_records_from_markdown(path)
    for record in records:
        update_registry(record, registry_path)
    return {
        "source": str(path),
        "registry": str(registry_path),
        "count": len(records),
        "pr_ids": [record["pr_id"] for record in records],
    }
