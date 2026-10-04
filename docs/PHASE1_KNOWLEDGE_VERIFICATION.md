# Phase 1 Knowledge Pipeline 实施验收

日期：2026-10-05（Asia/Shanghai）。代码与隔离验证交付；真实全链尚未完成。唯一规则源是 [SPEC](RAG_SELF_EVOLUTION_SPEC.md)，本报告不替代规格或人工批准。

## A. 实施摘要

只重构项目概览、知识库两个入口；其他六页源文件未改版。新增单文件直接 Provider / Pipeline 实现，复用现有 React、FastAPI、SQLite JSON、FAISS、Coverage Planner、Golden 和治理。新增版本身份、文件校验、Legacy 路由、持久化 Cluster / Slot 详情、阶段状态及迟到请求保护；没有新通用框架或新增数据库表。

迁移前使用 SQLite Backup API 保存真实数据库副本，完整备份 11 个运行 Corpus / Index / Manifest / 关联文件，以及源 PDF 与报告，记录 25 张表内容与文件 SHA-256。开发、浏览器和失败操作均在独立 clone / 数据库副本执行。提交前复核原始数据库 25 张表内容与 11 个产物哈希不变。

Knowledge Version 身份包含配置、冻结 tokenizer 序列摘要及 Parent/Child、Embedding、Index 摘要；构建校验后原子激活，失败保留 staging 和持久化操作原因。Legacy Production 永远使用归档 Legacy 索引；新激活不是 Production 迁移，历史快照不改写。

## B. 新 Pipeline 配置

| 项目 | 持久化默认配置 |
| --- | --- |
| Parser | MinerU 官方精准 API；上传 / 异步轮询 / 结果 ZIP；`model_version=vlm` |
| Table | 项目 `table-kv-v1`；保留原 Block / HTML / 页面位置 / 顺序 |
| Tokenizer | `BAAI/bge-small-zh-v1.5`，本地冻结序列摘要，仅计数 |
| Parent / Child / Overlap | 1400 / 400 / 80 Tokens |
| Embedding | `text-embedding-v4`，请求 1024 维并验证实际返回 |
| Index | FAISS IP；保留真实 Child vectors |
| Retrieval | 现有 Query Processing / Hybrid Vector + BM25 / CandidateK 12 |
| Rerank / Expand | `qwen3-rerank` → Parent 去重，保留全部命中 Child → TopK 4 |
| LLM | DeepSeek 现有 Generation / Judge / Optimization Agent 分工 |
| Golden | 已有 Full Profile（40 Positive / 18 Ablation / 40 Negative） |

接口以 [MinerU 官方说明](https://mineru.net/apiManage/docs)、[阿里 Embedding](https://help.aliyun.com/zh/model-studio/text-embedding-synchronous-api/) 和 [阿里 Rerank](https://help.aliyun.com/zh/model-studio/text-rerank-api) 为依据。新版本真实维度尚未采集，1024 是请求配置。

## C. 实际 Provider 状态

| Provider / 配置 | 本轮状态 | 证据边界 |
| --- | --- | --- |
| MinerU | missing | 本地 Token 缺失，未上传任何真实 PDF |
| Embedding Key | configured | 未真实调用 |
| Rerank Key | configured | 未真实调用 |
| Alibaba 业务空间根地址 | missing | 需与 Key 匹配的 `DASHSCOPE_BASE_URL` |
| DeepSeek | verified | 最小真实 QA 响应成功；不是新 Corpus QA / Judge / Agent 全链验收 |

凭据没有进入聊天、日志、数据库或 Git。Provider 失败不静默回退并标记新 Pipeline 成功。

## D. 新 Corpus 实际数据

新 Corpus 尚未构建。输入是 4 Documents / 157 Pages；新 Parent、Child、Embedding Artifact、Dimension、Indexed、Cluster 都未生成。页面实际展示的是 Legacy BGE 512d / 252 Indexed，已明确标为 Legacy，不能计为新版本结果。

## E. Coverage

真实新版本 Initial K / Final K / Merge Count / Cluster / Golden Slot 尚未生成。知识库只读持久化 Plan，访问页面不调用模型。隔离 fixture 的 3 Cluster / 98 Slot 仅用于测试 Drawer，不能作为真实业务数量。

## F. 数据链当前进度

停在真实 Corpus 构建的配置前提，尚未进行 MinerU、Embedding、Rerank、新 Golden、Baseline、Candidate 或 Release。隔离重建实际返回 `failed / build / MinerU Token missing`，保留旧有效索引。配置完整后重建成功会自动启动现有 Full Construction / Validation / Probe / QC，逐 Slot 保存结果和失败原因。

## G. Human Gate

尚未到达 Human Gate。当前需在本地 `.env` 配置 `MINERU_API_KEY` 和匹配业务空间的 `DASHSCOPE_BASE_URL`，重启后在知识库点击“重建 Knowledge Pipeline”。真实 Full Golden 到达 Gate 1 后，需要用户逐项人工审核并冻结；此前不得运行正式 Baseline。本轮未批准任何 Gate 或发布版本。

## H. 验证

- 后端 309 项全量通过，最终配置绑定改动后定向 11 项再次通过；前端 156 项通过，TypeScript / Vite build 通过，`git diff --check` 通过。
- 新隔离测试覆盖表格原结构、list/code、Token 上限与页码、配置身份、Embedding 维度、Rerank 排序映射、Child→Parent 去重证据、真实 FAISS + 模拟 Provider 响应、全文匹配 Probe、负向向量空间、跨版本拒绝、激活回滚、重启中断、旧失败 Golden 不阻断新 Corpus；同版本待补齐仍阻断。
- 1440×900 / 1280×800 / 1024×768 三尺寸八页检查均无横向溢出、无 pageerror。概览三个 Tab、知识库 Tab、文档 Drawer、Escape 已测。明确 fixture 测 Cluster→Slot→材料 Child、Parent Drawer、Escape 焦点恢复及内部滚动样式；前端迟到响应回归通过。其他六页只读回归通过，没有运行其付费或发布动作。
- 三份嵌入 SVG 的提取自检均 `OK`；图形人工查看文字、Provider 标注与正交连线，无节点穿线。浅绿 / 深绿按本轮文字规则覆盖默认橙色，不推测朋友截图。
- 复核发现的全文页 `parser`、负向编辑使用 Legacy embedding、list/code 遗漏、旧版本失败 Golden 阻断新版本均已关闭，并有隔离回归。真实 Provider、真实完整 Slot / QA / Gate 流程仍受配置前提阻塞。

## I. Git

提交仅包含上述代码、测试、配置示例、README、唯一 SPEC 与本报告；`.env`、真实 DB、索引、备份与 fixture 产物均忽略。最终 Commit SHA、`origin/main` 推送及原工作区同步结果以交付消息 / 输出报告为准。

## J. Screenshots

提供十类截图与来源索引。1–6、8、Legacy 文档 Drawer 和 10 是真实数据库副本状态；新资产与 Coverage 显示待生成 / 待更新。7 Cluster Drawer、9 新 Parent/Child Drawer 是显式标注“隔离 Fixture 验收｜非真实 Provider / Corpus 数据”的交互证据。缺少新真实 Corpus，无法提供真实新 Cluster 或 Parent/Child Drawer；不以 fixture 冒充真实完成。
