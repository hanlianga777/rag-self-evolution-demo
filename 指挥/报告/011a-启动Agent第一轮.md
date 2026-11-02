# 011a：启动 Agent 第一轮

**按任务单规定的“方案生成失败就停”分支收尾：实验已创建，Agent 返回 A/B/C 三份草案，但三份均被产品校验拒绝；自动循环和 Sandbox 没有启动。** 不是成功启动，也没有合格方案。真实 DeepSeek 调用 1 次，保存估算费用 **USD 0.00344985**，试跑 **0 / 12 次**，D 的 1 次额度没有使用。来源：正式库 `experiments`、`agent_traces`、`candidate_configs`，以及现有 POST 接口的 HTTP 409 响应。

## 实验与时间

- 实验编号：`EXP-20261102165726567823`。
- 绑定 Baseline：`EVAL-20261102140722852830`，已完成，回答 high、判分 low。当前指定记录 id=3，42/50、10/11 门槛通过。来源：`GET /api/evaluation?active_task=true&light=true`、`baseline_designations`、010b报告。
- 创建/发起生成：2026-11-02T16:57:26.567865+00:00（多伦多 2026-11-02T11:57:26.567865-05:00）。
- 接口返回：2026-11-02T16:57:53.590941+00:00。Agent 本次请求开始于 `2026-11-02T16:57:26.572318+00:00`，保存耗时 26975 毫秒。
- 最终核对时间：2026-11-02T16:58:40.003846+00:00。状态 `failed`，`result.generation_status=failed`，`result.validation_stage=schema`，`result.generated_candidate_count=0`，正式候选列表为空。
- 循环启动时间：无；没有调用 `/api/experiments/EXP-20261102165726567823/run-cycle`。首套方案前 2–3 题结果：**未执行，没有结果**。

## 执行依据、断点与理解

先读取根目录 `AGENTS.md`、`指挥/README.md` 和本任务单，再核对只读 Git 记录、报告、API 和正式库。开始时工作区干净，没有011a报告；最近提交 `89ed4cb` 是本单开始记录，正式库 `experiments`、`candidate_configs`、`agent_traces` 均为空，因此没有可续用的011a半成品或已付费方案。本次没有执行任何会修改仓库状态的 Git 命令，没有改 `指挥/当前任务.md`。

开始时 `GET /api/evaluations?active_only=true` 返回空列表；没有运行中的实验、候选、Golden生成或修订任务。010a max/high/low/review均已结束；010b review保存状态为failed、16/16份复核执行已保存，技术异常1，不在运行中。已有后端 PID 6451、前端 PID 88255 属于本项目，服务健康，未重启。

**我是这样理解的：** 任务背景称Q46为真错，但010b报告及当前Baseline保存结论均将Q46列为“复核技术异常、未知”。沿用产品现有筛选：真错目标Q04、Q06、Q24、Q27、Q29，不稳定题Q17、Q37需保持判对，Q46待复核；没有手工改复核结论或扩大Agent目标。来源：Baseline的 `result.baseline_review`、`product_diagnostics.review_summary`（目标5、不稳定2、待复核1），以及本次草案原文。

**我是这样理解的：** `/api/experiments/run` 一次请求返回HTTP 409、`generation_status=failed`、`retryable=false`、合法候选0，已命中任务单“方案生成失败”停止条件。故按指定分支写报告并归档任务，不另发付费请求、不手工修草案、不修产品代码、不启动循环。这是任务单预定停止分支，不表示A/B/C试跑目标达成。

## 三份草案的检查结论

| 检查项 | 观察结果 |
| --- | --- |
| 方向互不相同 | 三套改动参数集合不同：A为query_rewrite、multi_query、candidate_k；B为rerank、top_k、metadata_filter；C为query_decompose、alias_mapping、prompt_strategy、generation_thinking。仅说明草案方向不同，不代表通过合法性校验。 |
| 每个参数的原值、新值、预期影响点名目标 | A/B原文每项均点名目标；C的prompt_strategy影响只提Q46/Q37而非其目标Q29/Q24，generation_thinking影响未点名题号，未满足本单逐参数点名要求。产品实际先在目标ID校验处拒绝，未执行到后续参数/干预校验。 |
| 风险 | 三份都有风险，点名题号和指标；原文完整附后。 |
| 重复失败签名 | 开始前无历史实验、失败签名；本次三个参数签名互异。三份被拒后，系统已记录三个失败签名，未消耗Sandbox次数。 |
| 最终是否可试跑 | 全部被拒，正式候选0。不能把草案当作已通过校验或合格方案。 |

