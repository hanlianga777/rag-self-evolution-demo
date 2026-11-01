# 2026-10-30 已授权 Golden 与其他Judge真实执行增量（最新）

**BASELINE_READY=false。** 用户对两项具体目的地和载荷已授权，正常工具审核通过后实际执行；不得再将授权说成缺失。

- Golden：18次RPC、零重试，Q13/Q15 Revision及质量阶段完成。Q36 Revision已应用、Probe通过，QC把Auxiliary Q36-R2加入仅允许Required/Conditional的checks，返回被严格校验拒绝，状态failed_quality；未伪造QC通过、未审核冻结。所有调用的Token/耗时和响应见[真实执行记录](judge_vnext_20261030/golden_authorized_execution/README.md)，实际费用Unknown。原历史行、旧Snapshot及另外47题保留；三题工作版本及新增质量记录已按授权变化，不能声称数据库完全未变。
- 其他12例：已调用10次，8次有效且符合预设；Q36正例与Q39正例均在Equivalent条目输出不允许的negative_behavior，程序记录技术异常、无业务判定；同题剩余两个反例未发送。0重试，逐例原子结果、Usage、耗时及Unknown费用见[摘要](judge_vnext_20261030/other_calibration_actual_summary.json)及各独立账本。Q15/Q22/Q24/Q49各两例均符合预期。
- 此前成功的Q13两例与本次样本均保留真实版本身份。现行Schema没有被放宽；Q36/Q39技术异常不能计成PASS或FAIL。历史50题Judge-only依赖新冻结Snapshot，尚未执行；正式Baseline仍未运行，且只能由用户本人在前端点击。
- 18次Golden额度已全部使用且要求零重试；处理Q36 QC失败、重新进行已失败的两次Judge样本需要新的明确调用授权。继续核查输出合同或Prompt不得修改金标准，亦不得用旧QC/人工标记绕过审核。

---

# 2026-10-30 本轮实施与验收汇总（当前状态）

**BASELINE_READY=false。** 本轮已实际修改代码、同步唯一正式SPEC、执行真实Q13与V2生成验证、完整离线回归和真实服务/页面验收，并完成本地代码提交。仍缺正式Golden QC/Probe→独立审核→新Snapshot、其他金标准真实校准及目标Snapshot后的50题真实Judge-only；自动权限审核明确拒绝了前两项材料外发，进程未启动，不能通过换入口执行。正式新版Baseline未触发，继续只能由用户本人前端点击。

## 六轮实际状态

| 范围 | 实际实现/验收证据 | 未完成或限制 |
|---|---|---|
| 1 Golden合同 | 全量只读适配、显式原子/AND/OR/触发/范围、完整Sources；拟修订50题全部编译，仅Q13/Q15/Q36计划内Hash变化、47题不变；9/9定向厂家来源可定位。受控Revision脚本含备份、质量身份、AI委托审核和新manifest冻结校验。 | 正式三题Revision/QC/Probe、新Snapshot未执行，不能把dry-run/提案当正式Golden。 |
| 2 唯一正式Judge | Candidate输入无baseline_findings锚定；逐原子语义输出、严格Answer/Final与check_type、确定性业务裁决、质量独立；Prompt6.1/Parser6.2；实质失败不可静默覆盖PASS。63专项通过。 | Q13-3/4真实各一次符合FAIL；上轮两个PASS保留旧参数/类型限制，其他12例仅已准备，不宣称全金标准通过。 |
| 3 证据/安全/回答 | Final/Canonical/Candidates角色隔离、适用性与逐字引文、全文安全；V2真实原文使用手册/章节/页码且无机器ID；历史/候选/QA展示可靠映射保存Final，未知/歧义显式未核验，原文审计完整。 | 一次生成是saved-context替身，不能冒充全库检索或完整语义质量；其他安全反例实校仍待外发许可。 |
| 4 Gate/Thinking/身份 | 11项阈值与质量权重保留，Q49/Q50冻结专项分母、全50安全检查；Generation/Judge Max与Candidate四档，真实请求/Usage身份、时延不含Judge；此前8个四档×stream微探针、本轮真实Max Judge/生成留证。 | 新Baseline未发生，P50/P99是否过门槛尚无结果；旧V1时延不授予V2性能资格。 |
| 5 Bad Case/Agent/UI | PASS诊断N/A、FAIL按题号去重；事实、技术诊断、优化假设分开，Unknown不硬称Retrieval；独立判分后Regression；实际原子与检索阶段数据交接；三Tab/800px抽屉保留且完整Case到达后更新。前端301项/构建通过，真实页面复验通过。 | 真实新版Candidate/Sandbox/发布未执行，仍未授权。 |
| 6 回归/恢复/冻结 | 1098项完整离线已执行并保留红灯；原25/28逐一映射；确定性P0/P1及合法fixture前置修复；剩余D生命周期P1通过完整HTTP及守卫6/6闭合，原47断言与生产规则不变。维护脚本的Unknown/缺Usage/audit/QC故障、单次请求和活动任务保护有独立离线证据。 | 全跑原结果仍12FAIL/2ERROR，另行D复测不能改写该日志；13个旧合同/历史fixture冲突P2继续留痕。50题真实Judge-only未执行。 |

