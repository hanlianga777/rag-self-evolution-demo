# Codex 交接说明

执行 `./start.sh` 后打开 `http://127.0.0.1:5174`。后端数据事实源为 `backend/app/seed.py`；不要向 React 组件直接加入业务夹具。API 路由位于 `backend/app/main.py`，可变的演示行为位于 `backend/app/services.py`。

变更 Provider 行为前，须在 README 和设置 UI 中保留 Mock/已实现/计划中的明确边界。提交前运行后端测试、前端测试和 `npm run build`。
