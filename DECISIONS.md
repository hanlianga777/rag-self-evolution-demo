# 决策记录

> **2026-09-30 文档同步边界：** 唯一当前目标规格为 [SPEC V1.4](docs/RAG_SELF_EVOLUTION_SPEC.md)，两张架构图已按最新设计重绘为目标架构。本次没有业务代码、数据库或索引升级，没有 Provider 或发布重跑；下方 Phase 1 / V1.3 内容保留为现有实现及历史证据，不能表示 V1.4 全部已完成。需求状态和未决项以 SPEC 第 3–4 节为准。

V1.4 决策：仅同步目标规格与从头重绘两图，保留技术栈、治理数值和历史数据；QC P0 的材料冲突记录为 `[OPEN-QC-P0]`，本次不更改实现。

当前状态（2026-09-30）：见 [Current Demo Truth](docs/CURRENT_DEMO_TRUTH.md) 与 [Phase 1 验收](docs/PHASE1_VERIFICATION.md)。本轮规则与历史边界如下。

## 2026-09-30 · Phase 1 决策

采用明确 Evaluation Group；构造题型与 Positive/Ablation/Negative 独立。业务证据必须定位原文，不能仅有文件名。混合候选不继承审批，复制新 Run 重走质量链。仅新增 openpyxl 依赖、nullable Monitoring 指标列；其他新字段进入既有 JSON。价格默认不配，不以当前单价回算历史。朋友截图只提供产品参考，不推断源码与模型迁移。


V1.3 历史决策：生成 Run 冻结 Mini／Medium／Full Profile；旧 Mini 字段兼容读取。Baseline Gate 贡献题由保存的逐题结果按后端聚合公式计算，历史未采集字段不补造。八个导航保留原 Hash。

当前产品规则只以 [SPEC V1.4](docs/RAG_SELF_EVOLUTION_SPEC.md) 为准。本文件记录工程选择及历史决策，不覆盖 SPEC。

## 选择独立实现，而非 fork AutoRAG

V1.2 历史决策（继承规则以 V1.4 SPEC 为准）：Ablation 独立，Positive/Ablation 检索未命中为 P1，QC 分数辅助；机器 P0 明确接受理由，确定性错误和 Fake Negative 不可豁免。Gate 1 一次确认并冻结；Gate 2 一次报告确认并选赢家；Composite D 基于实测有效差异，冲突保留赢家，无有效组合不造 D；Gate 3 原子发布。12 次启动预算含失败，为 D 留一次。旧 Direct Release 停止当前入口。缺产品／章节元数据不阻断动态语料。

AutoRAG 原始 Python RAG AutoML 能力位于 `legacy/`，而根项目已转向 AutoRAG 2.0。本 Demo 不将两者作为依赖：在真实运行时尚未落地前直接集成，会先引入过重的评测栈。`legacy/` 仅保留为文档化的概念参考。

## 单 Agent 与逻辑沙箱

UI 呈现的是一个具有工具化步骤的结构化 Optimization Agent，不是聊天记录或多 Agent 系统。Sandbox 指独立的候选配置快照和评测运行，不构成生产容器边界。

## Mock-first API — Superseded by V1.1

历史阶段曾使用 FastAPI 提供展示数据。当前正式链路已使用真实 SQLite/Provider/索引；Seed 和 Fixture 仅限隔离测试或标记为历史，不能作为 Golden、评测、推荐和发布结果。React 仍不持有业务夹具。

## 本地真实 PDF 检索

原始 PDF 保留在 `backend/documents/`。`app.build_index` 使用 PyMuPDF 读取页码、目录和正文短标题；无文字层时使用本地 RapidOCR。可靠章节内按连续段落切片（BGE `AutoTokenizer` 的真实 token，目标 400、同章节 60 overlap），没有可靠章节时明确使用页级/段落 fallback；切片不会跨文档或跨章节。每个分块保留厂商、产品、章节、起止页、真实 token 数、原文和 Embedding 状态，并以 BAAI/bge-small-zh-v1.5 归一化向量写入 FAISS IndexFlatIP。索引产物和模型权重均不提交 Git。没有通过解析/OCR 质量检查的 PDF 显示 `Needs OCR` / `Parse Failed`，不进入语料库。

旧“纯向量、固定 TopK=4、无 MinScore”运行决策已 **Superseded by V1.1**。当前 Pipeline 为 CandidateK → Vector/BM25 归一化 Hybrid → 可选 Lightweight Rerank → MinScore → TopK Context；默认 TopK=4 只是可调配置的基线值。没有可用索引或分块时不调用 Provider；引用仍保留文档、Chunk ID、章节、页码和分数，并由原生 PDF iframe 定位原文件页。

## 单次 Human Release（V1.1）— Superseded by V1.2

完整 A/B/C 回合、Sandbox、11 项 Hard Gate、Regression 和 Recommendation 是发布前置条件。操作者只点击一次“确认发布”；服务端原子记录 Human Release 与 Version Snapshot。历史 Candidate / Release Approval 审计保留但不再构成当前审批链。`baseline-v1` 是 Bootstrap 配置，不是假装正式发布的版本。

## Revision Preview 的材料语义（V1.1）

在当前材料上重写草案与重新选材是两个显式动作。前者不改变 Chunk；后者以本次更新的修订意图选同产品真实材料，并将尝试与结果保留在既有 Revision JSON 审计。两者均不自动应用或批准题目。Operation Console 随 Modal Drawer 进入其交互层，背景仍由 Modal 阻断。

## Governance 运行恢复与验收隔离（V1.1）

进程内后台线程不具备跨重启续跑能力：服务启动将遗留的 Generation / 质量重跑标为失败并保存已完成阶段，用户手动发起新 Run 或质量重跑。Revision 已应用后的质量恢复仍按持久化 Probe/QC 阶段继续，不重复应用草案。单题任务只显示真实阶段和耗时，不使用固定阶段百分比。真实 Provider 生命周期仅在启动前指定的隔离 SQLite 中验收；Fixture E2E 不作为真实结果。
