# RAG Self-Evolution Platform 产品规格

> **唯一正式 Source of Truth**
> **SPEC Version：V1.0.1 — Final Closure Patch**
> **Status：Final Target SPEC Frozen · Implementation Authorized / In Progress**

## 1. 文档地位与使用规则

本文件定义 RAG Self-Evolution Platform 的下一版目标产品规格（Target Product SPEC）。后续 ChatGPT、Codex 与 SpecKit 在处理本项目之前，必须先读取本文件及 [SPEC ChangeLog](SPEC_CHANGELOG.md)，不得重新推导已经标记为 `[CONFIRMED]` 的决策。

- 当前仓库中可运行的 Demo 是 **Current Implementation**，不是本文件的实现证明，也不等同于 Target SPEC。
- 当前 Demo 与 Target SPEC 的差异属于正常状态；本次 V1.0 文档冻结不授权因差异修改业务代码、数据、Pipeline、页面或运行时。
- V1.0 范围内的产品决策均已冻结；实现可以选择数据字段、像素和样例内容的表现方式，但不得借此改变本文件的产品规则。
- 新的产品决策必须先更新本文件，再追加 ChangeLog；任何业务实施仍须经单独授权的 SpecKit、Implementation Plan 与 Tasks。

## 2. 产品定位 `[CONFIRMED]`

产品暂定名：**RAG Self-Evolution Platform / RAG 自进化平台**。

它不是普通 RAG Chatbot，也不是单纯的 RAG 参数调优工具。其目标是将企业 RAG 上线后的持续评测、问题发现、自动优化、实验验证、发布与持续监控过程产品化。

核心职责边界：

- Evaluation 负责识别评测中的 Bad Case；Monitoring 可自动识别新 Bad Case 或异常 Signal，并仅生成待处理 Optimization Trigger。
- Optimization Agent 不主动寻找 Bad Case；它从 Evaluation Bad Case 或经 Human Confirm 的 Monitoring Trigger 开始，依次进行 Diagnosis、Hypothesis、Candidate Generation、Experiment 与 Recommendation。

完整产品主线：

`Knowledge → Golden Dataset → Evaluation → Bad Case → Optimization Agent → Sandbox → Regression → Recommendation → Human Approval → Release → Production Monitoring → New Evaluation → Next Evolution`

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

### 5.3 V1 Default Generation Profile

Mini、Medium、Full 表示生成规模与知识覆盖等级，不表示 LLM 推理能力等级。V1 默认比例为 `Positive : Ablation : Negative = 2 : 1 : 2`：

| Profile | Positive | Ablation | Negative | Total |
| --- | ---: | ---: | ---: | ---: |
| Mini | 8 | 4 | 8 | 20 |
| Medium | 20 | 10 | 20 | 50 |
| Full | 40 | 20 | 40 | 100 |

该比例不是行业标准；V1.0 仅采用上述 Mini、Medium、Full Profile。任何后续 Profile 规则调整均须作为新的产品规格变更处理，而非本版本的待定决策。

## 6. Golden Governance `[CONFIRMED]`

正式治理链路固定为：

`Candidate → Hard Validation → Probe → QC → Human Review → Approved Golden → Golden Snapshot`

任何 Candidate 均不得由 AI 自动成为正式 Golden。

### 6.1 Hard Validation

Hard Validation 位于 Probe 之前，使用 Deterministic Rules 检查 Question Format、Required Fields、Evidence 是否存在及位置、Answer Anchor、Cross-Chunk Requirement、Duplicate、Forbidden Structure 及其他可明确判断的问题。明显不合法的数据应 Reject / Rewrite，避免浪费后续 LLM Judge / QC。

### 6.2 Probe

