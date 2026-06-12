---
name: cr-vigil-monitor
version: 1.1.0
last_updated: 2026-06-12
description: >
  Generate structured admission reports, daily digests, and weekly trend reports
  for the testing team by evaluating PRs against the 4-gate quality control system.
  Trigger when user asks for "CR-Vigil", "提测准入报告", "测试准入", "质量门禁报告",
  "PR monitoring report", "testing admission", "提测日报", "测试周报", "CR监控报告",
  or any request to check if a PR can enter testing.
---

# CR-Vigil Monitor Skill

## 概述

本 Skill 基于《AI 代码质量管控方案》定义的四道门禁体系，自动评估 PR 的测试准入条件，并生成结构化报告供测试团队使用。

四道门禁：
1. CI 质量红线（自动化强制）
2. AI 代码声明 + 人工 Code Review
3. 测试准入声明
4. 故障追溯倒查（不阻断提测，仅用于事后问责）

所有报告的核心结论始终放在最前面，直接回答测试团队最关心的问题：**这个 PR 能不能提测？**

## 适用场景

当用户提到以下关键词时启用本 Skill：
- 生成提测准入报告 / 测试准入判断 / 质量门禁检查
- 生成每日汇总 / 日报 / 今日提测清单
- 生成周报 / 趋势报告 / 违规统计
- 传入 GitLab MR 链接要求分析

## 调用方式

### 方式一：GitLab MR 链接（主力用法）

```
/cr-vigil-monitor --admit <MR链接>
```

示例：
```
/cr-vigil-monitor --admit https://gitlab.miotech.com/miotech-application/esghub/crrc/esghub-service-crrc/-/merge_requests/27
```

Skill 会自动调用 `scripts/collect-mr-data.sh` 从 GitLab API 采集 MR 数据，然后评估门禁并生成报告。

### 方式二：Markdown 文件（兼容旧用法）

```
/cr-vigil-monitor --admit-file <文件路径>
```

适用于测试、演示、或无法访问 GitLab API 的场景。数据格式参考 `assets/sample-pr.md`。

### 方式三：每日汇总

```
/cr-vigil-monitor --digest
```

从 `data/pr-registry.json` 读取所有活跃 PR，生成当日的全局状态报告。

### 方式四：周趋势报告

```
/cr-vigil-monitor --trend
```

从 `data/pr-registry.json` 和历史报告中计算趋势，生成周报。

## 工作流

### 第一步：识别报告类型和数据来源

根据用户输入判断报告类型：
- 用户提供了 URL（包含 `gitlab` 和 `merge_requests`）→ 提测准入报告，Git API 数据源
- 用户提供了文件路径（以 `.md` 结尾）→ 提测准入报告，文件数据源
- 用户要求日报或汇总 → 每日汇总报告
- 用户要求周报或趋势 → 周趋势报告

### 第二步：采集 PR 数据

**Git API 模式（主力）**：

1. 调用 `scripts/collect-mr-data.sh <MR_URL>` 执行数据采集
2. 该脚本会：
   a. 解析 MR URL，提取 GitLab 实例地址、项目路径、MR 编号
   b. 调用 GitLab API 获取 MR 元信息（标题、作者、描述、日期）
   c. 从 MR 描述中正则解析 AI 使用声明（占比、工具、模块）
   d. 调用 Pipelines API 获取 CI 结果（单元测试、覆盖率、静态扫描、冒烟测试）
   e. 调用 Notes API 获取审查评论（审查人、评论内容、形式主义检测）
   f. 调用 Approvals API 获取批准状态
   g. 按标准 JSON Schema 组装数据，写入 `data/pr-registry.json`
3. 如果脚本返回错误，向用户报告具体原因（Token 未配置、API 无权限、MR 不存在等）
4. 脚本成功后，从 `data/pr-registry.json` 读取刚写入的 PR 数据

**文件模式（兼容）**：

1. 读取指定的 Markdown 文件
2. 按 `assets/sample-pr.md` 的格式解析 PR 数据
3. 映射到标准 JSON Schema

