# 20–30 分钟 Interview Demo 演示路径

截至 2026-10-03，演示使用真实已保存的正式 Legacy Golden：20 题、8 Positive / 4 Ablation / 8 Negative，已批准并冻结，匹配当前 Corpus；Baseline 9/11、7 Bad Case，C 11/11 已人工发布，D 10/11 不合格并保留 C。Legacy 是生成工艺来源，不代表题目未经批准。详细身份见 [Current Demo Truth](CURRENT_DEMO_TRUTH.md)，产品规则只见 [V1.4 SPEC](RAG_SELF_EVOLUTION_SPEC.md)。

以下按八个一级页面讲解，建议约 23 分钟，余下时间用于追问与详情穿透。3–5 分钟版本只概述 Golden → Baseline → Bad Case → Agent → Sandbox → 人工发布主线；不要把它作为完整演示时长。

| 顺序 / 页面 | 建议时间 | 主问题与展示动作 |
|---|---|---|
| 1. RAG 自进化项目概览 | 2 分钟 | 系统把持续优化变成评测、诊断、实验、回归、人工发布闭环；展示真实 Golden/Baseline/Agent/Production 状态与下一步。必要时打开已有业务/技术架构。 |
| 2. 知识库 | 2 分钟 | 为什么这样构建知识库？四张策略卡解释 PyMuPDF/OCR fallback、Section-aware Chunk、中文 BGE、FAISS；展示 4 文档/157 页/252 Chunks/实际 252 indexed，打开文档或 Evidence Drawer 追溯页章节。 |
| 3. Pipeline 配置 | 2 分钟 | Agent 能改什么？按知识处理/检索/生成/评测四类说明 Frozen 与实际 Search Space，不讲重复流程图，不把 Judge 说成每次 QA 必经步骤。 |
| 4. Golden Dataset | 3 分钟 | Golden 是稳定测量尺；当前正式 20 题和 8/4/8、人审/冻结身份。说明 AI 与业务题进入同一候选池，Probe/QC/人工 Gate 1 保证可信；被追问时再打开 Coverage/题目详情。V2 Preview 与当前 Legacy Snapshot 分开。 |
| 5. Baseline | 3 分钟 | 当前为什么不合格？报告看失败结论，Hard Gate 表看 9 Passed / 2 Failed；打开一个真实 Bad Case，按 Expected/Evidence/Answer/Judge/Primary Root Cause 穿透。当前根因是 Generation 6 / Safety 1，不借任务书示例虚构 Retrieval 失败。 |
| 6. Agent 工作台 | 5 分钟 | 诊断 → Agent 输入/能力边界/实验意图 → A/B/C 的 WHY/CHANGE/RESULT → Sandbox 四核心指标。展示 B Regression FAIL、C 11/11 Qualified；D 是组合验证，10/11 不合格，保留 C。Search Space 和高级指标按需 Drawer，不在讲解中重新生成或跑 Sandbox。 |
| 7. 发布 | 2 分钟 | 为什么发布当前 C？看 Hard Gate、Regression、Gate 2 与 Gate 3 人工决策、真实参数变化 `Grounded → Abstention` 和当前 Production 来源；完整配置、其他 Candidate 与版本/Rollback 降为详情。只浏览，不重复发布或回滚。 |
| 8. 问答验证 | 4 分钟 | Tab 顺序：问答验证 → 方案对比 → Monitoring。对比为高潮：选真实 Baseline Bad Case，问题自动填入且可编辑；左正式 Baseline、右实际已发布 Production，说明答案/Evidence/Latency/Input/Output Tokens。最后用 30–60 秒说明新 Production QA → 人工 Bad Case → Confirm Trigger → 下一轮 Agent。 |

所有页面的普通详情从右侧 Drawer 打开：标准 560px、wide 800px，移动端全宽；Select 选中即收起。同组 A/B/C、双答案卡等高，长内容内部滚动。主页面先讲结论，审计 ID/Trace/完整配置在详情穿透。

## 历史结果与现场实时操作

页面上的 Golden、Baseline、A/B/C/D 和人工 Release 是已保存真实历史记录；本轮验收只读这些对象，没有重新执行真实 Provider 生命周期。不得把 Stub、截图、历史回答或已保存评测成绩称为刚刚运行的实时结果。

现场需真实同题 Before/After 时，由用户主动点击“运行实时对比”，这会分别调用 Baseline 与当前 Production 并消耗 Provider 配额；选 Bad Case、编辑问题、打开详情本身不会调用。前置是有效正式 Baseline、实际 active 且人工已发布 Production、可用 Provider。缺任一项会阻断，不回退到候选或 `baseline-v1`。结果属于该次同题请求的冻结配置，不从历史评测补答案，也不额外调用 Judge 自动评分。

只展示本次真实采集的 Latency/Input Tokens/Output Tokens；0 是合法采集值。费用需完整 Usage 与当次冻结模型/价格/币种，当前价格配置为 USD；不换汇、不回算历史缺失费用。单侧失败要说明失败并保留另一侧实际结果。

## 主动真实验证清单（本轮验收不自动执行）

1. 一次 Baseline vs 当前已发布 Production 实时同题问答，观察 Answer/Evidence/Usage/Latency 和费用依据或缺失原因。
2. 一次 Production QA → 人工标 Bad Case → Confirm Trigger → 手动启动首轮 Agent；可能创建新实验并耗用预算，仍不自动 Sandbox 或发布。
3. 一次当前 Corpus V2 Planner Preview，查看动态 K/merge/Slot；无需生成模型，不接着自动生成、审批或冻结新 Golden。

要声称当前 Golden 来自 V2，需用户另行授权新生成、人审与冻结，并在同一新 Snapshot 上重新评测；当前面试应表述为“V2 引擎已实施，当前正式演示快照保留其 Legacy 来源”。本轮 UI/Stub/只读保护验收详见 [Interview Demo 验收](INTERVIEW_DEMO_VERIFICATION.md)。
