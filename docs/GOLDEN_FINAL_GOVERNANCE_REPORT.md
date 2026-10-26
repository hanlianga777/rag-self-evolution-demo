# Golden Dataset最终治理验收 · 2026-10-26

基线与执行前远端main均为ec77f59219bddd2ef33688fc8a00ddcb151922ce。当前工作集`GCONTENT-10c6ab67b1ef279d70b4f361`，Run `GGEN-GCONTENT-10c6ab67b1ef279d70b4f361`。完成全部可自主解决的内容治理及实际必要复验；未批准、未冻结。

## 50题最终审核结果

35题内容通过并原样复用有效质量记录，15题修订完成并按新身份真实复验。原50个ID、20/10/20保持；仅Q15最小修改问题边界，Q09修改答案表述；其余参考答案不改。无已知未解决的内容/事实/安全P0或P1。逐题结论见[50题内容审计](GOLDEN_FINAL_GOVERNANCE_50_AUDIT.md)与[当前质量矩阵](GOLDEN_FINAL_GOVERNANCE_MATRIX.md)。这些均是AI辅助核查及真实机器检查，不冒充负责人批准。

## 集中修订与映射

本轮修订：Q03、Q04、Q06、Q07、Q08、Q09、Q13、Q14、Q15、Q16、Q17、Q22、Q23、Q24、Q28。其中13题仅调整证据映射、逐行来源或来源角色，Q09/Q15另有必要表述/问题修订。通过既有Revision流程，逐检查点移除96条不支持该项事实的关联；同一事实的正确多源或复合证据仍保留，未降低安全要求。全部修改计划在首次应用前保存至本地full_review_and_plan.json，之后集中应用；修改后按新单题内容哈希重新检查，不复用旧成绩身份。

Q03的创建用户、密码确认和主管权限均直接绑定C134；C132保留辅助导航角色。Q14的停机答案只绑定急停动作与立即停止功能的直接证据，恢复按钮/护罩等按条件处理。Q07答案首步的对接站作业条件补齐对应C204。接口、R1/R3分支、危险等级、清洁剂与刷辊更换均按对应事实精确绑定。

## 12道检索风险与审核阻断

完整逐事实对照见[12题检索核查](GOLDEN_FINAL_GOVERNANCE_RETRIEVAL.md)。Q03缺辅助导航但必要事实齐全；Q14急停事实齐全且恢复条件未触发，二者不再因指定ID缺失被阻断。Q08常规事实齐全，缺长期闲置清洁的条件资料；Q13禁覆膜、Q17共同App绑定、Q24厂家推荐已有等价信息，不能因另一Chunk缺失认定这些事实都缺失。其余真实局部缺口保留，Q27/Q29仍明确为核心证据缺失。跨产品/部件混入不作适用证据。

新增Golden只读通用逐事实派生诊断：用当前QC逐项引用核对真实Final、Canonical原文及同文档/产品范围；所有必要引用已定位可消除纯ID缺失的风险高估。未定位只记citation_not_located，不自动断言事实不存在或语义不等价；独立业务对照另外给出确证范围。条件不触发、辅助资料不被机械扩大。原始Probe、Trace和历史分类保留，不把离线分析伪装成新真实检索。

原14题中Q03/Q14/Q09/Q15四项阻断已消除，仍有10题：Q04/Q06/Q07/Q08/Q13/Q17/Q24/Q27/Q28/Q29。它们的Golden答案与来源正确，剩余为实际Pipeline的必要/条件资料缺口或范围混入的风险接受，集中等待负责人确认；不为迎合Pipeline修改正确答案，也不擅自取消现有风险批准规则。

## Q09、Q15与历史QC P1

Q09答案将“彻底放电后进入指定回收箱、禁止普通垃圾、损坏电池报废停用”等手册要求与联系厂家/回收方的谨慎建议明确分开，仅陈述当前废弃条款未给出具体放电操作，不生成自行放电方法。新QC100/P2，真实十项审计通过。

