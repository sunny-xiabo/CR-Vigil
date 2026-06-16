---
name: cr-vigil-monitor
version: 1.2.0
last_updated: 2026-06-15
description: >
  Skill-driven CR-Vigil workflow for GitLab MR testing admission, daily digests,
  and weekly trend reports. The Skill orchestrates collection, deterministic
  gate evaluation, Markdown report rendering, and team Git synchronization.
  Trigger when user asks for "CR-Vigil", "提测准入报告", "测试准入",
  "质量门禁报告", "提测日报", "测试周报", "CR监控报告", or whether an MR can
  enter testing.
---

# CR-Vigil Monitor Skill

## 定位

本 Skill 是 CR-Vigil 的唯一用户入口。用户继续使用 `/cr-vigil-monitor --admit|--admit-file|--digest|--trend`，不需要学习独立 CLI。

Skill 负责流程编排、异常解释和中文摘要；确定性脚本负责数据采集后的门禁评估和报告生成。

## 支持命令

```bash
/cr-vigil-monitor --admit <GitLab MR 链接>
/cr-vigil-monitor --admit-file <Markdown 文件路径>
/cr-vigil-monitor --digest
/cr-vigil-monitor --trend
```

## 内部脚本契约

| 命令 | 用途 | 输出 |
|------|------|------|
| `python -m crvigil admit <MR_URL>` | 采集、评估并生成单 MR 提测报告 | JSON 摘要 |
| `python -m crvigil admit-file <FILE_PATH>` | 从 Markdown 文件采集、评估并生成提测报告 | JSON 摘要 |
| `python -m crvigil digest` | 评估活跃 PR 并生成日报 | JSON 摘要 |
| `python -m crvigil trend` | 生成周趋势报告 | JSON 摘要 |
| `python -m crvigil validate --repair --write` | JSON 格式自检与修复 | JSON 校验摘要 |

底层脚本仍保留作为 legacy 兼容层，但 Skill 应优先调用 `python -m crvigil`。

## JSON 自检与修复

所有读取 `data/pr-registry.json` 的确定性脚本都会先进行 JSON 格式自检。发现格式异常时，优先尝试可选依赖 `json_repair`；如果本地未安装该依赖，则使用内置轻量修复处理 BOM、首尾空白、对象或数组末尾多余逗号等常见问题。

维护人员可手动执行：

```bash
python -m crvigil validate
python -m crvigil validate --repair --write
```

修复失败时必须停止后续阶段，不允许继续生成报告。

## 阶段驱动规则

CR-Vigil 必须按阶段推进，不允许跳过阶段直接生成报告。

| 阶段 | 名称 | 完成条件 | 下一步 |
|------|------|----------|--------|
| 阶段 1 | 数据采集与门禁评估 | registry 中目标 PR 已写入 `gates`、`gates_summary`、`verdict`、`blocking_reasons`，且门禁状态不再是全量 `PENDING` | 允许进入阶段 2 |
| 阶段 1.5 | 快照写入 | 当前 registry 已写入 `data/snapshots/daily-YYYY-MM-DD.json` 或 `weekly-YYYY-Www.json` | 报告使用稳定快照 |
| 阶段 2 | 报告生成 | `python -m crvigil` 成功输出报告路径 | 允许展示摘要并同步 |
| 阶段 3 | 团队同步与通知 | 团队模式下 `sync push` 成功，或个人模式明确跳过同步 | 向用户输出最终结果 |

如果阶段 1 未完成，Python 渲染器会拒绝生成单 MR 提测报告、日报和周报。Skill 应先修复采集或评估问题，再进入下一阶段。

当前存储为正式分层模式：`data/pr-registry.json` 是轻量索引，`data/mrs/<PR_ID>.json` 保存单个 MR 完整当前状态，`data/events/YYYY-MM.jsonl` 追加记录采集、评估和报告事件。Skill 不应直接手工编辑这些文件。

## 报告定制

报告内容由 `cr-vigil.yml` 控制。Skill 不应直接改模板内容来临时定制日报/周报；应先修改配置，再运行 `python -m crvigil digest` 或 `python -m crvigil trend`。

默认策略：

| 报告 | 默认 profile | 详细程度 |
|------|--------------|----------|
| 单 MR 提测报告 | detailed | 详细，包含完整门禁细节 |
| 日报 | standard | 简洁，突出行动项 |
| 周报 | standard | 中等详细，突出趋势和复盘 |

## Admit 工作流

收到 `/cr-vigil-monitor --admit <MR_URL>` 时：

1. 执行 `python -m crvigil admit <MR_URL>`。
2. 读取命令输出 JSON，向用户输出中文摘要：判定、阻塞原因、报告路径、同步状态。

## Admit File 工作流

收到 `/cr-vigil-monitor --admit-file <文件路径>` 时：

1. 执行 `python -m crvigil admit-file <文件路径>`。
2. 读取命令输出 JSON，向用户输出文件内 PR 数量、各 PR 判定、报告路径和同步状态。

文件模式与 Git API 模式的门禁评估逻辑必须完全相同。

## Digest 工作流

收到 `/cr-vigil-monitor --digest` 时：

1. 执行 `python -m crvigil digest`。
2. 读取命令输出 JSON，输出活跃 PR 数、准入数、阻塞数、报告路径。

## Trend 工作流

收到 `/cr-vigil-monitor --trend` 时：

1. 执行 `python -m crvigil trend`。
2. 读取命令输出 JSON，输出本周 PR 总数、准入率、主要阻塞问题、报告路径。

## 门禁规则来源

门禁判定以确定性脚本为准，规则来源为：

| 文件 | 用途 |
|------|------|
| `references/gate-rules.md` | 四道门禁规则与判定依据 |
| `references/data-schema.md` | 标准 PR 数据结构 |
| `references/checklist-12-items.md` | 12 项 AI Code Review Checklist |
| `references/gitlab-field-mapping.md` | GitLab 字段映射 |

Skill 不应临场改写阈值。覆盖率阈值、CI 模式、Reviewer 资质、Checklist 完成度等均由脚本按 registry 数据计算。

## 异常处理

| 场景 | Skill 行为 |
|------|------------|
| 未配置 `GITLAB_TOKEN` | 告知用户设置 Token，并停止 Git API 模式 |
| GitLab API 无权限或 MR 不存在 | 展示采集脚本错误，提示检查 MR 链接和权限 |
| registry 中找不到 PR | 停止评估，提示采集未成功写入 |
| 门禁评估脚本失败 | 展示 stderr，提示不要手工修改 registry 结构 |
| 报告渲染失败 | 展示错误，保留已评估 registry |
| `sync push` 失败 | 告知用户报告已本地生成，需稍后执行同步 |

## 输出要求

所有面向测试团队的输出必须使用中文，并包含：

- 判定：`ADMITTED`、`REJECTED`、`CONDITIONAL` 或 `PENDING`
- 报告路径
- 阻塞原因列表；无阻塞时写“无阻塞问题”
- 团队模式下的同步结果

报告必须使用合法 Markdown 表格；不得使用 emoji、box-drawing 字符或装饰性 ASCII 边框。

## 环境变量

```bash
export GITLAB_TOKEN="glpat-xxxx"
export GITLAB_HOST="https://gitlab.example.com"
export CRVIGIL_MODE=team
export CRVIGIL_MODE=personal
export CRVIGIL_JOB_MAPPING='{"unit_test":"run-tests","coverage":"coverage-report","static_scan":"sonar","smoke_test":"smoke"}'
```

`CRVIGIL_MODE` 默认为 `team`。个人模式跳过 Git 同步，仅在本地更新 registry 和报告。
