# 架构说明

## 运行时

React/Vite 展示工作区，FastAPI 负责数据边界，SQLite 以增量 migration 保存治理、评测、实验与版本记录；旧 `demo_state` 保留但不再作为正式页面数据源。`start.sh` 不依赖 Docker，同时启动两个进程。

## 数据流

`Golden Draft → GovernanceStore → FastAPI routes → frontend API client → 产品页面`

Evaluation 固化 approved Question Snapshot、Production Config、Judge 元数据和逐题结果；后台线程只写 SQLite 运行记录。Optimization Agent 只能从真实 Bad Case 中生成 A/B/C，且只能使用 Tool Registry 的 available 参数。每个 Candidate 在 Baseline Snapshot 上独立回归，直到 Candidate Approval 与 Release Approval 都通过才会生成 Production Version；回滚只切换保留版本。

## Provider 边界

当前 API 通过 `AiService` 提供 readiness、显式 probe 与真实 Preview；`DeepSeekProvider` 使用官方 OpenAI-compatible Chat Completions，并对 Evaluation Judge / Optimization Agent 强制结构化 JSON。UI 组件不得直接调用 Provider，且 API Key 永不返回给前端。

## 评测与推荐

正式评测只覆盖人工批准的 Golden Question；初始 40 题均为 Pending Review。Overall 使用 Draft Scoring Policy（Correctness 35%、Completeness 25%、Faithfulness 30%、Behavior/Safety 10%），红线独立于总分；无真实运行时没有推荐结果。
