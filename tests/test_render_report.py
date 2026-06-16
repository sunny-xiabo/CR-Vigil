import json
import re
import tempfile
import unittest
from pathlib import Path

from crvigil.evaluator import load_registry
from crvigil import renderer

ROOT = Path(__file__).resolve().parents[1]


class RenderReportTest(unittest.TestCase):
    def load_registry(self):
        return load_registry(ROOT / "data/pr-registry.json")

    def test_admission_report_filename_and_placeholders(self):
        registry = self.load_registry()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = renderer.render_admission(registry, "PR-001", Path(temp_dir))
            self.assertRegex(path.name, r"^PR-001-admission-\d{4}-\d{2}-\d{2}\.md$")
            content = path.read_text(encoding="utf-8")
            self.assertIn("准入判定：ADMITTED", content)
            self.assertNotRegex(content, r"\{[A-Z0-9_]+\}")

    def test_digest_only_counts_open_prs(self):
        registry = {
            "updated_at": "2026-06-12T09:30:00+08:00",
            "prs": [
                {
                    "pr_id": "OPEN-1",
                    "title": "open pr",
                    "author": "dev",
                    "status": "open",
                    "verdict": "ADMITTED",
                    "ai_usage": {"percentage": 10},
                    "gates_summary": {"gate_1": "N/A", "gate_2": "PASS", "gate_3": "PASS"},
                },
                {
                    "pr_id": "MERGED-1",
                    "title": "merged pr",
                    "author": "dev",
                    "status": "merged",
                    "verdict": "REJECTED",
                    "ai_usage": {"percentage": 90},
                    "gates_summary": {"gate_1": "FAIL", "gate_2": "FAIL", "gate_3": "FAIL"},
                },
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = renderer.render_digest(registry, Path(temp_dir))
            content = path.read_text(encoding="utf-8")
            self.assertIn("**活跃 PR 总数**：1", content)
            self.assertIn("🟢 ADMITTED", content)
            self.assertIn("🟢 PASS", content)
            self.assertIn("OPEN-1", content)
            self.assertNotIn("MERGED-1 |", content)

    def test_trend_handles_missing_history(self):
        registry = self.load_registry()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = renderer.render_trend(registry, Path(temp_dir))
            content = path.read_text(encoding="utf-8")
            self.assertRegex(path.name, r"^weekly-trend-\d{4}-\d{2}-\d{2}\.md$")
            self.assertIn("暂无历史数据", content)
            self.assertNotRegex(content, r"\{[A-Z0-9_]+\}")
            self.assertIn("🔴 50 `[█████░░░░░]`", content)

    def test_admission_refuses_to_render_before_stage1_completion(self):
        registry = {
            "updated_at": "2026-06-12T09:30:00+08:00",
            "prs": [
                {
                    "pr_id": "PENDING-1",
                    "title": "pending pr",
                    "author": "dev",
                    "status": "open",
                    "verdict": "PENDING",
                    "gates_summary": {"gate_1": "PENDING", "gate_2": "PENDING", "gate_3": "PENDING"},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "阶段 1 未完成"):
                renderer.render_admission(registry, "PENDING-1", Path(temp_dir))


if __name__ == "__main__":
    unittest.main()
