# 014b：启动第二轮 Agent

## 当前状态

**本单已完成启动与交接。** 新 max Baseline 已正式指定；A/B/C 已生成并通过规则校验；完整优化循环正在运行。观察截止 **2026-11-03 22:58:42.368485 UTC（多伦多 17:58:42）**，A 的 Q01、Q02 均有非空回答、有 Judge 判分，均 PASS，技术失败 **0**。达到前 2–3 题正常的要求后停止观察，不等全轮跑完。没有执行 Gate 2 人工确认、真实 D 或发布。

## Baseline

正式 Baseline：`EVAL-20261103151339324195`，题卷 `GD-20261101151940`。50/50 完整完成，答对 **42/50**，错 **8**，技术失败 **0**。回答 max、判分 low、上下文不限、有据生成。门槛 **9/11**；安全拒答率 **85% < 95%**、安全关键准确率 **75% < 95%**，其余 9 项通过。回答延迟 **P50 16.676 秒 / P99 42.240 秒**，两项均过线。

四类分布：检索层问题 **5**（Q04、Q06、Q24、Q27、Q29）；生成层问题 **2**（Q37、Q46）；安全边界问题 **1**（Q35）；性能问题 **0**。Baseline 和 Agent 的 API 逐题 ID/分类一致；真实页面均显示 8 题与上述四类数量，两页检查无 pageerror、无横向溢出。

来源：正式库 `evaluation_runs` / `evaluation_case_results`，`GET /api/evaluation`、`GET /api/bad-cases`、`GET /api/optimization?light=true&planning=true`；本机 `backend/data/task014b/baseline-designated.json`、`pages.json` 与页面截图。

正式指定记录：`baseline_designations.id=4`，2026-11-03 22:54:12 UTC。对照运行沿用此前正式 high 回答 / low 判分的 `EVAL-20261102140722852830`。没有复核或重跑这 50 道 Baseline 题，没有修改历史结果。

## D 组合准备与离线验证

检查发现 014a 已实现效率来源例外：同身份、evaluated、Regression 通过且门槛全过的效率方案，即使 all_fixed_question_ids 为空，也能进入 D 来源。`policy.evaluate_regression` 本来就只阻断新增安全关键/提示注入错题，允许新增普通错题，不需要再放宽。

本单补齐 D 输入：`optimization.py:strategy_candidate` 改成仅传当前组合需要的字段，移除历史波动、未完成复核和旧复核说明；`governance.py:create_composite` 的错题归因改用四大类，提示词明确单遍结果和零修复效率来源规则。历史数据库记录保持原样，D 的资格与发布条件不变。

扩展 `backend/tests/test_task014_optimization.py` 的真实存储 + Stub 测试：质量 Winner 保留 top_k=6，另一个门槛全过、无新增关键错、没有修好题的效率来源提供 off + HyDE，实际生成 D，断言来源与配置均保留，并断言旧字段没有传给模型、归因用四大类。测试先复现旧字段泄漏失败，修改后通过。相关 **24 项测试通过**，覆盖 014 核心/归因/ABC拒绝重出/效率组合、已有 D 组合与确认、完整循环返回分析及 D 预留；全为临时库和 Stub，付费调用 0。完整命令和输出留在 `backend/data/task014b/related-tests.log`。首次命令误写一个模块名导致 ImportError，改为真实模块名后上述 24 项通过，不算业务失败，不声称全仓测试通过。

## A/B/C 方案

实验：`EXP-20261103225621615671`。使用 `POST /api/experiments/run` 只请求一次，Agent 一次返回三套，`validation_stage=completed`、拒绝方案 0、试跑预算使用 0。保存后再用 validate_round_contract 校验：三种方向、恰一效率方案、质量方案不降档、参数互斥均通过；未触发重出。

|方案|方向 / 动作|修改参数（相对新 Baseline）|目标题|
|---|---|---|---|
|A|回答策略 / 启用分级回答与安全追问|prompt_strategy：Grounded → Tiered|Q35, Q46, Q37|
|B|检索召回增强 / 扩大候选并引入多路查询|candidate_k：12 → 24；multi_query：False → 4|Q29, Q24|
|C|效率（降档 + 检索补偿） / 降思考档并用TopK与关键词重排补偿|generation_thinking：max → high；rerank：True → query_only；top_k：4 → 6|Q27, Q06, Q04|

来源：正式库 `experiments` / `candidate_configs`；本机 `agent-generated.json` 保存方案、理由、预期与风险。Agent 方案是待验证假设，不代表已修好题。

## 优化循环与交接

2026-11-03 22:57:15 UTC 通过 `POST /api/experiments/EXP-20261103225621615671/run-cycle` 启动，没有附加 current_round_only，响应明确 false。预算 12，其中 1 次留给 D；无合格方案时按既有完整循环进入下一轮，直到合格或 ABC 预算耗尽。Gate 2 确认、D 真实生成/评测和发布留给总指挥，本单没有执行。

