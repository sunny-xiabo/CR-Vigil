from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from crvigil.gitlab_collect import (
    GitLabCollectError,
    parse_mr_url,
    parse_ai_declaration,
    substantive_comment_count,
    reviewer_mapped_level,
    reviewer_level,
    collect_review,
)
from crvigil.utils import ROOT


class GitlabCollectTest(unittest.TestCase):
    def test_parse_mr_url_valid(self):
        url1 = "https://gitlab.example.com/group/subgroup/project/-/merge_requests/123"
        info1 = parse_mr_url(url1)
        self.assertEqual(info1["host"], "https://gitlab.example.com")
        self.assertEqual(info1["project_path"], "group/subgroup/project")
        self.assertEqual(info1["iid"], "123")

        url2 = "https://gitlab.com/org/repo/-/merge_requests/456/"
        info2 = parse_mr_url(url2)
        self.assertEqual(info2["host"], "https://gitlab.com")
        self.assertEqual(info2["project_path"], "org/repo")
        self.assertEqual(info2["iid"], "456")

        url3 = "https://gitlab.example.com/foo/bar/-/merge_requests/789?diff=1"
        info3 = parse_mr_url(url3)
        self.assertEqual(info3["host"], "https://gitlab.example.com")
        self.assertEqual(info3["project_path"], "foo/bar")
        self.assertEqual(info3["iid"], "789")

    def test_parse_mr_url_invalid(self):
        with self.assertRaises(GitLabCollectError):
            parse_mr_url("invalid-url")

        with self.assertRaises(GitLabCollectError):
            parse_mr_url("https://gitlab.example.com/group/project/merge_requests/123")

    def test_parse_ai_declaration(self):
        desc1 = "This MR uses AI 辅助.\nAI代码占比: 45%\n使用工具: GitHub Copilot\n主要模块: User auth."
        res1 = parse_ai_declaration(desc1)
        self.assertTrue(res1["used"])
        self.assertTrue(res1["declared"])
        self.assertEqual(res1["percentage"], 45)
        self.assertEqual(res1["tools"], ["GitHub Copilot"])
        self.assertEqual(res1["modules"], ["User auth."])

        desc2 = "No AI used here."
        res2 = parse_ai_declaration(desc2)
        self.assertFalse(res2["declared"])
        self.assertTrue(res2["used"])

    def test_substantive_comment_count(self):
        notes = [
            {"system": True, "body": "added 1 commit"},
            {"system": False, "body": "LGTM"},
            {"system": False, "body": "Ok"},
            {"system": False, "body": "This is a substantive technical review comment explaining that the database pool should be closed."},
        ]
        self.assertEqual(substantive_comment_count(notes), 1)

    @patch("crvigil.gitlab_collect.Path.exists")
    @patch("crvigil.gitlab_collect.Path.read_text")
    def test_reviewer_mapped_level(self, mock_read_text, mock_exists):
        mock_exists.return_value = True
        mock_read_text.return_value = json.dumps({
            "lisi": "senior",
            "wangwu": "junior",
        })

        self.assertEqual(reviewer_mapped_level("lisi"), "senior")
        self.assertEqual(reviewer_mapped_level("WANGWU"), "junior")
        self.assertIsNone(reviewer_mapped_level("unknown_user"))

        self.assertEqual(reviewer_level("lisi"), "senior")
        self.assertEqual(reviewer_level("unknown_user"), "junior")

    @patch("crvigil.gitlab_collect.reviewer_mapped_level")
    def test_collect_review_level_resolution(self, mock_mapped):
        client = MagicMock()
        client.get_paginated.return_value = []
        client.get_single.return_value = {
            "approved_by": [
                {"user": {"name": "TestReviewer"}, "approved_at": "2026-06-15T10:00:00Z"}
            ]
        }

        # Case 1: Reviewer is explicitly mapped as junior. Should remain junior.
        mock_mapped.return_value = "junior"
        res = collect_review(client, "project_id", "iid", "author")
        self.assertEqual(res["reviewer_level"], "junior")

        # Case 2: Reviewer is explicitly mapped as senior. Should remain senior.
        mock_mapped.return_value = "senior"
        res = collect_review(client, "project_id", "iid", "author")
        self.assertEqual(res["reviewer_level"], "senior")

        # Case 3: Reviewer not in registry, but MR approved. Infer senior.
        mock_mapped.return_value = None
        res = collect_review(client, "project_id", "iid", "author")
        self.assertEqual(res["reviewer_level"], "senior")

        # Case 4: Reviewer not in registry, MR not approved. Default to junior.
        client.get_single.return_value = {"approved_by": []}
        res = collect_review(client, "project_id", "iid", "author")
        self.assertEqual(res["reviewer_level"], "junior")
