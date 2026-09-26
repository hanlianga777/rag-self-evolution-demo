# RAG Evolution

> 机器人官方 PDF 知识问答的可审计 RAG 自进化 Demo。

## Current Project Stage

- **唯一当前产品规则：** [RAG Self-Evolution SPEC V1.2](docs/RAG_SELF_EVOLUTION_SPEC.md)；[SPEC ChangeLog](docs/SPEC_CHANGELOG.md) 只记录历史。运行状态仍以 SQLite 审计和 API 为准。
- **当前真实状态：** 以当前完整 Run 的活动题目及 API 为准；旧 Run、已替换题和 Legacy 不混入当前统计。实施与验收不代用户审核、应用 Preview 或发布。
- **No fabricated results:** 40 条历史 Candidate 和任何 Demo Seed 不代表已验证 Golden、评测分数、推荐或发布结果。

## V1.2 主线

`知识入库 → Golden 8/4/8 → Gate 1 人工确认并冻结 → Baseline → Bad Case → Tuning Agent A/B/C Sandbox → Gate 2 报告确认并选赢家 → Composite D 决策与复验 → Gate 3 人工发布 → 问答`

只有 Tuning 是 Agent；Generation、QC、Evaluation 是受控工作流。动态文档清单、Embedding 主题配额不依赖四份示例 PDF。Positive/Ablation 检索未命中记为 P1；QC 按 P0/P1/P2 给理由，分数辅助展示。机器 P0 可明确接受并说明，确定性错误与 Fake Negative 不能豁免。Ablation 独立治理。

- SQLite 兼容迁移保存 Coverage / Question Plan、Golden、Probe/QC、评测逐题证据、Gate、Regression、Candidate、Recommendation、Monitoring Trigger、版本快照与审计记录，不删除历史数据库。
- 检索实际按 `CandidateK → Vector/BM25 normalized Hybrid → optional Lightweight Rerank → MinScore → TopK Context → DeepSeek` 执行；当前重排并非独立 Rerank Model。所有配置受冻结 Search Space、依赖和去重约束；A/B/C/D 共用 12 次预算，启动即占用（失败不退），为 D 保留一次。
- Production 问答先记录为待人工判定的 Monitoring Event；人工标记 Bad Case 后，系统在一个 Safety Critical Bad Case 或最近 20 个有效记录中至少 4 个 Bad Case 时创建 Pending Trigger。流程固定为 `Monitoring → Trigger → Human Confirm → Optimization Run`，不会自动调参或发布。
- Gate 2 在已启动评测全部终结后确认报告并选合格赢家。D 只合并有实测修复、Regression 通过的配置差异，冲突保留赢家；新组合完整重评且比赢家无新增失败、有实际修复才替代。无有效组合不虚构 D。Overall Score 不能替代 11 Gate。Monitoring、Version History 和 Rollback 是辅助能力。
- `baseline-v1` 是启动用 Pipeline Bootstrap 配置，不是经过 Sandbox 与人工发布的 Production Version。旧 `seed.py` 只用于历史/开发数据，不进入当前 V1 主流程。
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
DeepSeek 单次请求默认超时 60 秒，可用 `DEEPSEEK_TIMEOUT_SECONDS` 调整；Revision 生成和质量检查遇明确超时仅自动重试一次，应用后的质量运行失败可从已持久化的 Probe/QC 状态手动继续，不会重新应用草案。
Revision Preview 中“重新生成”保留当前证据；“重新选材并生成”使用最新修订原因重新选择同产品真实材料。两者都不会自动应用 Candidate 或批准 Golden。
答案锚点失败时，修订界面根据当前意图推荐沿用证据重写或重新选材；无可靠材料会要求修改意图或手选真实 Chunk。单题运行只显示阶段和耗时，不展示估算百分比。服务重启会将失去 Worker 的 Generation / Probe-QC 重跑标为失败并保留审计，后续重试需由用户手动发起。隔离验收可在启动 API 前设置 `RAG_DEMO_DB_PATH` 指向临时 SQLite；默认仍为 `backend/data/demo.db`。
