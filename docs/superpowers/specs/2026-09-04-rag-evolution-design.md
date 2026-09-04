# RAG Evolution 第一阶段设计

## 产品

RAG Evolution 是园区运营知识助手的评测驱动 RAG 优化 Demo。它演示一个可信的闭环：注入知识与黄金数据集、评测基线、查看 8 个问题案例、运行一个结构化 Optimization Agent、在逻辑沙箱中比较候选方案、重跑全部 40 道题、应用 SLA 闸门并推荐 Candidate B。

## 范围

第一阶段是桌面优先、可运行的 Demo，而不是生产 RAG 部署。UI 包含概览、知识与数据集、评测、进化实验室、版本管理、设置和预览对比弹窗，并使用一致的种子事实与 FastAPI Mock API。

## 架构

React 仅负责呈现与交互。FastAPI 负责种子读模型、实验重跑状态、版本启用、预览回答和 readiness。SQLite 是本地持久化边界。Provider Adapter 表示 RAG Answer、LLM Judge 和优化器角色；在后续配置环境变量前始终报告 Mock mode。

## 决策

- 独立仓库：AutoRAG `legacy/` 仅作参考，不复制源代码，也不安装依赖。
- 单一 Optimization Agent：不作多 Agent 声称。
- 逻辑沙箱：候选配置快照独立运行，不使用 Docker。
- 历史完成结果 + 现场重跑：概览可用于演示，进化实验室可直观看到 A/B/C 重跑。
- Candidate B 只在完整 40/40 回归，以及质量、安全、延迟和回归闸门全部通过后被推荐。
