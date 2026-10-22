# Agent 闭环修复验收单（2026-10-22）

代码与离线阶段已交付，真实闭环待验收。尚未达到任务书要求的“10/10可信诊断及真实完整实验验收”，不能据此结论宣称10题已修复。

正式Run仍为 `EVAL-20261021141811373593`：50题完成、40 PASS / 10 FAIL、Overall 91.5、11项Gate通过。本轮真实Provider调用0，新回答0，真实修复0题，仍有10题未经过新回答验证。正式服务未重启；页面截图来自隔离API预览，不代表正式服务已加载新代码。

已改好的部分：全部业务FAIL交给同一Agent处理；补证与方案执行资格分开。增加统一批量补证、按执行材料重新核验后复用观察、必要事实与无害补充分开保留、仅原问题的候选排序、有依据的必要联动及跨阶段D。已有合格方案不再无条件关闭后续轮次；剩余问题按同一个已验证配置计算，不把不同方案的修复相加。新Golden/新Baseline共用资料预检，原人工确认和发布保护保留。

## 当前10题分别怎样处理

下表的“补证后路径”是已实现的工具/验证链路，不是已经运行成功的候选。补证仍须核清全部失败要求和实际阶段，不能按题号直接放行。

| 题目 | 本轮核实的现状与处理 | 实际验证状态 |
|---|---|---|
| Q03 创建用户 | 当前为Ranking，旧登录补充引用仍使可恢复配置为空。统一补证须核验其是否为非必要补充；确认后允许关闭重排+Top6等恢复必要创建流程的方案，必要事实/安全/型号范围仍保护 | 待补证；未生成新答 |
| Q04 长期存放 | 当前根因未闭合。核存放与蓄电池维护的完整规范及候选/排序/Final；按核验缺失阶段提出查询、候选召回或上下文方案 | 待补证；未运行候选 |
| Q06 清洁电气安全 | 核电池隔离、湿手禁令与现有断电表述是否完整；资料未进Final时先修检索，Final足够才允许按生成问题干预 | 待补证；未运行候选 |
| Q07 滤网清洗 | 将机械步骤和维护安全前提拆开核验并共同保留；确有多段缺口时允许有证据的召回/上下文必要联动 | 待补证；未运行候选 |
| Q08 充电器保养 | 已有可核验Ranking和 `top_k=6` 路径。批量补证自动跳过，避免为统一形式重复收费 | 可提出实验；尚未真实验证新答 |
| Q17 遥控器绑定 | 核R1/R3章节来源、配对步骤及DL确认；未知现场型号不能当作已确认。按真实缺失阶段提出检索/生成方案 | 待补证；未运行候选 |
| Q24 清洁剂安全 | 核稀释、孩童隔离、急救及制造商说明等全部失败项；允许同一原check拆成原子要求，也允许绑定Golden短摘要之外的真实适用Canonical规范 | 待补证；未运行候选 |
| Q27 桌椅布局变化 | 生产路径已支持 `rerank="query_only"`。保存候选池试排中C00096排第1，选择只读原问题和候选正文；正式候选仍须补齐诊断并验证必要事实保留 | 仅排序反事实；未验证新答/全50题 |
| Q28 更换刷辊 | 核拆装与关机、供电隔离/脱离对接等前提；已答机械步骤保留，缺失前提按实际阶段处理 | 待补证；未运行候选 |
| Q29 不带电检查 | 完整表格与整机/充电器范围分别核验；完整Canonical输入及既有查询/召回/上下文工具接通，禁止只补Judge输入就宣称生产检索修复 | 待补证；未运行候选 |

已证实：隔离DB副本的Agent输入包含10/10；本轮可立即实验1题（Q08），其余9题统一待补证。没有将待补证强制标成可信根因或可执行Candidate。

## 新题、重评与保护怎样验证

- 无预置诊断的新题覆盖Retrieval/Ranking、Generation、Safety和Performance；任意题号与改写表达、等价来源、复合要求及R1/R3范围隔离均有离线回归。测试中的语义响应、计时与Provider均明确为fixture，不能作为真实效果。
- 相同执行重新评分/换Run/检查项重排时，复验来源与完整材料后重新关联；新增要求、答案/配置/Corpus/来源/题目改变拒绝旧观察。必需的保留角色审查缺失也不能伪装为诊断完成。
- 真实来源、完整阶段、必要安全及范围保护不放松；补充项需独立核验才能解除旧引用锁定，等价来源需来源/型号核验。
- 必要联动必须逐方向有实际观察和全部改动的依赖说明；D只组合真实完整实验已经证明有效的来源。离线测试证明验证器允许合法方案，不能证明组合后的业务改善。
- Qualified后可继续；报告已确认、上一轮未完成、预算耗尽、重复配置/假设等保护仍生效。预算不足明确未完成，Unknown或未结算请求阻止重发。
- 正式DB SHA-256前后相同：`ef4941e2229969257e086f35e45898e20c743003d9053d359bbef63aafd7d154`。Golden、Corpus、旧评分/原答/引用/Checkpoint未回填，Judge V5.1身份、11 Gate、Regression及三个人工Gate保持。

