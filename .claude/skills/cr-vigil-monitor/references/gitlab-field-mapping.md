# GitLab API 字段映射参考

本文件定义 GitLab API 响应字段到 CR-Vigil 标准 PR Schema 的映射关系。

---

## 使用的 API 端点

| 端点 | 用途 | 响应类型 |
|------|------|---------|
| `GET /projects/:id/merge_requests/:iid` | MR 元信息 + 描述 | 单对象 |
| `GET /projects/:id/merge_requests/:iid/pipelines` | 流水线列表 | 数组 |
| `GET /projects/:id/pipelines/:pipeline_id/jobs` | 流水线 Job 详情 | 数组 |
| `GET /projects/:id/merge_requests/:iid/notes` | 评论列表 | 数组 |
| `GET /projects/:id/merge_requests/:iid/approvals` | 审批状态 | 单对象 |
| `GET /projects/:id/merge_requests/:iid/changes` | 代码变更 | 单对象 |

---

## 零、CI 模式字段（新增）

| Schema 字段 | 采集来源 | 取值 | 备注 |
|------------|---------|------|------|
| `ci_mode` | 环境变量 + 自动检测 | `enabled` / `disabled` / `auto` | 默认 `auto` |

当 `ci_mode` 为 `auto` 时，采集脚本在获取 CI 数据后自动判定：
- 存在 `pipeline_url` 或 `unit_test.total > 0` 或 `smoke_test.total > 0` → 写入 `enabled`
- 均不满足 → 写入 `disabled`

环境变量 `CRVIGIL_CI_MODE` 和 `CRVIGIL_CI_MODE_MAP` 可用于显式覆盖自动检测结果（非必需）。

当 `ci_mode` 为 `disabled` 时：
- 门禁一直接标记 N/A，不参与准入判定
- 门禁三的 G3-01（CI 通过证明）同步标记 N/A

---

## 一、PR 元信息映射

| Schema 字段 | GitLab API 路径 | 备注 |
|------------|----------------|------|
| `pr_id` | 拼接：`MR-{iid}-{project_name}` | 脚本自动生成 |
| `title` | `merge_request.title` | 直接对应 |
| `author` | `merge_request.author.name` | 直接对应 |
| `url` | `merge_request.web_url` | 直接对应 |
| `created_at` | `merge_request.created_at` | ISO8601 格式 |
| `updated_at` | `merge_request.updated_at` | ISO8601 格式 |
| `status` | `merge_request.state` | `opened`/`merged`/`closed` |

---

## 二、AI 使用声明映射

所有字段从 `merge_request.description` 中通过正则解析：

| Schema 字段 | 正则模式 | 示例匹配 |
|------------|---------|---------|
| `ai_usage.used` | 推断：`percentage > 0` → true | -- |
| `ai_usage.declared` | 存在 `AI.*(辅助\|声明\|使用\|占比)` → true | `AI 辅助声明` |
| `ai_usage.percentage` | `AI[^0-9]*(\d+)%` | `45%` → 45 |
| `ai_usage.tools` | `使用工具[：:]\s*(.*)` | `GitHub Copilot、ChatGPT` |
| `ai_usage.modules` | `(主要\|生成\|涉及)模块[：:]\s*(.*)` | `JWT token 生成` |

---

## 三、CI 结果映射

### 流水线 URL

| Schema 字段 | GitLab API 路径 |
|------------|----------------|
| `ci.pipeline_url` | `pipelines[0].web_url` |

### 单元测试

| Schema 字段 | 采集来源 | 备注 |
|------------|---------|------|
| `ci.unit_test.pass_rate` | 匹配 Job name 含 `unit-test` 或 `ut` | status=success → 100，否则 0 |
| `ci.unit_test.total` | 同上，从 Job trace 解析 | 如无法获取则填 1/0 |
| `ci.unit_test.passed` | 同上 | -- |
| `ci.unit_test.failed` | 同上 | -- |

### 覆盖率

| Schema 字段 | 采集来源 | 备注 |
|------------|---------|------|
| `ci.coverage.incremental_coverage_pct` | 优先级：Job trace 中 `Coverage: X%` > pipeline.coverage 字段 | 无法获取时默认 0 |

### 静态扫描

| Schema 字段 | 采集来源 | 备注 |
|------------|---------|------|
| `ci.static_scan.blocker_count` | 匹配 Job name 含 `sonar`/`lint`/`static-scan` | status=success → 0，否则 -1（未检测） |
| `ci.static_scan.critical_count` | 同上 | -- |
| `ci.static_scan.tool` | 从 Job name 推断 | sonar/eslint/checkstyle |