来源：`agent_traces.result_json.provider_raw_text`、`rejected_candidates`、`failed_parameter_signatures`；实际校验顺序见 `backend/app/optimization.py` 的 `prepare_response`。

## 被拒草案及原因

三份统一在 `schema` 阶段的 `target_bad_cases` 字段被拒。Agent用了展示题号，系统只接受正式题目ID或Bad Case ID。例如Q29应引用 `CSV-20261101100758945425-29` 或 `BC-EVAL-20261102140722852830-CSV-20261101100758945425-29`。这说明目标引用没有通过校验；不能据此认定题目不存在或方案效果差。

| 草案 | Agent实际引用 | 产品保存的拒绝原因 |
| --- | --- | --- |
| A | Q29、Q24 | Agent Candidate A target_bad_cases 引用了不存在的当前证据：Q29, Q24 |
| B | Q27、Q06、Q04 | Agent Candidate B target_bad_cases 引用了不存在的当前证据：Q27, Q06, Q04 |
| C | Q29、Q24 | Agent Candidate C target_bad_cases 引用了不存在的当前证据：Q29, Q24 |

三个保存失败签名：

- `3356f82e82ba4833dfd2fe65ec831c136b52d9b870c615285a7a104d19fc7417`
- `514c3b4a890c01faa25f00446b90c8496a548bce64fd2e7453ab9350b622194c`
- `cbefa2ae92cc16556e2304eee36d235ebde3ad83c3aecf6273b6774e450cb93d`

未改写展示题号为正式ID，未修改参数、风险、干预方向，也未绕过现有校验。其他可能的参数和干预合法性问题尚未由产品校验完成，结论未知。

## 三套方案原文

下列内容直接取自 `agent_traces.result_json.provider_raw_text`，保留本次Agent完整JSON原文；包括方案名、核心思路、每项原值→新值→预期影响、风险、目标题号和理由。**均为被拒草案，所有“预计修好”均是Agent假设，没有Sandbox结果支撑。**

