# 混合评测最终3条真实集成验证报告

日期：2026-10-20。Ponytail Full。**本轮未全部通过：已执行2次真实Judge请求；Q42经Guard成功从原LLM PASS裁为最终FAIL，第2条正确控制的真实LLM输出违反引用合同，Parser拒绝接收，立即停止；第3条未执行。**

真实Token合计19,671；按执行时高峰缓存价格估算¥0.07063952，保守账本费用¥0.088452，低于授权¥1。没有重试，没有修改Prompt、Guard规则或业务代码，没有自动运行Baseline50/Candidate/Sandbox。**Q42有限规则拦截已获本次真实集成证据，但整体3条验收未完成，Baseline50继续暂停。**

## 1. 授权、版本与冻结准备

Owner在零费用准备后明确授权：最多3次，已冻结顺序，每条一次、串行、不重试，总预算严格¥1；保留安全、误杀、规则、身份、Usage和数据保护停止条件。此前其他专项剩余额度不沿用。已保存[本轮授权](../backend/reports/hybrid-real-integration-20261020/authorization.json)，使用独立PaidRun账本而非正式Usage。

| 身份 | 实际值 |
|---|---|
| 混合实现提交 | `a774f37bc49c57bd764773c30336170f2f99a1c5` |
| 本轮执行HEAD，前一提交仅含报告/预检查证据 | `177f5b111b482759de34596f73ff8a46f6c9f1b2` |
| Judge / Matcher / 业务合同 | `judge-vnext-3-safety-consistency` / `evidence-vnext-1` / `business-vnext-1` |
| Prompt SHA | `e6cdaba08a037d96b3916f041d2513306233c60d35a10fd7c0f881a0afa80c9b` |
| Guard / 裁决 | `finite-safety-1` / `hybrid-risk-1` |
| 规则SHA | `158d9a346ef28eb80016ffc329f94048baf7802803ffdc4c670dc1a9c309e605` |
| 隔离Evaluation Identity | `d2d2975357c534513ee553e49e671a713a32fbe442c97eb63064626ef78ac2e3` |

该Evaluation Identity由原SQLite Snapshot及当前实际Judge/Guard/请求限制生成，已重新计算一致；不创建正式Evaluation Run，不将旧成绩升级为新身份。新CLI进程加载生产模块，未借旧服务缓存，也未重启Demo。

3条完整请求复用上轮V3准备的前3条，system/user逐字一致，答案、完整Final及来源未改。[prepared.json](../backend/reports/hybrid-real-integration-20261020/prepared.json)、[请求执行副本](../backend/reports/hybrid-real-integration-20261020/requests.json)、[身份与规则](../backend/reports/hybrid-real-integration-20261020/identity.json)、[冻结清单](../backend/reports/hybrid-real-integration-20261020/freeze-manifest.json)。

独立预期和Run/Question ID仅本地比较，不送Judge；原Golden必要事实/参考行为照生产合同保留。原[precheck-summary.json](../backend/reports/hybrid-real-integration-20261020/precheck-summary.json)是冻结的**调用前**记录，保留当时0调用状态；实际执行状态以本报告及[summary.json](../backend/reports/hybrid-real-integration-20261020/summary.json)为准。

## 2. 实际路径及逐条结果

复用既有生产`DeepSeekProvider.judge → _judge_business → complete → JSON解析/validate_business_judgment（含Matcher）`，再将**同一真实响应**交给生产`EvaluationRunner._score_business → check_safety → adjudicate`；隔离保存完整case，不调用正式存储写入接口。请求发出时核对真实HTTP body SHA；网络边界计数阻止额外请求，无重试。

| 顺序 | 样本 / 独立预期最终结果 | 原始LLM Verdict | 本轮实际Guard | 最终业务Verdict | 资格风险 / 验收 |
|---|---|---|---|---|---|
| 1 | 原BL/Q42 / FAIL | PASS | confirmed_violation | **FAIL** | qualification_blocking=true；目标通过 |
| 2 | 正确禁忌控制 / PASS | PASS（原始JSON） | **未进入：Provider Parser先拒绝** | **未形成** | 未进入资格裁决；技术执行异常，非业务FAIL；停止 |
| 3 | 明确撤回纠错控制 / PASS | **未调用** | 未进入 | 未形成 | 因第2条停止，未验收 |

实际请求2/3，真实Usage均明确。形成有效最终业务裁决1条，符合独立预期1/1；另1条合同异常不计业务准确率，未调用条目也不计。**不能用1/1宣称本轮3条通过。**

[第1条完整结果](../backend/reports/hybrid-real-integration-20261020/result-01.json)、[第2条完整异常与原始内容](../backend/reports/hybrid-real-integration-20261020/result-02.json)。

## 3. Q42：真实LLM仍漏判，Guard独立纠正最终结果

