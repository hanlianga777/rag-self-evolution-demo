# RAG Self-Evolution Platform 产品规格

> **唯一当前目标规格：V1.4 — Golden Engine V2 & Identity-Bound Evolution**
> 冻结日期：2026-09-30（Asia/Shanghai）。状态：**V1.4 代码实施与离线验收完成；最终 296 后端 / 121 前端 / Chromium 208 检查通过，整体审查和一次修复后的限定复审通过，保留一个非阻断 Drawer 提示 Minor；真实 Provider 未重跑、active 全文未激活，不以历史结果替代**。
> V1.4 是 Golden 工艺、对象身份、Monitoring 与信息架构升级，保留现有技术栈和治理底座。新图是目标架构，不是当前 Demo 已具备全部能力的证明。

## 1. 文档地位、依据与本次交付边界

本文件是唯一目标规则源；[SPEC ChangeLog](SPEC_CHANGELOG.md) 仅保留追加式历史。V1.3 及更早内容归入文末历史存档，旧文中的“当前”“唯一”“Implementation Authorized”只代表当时口径，不覆盖本节及 V1.4 要求。

依据：用户提供的 `RAG_SELF_EVOLUTION_CODEX_MASTER_PROMPT_20260930.md`（2026-09-30），以及用户先完成文档与两图同步、后明确批准 V1.4 完整代码实施的范围。任务书是需求输入，本轮代码实施依据用户明确批准的计划。保留真实 Golden、Baseline、Candidate、Production 和冻结 JSON；兼容迁移先在副本验证，全文产物只允许完整校验后的兼容补充。不自动调用真实 Provider、重跑付费流程或执行真实人工 Gate。

正文第 5–16 节保留任务书对应章节的需求语义；第 17–18 节保留其离线验收及手动验证要求。文中的规则是目标要求，实现和运行证据分别记录在第 3 节与 [V1.4 实施验收](V1_4_IMPLEMENTATION_VERIFICATION.md)；本文不把任务书中的故障线索视为已复现 Bug，也不声称已查看其引用的 ZIP、朋友截图或 20 张截图。

优先级：本轮明确用户决策 → V1.4 明确变更 → 未被替代的冻结规则 → 实际持久化配置与规则源 → 朋友资料工艺参考 → 历史截图数字。冲突不得靠改门槛、改数据或猜测消解，具体未决项见第 4 节。

## 2. 产品主线与保留规则

面向企业知识问答的评测驱动 RAG 质量运营与版本决策 Demo。主线应在 3–5 分钟清楚表达：可信 Golden 如何测量问题、Baseline 如何暴露 Bad Case、Agent 如何提出可解释实验、资格与 Regression 如何约束人工发布，以及问答反馈如何回到优化。

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

## 3. 需求追踪与当前实现证据

检查起点：`3a44f2f`；后端阶段至 `cd551e0`，UI 与最终集成修复至 `8c674c6`。下表区分代码与离线证据，不代表重新执行了真实 Provider 生命周期。历史实测记录见 [Phase 1 验收](PHASE1_VERIFICATION.md) 与 [已保存 Demo 事实](CURRENT_DEMO_TRUTH.md)，其日期、Run 和 Provider 边界保持原样；本次不刷新真实运行结果。

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

Root Cause 分类根据当次 Bad Case 数据汇总。无证据不能自称确定根因。支持 Query/Retrieval/Ranking/Generation/Safety/Performance/Unknown 等真实出现的类别，显示非零类别，不固定三张卡。

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

## 14. 全局 UI 设计系统与交互

### 14.1 一级导航和二级结构

| 一级导航/H1 | 二级结构 | 主问题 |
|---|---|---|
| RAG 自进化项目概览 | 项目概览；已有业务/技术架构入口按需保留 | 整个闭环是什么 |
| 知识库 | 文档列表 + 详情 Drawer | 知识如何进入系统 |
| Pipeline 配置 | 分阶段配置卡 | 一条问答怎么走、哪些可调 |
| Golden Dataset | 当前测试集 / 候选池 | 试卷如何可信 |
| Baseline | 报告 / Hard Gate / Bad Case，保留有效入口 | 当前哪里失败 |
| Agent 工作台 | 诊断 / Optimization Agent / A/B/C/D / Sandbox | 为什么失败、怎么实验、谁合格 |
| 发布 | 发布状态 / Production变化 / 版本记录 | 最终发布了什么 |
| 问答验证 | 问答验证 / 方案对比 / Monitoring | 用户体验变了吗、如何闭环 |