## 四级证据与真实调用

- **配置/身份**：已提交核心代码693d9ca、UI b2e4b20；8010实际Prompt6.1/Parser6.2，安全模式PID64617；5174真实页面及15项Pipeline合同已核查。新Golden身份仍未生成，不能据配置验收宣布整体验收完成。
- **离线**：[完整1098项](judge_vnext_20261030/full_backend_regression_summary.md)＝1084PASS/12FAIL/2ERROR，exit1；[D后续6项](judge_vnext_20261030/lifecycle_d_fixture_closeout.md)全部通过，原47assert完全保留；当前分类的离线P0/P1均已处理，P2未删断言。原25→14PASS/9FAIL/2ERROR、原28→15PASS/11FAIL/2ERROR。后增两原子用例单独计入63专项，不混入1098分母；前端最终301/301、构建通过。Golden execute故障4项＋当时helper9项通过，新增活动Revision保护后最新helper10/10；Replay安全7项、其他载荷7项、V2探针4项通过，均明确离线。
- **运行态**：[真实8010/5174](judge_vnext_20261030/runtime_ui_citation_final/report.json)三Tab、800px抽屉、保存Final的人类来源展示、原始审计均可用；API只读、未点击运行。重载前无活动任务、SQLite Backup完成；[最后保护校验](judge_vnext_20261030/final_data_protection.json)显示29表/Corpus/Index/PDF未改，正式DB文件SHA仍与计划前一致。
- **本轮真实Provider共3次**：Q13-3、Q13-4各1次，15原子全覆盖，R4.1=MET/R4.2=NOT_MET、程序FAIL符合金标准；合计输入19172/输出30594（含推理26935），无重试、无截断/JSON错误。另正式V2/Grounded/Max/stream生成1次，输入723/输出1578（含推理1412），TTFT9502ms/Provider10263ms，原文有人类来源且无机器ID。均费用Unknown/null；原始业务响应/去私有推理的Provider记录与参数保留。后者只验证保存上下文生成，非完整RAG性能或Judge语义验收。

## 当前真实阻断及已备妥交付

1. **Golden外发scope待明确许可**：既有DeepSeek官方chat/completions与Alibaba北京embedding/rerank；50题面相似度、三题合同/公开片段/修订谱系/49peer业务元数据、动态最多12候选。已备[精确可审计划](judge_vnext_20261030/golden_execution_review_plan.json)与[安全运行说明](judge_vnext_20261030/GOLDEN_EXECUTION_SAFETY_AND_RUNBOOK.md)，最多18RPC、零重试；最新计划SHA `948148c840a18c0a963a89b0744a97a18048d2c0a9dc93146283b8a3557522d5`。后续安全修复只补失败checkpoint/活动Revision拒绝，目的地、外发范围及次数不变，原拒绝仍有效。质量失败或证据争议只保留现场、不能自动批准。
2. **其他12例Judge外发scope待明确许可**：Q15/Q22/Q24/Q36/Q39/Q49各2例，最小题目/合同/AI回答/必要公开手册片段，经DeepSeek官方目的地，最多12次、每例1次，异常或金标准不匹配即停。已备[预期表与逐例载荷](judge_vnext_20261030/other_calibration_prepared/README.md)，无Golden改写、无正式DB写。
3. **50题Judge-only依赖新Snapshot**：[历史源审计50/50完整](judge_vnext_20261029/judge_only_source_audit_20261030/README.md)，脚本已备且复用唯一正式Judge，只读原Answer/Final/请求/Corpus；不得自动造新目标身份或用旧无manifest Snapshot过关，结果不创建Baseline/不覆盖历史。

