# 夜间真实流程执行报告｜2026-10-12

Ponytail full。**完成安全修复、真实资产预检及离线验收；因预算前置条件未通过，停止在正式切换之前。新增Provider请求0次、Tokens 0、费用0元。** 正式结果与隔离结果分别记录，未运行阶段没有借用历史成绩。

## A–O 执行结果

|项|真实状态|
|---|---|
|A 实际完成阶段|完成执行前安全修复、只读正式预检、隔离联动回归；正式阶段1尚未执行。|
|B 正式Corpus切换|未切换。正式仍`CORPUS-c6bbb042130820be7a1a`；新隔离`CORPUS-38c90d5628b68c76d53e`、Medium Plan `PLAN-89801791985fdfe13f1421cf`完整。|
|C Hard Validation|本轮重新使用原Validator：正式49/50；新隔离50/50。切换成功副本再次50/50，不等于正式已通过。|
|D Probe/QC|当前工作集50题均Pending；本轮完成0、通过0，未调用。新身份下机器资格尚未建立。|
|E Human Gate 1|仍Pending。现有批量审核要求`confirmed_manual_review=true`；本轮没有写审批事件，也没有代理委托机制。|
|F 新Golden Snapshot|未冻结，无新ID。|
|G 新Baseline|未运行，无新ID或新成绩。|
|H 新Agent A/B/C|未启动、未生成、未评测；保留历史两轮记录。|
|I Qualified / Regression|本轮未判定；没有新评测，不能报0/3或通过。|
|J Bad Case / Root Cause|完成源码只读核查，见下文；无本轮新Bad Case，不补造诊断，不改UI。|
|K Provider / Tokens / 费用|本轮实际0次 / 0 / 0元。第一阶段历史2次调用不是本轮费用。|
|L 历史数据保护|29张表全部行摘要保持；77个PDF/新旧索引资产摘要保持，第一阶段账本保持。6 Snapshot、24 Evaluation Run、6 Experiment、16 Candidate、2 Production、9 Agent Trace保持。|
|M 阻断和原因|保持现有请求配置，无显式输出上限；20元预算不能可靠覆盖全量范围，按授权停止，不扩大预算。|
|N Commit / 同步|报告与修复、SPEC、ChangeLog同一提交；实际提交ID及push后的干净同步检查记录在本地`output/playwright/golden-overnight-20261012-delivery.json`及最终回复。|
|O 明日操作|需要明确解决预算限制或另行授权调整请求配置。完成预算预检后才能维护切换、真实Probe/QC；之后仍须真实人工Gate1，才能冻结与运行Baseline/ABC。|

## 预算核实与停止依据

用户明确选择保持DeepSeek请求配置；代码没有新增`max_tokens`、thinking开关、模型替换或提示词变更。真实配置为`deepseek-v4-flash`，凭据仅核实配置状态，不输出或保存值。

