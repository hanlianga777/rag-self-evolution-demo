# Codex 交接说明

执行 `./start.sh` 后打开 `http://127.0.0.1:5174`。真实 PDF 事实源为 `backend/documents/`，索引构建位于 `backend/app/build_index.py`，运行时读取位于 `backend/app/corpus.py` 与 `backend/app/retrieval.py`；不要向 React 组件或 `seed.py` 写入人工语料。`seed.py` 仅保存评测/优化 Demo 数据，API 路由位于 `backend/app/main.py`。

真实 Provider 边界位于 `backend/app/config.py`、`providers.py`、`retrieval.py` 与 `ai_service.py`。索引在 `backend/data/index/`，被 Git 忽略；启动脚本仅在 PDF 指纹变化时重建。`.env` 与 `*.swp` 被忽略，绝不读取或提交 Key。设置页面的“验证 Provider 连接”会显式发起最小模型调用；提交前运行后端测试、前端测试和 `npm run build`。

`/api/preview` 会始终返回结构化 evidence；若没有真实命中，它会拒答且 evidence 为空，不会调用 Provider。每个命中可由前端以 `/documents/...pdf#page=N` 打开原生 PDF。`/api/evaluations/live` 仅在响应 `mode=live` 时代表有效模型回答；Demo Active 保存于 SQLite 独立状态，`/api/experiments/*` 始终是 `mode=mock`、`source=seeded_replay` 的演示回放，不代表真实实验。