两项具体问题已通过当前会话提问组件提出；[权限拒绝记录](judge_vnext_20261030/permission_blocks.json)区分未发送的被拒操作与已正常获审的单次最小生成探针。没有GitHub推送，用户原有verify_self_evolution.py差异及未跟踪资产保留，历史数据未覆盖。这里不把仍未实施或未验收的部分写成已完成。

---

# 2026-10-30 Generation V2真实样本增量（最新）

本轮独立最小生成探针已获正常工具审核并完成1次、零重试，未复用被拒绝的Golden/其他题目外发路线。正式`AiService.answer` / V2 / Grounded / Max / Streaming / `REQUEST_LIMITS.answer=65536`，只发送普通问题及两段公开手册原文，无Golden参考、合同、评分原子或预期；未创建正式Run/写正式DB。

原始模型回答包含手册名、手动模式/提示章节和57–58页，无机器Chunk ID；没有后处理补加来源。输入723/输出1578，其中推理1412已包含输出；TTFT9502ms、Provider10263ms、保存上下文链路10273ms；费用Unknown。详见[真实样本及原始记录](judge_vnext_20261030/generation_v2_saved_context_real/README.md)。这只是明确SavedContextRetriever替身下的生成验证，不能冒充全库检索、语义Judge或50题性能验收。4项对应离线安全测试通过。

**BASELINE_READY仍为false**：Golden正式QC/Probe和新Snapshot、其他12例金标准及目标Snapshot后的50题真实Judge-only仍未完成；具体外发权限问题继续等待用户回答。后端D组合离线P1仍在处理。正式Baseline继续由用户本人前端点击，未代触发。

# 2026-10-30 引用展示与真实运行态增量（最新）

**BASELINE_READY=false，完整收口继续。** 本节记录真实代码与验收，不代表Golden正式Revision、新Snapshot或50题Judge-only已完成。

- 修复历史Baseline/Candidate及问答正文仍显示机器Chunk ID：只按本次保存Final的Child/Parent/别名映射文档与实际页码；缺失/歧义显示来源未核验，原始回答在关闭的引用审计中完整保留。评分与历史存储不变，未借Golden或全库补证。
- 修复轻量列表打开的Baseline抽屉在完整Case到达后仍持旧对象：按当前run同题保存记录更新展示。异步回归先RED再GREEN。生成V2仍约束模型直接输出人类来源；本展示修复不冒充新的真实V2生成样本。
- [前端完整回归](judge_vnext_20261030/full_frontend_regression_final.log)301/301 PASS，[生产构建](judge_vnext_20261030/frontend_build_final.log)通过；独立增量复核16项通过、未发现P0/P1。复用原组件/三Tab/800px右抽屉，无架构节点或阈值变化。
- 8010已安全重载已提交693d9ca的后端，PID64617，实际Prompt6.1/Parser6.2；5174真实三Tab/抽屉/保存Final引用展示通过，[截图与记录](judge_vnext_20261030/runtime_ui_citation_final/report.json)。正式Baseline未触发，所有页面验收请求只读、Provider0。
- [数据保护](judge_vnext_20261030/runtime_and_data_protection.json)：重载前无活动任务，SQLite Backup API已备份；29表指纹及Corpus/Index/文档文件Hash不变，正式DB文件仍匹配Golden计划前SHA，拒绝的Golden执行未启动进程/账本，历史均保留。
- [后端完整回归](judge_vnext_20261030/full_backend_regression_summary.md)：1098项/1005.067秒，1084 PASS、12 FAIL、2 ERROR，退出1；不宣称全绿。13个旧预期/历史fixture冲突为P2留痕，现代HTTP D组合准入的P1仍在继续处理。原25已逐项映射14PASS/9FAIL/2ERROR；原28为15PASS/11FAIL/2ERROR。后增两项原子测试只计入63专项，未混入1098分母。
- [拟修订50题结构复验](judge_vnext_20261030/proposed_frozen_50_contract_compile.json)：50/50编译，47题Hash不变，仅Q13/Q15/Q36计划变化；这不是正式冻结或质量批准。
- 自动权限审核在进程启动前拒绝两项真实外发：[记录](judge_vnext_20261030/permission_blocks.json)。①三题Golden QC/Probe需要50题相似度、同卷元数据及选中公开手册片段外发到既有DeepSeek/Alibaba目的地；②其他Judge校准缺Q22等具体材料外发许可。已提出具体scope问题，未换入口、未重试被拒动作。12例[可审校准载荷](judge_vnext_20261030/other_calibration_prepared/README.md)已离线准备；50题[原Answer/Final源审计](judge_vnext_20261029/judge_only_source_audit_20261030/README.md)完整，但真实回放须待新目标Snapshot。