Probe 回答“这道题是否真的成立”，用于 Golden Candidate 自身质量检查，不是 RAG Evaluation。总分为 100：Question Quality `30`、Golden Answer Quality `30`、Evidence Support `40`。Probe Pass 的确认门槛为 `Score ≥ 90`；Evidence 明显无法支撑 Golden Answer 时直接 Probe Failed，不允许依赖其他项目分数补偿。Probe Fail 不能进入正式 Approved Golden，必须进入 `needs_revision`，修改后重新 Probe / QC。

- Positive / Ablation：以真实 Question 进入当前 Retrieval Pipeline，检查 Golden Evidence 是否被召回。Evidence 确实存在但未召回时，应标记类似 `RETRIEVAL_INCOHERENT`，而非简单删除；它可能是高价值 Retrieval Bad Case。
- Negative：使用 Vector Probe 加 Full-text Probe。后者补足 Table、Exact Number、Model Number、Exact Term 等向量检索盲区；必要时才由 LLM 判断检出的原文是否实际可回答问题。核心目标是避免 Fake Negative。

### 6.3 QC

QC 回答“这道题作为 Golden Test Case 写得好不好”，采用 LLM Judge 加 Deterministic Rules，可检查 Question Clarity、Answer Quality、Evidence Support、Ambiguity、Fake Negative Risk、Unsupported Answer 与 Question / Evidence Alignment。V0.4 Target SPEC 复用现有 DeepSeek API / DeepSeek Model，不引入新的模型供应商；Judge Temperature 固定为 `0` 或当前 API / 模型可支持的最接近值，以减少同一 Candidate 多次 QC 的判定漂移。

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

V0.3 Target Baseline 默认参数如下；它们是 Target SPEC，不表示 Current Implementation 已支持：

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

`CandidateK` 是初始召回的候选 Chunk 数；`Rerank` 对候选 Chunk 重新做相关性排序；`TopK` 是最终进入生成模型上下文的 Chunk 数。例如 `CandidateK=12 → Rerank → TopK=4` 表示先召回 12 个候选，经重排后选取 4 个生成证据。V0.3 不新增 `Rerank TopN`。

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

TTFT、Token Cost、Recall@K、Precision@K、MRR 不属于 11 项 Hard Gate，但必须用于 Baseline、Candidate A、B、C 及条件触发 D 的横向比较：

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

`Baseline Evaluation → Bad Case → Bad Case Cluster → Root Cause → Optimization Hypothesis → A/B/C Candidates → Sandbox Evaluation → Regression / Safety / Performance / Red Line → Conditional Composite Candidate D → Recommendation → Human Release Gate → Production Version → Monitoring / Rollback`

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

A/B/C 主要由 Optimization Agent 根据 Bad Case、Root Cause、Current Baseline Configuration、Allowed Search Space 与 Historical Evaluation Results 动态生成。首次 Demo 可预置一组 A/B/C Example Seed Configuration，以保证初始展示具有完整、清晰的产品流程；它仅用于 Demo 初始化，不代表生产规则，不限制 Agent 后续生成新的 Candidate。

Seed 或后续 Candidate 的参数必须属于 V0.3 已冻结的 Search Space。Agent 可因 Root Cause 判断某些参数不应修改而保持 Baseline，也可同时修改多个共同服务于同一 Hypothesis 的相关参数；A/B/C 不限制为单变量实验。不得硬编码 Candidate A、B 或 C 永远获胜；Recommendation 必须来自真实 Evaluation、Hard Gate、Regression 与 Comparison Metrics。

每个 Candidate 必须记录 Candidate ID、Related Bad Case Cluster、Primary / Secondary Root Cause、Optimization Hypothesis、Parameter Diff、Why This Parameter Set、Expected Metric Improvement、Potential Risk、Full Pipeline Snapshot、Evaluation Result 与 Failure Reason。

### 8.3 V0.3 自动 Search Space