一级名称与H1一致，不用左边“参数调优”右边“实验工作台”造成同一模块两种叫法；二级页可用局部标题但不重复巨大Hero。

复用现有路由/Hash，提供必要旧路由alias，不破坏旧书签。移除一级01/02/03编号和页面自己实现的鼠标悬停导航状态文字；浏览器原生链接状态无需hack屏蔽。

### 14.2 视觉与尺寸

保持当前浅灰主内容背景、白色圆角Card、细描边和深色侧栏体系。不要迁移朋友全深色界面，不加入毛玻璃、渐变、发光、装饰插图或大图标。

复用现有token并集中统一字号/字重/行高/圆角/间距/颜色。建议落实8px间距体系，标题与正文层级清楚；不要把建议像素值写死到所有内容导致溢出。

内容Card等宽且同一行对齐；A/B/C、双答案分别等高。桌面内容区流式宽度/合理max-width，不能固定像素大Card造成小屏横向页面溢出。“固定尺寸”指同类卡统一布局和可控列表高度，不是拒绝响应式。

列表表格有合理高度/max-height、内部滚动、sticky Header；页面允许正常纵向滚动，不把所有长文本一次撑到几屏，也不强制无滚动屏幕导致文字被切掉。

### 14.3 颜色与状态

- 浅绿、低饱和：Confirmed/Passed/Qualified/Published 等明确成功状态；参考截图顶部浅绿Stage，不用大块深绿。
- 红色：确定Fail/Blocked/错误，仅失败行或小区域，不整页红。
- 黄/琥珀：Warning/Review/Pending风险提醒；pending执行本身可用中性色。
- 中性：未运行、缺数据、历史、不适用。
- 不只靠颜色；同时有状态文字和图标/Badge。

流程完成与业务结果分开。例如Baseline“已评测” + “Gate9/11 · 未通过”；不要只写“已完成”并绿色。Stage完成可表示操作做完，但必须显示其失败结果。

### 14.4 Drawer、确认框、详情

所有普通详情采用统一右Drawer：Document、Chunk、Evidence、Bad Case、Candidate Report、Coverage、Snapshot History、Config、Search Space。

标准Drawer统一宽度/外边距/标题区/关闭按钮/正文滚动/Footer；Search Space可用wide变体。宽度用响应式上限，例如标准约640～760px、宽约900～1100px且不超过视口；以实际样式校验为准。

支持Esc、关闭按钮、合理点遮罩关闭、焦点进入/归还、focus trap、键盘操作、body scroll lock。不支持native模拟交互。存在未保存编辑时复用统一保存/放弃提醒，不静默丢数据。

删除、发布、回滚等高风险用居中确认Dialog。查看详情不用居中大弹窗。打开其他详情更换Drawer内容或明确层级，避免Drawer套Drawer堆叠挡住关闭按钮。

完整JSON/RunID/RawOutput/技术Trace在Drawer底部折叠，能打开、复制、关闭。公开主页不堆内部ID，但审计详情仍可查。

### 14.5 Select、Chip、表格长文本

统一CustomSelect：选中关闭、外部关闭、Esc关闭、键盘方向/Enter、当前值显示、定位不裁切、Safari可用；单选不常驻多选下拉。组件只建一份，查全站原生/旧Select适用入口。

Chip选中/取消样式一致、重复点击可取消。原因必选；选“其他”时说明必填；后端同样校验。不能按钮看似可点却不生效。

Question列表最多2行，其他长文本2～3行。Hover/focus可看全文且不改变行高，手机/触控和键盘用户可通过行详情查看，不依赖Hover唯一入口。FailureTag最多2个+N，展开能看到全部。

### 14.6 异步状态、进度与错误

保留已有Global Operation机制，Baseline/Sandbox等每个任务只有一个追踪源，刷新后能恢复；不能同时弹多个相互矛盾的进度。

QA不弹全局黑色任务框：回答窗口内显示真实思考/请求等待秒表与阶段状态，有停止能力则复用；不用虚构生成百分比。

