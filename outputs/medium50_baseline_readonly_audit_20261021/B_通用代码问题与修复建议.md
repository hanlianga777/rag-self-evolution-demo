# B. 通用代码问题与必要修复建议

日期：2026-10-21（Asia/Shanghai）。对应最新运行 `EVAL-20261021013401711966`，冻结Golden `GD-20261015135415953347`。本报告只提建议，没有执行修复、重评或Provider调用。逐题完整问题、参考答案、实际回答、原始Judge JSON、Candidate/Final全文见同目录A报告。

## 1. 先区分四个层次

| 层次 | 本次真实发现 | 可以改变什么 | 不得由此推导 |
|---|---|---|---|
| 业务回答质量 | 十题至少一项必要事实未完整回答；Q27另有条件误用 | 后续RAG优化实验的目标 | 诊断Unknown不等于业务FAIL不成立 |
| 正式评测有效性 | 十题Judge输出通过当前严格Parser；Q18两次输出引用不合法 | 合法恢复或新身份评测 | 原始PASS字样不等于正式PASS |
| 技术诊断 | 5题Ranking/Generation目标准入、5题Unknown；Q08部分Final支持触发错误主因 | 解释/根因/策略方向；必须保留原评测 | 修诊断不能补业务分或完成Partial |
| Agent工具箱/治理 | Q27虽局部准入却没有本次Trace证明能补核心规范的合法context策略；整轮仍Partial | 是否提出合法假设、允许哪些参数 | 有target_eligible不等于可启动Agent或必定能修复 |

在人工证据审计层面，五题主要是已入候选后被上下文选择排除（Q03/Q04/Q06/Q08/Q27）；五题是必要规范未进入保存候选池（Q07/Q17/Q24/Q28/Q29）。后一组“候选池缺失”不能再细分为向量/BM25还是融合截断，因为本次Trace采集点已在CandidateK之后。Q27适用条件扩写、Q17将局部未见泛化为手册不存在，是可独立指出的生成问题，不应抹去主证据链缺口。

## 2. 已触发的诊断缺陷：真实片段存在，被当成完整必要事实存在

**影响：Q08，已在保存记录上复现。**

`business_analysis()`对失败check先执行 `verified(check['support'], trace['final'])`。verified只验证所有给出的片段在绑定来源中真实存在，未证明这些片段完整覆盖requirement，也没有区分“部分相关支持”和“全部必要规范支持”。条件成立便追加Generation。

Q08 checks[3]的requirement包含“长期未用先清洁充电板表面、干燥软布擦充电板表面和机身底部电极”等。support却只有Final `DOC-004-C-00017`的“请使用干燥抹布擦拭充电电极表面…”。完整板面规范在候选 `DOC-004-C-00032`（候选12、rerank6）而未入Top4。回答已经覆盖Final支持的电极擦拭部分；不能据此说模型忽略了完整板面规范。

同题checks[5]又合法形成Ranking finding，但根因选 `findings[0]`，得到Generation、stage=None。`diagnostic_view()`只有存在retrieval_failure_stage才产生ranking_omission，因此当前view仅有confirmed_claim，Agent只允许grounded_generation，失去真实可验证的Top6上下文策略。

**最小建议：** 在同一必要事实的诊断中明确区分完整与部分支持；完整规范已绑定候选且Final未覆盖的部分，应保留其Ranking阶段证据。不能以任意非空support推Generation，不能用一次纯字符串判断代替语义覆盖。复用当前Judge语义判断，但当现有字段无法区分覆盖程度时，应保留具体“部分支持，主因待核”而非强行Generation；要实现自动闭合，可由后续同次Judge输出必要事实的原子拆分/完整覆盖声明并与真实片段绑定，不能后端凭空重写历史checks。保持一个主要根因，但不能让数组先后顺序掩盖已证明的失败阶段和合法干预。

**只影响诊断的部分：** 对已有checks正确解释、避免部分支持冒充完整支持、保留阶段观察、生成具体阻断理由，不改变verdict/quality/Gate或评测身份字段。现有证据不足时可以缩减目标，不能为了扩大Agent输入而放松准入。

**影响正式身份的部分：** 如果选择更改Judge Prompt、正式Schema/Parser、必要原子事实输出要求，就进入新的Prompt/Parser身份，旧Partial不得混续。建议先做诊断侧必要修复，不为了这次诊断而扩大正式评分合同。

