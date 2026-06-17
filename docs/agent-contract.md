# CR-Vigil Agent Contract

本文件给 Claude Code、Codex、通用 Agent 和 CI 使用。CR-Vigil 的多 Agent 兼容方式是 CLI 兼容：任何能执行子进程并读取 stdout JSON 的工具都可以接入。所有自动化入口都应调用统一 Python 入口，不直接拼接底层脚本。

## 统一入口

```bash
python -m crvigil admit <MR链接>
python -m crvigil admit-file <Markdown文件路径>
python -m crvigil declare <MR链接>
python -m crvigil evaluate --pr-id <PR_ID> --write
python -m crvigil digest
python -m crvigil trend
python -m crvigil validate --repair --write
```

## 输入契约

推荐使用命令行参数传入输入：

```bash
python -m crvigil admit <MR_URL>
python -m crvigil admit-file <FILE_PATH>
python -m crvigil declare <MR_URL>
python -m crvigil evaluate --pr-id <PR_ID> --write
```

通用参数：

| 参数 | 说明 |
|------|------|
| `--registry <path>` | registry 路径，默认 `data/pr-registry.json` |
| `--output-root <path>` | 报告输出根目录，默认 `reports/` |
| `--config <path>` | 报告配置文件，默认 `cr-vigil.yml` |
| `--no-sync` | 跳过 Git pull/push，适合本地实验和 CI |

环境变量：

| 变量 | 说明 |
|------|------|
| `GITLAB_TOKEN` | GitLab API Token，`admit` 必填 |
| `CRVIGIL_MODE=personal` | 跳过自动团队同步 |
| `CRVIGIL_CA_FILE` | 内网 GitLab CA 文件路径 |
| `CRVIGIL_SSL_VERIFY=false` | 仅本地实验时跳过证书校验 |

本地实验时可跳过 Git 同步：

```bash
python -m crvigil --no-sync admit <MR链接>
python -m crvigil --no-sync admit-file <文件路径>
python -m crvigil --no-sync digest
python -m crvigil --no-sync trend
```

## 输出契约

所有命令向 stdout 输出机器可读 JSON。stderr 只用于执行错误。业务判定 `REJECTED` 仍返回 exit code 0，因为它表示评估成功但拒绝提测；CR-Vigil 不使用 exit code 2 表示业务拒绝。只有认证失败、网络失败、JSON 修复失败、报告生成失败等执行错误返回非 0。

`admit` 输出至少包含：

```json
{
  "ok": true,
  "command": "admit",
  "pr_id": "MR-42-project",
  "verdict": "REJECTED",
  "report_path": "reports/admissions/MR-42-project-admission-2026-06-17.md",
  "blocking_reasons": [],
  "stage1": {
    "evidence": {
      "mr_url": "https://gitlab.example.com/group/project/-/merge_requests/42",
      "pipeline_url": "",
      "cr_approval_link": "https://gitlab.example.com/group/project/-/merge_requests/42"
    }
  }
}
```

`admit-file` 可从一个 Markdown 文件解析一个或多个 PR 片段，输出 `pr_ids`、`verdicts` 和 `report_paths` 列表。文件解析只负责数据映射，门禁判定仍由统一 evaluator 完成。

退出码：

| 退出码 | 含义 |
|--------|------|
| `0` | 命令执行成功，业务 verdict 见 stdout JSON |
| `1` | 执行错误，例如认证、网络、JSON、报告渲染失败 |

并发策略：

- registry 的读-改-写序列会通过 `data/.pr-registry.json.lock` 加文件锁，并使用临时文件 + rename 原子写回。
- `data/pr-registry.json` 是轻量索引，完整 MR 当前状态读取 `record_path` 指向的 `data/mrs/<PR_ID>.json`。
- 每次采集或评估会同步刷新 `data/mrs/<PR_ID>.json`，registry 中只保留摘要和 `record_path`。
- 采集、门禁评估和报告生成会追加写入 `data/events/YYYY-MM.jsonl`，用于审计和后续趋势聚合。
- 多个 Agent 可以处理不同 MR；同一个 MR 并发处理时仍然是最后完成者覆盖最新状态。
- 需要完全隔离实验时，使用 `--registry` 和 `--output-root` 指向独立目录。

## 阶段规则

```text
阶段 0：JSON 自检与修复
阶段 1：采集或读取数据，并完成门禁评估
阶段 1.5：写入 daily/weekly snapshot
阶段 2：基于稳定数据生成 Markdown 报告
阶段 3：团队同步或明确跳过同步
```

阶段 1 未完成时，阶段 2 必须停止。

## 配置和快照

报告定制读取 `cr-vigil.yml`。日报/周报原始数据优先来自：

```text
data/snapshots/
```

快照缺失时，周报可通过 `data/pr-registry.json` 索引 hydrate `data/mrs/<PR_ID>.json` 后生成。快照中的 `prs` 是报表摘要，不包含完整 CI、declaration、自检和长 history；完整 MR 当前状态读取 `data/mrs/<PR_ID>.json`。

健壮性配置：

```yaml
storage:
  history_limit_per_mr: 50
  daily_snapshot_retention_days: 30
  weekly_snapshot_retention_weeks: 12

sync:
  push_retry: 1
```

命令输出包含 `sync_status`，取值通常为 `synced`、`skipped` 或 `failed`。团队同步失败不代表报告未生成，Agent 应同时展示 `stage2.report_path` 和 `stage3.push.detail`。

## 已知演进项

- 当前已进入正式分层存储阶段：registry 为纯索引，`data/mrs/<MR_ID>.json` 为完整当前状态，`data/events/YYYY-MM.jsonl` 为事件日志，snapshot 为报表摘要。
