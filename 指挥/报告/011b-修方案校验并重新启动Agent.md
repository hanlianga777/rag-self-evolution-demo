# 011b：修方案校验并重新启动 Agent

本单已修正 Q46 复核读取与题号校验，新实验 `EXP-20261102214606947837` 已生成合法 A/B/C 并启动自动循环。核验时首套 A 已完成前两题，Q01、Q02 均有效通过，无技术失败；Q03 正在判分。按任务单到此收尾，demo与自动循环保持运行，没有整轮成绩或合格结论。

## 执行依据与断点

先读根目录 AGENTS.md、指挥/README.md 和 011b 任务单；只读 Git 状态与近期历史后，未发现 011b 半成品、已付费生成或已有报告。011a 的失败实验保留为历史，没有重复执行其已付费请求。开始时活动评测接口为空，正式库实验仅 011a failed、候选为零；Golden 生成与修订无运行任务，followups 保存作业均 completed。没有执行修改仓库的 Git 命令，没有改指挥/当前任务.md。保存推送交给值班脚本。

我是这样理解的：内部重试记录是技术过程，成功得到有效布尔判分就正常计票；只有重试后仍拿不到有效结果才停止。此前 technical_stop_audit 保留为历史记录，并追加 011b 规则纠正说明。任务单要求的新实验通过现有 GovernanceStore.create_experiment 创建，随后调用现有 POST /api/experiments/run 生成；没有手工写候选或修改方案内容。

## Q46 与门槛归因前后对比

| 项目 | 修正前 | 修正后 |
| --- | --- | --- |
| Q46 | 未知（把第一次复核内部重判前的引用错误当最终失败） | 真错，3 次错 2 次；原判错、第一次复核对、第二次复核错 |
| 真错题 | Q04、Q06、Q24、Q27、Q29，共5题 | 加上 Q46，共6题 |
| 不稳定题 | Q17、Q37 | 不变 |
| 待复核未知 | Q46 | 0题 |
| 安全拒答门槛归因 | Q46待复核，归因未知；回答问题优先级2 | Q46真错、Q37不稳定；回答问题优先级1 |
| 概览待优化 Bad Case | 5 | 6 |

安全拒答率仍为90%，要求95%，未通过；正式Baseline仍为 `EVAL-20261102140722852830`，42/50、10/11门槛通过，判分low。没有重跑题或改变正式分数。复核结论只用已保存的三票重算，`baseline_review.complete` 从 false 恢复为 true。来源：正式库 evaluation_runs.result_json.baseline_review、evaluation_case_results；重启后的 evaluation/overview API 与浏览器概览。

改动：`backend/app/agent_inputs.py` 不再把成功恢复的Judge错误当失败；`backend/app/evaluation.py` 保留内部重判，stop_on_error仅在最终失败时停止；`backend/app/followups.py` 不因恢复过程停止，也不把成功恢复计入技术失败；`docs/BASELINE_REVIEW_RULES.md` 说明规则。原始重试、请求与Usage没有删除。

## 题号、失败签名与逐参数检查

`backend/app/optimization.py` 接受展示题号、正式题目ID、Bad Case ID。展示题号只从当前 Baseline 已保存题目诊断对照生成确定性映射，转换为正式题目ID再保存；不认识、有歧义、同一目标重复引用均拒绝。Agent 原始JSON保留在 trace 和 parsed_json 中。提示词改为 `"target_bad_cases":["Q04"]`，明确可用展示题号。

011a实验 `EXP-20261102165726567823` 保留，原三份格式拒绝签名从 active failed_parameter_signatures 移入 format_rejected_parameter_signatures，并标注不参与重复检查；原 agent_traces 保留原样。新实验的失败签名列表为空。后续校验拒绝只保存理由，不再作为试跑效果失败加入签名；真实失败或不合格候选仍由原逻辑加入。`backend/app/optimization_cycle.py` 仅同步更正对应注释。

逐参数点名检查**原来就有，未修改检查逻辑**，仍要求每个调整项对应原值、新值，预期影响点名目标；仅加强提示词明确“每个参数”。011a原始JSON回放：A/B越过ID校验；C越过ID校验后被原有预期影响检查拒绝（generation_thinking没有点名目标题号，prompt_strategy也未点名其目标）。不消耗Sandbox次数。

## 测试与页面

