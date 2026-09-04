# RAG Evolution

> 由评测驱动的 RAG 优化平台

RAG Evolution 是一个面向园区运营知识助手的本地可演示 Demo，完整呈现「知识与黄金数据集 → 基线评测 → 问题案例证据 → 结构化优化诊断 → A/B/C 沙箱实验 → 全量回归 → SLA 闸门推荐」闭环。

## 与普通 RAG Demo 的区别

本项目不以单次回答“成功”作为结论；它把评测证据、问题案例、候选配置、质量/延迟权衡和完整的 40 题回归放在同一个可审计闭环中展示。

## 已实现内容

- 五个核心页面：概览、知识与数据集、评测、进化实验室、版本管理，以及设置和优化前后预览。
- 基于 FastAPI Mock API 与 SQLite 统一种子数据：12 份文档、438 个分块、40 道黄金数据集问题、8 个问题案例，以及一致的 A/B/C 实验结果。
- 可现场重跑的逻辑隔离实验，依次呈现排队、运行、评测和完成状态。
- 只有完整 40/40 回归通过、质量/安全/延迟 SLA 均通过且无新增回归时，才推荐 Candidate B。

## Mock 与后续真实能力的边界

当前阶段为 **演示模拟模式**：不会调用 DeepSeek，不执行真实 RAG 检索或 LLM Judge，也不进行生产部署。后端 API 和 Provider 边界已经预留，可在后续用真实服务替换确定性夹具。

此处的 Sandbox 指候选配置的逻辑隔离与独立评测，不是 Docker 或容器沙箱。

## 本地启动

前置条件：Python 3.10+、Node.js 20+、npm。

```bash
./start.sh
```

打开 [http://127.0.0.1:5174](http://127.0.0.1:5174)，FastAPI API 文档位于 [http://127.0.0.1:8010/docs](http://127.0.0.1:8010/docs)。

手动启动：

```bash
python3 -m pip install -r backend/requirements.txt
PYTHONPATH=backend python3 -m uvicorn app.main:app --port 8010
cd frontend && npm install && npm run dev
```

## 演示故事线

1. 在概览查看基线 72.4、8 个问题案例和进化流程。
2. 打开评测，选择“我工位空调坏了咋整？”，查看检索证据。
3. 点击“优化本次运行”，审阅单 Agent 的结构化诊断和候选方案。
4. 点击“运行实验”，观察沙箱重跑。
5. 确认 Candidate B 仅在 40/40 回归和所有 SLA 闸门通过后被推荐。
6. 打开预览，比较基线拒答与 Candidate B 的有依据回答。

## 可选的 DeepSeek 配置

只有在明确实施真实 Provider 集成时，才将 `.env.example` 复制为 `.env` 并设置 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`。绝不提交 `.env`。

## AutoRAG 参考范围

本项目仅将 AutoRAG `legacy/` 作为数据集、评测、流水线和实验概念的技术参考；不 fork、不打包、不复制其源代码。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 [DECISIONS.md](DECISIONS.md)。

## 路线图

在保持既有 API/UI 契约的前提下，后续接入真实语料库与索引、RAG 运行时、Provider Adapter 和实测评测执行。
