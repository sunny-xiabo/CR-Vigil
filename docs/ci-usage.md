# CI and Scheduled Usage

CR-Vigil 可以在 CI 或定时任务中运行日报、周报和 JSON 校验。

## 环境变量

```bash
export GITLAB_TOKEN="glpat-xxxx"
export CRVIGIL_MODE=personal
```

CI 中建议使用 `CRVIGIL_MODE=personal`，避免自动 Git push。需要推送报告时，由 CI 自己控制 commit/push 权限。

## 定时日报

```bash
python -m crvigil --no-sync digest
```

## 定时周报

```bash
python -m crvigil --no-sync trend
```

## JSON 健康检查

```bash
python -m crvigil validate
```

需要自动修复常见 JSON 格式问题时：

```bash
python -m crvigil validate --repair --write
```

## 退出码

- `0`：命令执行成功。业务判定可能是 `ADMITTED`、`REJECTED`、`CONDITIONAL` 或 `PENDING`。
- 非 `0`：执行异常，例如 Token 缺失、GitLab API 失败、JSON 修复失败或报告生成失败。

## 并发说明

CR-Vigil 会对 `data/pr-registry.json` 的读-改-写加文件锁。registry 只保存轻量索引，完整 MR 当前状态写入 `data/mrs/<PR_ID>.json`，历史动作追加到 `data/events/YYYY-MM.jsonl`。多个 CI 任务共享同一工作区时仍建议串行运行，或通过 `--registry`、`--output-root` 指定独立目录。

## 保留策略

CI/定时任务会按 `cr-vigil.yml` 清理过期快照，并限制单个 MR 的 history 长度：

```yaml
storage:
  history_limit_per_mr: 50
  daily_snapshot_retention_days: 30
  weekly_snapshot_retention_weeks: 12
```