Q15原题含“单独降下/转起来”的能力暗示，改为手动启用清洁头并握安全开关推行，同时询问静止刷洗动作条件是否明确；答案本身不改，新增明确的能力范围检查。新QC95/P2，真实十项审计通过。未将菜单存在扩大为原地静止刷洗能力。

Q04/Q07/Q08/Q17原P1都来自检索覆盖疑点。QC职责明确为Golden内容质量，Pipeline缺口另行披露，不能直接作为内容P1或扣分。四题均在修改映射后真实重审为P2；旧P1原记录不篡改，不靠Parser强制PASS。QC85、P0阻断及实质P1显式复核规则保持。

## 当前执行与费用记录

- 当前Hard Validation预检50/50；来源验证、当前Probe50/50、QC50/50≥85且全部P2、业务质量审计50/50通过。
- 15题真实定向复验完成，35题原有效Probe/QC/审计行ID完全复用；14题相同问题/Corpus的embedding/rerank RPC由原请求哈希精确复用，只有改问法的Q15产生新检索请求。
- 本轮新增RPC 33次：DeepSeek 31、embedding1、rerank1。Q28一次已知空内容响应使用既有限次纠正恢复，原响应/Usage/错误保留。输入Token 560586、输出Token 130316；实际Usage保存在本地new_usage.json及原Checkpoint，不设人为金额封顶、不将估价冒充真实扣费。
- 无缺失/过期质量、未知请求或当前技术失败；批量completed。机器40、待审10，Human Gate pending；人工/委托批准0、approved Snapshot0。
- 已重载原有后端并实际核对页面：50题、Probe50、QC50、机器40、关注10、冻结禁用；前端未改。

## 回归验证与范围保全

最终相关10模块136项测试通过。扩展14模块181项中179项通过、2项既有错误：test_v14_probe_cost的旧fixture在Baseline生成合同预检被拒；test_governance的旧Dataset列表fixture未建立当前批准Snapshot而读取空列表。两处均以ec77f59原函数复现同一错误，不报告全仓通过，不在本轮改Baseline或旧Dataset合同。另修正本轮受影响的一项测试夹具：显式创建当前内容身份的两条隔离待审事件，避免依赖已过期的真实Q09/Q15历史意见。所有测试均隔离DB/Corpus/.env，不把Fixture批准写入真实库。

运行前SQLite Backup API完整备份：`backend/data/audit_backups/golden_final_governance_20261026/before.db`，SHA256 `1b8579954f80770dc651075021518b827501ee291cfe9b6002b56e1a4881e81f`，integrity_check=ok且全部表逐行一致。full_review_and_plan.json、applied_revisions.json、fact_diagnostics.json（含完整引用）、执行日志和Usage同目录仅本地保存；Git质量矩阵仅含摘要、检查点状态与来源ID，不含完整原文和Provider私有日志，能逐题追溯并恢复。原质量记录/审核事件完整保留，审批与Snapshot及实验/生产/回滚表与备份逐行相等，21个手册/索引资产哈希不变。

生产代码仅变更Golden QC说明、Golden派生覆盖诊断和Candidate资格读取；正式Judge/Parser/11 Gate、Baseline/Candidate生成及评测、Agent、Pipeline配置/检索实现、Corpus/Embedding/FAISS、前端、Release/Rollback不改。内部读取判断无架构节点/连线变化，无需另导架构图。没有执行Baseline、Candidate、发布或自动冻结。

## 最终负责人事项

Human Gate尚未Ready。只需对上述10题的真实检索风险作有效接受/不接受的集中决定，详细依据及建议见[一次性审核清单](GOLDEN_FINAL_GOVERNANCE_OWNER_CHECKLIST.md)。无待用户解决的模型欠费、代码中断或已知内容安全事实冲突。接受风险不等于Pipeline充分或已修复；有效处置后仍由负责人在原页面完成最终Human Gate与Snapshot冻结。本轮在此停止。
