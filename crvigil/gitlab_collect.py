"""GitLab MR collector implemented with Python standard library."""

from __future__ import annotations

import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evaluator import load_registry, save_registry
from .events import append_pr_event
from .json_tools import json_file_lock
from .storage import attach_record_path, workspace_root_for_registry, write_mr_record
from .utils import ROOT, now_iso


PER_PAGE = 100


class GitLabCollectError(RuntimeError):
    pass


def parse_mr_url(url: str) -> dict[str, str]:
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise GitLabCollectError(f"无法解析 MR URL: {url}")
    marker = "/-/merge_requests/"
    if marker not in parsed.path:
        raise GitLabCollectError("MR URL 必须包含 /-/merge_requests/<iid>")
    project_path, iid = parsed.path.split(marker, 1)
    project_path = project_path.strip("/")
    iid = iid.strip("/").split("/")[0]
    if not project_path or not iid.isdigit():
        raise GitLabCollectError(f"无法解析项目路径或 MR 编号: {url}")
    host = f"{parsed.scheme}://{parsed.netloc}"
    return {
        "host": host,
        "project_path": project_path,
        "project_id": urllib.parse.quote(project_path, safe=""),
        "iid": iid,
        "project_short": project_path.split("/")[-1],
    }


class GitLabClient:
    def __init__(self, host: str, token: str | None = None, timeout: int = 30):
        self.host = host.rstrip("/")
        self.api_base = f"{self.host}/api/v4"
        self.token = token or os.environ.get("GITLAB_TOKEN")
        self.timeout = timeout
        if not self.token:
            raise GitLabCollectError("未设置 GITLAB_TOKEN 环境变量")
        self.ssl_context = self.build_ssl_context()

    def build_ssl_context(self):
        verify = os.environ.get("CRVIGIL_SSL_VERIFY", "true").lower()
        if verify in {"0", "false", "no", "off"}:
            return ssl._create_unverified_context()
        cafile = os.environ.get("CRVIGIL_CA_FILE")
        if not cafile and Path("/etc/ssl/cert.pem").exists():
            cafile = "/etc/ssl/cert.pem"
        if cafile:
            return ssl.create_default_context(cafile=cafile)
        return ssl.create_default_context()

    def request(self, endpoint: str) -> tuple[Any, dict[str, str]]:
        url = f"{self.api_base}{endpoint}"
        request = urllib.request.Request(
            url,
            headers={"PRIVATE-TOKEN": self.token, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout, context=self.ssl_context) as response:
                body = response.read().decode("utf-8")
                headers = {key.lower(): value for key, value in response.headers.items()}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise GitLabCollectError(f"GitLab API 返回 HTTP {exc.code}: {url}; {body[:300]}") from exc
        except urllib.error.URLError as exc:
            raise GitLabCollectError(f"GitLab API 请求失败: {url}; {exc.reason}") from exc
        try:
            return json.loads(body), headers
        except json.JSONDecodeError as exc:
            raise GitLabCollectError(f"GitLab API 响应不是合法 JSON: {url}") from exc

    def get_single(self, endpoint: str) -> Any:
        data, _ = self.request(endpoint)
        return data

    def get_paginated(self, endpoint: str) -> list[Any]:
        page = 1
        total_pages = 1
        result: list[Any] = []
        join_char = "&" if "?" in endpoint else "?"
        while page <= total_pages:
            data, headers = self.request(f"{endpoint}{join_char}per_page={PER_PAGE}&page={page}")
            if not isinstance(data, list):
                raise GitLabCollectError(f"分页接口返回非数组: {endpoint}")
            result.extend(data)
            total_pages = int(headers.get("x-total-pages") or "1")
            page += 1
        return result

    def get_text(self, endpoint: str) -> str:
        url = f"{self.api_base}{endpoint}"
        request = urllib.request.Request(url, headers={"PRIVATE-TOKEN": self.token})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout, context=self.ssl_context) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception:
            return ""


def parse_ai_declaration(description: str) -> dict[str, Any]:
    negated = bool(re.search(r"(不涉及|未使用|没有使用|未借助|不包含|未利用|无 AI|未 AI|No AI|Without AI).*AI|AI.*(不涉及|未使用|没有使用|未借助|不包含|未利用|未参与)", description, re.I))
    positive = bool(re.search(r"AI.*(辅助|声明|使用|占比|生成)|(辅助|声明|使用|占比|生成).*AI", description, re.I)) and not negated
    declared = positive
    percentage = 0
    used: bool | str = "unknown"
    tools = "未知"
    modules = "未知"
    if declared:
        pct_match = re.search(r"AI[^0-9]*([0-9]+(?:\.[0-9]+)?)%", description, re.I)
        if pct_match:
            percentage = int(float(pct_match.group(1)))
            used = percentage > 0
        else:
            used = False
        tools_match = re.search(r"(使用工具|AI.*工具)\s*[：:]\s*(.+)", description, re.I)
        modules_match = re.search(r"(主要模块|生成.*模块|涉及.*模块|AI.*模块)\s*[：:]\s*(.+)", description, re.I)
        if tools_match:
            tools = tools_match.group(2).strip()
        if modules_match:
            modules = modules_match.group(2).strip()
    return {
        "used": used if isinstance(used, bool) else True,
        "declared": declared,
        "percentage": percentage,
        "tools": [tools],
        "modules": [modules],
    }


