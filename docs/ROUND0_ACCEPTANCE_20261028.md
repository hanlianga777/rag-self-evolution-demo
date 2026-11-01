# Round 0 实施与验收报告 · 2026-10-28

本轮完成基础配置、真实Pipeline能力、实验身份和指定页面迁移；**只完成离线验收，真实 API 未验证**。Provider调用0，正式Golden QC/Probe/Baseline/Candidate/Sandbox新增0。不批准、不冻结、不发布，不启动Judge VNext修复。

实施基点：`2a0f99c`；隔离分支：`codex/round0-foundation`。原工作区有用户已有修改及审计文件，本轮不纳入。最终Commit和工作区状态随交付另列，避免把报告自身的Commit哈希写成循环依赖。

## 1. 实施状态

|范围|结果|验收状态|
|---|---|---|
|DeepSeek模型|新请求规范化官方`deepseek-flash`，原.env旧别名和历史记录保留；Base URL核查为官方地址|**已实现、离线已验证；真实 API 未验证**|
|任务Thinking|Baseline/Judge独立Max；Candidate OFF/Low/High/Max；Agent High；Rewrite/MultiQuery Low；HyDE/拆解High|**已实现、离线已验证**|
|请求及Usage|真实请求构建发送thinking.type/effort；OFF无effort；启用不发送Temperature；独立最终content提取、Reasoning Token、Usage、请求哈希/UTC时间/响应模型与参数摘要|**已实现、离线已验证；真实账单未验证**|
|隐私/异常|不展示/持久化原始推理；JSON/SSE与残缺Stream推理片段过滤；length/超时/不支持档位明确技术错误；保留Unknown对账、有限重试、按完整请求hash复用|**已实现、离线已验证**|
|共同V2|默认generation-vnext-2，Grounded；其他合法策略继承共同证据/安全规范；生成不接收Golden参考/评分点|**已实现、离线已验证**|
|Baseline默认|12/4/0、Hybrid ON/0.5、Rerank ON，其余原扩展OFF，Parent原行为；不继承旧Production的Abstention|**已实现、离线已验证**|
|Query Decompose|默认OFF；单次JSON最多3子意图，保留原题约束，真实分别检索并共享Candidate→Rerank→Final；保存丢弃/来源/合并/耗时|**已实现、离线已验证**|
|Retrieval MaxTokens|默认OFF不截断；ON可选8192/16384/32768/65536；官方本地Tokenizer精确计数含来源；完整块保留、排除清单和不完整安全处理|**已实现、离线已验证**|
|工具箱/依赖|原12项保留、新3项受控；非法bool/int/档位拒绝；TopK≤CandidateK和Hybrid α依赖保留；Agent证据、主要方向和必要联合参数合同保留|**已实现、离线已验证**|
|共同身份|新共同身份绑定Golden内容、Corpus/Index、Judge模型/Max/Prompt/规则、原11 Gate定义及统计口径、共同V2/模型/业务来源|**已实现、离线已验证**|
|实验身份|Run.result.experiment_config_identity及保存配置/请求轨迹区分实验；合法Thinking/检索变更不改变共同评分身份；缺省OFF不重写历史，未知Thinking不冒认Max|**已实现、离线已验证**|
|Draft与恢复|当前有效Draft可在主动新建Baseline时生效；非Max档位只供Candidate，Baseline拒绝；续跑读取源冻结配置与限额，忽略后续Draft变化；旧未知共同合同阻断新比较|**已实现、离线已验证**|
|页面迁移|Pipeline独立Baseline卡删除，Draft差异内嵌；Baseline报告及原抽屉使用保存Run；无Run无假快照；历史未知/Corpus对象/保存的实验Thinking均正确展示|**已实现、离线已验证**|
|Golden 0.7|50题逐题、全局和整套只读审查；没有足够证据认定当前明确Golden事实错误，分类登记10项实现/覆盖/范围问题|**只读审查完成；待 Judge 讨论**|
|Judge/11 Gate|核心Prompt、判分、公式/阈值及动态安全分母代码AST保持；Baseline Gate FAIL可Agent，Candidate仍11/11＋原完整资格|**保护已验证；正式修复待 Judge 讨论**|
|D与后续运行|不新增D组合算法/推荐/发布，不启动付费试验|**留待后续阶段**|

## 2. 关键实现说明

Query Decompose与Rewrite/MultiQuery分开：模型仅产生检索意图，不当事实；原查询始终检索，每个子查询携完整原题及型号/否定/安全条件。去重、最多3项、新型号/数值约束、可证明的显式权限相反冲突受控记录；这不声称离线程序能证明所有自然语言意图语义正确。最终回答只读真实Final。与其他既有扩展合用仍各自有界，没有递归扩展。

