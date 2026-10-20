# 评测合同最终收口与Baseline50运行准备

日期：2026-10-20。Ponytail Full。**已完成最小合同兼容修复和统一零Provider验收。已知正确控制的空引用辅助说明可原样接收并形成合法PASS；Q42仍由Guard裁为最终FAIL。没有发现本轮范围内尚未解释的P0执行/安全接口阻断，建议直接进入新版Baseline50独立授权准备，不再默认增加单题真实测试。**

本轮Provider调用0、Token0、费用¥0；无正式Baseline/Candidate/Sandbox、Generation、Retriever、Embedding或Rerank运行，无Golden/Corpus/历史成绩写入。离线通过不保证未来所有LLM判断正确；未知输出仍应明确保存技术异常，而非降低必要事实或安全要求。

## 1. 共性问题与最小修改

已阅读当前SPEC、混合实施与真实集成报告，并核对实际Provider、Parser/Matcher、评分、诊断、比较和资格路径。

上轮第2条LLM的前4项必要事实、实际引用均正确，第5项是问题中明确的资料范围说明：“仅核对资料含义，不对未知瓶装产品是否可加注作判断。”它没有正向事实断言，却被通用引用校验作为事实项拒绝。直接放宽所有空引用会造成安全漏洞；只改Parser也不完整，因为评分器原本会把该项空support再次计为证据不足。

本次增加一个共享的**保守检查角色分类**，不新增Judge、Agent、Schema请求或模型调用，不改现有V3 Prompt：

- 默认所有checks均为`required`，执行原有引用和适用性校验。
- 仅支持问题中句首明确声明的有限资料范围句式：“仅核对/解释/介绍/说明/了解……，不询问某事项”，以及对应的“不对该事项作判断”。辅助项必须完整对应同一范围和同一事项，met=true且两种引用均为空；这只是任务范围回声，不是当前操作安全承诺。
- 问题本身必须存在该明确范围；Golden参考要求中若含相应范围/事项，保守保留为required。没有足够原问题/参考要求、不同事项、条件句/被引用的范围、无法可靠识别的改写均不自动免检。
- 不信任模型自填`kind/role`。不按题号、Run ID、产品名、清洁剂句子或安全关键词给Verdict；测试也覆盖不同领域的“解释资料范围/安装地点”。
- 至少保留一项实质必要检查，不能用一组辅助项构成PASS。所有非空引用仍严格定位，issues及最终Verdict与checks的一致性校验保持。

`business_check_roles`由Provider校验、共享评分和诊断使用同一原问题/参考要求。评分证据充分性仅汇总required项，`programmatic_metrics.judge_check_roles`保存角色及依据；原checks、原始Provider内容、quality和原始Verdict不删除、不改写。

**边界**：有限范围语法不是通用NLP，不声称自动理解任意辅助句。未识别辅助说明仍可能形成技术异常，这种显式失败优于静默接受无法核验的关键要求。安全拒答、停止危险操作、不得授权未知场景、必要断电等实际行为责任不因“否定表达”获得豁免；它们仍由完整Judge合同与现有Guard负责。

## 2. 修改范围与版本

| 文件 | 修改 |
|---|---|
| `backend/app/evaluation_contract.py` | 小型范围角色分类、严格校验边界、新Parser版本 |
| `backend/app/providers.py` | 向共享校验传原问题和参考要求；不改请求/Prompt |
| `backend/app/evaluation.py` | 同步校验上下文、保存角色、必要事实证据充分性 |
| `backend/app/diagnostics.py` | 诊断复核使用相同上下文，避免消费端重新拒绝合法结果 |
| `backend/tests/test_judge_output_compatibility.py` | 10项保存响应/反例/接口测试 |
| `docs/RAG_SELF_EVOLUTION_SPEC.md`、`docs/SPEC_CHANGELOG.md`、`README.md` | 同步生效合同和运行边界 |
| 本报告与隔离证据 | 统一验收及预算，非正式成绩 |

新增`output_parser_version=business-output-2-scope`进入既有`VERSIONS → evaluation_identity → policy_current`。Judge仍为`judge-vnext-3-safety-consistency`，Prompt SHA仍为`e6cdaba08a037d96b3916f041d2513306233c60d35a10fd7c0f881a0afa80c9b`；Matcher `evidence-vnext-1`、Policy `business-vnext-1`、Guard `finite-safety-1`、裁决`hybrid-risk-1`及规则SHA均不变。

旧记录和旧Identity不回填；新的完整Baseline必须使用当前Parser身份。按本次建议请求限制计算的准备Identity为`18e040254eacc1fdc483e6ab9642ced0c6e255d65e9dcaf59e3c80b811211b52`，正式创建前须重新核验Golden、Corpus、运行模型、版本与请求限制一致。

Generation、Retrieval、Embedding、Rerank、Agent策略、既有Gate/Regression/Qualification主流程与前端源代码无修改。正式架构唯一图源已核对：业务节点/关系与UI Contract未变，无需另画或重导拓扑图。无数据库迁移、额外依赖或审批流程。

