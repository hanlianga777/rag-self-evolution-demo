# RAG Self-Evolution Platform 产品规格

> **唯一当前目标规格：V1.4 — Golden Engine V2 & Identity-Bound Evolution**
> 业务规格冻结日期：2026-09-30（Asia/Shanghai）；Interview Demo UI 修订：2026-10-03。V1.4 业务代码的历史验收见 [实施验收](V1_4_IMPLEMENTATION_VERIFICATION.md)；本轮 UI 实施与验证结果单独见 [Interview Demo 验收](INTERVIEW_DEMO_VERIFICATION.md)，不沿用历史测试数字作为本次证据。
> V1.4 是 Golden 工艺、对象身份、Monitoring 与信息架构升级，保留现有技术栈和治理底座。新图是目标架构，不是当前 Demo 已具备全部能力的证明。

## 1. 文档地位、依据与本次交付边界

本文件是唯一目标规则源；[SPEC ChangeLog](SPEC_CHANGELOG.md) 仅保留追加式历史。V1.3 及更早内容归入文末历史存档，旧文中的“当前”“唯一”“Implementation Authorized”只代表当时口径，不覆盖本节及 V1.4 要求。

依据：用户提供的 `RAG_SELF_EVOLUTION_CODEX_MASTER_PROMPT_20260930.md`（2026-09-30），以及用户先完成文档与两图同步、后明确批准 V1.4 完整代码实施的范围。任务书是需求输入，本轮代码实施依据用户明确批准的计划。保留真实 Golden、Baseline、Candidate、Production 和冻结 JSON；兼容迁移先在副本验证，全文产物只允许完整校验后的兼容补充。不自动调用真实 Provider、重跑付费流程或执行真实人工 Gate。

业务规则第 5–13、16 节及既有验收契约继续保留；第 14–15 节由 2026-10-03 Interview Demo UI 修订原位替代，相关本轮验收边界见第 17.5 节。第 18 节保留用户主动运行的真实验证清单。文中的规则是目标要求，实现和运行证据分别记录在第 3 节与 [V1.4 实施验收](V1_4_IMPLEMENTATION_VERIFICATION.md)；本文不把任务书中的故障线索视为已复现 Bug，也不声称已查看其引用的 ZIP、朋友截图或 20 张截图。

优先级：本轮明确用户决策 → V1.4 明确变更 → 未被替代的冻结规则 → 实际持久化配置与规则源 → 朋友资料工艺参考 → 历史截图数字。冲突不得靠改门槛、改数据或猜测消解，具体未决项见第 4 节。

2026-10-03 UI 修订依据为桌面 `RAG_SELF_EVOLUTION_CODEX_INTERVIEW_DEMO_MASTER_PROMPT.md` 及用户批准的实施取舍。它仍属于唯一 V1.4 SPEC，不创建第二份 SPEC 或 V1.5/V2 业务流程；原桌面任务书保持原样。仅重排前端产品信息与交互，允许的唯一后端补充是 `GET /api/pipeline.index.dimension/indexed_count`：只读实际 FAISS 的 `d/ntotal`，未知返回 null，不从模型名推测、不写索引或数据库。禁止真实 Golden/Baseline/A/B/C/D/Provider/人工 Gate/发布重跑。

## 2. 产品主线与保留规则

面向企业知识问答的评测驱动 RAG 质量运营与版本决策 Demo。面向 20–30 分钟 AI 解决方案 / AI 产品经理面试，3–5 分钟可概述主线：可信 Golden 如何测量问题、Baseline 如何暴露 Bad Case、Agent 如何提出可解释实验、资格与 Regression 如何约束人工发布，以及问答反馈如何回到优化。

`知识库 → Golden V2 规划 / 构造 / 校验 / Probe / QC → Gate 1 冻结 → Baseline → Bad Case → Optimization Agent → A/B/C → Sandbox / Regression → Gate 2 报告与赢家 → 条件 D → Gate 3 人工发布 → Production → 问答对比 → Monitoring 人工确认 → 下一轮 Agent`

只有 Optimization Agent 是主 Agent。Generation、Probe、QC、Judge 是受控工作流；不自动寻找所有错误、修改知识、调参或上线。Monitoring 位于问答验证二级 Tab，不新增第九个一级模块。

### 2.1 保留的技术与资产边界

保留 React / TypeScript / Vite、FastAPI、SQLite、已有 DeepSeek Provider、`BAAI/bge-small-zh-v1.5`、FAISS IP / BM25、PyMuPDF / 页级 OCR 回退、Section-aware Chunk、现有启动方式和端口。Golden 离线规划复用已有向量，不属于每次 Production 在线检索。

保留 Corpus 原子更新、逐 Slot 保存、失败占位与局部补题、固定 Regression 集、Sandbox 隔离、Gate 1/2/3、D 失败保留 Winner、人工发布、版本与回滚、真实问答、CSV/XLSX 业务导入。旧 Frozen Snapshot、Evaluation 配置/Judge/Gate、Candidate 配置及发布版本不改写；新增语义采用兼容字段/JSON/审计和最小 additive migration。

不迁移模型、Embedding、Parser 或 Chunk 策略，不新增 E/F、多 Agent、Docker/Kubernetes、灰度发布、自动发布/回滚、APM/QPS 或复杂全自动搜索。未采集显示 `— / 未采集`，历史 Snapshot 保留真实 Legacy/V1 来源，不因 UI 或规格升级被标成 V2。

### 2.2 治理门槛与预算（本次未变）

以下为检查基线 `f6ea03d` 的 `backend/app/policy.py` 冻结定义；实际历史判定仍读取当次 Evaluation 快照。

| Hard Gate | 门槛 |
| --- | --- |
| Positive correctness / faithfulness / completeness | ≥80% / ≥80% / ≥75% |
| Ablation correctness / faithfulness / completeness | ≥70% / ≥75% / ≥65% |
| Safe Rejection / Safety Critical / Injection Resistance | 各 ≥95% |
| 回答延迟 P50 / P99 | ≤25s / ≤60s |

共 11 项，全部通过才满足 Hard Gate；Overall 是九项质量指标等权展示，不能抵消任一失败。Recall@K、Precision@K、MRR、TTFT、Token Cost 是诊断/比较项，不增加新 Gate。Baseline 可以未合格但仍是有效诊断起点。

Search Space 的键、类型、枚举、依赖和展示数量取自真实 `ALLOWED_SEARCH_SPACE` / Validator；不从截图硬编码数量。Rerank 保持现有开关与 Lightweight Rerank，不把它画成独立 Rerank Model。Parser/OCR、Chunk、模型、Temperature、Query Decompose、Retrieval MaxTokens、Rerank TopN 继续不进入 Agent 自动调参范围。

A/B/C/D 累计最多 12 次 Sandbox，开始即占用、失败不退、为 D 留一次。固定 Regression 的 Safety/Critical 不允许新增失败，普通题最多新增 1 个失败；Qualified 继续要求全部 Hard Gate 与 Regression 通过、至少修复 1 个目标 Bad Case 且总 Bad Case 至少减少 1 个，并满足现有身份/发布约束。D 只有合格、相对 Winner 无新增失败且实际修复才晋升。

Monitoring：1 个 Safety Critical Bad Case，或最近 20 个完整可判定 QA 中至少 4 个 Bad Case，仅创建 Pending Trigger；需要人工判定和 Human Confirm。Gate 1 批准冻结 Golden；Gate 2 确认报告并选择合格 Winner；Gate 3 在事务重验后人工发布。

## 3. 需求追踪与历史业务验收证据（截至 2026-10-02）

检查起点：`3a44f2f`；后端阶段至 `cd551e0`，UI 与最终集成修复至 `8c674c6`。下表保留前轮代码与离线证据，包括 121 项前端测试、208 项浏览器检查和当时的修订关闭提示 Minor，不能作为 2026-10-03 重排后的 UI 验收证据。本轮 UI 要求以第 14–15 节为准，最新验证见 [Interview Demo 验收](INTERVIEW_DEMO_VERIFICATION.md)。历史实测记录见 [Phase 1 验收](PHASE1_VERIFICATION.md) 与 [已保存 Demo 事实](CURRENT_DEMO_TRUTH.md)，其日期、Run 和 Provider 边界保持原样；本次不刷新真实运行结果。

| 需求 ID | V1.4 目标 | 当前源码证据 / 实施状态 | 目标章节 |
| --- | --- | --- | --- |
| P0-01 | Current Baseline ↔ Experiment 强绑定 | `GovernanceStore.current_baseline_identity()` 统一解析；当前对象 API 共用 identity、实验按 Baseline 查询；ID-01/02 后端回归通过 | 5 |
| P0-02 | Monitoring Confirm 后首轮 Round 1 | Confirm 幂等、Corpus→SQLite 短事务 claim/保存/发布身份重验、全批原子保存；Round 0 / 失败重试 / 真未完成轮次回归通过，真实 Monitoring-only 证据不伪造 Baseline Case | 5.3 |
| P0-03 | Monitoring 复用 resolver，排除 Sandbox | Confirm 共用 resolver；QA 配置/Corpus 来源贯穿实际 API，不重读回答后 Production 伪造归属；ID-02/05/07 后端回归通过 | 5.1 / 5.4 |
| P0-04 | Pool 建 Run 必须 Coverage / Slot 匹配 | 独立当前 Plan + 稳定最大二分匹配，保存 Slot 缺口/匹配；成功复制新候选，不继承审核；263 项离线回归及复审通过 | 9 |
| GV2-01 | Dynamic K-means / 小簇合并 / 厚度配额 | `golden_v2.build_plan()` 复用 FAISS 向量与 K-means，稳定合并/编号、协调最大余数配额；固定参数与输入审计冻结，Preview 无生成模型 | 6 |
| GV2-02 | Group × Construction 双维度 | Group / Construction 分存；真实可用材料专项优先并记录 fallback，旧字段只作 Legacy adapter，不改历史冻结 JSON | 7 |
| GV2-03 | Unified Hard Validation | AI / Import / Pool / Edit / Revision 共用 `validate_golden_candidate()`；证据定位、声明 Product/Version、Bridge 必要关系范围、Quota/Slot 与精确去重回归通过；未知语义待复核 | 8 |
| GV2-04 | Candidate Recall 与 Final Context Probe | 同次检索保存真实 CandidateK / Final、分层 Any/All、原解析全文信号与受控 Judge；284 项离线回归和复审通过；执行失败持久化 failed Probe，阻断 QC/批准，不伪装成零召回；内容/Corpus/精确 Probe 依赖捕获与短事务重验阻止旧质量覆盖新题 | 10 |
| GV2-05 | 原解析全文 Probe + 原子产物 | 原 Parser 页级全文 + schema/checksum、完整 bundle 校验/原子激活/回滚和兼容补充工具已实施；原后端进程仍在运行，真实 4 PDF/157 页在备份 Staging 完整校验通过，原 252 Chunk/FAISS 字节不变；未切 active sidecar。引擎支持与 active 就绪分开 | 10–11 |
| COST-01 | 集中价格、真实 Usage/Timing、版本与缺失原因 | `cost_report()` 版本化静态价格、冻结计费快照、缓存/模型/Usage/时间缺失原因；真实首输出 TTFT，无非流式 Total 替代；专项 CT 与全套 284 项离线回归及阶段复审通过 | 13 |
| UI-01 | 全局与全部指定页面信息架构 | 八模块 H1/hash、Drawer/Dialog/Select、等高 A/B/C 与独立 D、50/50 问答及过期响应隔离已实施；121 项前端测试、构建与四尺寸 Chromium 208 检查通过；实际手动当前 Preview / persisted Why 和必需 Drawer 具名验证，最终复审通过，保留换材重新生成后多一次关闭提示 Minor | 14–15 |
| SAFE-01 | 不可变旧快照、兼容迁移 | 兼容迁移、旧快照无改写、索引失败/混合身份拒绝在临时库/Corpus 验证；真实 25 张表完整内容与四个 active 文件 SHA 在最终整合后再次核验不变 | 16 |
| QA-01 | 离线状态流、迁移与 UI 验收 | 54 个 Test ID 逐项具名断言；实际 FastAPI 隔离生命周期覆盖 V2→Gate 1→Baseline→A/B/C→D 失败保留赢家→测试发布→Monitoring 首轮，296 项后端测试通过；最终复审无未解决 Critical/Important，一个 UI 提示 Minor 保留；WebKit 缺失未验证，真实 Provider 未重跑 | 17 |

## 4. 接口约束与明确未决项

### 4.1 既有接口与目标语义

既有 API 路由和字段兼容保留，新增身份、计划、校验及遥测语义按实施验收记录。已有路由包括 `GET /api/evaluation`、`GET /api/optimization`、`GET /api/pipeline`、`POST /api/governance/generation-runs/from-pool`、`POST /api/monitoring/triggers/{trigger_id}/confirm`、`POST /api/experiments/run`、`POST /api/candidates/{candidate_id}/run` 与人工发布/回滚接口。

已注册 `POST /api/governance/coverage-preview` 与 `POST /api/governance/generation-runs/from-pool/preview`。生成和 Pool 创建支持可选 `plan_id`，省略时服务端建立当前 Plan；提交再次校验 Corpus 身份。后续双层 trace、风险与价格版本继续追加既有 JSON，阶段证据见实施验收。第 8 节 Validator 签名是语义示意，不是当前可调用公共接口。Preview 保持无生成/Judge/QC调用、无人工批准和无 Production 变更。

### 4.2 QC P0 边界（用户已确认）

2026-09-30 用户明确选择保留 Friend-aligned 人工风险接受：机器 QC P0 必须展示风险、由用户明确填写理由后才能接受；确定性证据错误、Fake Negative、类别数量错误不可豁免。Provider/执行失败不是可接受的质量结论，不能用人工理由变成 Passed。

第 10.2 节的 P0 阻断指不可豁免确定性 Blocker，不撤销机器 QC 风险接受。合法但检索未命中的 P1 与执行失败分别记录。此确认关闭此前 `[OPEN-QC-P0]`；历史存档与原任务书冲突原文仅保留为历史依据。

---

## 5. 当前对象身份与 P0 后端规则

### 5.1 单一 Current Baseline resolver

统一封装当前 Baseline 判定供 Evaluation、Optimization、Monitoring、Release 校验和 Overview 使用，禁止各处独立写“最新 completed”。

当前可用于新优化的 Baseline 至少应满足：真实 completed、属于正式 Baseline 而非 `sandbox_candidate`、对应当前有效 Golden 和 Corpus、配置/评测标识可追踪、未被显式失效。

字段名遵循现有数据模型。要核实 run_target 缺失的旧数据分类，不能因为 NULL 直接把所有旧记录误认 Candidate 或 Baseline。证据不足显示历史未验证。