## 测试结果与边界

后端全量843项中837通过、5失败、1错误；六项在原始提交 `59e4f42` 的隔离对照中同样失败，不能写成全量绿灯。本轮相关定向200项通过，末次诊断/保留/复用保护73项通过（有重叠，不相加）。前端44个文件254项通过，TypeScript/Vite构建通过。浏览器断言实际10行、无页面异常；唯一架构源已导出SVG/PNG/manifest并目视检查。

六项既有失败分别是：`test_api` 的四份正式PDF、Mini生成状态、Partial禁止新生成三项；`test_machine_gate` 的旧Knowledge身份fixture；`test_baseline_resilience` 的旧Judge响应fixture；`test_judge_evidence_roles` 的历史Ranking预期。它们未被删掉、跳过或修改来美化结果，详见[验证摘要](../outputs/agent_closed_loop_20261022/verification_summary.json)。

## 下一步真实授权（尚未获得）

建议先只完成9题统一语义补证：Q03/Q04/Q06/Q07/Q17/Q24/Q27/Q28/Q29；最多9次，不自动重试，申请费用硬上限10元。10元是申请的停止上限，不是已核实报价；执行前必须重新核验24小时内价格及人民币计价依据，逐请求预留，余额不够即停止并保留未完成。不沿用历史费用授权。

本阶段不生成答案、不调用策略Agent、不启动A/B/C或任何Sandbox、不重跑Baseline、不自动审批/发布。补证后先验证9题结果是否全部闭合，再单列Agent与全冻结50题Sandbox的范围、调用上限和预算，另获授权；当前没有对这些后续调用作费用承诺。

冻结题目清单、输入binding和停止条件见[待批准方案](../outputs/agent_closed_loop_20261022/proposed_real_diagnostic_authorization.json)。执行时必须重新预检；任何材料变化使旧binding失效。

## 详细代码与原始证据

| 证据 | 定位 |
|---|---|
| 共用材料预检 | [canonical_evidence.py](../backend/app/canonical_evidence.py)、[golden_v2.py](../backend/app/golden_v2.py)、[evaluation.py](../backend/app/evaluation.py) |
| 诊断复用、独占请求、批量预算及身份重验 | [evidence_resolver.py](../backend/app/evidence_resolver.py)、[main.py](../backend/app/main.py)、[CLI](../scripts/agent_diagnostics.py) |
| 全量承接、候选资格与必要联动 | [optimization.py](../backend/app/optimization.py)、[diagnostics.py](../backend/app/diagnostics.py) |
| 必要事实/范围、等价载体与选择反事实 | [diagnostic_evidence.py](../backend/app/diagnostic_evidence.py) |
| 真实运行排序与参数合同 | [retrieval.py](../backend/app/retrieval.py)、[policy.py](../backend/app/policy.py) |
| 后续轮次、D与来源变动保护 | [governance.py](../backend/app/governance.py) |
| 逐题原始失败检查、答案与字面定位 | [current_ten_sources.json](../outputs/agent_closed_loop_20261022/current_ten_sources.json)；字面未命中不等于不存在等价证据 |
| 全10题隔离Agent输入与历史保护 | [核验结果](../outputs/agent_closed_loop_20261022/current_ten_verification.json)、[可重复运行脚本](../scripts/verify_agent_closed_loop.py) |
| 排序反事实（不含新答案或修复结论） | [query_only_counterfactual.json](../outputs/agent_closed_loop_20261022/query_only_counterfactual.json) |
| 当前统一补证计划 | [diagnostic_plan.json](../outputs/agent_closed_loop_20261022/diagnostic_plan.json) |
| 页面（隔离API预览） | [截图](../outputs/agent_closed_loop_20261022/agent_workbench_offline.png) |
| 回归 | [test_agent_closed_loop.py](../backend/tests/test_agent_closed_loop.py)、[Resolver回归](../backend/tests/test_evidence_resolver_v5.py)、[工作台回归](../frontend/src/diagnostic-workspaces.test.tsx) |

只读复验命令：

```sh
python3 scripts/agent_diagnostics.py --run EVAL-20261021141811373593
python3 scripts/verify_agent_closed_loop.py --run EVAL-20261021141811373593 --output /tmp/agent-closed-loop-check.json
```

批量真实执行必须使用独立PaidRun、已冻结的预检binding、授权编号、max_calls、预算和新核价快照；CLI的`--authorize-provider`和API授权字段是执行门禁，不表示本验收单已经获得授权。
