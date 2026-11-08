# V5 评测合同、通用归因与Medium50收口——第一阶段验收

日期：2026-10-21。实施基线：`09993bae`。本轮仅离线实施；真实Provider调用0，未触发正式Replay、Q18恢复、Medium50、Agent、Sandbox或发布。正式服务没有重启，隔离API/源码/构建验收不冒充旧进程已经加载新版。

## 1. 已解决的通用根因

- 正式引用合同将Fact正文与Scope来源范围分开。Fact只能证明真实Final连续原文；Scope绑定实际Final条目与Canonical标题来源、产品/版本/文档及真实页序/结构，不能用任意metadata或修改页码重新绑定。
- 冻结Golden摘要与完整规范分开输入Judge，按原source_chunk_ids读取同身份完整Corpus。保留原摘要与来源角色，不将规范伪装为检索Final。
- 诊断不再要求未来案例存在预置人工审计JSON。新增受控语义补证、程序来源验证、原子事实阶段覆盖和独立持久化；模型根因标签不参与程序决策。
- 新版Judge-only Replay复用真实生成执行，重新判分并建立新Identity与普通正式Baseline，复用原重试/Checkpoint/Stop/Gate/当前Baseline守卫；不复制旧Judge、verdict、quality、评分或Gate。

四个评估维度、五类典型Bad Case、原单一Optimization Agent与完整业务链不改；不加一级类别或工作台。24个受保护文件逐字节SHA相同，包括整库、原PDF/索引制品、Gate/Search Space定义和历史审计事实JSON。

## 2. Q18 Fact/Scope合同与严格性

新版输出可用：

```json
{"check_type":"scope","requirement":"R3遥控器","met":true,"answer_quotes":["R3遥控器"],"support":[],"scope_support":[{"source_id":"实际Final Child","heading_source_id":"真实Canonical标题Child","quote":"R3遥控器"}]}
```

这里的ID仅展示结构，不能代替真实绑定。显式scope要求逐字等于单个真实标题、答案引用识别该标题；操作/参数/安全事实不能借此免除正文support。没有这种逐字标题的答案可在正常fact检查附scope_support解释范围，不强造标题检查。所有scope_support均核真实来源，auxiliary范围项也不能夹带假引用。

保存的Q18中，R3标题 `DOC-003-C-00004` 可合法解释校准Final `DOC-003-C-00009`/`C00008`，R1标题 `DOC-003-C-00018` 可解释安装Final `DOC-003-C-00022`/`C00025`。前三项标题不在绑定正文中，新的Scope验证通过而原Fact定位仍为false；C00025的Parent正文确实还包含标题文字，应按真实正文记录，不能概括为“所有标题都只在metadata”。没有向Final.content拼标题，没有放宽逐字匹配，也没有删checks或改原始verdict。

反例涵盖错绑R1/R3、跨产品/版本、伪造scope metadata、改页码、Parent同页跨两分支、标题冒充操作事实。全部拒绝。可验证范围目前包括既有独立型号标题与Canonical显式heading/title；无结构来源的章节或未知现场适用性仍须保持阻断，不宣称程序理解任意标题。

Q18两份旧原始响应仍保存为技术异常，旧历史未补PASS。新版真实Judge能否按新合同正确引用与判业务，须第二阶段真实小样本验证，Parser通过本身不代表业务判断合理。

## 3. 新案例的通用Evidence Resolver

`resolve_case()`输入真实冻结题目、同身份Canonical完整规范、完整三阶段、回答及原checks，先验证实际来源。不能确定语义等价/复合事实/范围时返回`needs_semantic`和具体缺口；不把字符串未命中当作无适用证据，也不猜Scope=true。

显式授权后最多一次既有Provider语义调用，模型返回：必要原子事实、冻结引用、规范适用性、各阶段complete/partial/absent/unresolved、审过的完整阶段ID集合、真实引文和回答覆盖。程序校验来源/阶段/产品/版本/文档/型号分支、Golden与失败checks覆盖、字面反证及请求身份，再推Retrieval/Ranking/Generation。无法闭合保持阻断。语义真实性依赖后续真实Provider质量验证；来源校验不能证明模型所有语义推断正确。

复合check的已满足子事实不会因原check=false被整体否定，完整Final支持会保留为`preserve_support`，约束后续上下文策略；只对未满足子事实形成finding，所有必要子事实均满足却原check失败时才报告语义矛盾。原`critical`不变，不据此凭空转Safety。

测试在没有`diagnostic_evidence.json`新记录的情况下覆盖三种根因、复合部分已答、同义规范、相同产品不同型号分支、未授权/未闭合、伪造来源、部分覆盖、模型虚报根因、随机题号/来源ID与新规范文本、跨Run/配置/Corpus/Identity失效。Mock语义样本不是新的真实模型能力证明。

独立sidecar默认位于数据库同级`diagnostics/`，可用`RAG_DIAGNOSTIC_DIR`隔离。绑定Run/题目、Case、冻结Snapshot、全Corpus/全阶段/回答、配置、Evaluation Identity、Resolver版本和语义Prompt SHA，保存原语义响应/Usage/错误；读取重验，变化即失效。SQLite历史行不改。API投影补Run/题目身份供诊断读取，不回写原JSON。原10题审计JSON只保留作历史解释与回归，仍各自溯源。

