# 008a：Agent优化前体检

执行日期：2026-11-01。任务来源：`指挥/队列/008a-Agent优化前体检.md`；起始提交 `fccb8ef`。

已完成本单体检。三项指定旧失败已按现行规则更新，相关23项通过；全量收集1211个测试方法，最终1056通过、117未通过、38跳过，**不是全量通过**。正式起点与15参数正确；Agent未读007b具体建议、补齐规划器状态不匹配、诊断重复计算，以及本地tokenizer缺失，均已查明并列在下文。按约束只修改测试，没有改Agent逻辑或正式数据。

## 1. 从哪里接着做

开始时工作区干净，没有008a报告或半成品；`git log --all --grep='008a|已做部分'`只见本单入队/开始记录，没有008a的部分实现。007a小测、50题Baseline、007b十次回答加十次判分均已完成，本单只读取已保存结果，没有重做付费步骤。来源：只读git记录、007/007b报告、正式库`evaluation_runs`。

## 2. 三项指定旧失败

修改前用隔离离线入口复现：3项全失败。

| 原测试 | 结论、处理与依据 |
| --- | --- |
| `test_round0_thinking.ThinkingTests.test_agent_new_parameters_keep_evidence_and_direction_contract` | 过时测试：还要求空`evidence_assertions`必须拦截，但任务004 E明确“对照表是优先，不是只能”，允许跨环节必要参数。改为验证方向建议可省略额外证据断言，同时仍拒绝非本轮保存的目标。现名`test_agent_new_parameters_allow_advisory_directions_but_require_saved_targets`。 |
| `test_round0_thinking.ThinkingTests.test_agent_new_stage_parameters_require_measured_bottleneck` | 过时测试：还把`performance_stage=unknown`当强约束。现行`validate_intervention`只校验实际改参、参数合法、保存目标和必填说明。改为验证未知建议阶段不阻断，非法参数值仍阻断。现名`test_agent_new_stage_parameters_allow_advisory_bottleneck_but_reject_illegal_values`。 |
| `test_task004_policy.Task004PolicyTests.test_review_unknown_request_errors_without_duplicate` | 过时测试：第二次进入仍期望旧包装文本`Unknown request`；决策14后的`perform_stage`保留原异常`unknown request`，允许再次进入并保留失败历史。更新文本预期，并补充断言：两次进入执行两次、保留两个unknown失败尝试、复核仍在第一遍且没有伪造成功回答。现名`test_review_unknown_request_keeps_failed_attempts_on_reentry`。不是只改大小写后继续声称绝不重复。 |

依据：`指挥/历史任务/004-底层改造.md` E节、`backend/tests/test_task004_agent.py`、`backend/app/optimization.py::validate_intervention`；重试依据`指挥/历史任务/006a-第一段续做.md`、`指挥/报告/006-机器检查.md`与`backend/app/evaluation_stage.py::perform_stage`。两项Agent断言并不是被决策14替换，决策14只解释第三项的重试语义。

验证命令：

```text
python3 scripts/test_v14_offline.py test_round0_thinking test_task004_policy test_task004_agent
```

结果：23项通过，0失败，耗时20.300秒。修改前3项已实际复现失败。没有修改Agent方案校验代码。

## 3. 全量测试

两轮都完整执行结束，没有只跑到首个错误就停。第一次在测试改动前完成收集与加载；第二次加载更新后的测试，作为最终结果。

| 统计口径 | 修改前 | 最终复验 |
| --- | ---: | ---: |
| 收集到的测试方法 | 1211 | 1211 |
| 通过的方法 | 1053 | **1056** |
| 未通过的方法（去重，含断言失败/执行错误） | 120 | **117** |
| 跳过的方法 | 38 | **38** |
| unittest的`testsRun` | 1209 | 1209 |
| unittest的失败断言记录（含子场景） | 115 | **112** |
| unittest的执行错误记录（含子场景） | 47 | **47** |
| unittest显示的跳过记录 | 37 | 37 |
| 全量耗时 | 1254.112秒 | 1240.343秒 |

