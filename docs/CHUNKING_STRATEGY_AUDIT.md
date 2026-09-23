# Chunking Strategy 离线审计（2026-09-23）

## 结论

候选 `section-aware-adaptive` **未通过切换门槛**。生产继续使用 `section-aware-v2`（400 BGE tokens / 60 overlap）；生产 `corpus.py`、manifest、FAISS 索引和数据库均未修改。本次只是切分与检索离线对比，32 道 `GGC-001`～`GGC-032` 仍为 `Pending Review` 的 Legacy 候选题，不是 Approved Golden，也不是正式 Evaluation。

## 方法与可复现配置

- 来源：4 份正式 PDF；使用 `backend/data/index/manifest.json` 对应的 PDF 指纹。基线读取现存 252 个真实 chunk 和 FAISS 索引。候选从原 PDF 的文字层、本地 RapidOCR、目录/正文短标题重新切分，在系统临时目录建立 FAISS `IndexFlatIP`，执行后临时索引自动删除。
- 两组均使用本机缓存的 `BAAI/bge-small-zh-v1.5`、归一化向量与 `backend/app/policy.py` 的同一 `DEFAULT_PIPELINE_CONFIG`：CandidateK=12、TopK=4、Hybrid Alpha=0.5、轻量重排开启、MinScore=0、元数据过滤关闭。无 DeepSeek 调用。
- 候选按章节保留跨页连续性；短章节整体保留，操作/安全类长章节允许 450 token 目标，其他长章节仍为 400；60 token overlap；同一章节内小于 80 token 的尾块仅在合并后不超过 520 token 时并回前块。原有弱结构 OCR 页级 fallback 保留。此候选为离线实验代码 `backend/app/chunking_audit.py`，没有接入生产构建流程。
- 相关性由 `golden_evidence_inventory.json` 中的 `source_evidence_ids → document_id、page_start/end、原文 key_points` 映射确定。命中需要文档相同、页码区间相交且至少一个长度不少于 5 字的原文证据点出现在召回块；仅去除空白字符。旧 `source_chunk_ids` **不参与相关性判断**。Hit@1/4 是 32 题中至少命中一个证据点的题目占比；Recall@4 是每题已命中证据主题比例的宏平均；MRR 使用首个证据命中的倒数排名。该精确原文口径可能低估改写后仍可支持答案的块，需人工复核争议项。
- 纳入 32/32 道 Grounded 草案题；没有因证据 ID 缺失而排除的题。其证据映射仅用于本次离线检索对照，不改变题目的 Legacy / Pending Review 属性。
- 延迟为模型及每组首题预热后的 32 次本地 `retrieve` 调用 P95。两组顺序执行，受本机负载和缓存影响，只适合本次相对观察。结构中的 tiny 为 `<80` token，oversize 为 `>520` token；索引大小只计 FAISS 二进制文件。

## 实测结果

| 指标 | 现行 v2 | 候选 adaptive | 门槛判断 |
|---|---:|---:|---|
| Evidence Hit@1 | 18/32，56.25% | 18/32，56.25% | 持平 |
| Evidence Hit@4 | 26/32，81.25% | 25/32，78.13% | **下降** |
| Evidence Recall@4（宏平均） | 70.31% | 68.23% | **下降** |
| Evidence MRR | 0.6719 | 0.6615 | **下降** |
| chunk 数量 | 252 | 238 | 94.44% 基线 |
| token 中位数 | 139 | 140 | 观察 |
| tiny `<80` | 75 | 72 | 减少 3 |
| oversize `>520` | 0 | 0 | 持平 |
| 页码字段完整且顺序有效 | 252/252 | 238/238 | 持平 |
| FAISS 索引大小 | 516,141 B | 487,469 B | 94.44% 基线 |
| 本地检索 P95 | 45.52 ms | 19.42 ms | 42.66% 基线；仅单轮观察 |

基线 Top4 未命中：`GGC-012`、`017`、`020`、`021`、`023`、`028`。候选还增加 `GGC-031` 未命中。分块数、索引体积、P95 均未超过基线 110%，页码字段也未退化；但四项检索质量必须全部不下降，候选在 Hit@4、Recall@4、MRR 三项失败。tiny 块减少只能作为结构改善的观察，不能抵消检索退化。因此不切换生产配置，也不发布候选索引。

复现：在仓库根目录运行 `PYTHONPATH=backend python3 -m app.chunking_audit`；需已有 PDF、本地 RapidOCR/BGE 模型和仓库既有 Python 依赖。输出 JSON 包含逐题的相关性结果和 Top4 文档/页码/chunk 追溯。运行不写 `demo.db`、正式索引或 Golden 数据。
