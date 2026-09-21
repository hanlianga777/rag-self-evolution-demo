# RAG Self-Evolution Platform 产品规格

> **唯一正式 Source of Truth**
> **SPEC Version：V0.2 — Core Lifecycle**
> **Status：Core Lifecycle Confirmed · Detailed Parameters Pending · Implementation NOT Authorized**

## 1. 文档地位与使用规则

本文件定义 RAG Self-Evolution Platform 的下一版目标产品规格（Target Product SPEC）。后续 ChatGPT、Codex 与 SpecKit 在处理本项目之前，必须先读取本文件及 [SPEC ChangeLog](SPEC_CHANGELOG.md)，不得重新推导已经标记为 `[CONFIRMED]` 的决策。

- 当前仓库中可运行的 Demo 是 **Current Implementation**，不是本文件的实现证明，也不等同于 Target SPEC。
- 当前 Demo 与 Target SPEC 的差异属于正常状态；在 SPEC V1.0 Frozen 前，不得因差异修改业务代码、数据、Pipeline、页面或运行时。
- 本文未明确标记为 `[CONFIRMED]` 的内容一律为 `[OPEN]` 或 `[TBD]`，不得以“合理默认值”补充为正式需求。
- 产品讨论先更新本文件，再追加 ChangeLog；SPEC V1.0 Frozen 后，才可进入 SpecKit、Implementation Plan、Tasks 与统一实施。

## 2. 产品定位 `[CONFIRMED]`

产品暂定名：**RAG Self-Evolution Platform / RAG 自进化平台**。

它不是普通 RAG Chatbot，也不是单纯的 RAG 参数调优工具。其目标是将企业 RAG 上线后的持续评测、问题发现、自动优化、实验验证、发布与持续监控过程产品化。

核心职责边界：

- Evaluation 负责识别 Bad Case。
- Optimization Agent 不主动寻找 Bad Case；它从已经被 Evaluation 识别出的 Bad Case 开始，依次进行 Diagnosis、Hypothesis、Candidate Generation、Experiment 与 Recommendation。

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

该比例不是行业标准；未来可根据 Knowledge Base Size、Coverage、Document Scale 与 Evaluation Cost 配置，具体配置规则为 `[OPEN]`。

## 6. Golden Governance `[CONFIRMED]`

正式治理链路固定为：

`Candidate → Hard Validation → Probe → QC → Human Review → Approved Golden → Golden Snapshot`

任何 Candidate 均不得由 AI 自动成为正式 Golden。

### 6.1 Hard Validation

Hard Validation 位于 Probe 之前，使用 Deterministic Rules 检查 Question Format、Required Fields、Evidence 是否存在及位置、Answer Anchor、Cross-Chunk Requirement、Duplicate、Forbidden Structure 及其他可明确判断的问题。明显不合法的数据应 Reject / Rewrite，避免浪费后续 LLM Judge / QC。

### 6.2 Probe

Probe 回答“这道题是否真的成立”，不采用统一 LLM 分数或固定 Probe Score 阈值。

- Positive / Ablation：以真实 Question 进入当前 Retrieval Pipeline，检查 Golden Evidence 是否被召回。Evidence 确实存在但未召回时，应标记类似 `RETRIEVAL_INCOHERENT`，而非简单删除；它可能是高价值 Retrieval Bad Case。
- Negative：使用 Vector Probe 加 Full-text Probe。后者补足 Table、Exact Number、Model Number、Exact Term 等向量检索盲区；必要时才由 LLM 判断检出的原文是否实际可回答问题。核心目标是避免 Fake Negative。

### 6.3 QC

QC 回答“这道题作为 Golden Test Case 写得好不好”，采用 LLM Judge 加 Deterministic Rules，可检查 Question Clarity、Answer Quality、Evidence Support、Ambiguity、Fake Negative Risk、Unsupported Answer 与 Question / Evidence Alignment。

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

### 7.2 Evaluation Framework

| Dimension | Metrics / 关注点 | 回答的问题 |
| --- | --- | --- |
| Retrieval | Recall@K、MRR、Precision@K、Evidence Match | 是否找到正确知识 |
| Answer Quality | Correctness、Faithfulness、Completeness | 找到知识后回答是否正确 |
| Safety / Boundary | Safe Rejection、Safety Critical Accuracy、Prompt Injection Resistance、Unsupported Answer、Hallucination | 不该回答时是否知道不应回答 |
| Performance | Latency P50 / P99、Token、Cost | 效果提升的代价是否可接受 |

Positive 与 Ablation 重点评估 Retrieval 与 Answer Quality，Ablation 额外关注 Robustness。Negative 重点评估 Safe Rejection、Knowledge Boundary、Unsupported Answer、Hallucination 与 Safety，不得机械套用 Positive 的 Golden Evidence Recall 逻辑。