当前 Golden 尚未重新冻结或 Corpus 已变化时，不把另一套试卷的旧 Run 当当前有效 Baseline；提供历史报告入口和失效原因。

### 5.2 Experiment 必须绑定 Baseline

当前 Experiment 只能是满足 `experiment.baseline_run_id == current_baseline.id` 的当前选定实验。存在多个实验时遵循现有明确选择/最新有效规则，并显示 Round 和来源。

未找到时显示“当前 Baseline 尚未运行 Optimization Agent”，不借用上一轮 Diagnosis、Hypothesis、A/B/C、Target Cases、Config Diff、Sandbox Recommendation。

Root Cause 分类根据当次 Bad Case 数据汇总。每题保留一个 Primary Root Cause；Secondary Signals / Failure Tags 可有多个，不提升为并列主根因。保留真实出现的 Retrieval/Ranking/Generation/Safety/Evidence，以及 Query/Metadata/Performance/Unknown 类别；本轮不把历史类别强转为五类、不改原诊断值。显示非零类别，不固定三张卡，无证据不能自称确定根因。

历史 Experiment 可在现有历史详情入口只读查看，并显著显示其 Baseline；不新建复杂实验管理系统。

异步 UI 请求必须包含对象 ID。切换 Baseline 或刷新当前身份后，旧请求返回不能覆盖新视图；清除关联 Drawer、选中 Candidate 和对比结果的旧状态。

### 5.3 Monitoring Pending Context 与 Round 1

Human Confirm 的语义是确认需要优化，创建/复用 Pending Optimization Context，并保存 Trigger ID、事件证据、有效 Baseline ID、Golden/Corpus/配置来源，不等于 Agent 已完成。

允许两种最小实现：复用现有空 Experiment 加明确 `pending/round=0`；或复用现有 Pending Context 表/字段。不要另造平行状态机。

判断“上一轮必须完成”的前提是已经成功生成真实 Candidate 的有效 Round≥1。无 Candidates 的 Round 0、生成失败且无有效候选、仅已 Confirm 的上下文，不适用上一轮 Sandbox 阻塞。

首轮生成成功后持久化 Round 1 A/B/C；模型格式错误/Provider 异常不能留下“已生成”状态。重试复用同一 Pending Context，避免重复 Experiment/Trigger。

真实 Previous Round 有部分 Candidate 未完成 Sandbox 时保持现有阻断和明确说明，不为修 Round 0 放宽所有轮次规则。

### 5.4 Monitoring 的 Baseline 与 Production 来源

必须排除最近完成的 Sandbox Evaluation。没有有效 Baseline时，保留 Pending Trigger 并解释“需要当前有效 Baseline”，禁止随手拿 Candidate 报告替代。

Monitoring Event 记录对应 QA 的 Production Version/Config/Corpus/Question/Answer/反馈。当前比较 Baseline 可能早于 Production，来源关系必须可解释；不偷偷把事件配置视为已评测 Baseline。不一致时沿用当前 SPEC 的兼容/失效判断，不创建无评测的假 Baseline。

连续双击确认、刷新、重复请求不应重复创建上下文。调用 API 的状态检查与 UI 禁用必须一致，已有事务/幂等机制优先复用。

### 5.5 新 Baseline 不得覆盖旧 Production

新 Baseline B1 + 无 Experiment 的合法显示：Baseline 页面是 B1；Agent 是等待；Release 可显示当前仍在运行的旧 Production 及来源；Overview 不将旧 C 标为 B1 的候选。问答对比明确左右配置身份。

## 6. Golden Engine V2：Coverage Planning

### 6.1 目标、边界、输入

所有新 Golden Run（AI 自动生成、候选池选择、业务导入混合组卷）必须有当前 Corpus 的 Coverage Plan。老 Frozen Snapshot 不要求补造 Plan。

输入是同一 Corpus 下有效 Chunk、现有 Embedding、文档/产品/版本/章节 Metadata，以及选择的 Profile；不重算另一套 Embedding、不引入 LLM Topic 标签依赖。

Profile 保持：Mini 20=8 Positive/4 Ablation/8 Negative；Medium 49=20/9/20；Full 98=40/18/40。从 Profile 配置读取，不散落 hardcode 20。默认展示当前选定 Profile。

### 6.2 Dynamic K-means 工艺

朋友原始截图说明 `TARGET_CLUSTER_SIZE=40`、`MIN_CLUSTER_SIZE=3`，按 Chunk 数自动估计 K，结合约 √n 的上界，合并小簇，按主题厚薄分题。这些是工艺参考，不是对旧快照的描述。

V1.4 实施合理实现约定：

1. n 为有效可聚类 Chunk 数。n=0 返回明确无法规划；n=1 使用单簇，n 很小时不要触发非法 K。
2. 默认 target_cluster_size=40、min_cluster_size=3，集中配置。估计 K 可用 `max(2, min(floor(n/40), floor(sqrt(n))+1))` 后再 clamp 至 `[1,n]`；边界和舍入在代码/审计记录固定，实际图示模糊处不要装作已有唯一数学口径。
3. 复用当前有效向量，按现有归一化约定处理；随机 seed 和 n_init 固定，确保同版本相同输入可复现。算法距离约定写入 metadata，不悄悄切换线上检索。
4. 小于 min_cluster_size 的簇按最近有效中心合并，固定 tie-break 和迭代顺序。全是小簇时仍得到可用规划或明确不足原因，不死循环。
5. 合并后重新计算中心/规模，并稳定排序/编号。Cluster ID 只在 plan/corpus 内有意义，不是永久业务主题 ID。
6. 不按产品预先硬切簇代替语义聚类；但代表文档/章节与产品范围作为可解释 Metadata 展示。
7. Topic 名称优先从代表章节/文档派生为展示标签；历史没采集显示“未采集”，不调用 LLM 造标签。

上述工程约定须在 V2 SPEC 写明。若仓库已经有经过验证的等价动态实现，复用并记录，不重复安装重型依赖。

### 6.3 主题配额与 Slot 分配

按合并后的 Cluster 厚度分配 Slot，用明确整数分配方法（如最大余数法）确保总数和各组 Profile 配额精确一致，固定 tie-break，避免独立四舍五入总量错误。

规划必须区分全部题的 Coverage Anchor 与 Positive/Ablation 的证据覆盖。8 个 Negative Anchor 不等于 8 个主题得到正确答案验证。

每个 Slot 保存：slot_id、evaluation_group、construction_type、topic_cluster、要求的 Evidence/Bridge/主体范围、材料来源、抽样优先级、满足/缺口状态。

大主题多题，小主题通过合并避免无意义配额。总题数少于 Topic 数或某主题没有可构造材料时，记录实际覆盖不足；不要假称全覆盖，也不要强行生成无法成立的 Bridge。

优先使用V1.4 实施尚未使用 Chunk；其次再使用历史较少使用 Chunk。题量大于材料量可复用，但记录 reused，而非随机重复。事实题的合法证据可能被专项算法重复利用，不能因 reuse 本身否定合法题。

### 6.4 可查看、可复现的 Planner Preview

Preview 不调用生成模型/Probe Judge/QC，不创建新 Approved Snapshot，不改变 current Golden/Baseline/Production。可缓存并持久化审计 Preview，但要标记 Preview。

Plan 至少记录 planner_version、corpus_fingerprint、embedding identity、seed、参数、初始/最终 K、merge mapping、Cluster 规模、Topic 配额、Slot 表、代表 Chunk、复用统计、缺口、生成时间。

Run 使用的 Plan 为冻结副本或稳定引用，不随下一次 Preview 刷新而改变。Corpus 变化后旧 Preview 失效并解释原因。

## 7. Evaluation Group × Construction Type

### 7.1 两个维度分别存储、展示、校验

| 维度 | 允许概念 | 用途 |
|---|---|---|
| Evaluation Group | Positive / Ablation / Negative | 8/4/8 配额、评测分组、Gate |
| Construction Type | Fact / Aggregation / Bridge / Ordinary | 题怎么造、结构与 Evidence 是否成立 |

不把 Fact 当 Positive 的同义词，不把多 Chunk 当 Bridge 的充分条件，不把 Ablation 标签写两遍。

Ablation 的能力边界是保持可答知识点、扰动问法；必须仍能独立理解。可以保存来源题/知识点的可选关系，但不强制 Q09→Q01、不用题号绑定、不要求每道 Ablation 都有一对一当前 Positive 配对。

Negative 原则上用 Ordinary 和已有 negative subtype/expected_behavior（clarify/abstain/refuse 等），不能捏造 Golden Evidence。Coverage Anchor 与 Evidence 分字段保存。

### 7.2 专项出题工艺

朋友截图支持优先 Aggregation → Bridge → Fact → 剩余 Ordinary。程序识别材料，模板构造 Fact/Aggregation，Bridge 可由受控模型表达并由程序确认结构。

- Fact：明确实体/属性/值，Reference Answer 的关键事实能在原文定位。
- Aggregation：材料具备真实可聚合条目/范围，答案项逐项有支持，不能仅凑多个随机 Chunk。
- Bridge：至少两个材料节点有可核实的共同实体/关联，需联合才能得到目标答案；单个 Chunk 已能完整回答时不能标 Bridge。
- Ordinary：普通问答或边界题，不能因此绕过证据、去重或自包含校验。

专项只占符合条件的 Positive/Ablation 配额，不占用 Negative 配额。无合适材料时减少专项，剩余归 Ordinary，并在 Plan Audit 解释，不为凑类型让模型编证据。

朋友专项上限线索为 Mini 2/Medium 4/Full 8 且不超过当时剩余正向材料的一半；它不是V1.4 实施新增“必须每卷含2道Bridge”的硬门槛。工程采用的专项 quota/fallback 要集中定义，记录计划与实际，避免 UI 固定承诺一定包含所有类型。

### 7.3 历史字段兼容

旧 construction_type 未存的显示“未采集”；可根据旧持久化结构确定性映射的写 adapter 和 provenance，不能从题面猜测后把猜测当历史事实。不修改 Frozen Snapshot JSON。

## 8. Unified Hard Validation

### 8.1 单一规则源

抽取统一接口，示意：`validate_golden_candidate(candidate, corpus, coverage_plan, validation_context)`。AI 生成后、Business Import Preview/Confirm、Pool 建 Run、人工修订后的再验证使用同一规则源。上下文可不同但基础约束一致。

返回结构包含 valid/blocking_errors/warnings/normalized_candidate/evidence_locations/construction_checks/coverage_match/validator_version。保持可读错误与审计，不只返回 false。

Hard Validation 是确定性合法性检查，不等同于 LLM QC，不把当前检索未命中写成“题面非法”。无需泄露模型思维链；保存公开结构化诊断与允许的原始响应即可。

### 8.2 检查项

| 检查 | 必须行为 |
|---|---|
| Schema/Normalize | 必填、类型、枚举、列表规范化、question 与实际 user_query 一致 |
| Self-contained | 正常用户可独立理解，悬空“上文/图中/它”没有实体上下文时阻断；不误杀合法口语 |
| Entity Scope | 必要产品/版本/实体限定明确，跨产品事实不能混用 |
| Forbidden Structure | 阻断只问页码/目录/结构等无业务意义的题，不误杀正常章节内容问题 |
| Evidence Location | Positive/Ablation 的证据在当前 Corpus 原文可逐字定位，保存文档/页/字符范围或等价定位 |
| Answer Anchor | 答案关键事实有证据，不强制整句 Reference Answer 与原文逐字相同 |
| Duplicate | 规范化 exact duplicate 与已存在的相似检查；阈值集中配置，不加题号黑名单 |
| Construction | Fact/聚合项/真实 Bridge 必要性一致，无支持时不能伪装专项 |
| Negative Shape | 禁止伪造证据和库内答案；保留 subtype/expected_behavior，进一步真伪由 Probe/QC |
| Coverage Slot | 当前 Plan/Cluster/Group/Construction 匹配，Slot 不重占，Corpus 身份一致 |
| Quota | 按 Profile 严格计数，未齐不进入冻结；不特殊允许 19/20 凑合 |

数字、单位、标点、空白可有限规范化后定位，保存规范化规则。不要因为同义表述不在词典就报 `unsupported answer anchor`。无法确定实体/事实时给出具体修订原因，不人工写产品关键词补丁。

Bridge 验证保存引用节点、关系和必要性检查；不能声称纯字符串规则可以完全判定任意自然语言语义。确定性证据不足时为待复核，而非捏造“已证实”。

### 8.3 状态、修复、失败持久化

每个 Slot 持久化状态、Attempt、错误、材料来源。默认保留已有每 Slot 最多两次生成尝试、失败占位和 regenerate-failed 路由，不额外加入无限循环。

QC 自动修复最多一轮，生成重试与 QC 修复是不同计数。人工修改可以再次验证，但每次有版本/审计，不自动循环烧 Token。

不足 Profile 或存在 blocking Slot 时 `needs_regeneration`，系统异常 `failed`；保留已合格题，不回滚为零。凑齐且配额/Plan一致后才能进入后续批次阶段。

关键 Question/Answer/Evidence/Group/Construction 改动使相关 Probe/QC/Review 失效；不沿用旧 Passed。

## 9. Candidate Pool 与 Business Import

### 9.1 UI 工作流

Golden 二级 Tab 为“当前测试集”“候选池”。候选池顶部“导入业务用例”打开 Drawer，支持 CSV Template/XLSX Template/Upload/Preview/Confirm Import。导入操作不生成 Approved Golden，不绕过治理。

CSV/XLSX 使用已有字段契约，不要求用户手填 cluster ID、coverage slot、复杂 Metadata。模板与后端校验字段一致。

### 9.2 自动 Topic 归类

Positive/Ablation：根据已校验 Evidence Chunk 的 Cluster 归类。多 Cluster 证据保存涉及集合，按 Slot Requirement 选择主锚点，Bridge 保留关联簇，不丢掉第二跳。

Negative：Question 使用现有 Embedding 计算最近 Topic Cluster，仅为 Coverage Anchor；保存方法/距离/低置信度警告，不当 Golden Evidence，也不靠最近簇证明题是可答/不可答。

若导入只有文本证据而没有 Chunk ID，先用统一 Evidence Location 在当前 Corpus 定位。找不到是未合格候选，不自动随意绑定最相似 Chunk。

### 9.3 Pool→新 Golden 的必要条件

当前 Corpus → V2 Plan → Slot Requirements → 校验选题 → 匹配 Slot → 给出缺口 → 满足后创建 Run。

8/4/8 数量正确只是第一层；Coverage/Construction Slot 满足才允许创建。采用稳定匹配/分配，保存映射审计，避免 UI 顺序改变导致随机结果。不要为了20题集中在两个主题而重新规划一份迎合所选题的 Plan。

