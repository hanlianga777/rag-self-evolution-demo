# RAG Evolution 第二阶段实施计划

**目标：** 增加可审计的 DeepSeek 真实模式与本地证据检索，同时保留稳定的 Mock Demo。

**架构：** 后端读取被忽略的 `.env`，使用标准库 HTTP 调用 DeepSeek OpenAI-compatible Chat Completions；本地检索仅从种子文档返回证据。`AiService` 是页面 API 与 Provider 的唯一边界，任何失败返回显式 Mock fallback。

**技术栈：** Python 标准库、FastAPI、SQLite 种子数据、unittest、React/TypeScript。

**设计：** `docs/superpowers/specs/2026-09-04-rag-evolution-live-provider-design.md`

## 约束

- `DEEPSEEK_API_KEY` 只存在于本地 `.env`，不得打印、提交或传给前端。
- 默认模型为 `deepseek-v4-flash`，默认地址为 `https://api.deepseek.com`。
- 所有真实外部调用必须由 `probe`、`preview` 或 `live evaluation` 显式触发。
- API 无 Key/失败时必须可用，并返回 `mock` 而非伪造 `live`。

### 任务 1：配置、检索与 Provider 契约

**文件：** `backend/app/config.py`、`backend/app/retrieval.py`、`backend/app/providers.py`、`backend/tests/test_live_services.py`

- [ ] 写失败测试：本地检索将空调问题的报修流程排在首位；没有 Key 时 Provider 不发出 HTTP 请求；DeepSeek JSON Judge 响应可解析。
- [ ] 实现最小 `.env` 加载、证据检索和带超时的 Chat Completions Adapter。
- [ ] 运行 `PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v`。

### 任务 2：真实模式 API 与审计状态

**文件：** `backend/app/ai_service.py`、`backend/app/main.py`、`backend/app/services.py`、`backend/tests/test_api.py`

- [ ] 写失败测试：readiness 不泄露 Key；preview 无 Key 保持 Mock 契约；live evaluation 限制为 40 条。
- [ ] 实现 `AiService`、probe、preview 元数据与 live evaluation API。
- [ ] 运行完整后端套件并在配置 Key 后执行一次显式 probe。

### 任务 3：中文 UI 与交接材料

**文件：** `frontend/src/pages/SettingsPage.tsx`、`frontend/src/pages/EvaluationPage.tsx`、`frontend/src/types.ts`、`README.md`、`ARCHITECTURE.md`、`CODEX_HANDOFF.md`

- [ ] 写失败测试：显示映射呈现 LIVE / Mock 证据状态而不改动 API 原值。
- [ ] 增加 Provider probe、live evaluation 入口与中文可审计状态。
- [ ] 运行前端测试、生产构建和浏览器验收。

### 任务 4：发布验证

**文件：** 仅上述变更文件。

- [ ] 运行后端、前端、API smoke、显式 Provider probe 和浏览器主线。
- [ ] 确认 `.env` 与临时文件被忽略。
- [ ] 提交、推送 `origin/main`，确认本地/远端提交一致且工作树干净。