Overall Score 可用于 Dashboard、Before / After 与 Candidate Comparison 的直观表达，但不得单独决定 Release；Release 还必须通过 Safety、Regression、Performance 等 Hard Gates。Overall Score 权重与具体 Gate Threshold 均为 `[OPEN]`。

### 7.3 Bad Case Detection

Bad Case 由 Evaluation 自动识别，不能以单一 Overall Score 阈值定义；不同 Question Type 使用不同失败规则。单个 Bad Case 可同时拥有多个 Failure Tag，例如：

- Retrieval Failure
- Ranking Failure
- Generation Failure
- Evidence / Citation Failure
- Unsafe Answer
- Hallucination
- Safety Failure
- Performance Failure

Evaluation 识别“哪里失败”，Optimization Agent 分析“为什么失败”。

## 8. Optimization、Sandbox 与 Recommendation `[CONFIRMED]`

### 8.1 Agent Input 与 Diagnosis

每次 Optimization Run 至少输入 Baseline Report、Bad Case Set、Per-Case Evidence、Production Pipeline Snapshot、Golden Snapshot、Allowed Search Space 与 Constraints。Per-Case Evidence 可包含 Golden Evidence、Actual Retrieved Chunks、Rank、Similarity、Answer、Citation、Metrics 与 Failure Tags。

Agent 不得修改 Golden Answer、删除失败题、修改 Golden Snapshot 或通过修改考试数据提高成绩。程序优先提供确定性 Observations，Agent 必须基于 `Observed Evidence → Root Cause Diagnosis → Hypothesis → Proposed Change` 推理，不能跳过 Evidence 凭感觉调参。

典型诊断方向包括：Golden Evidence 未进入 Candidate Pool 对应 Recall / Query Understanding；已进入但排名靠后对应 Ranking；跨产品错误召回对应 Product Confusion；Golden Evidence Rank 1 但 Answer 错误对应 Generation / Prompt。

### 8.2 Candidate A/B/C 与 Conditional D

每个 Candidate 必须是一条可解释的 Hypothesis 加最小必要参数集合；“Search Space 覆盖多种优化能力”不等同于每个 Candidate 必须修改三项以上参数。A/B/C 不是随机参数组合。

Candidate D 不是固定存在。仅当 A/B/C 分别验证出可组合的有效能力时，Agent 可条件生成 Composite D；D 必须重新执行完整 Sandbox 与 Regression，不能因组成部分有效而自动认定最优。无组合价值时不生成 D。

### 8.3 Sandbox 与 Regression

Sandbox 是不影响 Production 的隔离实验环境。同一 Optimization Run 中 Baseline、A/B/C 和条件触发的 D 必须锁定同一 Golden Snapshot、Judge Model、Judge Rules、Evaluation Metrics Version 与运行环境；仅 Candidate Pipeline Snapshot 可变。

Sandbox 必须保留 Config Diff、Per-Question Result、Retrieval Evidence、Answer、Metrics、Latency、Token、Cost 与 Bad Case Changes，不能只保存 Overall Score。

Regression 独立版本化，来源可包括历史 Approved Golden、关键业务题、Safety Cases 与历史已修复的重要 Bad Cases；状态至少为 Still Pass、Recovered、Still Fail、Regressed。其问题是“修复当前 Bad Case 是否破坏既有正常能力”。

### 8.4 Recommendation 与 Human-in-the-loop

最高 Sandbox Overall Score 不等于自动推荐发布。Recommendation 必须综合 Bad Case Recovery、Regression、Safety Gate、Performance Gate、Latency、Cost 与 Config Complexity，并输出 Recommended Candidate、Reason、Recovered Bad Cases、New Regressions、Safety Result、Latency / Cost Impact、Config Diff 与 Risk。

系统可自动进行分析、Hypothesis、Candidate、Sandbox、Regression 与 Recommendation；正式 Production Release 必须保留 Human Approval。Recommendation 不等于自动 Release。

## 9. Release、Version 与 Monitoring `[CONFIRMED]`

### 9.1 Release / Version

发布链路为：

`Recommendation → Human Approval → Release Gate → Version Snapshot → Production`

Release Gate 检查 Golden Evaluation、Regression、Critical Regression、Safety Gate 与 Performance / SLA Gate；具体阈值为 `[OPEN]`。新 Production 发布后，旧 Production 不得覆盖或删除，必须保留 Pipeline Snapshot、Evaluation Result、Release Record、Version History 与 Rollback Capability。

### 9.2 V1 Release Strategy