需要提取的数据字段详见 `references/data-schema.md`。

核心字段：
- PR 元信息（编号、标题、作者、链接、日期）
- AI 使用声明（是否使用、是否声明、占比、工具、模块）
- Code Review（审查人、级别、评论、Checklist CK-01 至 CK-12）
- CI 结果（单元测试通过率、增量覆盖率、阻断/严重问题数、冒烟测试通过率）
- 测试准入声明（CI 证明、CR 批准链接、自检声明）

如果关键字段缺失（如 CI 结果无法获取、审查人未知），在报告中标注为「待补充」，不影响其他门禁的评估。

### 第三步：逐项评估四道门禁

读取 `references/gate-rules.md` 获取精确的阈值和判定逻辑。逐项评估：

**门禁一：CI 质量红线（自动检测，无需配置）**

评估前先自动判定 CI 模式：

1. 检查 `pr-registry.json` 中的 `ci_mode` 字段
2. 如果 `ci_mode == "enabled"`：强制评估，CI 数据缺失视为 FAIL
3. 如果 `ci_mode == "disabled"`：直接标记 N/A，门禁一不参与准入判定
4. 如果 `ci_mode == "auto"` 或未设置：自动检测
   - `pipeline_url` 非空 或 `unit_test.total > 0` 或 `smoke_test.total > 0` → 视为 enabled，正常评估
   - 以上条件全部不满足 → 视为 disabled，标记 N/A

环境变量 `CRVIGIL_CI_MODE` 和 `CRVIGIL_CI_MODE_MAP` 仅用于显式覆盖，绝大多数场景无需设置。Skill 自动判断即可覆盖 95% 以上的实际使用场景。

**仅当 CI 模式最终判定为 enabled 时，执行以下检查：**

| 检查项 | 阈值 | 判定 |
|--------|------|------|
| 单元测试通过率 | 100% | =100% → PASS，否则 FAIL |
| 增量代码覆盖率 | >= 70% | >=70% → PASS，否则 FAIL |
| 静态扫描阻断问题 | 0 | =0 → PASS，>0 → FAIL |
| 静态扫描严重问题 | 0 | =0 → PASS，>0 → FAIL |
| 冒烟测试通过率 | 100% | =100% → PASS，否则 FAIL |

五个检查项全部 PASS → 门禁一通过。任一 FAIL → 门禁一 FAIL。CI 模式为 disabled 时，门禁一直接标记 N/A。

**门禁二：AI 声明 + 人工 Code Review**

| 检查项 | 条件 | 判定 |
|--------|------|------|
| AI 使用声明 | AI 占比 > 0% 则必须声明 | 已声明 → PASS，未声明 → FAIL |
| 审查人资质 | 非作者、资深级别（>= senior） | 满足 → PASS |
| 实质性评论 | >= 1 条非形式主义评论 | >=1 → PASS，0 → FAIL |
| Checklist 完成 | 12 项全部勾选 | 12/12 → PASS |
| 审查时效 | CR 在 24 小时内完成 | <=24h → PASS，超时 → WARN |

前四项全部 PASS → 门禁二通过。如果全部 PASS 但有 WARN（审查超时）→ 门禁二状态为 WARN。任一 FAIL → 门禁二 FAIL。

形式主义检测规则（参考 `references/checklist-12-items.md`）：
- 仅含 "LGTM"、"Looks Good To Me"、"好的"、"OK"、"没问题"、"Approved"、"通过"、"+1"
- 去除非技术用语后字符数 < 10
- 无任何代码引用或技术讨论

Checklist 解析模式兼容性说明：
- 支持 `- [x]` Markdown 复选框、`已勾选` / `未勾选` 表格项、`✅` / `❌` / `PASS` / `FAIL` / `YES` / `NO` 等多种符号的识别。

审查人级别解析逻辑：
- 优先从 `data/reviewer-levels.json` 本地映射表读取，如未定义则从 approvals 审批结果推断（若被 approvals 通过则至少为 senior），最后默认为 junior。


**门禁三：测试准入声明**

