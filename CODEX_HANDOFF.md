# Codex 交接说明

执行 `./start.sh` 后打开 `http://127.0.0.1:5174`。后端数据事实源为 `backend/app/seed.py`；不要向 React 组件直接加入业务夹具。API 路由位于 `backend/app/main.py`，可变的演示行为位于 `backend/app/services.py`。

真实 Provider 边界位于 `backend/app/config.py`、`providers.py`、`retrieval.py` 与 `ai_service.py`。`.env` 与 `*.swp` 被忽略，绝不读取或提交 Key。设置页面的“验证 Provider 连接”会显式发起最小模型调用；提交前运行后端测试、前端测试和 `npm run build`。

`/api/preview` 与 `/api/evaluations/live` 仅在响应 `mode=live` 时代表有效模型回答；回退内容必须显示 Mock 与原因。Demo Active 保存于 SQLite 独立状态，启用后应通过 `/api/workspace`、`/api/versions` 和 `/api/overview` 一致回读。`/api/experiments/*` 始终是 `mode=mock`、`source=seeded_replay` 的演示回放，不代表真实实验。
