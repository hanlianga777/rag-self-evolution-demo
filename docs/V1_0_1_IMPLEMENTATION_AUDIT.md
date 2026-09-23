# V1.0.1 Implementation Audit

> 审计日期：2026-09-23。本文只记录当前 checkout 可验证的能力；历史 Candidate / Seed 不代表已批准 Golden、正式评测、Recommendation 或发布结果。

| SPEC 能力 | 当前 Backend | 当前 Frontend（改造前） | 状态 | 本轮动作 |
| --- | --- | --- | --- | --- |
| Knowledge Base | `CorpusStore` 提供 PDF、Chunk、BGE/FAISS 索引与详情 | 与测试集共用旧页面 | Keep | 知识库仅保留文档与 Inspector |
| Dataset Governance | `GovernanceStore` 保存 Candidate、Review、Snapshot | 混在“知识与数据集”Tab | Rebuild UI | 拆为测试集治理页 |
| Probe / QC | `/api/governance/questions/{id}/probe`、`/qc`；30/30/40、QC ≥85 | 旧 Tab | Keep | 在治理页保留受控操作 |
| Human Review | 单题与批量审核、Snapshot 审计 | 旧 Tab | Keep | 明示 AI 不可自动批准 |
| Baseline / Evaluation | `EvaluationRunner`、三组指标、11 Hard Gates、逐题记录 | 内容过薄 | Fix UI | 展示 Gate、指标、逐题结果与 Bad Case |
| Bad Case | `bad_cases` 持久化且有标签/根因 | 分散显示 | Fix UI | 评测为入口、进化实验室读取 |
| Optimization Agent | 冻结 Search Space、A/B/C、去重与 `max_evals=12` | 无真实运行时读取 | Fix API/UI | `/api/optimization` 返回最近持久化实验 |
| Sandbox / Regression | Candidate 评测、Regression、Qualification | 旧页面混入 Monitoring | Rebuild UI | 进化实验室四阶段表达 |
| Recommendation | 后端 Pareto 与无合格 Candidate 状态 | 不稳定/不可加载 | Fix API/UI | 返回并展示真实 Recommendation |
| Release / Version / Rollback | Approval、Publish、Version Snapshot、Rollback 已实现 | 版本页仅基础列表 | Keep / Fix UI | 保留快照、发布边界、真实空状态 |
| Monitoring | 事件、Trigger、Human Confirm 已实现 | 放在进化实验室 | Rebuild UI | 移至问答验证 |
| Production Q&A | `/api/preview` 与证据、TTFT/usage 路径 | AI 问答与问答试验为两个一级入口 | Rebuild UI | 合并为问答验证的 Q&A / 对照 / Monitoring |

## 结论

- 后端 V1.0.1 规则和审计存储可复用；本轮不重建 Pipeline、数据库或 Provider。
- 当前运行库含 40 条历史候选、0 条 Approved Golden；正式 Baseline、Sandbox、Recommendation、Release 必须如实显示 `Not Run` 或 `Not Qualified`。
- 发现 `/api/optimization` 原先固定返回 `not_run`，即使数据库已有 Experiment；本轮只补最近持久化实验的只读聚合，不改变任何实验或发布状态。