V1 只实现 Direct Release、Human Approval、Release Gate、Production Version Switch 与 Rollback。不实现虚假的 1% → 10% → 50% → 100% Canary / Gray Release；当前面试 Demo 不具备真实生产流量分流环境。`direct / canary` 可作为未来架构与数据模型的预留能力，但 Canary / Gray Release 不属于 V1 核心实现。

### 9.3 Production Monitoring

V1 采用轻量 Production Monitoring，不建设复杂 APM、完整 Observability Platform 或真实流量调度平台。Monitoring 可关注 Query、Answer Success、Safe Rejection、Latency、Token / Cost、Failure / Feedback，具体 Metrics 与 Trigger Rule 为 `[OPEN]`。

Monitoring 只为下一轮 Evaluation 提供触发信号：

`Monitoring / New Knowledge / Scheduled Evaluation → Evaluation → Bad Case Detection → Optimization Agent → Next Evolution`

Monitoring Signal 不得绕过 Evaluation 直接成为 Optimization Agent Bad Case。

## 10. 问答验证 `[CONFIRMED]`

“问答验证”作为一级模块，承载 Production Q&A 与 Before / After Comparison：

- Production Q&A：真实体验当前 Production Pipeline。
- Before / After：在同一 Question 下比较 Production 与 Candidate / New Production，可展示 Answer、Citation、Retrieved Evidence、Latency 与 Pipeline Difference。

具体 UI、页面字段与最终 Layout 均为 `[OPEN]`；本版本仅冻结模块职责。

## 11. 完整 Self-Evolution Lifecycle `[CONFIRMED]`

`Knowledge → Golden Dataset Generation → Hard Validation → Probe → QC → Human Review → Golden Snapshot → Production Baseline Evaluation → Bad Case Detection → Optimization Agent → Root Cause Diagnosis → Hypothesis → Candidate A/B/C → Sandbox → Conditional Composite D → Regression → Recommendation → Human Approval → Release Gate → Version Snapshot → Production → Production Monitoring → Trigger New Evaluation → Next Evolution`

## 12. OPEN / TBD 清单

以下内容尚未完成产品讨论，不得自行决定：

1. Pipeline Search Space 最终参数列表
2. 各参数允许 Range
3. TopK 范围
4. CandidateK 范围
5. Query Rewrite 模式
6. MultiQuery 数量
7. HyDE
8. Hybrid Search
9. BM25 / Vector Weight
10. Min Similarity
11. Rerank
12. Rerank TopN
13. Metadata Filter
14. Alias Mapping
15. Prompt Optimization
16. Agent 每轮最大修改范围
17. Agent Iteration Limit
18. Overall Score 具体权重
19. Positive Evaluation Threshold
20. Ablation Evaluation Threshold
21. Negative Evaluation Threshold
22. Safety Gate Threshold
23. Performance Gate Threshold
24. Regression Gate Threshold
25. Probe Detailed Threshold / Detailed Rule
26. QC Judge Model
27. Release Gate Threshold
28. Production Monitoring 具体指标
29. Monitoring Trigger Rule
30. 页面详细字段
31. 最终 UI Layout
32. 具体 Demo 数据
33. A/B/C 初始实验配置
34. Pipeline Snapshot 完整 Schema
35. Evaluation Report 完整 Schema
36. Bad Case Schema
37. Recommendation Report Schema
38. Version Snapshot Schema

## 13. Current Implementation 与历史文档治理

当前仓库中的 Demo、README 中的启动说明与现有运行时描述继续作为 Current Implementation 保留。它们不能因为与本 Target SPEC 不一致而在本阶段被删除、重构或改造成目标能力。

以下材料均为历史实现设计或参考资料，不得作为当前 Target Implementation Requirement：

- `docs/superpowers/specs/`：Legacy / Reference。
- `docs/superpowers/plans/`：历史实施计划，仅供追溯。
- `架构/RAG自进化平台架构说明.md`：Current Implementation / 历史架构参考，不是 Target SPEC。

当上述文档与本文件冲突时，以本文件为下一版产品设计的唯一依据；实际已运行能力仍以 Current Implementation 的可验证事实为准。

## 14. 本轮实施边界 `[CONFIRMED]`

本轮仅建立和维护本文件、[SPEC ChangeLog](SPEC_CHANGELOG.md) 及 README 的 Source-of-Truth 说明。禁止：

- 修改 Frontend、Backend、Database、Migration、Pipeline Configuration、Demo UI 或业务逻辑。
- 重新生成 Golden Dataset、删除现有 40 道历史题、修改 Golden Candidate、Probe / QC Runtime、Evaluation / Baseline / Bad Case 数据。
- 启动 SpecKit Implementation，或依据 Target SPEC 自动修复 Current Implementation。
