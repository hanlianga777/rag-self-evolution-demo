# 022g：重跑 Baseline 确认框

已给 Baseline 重跑、首次运行和恢复加上现有 `ConfirmDialog`，并补齐全站其他缺少确认的模型入口。前端全量 584 条通过，构建通过，浏览器只打开确认框并取消，没有执行正式评测、发布、回滚或真实问答。No SPEC Change。

## 执行边界与理解

- 先读根目录 `AGENTS.md`、`指挥/README.md` 和指定的 022g 任务单。开工工作树干净，HEAD 为 `255249c`；022f 已完成，没有找到 022g 半成品、旧报告或需要续跑的付费题。
- 我是这样理解的：任务要求检查“全站其余会调用模型的按钮”，因此同时检查了 Embedding、Golden 修订校验、运行浮窗恢复和旧实时双方案对比入口；不只检查 Baseline。实时问答“发送”不加确认。
- 我是这样理解的：确认框之前不进入点击触发的预检；页面原有初始化 GET、状态轮询保持原样。取消不触发任何额外请求。
- 我是这样理解的：自动值班只修改文件、写报告和普通 `mv` 归档。没有执行 Git 写命令，没有修改 `指挥/当前任务.md`，没有同步 SPEC。保存和推送交给值班脚本，结果未知。
- 开工已有前端 5174、后端 8010 保持运行，没有重启服务。测试浏览器、构建和测试进程用完退出；不关闭原有 demo。

来源：任务单、仓库规则、只读 `git status / git log / git diff`、本机 `output/task022g/`。

## Baseline 的最终行为

“重新运行 Baseline（新版本）”仍在“更多指标”折叠区。点击只打开确认框，正文完整列明：

1. 会用当前 Pipeline 配置对 50 题重新评测，产生新版本正式评测。
2. 会调用模型并产生费用。
3. 不会影响当前线上版本。

取消只关闭弹窗。确认后才调用原 `prepareStart`，重新读取完整预检，沿用原来的资格阻断和请求参数：可恢复时发送明确的 `resume_source_id`，否则发送 `{fresh:true}`。首次运行、恢复入口也须确认；恢复文案说明保留已完成题，不把续跑说成全部重跑。没有修改后端、评测数据、费用计算或断点机制。

来源：`frontend/src/pages/EvaluationPage.tsx:183`、`frontend/src/task022g-confirmation.test.tsx`、`frontend/src/baseline-entry.test.tsx`。

## 全站模型入口检查

| 入口 | 本轮处理 | 来源 |
|---|---|---|
| Baseline 重跑、首次运行、恢复 | 新增统一确认，确认后才预检 | `pages/EvaluationPage.tsx` |
| 运行单题 Probe、运行单题 QC | 新增确认，取消不调用原回调；覆盖共享详情页 | `pages/FrozenQuestionDetails.tsx` |
| Golden 补齐失败题 | 新增确认，说明生成和后续 Probe/QC 会收费 | `pages/GovernancePage.tsx` |
| 生成修订草案、重新生成、确认重新选材并生成 | 新增确认，保留原修订参数和哈希 | `pages/CandidateWorkspace.tsx` |
| 保存并校验草案 | 新增确认；相似度检查可能调用 Embedding | `pages/CandidateWorkspace.tsx`、`backend/app/ai_service.py:434` |
| 修订继续校验 / 重试失败步骤、手动继续校验 | 新增确认，沿用原恢复接口 | `pages/CandidateWorkspace.tsx` |
| 线上反馈“启动此上下文 Agent · Round 1” | 新增确认，仍启动原关联上下文 | `pages/VerificationPage.tsx` |
| 浮窗“继续运行” | 新增确认；统一覆盖 Baseline、Candidate、修订、Agent 循环恢复 | `operation.tsx` |
| 暂停任务“立即运行” | 原有内联确认改为同一个 ConfirmDialog，保留时段价格确认和目标参数 | `components/RuntimeSettings.tsx` |
| 知识库重建、选文件后的上传并索引、删除文档 | 新增确认，说明 Embedding 费用及 Golden/Baseline 需重新确认的可能性 | `pages/KnowledgePage.tsx`、`backend/app/corpus_management.py`、`backend/app/knowledge_pipeline.py:327` |
| 旧双方案“运行实时对比（调用模型）” | 新增确认，说明两次问答费用；当前主页面的 Before/After 仍读保存回答 | `pages/ExperimentPage.tsx`、`pages/VerificationPage.tsx` |
| Golden 新建测试集 | 已有 ConfirmDialog，保留 | `pages/GovernancePage.tsx` |
| Agent 生成 A/B/C、下一轮、单个 Sandbox、本轮 A/B/C Sandbox、生成 D（智能组合建议） | 已有 ConfirmDialog，经检查保留 | `pages/EvolutionPage.tsx:149`、`:197`、`:271`、`:329` |
| 修订“确认应用” | 已有 ConfirmDialog，补明后续 Probe/QC 调用模型并收费 | `pages/CandidateWorkspace.tsx` |
| 发布、回滚 | 已有 ConfirmDialog，保留，未操作 | `pages/VersionsPage.tsx` |
| 实时问答“发送” | 按任务要求保持原样，未发送问题 | `pages/AssistantPage.tsx` |

表内前端相对路径均以 `frontend/src/` 为根。候选池的覆盖预览、智能补齐和组卷使用已保存向量/候选匹配，没有因为按钮写着“智能”就加模型确认；Pipeline 草稿保存、人工审核等也沿用原流程。来源：`backend/app/main.py:471` 至各 `from-pool` 接口、`backend/app/ai_service.py:949`（读取持久化 FAISS 向量）。

## 测试与浏览器验收

