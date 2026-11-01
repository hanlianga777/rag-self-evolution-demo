# 007a 速度小测与 Baseline 启动

已完成本单：配置与原因保存已修复，20次小测全部完成，按规则选择max；正式50题Baseline已经启动，前3题都有回答和判分且均PASS，技术失败0。后台继续运行，本单不等待全卷结束。

## 已完成的修改与验证

- `backend/app/config.py`：新增后端环境配置 `BASELINE_THINKING=off|low|high|max`，缺省 max，非法值启动时拒绝。
- `backend/app/providers.py`、`ai_service.py`：Baseline 的显式回答档位可传到实际 HTTP 请求；Judge 始终 max。候选和 Agent 默认逻辑未改。
- `backend/app/evaluation.py`：启动时将后端配置写入本轮 `config.generation_thinking`、执行快照；逐题 `programmatic_metrics.generation_thinking` 保留实际档位。配置身份哈希本来就包含 generation_thinking，继续复用这条隔离规则。续跑始终使用原轮冻结配置。
- `backend/app/governance.py`：普通机器检查分支的 review-batch 确认事件保存传入 reason。未改43条旧事件。
- 新增 `backend/tests/test_task007_baseline_thinking.py`，更新一条旧 Baseline 固定 max 的测试预期。新增4项测试修改前全部失败，修改后通过；相关专项共21项通过。网络重试和 Judge 格式恢复另20项通过。测试使用临时目录、临时库与模拟HTTP，无真实Provider调用。
- 探索性联合测试36项中34通过、2失败。2项是旧 Agent validate_intervention 断言（test_agent_new_parameters_keep_evidence_and_direction_contract、test_agent_new_stage_parameters_require_measured_bottleneck）；用 `git show HEAD:backend/tests/test_round0_thinking.py` 的原测试同样复现2失败。Agent实现未修改，不扩围修复，不宣称全量绿。

来源：上述代码、unittest实际输出、HEAD原测试只读回放。

## 我是这样理解的

- 后端配置采用 `.env` 的 BASELINE_THINKING，不增加前端控件。每轮开始后冻结档位，改变环境配置不会改变已启动的轮次。
- 小测速使用 `EvaluationRunner.baseline_inputs → AiService.answer → EvaluationRunner.score_execution`，即正式检索、回答、最高档判分链路；只替换回答档位。没有创建 evaluation_runs/evaluation_case_results 记录。四档可并行，各档五题串行。
- “总耗时”是正式门槛使用的回答端到端 `latency_ms`（检索到回答结束），不含Judge；首字时间沿用Provider的 request_to_first_content；检索、回答耗时从对应stages取。CSV输入输出token和费用按该样本全部DeepSeek调用（回答、判分、格式补判、重试）合计，向量重排另列统计。费用是本地配置价估算，实际扣款未知。
- 决策14沿用现有HTTP传输重试：网络/SSL/超时/408/429/5xx最多再试2次，间隔5和15秒；Judge格式最多纠正1次；技术失败继续后续题，最后补跑1次失败项，已成功子请求复用。来源：006报告与现有providers/evaluation_stage实现。
- 用户要求本单 demo 保持运行，优先于根目录通用“用完关闭”规则。测试浏览器关闭，常驻demo保留。
- 8个页面（overview、knowledge、settings、governance、evaluation、evolution、versions、verification）均等待实际内容加载后检查，标题正确、无pageerror，临时无头Chromium已关闭。最初脚本对hash路由等待不足，以及误写pipeline/release/qa路由；已改为产品实际路由重新检查，没有改前端代码。正式启动后再次打开Baseline页面，实际显示“后台评测进行中”、4/50、Generation Max/Judge Max且pageerror=0；页面将Run ID缩略显示，最初等待完整ID文本的断言超时，按实际DOM核验后通过，浏览器均在finally关闭。页面最新4/50晚于下文费用统计截点，费用仍只按那个截点记。

## 速度小测断点

执行脚本 `backend/scripts/task007_speed.py`。本机检查点 `backend/data/task007-speed.json` 保存每题每档的请求、尝试、Usage、回答和判分。重启脚本时复用已完成结果，不重复付费。CSV：`指挥/报告/007-数据/速度小测.csv`。20组已全部完成，每组1次回答、1次最高档判分，全部答对；技术失败0、HTTP重试0、格式补判0、末尾技术补跑0。原始请求参数也逐项核对：回答用对应档位，Judge均为max。

## 速度结果与定档

单位为秒；每档各5题，表内为回答端到端耗时。

| 档位 | Q13 | Q17 | Q25 | Q35 | Q36 | P50 | 最慢一题 | 答对 | 技术失败 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| off | 5.696 | 3.527 | 3.842 | 3.550 | 3.279 | 3.550 | Q13 / 5.696 | 5/5 | 0 |
| low | 10.900 | 14.993 | 9.094 | 8.110 | 6.901 | 9.094 | Q17 / 14.993 | 5/5 | 0 |
| high | 14.986 | 12.033 | 23.110 | 8.465 | 7.449 | 12.033 | Q25 / 23.110 | 5/5 | 0 |
| max | 79.982 | 55.893 | 97.699 | 10.529 | 15.443 | 55.893 | Q25 / 97.699 | 5/5 | 0 |

max的P50为55.893秒，≤60秒，因此按任务单选择 **max**。max小样本P50超过正式25秒门槛，正式Baseline大概率过不了延迟P50这一项；5题样本不能保证50题实际分布。其他档位虽然更快且本样本都判对，也不改变指定定档规则。未改门槛或判分。

