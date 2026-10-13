# 五类典型Bad Case × 四大技术方向验收

2026-10-13，承接 `cbc0a61` 已完成的评测治理与两个工作台。Ponytail full：复用既有诊断/规则/Drawer，不新增依赖，不改其他一级导航。本轮自身Provider调用0次、费用0元；未启动任何Golden、Probe/QC、Baseline、Agent生成、Candidate/Sandbox或治理执行。

## A. 产品逻辑

五类描述“出现什么现象”，四方向描述“保存证据支持的主要技术根因”，可信度单独保留。一个问题可以有多个现象，但只有一项保存的Primary，可有Secondary。根因未知不会因新标签变成Retrieval，Needs Review/Disputed不会升级Confirmed。Evaluation / Data Quality只作治理背景。

|典型现象|实际实现及证据边界|本次历史Baseline中可靠观测|
|---|---|---|
|检索失败|Golden required_chunk_ids须能在真实候选Chunk/matched_child_ids中定位，且保存Final coverage未完整；未验证库内存在性的候选未命中信号保持待核实|Q22一题有Final遗漏观测，根因仍Unknown、可信度仍Needs Review|
|检索噪声|需保存的Retrieval Noise类型、实际答案主张及可定位最终Context来源；低Precision不判定噪声|尚无可靠案例；没有由Q22版本冲突自动制造Confirmed噪声|
|模型过度拒答|需保存的Over Refusal类型、证据充分且实际拒答片段可定位；真实缺依据时不接受此分类|尚未形成可靠自动识别；不把Q35合理拒答标成过度拒答|
|安全边界误伤|需保存的Safety False Positive类型、充分证据及实际答案片段；与失守独立|尚无可靠案例；Q38/Q39仍安全失守|
|延迟黑洞|采用保存Performance Failure和问答latency，不增加阈值；分开question_stages、judge_stages、TTFT，最长独立问答环节仅作实测观测|当前两组完整历史Run无此类保存失败；阶段数据存在，不编造瓶颈根因或占比|

检测状态区分observed、not_observed、not_collected。未采集能力不会显示成“已确认0例”；保存标签也不等于Confirmed技术根因。五类之外的无依据生成、来源冲突、定位/分类待核实、安全失守等仍可见。

Q13：Candidate A保留来源时间边界冲突和Unknown/待核实，不创造恰好5分钟的运行规则。Q22：候选证据与Final遗漏、版本范围冲突可查，根因不改。Q32：Baseline保存Generation/Confirmed及无依据步骤。Q35：A保存分类待核实；上一轮E类合同继续存在，但历史缺字段不会回填。Q38：Baseline安全失守；A已保存通过，同时不隐去原证据。Q39：Baseline Safety、A历史Generation均原样保留；不把本轮视图当作重评分。Q40：A定位争议和版本先后风险保留。Q44：原保存Generation/Confirmed及无依据归属否定证据可查。通用实现无题号硬编码或问题关键词猜根因。

## B. 后台实现与冻结边界

`backend/app/diagnostics.py`提供只读 `diagnosis-view-v1`：phenomena及字段来源、原Primary/Secondary、原Confidence、治理依据、检测能力状态、独立问答/Judge耗时、可信目标资格。没有覆盖Failure Tags，所有原Judge/Matcher/Trace保留。

`GET /api/bad-cases`、单案例及 `GET /api/evaluations/{id}`在响应内增加视图，数据库不写入新分类。Optimization Agent的真实输入路径增加同一视图：`bad_cases`、`all_bad_case_audit`、`target_reference_map`；原始回答/证据、Baseline配置、Search Space、历史策略及Sandbox风险仍传递。只有保存Confirmed且属于Retrieval/Generation/Safety/Performance的对象可进入目标引用；Needs Review/Disputed/Unknown仅背景。隔离FixedProvider测试读取实际构造的prompt，验证风险案例不进入目标；未调用真实Agent。

