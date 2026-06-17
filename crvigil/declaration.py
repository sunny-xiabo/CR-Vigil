"""Declaration template generator for CR-Vigil."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .gitlab_collect import GitLabClient, parse_mr_url, parse_ai_declaration, collect_ci, collect_review
from .renderer.helpers import read_template, replace_placeholders
from .utils import now_iso


def generate_declaration_markdown(
    ai_usage: dict[str, Any],
    reviewer: str,
    cr_approval_link: str,
) -> str:
    if ai_usage.get("declared") and ai_usage.get("percentage", 0) > 0:
        tools = "、".join(ai_usage.get("tools", [])) or "未知"
        modules = "、".join(ai_usage.get("modules", [])) or "未知"
        ai_declaration = (
            f"- [x] 本 MR 使用了 AI 辅助，AI 生成代码占比约：{ai_usage['percentage']:.0f}%\n"
            f"  - 使用工具：{tools}\n"
            f"  - AI 生成的主要模块：{modules}"
        )
    else:
        ai_declaration = (
            "- [ ] 本 MR 未使用 AI 辅助\n"
            "- [ ] 本 MR 使用了 AI 辅助，AI 生成代码占比约：___%\n"
            "  - 使用工具：\n"
            "  - AI 生成的主要模块："
        )

    template = read_template("declaration-template.md")
    values = {
        "AI_DECLARATION": ai_declaration,
        "REVIEWER": reviewer or "待填写",
        "CR_APPROVAL_LINK": cr_approval_link or "待填写",
    }
    return replace_placeholders(template, values)


def build_declaration(url: str) -> dict[str, Any]:
    info = parse_mr_url(url)
    client = GitLabClient(info["host"])
    mr = client.get_single(f"/projects/{info['project_id']}/merge_requests/{info['iid']}")

    author = mr.get("author", {}).get("name", "")
    description = mr.get("description") or ""
    ai_usage = parse_ai_declaration(description)
    ci_mode, ci = collect_ci(client, info["project_id"], info["iid"])
    review = collect_review(client, info["project_id"], info["iid"], author)

    reviewer = review.get("reviewer", "")
    cr_approval_link = ""
    try:
        approvals = client.get_single(f"/projects/{info['project_id']}/merge_requests/{info['iid']}/approvals")
        approved_by = approvals.get("approved_by", [])
        if approved_by:
            cr_approval_link = mr.get("web_url", url)
    except Exception:
        pass

    declaration_markdown = generate_declaration_markdown(ai_usage, reviewer, cr_approval_link)

    return {
        "pr_id": f"MR-{info['iid']}-{info['project_short']}",
        "mr_url": mr.get("web_url", url),
        "title": mr.get("title", ""),
        "author": author,
        "reviewer": reviewer,
        "ci_mode": ci_mode,
        "ci_proof_url": ci.get("pipeline_url", ""),
        "ai_usage": {
            "declared": ai_usage.get("declared", False),
            "percentage": ai_usage.get("percentage", 0),
            "tools": ai_usage.get("tools", []),
            "modules": ai_usage.get("modules", []),
        },
        "declaration_markdown": declaration_markdown,
    }
