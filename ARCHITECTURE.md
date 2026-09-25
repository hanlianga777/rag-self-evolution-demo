# 架构说明

## 运行时

React/Vite 展示工作区，FastAPI 负责数据边界，SQLite 以增量 migration 保存治理、评测、实验与版本记录；旧 `demo_state` 保留但不再作为正式页面数据源。`start.sh` 不依赖 Docker，同时启动两个进程。

## 数据流

`Golden Draft → GovernanceStore → FastAPI routes → frontend API client → 产品页面`

Revision AI 在生成单题草案前先从当前文档、再从同产品文档确定真实 Chunk；人工指定材料优先，选材依据写入既有 Revision JSON 审计。Negative 只把材料作为生成上下文。此分支不改变主业务链，故现有 HTML 架构图及同源 PNG 无需重画。

Evaluation 固化 approved Question Snapshot、Production Config、Judge 元数据和逐题结果；后台线程只写 SQLite 运行记录。Optimization Agent 只能从真实 Bad Case 中生成 A/B/C，且只能使用 Tool Registry 的 available 参数。每个 Candidate 在 Baseline Snapshot 上独立回归；人工一次确认发布时服务端重新检查 Recommendation、Sandbox、Gate 与 Regression，之后生成 Production Version；回滚只切换保留版本。

## Provider 边界

当前 API 通过 `AiService` 提供 readiness、显式 probe 与真实 Preview；`DeepSeekProvider` 使用官方 OpenAI-compatible Chat Completions，并对 Evaluation Judge / Optimization Agent 强制结构化 JSON。UI 组件不得直接调用 Provider，且 API Key 永不返回给前端。

## 评测与推荐

正式评测只覆盖人工批准的 Golden Snapshot；历史 40 题为 Legacy，不计入当前 Mini。Overall 仅作可读指标，11 项 Hard Gate 与 Regression 独立判定；无真实运行时没有推荐结果。
