# 变更记录

## 0.2.2 — 2026-09-14

- 真实 PDF 切片改为“章节 → 连续段落 → BGE tokenizer token 上限”；同章节可跨页，跨章节绝不合并。没有可靠目录或正文短标题的文件明确记录为页级/段落 fallback。
- 每个真实分块新增厂商、产品、章节、跨页范围、`chunk_text`、真实 token 数与 Embedding 状态；FAISS 写入成功后才标记为 `Indexed`。
- 默认检索固定为 BGE 归一化向量 + FAISS `IndexFlatIP` TopK=4；移除相关度阈值和消费电子关键词拦截，低分候选仍如实返回。
- Document Inspector 分块卡片展示章节、页码范围、Token Count、Chunk Text 与 Embedding Status，引用继续定位原始 PDF 的 `page_start`。

## 0.2.1 — 2026-09-13

- PDF Inspector 改用 API 原点的绝对 URL，避免前端 SPA 回退被错误嵌入为“PDF 原文”。
- `start_demo.command` 改为 Finder 可双击、登录后自动恢复的本地启动入口；它不修改模型配置或 `.env`。

## 0.2.0 — 2026-09-13

- 新增本地 PDF OCR、章节/页内段落真实切片、BAAI/bge-small-zh-v1.5 向量与 FAISS IndexFlatIP 持久化索引。
- 移除人工 `samples` 作为问答语料的路径；索引缺失或无可用分块时不会调用 DeepSeek。
- 新增含页码、Chunk ID、相关度与原文预览的结构化 evidence；Document Inspector 支持 PDF、分块与索引信息三标签及页码定位。
- 索引产物、PDF 指纹与模型/OCR 缓存均保持本地，不提交 Git；评测/优化/A-B-C 回放维持 Demo 数据边界。

## 0.1.0 — 2026-09-04

- 初始化 RAG Evolution Mock Demo，呈现评测驱动的优化故事线。
- 新增 FastAPI/SQLite 种子 API、React SaaS UI、可重跑实验和文档。
- 新增 DeepSeek 真实 Provider、本地证据检索、显式连接验证与 live evaluation API；未配置或调用失败时明确回退 Mock。
- 加固真实/模拟边界：严格校验付费请求、拒绝不可信 Origin、禁止 fallback 被计为真实评测分数，并校验 Judge 输出。
- Demo Active 版本改为 SQLite 持久状态；前端逐次展示回答来源与回退原因，补齐中文数据边界、移动端导航、键盘详情与局部错误反馈。
