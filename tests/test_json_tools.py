import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from crvigil import json_tools


ROOT = Path(__file__).resolve().parents[1]
VALIDATE_PATH = ROOT / ".claude/skills/cr-vigil-monitor/scripts/validate_data.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


validate_data = load_module("validate_data", VALIDATE_PATH)


class JsonToolsTest(unittest.TestCase):
    def test_valid_json_passes_without_repair(self):
        data, repaired = json_tools.parse_json_text('{"prs": []}')
        self.assertEqual(data, {"prs": []})
        self.assertFalse(repaired)

    def test_trailing_comma_is_repaired(self):
        data, repaired = json_tools.parse_json_text('{"prs": [],}', repair=True)
        self.assertEqual(data, {"prs": []})
        self.assertTrue(repaired)

    def test_invalid_json_fails_when_repair_disabled(self):
        with self.assertRaises(json_tools.JsonRepairError):
            json_tools.parse_json_text('{"prs": [],}', repair=False)

    def test_validate_data_can_repair_and_write_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "registry.json"
            path.write_text('{"updated_at": "now", "prs": [],}', encoding="utf-8")

            with redirect_stdout(StringIO()):
                rc = validate_data.main(["--registry", str(path), "--repair", "--write"])

            self.assertEqual(rc, 0)
            with path.open(encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), {"updated_at": "now", "prs": []})

    def test_json_file_lock_creates_sibling_lockfile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "registry.json"
            with json_tools.json_file_lock(path):
                self.assertTrue((Path(temp_dir) / ".registry.json.lock").exists())


if __name__ == "__main__":
    unittest.main()