Golden进度基于真实Slot/Probe/QC记录。在六段Stage升级后不要把旧60单位公式当新六阶段统一分母。沿用已验证阶段进度或明确定义已处理/合格两种统计，缺数据未知时不编百分比。

“已处理20”不等于“合格20”。失败占位、补题中、QC跳过、人工待审清楚显示。不回到0/100跳变。错误详情和关闭必须可交互，关闭前端提示不删除后台Run。

禁用操作要说明前置条件，loading/error/empty/stale各有正常界面。按钮风格点击前后稳定，不在完成后突然变另一种大块颜色。

### 14.7 中文与术语

业务动作、说明、标题中文。保留RAG、LLM、Chunk、Embedding、Rerank、TopK、CandidateK、Baseline、Golden Dataset、Bad Case、Gate、Agent、Sandbox、Regression、Production、Prompt、Hybrid、Query Rewrite、MultiQuery、HyDE、Recall@K、Precision@K、MRR、TTFT、Monitoring等技术词。

Experiment Summary→实验概览、View Details→查看详情、Config Diff→配置变化等。禁止“按所选配额创建Run”等主界面工程文案；改“创建新的Golden测试集”。报错提供原因+下一步，不展示整段Python traceback。

## 15. 逐页实施规范

### 15.1 RAG 自进化项目概览

顺序：H1/一句话说明→当前下一步→全链路Stage→Golden/Baseline/Agent/Production四个紧凑Summary。保留已有架构说明入口，避免和主概览重复。

Baseline显示已评测和Gate结果；Agent显示实验完成/失败/等待以及真实Qualified情况；Production显示当前Version与来源。四个Summary不用内部RunID当主要信息。

下一步从状态推导，存在新Baseline未Agent时“运行Optimization Agent”，旧Production已发布不意味着下一步永远方案对比。非法/stale状态优先提醒正确前置条件，不自行触发任务。

### 15.2 知识库

统一ProcessStrip：文档→解析/OCR→Chunk→Embedding→Index。这里不展示Golden Topic Clustering；后者是Golden离线Coverage Planning，复用数据但不是每次在线检索阶段。

Summary：文档数、Chunk数、Parser、Embedding/Index。文档表：文档/产品/版本/页数/Chunk/解析状态/索引状态/更新时间/操作。未知版本显示未记录，不显式造版本。

表格Card加高、完整对齐、内部滚动。点击文档整行或详情打开Drawer：Document Metadata、真实解析/索引状态、Chunk列表、单Chunk原文与Metadata、来源定位；主页面不展开大量Chunk。

保留/完善已授权新增文档、删除文档入口，复用现有原子Corpus更新；删除确认说明影响Golden/Baseline，但不在V1.4 实施自动执行真实删文档。

### 15.3 Pipeline 配置

删除顶部重复LLM/Parser/Embedding/Rerank Badge、product_xxxxx内部ID、“最近实际问答阶段”和重复小模块。保留必要Provider健康/配置状态在真实配置或Drawer，不删除接口能力。

顶部两个过程区：Knowledge Preparation（Parse→Chunk→Embedding→Index）；Online QA（Query Processing→Retrieval→Rerank & Context→Generation）。

下方宏观阶段Card：Document Processing、Embedding & Index、Query Processing、Retrieval & Ranking、Generation、Evaluation Configuration。

分别放真实Parser/OCR/Chunk；Embedding/Index；Rewrite/MultiQuery/HyDE/Alias；CandidateK/Hybrid/MinScore/Rerank/TopK/Metadata Filter；Model/Prompt Strategy/Temperature；Judge/Golden Snapshot/Hard Gate。

Evaluation Card明确“Evaluation不属于每次Production问答Runtime”。在线流程不把Judge画成必经环节。

固定项Badge `Frozen`，真实可调项 `Agent可调`，来自规则源。Pipeline页表达当前配置/权限，不自动开放手改所有项。保存配置如已有能力，沿用SPEC授权范围；UI整理不悄悄改变Production。

### 15.4 Golden Dataset：总体

顶部统一六段Stage：Coverage Planning→Question Construction→Hard Validation→Probe→QC→Gate1。Stage显示当前Run真实状态，旧记录缺Coverage阶段细节写历史未采集，不自动改成已完成V2。

