# 项目上下文（当前 V1.1）

- **产品与受众：** RAG Evolution 是供 AI 解决方案工程师面试展示的评测驱动 RAG 自进化 Demo；唯一当前产品规则见 [SPEC V1.1](docs/RAG_SELF_EVOLUTION_SPEC.md)。
- **知识与运行时：** 四份机器人官方 PDF 经本地解析、Section-Aware Chunk、BGE Embedding 与 FAISS 建索引；检索按 CandidateK → Vector/BM25 Hybrid → 可选 Lightweight Rerank → MinScore → TopK Context 执行。回答、Golden QC、Judge 与 Agent 显式调用 DeepSeek；无 Provider 时不伪造结果。
- **Golden：** 当前只支持 Mini 8 Positive / 4 Ablation / 8 Negative。Candidate 经 Hard Validation、Probe ≥90、QC ≥85 和人工审核后才可进入不可变 Golden Snapshot；修订单题独立进行，关联由元数据表达。Preview 的重新生成沿用证据，重新选材并生成使用最新意图且仍须人工应用。历史 40 题和旧 V1 Run 不计入当前 KPI。
- **评测与优化：** 正式 Baseline 只读 Approved Snapshot；三组质量指标、11 项 Hard Gate、逐题 Bad Case 与 Regression 决定资格。Agent 基于真实 Bad Case 和冻结 Search Space 生成每轮 A/B/C；Sandbox 最多累计 12 次完整评测；多个 Pareto Frontier Candidate 需人工确定 Recommendation。
- **发布与反馈：** 合格候选由用户一次“确认发布”，服务端同事务记录 Human Release 与 Version Snapshot；保留人工 Rollback。Production QA 经人工判定后可形成 Trigger，只有 Human Confirm 后可进入下一轮优化。
- **当前数据边界：** 2026-09-26 只读基线为最近完整 Run 20 题（18 已批准、1 已拒绝、1 需修订），尚无正式 Golden Snapshot；实际数量以 SQLite/API 实时记录为准。`baseline-v1` 仅为初始配置，不是正式发布记录。项目不以 Seed、Mock 或 Fixture 冒充 Golden、评测、推荐或发布成果。
- **运行可靠性：** Generation 与质量重跑的线程在服务重启后不能自动继续；数据库保留阶段与审计并允许用户手动重试。单题 Revision 只展示实际阶段与耗时；隔离真实链路使用临时 SQLite，不写当前用户库。
