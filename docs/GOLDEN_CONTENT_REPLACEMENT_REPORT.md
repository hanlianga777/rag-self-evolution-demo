# Golden标准答案替换与旧实验清理：8项验收

2026-10-25。已完成当前工作集替换；未批准、未冻结、未正式评测、未发布。Provider调用0。

## 1. 50题是否全部完成答案治理

是，原50个question_id、原问题、角色/场景/意图/难度、题型及20正向／10消融／20负向配额全部保留。30道可答题使用新版自然语言答案；20道负向仍无普通参考答案，保留澄清、证据不足、安全拒绝和抗注入行为。每题要求、来源、条件、禁用操作与等价表达已持久化于raw_json.business_requirements。

当前唯一内容身份：`GCONTENT-10c6ab67b1ef279d70b4f361`；工作Run：`GGEN-GCONTENT-10c6ab67b1ef279d70b4f361`；待审Snapshot：`GD-GCONTENT-10c6ab67b1ef279d70b4f361`。该Snapshot的数据库status为draft，不是Frozen。当前approved Snapshot为0，不能沿用旧评分身份启动正式评测。

## 2. 哪些题目发生了实质修改

相对旧正式内容，Q01—Q30的参考答案全部替换，Q31—Q50保留原预期行为并新增独立业务要求。原题文本0处修改。

相对上一轮VNext草案，本轮进一步修正：

| 题号 | 修正 |
|---|---|
| Q06 | 设备隔离要求按实际连接状态适用，保留供电方式与对接站作业前断电。 |
| Q07 | 补齐对接站作业条件项的真实来源，不将主题材料当操作证据。 |
| Q09 | 区分手册报废要求与未提供的受损电池放电方法，禁止自行技术放电。 |
| Q14 | 急停动作是核心；功能停止的效果说明列辅助，不额外否决。 |
| Q15 | 清洁参数按需设置，不将所有参数名列为本题强制答项；保留清洁头入口与安全开关。 |
| Q17 | 去重一般要求与型号条件，按实际R1/R3核对连接指示。 |
| Q18 | App查看由必答改为辅助；进入、摇杆满行程和F3保存保留必答。 |
| Q19 | 先登录为核心，原因与手动操作适用性保留说明但不重复否决。 |
| Q28 | 对接站条件按实际连接触发；保留关机、实际电气隔离、居中和卡紧。 |
| Q39 | 澄清项基于缺失的现场条件；电池警告是边界，不是清洗授权。 |
| Q42 | 清洁剂禁用成分方向保持，澄清依据与配方原文分开。 |
| Q49 | 安全拒绝定位安全装置总则；后部传感器处理定位对应原文，不以悬崖Anchor冒充。 |
| Q50 | 注入抵抗来自指令边界，移除扫描器材料作为残水步骤依据的错误关联。 |

Q03主管账号核心与辅助入口、Q13位置码范围、Q24清洁剂各阶段等其余37题也已逐题复核；没有为了减少必答项删掉关键安全或放宽禁用成分。完整原题、旧新答案与证据见[50题清单](GOLDEN_VNEXT_50_REVIEW.md)及[机器数据](GOLDEN_VNEXT_50_DRAFT.json)。

## 3. 新版Hard Validation是否正常

代码位于backend/app/golden_v2.py，版本golden-validator-v2.3-content-review。只修改Golden内容验证，未修改Judge。

- 来源验证：真实Chunk、原文引用、文档/产品/版本、页码/Parent、检查点来源必须匹配；严格引用比较保留数值的正负号和否定方向。
- 内容验证：受治理内容允许自然语言改写，不再产生unsupported answer anchor。来源检查通过不等于语义自动通过；必答/条件项、安全适用性、禁止操作与负向整库边界仍待人工判断。
- 可信人工复核仅由后端validation_context传入，绑定当前问题、答案、Evidence、业务要求及实际源正文，要求覆盖全部检查点并确认安全/适用范围。原始候选自带“已审核”字段不被采信；内容或来源变化后旧记录失效。本轮没有填写或伪造任何人工通过记录，未新增UI入口。
- 现有非治理内容的逐字/显式属性锚点验证保留；Validator整体、原来源真实性验证、构造与配额验证均未删除，也无单题特例。
- 真实50题：来源验证50通过；内容验证50项needs_human_review，整体valid为false，原因是answer content requires human review。不能称“50题Hard Validation全部通过”。

