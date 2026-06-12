# CR 监控周报

**报告周期**：{WEEK_START} 至 {WEEK_END}
**生成时间**：{TIMESTAMP}
**报告编号**：WTR-{WEEK_START}

---

## 本周概览

- 本周监控 PR 总数：{TOTAL_PR_COUNT}
- 整体准入率：{OVERALL_ADMISSION_RATE}%
- PR 从创建到准入的平均时间：{AVG_TIME_TO_ADMIT} 天
- 最常见的阻塞问题：{TOP_BLOCKING_ISSUE}
- AI 使用趋势：{AI_TREND_DIRECTION}（与上周相比 {AI_TREND_CHANGE}%）
- 需要升级处理的复现违规：{ESCALATION_COUNT} 起

---

## 团队合规评分

**本周评分：{TEAM_COMPLIANCE_SCORE} / 100**

| 维度 | 满分 | 得分 | 说明 |
|------|------|------|------|
| CI 合规率 | 30 | {CI_COMPLIANCE_SCORE} | {CI_COMPLIANCE_DESC} |
| CR 合规率 | 30 | {CR_COMPLIANCE_SCORE} | {CR_COMPLIANCE_DESC} |
| 声明合规率 | 20 | {DECLARATION_COMPLIANCE_SCORE} | {DECLARATION_COMPLIANCE_DESC} |
| AI 声明合规率 | 20 | {AI_DECLARATION_COMPLIANCE_SCORE} | {AI_DECLARATION_COMPLIANCE_DESC} |

*注：合规率评分标准参见门禁规则参考文档，各维度得分反映了本周所有 PR 在对应门禁阶段的首次通过情况。*

---

## 本周每日准入率趋势

| 日期 | 活跃 PR 数 | 已准入 | 已拒绝 | 有条件通过 | 准入率 |
|------|-----------|--------|--------|-----------|--------|
{MONDAY_ROW}
{TUESDAY_ROW}
{WEDNESDAY_ROW}
{THURSDAY_ROW}
{FRIDAY_ROW}
{SATURDAY_ROW}
{SUNDAY_ROW}

---

## 门禁违规趋势

### 门禁一：CI 质量红线

| 指标 | 本周 | 上周 | 变化 |
|------|------|------|------|
| 活跃检查项数（CI enabled） | {G1_ACTIVE_COUNT} | {G1_ACTIVE_LAST} | {G1_ACTIVE_CHANGE} |
| N/A（无 CI，自动跳过） | {G1_NA_COUNT} | {G1_NA_LAST} | {G1_NA_CHANGE} |
| 违规总数（enabled 中） | {G1_THIS_WEEK} | {G1_LAST_WEEK} | {G1_CHANGE} |
| 单元测试未通过 | {G1_UT_COUNT} | {G1_UT_LAST} | {G1_UT_CHANGE} |
| 覆盖率低于阈值 | {G1_COV_COUNT} | {G1_COV_LAST} | {G1_COV_CHANGE} |
| 静态扫描阻断问题 | {G1_STATIC_COUNT} | {G1_STATIC_LAST} | {G1_STATIC_CHANGE} |
| 冒烟测试未通过 | {G1_SMOKE_COUNT} | {G1_SMOKE_LAST} | {G1_SMOKE_CHANGE} |

### 门禁二：AI 声明 + 人工 Code Review

| 指标 | 本周 | 上周 | 变化 |
|------|------|------|------|
| 违规总数 | {G2_THIS_WEEK} | {G2_LAST_WEEK} | {G2_CHANGE} |
| AI 使用未声明 | {G2_UNDECLARED} | {G2_UNDECLARED_LAST} | {G2_UNDECLARED_CHANGE} |
| 审查人资质不符 | {G2_REVIEWER} | {G2_REVIEWER_LAST} | {G2_REVIEWER_CHANGE} |
| 无实质性评论 | {G2_COMMENTS} | {G2_COMMENTS_LAST} | {G2_COMMENTS_CHANGE} |
| Checklist 未完成 | {G2_CHECKLIST} | {G2_CHECKLIST_LAST} | {G2_CHECKLIST_CHANGE} |

