> 本记录保留10月31日中途状态；最终实现、6.4验收及Ready判定见 [2026-11-01最终收口](JUDGE_VNEXT_FINAL_CLOSEOUT_20261101.md)。

# Judge VNext 最终收口记录（2026-10-31）

当前状态：`BASELINE_READY=false`，历史50题Judge-only Replay进行中，以真实执行产物为准。本文件随本次连续任务更新，不把进行中结果当完成。

本次从7597ff6继续，保护用户已有scripts/verify_self_evolution.py（16增/14删）及未跟踪资产；无远端推送、正式Baseline/Candidate/Sandbox或发布。

## 已落地的代码和合同

- Golden QC明确Required/Conditional父ID封闭集合；Q36-R2保持Auxiliary。原错误QC继续严格拒绝；修复后新增一次真实QC：96/P2、全部内容验证通过，输入7468/输出4475 Token、28.242秒、费用Unknown。Q13/Q15已通过调用不重跑，未重复50题相似度检查。
- Judge原子角色类型矩阵明确Equivalent使用fact，Negative纯行为Required才可negative_behavior。保留严格Validator与程序裁决。
- Q39后续真实响应把Forbidden未发生的观察重复写成无Final事实checks，严格校验仍拒绝。通用Prompt6.3明确checks只记录实际回答主张/必要行为；未发生禁错仅对应Forbidden原子NOT_MET。没有评分后删除输出，没有按题号判分，没有修改Golden或金标准。
- Replay使用正式REQUEST_LIMITS，独立文件身份、真实保存Answer/Final、每题最多一次、技术异常即停、不回写历史成绩。
- 唯一正式SPEC已同步；11 Gate及阈值、固定安全题集、Parser、四维质量及历史读取保持原合同。

## 新Golden

- ID：GD-20261031071527，数据库status=approved，50题；Q13/Q15/Q36定向Revision，其余47题内容未变。
- 数据库snapshot_json SHA256：6aa7441f287cbe8564a2d7c3cf21e850a9050a9932a2382040090c63bc4c9c79。
- 50题评分合同manifest SHA256：9e592b55e42a8055f055f53a7870e1eee549390c892f27f5eba3b8e06677b88e。
- 审核模式Owner Delegated AI，19条实际Child/PDF引用复核；未伪造人类签字。Q13既有检索不连贯仍明确retrieval_not_fixed，不将厂家Golden来源冒充运行Final。
- 真实治理流程先在SQLite副本演练完整Gate，然后正式review_owner_delegated_batch/create_dataset_snapshot；SQLite Backup API备份在/private/tmp/judge-golden-finalize-review-20261031/，完整产物见golden_frozen_20261031。

## 四例真实校准

| 样本 | 预期 | 最终实际 | 输入/输出Token | 耗时秒 |
|---|---|---|---|---|
| Q36-overall-insufficient | PASS | PASS | 7389/8004 | 46.699 |
| Q36-local-30s-as-overall | FAIL | FAIL | 7381/14782 | 87.103 |
| Q39-clarify-only | PASS | PASS | 6240/6343 | 36.736 |
| Q39-clarify-then-wet-wipe | FAIL | FAIL | 6239/14830 | 83.332 |

补充授权内四次调用含Q39正向一次技术无效；用户随后明确追加一次正向复校准，最终符合金标准。累计5次、零自动重试，所有原始响应保留，费用全部Unknown。技术无效原请求输入6045/输出10537 Token、60.846秒，未记作业务FAIL。逐原子、实际参数及响应路径见final_four_calibration_results_20261031.json。

## 验证证据

- 当前Prompt6.3定向105/105通过；包含新增QC3、Equivalent8、Nonclaim7，以及冻结合同、安全和相关当前回归。历史真实无效响应仍拒绝，新增无Final事实仍拒绝，Forbidden违反仍FAIL。
- Replay5项离线边界检查通过；恢复/冻结/报告工具离线安全测试另见日志，不冒充真实Provider Replay。
- 既有完整后端1098项原始结果仍为1084PASS/12FAIL/2ERROR；13项P2旧合同冲突留痕，唯一D生命周期P1已有合法fixture后续6/6通过，原47断言与生产准入不变。25项历史异常映射及分级见full_backend_regression_index.json，当前分类没有未闭合P0/P1。没有伪报全量测试全绿。
- 既有前端301项及构建通过的证据保留；本次真实5174三Tab、800px Drawer无页面错误、无API写操作，8010实际加载Prompt6.3/Parser6.2，入口can_start=true。此入口配置可用本身不替代完整Ready条件。
- 29张表/21个Corpus及Index/PDF资产保护复核通过，仅新增3审核、3批准、1Snapshot并改变三道当前编辑状态；旧Run/旧Snapshot/47题/原答案保留。见history_protection_20261031.json。

## 历史50题回放

原Run EVAL-20261027122116244939、原保存50题Answer/Final全部通过只读来源校验，新冻结合同与manifest匹配。正式回放仅创建独立文件结果，generation_calls=0、production_database_writes=0；历史V1耗时不作为V2/Max性能资格。执行身份cbc127aaf104dc41058fcf5b2f3587771a6b447cba8bae317bb698e43ab4b1ad。最终结果与翻转解释待本轮实际执行完成后写入。