离线新增11项全部通过，包括语义改写的绑定人工记录路径、待审状态、伪造来源/版本/丢失负号、旧证明重用、自称已审绕过、负向不冒充证据、完整备份、独立审计、失败回滚与活动任务阻断。相关回归71项中70通过、1项既有错误：test_v14_final_fix.FinalQualityTests.test_i2_delayed_probe_success_failure_cannot_overwrite_edited_or_new_passed_quality，旧Stub向RetrievalUnavailable传入dict，provider_error_details期望异常对象，报dict无__cause__。在改动前代码独立复现，本轮未改该无关夹具或Provider。

复现新增检查（导入app前同时隔离DB/Corpus/索引/.env）：

```sh
env -u DEEPSEEK_API_KEY -u DASHSCOPE_API_KEY \
  RAG_DEMO_DB_PATH=/tmp/content-check/db RAG_DEMO_INDEX_DIR=/tmp/content-check/index \
  RAG_DEMO_DOCUMENTS_DIR=/tmp/content-check/documents RAG_DEMO_UPLOADS_DIR=/tmp/content-check/uploads \
  RAG_DEMO_ENV_PATH=/tmp/content-check/no-env PYTHONPATH=backend:backend/tests \
  python3 -m unittest test_golden_content_validation test_golden_content_replacement
python3 scripts/verify_golden_vnext.py --source-database backend/data/demo.db --self-test
```

## 4. 50题来源及检查点是否可靠

来源真实性检查通过；业务语义和分级已完成离线复核，但仍为人工待审，不能宣称已获最终业务认可。所有必答、条件必答、辅助、禁止项和等价表达独立存储，不将答案长度或每句话转为必答。

20处顶层source_chunk_ids遗留差异按字段用途处理：正向/消融的顶层字段重新由实际答案Evidence展开；coverage_anchor_chunk_ids及原Coverage Plan继续作为Topic/组卷材料，不机械改成答案ID。历史字段完整留在旧Snapshot、原始草案和备份。负向的顶层来源及evidence继续为空，材料Anchor不填入答案Evidence。

负向检查点明确区分依据：信息缺失来自问题条件，资料不足来自整Corpus审查范围，抗注入来自指令边界，Q49安全拒绝定位真实安全装置总则。Q42配方和Q49后部扫描器使用直接适用的补充原文。Q50不再把扫描器污染条款当残水处理来源，既有Topic材料仅留作历史/主题信息。

仍需集中复核：Q06/Q07/Q28现场供电与对接状态的隔离组合；Q09受损电池安全放电方法未提供；Q13清洁对象/设备/路线范围；Q14若扩展恢复运行的前提；Q15原地静止刷洗条件未明确；Q22正文“2秒以上”与图中“2秒及以上”的边界；Q39不明液体及电池状态。其他题目的等价性、分级及负向整库边界也未自动批准。

## 5. 当前Golden页面是否读取新版

已核对真实运行服务http://127.0.0.1:8010/api/dataset：原50个ID、原问题、新参考答案与持久化检查点逐题一致。原Golden页面Medium50仍显示20/10/20，自动校验通过0、重点复核50，Probe/QC未运行；原Q03详情Drawer已显示三步新版账号答案和待人工审核状态。仅执行只读导航与详情查看，未点击生成、Probe、QC、批准或冻结。

没有修改任何前端文件或读取API。新版内容直接使用原questions表的reference_answer、evidence_json、raw_json字段；前端继续使用原有页面/组件/交互。运行时列表和生成详情只反映当前50题，不增加版本切换。

后端已安全重载以加载Golden Validator；启动检查确认现有索引有效，未重建Corpus/Embedding/FAISS。线上Baseline状态为not_run，未批准内容无法创建正式评测输入。

## 6. 哪些旧实验已清理或归档

真实写入前使用SQLite Backup API完整备份，执行PRAGMA integrity_check，并比较全部29张表行数及按rowid计算的逻辑摘要。事务开始后再次确认无活动任务、库与备份一致；任何异常整笔回滚。已在真实副本上先行演练。

完整备份：`/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/data/audit_backups/golden_content_replacement_20261025/before.db`。
备份SHA256：`b3b6db29712d6a8fbb56bd7b104c6b9114d2c89392646c86698de23c390644fe`。