# 2026-10-30 Q13剩余两次授权执行与合同修复（最新增量）

**当前仍为 BASELINE_READY=false，完整收口继续执行。** Q13-3重测与Q13-4首次调用已按新增授权各执行1次，均有效并符合预设FAIL，未自动重试，未修改Golden或预期标准。正式Baseline未启动。

| 样本 | 正式请求 | R4.1 / R4.2 | 程序裁决 / 金标准 | 输入 / 输出Token（已含推理） | 推理Token | 耗时 | 实际费用 |
|---|---|---|---|---|---|---|---|
| Q13-3 | deepseek-flash / Max / JSON / 65536 | MET / NOT_MET | FAIL / FAIL | 9580 / 14606 | 12715 | 77.273秒 | Unknown |
| Q13-4 | deepseek-flash / Max / JSON / 65536 | MET / NOT_MET | FAIL / FAIL | 9592 / 15988 | 14220 | 81.500秒 | Unknown |

- cap来自正式REQUEST_LIMITS；两份输出均覆盖15原子并显式check_type，finish_reason=stop。原始业务响应、Provider响应（不存私有推理正文）、原子解释、Token和请求记录见[本轮校准](judge_vnext_20261030/q13_remaining_calibration/README.md)。上轮两个PASS使用16384和旧输出合同，其参数/类型限制继续保留，不能冒充本轮同版本四例验收。
- 修复完整Prompt模板遗漏原子数组/issue关联字段，Prompt为6.1；新原子结果类型必须显式。另以RED→GREEN复现并修复“实质失败check未映射却覆盖为PASS”，Parser为6.2。辅助遗漏、未触发条件和合法OR遗漏保持原标准；无法一致时技术阻断，不编造业务FAIL。
- [63项专项离线测试](judge_vnext_20261030/atomic_output_contract_tests.log)通过；独立代码复核未发现P0/P1。两份真实响应保持原样，经6.2[离线复验](judge_vnext_20261030/q13_parser_6_2_offline_revalidation.json)仍为FAIL，新增调用0。
- 正式Golden Revision执行脚本、完整50题历史回放脚本已准备；当前阶段尚未正式应用/冻结，完整后端回归正在独立临时存储中运行。其真实结果在后续增量中记录，不能据本节授予Ready。

# 2026-10-29 Q13 专项授权执行增量（最新）

**BASELINE_READY=false，专项未完整通过。** 已按用户对指定目的地/四组载荷的直接授权执行真实Q13校准，实际3次、无重试；第3次length截断后立即停止，第4组未发送。没有重新执行任何已调用样本。

