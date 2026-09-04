# RAG Evolution 第二阶段真实 Provider 设计

## 目标

在不改变既有页面、Mock 演示闭环或 API 枚举的前提下，让 RAG Evolution 能在配置 `DEEPSEEK_API_KEY` 后执行真实的基于证据的回答、可审计 Provider probe 和真实 LLM Judge 评分。

## 边界

- 仍然使用本地园区文档作为语料来源，不上传文档或 API Key 到 Git。
- 检索采用 Python 标准库实现的中文字符/词元重叠评分；这是可运行的本地检索基线，不宣称为向量检索。
- DeepSeek 调用仅发生在显式的 preview、probe 或 live evaluation API 请求中；服务启动与普通页面加载不会调用外部模型。
- 缺少 Key、网络错误、超时或无有效模型结果时，接口返回明确的 Mock fallback 与原因，不伪称为 LIVE。
- 保持 `POST /api/preview` 兼容；在响应中新增 `mode`、`model`、`latency_ms`、`fallback_reason` 和检索来源。

## 组件与数据流

`LocalRetriever` 从 `SeedStore.documents` 的 sample chunks 中返回带分数的证据。`DeepSeekProvider` 使用官方 OpenAI-compatible `POST /chat/completions` 接口：回答调用发送问题与证据；Judge 调用要求 JSON 输出 `{score, rationale}`。`AiService` 统一选择 LIVE 或 Mock fallback，并记录最后一次 probe 的脱敏审计信息。

## API

- `GET /api/readiness`：返回配置状态、当前模型和最后 probe 的脱敏状态，绝不返回 Key。
- `POST /api/ai-readiness/probe`：显式最小调用，验证 Provider 与模型可用性。
- `POST /api/preview`：保留当前字段，新增真实模式元数据与本地检索来源。
- `POST /api/evaluations/live`：对最多 40 条黄金数据集记录运行真实回答与 Judge，返回完成数、平均分、延迟、模式与失败数；不会覆盖历史基线。

## 验证

- 单元测试覆盖 `.env` 加载优先级、检索证据排序、无 Key fallback、Provider JSON 解析与 probe 审计。
- API 测试覆盖 readiness、preview Mock 契约和 live evaluation 上限。
- 配置 Key 后，使用显式 probe 验证 provider/model/source，并在 README 和设置页显示 LIVE 或 Mock 证据。