2026-10-12核对[DeepSeek官方价格](https://api-docs.deepseek.com/quick_start/pricing/)：该旧别名由Flash提供服务，最大输出384K；每百万输出Tokens非高峰0.6美元、高峰1.2美元。按[外汇局中间价](https://www.safe.gov.cn/AppStructured/hlw/RMBQuery.do?COLLCC=546877760)当天1美元=6.7313元作规划折算，**仅50次业务质量审计的最大输出范围**为77.544576–155.089152元，尚未包含输入、QC或负向语义判定。

这不是典型用量预测、预计账单、费用下限或实际扣款。真实用量可能远低于该范围，但不能把典型Tokens当成可靠预算保证。本轮没有为了测费用先付费试跑，也没有擅自限制输出。按照已确认计划，在预算预检失败时停在正式切换之前。

流程调用范围：50题至多50次业务质量审计、50次QC；负向必要时再调用Answerability/Subtype；正常Vector检索涉及每题一次Embedding、一次Rerank，失败停止时减少。QC按原合同可跳过，具体数量取决于真实结果，不虚报固定请求数。北京text-embedding-v4和qwen3-rerank标价均为0.5元/百万输入Tokens，依据[阿里云官方价格](https://help.aliyun.com/zh/model-studio/model-pricing)。Baseline/ABC尚不满足人工前置条件，不计为本轮已执行请求。

## 必要修复与验证

- `app.paid_run`提供显式单次串行运行上下文：全新持久化账本，调用前验证实时身份/价格/剩余预算并预约，返回后校验Provider/model/Usage及费用。缓存按未命中、高峰费率作保守估算；Rerank预算计入逐文档查询。缺失/失败Usage保留不确定预约，不当作免费请求；已有账本拒绝自动重开。
- DeepSeek和Alibaba既有HTTP入口接入同一上下文。请求参数不变；没有公共API扩展或自动化任务。账本只保存请求摘要及Usage，不保存凭据或完整请求内容。
- 原质量Worker可显式传入`paid_run`至线程入口，避免ContextVar不随新线程继承而漏审计。该约束仅对显式受控运行生效，普通任务规则不变；受控入口禁止生成/补题。QC/Answerability只尝试一次，业务质量技术异常保存后停止下一题；已记录检索执行失败会终止，内容不合格继续按原合同处理。
- 完成92项相关离线回归，以及11个真实资产副本切换/SQLite异常/SIGKILL/重复恢复场景；副本成功50/50、失败恢复旧绑定、未完成状态阻止启动。启动A–G及LaunchAgent合同测试通过。Fixture/HTTP替身仅证明守卫，不是Provider实测。
- 仍有既有SQLite资源、Starlette、SWIG/joblib环境警告，不称无警告验收。初次只读预检误用了Candidate表名，改为真实`candidate_configs`后全量复核通过；此错误未触碰正式数据或调用Provider。

没有停止/重启正式服务，没有创建正式切换Journal，也没有正式DB写入，因此本轮没有启动新的正式备份/恢复。隔离恢复演练使用SQLite Backup API副本并保留审计；下一次实际切换仍须维护窗口重新备份。正式后端没有为这次预检重启，新守卫须在合法执行前由新进程加载，不声称运行进程已经热更新。

## 内容和关联复核

当前工作集`GGEN-20261012120721324996`的50题内容与隔离切换预览一致；22题仍17轻修/4实修/1替换，28题与旧Snapshot逐字段保持（仅排除既有生命周期字段）。20/10/20、9 Topic保持。367行原始向量字节一致，摘要`556641bf5b3bc2da30d32c645bfc3eac2be5044b8cfde182ce9114cc8f41a852`；没有新Embedding或全库重建。

Q02新隔离Parent及题目合同保留全部14步，原Validator通过；第一阶段真实检索证据继续保留，本轮未重新检索调用Provider。Q42隔离预览Anchor为`DOC-001-C-00031`、`DOC-001-C-00095`，仍是负向材料Anchor。Q16范围限定R1及对应章节，Q22范围限定V2.1/2025-04-18的R3，已有蜂鸣/指示灯范围关联保持，没有把R1要求迁入R3。

## 症状与根因只读核查

`evaluation.py`持久化`failure_tags`、`primary_root_cause`、`secondary_root_causes`与`diagnosis.status/reason`，四方向Retrieval/Generation/Safety/Performance保持。Unknown是待核实；Evidence/Citation失败和评分不足不直接确认为Retrieval。性能归因须实测，Safety和Generation须定位实际失败依据。

`EvaluationPage.tsx`展示症状及可信度，`EvolutionPage.tsx`区分confirmed/disputed/needs_review；`optimization.py`仅把confirmed案例纳入Agent可信目标，并传递根因及依据。Evaluation/Data Quality不新增为第五调参方向。没有本轮新评测数据，具体症状词汇扩展/展示改进留待新数据审核，未修改UI或Agent合同。

## 私有证据

- `output/playwright/golden-overnight-20261012-final/`：只读预检报告、77资产摘要、29表行摘要。
- `output/playwright/golden-overnight-20261012-stage3/`：11个场景、恢复备份及历史保护证据；其中授权标志是隔离测试脚本的固定说明，不代表执行了正式切换。
- `output/playwright/golden-overnight-20261012-final-regression.log`：离线测试日志。

上述数据、索引、备份、凭据和私有审计不进入Git。本轮没有自动批准、冻结、Baseline、Sandbox、Gate2、第二轮实验、D或Production发布。