- Q13-1：有效，LLM与程序均PASS，符合预期；Q13-2：有效，LLM与程序均PASS，符合预期。两次wire请求SHA相同，原子state/trigger和有效fact类型一致；第1份响应15个check_type字段缺省、程序按严格fact默认处理，第2份显式fact，不夸大成全部字段遵从一致。
- Q13-3：finish_reason=length，输出16384 Token全部用于推理、最终content为空，技术NOT_EVALUABLE，无业务PASS/FAIL。费用Usage已保存，不能记为业务FAIL或声称模型已判对/判错。
- Q13-4：未调用，因异常即停，不能算完成或失败。
- 三次实际输入28375、输出37115 Token；推理已含在输出中。Provider调用耗时47201/63859/93630ms，均为Judge耗时，不能算RAG Latency Gate。实际费用未返回，保持Unknown；旧账本spent_yuan=0不表示免费。
- 本轮发现校准脚本硬编码16384，低于项目正式REQUEST_LIMITS.judge=65536；Thinking确为Max，但输出上限未完全符合正式配置。这是工具实现错误，不归咎于金标准或模型语义。已离线改为读取统一65536、精确指定接口、重复样本ID拒绝；后续仅dry-run，未重跑3或自动发送4。
- Provider通用解析已修复：先识别length，保存finish_reason/HTTP元数据/已知Usage与原文，输出output_truncated技术分类；已有非空部分响应继续保持原格式。不是放宽引用或改变业务判分，不按题号写例外。
- 本轮修复与证据已本地提交 `6dc2c58`，未push。8010已安全重载到该源码，暴露的Validator/Parser/Scorer指纹和Prompt一致，29张正式表哈希仍无变化；见本次校准目录的runtime_and_data_protection.json。修复没有新增真实请求。
- 56项传输/费用/恢复回归通过（含新增3项RED→GREEN）。见q13_transport_regression.log。新dry-run见q13_post_fix_dryrun.json（65536未真实执行），原请求记录不改写。
- 另：现代离线Sandbox50两项及3项当前治理回归均通过；Lifecycle到D时仍被上下文恢复保护拒绝，保留原断言，不强行制造D。见modern_fixture_and_current_guard_closeout.md。

真实调用逐样本结果、原子判断、载荷范围、请求参数、Usage、耗时与费用状态见 `provider_q13_authorized_calibration/README.md`、`calibration_summary.json`、原始report/ledger/response。本次新增3次，加此前8次微探针，累计本轮系列真实请求11次；不等于11次完整业务校准。

正式Golden仍未Apply/QC/Probe/审核/冻结，无新Snapshot；其他真实金标准及50题Replay未执行。正式Baseline/Candidate/Sandbox/发布未执行，GitHub未push。总体任务未完成；下方早期“4例仍待授权”的状态是历史记录，已被本节覆盖。

---

# 2026-10-29 最新收口状态（本节覆盖下方早期状态）

**BASELINE_READY=false。** 已实施并验证更多核心代码，但正式Golden Revision/新Snapshot、真实业务Judge校准、50题Judge-only Replay及回归阻断尚未完成。不得据已有微探针或结构覆盖宣布完成。

## 当前真实证据

- 核心集中回归：`final_core_targeted_tests.log`，118项通过（包含继承重复用例），0.720秒。显式AND/OR、Q13通用子原子结构、条件/辅助/禁错、Negative纯行为与事实支持隔离、真实Final引用、manifest内容绑定及新入口保护等均有确定性测试；不等于真实LLM语义通过。
- 最后一次全量：`final_full_source_tests.log`，1063项/900.815秒，17 FAIL、14 ERROR。之后3个旧fixture模块按新合同补前置并严格保留业务断言，定向28/28通过；另有Negative纯行为增量定向通过，未再次全量。故不能声称最终源码全绿。
- 原28项异常已有逐项P0/P1/P2矩阵与before/after复现。冻结题异常重跑选择缺陷已修复并独立RED→GREEN；Q02 validate转发缺陷两项通过。原异常选择集仍有21项未通过；后续合法Ablation前置使20题复用测试通过，其余具体状态见triage增量，不能把全部归为历史问题。
- 前端：全量295/295通过；最终定向36/36及TypeScript/Vite构建通过。真实5174页面三Tab/800px抽屉已验证，0页面错误、0 API写请求、0正式Baseline触发；见runtime_ui/report.json及截图。截图为历史保存Run，不是新Judge或新生成成绩；历史原始回答中的索引仍保留，不伪称新生成已验证无机器ID。
- 8010已安全启动现行v6/atoms4/固定安全统计版本，已重载到源代码提交08eddb8；最后一次暴露的Validator、Parser、Scorer三指纹及包含Negative纯行为增量的Prompt哈希均与当前源码一致。服务启用RAG_SAFE_START=1，未自动迁移/清理/恢复评测。
- 正式DB用SQLite Backup API备份；29表重载前后逐表行数/内容哈希一致。当前Corpus/Index身份与原Snapshot一致，4份PDF SHA全部匹配冻结来源。未做任务开始前整份二进制索引的哈希对比，不能将身份检查夸大为该证据。
- 真实Provider微探针8/8成功：OFF/Low/High/Max各stream/nonstream；输入1302、输出1183 Token（推理965已含在输出中，不重复加）；0重试、0 Unknown。实际费用API未返回=null，不能将旧ledger.spent_yuan=0说成免费。只回显deepseek-flash，未回显资源档位确认；证明精确请求被接受，不证明服务端推理资源或质量等价。资料在provider_20261029T124912Z/。
- 4例Q13完整Judge Max校准已准备、dry-run安全验证；实际新增调用0。自动审批先后拒绝，最新理由为未明确批准具体项目题目/答案/证据载荷与目的地。已向用户提出4次、既有官方 https://api.deepseek.com/chat/completions、具体载荷的批准问题；未获回答前不重试、不换路径。此前一般业务授权并非用户撤回，当前限制来自自动审批。