口径说明：`HistoricalAuditPairs.setUpClass`一次跳过覆盖2个方法，unittest记1条skip，而且这2个方法不进入`testsRun`。所以方法口径是1056+117+38=1211；unittest原始摘要则是`Ran 1209 / failures=112 / errors=47 / skipped=37`。矩阵用例有多个失败子场景，不能把112+47当作159个不同方法。两轮失败/错误ID集合的差异恰好是指定3项消失，**没有新增失败或错误ID**。

完整明细为本报告附件：[008a-失败与跳过逐项分类.csv](008a-失败与跳过逐项分类.csv)，197行：159条失败/错误记录与38个跳过方法。每行有完整测试ID（保留子场景）、一句原因、三类归属、代码/任务来源及处理方式。没有把缺少夹具的错误改成通过。

| 分类 | 断言失败记录 | 执行错误记录 | 跳过方法 |
| --- | ---: | ---: | ---: |
| 过时测试 | 111 | 24 | 0 |
| 真问题 | 1 | 0 | 0 |
| 环境原因 | 0 | 23 | 38 |

过时测试主要包括：004之前的Unknown/探索/方向强约束；006之前的遇错停止、Usage未知阻断及旧终态；007a之前Baseline固定max；旧40条Seed题；旧发布/审批夹具；一次性HTTPError/BytesIO被新重试读取多次；Probe/QC桩返回MagicMock而无法写入JSON检查点。这里只更新本单指定3项，其余逐项记录，未把整批旧断言重写成当前实现的镜像。

补充根因核验：在临时库单独检查两个生成测试，机器合格20题但未人工确认时Human Gate为pending；补题测试的失败原文为`Object of type MagicMock is not JSON serializable`，不是正式库题目生成失败。新版传输/复核专项与本次23项相关专项通过，不能将历史大批断言失败直接等同当前正式Baseline失效。

**全量中保留的真问题**：`test_page_performance.PagePerformanceTests.test_light_planning_reuses_case_diagnosis_and_preserves_full_audit`。`coverage_inputs`已经计算每题诊断，`case_list_row`又按冻结题重算，旧缓存复用失效。影响是规划页面增加计算/读取，不证明评分错误。最小建议是先让规划诊断和列表诊断使用相同冻结题来源，再安全复用；不能只无条件复用一个可能缺冻结证据的旧view。两处的冻结来源目前不完全相同，不能认定无条件复用是一行且无行为影响的小修；本单保留问题，建议与规划器使用的冻结诊断一起修。

**环境原因**：21条历史夹具/manifest缺失错误，2条tokenizer缺失错误；38个方法跳过中24个依赖正式库复制、其余14个依赖私有历史材料（包括类级跳过覆盖的2个方法）。本地已安装`tokenizers 0.23.2`，缺的是`backend/config/deepseek_v4_tokenizer.zip`，不是库没有安装。代码要求SHA256 `e7310d1dafe0a86d8a5629fe78a7c763760f651db9b8682718a1781dcd6fe495`；任务003总备份中央目录中未找到该文件，本单没有从正式库或私有响应伪造测试夹具。

开启`retrieval_max_tokens=8192/16384/32768/65536`会因该缺失明确报错；当前冻结值false不加载tokenizer，所以现有Baseline和demo仍能运行。下一阶段若允许Agent选该参数，需要先补齐与上述摘要一致的本地官方归档；压缩包按`.gitignore`不进入公开仓库。本单未下载/替换模型资源。


执行方式：系统Python 3.14自带unittest发现`backend/tests`全部测试（环境没有pytest，因此使用仓库原有unittest入口习惯，不为此安装依赖）。`RAG_FORCE_MOCK=1`、临时`RAG_DEMO_DB_PATH`、空环境配置与空Provider密钥、临时诊断目录；阻断TCP连接。复用`scripts/test_v14_offline.py::isolated_corpus(legacy_fixture=True)`，只在临时目录放历史检索语料fixture，不能当正式Provider验收；未复制正式数据库。另在测试进程中禁止sqlite打开`backend/data`下数据库。

`test_golden_closeout.CloseoutTests`原本会从正式库复制题目/生成记录/审批数据；本次全量收集该组全部用例，但显式按“环境原因”跳过，以遵守本单“临时库和模拟数据、不要复制正式库”要求。未把这组跳过计为通过，也没有修改其生产或测试源码。跳过列表将在明细表逐项列出。

## 4. Agent下一轮起点（只读核对）

