# V1.3 架构说明

当前状态（2026-09-30）：见 [Current Demo Truth](docs/CURRENT_DEMO_TRUTH.md) 与 [Phase 1 验收](docs/PHASE1_VERIFICATION.md)。本轮规则与历史边界如下。

## Phase 1 增量架构（2026-09-30）

业务文件 → 标准库 CSV / openpyxl XLSX → 当前 Corpus 原文定位 → questions/raw_json → Profile 复制新 Run → 既有 Hard Validation / Probe / QC / Gate 1。无第二套 Golden 系统。

perf_counter 测量实际 Query、Retrieval 子阶段、Context、Generation 与 Judge；保留 UTC 时间、原回答 Gate 延迟和完整 Provider Usage。价格仅集中配置；Monitoring additive nullable JSON。React 复用 Radix Dialog / 原组件，不增加框架或状态库。架构 HTML 与 PNG 同步。


## 运行时

React/Vite + FastAPI + SQLite + 本地 BGE/FAISS，复用已有八个一级工作区。动态文档清单与 Embedding 主题配额；文档 ID、Chunk ID、原文必需，产品／章节可选。原四 PDF 仅示例。

## 主链与事务

Golden（Mini 20／Medium 49／Full 98）→ Gate 1 人工确认并冻结 → Baseline 报告／门禁／逐题诊断 → Tuning A/B/C Sandbox → Gate 2 报告确认并选择赢家 → D 决策／重评 → Gate 3 人工发布 → 问答试验。

只有 Tuning 是 Agent。Generation、QC、Evaluation 是受控工作流；编辑和替换复用 Revision JSON、哈希与后台线程。采用替换才原子切换活动题映射，历史不删除。Gate 1 原子保存审核和不可变 Golden Version。

Baseline/A/B/C/D 共用冻结 Golden、Judge、逐题评测器。新 Run 保存 Profile 计数、Hard Validation 逐项检查与 Probe 审计；历史缺失字段不推断。Baseline 页面按持久化 Snapshot、配置、逐题结果和相同聚合公式解释 Gate。12 次启动预算含失败并为 D 留一次；SQLite 写锁防并发超支。Gate 2 等已启动评测全部终结。D 合并实测有效配置差异，冲突保留赢家，新组合完整重评；无新增失败且有实际修复才替代赢家。Gate 3 重验报告／D 决策、Sandbox、11 Gate 与 Regression，同事务写 Human Release 及 Version Snapshot。

Monitoring、版本历史和回滚是辅助能力。重启不假称线程仍在执行：运行标为中断／失败，审计和已消费预算保留。

八个现有 Hash 工作区共用只读 Lifecycle 导航。`GET /api/pipeline` 汇总活动版本、最近 Baseline、索引信息和 `policy.py` 冻结 Search Space；`POST /api/preview/scheme` 只按已保存 Baseline、Candidate 或 Production Version ID 解析配置，不接收客户端配置。该预览由人主动触发，历史逐题 Evaluation 仍从保存的 Run 读取。

## Provider 与证据

DeepSeek 只经后端显式调用，密钥不返回前端。检索是 Vector/BM25 Hybrid + 可选 Lightweight Rerank，不是独立重排模型。Provider 错误不伪装为质量结论；Legacy、Fixture 与真实生命周期分别报告。

[业务图源](架构/业务流程图.html) 与 [技术图源](架构/技术架构图.html) 是唯一可编辑图源，PNG 从对应 HTML 导出。