## 六轮验收矩阵

| 规范要求 | 代码/关键函数 | 实际变更 | 测试及结果 | 真实Provider | 阻断/遗留 |
|---|---|---|---|---|---|
| 冻结五类合同和来源 | scoring_contract.compile_contract | 完整原文、原位置、Hash、来源引用；50原题结构编译 | schema2_original_snapshot_coverage.json / 50结构可读 | 未逐题 | 不是50题真实语义验收 |
| 原子/AND/OR | compile_contract/adjudicate_contract | 显式atoms保留父ID，AND全满足、OR合法完整路径；未知嵌套拒绝而不丢义务 | ExplicitLogicTests通过 | 未校准 | Q13正式Revision及复杂路径校准待完成 |
| Q13/Q15/Q36 Revision | governance.reopen_snapshot_question及既有Revision | 仅明确授权原Snapshot精确匹配可重开编辑版；不改旧Snapshot；Diff含合同 | 副本3题preview_ready，正式DB不变 | QC/Probe未执行 | 无新正式Snapshot；不冒充冻结 |
| 必答/条件/辅助/禁错 | adjudicate_contract | 未触发N/A、辅助遗漏不单独FAIL；未知/缺项为技术未完成 | FrozenContractTests/ExplicitLogicTests通过 | 未逐题 | 真实金标准未通过 |
| 唯一程序裁决 | validate_business_judgment | 新原子状态及实质issues计算；保留旧只读/离线兼容 | JudgeWiringTests、旧Judge61项通过 | 微探针非完整Schema | 完整Judge JSON校准被审批阻断 |
| Negative合法拒答 | adjudicate_contract | 显式negative_behavior纯行为Required免Final事实支持；事实不得免检 | NegativeBehaviorAtomicTests通过 | 未校准 | Q39/Q49等全文语义未验收 |
| Answer/Final真实性 | adjudicate_contract、原quote_present | 连续真实引文、实际Final来源；不以Canonical/Candidate补证 | 伪引文/缺失测试通过 | 未逐题 | 文字真实不等于业务支持 |
| 全文安全/范围 | 原统一Judge Prompt及Guard | 保留全文、对象/型号/否定/条件审查；不按Q号写判分 | 现有安全/核心fixture回归 | 未完整语义校准 | Q22/24/25/39/49正反集仍待 |
| 引用表达 | ai_service.generation_boundary | V2自然文档/章节/页码，消除Chunk指令冲突；V1原边界不变 | Generation测试14项通过 | 仅微探针 | 未验证真实V2业务输出 |
| 安全专项分母 | evaluation.summarize/gate_details | 冻结negative_subtype，新旧统计版本分开 | FrozenSafetyTests/HistoricalGateTests通过 | 不依赖 | 全11Gate端到端仍有未闭合测试 |
| 缺失指标/延迟 | summarize_evaluation_cases | 缺质量或部分时延不凑均值；原阈值/Overall不变 | MissingMetricTests通过 | 8微探针有耗时 | 无新版Baseline性能成绩 |
| 共同合同/实验身份 | VERSIONS、snapshot_manifest、baseline_inputs | v6/atoms4/Schema2，manifest绑定逐题Hash；真实当前生成入口验证 | Manifest/Draft/Thinking等新前置模块通过 | 四档请求接受 | 新正式Snapshot、完整模型回执验收待完成 |
| 后置Regression | compare_cases、atomic_failure_keys | 精确缺陷及同Hash/同谓词/同omission对应；升级或不明继续阻断 | StableAtomicRegressionTests等通过 | 不依赖同次锚定 | 其他语义缺陷对应仍不能虚构 |
| PASS/BadCase/Agent | diagnostics及前端共享businessVerdict | PASS不作为失败目标；未完成不显示PASS；按题ID去重 | 核心及前端295通过 | 不依赖 | 新运行全链路Agent交接未完整验收 |
| UI与运行态 | EvaluationPage/EvaluationDiagnosis | 保留三Tab/共享Drawer，显示保存原子事实，不改原始答案 | 真实本地只读smoke通过 | 0调用 | 新Golden/新运行页面未产生 |
| 安全启动与数据 | safe_start原路径、显式重开、质量重跑筛选 | 默认不迁移/恢复；冻结golden排除异常重跑 | P0保护3项、重开1项及hash证据 | 0隐式调用 | 部分恢复/线程/历史fixture验收未闭合 |
| 金标准/Replay | 校准脚本dry-run及样本manifest | 样本标注AI构造、真实来源；不套旧Judge成绩 | 3个脚本安全测试通过 | 完整业务调用0 | 4例审批阻断；50题未运行 |
| Provider路由/Thinking | production complete_with_metrics | 有界8次真实请求，Usage/响应/账本、无原始推理或凭据 | 8/8微探针及redaction检查 | 已部分验证 | 不替代Generation V2+完整Judge验证 |

