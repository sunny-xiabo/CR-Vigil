# AGENTS.md

本项目支持 Claude Code、Codex、通用 Agent、CI 和手动执行。Agent 处理 CR-Vigil 任务时，必须优先调用统一 Python 入口，不直接拼接底层脚本。

## 统一入口

```bash
python -m crvigil admit <MR链接>
python -m crvigil admit-file <文件路径>
python -m crvigil digest
python -m crvigil trend
python -m crvigil validate
```

本地实验或避免 Git 同步时：

```bash
python -m crvigil --no-sync admit <MR链接>
python -m crvigil --no-sync admit-file <文件路径>
python -m crvigil --no-sync digest
python -m crvigil --no-sync trend
```

## Agent 行为规则

- `REJECTED` 是业务判定，不是程序错误；命令返回 0 时应正常展示阻塞原因。
- 只有 JSON 校验失败、GitLab API 失败、认证失败、报告生成失败等执行异常才视为失败。
- 不要手工编辑 `data/pr-registry.json`，需要修复 JSON 时调用：

```bash
python -m crvigil validate --repair --write
```

- 日报/周报内容定制优先修改 `cr-vigil.yml`，不要直接改生成后的报告。
- 详细契约见 `docs/agent-contract.md`。
