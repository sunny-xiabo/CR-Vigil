from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from crvigil.file_collect import (
    build_records_from_markdown,
    parse_checklist,
    parse_static_scan,
    parse_ai_usage,
    parse_review,
    parse_declaration,
    parse_ci,
    field,
    bool_zh,
    first_number,
)


SAMPLE_MD = """\
## PR-001: Test PR One

- **标题**: feat: add login
- **开发人员**: zhangsan
- **链接**: https://example.com/pr/1
- **状态**: open
- **单元测试**: 通过 100，通过率 100%
- **增量代码覆盖率**: 85%
- **阻断性问题**: 0
- **严重问题**: 0
- **冒烟测试**: 通过 10，通过率 100%
- **AI 代码占比**: 30%
- **是否使用 AI**: 是
- **是否已在 PR 中声明**: 是
- **审查人**: lisi
- **审查人级别**: senior
- **实质性评论数量**: 3
- **审查批准时间**: 2026-06-10T12:00:00+08:00
- **已提交**: 是
- **CR 批准链接**: https://example.com/review/1
- **CI 通过证明**: 已提供
- **流水线链接**: https://ci.example.com/1

## PR-002: Test PR Two

- **标题**: fix: bug fix
- **开发人员**: wangwu
- **状态**: open
"""


class FileCollectTest(unittest.TestCase):
    def test_build_records_from_markdown(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.md"
            path.write_text(SAMPLE_MD, encoding="utf-8")
            records = build_records_from_markdown(path)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["pr_id"], "PR-001")
        self.assertEqual(records[0]["author"], "zhangsan")
        self.assertEqual(records[0]["ci_mode"], "enabled")
        self.assertEqual(records[0]["review"]["reviewer"], "lisi")
        self.assertEqual(records[1]["pr_id"], "PR-002")

    def test_parse_static_scan_with_data(self):
        section = "- **阻断性问题**: 0\n- **严重问题**: 1\n- **工具**: SonarQube\n"
        result = parse_static_scan(section)
        self.assertEqual(result["blocker_count"], 0)
        self.assertEqual(result["critical_count"], 1)
        self.assertTrue(result["detected"])

    def test_parse_static_scan_without_data(self):
        section = "no scan data here"
        result = parse_static_scan(section)
        self.assertEqual(result["blocker_count"], 0)
        self.assertEqual(result["critical_count"], 0)
        self.assertFalse(result["detected"])

    def test_parse_checklist_all_selected(self):
        section = "全部 12 项已勾选"
        result = parse_checklist(section)
        self.assertTrue(all(v is True for v in result.values()))

    def test_parse_checklist_from_table(self):
        section = "| CK-01 | 边界条件已覆盖 | 已勾选 |\n| CK-02 | 异常处理完整 | 未勾选 |\n| CK-03 | 并发安全 | 已勾选 |"
        result = parse_checklist(section)
        self.assertTrue(result["ck_01"])
        self.assertFalse(result["ck_02"])
        self.assertTrue(result["ck_03"])
        self.assertIsNone(result["ck_04"])

    def test_parse_ai_usage(self):
        section = "- **AI 代码占比**: 45%\n- **是否使用 AI**: 是\n- **是否已在 PR 中声明**: 是\n- **使用的 AI 工具**: Copilot, ChatGPT\n- **AI 生成的主要模块**: auth, login\n"
        result = parse_ai_usage(section)
        self.assertEqual(result["percentage"], 45)
        self.assertTrue(result["declared"])
        self.assertEqual(result["tools"], ["Copilot", "ChatGPT"])
        self.assertEqual(result["modules"], ["auth", "login"])

    def test_parse_review(self):
        section = "- **审查人**: lisi\n- **审查人级别**: senior\n- **实质性评论数量**: 2\n- **审查批准时间**: 2026-06-10T12:00:00+08:00\n"
        result = parse_review(section, "zhangsan")
        self.assertEqual(result["reviewer"], "lisi")
        self.assertEqual(result["reviewer_level"], "senior")
        self.assertEqual(result["substantive_comments"], 2)

    def test_parse_declaration_ci_not_required(self):
        section = "- **已提交**: 是\n- **CR 批准链接**: https://example.com/review\n- **CI 通过证明**: N/A\n"
        result = parse_declaration(section, gate_1_has_ci=False)
        self.assertTrue(result["ci_proof_provided"])
        self.assertTrue(result["self_inspection"]["submitted"])

    def test_field_extraction(self):
        section = "- **名称**: 测试值\n- **数字**: 42\n"
        self.assertEqual(field(section, "名称"), "测试值")
        self.assertEqual(field(section, "数字"), "42")
        self.assertEqual(field(section, "不存在"), "")
        self.assertEqual(field(section, "不存在", "默认"), "默认")

    def test_bool_zh(self):
        self.assertTrue(bool_zh("是"))
        self.assertTrue(bool_zh("已提供"))
        self.assertTrue(bool_zh("PASS"))
        self.assertFalse(bool_zh("未"))
        self.assertFalse(bool_zh("否"))
        self.assertFalse(bool_zh("FAIL"))
        self.assertFalse(bool_zh("未知"))
        self.assertTrue(bool_zh("abc", default=True))
        self.assertFalse(bool_zh("abc", default=False))

    def test_first_number(self):
        self.assertEqual(first_number("通过 100"), 100.0)
        self.assertEqual(first_number("85.5%"), 85.5)
        self.assertEqual(first_number("无数据", 0), 0)

    def test_parse_ci(self):
        section = "- **流水线链接**: https://ci.example.com/1\n- **单元测试**: 通过 100，通过率 100%\n- **增量代码覆盖率**: 85%\n- **冒烟测试**: 通过 10，通过率 100%\n"
        mode, ci = parse_ci(section)
        self.assertEqual(mode, "enabled")
        self.assertEqual(ci["unit_test"]["total"], 100)
        self.assertEqual(ci["unit_test"]["pass_rate"], 100)
        self.assertEqual(ci["coverage"]["incremental_coverage_pct"], 85)
        self.assertEqual(ci["smoke_test"]["total"], 10)


if __name__ == "__main__":
    unittest.main()
