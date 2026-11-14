# 027g2：发布历史与 Monitoring 布局

## 当前进度

页面改动沿用已有实现，本次从未完成的全量测试和页面验收接续。以下补充最终验收结果，历史阶段记录保留。

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

暂无。


## 本次接续的最终验收（2026-11-13）

- 从 `30b9777` 接续，开始前按手动模式执行 `git pull --rebase`。此前的页面实现已经在仓库里，没有重写。
- 新版流程图使 4 个测试文件的旧 DOM 选择器失效，导致起始全量前端 5 项失败。本次仅把结构断言改为新版图的可访问名称、关键文字及真实数据，保留无写入、旧响应隔离、线上配置和抽屉交互断言；没有改动总指挥的图形设计。来源：`frontend/src/knowledge-phase1.test.tsx`、`overview-architecture.test.tsx`、`task024b-customer-copy.test.tsx`、`task027c-assets.test.tsx`。
- 前端全量：113 个文件、671 项通过；构建通过。后端全量：1459 项，0 失败、0 错误、21 项既有跳过，名称和原因与 027f2 完全一致。来源：`output/task027g2/frontend-delivery.txt`、`build-final.txt`、`backend-full.json`、`backend-full.txt`。后端使用临时数据目录、Mock 和拒绝外网的 audit hook，未复制正式数据库。
- 1440×900 两页 fit-check：发布 790 / 790；Monitoring 737 / 737，比例均为 1.00，无全局横向滚动。两栏底部同高、宽度约 2:1；Q06、Q27 保存的原因与 D 视图一致；抽屉、报告、快照、取消回滚确认、题目跳转均可用。来源：`output/task027g2/browser.json`、`fit-check.json`、`browser_acceptance.py`。
- 截图仅在本机：`output/task027g2/01-release.png`、`02-monitoring.png`，均为 1440×900，已目视核对。当前正式记录为 2 条，原脚本的 1 条历史断言已按实际数量更新；无新增问答或反馈。
- 6 个正式接口验收前后 SHA-256 一致（评测、优化、版本、Monitoring、文档、工作区）。来源：`output/task028-run/data-before.json`、`data_check.py after`。浏览器只允许本机 GET / HEAD / OPTIONS，无脚本错误、控制台错误或被阻止的写请求。
- 真实 DeepSeek / Provider 调用 0 次。没有发送问题、标注、发布或回滚；沿用用户 8010 / 5174 服务，本次无自行启动的服务器，验收浏览器已关闭。
- 本次按最新 `指挥/当前任务.md` 的手动模式归档、提交并推送；此前报告中的“未运行 Git 写命令”仅是历史阶段记录，不代表当前手动流程。没有遗留未完成项。