## 3. 各消费字段一致性

| 字段/路径 | 本次结果 |
|---|---|
| 原Judge JSON/Verdict | 保留原文，不把Guard结论伪装为模型结论 |
| 最终业务Verdict、passed/redline_pass | 从同一`adjudicate`结果生成，Baseline/Candidate共用评分函数 |
| 关键事实证据充分性 | 只对可靠分类为辅助范围的项排除空support；所有必要事实校验保留 |
| Guard confirmed_violation | 原LLM PASS仍可变最终FAIL并保存证据 |
| inconclusive/review_required | 独立风险与资格阻断，不伪造业务FAIL |
| 技术异常 | ProviderInvalidResponse等按原checkpoint/Partial/Failed保存，未形成case，不造业务Bad Case |
| Agent准入 | 仍仅接收已完成真实业务FAIL及可信缺陷；技术异常不准入 |
| Regression/Qualification/发布 | 完整同身份比较与安全风险阻断保持，不新增第12 Gate或降低阈值 |

未发现需要修改Baseline/Candidate/Regression业务规则的冲突。既有异常路径会保留出错阶段、尝试、原响应和错误；未执行题不得伪造FAIL或Completed。新版本Identity阻止旧记录直接作为新版正式Baseline继续比较。

## 4. 一次性离线验收

先写回归测试，观察旧实现对真实控制响应失败，再实施修复；最后在导入app前配置临时SQLite、复制Corpus/手册、空.env、清空Provider密钥、强制Mock并禁用网络。共**267项相关后端测试通过**，其中新增10项；前端**42文件/241测试通过**，TypeScript与Vite构建通过。无前端源代码修改。日志仅有既有Starlette弃用提醒，无失败。

| 验证 | 类型 | 结果 |
|---|---|---|
| Q42旧LLM错误PASS，原冲突双方与真实Final | 保存真实响应离线回放 | Parser合法；Guard确认方向违规；最终FAIL、资格阻断 |
| 正确清洁剂控制，原第5项空引用 | 保存真实响应经生产Provider Parser/评分离线回放 | 原JSON不改；原LLM PASS→最终PASS；sufficient=true，无资格阻断 |
| 明确引用错误、撤回并纠正 | 冻结答案/真实资料 + 显式Mock响应 | Guard无误杀，最终PASS；不是新真实LLM验证 |
| 逐个删除前4项必要事实引用 | 故障注入 | 均保持技术异常，不能凭原PASS放行 |
| 安全不执行/必要断电等空引用 | 故障注入 | 仍按必要行为拒绝，不因否定或自标auxiliary免检 |
| 不同问题范围、Golden规定范围、仅辅助项、假引用/缺字段 | 正反例 | 不静默放行；模型角色标签无效 |
| Q39、Q07、B/Q36及A1/A2/A3 | 既有安全专项与Guard回归 | Guard仍不声称覆盖未知液体/断电/介质；原语义合同与有限适用边界不变 |
| 技术异常→Bad Case | 显式损坏响应/诊断 | 评分抛技术异常，不产生业务FAIL；不进入Agent技术目标 |
| Baseline/Candidate、恢复/Stop/Unknown、比较/资格及11 Gate | 相关隔离回归 | 通过；原阈值、部分运行阻断保持 |

[保存响应回放结果](../backend/reports/evaluation-contract-closeout-20261020/saved-real-replays.json)、[测试汇总](../backend/reports/evaluation-contract-closeout-20261020/test-summary.json)、[后端日志](../backend/reports/evaluation-contract-closeout-20261020/backend-tests.log)、[前端日志](../backend/reports/evaluation-contract-closeout-20261020/frontend-tests.log)、[构建日志](../backend/reports/evaluation-contract-closeout-20261020/build.log)。

## 5. 200条历史只读回归

使用原历史问题、回答、完整Final与冻结独立标准，复用现有`verify_evaluation_vnext.py`经生产Provider解析、共享评分、诊断与比较路径处理**显式离线Judge测试响应**：

| 组 | PASS | FAIL |
|---|---:|---:|
| BL | 37 | 13 |
| A | 41 | 9 |
| B | 40 | 10 |
| C | 39 | 11 |
| 总计 | **157** | **43** |

200条完整身份/答案/Final哈希通过，全部无未解释Parser系统失败。每组50题均可经当前合同处理显式合法响应；这是程序可评分性，不是新模型对50题的准确率。原比较、持续FAIL新增风险及技术目标断言通过。

单独Guard Shadow仍为：confirmed_violation=1、no_violation_detected=6、not_applicable=193、inconclusive=0；独立PASS误杀0，独立FAIL中42条不被该有限Guard确认，不能宣称它们安全。历史分数未回填，157/43未调整。