上下文容量使用官方V4 Tokenizer归档SHA `e7310d1dafe0a86d8a5629fe78a7c763760f651db9b8682718a1781dcd6fe495`，只加载JSON，禁止执行远程Python；缺损显式阻断ON，OFF不加载。计数对应实际generation_context，区别于整个Chat模板和Provider实际账单Usage。349个真实Parent正文最大839 token、最大6个正文总和3799，最低8192为当前TopK留足空间，非人为极低截断。任何完整块被排除都不能证明安全证据完整，因此停止生成并明确容量不足；不按字符割正文、不伪称裁剪Parent完整。

新技术输出上限answer/Judge65536、Agent32768、query16384，为Thinking＋最终输出留空间，历史限额保持。没有恢复人民币硬预算。旧价格配置仅用于带版本、日期和可用性状态的估算，未重新确认当前账单价格，未知费用不当零；真实费用、实际延迟和网关兼容性仍需授权后验证。

共同身份与独立实验身份分开：同一合法Candidate Thinking/TopK等Diff不要求重新评测Baseline。Golden/Judge/Corpus/V2或共同模型改变必须建立新边界。已知历史Run为V1＋Abstention＋旧模型别名、Thinking未知，不能转换为新Max成绩。请求返回模型/时间已保存；无法获得的服务端具体修订不推断。

## 3. 数据和受保护代码

核查正式Golden `GD-20261027070931`、Corpus `CORPUS-38c90d5628b68c76d53e`、Index `IDX-ee5bb4977dcf28f8e2f8`、试运行 `EVAL-20261027122116244939` 均匹配本地记录。原SQLite共2个Run、99条Case；未写库，未创建新正式Run。

[保护结果](round0/protection_result.json)：实施前后原DB、Corpus状态、.env、活动Index共20个文件SHA一致。冻结50题及内容/审核绑定50/50一致；77条规范源记录、4份PDF、所有Manifest产物哈希一致。Embedding/Rerank/MinerU/Chunk/Index未重建。

以下AST与实施基点一致：BUSINESS_JUDGE_PROMPT、VERSIONS、validate_business_judgment、score_execution、_score_business、summarize_evaluation_cases、gate_details、GATE_DEFINITIONS、Gate/Regression/Qualification/Overall函数、GENERATION_BOUNDARY/EXPRESSION。只有新默认选择、任务配置/采集、身份和指定UI改变，未借Max修补Judge。

## 4. 测试与视觉

后端相关验收：**运行205项：204通过、1项既有跳过**。含38个本轮配置/身份/API/Thinking/拆解/Token专项与PaidRun、现有Generation/Optimization/Identity/Evaluation/恢复/HTTP错误、模型服务及Judge传输合同。所有测试在导入前隔离DB/Corpus/env，并阻断urlopen和socket连接；Mock调用不等于真实Provider验收。

前端：**49文件、287测试通过**；新增专项9项包括保存/恢复、Draft差异、无Run、未知历史Thinking、Corpus三种历史形态、独立实验Thinking。最后一次保存的实验Thinking优先级修正后，专项9项及正式构建再次通过。`npm run build`包含TypeScript项目检查与Vite构建；Python compileall、git diff --check通过。现有act环境提示和chunk体积建议没有成为失败。

实际浏览器离线Fixture验收：1440×1000与390×844，Pipeline/报告/原抽屉；桌面Drawer800px、小屏390px，未发现横向溢出。所有数据明确Fixture，无后端与Provider调用。系统深色偏好下项目仍采用原有浅色调；仓库没有独立深色主题，本轮未扩展整站主题，不能声称深色主题验收通过。用户提到的两张截图未附于文本，不能声称逐图对齐。

全量离线结果、修改前后失败对照和重跑说明见下一节。旧运行实际成绩不因测试代码迁移而改变。

## 5. 全量离线与历史失败归因

全量原测试体系使用相同真实资产的隔离副本，在修改前与修改后分别执行；重持久化故障矩阵未删减。[逐项对照与最终补测](round0/full_suite_comparison.json)保留原始数据：

|执行|测试数|FAIL|ERROR|跳过|解释|
|---|---:|---:|---:|---:|---|
|修改前2a0f99c|972|10|15|38|25个既有失败事件|
|中间实现（最后修复前已导入代码）|1003|17|77|38|原25事件重现，另69事件来自下述根因|
|最终相关补测|205|0|0|1|新功能、身份、请求、现有相关合同|
|最终独立预检补测|23|0|0|0|新建与恢复独立、配置防篡改、API等|
|最终完整矩阵/RPC补测|9|0|0|0|含38×50故障组合与第二轮隔离|

69个新增事件分别归因：64个由新建抽象Runtime遗漏共同身份触发（不是旧Run回填问题）；1个续跑信任被篡改配置而未验实验哈希；1个旧断言要求进程默认值变化废弃冻结续跑；3个旧Thinking/Token/V1预期。前两项修复生产根因：所有新Run记录共同身份，配置哈希在创建、进度、完成和恢复/当前身份检查中保持；新建与续跑资格分开预检。后三类测试按已授权合同迁移。上述补测均通过，覆盖了已识别新增问题。最终修复后没有再启动第三次全量，因此仍明确`full_suite_green=false`；不能把历史25事件说成已修好或将中间全量数值冒充最终全绿。