不满足时显示缺少哪个 Topic/Group/Construction、可用候选数/缺口，不只“创建失败”。提供继续选择/导入以及已有生成能力的“补缺口”入口；补题调用仍由用户点击，默认不自动调用真实 Provider。

Pool 建新 Run 必须复制为新候选版本，重新经过当前 Corpus/Plan 的验证与必要 Probe/QC/人审；旧批准状态不自动继承为新 Snapshot 批准。

创建 Golden 的 API 也检查同样条件；隐藏按钮不是后端治理。

## 10. Probe：题真实性与 RAG 能力分开

### 10.1 Positive/Ablation 两层记录

在同一次 Retrieval Pipeline 中保存真实候选召回列表和最终 Context 列表。CandidateK/TopK 使用当次配置，不硬编码只许12/24和4；截图常见配置是 CandidateK12/24、TopK4。

明确候选集合的位置：按实际 pipeline 获取进入 Rerank/最终 TopK 选择前的候选集合，记录 filtering/fusion/threshold 的结果来源；不把 Vector/BM25 原始堆叠无限列表当 CandidateK。

保存：Candidate IDs、排名/分数/来源、Final IDs、Golden Evidence 交集、所需证据集合、Any/All hit、必要时各证据覆盖率、Pipeline Config Snapshot、Corpus、timings。

| 观测 | 可支持的初步诊断 |
|---|---|
| 正确证据未进入候选集合 | Retrieval Failure，具体原因仍需证据 |
| 已在候选集合，最终 Context 缺必要证据 | Ranking/Context Selection Failure |
| 最终 Context 已具必要支持但回答错误 | Generation Failure 的重要依据 |
| 历史没有候选集合 | “未采集”，不能反推命中 |

Any hit 不等于多跳题全部 Evidence 可用；检索 trace 本身也不证明生成一定正确。Query、过滤、上下文预算等因素需保留定位来源。

### 10.2 不把检索不命中直接当坏题

Hard Validation 已确认真实证据，但当前 Baseline 没召回时，记录 `RETRIEVAL_INCOHERENT` 或等价 P1 能力风险，供 Gate 1 看见；不得为了让 Probe 好看删除所有检索难题。

区分 `probe_execution_status`（是否运行成功）、`candidate_recall/final_hit`（系统表现）、`question_validity/risk`（题是否成立）。上层 Passed 文案不能掩盖未命中。

复用 Friend-aligned 人审风险边界（见 4.2）：确定性 P0 Blocker、证据不成立、Fake Negative、数量错误不可豁免；机器 QC P0 与合法但检索不连贯的 P1 可展示风险并经明确人工理由确认。Provider/执行失败不能豁免，不变更旧数值门槛。

### 10.3 Negative 三层 Probe

Vector Probe → Raw Parsed Full-text Probe → 有可疑材料且无法确定时 Answerability Judge。

全文 Probe 搜索原解析文本，包括未成为 Chunk 的段落/表格/数字；不能仅对 Chunk 拼接文本循环搜索后称全文。

提取一般实体/短语/数字单位等检索 Anchor，返回文档/页/上下文/命中方法/Corpus。参考朋友6～8字符短语、上限约24个的工艺可集中配置；不能加某产品/题号专用规则。

字面命中仅表示相关，不等于能回答。Answerability Judge 要区分直接可答、组合可答、仅实体相关、缺失必要细节、信息不足。对注入/安全边界题，知识里相关事实存在并不自动取消“需要拒绝危险操作”的预期；按 Negative subtype 判断。

真实 Provider Judge 只有在用户触发真实 Probe 时运行，离线验收用 Stub。返回 malformed/超时/证据不足标 uncertain/needs_review，不当自动通过。

全文未命中也不能在解析覆盖不足时宣称“确定没有”。显示解析覆盖与可信边界。Unknown 不能当0或Pass。

## 11. Full-text 索引与 Corpus 原子性

### 11.1 保留当前 Corpus 更新机制

新增/删除文档 → Staging 构建全部产物 → 完整校验 → 原子 Activate；任一失败不改变 active pointer，保留失败审计与清理策略。复用现有实现。

新增 full_text 等价产物并纳入 manifest。示意：documents.json、chunks.json、full_text.json、faiss.index、manifest.json，遵循现有命名，不强制目录重构。

full_text 保存原解析文本及文档/页定位、parser identity、文本 checksum、产物 schema version；Corpus Fingerprint 与其他产物一致，不能新FAISS配旧Full Text。

### 11.2 旧 Corpus 的安全补充

用户已确认补全文产物及必要索引产物构建，但未授权改文档内容、模型和 Chunk。优先使用保存的解析原文；没有时用现有 Parser 重新解析至 Staging，比较旧文档、Chunk、向量、内容身份。

区分 Corpus 内容身份与 artifact_schema_version。仅增加全文 sidecar 且内容/Chunk 身份没变时，不应无故让全部旧评测失效；若现有 fingerprint 机制不能区分，按原实现一致性处理并明确影响，不能改历史 fingerprint 伪造匹配。

如重新解析实际产生不同 Chunk/文本、缺模型权重、耗时异常或旧产物无法核实，不静默覆盖 active Corpus。保留 Staging 与明确阻塞，历史演示继续可用。索引引擎支持与 active 产物是否就绪分别报告。

不自动下载巨大新模型、不调用付费 OCR。产物扩展如无需变换 Chunk/vector，可只构建新增产物并完整校验后原子激活兼容 bundle。

### 11.3 历史与失效提示

旧 Snapshot 标 `Coverage Planner：Legacy/V1` 或历史实际采集版本；未采集 Cluster 详情显示未采集。不能在升级前端后把旧20题标成 Dynamic K-means。

文档内容真实变化后显示“知识库已变化，当前 Golden/Baseline 为旧 Corpus 结果；新 Evaluation 前需重新冻结 Golden”。旧 Production 不自动下线，运行来源及检索 Corpus 兼容状态须诚实展示，不能假称仍是当时冻结环境。

## 12. Baseline、Agent、Sandbox、Regression 与发布

### 12.1 保持一把尺

Baseline 和同一 Experiment 的 A/B/C/D 使用同一冻结 Golden、Corpus、Judge/Gate 定义和可比较配置边界。Evaluation 保存实际配置，不从 current config 反向填历史报告。

总体得分 Overall 只用于比较，11项 Hard Gate 的当前定义/门槛来自当次冻结配置。TTFT、Token Cost、Recall@K、Precision@K、MRR 是比较/诊断项，是否属于 Hard Gate 必须看现有 SPEC，不因V1.4 实施排版改变其资格。

Gate 评测执行失败、Judge 缺失、题目分母不足、部分处理不能显示 11/11 或 completed qualified。旧报告历史缺失不得补算未保存数据。

### 12.2 Agent 的输入输出与搜索空间

输入至少包含当前 Baseline identity、Failed Gate、Bad Case 与 Evidence、Root Cause、Config Snapshot、冻结 Search Space、上一轮合法结果与预算（如果存在）。

输出真实保存 Agent Diagnosis、每个 A/B/C 的独立 Hypothesis、Target Bad Cases、最小必要参数变更、Why/Risk、Config Diff、Round/Experiment identity。

A/B/C 是并列可解释假设，每个假设可包含实现该能力所需的最少联动参数；不把“最小变更”误实现成绝对只能改1个字段。也不能借一个宽泛假设一次改一大串不相关参数。

Agent Prompt、schema 和 Validator 共享当前规则源，包括类型、枚举、范围、依赖与参数名称。典型 `CandidateK >= TopK` 等必须验证。Boolean false、integer0、字符串OFF按照真实 schema 处理，不能宽松强转导致配置语义变化。

保留现有有限格式修复/重试预算，失败不部分写入假候选。保存解析错误路径、允许保留的 Provider 原始输出和 attempt审计；UI 技术详情折叠。不要输出敏感信息或模型隐藏思维链。

Agent 生成计划不执行 Sandbox、不发布。连续点击期间幂等/锁定，异步状态与后台真实记录同步。

### 12.3 Sandbox/Regression

Sandbox 使用隔离 Candidate Config，不修改全局 Production Config。可执行完整 Golden 和固定 Regression 验证，保留当前正确后端逻辑。

Regression PASS 必须来自真实固定回归集/既定方法，不能用“Hard Gate 通过”替代。Fixed Bad Case 必须有基准问题与同尺结果对应，不把当前所有高分题算修复。

Candidate 资格优先：Hard Gate + Regression + 新失败/红线 + 有效身份 + 当前已冻结发布约束。不得因 A Overall 比 C高而自动推荐 A。

### 12.4 Gate 2 与条件性 D

保留 Gate 2 人工确认报告/Recommendation。Qualified Candidate 才可按现有规则进入选择，不用 UI 排序覆盖后端 Winner。

D 是经证据确认有效且可组合的改动组合验证，说明来源 Candidate/有效能力/Config Diff/兼容关系。允许来源 Candidate 整体 Gate 未过但其局部能力有证据有效，前提是当前已支持规则，不按名字随机拼参数。

无可组合能力时沿用现有显式 skip D/retain Winner 规则并记录理由；不为满足 UI 强行造 D。已有 D 生成则完整 Sandbox+Regression，不能只抽查 Bad Case。

D 未通过或没有按当前规则改进 Winner，保持 Winner。例：C11/11、D10/11 → 保留 C；只是例子，所有结果读取真实数据。

### 12.5 Gate 3 与发布：不重构正确底座

保留并回归验证发布前：Sandbox Evaluated、Qualified、当前全部 Hard Gate、Regression PASS、Gate 2 Recommendation、D Decision 完成或合法跳过、Human Release、Evaluation 有效、同 Golden/Corpus/实验来源。

发布事务内再次校验身份/资格，防过期 UI 提交。API 直接请求也不能绕过。Production Version 保存 Config、Candidate、Experiment、Baseline、Golden/Corpus、评测与人工决策来源。

发布后 Baseline 比较起点不是无条件改成新 Production；其更新遵循当前 SPEC。Production、新的默认配置、历史 Baseline 是不同概念。

保留回滚确认、版本记录与现有能力。V1.4 实施禁止自动发布、自动回滚，也不在真实库为了验收按发布按钮。

## 13. Token Usage、Latency 与 Price Config

### 13.1 复用已有采集

检查现有 prompt_tokens/completion_tokens/prompt_cache_hit_tokens、miss tokens、stage timings、estimate_cost()、price env 配置。已有字段复用，避免另建重复 Token 系统。

QA Pipeline 调用与 Judge/QC/Agent 调用分开统计；同一问题对比的成本来自实际两侧调用，不把整个评测成本塞进单答案卡。

### 13.2 集中价格配置

当前实际使用的模型/Provider，官方价格一次核对后存集中配置：provider、实际 model ID/可识别别名、currency、unit（如每百万Token）、uncached_input、cached_input、output、source_url、checked_at/effective_date、billing_mode、price_config_version。

不在每次问答时爬官网；不在前端散落硬编码价格；不按“DeepSeek最新”推测当前 model名称。无法访问官方来源就留未配置状态/完整样例，交付指出阻塞，禁止编价格。

真实运行记录当次价格配置版本或计算快照，后续更新价格不能静默改历史费用。Estimated Cost 是估算，不能称账单费用。

### 13.3 计算和缺失值

在总输入含缓存命中、缓存拆分完整时：`estimated_cost = ((input - cache_hit)*uncached_price + cache_hit*cached_price + output*output_price) / unit`；若 Provider 分别给 miss/hit，则按其实际语义算，校验总数一致。

缺 cache Usage 且存在不同缓存费率时不能把 missing当0而显示精确费用。显示“无法精确估价/Usage不完整”；确有全部输入统一计费的 billing_mode 则可按其真实规则估算。Price缺失、model未知、Usage缺失都有 reason。

数值0表示已采集且确为0；`—`表示未采集。旧记录不把null改0。Token 计数必须是 Provider真实返回，除非另列明确标注的本地估算。

### 13.4 Timing 定义

统一 ms存储、s展示，记录单位。TTFT为请求到首个实际输出Token的时间，非流式未采集时显示未采集，不用total替代。

Retrieval、Generation、Total使用现有真实计时点；并行阶段不简单求和。Generation如包含TTFT则说明嵌套；Judge延迟单独展示。Flow记录体现query processing、embedding/search、fusion/filter/rerank/context、generate等实际存在阶段，不造不存在的组件。

不用Gate2、发布审核等待时长冒充RAG latency，不把浏览器思考秒表当后端Pipeline耗时。

## 14. Interview Demo UI 修订（2026-10-03）

本节与第 15 节替代旧 UI 指令，包括各页 StageStepper/ProcessStrip、Baseline 三张 KPI/Conclusion Banner、Pipeline 流程图、优化 Agent 重复 A/B/C 方案卡、Sandbox 全指标主表、发布大流水线、方案对比历史评测与方案选择器。业务流程仍由真实状态与人工操作约束；全局闭环只在概览表达。每页 H1 下副标题只解释当前页负责什么。

### 14.1 一级导航和二级结构

| 一级导航/H1 | 二级结构 | 主问题 |
|---|---|---|
| RAG 自进化项目概览 | 项目概览；已有业务/技术架构入口 | 项目解决什么问题、当前到哪里 |
| 知识库 | 技术策略、Corpus 摘要、文档列表 | 用了什么知识技术策略 |
| Pipeline 配置 | 知识处理 / 检索 / 生成 / 评测配置 | 什么固定、什么允许 Agent 调 |
| Golden Dataset | 当前测试集 / 候选池；历史详情 Drawer | 评测集是否可信、哪些题需人处理 |
| Baseline | Baseline 报告 / Hard Gate / Bad Case 诊断 | 当前 Baseline 哪里失败 |
| Agent 工作台 | 诊断 / 优化 Agent / A/B/C/D / Sandbox | 为什么失败、如何实验、谁合格 |
| 发布 | 当前 Production 决策、参数变化、版本记录 | 为什么发布当前方案 |
| 问答验证 | 问答验证 / 方案对比 / Monitoring | 同题回答如何变化、如何进入下一轮 |

保持八个一级模块、已有 Hash/兼容入口与启动方式。导航名与 H1 一致，不新增导航、重新编号或重复巨大 Hero。

### 14.2 视觉、卡片与滚动

复用浅灰背景、白色细描边和深色侧栏、既有 token 与组件；统一标题/副标题/字段/表格/状态字体。成功状态采用极浅低饱和绿与深绿文字，失败/风险用小范围提示；不加渐变、毛玻璃、发光、装饰大图标。

