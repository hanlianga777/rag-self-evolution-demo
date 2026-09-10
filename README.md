# RAG Evolution

> 由评测驱动的 RAG 优化平台

RAG Evolution 是一个面向机器人官方 PDF 知识问答的本地可演示 Demo，完整呈现「可追溯资料 → 已复核评测集 → 基线评测 → 问题案例证据 → 结构化优化诊断 → A/B/C 沙箱实验 → 全量回归 → SLA 闸门推荐」闭环。

## 业务与技术架构

![RAG Evolution 业务流程图](架构/业务流程图.png)

![RAG Evolution 技术架构图](架构/技术架构图.png)

完整的模块职责、数据流、状态生命周期、接口边界与能力范围见 [RAG Evolution 平台架构说明](架构/RAG自进化平台架构说明.md)。

## 与普通 RAG Demo 的区别

本项目不以单次回答“成功”作为结论；它把官方 PDF 证据、问题案例、候选配置、质量/延迟权衡和完整的已复核评测集放在同一个可审计闭环中展示。

## 已实现内容

- 五个核心页面：概览、知识与数据集、评测、进化实验室、版本管理，以及设置和优化前后预览。
- 基于 FastAPI Mock API 与 SQLite 统一种子数据：当前 4 份已核验的机器人官方 PDF（卡赫 KIRA B 50 与宇树 B2 系列）、10 个证据片段、8 道已复核评测问题、4 个问题案例，以及预置 A/B/C 实验结果；页面文档数以接口列表为准。
- 可现场运行模拟重放，依次呈现排队、运行、评测和完成状态；进度和结果来自预置演示数据，不是本次 Live 实验。
- 只有完整 8/8 回归通过、质量/安全/延迟 SLA 均通过且无新增回归时，才推荐 Candidate B。

## 真实模式与 Mock 边界

未配置 `DEEPSEEK_API_KEY` 时，系统为 **演示模拟模式**。配置后可在设置页手动验证 DeepSeek Provider，预览接口会执行真实的本地证据检索与 DeepSeek 回答；接口会返回 `mode`、`model`、`latency_ms`、证据来源与 fallback 原因。服务启动和普通页面加载不会调用模型。

配置状态区分“已配置（未验证）”“已验证可用”和“不可用”。打开预览不会自动请求，需点击“对比版本”；每次响应均显示实际 Live/Mock 来源、模型、延迟和回退原因，基线始终是模拟样例。失败时清除旧结果并允许重试。

不上传原文件，但真实回答会把问题与相关知识片段发送给 DeepSeek；真实评测的 Judge 还会接收问题、预期回答与生成回答。验证连接仅发送固定测试消息。各手动触发点均显示相应提醒。

本地检索是透明的中文字符/词元重叠基线，不宣称为向量检索；LLM Judge 与最多 40 条的 live evaluation API 已预留为显式触发能力。系统不进行生产部署。

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

1. 在概览查看基线 72.4、4 个机器人问题案例和进化流程。
2. 打开评测，选择“B2 遥控器低电量时如何充电？”，查看官方 PDF 检索证据。
3. 点击“优化本次运行”，审阅单 Agent 的结构化诊断和候选方案。
4. 点击“运行模拟重放”，观察沙箱演示进度与预置指标。
5. 确认 Candidate B 仅在 8/8 回归和所有 SLA 闸门通过后被推荐。
6. 打开预览，阅读发送边界后点击“对比版本”，结合单次 Live/Mock 标识比较回答。

## DeepSeek 配置

将 `.env.example` 复制为 `.env` 并设置 `DEEPSEEK_API_KEY`。默认 `DEEPSEEK_BASE_URL=https://api.deepseek.com`、`DEEPSEEK_MODEL=deepseek-v4-flash`；绝不提交 `.env` 或编辑器临时文件。

## AutoRAG 参考范围

本项目仅将 AutoRAG `legacy/` 作为数据集、评测、流水线和实验概念的技术参考；不 fork、不打包、不复制其源代码。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 [DECISIONS.md](DECISIONS.md)。

## 路线图

在保持既有 API/UI 契约的前提下，后续接入真实语料库与索引、RAG 运行时、Provider Adapter 和实测评测执行。
