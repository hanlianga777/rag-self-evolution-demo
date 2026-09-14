# 决策记录

## 选择独立实现，而非 fork AutoRAG

AutoRAG 原始 Python RAG AutoML 能力位于 `legacy/`，而根项目已转向 AutoRAG 2.0。本 Demo 不将两者作为依赖：在真实运行时尚未落地前直接集成，会先引入过重的评测栈。`legacy/` 仅保留为文档化的概念参考。

## 单 Agent 与逻辑沙箱

UI 呈现的是一个具有工具化步骤的结构化 Optimization Agent，不是聊天记录或多 Agent 系统。Sandbox 指独立的候选配置快照和评测运行，不构成生产容器边界。

## Mock-first API

所有展示数据均经过 FastAPI API，因此 React UI 不持有业务夹具。后续可用真实 RAG、评审器和 Provider Adapter 替换确定性后端服务。

## 本地真实 PDF 检索

原始 PDF 保留在 `backend/documents/`。`app.build_index` 使用 PyMuPDF 读取页码、目录和正文短标题；无文字层时使用本地 RapidOCR。可靠章节内按连续段落切片（BGE `AutoTokenizer` 的真实 token，目标 400、同章节 60 overlap），没有可靠章节时明确使用页级/段落 fallback；切片不会跨文档或跨章节。每个分块保留厂商、产品、章节、起止页、真实 token 数、原文和 Embedding 状态，并以 BAAI/bge-small-zh-v1.5 归一化向量写入 FAISS IndexFlatIP。索引产物和模型权重均不提交 Git。没有通过解析/OCR 质量检查的 PDF 显示 `Needs OCR` / `Parse Failed`，不进入语料库。

问答默认使用该向量索引，固定 TopK=4，不设置相关度阈值或面向特定消费设备的关键词规则；没有可用索引或分块时不调用 Provider。每个引用携带文档、Chunk ID、章节、页码和分数，并由原生 PDF iframe 定位原文件页。