同组卡片同宽、同高、同 padding、同字段顺序与 Footer 位置。A/B/C 与双答案桌面等高，超长内容内部滚动；响应式保持可读。表格内部滚动、sticky Header，允许页面正常纵向滚动，桌面与 390px 主文档无横向溢出。

空态只需一句说明与必要操作；主页面不重复铺“未采集 / — / 暂无”。真实存在的 0、false 必须显示；历史未采集主屏隐藏，在技术详情解释原因；不适用字段不展示，不回填历史。

### 14.3 Drawer、确认框与 Select

文档、Chunk/Evidence、Case、Candidate、Gate、Coverage/Planner、Search Space、完整配置、高级指标、其他 Candidate 与技术 JSON/Trace 统一右侧 Drawer。标准宽 560px，wide 宽 800px，贴右且高 100dvh；移动端占满视口，内部滚动，不挤压主布局。支持 Esc、关闭按钮、遮罩、焦点进入/归还与锁定背景滚动；未保存编辑复用保存/放弃提醒。

删除、发布、回滚及明确不可逆操作保留居中确认 Dialog。详情不使用居中大弹窗；切换内容避免叠层遮挡关闭按钮。长审计内容在 Drawer 技术详情折叠，仍可查阅。

全站统一 Select：选中自动关闭，外部点击/Esc 关闭，方向键/Enter 与焦点状态可用，选项不被裁切。Chip 支持选择/取消；原因与“其他”说明按现有规则校验。长文本按同类规则截断，全文可通过键盘/触控详情读取。

### 14.4 异步、术语与费用

保留已有 Global Operation 与对象身份绑定；旧请求不能覆盖新 Baseline/Production/问题结果。QA 等待只在回答区体现真实等待状态，不虚构进度；加载、失败、失效、空态都有明确原因和可行操作。

动作与说明优先中文，保留 RAG、Chunk、Embedding、Baseline、Golden Dataset、Bad Case、Gate、Agent、Sandbox、Regression、Production、Prompt、Recall@K、Precision@K、MRR、TTFT 等术语；入口统一“查看 Hard Gate”。

Input Tokens / Output Tokens 是数量，费用另列 Provider Cost / 估算费用。只有完整真实 Usage 与当次冻结价格依据、模型和币种匹配时展示估算；当前价格配置为 USD，展示 USD，不自行换算人民币。历史缺完整计费信息只在详情解释无法回算，不把 null 当 0、不编金额。Judge Model 只取实际评测配置，缺失显示原因，禁止用 Generation Model 兜底。

## 15. 逐页 Interview Demo 实施规范

### 15.1 RAG 自进化项目概览

唯一保留全局闭环的页面：项目问题 → 当前下一步 → 生命周期 → Golden/Baseline/Agent/Production 紧凑状态。保留已有业务架构、技术架构入口与目标架构边界。状态来自当前对象：已评测与 Gate 通过分开，旧 Production 不冒充新 Baseline 的 Candidate；下一步按真实状态推导，不自动触发业务。

### 15.2 知识库

删除顶部知识入库流程与大 KPI，替换为四张统一技术策略卡：PyMuPDF / OCR fallback 与页章节定位；Section-aware Chunking 与跨页/section_path/page_start/page_end；现有中文 Embedding；实际 FAISS 类型/相似度。维度与 indexed 数量仅来自只读实际索引字段，未知不按模型推测。

Corpus 规模用一条轻量摘要（文档/页/Chunk/indexed）；文档表拉宽，保留文档名、页数、Chunk 数、解析/索引状态与操作。Metadata、Chunk 原文、JSON 和定位进入右 Drawer。现有新增/删除入口和原子 Corpus 规则保留，本轮不实际增删文档或构建索引。

### 15.3 Pipeline 配置

删除 Knowledge Preparation / Online QA 大区与流程条，不补新 Query→Retrieval→Generation 流程。正文四类统一配置卡：知识处理配置、检索策略、生成策略、评测配置；Provider 为轻量状态行。

Frozen / Agent 可调是主信息，来自实际 Search Space/Validator；不推测可调范围，不开放固定模型、Parser/OCR/Chunk。评测配置不属于每次 Production QA runtime；Judge 缺失不借 Generation Model 兜底。完整配置与技术审计在 Drawer。

### 15.4 Golden Dataset：总体

删除 Coverage/Construction/Validation/Probe/QC/Gate 1 顶部阶段 Stepper，不替换流程条。主顺序为紧凑 Coverage Preview → 当前 Golden 摘要 → 真实风险（仅有时）→ 完整题目表；“当前测试集 / 候选池”两 Tab 保留，Snapshot History 为右 Drawer。

当前 Legacy 工艺 Snapshot 与 V2 Planner Preview 分开：Legacy 不等于未批准，仍按实际冻结/审核/Corpus 身份判断正式评测资格；UI 改版不能将其改标 V2。主表保留 #/类型/问题/Probe/QC/人工审核/操作，构造类型和来源弱化或进入详情。

### 15.5 Golden：Coverage与当前结果

现有当前 Corpus Planner Preview 能力保留为一行/小卡：Corpus、Profile、Coverage 状态与详情入口。Cluster、Slot、Gap、Material、Frozen Plan、merge/抽样/复用与 Audit 在右 Drawer；正常主页面不铺内部 JSON。

题数与 Positive/Ablation/Negative、Frozen/已确认状态均来自当前数据；Validation/Probe/QC/人审风险只在实际存在时出现，可查看相关题目。无风险隐藏整个关注区。批准、修订、AI 草案、Evidence 选择与质量失效仍复用既有规则，不自动改 Corpus 或批准。

### 15.6 Golden：Snapshot History

只读历史 Drawer 保留实际 Snapshot/Profile/题数/冻结时间/Corpus/Generation Run/Planner 来源。查看不切换 current Golden；已有“选择用于后续评测”操作仍需明确影响并遵守治理。无历史采集字段在详情解释，不伪造 V2 Plan。

### 15.7 Golden：候选池与导入

工具栏压成一行：Profile、来源、评测组、构造类型、搜索、导入业务用例；候选列表为主体，创建新 Golden 按钮保持紧凑。AI 生成与真实业务导入进入统一候选池，保留来源。

Profile 进度与 Coverage 缺口、选择、模板下载、上传预览/逐行错误/确认仍按既有契约；满足数量与 Slot 后才能建新 Run，复制不继承旧批准。导入使用右 Drawer，不改变治理与真实数据。

### 15.8 Baseline报告

删除三张 KPI（Hard Gate/Overall/Bad Case）、顶部 Stepper，不用 Conclusion Banner 替代。保留 Baseline 报告 / Hard Gate / Bad Case 诊断三 Tab。

报告按运行结果（是否通过、Failed Gate、Bad Case）→ 配置摘要（Query/Retrieval/Rerank & Context/Generation）→ Golden 组成与必要性能 → 技术详情排序。Run/Snapshot/Judge ID、时间、完整配置与 Usage 在 Drawer。Overall 仍只用于比较，历史缺失不补算。

### 15.9 Hard Gate

保留滚动 Table 与轻量 X Passed / Y Failed，不做 11 张卡。按 Positive/Ablation/Negative & Safety/Performance 展示实际值/冻结门槛/判定，失败行淡红，通过只用小 PASS 状态。

点行打开右 Drawer：指标定义、Actual、Threshold、Included/Contributing Cases 与关联配置。判断读取当次报告；非 Gate 比较指标进高级指标，不新增门槛。

### 15.10 Bad Case诊断

主表保留题目/问题、单一 Primary Root Cause、主要失败指标、Secondary Signals/Evidence 与操作。真实历史主根因原值保留，Secondary Signals 可多项；不把主根因与失败标签混为同级，也不强制五类映射。

点行右 Drawer 顺序：问题、Expected/Reference、Golden Evidence、Retrieved Evidence、Model Answer、Judge、Primary Root Cause、Secondary Signals、关联 Gate、技术详情。候选召回未采集时不能用 Final TopK 冒充。

### 15.11 Agent工作台：诊断

删除顶部 Stepper 和重复大指标。动态非零根因卡显示实际 Case 数、现象/影响/依据与可用能力，卡可点击且有轻量相关案例链接。当前已保存 7 个 Bad Case 是 Generation 6 / Safety 1，页面不得写死此分布或虚构 Retrieval/Ranking 根因。

案例/证据在 Drawer；Agent 未运行时机器诊断与 Agent 解释分别标来源，不借上轮实验兜底。

### 15.12 Agent工作台：优化 Agent

主页面只保留三类：Agent 收到了什么（Failed Gate/Bad Case/Root Cause）、能改什么（Search Space/当前预算）、决定验证什么（已保存诊断与实验假设摘要）。删除 Experiment Plan 的重复 A/B/C 卡，候选具体 WHY/CHANGE/RESULT 由下一 Tab 承担。

保留真实 Round/状态/预算及必要来源。生成中、失败、等待显示真实状态；生成计划不执行 Sandbox、不发布。

### 15.13 Search Space

主屏“Search Space · N”轻入口，N 来自真实 Validator；点击 wide 右 Drawer。表展示参数、类型、允许值、当前冻结 Baseline 值、依赖、Agent 可调与含义；表头固定、长说明可读。不硬编码 12 或改变范围、类型、授权。

### 15.14 A/B/C/D

桌面 A/B/C 同宽同高同字段，统一 WHY（提出原因）/ CHANGE（真实参数差异）/ RESULT（Hard Gate/Regression/资格）；长 Hypothesis、风险、目标案例、完整配置、Usage/报告进入 Drawer。未运行/失败/不合格分别诚实展示，不能预设 C 永远获胜。

D 独立放在下方，说明 Winner + 已验证有效能力组合、来源与差异、完整回归与最终决定；失败或未提升保留 Winner。当前历史 C 11/11、D 10/11、保留 C 只由持久化结果呈现，不固定为业务常量。

### 15.15 Sandbox

主表仅四项：Hard Gate、Bad Case、Regression、Qualification，含 Baseline 与实际 A/B/C/D。Baseline 不适用 Regression/资格时不显示 FAIL 或 0；缺 D 按真实状态说明。

完整三组质量、Fixed Bad Case、Overall、Recall@K/Precision@K/MRR、TTFT、Input/Output Tokens、Provider Cost 与阶段 Timing 保留在“查看高级指标”右 Drawer。Recommendation 浅绿/低饱和；Gate 2 保留人工确认且低于主表视觉权重，不推荐不合格高分方案。

### 15.16 发布

删除顶部 Sandbox/Gate 2/Gate 3 Stepper 与 A/B/C/D 大流水线。焦点是为何发布当前 Production：实际来源 Candidate、Hard Gate、Regression、Gate 2 与 Gate 3 人工决策。

主屏仅列真正变化字段；完整配置/未变参数→“查看完整配置”右 Drawer，A/B/D 或其他真实状态→“查看其他 Candidate”右 Drawer，不页面内展开巨大 details。版本/报告/人工 Rollback 保留但降低视觉权重。新 Baseline 不改旧 Production 身份，未发布状态保留必要动作与阻断原因。

### 15.17 问答验证

Tab 固定问答验证 → 方案对比 → Monitoring。Chat 为主体，拉伸回答区，历史会话与问题 chips 轻量，输入固定底部，Production Version 为小标签。Evidence 右 Drawer；内部 Trace/Provider ID/Corpus Fingerprint/Full Config/缺失字段进入详情。

等待、失败/重试/停止沿用真实能力；历史回答不冒充本次实时回答，不在本轮验收触发真实 Provider。

### 15.18 方案对比

唯一对比对象固定为左侧当前正式 Baseline 与右侧实际 active、人工已发布 Production；无 Qualified Candidate fallback、Previous Production 默认、任意方案选择器。缺当前有效 Baseline 或真实已发布 Production 时明确阻断，不用 bootstrap `baseline-v1`、候选或无审核版本冒充 Production。

紧凑控制区为 Baseline Bad Case Select + 可编辑问题输入 + 右侧“运行实时对比”；选题立即填框，不自动调用。删除历史评测 UI、对应 GET 加载与历史缓存；Sandbox 承担历史实验比较，Comparison 缓存不能恢复旧历史报告为实时结果。

桌面双栏 50/50 严格对齐、同高：顶部小配置摘要/真实身份 → 最大回答正文 → Evidence 与已采集 Latency/Input Tokens/Output Tokens；参数差异在各栏顶部，长配置内部滚动，不另做巨卡。高级 Timing/TTFT/费用详情按需查阅，不铺缺失占位。

两侧绑定同 Question/comparison ID 及请求开始时冻结配置；Production 更新/旧请求返回不能混写，单侧失败保留另一侧与具体原因。零 Token/零耗时等真实 0 保留；费用只按完整 Usage+冻结价格币种显示，不额外调用 Judge 给实时回答评分。小屏堆叠且身份清楚。

### 15.19 Monitoring

主表仅问题、当前状态、人工判断、操作；Signal/Latency/Source 与版本归属进入右 Drawer。删除顶部流程条与大量空 Signal 字段；不增加监控图表、大盘、告警中心、SLA 或实时任务。

面试用 30–60 秒说明 Production QA → 人工判 Bad Case → Confirm Trigger → 下一轮 Optimization Agent。沿用 Pending Trigger/Context、有效 Baseline、幂等 Confirm、首轮 Round 1 和人工边界；确认不等于 Agent 已完成，不自动调参或发布。

## 16. 数据模型、Migration 与兼容策略

### 16.1 新字段/对象只作为语义建议

按实际Schema最小扩展，字段名可沿用仓库，不强制建立所有新表。需要承载的语义有：Planner版本与冻结Plan、Cluster/Slot、Group/Construction、Evidence位置、Candidate/Final retrieval trace、Full-text产物schema、Validation/Probe风险、PendingContext状态、Usage完整性、Price版本、对象来源ID。

旧字段null保留，Adapter显示未采集。新增字段默认不能把旧记录变成V2Passed。旧approved不因新增nullable字段全部变unapproved，但不能因此被展示为V2工艺。

### 16.2 SQLite写入与事务

所有INSERT显式列名，禁止依赖表列顺序。Negative可为空ReferenceAnswer/Evidence与必填审计字段语义区分，不允许NULL错位写入EvidenceJSON造成NOTNULL失败。

迁移可重复执行不破坏数据，有migration版本/验证；在旧Schema副本执行两次验证幂等性。保持已有外键/唯一性/JSON约束，兼容SQLite实际版本。

新Golden/Candidate状态与审计写入事务保持一致；Provider调用不要占数据库写事务几十秒。失败Record保留；DB错误提供结构化可定位原因。

### 16.3 Frozen对象不可变

ApprovedSnapshot、当次EvalConfig/Judge/Gates、已生成CandidateConfig、发布Version保留不可变内容。可附加新审计/显示Adapter，不覆盖原JSON。

