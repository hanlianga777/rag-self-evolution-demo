# RAG Evolution 平台架构说明

> 当前产品规则以 [RAG Self-Evolution SPEC V1.1](../docs/RAG_SELF_EVOLUTION_SPEC.md) 为唯一依据；本文件只说明可核验的实现。

![RAG Evolution 业务流程图](业务流程图.png)

![RAG Evolution 技术架构图](技术架构图.png)

可编辑图源：[业务流程图 HTML](业务流程图.html) · [技术架构图 HTML](技术架构图.html)。

## 运行边界

系统使用本地官方 PDF、BGE/FAISS、SQLite、FastAPI、React 和 DeepSeek。Generation Run 会持久化 Coverage Plan、Question Plan 与 Hard Validation；没有已人工批准的 Positive、Ablation、Negative Golden Snapshot 时，正式 Baseline、Sandbox、Recommendation 与 Release 均保持 `Not Run / Not Qualified`；历史候选题与展示 Seed 绝不作为已验证结果。

## 已实现链路

`Chunk Pool → Mini Golden Candidate (8/4/8) → Hard Validation → Probe ≥90 → QC ≥85 → Human Review → Golden Snapshot → Baseline Evaluation → Bad Case → Optimization A/B/C → Sandbox → 11 Gate + Regression → Recommendation → 一次 Human Release → Version / Rollback → Production QA → Human Confirm Trigger → 下一轮优化`

Mini Golden 的自动步骤只生成候选与机器检查。Human Review 是唯一能批准 Golden 的操作。Monitoring 记录完整、可判定的生产问答；触发 Safety Critical 或最近 20 个有效记录中至少 4 个 Bad Case 时，仅创建 Pending Trigger，必须经 Human Confirm 才会创建关联 Optimization Run。

## 检索与评测

运行时管道为：`Query → CandidateK → Vector/BM25 normalization + Hybrid → optional Lightweight Rerank → MinScore → TopK Context → DeepSeek`。Lightweight Rerank 是现有轻量二阶段重排，不是独立模型。Candidate 配置仅可使用冻结 Search Space；Parser/OCR、Chunk、模型、Temperature、Query Decompose、Retrieval MaxTokens 与 Rerank TopN 不可由 Agent 修改。

逐题结果保存检索排序、证据、Judge、Latency、TTFT、Token Usage / Provider Cost、检索指标、Bad Case 标签和结构化 Root Cause。后端统一计算三组评测、11/11 Hard Gate、Regression、Qualified 与 Recommendation；多个 Pareto Frontier 候选需人选择 Recommendation。Overall Score 只展示九项质量指标等权平均，不是发布 Gate。

## 治理接口

| 范围 | 主要接口 |
| --- | --- |
| Golden 治理 | `POST /api/governance/generate-mini`、`/probe`、`/qc`、`/review`、`/review-batch` |
| 评测与优化 | `POST /api/evaluations/run`、`/api/experiments/run`、`/api/candidates/{id}/run` |
| 发布治理 | `POST /api/candidates/{id}/publish`（单次 Human Release）、`/api/versions/{id}/rollback`；Direct Release 仅为受限内部入口 |
| Monitoring | `POST /api/monitoring/events`、`/api/monitoring/triggers/{id}/confirm` |

DeepSeek 不可用时，系统返回明确的不可用状态，不生成模拟回答、评测、推荐或发布记录。Provider 返回用量时持久化 Token Usage；未提供计费时标记 `Token Usage / Provider Cost unavailable`。
