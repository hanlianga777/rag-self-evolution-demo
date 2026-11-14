# 031d：新 Baseline 已启动，后台串联已登记

新 Baseline：**EVAL-20261114165832146406**。本单只负责启动与前 2–3 题核验，整卷和 Agent 的最终成绩、最终推荐及最终实际扣款均还未知；不会等长任务跑完，也没有执行 Gate 3 发布。

## 我是这样理解的

- 031c 原报告的 Q10 停点已被 031c3 明确处置：新题卷 `GD-20261114160635` 已冻结，新 Corpus 为 `CORPUS-bf24725c92cb4e191879`。因此接续这份题卷，不重建、不重锚、不重跑旧探针，也不重复已完成的付费题。来源：031c3 报告、正式库 `dataset_versions`、`/api/workspace`。
- 本单开始时没有本单半成品或当前活动的 Baseline、Agent、Sandbox。旧正式 Baseline 指定记录仍绑定旧题卷，不能把旧实验拿来续跑。来源：开工 Git 日志、本机 `output/task031d/before.json`、`loaded-preflight.json`。
- “每轮参数互不相同”沿用原来的同轮修改参数互斥校验；去掉预设方向及固定一套效率方案。四段格式和 D 的两种生成方式用 `agent-strategy-3` 绑定这次新实验，不改写旧实验的保存结果。
- 原后台监控负责恢复和调度，本单只加一个持久化串联记录，不另起 Codex 值守进程。任务要求后台继续运行，所以保留原 supervisor 管理的后端；自己启动的测试程序和浏览器均已结束。

## 启动配置与运行设置

- 使用 `DEFAULT_PIPELINE_CONFIG`：Thinking **Max**、Candidate K **12**、Top-K **4**、Hybrid **0.5**、Rerank 开启、Grounded，其他增强关闭。回答 Prompt 为 **generation-vnext-3**；评分合同与 Hard Gate 未改。
- 线上旧 Candidate D 配置（High / K24 / Top-K6）已归档，新增初始配置记录作为新版本起点；旧发布记录、配置、快照及索引保留。旧版本跨 Corpus 的回滚仍受原兼容检查约束，需要配套恢复旧知识资产，本单没有实际回滚旧知识库。
- 已通过 `POST /api/runtime-settings` 关闭“只在平价时段运行”，`off_peak_only=false`，后台备注 **用户 2026-11-14 确认关闭平价限制**。本单结束后保持关闭。
- 已通过 `POST /api/runtime-settings/unattended` 打开授权，确认人 `用户`，审计备注 **用户 2026-11-14 授权**。预算 **12** 次，沿用 A/B/C 预留 1 次给 D 的现有规则；不增加金额上限。
- 付费启动前重载后端一次：PID **66316 → 70446**；真实启动后不再改应用代码、不重启。来源：`restart.json`、`started.json`、启动前后代码 SHA-256、正式库 `production_versions` / `paid_schedule_settings`。

## 串联方式及 Agent 规则

`POST /api/evaluations/run` 使用 `fresh=true, unattended_chain=true`。串联记录保存在正式库 `paid_schedule_settings.baseline_agent_chain`，绑定本次 Baseline 和新题卷。

后台每 5 秒的原恢复监控检查该记录；Baseline 完整结束且技术失败为 0 后，将其指定为当前正式 Baseline，原子地建立一个新实验，再复用原优化循环。新实验只关联新 Baseline；首轮没有旧 Candidate、旧实验结果。重复请求会拒绝，进程重启后沿用该记录及原评测/循环断点。串联当前为 `waiting_baseline`，新实验编号将在 Baseline 完成后产生，现阶段未知。

- 每轮保存前几轮总结、Bad Case 按层/细分类型统计、三套参数方案及预计修好题号；缺字段、错题统计不符、修好/弄坏题号不符或引用无效会带原因拒绝重出。多参数复盘须给最可能参数与理由，保留无法单独归因的要求。
- 本轮评测结束后另请 Agent 写结论，核对实际修好/弄坏题号、预测吻合题号及数量、原因、参数判断和下一轮经验；原始响应与请求断点保存，已完成的结论重启后直接复用。下一轮和 D 都收到本实验已保存的结论。前端 Candidate 对比按“Agent 策略 → 三个 Candidate → 本轮结论”展示保存内容。
- 未触发时不强制效率方向；已用 6 次且没有合格方案时，下一轮 Agent 输入及校验要求一个 **Max → High + 检索补偿**方案，前端显示 **Agent 策略 · 效率优化**。保存的耗时占比和参数耗时观测仍提供给 Agent，不伪造思考过程。
- 出现合格方案后沿用跳过未运行方案的规则，完成本轮结论；Gate 2 确认人记为 **用户**，审计备注 **用户 2026-11-14 预先授权**，页面只展示“已确认”和确认人。
- D 须选择“部分融合”或“Winner 加有效参数”，说明依据、预计修好题号和风险；本次不能新增未验证的参数取值。沿用 `select_final_candidate`：D 必须优于 Winner 才推荐 D，否则保留 Winner。流程停在发布前。

来源：`backend/app/baseline_chain.py`、`agent_strategy.py`、`optimization.py`、`optimization_cycle.py`、`governance.py`、`main.py`，`frontend/src/components/RoundStrategy.tsx` 和 `pages/EvolutionPage.tsx`。