| 材料 | 要求 | 判定 |
|------|------|------|
| CI 通过证明 | 流水线链接或截图 | 已提供 → PASS |
| CR 批准链接 | 可见 Checklist + 评论的 PR 链接 | 已提供 → PASS |
| AI 自检声明 | 开发签字确认（五项全部确认） | 已提交 → PASS |

三项材料全部提供 → 门禁三通过。任一缺失 → 门禁三 FAIL。

**门禁四：故障追溯倒查**

不参与提测准入判定。仅确保 CI 记录、CR 记录、自检声明副本、发布记录在需要时可拉取。

### 第四步：计算准入判定

```
// 排除 N/A 门禁，只评估有效门禁
active_gates = [g for g in [Gate1, Gate2, Gate3] if g.STATUS != N/A]

如果 全部 active_gates 为 PASS:
    如果 Gate2 == WARN:
        判定 = CONDITIONAL（有条件通过，需注明风险）
    否则:
        判定 = ADMITTED（准予提测）
如果 任一 active_gate 为 FAIL:
    判定 = REJECTED（拒绝提测）
如果 任一 active_gate 为 PENDING:
    判定 = PENDING（待评估）

// 常见场景
- Gate1=N/A (无CI), Gate2=PASS, Gate3=PASS → ADMITTED
- Gate1=N/A (无CI), Gate2=FAIL → REJECTED（门禁二阻塞，与CI无关）
```

注意：门禁三的 G3-01（CI 通过证明）随门禁一联动。当 CI 模式为 disabled 时，G3-01 同步标记为 N/A，不再要求提供 CI 证明。

收集阻塞原因：
- 每一项 FAIL：列出具体检查项、阈值、实际值
- 每一项 WARN：作为已知风险列出

### 第五步：生成并写入报告

根据报告类型，读取对应的模板：

- 准入报告：`assets/admission-report-template.md`
- 每日汇总：`assets/daily-digest-template.md`
- 周趋势报告：`assets/weekly-trend-template.md`

用评估结果填充模板：
- 替换所有 `{PLACEHOLDER}` 占位符
- 表格行按数据逐行生成
- 列表项按规则逐条生成
- 准入判定放在报告最顶部

报告写入路径规范：
- 准入报告：`reports/admissions/{PR_ID}-admission-{YYYY-MM-DD}.md`
- 每日汇总：`reports/digests/daily-digest-{YYYY-MM-DD}.md`
- 周趋势报告：`reports/trends/weekly-trend-{YYYY-MM-DD}.md`

### 第六步：更新注册表并展示摘要

1. 更新 `data/pr-registry.json`：
   - 如果 PR 已存在，更新记录
   - 如果 PR 是新的，新增记录
   - 更新时间戳
   - 如果是再次拒绝，递增违规计数器

2. 向用户展示简洁摘要：
   - 报告类型和文件路径
   - 准入判定（准入报告）或关键统计（日报/周报）
   - 评估的 PR 数量

## 每日汇总专用逻辑

1. 从 `data/pr-registry.json` 读取所有活跃 PR（状态为 open）
2. 对每个 PR，如果数据自上次评估后有更新，重新评估门禁
3. 计算聚合统计：活跃总数、准入/阻塞/待评估数量、最常见阻塞门禁、平均 AI 占比
4. 阻塞 PR 段：列出失败门禁、失败原因、阻塞天数、开发需执行的操作
5. 生成违规复现预警：对曾被拒绝超过一次的开发者发出警告

## 周趋势报告专用逻辑

1. 从 `data/pr-registry.json` 和最近 4 周的历史报告读取数据
2. 计算趋势：本周每日准入率、各门禁违规对比上周、AI 使用趋势、Top 阻塞问题排名
3. 审查人统计：完成审查数、平均评论数、形式主义事件数
4. 违规复现追踪：按开发者列出违规次数和升级级别
5. 与前三周对比，产出 4 周合规趋势表
6. 根据数据模式生成可操作的建议

## 反模式与硬性规则

生成报告时必须严格遵守以下规则：

