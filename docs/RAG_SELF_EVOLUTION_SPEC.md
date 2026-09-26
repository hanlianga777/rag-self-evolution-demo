# RAG Self-Evolution Platform 产品规格

> **唯一当前规则：V1.2 — Friend-Aligned Simplified Baseline**
> **Implementation Delivered / Real Lifecycle Blocked**。本节替代下方完整保留的 V1.1 历史规则；实现和分层验收见 [V1.2 验证报告](V1_2_VERIFICATION.md)，不以规格或 Fixture 冒充真实闭环。

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

## V1.1 历史规格（Superseded by V1.2，不用于当前判定）

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