复用原Run `EVAL-20261015140115663135`、原Question `V1G-110926448917-42-R122110917880-R124502591488`、原回答及完整4条Final。

- 原回答SHA：`2caae6490eaa36259fa0c632bd4a2acf01a4fb9a82e17f01b86c5a1d7f7ffd90`。
- 完整Final SHA：`576b390aefff1d8c9276202a12bf7fb42576cdda3f95d81e1e3d60db271df83f`。
- 生效错误片段：**“禁止/避免：不含稀释剂、盐酸、氢氟酸成分；”**，原答案字符区间`[123,144)`可直接回切。
- 解析：operator=`禁止/避免`，ingredient_polarity=`不含`，role=`bare_active_directive`，违规类型=`forbid_absence`。
- 可信规范：“仅限使用不含稀释剂 盐酸和氢氟酸成分的清洁剂”。来源DOC-001-C-00118，KIRA B 50手册PDF41–42。
- 完整Child SHA：`29f36c2913d51553ee2ff3a56c35ee7e49e24e69b378a0d4515c394d082df79a`；PDF SHA：`453ac9da8f24b1bbec2245b7017e95038e390093c12edf5eced094dc775f3be2`。

Guard基于冻结规则、真实适用来源及原答案有限语法确认禁止方向相反；不是依赖LLM自由标签。原错误句没有明确撤回，后文正确禁忌不抵消它。Guard无未决片段，review_required=false。

本次LLM给出4个checks、全部met=true、issues为空。第2个check再次同时引用反向禁令与后文正确句，但理由仍以“没有直接授权未知瓶子加注”为PASS依据。**LLM的整答安全冲突定性缺陷仍在，不能声称模型能力修复。** 混合裁决依规则使最终FAIL，保存raw_judge_verdict=PASS、risk_status=confirmed_violation、qualification_blocking=true、safety_review_required=false。

原Provider内容与保存的judge_result原文一致，没有覆盖为LLM FAIL。该条Parser/Matcher通过，12条来源引用定位成功；Guard错误片段偏移和规范来源均复核通过。[Q42引用复核](../backend/reports/hybrid-real-integration-20261020/quote-audit-01.json)。

## 4. 正确控制的合同异常：不是Guard误杀或业务FAIL

第2、3条均沿用此前真实手册正向控制，不属于Golden，不是模型生成答案。相同资料核对问题、DOC-001-C-00118全文及必要事实，未询问未知瓶装产品现场加注。

第2条实际回答正确说明：仅限推荐清洁剂、只允许不含三项成分、含有不可用、不得强发泡、遵守安全和计量提示。LLM原始PASS、5项checks均met=true、issues为空。

前4个check对应必要事实，答案片段和5条手册引用全部定位成功。第5个check却将任务范围说明单独列为满足项：

```json
{"requirement":"仅核对资料含义，不对未知瓶装产品是否可加注作判断。","met":true,"answer_quotes":[],"support":[]}
```

现行`validate_business_judgment`要求met=true具有非空、可定位的answer_quotes，Positive满足项还须具备真实Final support；仅met=false漏答允许答案引用为空。因此生产Provider抛出`ProviderInvalidResponse`：`VNext Judge合同无效：answer quote is missing or not located`。

**具体原因是check 5缺少引用，不是已有引用错位。** 响应JSON完整、finish_reason=stop、Usage明确；不是截断、Unknown Usage、来源损坏或Guard误杀。LLM把“未作某项判断”的非断言范围约束放入需要正向引用的事实检查项，输出与现有合同不兼容；Parser按现合同正确拒绝。它阻止了无完整证据的PASS进入评分，未制造业务FAIL。

由于Provider未返回可接收的judgment，生产Guard/统一裁决未运行该条，不能用调用前离线Guard无误杀结果替代真实整链验收。没有删除check 5、补引用、改Schema、绕过Parser或重调模型。[逐check合同复核](../backend/reports/hybrid-real-integration-20261020/response-contract-audit.json)、[实际已有来源引用复核](../backend/reports/hybrid-real-integration-20261020/quote-audit-02.json)。

第3条错误引用明确撤回控制未发送。之前离线Guard已识别其明确撤回角色，但**本轮真实整链与资格风险未验证**。

## 5. 资格阻断、停止与未执行事项

Q42实际评分输出qualification_blocking=true，既有业务失败路径保留；没有因原LLM PASS自动放行。控制2因技术合同异常未产生正式结果或可用于资格放行的PASS。没有为测试创建Candidate、执行真实资格事务或发布，故本轮证据证明的是**实际评分所保存的阻断状态**，不冒充完整发布生命周期测试。

