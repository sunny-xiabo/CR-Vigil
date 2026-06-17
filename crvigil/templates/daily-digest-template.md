# CR 监控日报：{DATE}

**生成时间**：{TIMESTAMP}
**活跃 PR 总数**：{ACTIVE_PR_COUNT}
**可提测**：{ADMITTED_COUNT}
**已阻塞**：{BLOCKED_COUNT}

---

## 今日概览

| 指标 | 今日 | 昨日 | 变化 |
|------|------|------|------|
| 活跃 PR 总数 | {ACTIVE_PR_COUNT} | {YESTERDAY_ACTIVE_PR_COUNT} | {ACTIVE_PR_COUNT_CHANGE} |
| 准予提测 | {ADMITTED_COUNT} | {YESTERDAY_ADMITTED_COUNT} | {ADMITTED_COUNT_CHANGE} |
| 已阻塞 | {BLOCKED_COUNT} | {YESTERDAY_BLOCKED_COUNT} | {BLOCKED_COUNT_CHANGE} |

- 最常触发的阻塞门禁：{TOP_BLOCKING_GATE}
- 今日 AI 使用率：{AVG_AI_PERCENTAGE}%（所有活跃 PR 的平均值）
- PR 平均评审天数：{AVG_REVIEW_DAYS} 天

---

## 所有活跃 PR 状态总览

| PR 编号 | 标题 | 开发 | AI占比 | 门禁一 | 门禁二 | 门禁三 | 判定 |
|---------|------|------|--------|--------|--------|--------|------|
{PR_STATUS_ROWS}

---

## 已准入 PR（可排期测试）

{ADMITTED_PR_LIST}

---

## 被阻塞 PR

{BLOCKED_PR_LIST}

---

## 待评估 PR

{PENDING_PR_LIST}

---

## 今日门禁违规分布

| 门禁 | 失败次数 | N/A（无CI） | 涉及 PR |
|------|---------|------------|--------|
| 门禁一：CI 质量红线 | {G1_FAIL_COUNT} | {G1_NA_COUNT} | {G1_FAIL_PRS} |
| 门禁二：AI 声明 + 人工 CR | {G2_FAIL_COUNT} | -- | {G2_FAIL_PRS} |
| 门禁三：测试准入声明 | {G3_FAIL_COUNT} | {G3_NA_COUNT} | {G3_FAIL_PRS} |

---

## 违规详情

### 门禁一违规

{GATE1_FAILURE_DETAILS}

### 门禁二违规

{GATE2_FAILURE_DETAILS}

### 门禁三违规

{GATE3_FAILURE_DETAILS}

---

## 违规复现预警

{VIOLATION_ALERTS}

---

## 今日行动项

{ACTION_ITEMS}

---

*本报告由 CR-Vigil Monitor Skill 自动生成。*