## 离线验证与主链路验收

- 相关后端套件 **77/77 通过**；新增 API、预算末轮复盘等边界后定向复验 **23/23 通过**，两组有重叠，不能相加。只用临时数据库，禁止外网，没有复制正式库用于测试。
- 包含真实保存逻辑的 50 题 Mock 串联演练：Baseline → 新实验 → 首轮失败 → 下一轮 → 合格 Winner → Gate 2 → D → 推荐；确认无 Gate 3 审批、无新 Candidate 发布。D 优于/不优于 Winner 的两条推荐分支均有测试。Mock 仅证明流程，不代表真实模型成绩。
- 另验证：6 次后效率规则进入 Agent 输入、有 Winner 时不触发；方向不再预设但参数互斥保留；结论拒绝重出与重启复用；重复启动被拒绝；原断点恢复与 Provider 余额错误停止规则。
- 前端定向测试 **17/17 通过**，生产构建通过。临时库 demo 启动及 7 个入口通过；真实浏览器打开知识库、Pipeline、Golden、Baseline、Agent、发布共 6 页，无 alert，Golden 实际读到新冻结 50 题。浏览器只允许本机 GET/HEAD，已关闭。
- `git diff --check` 通过。未运行修改仓库的 Git 命令；没有提交数据库、密钥、日志、截图或运行数据；提交和推送交给值班脚本。No SPEC Change。
- 首次套件曾因测试列表误写不存在的模块名而报 1 个导入错误，已纠正后得到 77/77；新增 API 测试的线程替身曾影响测试客户端，修正测试隔离后 23/23。这些均在付费启动前处理。

来源：本机 `output/task031d/targeted-final.txt`、`edge-final.txt`、`frontend-final.txt`、`frontend-build-final.txt`、`startup-smoke.json`、`browser-smoke.json`，及相关测试文件。

## 前 2–3 题检查与费用

核验收据时间：**2026-11-14 12:00:01 EST（17:00:01 UTC）**。此时 Baseline 为 **running，3/50 完成，技术失败 0**，第 4 题处于原后台流程中。只读取这份收据，不继续循环盯进度。

| 题号 | 正式题目 ID | 有回答 | 有判分 | 业务结果 |
| --- | --- | --- | --- | --- |
| Q01 | CSV-20261101100758945425-01 | 是 | 是 | PASS |
| Q02 | CSV-20261101100758945425-02 | 是 | 是 | PASS |
| Q03 | CSV-20261101100758945425-03 | 是 | 是 | PASS |

- 前 3 题保存的请求断点确认：DeepSeek **6 次已完成**（3 次回答、3 次判分）；Embedding **3 次**、Rerank **3 次**。这些是本次抽查样本的已完成调用，不是后台整个任务的最终调用总数。离线演练的真实 Provider 调用为 0；没有重新生成旧题或复跑旧付费评测。
- 前 3 题的 DeepSeek 回答加判分费用估算合计 **USD 0.01659015**，使用系统保存的 `deepseek-flash-2026-09-30` 价格快照；这不是实际扣款凭证。Embedding、Rerank 实际费用未知。
- 整个运行的 `request_accounting.call_events=14`、`unknown_usage_events=0`，但多模型合并费用返回 `model_mismatch`，估算金额为空，不能记成 0；后续运行仍继续花费。因此**最终实际扣款、最终总调用数、整卷成绩、Agent 结果均未知**，本单没有账单查询凭证。
- 10 类受保护历史表的原记录哈希全部一致；仅将旧活动生产版本改为归档状态，该行的配置、快照和其他字段未改。新初始线上版本为 **initial-20261114165831904047**。正式题卷及原有评测、逐题结果、实验、Candidate、QC、Probe、题目、Agent Trace 均未改写或删除。
- 后端仍为 PID **70446**；应用代码与付费启动前 SHA-256 一致。没有启动后重启或修改应用代码。

来源：正式库 `evaluation_case_results`、`evaluation_checkpoints`，本机 `output/task031d/final-verification.json`、`started.json`、`before.json`，以及上述只读 API 收据。

## 只读进度接口

- `GET /api/evaluations/EVAL-20261114165832146406?light=true`：本次 Baseline 状态、完成数、技术失败和费用估算。
- `GET /api/evaluations/EVAL-20261114165832146406/comparison-cases`：保存的题目列表与逐题通过状态。
- `GET /api/evaluations/EVAL-20261114165832146406/cases/{question_id}`：单题保存的回答与判分详情。
- `GET /api/runtime-settings`：`off_peak_only`、授权及 `baseline_agent_chain`，其中将保存新实验编号。
- `GET /api/experiments/{experiment_id}?light=true`：新实验预算、各轮 Candidate、循环状态与最终推荐。
- `GET /api/optimization?light=true&planning=true`：当前正式 Baseline 对应的 Agent 工作台数据。

## 待回答问题

实际账单扣款金额未知，运行期间费用仍会增长；最终结果由原 031a 状态播报和总指挥跟进。本单不等待最终成绩，不请求无人值守期间的人工答复。

## 任务归档

本单要求的启动、串联代码、离线演练、前 3 题核验和设置确认均已完成；任务单用普通 `mv` 移到 `指挥/历史任务/031d-新版本Baseline与Agent无人值守启动.md`。后台长任务继续运行，Gate 3 本单未执行。保存和推送由值班脚本负责。
