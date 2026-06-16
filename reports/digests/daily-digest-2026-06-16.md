# CR 监控日报：2026-06-16

**生成时间**：2026-06-16 10:49:39 +0800
**活跃 PR 总数**：3
**可提测**：1
**已阻塞**：1

---

## 今日概览

| 指标 | 今日 | 昨日 | 变化 |
|------|------|------|------|
| 活跃 PR 总数 | 3 | 3 | 0 |
| 准予提测 | 1 | 1 | 0 |
| 已阻塞 | 1 | 2 | -1 |

- 最常触发的阻塞门禁：gate_1
- 今日 AI 使用率：51.7%（所有活跃 PR 的平均值）
- PR 平均评审天数：6.1 天

---

## 所有活跃 PR 状态总览

| PR 编号 | 标题 | 开发 | AI占比 | 门禁一 | 门禁二 | 门禁三 | 判定 |
|---------|------|------|--------|--------|--------|--------|------|
| PR-001 | feat: add user authentication module with JWT support | zhangsan | 45% | 🟢 PASS | 🟢 PASS | 🟢 PASS | 🟢 ADMITTED |
| PR-002 | fix: quick patch for payment callback timeout | wangwu | 80% | 🔴 FAIL | 🔴 FAIL | 🔴 FAIL | 🔴 REJECTED |
| PR-003 | refactor: extract common logging middleware | zhaoliu | 30% | 🟢 PASS | 🟡 WARN | 🟢 PASS | 🟡 CONDITIONAL |

---

## 已准入 PR（可排期测试）

- PR-001：feat: add user authentication module with JWT support（zhangsan）

*如无 PR 通过准入，显示：「当前没有 PR 通过测试准入。」*

---

## 被阻塞 PR

- PR-002：fix: quick patch for payment callback timeout（wangwu）

*如无 PR 被阻塞，显示：「当前没有 PR 被阻塞，所有活跃 PR 均可进入测试。」*

---

## 待评估 PR

按配置隐藏待评估 PR。

*如无 PR 待评估，显示：「当前没有 PR 等待评估。」*

---

## 今日门禁违规分布

| 门禁 | 失败次数 | N/A（无CI） | 涉及 PR |
|------|---------|------------|--------|
| 门禁一：CI 质量红线 | 1 | 0 | PR-002 |
| 门禁二：AI 声明 + 人工 CR | 1 | -- | PR-002 |
| 门禁三：测试准入声明 | 1 | 0 | PR-002 |

---

## 违规详情

### 门禁一违规

按配置隐藏详细门禁原因，详见单 MR 提测报告。

### 门禁二违规

按配置隐藏详细门禁原因，详见单 MR 提测报告。

### 门禁三违规

按配置隐藏详细门禁原因，详见单 MR 提测报告。

---

## 违规复现预警

今日未检测到复现违规。

*如无复现预警，显示：「今日未检测到复现违规。」*

---

## 今日行动项

- PR-002：开发需处理阻塞原因后重新提测。

---

*本报告由 CR-Vigil Monitor Skill 自动生成。下一次日报计划于 下一次 /loop 24h 触发时间 生成。*