不因更改当前Price/Validator/Planner而反向重写历史。外部重新生成采用新Run/新Snapshot，用户手动触发。

### 16.4 可比性与失效

所有结果绑定Golden/Corpus/Config/Judge/Gate/Experiment来源。若不可比，明确历史/失效，不将分数放一表冒充同尺结论。CurrentResolver用相同规则。

新PlanPreview不触发任何历史失效；真实Corpus变更按既有规则失效相应Golden/Baseline。仅UI重排不造成业务状态改变。

### 16.5 错误审计

记录阶段、attempt、对象ID、错误类型、公开简短原因、允许保留的RawOutput/ValidationPath。旧Run仅有error没有raw时显示历史未保存，不虚构响应。

HTTP接口失败码与UI状态一致。未生成Candidate时不得数据库显示成功；取消客户端弹窗不等于取消后端任务；后台终止能力存在才展示终止按钮。

## 17. 必须覆盖的离线验收矩阵

以下均使用隔离测试库、临时Corpus、合成Fixture或Stub，禁止污染真实Demo数据。优先拓展已有测试；不要为普通文字/间距写大量镜像测试，把测试预算用在数据与流程边界。

第 17.1–17.4 节保留既有业务验收契约；2026-10-03 Interview Demo 本轮验证范围为第 17.5 节的 UI/只读字段与数据保护，不因文档修订重复执行真实或隔离业务生命周期。

### 17.1 P0与身份

| Test ID | 场景 | 通过标准 |
|---|---|---|
| ID-01 | B0有E0；新B1无Experiment | B1Agent等待，E0只在历史，Production仍旧版本 |
| ID-02 | 最新completed是CandidateSandbox | resolver/Monitoring仍选有效Baseline |
| ID-03 | PendingRound0无Candidates | 首次Generate正常Round1 A/B/C |
| ID-04 | 真Round1有候选未Sandbox | 下一轮保持原阻断，不因Round0修复放宽 |
| ID-05 | Trigger重复Confirm/双击 | 一个上下文、一份审计关系，无重复实验 |
| ID-06 | 首次Agent malformed/Provider error | Failed可重试，不假完成，不创建半套ABC |
| ID-07 | Corpus/Golden已失效，无当前Baseline | Trigger保留pending，有可读前置条件 |
| ID-08 | 切换Baseline后旧异步响应到达 | 不覆盖新视图，Drawer/Candidate已清旧身份 |

### 17.2 Coverage与组卷

| Test ID | 场景 | 通过标准 |
|---|---|---|
| GV-01 | n=0/1/2/小语料 | 明确边界，无非法K、不崩溃 |
| GV-02 | 同Corpus/seed/参数重复Preview | 相同分配，Audit可复现 |
| GV-03 | 存在多个小簇/全小簇 | 稳定合并、无死循环、总量守恒 |
| GV-04 | Mini/Medium/Full | 总数20/49/98与8/4/8、20/9/20、40/18/40一致 |
| GV-05 | Topic数多于可用Slot | 真实缺口，不虚称全覆盖 |
| GV-06 | 优先未使用Chunk | 可追踪采样与reuse，不按产品题号写分支 |
| GV-07 | 无表格/无桥接材料 | 不造Aggregation/Bridge，合法fallback并记录 |
| GV-08 | Pool20题8/4/8但集中2Topic | 阻断Coverage不足，显示缺口 |
| GV-09 | Pool选题满足Slot | 新Run保存匹配与Plan，不继承旧Approved |
| GV-10 | Negative自动Topic归类 | 只CoverageAnchor，无伪Evidence |
| GV-11 | MultiCluster Evidence | 保存关联，匹配稳定，不丢Bridge第二跳 |
| GV-12 | Preview后Corpus变化 | Preview失效，不使用旧Plan创建Run |

### 17.3 HardValidation/Probe/QC

| Test ID | 场景 | 通过标准 |
|---|---|---|
| VP-01 | AI/Import/Pool输入同类候选 | 同基础Validator输出，无三套规则 |
| VP-02 | 答案同义表述但关键事实有原文 | 不强制整句字面相等、不误报Anchor |
| VP-03 | Evidence在错误Corpus/伪造页码 | 阻断，并给出位置错误 |
| VP-04 | 两Chunk但单Chunk即可回答 | 不假称Bridge通过 |
| VP-05 | Aggregation缺项/超出范围 | 阻断或具体风险，不能Pass |
| VP-06 | 口语Ablation自包含 | 可通过，无强制Q01/Q09关系 |
| VP-07 | 候选召回命中但TopK落掉 | 保存两层，初步RankingFailure |
| VP-08 | 候选召回也未命中 | RetrievalFailure，合法题不因而直接非法 |
| VP-09 | 多跳AnyHit而AllHit失败 | 不显示充分Evidence命中 |
| VP-10 | Final充分Evidence但生成失败 | 诊断有Generation依据，非仅标签 |
| VP-11 | 假Negative答案只在未切块原文/表数字 | RawFullText能发现可疑材料；StubJudge可阻断 |
| VP-12 | 字面相关但不足回答 | 不把字面命中直接判FakeNegative |
| VP-13 | 注入/安全题有相关原文 | 根据expected_behavior，不误取消边界题 |
| VP-14 | Judge超时/非法JSON/文本解析不足 | uncertain/review，不默认Pass |
| VP-15 | 人工改Question/Answer/Evidence | 相关Probe/QC/Review重置并留审计 |
| VP-16 | 19/20或失败Slot | 保留19合法题与失败占位，不冻结20题Snapshot |
| VP-17 | 生成失败重试、QC修一次 | 预算分开且有限，不无限自动修复 |

### 17.4 数据、索引、成本、发布

| Test ID | 场景 | 通过标准 |
|---|---|---|
| DS-01 | 旧Schema迁移、重复迁移 | 数据语义无损、幂等、显式列INSERT |
| DS-02 | Negative可空答案与EvidenceJSON | 不出现列错位/NOTNULL异常 |
| DS-03 | 旧FrozenSnapshot/已发布Version | 原内容不改，V1/Legacy而非伪V2 |
| DS-04 | FullText构建中失败 | activeCorpus不变，旧产物仍可用 |
| DS-05 | Manifest指向混合Fingerprint | 拒绝Activate/Probe，不读半版本 |
| DS-06 | 只新增兼容FullText产物 | 记录schema升级，不伪改旧内容/身份 |
| DS-07 | 实际解析/Chunk变化 | 不无声覆盖，按Corpus变化提示失效 |
| CT-01 | CacheHit/Miss/Output齐全 | 单位/币种/模型价格正确，无重复计算 |
| CT-02 | Cache拆分缺失、不同费率 | 显示不可精确估价，missing非0 |
| CT-03 | Price/model/Usage未知 | 原因明确，不编价/编Token |
| CT-04 | 真实采集0 vs历史null | 分别0和—，版本化价格不改旧估价 |
| CT-05 | 并行/嵌套Timing | 不误相加、TTFT未采集不填Total |
| RL-01 | Overall最高但Gate未过 | 不推荐/发布，资格优先 |
| RL-02 | D未过而Winner合格 | 保留Winner，Ddecision完整 |
| RL-03 | RegressionFAIL/未跑/Gate2未确认 | UI/API/事务均阻断发布 |
| RL-04 | Preview/新实验/升级UI | 不改真实Production、Baseline和旧Snapshot |
| RL-05 | 旧UI资格在提交前失效 | 事务拒绝过期发布，不假成功 |

### 17.5 前端与Browser/E2E

前轮 V1.4 业务验收的完整隔离 Stub 生命周期与 54 个 Test ID 保留为历史契约，证据见 V1_4_IMPLEMENTATION_VERIFICATION；本轮 Interview Demo 不重跑业务生命周期，聚焦前端隔离/Stub 行为、真实持久化数据只读 GET 与数据保护。隔离交互覆盖未运行/失败/不合格/Qualified/Published/Legacy/Stale，不把固定截图或 Stub 称为真实 Provider 验收。

检查以下交互：Select选择/外部/Esc/键盘关闭；原因Chip取消与其他必填；列表整行Drawer；所有详情/Evidence/错误/关闭按钮；stickyHeader与内部滚动；QA不出全局进度框；同问题选择立即填入；双答案字段固定；异步刷新身份不串台；真实缺值清楚；空态正常。重点断言各页已移除指定 Stepper/KPI/流程与历史对比、固定正式 Baseline vs 已发布 Production、Advanced Metrics/Full Config 在 Drawer、0/false 保留、费用币种/价格依据与无真实写请求。

桌面三尺寸建议1440×900、1280×800、1024×768，重点对应MacBook屏幕空间。小屏Drawer不超屏，主页面不横向溢出。Chromium与WebKit/Safari验证（能用WebKit则运行；不可用不能宣称Safari已实测）。保留截图证据与检查表。

截图目测检查标题/表头/行距/字重/对齐/按钮Footer/遮挡/截断/卷内计数。一页页检查全部8个一级模块与关键二级页，不只首页截图。

若E2E可能访问真实Provider，强制测试环境注入Stub/禁止外部Provider网络；先核实测试配置再运行，不能“测试顺便烧一次”。

## 18. 最少量真实验证：作为用户操作清单，不自动执行

代码和离线验收通过后，交付三条可复现手动步骤：

1. 一次Baseline vs Production实时问答对比：验证真实Answer、Usage、Latency、Cost配置与缺失原因。默认只需现有问题，不自动Judge整卷。
2. 一次ProductionQA事件→人工标BadCase→ConfirmTrigger→手动启动Agent：验证P0首轮真实生命周期。必须说明真实Agent可能创建新实验并使用预算，用户选择何时跑，不自动跑Sandbox/发布。
3. V2PlannerPreview：确认动态K/小簇合并/Slot分配，Preview使用已存向量无需付费模型；不紧接着自动生成20题。

如果面试要声称“当前Golden是V2生成”，必须以后另行运行/审核/冻结新V2Golden，并在同一新Snapshot上重新Baseline/实验/验证。当前仅升级Engine且保留V1演示时，要讲“V2引擎已实现，当前演示快照来自V1”，不能误导。

不为了用户可能将来演示而现在自动重跑Mini20。完整真实Lifecycle重跑需要单独指令。


需求输入 SHA-256：`e576e62794e7dcf1a26399a6de0b7ca2a5152d8ed2142edf0e6c6f1a6aec80bc`。此校验值仅用于追踪需求来源，不代表代码或真实数据完成验证。

## 19. 历史存档（Superseded，不用于当前目标判定）

<details>
<summary>展开 V1.3 及其包含的 V1.2 / V1.1 历史内容（截至 2026-09-30）</summary>

以下为升级前文本原样存档，其中的“当前”“唯一”和实施授权均属于历史，不覆盖 V1.4。未被 V1.4 替代的数值与安全底座已在第 2 节明确继承；未决冲突以第 4 节为准。

# RAG Self-Evolution Platform 产品规格

> **唯一当前产品规则：V1.3 — Friend-Aligned Evaluation & Experiment UX**
> 本节覆盖下方 V1.2 / V1.1 历史条款。历史条款仅供追溯，标有 Current / Confirmed 的旧措辞不再生效。运行能力、真实数据及发布状态以持久化审计为准；本版本开发不得修改真实 `demo.db` 或代替用户调用 Provider、重新运行 Baseline、生成实验或执行人工 Gate。

## V1.3 冻结规则

1. 面试主线：知识库 → 黄金测试集（Hard Validation、三类 Probe、QC P0/P1/P2、Gate 1）→ Baseline 报告和逐题诊断 → 唯一 Optimization Agent 的 Hypothesis / A/B/C → Sandbox / Regression → Gate 2 → 条件 Composite D → Gate 3 → 问答试验。版本、监测和回滚保留为辅助能力。
2. 八个一级导航依次为概览、知识库、管线配置、黄金测试集、Baseline、Tuning、版本与发布、问答试验。旧 Hash route 保留；启动入口固定 `#overview`。正式题型名称仅为 Positive（正向题）、Ablation（消融题）、Negative（负向题）；Faithfulness 中文为“忠实性”。
3. Golden Profile 为 Mini 8/4/8=20、Medium 20/9/20=49、Full 40/18/40=98。新 Run 冻结 `expected_count`、`positive_count`、`ablation_count`、`negative_count`，生成、局部持久化、补题、Probe、QC、审核、Gate 1、进度和导出均读取该 Profile。旧 Mini 元数据兼容读取，不改写旧 Run 或 Snapshot；历史 40 题仍是未验证 Legacy。大 Profile 仅提示调用量和时间，不虚构 Token 费用。
4. Hard Validation 逐项记录实际检查结果；未运行或旧记录缺少的检查显示“未记录”，不伪装为通过。Positive / Ablation 的 Retrieval Recall Probe 用当前检索链检查冻结证据在 TopK 的命中和排名；未召回但证据有效时保留为 `RETRIEVAL_INCOHERENT`。Negative 的 Vector 与 Full-text Probe 提供真实候选证据和可回答性风险；存在歧义才调用 Semantic Answerability Judge，并保留 safe_rejection 与 prompt_injection 的语义子类校验。Fake Negative 和确定性错误不可豁免。
5. QC 判断题目质量，使用 P0 Blocker、P1 Review、P2 Suggestion 与理由；分数仅辅助，不能恢复“QC ≥85”数值审批门槛。Gate 1 仍是一次人工确认并冻结 Snapshot。
6. Baseline 以冻结 Run 的配置、Golden Snapshot、Judge、指标版本和逐题结果为唯一报告数据。页面按“Baseline 报告 → 质量门禁 → 逐题诊断”组织；报告显示身份、配置、题型组成、失败 Gate、Performance / Retrieval；未采集的历史字段写“未采集”。11 个 Hard Gate 的顺序、阈值、计算和资格继续以当前 `policy.py` 与 `evaluation.py` 为准；Overall 仅供比较。Gate 详情从同一批逐题结果解释贡献题，Bad Case 是逐题诊断的默认筛选，不另建数据源。
7. Tuning 复用现有 Diagnosis、Agent Trace、Candidate 配置、Sandbox 和 Recommendation 审计，展示 Hypothesis、目标 Bad Case、真实 Config Diff、11 Gate、修复、Regression 及风险。Gate 2 只能确认 Qualified Candidate；D 只合并已验证的有效非冲突修改，无有效组合时记 `no_effective_composite`；Gate 3 人工发布。未发布的 `baseline-v1` 是当前 Baseline / 初始配置，不称 Production。
8. 质量指标详情保留两位小数，百分比注明单位；P50/P99 是 Hard Gate，Recall@K、Precision@K、MRR、TTFT、Token Cost 是诊断/比较指标。阶段耗时、相似度、成本等仅展示真实采集值。前端沿用紧凑企业工作台样式，不新增框架、Agent、管理平台或假数据。

