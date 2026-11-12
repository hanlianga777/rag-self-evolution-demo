# 027g2：发布历史与 Monitoring 布局

## 当前进度

页面修改已完成，正在等本轮全量测试最终结束。任务单尚未移动，以下为已核实的阶段事实；最终结果会在验收结束后补全。

- 发布历史的版本名和来源已拆成两行，关键配置已按“Candidate K / Top-K / Thinking”及回答策略拆成两行，来源与策略用 12px 灰字。仅取消这两列的自动截断，保留版本详情和回滚确认。来源：`frontend/src/pages/VersionsPage.tsx:106`、`frontend/src/pages/evaluation-workspaces.css:138`。
- Monitoring 四个数字块下改为 2:1 双栏，右边显示保存的 Q06、Q27 原因及线上 Bad Case；原底部说明已经合并到右卡底部。来源：`frontend/src/pages/VerificationPage.tsx:105`、`:123`、`:136`。
- 原有 demo 没有重启，后端、前端沿用原进程。没有调用真实模型、发送新问题、标注反馈、发布或回滚，没有执行 Git 写命令。全量后端测试使用临时路径和 Mock，并禁止外网连接。来源：`output/task027g2/run_backend.py`、`browser_acceptance.py` 和本轮进程检查。

## 接续检查

已读取根目录 `AGENTS.md`、`指挥/README.md`、本任务单和 `指挥/历史任务/027a-全站规范统一.md` 共用背景。开始时工作区干净，最新提交为 `8ffb27a`；027g 和 027f2 已有完成报告，未发现 027g2 半成品，因此从本单的两处改动开始，没有重跑历史付费题目。

## 我是这样理解的

1. 版本来源的时间沿用现有 `localShortTime(created_at)`，与创建时间列、页面其他保存时间保持一致；初始版本显示 `Baseline / 初始配置`，发布版本显示保存的 Candidate 名及“推荐发布 · 时间”。来源：`VersionsPage.tsx:106`。
2. “本轮仍未修好的题”沿用保存的推荐 Candidate 的 `continued_failure_question_ids`，Baseline 不匹配时显示未知。原因来自 D 保存报告的 `d_facts.remaining_failures[].evidence_positions`，兼容原 D 视图已有的 composite facts 来源。与 D 视图共用 `missedEvidenceRank`，不会根据题号硬编码原因，缺少字段显示“保存的证据位置不足，原因未知”。来源：`components/EvolutionStory.tsx:86`、`:92`，`VerificationPage.tsx:105`。
3. 线上 Bad Case 只列 `determinable && bad_case` 的保存反馈；当前 0 条时显示“暂无”。保留原三个标注按钮及问答详情，未实际操作标注。来源：`VerificationPage.tsx:107`、`:132`、`:140`。
4. 当前一条问答时，左卡内保留表格余白，双栏等高并拉伸到视口底部附近；窄屏改为上下排列。来源：`evaluation-workspaces.css:407`。

## 待回答问题

暂无。全量测试及最终数据不变核对仍在执行，本报告当前版本不代表任务已完成。