- 实际GET `/api/overview`、`/api/optimization?light=true&planning=true`、`/api/pipeline`均指向Baseline `EVAL-20261101155246923769`、题卷`GD-20261101151940`，没有指向旧轮。`current_experiment_id=null`、`status=not_run`、`requires_policy_upgrade=false`、`draft_stale=false`。
- 正式库该轮`completed`、50/50、45对5错，`evaluation_complete=true`，技术失败0，11项门槛通过；`result.baseline_review.complete=true`，5题各有两次完整复核。核对来源是当前接口及SQLite `mode=ro` / `PRAGMA query_only=ON`查询，不是旧报告推断。
- GET `/api/bad-cases?light=true`和Agent工作台规划接口均返回且仅返回5题。五题的`target_eligible=true`，没有“记录缺失”的阻断。

| 题号 | Agent实际读到的归因 | 可作为目标 | baseline_review保存的建议（未传给Agent） |
| --- | --- | --- | --- |
| Q04 | 检索噪声 | 是 | top_k：4→6；该证据在原轮重排第5位，增加最终条数最直接。 |
| Q06 | 检索噪声 | 是 | top_k：4→6；该证据在原轮重排第6位，增加最终条数最直接。 |
| Q24 | 检索失败 | 是 | candidate_k：12→24；query_rewrite：False→True，将口语问题补为“使用清洁剂运行的一般安全提示”。 |
| Q27 | 检索噪声 | 是 | rerank：True→query_only；对原轮已保存候选做纯本地重排，标准证据从原重排第12位排到第1位。仅为建议与候选池回放，未验证新回答/门槛。 |
| Q29 | 检索失败 | 是 | candidate_k：12→24；query_rewrite：False→True，将“重新使用、不带电检查”关联到手册“不带电检查”清单。 |

### 15个参数

逐项比对正式`config_json`、接口`baseline_config`与`OptimizationAgent.generate`构造的`base_config`，15项全部一致。Agent基于Baseline冻结配置合并默认值，再去掉`run_target`和`knowledge_identity`，不是拿生产版本或草稿当优化起点。

| 参数 | Baseline冻结值 | 接口与Agent起点 |
| --- | --- | --- |
| `candidate_k` | `12` | 一致 |
| `top_k` | `4` | 一致 |
| `min_score` | `0` | 一致 |
| `hybrid_search` | `true` | 一致 |
| `hybrid_alpha` | `0.5` | 一致 |
| `rerank` | `true` | 一致 |
| `query_rewrite` | `false` | 一致 |
| `multi_query` | `false` | 一致 |
| `hyde` | `false` | 一致 |
| `metadata_filter` | `"OFF"` | 一致 |
| `alias_mapping` | `false` | 一致 |
| `prompt_strategy` | `"Grounded"` | 一致 |
| `generation_thinking` | `"max"` | 一致 |
| `query_decompose` | `false` | 一致 |
| `retrieval_max_tokens` | `false` | 一致 |

来源：`backend/app/optimization.py::OptimizationAgent.generate`、`backend/app/main.py::pipeline`、正式Run冻结配置；只在内存重建`build_agent_prompt`，没有调用`generate`或claim、没有新建实验。

### 发现的缺口：复核建议没有接入Agent提示词

**5题和基础归因可读，`baseline_review.analysis`及其中具体参数建议不可读。** GET原Run能读到5份完整复核结论及建议；但`OptimizationAgent.generate`只从`bad_case_rows`取原错题、重新构造`diagnostic_view`；`build_agent_prompt`每题只放ID、题号、问题、归因类别、理由，没有合并`result.baseline_review.cases[question_id].analysis`。内存复建实际提示词也没有`baseline_review`或`suggested_parameters`字段。

影响：Agent能知道Q27是筛选漏证据，却看不到007b“改为query_only、保存候选回放从第12到第1”的具体依据；Q04/Q06也看不到明确的4→6建议。通用“类别→优先参数”表仍在，不能据此说007b的逐题建议已经接通。

建议后续最小改法：仅按相同Baseline与question_id读取已保存review的分类、依据和`suggested_parameters`，并入Agent输入；不能为此重跑复核或改写原判分。**这涉及Agent方案输入逻辑，本单只报告，不修改。** 起点ID没有错，不需要改数据库里的Baseline/题卷。

