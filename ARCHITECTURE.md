# 架构说明

## 运行时

React/Vite 展示工作区，FastAPI 负责数据边界，SQLite 保存种子 JSON 并提供轻量本地持久化边界。`start.sh` 不依赖 Docker，同时启动两个进程。

## 数据流

`SeedStore → FastAPI routes → frontend API client → 产品页面`

实验接口会创建内存中的重跑任务；轮询按耗时依次返回 `queued`、`running`、`evaluating`、`completed`。它不会改变生产配置，版本启用也只改变演示选择。

## Provider 边界

当前 API 通过 `AiService` 提供 readiness、显式 probe、真实 Preview 与 live evaluation。`DeepSeekProvider` 使用官方 OpenAI-compatible Chat Completions；`LocalRetriever` 只在本地种子文档中检索证据。UI 组件不得直接调用 Provider，且 API Key 永不返回给前端。

## 评测与推荐

基线评测覆盖全部 40 条黄金数据集记录。Candidate B 是满足条件的最优结果：质量、安全、延迟和 40/40 回归均通过，且没有新增回归。Candidate A 不满足延迟要求，Candidate C 不满足质量要求。
