# PR Data Schema

本文件定义了 CR-Vigil Monitor Skill 使用的标准 PR 数据结构。所有数据源（文件、API、手动输入）在进入门禁分析引擎前，必须将数据规范化为以下格式。

---

## 完整 PR 记录与注册表结构

CR-Vigil 统一使用单一的标准 PR 记录结构。注册表 `data/pr-registry.json` 包含该结构的列表，其格式定义如下：

### 注册表外层结构 (pr-registry.json)
```json
{
  "updated_at": "ISO8601",
  "prs": [
    // 包含多个完整 PR 记录结构（见下文）
  ]
}
```

### 完整 PR 记录结构
```json
{
  "pr_id": "string",
  "title": "string",
  "author": "string",
  "url": "string",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "status": "open | merged | closed",
  "ci_mode": "enabled | disabled | auto",
  "ai_usage": {
    "used": "boolean",
    "declared": "boolean",
    "percentage": "number (0-100)",
    "tools": ["string"],
    "modules": ["string"]
  },
  "review": {
    "reviewer": "string",
    "reviewer_level": "junior | senior | staff",
    "substantive_comments": "number",
    "review_approved_at": "ISO8601 | null",
    "checklist": {
      "ck_01": "boolean | null",
      "ck_02": "boolean | null",
      "ck_03": "boolean | null",
      "ck_04": "boolean | null",
      "ck_05": "boolean | null",
      "ck_06": "boolean | null",
      "ck_07": "boolean | null",
      "ck_08": "boolean | null",
      "ck_09": "boolean | null",
      "ck_10": "boolean | null",
      "ck_11": "boolean | null",
      "ck_12": "boolean | null"
    }
  },
  "ci": {
    "pipeline_url": "string",
    "unit_test": {
      "total": "number",
      "passed": "number",
      "failed": "number",
      "pass_rate": "number (0-100)"
    },
    "coverage": {
      "incremental_coverage_pct": "number (0-100)",
      "threshold": "number (default 70)"
    },
    "static_scan": {
      "blocker_count": "number",
      "critical_count": "number",
      "warning_count": "number",
      "tool": "string (sonar | eslint | checkstyle | other)"
    },
    "smoke_test": {
      "total": "number",
      "passed": "number",
      "failed": "number",
      "pass_rate": "number (0-100)"
    }
  },
  "declaration": {
    "ci_proof_provided": "boolean",
    "ci_proof_url": "string",
    "cr_approval_link": "string",
    "self_inspection": {
      "submitted": "boolean",
      "signed_by": "string",
      "signed_date": "ISO8601 | null",
      "checks": {
        "ci_passed": "boolean",
        "cr_completed": "boolean",
        "boundary_verified": "boolean",
        "self_tested": "boolean",
        "no_known_blockers": "boolean"
      }
    }
  },
  "gates": {
    "gate_1": {
      "status": "PASS | FAIL | WARN | PENDING | N/A",
      "details": {
        "unit_test": "PASS | FAIL | N/A",
        "incremental_coverage": "PASS | FAIL | N/A",
        "static_scan": "PASS | FAIL | N/A",
        "smoke_test": "PASS | FAIL | N/A"
      }
    },
    "gate_2": {
      "status": "PASS | FAIL | WARN | PENDING",
      "details": {
        "ai_declared": "PASS | FAIL",
        "reviewer_qualified": "PASS | FAIL",
        "substantive_comments": "PASS | FAIL",
        "checklist_complete": "PASS | FAIL"
      }
    },
    "gate_3": {
      "status": "PASS | FAIL | WARN | PENDING",
      "details": {
        "ci_proof": "PASS | FAIL | N/A",
        "cr_link": "PASS | FAIL",
        "self_inspection": "PASS | FAIL"
      }
    },
    "gate_4": {
      "status": "N/A | READY",
      "details": {
        "records_available": "boolean"
      }
    }
  },
  "gates_summary": {
    "gate_1": "PASS | FAIL | WARN | PENDING | N/A",
    "gate_2": "PASS | FAIL | WARN | PENDING",
    "gate_3": "PASS | FAIL | WARN | PENDING",
    "gate_4": "N/A | READY"
  },
  "verdict": "ADMITTED | REJECTED | CONDITIONAL | PENDING",
  "blocking_reasons": ["string"],
  "ai_percentage": "number (0-100)",
  "reviewer": "string",
  "violations": "number",
  "last_updated": "ISO8601",
  "history": [
    {
      "timestamp": "ISO8601",
      "event": "created | updated | gate_evaluated | admitted | rejected | data_collected",
      "details": "string"
    }
  ]
}
```