### 发现的缺口：旧补齐规划器不接收新版ready状态

另用当前5道真实错题和冻结15参数做纯内存`plan_coverage(rows, base_config, [])`回放，5题均`target_eligible=true`、`experiment_plan.status=ready`，返回`total=5 / covered_count=0 / planned_count=0 / status=complete_with_gaps / provider_calls=0`。

根因：`backend/app/agent_coverage.py::plan_coverage`仍仅对`experiment_plan.status=exploratory`构造补齐提案；004后`diagnostics.experiment_plan`对可执行题返回ready。影响是新状态的题没有被确定性补齐规划器接住；不代表主模型Agent必定生成0个A/B/C，它有独立的生成路径。建议后续统一ready/旧exploratory的规划资格，并保留缺记录阻断和真实已覆盖计数。属于Agent方案规划逻辑，本单只报告，不修改、不创建实验。

### 合格规则核对

代码与任务004 D一致：`policy.qualify_candidate`要求11门槛全过、错题总数至少少1、目标错题至少修好1、关键回退检查通过；`evaluate_regression`对普通新错不设上限，对安全关键/提示注入新错要求0。`evaluation.protected_question`按冻结题的安全类型/关键级别判定，避免用候选回答动态问题级别改变安全身份。

`_execute_baseline`候选执行分支对Baseline对而候选错的题调用`review_regression`，重新回答+判分两次，原轮加两遍复核三次多数判错才算真的新增错，成功的已存阶段不重跑。任务004模拟集成测试实际确认新错回答执行3次、保存原次FAIL、波动不计新增；本次相关23项测试已通过。

D或最终发布更严格：`policy.qualify_release`要求11门槛全过、相对Baseline零新增错、至少修好1题；失败回退到已合格A/B/C错题最少者，全部不合格保持Baseline。D只在有实测互补来源等前提下生成，本单估算按用户要求“D也完整跑50题”的情形计算，不表示已经满足生成D的条件。

来源：`backend/app/policy.py::{evaluate_regression,qualify_candidate,qualify_release,select_final_candidate}`，`backend/app/evaluation.py::{candidate_comparison,review_regression,_execute_baseline}`；`backend/tests/test_task004_policy.py`。没有改判分、门槛或发布逻辑。

## 5. 下一阶段耗时与DeepSeek费用（只算，不跑）

### 实测底数

| 历史范围 | 回答调用 | 判分调用 | 输入token（回答/判分） | 输出token（回答/判分） | 回答/判分阶段耗时 | DeepSeek估算美元 |
| --- | ---: | ---: | --- | --- | --- | ---: |
| 正式Baseline50题，回答max | 50 | 51 | 50,332 / 618,917 | 130,255 / 739,364 | 924.956秒 / 3942.834秒 | 0.59555293 |
| 5道错题各复核两次，共10遍 | 10 | 10 | 9,250 / 127,932 | 31,058 / 203,546 | 209.280秒 / 1093.720秒 | 0.15558200 |

Baseline墙钟为15:52:46.951358→17:14:07.910973 UTC，约81分21秒；阶段合计81.13分钟。复核墙钟约21分44秒，阶段合计21.72分钟。Baseline多1次Judge Usage沿用007b按请求标识去重后的真实记录，没有删掉这笔开销。

来源：正式Run的`result.checkpoints`、`baseline_review.cases[].regression_review.runs`，`evaluation_stage.checkpoint_usage`逐请求去重，`telemetry.cost_report`；与007b的101/20次和费用完全对齐。缓存命中输入分别为Baseline回答16,512、判分164,480，复核回答7,168、判分32,000。判分费用占Baseline约86%，耗时约81%，所以降回答档位不会把整轮变成几分钟。

### 估算口径