| Capability | Baseline | Allowed Search Space | 适用范围与约束 |
| --- | --- | --- | --- |
| CandidateK | `12` | `12 / 24` | Retrieval Miss、Evidence Coverage Insufficient 时可扩大初始召回深度。 |
| TopK | `4` | `4 / 6` | Retrieval Miss、Evidence Coverage Insufficient、Multi-chunk Evidence 不完整时可提高最终生成证据数。 |
| MinScore | `0` | `0 / 0.1 / 0.2 / 0.3` | 仅低相关噪声、误回答、知识边界等 Root Cause 时调整；提高可降噪，也可能误删真实 Evidence 并降低 Recall。 |
| Hybrid Search | `ON` | `ON / OFF` | Vector + BM25 / Keyword Search；由 Root Cause 决定，非每轮穷举。 |
| Hybrid Alpha | `0.5` | `0.3 / 0.5 / 0.7` | 仅 Hybrid ON 时有效；`0.3` 偏 Keyword / BM25，`0.5` 平衡，`0.7` 偏向量语义。 |
| Rerank | `ON` | `ON / OFF` | 可因 Ranking Error、Performance、Latency 与实际收益调整；Rerank Model 固定。 |
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

以下能力可继续存在于 Pipeline Config，但 V0.3 Agent 不自动修改：

- Parser / OCR：MinerU、OCR、VLM Parser、Table Normalize 等。
- Chunk：Chunk Method、Section-aware、Parent-Child、Page-level、Chunk Size、Child / Parent Chunk Size、Chunk Overlap。
- Embedding Model：固定；不自动 Re-embedding 或重建 Index。
- Generation Model：固定；不自动切换 DeepSeek、Qwen 等。
- Rerank Model：固定；仅允许 Rerank ON/OFF。
- Temperature：固定为 `0.2`。
- Query Decompose：Pipeline Future Capability，不进入自动 Search Space。
- Retrieval MaxTokens：保留为 Pipeline Config，不进入自动 Search Space。
- Rerank TopN：V0.3 不新增且不自动修改。

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

`max_evals = 12`：单次 Optimization Run 最多累计进行 12 次 Candidate 完整 Evaluation，不要求跑满。Conditional / Composite Candidate D 同样计入；所有实际执行过完整 Evaluation 的 Candidate 都计入 Evaluation Budget。A/B/C 全失败后，Agent 必须读取 Sandbox Result、Regression、Failure Reason、Bad Case Change、Root Cause Evidence，重新判断 Root Cause / Hypothesis 后生成下一轮 A/B/C；禁止原样重复、机械调整数字或无解释扩大 Search Space。

满足以下任一条件可停止：已出现满足 Release Gate 且没有值得继续验证的明确 Hypothesis 的 Candidate；达到 `max_evals = 12`；连续迭代没有有效提升；持续触发 Safety / Performance / Regression Red Line；没有新的可解释 Hypothesis。12 次仍无合格 Candidate 时，状态为 `No Qualified Candidate / Needs Human Review`：保留 Baseline、不发布失败方案、保存全部实验、输出失败原因与人工检查方向。

即使已有 Candidate 满足 Release Gate，仅在仍有明确剩余 Bad Case、存在新的合理 Hypothesis，且没有明显 Cost / Performance 风险时才继续下一轮；禁止为多几分无限优化。

### 8.8 Conditional Composite Candidate D

A/B/C 不是递进叠加。D 是条件触发的 Composite Candidate：仅当 A/B/C 中存在多个已独立验证有效、且有明确组合价值的能力 / Candidate 时生成。D 可组合多个能力 / 参数，不设最多两项或三项的死限制，仍遵循 `Minimum Necessary Combination`。

D 必须重新执行 Sandbox、Golden Evaluation、Regression、Safety、Performance、Red Line。D 不天然优于 A/B/C；若失败、引入明显 Regression 或 Cost / Latency 不合理，退回最佳已验证 A/B/C，不得为展示组合能力强制选择 D。D 的完整 Evaluation 与任何其他 Candidate 相同计入 `max_evals = 12`。