本轮没有修改 `evaluation.py`、`evaluation_contract.py`、`providers.py`或`policy.py`。Judge `judge-v3.2-governance`、Matcher `evidence-v4-fragments`、Policy `v1.3-abstention-scope`沿用上一轮；11 Gate、Safe Rejection≥95%、Regression Critical0/Ordinary≤1、Search Space及评分身份计算全部不变。视图版本只表示解释层，不建立新正式评测身份。

## C. Baseline前端

保留报告/Hard Gate/Bad Case三个Tab及上一轮摘要层级。本轮主要修改Bad Case列表：失败现象、主要技术根因、可信度、核心依据、详情同列展示；默认最多两个现象，其他可展开。

三个紧凑Select支持现象、四方向/待定位、可信度的组合筛选。“其他真实问题”保留五类之外现象，“恢复全部问题”重置三维条件；唯一题号去重统计，空状态区分无匹配和分类未采集。既有题型/召回筛选保留在折叠区，不新增大卡片。

CaseDetails复用原Drawer：问题/实际答案/参考行为、Golden来源、最终Context、Matcher、Judge、Primary/Secondary/Confidence、分类依据和保存的关联候选假设可查；耗时分开问答/Judge，长JSON/Trace默认折叠。加载时优先使用同Run已保存Bad Case，避免短暂缺完整cases时显示假0。

截图（真实已保存数据，本地私有）：

- [Baseline完整报告](../output/playwright/badcase-classification-20261013/baseline-report.png)
- [Bad Case完整列表](../output/playwright/badcase-classification-20261013/baseline-list.png)
- [检索失败筛选](../output/playwright/badcase-classification-20261013/baseline-retrieval-filter.png)
- [三条件组合筛选](../output/playwright/badcase-classification-20261013/baseline-combined-filter.png)
- [安全误伤空状态](../output/playwright/badcase-classification-20261013/baseline-empty-filter.png)
- [案例Drawer](../output/playwright/badcase-classification-20261013/baseline-drawer.png)
- [手机列表](../output/playwright/badcase-classification-20261013/mobile-baseline.png)、[手机Drawer](../output/playwright/badcase-classification-20261013/mobile-drawer.png)

## D. Agent、Candidate、Sandbox与Regression

Agent根因页用12题实际列表与共享组合筛选替代五张根因大卡片，仅保留紧凑12/5/7/0概览。每题关联保存的Candidate和参数干预，不根据根因固定分配A/B/C。策略页展示真实目标现象/根因、Hypothesis/Why/参数/Expected/Risk，目标可打开证据。

A/B/C卡片继续等宽等高，目标首题及分类可见，展开目标列表展示现象、技术根因、可信度和保存Hypothesis；点击打开原始CaseDetails。未采集不假造预期收益，B/C保持Generated且旧身份守卫仍禁止执行。

Sandbox和Regression新增保存逐题对照：读取候选所属完整Baseline及其保存evaluation_run_id，先校验两侧Evaluation Identity及Golden一致，通过已有all_fixed_question_ids/new_regression_question_ids定位，显示原/新增现象、保存根因及可信度、两侧passed、依据变化和治理待核实信号。可组合筛选，分别查看Baseline或Candidate证据；不重算历史修复/Regression资格。未运行候选明确没有逐题结果。

真实A：Overall97.20、Gate11/11、Bad Case12、全部原问题修复4（Q06/Q24/Q32/Q38，其中指定目标2、附带2）、新增普通失败4（Q13/Q33/Q35/Q40）、Regression FAIL、NOT_QUALIFIED。净改善0，不制造Winner。B/C不显示模拟成绩。Sandbox摘要区分已完成A和待运行B/C，Recommendation仍由正式资格合同决定。

截图：

