# Codex 交接说明（当前 V1.3）

当前状态（2026-09-30）：见 [Current Demo Truth](docs/CURRENT_DEMO_TRUTH.md) 与 [Phase 1 验收](docs/PHASE1_VERIFICATION.md)。本轮规则与历史边界如下。

## Phase 1 交接（2026-09-30）

依旧使用 ponytail full；保留技术栈和八个导航。新导入 API：`GET /api/governance/import-template`、`POST /api/governance/imports?filename=...&confirm=false|true`（raw body）、`POST /api/governance/generation-runs/from-pool`。新题副本重新治理；现有质量/审核接口复用。

开发前备份，写入测试仅隔离 DB。`scripts/verify_phase1_data.py` 校验原字段与索引指纹；唯一允许迁移 `monitoring_events.metrics_json`。不要重新执行真实 Golden/Baseline/A–D/Gate/Release。历史指标缺失保持未采集。QA 恢复不是执行授权。


当前主链：Golden Mini／Medium／Full → Gate 1 确认并冻结 → Baseline 报告／门禁／逐题诊断 → Tuning A/B/C Sandbox → Gate 2 报告确认并选择赢家 → D 决策／复验 → Gate 3 发布 → 问答试验。只有 Tuning 是 Agent。不得使用旧 numeric Probe/QC、强制 Ablation 配对或 Direct Release 豁免。真实库数量以 API 为准；本轮验收只写隔离库。

开始任何业务改动前先读 [唯一当前产品 SPEC](docs/RAG_SELF_EVOLUTION_SPEC.md)。ChangeLog、旧实施计划和 Seed 只用于历史追溯，不能创造第二套当前规则，也不能冒充真实结果。

执行 `./start.sh` 后打开 `http://127.0.0.1:5174`。真实 PDF 在 `backend/documents/`；索引由 `backend/app/build_index.py` 构建，运行时由 `backend/app/corpus.py` 与 `backend/app/retrieval.py` 读取。Backend 是 FastAPI + SQLite，前端是 React/TypeScript/Vite。检索已实现 Vector/BM25 Hybrid、Query Rewrite、MultiQuery、HyDE、Metadata Filter、Alias Mapping 和轻量二阶段重排；没有独立 Rerank Model。`/api/experiments/*` 使用持久化实验与真实 Sandbox，不是旧文档所述的 seeded replay。

当前 UI 按七阶段 Lifecycle 组织八个现有 Hash 工作区。Pipeline/Search Space 使用只读 `/api/pipeline`；Before / After 使用已持久化方案 ID 的 `/api/preview/scheme`，发布后默认上一保存配置对当前 Production；Bootstrap 初始配置标为 Baseline。`Use Fixed Bad Case` 读取当前 Baseline Bad Case 和已保存逐题 Evaluation；“运行实时对比”才调用 Provider。前端改动部署后需重启 API 才有新增接口。验收时不要点击生成、Sandbox 或发布。

历史 V1.1 链路（Superseded by V1.3，不用于当前判定）：Mini Golden → Probe/QC → Human Review → Snapshot → Baseline → Bad Case → Agent A/B/C → Sandbox/Regression → Recommendation → 单次 Human Release → Production/Monitoring。2026-09-26 只读基线为最近 Run 18/20 批准、1 拒绝、1 需修订，尚无正式 Snapshot；执行前重新读取当前状态。不要为测试自动修改用户 Candidate、应用 Preview、人工批准或发布。`baseline-v1` 是 Bootstrap 配置，不是正式发布成果。`seed.py` 只能用于隔离开发/历史展示。

Provider 配置在 `.env`，绝不打印或提交密钥。设置页“验证 Provider”会发起最小模型调用；无 Provider 时展示真实不可用状态。Fixture E2E 与使用真实 Provider/索引的隔离生命周期必须分层报告。隔离 API 启动前用 `RAG_DEMO_DB_PATH` 指向临时 SQLite，避免导入时的数据库初始化触碰用户库。

Revision Preview 的“重新生成”沿用当前材料；“重新选材并生成”按最新原因／标签重新执行选材，失败时保留未应用草案。**No Pseudo Interaction：** 视觉上可点击的按钮、关闭、展开、菜单、标签和下拉必须有真实状态变化，并在浏览器中可点击；关键交互须有 Interaction Test。Modal 打开时也要检查浮层的指针与焦点交互。

答案锚点失败不绕过 Hard Validation；按意图推荐恢复动作，无可靠材料即停止。单题 Revision 不显示固定阶段百分比；服务重启后失去 Worker 的 Generation / 质量重跑应保留原审计并由用户手动重试。

**Impact Check 硬规则：** 修改业务逻辑、页面流程、状态机、API、数据字段、Retrieval、Evaluation、Agent、Release 或 Monitoring 时，逐项检查 SPEC、SPEC ChangeLog、README、PROJECT_CONTEXT、CODEX_HANDOFF、DECISIONS、TODO、架构说明、两张架构图、后端测试、前端测试、E2E 与当前 Demo；记录需更新项和无需更新的理由。禁止只改代码不改文档，也禁止只改 SPEC 不改实现。

交付前运行后端全量测试、前端 Vitest、生产构建、五条业务 E2E、Fresh/Existing DB 验证、HTTP/UI smoke 和 `git diff --check`；推送后确认 `HEAD == origin/main` 与干净工作树。
