# 项目上下文

- **产品：** RAG Evolution，评测驱动的 RAG 优化 Demo。
- **场景：** 商用清洁与工业巡检机器人官方 PDF 知识问答。
- **受众：** 企业 AI/RAG 运营人员与 AI 解决方案工程面试官。
- **当前阶段：** SQLite Golden Dataset Governance 与真实手动 Evaluation 基础已接入；PDF 经本地 OCR、BGE token 切片、BGE 向量和 FAISS 生成可追溯引用，DeepSeek 仅由人工动作显式调用。
- **数据边界：** 四份 PDF 与 252 个索引分块是真实资料链路；40 道候选题来自已审计报告但尚未自动批准。没有批准题、真实运行或真实 Candidate 时，产品显示 Not Run。
- **已实现边界：** Candidate / Golden 审核、Probe/QC、Snapshot、逐题 Evaluation、结构化 Judge、Bad Case、受限 Tool Registry、结构化 A/B/C Agent、候选独立 Sandbox、三道人审、发布与回滚。当前可执行 Sandbox 参数仅为 TopK 与 Min Score；Rerank、Rewrite、Hybrid 仍为 Unavailable。
- **非目标：** 生产部署、多 Agent 编排、Docker 和复杂基础设施。
