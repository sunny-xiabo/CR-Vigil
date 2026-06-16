"""Append-only event log for CR-Vigil workflows."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .json_tools import json_file_lock
from .utils import ROOT, now_iso


def events_dir(root: Path = ROOT) -> Path:
    return root / "data" / "events"


def event_log_path(root: Path = ROOT, timestamp: str | None = None) -> Path:
    timestamp = timestamp or now_iso()
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        name = parsed.strftime("%Y-%m")
    except ValueError:
        name = now_iso()[:7]
    return events_dir(root) / f"{name}.jsonl"


def append_event(root: Path, event: dict[str, Any]) -> Path:
    event = dict(event)
    event.setdefault("timestamp", now_iso())
    path = event_log_path(root=root, timestamp=str(event["timestamp"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with json_file_lock(path):
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    return path


def append_pr_event(root: Path, pr_id: str, event: str, **fields: Any) -> Path:
    payload = {"event": event, "pr_id": pr_id, **fields}
    return append_event(root, payload)