相关后端6个测试文件共45项全部通过（任务011b、010b失败停止、010b低档基线、007复核、009循环、optimization合同）。先看到题号和Q46旧逻辑的复现失败，再修正为通过。覆盖原始011a草案、展示题号转正式ID、未知题号拒绝、正式/Bad Case ID兼容、别名重复、失败签名不增加、成功重判有效、最终失败仍未知、后台恢复后不停止。测试只用临时库、临时目录和Stub，没有Provider调用。另对循环注释变更后复跑4项循环测试通过。`git diff --check` 通过。

用 headless Playwright 实际打开概览、Baseline、Agent工作台，等待对应页面标题与正文完成加载，三个页面均成功渲染、pageerror为0；概览实际显示“待优化 Bad Case 6 道”。只做只读页面验收，未点击付费/发布按钮。第一次浏览器脚本误把hash切换的空response当HTTP响应而退出，第二次又发现仅等networkidle仍可能抓到加载态；最终增加页面标题和正文就绪检查后验收通过。每次均在finally关闭测试浏览器，截图与完整证据只保存在backend/data/task011b，不提交。

## 新实验、三套方案原文

- 新实验：`EXP-20261102214606947837`，绑定 Baseline `EVAL-20261102140722852830`。
- 生成开始：2026-11-02T21:46:06.949867+00:00；结束：2026-11-02T21:46:37.551201+00:00（UTC）。真实Agent生成1次，HTTP201，候选3，拒绝0；未人工修改方案。
- 循环请求：2026-11-02T21:46:51.280308+00:00；确认启动：2026-11-02T21:46:51.539228+00:00（UTC），run-cycle HTTP201。
- 生成后预算0/12，D留1次；循环启动会占用首套一次，启动后不重启后端。
- 三个参数方向集合不同，签名互异；每个参数预期影响点名其目标题号，三套有具体风险；重复失败检查通过。来源：experiment.result、candidates.reasoning 和原始JSON。

以下是**本次Agent原始回复**。包括方案名、核心思路、每个参数原值→新值→点名题号的预期影响、风险、目标错题；均是待验证假设，不能当成已经修好。

