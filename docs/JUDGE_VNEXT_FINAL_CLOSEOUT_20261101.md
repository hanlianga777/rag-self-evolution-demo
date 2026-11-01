# Judge VNext 最终实施与验收报告（2026-11-01）

`BASELINE_READY=true`。新Golden正式冻结、最终通用Judge协议已修复并验证，当前完整离线回归无新增P0/P1，真实8010/5174可用。**正式新版50题Baseline尚未运行，必须由用户本人在前端点击。** 未运行Candidate、Sandbox或发布，未推送远端。

本结论是“新Baseline的前置条件就绪”，不是生产资格、50题新版完整成绩，也不是把历史技术异常计作业务分。唯一正式SPEC仍为`docs/RAG_SELF_EVOLUTION_SPEC.md`。

## 实际代码修改

1. Golden QC显式传递Required/Conditional父ID封闭集合，checks不混入Auxiliary/Forbidden/Equivalent或Judge子原子。Q36-R2继续Auxiliary，严格Validator未放宽。原失败响应保留；新增Q36 QC仅1次，96/P2通过，没有重跑Q13/Q15或50题相似度。
2. Judge明确角色与check_type矩阵，Equivalent使用fact，只有Negative纯行为Required可negative_behavior。对全文实际主张与“禁错未发生”等状态分工明确，不制造无Final支持的重复事实checks。
3. Q24/Q27在额外纠正后仍出现Golden-only引用或无可定位引文的遗漏issue，定位到通用输出协议缺口。最终Prompt为`judge-vnext-6.4-omission-evidence-protocol`：纯遗漏完整保留NOT_MET、checks与理由；无法合法引用的重复omission issue不要求模型生成。存在实际引文时也不能用Golden冒充Final。真实危险/矛盾/越界主张仍保留issue与真实引文。
4. 现有Validator/裁决函数逐函数AST与6.3一致，Parser仍`business-output-6.2-atomic-consistency`。没有运行时过滤无效输出、按题号设结果、删除失败原子或修改Golden预期。新边界测试使用真实失败响应和明确标注的离线合法输出对照，后者不作为Provider结果。
5. 独立历史Replay只调用唯一正式Provider Judge，正式REQUEST_LIMITS、每题一次、有界独占claim；只处理未尝试题，不写正式Run或历史成绩。Q17中断后原reserved账本未修改、未释放、未重试；其余33题经绑定父链与退出证据后单独执行。

原六轮其他实现（独立Candidate评分及后置Regression、固定安全/注入题集、四维质量、11 Gate、性能身份、Bad Case与Agent交接、引用展示和历史兼容）保留既有实现；未重构第0轮、改11 Gate阈值或重新设计产品规则。

## 正式Golden

| 字段 | 实际值 |
|---|---|
| 新Snapshot | `GD-20261031071527`，数据库status=`approved`，50题 |
| 数据库snapshot_json SHA256 | `6aa7441f287cbe8564a2d7c3cf21e850a9050a9932a2382040090c63bc4c9c79` |
| 50题合同manifest SHA256 | `9e592b55e42a8055f055f53a7870e1eee549390c892f27f5eba3b8e06677b88e` |
| 定向Revision | Q13双Required无损原子化；Q15厂家执行顺序；Q36局部30秒R2为Auxiliary |
| 其余47题 | 内容及既有合格审核身份保留 |
| 审核 | Owner Delegated AI，三题独立审核，19条Child/PDF引文核验；没有伪造人类签字 |

冻结前在副本演练原有完整Gate，正式沿`review_owner_delegated_batch`及`create_dataset_snapshot`完成。旧Snapshot `GD-20261027070931`不变。Q13的既有检索缺口明确`retrieval_not_fixed=true`，不把Golden规范补入Final。

## 四例真实校准

| 样本 | 预期 | 最终有效裁决 | 输入/输出Token | 耗时秒 |
|---|---|---|---|---|
| Q36-overall-insufficient | PASS | PASS | 7389/8004 | 46.699 |
| Q36-local-30s-as-overall | FAIL | FAIL | 7381/14782 | 87.103 |
| Q39-clarify-only | PASS | PASS | 6240/6343 | 36.736 |
| Q39-clarify-then-wet-wipe | FAIL | FAIL | 6239/14830 | 83.332 |

本组累计5次（含具名额外批准的Q39正向一次），零自动重试；原技术无效记录保留。此组真实Prompt版本按各自记录保存，不冒称全部为6.4；业务合同及严格Parser未改。先前Q15/Q22/Q24/Q49八例有效证据保留，未重复收费。

## 历史50题及后续协议验证的版本边界

