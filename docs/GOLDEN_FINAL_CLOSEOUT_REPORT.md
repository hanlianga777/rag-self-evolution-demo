# Golden Dataset最终审核链路验收（2026-10-26）

基于`075cb51`，使用Ponytail最小修改。结论：已知审核链路阻断已修复，具备申请真实付费批量审核的条件；尚不具备正式冻结条件。真实Provider、Probe/QC、批准与冻结均未执行。未新建服务、表、依赖或前端流程。

## 1. 当前50题逐题核查

正式工作集仍为`GCONTENT-10c6ab67b1ef279d70b4f361`，Run为`GGEN-GCONTENT-10c6ab67b1ef279d70b4f361`。50个ID、原题、Positive20/Ablation10/Negative20、30份参考答案、20份负向行为、全部业务要求和来源与修改前备份完全一致。本轮没有实质答案/检查点修改，也没有重新生成题目。

逐题核对问题、参考/行为、必答/条件/辅助、型号版本数值、禁止错误、来源及安全顺序：[50题审计表](GOLDEN_CLOSEOUT_50_AUDIT.md)、[完整ID/来源/哈希](GOLDEN_CLOSEOUT_50_AUDIT.json)。48题未发现新增实质错误；这不是正式质量批准。Negative无源行为依据与材料Anchor仍分开，真实整库边界必须由后续Probe验证。

## 2. 实质争议

- **Q09，P1待复核**：手册要求受损电池报废、彻底放电和专门回收，但没有安全放电操作方法。当前答案明确不授权自行放电；仍需确认该保守边界是否足够，不得编造厂家流程。
- **Q15，P1待复核**：手册支持手动清洁头单独激活和握安全开关推动，未明确原地静止刷洗的动作条件。答案保留该限制，不能保证静止转刷。

两项已通过现有`review_events`登记，绑定当前内容哈希，actor为`Codex AI / offline content audit`，decision为`content_review_required`，没有人工批准。即使后续QC给出高分/P2，也仍进入复核。人工批准必须明确填写处置结论；委托代审须有匹配当前内容、逐题哈希、Run/Corpus/Plan/Profile的独立有效授权。本次未取得该授权。

Q06/Q07/Q28维护隔离、Q13位置码唯一性范围、Q14急停/恢复边界、Q39未知液体均有对应依据。Q22正文“2秒以上”和图“2秒及以上”均真实存在，持久化等价表达已覆盖，不能机械把“至少2秒”判为错；仍由正式QC按来源核对。

## 3. Hard Validation实际状态

新版`golden-validator-v2.4-precheck-freeze`分开两个结论：

- **预检valid：50/50通过**，覆盖结构、来源真实性、原文定位、业务检查点结构及适用元数据。允许新版自然语言改写进入Probe/QC。
- **冻结freeze_valid：0/50**，当前没有正式语义审核/批准证明。伪造引用、来源版本错误、丢失负号及自带/过期语义证明仍被拦截。

Probe对治理内容使用预检，不再对参考答案作逐字Anchor比较。来源存在只证明来源真实；语义支持仍由QC与最终审核分别处理。保留真实检索观察、全文解析覆盖、负向可答性/子类检查。指定Golden Chunk未召回只记录检索风险，不宣称实际RAG一定答错。

## 4. Probe/QC离线整链路

隔离库复制当前50题；所有模型响应和人审动作均显式Fixture，未向正式库写入成功质量或批准记录。覆盖：

1. 全50题预检→Probe→QC→机器合格；无争议题无需逐题批准。
2. 复制当前两条真实待审问题时，48题机器合格、2题复核；高QC不能关闭问题，显式测试复核后整套Human Gate才可通过。
3. 未确认Human Gate不能冻结；确认后Fixture Snapshot的50题、参考答案与当前工作集一致，既有Baseline预检能读取唯一批准Snapshot。
4. Probe失败禁止QC，伪造QC引用/漏检查点禁止保存合格记录；任一题预检错误在任何付费阶段之前阻断全批。
5. QC84失败、85满足分数条件、95/P0失败、90/P1或安全争议需复核；已批准题新出P0也不能沿用旧批准。
6. 内容/Corpus/Probe/质量合同身份变化失效；复核另绑定实际QC记录ID，同题重新QC也不能沿用旧批准，旧委托不可用于新版；空/局部/未批Snapshot绕过失败。
7. 成功阶段和成功RPC恢复时复用；已知无效QC显式重试只更新失败阶段缓存，保留历史响应；执行/Usage未知先对账，禁止重复发送。
8. 现有后端批量入口能接收完整50题，未实际启动Provider。

核心9个模块共96项全部通过；扩展23个模块共**280项：278通过，2个历史错误**，不是全绿。两错误在`075cb51`同条件复现：

- `test_governance...test_governance_endpoints_block_review_until_probe_and_qc_pass`：旧API测试要求无工作Run时`/api/dataset`返回Legacy首题，与已有“只读当前工作集”合同冲突。
- `test_v14_probe_cost...test_r1_bm25_execution_failure_blocks_probe_and_evaluation_without_judge`：Baseline夹具`judge={}`缺少已有Generation Contract，尚未到检索失败断言即被预检拦截。

未修改Baseline代码或为历史测试放宽合同。另更新3个旧QC规则断言以符合85/P0新合同，并修正已有检索异常夹具把字典当Exception的传参错误。实际测试日志保存在本轮本地备份目录；确定性摘要见[验证JSON](GOLDEN_CLOSEOUT_VERIFICATION.json)。

## 5. QC85全部资格路径