### 冒烟测试

| Schema 字段 | 采集来源 |
|------------|---------|
| `ci.smoke_test.pass_rate` | 匹配 Job name 含 `smoke`，status=success → 100 |

---

## 四、Code Review 映射

| Schema 字段 | GitLab API 路径 | 备注 |
|------------|----------------|------|
| `review.reviewer` | `approvals.approved_by[0].user.name` 或第一个非作者的系统外 `notes[].author.name` | 优先取审批人 |
| `review.reviewer_level` | 由 Skill 推断 | 依赖团队 LDAP 或人工标注 |
| `review.substantive_comments` | 统计所有非系统 `notes` 中 body 长度 >= 10 且非形式用语的条目数 | -- |
| `review.review_approved_at` | `approvals.approved_by[0].approved_at` | ISO8601 |

---

## 五、形式主义检测规则

针对 `notes[].body` 内容检测：

以下模式判定为形式主义，不计入实质性评论：
- 仅含 `LGTM`、`Looks Good To Me`
- 仅含 `OK`、`好的`、`没问题`、`+1`
- 仅含 `Approved`、`通过`
- 去除非技术用语后字符数 < 10

---

## 六、Checklist 映射

Checklist（CK-01 至 CK-12）从 MR 描述中解析：

如果 MR 描述中包含 Checklist 表格（标准 PR 模板），按行匹配。格式示例：

```markdown
| CK-01 | 边界条件已覆盖 | 已勾选 |
| CK-02 | 异常处理完整 | 未勾选 |
```

解析规则（兼容多种主流格式以提高解析鲁棒性）：
- 搜索 `CK-\d{2}` 标识所在的行或文本。
- 提取并分析勾选/完成状态：
  - **已通过/已勾选（`true`）判定条件**：匹配到 `[x]`、`[X]`、`已勾选`、`PASS`、`YES`、`true`、`对` 或 emoji 符号如 `✅`、`:white_check_mark:`
  - **未通过/未勾选（`false`）判定条件**：匹配到 `[ ]`、`未勾选`、`FAIL`、`NO`、`false`、`错` 或 emoji 符号如 `❌`、`:x:`
  - **空白/未提供（`null`）判定条件**：若无上述显式匹配或缺少对应项，则写入 `null` 并触发人工核对提示
- 如果 MR 描述中完全不包含任何 Checklist 标识或表格，则 12 项 Checklist 全部写入 `null`。

---

## 七、测试准入声明映射

| Schema 字段 | 采集来源 | 默认值 |
|------------|---------|--------|
| `declaration.ci_proof_provided` | 存在 `ci.pipeline_url` 即视为 true | false |
| `declaration.ci_proof_url` | `ci.pipeline_url` | 空串 |
| `declaration.cr_approval_link` | `merge_request.web_url` | 空串 |
| `declaration.self_inspection.submitted` | 需人工提交，默认 false | false |

自检声明的五项确认（SI-01 至 SI-05）：通过 MR 描述中的自检声明表格解析，或留空等待开发填写。

---

## 八、认证配置

```bash
# 必填
export GITLAB_TOKEN="glpat-xxxx"

# 可选（默认从 MR URL 自动解析）
export GITLAB_HOST="https://gitlab.miotech.com"

# 可选：Job 名称映射（当流水线 Job 命名不标准时使用）
export CRVIGIL_JOB_MAPPING='{
  "unit_test": "run-unit-tests",
  "coverage": "coverage-report",
  "static_scan": "sonarqube-scan",
  "smoke_test": "smoke-tests"
}'
```

---

## 九、限制说明

| 限制项 | 说明 |
|--------|------|
| 审查人级别 | GitLab API 不直接返回开发者级别，当前默认填补为 `junior`，需后续接入 LDAP/成员 API |
| 增量覆盖率 | GitLab CI 默认提供的是整体覆盖率，`incremental_coverage_pct` 需要 CI Job 配置了 diff-cover 等工具 |
| 静态扫描详情 | 仅能判断 Job 是否通过，具体的 Blocker/Critical 数量需要从 Job trace 或 SonarQube API 单独获取 |
| Checklist 自动解析 | 如果团队不使用标准 PR 模板，Checklist 字段将为 null，需人工补充 |
| 自检声明 | 这是制度要求的开发签字动作，无法完全自动化，仍需开发提交 |
