# Changelog

## 2026-06-16

### Fixed

- 团队同步时将 `data/snapshots/` 纳入 Git staging，避免日报/周报快照只存在本地。
- 修正团队同步的错误处理，`git add` 或 `git commit` 失败时立即返回同步失败，不再继续 push 并误报成功。
- 调整阶段顺序为先 `sync pull` 再进行 JSON 自检，确保拉取后的 registry 也会被校验和修复。

### Added

- 新增统一 Python 子命令 `python -m crvigil admit-file <文件路径>`，文件模式可解析一个或多个 PR 片段并生成对应提测报告。
- 新增 Markdown 文件采集器 `crvigil/file_collect.py`，文件模式只做数据映射，门禁判定继续复用统一 evaluator。
- 新增 `storage.history_limit_per_mr`、`storage.daily_snapshot_retention_days`、`storage.weekly_snapshot_retention_weeks` 配置，用于限制 MR 历史和快照增长。
- 新增 `sync.push_retry` 配置，团队 push 失败后可自动 pull --rebase 并重试。
- CLI 输出新增 `sync_status`，用于区分 `synced`、`skipped` 和 `failed`。
- 新增 per-MR 双写存储：采集和评估会同步写入 `data/mrs/<PR_ID>.json`，registry 中补充 `record_path`。
- 新增追加式事件日志 `data/events/YYYY-MM.jsonl`，记录采集、门禁评估和报告生成事件。
- 新增摘要 snapshot 结构，日报/周报快照只保留报表所需 PR 摘要，完整 MR 详情由 `data/mrs/<PR_ID>.json` 承载。
- 新增 registry hydrate/index 存储层，读取时通过 `record_path` 自动加载完整 MR，写入时将 `data/pr-registry.json` 保存为轻量索引。

### Changed

- 更新 README 和 Skill 文档，统一推荐 `python -m crvigil validate`，修正 renderer 包结构说明和重复表头。
- `.gitignore` 增加 `.pytest_cache/`。
- 增加同步行为回归测试，覆盖快照 staging、add 失败、commit 失败和 push retry。
- 增加 `admit-file`、history 截断、snapshot 清理、per-MR 文件生成和事件日志回归测试。
- 增加摘要 snapshot 回归测试，防止快照重新写入完整 CI、declaration 和长 history。
- 将 `data/pr-registry.json` 迁移为 `storage_mode=index` 的轻量索引结构。

## 2026-06-15

### Changed

- 将 CR-Vigil 重构为 Skill 驱动编排模式，保留 `/cr-vigil-monitor --admit|--admit-file|--digest|--trend` 作为用户入口。
- 瘦身 `cr-vigil-monitor` Skill 说明，将门禁判定和报告生成下沉到确定性脚本。
- 整理项目结构，将核心 evaluator、renderer、json tools 移入 `crvigil/` 包，`.claude/skills/.../scripts/` 仅保留 legacy wrapper。
- 简化 README 操作说明，新增“最简操作”入口，突出测试人员日常只需执行 `/cr-vigil-monitor --admit <MR链接>`。
- 引入阶段驱动规则：阶段 1 完成采集和门禁评估后，才允许进入单 MR 提测报告、日报或周报生成。
- 增加 JSON 格式自检机制，读取 registry 时先校验并尝试修复常见 JSON 格式问题。
- 新增通用 Python 入口 `python -m crvigil`，供 Claude Code、Codex、通用 Agent、CI 和手动执行复用。
- Python GitLab client 支持 `CRVIGIL_CA_FILE` 和 `CRVIGIL_SSL_VERIFY=false`，适配内网 GitLab 证书环境。
- 新增 `cr-vigil.yml` 报告定制配置，支持日报/周报关键章节开关和 profile。
- 新增日报/周报快照层，报告生成前写入 `data/snapshots/`，周报优先使用本周每日快照。
- 新增 `AGENTS.md`、`docs/codex-usage.md`、`docs/ci-usage.md` 和 `pyproject.toml`，补齐多 Agent 与可安装命令入口。
- 为 registry 读-改-写增加文件锁，降低多 Agent/CI 并发写入覆盖风险。
- 在评估 JSON 中补充 `evidence` 字段，包含 MR、Pipeline、CR 等人工复核链接。
- 明确 Agent 契约为 CLI 兼容，补充输入参数、stdout/stderr、退出码和并发策略说明。

### Added

- 新增门禁评估脚本：`.claude/skills/cr-vigil-monitor/scripts/evaluate_gates.py`。
- 新增报告渲染脚本：`.claude/skills/cr-vigil-monitor/scripts/render_report.py`。
- 新增单元测试，覆盖门禁判定、现有样例 verdict 回归、报告文件生成和日报/周报渲染。
- 报告渲染前新增阶段 1 完成校验，防止跳过评估直接生成报告。
- 新增 JSON 工具脚本和 `validate_data.py`，支持 `json_repair` 可选修复及内置轻量 fallback 修复。
- 新增 `docs/agent-contract.md`，定义统一命令、JSON 输出、退出码和阶段规则。
- 新增 `crvigil/config.py` 和 `crvigil/snapshots.py`，分别负责配置解析和快照生成。
- 新增 `AGENTS.md`、`docs/codex-usage.md`、`docs/ci-usage.md`。

### Notes

- 第一阶段仍保留 `data/pr-registry.json` 作为共享 registry，不迁移存储结构。
- 现有 GitLab 采集脚本和团队 Git 同步脚本保持兼容。