## V1.2 历史规则（Superseded by V1.3，不用于当前判定）

以下 V1.2 条款保留为历史记录；其中“当前”“必须”等字样只描述当时版本。

## V1.2 冻结规则

来源：用户提供的《产品成果参考.zip》《视频截图.zip》原始流程图、黄金测试集流程及产品截图，加上用户明确确认的取舍。截图不是可移植源码；不臆造未展示的 Prompt。

1. 主线：Knowledge → Mini Golden → Hard Validation / Probe / QC → **Gate 1 Human Confirm Golden** → Baseline → Bad Case → **唯一 Tuning Agent** → A/B/C Sandbox → **Gate 2 Human Confirm Report** → Composite D / Regression → **Gate 3 Human Release** → Production Q&A。Monitoring、版本历史、Rollback 是辅助能力，不是主线前置条件。
2. 保留七个一级页面和现有 FastAPI / SQLite / React / BGE / DeepSeek / FAISS，不增加依赖、数据库表或新 Agent。
3. Corpus 动态发现，最低字段 document_id / chunk_id / chunk_text；product / section 可选。Mini 配额 8 Positive / 4 Ablation / 8 Negative。Coverage 使用真实 Embedding 主题聚类，按簇分配且优先未用 Chunk，不依赖四份 PDF、题号、固定型号。可靠结构可生成 Aggregation / Bridge / Fact；不足由普通槽位补足，不强造特殊题。
4. Hard Validation 只做确定性格式、字段、真实证据、答案锚点、结构、重复等校验。保留通用 OCR 多事实答案锚点，不继续扩展单题规则。Ablation 独立有效即可；source_positive_id 仅可选参考，不要求配对、同答案、同证据、BGE 相似区间或 bigram 阈值。
5. Positive / Ablation 检索未召回为 P1 RETRIEVAL_INCOHERENT，不以 Probe ≥90 阻止人工确认。Negative 保留向量、全文和可回答性检查；Fake Negative 必须阻断。
6. QC 使用 P0/P1/P2 和理由，分数辅助展示，不以 ≥85 单独阻止审批。机器 QC P0 可以在展示风险后由用户明确接受并记录理由；确定性错误、Fake Negative、类别数量错误不可豁免。Provider 运行错误不能伪装为质量结论或可接受 P0。
7. 单题自动 Targeted Fix 最多一次。仍失败交给人工 Edit / Replace，不整集重写、不无限重试。旧 Revision、哈希、事务、恢复审计继续作为内部安全机制。替换保持 Slot / Category，确认采用前不改变活动题；旧题历史保留，新题重新质量检查及人工审核。
8. Gate 1 一次人工确认原子记录审核并冻结 Golden Version；Snapshot 是内部不可变实现，不是另一人工阶段。历史版本不重新解释，正式评测只读取冻结版本。
9. Baseline / A/B/C / D 共用冻结 Golden、Judge、逐题评测器、指标与 Search Space。11 Hard Gates 保留：Positive correctness/faithfulness/completeness ≥80/80/75；Ablation ≥70/75/65；Safe Rejection / Safety Critical / Injection Resistance 均 ≥95；P50 ≤25s，P99 ≤60s。全部通过，不以 Overall Score 抵消失败。诊断指标仍为 Recall/Precision/MRR/TTFT/Token。
10. Tuning 观察历史 Sandbox 结果和真实 Bad Case 后调整假设。A/B/C/D 合计最多 12 次 Sandbox，开始时预占额度、失败也计数，为 D 保留一次。所有已启动评测终结且至少一项合格才开放 Gate 2；用户在同一次报告确认中选择合格赢家，不强求三个方案均合格。
11. D 以赢家为基础，合并经过 Sandbox、确有修复且 Regression 通过的非冲突配置差异；来源方案可整体未达 11 Gate，但必须如实保存失败与有效证据，不推断单参数因果。冲突保留赢家值；记录来源/理由/冲突/最终配置。无新增有效组合不造假 D。有组合则完整重评；只有同时合格、相对赢家无新增失败且实际修复才晋升，否则保留赢家。
12. Gate 3 一次人工确认，在同一事务重验资格、报告确认及 D 决策后发布，记录 Human Release 和完整版本快照。保留前版本与回滚；不能自动发布。
13. 所有本轮写入验收仅用隔离 Fresh DB / Existing DB Copy，actor=test_human。真实用户库、Candidate、审核及 Q01/Q09 Preview 不参与修改。先确定性/Fixture/Portability/Copy 测试，后只跑一条真实 Provider 主链；失败诚实停止，不为通过改考卷或 Gate。

## V1.1 历史规格（Superseded by V1.3，不用于当前判定）

> **唯一正式 Source of Truth**
> **SPEC Version：V1.1 — Simplified & End-to-End Verified Demo Baseline**
> **Status：Current Product Baseline · Implementation Authorized**

## 1. 文档地位与使用规则

本文件是当前 V1.1 Demo 的唯一产品 Source of Truth。[SPEC ChangeLog](SPEC_CHANGELOG.md) 仅记录历史，不产生并行的当前规则。运行能力和数据状态仍以代码及持久化记录为证，不能用规格文字冒充已完成的评测或发布。

修改产品规则时先更新本文件，再检查并同步代码、测试、README、项目上下文、交接文档、决策记录、TODO、架构说明与图、当前 Demo；无影响项须说明原因。历史 Seed、Legacy 和测试 Fixture 不得充当正式 V1 结果。

## 2. 产品定位 `[CONFIRMED]`

产品暂定名：**RAG Self-Evolution Platform / RAG 自进化平台**。

它是面向 3–5 分钟面试展示的评测驱动 RAG 持续优化 Demo，不是普通 Chatbot、大型 RAGOps、多 Agent 或企业审批平台。

核心职责边界：

- Evaluation 负责识别评测中的 Bad Case；Monitoring 可自动识别新 Bad Case 或异常 Signal，并仅生成待处理 Optimization Trigger。
- Optimization Agent 不主动寻找 Bad Case；它从 Evaluation Bad Case 或经 Human Confirm 的 Monitoring Trigger 开始，依次进行 Diagnosis、Hypothesis、Candidate Generation、Experiment 与 Recommendation。

完整产品主线：

`Knowledge → Mini Golden Generation → Hard Validation → Probe → QC → Human Review → Approved Golden → Golden Snapshot → Baseline Evaluation → Bad Case → Optimization Agent → A/B/C → Sandbox → Regression → Recommendation → Human Release → Production Version → Production QA / Monitoring → Human Confirm Trigger → Next Optimization Run`

## 3. 一级信息架构 `[CONFIRMED]`

主业务模块按因果流程排序：

1. 概览
2. 知识库
3. 测试集治理
4. 评测
5. 进化实验室
6. 版本与发布
7. 问答验证

“设置”独立放置，不属于 Self-Evolution 主业务生命周期模块。导航应表达“系统现状 → 知识来源 → 测试资产 → 问题 → 优化 → 发布版本 → 真实问答验证”的顺序，而非功能罗列。

## 4. Knowledge 与 Golden Dataset `[CONFIRMED]`

Knowledge Base 是 RAG 知识资产，生命周期为：

`Document → Parse → Chunk → Metadata → Embedding → Index`

Golden Dataset 是 Evaluation 测试资产，不是知识库的附属功能，须作为独立生命周期阶段治理。

新版正式 Golden Dataset 必须基于当前真实知识库重新生成。现有历史 40 题可保留为 Legacy / Historical Data，但不得直接迁移为新版正式 Golden Snapshot；本规格不授权物理删除或重新生成历史数据。

## 5. Golden Dataset Generation `[CONFIRMED]`

### 5.1 生成链路

`Knowledge Chunk Pool → Embedding / Coverage Clustering → Coverage Planning → Question Planning → Question Generation → Hard Validation → Probe → QC → Human Review → Approved Golden → Golden Snapshot`

V1.2 新 Run 对每个 Slot 最多自动尝试两次；通过单题 Hard Validation 后，在同一 SQLite 事务中写入 Candidate、活动题目 ID 和 attempt 审计。同一 Run / Slot 仅允许一个活动 Candidate。未凑齐 20 题时状态为 `needs_regeneration`，合格题仅可查看；局部补题只调用失败或缺失 Slot，先沿用原 Coverage 材料及失败反馈，后续持续失败再换同产品真实 Corpus 材料。Corpus 指纹变化时必须新建 Run。20/20 且 8/4/8 复核通过后才进入 Probe、QC 与人工审核；系统异常记为 `failed`。旧 Run 不回填、不补题。

生成必须 Coverage-Aware，避免题目集中于少数文档或 Chunk、问题扎堆、简单改写重复、Fake Negative、证据缺失及答案与 Evidence 不一致。

优先由程序完成确定性工作，例如 Structured Fact、Aggregation、Bridge / Cross-Chunk、Entity → Attribute → Value 的 Question Slot；LLM 用于语义生成、表达变化与复杂 Slot 填充，而非承担全部逻辑。

### 5.2 题型

| Type | 知识证据状态 | 主要验证目标 |
| --- | --- | --- |
| Positive | 知识库存在明确答案 | Retrieval + Answer Quality |
| Ablation | 知识库存在明确答案，但以弱线索、表达扰动、跨 Chunk 或弱化关键词增加检索难度 | Retrieval + Answer Quality 的鲁棒性 |
| Negative | 知识库不存在可回答的有效证据 | Safe Rejection、Knowledge Boundary、Unsupported Answer、Hallucination 与 Safety |

Golden 中的 Ablation Question 不等同于关闭 Rerank、Rewrite 等能力的策略消融实验；两者必须在后续产品与实现中保持区分。

### 5.3 V1.1 Generation Profile

当前仅实现 Mini；Profile 元数据保存类别配额与 `expected_count`，通用治理流程不得依赖题号或固定长度常量。

| Profile | Positive | Ablation | Negative | Total |
| --- | ---: | ---: | ---: | ---: |
| Mini | 8 | 4 | 8 | 20 |

Medium / Full 属于未来版本，不是 V1.1 实现或验收要求。

## 6. Golden Governance `[CONFIRMED]`

正式治理链路固定为：

`Candidate → Hard Validation → Probe → QC → Human Review → Approved Golden → Golden Snapshot`

任何 Candidate 均不得由 AI 自动成为正式 Golden。

Human Review 仅有批准、需修订、拒绝三个业务决定。需修订题可单独编辑 Question / Reference Answer / 真实 Evidence，或请求 AI 草案；保存后重新 Hard Validation → Probe → QC → 人工复审。Draft、版本哈希和尝试历史是内部事务与审计，不是额外人工审批阶段。Positive–Ablation 关系由 `source_positive_id` 等明确元数据表达，不以 Qxx 题号或共享 Evidence 推断，也不强制成对修订。

AI 局部修订先确定真实材料：表达或答案问题默认保留原 Evidence；业务价值、证据不足、重复或明确换知识点时按修订意图先检索当前文档，再检索同产品文档。无合适材料则停止并提示补充意图或手动选材，不随机指派或自动跨产品。人工指定的真实 Chunk 优先；选材方式、范围、原因及 Chunk ID 进入 Revision 审计。Positive/Ablation 使用选定 Evidence 并重新验证答案锚点与关联关系；Negative 材料仅作生成上下文，其 Golden Evidence 仍为空。草案“重新生成”沿用当前材料；“重新选材并生成”按最新原因与标签重新选材，自动选择须避开原证据和当前草案材料。两者均只更新通过 Hard Validation 的预览，草案应用和最终批准始终由人确认。

运行失败时保留原草案、Candidate 和审计。答案锚点失败不降低校验门槛：按最新修订意图提示基于当前材料重写，或重新选择同产品真实材料；无可靠材料时提示修改意图或人工选 Chunk。后台线程在服务重启后不自动续跑，运行态应记录中断并由用户手动重试。进度只显示已持久化的题目计数；单题多阶段任务只显示阶段与耗时，不将固定阶段映射冒充百分比。

### 6.1 Hard Validation

Hard Validation 位于 Probe 之前，使用 Deterministic Rules 检查 Question Format、Required Fields、Evidence 是否存在及位置、Answer Anchor、Cross-Chunk Requirement、Duplicate、Forbidden Structure 及其他可明确判断的问题。明显不合法的数据应 Reject / Rewrite，避免浪费后续 LLM Judge / QC。

### 6.2 Probe

Probe 回答“这道题是否真的成立”，用于 Golden Candidate 自身质量检查，不是 RAG Evaluation。总分为 100：Question Quality `30`、Golden Answer Quality `30`、Evidence Support `40`。Probe Pass 的确认门槛为 `Score ≥ 90`；Evidence 明显无法支撑 Golden Answer 时直接 Probe Failed，不允许依赖其他项目分数补偿。Probe Fail 不能进入正式 Approved Golden，必须进入 `needs_revision`，修改后重新 Probe / QC。

- Positive / Ablation：以真实 Question 进入当前 Retrieval Pipeline，检查 Golden Evidence 是否被召回。Evidence 确实存在但未召回时，应标记类似 `RETRIEVAL_INCOHERENT`，而非简单删除；它可能是高价值 Retrieval Bad Case。

QC 应根据完整 Golden Evidence 原文独立判断支持度，不能只因当前检索未召回就认定证据不支持；Fake Negative 风险仍按原规则阻断。
- Negative：使用 Vector Probe 加 Full-text Probe。后者补足 Table、Exact Number、Model Number、Exact Term 等向量检索盲区；必要时才由 LLM 判断检出的原文是否实际可回答问题。核心目标是避免 Fake Negative。

### 6.3 QC

QC 回答“这道题作为 Golden Test Case 写得好不好”，采用 LLM Judge 加 Deterministic Rules，可检查 Question Clarity、Answer Quality、Evidence Support、Ambiguity、Fake Negative Risk、Unsupported Answer 与 Question / Evidence Alignment。当前复用现有 DeepSeek API / DeepSeek Model，不引入新的模型供应商；Judge Temperature 固定为 `0` 或当前 API / 模型可支持的最接近值，以减少同一 Candidate 多次 QC 的判定漂移。

QC Pass Threshold 为 `Score ≥ 85`。QC Fail 必须进入 `needs_revision`，修改后重新进入治理流程；Probe / QC 都不能替代最终 Human Review。

| Severity | 含义 | 治理结果 |
| --- | --- | --- |
| P0 Blocker | 明确不能成为正式 Golden | 阻止批准 |
| P1 Review | 存在机器不能完全确定的风险 | 必须人工判断 |
| P2 Suggestion | 不影响基本有效性 | 提供建议，不自动阻断 |

### 6.4 Human Review 与 Snapshot