def job_patterns() -> dict[str, str]:
    patterns = {
        "unit_test": r"unit.?test|ut[^a-z]",
        "coverage": r"coverage|cov[^a-z]",
        "static_scan": r"sonar|lint|static.?scan|code.?scan",
        "smoke_test": r"smoke",
    }
    raw = os.environ.get("CRVIGIL_JOB_MAPPING")
    if raw:
        try:
            custom = json.loads(raw)
            for key in patterns:
                if custom.get(key):
                    patterns[key] = str(custom[key])
        except json.JSONDecodeError:
            pass
    return patterns


def collect_ci(client: GitLabClient, project_id: str, iid: str) -> tuple[str, dict[str, Any]]:
    ci = {
        "pipeline_url": "",
        "unit_test": {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0},
        "coverage": {"incremental_coverage_pct": 0, "threshold": 70},
        "static_scan": {"blocker_count": 0, "critical_count": 0, "warning_count": 0, "tool": "sonar", "detected": False},
        "smoke_test": {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0},
    }
    try:
        pipelines = client.get_paginated(f"/projects/{project_id}/merge_requests/{iid}/pipelines")
    except GitLabCollectError:
        return "collect_error", ci
    if not pipelines:
        return "disabled", ci

    pipeline = pipelines[0]
    pipeline_id = pipeline.get("id")
    ci["pipeline_url"] = pipeline.get("web_url", "")
    if not pipeline_id:
        return "enabled", ci

    try:
        jobs = client.get_paginated(f"/projects/{project_id}/pipelines/{pipeline_id}/jobs")
    except GitLabCollectError:
        return "collect_error", ci

    patterns = job_patterns()
    for job in jobs:
        name = str(job.get("name", ""))
        status = str(job.get("status", ""))
        if re.search(patterns["unit_test"], name, re.I):
            ok = status == "success"
            ci["unit_test"] = {"total": 1, "passed": 1 if ok else 0, "failed": 0 if ok else 1, "pass_rate": 100 if ok else 0}
        if re.search(patterns["coverage"], name, re.I):
            if status == "success":
                trace = client.get_text(f"/projects/{project_id}/jobs/{job.get('id')}/trace") if job.get("id") else ""
                match = re.findall(r"Coverage[:\s]*([0-9]+(?:\.[0-9]+)?)%", trace, re.I)
                if match:
                    ci["coverage"]["incremental_coverage_pct"] = float(match[-1])
                elif pipeline.get("coverage"):
                    ci["coverage"]["incremental_coverage_pct"] = float(str(pipeline["coverage"]).rstrip("%"))
        if re.search(patterns["static_scan"], name, re.I):
            ci["static_scan"]["detected"] = True
            if status == "success":
                ci["static_scan"]["blocker_count"] = 0
                ci["static_scan"]["critical_count"] = 0
        if re.search(patterns["smoke_test"], name, re.I):
            ok = status == "success"
            ci["smoke_test"] = {"total": 1, "passed": 1 if ok else 0, "failed": 0 if ok else 1, "pass_rate": 100 if ok else 0}
    return "enabled", ci


def substantive_comment_count(notes: list[dict[str, Any]]) -> int:
    count = 0
    for note in notes:
        if note.get("system") is True:
            continue
        body = str(note.get("body", ""))
        clean = re.sub(r"LGTM|Looks Good|OK|\+1|好的|没问题|通过|Approved", "", body, flags=re.I)
        clean = re.sub(r"\s+", "", clean)
        if len(clean) >= 10:
            count += 1
    return count


def reviewer_mapped_level(reviewer: str) -> str | None:
    path = ROOT / "data" / "reviewer-levels.json"
    if not reviewer or not path.exists():
        return None
    try:
        levels = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    lowered = {str(key).lower(): value for key, value in levels.items()}
    return lowered.get(reviewer.lower())


def reviewer_level(reviewer: str) -> str:
    return reviewer_mapped_level(reviewer) or "junior"


