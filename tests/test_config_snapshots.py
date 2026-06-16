import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from crvigil.config import load_config, section_enabled
from crvigil.snapshots import build_daily_snapshot, cleanup_snapshots, registry_from_snapshots, write_daily_snapshot


class ConfigSnapshotsTest(unittest.TestCase):
    def test_load_config_merges_report_sections(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "cr-vigil.yml"
            path.write_text(
                """
reports:
  daily:
    sections:
      pending_prs: true
      detailed_gate_reasons: true
""",
                encoding="utf-8",
            )
            config = load_config(path)
            self.assertTrue(section_enabled(config, "daily", "pending_prs", False))
            self.assertTrue(section_enabled(config, "daily", "detailed_gate_reasons", False))
            self.assertTrue(section_enabled(config, "daily", "action_items", True))

    def test_daily_snapshot_contains_registry_prs(self):
        registry = {"updated_at": "now", "prs": [{"pr_id": "PR-1", "status": "open", "verdict": "ADMITTED"}]}
        snapshot = build_daily_snapshot(registry, load_config(Path("/not/exist.yml")))
        self.assertEqual(snapshot["snapshot_type"], "daily")
        self.assertEqual(snapshot["summary"]["active_pr_count"], 1)
        self.assertEqual(snapshot["prs"][0]["pr_id"], "PR-1")

    def test_daily_snapshot_uses_compact_pr_shape(self):
        registry = {
            "updated_at": "now",
            "prs": [
                {
                    "pr_id": "PR-1",
                    "status": "open",
                    "verdict": "REJECTED",
                    "record_path": "data/mrs/PR-1.json",
                    "ci": {"pipeline_url": "heavy"},
                    "declaration": {"self_inspection": {"checks": {"x": True}}},
                    "ai_usage": {"used": True, "declared": True, "percentage": 20, "tools": ["Copilot"]},
                    "review": {"reviewer": "lisi", "substantive_comments": 2, "review_approved_at": "2026-06-12T09:00:00+08:00"},
                    "gates": {"gate_1": {"status": "PASS", "details": {}}},
                    "gates_summary": {"gate_1": "PASS"},
                    "blocking_reasons": ["blocked"],
                    "history": [{"timestamp": str(i), "event": "gate_evaluated", "details": "x"} for i in range(8)],
                }
            ],
        }
        snapshot = build_daily_snapshot(registry, load_config(Path("/not/exist.yml")))
        pr = snapshot["prs"][0]
        self.assertEqual(pr["record_path"], "data/mrs/PR-1.json")
        self.assertEqual(pr["ai_usage"]["percentage"], 20)
        self.assertEqual(pr["review"]["reviewer"], "lisi")
        self.assertNotIn("ci", pr)
        self.assertNotIn("declaration", pr)
        self.assertEqual(len(pr["history"]), 5)

    def test_write_daily_snapshot_uses_given_root(self):
        registry = {"updated_at": "now", "prs": []}
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_daily_snapshot(registry, load_config(Path("/not/exist.yml")), root=Path(temp_dir))
            self.assertTrue(path.exists())
            self.assertTrue(str(path).startswith(temp_dir))
            with path.open(encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["snapshot_type"], "daily")

    def test_registry_from_snapshots_uses_latest_pr_state(self):
        snapshots = [
            {"generated_at": "day1", "prs": [{"pr_id": "PR-1", "verdict": "PENDING"}]},
            {"generated_at": "day2", "prs": [{"pr_id": "PR-1", "verdict": "ADMITTED"}]},
        ]
        registry = registry_from_snapshots(snapshots, {"prs": []})
        self.assertEqual(registry["prs"][0]["verdict"], "ADMITTED")

    def test_cleanup_snapshots_removes_expired_known_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_dir = Path(temp_dir) / "data" / "snapshots"
            snapshot_dir.mkdir(parents=True)
            old_daily = snapshot_dir / "daily-2026-01-01.json"
            fresh_daily = snapshot_dir / "daily-2026-06-15.json"
            old_weekly = snapshot_dir / "weekly-2026-W01.json"
            unknown = snapshot_dir / "notes.json"
            for path in [old_daily, fresh_daily, old_weekly, unknown]:
                path.write_text("{}", encoding="utf-8")

            removed = cleanup_snapshots(
                {
                    "storage": {
                        "daily_snapshot_retention_days": 30,
                        "weekly_snapshot_retention_weeks": 12,
                    }
                },
                root=Path(temp_dir),
                day=datetime(2026, 6, 16),
            )

            self.assertIn(old_daily, removed)
            self.assertIn(old_weekly, removed)
            self.assertFalse(old_daily.exists())
            self.assertFalse(old_weekly.exists())
            self.assertTrue(fresh_daily.exists())
            self.assertTrue(unknown.exists())


if __name__ == "__main__":
    unittest.main()