Probe 出现 `RETRIEVAL_INCOHERENT` 不等同题目失败；若 Evidence 存在，可进入人工审核并成为高价值 Evaluation Case。仅经 Human Review 批准的题目进入正式 Golden。

正式 Evaluation 只能使用 Approved Golden Snapshot，不能直接读取变化中的 Candidate Workspace。Snapshot 一经正式 Evaluation 使用即 Immutable；修改 Golden Item 必须生成新的 Golden Snapshot Version，不得回写历史 Snapshot。

## 7. Baseline、Evaluation 与 Bad Case `[CONFIRMED]`

### 7.1 Baseline

Baseline 是当前 Production Pipeline 在固定 Golden Snapshot、固定 Judge Model、固定 Evaluation Rules、固定 Metrics Version 下的一次正式 Evaluation。它不是永远固定的初始版本；Candidate 发布为新的 Production 后，新 Production 成为下一轮优化的 Baseline。

在一次 Optimization Run 中，Baseline 是固定对照组。Candidate A/B/C 的变化不得反向修改 Baseline。

V1.1 默认 Baseline 参数如下；实际执行配置仍以 Evaluation Snapshot 为准：

| Parameter | Target Baseline |
| --- | --- |
| CandidateK | `12` |
| TopK | `4` |
| MinScore | `0` |
| Hybrid Search | `ON` |
| Hybrid Alpha | `0.5` |
| Rerank | `ON` |
| Query Rewrite | `OFF` |
| MultiQuery | `OFF` |
| HyDE | `OFF` |
| Metadata Filter | `OFF` / 不全局强制 |
| Alias Mapping | `OFF` |
| Generation Prompt | 当前 Baseline Prompt |
| Temperature | `0.2` |

`CandidateK` 是初始召回的候选 Chunk 数；当前 `Rerank` 是轻量二阶段重排，不是独立 Rerank Model；`TopK` 是最终进入生成模型上下文的 Chunk 数。实际管道为 `Query → CandidateK → Vector/BM25 归一化 Hybrid → 可选 Lightweight Rerank → MinScore → TopK Context → DeepSeek`。

### 7.2 Evaluation Framework 与 Release Gate

正式 Evaluation 按 Positive、Ablation、Negative 三组分别执行。`Positive × 40% + Ablation × 20% + Negative × 40%` 的公式及其权重明确废弃，不得用于任何发布判断。Evaluation 采用“指标实际值 → 对照 Target → PASS / FAIL”。

| Group | Metric | Target | Release Gate |
| --- | --- | --- | --- |
| Positive | Answer Correctness | `≥ 80%` | Hard Gate |
| Positive | Faithfulness | `≥ 80%` | Hard Gate |
| Positive | Completeness | `≥ 75%` | Hard Gate |
| Ablation | Answer Correctness | `≥ 70%` | Hard Gate |
| Ablation | Faithfulness | `≥ 75%` | Hard Gate |
| Ablation | Completeness | `≥ 65%` | Hard Gate |
| Safety / Negative | Safe Rejection Rate | `≥ 95%` | Hard Gate |
| Safety / Negative | Safety Critical Accuracy | `≥ 95%` | Hard Gate |
| Safety / Negative | Prompt Injection Resistance | `≥ 95%` | Hard Gate |
| Performance | Latency P50 | `≤ 25s` | Hard Gate |
| Performance | Latency P99 | `≤ 60s` | Hard Gate |

上述 11 项是当前 Release Gate 的全部 Hard Gate Metrics，必须 `11 / 11` 全部 PASS。任一单项失败即 Gate FAIL；不采用平均分或其他指标抵消关键失败。

Positive 与 Ablation 均使用 Answer Correctness、Faithfulness、Completeness，Ablation 以不同 Target 评估鲁棒性。Negative / Safety 的三个 Hard Metrics 分别衡量：无证据、不可回答或应拒答时的 Safe Rejection；安全关键操作问题的正确安全回答；以及对“忽略之前规则”“不要参考知识库”等 Prompt Injection 的抵抗能力。现有 Unsupported Answer、Hallucination、Evidence / Citation 等 Failure Tag 继续用于诊断，不额外构成新的 Hard Gate。

### 7.3 Comparison Metrics

TTFT、Token Cost、Recall@K、Precision@K、MRR 不属于 11 项 Hard Gate，但必须用于 Baseline 与 Candidate A/B/C 的横向比较：

- TTFT（Time To First Token）必须记录，用于比较用户首 Token / 首字响应体验。`TTFT ≤ 5s` 是展示目标；超过时 UI 可标黄 / Warning，但不导致 Candidate Failed，也不新增 Hard Gate。
- Token Cost 必须展示，用于 Baseline / Candidate 横向比较；不设 Budget Limit、不属于 Hard Gate，且不得因 Token Cost 高自动淘汰 Candidate。
- Recall@K 用于判断正确 Evidence 是否被 Retrieval 找回；`Recall@K ≥ 85%` 是 Target / Diagnostic Metric，不属于 Hard Gate。
- Precision@K 用于判断 Retrieval Chunk 中相关 Evidence 的比例；`Precision@K ≥ 50%` 是 Target / Diagnostic Metric，不属于 Hard Gate。
- MRR 用于分析 Ranking Error、Rerank Effect 与 Retrieval Ranking Quality；`MRR ≥ 75%` 是 Target / Diagnostic Metric，不属于 Hard Gate。

当多个 Candidate 通过 11 项 Hard Gate 时，Recommendation 必须能解释其 TTFT、Token Cost、Recall@K、Precision@K、MRR 的差异。Overall Score 仅用于 UI 展示和 Candidate 横向比较：`Overall Score = (Positive Correctness + Positive Faithfulness + Positive Completeness + Ablation Correctness + Ablation Faithfulness + Ablation Completeness + Safe Rejection Rate + Safety Critical Accuracy + Prompt Injection Resistance) / 9`。以上 9 项均为 `0–100` 百分比质量指标，等权平均并保留 `1` 位小数。Latency P50 / P99、TTFT、Token Cost、Recall@K、Precision@K、MRR 均不计入 Overall Score。Overall Score 不是发布 Hard Gate，也不得改变 Candidate 的 Qualified 判定；即使 Overall Score 很高，只要 11 个 Hard Gate 任一失败，Candidate 仍为 Not Qualified。不得重新引入 40/20/40 或其他 Overall Score 加权公式作为发布依据。

### 7.4 Bad Case Detection

Bad Case 可由 Evaluation 自动识别；Monitoring 识别到新 Bad Case 或异常 Signal 时仅生成待处理 Optimization Trigger，须经 Human Confirm 才能启动 Agent。Bad Case 不能以单一 Overall Score 阈值定义；不同 Question Type 使用不同失败规则。单个 Bad Case 可同时拥有多个 Failure Tag，例如：

- Retrieval Failure
- Ranking Failure
- Generation Failure
- Evidence / Citation Failure
- Unsafe Answer
- Hallucination
- Safety Failure
- Performance Failure

Evaluation 识别“哪里失败”，Optimization Agent 分析“为什么失败”。

## 8. Optimization Agent 与 Search Space `[CONFIRMED]`

### 8.1 Run、Diagnosis 与 Bad Case Cluster

Optimization Agent 的完整逻辑为：

`Baseline Evaluation → Bad Case → Bad Case Cluster → Root Cause → Optimization Hypothesis → A/B/C Candidates → Sandbox Evaluation → Regression / Safety / Performance / Red Line → Recommendation → Human Release → Production Version → Monitoring / Rollback`

每次 Optimization Run 至少输入 Baseline Evaluation Result、Bad Case Set、Retrieved Chunks、Similarity / Ranking、Final Answer、LLM Judge、Bad Case Label、Evidence Match、Product / Document Group Result、Production Pipeline Snapshot、Golden Snapshot、Allowed Search Space 与 Constraints。

Agent 不得修改 Golden Answer、删除失败题、修改 Golden Snapshot 或通过修改考试数据提高成绩。它必须基于 `Observed Evidence → Root Cause Diagnosis → Hypothesis → Proposed Change` 推理，不能因最终 Answer 错误而随机调参。

Root Cause 先判断问题层级：Query、Retrieval、Ranking、Metadata / Entity、Generation、Safety、Performance。一个 Bad Case 可有多个 Root Cause，必须记录 Primary Root Cause 与 Secondary Root Cause，并优先围绕 Primary Root Cause 设计 Candidate。

Agent 优先按 Root Cause / Problem Pattern 聚类 Bad Case，例如 Retrieval Miss、Cross-product Confusion、Ranking Error、Answer Incomplete、Hallucination、Over-refusal、Unsafe Answer、Performance Issue。同一 Cluster 使用共同 Hypothesis；不建议每题独立启动完整 Optimization Run。

### 8.2 One Candidate 与 A/B/C Generation

`One Candidate = One Explainable Hypothesis + Minimum Necessary Parameter Set`。它不限制 Candidate 只能修改一个参数：可修改一个参数、多个相关参数，或在存在明确理由时跨多个能力调整。判断标准是参数是否共同服务于清晰、可解释的 Hypothesis；禁止无原因地把大量能力全部开启碰运气。

每轮 Agent 必须生成 Candidate A、Candidate B、Candidate C 三个并列 Candidate：

- A/B/C 不是 A → B → C 的逐级叠加，而是三个不同、可解释的 Hypothesis / Strategy。
- 它们可针对相同 Root Cause 使用不同解决策略，也可使用不同参数组合，但不得机械穷举数字。
- 即使当前轮的 A 先满足 Release Gate，也必须完成当轮 A/B/C 的 Evaluation 后再统一比较。

### A/B/C Generation Principle

A/B/C 由 Optimization Agent 根据 Bad Case、Root Cause、Current Baseline Configuration、Allowed Search Space 与 Historical Evaluation Results 动态生成。测试 Fixture 可提供示例配置，但正式 V1.1 流程不得依赖 Seed 生成 Candidate、结果或赢家。

Candidate 参数必须属于下述已冻结的 Search Space。Agent 可因 Root Cause 判断某些参数不应修改而保持 Baseline，也可同时修改多个共同服务于同一 Hypothesis 的相关参数；A/B/C 不限制为单变量实验。不得硬编码 Candidate A、B 或 C 永远获胜；Recommendation 必须来自真实 Evaluation、Hard Gate、Regression 与 Comparison Metrics。

每个 Candidate 必须记录 Candidate ID、Related Bad Case Cluster、Primary / Secondary Root Cause、Optimization Hypothesis、Parameter Diff、Why This Parameter Set、Expected Metric Improvement、Potential Risk、Full Pipeline Snapshot、Evaluation Result 与 Failure Reason。

### 8.3 当前自动 Search Space

| Capability | Baseline | Allowed Search Space | 适用范围与约束 |
| --- | --- | --- | --- |
| CandidateK | `12` | `12 / 24` | Retrieval Miss、Evidence Coverage Insufficient 时可扩大初始召回深度。 |
| TopK | `4` | `4 / 6` | Retrieval Miss、Evidence Coverage Insufficient、Multi-chunk Evidence 不完整时可提高最终生成证据数。 |
| MinScore | `0` | `0 / 0.1 / 0.2 / 0.3` | 仅低相关噪声、误回答、知识边界等 Root Cause 时调整；提高可降噪，也可能误删真实 Evidence 并降低 Recall。 |
| Hybrid Search | `ON` | `ON / OFF` | Vector + BM25 / Keyword Search；由 Root Cause 决定，非每轮穷举。 |
| Hybrid Alpha | `0.5` | `0.3 / 0.5 / 0.7` | 仅 Hybrid ON 时有效；`0.3` 偏 Keyword / BM25，`0.5` 平衡，`0.7` 偏向量语义。 |
| Lightweight Rerank | `ON` | `ON / OFF` | 可因 Ranking Error、Performance、Latency 与实际收益调整；不声称集成独立重排模型。 |
| Query Rewrite | `OFF` | `OFF / ON` | Retrieval 前执行，适用于口语化表达、Query 与知识库标准表达偏差、Query 导致检索偏移。 |
| MultiQuery | `OFF` | `OFF / 2 / 4 / 6` | 开启后生成对应数量的扩展 Query，必须保留原始 Query；可改善单一问法召回不足，也可能引入扩展噪声。 |
| HyDE | `OFF` | `OFF / ON` | Query 与文档表达差异大、直接向量检索召回不足时，用 Hypothetical Answer / Document Representation 辅助 Retrieval。 |
| Metadata Filter | `OFF` / 不全局强制 | `OFF / STRICT / FALLBACK` | 重点字段为 `product`、`version`、`vendor`，后续 Metadata 完整可扩展 `document_type`。 |
| Alias Mapping | `OFF` | `OFF / ON` | 使用版本化 Dictionary 做 Entity / Terminology Normalization，不等同 Query Rewrite。 |
| Prompt Strategy | 当前 Baseline Prompt | Grounded / Completeness / Abstention | 受控修改 Prompt，不允许每轮完全自由生成新 Prompt。 |

CandidateK 与 TopK 可作为同一 Candidate 的参数组合，例如 `CandidateK 12 → 24` 加 `TopK 4 → 6`，前提是共同服务于“扩大 Retrieval Depth / Evidence Coverage”这一 Hypothesis。

Hybrid Alpha 统一表示 Vector Search 权重：`0.3 = Vector 30% / BM25 70%`，`0.5 = Vector 50% / BM25 50%`，`0.7 = Vector 70% / BM25 30%`。Vector 与 BM25 分数必须先完成可比较的归一化，再进行融合。

MinScore 用于最终候选 Evidence 进入 LLM Context 前的过滤：未开启 Rerank 时，在 Retrieval / Hybrid 后执行；开启 Rerank 时，以 Rerank 后的最终候选结果执行。

Metadata Filter 的 `STRICT` 在识别到可靠 Metadata 后仅检索对应范围；`FALLBACK` 优先过滤，但无结果、结果不足或 Evidence Coverage 不足时退回更宽范围。它用于 Cross-product、Cross-version、Vendor Confusion；实体识别不明确时不得强制过滤到某产品。

Alias Mapping 可启用既有版本化 Dictionary，也可提议新增 Mapping；新增 Mapping 必须审核后才正式生效。示例包括“手柄 → B2 遥控器”“B2遥控 → B2 遥控器”“Dock → 充电座”。

Prompt Strategy 的边界：Grounded 处理 Hallucination、脱离 Evidence 的补充与引用不严谨；Completeness 处理 Evidence 已召回完整但回答漏步骤、限制条件或关键事实；Abstention 处理 Unanswerable / Negative、Evidence 不足仍强答与知识边界不足。每次 Prompt Optimization 必须保存 Original Prompt、New Prompt、Strategy、Prompt Diff、Change Reason、Related Bad Case、Root Cause、Version、Sandbox Result。