源码：[backend/app/diagnostics.py:326](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/diagnostics.py:326)、[backend/app/diagnostics.py:341](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/diagnostics.py:341)、[backend/app/diagnostics.py:278](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/diagnostics.py:278)、[backend/app/optimization.py:16](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/optimization.py:16)。

## 3. 五题Unknown不是同一个“scope不足”：可选诊断字段与强制准入之间有缺口

| 题目 | 实际失败分支（0起始索引） | 正确阻断还是缺陷 | 必要处理 |
|---|---|---|---|
| Q07 | checks[0]/[1]的scope=true，reference有效，support=[]；candidate_support键不存在，list判断false；issue无Final/无reference | 阻断正确：未声明审完候选；缺的是诊断资料完整性 | 显示精确缺字段；后续明确候选无适用等价事实的审查，不将缺失字段当空数组 |
| Q17 | checks[2]/[3]及issue scope=false先continue；已有candidate_support=[]与有效R3规范 | 不得直接覆盖false；事实根因在人工审计已可确认，Judge未闭合“B2系列R3分支”源范围 | 区分现场备件未知与手册源范围已知；不得用前者吞掉后者的所有诊断 |
| Q24 | checks[5..9] scope=true、reference有效、support=[]，candidate_support不存在；issue无规范定位 | 阻断正确；不是scope问题 | 同Q07；保留稀释/孩童/急救三个独立证据缺口 |
| Q28 | check[0]有效reference但candidate_support缺失；check[1]/[5]有错绑C00026的C00181原文；check[4]/issue[0]scope=false；issue[1]空支持 | 对不真实定位和未知字段阻断正确；原始Judge诊断引用不可靠 | 指出错误source绑定；不自动跨ID修正、不把整个题强归Safety |
| Q29 | checks[0..6]及issue全部scope=false；check[0..2]有效reference，check[3..6]还缺reference | 阻断正确；范围标志未闭合且规范项缺字段 | 冻结表/同产品PDF可供人工确认；后续将逐项规范和范围语义补齐，保持历史只读 |

这五题均已通过：业务FAIL、完整Trace、现Parser重验、Corpus身份、Final Canonical、候选Canonical。不能把它们解释为Corpus过期、记录残缺或Canonical失败。它们的Guard均没有额外finding，回答latency均小于60000ms，不能借Safety/Performance兜底绕过检索诊断。

**最小通用建议：** `business_analysis()`在每个return/continue路径输出既有analysis_reason/evidence_checks能承载的明确检查项与实际值，例如“checks[1].candidate_support missing”“reference quote X绑定C00026未定位；适用原文在C00181但未自动更正”。不要新增一套流程或宽泛状态体系。

当前Prompt写的是checks“可提供”reference_support/candidate_support/scope_resolved；诊断却依赖这些字段完成检索归因。缺字段并非Parser报错，也不能解释为不存在证据。最小诊断修复应解释这种差别。若未来要求同次Judge在所有失败项强制提供这些字段，则需改Prompt/Parser并升级身份；缺字段的历史输出继续只读。另一条路线是经Owner认可的独立、可追溯诊断证据，不改正式评分，但不能假装它来自历史Judge，也不能默认自动准入。

`scope_resolved=false`的两种语义尤其不能混淆：现场对象具体子型号尚未确认，和手册对应分支/一般规范的来源适用范围未核清。Q17/29已有源标题/产品/PDF原页可独立审计；这不授权程序将原false无条件改true，更不允许忽略安全条件。

源码：[backend/app/diagnostics.py:302](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/diagnostics.py:302)、[backend/app/diagnostics.py:325](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/diagnostics.py:325)、[backend/app/diagnostics.py:328](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/diagnostics.py:328)、[backend/app/diagnostics.py:333](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/diagnostics.py:333)、[backend/app/evaluation_contract.py:422](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/evaluation_contract.py:422)。

## 3.1 已证实的上游缺口：冻结规范摘要截断，评测原样发送摘要

Q29冻结Golden的evidence_key_points只有160字，精确等于Corpus C00056.chunk_text[:160]，止于“有裂纹或者有破”；完整Child为419字，包含参考答案所列全部检查项目。其来源题V1G-153537417845-29当前保存证据也为160字，clone_provenance记录复制时semantic_content_unchanged=true，说明不能将缺口归咎于本次评测修改Golden。