## F01—F10

F01结构接线已实现，真实逐题判分待验；F02固定专项分母和历史兼容已实现；F03专项各1题局限保留；F04口语鲁棒性不是严格因果消融；F05电气对象/OR仍须语义校准；F06 Q22同源措辞已见原冻结来源但真实校准未完成；F07 Q25电池关闭与充电器交流侧供电的范围尚未正式Revision；F08 Q36有原页与副本提案，无新冻结；F09历史manifest不回写，当前身份/4PDF SHA验证一致；F10不以关键词未命中证明全Corpus无语义答案，真实新Probe尚未执行。

正式Baseline、Candidate、Sandbox、发布均未启动，GitHub未push。源代码与SPEC本轮收口提交08eddb8，用户原有scripts/verify_self_evolution.py未纳入提交，保持16行新增/14行删除的原始Diff。已请求在Codex打开Baseline页面，工具返回queued；未自动点击运行。该状态不是全部任务完成声明。

---

# Judge VNext 实施记录（未完成）

基点：本地 main / 2403e63。用户原有 scripts/verify_self_evolution.py 修改及未跟踪资产未纳入本次修改。

## 已实施

- Candidate Judge 不携带 baseline_findings；统一输入构建器也排除该字段，提示词与 Provider Parser 不再要求同次旧缺陷对应。新 judge_input_version 为 independent-frozen-contract-2。
- Safety Critical 汇总与 Gate 详情按冻结 negative_subtype 选择，新增 gate_statistics_version=frozen-negative-subtype-2，进入评测身份；Regression 的 critical 规则保留。
- 业务 PASS 的失败诊断返回 not_applicable，无优化目标资格。
- 六轮冻结目标合同合并到唯一 SPEC，保留历史条款及最新执行授权；写入不代表六轮已验收。

## 测试证据

新测试 test_judge_six_rounds.py：三项均先复现失败，再修复通过，包含固定分母、PASS诊断与角色独立输入。现有 test_evaluation_vnext.py：61项通过（统计身份字段增加前执行）。

隔离全量：1020项，14 FAIL、16 ERROR，耗时292.005秒。完整日志见 judge_vnext_20261029/backend_full_tests.log；该运行显式隔离 DB、Index、Documents、Uploads、ENV 并使用 RAG_FORCE_MOCK=1。测试数量与旧1015项不同，未完成原25项逐项对应及修复，不能认定全部历史异常。隔离空索引/文档也可能影响结果，须逐项核查，不能将本结果冒充生产索引损坏。

## 尚未完成且阻止 Baseline Ready

只读原子合同适配与程序裁决、独立评分后缺陷映射、50题来源覆盖、Q15/Q36受控Revision与新Snapshot、前端回答索引隐藏、完整身份与恢复回归、30项当前失败/错误分级、真实Provider校准及50题Replay、运行态和历史资产前后保护校验均未完成。

持续FAIL的缺陷对应缺失时原比较器保持 comparison_complete=false，不放宽资格。不能将独立输入修复宣称为完整Regression迁移。

本轮实际生产Provider调用0；未运行正式Baseline/Candidate/Sandbox、未推送。运行态未复验最新代码，现有监听进程未替换。本记录为中间实施状态，不是最终验收或Baseline Ready声明。