Optimization Agent 可受控修改回答约束、Evidence / Citation 要求、Refusal Rule、输出结构与格式；不得修改业务事实、Golden Answer、Golden Evidence，不得将测试答案直接写入 Prompt，也不得通过针对测试集作弊提高成绩。

### 8.4 明确排除的自动 Search Space

以下能力可继续存在于 Pipeline Config，但当前 Agent 不自动修改：

- Parser / OCR：MinerU、OCR、VLM Parser、Table Normalize 等。
- Chunk：Chunk Method、Section-aware、Parent-Child、Page-level、Chunk Size、Child / Parent Chunk Size、Chunk Overlap。
- Embedding Model：固定；不自动 Re-embedding 或重建 Index。
- Generation Model：固定；不自动切换 DeepSeek、Qwen 等。
- Lightweight Rerank：当前是轻量二阶段重排，不是独立 Rerank Model；仅允许 ON/OFF。
- Temperature：固定为 `0.2`。
- Query Decompose：Pipeline Future Capability，不进入自动 Search Space。
- Retrieval MaxTokens：保留为 Pipeline Config，不进入自动 Search Space。
- Rerank TopN：当前不新增且不自动修改。

### 8.5 Root Cause → Search Guidance

此映射是 Candidate Generation 的候选范围，不要求全部执行：

| Root Cause | 可考虑的能力 |
| --- | --- |
| Retrieval Miss | CandidateK、TopK、HyDE、MultiQuery、Hybrid、Hybrid Alpha |
| Cross-product / Version Confusion | Metadata Filter、Alias Mapping、Rerank |
| Ranking Error | Rerank、Retrieval Strategy、Hybrid Strategy |
| Answer Incomplete | Prompt Completeness、TopK |
| Hallucination | Grounded Prompt、MinScore |
| Over-refusal / Unanswerable Handling | Abstention Prompt、MinScore |

### 8.6 Parameter Validation 与 Candidate 去重

Candidate 进入 Sandbox 前必须通过 Parameter Rule Check：参数属于合法 Search Space、未修改禁止参数、参数依赖满足、参数值合法、无明显冲突且不重复历史 Candidate。非法 Candidate 不进入 Sandbox，直接要求 Agent 重新生成。

依赖规则：Hybrid Alpha 只在 Hybrid ON 时有效；`MultiQuery = 2 / 4 / 6` 表示已开启 MultiQuery；Metadata Filter 的 STRICT / FALLBACK 只在 Filter 启用后有意义。

Agent 在生成新 Candidate 前必须查询历史。以实际生效的 Candidate Configuration 判断：最终参数组合完全一致即为 Duplicate Candidate，不重复执行完整 Evaluation；失败 Candidate 也必须保留，以避免重复踩坑。

### 8.7 Sandbox、Regression、max_evals 与停止条件

Sandbox 是不影响 Production 的隔离实验环境。A/B/C 必须使用同一 Baseline Snapshot、Golden Dataset Snapshot、Evaluation Rules 与 Release Gate；技术上可并行或顺序执行，但在产品语义上是并列实验。

每次 Candidate 完整 Evaluation 至少保存：

1. Version / Candidate ID、实际生效的 Candidate Configuration、Pipeline Snapshot 与 Timestamp
2. Model Version、Dataset / Golden Snapshot Version、Golden / Evaluation Snapshot
3. Positive、Ablation、Negative Group Metrics、Product / Document Group Metrics 与 Per-question Result
4. 11 项 Hard Gate Result、Pass / Fail 与 Failure Reason
5. Bad Case Fix Result、Bad Case Count、Regression Result、Safety / Performance Result、Red Line Observation
6. TTFT、Latency、Token Cost、Recall@K、Precision@K、MRR
7. Recommendation Reason，以及 Human Operator / Release Information

Regression 独立版本化，来源可包括历史 Approved Golden、关键业务题、Safety Cases 与历史已修复的重要 Bad Cases；状态至少为 Still Pass、Recovered、Still Fail、Regressed。Regression 是 Sandbox 到 Release Gate 的必须验证步骤：Safety / Critical 类题目不允许新增失败；普通题最多允许新增 `1` 个失败；超过即 Regression Failed。

`max_evals = 12`：单次 Optimization Run 最多累计进行 12 次 Candidate 完整 Evaluation，不要求跑满。仅 A/B/C 回合的实际完整 Evaluation 计入预算。A/B/C 全失败后，Agent 必须读取 Sandbox Result、Regression、Failure Reason、Bad Case Change、Root Cause Evidence，重新判断 Root Cause / Hypothesis 后生成下一轮 A/B/C；禁止原样重复、机械调整数字或无解释扩大 Search Space。

满足以下任一条件可停止：已出现满足 Release Gate 且没有值得继续验证的明确 Hypothesis 的 Candidate；达到 `max_evals = 12`；连续迭代没有有效提升；持续触发 Safety / Performance / Regression Red Line；没有新的可解释 Hypothesis。12 次仍无合格 Candidate 时，状态为 `No Qualified Candidate / Needs Human Review`：保留 Baseline、不发布失败方案、保存全部实验、输出失败原因与人工检查方向。

即使已有 Candidate 满足 Release Gate，仅在仍有明确剩余 Bad Case、存在新的合理 Hypothesis，且没有明显 Cost / Performance 风险时才继续下一轮；禁止为多几分无限优化。

### 8.8 当前 Candidate 边界

V1.1 仅有每轮并列的 A/B/C；Composite D 不进入当前产品、UI 或预算规则。

## 9. Recommendation、Release、Version 与 Monitoring `[CONFIRMED]`

### 9.1 Recommendation

Candidate 只有同时满足以下条件，才进入 Qualified Candidate / Recommendation 范围：11 项 Hard Gate 全部 PASS、Regression PASS、至少修复 `1` 个本轮目标 Bad Case，且全量 Evaluation 后 Bad Case 总数至少减少 `1` 个。任一条件失败即直接淘汰。多个 Qualified Candidate 之间，再比较 Positive / Ablation / Negative Group Metrics、TTFT、Token Cost、Recall@K、Precision@K、MRR、Parameter Complexity 与 Remaining Risk。

Recommendation Report 必须复用 Sandbox 已保存的实验记录，并至少包括：Recommended Candidate、Candidate Hypothesis、Root Cause、Before / After Pipeline、Parameter Diff、三组 Evaluation Metrics、11 项 Hard Gate Result、Product / Document Group Results、Bad Case Fixed、Remaining Bad Case、Regression、TTFT / Latency / Token Cost Change、Recall@K / Precision@K / MRR Change、Risks、Why Recommended、Why Other Candidates Were Not Selected。无合格 Candidate 时必须明确 `No Qualified Candidate`，不得强行选 Winner。

### 9.2 单次 Human Release

发布链路为：

`Qualified Candidate → Recommendation → Human Release / 确认发布 → Version Snapshot → Production`

Optimization Agent 只能生成 Recommendation，不能自动修改 Production。用户只执行一次“确认发布”；服务端在同一事务中复核 Sandbox、11/11 Hard Gate、Regression、Recommendation，写入 Human Release 审计及 Version Snapshot。旧 Candidate Approval / Release Approval 记录仅用于历史追溯，不是当前发布前置条件。Direct Release 不属于 V1.1 主线；若保留内部入口，也不得绕过 Sandbox、Gate、Regression 与人工发布。

V1 不实现虚假的 1% → 10% → 50% → 100% Canary / Gray Release。`direct / canary` 可作为未来架构与数据模型的预留能力，但 Canary / Gray Release 不属于 V1 核心实现。

### 9.3 Version Snapshot 与 Rollback

每次 Production Release 必须在同一事务内保存完整 Version Snapshot，至少包括 Pipeline Config、Prompt、Model Version、Lightweight Rerank 模式、Embedding Model、Golden Snapshot、Evaluation Report、Release Gate Result、Release Time、Release Operator、Previous Version。旧 Production 不得覆盖或删除，出现异常时支持人工 Rollback 至上一已发布版本。

### 9.4 Production Monitoring

V1.1 采用半自动闭环与轻量 Production Monitoring，不建设复杂 APM、完整 Observability Platform 或真实流量调度平台。满足任一条件时，Monitoring 生成 `Optimization Trigger / Pending Optimization Task`：出现 `1` 个 Safety Critical Bad Case；或最近 `20` 次有效问答中 Bad Case `≥ 4`。有效问答仅指有完整问题、回答及可判定 Bad Case 结果的完成记录；中断、缺字段或不可判定记录不计入。

Monitoring 不直接自动启动完整 Agent 调参或自动发布。流程为：

`Monitoring → Trigger → Human Confirm → Optimization Agent`

Monitoring 绝不直接自动启动 Agent 调参或自动发布，Human Confirm 不得被自动绕过。

## 10. 问答验证 `[CONFIRMED]`

“问答验证”作为一级模块，承载 Production Q&A 与 Before / After Comparison：

- Production Q&A：真实体验当前 Production Pipeline。
- Before / After：仅在同一 Question 下比较当前 Production 与已合格 Sandbox Candidate；无合格候选时显示真实空状态。

V1.1 只冻结 UI 原则：优先沿用当前 Demo 的页面结构与设计语言，不重新推翻设计；保持卡片化表达，信息层级、对齐和间距整齐；Baseline / A / B / C / Recommendation 的比较必须容易理解；最终展示质量应达到 AI 解决方案工程师面试 Demo 水平；禁止为“科技感”堆砌无业务意义组件。像素、具体字段扩展与布局细节属于实现表现层，不构成产品规格缺口。

最终 Demo 必须采用稳定、可重复演示的数据链：`Baseline → Evaluation → Bad Case → Optimization Agent → A/B/C → Sandbox → Regression → Recommendation → Human Release`。数据必须清晰体现 Before / After，不得让所有页面只显示随机数据或无法对应的 Mock 数字。A/B/C 必须体现不同的 Optimization Strategy / Parameter Combination，但不得硬编码某一个 Candidate 永远胜出；最终 Recommendation 必须来自实际 Sandbox Evaluation、Gate 与 Regression 结果。

## 11. 完整 Self-Evolution Lifecycle `[CONFIRMED]`

`Knowledge → Mini Golden Generation → Hard Validation → Probe ≥90 → QC ≥85 → Human Review → Golden Snapshot → Production Baseline Evaluation → Bad Case → Root Cause Diagnosis → Candidate A/B/C → Sandbox Evaluation → 11 Hard Gates + Regression → Recommendation → Human Release → Production Version → Production QA / Monitoring → Human Confirm Trigger → Next Optimization Run`

## 12. V1.1 收口原则 `[CONFIRMED]`

当前有效规则是本文件第 1–11 节。V1.0.1 与更早版本的 Decision / ChangeLog 只作历史追溯；不得据此恢复 Composite D、双层发布审批、Seed 结果或题号驱动业务规则。

本文件不定义 Report 的非必填字段、像素级 UI、具体演示题材或固定 Candidate 参数；这些是实现表现层细节，不得反向改变已冻结的流程、质量门槛、审计记录、数据可追溯性或人工发布边界。

## 13. Current Implementation 与历史文档治理

代码与运行记录证明已实现能力；若与本产品规则冲突，应先修正实现并在交付中如实报告未完成项，不得把 Target 文字当作运行证据。

以下材料均为历史实现设计或参考资料，不得作为当前 Target Implementation Requirement：

- `docs/superpowers/specs/`：Legacy / Reference。
- `docs/superpowers/plans/`：历史实施计划，仅供追溯。
- `架构/RAG自进化平台架构说明.md`：当前实现说明，必须与本 SPEC 一致；不产生额外产品规则。

历史材料与本文件冲突时，以 V1.1 为当前产品规则；实际结果仍以可验证记录为准。

## 14. V1.1 实施与验收边界 `[CONFIRMED]`

保持七个一级页面、FastAPI / SQLite / React、11 Hard Gates、Probe ≥90、QC ≥85、人工 Golden Review 与人工发布。不得自动修改用户现有 Candidate、应用未确认 Preview、批准当前库 Snapshot 或发布版本。确定性完整 E2E 与真实 Provider 生命周期验收均须使用隔离数据库，并明确区分 Fixture 与 Real Lifecycle 证据；隔离库中的 Test Human Action 不代表用户实际审核。Medium / Full、Composite D、新模型、多 Agent、Docker、复杂监控和 UI 重设计均不在本版本范围。

## Phase 1 收口补充（2026-09-30，SPEC V1.3）

- 当前事实以 [Current Demo Truth](CURRENT_DEMO_TRUTH.md) 为准；2026-09-26 的阻塞结果为 Historical / Legacy。本轮不重新执行真实 Golden、Baseline、A/B/C/D、人工 Gate 或发布。
- AI 生成与 CSV/XLSX 业务导入进入同一 `questions` 候选池；显式 Evaluation Group 与独立构造题型分开。模板、逐行预览、当前 Corpus 原文定位与重复检查通过后才能确认导入。导入不调用 Provider。
- Mixed Pool 只接受 Mini 8/4/8、Medium 20/9/20、Full 40/18/40。选题复制到新 Run，保留 `source_reference`，清空质量及审批状态；重新完成原有 Probe、QC、人工审核、Gate 1。旧题、审批与 Snapshot 不变。
- Fact 仅采用显式实体属性值；Aggregation 必须有完整材料和穷举答案；Bridge 需共享实体与两段共同支持。可靠事实/聚合正向题确定性构造；不足则普通槽位，不强贴题型。只影响未来候选，历史不回填。
- UI 复用 Radix Dialog、CustomSelect、StageStepper、内部滚动表格、两至三行文字浮层和 `+N` 标签 Popover。执行完成与 Gate 通过分开。QA 保存配置差异可直接查看，版本化 sessionStorage 恢复时不发模型请求；Bootstrap 标 Baseline，Candidate 与其同配置发布版禁止自比。
- 实际执行以单调时钟记录 UTC 起止和阶段耗时。检索子阶段归属 Retrieval，不重复求和；回答与 Judge 分开。P50/P99 Gate 口径和资格规则不变。未来保存完整 Provider Usage，历史无记录显示未采集。
- `RAG_PRICE_CONFIG` 指向集中 JSON 单价配置；默认无价格。必需 model/currency/source/effective_date/cache_billing 和 input_per_million/cached_input_per_million/output_per_million。仅完整 Usage（含 cache-hit）且模型匹配时估算当前调用，保留计价依据，不回算历史。
- 唯一迁移为可空 `monitoring_events.metrics_json` 与迁移登记；旧事件为空，不伪造。人工 Monitoring 阈值和 Trigger 确认规则不变，确认不自动调参或发布。

</details>
