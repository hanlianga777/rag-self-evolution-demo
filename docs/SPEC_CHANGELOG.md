# RAG Self-Evolution SPEC ChangeLog

本文件是产品规格变更的正式、追加式历史记录。当前 Target Product SPEC 见 [RAG_SELF_EVOLUTION_SPEC.md](RAG_SELF_EVOLUTION_SPEC.md)。不得覆盖或重写既有条目。

## V0.2 — Core Lifecycle

- **Date:** 2026-09-21
- **Status:** Confirmed

### Confirmed Decisions

- 产品定位为评测驱动的企业 RAG 持续优化、验证、发布与监控平台；Evaluation 负责发现 Bad Case，Optimization Agent 从已识别 Bad Case 开始工作。
- 冻结一级信息架构：概览、知识库、测试集治理、评测、进化实验室、版本与发布、问答验证；设置独立。
- Knowledge Base 与 Golden Dataset 分离；历史 40 题保留为 Legacy / Historical Data，不能直接成为新版正式 Golden Snapshot。
- 冻结 Coverage-Aware Golden Generation、Positive / Ablation / Negative 题型、Mini / Medium / Full 默认 Profile，以及 Candidate → Hard Validation → Probe → QC → Human Review → Approved Golden → Golden Snapshot 治理链路。
- 冻结 Baseline、四维 Evaluation、Question-Type-Aware Evaluation、Bad Case Detection、Observed-Evidence-Driven Agent Diagnosis、可解释 Candidate A/B/C 与条件 Composite D。
- 冻结 Sandbox、独立 Regression、Recommendation、Human Approval、Release Gate、Version Snapshot、Production Version 保留与 Rollback。
- V1 使用 Direct Release，不伪造 Canary / Gray Release；采用轻量 Monitoring，且 Monitoring Signal 必须经 Evaluation 才能进入下一轮优化。
- 冻结完整 Self-Evolution Lifecycle 与问答验证模块职责。

### OPEN / TBD Summary

