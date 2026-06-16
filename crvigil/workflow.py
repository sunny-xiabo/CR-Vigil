"""Stage-driven CR-Vigil workflows."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .evaluator import (
    apply_evaluation,
    evaluate_pr,
    find_pr,
    load_registry,
    save_registry,
)
from .events import append_event, append_pr_event
from .json_tools import validate_json_file, json_file_lock
from .renderer import render_admission, render_digest, render_trend
from .utils import ROOT
from .config import load_config, storage_int, sync_int
from .gitlab_collect import collect_mr
from .file_collect import collect_file
from .storage import workspace_root_for_registry, write_mr_record, write_mr_records
from .snapshots import (
    cleanup_snapshots,
    load_week_daily_snapshots,
    registry_from_snapshots,
    write_daily_snapshot,
    write_weekly_snapshot,
)


def emit(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)


def trim_history(pr: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    limit = storage_int(config, "history_limit_per_mr", 50)
    if limit > 0 and isinstance(pr.get("history"), list):
        pr["history"] = pr["history"][-limit:]
    return pr


def trim_registry_history(registry: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    registry["prs"] = [trim_history(pr, config) for pr in registry.get("prs", [])]
    return registry


def evaluate_one(registry_path: Path, pr_id: str, *, write: bool = True, config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config()
    with json_file_lock(registry_path):
        registry = load_registry(registry_path)
        index, pr = find_pr(registry, pr_id)
        result = evaluate_pr(pr)
        if write:
            registry["prs"][index] = trim_history(apply_evaluation(pr, result), config)
            registry["updated_at"] = registry["prs"][index]["last_updated"]
            root = workspace_root_for_registry(registry_path)
            write_mr_record(registry["prs"][index], root=root)
            append_pr_event(
                root,
                pr_id,
                "gate_evaluated",
                verdict=registry["prs"][index].get("verdict"),
                record_path=registry["prs"][index].get("record_path"),
            )
            save_registry(registry_path, registry)
    return result


def evaluate_open_prs(registry_path: Path, config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    config = config or load_config()
    with json_file_lock(registry_path):
        registry = load_registry(registry_path)
        results: list[dict[str, Any]] = []
        changed = False
        for index, pr in enumerate(registry.get("prs", [])):
            if pr.get("status") == "open":
                result = evaluate_pr(pr)
                registry["prs"][index] = trim_history(apply_evaluation(pr, result), config)
                results.append(result)
                changed = True
        if changed:
            registry["updated_at"] = registry["prs"][0].get("last_updated", registry.get("updated_at")) if registry.get("prs") else registry.get("updated_at")
            registry = trim_registry_history(registry, config)
            root = workspace_root_for_registry(registry_path)
            write_mr_records(registry, root=root)
            for result in results:
                pr_id = str(result.get("pr_id") or "")
                _, updated_pr = find_pr(registry, pr_id)
                append_pr_event(
                    root,
                    pr_id,
                    "gate_evaluated",
                    verdict=result.get("verdict"),
                    record_path=updated_pr.get("record_path"),
                )
            save_registry(registry_path, registry)
    return results


def should_sync(no_sync: bool) -> bool:
    return not no_sync and os.environ.get("CRVIGIL_MODE", "team") != "personal"


def git_command(args: list[str], cwd: Path = ROOT) -> tuple[bool, str]:
    try:
        completed = subprocess.run(["git", *args], cwd=str(cwd), text=True, capture_output=True, check=False)
    except OSError as exc:
        return False, str(exc)
    output = (completed.stdout + completed.stderr).strip()
    return completed.returncode == 0, output


def sync_pull(no_sync: bool = False) -> dict[str, Any]:
    if not should_sync(no_sync):
        return {"skipped": True, "reason": "personal mode or --no-sync"}
    ok, remote = git_command(["remote", "get-url", "origin"])
    if not ok:
        return {"skipped": True, "reason": "no git remote", "detail": remote}
    ok, branch = git_command(["rev-parse", "--abbrev-ref", "HEAD"])
    branch_name = branch.splitlines()[-1] if ok and branch else "master"
    ok, output = git_command(["pull", "--rebase", "origin", branch_name])
    return {"skipped": False, "ok": ok, "detail": output}


def sync_push(message: str, no_sync: bool = False, *, retry: int = 0) -> dict[str, Any]:
    if not should_sync(no_sync):
        return {"skipped": True, "ok": True, "status": "skipped", "reason": "personal mode or --no-sync"}
    add_ok, add_output = git_command(["add", "data/pr-registry.json", "data/mrs", "data/events", "data/snapshots", "reports/"])
    if not add_ok:
        return {"skipped": False, "ok": False, "status": "failed", "stage": "add", "detail": add_output}
    ok, diff = git_command(["diff", "--cached", "--quiet"])
    if ok:
        return {"skipped": True, "ok": True, "status": "skipped", "reason": "no changes"}
    commit_ok, commit_output = git_command(["commit", "-m", message])
    if not commit_ok:
        return {"skipped": False, "ok": False, "status": "failed", "stage": "commit", "detail": commit_output}
    ok, branch = git_command(["rev-parse", "--abbrev-ref", "HEAD"])
    branch_name = branch.splitlines()[-1] if ok and branch else "master"
    attempts = []
    for attempt in range(max(retry, 0) + 1):
        ok, output = git_command(["push", "origin", branch_name])
        attempts.append({"stage": "push", "attempt": attempt + 1, "ok": ok, "detail": output})
        if ok:
            return {"skipped": False, "ok": True, "status": "synced", "attempts": attempts, "detail": output}
        if attempt < retry:
            pull_ok, pull_output = git_command(["pull", "--rebase", "origin", branch_name])
            attempts.append({"stage": "retry_pull", "attempt": attempt + 1, "ok": pull_ok, "detail": pull_output})
            if not pull_ok:
                return {"skipped": False, "ok": False, "status": "failed", "stage": "retry_pull", "attempts": attempts, "detail": pull_output}
    return {"skipped": False, "ok": False, "status": "failed", "stage": "push", "attempts": attempts, "detail": attempts[-1]["detail"]}


def sync_summary(pull: dict[str, Any], push: dict[str, Any]) -> str:
    if push.get("status") == "failed" or (pull.get("ok") is False and not pull.get("skipped")):
        return "failed"
    if push.get("status") == "synced":
        return "synced"
    if push.get("skipped"):
        return "skipped"
    return "unknown"


def _workflow_setup(registry_path: Path, no_sync: bool, config_path: Path | None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    config = load_config(config_path)
    pull = sync_pull(no_sync)
    stage0 = validate_json_file(registry_path, repair=True, write=True) if registry_path.exists() else {"valid": True}
    return config, pull, stage0


def _workflow_finish(
    registry_path: Path,
    config: dict[str, Any],
    no_sync: bool,
    pull: dict[str, Any],
    stage0: dict[str, Any],
    command: str,
    commit_message: str,
    stage2: dict[str, Any],
    **extra: Any,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    workspace_root = workspace_root_for_registry(registry_path)
    snapshot_path = write_daily_snapshot(registry, config, root=workspace_root)
    removed_snapshots = cleanup_snapshots(config, root=workspace_root)
    push = sync_push(commit_message, no_sync, retry=sync_int(config, "push_retry", 1))
    push_ok = bool(push.get("skipped") or push.get("ok", False))
    result: dict[str, Any] = {
        "ok": push_ok,
        "command": command,
        "sync_status": sync_summary(pull, push),
        "stage0_json_check": stage0,
        "stage1_5_snapshot": {"snapshot_path": str(snapshot_path), "removed_snapshots": [str(path) for path in removed_snapshots]},
        "stage2": stage2,
        "stage3": {"pull": pull, "push": push},
    }
    result.update(extra)
    return result


def admit(
    url: str,
    registry_path: Path,
    output_root: Path,
    *,
    no_sync: bool = False,
    config_path: Path | None = None,
) -> dict[str, Any]:
    config, pull, stage0 = _workflow_setup(registry_path, no_sync, config_path)
    collected = collect_mr(url, registry_path)
    evaluation = evaluate_one(registry_path, collected["pr_id"], write=True, config=config)
    registry = load_registry(registry_path)
    report_path = render_admission(registry, collected["pr_id"], output_root, config=config)
    workspace_root = workspace_root_for_registry(registry_path)
    append_pr_event(workspace_root, collected["pr_id"], "report_rendered", command="admit", verdict=evaluation["verdict"], report_path=str(report_path))
    return _workflow_finish(
        registry_path, config, no_sync, pull, stage0,
        command="admit",
        commit_message=f"chore：同步 {collected['pr_id']} 提测评估（{evaluation['verdict']}）",
        stage2={"report_path": str(report_path)},
        stage1=evaluation,
        pr_id=collected["pr_id"],
        verdict=evaluation["verdict"],
        report_path=str(report_path),
        blocking_reasons=evaluation["blocking_reasons"],
    )


def admit_file(
    file_path: Path,
    registry_path: Path,
    output_root: Path,
    *,
    no_sync: bool = False,
    config_path: Path | None = None,
) -> dict[str, Any]:
    config, pull, stage0 = _workflow_setup(registry_path, no_sync, config_path)
    collected = collect_file(file_path, registry_path)
    evaluations = [evaluate_one(registry_path, pr_id, write=True, config=config) for pr_id in collected["pr_ids"]]
    registry = load_registry(registry_path)
    report_paths = [render_admission(registry, pr_id, output_root, config=config) for pr_id in collected["pr_ids"]]
    workspace_root = workspace_root_for_registry(registry_path)
    for report_path, evaluation in zip(report_paths, evaluations):
        append_pr_event(workspace_root, str(evaluation["pr_id"]), "report_rendered", command="admit-file", verdict=evaluation["verdict"], report_path=str(report_path))
    return _workflow_finish(
        registry_path, config, no_sync, pull, stage0,
        command="admit-file",
        commit_message=f"chore：同步文件提测评估（{collected['count']} 个 PR）",
        stage2={"report_paths": [str(path) for path in report_paths]},
        stage1={"source": collected["source"], "count": collected["count"], "evaluations": evaluations},
        pr_ids=collected["pr_ids"],
        verdicts={e["pr_id"]: e["verdict"] for e in evaluations},
        report_paths=[str(path) for path in report_paths],
    )


def digest(
    registry_path: Path,
    output_root: Path,
    *,
    no_sync: bool = False,
    config_path: Path | None = None,
) -> dict[str, Any]:
    config, pull, stage0 = _workflow_setup(registry_path, no_sync, config_path)
    evaluations = evaluate_open_prs(registry_path, config=config)
    registry = load_registry(registry_path)
    workspace_root = workspace_root_for_registry(registry_path)
    snapshot_registry = {"updated_at": registry.get("updated_at"), "prs": registry.get("prs", [])}
    report_path = render_digest(snapshot_registry, output_root, config=config)
    append_event(workspace_root, {"event": "report_rendered", "command": "digest", "report_path": str(report_path), "evaluated_count": len(evaluations)})
    return _workflow_finish(
        registry_path, config, no_sync, pull, stage0,
        command="digest",
        commit_message="chore：同步 CR-Vigil 日报",
        stage1_count=len(evaluations),
        stage2={"report_path": str(report_path)},
        report_path=str(report_path),
    )


def trend(
    registry_path: Path,
    output_root: Path,
    *,
    no_sync: bool = False,
    config_path: Path | None = None,
) -> dict[str, Any]:
    config, pull, stage0 = _workflow_setup(registry_path, no_sync, config_path)
    registry = load_registry(registry_path)
    workspace_root = workspace_root_for_registry(registry_path)
    snapshots = load_week_daily_snapshots(root=workspace_root)
    trend_registry = registry_from_snapshots(snapshots, registry)
    weekly_snapshot = write_weekly_snapshot(trend_registry, config, root=workspace_root)
    report_path = render_trend(trend_registry, output_root, config=config)
    append_event(workspace_root, {"event": "report_rendered", "command": "trend", "report_path": str(report_path), "snapshot_path": str(weekly_snapshot), "daily_snapshot_count": len(snapshots)})
    return _workflow_finish(
        registry_path, config, no_sync, pull, stage0,
        command="trend",
        commit_message="chore：同步 CR-Vigil 周报",
        stage1_5_snapshot_detail={"snapshot_path": str(weekly_snapshot), "daily_snapshot_count": len(snapshots)},
        stage2={"report_path": str(report_path)},
        report_path=str(report_path),
    )