```json
{"candidates":[{"id":"A","action_name":"分级澄清回答","strategy_name":"「分级澄清回答」（回答优先）","core_idea":"遇到信息不全或需要判断设备状态的问题时，先给出证据能确定的部分，再追问1–2个最关键条件，不猜测缺失信息；安全警告必须完整保留。","adjustments":[{"parameter":"prompt_strategy","baseline_value":"Grounded","candidate_value":"Tiered","expected_impact":"预计修好Q46：当缺少连接模式与机器人网络状态时，先追问关键条件；同时保持Q37判对"}],"risks":[{"question_ids":["Q06","Q29"],"metric":"答案完整性","reason":"分级策略可能把证据充分的问题误判为条件不足，增加不必要追问，降低直接可答题的完整性。"},{"question_ids":["Q37"],"metric":"安全拒答率稳定性","reason":"Q37为随机波动题，策略改变可能影响其澄清触发，需要保持原判对，不能作为必修目标。"}],"hypothesis":"对信息不全的负向题采用分级澄清，比直接给步骤更能满足安全拒答要求。","why":"Q46被判为澄清不足，缺少追问连接模式与机器人网络状态；Tiered策略正好支持先说明可确定部分再追问关键条件。Q37为随机波动，不作为优化目标但需保持判对。","target_bad_cases":["Q46"],"config_diff":{"prompt_strategy":"Tiered"},"expected_improvement":"Q46完成必要澄清，安全拒答率从90%提升到至少95%，且不把Q37作为必修目标。","risk":"可能对证据充分题增加不必要澄清，影响Q06/Q29的直接回答完整性及Q37稳定性。"},{"id":"B","action_name":"扩大召回并多路查询","strategy_name":"「扩大召回+多路查询」（检索优先）","core_idea":"针对问法与手册术语不匹配的标准证据未进候选问题，扩大候选池并用多个互补问法检索，覆盖“不带电检查”“清洁剂安全提示”等同义表达；同时保留分级澄清修复Q46。","adjustments":[{"parameter":"candidate_k","baseline_value":12,"candidate_value":24,"expected_impact":"预计修好Q29、Q24：让标准证据进入候选池"},{"parameter":"multi_query","baseline_value":false,"candidate_value":4,"expected_impact":"预计补足Q29检查项目、Q24清洁剂安全提示的多种问法召回"},{"parameter":"prompt_strategy","baseline_value":"Grounded","candidate_value":"Tiered","expected_impact":"预计修好Q46并保持Q37判对"}],"risks":[{"question_ids":["Q04","Q06","Q27"],"metric":"检索噪声与最终答案准确性","reason":"候选从12扩到24并多路查询会引入更多相近段落，重排后可能挤占原本靠前证据，Q04/Q06/Q27仍有筛选风险。"},{"question_ids":[],"metric":"延迟","reason":"多路查询和更大候选池会增加检索与重排耗时。"}],"hypothesis":"检索失败题需要先扩大召回并增加语义互补问法，使未进候选的标准证据进入候选，再由原有重排筛选。","why":"Q29与Q24均显示标准证据未进入候选，属于检索失败；Q46需要通过Tiered补足澄清要求，否则方案无法通过安全拒答门槛。Q37为随机波动，不作为优化目标。","target_bad_cases":["Q29","Q24","Q46"],"config_diff":{"candidate_k":24,"multi_query":4,"prompt_strategy":"Tiered"},"expected_improvement":"Q29与Q24的标准证据进入候选并进入最终上下文，Q46完成澄清，安全拒答率达到至少95%。","risk":"更多候选可能增加噪声与延迟，并影响Q04/Q06/Q27的最终排序。"},{"id":"C","action_name":"放宽最终保留条数并分级澄清","strategy_name":"「增加最终保留条数」（检索优先）","core_idea":"针对证据已在候选但被top_k=4截掉的检索噪声题，将最终上下文从4段增至6段，纳入重排第5/6位证据；同时用分级澄清修复Q46。","adjustments":[{"parameter":"top_k","baseline_value":4,"candidate_value":6,"expected_impact":"预计修好Q04（重排第5）、Q06（重排第6）"},{"parameter":"prompt_strategy","baseline_value":"Grounded","candidate_value":"Tiered","expected_impact":"预计修好Q46并保持Q37判对"}],"risks":[{"question_ids":["Q27"],"metric":"检索噪声与答案准确性","reason":"Q27标准证据重排第12，top_k=6仍无法纳入，且增加上下文可能引入干扰。"},{"question_ids":["Q29","Q24"],"metric":"答案准确性","reason":"最终上下文增加后，若噪声段混入，可能分散生成，影响原本可答内容。"},{"question_ids":["Q46"],"metric":"安全拒答率","reason":"更多上下文可能让负向题更容易被无关证据诱导作答，需要Tiered澄清约束；若约束不足，Q46仍可能失败。"}],"hypothesis":"当标准证据已进入候选但被最终保留条数截断时，适度增加top_k可直接修复漏选；负向题再用Tiered补足澄清。","why":"Q04与Q06均显示标准证据已在候选且重排位次为第5/第6，只因top_k=4未进入最终内容；Q46需分级澄清才能通过安全拒答门槛。Q27重排第12，不能作为本方案可修目标。","target_bad_cases":["Q04","Q06","Q46"],"config_diff":{"top_k":6,"prompt_strategy":"Tiered"},"expected_improvement":"Q04与Q06的漏选证据进入最终上下文，Q46完成澄清，安全拒答率达到至少95%。","risk":"Q27仍可能漏选，且更多上下文可能引入噪声、影响答案准确性和延迟。"}]}
```

## 被拒草案

本次生成没有被拒草案。011a拒绝与本次离线回放结果见前文，不混算为本次新付费结果。

## 第一套前几题

唯一一次循环启动后的进度核验时间：2026-11-02T21:48:02.692720+00:00（UTC）。首套 A：`EXP-20261102214606947837-R1-A`；Sandbox：`EVAL-20261102214652063044`，状态running，完成2/50，预算1/12。

| 展示题号 | 正式题目ID | 有效判分 | 业务判定 |
| --- | --- | --- | --- |
| Q01 | CSV-20261101100758945425-01 | 对 | PASS |
| Q02 | CSV-20261101100758945425-02 | 对 | PASS |

两题均保存回答、Judge和完整业务判定；已保存checkpoints中 generation/judge 阶段均ok，没有error attempt、technical_error或response_recovery。核验时Q03已保存回答、正在judge，不把它计成已完成；result.technical_errors=[]，technical_failed=0，循环last_error为空。满足任务单前2–3题正常结果条件，随后不再获取循环进度、不等待全部跑完。后续成绩和最终资格未知。来源：上述Sandbox详情接口，完整响应只存本地 sandbox-observed.json。

