# Codex 交接说明（当前 V1.1）

开始任何业务改动前先读 [唯一当前产品 SPEC](docs/RAG_SELF_EVOLUTION_SPEC.md)。ChangeLog、旧实施计划和 Seed 只用于历史追溯，不能创造第二套当前规则，也不能冒充真实结果。

执行 `./start.sh` 后打开 `http://127.0.0.1:5174`。真实 PDF 在 `backend/documents/`；索引由 `backend/app/build_index.py` 构建，运行时由 `backend/app/corpus.py` 与 `backend/app/retrieval.py` 读取。Backend 是 FastAPI + SQLite，前端是 React/TypeScript/Vite。检索已实现 Vector/BM25 Hybrid、Query Rewrite、MultiQuery、HyDE、Metadata Filter、Alias Mapping 和轻量二阶段重排；没有独立 Rerank Model。`/api/experiments/*` 使用持久化实验与真实 Sandbox，不是旧文档所述的 seeded replay。

正式链路：Mini Golden → Probe/QC → Human Review → Snapshot → Baseline → Bad Case → Agent A/B/C → Sandbox/Regression → Recommendation → 单次 Human Release → Production/Monitoring。当前用户库最近 Run 为 16/20 批准、4 需修订，尚无正式 Snapshot；不要为测试自动修改 Candidate、应用 Preview、人工批准或发布。`baseline-v1` 是 Bootstrap 配置，不是正式发布成果。`seed.py` 只能用于隔离开发/历史展示。

Provider 配置在 `.env`，绝不读取或提交密钥。设置页“验证 Provider”会发起最小模型调用；无 Provider 时展示真实不可用状态。真实模型 Smoke 必须用隔离数据库，确定性 E2E 必须用临时 SQLite 与 Fixture。

Revision Preview 的“重新生成”沿用当前材料；“重新选材并生成”按最新原因／标签重新执行选材，失败时保留未应用草案。**No Pseudo Interaction：** 视觉上可点击的按钮、关闭、展开、菜单、标签和下拉必须有真实状态变化，并在浏览器中可点击；关键交互须有 Interaction Test。Modal 打开时也要检查浮层的指针与焦点交互。

**Impact Check 硬规则：** 修改业务逻辑、页面流程、状态机、API、数据字段、Retrieval、Evaluation、Agent、Release 或 Monitoring 时，逐项检查 SPEC、SPEC ChangeLog、README、PROJECT_CONTEXT、CODEX_HANDOFF、DECISIONS、TODO、架构说明、两张架构图、后端测试、前端测试、E2E 与当前 Demo；记录需更新项和无需更新的理由。禁止只改代码不改文档，也禁止只改 SPEC 不改实现。

交付前运行后端全量测试、前端 Vitest、生产构建、五条业务 E2E、Fresh/Existing DB 验证、HTTP/UI smoke 和 `git diff --check`；推送后确认 `HEAD == origin/main` 与干净工作树。
