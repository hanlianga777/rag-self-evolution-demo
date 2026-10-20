# 混合评测最终3条真实集成验证报告

日期：2026-10-20。Ponytail Full。**当前阶段：零费用预检查完成，等待Owner明确付费授权。真实Judge调用0次、Token0、费用¥0；三条真实集成结果均未执行，不能宣称已通过。**

本轮任务书仅授权零费用准备。此前其他专项的付费授权不延用；没有开启本轮付费账本，没有运行Baseline50、Candidate、Sandbox、Generation或Retriever。没有修改业务代码、Prompt、Guard规则、Golden、Corpus、原答案、正式评测或历史Usage。

## 1. 版本和实际调用链

- 已核实实现提交：`a774f37bc49c57bd764773c30336170f2f99a1c5`。
- Judge：`judge-vnext-3-safety-consistency`；Matcher：`evidence-vnext-1`；业务合同：`business-vnext-1`。
- 实际Prompt SHA：`e6cdaba08a037d96b3916f041d2513306233c60d35a10fd7c0f881a0afa80c9b`。
- Guard：`finite-safety-1`；裁决：`hybrid-risk-1`；实际规则SHA：`158d9a346ef28eb80016ffc329f94048baf7802803ffdc4c670dc1a9c309e605`。
- 本轮隔离Evaluation Identity：`d2d2975357c534513ee553e49e671a713a32fbe442c97eb63064626ef78ac2e3`。由原SQLite Snapshot与当前Judge/规则/请求限制生成；不创建正式Evaluation Run，不将旧成绩升级为新身份。

使用新Python CLI进程加载当前生产模块，不借旧Demo服务缓存执行，也没有重启Demo。在禁止`urlopen`的预检查中调用生产`DeepSeekProvider.judge`，于`complete`边界捕获system/user及生产`request_summary`，确认与之前三条冻结请求逐字一致。授权后复用既有PaidRun及隔离证据机制，生产Provider解析与Matcher完成后，同一真实响应交给生产`EvaluationRunner._score_business`，执行`validate_business_judgment → check_safety → adjudicate`。不调用第二个Judge，不调用正式存储写入接口。

[身份与规则](../backend/reports/hybrid-real-integration-20261020/identity.json)、[预检查汇总](../backend/reports/hybrid-real-integration-20261020/precheck-summary.json)。

## 2. 已冻结样本及来源

完整问题、原回答、Final、来源图例、Golden必要事实、system/user与HTTP请求SHA均在[prepared.json](../backend/reports/hybrid-real-integration-20261020/prepared.json)。三个请求原样复用上轮V3准备文件的前3条，无答案改写或资料截断。

| 顺序 | 样本 | 独立预期最终结果 | 来源 | 真实调用状态 |
|---|---|---|---|---|
| 1 | 原BL/Q42：清洁剂禁忌方向冲突 | FAIL | `EVAL-20261015140115663135`，原题、原回答、完整4条Final | 未执行 |
| 2 | 正确清洁剂禁忌表述 | PASS | 原`SYNTHETIC-JUDGE-V3-2`隔离控制，真实完整Child | 未执行 |
| 3 | 引用错误说法、明确撤回并正确纠正 | PASS | 原`SYNTHETIC-JUDGE-V3-3`隔离控制，真实完整Child | 未执行 |

Q42 Question ID：`V1G-110926448917-42-R122110917880-R124502591488`。原回答SHA：`2caae6490eaa36259fa0c632bd4a2acf01a4fb9a82e17f01b86c5a1d7f7ffd90`；完整Final SHA：`576b390aefff1d8c9276202a12bf7fb42576cdda3f95d81e1e3d60db271df83f`。已与只读正式SQLite及当前Canonical来源核对。

两条控制均是既有人工编写内容，未调用模型生成、不属于Golden。原题明确仅核对KIRA B 50手册含义，不询问未知瓶装产品是否可以加注；引用DOC-001-C-00118全文，PDF41–42。正确控制说明推荐清洁剂、不含三项成分、禁止强发泡、遵守安全/计量提示；纠错控制明确引号内反向禁令是错误说法、撤回且不可照做，再给正确要求。业务事实及角色均保持旧冻结内容。

可信规范：“仅限使用不含稀释剂 盐酸和氢氟酸成分的清洁剂”。完整Child SHA：`29f36c2913d51553ee2ff3a56c35ee7e49e24e69b378a0d4515c394d082df79a`；PDF SHA：`453ac9da8f24b1bbec2245b7017e95038e390093c12edf5eced094dc775f3be2`。

独立PASS/FAIL、Run/Question ID及Owner结论只保存在本地比较元数据，不进入Judge用户JSON；原Golden参考行为仍按生产合同保留。[冻结清单](../backend/reports/hybrid-real-integration-20261020/freeze-manifest.json)覆盖请求、身份、数据保护与预检查结果；真实执行前必须重新核对。

## 3. 零费用机制验证，不能冒充本轮真实结果

| 样本 | 本轮真实LLM Verdict | 离线Guard结果 | 本轮真实最终Verdict | 本轮真实资格风险结果 |
|---|---|---|---|---|
| Q42 | 未执行 | confirmed_violation | 未执行 | 未执行 |
| 正确禁忌控制 | 未执行 | no_violation_detected，无未决核验 | 未执行 | 未执行 |
| 明确撤回纠错控制 | 未执行 | no_violation_detected，无未决核验 | 未执行 | 未执行 |