snapshot_items复用冻结evidence；score_execution直接将item['evidence']作为golden_evidence传给Judge，没有按source_chunk_ids解析完整规范。Q29的候选和Final均未命中检查表，所以Judge虽看到完整reference_answer，却没有看见后半表的可逐字引用规范。原始checks[0..2].reference_support也恰好是那段160字，而checks[3..6]没有reference_support，与实际输入缺口一致。不能仅凭这个事实断言所有scope=false的模型心理原因，但后半项没有可用规范原文属于确定的程序输入问题。

当前governance._validate_revision_drafts:1184还存在按[:160]构造evidence_key_points的路径；ai_service:637的新生成路径保存全文，golden_v2.validate_golden_candidate:429只归一化现有evidence并校验完整Corpus答案可支持，不会把160字自动替换成完整必要规范。因此“Validator通过完整参考答案”与“Judge收到完整规范”是两个不同事实。未取得该历史题实际写入时的执行栈，不把当前这处[:160]当成已证明的唯一历史写入函数；已证明的是冻结数据实际截断，以及当前评测原样传入的确定路径。

**必要建议：** 不回填Frozen Golden。诊断侧可以只读解析同身份Canonical Corpus的必要规范并作为独立审计证据，仍须闭合来源和语义；若要让正式Judge看到完整规范，应单独定义并版本化“从冻结source_chunk_ids读取同Corpus完整原文”的输入合同，与Final支持严格分离，不能用Golden规范替代答案Final证据。新Revision的证据持久化也应避免无条件前160字导致必要规范消失；这是新数据写入/治理行为变化，须同步SPEC并重新资格审查，不修改旧Snapshot。若补给正式Judge更多资料，必须记录输入合同/Identity变化，不能声称旧身份完全相同。

源码：[evaluation.snapshot_items:152](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/evaluation.py:152)、[evaluation.score_execution:239](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/evaluation.py:239)、[governance._validate_revision_drafts:1184](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/governance.py:1184)、[golden_v2.validate_golden_candidate:429](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/golden_v2.py:429)、[ai_service新生成证据:637](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/ai_service.py:637)。

## 4. Q18确定问题：可见的source_scope标题不在正文引用域

链路为：

1. `attach_heading_scopes()`从真实独立标题Child读取R1/R3范围，挂到Final.source_scope，没有改正文。
2. `generation_context()`把该heading放到展示头；Judge输入同时收到原始完整Final（含source_scope）。
3. Judge把标题作为checks[5]的事实support，source_id却填校准/安装Child（C00009/C00022/C00008）。这三条的content根本没有R1/R3标题。
4. `quote_present()`仅查绑定的Child/Parent/matched_child_ids与对应content，既不查source_scope.quote，也不把其source_id自动加入正文来源集合。
5. 第一次和纠正后的第二次均在相同三处失败，ProviderInvalidResponse被正确保存；Q18有成功生成execution、两份完整原始Judge响应，无正式case/bad_case。

真实标题来源为C00004（R3）和C00018（R1），其关系经Canonical检查可验证。但这两条也没有独立进入本题Final正文，因此只换成标题ID仍不符合现有引用域。正文“嘀\~”转义在实际normalize_display后可匹配，不是本次原因。两次响应finish_reason均为stop，不是max_tokens截断。

**在不改现Judge版本下恢复：可以尝试，但必须以后另行授权一次同身份显式恢复。** 当前源码Prompt/Parser/Matcher身份和保存Identity一致，使用保存配置的共享start/resume只读资格校验通过，49个成功case可复用，Q18生成答案/Trace可复用。恢复子Run仅缺Q18 Judge判分；仍须实时模型/配置/费用预检，且相同错误可能再现，不能承诺成功。原Run保持Partial，新子Run不覆盖原记录。当前state=stopped，`recover_run()`不会自动继续；必须显式恢复，不是后台自行重试。

**离线零调用恢复：不可以。** 两份原始JSON均违反当前引用合同。删除标题support、换ID、拼接正文、改met、把原始PASS强行写case都会改变证据或成绩。现有机制没有可以合法复用的已成功scored_result。

**若要通用根因修复，有两条可选方案，不能本轮代选并执行：**

- 维持严格正文引用：后续Prompt/输入明确标题只用于范围判定，不作为正文support；正文事实仍逐字引用。需要更改Prompt或传入证据形态，属于新正式评测身份，应重新按身份规则运行。
- 正式定义可信元数据引用：在统一Matcher里单独校验source_scope的来源ID、原始标题、对应文档、页序和Canonical派生关系，不能简单把任意metadata文本拼进正文放行。增加接受的证据类别，须Matcher/Parser版本及Identity升级；旧Partial不能冒用新身份恢复。