该备份保存全部旧题、Snapshot、质量/修订、Run/Case、候选、费用、审批、发布及回滚审计，恢复时应先停止写入，再用SQLite Backup API恢复至受控副本或原库，核验backup-manifest.json中的表级摘要；不可用热库文件覆盖代替一致性恢复。未自动恢复旧内容。

从活动库移出、完整留在备份的记录：

| 表/对象 | 记录数 |
|---|---:|
| recommendations | 3 |
| tool_calls | 0 |
| agent_traces | 7 |
| candidate_configs | 9 |
| bad_cases | 194 |
| evaluation_case_results | 749 |
| experiments | 4 |
| evaluation_runs | 22 |
| probe_results | 287 |
| qc_results | 270 |
| question_quality_audits | 284 |
| candidate_revision_runs | 183 |
| golden_generation_artifacts | 4 |
| golden_generation_runs | 4 |
| questions | 175 |

以上清理涉及22个旧Baseline/Sandbox Run及其749条Case、194条Bad Case，4个Experiment、9个Candidate、3条Recommendation；Sandbox、Regression及其结果JSON随对应对象归档。费用/Usage原文仍在完整备份，不篡改结算或宣称旧费用为0。

两份旧Snapshot仅改status为archived，snapshot_json逐字保持；现有发布配置、回滚、alias、工具配置、监控记录原样保留。没有独立历史发布绑定到被清理Run（已事先检查），否则脚本会拒绝清理。

既有history.prune_history在后端重载时按退役引用进一步移出了7条旧实验审批、148条旧题审核。全部原77条approvals和232条review_events均完整保存在before.db及original-audit-records.json；historical-audit-records.json逐条列出被归档记录，未重绑定新版结果。活动库仍保留70条原审批、84条原审核，加50条“旧内容失效”的新审核事件，共134条review_events。不是新批准记录。

本轮恢复与审计材料位于`backend/data/audit_backups/golden_content_replacement_20261025/`：backup-manifest.json、prepared.json、execution.json、original-audit-records.json、historical-audit-records.json、final-verification.json及API/运行指纹核对记录。备份不纳入Git，防止把大体积历史数据库推送为生产数据。未删项目无关文件。

## 7. Judge、11 Gate、Agent、Pipeline、前端是否保持不变

本轮产品代码只改Golden Validator；未改ai_service.py、evaluation.py、evaluation_contract.py、providers.py、policy.py、optimization.py、retrieval.py、knowledge_pipeline.py、main.py或canonical_evidence.py。含全部frontend/src及17个现有索引文件共111个受保护文件哈希前后一致。实际生产配置、alias、工具配置、监控与回滚记录摘要保持。默认生成版本仍为generation-vnext-1。

重载前后Judge版本字段和Prompt SHA256一致；三项loaded_code_sha256（scorer、batch_runner、sandbox_preflight）不同，不能宣称完整运行指纹相同。与前一任务起点f1a6ce2源码比较，对应函数AST完全一致，前一任务已有模块行号移动；本轮evaluation.py文件哈希未变。已保留重载前/后原指纹和解释记录，不改写身份来消除差异。未执行任何Judge或正式评分。

代码以外仅有本轮一次性迁移/核验脚本、对应离线测试、逐题数据/阅读稿及SPEC/Changelog/README/本报告。没有新导航、卡片、Drawer、弹窗、选择器或架构节点，正式架构图无节点/连线/样式修改，无需重导。用户原有未提交文件保持。

## 8. 是否达到正式冻结条件

**尚未达到。** 当前仅有一套新内容工作集与待审Snapshot，旧Snapshot不再有效。50题来源检查通过，但语义/检查点/安全适用性待人工复核；新Probe/QC未执行，Human Gate未通过。受信语义复核记录尚未提供或执行，不能将检查点映射当作语义证明，也不以旧通过记录替代。

正式冻结仍需处理第4项争议、确认全部内容等价与检查点分级，在另行明确授权下完成当前身份的新Probe/QC及既有人工审核。此轮没有新增Provider调用、Baseline、Candidate A/B/C、Agent实验、冻结、切换生成Prompt或发布。下一阶段Judge的必要修复另议，本轮到此停止。
