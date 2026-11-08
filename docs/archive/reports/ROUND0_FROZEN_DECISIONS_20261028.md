# 第0轮非 Judge 决策记录 · 2026-10-28

权威来源：用户《第0轮基础配置统一实施总任务书》；当前正式合同为 `RAG_SELF_EVOLUTION_SPEC.md` 文首。本文将本轮实现与验收边界固定，不替代未来 Judge 六轮讨论。

|事项|当前决策及实施|状态|
|---|---|---|
|新请求模型|DeepSeek-V4.1 Flash，`deepseek-flash`；load_settings只为新请求规范化旧env别名`deepseek-v4-flash`，不推断服务端具体修订|已实现；真实 API 未验证|
|任务 Thinking|Baseline Max、Judge独立Max、Candidate `off/low/high/max`（未改继承Max）、Agent High、Rewrite/MultiQuery Low、HyDE/Decompose High；其他辅助High|已实现、离线已验证|
|API参数|启用`thinking.type=enabled`并传`reasoning_effort`；OFF只传disabled且无effort；Thinking不传temperature，不将其描述为有效控制变量|已实现、离线已验证|
|共同生成合同|默认`generation-vnext-2`＋Grounded，复用既有规则；Completeness、Abstention仍合法且共享V2证据/安全边界；禁止Golden参考/评分点进入生成请求|已实现、离线已验证|
|初始检索|CandidateK12、TopK4、MinScore0、Hybrid ON/α0.5、Rerank ON；Rewrite/MultiQuery/HyDE/Filter/Alias OFF；Parent Expand原行为|已实现、离线已验证|
|技术基座|真实Manifest：MinerU VLM，Parent1400/Child400/Overlap80、text-embedding-v4、qwen3-rerank、现有Corpus/FAISS；BGE只属于冻结分块tokenizer或明确Legacy fixture|只读核查，未改数据|
|Query Decompose|默认False；手动Draft及合法Candidate可开启；单次JSON拆解最多3个独立意图，每个携完整原问题约束，实际独立检索合并到原Candidate/Rerank/Final链|已实现、离线已验证|
|Retrieval MaxTokens|默认False且不额外裁剪；可选8192/16384/32768/65536；官方V4本地Tokenizer精确计数完整生成上下文含来源legend，逐完整证据块保留；任何排除均标不完整并停止生成|已实现、离线已验证|
|Search Space|原12项全部保留，新增generation_thinking/query_decompose/retrieval_max_tokens；bool/int严格区分，TopK≤CandidateK、Hybrid α依赖保留；新增缺省字段兼容读取不回写|已实现、离线已验证|
|Candidate组合|一个可验证假设＋一个主要方向＋有证据的必要多参数联合；不为凑ABC产生无证据候选|沿用并扩展新参数识别|
|Candidate D|未来组合已验证有效且兼容的ABC改进，再全量回归；本轮未新增D组合算法、生成流程、推荐或发布能力|留待后续阶段|
|共同评测身份|冻结Golden ID及内容哈希、Corpus/Index、Judge模型/Thinking/Prompt/评分版本、11 Gate定义/原统计版本、Generation V2、共同模型约束、业务规则来源|已实现、离线已验证|
|独立实验身份|实际检索、Thinking、Prompt Strategy及新能力配置单独哈希，Run.result保存experiment_config_identity；实际请求payload摘要/UTC时间/响应模型/usage另存真实轨迹|已实现、离线已验证|
|比较/续跑|合法Candidate参数不改变共同身份，不要求重跑同合同Baseline；共同版本变更不能继承成绩；旧未知Thinking不冒认Max；续跑只复用同身份冻结配置、请求限额和检查点|已实现、离线已验证|
|Draft|未保存变更只在编辑区；保存且当前身份有效的Draft可在用户主动新建Baseline时生效，Baseline只允许Max；无Draft用确认默认值，不继承旧Production的Abstention；续跑读源Run|已实现、离线已验证|
|页面归属|Pipeline负责技术基座/可调参数/Search Space/Draft和内嵌差异；独立冻结卡删除；Baseline报告评测信息及原抽屉展示保存的Run|已实现、离线已验证|
|Golden 0.7|全局/50题/整套审查；不修题、不改审核、不冻结；具体证据与确定程度见专项报告|只读审计|
|Judge/11 Gate|不改Prompt、核心判分/公式/阈值/动态安全分母。有效完成Baseline即使Gate FAIL仍可Agent；Candidate仍11/11＋目标改善＋失败减少＋Regression|待 Judge 讨论；本轮只审计|
|运行与发布|本轮Provider0、Golden QC/Probe0、正式Baseline/Candidate/Sandbox0；不批准、不推荐、不发布、不回滚|留待后续阶段|

## Token与费用边界

新请求技术输出上限：answer/Judge 65536、Agent32768、query16384；这些容量同时容纳推理和最终内容，低于官方模型接口最大输出393216，避免将旧8192回答上限直接当Max总容量。不是人民币预算，不保证模型必定在Gate时限内完成。历史请求限额保留原值，身份内冻结，不回填。

保留真实Usage、缓存输入、含推理的completion计费、未知费用对账、有限重试及断点恢复。`finish_reason=length`仍报技术异常，unsupported effort明确报API技术错误，禁止静默降档；不存储或展示原始reasoning_content。估算费用沿原价格配置、时间及有效性规则，不能冒充账单。

## 核查到的真实历史状态

正式Golden `GD-20261027070931`；Corpus `CORPUS-38c90d5628b68c76d53e`；Index `IDX-ee5bb4977dcf28f8e2f8`。试运行 `EVAL-20261027122116244939` 已完成，但实际为generation-vnext-1、Abstention、deepseek-v4-flash，Thinking字段缺失。旧记录只读；无法由别名证明其实际推理档位或服务端模型修订。

`.env`有效Base URL为`https://api.deepseek.com`、模型旧别名；未输出/更改密钥或源.env。新配置加载将规范化别名。官方兼容合同已查验，认证接口与网关实测未执行。官方当前首调文档说明Flash由V4.1-Flash-1017提供服务，但这只是当前公开说明，不能据此回填历史响应的具体模型版本。

## 实施与阶段边界

顺序保持：第0轮代码验收 → Judge六轮规则讨论 → 集中修复/验收 → 明确授权后正式新Baseline → Agent优化。Max不能代替Judge修复，也不预设其准确率或延迟。

现有暗色主题能力缺失，本轮不扩展整站视觉系统；系统深色偏好下仍使用既有浅色主题。用户提及的两张截图未附于任务文本，不能声称已逐图对齐。隔离Fixture页面只验证布局，不是正式运行证据。

## 官方合同来源（2026-10-28只读）

- [Thinking模式](https://api-docs.deepseek.com/guides/thinking_mode/)
- [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)
- [模型元数据](https://api-docs.deepseek.com/api/list-models/)
- [官方离线Tokenizer](https://api-docs.deepseek.com/quick_start/token_usage/)；归档来源及哈希见`../backend/config/THIRD_PARTY_NOTICES.md`。
