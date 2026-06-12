# 提测准入报告：{PR_TITLE}

**报告编号**：ADM-{PR_ID}-{DATE}
**生成时间**：{TIMESTAMP}
**PR 链接**：[{PR_TITLE}]({PR_URL})
**开发人员**：{AUTHOR}
**AI 代码占比**：{AI_PERCENTAGE}%
**审查人**：{REVIEWER}
**CI 模式**：{CI_MODE_LABEL}

---

## 准入判定：{VERDICT_LABEL}

{VERDICT_SUMMARY}

---

## 门禁状态总览

| 门禁 | 要求 | 状态 | 依据 |
|------|------|------|------|
| 门禁一：CI 质量红线 | {GATE1_REQUIREMENT} | {GATE1_STATUS} | {GATE1_SUMMARY} |
| 门禁二：AI 声明 + 人工 CR | AI 已声明、资深审查人、实质性评论、Checklist 全部勾选 | {GATE2_STATUS} | {GATE2_SUMMARY} |
| 门禁三：测试准入声明 | {GATE3_REQUIREMENT} | {GATE3_STATUS} | {GATE3_SUMMARY} |
| 门禁四：故障追溯倒查 | 事后追溯记录可用 | 不适用 | 不参与提测准入判定 |

---

## 变更影响与风险分析

### 变更影响分析

| 指标 | 值 |
|------|------|
| 变更文件数 | {CHANGES_COUNT} |
| 新增行数 | {ADDITIONS} |
| 删除行数 | {DELETIONS} |
| 净增行数 | {NET_ADDITIONS} |
| 变更规模评级 | {CHANGE_SCALE_RATING} |
| 风险提示 | {SCALE_RISK_WARNING} |

### AI 代码分布

{AI_DISTRIBUTION_TABLE}

### 综合风险评估

| 风险因素 | 评级 | 说明 |
|---------|------|------|
| AI 代码占比 | {AI_USAGE_RISK_LEVEL} | {AI_USAGE_RISK_DESC} |
| 变更规模 | {CHANGE_SCALE_RISK_LEVEL} | {CHANGE_SCALE_RISK_DESC} |
| CR 质量 | {CR_QUALITY_RISK_LEVEL} | {CR_QUALITY_RISK_DESC} |
| 模块敏感度 | {MODULE_SENSITIVITY_RISK_LEVEL} | {MODULE_SENSITIVITY_RISK_DESC} |
| **整体风险等级** | **{OVERALL_RISK_LEVEL}** | {OVERALL_RISK_DESC} |

---

## 测试重点建议

{TESTING_RECOMMENDATIONS}

---

## 门禁详细分析

### 门禁一：CI 质量红线

**CI 模式**：{CI_MODE_LABEL}

{GATE1_SECTION_CONTENT}

### 门禁二：AI 代码声明 + 人工 Code Review

**AI 使用声明**

| 项目 | 内容 |
|------|------|
| 是否使用 AI | {AI_USED} |
| 是否已在 PR 中声明 | {AI_DECLARED} |
| AI 生成代码占比 | {AI_PERCENTAGE}% |
| 使用的 AI 工具 | {AI_TOOLS} |
| AI 生成的主要模块 | {AI_MODULES} |

**Code Review 情况**

| 项目 | 内容 |
|------|------|
| 审查人 | {REVIEWER} |
| 审查人级别 | {REVIEWER_LEVEL} |
| 审查人是否为 PR 作者 | {IS_SELF_REVIEW} |
| 实质性评论数量 | {SUBSTANTIVE_COMMENTS_COUNT} |
| 评论质量判定 | {COMMENT_QUALITY} |

**AI Code Review Checklist（12 项）**

| 编号 | 分类 | 检查项 | 状态 |
|------|------|--------|------|
| CK-01 | 逻辑正确性 | 边界条件已覆盖（空值、零值、最大值、并发场景） | {CK01_STATUS} |
| CK-02 | 逻辑正确性 | 异常处理完整（不吞异常、有合理的降级或告警） | {CK02_STATUS} |
| CK-03 | 逻辑正确性 | 业务逻辑与需求文档一致，无过度实现或缺失实现 | {CK03_STATUS} |
| CK-04 | 性能与安全 | 无循环内数据库查询（N+1 问题） | {CK04_STATUS} |
| CK-05 | 性能与安全 | 无明显内存泄漏风险（大对象、未关闭资源等） | {CK05_STATUS} |
| CK-06 | 性能与安全 | 无硬编码敏感信息（密码、Token、AK/SK 等） | {CK06_STATUS} |
| CK-07 | 性能与安全 | 输入数据有校验，无 SQL 注入 / XSS 等基础安全漏洞 | {CK07_STATUS} |
| CK-08 | 代码质量 | 无死代码或冗余逻辑 | {CK08_STATUS} |
| CK-09 | 代码质量 | 命名清晰，无魔法数字 | {CK09_STATUS} |
| CK-10 | 代码质量 | 单元测试覆盖了主要逻辑路径和异常分支 | {CK10_STATUS} |
| CK-11 | 代码质量 | 无明显 AI 幻觉痕迹（调用不存在的方法、错误引用第三方 API） | {CK11_STATUS} |
| CK-12 | 代码质量 | 代码符合团队编码规范 | {CK12_STATUS} |

Checklist 完成情况：{CHECKLIST_COMPLETED_COUNT}/12（{CHECKLIST_COMPLETION_PCT}%）

**门禁二判定**：{GATE2_VERDICT}

{GATE2_DETAIL_NOTES}

### 门禁三：测试准入声明

| 材料 | 要求 | 是否提供 | 状态 |
|------|------|---------|------|
| CI 通过证明 | {CI_PROOF_REQUIREMENT} | {CI_PROOF_PROVIDED} | {CI_PROOF_STATUS} |
| CR 批准链接 | 可见 Checklist 全部勾选 + 实质性评论的 PR 链接 | {CR_LINK_PROVIDED} | {CR_LINK_STATUS} |
| AI 代码自检声明 | 开发签字确认的勾选表 | {SELF_INSPECTION_PROVIDED} | {SELF_INSPECTION_STATUS} |

**自检声明五项确认**

| 编号 | 确认项 | 状态 |
|------|--------|------|
| SI-01 | {SI01_REQUIREMENT} | {SI01_STATUS} |
| SI-02 | 所有 AI 辅助代码已完成 CR，Checklist 全部勾选 | {SI02_STATUS} |
| SI-03 | 已对 AI 生成的边界条件和异常逻辑进行人工验证 | {SI03_STATUS} |
| SI-04 | 本人已在本地完成基础功能自测，主流程可正常运行 | {SI04_STATUS} |
| SI-05 | 无已知的阻断性缺陷被刻意隐瞒 | {SI05_STATUS} |

**门禁三判定**：{GATE3_VERDICT}

{GATE3_DETAIL_NOTES}

### 门禁四：故障追溯倒查

门禁四不参与提测准入判定。其作用是确保线上故障发生时，以下记录可追溯：

- 对应 PR 的 CI 流水线状态记录
- CR 记录（审查人、评论内容、批准时间）
- AI 代码自检声明副本
- 发布记录与审批链

**门禁四状态**：{GATE4_STATUS}

---

## 阻塞问题清单

{BLOCKING_ISSUES_LIST}

---

## 建议

{RECOMMENDATIONS}

---

## 历史记录

| 时间 | 事件 |
|------|------|
| {HISTORY_ENTRIES} |

---

*本报告由 CR-Vigil Monitor Skill 自动生成，基于《AI 代码质量管控方案 V2.0》定义的四道门禁体系进行评估。*