```json
{"candidates":[{"id":"A","action_name":"查询改写与多路扩展","strategy_name":"「查询改写多路扩展」（检索优先）","core_idea":"先用查询改写把口语问题标准化，再多生成互补问法并扩大候选数，让原本未进候选的标准证据有机会被召回。","adjustments":[{"parameter":"query_rewrite","baseline_value":false,"candidate_value":true,"expected_impact":"预计修好Q29、Q24"},{"parameter":"multi_query","baseline_value":false,"candidate_value":4,"expected_impact":"预计修好Q29、Q24，并有望稳定Q17"},{"parameter":"candidate_k","baseline_value":12,"candidate_value":24,"expected_impact":"预计修好Q29、Q24"}],"risks":[{"question_ids":["Q27","Q04","Q06"],"metric":"检索噪声比例/安全拒答率","reason":"候选数扩大且多路查询会引入更多近邻内容，可能让本已重排下沉的Q27/Q04更难进入最终内容，并增加Q06的无关上下文。"}],"hypothesis":"检索失败主要来自用户口语与手册表述不一致，先改写再扩展多路问法能提升标准证据进入候选的概率。","why":"Q29和Q24均表现为标准证据未进入候选，属于优先修复的检索失败；Q17虽为不稳定题，不作为必修目标，但同属未进候选问题，可观察是否受益。","target_bad_cases":["Q29","Q24"],"config_diff":{"query_rewrite":true,"multi_query":4,"candidate_k":24},"expected_improvement":"Q29、Q24的标准证据预计进入候选并通过证据覆盖；Q17作为不稳定题保持判对不作为必修目标。","risk":"候选增多可能加剧检索噪声，Q27/Q04/Q06有退化风险；安全拒答率可能因无关上下文波动。"},{"id":"B","action_name":"重排收紧与元数据回退","strategy_name":"「重排收紧保留」（检索优先）","core_idea":"减少重排模型对候选的二次压序，改用原问题关键词重排并适度增加最终保留条数，同时用型号元数据回退缩小噪声范围。","adjustments":[{"parameter":"rerank","baseline_value":true,"candidate_value":"query_only","expected_impact":"预计修好Q04、Q06，争取Q27"},{"parameter":"top_k","baseline_value":4,"candidate_value":6,"expected_impact":"预计修好Q04、Q06，争取Q27"},{"parameter":"metadata_filter","baseline_value":"OFF","candidate_value":"FALLBACK","expected_impact":"预计降低Q06、Q04的噪声干扰"}],"risks":[{"question_ids":["Q29","Q24","Q17"],"metric":"检索召回率/答案完整率","reason":"元数据FALLBACK可能在型号识别偏差时过滤掉正确资料，Q29/Q24这类检索失败题若标准证据本就在候选外，本方案帮助有限；Q17也可能继续未进候选。"},{"question_ids":["Q06","Q04"],"metric":"最终上下文精确度","reason":"保留6段资料会增加无关段落进入回答的机会，可能稀释安全要点。"}],"hypothesis":"检索噪声题的标准证据已进候选但被重排压到后面，改为轻量关键词重排并增加保留条数，可把关键段落送回最终内容。","why":"Q27、Q06、Q04均属于标准证据已进候选但最终未进入的检索噪声，优先按检索噪声方向加强重排与保留条数。","target_bad_cases":["Q27","Q06","Q04"],"config_diff":{"rerank":"query_only","top_k":6,"metadata_filter":"FALLBACK"},"expected_improvement":"Q04、Q06预计把重排第5/6位证据纳入最终内容，Q27争取通过轻量重排改善位次。","risk":"元数据回退可能误伤跨型号或别名问题；保留条数增加可能降低上下文精确度并影响安全拒答率。"},{"id":"C","action_name":"问题拆分别名映射与分级澄清","strategy_name":"「拆分别名分级答」（检索优先）","core_idea":"先拆开多意图问题并用已审核别名映射统一设备称谓，再以分级回答处理证据不足时的澄清，兼顾检索召回和安全拒答门槛。","adjustments":[{"parameter":"query_decompose","baseline_value":false,"candidate_value":true,"expected_impact":"预计修好Q29、Q24"},{"parameter":"alias_mapping","baseline_value":false,"candidate_value":true,"expected_impact":"预计修好Q29"},{"parameter":"prompt_strategy","baseline_value":"Grounded","candidate_value":"Tiered","expected_impact":"不把Q46/Q37列为目标，但预计降低安全拒答门槛波动"},{"parameter":"generation_thinking","baseline_value":"high","candidate_value":"max","expected_impact":"预计提升澄清与安全要点的覆盖稳定性"}],"risks":[{"question_ids":["Q06","Q04"],"metric":"安全答案完整率/延迟","reason":"Tiered可能倾向先澄清而少给完整安全步骤，Q06/Q04的电气安全和存放要点可能被追问打断；generation_thinking最高档会增加延迟。"},{"question_ids":["Q29","Q24"],"metric":"答案精确度","reason":"拆分和别名映射若识别偏差，可能改变检索意图或引入错误型号资料。"}],"hypothesis":"对多意图、设备称谓不一致的问题先拆解并映射别名，可补足检索失败；分级回答可在证据不足时做必要澄清，维持安全拒答门槛。","why":"Q29涉及B2称谓与多项检查，Q24是较泛化的安全提示，拆分与别名映射可改善未进候选；Q37/Q46不作为确认目标，仅通过Tiered保留更稳的澄清路径。","target_bad_cases":["Q29","Q24"],"config_diff":{"query_decompose":true,"alias_mapping":true,"prompt_strategy":"Tiered","generation_thinking":"max"},"expected_improvement":"Q29、Q24预计进入候选并覆盖必答要点；安全拒答率通过分级澄清争取达到95%门槛，但不将Q37/Q46作为必修目标。","risk":"分级回答可能对安全类问题过度澄清，Q06/Q04有完整率下降风险；最高思考档增加耗时和费用。"}]}
```

## 查进度的方法（浏览器直接打开，均只读）

