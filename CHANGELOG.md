# 变更记录

## 0.1.0 — 2026-09-04

- 初始化 RAG Evolution Mock Demo，呈现评测驱动的优化故事线。
- 新增 FastAPI/SQLite 种子 API、React SaaS UI、可重跑实验和文档。
- 新增 DeepSeek 真实 Provider、本地证据检索、显式连接验证与 live evaluation API；未配置或调用失败时明确回退 Mock。
- 加固真实/模拟边界：严格校验付费请求、拒绝不可信 Origin、禁止 fallback 被计为真实评测分数，并校验 Judge 输出。
- Demo Active 版本改为 SQLite 持久状态；前端逐次展示回答来源与回退原因，补齐中文数据边界、移动端导航、键盘详情与局部错误反馈。