交接快照：

|方案|候选编号|Sandbox 运行编号|截止状态|
|---|---|---|---|
|A|`EXP-20261103225621615671-R1-A`|`EVAL-20261103225716098518`|running，2/50 已完成；Q01、Q02 PASS，技术失败0；Q03处于判分阶段|
|B|`EXP-20261103225621615671-R1-B`|尚未生成|generated，等待循环顺序启动|
|C|`EXP-20261103225621615671-R1-C`|尚未生成|generated，等待循环顺序启动|

来源：正式 `experiments` / `candidate_configs` / `evaluation_runs` / `evaluation_case_results` 的同一只读事务快照，保存于本机 `backend/data/task014b/startup-observation.json`。循环状态为 running / sandbox，owner_pid=69176、current_round_only=false。A 已占用 1 次 Sandbox；循环内部 used=0 是启动 A 前的状态快照，不能当作实际预算尚未使用。实际已用以实验接口 evaluation_budget.used 为准。

只读查进度（无需发任何 POST）：

- `GET http://127.0.0.1:8010/api/experiments/EXP-20261103225621615671?light=true`：完整循环状态、实际已用预算、A/B/C 状态；B/C 启动后从各自 `result.evaluation_run_id` 取新运行编号。
- `GET http://127.0.0.1:8010/api/evaluations/EVAL-20261103225716098518?light=true`：A 的完成数量、技术失败、恢复状态、调用账目。
- `GET http://127.0.0.1:8010/api/evaluations/EVAL-20261103225716098518`：A 已保存的完整逐题回答、判分与证据，响应较大。
- `GET http://127.0.0.1:8010/api/optimization?light=true`：当前正式 Baseline 对应的实验。
- `GET http://127.0.0.1:8010/api/evaluation`：正式 Baseline；不要把它当作当前 A 的试跑进度。

所有 API、页面、测试检查完成后，仅保留原有前端和既有监督程序托管的正式后端。本单独立 Playwright 浏览器均已 finally 关闭。正式 9 张保护表的原有行逐行哈希均保持一致；题目150、题卷7、线上版本1、审批224未变，仅追加授权的新 designation、实验、候选和试跑结果。来源 `protected-before.json` / `protected-after.json`。

## 费用

下表截止到上述 **22:58:42 UTC** 观察点；后台随后还会继续产生调用。费用使用保存的 `deepseek-flash-2026-09-30` 价格快照与真实 usage 离线估算，**不是实际账单**，没有为算钱发新 Provider 请求。

|范围|已保存调用|DeepSeek 已知费用估算（USD）|
|---|---|---:|
|新 Baseline 完整50题（014a已执行，本单没有重跑）|200：DeepSeek100（回答50、Judge50），Alibaba100|0.36072371|
|本单 Agent 生成第一轮ABC|DeepSeek1；无格式重出|0.00354360|
|本单 A 启动到交接观察点|11：DeepSeek5（回答3、Judge2），Alibaba6|0.00824929|
|**本单新增的已保存调用合计**|**12：DeepSeek6、Alibaba6**|**0.01179289**|

Baseline 的混合 Provider 总额字段因 model_mismatch 为不可用；表中 Baseline 和 A 的 DeepSeek 金额是从 `evaluation_checkpoints` 用 `checkpoint_usage` 提取保存事件，仅筛 DeepSeek 后按项目 `telemetry.cost_report` 计算的分项估算，没有把 Alibaba 当成免费。Agent 金额直接取实验保存的 cost_estimation。Alibaba 费用**未知**；Q03 判分对应的完整 usage 当时尚未保存，后续调用和最终费用**未知**。不能把已记账次数当成包括所有在途请求的最终调用总数。离线与页面验证真实 Provider 调用 **0**。

来源：`evaluation_checkpoints`、`experiments.result_json.token_usage/cost_estimation`；本机 `startup-observation.json`，及项目 `backend/config/deepseek-prices.json` 价格快照。

## 我是这样理解的

- 自动值班只执行本单，不等待人答复，不加确认环节。Git 只读；提交、推送交给值班脚本，不改 `指挥/当前任务.md`。
- 第 1.5 条明确允许“启动循环前可重启后端一次”，与末尾“不重启后端”冲突。本单按更具体条款，在确认无活动评测或循环后，唯一一次 TERM 空闲 PID52066，由既有监督程序40379加载修改为 PID69176；22:54:12 UTC 指定 Baseline 前完成。启动 Agent 后不再重启。
- 达到 A 前 2–3 题正常即交接，正式后端和既有前端5174保留运行；关闭本单临时浏览器，不停止已授权的付费循环。
- 业务判错不等于技术失败；前几题正常也不代表方案合格或全轮通过。预算是 Sandbox 次数，不是 Provider 请求次数；格式重出若发生仍会消耗模型调用费用。

## 待回答问题

无须回答才能继续的事项。B/C 的运行编号、最终费用和整轮结论将在后续产生，本单按要求不等跑完。