1. [本次实验详情](http://127.0.0.1:8010/api/experiments/EXP-20261102165726567823)：核对 `id`、`baseline_run_id`、`status`；看 `result.generation_status`、`result.validation_stage`、`result.validation_error` 和 `result.rejected_candidates` 找生成失败原因。`result.provider_raw_text` 是三份草案原文。本次 `status=failed`、`candidates=[]`。
2. [当前优化概览](http://127.0.0.1:8010/api/optimization?light=true)：核对 `current_baseline_id`、`id`、`status` 和 `evaluation_budget`。本次 `used=0`、`max=12`、`reserved_for_d=1`。
3. [活动评测](http://127.0.0.1:8010/api/evaluations?active_only=true)：本次收尾返回 `[]`，没有活动Sandbox。
4. [当前Baseline](http://127.0.0.1:8010/api/evaluation?active_task=true&light=true)：看 `current_baseline_id`、`judge.judge_thinking.reasoning_effort` 和复核结论。

循环相关字段在本次不存在，因为循环没有启动。以后如果另有任务成功启动，现有产品字段读法如下，来源为 `backend/app/optimization_cycle.py`、`evaluation.py`、`governance.py`：

- 当前哪套：实验的 `candidates` 内查 `status=running`，看 `id`、`reasoning.candidate_label`、`reasoning.round`；循环的 `result.optimization_cycle.phase` 区分 `analysis`、`sandbox`、`review`。
- 完成几题：候选有 `result.evaluation_run_id` 后，打开 `http://127.0.0.1:8010/api/evaluations/对应的评测编号`；看 `result.completed` / `result.total`、`cases` 和 `result.auto_recovery.question_id`。`result.technical_errors`、`result.checkpoints` 可进一步看错误、当前阶段及内部重试，不能只凭外层错误计数判断完全无异常。
- 用了几次：实验 `evaluation_budget.used`，上限 `max=12`，`reserved_for_d=1`；现有ABC流程最多用11次，D留1次。`used` 包括已经占用的运行中试跑。
- 是否结束：`result.optimization_cycle.status` 为 `running` 表示在跑；`qualified`、`budget_exhausted`、`analysis_exhausted`、`failed` 表示该循环已结束或停止。本次字段缺失表示未启动，不能写成循环已跑完。
- 是否有合格方案：候选 `status=evaluated` 且 `result.qualification.qualified=true`；草案、已生成候选和部分题结果都不足以证明合格。本次候选0，所以没有合格方案。

不要通过再次POST生成或run-cycle来“查看进度”。本单没有循环轮询，也没有等待整轮试跑。

## 备份、数据与服务

- 写正式库前SQLite在线备份：`/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/data/audit_backups/task011a-20261102T165718Z.db`，大小195,096,576字节。`PRAGMA quick_check` 返回 `ok`；备份中实验数为0，确认在本次创建前完成。按 `keep_recent_two(..., 'task011a')` 管理同类最多两份。
- 本次只新增1个失败实验、1条Agent追踪，无正式候选、无新评测。结束核对 `dataset_versions`、`questions`、`evaluation_runs`、`evaluation_case_results`、`bad_cases`、`approvals`、`production_versions`、`recommendations`、`baseline_designations` 的行数与内容SHA-256全部和开始前一致。未改题目、判分、门槛、发布规则；未确认报告、未跑D、未发布。来源：正式库前后只读查询；本地核对断点 `backend/data/task011a/state.json`。
- 后端和前端保持运行，未启动测试浏览器或额外服务。最终实验详情、优化概览、Baseline、活动评测接口均HTTP 200，前端首页及 `#evaluation`、`#evolution` URL均HTTP 200。该检查证明HTTP可达，未做浏览器点击验收。无业务代码修改，未额外跑测试或付费验证。
- 数据库、备份、完整API响应及本地断点只留在 `backend/data/`，Git状态没有显示这些本地数据。交付文件仅本报告和任务单归档；保存和推送交给值班脚本。

## 调用次数与费用

| 项目 | 次数 | 费用 |
| --- | ---: | --- |
| DeepSeek Agent生成 | 1 | USD 0.00344985（保存估算） |
| Sandbox回答、判分、回归复核、D | 0 | 无本次调用 |
| Alibaba向量/重排或其他Provider | 0 | 无本次调用 |

输入5,271词元，输出4,432词元（包含思考2,998），缓存命中0，总计9,703。请求ID `758d1423-ba31-4981-a5f4-c087f7861f07`；`task=agent`、`reasoning_effort=high`。这是Agent的档位；本单要求的判分low已核实，本次并未发起判分。

费用来源：Agent追踪保存的 `token_usage` 与 `cost_estimation`，价格快照版本 `deepseek-flash-2026-09-30`，计费时段 `off_peak`，每百万输入USD 0.15、输出USD 0.60：`(5271×0.15 + 4432×0.60) / 1000000 = 0.00344985`。费用是本机配置和真实Usage的估算；实际扣费账单未知。本报告未查询外部实时价格或账单。失败调用已计入1次，不会因为草案被拒而算作免费；不消耗的是Sandbox试跑次数。

## 待回答问题与后续状态

- 展示题号与正式ID的输出/校验不一致，后续修复或重新运行需要另张任务处理。本单未修复，也未重复花钱生成；没有待用户在线确认的操作。
- 合法A/B/C、自动循环、首套方案前2–3题验证均未达成，原因是预定停止条件已触发。Q46复核结论仍未知。
- 按任务单“遇到这些情况就停，写进报告后照常收尾”执行归档；不继续队列中的其他任务，不等待回复。