GET诊断/预检不调用模型；POST补证须显式authorize_provider，现有Drawer费用确认可发起。新Case尚无语义授权或有效结果时保留具体诊断任务，不能承诺自动100%归因。Negative纯行为与无可定位必要规范的情形仍单独阻断，不能拿Anchor补事实。

## 4. Q29与其他完整规范输入

Q29冻结摘要仍160字，实际规范 `DOC-002-C-00056` 为419字；新版Judge同时收到原摘要及完整419字，明确`normative_requirement_only`。冻结Golden、RAG Final和旧Judge输入没有回填。

逐题清点50题，30道正向/消融题共54个冻结来源引用全部从同身份Canonical读取全文，不再按160字截断。JSON保留每题每来源全文长度与原摘要，对多项列表/多来源跨段同样适用。20道Negative仍按预期行为处理，Anchor不作为事实答案。

这解决的是已冻结来源ID所指原文的输入截断，不能自动补造Golden未冻结的邻段规范或证明所有语义要求已经完整。未来新Revision取消无条件[:160]；回归把必要答案放在第160字之后，验证预览仍成功保留全文且原题不变。旧Revision与Snapshot未改。

## 5. Judge-only Replay逐题资格与正式身份

- 可复用 **50/50**：49份已评分记录的真实生成数据 + Q18保存generation execution；没有不可复用题。
- 每题检查原问题/参考/类别、回答、成功generation Usage与请求SHA/模型、Pipeline/配置/Corpus、三阶段全文Canonical/来源、Rerank到阈值/Parent/TopK的确定性Final派生、未知生成请求状态；不仅检查数量。旧Judge异常不影响已知成功generation的复用资格。
- 原运行缺少显式request_limits快照，但有成功generation请求SHA、requested_model与已知Usage，执行模型/temperature/Embedding及完整配置/Trace可核验；没有伪造历史输出上限。新版请求上限另行冻结进新Identity；复用并不再请求生成。
- 任一题不合格则不创建整轮正式Replay，给逐题blocker；不静默重新生成。创建事务再次核当前Golden/Production及旧源摘要，只种入execution与空的新attempts。旧判分不复制。
- 临时库副本内50次独立Mock Judge、0次生成，50/50完成并通过`require_current_baseline()`及原11 Gate聚合。不是只改UI状态。删除execution后及其显式恢复子Run均阻断，未调用生成；不构造假Completed。
- 性能字段明确来自历史生成，页面与结果标记，不当作本次生成实测；新Judge Usage单独保存。

[完整逐题资格/规范清单/Scope校验/预算](../outputs/medium50_contract_resolver_replay_v5_20261021/replay_preflight.json)。真实正式库仍只有旧Partial，旧49成绩+Q18异常；Mock成绩未写正式库。

新版版本：`judge-vnext-5-fact-scope` / `business-output-5-fact-scope` / `evidence-vnext-2-fact-scope` / `frozen-canonical-norms-1`。

新版Evaluation Identity：`e7ff2e15737521518b0104dcf3d253a9726d7809fa77947f6325804e88f8119c`。
旧V4 Identity：`d18aab6365a63c6de63e295866a7036e0fe6a25f1f74c2afbb4782bbab73ae3e`。旧Partial在V5下禁止续跑，新旧分离；新V5 Replay如中断，只能按自身同身份显式恢复并继续禁止生成。现有非正式answer_replay保留独立历史工具语义，不能替代这个正式Baseline流程。

前端原Baseline页新增“新版Baseline判分（复用回答）”只读预检、逐题资格与新身份展示，资格全部通过后仍须费用确认，再次实时预检后才POST；旧Run不显示为可续跑新版。未删除任何业务FAIL或技术异常。

## 6. Q27扩展方案与当前能力边界

当前仍Ranking，现有16种固定池上下文组合不可恢复，仍`target_eligible=false`；未向Agent伪造可用context_selection方案，未改Search Space。

离线仅用原问题与保存Candidate正文，复用已有BM25算法在池内重排，再按原Parent展开。选取阶段没有Golden答案、缺失规范或目标Chunk ID输入；之后才用已审事实作留出验证。核心地图规范进入新排序第1，Top4/Top6都补全4项缺失规范并保留原已满足事实。这只是query-only lexical复排的单例上下文可行性，不是回答改善、全50不退化或上线资格。

建议下一阶段优先评估“保留问题词面覆盖的受约束重排/选择”，先做全部保存Trace反事实覆盖及噪声比较，再单独审批参数/实现/真实Sandbox与Regression。查询扩展或Hybrid也可有跨阶段因果假设，但本题原池已命中、Hybrid已开启，单纯声称扩大召回能修Ranking缺乏新增证据，本轮不执行。规范/目标ID只参与离线评价，不注入在线检索。

[Q27离线可行性数据](../outputs/medium50_contract_resolver_replay_v5_20261021/q27_feasibility.json)，可复现：`python3 scripts/probe_context_selection_offline.py --run EVAL-20261021013401711966 --question V1G-110926448917-27-R123429216749`。