- 新增 **18 条**回归测试：Baseline 三种入口、Probe/QC、补齐失败题、修订生成/编辑/重生成/换材/恢复、监控 Agent、暂停任务立即运行、浮窗续跑、知识库三种操作、双方案对比。检查打开确认框前和取消后无请求；Baseline 确认后核对原预检顺序及 fresh/resume 参数，Probe/QC 确认后核对原题目和操作回调。
- 原实现先观察到 12 条确认缺失失败；补充检查又观察到 5 条缺失失败，剩余修订生成测试验证已补上的共同入口。修正测试响应结构和旧断言后，新增 18 条全部通过。来源：`red.txt`、`red-extra.txt`、`green-final.txt`。
- 旧有执行测试只补上新的确认点击，继续检查原接口、请求体、断点、刷新、脏状态和两侧回答独立性，没有删除原业务断言。原“无独立收费提示”的 Baseline 断言改为先确认才执行。
- 前端全量：`frontend/` 下 `npx vitest run`，**98 文件、584 条通过，0 失败、0 跳过**。来源：`output/task022g/frontend-verified.txt`。
- 构建：`frontend/` 下 `npm run build`，TypeScript 与 Vite 通过。来源：`output/task022g/build.txt`。
- 单元日志仍有既有 React act / 服务端 useLayoutEffect 警告；不把通过写成零警告。浏览器脚本错误为 0。
- 后端全量：`python3 output/task022g/run_backend.py`，**1459 条，1438 条通过、21 条跳过，0 失败、0 错误**，耗时 579.771 秒。跳过名单及原因与 022f 逐项一致。来源：`backend-full.txt`、`backend-full.json`、`backend-verified.json`。
- `git diff --check` 通过。

真实浏览器连接开工已有 demo，逐页打开概览、知识库、Golden、Pipeline、Baseline、Agent、发布和问答验证。Baseline 在 1440×900 和 390×844 都打开确认框再取消，三项提示完整可读，无横向溢出；桌面这次打开及取消期间额外 API 请求 **0**。另打开知识库重建、删除的确认框并取消。浏览器拦截所有 API 非 GET 请求，实际拦截次数 **0**，即没有尝试发写请求；没有脚本错误。其余当前未具备运行条件的入口由前端组件测试和代码检查覆盖，没有为验收改变正式数据。

验收先展开“更多指标”，等预检启用按钮后再打开弹窗。来源：`output/task022g/browser.py`、`browser-acceptance.json`。

本机截图已查看，均不进公开仓库：

- `output/task022g/baseline-confirm.png`
- `output/task022g/baseline-confirm-mobile.png`
- `output/task022g/knowledge-rebuild-confirm.png`
- `output/task022g/knowledge-delete-confirm.png`

## 模型与保存数据

DeepSeek 真实调用 **0 次**；其他真实模型调用 **0 次**。没有新建评测、重跑题目、修改历史成绩、发布、回滚或新增实际问答。前端单元验证使用模拟响应，后端 runner 设置 Mock、临时数据库/目录，并通过 Python 审计钩子禁止外网连接；没有复制正式数据库。

开工和收尾六个只读响应的 SHA-256 全部一致：

| 响应 | 前后 SHA-256 |
|---|---|
| `/api/evaluation` | `80e628ef7a89e29d15a9eaa3a7421109647bb772992d4c7c6db2055de2ec6ad1` |
| `/api/optimization` | `8bb4d2750701fc1a3a287741b19ce2afbc0742deaa75333f3c61af72c6567330` |
| `/api/versions` | `2aa2d9fa862398b39175db9748acbdb70a1eb789b1527b5d9020fe692fbedf3a` |
| `/api/monitoring` | `4f0af8246ccff06193d951501913555666037bc84fa51dec5181b740c151a490` |
| `/api/documents` | `39ae68f0bdbd76c15121c9931763afbaa4431c3f93a95bd5ddfb64750c0efd60` |
| `/api/workspace` | `5c4f66aef1a8601d19f30ecbf837cbc89c62bec7ee4b9555e218605bb1824a0e` |

这证明所核对的保存响应未变，不声称整个数据库文件字节未变。前端首页和后端 overview 均 HTTP 200。来源：`output/task022g/run_backend.py`、`state-before.json`、`state-verified.json`、`browser-acceptance.json`。

## 待回答问题

没有需要等待人工回答的问题。本任务的修改与验收已完成；以下 21 项既有检查缺少私有材料或历史源码，仍然无法验证，不把跳过写成通过：

| 测试模块 | 跳过数 | 原因 |
|---|---:|---|
| test_behavior_parser | 2 | 私有真实 Judge 回包未随源码保存 |
| test_claim_consistency | 2 | 私有真实 Judge 回包未随源码保存 |
| test_evaluation_policy | 3 | 私有保存材料未随源码保存 |
| test_intervention_contract | 1 | 私有只读审计 CSV 未分发 |
| test_judge_equivalent_output_contract | 3 | 缺少私有原始回包 judge_equivalent_type_errors_20261030.json |
| test_judge_forbidden_nonclaim_contract | 5 | 缺少私有原始回包 judge_forbidden_nonclaim_error_20261031.json |
| test_judge_omission_protocol | 5 | 1 项缺少 Judge 6.3 历史源码，4 项缺少私有原始回包 judge_omission_protocol_errors_20261101.json |

来源：`output/task022g/backend-full.json.skipped`；与 022f 逐项比较相同，记录于 `backend-verified.json`。

## 收尾

前端、后端、构建和测试浏览器均已退出；没有留下本轮新增后台进程。开工已有 demo 继续运行。报告与测试结果核对完成后，用普通 `mv` 将任务单归档至 `指挥/历史任务/022g-重跑Baseline确认框.md`。保存和推送由值班脚本负责，结果未知。
