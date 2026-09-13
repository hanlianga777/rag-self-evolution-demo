# 变更记录

## 0.2.1 — 2026-09-13

- PDF Inspector 改用 API 原点的绝对 URL，避免前端 SPA 回退被错误嵌入为“PDF 原文”。
- `start_demo.command` 改为 Finder 可双击的本地后台启动入口；它不修改模型配置或 `.env`。

## 0.2.0 — 2026-09-13

- 新增本地 PDF OCR、章节/页内段落真实切片、BAAI/bge-small-zh-v1.5 向量与 FAISS IndexFlatIP 持久化索引。
- 移除人工 `samples` 作为问答语料的路径；无证据问题直接拒答，且不会调用 DeepSeek。
- 新增含页码、Chunk ID、相关度与原文预览的结构化 evidence；Document Inspector 支持 PDF、分块与索引信息三标签及页码定位。
- 索引产物、PDF 指纹与模型/OCR 缓存均保持本地，不提交 Git；评测/优化/A-B-C 回放维持 Demo 数据边界。

## 0.1.0 — 2026-09-04

- 初始化 RAG Evolution Mock Demo，呈现评测驱动的优化故事线。
- 新增 FastAPI/SQLite 种子 API、React SaaS UI、可重跑实验和文档。
- 新增 DeepSeek 真实 Provider、本地证据检索、显式连接验证与 live evaluation API；未配置或调用失败时明确回退 Mock。
- 加固真实/模拟边界：严格校验付费请求、拒绝不可信 Origin、禁止 fallback 被计为真实评测分数，并校验 Judge 输出。
- Demo Active 版本改为 SQLite 持久状态；前端逐次展示回答来源与回退原因，补齐中文数据边界、移动端导航、键盘详情与局部错误反馈。