原Q42的有限规则解析命中“禁止/避免：不含稀释剂、盐酸、氢氟酸成分；”，定位原回答字符偏移并核对回切内容；禁止对象为“不含”，与可信规范方向相反；原错误句为未明确撤回的生效裸指令。后文正确说明不抵消前段。

额外使用**保存的上轮真实V3响应离线回放**，直接调用当前生产`_score_business`：原Judge PASS保持不改、Guard confirmed_violation、最终FAIL、qualification_blocking=true、safety_review_required=false。Parser/Matcher通过该旧响应结构与原句定位校验。该结果只证明当前程序集成可处理旧响应，并非本轮模型再次作答。

两条控制直接运行同一生产Guard：均未确认违规，无未决review；纠错句被作为明确撤回的错误引用处理。没有为控制编造新的真实LLM PASS。授权后仍须检查真实LLM及最终裁决均PASS，且qualification_blocking=false；即使最终业务PASS，只要inconclusive导致资格阻断，仍按未满足本轮完整验收记录。

[完整Guard检查](../backend/reports/hybrid-real-integration-20261020/offline-guard-check.json)、[旧响应经生产评分路径回放](../backend/reports/hybrid-real-integration-20261020/saved-response-production-replay.json)。资格/发布边界沿用当前实现，不实际执行Candidate资格事务或发布；一条Q42失败不等于可以推断某个未运行Baseline50的整体Gate成绩。

## 4. 成本上界与拟申请授权

配置模型`deepseek-v4-flash`，端点`https://api.deepseek.com/chat/completions`。按本轮核实的官方高峰未缓存输入¥2/百万、输出¥8/百万计算，不使用缓存或非高峰折扣；模型旧别名的服务映射以Provider实际回包为准。[DeepSeek官方价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)

保留temperature=0、JSON、非流式及每次32768输出上限，没有为压价截断Final或降低既有输出限制。生产粗估输入合计13,051 Token，仅供参考；预算预留采用更保守的**实际生产HTTP body字节数+每次1024封装余量**作为输入Token代理，加每次满额输出，避免把字符比例估算当成精确分词器。

| 顺序 | 实际HTTP body字节 | 输出Token上限 | 保守费用上界 |
|---|---:|---:|---:|
| 1 | 46,514 | 32,768 | ¥0.357220 |
| 2 | 26,129 | 32,768 | ¥0.316450 |
| 3 | 26,333 | 32,768 | ¥0.316858 |
| 合计 | 98,976 | 98,304 | **¥0.990528** |

申请范围：**最多3次、每条一次、串行、零重试，总预算¥1**。这是基于当前价格/请求限制的保守合理上界，不是账户发票保证；授权后发送前仍核对价格、SHA、预算并通过既有隔离账本逐次预留，回包按真实Usage计算估算费用。当前实际调用0、Token0、费用¥0、真实请求耗时不适用。

## 5. 数据保护与停止条件

正式SQLite以`mode=ro`、`query_only`读取，29张表全量行数/逻辑SHA与此前保护清单一致，含Golden、评测、Candidate、Approval及历史记录。16项索引制品、4份PDF来源SHA一致，Prompt/Guard/生成等生产代码无本轮Diff。5类正式任务表无running/queued/pending/generating/evaluating记录；正式服务未重载。没有写正式Usage、改分或运行检索。

[正式表保护指纹](../backend/reports/hybrid-real-integration-20261020/protection.json)、[知识资产指纹](../backend/reports/hybrid-real-integration-20261020/asset-protection.json)。收到授权后每次发送前再次确认，预检查不能保证未来没有其他任务启动。

严格按上述顺序，逐条回包后复核，遇以下任一条件立即停止，不发送下一条：

- Q42 Guard未独立识别真实适用的反向禁令，或最终错误PASS；原LLM PASS本身不触发停止。
- 任一正确控制LLM/最终结果错误FAIL、Guard误报违规，或无依据资格阻断；纠错控制inconclusive也不计完整通过。
- 规则、来源、请求/版本身份异常；原响应被覆盖或关键解析/Matcher异常。
- Provider执行/Usage不明确、响应不完整或预计继续超预算；不重试。
- 正式数据/知识资产改变或存在活动正式任务。

原Judge JSON、Guard证据、最终业务裁决和资格风险分别存独立专项证据；不修改原始响应。不得自动改Prompt、规则或答案后再试，不扩大范围，不自动Baseline50/A/B/C/Sandbox。

## 6. 当前结论与后续决策

**已具备申请最多3次真实调用的准备条件。尚未完成本轮真实集成验收，无法确认三条均通过；Baseline50仍等待本轮结果及独立授权。**

若三条真实结果全部符合目标，Guard独立确认Q42违规、正确控制不误杀且没有不当资格阻断，则建议结束本轮Q42专项，进入新版Baseline50独立授权准备。有限规则及3条小样本仍不能证明所有自然语言安全问题准确；不据此自动执行Baseline50。

本次提交仅本报告及隔离预检查证据，No SPEC Change；业务合同和实现均未变，未运行无关构建或全面审计。收到明确付费授权后再更新真实Verdict、checks/issues、Parser/Matcher、真实Token、耗时、费用及停止原因。