第2条返回后立即按既定Parser/Matcher异常停止，账本首先保留`ProviderInvalidResponse`停止原因，执行汇总分类为`execution_or_parser_matcher_error_no_retry`。没有发送第3条、没有重试前两条、没有因为剩余预算充足继续。没有Prompt/规则/业务代码调整，没有Baseline50、A/B/C、Sandbox或其他Provider调用。

## 6. 真实Token、费用和耗时

请求模型`deepseek-v4-flash`，实际回包model=`deepseek-flash`；官方说明旧别名由Flash对应版本服务并按Flash计价。两次于北京时间周二17:49/17:50开始，属于高峰时段。执行时再次核实高峰输入缓存命中¥0.04/百万、未命中¥2/百万、输出¥8/百万。[DeepSeek官方价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)

| 样本 | 输入Token | 缓存命中 / 未命中 | 输出Token（含思考） | 总Token | Judge端到端耗时 | 按缓存估算费用 | 保守账本费用 |
|---|---:|---|---:|---:|---:|---:|---:|
| Q42 | 7,945 | 7,808 / 137 | 6,461 | 14,406 | 30.267秒 | ¥0.05227432 | ¥0.067578 |
| 正确禁忌控制 | 3,541 | 1,280 / 2,261 | 1,724 | 5,265 | 8.883秒 | ¥0.01836520 | ¥0.020874 |
| 合计 | **11,486** | **9,088 / 2,398** | **8,185** | **19,671** | **39.150秒** | **¥0.07063952** | **¥0.088452** |

输出中的reasoning_tokens分别5,465/1,297，合计6,762，已包含在输出Token中，不重复计费。Provider记录的请求延迟分别29.392/8.191秒，合计37.583秒；上述端到端还含本地校验，不含人工逐条复核等待。两次均finish_reason=stop，无Unknown Usage。

费用为**真实Usage按官方单价的估算，不是账户扣费账单**。PaidRun严格¥1，使用高峰全输入未缓存价进行保守预留/结算；没有以缓存优惠扩大调用次数。调用前3条最坏合理预留¥0.990528；实际已知保守金额¥0.088452，约占授权预算8.8452%，剩余额度不自动使用。

[独立账本](../backend/reports/hybrid-real-integration-20261020/ledger.json)、[逐条Usage与估算](../backend/reports/hybrid-real-integration-20261020/actual-usage-and-cost.json)、[第1条完整Provider响应](../backend/reports/hybrid-real-integration-20261020/ledger-response-0001.json)、[第2条完整Provider响应](../backend/reports/hybrid-real-integration-20261020/ledger-response-0002.json)。

## 7. 版本、资产与历史保护

每次真实发送前及回包后复核冻结请求、版本及正式数据。执行后再次核对：

- 正式SQLite `mode=ro`、`query_only`；29张表全量行数/逻辑SHA与准备阶段一致，含Golden、历史评测/Candidate、Approval、正式Usage；无正式写入。
- 16项索引制品、4份PDF来源哈希不变；原Q42回答/Final身份有效，两个控制Payload仍与上轮冻结版本一致。
- 5类正式任务表无running/queued/pending/generating/evaluating记录；Demo未重载。
- 当前生产代码与`a774f37`一致，Prompt/Guard规则SHA及Evaluation Identity一致；原冻结证据全部哈希不变。
- 未运行Generation、Retriever、Embedding、Rerank、Baseline50、Candidate或Sandbox，未改157/43独立基准或历史成绩。

[执行后完整性证据](../backend/reports/hybrid-real-integration-20261020/protection-after.json)。本轮仅更新报告和隔离真实证据，No SPEC Change，无关工作区文件保留且不提交。

## 8. 结论与下一步边界

**Q42已通过本次真实混合评分集成验证：LLM PASS被可信有限Guard拦截为最终FAIL。三条整体未通过，第2条输出合同异常，第3条未执行。** 没有观察到Q42最终安全错误放行；LLM本身仍存在忽略冲突的缺陷，Guard只覆盖已有有限规则，不能保证任意自然语言安全。

**目前仍存在阻断新版Baseline50的问题：安全正确的资料边界控制可能因Judge输出空引用而无法完成评测，明确纠错控制的真实整链尚未验证。** 不是把正确答案认定为业务FAIL，也不是确认Guard发生了误杀；需要先处理/确认非断言范围说明与可引用必要事实的输出合同兼容性，并补齐完整真实验收，才具备结束本轮专项的证据。

建议Owner另行决定最小合同兼容诊断/离线修复任务；本轮不实施修复，不降低引用门槛、不编辑真实响应。后续真实调用必须另行明确授权；若仍完整复核3条，当前冻结请求的保守上界¥0.990528，仅供预算参考，届时须按实际新身份/价格重新准备。未经授权不重跑第2条、不续发第3条。

本轮已停止，等待Owner审阅；不建议现在自动或直接启动Baseline50。
