# Phase 1 最终收口验收报告

日期：2026-10-05（Asia/Shanghai）。基线 main `1fa4227`。使用 ponytail 最小改动原则与上传的 diagram-design。唯一规格源为 `docs/RAG_SELF_EVOLUTION_SPEC.md`。

## A. 改动

八页共用 PageShell 与 Shared Card Token；重构概览和知识库，其他六页仅统一容器与结构化证据展示，保留业务规则。未新增依赖或通用框架。修复受控重启、MinerU 上传 Content-Type、受限官方 CDN TLS 下载、逐 Slot 质量恢复、有限响应重试及 Judge 结构化契约；未放宽冻结 Validator、Coverage 或批准规则。

实时操作前通过 SQLite Backup API 与文件备份保护 25 张表、27 个 Corpus/Index/Manifest/关联文件。最终历史行及文件摘要均未改变；Legacy Production 实际检索仍使用绑定的 252 Chunk / 512d 索引，成功返回 4 个上下文。

## B. 真实 Provider

MinerU、text-embedding-v4、qwen3-rerank、DeepSeek 均经真实调用验证。MinerU 官方 VLM 成功解析四份 PDF；Embedding 实际返回 1024d；Rerank 使用模型真实排名；DeepSeek 完成新版本 QA 与 Golden Generation/Judge。真实 QA“水箱冲洗多久”回答约 30 秒，证据来自 PDF 第 92–93 页。

根目录 .env 专用接口地址由现有配置边界读取。凭据不进入聊天、数据库、输出报告或 Git。API providers 的 configured 字段仍表示配置状态，真实 verified 结论依据实际产物及请求结果。

## C. 真实资产

版本 `KP-6cb9388a1131f837dac2`；构建 `CORP-20261005060652072289` 已校验并原子激活。

| Documents | Pages | Parent | Child | Embedding | Dimension | Indexed |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | 157 | 349 | 368 | 368 | 1024 | 368 |

Parent 1400 / Child 400 / Overlap 80，冻结 BGE tokenizer 身份；FAISS IndexFlatIP。保留 MinerU 原 Block、表格结构、页面位置、顺序与业务 KV。新资产没有复用旧 252 Chunk / 512d 结果。

## D. Coverage

真实 Child 向量生成 Initial K 9 / Final K 9 / Merge 0 / Cluster 9 / Slot 98。所有 Cluster、代表 Child、合并关系、配额、Slot 持久化；页面展示全部真实记录，不调用生成模型重算。数据库、API、索引与 UI 数量一致。

## E. Golden 与 Human Gate 1

Run `GGEN-20261005060827468143`，Full Profile：40 Positive / 18 Ablation / 40 Negative。98 Slot 完成 Generation 与 Hard Validation，Probe 98 通过；QC 98 完成，其中 97 通过、1 项 P0（Q66）。91 题使用真实 Provider 构建，7 题沿用冻结 Fact/Aggregation 确定性构建。

Q66 的 clarify 子类与请求忽略手册、直接设置的题意不符；一次内容修复预算已消耗，修复草稿未通过硬校验，原题和失败原因保留给人工处理。不会自动批准或再次消耗内容修复预算。97 项待人审、1 项待修订、批准 0。

Human Gate 1 Ready 来自实际逐 Slot Probe/QC 记录，而非单独依赖 completed。一次质量重跑被重启中断，仅恢复其中 3 项网络失败及 1 项未完成 QC，保留中断审计，其余合格 Slot 不重跑。最终恢复后再次从 API 核对 Ready。

未批准 Gate、未冻结新 Golden Snapshot；未运行新正式 Baseline、Agent、Sandbox、Regression 或发布。QC P1/P2 疑点仍须人工审核，Ready 不表示全部质量通过。

## F. UI 与 Diagram

八页统一 1px 边框、9px 圆角、9px padding、8px gap、112px 紧凑卡高及 12/700、11、10 字号层级；复用原母版颜色和状态。固定 Header/Tabs，仅内容区滚动；切页/Tab 复位；Drawer 独立。知识库保留两个 Tab 与五段顺序，名称统一为“知识处理选型策略”。正式 UI 删除开发详情、Raw JSON 和参考图上传。

Diagram 使用 smoke gray / orange，与产品卡片分离。业务图按生命周期从左到右，只有 Optimization Agent 标记 Main Agent。技术图为处理链、检索链及 Coverage、Evidence 两支路，明确 Parent Expand、Provider 边界和“小块负责找得准，大块负责答得全”。内联 SVG、正交连接、独立可访问性 ID；复杂图分两行，不生成独立演示文件。旧 404 路由经受控服务重启解决，新 /api/knowledge 与 Vite 代理正常。

## G. 证据穿透

真实 Child→Parent→PDF 页、Cluster→全部 Slot→Evaluation Group/Construction Type/材料 Child 已浏览器验证。Document/Bad Case/检索/质量证据用结构化记录展示。Cluster 与文档列表固定高度内部滚动；Drawer Escape 和 Tab 键盘操作通过。

## H. 验证

后端 317 项、前端 156 项 / 24 files 全量通过，TypeScript、Vite Build、git diff --check 通过。后端测试以导入前临时数据库与禁外网模式运行，与真实 Provider 验证分开报告。

覆盖 Token/Overlap、原表结构/页码、向量数量/维度、Rerank 排名、Parent 去重、配置身份/跨版本隔离、失败与重启恢复、原子激活回滚、Coverage 过期、迟到前端请求、真实质量恢复预算和 Gate 推导。

1440×900、1280×800、1024×768 八页共 24 次检查通过：Header 固定、单一页面滚动、无横向溢出、无 pageerror。真实 Drawer/PDF/Cluster/Slot 验证通过，键盘 Enter/Escape 与滚动复位通过。Diagram skill 自检与文字几何检查通过，并人工查看正交连线和文字。其余六页只读回归，不触发付费评测或发布。

## I. Git 与证据

Scoped diff 只含本轮代码、测试、唯一 SPEC 与验收报告。数据库、.env、索引和备份不进 Git。最终 Commit SHA、push origin/main 与工作区同步结果见交付 Git 证据。输出目录含测试日志、Legacy 数据证明、真实 QA、API 结果及十类截图索引。

## J. 外部阻塞

当前外部阻塞：无。按授权边界停在 Human Gate 1；Q66 P0 和其余人工审核属于后续人审事项，不宣称 QC 全部通过或已具备发布条件。

---

<details>
<summary>历史实施验收（本轮前，状态已由上文替代）</summary>

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

</details>
