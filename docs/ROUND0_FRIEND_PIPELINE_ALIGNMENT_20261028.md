# 第0轮朋友 Pipeline 能力对标 · 2026-10-28

证据范围：本轮用户任务书描述的朋友方案D＋当前真实本地实现。未提供朋友代码、完整运行数据或截图，不推定其他能力或优化收益。朋友方案D仅作多参数综合参考，不能成为本项目正式默认值。

|能力|本轮前真实实现|本轮后状态|可能影响的Bad Case/可检验假设|延迟及Token副作用|
|---|---|---|---|---|
|任务Thinking|Provider无显式参数，历史行为未知|独立Baseline/Judge Max、Agent High；Candidate自主四档|Final充分但生成遗漏/证据误用时检验推理档位；性能瓶颈检验OFF/Low，不能预言收益|推理Token/首字/总耗时可能增加；Judge单独计时|
|Query Rewrite|已具备|保留，默认OFF，Low|词汇表达导致召回不足，保留型号约束|增加一次辅助模型调用/检索|
|MultiQuery|已具备|保留False/2/4/6，Low|同意图多种表达补充召回|辅助输出及多次Embedding/BM25增加|
|HyDE|已具备|保留OFF/ON，High|真实Trace支持的召回缺口探索，假设文本不当答案证据|辅助生成/检索成本，可能检索噪声|
|Query Decompose|朋友支持，本项目缺真实能力且原Search Space排除|本轮新增，默认OFF；真正子意图拆解/分别检索/原问题约束/共享合并重排|多事项复合题仅部分命中时检验；普通单问题不强制拆分|最多1次拆解＋3个子检索，保留原查询；最多4路（与其他已授权扩展合并时各有原限额）|
|Retrieval MaxTokens|朋友支持，本项目无真实容量控制|本轮新增，默认OFF；8/16/32/64Ki-token完整块预算|上下文过长或噪声时探索；排除任何证据会停止生成，不能靠删安全前提提分|本地Tokenizer耗时；可能减少生成输入，但不保证性能收益/资格|
|Hybrid/CandidateK/TopK/α/阈值|已具备|保留原Search Space与依赖|有来源的召回缺口/排序遗漏/噪声，按同一假设联合调整|更多Candidate/Rerank和Final输入Token|
|Rerank/Metadata/Alias|已具备|保留，默认ON/OFF/OFF|排序或对象混淆，仅限真实根因/合法关系|Rerank调用、过滤召回风险、Alias范围风险|
|Prompt策略|已有Grounded/Completeness/Abstention|共同V2正式启用，初始Grounded；其他仍合法|操作遗漏/拒答不当，必须保持证据/安全约束|实际回答长度与Token变化，未设统一字数上限|
|Parent Expand|现有真实Parent合并|保留，不重建/切块/索引|完整来源减少切断上下文，不能将Child预览当全部Parent|输入Token可能增多|
|综合方案D|任务书给出朋友参考方向，不能外推结果|本轮不新增自动组合；未来仅整合已实测有效兼容ABC，再完整回归|参数交互、回归与安全副作用均须验证|额外完整Sandbox；当前不执行|

## 为什么不能照搬参数

本项目真实基座为MinerU VLM、1400/400/80、text-embedding-v4和qwen3-rerank，数据为设备型号、安全操作和负向边界混合50题；朋友的Corpus、文档、Tokenizer、规模、延迟口径及评分合同未提供，参数效果不可迁移。当前正式Manifest不变，不以旧本地BGE fallback替代正式Embedding。

当前349个真实Canonical Parent用官方V4 tokenizer计数：正文p50=55、p95=267、最大839 token；最大4个正文总和2708、6个3799（生成legend/页码/标题另算）。因此最低8192档已为当前TopK留出空间，较高档位用于受控未来实验；默认OFF继续送完整Final。完整统计及来源哈希见`round0/audit_evidence.json`。这些是离线容量观测，不是回答质量结论。

## 后续检验条件

Agent只基于保存的Bad Case/Trace提出假设；一个候选可有多个必要参数，必须说明主要方向、参数依赖、目标、预期收益与副作用。共同评测身份保持一致，独立实验身份记录实际Diff，合法Thinking/TopK等变化不要求重跑同合同Baseline。改变Golden/Judge/Corpus/Generation共同合同则建立新边界。

未来候选必须完整50题回归，保留原11 Gate（P50≤25s、P99≤60s；Safety/Injection≥95%）、目标改善、总失败减少及Regression资格。Judge耗时不能混入回答延迟。所有优化假设目前均未通过真实新Baseline/Sandbox验证。
