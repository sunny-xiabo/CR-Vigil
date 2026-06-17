import unittest
from pathlib import Path

from crvigil.declaration import generate_declaration_markdown


class DeclareTest(unittest.TestCase):
    def test_generate_declaration_with_ai_usage(self):
        ai_usage = {
            "declared": True,
            "percentage": 30,
            "tools": ["GitHub Copilot", "ChatGPT"],
            "modules": ["数据处理", "日志格式化"],
        }
        md = generate_declaration_markdown(ai_usage, "lisi", "https://gitlab.example.com/mr/1")
        self.assertIn("30%", md)
        self.assertIn("GitHub Copilot", md)
        self.assertIn("ChatGPT", md)
        self.assertIn("数据处理", md)
        self.assertIn("lisi", md)
        self.assertIn("https://gitlab.example.com/mr/1", md)
        self.assertIn("[x] 本 MR 使用了 AI 辅助", md)

    def test_generate_declaration_without_ai_usage(self):
        ai_usage = {"declared": False, "percentage": 0, "tools": [], "modules": []}
        md = generate_declaration_markdown(ai_usage, "", "")
        self.assertIn("[ ] 本 MR 未使用 AI 辅助", md)
        self.assertIn("[ ] 本 MR 使用了 AI 辅助", md)
        self.assertIn("待填写", md)

    def test_generate_declaration_self_checks(self):
        ai_usage = {"declared": False, "percentage": 0, "tools": [], "modules": []}
        md = generate_declaration_markdown(ai_usage, "", "")
        self.assertIn("[x] 本次提测代码已通过 CI 全部质量门禁", md)
        self.assertIn("[x] 所有 AI 辅助代码已完成开发 CR", md)
        self.assertIn("[x] 已对 AI 生成的边界条件和异常逻辑进行人工验证", md)
        self.assertIn("[x] 本人已在本地完成基础功能自测", md)
        self.assertIn("[x] 无已知的阻断性缺陷被刻意隐瞒", md)

    def test_generate_declaration_no_placeholders(self):
        ai_usage = {"declared": True, "percentage": 50, "tools": ["Copilot"], "modules": ["模块A"]}
        md = generate_declaration_markdown(ai_usage, "reviewer", "link")
        import re
        self.assertNotRegex(md, r"\{[A-Z0-9_]+\}")


if __name__ == "__main__":
    unittest.main()