## 7. 历史保护与验证记录

[历史10题诊断](../outputs/medium50_contract_resolver_replay_v5_20261021/historical_fail_diagnostics.json)：Q03/Q04/Q06/Q08/Q27=Ranking；Q07/Q17/Q24/Q28/Q29=Retrieval。Q08不退化，Q27继续阻断。原49成绩/10FAIL/原始Judge/Checkpoint/Golden/Corpus/Gate定义与参数域不变。[完整性SHA](../outputs/medium50_contract_resolver_replay_v5_20261021/integrity.json)，整库SHA仍`983488ce11505c8d1e8e94677a6619a8b48f0bed23ecf57cccc869f0629d0e46`。

最终全量后端818项通过（380.227秒，0 failure / 0 error）；最新范围/Resolver反例28项单独通过。此前一轮809项全量也通过。前端44文件250项通过，TypeScript/Vite构建通过。旧200条离线响应仍157 PASS/43 FAIL、Provider0，不能冒充V5真实Judge成绩。首次全量发现旧测试硬编码V4版本、私有Legacy记录不属于当前Corpus，以及API投影增加Run身份的预期变化，按新合同仅调整夹具/断言；未为测试放宽正式来源守卫。既有异步测试清理竞态与被注入的错误日志不代表实际Provider运行。

独立只读代码评审发现的复合check聚合、Final派生链两项P2均补红后绿并复核通过；额外页码/同页多分支反例也通过。无新依赖、无新Agent、无新数据库表。图的节点/关系未变，正式图源未改；架构文本同步。

## 8. 下一阶段调用、费用与授权前置条件

本轮到此停止。下一阶段先实时核服务加载版本/新Identity、当前Golden/Corpus/Production与逐题资格，核价格和用户预算，不沿用本轮0调用授权。

1. 单独授权Q18小样本：复用保存答案和Final，首轮1次Judge，最多3次（结构错误最多1次纠正仍占额度、每阶段600秒；Unknown不自动重发）。保存原始输出/引用/Usage，逐条审业务判断、必要事实与Scope，不以Parser通过当成功。失败停止，不进行批量。探针不是正式50成绩。
2. Q18通过后**再次授权**50题Judge-only Replay：预计50次Judge，生成0；每题最多3次、最多150次；连续两题耗尽熔断。新Run逐题保存，异常仍Partial。计划50题重新判分，先前探针不冒充整轮成绩。前置探针另计，合计预计51次、理论最多153次。
3. 当前输入估算约 **413,273 tokens/50题首轮**，方法为项目既有字符比例估算而非模型tokenizer。常规输出区间50,000–300,000 tokens；每题输出上限32,768，单轮理论输出1,638,400、150尝试上限4,915,200；纠错反馈还可能增大输入。
4. 仅按本地2026-09-30 USD计价快照，首轮估算 **$0.073–$0.546**；含150尝试、输出上限及一次纠错反馈增量的保守估算约 **$7.44**。这是离线快照估算，不是实时价格、实际扣款或已授权预算；探针及额外语义补证另计。真实执行前必须重新核价并冻结预算/请求上限，输入比例估算不能当精确费用硬保证。
5. 只有真实50/50合法业务判定、正式Completed、Overall/11 Gate按真实结果聚合、身份一致且`require_current_baseline()`通过，才可作为正式当前Baseline。50/50指完成，不要求全PASS或全Gate通过。Agent/Sandbox仍需后续独立授权。

## 源码入口

- `backend/app/evaluation_contract.py:321 scope_quote_present` / `:351 validate_business_judgment`：Scope绑定与Fact严格合同；版本及Prompt同文件。
- `backend/app/ai_service.py:34 attach_heading_scopes`：Canonical标题/页序/Parent多分支；`:187 resolve_diagnostic`复用Provider。
- `backend/app/canonical_evidence.py:5 full_norms`：冻结源全文与角色；`backend/app/governance.py:1152 _validate_revision_drafts`：新Revision不截断。
- `backend/app/evidence_resolver.py:19 resolve_case` / `:115 resolve_persisted` / `:135 saved_findings`：通用事实与阶段验证、独立存取与身份失效。
- `backend/app/judge_replay.py:33 replay_eligibility` / `:12 saved_selection_error`：逐题资格及确定性Final派生。
- `backend/app/evaluation.py:236 judge_context` / `:369 judge_replay_preflight` / `:383 start_judge_replay` / `_execute_baseline`：输入构建、新Run和禁止生成边界。
- `backend/app/governance.py:2003 create_baseline_run`：事务内核源并种入执行；`:1943 require_current_baseline`保持原正式守卫。
- `backend/app/main.py:1541/1547/1569`新增预检、judge-replay与resolve-diagnostics端点；`frontend/src/pages/EvaluationPage.tsx`复用原费用授权和Drawer。
- `scripts/verify_contract_replay_v5.py --simulate`：实际50只读资格及临时副本Mock；`scripts/verify_baseline_diagnostics.py`：旧10题与旧身份阻断；`scripts/verify_evaluation_vnext.py`：旧200条离线回归。