补充独立复核已确认：coverage incomplete的50题Fixture E2E错误在修改前后相同；Resilience/V14/Q38/Negative选中51项在修改前后均5失败/1错误。旧测试对无Thinking、Temperature有效、Judge32768、默认V1的假设已按本轮明确新合同更新，相关模块补充29项通过。新API身份状态、历史对象渲染和Stream残片隐私问题均先复现后修复。

首次临时基点checkout缺backend/documents导致的导入错误不作为历史业务失败证据；已补齐相同资产目录后重新运行。已有失败主要涉及旧业务/Golden/恢复Fixture与断言，逐项ID见JSON；相同后台质量测试在临时目录清理后访问SQLite的异常也已记录，未混入正式数据。没有为了全绿改Golden/Judge/Gate规则。

## 6. 正式文档与待讨论问题

- [非Judge冻结决策](ROUND0_FROZEN_DECISIONS_20261028.md)
- [朋友Pipeline对标](ROUND0_FRIEND_PIPELINE_ALIGNMENT_20261028.md)
- [Golden 0.7审查及50题表](ROUND0_GOLDEN_CONTRACT_AUDIT_20261028.md)
- [唯一正式SPEC](RAG_SELF_EVOLUTION_SPEC.md)及SPEC_CHANGELOG，README/ARCHITECTURE同步。

**待 Judge 讨论**：正式Judge未直接消费完整business_requirements；安全负向分母受评分产物severity动态影响；安全与注入各1题的覆盖限制；条件/辅助/等价/OR及额外危险操作；Q22源内边界、Q25带电措辞、Q36局部30秒必答范围等有依据争议。第4轮Gate议题归属已明确，其余六轮分工仅作建议，未冒充用户确认。

**留待后续阶段**：Judge集中修复、必要Golden Revision/厂家澄清、明确授权后的正式新Baseline、Agent/Sandbox和D综合回归、人工推荐确认与发布。Max的质量或延迟收益没有真实新实验结论。

## 7. 最小真实API验收清单（未执行）

只有另行获得明确授权后才能执行，不涉及完整50题或正式Run：

1. GET `/models`：检查实际账户/网关公开模型、上下文/输出/支持effort元数据；不能把公开文档当账户验收。
2. 1次Max流式生成：真实Canonical单例上下文，核final content完整、reasoning不泄漏、Usage/响应模型/请求时间及首字和总耗时。
3. 1次OFF流式Candidate：disabled无effort、Temperature按OFF规范、实际配置及请求Diff独立保存，Judge仍Max。
4. 1次Low辅助查询：验证Low被接口接受，不引入额外事实。
5. 1次High JSON拆解：最多3项与原问题约束，真实子检索与来源合并，验证高档JSON及限额兼容。
6. 1次Max JSON Judge：验证响应合同、Usage、超时/length等错误边界；仅传输验收，不修Judge规则。

合计5次Completion＋1次模型元数据读取，均为建议的最小单例验收；本轮实际0次。异常注入/断点/length尽量继续Mock，避免人为制造重复费用或Unknown；账单与估算需核对，不能将Mock费用当扣费。

## 8. 工作区与运行进程

在隔离工作区开发和测试，完成后仅同步本轮已提交路径。原先修改的scripts/verify_self_evolution.py及未跟踪审计材料保持原样。本地既有8010后端核实未使用--reload；本轮不重启它、不运行启动脚本（启动脚本会检查/构建Index），因此正在运行的服务仍是原加载版本。代码在下一次由用户安排的后端重启后生效；本轮没有冒充运行态已切到Max。

## 9. 已修改文件

完整逐文件清单见 [changed_files.json](round0/changed_files.json)。主要实现归属：

- config/providers/ai_service：模型、任务Thinking、V2、真实请求及上下文能力集成。
- policy/retrieval/context_budget/optimization：合法值、拆解检索/Trace、官方Tokenizer预算和Agent受控识别。
- evaluation/evaluation_contract/governance/main/paid_run：默认/Draft/恢复、共同与实验身份、API历史有效性、技术Token上限。
- PipelineFields/SettingsPage/EvaluationPage/styles：三个入口、Draft差异与报告/抽屉归属、局部小屏布局。
- 相关测试、requirements、.env.example、官方Tokenizer及来源说明、离线验收脚本、SPEC/变更记录/README/架构、三份决策审计文档与审计支持证据。

未修改原scripts/verify_self_evolution.py、正式数据库/冻结JSON、知识库产物、Judge Prompt/评分核心或Gate公式。