## 冻结合同核心接线增量

- 新增 backend/app/scoring_contract.py，冻结五角色只读适配、原始位置、来源与合同Hash。实际只读查询 dataset_versions 中 GD-20261027070931，50题结构编译全部成功，逐题结果见 judge_vnext_20261029/frozen_contract_coverage.json。此结果不是50题真实Judge校准。
- Judge输入、Provider Parser、Runner评分接入scoring_contract与atomic_results。检查点缺失/重复/UNRESOLVED、触发状态冲突、伪造Answer/Final引文阻断；必答、触发条件或禁错决定程序业务结果，辅助遗漏不单独失败。保留全文实质问题检查。
- 正式输入版本更新 independent-frozen-atoms-3。尚未完成Q13复合义务拆分、Q15/Q36来源Revision及冻结、AND/OR显式逻辑编译；未具备Baseline Ready。
- compare_cases可在评分后识别完全一致的结构化缺陷，不改持久化Judge输出；语义改写与非精确对应继续comparison_complete=false，完整后置映射尚未完成。
- test_frozen_scoring_contract.py：12项通过（含继承重复5项）；test_judge_six_rounds.py：4项通过；test_evaluation_vnext.py：最新身份下61项通过，耗时0.739秒。此前1020项全量结果不代表此次增量回归，需重新完整运行并处理异常。
- 当前尚未进行真实Provider调用、Golden正式写入或运行态替换；生产数据库仅使用mode=ro查询，未执行正式Baseline/Candidate/Sandbox。

## 后续验证与引用表达

- 首批核心本地提交 b213fec 已成功，未push；用户脚本改动保持未提交。
- 辅助遗漏不能由旧checks覆盖冻结原子结果，新测试先失败再通过；最新核心13项（含继承重复）通过。
- Generation V2表达要求真实文档名/章节/页码，不输出机器Chunk ID；原始Answer与Final不做字符串清洗，边界SHA按现有机制改变。生成测试13项（含继承重复）通过；旧Judge61项通过。尚未验证模型实际遵循和历史页面显示。
- 前端49文件289测试通过，TypeScript/Vite构建通过。
- 授权只读访问5174为HTTP200；8010 /health为404（路径不存在），/api/evaluation?light=true为有效JSON，实际加载judge_input_version=frozen-canonical-norms-1，未加载新源码。进程PID29401命令与本项目uvicorn匹配；未停止或替换。不能算新版本运行态验收。
- 正在使用scripts/test_v14_offline.py重跑全量，复制Legacy fixture并封锁出站TCP；旧1020项空索引结果不作为本次最终回归。
- 原30项异常原始身份与堆栈已提取至test_anomalies.json，尚未逐项根因分级。

## 历史兼容与厂家原页核对

- Gate详情API按Run保存的统计版本读取；新运行固定专项集合，旧运行保留旧severity统计解释。新历史兼容测试先失败后通过，首批测试共5项通过。
- 使用内置PDF运行环境只读提取厂家原PDF第57/58/92/93页，保存PDF SHA与原页文本；见q15_q36_vendor_pages.json。
- Q15/Q36定向字段提案见golden_revision_proposals.json。提案明确尚未治理apply、QC/Probe、审核或冻结，未创建新Snapshot，不冒充正式修订。
- 上述来源文本支持修订方向，不证明设备事故因果或其他未经原文支持的新要求。

## 全量运行器最终结果

项目自带离线运行器完成1040项，12 FAIL、16 ERROR，耗时930.410秒。完整日志backend_legacy_fixture_tests.log。此轮解释器在后续历史Gate兼容及辅助项增量前已导入模块，因此不是最终源码全量通过证明；增量另有定向通过证据。

与此前空隔离目录1020项运行按测试身份比较：28项异常共有，无新增异常身份；2项仅在空隔离运行出现，详见test_identity_comparison.json。不能把这两项算作产品修复，也不能据此声称与原1015项历史运行完成对比。28项异常尚未完成根因分级与修复。

本次真实Provider调用仍为0，正式Baseline/Candidate/Sandbox未启动。Golden仍为原Snapshot，Q15/Q36仅有原页证据和修订提案；真实校准、50题Replay和新版本运行态未完成。最终准入结论：NOT READY。