---

## 字段说明

### AI Usage 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `used` | boolean | 是否使用了 AI 辅助编码 |
| `declared` | boolean | 开发是否在 PR 描述中声明了 AI 使用 |
| `percentage` | number | AI 生成代码占比 (0-100) |
| `tools` | string[] | 使用的 AI 工具列表 |
| `modules` | string[] | AI 生成的主要模块名称 |

### Review 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `reviewer` | string | 审查人姓名 |
| `reviewer_level` | string | 审查人级别：junior (<3年) / senior (>=3年) / staff |
| `substantive_comments` | number | 实质性评论数量（非 LGTM/OK 等） |
| `ck_01` ~ `ck_12` | boolean | 12 项 Checklist 逐项勾选状态 |

### CI 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `unit_test.pass_rate` | number | 单元测试通过率 (0-100) |
| `coverage.incremental_coverage_pct` | number | 增量代码覆盖率 (0-100) |
| `static_scan.blocker_count` | number | 阻断性问题数量 |
| `static_scan.critical_count` | number | 严重问题数量 |
| `smoke_test.pass_rate` | number | 冒烟测试通过率 (0-100) |

### Verdict 取值含义

| 值 | 含义 |
|----|------|
| ADMITTED | 所有门禁通过，可进入测试 |
| REJECTED | 至少一道门禁未通过，拒绝提测 |
| CONDITIONAL | 所有门禁通过但存在 WARN 项，可提测但需关注 |
| PENDING | 尚未完成全部门禁评估 |

---

## 数据源

CR-Vigil 支持两种数据采集模式，产出的 JSON 格式完全相同。

### 模式一：GitLab API（主力）

通过 `scripts/collect-mr-data.sh` 从 GitLab API 自动采集。字段来源：

| Schema 区块 | 采集来源 | 自动化程度 |
|------------|---------|-----------|
| PR 元信息 | `GET /projects/:id/merge_requests/:iid` | 全自动 |
| AI 声明 | MR 描述中正则解析 | 自动（需开发按模板填写） |
| CI 结果 | `GET /projects/:id/pipelines/:pipeline_id/jobs` | 自动（需 CI Job 命名规范） |
| 审查评论 | `GET /projects/:id/merge_requests/:iid/notes` | 全自动 |
| 审批状态 | `GET /projects/:id/merge_requests/:iid/approvals` | 自动（需 GitLab Premium） |
| Checklist | MR 描述中正则解析 | 自动（需开发按模板勾选） |
| 自检声明 | 人工提交 | 半自动 |

详细映射关系见 `references/gitlab-field-mapping.md`。

### 模式二：Markdown 文件（兼容）

用户可通过 Markdown 格式提供 PR 数据。Skill 会解析 Markdown 并映射到上述 Schema。

Markdown 输入示例见 `assets/sample-pr.md`。

调用方式：
```
/cr-vigil-monitor --admit-file assets/sample-pr.md
```

### 数据完整度处理

无论是哪种模式采集的数据，都可能存在部分字段缺失。Skill 的处理策略：
- 如果字段影响门禁判定（如 CI 结果、审查人）→ 标记为 FAIL，原因是「数据缺失」
- 如果字段不影响核心门禁判定（如静态扫描工具名称）→ 留空，报告中标注「未采集」
- 如果 AI 声明无法检测到 → 默认 `declared: false`，触发门禁二 FAIL
