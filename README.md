# CR-Vigil Monitor

基于 GitLab API 的自动化 CR 监控报告系统。自动采集 MR 数据，按四道门禁体系评估测试准入条件，为测试团队生成结构化的中文报告。支持团队共享模式，一人评估全团队可见。

![CR-Vigil 流程概览](docs/CR-Vigil.png)

## 两种使用方式

### 团队共享模式（推荐）

全团队共享一份 `data/pr-registry.json`，每个测试人员生成的报告自动通过 Git 同步。

```bash
git clone git@github.com:sunny-xiabo/CR-Vigil.git
cd CR-Vigil
export GITLAB_TOKEN="你的个人token"
# 默认就是团队模式，直接使用
/cr-vigil-monitor --admit <MR链接>
# 自动拉取团队最新数据 → 评估 → 自动推送
```

多人同时使用时，Skill 会自动处理 `git pull` 和 `git push`，确保数据一致。

### 个人模式

```bash
export CRVIGIL_MODE=personal
# 数据仅保存在本地，不会推送到团队仓库
```

## 环境配置

### 第一步：设置 GitLab Token

```bash
# 在终端执行（或加入 ~/.zshrc）
export GITLAB_TOKEN="glpat-xxxx"
```

Token 获取路径：GitLab → Settings → Access Tokens → 勾选 `read_api` + `read_repository`。

### 第二步：验证环境

```bash
# 测试 Token 是否有效
curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://gitlab.example.com/api/v4/user" | python3 -c "import sys,json; print(json.load(sys.stdin).get('username','FAIL'))"
```

## 快速开始

### 生成单 MR 提测准入报告

```bash
/cr-vigil-monitor --admit https://gitlab.example.com/your-group/your-project/-/merge_requests/27
```

Skill 会自动：
1. 从 GitLab API 拉取 MR 数据（元信息、CI 结果、审查评论、AI 声明）
2. 按四道门禁逐项评估
3. 生成准入报告到 `reports/admissions/`
4. 向测试团队展示判定结论

### 生成每日汇总

```bash
/cr-vigil-monitor --digest
```

从 `data/pr-registry.json` 读取所有活跃 MR，生成当日的全局状态报告。

### 生成周趋势报告

```bash
/cr-vigil-monitor --trend
```

### 使用本地文件测试（无需 GitLab API）

```bash
/cr-vigil-monitor --admit-file .claude/skills/cr-vigil-monitor/assets/sample-pr.md
```

## 报告类型

| 报告 | 触发方式 | 输出路径 | 用途 |
|------|---------|---------|------|
| 提测准入报告 | `--admit <MR链接>` | `reports/admissions/` | 判断单个 MR 能否进入测试 |
| 每日汇总 | `--digest` | `reports/digests/` | 测试团队晨会使用 |
| 周趋势报告 | `--trend` | `reports/trends/` | 团队复盘与趋势分析 |

## 开发提测材料最小模板

测试执行 Skill 时只需要 MR 链接，但开发必须把准入材料写在 MR 描述或评论中，确保可自动采集、可追溯。如果 MR 中缺少以下材料，提测准入将判定为 `REJECTED`。

```markdown
## AI 辅助声明
- [ ] 本 MR 未使用 AI 辅助
- [ ] 本 MR 使用了 AI 辅助，AI 生成代码占比约：__%
  - 使用工具：
  - AI 生成的主要模块：

## 开发自检声明
- [ ] 本次提测代码已通过 CI 全部质量门禁
- [ ] 所有 AI 辅助代码已完成开发 CR，Checklist 全部勾选
- [ ] 已对 AI 生成的边界条件和异常逻辑进行人工验证
- [ ] 本人已在本地完成基础功能自测，主流程可正常运行
- [ ] 无已知的阻断性缺陷被刻意隐瞒

开发签名：
日期：

## 开发 CR 信息
- Reviewer：
- CR 批准链接：
- 实质性评论链接：
```

说明：
- 开发 CR 指开发侧 Code Review，Reviewer 应为非作者的资深开发工程师。
- 测试负责运行 Skill 做提测准入校验，不承担代码 CR 责任。
- 项目暂未配置 CI 时，CI 证明可标记为 N/A；开发 CR、自检声明、AI 声明仍需提供。

