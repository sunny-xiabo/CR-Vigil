import copy
import json
import unittest
from pathlib import Path

from crvigil import evaluator

ROOT = Path(__file__).resolve().parents[1]


def checklist(value=True):
    return {f"ck_{i:02d}": value for i in range(1, 13)}


def base_pr():
    return {
        "pr_id": "PR-TEST",
        "title": "test",
        "author": "dev",
        "url": "https://gitlab.example.com/group/project/-/merge_requests/1",
        "created_at": "2026-06-10T10:00:00+08:00",
        "updated_at": "2026-06-10T11:00:00+08:00",
        "status": "open",
        "ci_mode": "auto",
        "ai_usage": {"used": False, "declared": False, "percentage": 0, "tools": [], "modules": []},
        "review": {
            "reviewer": "senior-dev",
            "reviewer_level": "senior",
            "substantive_comments": 1,
            "review_approved_at": "2026-06-10T12:00:00+08:00",
            "checklist": checklist(True),
        },
        "ci": {
            "pipeline_url": "",
            "unit_test": {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0},
            "coverage": {"incremental_coverage_pct": 0, "threshold": 70},
            "static_scan": {"blocker_count": 0, "critical_count": 0, "warning_count": 0, "tool": "sonar", "detected": False},
            "smoke_test": {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0},
        },
        "declaration": {
            "ci_proof_provided": False,
            "ci_proof_url": "",
            "cr_approval_link": "https://gitlab.example.com/review",
            "self_inspection": {
                "submitted": True,
                "signed_by": "dev",
                "signed_date": "2026-06-10T12:30:00+08:00",
                "checks": {
                    "ci_passed": False,
                    "cr_completed": True,
                    "boundary_verified": True,
                    "self_tested": True,
                    "no_known_blockers": True,
                },
            },
        },
        "history": [],
    }


class GateEvaluatorTest(unittest.TestCase):
    def test_existing_registry_verdicts_are_preserved(self):
        registry = evaluator.load_registry(ROOT / "data/pr-registry.json")

        for pr_summary in registry["prs"]:
            with self.subTest(pr_id=pr_summary["pr_id"]):
                record_path = pr_summary.get("record_path")
                if record_path and (ROOT / record_path).exists():
                    pr = json.loads((ROOT / record_path).read_text(encoding="utf-8"))
                else:
                    pr = pr_summary
                result = evaluator.evaluate_pr(pr)
                self.assertEqual(result["verdict"], pr.get("verdict", pr_summary.get("verdict")))

    def test_gate1_na_allows_gate3_without_ci_proof(self):
        result = evaluator.evaluate_pr(base_pr())
        self.assertEqual(result["gates_summary"]["gate_1"], "N/A")
        self.assertEqual(result["gates"]["gate_3"]["details"]["ci_proof"], "N/A")
        self.assertEqual(result["verdict"], "ADMITTED")
        self.assertEqual(result["evidence"]["mr_url"], "https://gitlab.example.com/group/project/-/merge_requests/1")
        self.assertEqual(result["evidence"]["cr_approval_link"], "https://gitlab.example.com/review")

    def test_ai_used_without_declaration_is_rejected(self):
        pr = base_pr()
        pr["ai_usage"] = {"used": True, "declared": False, "percentage": 30, "tools": [], "modules": []}
        result = evaluator.evaluate_pr(pr)
        self.assertEqual(result["verdict"], "REJECTED")
        self.assertEqual(result["gates_summary"]["gate_2"], "FAIL")

    def test_reviewer_must_not_be_author_or_junior(self):
        for reviewer, level in [("dev", "senior"), ("junior-dev", "junior")]:
            pr = base_pr()
            pr["review"]["reviewer"] = reviewer
            pr["review"]["reviewer_level"] = level
            with self.subTest(reviewer=reviewer, level=level):
                result = evaluator.evaluate_pr(pr)
                self.assertEqual(result["verdict"], "REJECTED")
                self.assertEqual(result["gates_summary"]["gate_2"], "FAIL")

    def test_incomplete_checklist_is_rejected(self):
        pr = base_pr()
        pr["review"]["checklist"]["ck_06"] = False
        result = evaluator.evaluate_pr(pr)
        self.assertEqual(result["verdict"], "REJECTED")
        self.assertIn("CK-06", " ".join(result["blocking_reasons"]))

    def test_review_timeout_warns_and_becomes_conditional(self):
        pr = base_pr()
        pr["updated_at"] = "2026-06-10T10:00:00+08:00"
        pr["review"]["review_approved_at"] = "2026-06-12T11:00:00+08:00"
        result = evaluator.evaluate_pr(pr)
        self.assertEqual(result["gates_summary"]["gate_2"], "WARN")
        self.assertEqual(result["verdict"], "CONDITIONAL")

    def test_apply_evaluation_does_not_double_count_existing_rejection(self):
        pr = base_pr()
        pr["verdict"] = "REJECTED"
        pr["violations"] = 2
        pr["review"]["reviewer"] = "dev"
        result = evaluator.evaluate_pr(pr)
        updated = evaluator.apply_evaluation(pr, result)
        self.assertEqual(updated["violations"], 2)

    def test_apply_evaluation_counts_new_rejection_once(self):
        pr = base_pr()
        pr["verdict"] = "ADMITTED"
        pr["violations"] = 0
        pr["review"]["reviewer"] = "dev"
        result = evaluator.evaluate_pr(copy.deepcopy(pr))
        updated = evaluator.apply_evaluation(pr, result)
        self.assertEqual(updated["violations"], 1)


if __name__ == "__main__":
    unittest.main()
