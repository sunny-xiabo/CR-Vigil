# CR-Vigil Monitor 工作流与流程图

本文档描述当前最新提测准入流程。核心责任边界：

- 开发负责在 MR 描述或评论中提供准入材料，包括 AI 辅助声明、开发自检声明、开发 CR 信息、CI 证明。
- 开发 CR 指开发侧 Code Review，Reviewer 应为非作者的资深开发工程师。
- 测试负责运行 `cr-vigil-monitor` Skill 做提测准入校验，不承担代码 CR 责任。
- 测试执行 Skill 时只需要 MR 链接；如果 MR 内材料缺失，准入判定为 `REJECTED`。

## 信息图版

![CR-Vigil 提测准入治理闭环](./cr-vigil-governance-flow.png)

## 一、角色协作主流程

```mermaid
flowchart TD
    START["开发开始 MR 提测准备"] --> DEV_CODE["开发提交代码并创建 MR"]
    DEV_CODE --> DEV_MATERIAL["开发在 MR 描述或评论中填写准入材料"]

    DEV_MATERIAL --> AI_DECL["AI 辅助声明\n是否使用 AI、占比、工具、主要模块"]
    DEV_MATERIAL --> SELF_CHECK["开发自检声明\nCI、CR、边界异常、本地自测、无阻断缺陷"]
    DEV_MATERIAL --> CR_INFO["开发 CR 信息\nReviewer、批准链接、实质性评论链接"]
    DEV_MATERIAL --> CI_INFO["CI 证明\n流水线链接或 N/A 说明"]

    AI_DECL --> DEV_REVIEW["开发侧 Code Review"]
    SELF_CHECK --> DEV_REVIEW
    CR_INFO --> DEV_REVIEW
    CI_INFO --> DEV_REVIEW

    DEV_REVIEW --> REVIEWER_CHECK["非作者资深开发 Reviewer 审查"]
    REVIEWER_CHECK --> REVIEW_COMMENT["留下至少 1 条实质性技术评论"]
    REVIEW_COMMENT --> REVIEW_CHECKLIST["完成 12 项 AI Code Review Checklist"]
    REVIEW_CHECKLIST --> REVIEW_APPROVE["开发 CR 批准"]

    REVIEW_APPROVE --> QA_NOTIFY["开发通知测试\n提供 MR 链接"]
    QA_NOTIFY --> QA_RUN["测试运行 Skill\n/cr-vigil-monitor --admit MR链接"]
    QA_RUN --> COLLECT["Skill 从 GitLab API 采集 MR 数据"]
    COLLECT --> EVALUATE["按四道门禁评估提测准入"]
    EVALUATE --> VERDICT{"准入判定"}

    VERDICT -->|"ADMITTED"| ADMIT["准予提测\n测试排期"]
    VERDICT -->|"CONDITIONAL"| CONDITIONAL["有条件通过\n测试可执行并关注 WARN 风险"]
    VERDICT -->|"REJECTED"| REJECT["拒绝提测\n返回阻塞清单"]

    REJECT --> DEV_FIX["开发补齐材料或修复问题"]
    DEV_FIX --> DEV_MATERIAL
```

## 二、测试执行 Skill 的判断流程

```mermaid
flowchart TD
    MR["测试收到 MR 链接"] --> RUN["运行 /cr-vigil-monitor --admit MR链接"]
    RUN --> FETCH["采集 MR 元信息、描述、CI、评论、审批状态"]

    FETCH --> HAS_MATERIAL{"MR 内准入材料是否齐全?"}
    HAS_MATERIAL -->|"否"| MISS["标记材料缺失"]
    MISS --> REJECTED["REJECTED\n拒绝提测"]

    HAS_MATERIAL -->|"是"| GATE1_MODE{"门禁一 CI 模式"}
    GATE1_MODE -->|"有 CI 数据"| G1_CHECK["检查 UT 100%、覆盖率 >=70%、静态扫描、冒烟测试"]
    GATE1_MODE -->|"无 CI 数据"| G1_NA["Gate1 = N/A\n不阻断提测"]
    G1_CHECK --> G1_RESULT{"Gate1 是否通过?"}
    G1_RESULT -->|"否"| REJECTED
    G1_RESULT -->|"是"| G2_CHECK
    G1_NA --> G2_CHECK

    G2_CHECK["门禁二\nAI 声明 + 开发侧 CR"] --> G2_RESULT{"AI 声明、Reviewer、实质性评论、Checklist 是否合格?"}
    G2_RESULT -->|"否"| REJECTED
    G2_RESULT -->|"合格且无超时"| G3_CHECK
    G2_RESULT -->|"合格但 CR 超 24h"| G2_WARN["Gate2 = WARN"]
    G2_WARN --> G3_CHECK

    G3_CHECK["门禁三\n测试准入声明"] --> G3_RESULT{"CI 证明或 N/A、CR 链接、自检声明是否齐全?"}
    G3_RESULT -->|"否"| REJECTED
    G3_RESULT -->|"是"| FINAL{"最终判定"}

    FINAL -->|"Gate2 = WARN"| CONDITIONAL["CONDITIONAL\n有条件通过"]
    FINAL -->|"全部有效门禁 PASS"| ADMITTED["ADMITTED\n准予提测"]
```