不建议针对Q18硬编码、大小写/字符串模糊匹配、把所有metadata都并入content、重建Corpus或改Golden。这些都未命中实际根因。

源码：[backend/app/ai_service.py:30](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/ai_service.py:30)、[backend/app/ai_service.py:56](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/ai_service.py:56)、[backend/app/evaluation.py:239](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/evaluation.py:239)、[backend/app/evaluation_contract.py:99](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/evaluation_contract.py:99)、[backend/app/evaluation_contract.py:334](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/evaluation_contract.py:334)、[backend/app/providers.py:233](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/providers.py:233)、[backend/app/evaluation.py:516](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/evaluation.py:516)、[backend/app/evaluation.py:564](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/evaluation.py:564)、[backend/app/governance.py:1983](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/governance.py:1983)、[backend/app/governance.py:2024](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/governance.py:2024)。

## 5. 现有工具箱的能力边界：Q27不是一个TopK=6能解决的例子

现有Search Space：candidate_k=12/24，top_k=4/6，min_score=0/.1/.2/.3，rerank开关，三种prompt_strategy，及查询/混合/过滤参数。INTERVENTIONS不是所有参数任意组合：每方向必须有保存Trace观察，validate_intervention还要求目标根因、参数变动、逐目标断言和必要联动匹配。

| 题目/组 | 只读固定池验证结果 | 当前能否合法提出策略 |
|---|---|---|
| Q03 | 原rerank Top6仍没有C00132；rerank关Top4漏C00134；rerank关Top6同时含入口与后续创建步骤 | context_selection方向两个必要参数联动有证据；只证明上下文覆盖 |
| Q04 | C00180排第5，Top6可纳入；C00179未召回不重要，因为同等重量要求在C00180 | 当前Ranking view支持context_selection |
| Q06 | C00026/C00017排第5/6，Top6同时纳入 | 当前Ranking view支持context_selection |
| Q08 | C00032排第6，Top6纳入 | 当前错误Generation view仅给grounded_generation，需先纠正诊断或保留不确定性 |
| Q27 | 核心地图条款C00096原候选第7、rerank第12；枚举top_k×rerank×min_score全部16种固定池context选择均不含该事实 | 当前虽Ranking/target_eligible=true，合法context_selection没有已证明有效的参数方案；允许零候选 |
| 五道候选缺规范题 | 只重排或Top6无法产生不在候选的规范；candidate_k=24/查询扩展是否有效未运行、未知 | 当前Unknown阻断；诊断闭合后可提出可证伪召回假设，不能承诺改善 |

Q27提高min_score只筛低分，不会把排名较后的必要条款抬到前六。当前query_expansion/candidate_recall要求recall_missing；Q27是已有候选遗漏，只有ranking_omission。source_filter需要retrieval_noise，本次view也未给出。禁止为使用这些方向而改写事实根因/伪造观察。

**必要建议：** 先复用现有0–3候选/insufficient_evidence出口，明确“无合法且有观测支持的假设”可以不产生Candidate，不因target_eligible=true强行凑方案。若Owner要实际解决Q27，需要进一步决定能否扩大合法上下文预算，或增加能把所需规范提升到预算内的重排/上下文选择能力。修改重排模型、规则、源覆盖选择或Search Space属于真实RAG/优化合同变化，必须同步SPEC及后续真实实验；不是修诊断就自动解决。无需新增第二个Agent或扩大整个系统。

源码：[backend/app/policy.py:42](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/policy.py:42)、[backend/app/optimization.py:16](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/optimization.py:16)、[backend/app/optimization.py:26](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/optimization.py:26)、[backend/app/optimization.py:98](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/optimization.py:98)、[backend/app/optimization.py:118](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/optimization.py:118)、[backend/app/retrieval.py:255](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/retrieval.py:255)、[backend/app/retrieval.py:279](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/retrieval.py:279)、[backend/app/knowledge_pipeline.py:136](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/knowledge_pipeline.py:136)。

## 6. 应保留的正确阻断与次要审计风险