## 四道门禁

| 门禁 | 核心要求 | 状态 |
|------|---------|------|
| 门禁一：CI 质量红线 | UT 100%、覆盖率 >= 70%、无阻断/严重问题、冒烟 100% | PASS / FAIL / N/A |
| 门禁二：AI 声明 + 人工 CR | AI 声明、资深审查人、实质性评论、12 项 Checklist | PASS / WARN / FAIL |
| 门禁三：测试准入声明 | CI 证明、CR 批准链接、自检声明签字 | PASS / FAIL / N/A |
| 门禁四：故障追溯 | 事后问责链，不阻断提测 | N/A |

### 门禁一 CI 模式（自动检测，无需配置）

门禁一默认自动检测 CI 管线是否存在：
- 有 CI 数据 → 正常评估，按阈值判定 PASS/FAIL
- 无 CI 数据 → 自动标记 N/A，不阻断提测

可通过环境变量显式覆盖（非必需）：
```bash
export CRVIGIL_CI_MODE="auto"       # 默认，自动检测
export CRVIGIL_CI_MODE="enabled"    # 强制检查，CI 缺失即 FAIL
export CRVIGIL_CI_MODE="disabled"   # 全局跳过门禁一

# 按项目精细控制
export CRVIGIL_CI_MODE_MAP='{"llm-testgen":"disabled","crrc-service":"enabled"}'
```

## 准入判定

```
排除 N/A 门禁后评估有效门禁:

全部有效门禁 PASS → ADMITTED
门禁二 WARN（其他有效门禁 PASS）→ CONDITIONAL
任一有效门禁 FAIL → REJECTED
门禁一 N/A（无 CI）时不影响准入，提测通过与否由门禁二+三决定
```

## 定时自动生成

每日早 8:57 生成日报：
```
/loop 24h /cr-vigil-monitor --digest
```

每周一早 8:57 生成周报：
```
/loop 7d /cr-vigil-monitor --trend
```

## 项目文件结构

```
CR-Vigil/
├── AI代码质量管控方案.md              # 方案文档
├── README.md                          # 本文件
├── .claude/skills/cr-vigil-monitor/
│   ├── SKILL.md                       # Skill 定义与工作流
│   ├── references/
│   │   ├── data-schema.md             # PR 数据 JSON Schema
│   │   ├── gate-rules.md              # 门禁规则与判定逻辑
│   │   ├── checklist-12-items.md      # 12 项 CR Checklist
│   │   └── gitlab-field-mapping.md    # GitLab API 字段映射
│   └── assets/
│       ├── admission-report-template.md
│       ├── daily-digest-template.md
│       ├── weekly-trend-template.md
│       └── sample-pr.md               # 示例数据
├── scripts/
│   ├── collect-mr-data.sh             # MR 数据采集主脚本
│   └── gitlab-api.sh                  # GitLab API 请求封装
├── data/
│   └── pr-registry.json               # PR 注册表（持久状态）
├── reports/
│   ├── admissions/                    # 准入报告存档
│   ├── digests/                       # 日报存档
│   └── trends/                        # 周报存档
└── docs/
    └── flowchart.md                   # 流程图
```

## 违规升级机制

| 违规次数 | 处理 |
|---------|------|
| 第 1 次 | 测试打回，邮件通知开发及其直属 Leader |
| 第 2 次 | 记录为「无效提测」，纳入绩效评估 |
| 第 3 次 | 暂停提测权限，需重新通过质量培训 |

## CI Job 命名适配

采集脚本通过 Job 名称匹配来识别 CI 检查项。如果你的流水线 Job 命名与默认模式不一致，可通过环境变量配置映射：

```bash
export CRVIGIL_JOB_MAPPING='{
  "unit_test": "run-unit-tests",
  "coverage": "coverage-report",
  "static_scan": "sonarqube-scan",
  "smoke_test": "smoke-tests"
}'
```

默认匹配模式（大小写不敏感）：
- 单元测试：`/unit.?test|ut/`
- 覆盖率：`/coverage|cov/`
- 静态扫描：`/sonar|lint|static.?scan/`
- 冒烟测试：`/smoke/`