1. 禁用 box-drawing 字符。不使用 ┌ ─ ┐ │ └ ┘ ├ ┤ ┬ ┴ ┼ 等 Unicode 制表符。使用标准 Markdown 表格（`|` 和 `-`）。
2. 禁用 emoji 和表情符号。状态标记用纯文本：PASS、FAIL、WARN。
3. 禁用装饰性 ASCII 画。不使用 + - = * 拼成的横幅或边框。
4. 准入判定必须是报告标题之后的第一项内容。直接回答「能不能提测」。
5. 判定标签使用：ADMITTED（准予提测）、REJECTED（拒绝提测）、CONDITIONAL（有条件通过）、PENDING（待评估）。不使用彩色圆点或符号。
6. 所有报告必须是合法的 Markdown 格式，在标准渲染器中正确显示。
7. 门禁失败时，必须列出具体检查项、阈值和实际值。
8. 阻塞问题必须具体且可操作——开发者看后应明确知道需要做什么。
9. 所有报告内容必须使用中文。标题、标签、判定说明、建议、摘要——测试团队阅读的所有文字都必须是中文。技术标识符（PR-001、CK-01、G1-01、ADMITTED 等）和 URL 可以保持英文。

## 数据源模式

### Git API 模式（默认）

传入 GitLab MR 链接时，Skill 调用 `scripts/collect-mr-data.sh` 自动采集数据。需要预先配置环境变量：

```bash
export GITLAB_TOKEN="glpat-xxxx"  # GitLab Personal Access Token
```

采集脚本将 GitLab API 返回的数据映射为标准 JSON Schema 并写入 `data/pr-registry.json`。报告生成逻辑不变。

GitLab API 字段映射详见 `references/gitlab-field-mapping.md`。

### 文件模式（兼容）

传入 Markdown 文件路径时，Skill 直接解析文件内容。数据格式参考 `assets/sample-pr.md`。适用于：
- 本地测试和演示
- 无法访问 GitLab API 的环境
- 人工补充数据场景

文件模式和 API 模式的报告生成逻辑**完全相同**，只是数据来源不同。两种模式产出的 JSON 都写入同一个 `pr-registry.json`。

## 环境配置

```bash
# GitLab 认证（必填，使用 API 模式时需要）
export GITLAB_TOKEN="glpat-xxxx"

# GitLab 实例地址（可选，默认从 MR URL 自动解析）
export GITLAB_HOST="https://gitlab.miotech.com"

# CI Job 名称映射（可选，当流水线 Job 命名不标准时使用）
export CRVIGIL_JOB_MAPPING='{"unit_test":"run-tests","coverage":"coverage-report","static_scan":"sonar","smoke_test":"smoke"}'
```

## 定时调度

使用 `/loop` 命令设置定时自动生成：

每日汇总（每 24 小时）：
```
/loop 24h /cr-vigil-monitor --digest
```

周趋势报告（每 7 天）：
```
/loop 7d /cr-vigil-monitor --trend
```

如果需要精确时间（如每日 8:57 赶在晨会前），可使用 CronCreate。

## 参考文件

| 文件 | 用途 |
|------|------|
| `references/data-schema.md` | 标准 PR 数据 JSON Schema |
| `references/gate-rules.md` | 四道门禁的完整规则与判定逻辑 |
| `references/checklist-12-items.md` | 12 项 AI Code Review Checklist |
| `references/gitlab-field-mapping.md` | GitLab API 字段到 PR Schema 的映射关系 |
| `assets/admission-report-template.md` | 提测准入报告模板 |
| `assets/daily-digest-template.md` | 每日汇总报告模板 |
| `assets/weekly-trend-template.md` | 周趋势报告模板 |
| `assets/sample-pr.md` | 示例 PR 数据（用于文件模式测试） |
| `scripts/collect-mr-data.sh` | GitLab MR 数据采集脚本 |
| `scripts/gitlab-api.sh` | GitLab API 通用请求封装 |
| `data/reviewer-levels.json` | 审查人级别本地配置映射表 |