## 9. Recommendation、Release、Version 与 Monitoring `[CONFIRMED]`

### 9.1 Recommendation

Candidate 只有同时满足以下条件，才进入 Qualified Candidate / Recommendation 范围：11 项 Hard Gate 全部 PASS、Regression PASS、至少修复 `1` 个本轮目标 Bad Case，且全量 Evaluation 后 Bad Case 总数至少减少 `1` 个。任一条件失败即直接淘汰。多个 Qualified Candidate 之间，再比较 Positive / Ablation / Negative Group Metrics、TTFT、Token Cost、Recall@K、Precision@K、MRR、Parameter Complexity 与 Remaining Risk。

Recommendation Report 必须复用 Sandbox 已保存的实验记录，并至少包括：Recommended Candidate、Candidate Hypothesis、Root Cause、Before / After Pipeline、Parameter Diff、三组 Evaluation Metrics、11 项 Hard Gate Result、Product / Document Group Results、Bad Case Fixed、Remaining Bad Case、Regression、TTFT / Latency / Token Cost Change、Recall@K / Precision@K / MRR Change、Risks、Why Recommended、Why Other Candidates Were Not Selected。无合格 Candidate 时必须明确 `No Qualified Candidate`，不得强行选 Winner。

### 9.2 Human Release Gate 与 Direct Release

发布链路为：

`Recommendation → Human Approval → Release Gate → Version Snapshot → Production`

Optimization Agent 只能生成 Recommendation，不能自动修改 Production；Human Approve 后才能生成新的 Production Version。Release Gate 的确认门槛是 11 项 Hard Gate 全部 PASS 与 Regression PASS；Human Release 是最终发布决策，不是绕过 Gate 的快捷入口。

V1 保留 Direct Release：人工已明确确认某个 Pipeline Configuration 时，不需要经过 Agent 搜索即可进入发布流程。Direct Release 仍必须完成 Sandbox 质量验证、11 项 Hard Gate 全部 PASS、Regression PASS、Version Snapshot、Release Record、Audit Trail 与 Rollback Capability；它不等同于 Agent 自动绕过 Sandbox。

V1 不实现虚假的 1% → 10% → 50% → 100% Canary / Gray Release。`direct / canary` 可作为未来架构与数据模型的预留能力，但 Canary / Gray Release 不属于 V1 核心实现。

### 9.3 Version Snapshot 与 Rollback

每次 Production Release 前必须保存完整 Version Snapshot，至少包括 Pipeline Config、Prompt、Model Version、Rerank Model、Embedding Model、Golden Snapshot、Evaluation Report、Release Gate Result、Release Time、Release Operator、Previous Version。旧 Production 不得覆盖或删除，出现异常时支持人工 Rollback 至上一已发布版本。

### 9.4 Production Monitoring

V1.0 采用半自动闭环与轻量 Production Monitoring，不建设复杂 APM、完整 Observability Platform 或真实流量调度平台。满足任一条件时，Monitoring 生成 `Optimization Trigger / Pending Optimization Task`：出现 `1` 个 Safety Critical Bad Case；或最近 `20` 次有效问答中 Bad Case `≥ 4`。有效问答仅指有完整问题、回答及可判定 Bad Case 结果的完成记录；中断、缺字段或不可判定记录不计入。

Monitoring 不直接自动启动完整 Agent 调参或自动发布。流程为：

`Monitoring → Trigger → Human Confirm → Optimization Agent`

Monitoring 绝不直接自动启动 Agent 调参或自动发布，Human Confirm 不得被自动绕过。

## 10. 问答验证 `[CONFIRMED]`

“问答验证”作为一级模块，承载 Production Q&A 与 Before / After Comparison：

- Production Q&A：真实体验当前 Production Pipeline。
- Before / After：在同一 Question 下比较 Production 与 Candidate / New Production，可展示 Answer、Citation、Retrieved Evidence、Latency 与 Pipeline Difference。