- [Agent完整问题列表](../output/playwright/badcase-classification-20261013/agent-list.png)
- [Safety+Confirmed筛选](../output/playwright/badcase-classification-20261013/agent-safety-filter.png)
- [Agent保存策略](../output/playwright/badcase-classification-20261013/agent-strategy.png)
- [ABC完整方案](../output/playwright/badcase-classification-20261013/candidate-cards.png)
- [候选目标列表](../output/playwright/badcase-classification-20261013/candidate-targets.png)、[目标证据](../output/playwright/badcase-classification-20261013/candidate-target-evidence.png)
- [Sandbox修复对照](../output/playwright/badcase-classification-20261013/sandbox-fixed.png)、[B未运行状态](../output/playwright/badcase-classification-20261013/sandbox-b-unrun.png)
- [Regression完整列表](../output/playwright/badcase-classification-20261013/regression-list.png)、[Regression证据](../output/playwright/badcase-classification-20261013/regression-evidence.png)
- [手机Agent](../output/playwright/badcase-classification-20261013/mobile-agent.png)

## E. 工程验收与数据保护

- 后端专项57项通过，包括只读API、不落库、五类依据、多标签/Unknown/原可信度、合理拒答、安全误伤/失守、来源定位、问答/Judge区分、非一一映射、Agent完整上下文/风险排除/Search Space。测试隔离DB、索引、PDF/env，用FixedProvider；不冒充真实调用。
- 前端36文件195项通过。组合过滤、其他问题、唯一题号、空状态、Drawer、真实保存修复列表及B未运行通过。TypeScript与Vite构建通过，diff检查通过。
- 浏览器对正式API读取真实保存数据，全部非GET拦截，审计无写请求、无页面异常；1440桌面、390手机无文档横向溢出，宽表内部滚动，Drawer≤390。采用实测加载完成条件，避免加载中的空表当作最终结果。已视觉检查表格对齐并补上Agent局部table-cell样式，没有修改全局CSS。
- 扩展相关后端97项首轮通过，但某既有异步Fixture在测试目录清理后仍执行Recommendation，出现后台sqlite异常；本轮没有改变对应执行器。最终影响范围57项干净通过。上一轮全量后端既有四个失败的记录仍保留，本轮不宣称整库全部测试全绿。
- 任务前SQLite Backup API备份位于本地 `output/playwright/badcase-classification-20261013/before.db`。正式API重载前确认无Running/Queued任务、属于既有监督进程，未停止独立Worker。后续出现任务范围外新增真实Run `EVAL-20261013120614428980`；本轮只读请求审计没有启动它，不停止、不回滚、不改状态，也不将其调用/费用算作本轮成果。历史校验比较29张表中全部任务前记录仍原样保留；新增运行及新增逐题行单独记录，不错误报告整个数据库字节不变。
- 旧Golden `GD-20261012170200900815`、Baseline `EVAL-20261013055639244452`、A `EVAL-20261013083057546375`、B/C与历史实验/Production记录没有回填。旧Baseline的97.80/10 Gate/12 Bad、A的97.20/11 Gate/12 Bad/FAIL/NOT_QUALIFIED保持。与上一轮验收校验清单比较的74项正式/旧索引产物SHA全部一致。PDF/索引不写入、不切换Corpus；凭据/DB/索引/原始运行产物/截图不入Git。
- 上一轮正确拒答合同、多片段严格定位、冲突范围、版本守卫、Gate详情、六阶段/ABC对齐、统一Drawer和数据保护全部保留。其他一级导航源代码与共享组件未改。
- **旧Candidate B仍不具备直接运行条件**：既有评测规则升级守卫保留。本轮未生成新Candidate或重建实验；后续需授权新版完整统一Baseline及新实验，不能把旧B归入新身份。任务范围外正在运行的新Baseline是否合格、完整及可驱动后续实验，不由本轮只读验收代行确认。

修改文件集中在 `diagnostics.py`、只读评测/Bad Case API、Optimization Agent诊断上下文、两个页面、共享的两页专属诊断/对照组件、局部CSS、测试、SPEC/变更日志及本报告。无新依赖，范围内提交并推送origin/main；最终Commit ID与干净同步状态在交付回复中列出，避免报告嵌入自身SHA。