Pipeline Search Space、参数 Range、Agent 修改边界与迭代限制、各题型与各 Gate 阈值、Overall Score 权重、Probe 细则、QC Judge Model、Monitoring 指标与触发规则、页面字段与 Layout、Demo 数据、A/B/C 初始配置，以及各核心 Snapshot / Report Schema 均未冻结。完整清单见 [SPEC 的 OPEN / TBD 清单](RAG_SELF_EVOLUTION_SPEC.md#12-open--tbd-清单)。

### Implementation Status

Implementation NOT Authorized。Current Implementation 与 Target SPEC 的差异已接受并保留；SPEC V1.0 Frozen 前不得因此启动业务重构或 SpecKit Implementation。

## V0.3 — Optimization Agent & Search Space

- **Date:** 2026-09-22
- **Status:** Confirmed

### Changed Items

- 将 Target Baseline 的 Pipeline 默认参数、V0.3 Agent 自动 Search Space、参数依赖与明确排除项写入正式 SPEC。
- 将 A/B/C 生成、Root Cause Cluster、Candidate 去重、Sandbox 保存范围、`max_evals = 12`、停止条件、Composite D、Recommendation、Human Release Gate、Direct Release、Version Snapshot / Rollback 细化为正式决策。
- 将 Monitoring 更新为“生成待处理 Optimization Trigger → Human Confirm → Agent”的半自动闭环；不允许自动调参或自动发布。

### Confirmed Decisions

- Baseline 在一次 Optimization Run 中固定；每轮必须生成三个并列、可解释的 A/B/C Candidate，且每个 Candidate 使用服务于单一 Hypothesis 的最小必要参数集合。
- 冻结 CandidateK、TopK、MinScore、Hybrid / Alpha、Rerank、Rewrite、MultiQuery、HyDE、Metadata Filter、Alias Mapping、Prompt Strategy 的允许值与规则；Rerank TopN 及模型、Chunk、Parser / OCR、Temperature、Query Decompose、Retrieval MaxTokens 不进入自动 Search Space。
- 冻结 Root Cause 诊断、Cluster、Search Guidance、Parameter Rule Check、历史去重、Sandbox Result 最低保存项、12 次累计 Evaluation 上限、失败处理和停止条件。
- 冻结 Recommendation 的 Hard Gate 优先比较、无合格 Candidate 的 `No Qualified Candidate` 状态、条件 Composite D 的完整复验与退回最佳 A/B/C 的规则。
- 冻结 Human Release Gate、受审计的 Direct Release、发布前 Version Snapshot、人工 Rollback 与 Monitoring 人工确认触发链路。

### Closed OPEN / TBD Items

Pipeline Search Space、TopK、CandidateK、Query Rewrite、MultiQuery、HyDE、Hybrid、BM25 / Vector Weight、Min Similarity、Rerank、Rerank TopN、Metadata Filter、Alias Mapping、Prompt Optimization、Agent 每轮最大修改范围、Agent Iteration Limit、A/B/C Generation Rule、Composite D Rule。

### Remaining OPEN / TBD

Overall Score 与各题型 / Gate 阈值、Probe 细则、QC Judge Model、Monitoring 指标与 Trigger 数值、页面字段与最终 Layout、Demo 数据、A/B/C 初始实验配置、`max_evals` 的 D 计数与预算处理、有效提升判定、Candidate 去重范围、Prompt 受控变换边界、Hybrid Alpha 融合细则、MinScore 生效细则、Direct Release 验证顺序，以及各核心 Schema 的剩余字段定义仍未冻结。完整清单见 [SPEC 的 OPEN / TBD 清单](RAG_SELF_EVOLUTION_SPEC.md#12-open--tbd-清单)。

## V0.4 — Evaluation, Gate & Quality Governance

- **Date:** 2026-09-22
- **Status:** Confirmed

### Changed Items

- 将正式 Evaluation 固定为 Positive、Ablation、Negative 三组，并废弃 40/20/40 或其他新的 Overall Score 加权公式。
- 冻结 Positive、Ablation、Safety / Negative、Latency 的 11 项 Release Hard Gate 与 11 / 11 全部 PASS 规则。
- 冻结 TTFT、Token Cost、Recall@K、Precision@K、MRR 为 Candidate Comparison Metrics；它们当前不设 Hard Threshold。
- 冻结 Probe `Score ≥ 90`、QC 使用既有 DeepSeek Judge 且 `Score ≥ 85`，并保留 Human Review。
- 明确 Regression 必须验证但数值 Gate 仍未冻结；Monitoring 保留 Human Confirm 后才进入 Agent 的半自动链路。

### Confirmed Decisions

- Candidate 不能用平均分、Overall Score 或其他指标抵消任一 Hard Gate 失败；仅 11 / 11 全部 PASS 的 Candidate 可进入 Recommendation。
- Safety / Negative Hard Metrics 仅为 Safe Rejection Rate、Safety Critical Accuracy、Prompt Injection Resistance，均为 `≥ 95%`。
- Latency P50 `≤ 25s` 与 Latency P99 `≤ 60s` 为 Performance Hard Gate；TTFT 必须记录但不是当前 Release Gate。
- Token Cost、Recall@K、Precision@K、MRR 必须进入 Baseline / A / B / C / D 的比较与 Recommendation 解释，但不新增 Cost、Recall、Precision、MRR 的 Hard Gate。

### Closed OPEN / TBD Items

Positive / Ablation / Negative Evaluation Threshold、Safety Gate Threshold、Performance Gate Threshold、QC Judge Model、Release Gate Threshold。

### Remaining OPEN / TBD

Overall Score 的未来展示、Regression 数值规则、Monitoring Numeric Trigger、TTFT / Token Cost / Retrieval Metrics 的未来 Target、Probe Detailed Score Rule、Hybrid / MinScore 技术细则、Direct Release 验证顺序、Composite D 预算、有效提升、Candidate 去重、Prompt 边界、Schema、UI、Demo 数据与 A/B/C 初始配置仍未冻结。完整清单见 [SPEC 的 OPEN / TBD 清单](RAG_SELF_EVOLUTION_SPEC.md#12-open--tbd-清单)。

## V1.0 — Final SPEC Closure

- **Date:** 2026-09-22
- **Status:** Confirmed

### Changed Items

- 将 Regression、Monitoring Trigger、有效提升、Probe 评分、Hybrid Alpha、MinScore、Direct Release、Composite D 预算、Candidate 去重、Prompt Strategy、实验记录、Overall Score、TTFT、Token Cost、Retrieval Metrics、UI、Demo 数据链与 A/B/C 原则固化为当前有效规格。
- 将正式 SPEC 的遗留产品待定项全部关闭；未列出的 Report 字段、像素级 UI 与具体演示题材仅为实现表现层细节。

### Confirmed Decisions

- Regression：Safety / Critical 不允许新增失败；普通题最多新增 `1` 个失败；超出即 Failed。Qualified Candidate 必须 11 / 11 Hard Gate PASS、Regression PASS、修复至少 `1` 个目标 Bad Case，且全量 Bad Case 总数至少减少 `1` 个。
- Monitoring 满足 `1` 个 Safety Critical Bad Case 或最近 `20` 次完整可判定问答中 Bad Case `≥ 4` 时，生成 Trigger；流程始终为 `Monitoring → Optimization Trigger → Human Confirm → Optimization Agent`。
- Probe 总分 `100`，Question Quality / Golden Answer Quality / Evidence Support 分别为 `30 / 30 / 40`；Evidence 无法支撑 Golden Answer 直接 Failed。Hybrid Alpha 是归一化后 Vector 权重；MinScore 在最终 Evidence 进入 LLM Context 前执行。
- Direct Release 可跳过 Agent 搜索，但不能跳过 Sandbox、11 / 11 Gate、Regression、Snapshot、审计、Rollback 与 Human Release。D 与所有完整评测 Candidate 同样计入 `max_evals = 12`。
- Overall Score 仅可作为 `0–100` UI 展示和快速比较，绝不作为发布 Hard Gate；TTFT `≤ 5s` 仅为 Warning Target；Token Cost 仅展示比较；Recall@K / Precision@K / MRR 的 Diagnostic Target 分别为 `≥ 85% / ≥ 50% / ≥ 75%`，均不覆盖 V0.4 的 11 项 Gate。
- 实验记录的最低字段、卡片化 UI 原则、稳定可追溯的 Demo 数据链、A/B/C 的差异化策略及 Recommendation 不可硬编码的规则均已冻结。

### Compatibility

- V0.3 的 Baseline、Search Space、A/B/C、D、人工发布、Snapshot / Rollback 与 V0.4 的三组 Evaluation、11 / 11 Gate、Comparison Metrics、Human Confirm 均保留。
- V0.2 中 Monitoring Signal 必须先经 Evaluation 的表述仅保留为历史记录；V0.3 起已确立、且 V1.0 继续采用的 Human Confirm Trigger 链路为当前有效规则。未发现其他现行冲突。

### Closed OPEN / TBD Items

Overall Score、Regression、Monitoring Trigger、TTFT、Token Cost、Recall@K、Precision@K、MRR、Probe、Hybrid Alpha、MinScore、Direct Release、Composite D Budget、有效提升、Candidate 去重、Prompt Strategy、Pipeline / Evaluation / Bad Case / Recommendation / Version Snapshot、UI、Demo 数据与 A/B/C 初始原则。

### Remaining OPEN / TBD

无。V1.0 Target Product SPEC 的产品决策已冻结；实现表现层细节不得反向更改已确认规则。

## Future Entry Template

后续每次规格更新必须在本文件末尾追加以下内容，不得覆盖历史条目：

```md
## Vx.y — Title

- **Date:** YYYY-MM-DD
- **Status:** Draft | Confirmed | Superseded

### Changed Items

- ...

### Reason

- ...

### Confirmed Decisions

- ...

### New OPEN / TBD Items

- ...

### Closed OPEN / TBD Items

- ...
```
