# 待办（V1.4 目标 / Phase 1 历史记录）

> **2026-09-30 文档同步边界：** 唯一当前目标规格为 [SPEC V1.4](docs/RAG_SELF_EVOLUTION_SPEC.md)，两张架构图已按最新设计重绘为目标架构。本次没有业务代码、数据库或索引升级，没有 Provider 或发布重跑；下方 Phase 1 / V1.3 内容保留为现有实现及历史证据，不能表示 V1.4 全部已完成。需求状态和未决项以 SPEC 第 3–4 节为准。

V1.4 的 P0-01–04、GV2-01–05、COST-01、UI-01、SAFE-01、QA-01 按 SPEC 需求追踪及离线验收矩阵继续实施；本次仅完成文档与图交付。旧勾选状态不代表这些目标已完成。

当前状态（2026-09-30）：见 [Current Demo Truth](docs/CURRENT_DEMO_TRUTH.md) 与 [Phase 1 验收](docs/PHASE1_VERIFICATION.md)。本轮规则与历史边界如下。

## Phase 1 验收状态（2026-09-30）

本轮实现与验收见 PHASE1_VERIFICATION；Current Demo Truth 是真实已保存状态。历史阶段耗时/完整 Usage/费用未采集，不能补造。真实 Provider 新链路验证本轮明确未执行；不属于可自动推进的任务。

以下原待办保留为历史追踪，是否仍适用须依据当前 SPEC 与 Truth 判断。


## 本轮验收

- 用临时库、Fixture 和 Mock 验证三个 Profile、11 Gate 与浏览器八页；真实主链由用户按人工 Gate 推进，确定性测试不冒充 Provider 验收。
- 更新 [参考对齐矩阵](docs/FRIEND_LOGIC_ALIGNMENT_MATRIX.md)，未实测项明确标注。
- 真实用户审核及 Preview 留给用户，不为验收自动推进。

## 范围外

- 新模型、独立重排服务、队列、多 Agent、生产部署和新一级页面。
