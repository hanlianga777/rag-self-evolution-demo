# RAG Evolution

> 由评测驱动的 RAG 优化平台

RAG Evolution 是一个面向机器人官方 PDF 知识问答的本地 Demo，提供「可追溯资料 → 人工复核数据集 → 基线评测 → 问题案例证据 → 受限 A/B/C 候选 → 独立 Sandbox 回归 → 人工发布/回滚」的可审计基础闭环。

## 业务与技术架构

![RAG Evolution 业务流程图](架构/业务流程图.png)

![RAG Evolution 技术架构图](架构/技术架构图.png)

完整的模块职责、数据流、状态生命周期、接口边界与能力范围见 [RAG Evolution 平台架构说明](架构/RAG自进化平台架构说明.md)。

## 与普通 RAG Demo 的区别

本项目不以单次回答“成功”作为结论；它把官方 PDF 证据、问题案例、候选配置、质量/延迟权衡和完整的已复核评测集放在同一个可审计闭环中展示。

## 已实现内容

- 保留 AI 问答、问答试验、概览、知识与数据集、评测、进化实验室和版本管理的既有导航。
- 4 份机器人官方 PDF 在本机经 PyMuPDF / RapidOCR 解析为 252 个真实分块，再以 BAAI/bge-small-zh-v1.5 和 FAISS IndexFlatIP 检索；文件、页码、Chunk ID 与分数可在 Document Inspector 追溯。
- SQLite 会一次性导入已审计的 40 道 Golden Dataset Candidate（32 Positive、8 Negative），全部初始为 `human_review_pending`；不会自动批准，也不会重写原始题目或证据。
- Probe 同时记录程序校验、向量信号与全文检索信号；人工批准后才可进入不可变 Dataset Snapshot 并触发正式 Baseline Evaluation。
- Evaluation、Bad Case、Optimization Agent、Candidate A/B/C 与 Production Version 仅记录真实手动动作；没有实际运行时页面显示 `Not Run`，不会再展示历史 Seed 指标。

## 真实模式与 Mock 边界

未配置 `DEEPSEEK_API_KEY` 时，系统仍可显示本地资料与治理状态，但不会模拟 Provider 回答、Judge 分数或正式评测结果。配置后可在设置页手动验证 DeepSeek Provider，预览接口会执行真实的本地证据检索与 DeepSeek 回答；接口会返回 `mode`、`model`、`latency_ms`、证据来源与 fallback 原因。服务启动和普通页面加载不会调用模型。

配置状态区分“已配置（未验证）”“已验证可用”和“不可用”。AI 问答与正式评测均使用当前 Production Baseline 的真实检索配置；没有真实 Sandbox Candidate 时，问答试验明确显示“暂无可比较候选”。模型只在人工发送、QC、评测或 Agent 生成动作时调用。

不上传原文件，但真实回答会把问题与相关知识片段发送给 DeepSeek；真实评测的 Judge 还会接收问题、预期回答与生成回答。验证连接仅发送固定测试消息。各手动触发点均显示相应提醒。

默认问答检索为本地 BGE 向量与 FAISS；固定 TopK=4。仅当相关度达到门槛时才将真实分块传给 Provider；否则返回“当前机器人知识库没有足够证据回答该问题”，不调用 DeepSeek，也不返回虚假引用。旧词元检索只保留为测试/调试兼容路径。

索引文件位于 `backend/data/index/`，包含 `faiss.index`、`chunks.json`、`documents.json` 与 PDF 指纹，均被 Git 忽略。`./start.sh` 仅在原始 PDF 或索引设置变化时运行 `python -m app.build_index --if-needed`；首次构建会下载本地 BGE 权重和 RapidOCR 运行依赖，原始 PDF 不会上传。原生浏览器 PDF Viewer 使用 API 原点的 `http://localhost:8010/documents/...pdf#page=N`，未引入 PDF.js，因此不会再加载前端 Demo 页面。

此处的 Sandbox 指候选配置的逻辑隔离，不是 Docker 或容器沙箱；它复用已完成 Baseline 的冻结数据集快照、保存独立逐题结果，并计算 Fix Rate、Regression、红线与延迟。尚未运行时显示 Not Run。

## 本地启动

前置条件：Python 3.10+、Node.js 20+、npm。

```bash
./start.sh
```

打开 [http://127.0.0.1:5174](http://127.0.0.1:5174)，FastAPI API 文档位于 [http://127.0.0.1:8010/docs](http://127.0.0.1:8010/docs)。

macOS 下可在 Finder 双击 `start_demo.command` 一次。它会登记登录启动项并打开上述网址；之后直接访问该网址即可，无需手动运行终端。登录启动项会以隐藏的 Terminal 上下文启动受保护 `Documents` 目录内的服务，服务随后脱离 Terminal 常驻。日志仅保存在本机 `.demo-logs/`，不修改 `.env`、模型设置或其他 Demo 的运行环境。

手动启动：

```bash
python3 -m pip install -r backend/requirements.txt
PYTHONPATH=backend python3 -m uvicorn app.main:app --port 8010
cd frontend && npm install && npm run dev
```

如需手工强制重建索引：

```bash
PYTHONPATH=backend python3 -m app.build_index --force
```

## 演示故事线

1. 在“候选题库”审核已审计题目，并按需运行 Probe。
2. 仅在至少一题已批准后，在“评测”手动运行真实 Baseline Evaluation。
3. 查看不可变 Snapshot、逐题结果、红线与真实 Bad Case。
4. 在“进化实验室”手动调用结构化 Optimization Agent；它只能提出 Tool Registry 中可用的 TopK / Min Score 配置。
5. 未运行、未配置或无法解析的外部能力都保留真实状态，不生成演示分数。

## DeepSeek 配置

将 `.env.example` 复制为 `.env` 并设置 `DEEPSEEK_API_KEY`。默认 `DEEPSEEK_BASE_URL=https://api.deepseek.com`、`DEEPSEEK_MODEL=deepseek-v4-flash`；绝不提交 `.env` 或编辑器临时文件。

## AutoRAG 参考范围

本项目仅将 AutoRAG `legacy/` 作为数据集、评测、流水线和实验概念的技术参考；不 fork、不打包、不复制其源代码。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 [DECISIONS.md](DECISIONS.md)。

## 路线图

后续将对真实语料新增、OCR 质量复核与实测评测执行建立独立的可审计流程。