源Run：`EVAL-20261027122116244939`，原始Answer/真实Final/厂家来源和新合同全部通过只读核验。6.3独立回放包含50个题目及显式技术状态；原50次预算含Q17的1次Unknown预约，另获Q04/Q13/Q24/Q27各1次具名纠正。累计54次尝试/预算消耗，53次有已知响应，Q17执行和Usage未知。

| 6.3有效视图 | 数量 |
|---|---:|
| PASS | 38 |
| FAIL | 9 |
| NOT_EVALUABLE | 3（Q17、Q24、Q27） |
| 可比较的有效判分翻转 | 0 |

Q04、Q13的额外纠正有效FAIL，原技术失败仍保留。Q24、Q27的6.3额外响应仍无效，不能把其raw verdict=FAIL计作业务结果。Q17旧工作进程已退出、没有最终响应或Usage，仅在独立视图标记Unknown；原账本未重写。

用户最新验收允许“真实完成或准确记录不可评估题”，因此不虚构历史必须零NE的条件。正式成绩/Overall/11 Gate仍不能以不完整或混合版本样本凑齐。

修复通用协议后，另获明确批准以6.4对Q24/Q27各验证一次，采用独立协议身份；不发送旧响应或预期裁决，不回填旧6.3成绩：

| 当前6.4协议验证 | 严格有效性 | 程序裁决 | 实际失败原子 |
|---|---|---|---|
| Q24 | 有效 | FAIL | Q24-R4、Q24-R6 |
| Q27 | 有效 | FAIL | Q27-R1、Q27-R2、已触发Q27-C2、Forbidden0 |

两例均保留原子硬失败与真实问题，未借省略重复issue变成PASS。真实记录见`docs/judge_vnext_20261101/protocol64_real_validation.json`。6.3完整逐题Answer、Final、检查点与来源见`historical_replay_final_6_3_comparison_20261101/comparison.json`；没有有效翻转，所以不存在伪造翻转解释。旧成绩不作为真值。

## 最终离线与运行态

- **当前6.4完整后端：1124项，1111 PASS、11 FAIL、2 ERROR，0 SKIP。全量未全绿。** 13项均匹配既有P2，新增异常0，P0/P1为0；源码运行前后未变，无后台线程异常。D生命周期原完整链路本次PASS，未删除或降低旧断言。25项历史异常映射及当前逐项分级见机器索引和`final_test_triage.json`。
- 当前专项111/111通过；治理/恢复/报告/权限绑定工具44/44通过。旧6.3完整1118项及原1098项日志保留，不与新版分母混算。
- 完整测试导入app前隔离DB、Corpus/索引/PDF、uploads与空.env；底层阻断网络与正式路径写入。网络入口尝试0、受保护写尝试0。1次被拦截的sysctl物理核探测由库正常回退；不是Provider调用。硬编码正式只读测试只读取SQLite Backup API副本。
- 既有前端301测试与构建证据保留，当前前端源码未变。本次真实5174三Tab无错误、API写操作0；历史案例抽屉800px证据保留。新Snapshot当前无Baseline，空状态不伪装旧成绩。
- 实际8010加载6.4及新GD，入口`can_start=true`、`can_resume=false`，当前Baseline=`not_run`。服务安全后台启动、有PID/日志、无自动重启、迁移或付费恢复。
- 29张正式表与授权冻结后的指纹完全一致，21个Corpus/Index/PDF资产不变；旧Run、旧Snapshot、原答案及47题保留。用户`verify_self_evolution.py`的16增/14删及原未跟踪资产没有误提交。

## Token、费用与剩余外部事项

从7597ff6本次续接计：Golden QC1、目标校准5、6.3历史尝试54、6.4协议验证2，共62次尝试/预算消耗；61次有已知响应，1次执行/Usage未知。已知Token仅记小计，不将未知请求记零；所有实际费用未返回，统一 **Unknown**。逐调用参数、原始响应、Token和耗时见`provider_accounting_final.json`及各ledger。

Q17只有在后续取得账单/响应对账证据后，才能另议该历史请求；本次不自动重发或释放预约。这不允许把它判为业务PASS/FAIL，也不阻断已具备前置条件的全新用户触发Baseline。

正式新版50题Baseline、Candidate、Sandbox及人工发布均未由Codex启动。下一次正式Baseline必须由用户本人点击，之后才有新版完整成绩和11 Gate。新Baseline Ready不等于既有12个业务问题已修复或版本已合格发布。

代码、唯一SPEC、测试、冻结及真实验收证据随本地Git提交保存；不推送GitHub。最终提交Hash由交付回复给出，避免在提交内容中自引用。
