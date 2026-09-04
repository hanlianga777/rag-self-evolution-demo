# 决策记录

## 选择独立实现，而非 fork AutoRAG

AutoRAG 原始 Python RAG AutoML 能力位于 `legacy/`，而根项目已转向 AutoRAG 2.0。本 Demo 不将两者作为依赖：在真实运行时尚未落地前直接集成，会先引入过重的评测栈。`legacy/` 仅保留为文档化的概念参考。

## 单 Agent 与逻辑沙箱

UI 呈现的是一个具有工具化步骤的结构化 Optimization Agent，不是聊天记录或多 Agent 系统。Sandbox 指独立的候选配置快照和评测运行，不构成生产容器边界。

## Mock-first API

所有展示数据均经过 FastAPI API，因此 React UI 不持有业务夹具。后续可用真实 RAG、评审器和 Provider Adapter 替换确定性后端服务。
