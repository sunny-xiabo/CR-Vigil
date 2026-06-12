# Gate Rules Reference

本文件将四道门禁规则结构化为可机读的判定逻辑。门禁评估引擎必须严格按此规则判定，不允许自行调整阈值或条件。

---

## Gate 1: CI 质量红线（可配置）

**原则**: 有 CI 管线的团队，门禁未过则提测流水线直接失败。无 CI 管线的团队，门禁一自动跳过，不阻断提测。

### CI 模式配置

系统通过 `ci_mode` 参数控制门禁一的行为，支持三种模式：

| 模式 | 含义 | 门禁一行为 |
|------|------|-----------|
| `enabled` | 团队有 CI 管线，强制检查 | CI 数据缺失视为 FAIL |
| `disabled` | 团队无 CI 管线 | 门禁一直接标记 N/A，不参与准入判定 |
| `auto` | 自动检测（推荐默认） | 有 CI 数据则 enabled，无则 disabled |

`ci_mode` 可通过以下方式配置（优先级从高到低）：

1. 环境变量 `CRVIGIL_CI_MODE`：全局设置，`enabled` / `disabled` / `auto`
2. 环境变量 `CRVIGIL_CI_MODE_MAP`：按项目设置，JSON 格式
3. 默认值：`auto`

### 检查项与阈值（仅 ci_mode == enabled 时生效）

| ID | 检查项 | 阈值 | 不达标后果 |
|----|--------|------|-----------|
| G1-01 | 新增/修改代码单元测试通过率 | 100% | 阻断，流水线失败 |
| G1-02 | 增量代码覆盖率 | >= 70% | 阻断，流水线失败 |
| G1-03 | 静态扫描阻断性问题 (Blocker) | 0 个 | 阻断，流水线失败 |
| G1-04 | 静态扫描严重问题 (Critical) | 0 个 | 阻断，流水线失败 |
| G1-05 | 流水线冒烟测试通过率 | 100% | 阻断，流水线失败 |

### 判定逻辑

```
第一步：确定 CI 模式
ci_mode = resolve_ci_mode(project_path, env_vars)  // enabled | disabled | auto

第二步：auto 模式下自动检测
IF ci_mode == auto:
    has_ci = (pipeline_url 非空) OR (unit_test.total > 0) OR (smoke_test.total > 0)
    IF has_ci:
        ci_mode = enabled
    ELSE:
        ci_mode = disabled

第三步：根据最终模式判定
IF ci_mode == disabled:
    Gate1.STATUS = N/A
    所有子项标记为 N/A，不参与最终准入判定

IF ci_mode == enabled:
    G1-01.PASS = (unit_test.pass_rate == 100)
    G1-02.PASS = (coverage.incremental_coverage_pct >= 70)
    G1-03.PASS = (static_scan.blocker_count == 0)
    G1-04.PASS = (static_scan.critical_count == 0)
    G1-05.PASS = (smoke_test.pass_rate == 100)
    Gate1.STATUS = (全部 PASS) ? PASS : FAIL
```

### 注意事项

- 覆盖率采用**增量**而非整体覆盖率，避免存量代码欠债造成阻力
- 静态扫描的 Warning 级别不阻断，但需在 PR 说明中解释
- 冒烟用例由**开发负责编写和维护**，测试负责验收
- 任何一项 FAIL 均导致整道门禁 FAIL
- CI 模式为 N/A 时，报告中标注「该项目未配置 CI 管线，门禁一自动跳过」
- `auto` 模式下首次检测无 CI 数据，标记为 N/A；后续如出现 CI 数据则自动切换为 enabled

---

## Gate 2: AI 代码声明 + 人工 Code Review

**原则**: AI 代码进入测试前，必须经过人类工程师的批准。

### 检查项与条件