V1.0 只冻结 UI 原则：优先沿用当前 Demo 的页面结构与设计语言，不重新推翻设计；保持卡片化表达，信息层级、对齐和间距整齐；Baseline / A / B / C / Recommendation 的比较必须容易理解；最终展示质量应达到 AI 解决方案工程师面试 Demo 水平；禁止为“科技感”堆砌无业务意义组件。像素、具体字段扩展与布局细节属于实现表现层，不构成产品规格缺口。

最终 Demo 必须采用稳定、可重复演示的数据链：`Baseline → Evaluation → Bad Case → Optimization Agent → A/B/C → Sandbox → Regression → Recommendation → Human Release`。数据必须清晰体现 Before / After，不得让所有页面只显示随机数据或无法对应的 Mock 数字。A/B/C 必须体现不同的 Optimization Strategy / Parameter Combination，但不得硬编码某一个 Candidate 永远胜出；最终 Recommendation 必须来自实际 Sandbox Evaluation、Gate 与 Regression 结果。

## 11. 完整 Self-Evolution Lifecycle `[CONFIRMED]`

`Knowledge → Golden Dataset Generation → Hard Validation → Probe ≥90 → QC ≥85 → Human Review → Golden Snapshot → Production Baseline Evaluation → Bad Case → Bad Case Cluster → Root Cause Diagnosis → Optimization Hypothesis → Candidate A/B/C → Sandbox Evaluation → 11 Hard Gates + Regression Validation → Conditional Composite Candidate D → Recommendation → Human Release Gate → Version Snapshot → Production Version → Monitoring / Rollback`

## 12. V1.0.1 Final Closure Patch `[CONFIRMED]`

V0.2–V1.0 遗留的产品决策已在本版本全部关闭：Overall Score、Regression、Monitoring Trigger、TTFT、Token Cost、Retrieval Metrics、Probe、Hybrid Alpha、MinScore、Direct Release、Composite D Budget、有效提升、Candidate 去重、Prompt Strategy、Snapshot / Report、UI、Demo 数据与 A/B/C 初始原则均以本文件第 6 至 10 节为准。V1.0.1 进一步固定 Overall Score 的展示计算方式与 A/B/C Example Seed 的 Demo 初始化定位。

本文件不定义 Report 的非必填字段、像素级 UI、具体演示题材或固定 Candidate 参数；这些是实现表现层细节，不得反向改变已冻结的流程、质量门槛、审计记录、数据可追溯性或人工发布边界。

## 13. Current Implementation 与历史文档治理

当前仓库中的 Demo、README 中的启动说明与现有运行时描述继续作为 Current Implementation 保留。它们不能因为与本 Target SPEC 不一致而在本阶段被删除、重构或改造成目标能力。

以下材料均为历史实现设计或参考资料，不得作为当前 Target Implementation Requirement：

- `docs/superpowers/specs/`：Legacy / Reference。
- `docs/superpowers/plans/`：历史实施计划，仅供追溯。
- `架构/RAG自进化平台架构说明.md`：Current Implementation / 历史架构参考，不是 Target SPEC。

当上述文档与本文件冲突时，以本文件为下一版产品设计的唯一依据；实际已运行能力仍以 Current Implementation 的可验证事实为准。

## 14. 本轮实施边界 `[CONFIRMED]`

V1.0.1 的 `[CONFIRMED]` 产品规则保持冻结。本次已获得独立实施授权；实现必须保持真实数据边界、审计记录与人工发布边界，不得以实现便利改变已确认业务规则。禁止：

- 修改 Frontend、Backend、Database、Migration、Pipeline Configuration、Demo UI 或业务逻辑。
- 重新生成 Golden Dataset、删除现有 40 道历史题、修改 Golden Candidate、Probe / QC Runtime、Evaluation / Baseline / Bad Case 数据。
- 启动 SpecKit Implementation，或依据 Target SPEC 自动修复 Current Implementation。