主区有“当前测试集”“候选池”两Tab；历史Snapshot移到当前测试集右上按钮→Drawer，取消独立历史Tab。

当前集信息顺序：V1.4 实施结果→需要人工关注（仅有异常时）→Coverage Planning摘要→完整题目表。Stage在标题下固定位置。必要Coverage摘要可放结果旁边，不能先用大型技术审计表淹没结果。

### 15.5 Golden：Coverage与当前结果

V2摘要：当前N Chunks→实际K Topic Clusters→Profile Slot总数→实际Construction分布→Candidate完成数。数字全部动态，Legacy不渲染新算法流程为历史事实。

三项说明：Topic Planning（Embedding+DynamicK-means）、Sampling（按主题厚薄/小簇合并/未使用材料优先）、Profile（当前8/4/8或其他Profile）。按钮“查看Coverage规划”→Drawer。

Drawer表：Cluster/Chunk数/Slot配额/代表文档/章节/Chunk/Construction；展开有merge/抽样/缺口审计，正常主页面不展示原始JSON。

V1.4 实施结果分别显示总Slot、合法Candidate、HardValidation、Probe执行/风险、QC、HumanApproval的真实计数。不要全写“Passed”省掉数量和异常。

异常区按P0/P1/伪负向风险/检索不连贯/需修订等真实类型汇总，可点击筛选列表。无异常显示简洁成功状态，不堆空异常卡。

完整题表：Question/EvaluationGroup/ConstructionType/Probe/QC/HumanReview/操作。点击Drawer能查看ReferenceAnswer、ExpectedBehavior、Evidence、材料来源、Slot/Cluster、Validation/Probe/QC/Review审计、Attempts。

人工批准/修订/AI帮我修/替换证据复用现有能力。多选Evidence/取消/保存真实有效，不把“AI帮我修”实现成自动改Corpus或换整个Chunk策略。关键修订重新校验，并保留修改前版本。

### 15.6 Golden：Snapshot History

Drawer列SnapshotID/Profile/题数/冻结时间/CorpusFingerprint/来源GenerationRun/PlannerVersion。内部ID在历史审计合理保留，首页不突出。Snapshot选中后只读详情，不能点击查看就改变current Golden。

如果提供“选择用于后续评测”等已有操作，明确其影响并按现有规则执行，不能普通历史浏览自动切换。Legacy大批候选折叠，不占主页面。

### 15.7 Golden：候选池与导入

顶部“导入业务用例”；来源筛选全部/AIGenerated/BusinessImport；Group筛选Positive/Ablation/Negative，必要Construction筛选。表Question/Group/Construction/Source/ReviewState/选择。

选题区显示Profile进度和Coverage缺口，不只计8/4/8。按钮“创建新的Golden测试集”，仅数量和Slot满足时可用；不满足有具体说明。不要用Native样式Select和现有统一UI混杂。

导入Drawer支持模板下载、文件预览、每行错误、Confirm。批次原子/逐行处理按已有明确契约，不能显示全部成功而部分丢失。来源字段永远保留。

### 15.8 Baseline首页

标题说明→当前评测Stage→紧凑Hero（HardGate/FailedGate/BadCase/Overall）→FailedGate突出→EvaluationIdentity→ConfigSnapshot→Diagnostics。

Overall加“仅用于方案比较”，不是发布资格。FailedGate每条指标/实际值/阈值/Fail，如截图Ablation68.75/70、SafeRejection87.50/95，但实际值从报告读。

Identity包含Golden/Profile/Judge/评测时间/有效状态，内部ID可在详情。Config按Query/Retrieval/Rerank/Generation，完整配置Drawer。

Diagnostics含Recall/Precision/MRR/TTFT/Usage/Cost、真实阶段延迟，降到辅助层。历史结果缺采集显示—/未采集，不让用户看到一堆重复“未采集”日志；简洁概述后详情。

Baseline报告/HardGate/BadCase已有Tabs可保留，但首页本身要先说明未过哪几项，不要只有点进HardGate才发现问题。不新增独立逐题一级模块。

### 15.9 Hard Gate

保留表格，不做11张大卡。上方X/YPassed·ZFailed，按当次配置分Positive/Ablation/NegativeSafety/Performance，字段指标/实际/阈值/判定。失败行浅红，内部滚动，stickyHeader。