| ID | 检查项 | 条件 | 不达标后果 |
|----|--------|------|-----------|
| G2-01 | AI 使用声明 | AI 占比字段已填写，声明了使用工具和主要模块 | 如 AI 占比 > 0% 且未声明 → FAIL |
| G2-02 | 审查人资格 | 至少 1 名非作者的资深工程师（>= 3 年或 Senior 级别以上） | 不满足 → FAIL |
| G2-03 | 实质性评论 | 审查人至少留 1 条实质性评论（非 "LGTM"、"好的"、"OK" 等形式用语） | 0 条或全部为形式用语 → FAIL |
| G2-04 | Checklist 完成 | 12 项 AI Code Review Checklist 全部勾选 | 任何一项未勾选 → FAIL |
| G2-05 | 审查时限 | CR 应在提测申请后 24 小时内完成 | 超时 → WARN（不阻断但升级至 TL） |

### 形式主义评论检测规则

以下评论模式视为无效（形式主义）：
- 仅包含 "LGTM"、"Looks Good To Me"、"好的"、"OK"、"没问题"、"+1"、"Approved"
- 仅包含表情符号或单字符
- 无任何技术内容（少于 10 个有意义的字符）

以下评论视为实质性：
- 提及了具体代码行或逻辑
- 提出了改进行动或问题
- 讨论了边界条件、性能、安全等具体维度
- 包含了代码建议或技术讨论

### 判定逻辑

```
G2-01.PASS = (ai_usage.percentage == 0) OR
             (ai_usage.percentage > 0 AND ai_usage.declared == true)

G2-02.PASS = (review.reviewer != null) AND
             (review.reviewer != pr.author) AND
             (review.reviewer_level IN [senior, staff])

G2-03.PASS = (review.substantive_comments >= 1)

G2-04.PASS = (review.checklist.ck_01 AND ck_02 AND ... AND ck_12)  // 全部为 true

G2-05.WARN = (review.review_approved_at - pr.updated_at > 24h)  // 不阻断

Gate2.STATUS = (G2-01.PASS AND G2-02.PASS AND G2-03.PASS AND G2-04.PASS)
              ? (G2-05.WARN ? WARN : PASS)
              : FAIL
```

### 触发条件

AI 辅助代码比例 > 0%，或连续 >= 10 行由 AI 生成时，触发强制 CR。

---

## Gate 3: 测试准入声明

**原则**: 缺任何一项材料直接退回，不排期，不计入测试绩效。

### 检查项

| ID | 材料 | 形式 | 不达标后果 |
|----|------|------|-----------|
| G3-01 | CI 通过证明 | 流水线截图或链接，显示所有质量门禁绿色通过 | 缺失 → FAIL，退回 |
| G3-02 | CR 批准链接 | PR 链接，可见 Checklist 全部勾选 + 实质性评论 | 缺失 → FAIL，退回 |
| G3-03 | AI 代码自检声明 | 勾选表，开发签字确认 | 缺失 → FAIL，退回 |

### 自检声明五项确认

| ID | 确认项 |
|----|--------|
| SI-01 | 本次提测代码已通过 CI 全部质量门禁 |
| SI-02 | 所有 AI 辅助代码已完成 CR，Checklist 全部勾选 |
| SI-03 | 已对 AI 生成的边界条件和异常逻辑进行人工验证 |
| SI-04 | 本人已在本地完成基础功能自测，主流程可正常运行 |
| SI-05 | 无已知的阻断性缺陷被刻意隐瞒 |

### 判定逻辑

```
G3-01.PASS = (declaration.ci_proof_provided == true)
G3-02.PASS = (declaration.cr_approval_link 不为空)
G3-03.PASS = (declaration.self_inspection.submitted == true) AND
             (SI-01 至 SI-05 全部为 true)

Gate3.STATUS = (G3-01.PASS AND G3-02.PASS AND G3-03.PASS) ? PASS : FAIL
```

### 重要规则

