# 变更记录

## 2026-10-02 · V1.4 完整实施（整合验收中）

- 实施 Current Baseline/Experiment 绑定、Monitoring 首轮与幂等、Golden V2 规划、统一 Validator/Pool 匹配、双层 Probe/原解析全文和版本化成本。
- UI 八模块和完整隔离 HTTP 生命周期测试通过，286 项后端、105 项前端、构建和四尺寸 Chromium 187 检查通过，阶段复审已通过，最终整体审查中；阶段结果、真实数据保护与恢复入口见 [实施验收](docs/V1_4_IMPLEMENTATION_VERIFICATION.md)。
- 关闭机器 QC P0 人工理由接受的未决项；确定性错误与执行失败继续不可豁免。两张目标架构图保留，真实 Provider 与发布没有重跑，active 全文没有切换。

## 2026-09-30 · V1.4 目标规格与架构重绘

- 唯一 SPEC 更新为 V1.4，完整保留需求 ID、当前源码差异与离线验收要求；V1.3 及更早规则标为历史。
- 两张架构图从头生成自包含 HTML/内嵌 SVG 与 2560×1440 PNG，表达可信测量、优化、人工发布反馈和离线/在线/数据支撑边界。
- README、架构说明及项目入口文档同步版本边界；QC P0 冲突作为明确未决项保留。
- 仅文档与图交付，没有业务代码/数据/索引迁移或真实 Provider/发布调用。验收见 [同步报告](docs/V1_4_DOCS_SYNC_VERIFICATION.md)。

当前状态（2026-09-30）：见 [Current Demo Truth](docs/CURRENT_DEMO_TRUTH.md) 与 [Phase 1 验收](docs/PHASE1_VERIFICATION.md)。本轮规则与历史边界如下。

## 2026-09-30 · Phase 1 / V1.3

- CSV/XLSX 预览、原文定位、业务候选池及混合 Profile Run，旧审批不继承。
- 独立构造题型与可靠事实/聚合确定性生成，普通题 fallback。
- Select、文字浮层、标签 Popover、表格、Radix 详情和流程统一。
- Baseline Gate/案例、Tuning/D、发布状态、QA 保存配置差异与会话恢复。
- 实际阶段、完整 Usage、未配置价格与 nullable Monitoring 指标迁移。
- 验证层与真实历史分开，业务数据逐字段保全。


## V1.3 — 评测与实验闭环

- Golden 支持 Mini 20、Medium 49、Full 98，保留旧 Mini 兼容与一次人工 Gate 1。
- Baseline 使用持久化 Snapshot、配置、逐题结果解释 11 Gate；Tuning 呈现已有候选配置差异和 Sandbox 记录。
- 八个一级导航沿用原 Hash；启动入口固定 `#overview`。开发验收使用隔离库，不运行真实业务主链。

## 0.2.2 — 2026-09-14

- 真实 PDF 切片改为“章节 → 连续段落 → BGE tokenizer token 上限”；同章节可跨页，跨章节绝不合并。没有可靠目录或正文短标题的文件明确记录为页级/段落 fallback。
- 每个真实分块新增厂商、产品、章节、跨页范围、`chunk_text`、真实 token 数与 Embedding 状态；FAISS 写入成功后才标记为 `Indexed`。
- 默认检索固定为 BGE 归一化向量 + FAISS `IndexFlatIP` TopK=4；移除相关度阈值和消费电子关键词拦截，低分候选仍如实返回。
- Document Inspector 分块卡片展示章节、页码范围、Token Count、Chunk Text 与 Embedding Status，引用继续定位原始 PDF 的 `page_start`。

## 0.2.1 — 2026-09-13

- PDF Inspector 改用 API 原点的绝对 URL，避免前端 SPA 回退被错误嵌入为“PDF 原文”。
- `start_demo.command` 改为 Finder 可双击、登录后自动恢复的本地启动入口；它不修改模型配置或 `.env`。

## 0.2.0 — 2026-09-13

- 新增本地 PDF OCR、章节/页内段落真实切片、BAAI/bge-small-zh-v1.5 向量与 FAISS IndexFlatIP 持久化索引。
- 移除人工 `samples` 作为问答语料的路径；索引缺失或无可用分块时不会调用 DeepSeek。
- 新增含页码、Chunk ID、相关度与原文预览的结构化 evidence；Document Inspector 支持 PDF、分块与索引信息三标签及页码定位。
- 索引产物、PDF 指纹与模型/OCR 缓存均保持本地，不提交 Git；评测/优化/A-B-C 回放维持 Demo 数据边界。

## 0.1.0 — 2026-09-04

- 初始化 RAG Evolution Mock Demo，呈现评测驱动的优化故事线。
- 新增 FastAPI/SQLite 种子 API、React SaaS UI、可重跑实验和文档。
- 新增 DeepSeek 真实 Provider、本地证据检索、显式连接验证与 live evaluation API；未配置或调用失败时明确回退 Mock。
- 加固真实/模拟边界：严格校验付费请求、拒绝不可信 Origin、禁止 fallback 被计为真实评测分数，并校验 Judge 输出。
- Demo Active 版本改为 SQLite 持久状态；前端逐次展示回答来源与回退原因，补齐中文数据边界、移动端导航、键盘详情与局部错误反馈。
