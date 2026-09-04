# RAG Evolution 第一阶段实施计划

**目标：** 构建本地可运行、可公开展示的 RAG 评测与自进化 Demo，提供完整可点击的 Mock 工作流。

**架构：** React SPA 展示产品 UI 并调用 FastAPI API。由 Python/SQLite 支撑的种子仓库管理所有演示事实与实验状态；API 提供稳定读模型并驱动实验重跑状态机。真实 Provider 工作保留在后端 Adapter 后，Mock mode 不需要调用真实服务。

**技术栈：** React、TypeScript、Vite、Tailwind CSS、shadcn 风格原语、Lucide、Recharts、FastAPI、SQLite、Python stdlib unittest。

**设计说明：** `docs/superpowers/specs/2026-09-04-rag-evolution-design.md`

## 全局约束

- 桌面优先的浅色 SaaS 界面，目标视口为 1440×900，1280×720 仍可使用。
- 不使用 Docker、Redis、Kafka、微服务、真实 DeepSeek 调用、AutoRAG 依赖，也不将密钥提交到 Git。
- Mock mode 的所有数据必须经过 FastAPI API，不允许分散在 React 组件中的业务夹具。
- Sandbox 指逻辑配置隔离，不代表容器隔离。
- 仅使用一个具有工具化步骤的 Optimization Agent。

## 任务 1：仓库基础与后端数据契约

**文件：** `.gitignore`、`.env.example`、`backend/app/main.py`、`backend/app/seed.py`、`backend/tests/test_api.py`

**接口：** `GET /api/overview`、`/api/documents`、`/api/dataset`、`/api/evaluation`、`/api/bad-cases`、`/api/optimization`、`/api/versions`、`/api/readiness`。

- 定义种子一致性与 Candidate B 推荐的失败测试。
- 实现 SQLite 种子仓库与 FastAPI 读取路由。
- 运行 `PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v`。

## 任务 2：实验、版本与预览写操作

**接口：** `POST /api/experiments/run`、`GET /api/experiments/{id}`、`POST /api/versions/{id}/activate`、`POST /api/preview`。

- 添加重跑、状态读取、版本启用与空调问题预览的失败测试。
- 实现最小的基于时间的重跑服务与逻辑 SLA 闸门。
- 重新运行后端测试。

## 任务 3：React 外壳与 API 客户端

- 建立 TypeScript strict 与 Tailwind 兼容的构建配置。
- 实现侧栏、工作区头部、Mock mode 徽标、预览入口、路由状态与请求客户端。
- 在 `frontend/` 中运行 `npm run build`。

## 任务 4：产品页面与交互闭环

- 实现概览 KPI/流程/图表/运行记录，文档与数据集 Tab 及文档详情。
- 实现评测指标、筛选、问题案例 Drawer 与“优化本次运行”导航。
- 实现 Agent 时间线、A/B/C 卡片、实验轮询、结果/SLA/回归状态、版本差异/启用和优化前后预览。
- 重新运行前端生产构建。

## 任务 5：运维与交接材料

- 编写启动、演示流程、Mock 与后续能力边界、AutoRAG 参考范围和逻辑沙箱限制。
- 验证一键启动、API 冒烟、浏览器故事线、响应式布局和干净的浏览器 Console。
- 初始化 Git、提交变更；在认证可用时创建并推送 `hanlianga777/rag-self-evolution-demo`，确认同步。