### 门禁三：测试准入声明

| 指标 | 本周 | 上周 | 变化 |
|------|------|------|------|
| 违规总数 | {G3_THIS_WEEK} | {G3_LAST_WEEK} | {G3_CHANGE} |
| CI 通过证明缺失 | {G3_CI_PROOF} | {G3_CI_PROOF_LAST} | {G3_CI_PROOF_CHANGE} |
| CR 批准链接缺失 | {G3_CR_LINK} | {G3_CR_LINK_LAST} | {G3_CR_LINK_CHANGE} |
| 自检声明缺失 | {G3_SELF} | {G3_SELF_LAST} | {G3_SELF_CHANGE} |

---

## AI 代码使用统计

| 指标 | 本周 | 上周 | 变化 |
|------|------|------|------|
| 平均 AI 代码占比 | {AVG_AI_PCT}% | {AVG_AI_PCT_LAST}% | {AVG_AI_PCT_CHANGE}% |
| AI 占比 > 50% 的 PR 数 | {HIGH_AI_COUNT} | {HIGH_AI_COUNT_LAST} | {HIGH_AI_CHANGE} |
| 使用 AI 的 PR 数（任意占比） | {ANY_AI_COUNT} | {ANY_AI_COUNT_LAST} | {ANY_AI_CHANGE} |
| 未声明 AI 的 PR 数（标记） | {UNDECLARED_COUNT} | {UNDECLARED_COUNT_LAST} | {UNDECLARED_CHANGE} |
| 最常用的 AI 工具 | {TOP_TOOL} | {TOP_TOOL_LAST} | -- |

### 本周 AI 工具分布

| 工具 | PR 数量 | 平均 AI 占比 |
|------|--------|-------------|
{AI_TOOL_ROWS}

---

## 本周 Top 阻塞问题

| 排名 | 问题类型 | 出现次数 | 涉及 PR | 平均阻塞天数 |
|------|---------|---------|--------|-------------|
{TOP_BLOCKING_ROWS}

---

## 审查人统计

| 审查人 | 审查 PR 数 | 平均实质性评论数 | 形式主义事件数 | 平均审查耗时 |
|--------|-----------|----------------|--------------|-------------|
{REVIEWER_STATS_ROWS}

**形式主义定义**：评论仅含 "LGTM"、"OK"、"+1"、"好的"、"没问题" 等用语，无任何技术内容。

---

## 违规复现追踪

| 开发人员 | 本周违规次数 | 累计复现次数 | 升级级别 | 处理措施 |
|---------|------------|------------|---------|---------|
{VIOLATION_RECURRENCE_ROWS}

**违规升级级别说明**：
- 第 1 级（第 1 次违规）：警告 -- 邮件通知开发本人及其直属 Leader
- 第 2 级（第 2 次违规）：KPI 影响 -- 记录为"无效提测"，纳入绩效评估
- 第 3 级（第 3 次违规）：暂停提测权限 -- 需重新通过质量培训后恢复

---

## 门禁四：故障追溯（如有）

{INCIDENT_SECTION}

*如本周无线上故障：「本周无线上故障记录。所有已准入 PR 的门禁四追溯记录均可用。」*

---

## 四周合规趋势

| 周次 | PR 总数 | 准入率 | 门禁一平均 | 门禁二平均 | 门禁三平均 | 平均准入耗时 |
|------|--------|--------|-----------|-----------|-----------|-------------|
{WEEK_COMPLIANCE_ROWS}

---

## 建议

{RECOMMENDATIONS}

---

*本报告由 CR-Vigil Monitor Skill 自动生成。数据周期：{WEEK_START} 至 {WEEK_END}。下一次报告计划于 {NEXT_WEEK_START} 生成。*
