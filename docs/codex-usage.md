# Codex Usage

Codex 处理本项目时，优先使用统一 Python 入口。

## 常用任务

### 评估单个 MR

```bash
python -m crvigil admit <MR链接>
```

本地实验时避免 Git 同步：

```bash
python -m crvigil --no-sync admit <MR链接>
```

### 使用本地 Markdown 文件评估

```bash
python -m crvigil --no-sync admit-file <文件路径>
```

文件中可以包含一个或多个 PR 片段，输出 JSON 中读取 `verdicts` 和 `report_paths`。

### 生成日报

```bash
python -m crvigil digest
```

### 生成周报

```bash
python -m crvigil trend
```

### 校验或修复 registry

```bash
python -m crvigil validate
python -m crvigil validate --repair --write
```

## 输出处理

命令输出 JSON。Codex 应读取：

- `ok`
- `command`
- `verdict`
- `report_path`
- `blocking_reasons`
- `stage0_json_check`
- `stage1`
- `stage1_5_snapshot`
- `stage2`
- `stage3`
- `sync_status`

`verdict=REJECTED` 时不要当作执行失败，应把 `blocking_reasons` 作为业务结论反馈给用户。

如果需要并发或隔离实验，Codex 应使用独立路径：

```bash
python -m crvigil --registry /tmp/crvigil/pr-registry.json --output-root /tmp/crvigil/reports --no-sync digest
```