1. A、B、C、D每个完整50题，按现有单题顺序执行，四份相加；Judge始终max，不随回答档位降档。每50题沿用Baseline实测判分开销，包含历史出现的额外Judge请求。
2. high/off没有50题实测。仅使用007a相同5题Q13/Q17/Q25/Q35/Q36的已保存真实样本推算回答段：high/max的模型响应时间比例0.2361、输出token比例0.2141；off/max分别0.05578、0.04121。检索与本地阶段耗时保持原Baseline；输入token和缓存命中保持Baseline实测值，Judge耗时/token保持max原值。五题样本很小，且max样本明显比全卷偏慢，推算不是承诺，也不证明high/off会过质量门槛。
3. N表示“某题在某方案里首次新错”的组合数，同题在两方案新错计2。每个组合多做2遍完整回答+判分。N=0不复核，N=4等于每方案平均新错1道，N=12等于每方案平均新错3道；不是假定所有错题都复核。
4. 价格只按仓库当前配置`deepseek-flash-2026-09-30`估算，不声称是未来实际账单：低谷未缓存输入$0.15/百万、缓存$0.003/百万、输出$0.60/百万；高峰三项都是2倍。调用发生在哪个计费时段、实际扣款、向量/重排费用未知。没有修改价格配置或用未知费用填0。

| 回答档位 | A/B/C/D各50题（每个同样估计） | 四方案，N=0 | 四方案+复核，N=4 | 四方案+复核，N=12 |
| --- | --- | --- | --- | --- |
| max | 81.1分钟 / $0.596 | 5.41小时 / $2.382 | 5.70小时 / $2.507 | 6.28小时 / $2.756 |
| high | 70.1分钟 / $0.534 | 4.67小时 / $2.137 | 4.93小时 / $2.249 | 5.44小时 / $2.475 |
| off | 67.5分钟 / $0.521 | 4.50小时 / $2.082 | 4.75小时 / $2.193 | 5.24小时 / $2.413 |

上表美元是低谷配置价，高峰约乘2。例如N=4时，max约5.70小时/$2.507（高峰$5.013），high约4.93小时/$2.249（高峰$4.499），off约4.75小时/$2.193（高峰$4.385）。完整9行计算表：`指挥/报告/008a-耗时费用估算.csv`。

公式：每50题时间=原回答非模型耗时+原回答模型耗时×档位样本比例+原Judge阶段耗时；回答费用=(未缓存输入×0.15+缓存输入×0.003+原输出×档位输出比例×0.60)/百万；Judge费用不变。总量=4×每50题+2N×复核每遍均值。

额外开销：生成A/B/C通常1次Agent，D合并最多再1次，未来实际token和耗时未知。表内未冒充已实测；如需排值班窗口，可**另作工程预留**合计10分钟、低谷$0.05（高峰$0.10），这是预留假设，不是用量统计或上限。N=4加这份预留后约：max5.87小时/$2.56、high5.10小时/$2.30、off4.92小时/$2.24；还应给网络、检索参数增开query_rewrite/multi_query/HyDE等带来的额外调用留余地，这些方案尚未生成，确切增量未知。Gate2/发布的人等多久也未知，未算成模型执行时间。

## 6. 改了哪些文件

- `backend/tests/test_round0_thinking.py`：更新两项过时断言，保留真实目标和非法参数的阻断检查。
- `backend/tests/test_task004_policy.py`：更新unknown错误文本与重新进入的失败历史检查。
- 本报告、`008a-耗时费用估算.csv`与`008a-失败与跳过逐项分类.csv`。
- 任务单完成后从队列用普通mv移到`指挥/历史任务/008a-Agent优化前体检.md`。

没有改前端、Agent方案逻辑、题目、判分、门槛、SPEC、当前任务单、正式数据库或价格配置。No SPEC Change。

## 7. demo与收尾验证

已使用`webapp-testing`做只读实际浏览器检查，8页分别为overview/knowledge/settings/governance/evaluation/evolution/versions/verification，各页主内容加载成功、标题正确、pageerror=0。浏览器只允许本机GET接口，没有触发写请求；finally已关闭测试浏览器。现有8010后端、5174前端保持运行，没有为测试重新启动demo。

正式库29张表的前后行数及全部行内容SHA256摘要逐表一致，包含Baseline、逐题结果、review、题卷、配置与实验表；本单DeepSeek实际调用0次，向量/重排等其他付费调用0次。测试网络被阻断，正式接口只GET，没有调用Agent生成、优化、复核、探针或发布接口。

## 8. 需要总指挥决定的事 / 待回答问题