- 测试人员**不得**因"开发压力"接受违规提测
- 因流程缺失导致的质量问题，测试**完全免责**
- 门禁是硬性规定，不存在"特事特办"

---

## Gate 4: 故障追溯倒查（事后问责链）

**原则**: 门禁四不阻断提测，但确保故障可追溯。这是事后问责的基础设施。

### 检查项

| ID | 追溯项 | 说明 |
|----|--------|------|
| G4-01 | CI 流水线状态记录 | 对应 PR 的 CI 运行历史 |
| G4-02 | CR 记录 | Reviewer 是谁、留了什么评论、何时批准 |
| G4-03 | AI 代码自检声明副本 | 开发签字的自检声明 |
| G4-04 | 发布记录与审批链 | 发布流程与审批人 |

### 故障定责原则

| 场景 | 定责 |
|------|------|
| 门禁齐全但仍出现故障 | 开发承担主要责任，测试免责 |
| 绕过门禁（CR 走形式、CI 未通过强推） | 开发 + CR 人共同承担，加重处理 |
| 门禁流程本身存在漏洞导致故障 | 由质量负责人承担流程责任 |

### 判定逻辑

```
Gate4.STATUS = 不参与准入判定，始终为 N/A（对提测流程而言）

仅在线上故障复盘时触发追溯：
  Gate4.READY = (G4-01 记录可拉取) AND
                (G4-02 记录可拉取) AND
                (G4-03 副本可拉取) AND
                (G4-04 记录可拉取)
```

---

## 整体准入判定

```
// 有效门禁列表（排除 N/A 的门禁，不参与判定）
active_gates = [g for g in [Gate1, Gate2, Gate3] if g.STATUS != N/A]

// 核心判定
IF 所有 active_gates 状态均为 PASS:
    IF Gate2.STATUS == WARN:
        Verdict = CONDITIONAL（可提测但注明风险）
    ELSE:
        Verdict = ADMITTED
ELSE IF 任一 active_gate 状态为 FAIL:
    Verdict = REJECTED
ELSE IF 任一 active_gate 状态为 PENDING:
    Verdict = PENDING

// 常见场景
- Gate1=N/A (无CI), Gate2=PASS, Gate3=PASS → ADMITTED
- Gate1=N/A (无CI), Gate2=FAIL → REJECTED（门禁二阻塞）
- Gate1=FAIL, Gate2=PASS, Gate3=PASS → REJECTED（门禁一阻塞）
- Gate2=WARN 且其他 PASS → CONDITIONAL
```

### CI 模式对判定的影响

| CI 模式 | Gate1 状态 | 参与判定 | 备注 |
|---------|-----------|---------|------|
| disabled | N/A | 否 | 团队无 CI 管线，门禁一自动跳过 |
| auto（无 CI 数据） | N/A | 否 | 自动检测为无 CI 管线 |
| auto（有 CI 数据） | PASS / FAIL | 是 | 按正常阈值评估 |
| enabled | PASS / FAIL | 是 | 强制检查，CI 数据缺失即 FAIL |

### 门禁三的 CI 材料调整

当 CI 模式为 N/A 时，门禁三的 G3-01（CI 通过证明）同步调整为 N/A，不再要求提供 CI 证明。此时门禁三仅检查 G3-02（CR 批准链接）和 G3-03（自检声明）。

---

## 违规级别与处理

| 违规次数 | 处理措施 | registry 中标记 |
|---------|---------|---------------|
| 第 1 次 | 测试打回，邮件通知开发及其直属 Leader | violations = 1 |
| 第 2 次 | 记录为"无效提测"，纳入绩效评估 | violations = 2 |
| 第 3 次 | 暂停提测权限，需重新通过质量培训后恢复 | violations = 3 |
| CR 人走形式 | 线上故障连带定责，记录至 Reviewer 绩效档案 | formalism_incident = true |
| 管理层强推绕过 | 故障复盘明确记录，纳入管理层问责 | bypass_incident = true |