## 查进度的方法

1. `http://127.0.0.1:8010/api/experiments/EXP-20261102214606947837`：看id、baseline_run_id、status；candidates中 status=running 是当前套，reasoning.candidate_label 和 round 给出套名与轮数。result.optimization_cycle.phase 为 analysis/sandbox/review，status=running 表示在跑，qualified/budget_exhausted/analysis_exhausted/failed 表示结束；last_error 查看停止原因。
2. 候选 `result.evaluation_run_id` 给出Sandbox编号；打开 `http://127.0.0.1:8010/api/evaluations/对应评测编号`，看 result.completed / total、cases、auto_recovery.question_id；technical_errors 和 checkpoints 查看最终错误、阶段及内部重试。内部错误恢复成功不算最终技术失败，不能只看某个历史错误。
3. 实验 evaluation_budget.used/max/reserved_for_d 看预算，含运行中已占用的试跑；ABC最多11次，D留1次。qualified 只能看完整evaluated候选的 result.qualification.qualified，部分题输出不代表合格。
4. `http://127.0.0.1:8010/api/optimization?light=true` 看当前Baseline、实验和预算；`http://127.0.0.1:8010/api/evaluations?active_only=true` 看活动评测；`http://127.0.0.1:8010/api/evaluation?active_task=true&light=true` 看固定Baseline与判分档位。

不要再次POST生成或run-cycle来查进度。

## 备份与数据边界

改正式库前在线备份：`/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/data/audit_backups/task011b-20261102T214512Z.db`，PRAGMA quick_check=ok，同类备份最多两份。只重算已保存复核结论、标注011a格式拒绝签名，并新增新实验和后续Sandbox记录；不改题目、判分、门槛、发布规则，不人工确认，不跑D、不发布。前后与备份逐项核对：dataset_versions、questions、approvals、production_versions、recommendations、baseline_designations 的原有行及总数未变；evaluation_case_results、bad_cases 的所有原有行哈希未变（只允许本次后台追加新行）。Baseline除baseline_review外全部字段、全部原有逐题判分、8题复核检查点和原011a Agent trace均保持一致。来源：在线备份与正式库只读比较，本地preservation.json；本地断点backend/data/task011b/state.json。

本单正常重启后端一次，旧PID6451，由已有supervise_api.sh拉起新PID22275；循环由新PID承接。启动后demo保持运行，不终止后端/前端。

## 调用次数和费用

截至2026-11-02T21:48:02.692720+00:00（UTC）的已保存Usage：

| 项目 | 已保存调用数 | 费用 |
| --- | ---: | --- |
| Q46重算、011a签名更正、测试 | 0 | 无模型调用 |
| Agent生成 | 1次DeepSeek | USD 0.00385995（保存估算） |
| Sandbox回答 | 3次DeepSeek（含Q03已生成答案） | 与判分合计USD 0.00707194 |
| Sandbox判分 | 2次DeepSeek（Q01/Q02） | 同上，按DeepSeek子集重新汇总估算 |
| Sandbox向量/重排 | 6次Alibaba（3次向量、3次重排） | 未知；当前DeepSeek价格快照不能估算Alibaba费用 |
| D、发布 | 0 | 无本次调用 |

合计已保存6次DeepSeek、6次Alibaba，共12次Provider调用。DeepSeek已保存部分估算合计 **USD 0.01093189**。Q03判分在途，未出Usage，不能计为0次或免费；本次自动循环继续运行，后续调用和费用仍会增加。本报告不是整轮最终费用。Sandbox整体request_accounting.cost_estimation为unavailable/model_mismatch，因为混合了Alibaba与DeepSeek；本报告只对其DeepSeek事件子集使用原cost_report和同一快照汇总，没有把Alibaba费用算成0。

Sandbox已保存部分已知输入27007、输出7577词元；Agent输入5377、输出5089。价格来自本机 deepseek-flash-2026-09-30 快照，逐事件按保存开始时间和缓存Usage计算；实际扣费账单与Alibaba费用未知。来源：Agent trace token_usage/cost_estimation、Sandbox checkpoints 的 checkpoint_usage、request_accounting。

## 待回答问题

本单范围内没有未完成项或待在线回答问题。全部Sandbox、后续轮次、最终合格方案和完整费用尚未知，按任务单留给已启动的自动循环继续执行；没有等待整轮，不跑D、不发布。已写报告并按任务单归档，保存推送由值班脚本负责。
