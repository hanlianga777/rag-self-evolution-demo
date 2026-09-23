# RAG Evolution

> 机器人官方 PDF 知识问答的可审计 RAG 自进化 Demo。

## Current Project Stage

- **Target Source of Truth:** [RAG Self-Evolution SPEC](docs/RAG_SELF_EVOLUTION_SPEC.md)（`V1.0.1 — Final Closure Patch`）；变更历史见 [SPEC ChangeLog](docs/SPEC_CHANGELOG.md)。
- **Current Implementation ≠ Target Production Acceptance:** V1.0.1 的治理与运行链路已实现并受自动化测试覆盖；没有人工批准的 Positive / Ablation / Negative Golden Snapshot 时，正式 Baseline、Sandbox、Recommendation 与 Release 仍为 `Not Run / Not Qualified`。
- **No fabricated results:** 40 条历史 Candidate 和任何 Demo Seed 不代表已验证 Golden、评测分数、推荐或发布结果。

## 已实现的真实闭环

`PDF / Chunk → Mini Golden Candidate 8/4/8 → Hard Validation → Probe 30/30/40 → QC ≥85 → Human Review → Golden Snapshot → Baseline → Bad Case → A/B/C → Sandbox → 11 Gate + Regression → Recommendation → Human Release → Version / Rollback`

- SQLite 兼容迁移保存 Coverage / Question Plan、Golden、Probe/QC、评测逐题证据、Gate、Regression、Candidate、Recommendation、Monitoring Trigger、版本快照与审计记录，不删除历史数据库。
- 检索实际按 `CandidateK → Vector/BM25 normalized Hybrid → optional Rerank → MinScore → TopK Context` 执行；所有 Candidate 配置受 V1.0.1 Search Space、依赖、去重和单轮 `max_evals=12` 限制。
- Production 问答先记录为待人工判定的 Monitoring Event；人工标记 Bad Case 后，系统在一个 Safety Critical Bad Case 或最近 20 个有效记录中至少 4 个 Bad Case 时创建 Pending Trigger。流程固定为 `Monitoring → Trigger → Human Confirm → Optimization Run`，不会自动调参或发布。
- 多个 Qualified Candidate 使用透明 Pareto 比较；存在质量、速度、成本等真实取舍时交由 Human Release 决策，Overall Score 仍仅作展示。
- DeepSeek 不可用时，页面显示明确状态，不生成模拟回答、分数、推荐或发布记录。可用时记录流式 TTFT、Token Usage；Provider 未返回成本时显示 `Token Usage / Provider Cost unavailable`。

## 架构

![RAG Evolution 业务流程图](架构/业务流程图.png)

![RAG Evolution 技术架构图](架构/技术架构图.png)

可编辑图源：[业务流程图 HTML](架构/业务流程图.html) · [技术架构图 HTML](架构/技术架构图.html)。详细模块边界见 [平台架构说明](架构/RAG自进化平台架构说明.md)。

## 本地启动

前置条件：Python 3.10+、Node.js 20+、npm。

```bash
./start.sh
```

打开 [http://127.0.0.1:5174](http://127.0.0.1:5174)，API 文档位于 [http://127.0.0.1:8010/docs](http://127.0.0.1:8010/docs)。

手动启动：

```bash
python3 -m pip install -r backend/requirements.txt
PYTHONPATH=backend python3 -m uvicorn app.main:app --port 8010
cd frontend && npm install && npm run dev
```

将 `.env.example` 复制为 `.env` 并设置 `DEEPSEEK_API_KEY` 后，才可执行真实 Golden Generation、QC、回答、Judge、评测与 Agent。原始 PDF 不上传；显式运行回答、QC、评测或 Agent 时，相关 Chunk 会发送给 DeepSeek。