1. 是否在下一单把007b逐题复核结论、参数建议接进Agent输入；当前只接通原错题和基础归因。按任务单禁止改Agent逻辑，本单不代做。
2. Agent补齐规划器仍只收旧exploratory状态，当前5题ready规划0条；诊断投影重复计算也需在统一冻结来源后处理。规划资格按禁止改Agent方案逻辑的约束只报告；诊断复用需要先统一冻结来源，影响未足够明确，暂不直接改。
3. 是否在下一阶段开始前补齐本地官方tokenizer归档；当前预算关闭正常，开启时会明确失败。历史私有Judge/QC夹具缺失也仍需本地材料才能验证，不将其下载或发布为正式成绩。
4. 演示选max/high/off、是否全串行执行、实际各方案新错数量，以及生成D的实测互补条件尚未确定；本单只提供条件估算，没有启动优化。
5. 实际账单、向量/重排计费、未来Agent及新检索环节token未知。

## 9. 我是这样理解的

- 以本次明确指定的队列任务为准；不执行指挥README中手动模式的pull/commit/push，不运行任何修改仓库状态的git命令，保存推送由值班脚本负责。
- 本单明确“demo保持运行”优先于一般结束关服务；只关自己启动的测试进程和浏览器。
- “清理3项失败”不等于降低有效校验：改旧规则断言，同时保留保存目标/非法参数/失败历史这些当前规则检查。Agent方案代码有缺口只报告。
- 严守禁止复制正式库，依赖正式库内容的旧Closeout测试按环境跳过；其他用例仍全部收集执行，逐项列出失败、错误和跳过，不把环境失败说成产品失败。

## 10. 有没有没做完的

本单要求已完成：3项指定旧失败已处理、全量测试完成并逐项分类、起点只读核对完成、3档耗时费用估算完成、demo主链路可读。117个方法仍未通过、38个方法跳过，原因与处置均已记录；Agent建议接入/旧状态规划/诊断复用及tokenizer环境缺口尚未修复，按任务单作为待决定事项交接，不表示下一轮优化已完成。

任务单归档到`指挥/历史任务/008a-Agent优化前体检.md`。本单没有运行任何修改仓库状态的git命令，提交推送交自动值班脚本；没有改`指挥/当前任务.md`。常驻demo保留，本次测试进程和浏览器均已结束，临时数据库/目录随测试退出清理。


## 附：全量运行方法

以下命令在仓库根目录运行，环境和本次全量相同；没有pytest依赖。原始日志没有放入公开报告，统计和每项原因已在正文/CSV中保存。

```python
import importlib.util, os, socket, sqlite3, sys, tempfile, unittest
from pathlib import Path
from urllib.parse import unquote
from unittest.mock import patch
root = Path.cwd()
sys.path[:0] = [str(root / 'backend'), str(root / 'backend/tests')]
spec = importlib.util.spec_from_file_location('offline', root / 'scripts/test_v14_offline.py')
offline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(offline)
connect = sqlite3.connect

def disposable_connect(database, *args, **kwargs):
    if str((root / 'backend/data').resolve()) in unquote(str(database)):
        raise AssertionError('禁止测试打开正式数据库')
    return connect(database, *args, **kwargs)

with tempfile.TemporaryDirectory(prefix='task008a-tests-') as temporary:
    path = Path(temporary)
    env = {'RAG_DEMO_DB_PATH': str(path / 'test.db'),
           'RAG_DEMO_ENV_PATH': str(path / 'empty.env'),
           'RAG_DIAGNOSTIC_DIR': str(path / 'diagnostics'),
           'RAG_FORCE_MOCK': '1', 'RAG_SAFE_START': '0',
           'DEEPSEEK_API_KEY': '', 'DASHSCOPE_API_KEY': '', 'MINERU_API_KEY': '',
           'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
    with patch.dict(os.environ, env), \
         patch.object(socket.socket, 'connect', offline.offline_connect), \
         patch.object(socket.socket, 'connect_ex', offline.offline_connect_ex), \
         patch.object(sqlite3, 'connect', disposable_connect), \
         offline.isolated_corpus(temporary, legacy_fixture=True):
        suite = unittest.defaultTestLoader.discover(str(root / 'backend/tests'))
        import test_golden_closeout
        test_golden_closeout.CloseoutTests.__unittest_skip__ = True
        test_golden_closeout.CloseoutTests.__unittest_skip_why__ = '禁止复制正式库'
        print('收集方法数：', suite.countTestCases())
        unittest.TextTestRunner(verbosity=2).run(suite)
```