## 三、GitLab API 数据采集流程

```mermaid
flowchart TD
    URL["输入 GitLab MR 链接"] --> PARSE["解析 URL\n提取 host、project_path、mr_iid"]
    PARSE --> TOKEN{"GITLAB_TOKEN 是否配置?"}
    TOKEN -->|"否"| TOKEN_ERR["报错\n请设置 GITLAB_TOKEN"]
    TOKEN -->|"是"| API_COLLECT["调用 GitLab API"]

    API_COLLECT --> MR_API["MR 元信息与描述"]
    API_COLLECT --> PIPELINE_API["Pipeline 与 Jobs"]
    API_COLLECT --> NOTES_API["评论 Notes"]
    API_COLLECT --> APPROVAL_API["审批 Approvals"]

    MR_API --> PARSE_AI["解析 AI 声明\n占比、工具、模块"]
    MR_API --> PARSE_SELF["解析自检声明与 Checklist"]
    PIPELINE_API --> PARSE_CI["匹配 UT、Coverage、Static Scan、Smoke"]
    NOTES_API --> PARSE_REVIEW["过滤系统评论\n识别实质性评论"]
    APPROVAL_API --> PARSE_APPROVAL["提取审批人和批准时间"]

    PARSE_AI --> REGISTRY["组装标准 JSON"]
    PARSE_SELF --> REGISTRY
    PARSE_CI --> REGISTRY
    PARSE_REVIEW --> REGISTRY
    PARSE_APPROVAL --> REGISTRY

    REGISTRY --> WRITE["写入 data/pr-registry.json"]
    WRITE --> REPORT["生成 reports/admissions 准入报告"]
```

## 四、开发提测材料最小模板

```mermaid
flowchart LR
    TEMPLATE["MR 中必须提供的材料"] --> AI["AI 辅助声明"]
    TEMPLATE --> SELF["开发自检声明"]
    TEMPLATE --> CR["开发 CR 信息"]
    TEMPLATE --> CI["CI 证明或 N/A"]

    AI --> AI_ITEMS["是否使用 AI\nAI 占比\n使用工具\n主要模块"]
    SELF --> SELF_ITEMS["CI 已通过\n开发 CR 已完成\n边界异常已验证\n本地自测已完成\n无已知阻断缺陷"]
    CR --> CR_ITEMS["Reviewer\nCR 批准链接\n实质性评论链接\n12 项 Checklist"]
    CI --> CI_ITEMS["流水线链接\n或项目无 CI 的 N/A 说明"]
```

## 五、违规升级机制

```mermaid
flowchart LR
    V1["第 1 次违规"] --> WARN["警告\n邮件通知开发及直属 Leader"]
    WARN --> V2["第 2 次违规"]
    V2 --> KPI["记录为无效提测\n纳入绩效评估"]
    KPI --> V3["第 3 次违规"]
    V3 --> SUSPEND["暂停提测权限\n重新通过质量培训后恢复"]
```

## 六、日报与周报流程

```mermaid
flowchart TD
    REGISTRY["data/pr-registry.json"] --> DIGEST["生成每日汇总\n/cr-vigil-monitor --digest"]
    REGISTRY --> TREND["生成周趋势报告\n/cr-vigil-monitor --trend"]

    DIGEST --> DIGEST_REPORT["reports/digests/"]
    TREND --> TREND_REPORT["reports/trends/"]

    DIGEST_REPORT --> QA_MEETING["测试晨会\n查看准入、阻塞、行动项"]
    TREND_REPORT --> REVIEW_MEETING["团队复盘\n查看趋势、复现违规、流程改进"]
```

*流程图使用 Mermaid 语法，在支持 Mermaid 的 Markdown 渲染器中可直接显示为图形。*