小测开始UTC：2026-11-01T15:37:52.098795+00:00；结束UTC：2026-11-01T15:51:55.680588+00:00。来源：本机task007-speed.json、速度小测CSV及现有计时字段。

## 正式 Baseline

- 启动时间UTC：2026-11-01T15:52:46.951358+00:00（请求时间 2026-11-01T15:52:46.757726+00:00）。
- 运行编号：`EVAL-20261101155246923769`；题卷：`GD-20261101151940`，冻结完整50题。
- 回答档位：max；已在本地.env显式保存BASELINE_THINKING=max；运行config.generation_thinking=max，Judge保持max。选中值与刚重启的后端有效默认值一致，无需再次重启。
- 产品默认并发：**1**，现有_execute_baseline按完整题集顺序执行。没有为正式Baseline加并行。
- 通过只读GET /api/evaluation/preflight，can_start=true，然后调用产品正常POST /api/evaluations/run（fresh:true），HTTP 201。启动前正式库没有本题卷的评测，未重复启动或恢复旧题卷。
- 首批核验完成。按任务要求在前2题有效完成时结束事件监听，再单次读取产品进度接口时第3题也已完成。没有等待全卷结束，没有循环轮询接口。

改库前用SQLite backup接口备份至 `/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/data/audit_backups/task007-baseline-20261101155245.db`。同类task007-baseline备份最多保留最近2份，仅留本机，没有为测试复制正式库。

启动前已通过 `RAG_RESTART=1 ./start_demo.command` 正常加载新代码，重启前只读确认没有活动评测或生成任务；重启后8010/5174可用。来源：启动脚本输出、正式库evaluation_runs记录及HTTP返回。


首批截点UTC：2026-11-01T15:54:58.305925+00:00。此时 `status=running`，`completed=3`、`failed=0`、`technical_failed=0`、`evaluation_complete=false`。这不是50题最终成绩。

| 题号 | 回答 | 正式判分 | 回答总耗时（秒） | 实际档位 |
| --- | --- | --- | ---: | --- |
| Q01 | 非空、已保存 | PASS | 9.913 | max |
| Q02 | 非空、已保存 | PASS | 2.668 | max |
| Q03 | 非空、已保存 | PASS | 14.289 | max |

回答原文和完整判分均可在上述进度接口的cases里查看；没有用模拟数据当正式结果。第四题已有回答并在判分中，后续结果仍由常驻worker继续产生。来源：该Run单次最终GET返回、evaluation_case_results与checkpoint Usage。

## 总指挥怎样查看进度

- 浏览器页面：http://127.0.0.1:5174/#evaluation
- 只读进度接口：http://127.0.0.1:8010/api/evaluations/EVAL-20261101155246923769
- result.completed：已经有回答和有效判分结果的题数；result.total：应跑50题。
- result.failed：有效判分中的业务错题数，不是技术失败；cases[].passed逐题显示对错。运行未完成时另有result.partial_bad_case_count。
- result.technical_failed（同technical_error_count）：当前技术失败题数；technical_errors和checkpoints保留具体原因与重试记录。
- status=queued/running表示未结束；status=completed/partial/failed表示该轮已结束。**完整有效50题**还需result.evaluation_complete=true、completed=50、technical_failed=0；不能只看status=completed，因为末尾补跑后仍有技术失败也可能结束为completed。
- result.auto_recovery.question_id、phase表示当前题和阶段；cases包含逐题model_answer、judge_result及programmatic_metrics.generation_thinking。

本单按任务要求只监听SQLite写入事件核验首批结果，不循环轮询进度接口，不等待50题结束。来源：main.py评测接口、evaluation.py::_execute_baseline和正式库。

## 调用与费用

| 范围/服务 | 已完成调用 | 估算费用 | 实际扣款 |
| --- | ---: | --- | --- |
| 速度小测 DeepSeek deepseek-flash | 40（回答20、判分20） | 0.30905940美元 | 未知 |
| 速度小测 text-embedding-v4 | 20 | 未知 | 未知 |
| 速度小测 qwen3-rerank | 20 | 未知 | 未知 |

截至UTC 2026-11-01T15:54:58.305925+00:00，正式Baseline新增 **DeepSeek成功7次（回答4、判分3）**，另有 **1次判分进行中**；向量成功4次、重排成功4次。已返回7次DeepSeek按同一配置价估算 **0.01623852美元**；进行中调用的token与费用未知。该截点无技术失败、无HTTP重试或格式补判。

本单截至该截点合计：DeepSeek成功 **47次**，另1次进行中；向量 **24次**；重排 **24次**。已返回DeepSeek费用估算合计 **0.32529792美元**。后台还在继续，之后调用不在该截点统计内；整轮最终调用数、实际扣款及全服务费用合计均未知，交由后续任务从同一Run补齐。CSV逐行估算各自保留8位小数，求和可能有末位舍入差。

小测费用按backend/config/deepseek-prices.json的deepseek-flash-2026-09-30配置和真实token Usage通过telemetry.cost_report计算，是估算，不是账单。向量/重排无足够计价资料，不能填0。来源：逐请求checkpoint_usage按request id去重。

## 待回答问题

无阻塞待回答问题。

## 有没有没做完的

本单要求均已完成。50题整轮后续完成、错题复核和最终费用账单不属于本单，尚未知；未自行等待、重跑、启动Agent或改判分。任务单归档到 `指挥/历史任务/007a-速度小测与Baseline启动.md`。常驻后端和前端继续运行，测试浏览器与临时测试进程均已退出。

No SPEC Change；本单未执行任何修改仓库状态的git命令，保存与推送交给自动值班脚本。
