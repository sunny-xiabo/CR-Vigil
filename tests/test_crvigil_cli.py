import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from crvigil.cli import main
from crvigil.gitlab_collect import parse_mr_url
from crvigil.workflow import sync_push


ROOT = Path(__file__).resolve().parents[1]


class CrvigilCliTest(unittest.TestCase):
    def test_parse_gitlab_mr_url(self):
        parsed = parse_mr_url("https://gitlab.miotech.com/miotech-application/esghub/test/llm-testgen/-/merge_requests/3")
        self.assertEqual(parsed["host"], "https://gitlab.miotech.com")
        self.assertEqual(parsed["project_path"], "miotech-application/esghub/test/llm-testgen")
        self.assertEqual(parsed["iid"], "3")
        self.assertEqual(parsed["project_short"], "llm-testgen")

    def test_validate_command_outputs_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "registry.json"
            registry.write_text('{"updated_at": "now", "prs": []}', encoding="utf-8")
            out = StringIO()
            with redirect_stdout(out):
                rc = main(["--registry", str(registry), "validate"])
            self.assertEqual(rc, 0)
            result = json.loads(out.getvalue())
            self.assertTrue(result["valid"])

    def test_evaluate_command_can_write_temp_registry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "registry.json"
            (Path(temp_dir) / "data").mkdir()
            shutil.copytree(ROOT / "data/mrs", Path(temp_dir) / "data" / "mrs")
            shutil.copy(ROOT / "data/pr-registry.json", registry)
            out = StringIO()
            with redirect_stdout(out):
                rc = main(["--registry", str(registry), "evaluate", "--pr-id", "PR-001", "--write"])
            self.assertEqual(rc, 0)
            result = json.loads(out.getvalue())
            self.assertEqual(result["verdict"], "ADMITTED")

    def test_digest_command_can_skip_sync(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "registry.json"
            output_root = Path(temp_dir) / "reports"
            shutil.copy(ROOT / "data/pr-registry.json", registry)
            out = StringIO()
            with redirect_stdout(out):
                rc = main(["digest", "--registry", str(registry), "--output-root", str(output_root), "--no-sync"])
            self.assertEqual(rc, 0)
            result = json.loads(out.getvalue())
            self.assertEqual(result["command"], "digest")
            self.assertTrue(Path(result["report_path"]).exists())
            self.assertTrue(Path(result["stage1_5_snapshot"]["snapshot_path"]).exists())
            self.assertTrue(str(result["stage1_5_snapshot"]["snapshot_path"]).startswith(temp_dir))

    def test_admit_file_command_evaluates_sample_prs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "registry.json"
            output_root = Path(temp_dir) / "reports"
            sample = ROOT / ".claude/skills/cr-vigil-monitor/assets/sample-pr.md"
            out = StringIO()
            with redirect_stdout(out):
                rc = main(["--registry", str(registry), "--output-root", str(output_root), "--no-sync", "admit-file", str(sample)])
            self.assertEqual(rc, 0)
            result = json.loads(out.getvalue())
            self.assertEqual(result["command"], "admit-file")
            self.assertEqual(
                result["verdicts"],
                {"PR-001": "ADMITTED", "PR-002": "REJECTED", "PR-003": "CONDITIONAL"},
            )
            self.assertEqual(len(result["report_paths"]), 3)
            self.assertTrue(all(Path(path).exists() for path in result["report_paths"]))
            registry_index = json.loads(registry.read_text(encoding="utf-8"))
            self.assertEqual(registry_index["storage_mode"], "index")
            self.assertNotIn("ci", registry_index["prs"][0])
            self.assertTrue((Path(temp_dir) / "data" / "mrs" / "PR-001.json").exists())
            stored = json.loads((Path(temp_dir) / "data" / "mrs" / "PR-001.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["record_path"], "data/mrs/PR-001.json")
            event_files = list((Path(temp_dir) / "data" / "events").glob("*.jsonl"))
            self.assertTrue(event_files)
            events = [json.loads(line) for line in event_files[0].read_text(encoding="utf-8").splitlines()]
            self.assertIn("gate_evaluated", {event["event"] for event in events})
            self.assertIn("report_rendered", {event["event"] for event in events})

    def test_evaluate_command_trims_history_from_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "registry.json"
            config = Path(temp_dir) / "cr-vigil.yml"
            shutil.copy(ROOT / "data/pr-registry.json", registry)
            data = json.loads(registry.read_text(encoding="utf-8"))
            data["prs"][0]["history"] = [{"timestamp": str(i), "event": "old", "details": ""} for i in range(20)]
            registry.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            config.write_text("storage:\n  history_limit_per_mr: 3\n", encoding="utf-8")
            out = StringIO()
            with redirect_stdout(out):
                rc = main(["--registry", str(registry), "--config", str(config), "evaluate", "--pr-id", "PR-001", "--write"])
            self.assertEqual(rc, 0)
            updated = json.loads(registry.read_text(encoding="utf-8"))
            self.assertEqual(updated["storage_mode"], "index")
            self.assertNotIn("history", updated["prs"][0])
            mr_record = Path(temp_dir) / "data" / "mrs" / "PR-001.json"
            self.assertTrue(mr_record.exists())
            self.assertLessEqual(len(json.loads(mr_record.read_text(encoding="utf-8"))["history"]), 3)

    def test_sync_push_stages_snapshots(self):
        calls = []

        def fake_git(args):
            calls.append(args)
            if args == ["diff", "--cached", "--quiet"]:
                return False, ""
            if args[0] == "commit":
                return True, "committed"
            if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
                return True, "main"
            if args[0] == "push":
                return True, "pushed"
            return True, ""

        with patch.dict(os.environ, {"CRVIGIL_MODE": "team"}), patch("crvigil.workflow.git_command", side_effect=fake_git):
            result = sync_push("chore：同步测试")

        self.assertTrue(result["ok"])
        self.assertIn(["add", "data/pr-registry.json", "data/mrs", "data/events", "data/snapshots", "reports/"], calls)

    def test_sync_push_reports_commit_failure(self):
        calls = []

        def fake_git(args):
            calls.append(args)
            if args == ["diff", "--cached", "--quiet"]:
                return False, ""
            if args[0] == "commit":
                return False, "missing git identity"
            return True, ""

        with patch.dict(os.environ, {"CRVIGIL_MODE": "team"}), patch("crvigil.workflow.git_command", side_effect=fake_git):
            result = sync_push("chore：同步测试")

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "commit")
        self.assertNotIn(["push", "origin", "main"], calls)

    def test_sync_push_reports_add_failure(self):
        calls = []

        def fake_git(args):
            calls.append(args)
            if args[0] == "add":
                return False, "pathspec failed"
            return True, ""

        with patch.dict(os.environ, {"CRVIGIL_MODE": "team"}), patch("crvigil.workflow.git_command", side_effect=fake_git):
            result = sync_push("chore：同步测试")

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "add")
        self.assertNotIn(["diff", "--cached", "--quiet"], calls)

    def test_sync_push_retries_after_push_failure(self):
        calls = []
        push_count = 0

        def fake_git(args):
            nonlocal push_count
            calls.append(args)
            if args == ["diff", "--cached", "--quiet"]:
                return False, ""
            if args[0] == "commit":
                return True, "committed"
            if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
                return True, "main"
            if args[0] == "push":
                push_count += 1
                return (push_count == 2), "push result"
            if args[0] == "pull":
                return True, "rebased"
            return True, ""

        with patch.dict(os.environ, {"CRVIGIL_MODE": "team"}), patch("crvigil.workflow.git_command", side_effect=fake_git):
            result = sync_push("chore：同步测试", retry=1)

        self.assertTrue(result["ok"])
        self.assertEqual(push_count, 2)
        self.assertIn(["pull", "--rebase", "origin", "main"], calls)


if __name__ == "__main__":
    unittest.main()
