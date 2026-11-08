# Golden 真实批量恢复验收 · 2026-10-26

当前工作集 `GCONTENT-10c6ab67b1ef279d70b4f361`，原50题、ID和20/10/20配额保留。执行已完成，审核与冻结尚未完成。

## 真实根因

1. Q32已完成Provider响应为有效JSON，但无源负向检查点错误引用背景材料，严格引用校验抛错，被包装成“未返回有效JSON”。请求`ceec4305-581c-4ad1-b779-22133b9244df`、Checkpoint请求`03d787267bcd472e91a7d9e4e6f60eb1`有真实Usage；批量外层异常处理令Q33–Q50未运行。
2. 异常选择混合缺失阶段与已完成质量争议，可能重复付费；缺失QC还显示未达85。现按当前身份选择缺失/技术中断，复用已完成阶段；失败、低分、P1和人工待审分开。
3. Q36原Probe把污水箱约30秒冲洗流程扩大为管路/残留达标的完整答案。通用范围核对修复后真实复核确认负向有效，但QC82/P1发现背景证据及已知部分说明不完整。已通过既有Revision最小补齐，当前真实QC96/P2；原失败不删除。
4. Q29业务审计缺少已归档的题目收窄谱系。核实归档SHA及已应用Revision后提供真实谱系，重新执行一次业务审计通过；未恢复旧实验或复用历史批准。

## 当前50题结果

|项目|实际结果|
|---|---|
|Hard Validation预检|50/50通过；不等于冻结前人工审核|
|Probe|50/50通过，保留12题检索覆盖风险|
|QC|50/50达到85且无P0|
|业务审计|50/50完成并通过|
|当前技术失败/未知请求/缺失阶段|0 / 0 / 0|
|机器合格 / 人工关注|36 / 14|
|Human Gate 1|Pending，14题异常处置尚待用户确认|
|正式冻结|未执行，approved Snapshot仍为0|

逐题完整诊断见[初始矩阵](GOLDEN_BATCH_INITIAL_DIAGNOSIS.json)、[最终50题矩阵](GOLDEN_BATCH_FINAL_MATRIX.md)及[验证摘要](GOLDEN_BATCH_VERIFICATION.json)。未执行不归类低分，检索未命中不归类Golden答案错误。

Q09保持88/P1：接受受损电池停用、不得自行尝试放电、转厂家或合规回收方确认的建议待用户确认。Q15保持93/P2及独立语义待审：手动启用步骤有据，不承诺原地静止刷洗，待用户确认。其余12题为Q03/Q04/Q06/Q07/Q08/Q13/Q14/Q17/Q24/Q27/Q28/Q29的检索风险（含4个QC P1）；详见[集中处置依据](GOLDEN_BATCH_REVIEW_BASIS.md)。无当前P0，不用高分冒充人工批准。

## 修复及执行

仅修改Golden QC响应合同/一次有限纠正、Probe范围核对、批量单题失败隔离/状态持久化/成功复用/缺失选择、治理内容Revision携带与未执行文案。未知执行或未结算Usage、鉴权/余额/配置错误仍停止；不无限重试。共享正式Judge、Parser、11 Gate及评测合同未改。

最初成功的32个Probe和31个QC原记录完整保留。补跑Q32仅缺失QC、Q33–Q50缺失阶段，随后定向处理Q29和Q36。当前批量状态completed；不存在未解释中断。合计新增95次真实RPC：DeepSeek59、embedding18、rerank18，输入Token1,657,967、输出Token168,045。Usage及请求明细在本地备份目录final_usage.json；不将费用估算当真实扣费，不设置额外金额封顶。

Q36唯一内容修订详见[修订审计](GOLDEN_BATCH_SCOPE_REVISION.json)，问题、参考答案、类型不变，仅负向预期行为/检查点/背景来源。单题内容哈希改变后重新记录质量结果；其他49题业务内容不变。按完整RPC输入哈希复用已成功检索请求。

## 验证与保全

9个相关测试模块共131项通过，覆盖边界、恢复、异常隔离、身份、审核/冻结前置和严格引用；不宣称全仓测试全部通过。测试使用隔离DB/Corpus，未把Mock写入正式库。实际页面已核对显示50题、Probe50、QC50、机器36、关注14；现有批量入口无缺失阶段时禁用。

写入前SQLite Backup API完整备份并验证，另有Q36修订前备份，位置`backend/data/audit_backups/golden_batch_recovery_20261026/`。原质量、Snapshot和历史审计保留；21个PDF/索引资产哈希不变。Judge、Baseline、Candidate、Agent、11 Gate、Pipeline、Corpus、Embedding/FAISS实现、前端代码、旧实验归档、Production/Release/Rollback未改，也未运行Baseline/Candidate或发布。

最终阻断仅为14题有效人工异常确认。确认后仍须用户在现有Golden页面勾选“我确认异常已关闭，并冻结当前 Golden Dataset”，点击“确认并冻结 Golden Dataset”。本轮不代行最终Human Gate或创建已批准Snapshot。