- Q28的断开对接站原文误绑C00026，诊断拒绝其reference是正确行为；应修或重新取得诊断证据，而非让quote_present跨任意Chunk找相似句。
- 十题Judge的critical与safety_violation在数据上是不同字段，许多critical=true但safety_violation=false。`business_analysis()`issue分支使用 `safety_violation is True or critical` 分类Safety，存在严重性与安全类型混用的代码风险；本次对应issue因为空Final、缺reference或scope=false没有使这十题主因变Safety，故不是五个Unknown的原因。本轮不把未触发分支冒充已造成的误判。后续若修，应保留critical供原资格/严重性使用，只把真实安全边界证据用于Safety归因，不改历史critical分值。
- `_score_business()`的sufficient通过“所有required check的support非空”汇总，没有区分support真实位于Final还是遗漏检查的candidate_requirement_evidence，也不保证复合check全部事实已支持。Q08实际仍为insufficient（有空support），本轮没有由此证明该题被错误标成sufficient；但同一部分支持语义缺口应在修诊断时避免当作完整覆盖信号。若修改只是派生诊断展示，不改verdict/quality；若要把它升级为正式PASS门槛，须明确进入评测身份，不顺手改尺。
- 所有审计题回答latency为4.9–28.8秒，未达到业务诊断的>60000ms条件；Judge几十秒不等于RAG回答延迟。没有证据支持把它们归为Performance。本轮没有发现应通过调参“修复”的性能目标。
- 未发现必须改Golden的根因。Q24的等价“制造商说明”子项可争议，Q28的安全违规标签尚未闭合；都不推翻各自其他明确漏答，也不授权回填历史成绩。Q03入口遗漏严重性是否应critical需按现有严重性定义另审，不能因为是安全设备就当Safety。

源码：[backend/app/diagnostics.py:334](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/diagnostics.py:334)、[backend/app/evaluation.py:337](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/evaluation.py:337)、[backend/app/diagnostics.py:337](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/diagnostics.py:337)。

## 7. 持久化与正式准入：本次应保持的行为

`_score_business()`仅在Judge结构/引用有效后形成业务case；业务verdict来自Judge与有限Guard统一裁决，quality仅供既有Gate。`record_evaluation_case()`保存不可冲突的case并只对实际业务FAIL生成bad_case。Q18未完成有效score，不应有业务Bad Case。批处理保存execution与raw_provider_response，结构错误最多一次纠正，两次无效后保留题目技术异常继续其余题，最终Partial屏蔽完整Overall/Gate。本次49+1的数据库记录与代码一致，未发现应跳过这些保护的持久化缺陷。

Agent.generate首先require_current_baseline；后者只认可当前已Completed的正式同身份基线。最新Partial不满足；resolver回到旧Completed并标规则需升级。因此即使局部5题view合格，也不能现在直接对最新Run调用Agent。恢复Q18/完成整轮、同身份资格与人工授权仍必须遵守。

代码位置：[backend/app/evaluation.py:309](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/evaluation.py:309)、[backend/app/evaluation.py:343](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/evaluation.py:343)、[backend/app/governance.py:2093](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/governance.py:2093)、[backend/app/evaluation.py:467](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/evaluation.py:467)、[backend/app/evaluation.py:523](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/evaluation.py:523)、[backend/app/evaluation.py:544](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/evaluation.py:544)、[backend/app/governance.py:1907](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/governance.py:1907)、[backend/app/governance.py:1943](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/governance.py:1943)、[backend/app/optimization.py:98](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/optimization.py:98)。

## 8. 改动范围与身份影响清单（全部尚未执行）

| 建议 | 层次 | 正式评测身份影响 | 历史处理 |
|---|---|---|---|
| 具体返回诊断阻断路径、missing与[]区分、忠实显示原字段 | 诊断解释 | 不改Judge/Matcher/Policy/生成身份；需同步诊断合同文档 | 原始分数/JSON/Run只读 |
| 纠正“部分Final支持→完整Generation”及阶段证据丢失 | 诊断/Agent准入 | 仅解释已有证据时不改正式分尺；应记录诊断行为变更及SPEC | 不回填原Judge，当前视图可按新诊断解释 |
| 强制Judge产出诊断字段、重定义scope语义或原子事实Schema | Judge输出合同 | Prompt/Parser变化进入新Identity | 旧Partial不能直接混续 |
| 新Judge完整规范输入/新Revision不再固定截摘要 | 评测输入/治理持久化 | 正式Judge输入增加须版本化；新数据重新治理，不改旧Golden | 冻结摘要只读；人工诊断注明独立补充来源 |
| source_scope正式成为可引用证据 | Matcher/Parser证据合同 | 必须版本化并进入新Identity | 不改旧Final/历史support；新身份评测 |
| Q18按原合同只补Judge | 正式恢复操作，非代码修复 | 同身份且实时预检通过可恢复 | 新建子Run，复制49成功题及已有execution；需另授权Provider |
| 用已有top_k/rerank/prompt_strategy做合法实验 | 真实RAG配置优化 | 不改Judge尺；新Candidate配置与正式实验记录 | 不改Baseline回答/成绩；须费用授权和完整Sandbox |
| 扩Search Space/改重排、上下文策略或Generation Boundary | 真实能力/产品合同 | 依具体方案更新配置/Prompt身份；Generation Boundary已入Identity | 不伪称诊断修复，不能继承未经验证资格 |
| 修改冻结Golden、回写历史JSON、把Q18原始PASS直接入账 | 非本轮授权且无必要依据 | 会破坏冻结/评测真实性 | 不建议 |