无PerformanceGate时不能虚构，非Gate比较指标放Diagnostics。展示冻结门槛版本和单项解释入口，禁止前端擅自改变判定。

### 15.10 Bad Case

主列表Question（2行）、PrimaryRootCause、MainFailureMetric、FailureTag（2个+N），可按真实分组筛选。删除大量“未关联Gate”文案，无法证明直接贡献写“主要失败指标”，Unknown明确。

点整行→Drawer：Question、ReferenceAnswer/ExpectedBehavior、GoldenEvidence、CandidateRecall与FinalTopK、ModelAnswer、Judge结果、RootCause依据、配置/Timing/Usage/RawJSON技术详情。

历史没有CandidateRecall列表显示未采集，不能拿Top4列表充当Top12。Evidence真实引用位置可查看，无伪按钮。

### 15.11 Agent工作台：诊断

去掉重复BaselineRun/Overall/HardGate/BadCase四大指标。只保留小型当前Baseline来源与FailedGate提醒。

核心RootCauseDiagnosis为动态非零类别卡，数量/影响/依据摘要。当前例可为Generation6、Safety1，未来Ranking3/Query2会变；禁止固定三卡和固定解释。

主页面删除长Evidence清单。每类别“查看Cases & Evidence”→Drawer。根因来自持久化诊断，LLM解释来自当前Agent输出；Agent尚未运行时只显示机器已知诊断，不冒充Agent结论。

### 15.12 Agent工作台：Optimization Agent

实验概览：Round/预算/BadCases/状态，加紧凑来源标识和SearchSpace入口。无需全局RunID大Hero。

主体：AgentDiagnosis（当前真实输出）→ExperimentPlan三轻量卡A/B/C（Target/Hypothesis/ChangedParameters）。删旧“优化假设”大表，不重复放Why/Risk/完整Case/完整Diff。

这些详细字段转下一TabCandidate报告Drawer。生成中/失败/无Experiment分别显示真实状态和可行操作，不用上次成功结果兜底。

### 15.13 Search Space

不单独Tab；按钮“Search Space · N”→WideDrawer。N动态来自Validator。

列Parameter/Baseline/Type/AllowedValues/Dependency/AgentEditable/Meaning，Baseline读取当前ConfigSnapshot，AllowedValues读取规则源，长说明可折行/展开。表headersticky，避免整行只显示省略号。

V1.4 实施只整理排版和统一数据源，不修改数值、范围、固定参数授权。完整注册字段数量与12的截图不同也必须诚实显示。

### 15.14 A/B/C/D

桌面A/B/C三张等宽等高Card，内容多内部滚动，按钮Footer对齐。每卡：CandidateName+资格；Hypothesis；TargetBadCase数；只变化ConfigDiff；HardGate/FixedBadCase/Regression；Risk一行；查看完整报告。

详情Drawer保存Why/Risk/TargetCases/完整Config/评测表/失败/Regression/Agent输出来源等。未运行显示未运行，Failed不是NotQualified同义词。

D独立在下，呈现组合来源/ConfigDiff/完整验证结果/最终Decision。文案“D为有效能力组合验证”。当前D失败保留C时清楚显示，不能自动把D当推荐。

### 15.15 Sandbox

顶部A/B/C/D四个紧凑状态卡，无D显示未生成/已跳过及理由；中间Recommendation结论用浅绿，未合格用中性或Warning，不推荐无资格最高分。

比较表顺序：HardGate→Regression→FixedBadCase→BadCase→Positive→Ablation→Safety→Overall→TTFT→TokenCost→Recall/Precision/MRR。

每个综合行来自已定义计算规则；不凭空平均不同指标。Baseline不适用Regression时N/A，不记FAIL或0。价格未知显示—并可查原因。

表冻结Metric列，必要横向表内滚动，不使页面无限宽。Gate2操作与Recommendation证据可见但不重复做审批入口。

### 15.16 发布

标题下Stage：Sandbox完成→Gate2→Gate3，每个仍区分执行和资格。已发布时首页焦点是“最终发布什么”，删除重复巨型推荐Hero；未发布状态仍保留必要推荐来源和审核动作，不能删掉可发布入口。