[200条显式响应回归](../backend/reports/evaluation-contract-closeout-20261020/explicit-200.json)、[独立Shadow汇总](../backend/reports/evaluation-contract-closeout-20261020/shadow-summary.json)。未新增第二Judge，未用独立预期指导生产判分。

## 6. 历史与知识完整性

正式SQLite严格只读：29张表行数/全量逻辑SHA不变；16项索引制品、4份PDF SHA不变。旧真实响应及隔离证据执行清单哈希不变；冻结200条fixture不变。5类正式任务表无活动任务。无知识重建、正式数据写入、Snapshot冻结、人工批准、发布或服务重载。

[完整性与版本证据](../backend/reports/evaluation-contract-closeout-20261020/integrity.json)。本轮真实Provider调用0次、Token0、费用¥0。

## 7. Baseline50运行准备与预算

目标Golden：`GD-20261015135415953347`，保持当前冻结50题与Corpus。采用当前有效生产配置：Abstention、candidate_k=12、top_k=4、Rerank开启，Query Rewrite/Multi Query/HyDE关闭；不进行候选实验。首次调用上限预计：

- DeepSeek Generation最多50次，Judge最多50次；没有额外审核模型或辅助Query LLM。
- 阿里云查询Embedding最多50次、Rerank最多50次；不重新嵌入知识库。无Final时Generation按现有流程本地返回，因此实际可少于50次。
- 保留既有输出限制：answer=8192、judge=32768、query=4096；100次LLM首次请求输出总上限2,048,000 Token（含思考）。

用原Baseline50历史Final/答案**离线重建请求摘要**，未检索或生成新答案：当前Judge输入粗估368,148 Token、Generation输入粗估32,326 Token，合计约40万。历史实际Generation+旧Judge共输入288,955、输出582,236 Token，按当前高峰全未缓存DeepSeek价重算¥5.235798，仅作历史参照，不能当新版实际账单。

执行时重新核实价格：DeepSeek高峰输入未缓存¥2/百万、输出¥8/百万；本项目阿里云北京地域text-embedding-v4、qwen3-rerank均为输入¥0.5/百万，不依赖免费额度。[DeepSeek官方价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)、[阿里云官方价格](https://help.aliyun.com/zh/model-studio/model-pricing)

按实际序列化请求字节+封装余量作为保守输入代理、所有首次LLM满输出上限、Rerank重复Query计量计算，历史资产代理费用 **¥22.744165**。新Generation答案及检索上下文尚未产生，实际输入长度会变化，因此它不是新Baseline完成的绝对费用保证。

**建议申请总预算¥30，首次最多100次DeepSeek+100次阿里云请求，串行执行；每次以实际请求预留，预算不足/Unknown Usage/身份异常立即停止。** 建议首轮异常即停、不自动付费重试；若Owner另行授权既有有限恢复，也必须消耗同一预算、保留成功生成而不重生成，不能因低分重跑。¥30不是必须花完，也不保证异常时仍能完成50题。

**执行入口限制**：历史`execute_baseline`包装及旧完整演化脚本含`accounting_only`，不能直接当作¥30硬预算保护。正式授权后的受控CLI应复用当前`_execute_baseline`核心流程，在既有严格`PaidRun/controlled_run`上下文执行、保持accounting_only关闭，不复用历史无限制授权入口或旧账本。本轮不修改该历史入口、不创建新正式Run。此限制已在准备阶段标明，不能在实跑时忽略。

[逐题请求摘要/预算和新Identity](../backend/reports/evaluation-contract-closeout-20261020/baseline50-budget.json)。收到授权后，首先以SQLite Backup API及产物备份保护真实写入，重新核Golden/Corpus/模型价格/无活动任务/代码提交与版本；创建独立新Baseline与预算账本，逐题保存原答案、完整Final、原Judge、Guard、最终裁决和真实Usage；失败时保存真实技术异常和Partial/Failed，不自动造业务FAIL、续跑Candidate或发布。

## 8. 结论与剩余限制

**已修复本轮确认的通用输出兼容缺陷，并同步评分、Provider和诊断消费端；当前离线验收未发现已知P0接口或安全放行阻断。建议直接申请新版Baseline50正式执行，不再默认增加单题真实Judge测试。**

本次不会证明LLM对任意题的语义可靠性：Q42原模型仍会错PASS，由有限Guard独立拦截；未覆盖风险继续依赖同次Judge，任意范围改写也可能因无法可靠分类而成为技术异常。这些限制明确保留，不以弱化必要事实/操作/型号/安全标准换取全PASS。

业务失败正常进入可信Bad Case/Agent链路；技术失败保留真实执行证据并阻断完成/资格，不伪装成RAG缺陷。Baseline50完成后才能基于新版真实结果判断业务水平和合格技术目标；本轮不能从离线157/43选择Winner或给Candidate资格。

本轮完成代码、文档、测试与范围内提交后停止。等待Owner对**新版Baseline50及¥30预算**的明确授权，不擅自执行任何付费Baseline或Candidate实验。
