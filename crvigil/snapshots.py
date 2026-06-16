"""Snapshot persistence for digest and trend reports."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .config import report_profile, storage_int
from .json_tools import save_json_file

from .utils import ROOT


def now_local() -> datetime:
    return datetime.now().astimezone()


def snapshots_dir(root: Path = ROOT) -> Path:
    return root / "data" / "snapshots"


def daily_snapshot_path(day: datetime | None = None, root: Path = ROOT) -> Path:
    day = day or now_local()
    return snapshots_dir(root) / f"daily-{day.strftime('%Y-%m-%d')}.json"


def weekly_snapshot_path(day: datetime | None = None, root: Path = ROOT) -> Path:
    day = day or now_local()
    week_start = day - timedelta(days=day.weekday())
    return snapshots_dir(root) / f"weekly-{week_start.strftime('%Y-W%V')}.json"


def summarize_registry(registry: dict[str, Any]) -> dict[str, Any]:
    prs = registry.get("prs", [])
    return {
        "total_pr_count": len(prs),
        "active_pr_count": sum(1 for pr in prs if pr.get("status") == "open"),
        "admitted_count": sum(1 for pr in prs if pr.get("verdict") == "ADMITTED"),
        "conditional_count": sum(1 for pr in prs if pr.get("verdict") == "CONDITIONAL"),
        "rejected_count": sum(1 for pr in prs if pr.get("verdict") == "REJECTED"),
        "pending_count": sum(1 for pr in prs if pr.get("verdict") == "PENDING"),
    }


def compact_history(pr: dict[str, Any]) -> list[dict[str, Any]]:
    compact = []
    for item in pr.get("history", []):
        if item.get("event") == "gate_evaluated":
            compact.append(
                {
                    "timestamp": item.get("timestamp", ""),
                    "event": item.get("event", ""),
                    "details": item.get("details", ""),
                }
            )
    return compact[-5:]


def snapshot_pr(pr: dict[str, Any]) -> dict[str, Any]:
    review = pr.get("review", {})
    ai_usage = pr.get("ai_usage", {})
    return {
        "pr_id": pr.get("pr_id"),
        "title": pr.get("title", ""),
        "author": pr.get("author", ""),
        "status": pr.get("status", ""),
        "url": pr.get("url", ""),
        "created_at": pr.get("created_at", ""),
        "updated_at": pr.get("updated_at", ""),
        "last_updated": pr.get("last_updated", ""),
        "record_path": pr.get("record_path", ""),
        "verdict": pr.get("verdict", "PENDING"),
        "gates_summary": pr.get("gates_summary", {}),
        "gates": pr.get("gates", {}),
        "blocking_reasons": pr.get("blocking_reasons", []),
        "ai_usage": {
            "used": ai_usage.get("used", False),
            "declared": ai_usage.get("declared", False),
            "percentage": ai_usage.get("percentage", pr.get("ai_percentage", 0)),
            "tools": ai_usage.get("tools", []),
        },
        "review": {
            "reviewer": review.get("reviewer", ""),
            "substantive_comments": review.get("substantive_comments", 0),
            "review_approved_at": review.get("review_approved_at"),
        },
        "violations": pr.get("violations", 0),
        "history": compact_history(pr),
    }


def snapshot_prs(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return [snapshot_pr(pr) for pr in registry.get("prs", [])]


def build_daily_snapshot(registry: dict[str, Any], config: dict[str, Any], day: datetime | None = None) -> dict[str, Any]:
    day = day or now_local()
    return {
        "snapshot_type": "daily",
        "date": day.strftime("%Y-%m-%d"),
        "generated_at": day.isoformat(timespec="seconds"),
        "report_profile": report_profile(config, "daily"),
        "summary": summarize_registry(registry),
        "prs": snapshot_prs(registry),
    }


def write_daily_snapshot(registry: dict[str, Any], config: dict[str, Any], root: Path = ROOT) -> Path:
    snapshot = build_daily_snapshot(registry, config)
    path = daily_snapshot_path(root=root)
    save_json_file(path, snapshot)
    return path


def load_week_daily_snapshots(day: datetime | None = None, root: Path = ROOT) -> list[dict[str, Any]]:
    day = day or now_local()
    week_start = day - timedelta(days=day.weekday())
    snapshots: list[dict[str, Any]] = []
    for offset in range(7):
        path = daily_snapshot_path(week_start + timedelta(days=offset), root=root)
        if path.exists():
            import json

            snapshots.append(json.loads(path.read_text(encoding="utf-8")))
    return snapshots


def load_yesterday_snapshot(day: datetime | None = None, root: Path = ROOT) -> dict[str, Any] | None:
    day = day or now_local()
    yesterday = day - timedelta(days=1)
    path = daily_snapshot_path(yesterday, root=root)
    if path.exists():
        import json
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def registry_from_snapshots(snapshots: list[dict[str, Any]], fallback: dict[str, Any]) -> dict[str, Any]:
    if not snapshots:
        return fallback
    latest_by_pr: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        for pr in snapshot.get("prs", []):
            if pr.get("pr_id"):
                latest_by_pr[pr["pr_id"]] = pr
    return {"updated_at": snapshots[-1].get("generated_at", ""), "prs": list(latest_by_pr.values())}


def write_weekly_snapshot(registry: dict[str, Any], config: dict[str, Any], root: Path = ROOT) -> Path:
    snapshot = {
        "snapshot_type": "weekly",
        "generated_at": now_local().isoformat(timespec="seconds"),
        "report_profile": report_profile(config, "weekly"),
        "summary": summarize_registry(registry),
        "prs": snapshot_prs(registry),
    }
    path = weekly_snapshot_path(root=root)
    save_json_file(path, snapshot)
    return path


def cleanup_snapshots(config: dict[str, Any], root: Path = ROOT, day: datetime | None = None) -> list[Path]:
    """Delete expired CR-Vigil snapshots according to storage retention config."""

    day = day or now_local()
    daily_days = storage_int(config, "daily_snapshot_retention_days", 30)
    weekly_weeks = storage_int(config, "weekly_snapshot_retention_weeks", 12)
    removed: list[Path] = []
    directory = snapshots_dir(root)
    if not directory.exists():
        return removed

    daily_cutoff = (day - timedelta(days=daily_days)).date()
    weekly_cutoff = (day - timedelta(weeks=weekly_weeks)).date()
    for path in directory.iterdir():
        if not path.is_file():
            continue
        if path.name.startswith("daily-") and path.suffix == ".json":
            try:
                snapshot_day = datetime.strptime(path.stem.removeprefix("daily-"), "%Y-%m-%d").date()
            except ValueError:
                continue
            if snapshot_day < daily_cutoff:
                path.unlink()
                removed.append(path)
        elif path.name.startswith("weekly-") and path.suffix == ".json":
            try:
                snapshot_week = datetime.strptime(path.stem.removeprefix("weekly-") + "-1", "%G-W%V-%u").date()
            except ValueError:
                continue
            if snapshot_week < weekly_cutoff:
                path.unlink()
                removed.append(path)
    return removed


def load_previous_weekly_snapshot(day: datetime | None = None, root: Path = ROOT) -> dict[str, Any] | None:
    day = day or now_local()
    last_week_day = day - timedelta(days=7)
    path = weekly_snapshot_path(last_week_day, root=root)
    if path.exists():
        import json
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None