def collect_review(client: GitLabClient, project_id: str, iid: str, author: str) -> dict[str, Any]:
    reviewer = ""
    approved_at = None
    try:
        notes = client.get_paginated(f"/projects/{project_id}/merge_requests/{iid}/notes?sort=asc")
    except GitLabCollectError:
        notes = []
    for note in notes:
        if note.get("system") is not True:
            name = note.get("author", {}).get("name", "")
            if name and name != author:
                reviewer = name
                break

    try:
        approvals = client.get_single(f"/projects/{project_id}/merge_requests/{iid}/approvals")
        approved_by = approvals.get("approved_by", [])
        if approved_by:
            reviewer = ",".join(item.get("user", {}).get("name", "") for item in approved_by if item.get("user"))
            approved_at = approved_by[0].get("approved_at")
    except GitLabCollectError:
        pass

    mapped = reviewer_mapped_level(reviewer) if reviewer else None
    if mapped is not None:
        level = mapped
    else:
        level = "unknown"
    return {
        "reviewer": reviewer,
        "reviewer_level": level,
        "substantive_comments": substantive_comment_count(notes),
        "review_approved_at": approved_at,
        "checklist": {f"ck_{i:02d}": None for i in range(1, 13)},
    }


def build_record(url: str, registry_path: Path = ROOT / "data" / "pr-registry.json") -> tuple[dict[str, Any], dict[str, Any]]:
    info = parse_mr_url(url)
    client = GitLabClient(info["host"])
    mr = client.get_single(f"/projects/{info['project_id']}/merge_requests/{info['iid']}")
    ci_mode, ci = collect_ci(client, info["project_id"], info["iid"])
    ai_usage = parse_ai_declaration(mr.get("description") or "")
    review = collect_review(client, info["project_id"], info["iid"], mr.get("author", {}).get("name", ""))
    pr_id = f"MR-{info['iid']}-{info['project_short']}"
    timestamp = now_iso()
    record = {
        "pr_id": pr_id,
        "title": mr.get("title", ""),
        "author": mr.get("author", {}).get("name", ""),
        "url": mr.get("web_url", url),
        "created_at": mr.get("created_at", ""),
        "updated_at": mr.get("updated_at", ""),
        "status": mr.get("state", ""),
        "ci_mode": ci_mode,
        "ai_usage": ai_usage,
        "review": review,
        "ci": ci,
        "declaration": {
            "ci_proof_provided": False,
            "ci_proof_url": ci.get("pipeline_url", ""),
            "cr_approval_link": mr.get("web_url", url),
            "self_inspection": {
                "submitted": False,
                "signed_by": "",
                "signed_date": None,
                "checks": {
                    "ci_passed": False,
                    "cr_completed": False,
                    "boundary_verified": False,
                    "self_tested": False,
                    "no_known_blockers": False,
                },
            },
        },
        "gates": {
            "gate_1": {"status": "PENDING", "details": {}},
            "gate_2": {"status": "PENDING", "details": {}},
            "gate_3": {"status": "PENDING", "details": {}},
            "gate_4": {"status": "N/A", "details": {}},
        },
        "gates_summary": {"gate_1": "PENDING", "gate_2": "PENDING", "gate_3": "PENDING", "gate_4": "N/A"},
        "verdict": "PENDING",
        "blocking_reasons": [],
        "ai_percentage": ai_usage["percentage"],
        "reviewer": review["reviewer"],
        "violations": 0,
        "last_updated": timestamp,
        "history": [{"timestamp": timestamp, "event": "data_collected", "details": "Data collected from GitLab API"}],
    }
    return record, {"host": info["host"], "project_path": info["project_path"], "iid": info["iid"]}


def update_registry(record: dict[str, Any], registry_path: Path = ROOT / "data" / "pr-registry.json") -> dict[str, Any]:
    with json_file_lock(registry_path):
        root = workspace_root_for_registry(registry_path)
        attach_record_path(record, root)
        registry = load_registry(registry_path) if registry_path.exists() else {"updated_at": "", "prs": []}
        updated = False
        for index, existing in enumerate(registry.get("prs", [])):
            if existing.get("pr_id") == record["pr_id"]:
                record["violations"] = existing.get("violations", 0)
                record["history"] = list(existing.get("history", [])) + list(record.get("history", []))
                attach_record_path(record, root)
                registry["prs"][index] = record
                updated = True
                break
        if not updated:
            registry.setdefault("prs", []).append(record)
        registry["updated_at"] = record["last_updated"]
        write_mr_record(record, root=root)
        append_pr_event(
            root,
            record["pr_id"],
            "data_collected",
            source=record.get("source", "gitlab"),
            verdict=record.get("verdict"),
            record_path=record.get("record_path"),
        )
        save_registry(registry_path, registry)
    return registry


def collect_mr(url: str, registry_path: Path = ROOT / "data" / "pr-registry.json") -> dict[str, Any]:
    record, meta = build_record(url, registry_path)
    update_registry(record, registry_path)
    return {
        "pr_id": record["pr_id"],
        "title": record["title"],
        "author": record["author"],
        "status": record["status"],
        "ci_mode": record["ci_mode"],
        "registry": str(registry_path),
        "meta": meta,
    }