统一常量`QC_THRESHOLD=85`、合同`golden-quality-85-v1`用于保存与资格判定；不接受调用方“passed”覆盖分数。资格列表/异常分类、单题批准、批量重跑筛选、质量迁移复用、委托审核、Human Gate与Snapshot入口使用当前质量身份。

P0不能接受风险后绕过；P1和未解决语义/安全争议须显式处置；无争议P2不单独阻断。条件项先判断触发，辅助项不当必答。QC模型必须返回全部必答/条件项的适用性、判断、理由和来源引用，后端核对覆盖及真实原文，不能用模型自述替代证据真实性。该机制只属于Golden QC，不修改正式Judge。

## 6. 现有批量入口与页面

`POST /api/governance/generation-runs/{run_id}/rerun-quality?anomalies_only=true`保留原路径。完整工作集已接到既有`completed`候选生成/预检状态，并用`working_set_completion`明确限定该状态；Probe/QC仍`pending`，质量通过/审批不能由Run状态推断。这样现有页面的批量按钮可用、完整工作集可审核，不需要改前端。

真实浏览器只读检查：MEDIUM50、20/10/20完整，Hard Validation显示完成，Probe0/50、QC0/50、Human Gate待处理；“批量重跑异常项”已启用，Q01详情显示当前新版参考答案。未点击付费/批准按钮。API亦核对50题与approved0。

## 7. Human Gate与Snapshot前置

冻结必须满足：完整原50题及Profile/Slot/Topic、当前Corpus、严格来源、当前身份Probe成功、QC≥85且无P0、全部检查点/语义安全争议处置、必要业务审计、无未完修订、有效人审或委托、整套显式Human Gate确认。成功机器审核不要求逐题点击；最终确认仍不可自动代行。

正式库当前approved Snapshot为0；现有`GD-GCONTENT-10c6ab67b1ef279d70b4f361`仍是待审快照，未篡改原历史Snapshot。未来Human Gate创建新的批准Snapshot，后续Baseline预检读取该唯一当前批准版本。本轮仅验证隔离链路，不执行真实Baseline。

## 8. 保护范围与备份

修改前用SQLite Backup API完整备份，`integrity_check=ok`且全表逻辑摘要一致：

`backend/data/audit_backups/golden_closeout_20261026/before.db`

SHA256：`47656e70fe26296587d8f14c628a757ae4018d131373821067c4bc9a10648c45`。

本轮正式库仅变更`questions`的派生Validation、`golden_generation_runs/artifacts`的预检/阶段衔接、两条AI待审`review_events`。题目业务字段及时间戳不变；Probe/QC/业务审计0，批准数量不变，旧实验与历史Snapshot表完全不变。额外活动元数据已备份。

111个受保护文件核对，仅`ai_service.py`和`main.py`中的Golden函数有差异；AST验证前者仅QC/业务质量审计、后者仅Golden批量质量Runner。正式Judge Prompt/Parser/PASSFAIL、默认生成Prompt、Baseline/Candidate、Agent/Sandbox/Regression/Recommendation、11 Gate、Pipeline、Production/Release/Rollback及前端未改。21个Corpus/索引/原PDF文件哈希不变，无Embedding/FAISS重建。架构节点/连线未变。

## 9. 未执行步骤与费用预检

待运行50题；既有合格质量记录可复用0。正常完整批次上限：50业务审计＋50QC＋18负向可答性＋2负向子类判断=120次DeepSeek，另50查询Embedding＋50 Rerank，共**最多220次请求**；负向无需额外判定、Probe失败跳过QC等情况会更少。失败停止，成功结果保留。

当前配置仍`deepseek-v4-flash`、`text-embedding-v4`、`qwen3-rerank`，未切换默认模型。DeepSeek官方说明旧Flash别名由当前V4.1-Flash服务；按峰值未缓存输入2元/百万、输出8元/百万估算。[DeepSeek官方价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)。Embedding/Rerank按0.5元/百万输入估算。[阿里官方计费示例](https://help.aliyun.com/zh/model-studio/billing-for-knowledge-base)。不计缓存/免费额度优惠。

离线捕获请求文本以UTF-8字节作保守Token近似：DeepSeek输入约537万字节Token近似，冻结输出上限合计1,875,968 tokens；Embedding约1.4万、Rerank约192万字节Token近似。按捕获文本和所有调用打满输出上限约**26.72元**，不是真实账单或严格运行上界；真实检索Trace与上下文会变化。建议单独授权**40元封顶**，逐请求预留实际输入和输出上限，预算不足停止。

此估算对应现有`controlled_run/PaidRun`受控调用Golden批量Runner：QC/可答性只尝试一次，外层及RPC自动重试上限0；Unknown/未结算停止，显式后续重试需先对账及另行授权。现有浏览器批量线程自身不携带独立PaidRun预算；有费用上限的正式执行须在同一受控上下文运行既有Runner，不能把本轮浏览器只读检查当作费用授权。没有新增费用UI。

旧Probe/QC、旧审批/委托、旧语义审核和旧冻结Snapshot不可作为新版通过记录。详见[逐阶段费用预检](GOLDEN_CLOSEOUT_PREFLIGHT.json)。

## 10. 停止条件

可以申请付费批量审核；尚不能冻结。剩余事项集中为：单独费用授权→真实50题Probe/QC及业务质量审计→Q09/Q15与运行产生的实质争议处置→真实Human Gate确认→新Snapshot。本轮停止，不继续改写Golden，不修Judge，不运行Baseline/Candidate，不发布。