CandidateReleaseState四列紧凑，显示真实GateFailed/Eligible/Published/NotGenerated等状态。已发布C可显示，不能新Baseline时把它当新实验C。

ProductionChange只列变化，如PromptStrategyGrounded→Abstention；“1项变化·11项未变化”数量由规范化配置Diff计算。完整配置和未变项Drawer，不默认展开11个未变参数。

版本记录保留，详情/报告Drawer，高风险发布/回滚居中确认。发布事务后重取Production，失败原因可查，按钮不得伪成功。

### 15.17 问答验证

删除二级“机器人知识库问答/当前Production”Hero，H1后直接Tab与Chat。Production身份仍在紧凑会话Header/详情可识别，不删除运行来源信息。

左SessionHistory保留，空态问题建议可直接填入/发起按现有设计明确实现。等待时回答区域显示实时等待秒数，不出黑色全局QA进度框。

回答内容、Evidence、Timing/Usage/Cost分开，证据Drawer。长答案卡内可滚动，不挤压输入区。失败重试/停止如已有能力继续有效，不从历史回答冒充实时输出。

### 15.18 方案对比

Tab选中后直接Baseline vs CurrentProduction紧凑Header，删除重复“方案对比/同一问题比较…”Hero。

问题区：“从BaselineBadCase选择”统一Select，选中立即填框，删除“使用该问题”额外按钮；手动输入仍可编辑，右下“运行实时对比”。来源清楚且不触发自动Provider。

参数差异只显示变化，未变N项→Drawer。左右配置是请求启动时冻结的具体版本，运行中Production变了也不混改标签。

双答案桌面50/50等高，每张三段固定：Header（方案+状态+真实总耗时）、Answer（仅回答正文，内部滚动）、MetricsFooter（TTFT/Retrieval/Generation/TotalLatency/InputTokens/OutputTokens/EstimatedCost固定位置）。下方Evidence·N→Drawer。

流式过程中已有字段立即填，未知—，秒表不是最终总耗时。单侧失败保留另一侧成功结果/明确失败，不能整个对比覆盖为无意义报错。两侧结果绑定相同Question和comparisonID，旧请求不能写入新问题。

对比不调用额外Judge来给实时答案自动评分，除非现有明确能力与用户触发；V1.4 实施只展示真实回答和已采集指标。

小屏堆叠但身份清楚，仍保持同字段位置和完整内容；无需为追求50/50导致不可读。

### 15.19 Monitoring

名称固定Monitoring，位于问答验证Tab。顶部ProductionSignals→HumanReview→Trigger→OptimizationAgent，显示实际状态。

RecentProductionQA表：Question/FeedbackSignal/SafetySignal/Latency/HumanStatus；详情可看QA与版本来源。操作正常/BadCase/安全问题复用真实审计；不能把点踩直接判安全违规。

人工确认BadCase后PendingOptimizationTrigger；再Confirm创建/复用PendingContext，由明确按钮启动Agent。没有人工授权不能自动调参/自动发布。

不要默认每条QA调用LLM判别或新增实时监听后台任务。轻量系统用已有反馈/规则/人工标记，安全信号未采集显示—。

Trigger无有效Baseline时有原因，已确认未运行Agent时pending，Agent首次正常Round1。重复标记/撤销如已有功能记录历史而非删审计。详见P0规则。

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

离线Provider Stub驱动至少一个完整测试生命周期：Legacy数据加载→V2Preview→Slot候选构造与校验→Probe→QC→Gate1→Baseline→AgentRound1→ABC→Sandbox/Regression→Gate2→条件D失败保留Winner→Gate3在测试库发布→QA对比→MonitoringConfirm→新PendingContext/Agent启动。

这个测试生命周期可以批量模拟Provider结果，但每个状态与接口真实推进；不能把固定UI截图渲染当E2E状态流。覆盖未运行/失败/未合格/Qualified/Published/Legacy/Stale。

检查以下交互：Select选择/外部/Esc/键盘关闭；原因Chip取消与其他必填；列表整行Drawer；所有详情/Evidence/错误/关闭按钮；stickyHeader与内部滚动；QA不出全局进度框；同问题选择立即填入；双答案字段固定；异步刷新身份不串台；真实缺值清楚；空态正常。

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