最小顺序建议：先审阅A报告并确认诊断缺陷的证据；如要先闭合现版本Baseline，可单独授权Q18同身份补Judge（有再次失败风险）；另行决定是否只做诊断修复，或接受正式合同版本升级。两条路线不要混成“改完诊断即可原身份补分”。任何正式合同变化仍按项目要求同Commit同步SPEC/Changelog/相关文档，本轮没有执行Commit/Push。

## 9. 可复核源码索引

| 源文件与函数 | 行号 | 作用 |
|---|---|---|
| diagnostics._current_corpus / _canonical_final | 20 / 41 | Corpus SHA、冻结身份、完整正文与元数据核对 |
| diagnostics.diagnostic_view | 214，272–286 | 阶段观察、工具箱方向、technical目标资格 |
| diagnostics.business_analysis | 302–342 | 本报告逐题命中的具体条件 |
| optimization.INTERVENTIONS / validate_intervention | 16 / 26–72 | 干预方向、参数、目标与Trace断言验证 |
| optimization.OptimizationAgent.generate | 98–159 | 完整基线身份、可信目标过滤、空候选、Agent输入 |
| evaluation_contract.quote_present / normalize_display | 99 / 39 | 真实来源正文引用定位 |
| evaluation_contract.omission_evidence / validate_business_judgment | 305 / 320–370 | 失败遗漏规范引用与正式证据合法性 |
| evaluation_contract.evaluation_identity / BUSINESS_JUDGE_PROMPT | 17 / 383–426 | 版本/Prompt/生成边界身份及必要事实合同 |
| evaluation._score_business / score_execution | 309 / 233 | 业务判定与派生诊断输入 |
| evaluation._execute_baseline | 393–561 | 成功题/生成execution复用、有限纠正、错误保存、Partial |
| evaluation.recover_run / baseline_preflight | 564 / 200 | stopped不自动恢复；共享只读资格读取 |
| governance.current_baseline_identity / require_current_baseline | 1907 / 1943 | 仅Completed正式基线可供Agent |
| governance.validate_evaluation_resume / create_baseline_run | 1983 / 2003 | 续跑身份与子Run保留历史 |
| governance.record_evaluation_case | 2093 | case幂等冲突保护与真实FAIL bad_case持久化 |
| ai_service.attach_heading_scopes / generation_context / answer | 30 / 56 / 110 | 标题来源映射、展示与最终生成上下文 |
| providers.DeepSeekProvider._judge_business | 233–254 | 单次Judge、校验与原始响应错误保留 |
| retrieval.VectorRetriever.retrieve | 255–286 | CandidateK截断、rerank、阈值、Parent TopK |
| knowledge_pipeline.expand_parents | 136–146 | 完整Parent展开与TopK裁切 |
| policy.ALLOWED_SEARCH_SPACE | 42–55 | 现有合法参数域 |

以上路径均相对于项目根目录；前文提供绝对路径可点击链接。审计使用源码HEAD `a32e6730fce36eb07b73b1872fd85c92f064e270`，没有把源码检查冒充运行中进程重新加载验证。


最终文件验证：11/11题的完整问题、参考答案、实际回答、全部候选及Final正文和原始Judge响应均已逐项核对包含；Q18两次响应均定位到同一组三处标题引用；所有源码链接行号在当前文件内有效。17项保护文件（数据库、代码、SPEC与知识制品）SHA前后相同，数据库SHA亦与本次首次完整性采样相同；数据库仍49个完成判分、10个业务FAIL、1个技术异常/Partial。本轮仅新增本目录两份Markdown。
