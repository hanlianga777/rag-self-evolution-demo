## 2026-10-14 — Mini Business V2及限定Profile委托审核

- Mini显式business_v2复用Topic/Group/产品配额与十维审计；通用业务选材避免封底/声明驱动机械题，专项无支持在新Plan记录真实Ordinary fallback，旧冻结Plan/题目不改名；Medium及知识资产不变。
- 所有者委托能力通用于合法Mini20/Medium50，Mini必须有本次Run及Profile明确授权；逐题PDF、机器质量与风险校验不变。UI准确区分委托AI与真人。
- 本次付费治理使用新账本及更低有效预算，不运行Baseline/Agent/Candidate/Sandbox。真实结果见[Mini20收口验收](MINI20_QUALITY_CLOSURE_ACCEPTANCE.md)。

- Mini20收口补充：删除安全拒答修订中以五个词代替危险语义的预览门槛；真实Probe负向子类及QC仍须重跑并保留阻断。自然高压水枪危险请求、语义不匹配阻断及负向Evidence禁令有隔离回归验证。
- 负向Business Audit补齐expected_response及显式、当前同产品的必要审计上下文（默认不扩张、不发送整库）；修复单Anchor缺禁令造成的审计盲区，原十维标准不变。重审请求被自动审批拒绝而未执行；保留旧失败/独立PDF核验，等待具体载荷外发授权。正向Evidence范围不扩张，无知识重建。
- 本轮实际Hard/Probe/QC20通过、Business19/20；独立建议19通过1待复核，正式批准0、Snapshot0；Q18必要补审外发被自动审批拒绝且未执行，等待具体载荷授权。

## 2026-10-14 — 证据驱动诊断、单一干预与实验重新开始

- 评估四维组织、原11 Gate/Overall/Regression阈值保持；主张结果分正式阻断与结构化确证/待审/争议，新Judge/Matcher/Policy版本见SPEC文首，旧成绩不重算。
- Agent及D保存前验证Trace、方向及必要联动；允许候选不足，不强凑ABC。Monitoring人工判定不替代技术Trace。
- 生成输入共享文档身份、Chunk引用/范围/全文，明确操作边界；仅离线输入验证，效果待后续授权。
- 用户授权事务清空旧Golden/实验/审批/Monitoring/Seed；当前参数保存为未评测未发布bootstrap，Knowledge不重建。保留一次SQLite备份及外部审计。
- 依赖闭包对象保留（非引用实验/评测各50、活动/引用豁免）及历史分页≤50；关联Q02启动守卫识别Corpus绑定的清理标记。
- 验收与Mini20前置条件见[RAG机制修复与清理验收](RAG_DIAGNOSTIC_RESET_ACCEPTANCE.md)。本轮Provider0，不创建或运行Mini。

## 2026-10-14 — Optimization Agent已证实上下文超限的无损去重

- 真实HTTP400返回messages=1,106,742，最大上下文1,048,576；已确认消息超限，旧粗估不能代表实际Tokenizer。
- 最小修复只从发给Agent的行中去掉与result完全相同的result_json字符串；所有结构化判断依据及13题/7目标保留，算法、Search Space、评分/身份/历史不动。
- 真实请求隔离重建由5,774,935降至2,947,105字节；逐字段证明仅去掉冗余序列化字段。未真实调用Provider/Sandbox。
- 详见[验收报告](AGENT_CONTEXT_LIMIT_ACCEPTANCE.md)。

## 2026-10-14 — Optimization Agent HTTP错误可诊断化

- 隔离重建失败请求，SHA与历史一致；5.77MB请求体、约93.6万字符Token估算，仅为观测，缺旧400正文不能认定确切Provider拒绝原因。
- Agent增加调用前请求摘要及本地格式/参数校验；共用HTTP错误保存脱敏正文、状态/Provider码/详情，Agent记录失败阶段/重试判断并显示完整错误。
- 未改Agent策略、13题读取/7个Confirmed目标、Search Space、Baseline/Golden/Judge/Matcher/Policy/Gate/Regression、费用及累计时间逻辑。没有真实Provider或Sandbox，无历史回填。
- 详见[离线验收](AGENT_HTTP400_ACCEPTANCE.md)。

## 2026-10-13 — Q38 Judge结构输出与Resume计数修复

- 真实响应复现定位behavior_evidence数组与原字符串合同冲突；补齐JSON形状示例、单个连续引文类型要求，保留严格字段校验及全部评分语义。
- 输出错误保留具体语法/缺字段/合同原因及原始响应，supported_abstention缺少依据显示精确字段路径，不自动填充。
- 显式Resume子Run独立六次结构失败窗口，同Run恢复继续累计，继承原尝试记录不删除。请求级参数、Evaluation Identity、费用/时长逻辑不变。
- 详见[Q38验收报告](Q38_JUDGE_ACCEPTANCE.md)。

## 2026-10-13 — Baseline/Sandbox运行窗口停止入口

- 增加幂等停止接口和窗口按钮，持久化用户停止请求，共用执行器在请求边界/退避期响应。当前请求结束后保存断点，不强杀共享服务，不启动后续调用。
- Partial保留真实完成题数、生成/评分断点、Usage及审计；停止后不自动恢复，可明确续跑新Run。停止接口受可信Origin保护，旧已结束Run不变。
- 无Provider调用或真实停止操作；详见[验收](EVALUATION_STOP_ACCEPTANCE.md)。

## 2026-10-13 — Baseline/Sandbox自动恢复与费用统计化

- 共用执行器持久化生成/评分断点与重试审计，网络/暂时服务错误自动退避，Judge格式/字段异常只补Judge；六次不合格结构后保留断点停止，账户/身份/持久化错误不盲目重试。
- 新授权持久化、SQLite并发领取及PID/线程归属保护，后台监控恢复真正中断的任务，不误接管存活Worker或自动激活旧历史Run。已完成Case不重复调用，Case/BadCase原子保存。
- 评测PaidRun改为只统计，费用/余额/价格/Usage未知不阻断，未知费用不当0；请求参数与评测身份不变。未发现后端整批时长上限；移除Baseline前端300次轮询限制，刷新从DB定位实际任务。
- Judge评分/Matcher/Gate/Regression/算法/Golden/Corpus与历史成绩不变。仅离线故障注入，无真实Provider。详见[中文验收](BASELINE_AUTORECOVERY_ACCEPTANCE.md)。

## 2026-10-13 — 五类现象与四方向真实列表闭环

- 新增只读diagnosis-view-v1，保存标签/来源/Trace/独立可信度可追溯；缺证据的噪声/拒答/误伤不硬推断，安全失守独立保留，问答与Judge耗时分开。
- Baseline/Agent共享组合筛选、唯一题号列表与详情；Agent输入实际加入诊断视图与风险背景。目标仍限可信四方向，参数仍由真实假设及Search Space约束。
- 候选目标/策略可查看原证据，Sandbox与Regression按保存题号读取真实两侧结果，未运行B/C无模拟成绩。压缩根因大卡片，保留上一轮UI体系/Drawer/版本守卫。
- 评分语义、Evaluation Identity及历史结果不变；没有Provider、评测或治理执行。详见[中文验收](BAD_CASE_CLASSIFICATION_ACCEPTANCE.md)。

## 2026-10-13 — 评测规则治理与两个工作台

- B类规则升级：Judge v3.2、Matcher v4、Policy v1.3；新增结构化正确拒答、连续多片段定位、题外冲突范围及治理争议记录。负向题另存政策行为有效值与原Judge矛盾依据；已定位的无来源技术操作不能由主拒答豁免，Gate汇总/逐题贡献采用同一有效值，旧记录沿用保存字段。旧规则/成绩/资格不迁移，50题旧Judge离线预览不作为真实评测。
- A类展示：只改Baseline/Agent专属组件与样式，摘要按Tab分层，症状/根因/可信度独立，六阶段工作台/ABC齐列及保存的Regression明细。既有Drawer和设计Token复用。
- 11 Gate及Regression阈值、四根因、Agent/SearchSpace/Winner/Gate2/Production保持；旧B/C因版本升级只读，后续完整新Baseline/新实验须另行付费授权。本轮Provider0，不跑任何正式评测或审批。详见[中文A–P验收报告](EVALUATION_GOVERNANCE_WORKBENCH_ACCEPTANCE.md)。

## 2026-10-13 连续恢复授权

保留全部历史请求及未知预约，允许显式连续运行中的缺失网络请求最多一次恢复；同题第二次失败停止，解析及身份/预算错误不重试。新增受控执行脚本复用26题及Q27回答，合法自动衔接第一轮Agent/ABC；评分、Gate及冻结身份不变。真实执行推进至42/50；Q38仅对保存响应作证据字段格式回放，Q43两次网络失败后停止，详见[验收报告](BASELINE_CONTINUOUS_ACCEPTANCE.md)。

## 2026-10-12 — Medium Golden 22题离线集中修订

- 新工作集覆盖审计17轻修、4实修、1替换；28题内容保持，原冻结Snapshot/成绩/实验/Corpus不改写。Q37修正Anchor主题，Q45新高风险标注，Q28替换待厂商确认的歧义流程。
- Q06/Q39保存响应复现Markdown加粗定位缺陷，最小格式清理保留安全守卫；评测语义版本不升级，不回填历史。
- Q02正确PDF答案因正式索引漏采而阻断Hard Validation；隔离文本预览不冒充重建索引。带阻断离线工作集禁止启动付费质量恢复；Probe/QC和Human Gate1均待授权。
- 详见[完整修订报告](GOLDEN_MEDIUM_22_REVISION.md)。不修改架构图源、UI、Gate、Regression或Agent策略。

## 2026-10-12 — 第二轮Agent根因合同对齐

- 真实Trace 8的B将三个confirmed Generation目标标为Retrieval，被现有校验拒绝；原始响应已保存，非网络/JSON故障。
- Prompt目标映射显式提供根因/可信度/依据，并区分根因与参数干预。保留根因校验，补齐拒绝字段审计；历史反馈省略执行checkpoint，数据库不删改。
- 保存响应离线复现与跨环节参数回归；不调用Provider、不生成真实Round2、不改第一轮或Sandbox预算。见[第二轮失败报告](AGENT_ROUND2_FAILURE_AUDIT.md)。

## 2026-10-12 — Candidate C技术失败审计

- 确认C保存43题及第44题生成检查点；既有续跑在真实库隔离副本验证跳过43题，仅补7次Judge、6次Generation，保留A/B与原Run。
- 修复执行器丢失Parser异常具体原因和异常携带原始响应的审计缺口；不修改Parser合同或评测语义，不补造历史响应。详见[C异常报告](CANDIDATE_C_FAILURE_AUDIT.md)。

## 2026-10-12 — Candidate Sandbox 检查点与批量暂停

- 复用 Baseline 子Run恢复，Candidate预约与Run关联原子持久化；同身份人工续跑跳过完成题、复用生成成功答案，仅补Judge。
- 每次启动占额、失败不退款、D预留不变；预算/身份拒绝整体回滚。重启保留检查点及Run关联。
- 未完整结束暂停A/B/C串行队列；再次人工点击仅启动未启动项，失败项须单独费用确认续跑。仅修改按钮行为/文字，视觉不变。
- Judge/Matcher/Golden/Gate/Regression/Search Space/Agent策略及评测语义版本不变；历史成绩不回填。

# Baseline超时与检查点保护（2026-10-12）

默认DeepSeek请求等待240秒，未改性能Gate或Judge语义版本。生成检查点/逐题结果/失败阶段和Usage保存；原运行只读，手动同身份续跑建立子Run，跳过完成题和已生成答案，事务阻断身份混用/重复请求。原API支持resume_source_id/fresh，既有按钮在最新中断Baseline时选择续跑。验收及旧超时无法追溯项见[BASELINE_STABILITY](BASELINE_STABILITY.md)。

# V1.2.1 Parser兼容修复（2026-10-12）

behavior_pass=true时允许behavior_evidence缺省并规范化为空串；false时必须有实际答案中的非空失败片段，否则拒绝解析。保留原始Provider响应审计，不改评分规则、版本身份、Matcher或主张合同。保存Q06离线复现及Q35/Q38安全回归，未调用Provider或重评。详见[JUDGE_PARSER_COMPATIBILITY](JUDGE_PARSER_COMPATIBILITY.md)。

# V1.2.1 — Judge技术操作语义与结构化一致性（2026-10-11）

明确changes_operation不因保守中止使用而为true；新增operation_basis，交叉核验kind/effect/boolean/来源状态，未知或矛盾待核实。来源引用、安全和评分门槛不变，不用reason关键词自动判断。版本judge-v3.1-claims/evidence-v3-scoped/v1.2.1-claim-consistency；历史身份和结果保留。保存Q06/Q38真实响应离线复现，Q11/Q35/具体操作回归。未调用Provider、未重评、未重启服务。详见[EVALUATION_POLICY_V121](EVALUATION_POLICY_V121.md)。

## 2026-10-11 — Baseline16题审计后的通用评测修复

- 升级judge-v3-claims / evidence-v3-scoped / v1.2-grounded-diagnosis；HTML清理先于分句，区分未解决冲突与有来源的适用范围差异。
- 单Judge结构化主张审计，合理安全建议不等于放行具体操作；关键方向错误与Negative后续指导独立检查，可信根因须有可定位依据。
- 旧成绩/身份不迁移；Gate、Regression、Golden、Corpus和前端不变。离线验收见 EVALUATION_POLICY_V12.md；真实Provider未执行。

## 2026-10-11 — 统一评测、可信Agent与面客收口

- SPEC文首新增当前合同，旧评测/目标字段/D规则标记Superseded；冻结Gate/Search Space/预算和人工治理不变。
- 上下文Judge、Parent证据充分性与评测身份；独立答案回放；新目标/附带修复统计和可信诊断。
- 程序Winner、单次授权LLM D、发布身份及回滚兼容；Baseline/Agent面客层级与历史Drawer。
- 既有唯一图源同步统一评测/预算/D边界。验收见 SELF_EVOLUTION_CLOSURE.md。真实Provider未执行。

# RAG Self-Evolution SPEC ChangeLog

本文件是产品规格变更的追加式历史记录。当前有效产品规则仅见 [V1.4 SPEC](RAG_SELF_EVOLUTION_SPEC.md)；以下旧版本条目不是并行生效规则。不得覆盖或重写既有条目。

## 2026-10-09 — Baseline / Agent 高保真恢复

- 用户明确覆盖旧 UI 收口：恢复阶段条、紧凑 Baseline 报告、证据案例、实验概览/计划、完整六项 A/B/C、六行 Sandbox、条件 D 与人工版本决策。
- 共享 Operation 复用单候选 API 串行执行；预约事务闭合当前身份，重启中断不自动启动剩余项。未来初步归因按安全/证据观察，历史结果不改写。
- 11 Gate、12预算/D预留、Search Space、Regression/D晋升、人工批准与发布保持冻结。无真实 Provider 调用或业务数据变更。
- 验证、九图映射、保护证据与演示脚本见 `BASELINE_AGENT_RESTORATION.md`。

## 候选池与中文业务导入收口（2026-10-08）

- 默认浏览合并一行三质量Chip与业务用例/创建操作，后端筛选、分页、懒详情和SWR保留；组建简化为数量与操作，配额/覆盖按需展开。选题按Corpus会话暂存，返回浏览保留。
- 智能补齐无Provider调用，只用已有可用候选、真实证据及当前Anchor最大匹配，优先保留已选；缺口、无效候选与待治理状态明确展示，不降低正式创建、质量或人工Gate要求。
- 默认中文四列XLSX与独立示例/说明；经验仅待核验材料，进入待分类候选。旧14列CSV/XLSX校验继续支持。全高导入Drawer改紧凑预览Dialog，显式部分导入、行号错误、摘要绑定及事务回执幂等。
- 活跃查询按修订/复制来源谱系保留当前版本，物理历史不删除。既有Medium、Full、Probe/QC、人工审批和Snapshot受保护；并发用户审批独立报告，不归为代理修改。
- 架构关系不变，唯一图源与同源导出不重画。验收见[候选池与业务导入验收](CANDIDATE_POOL_IMPORT_VERIFICATION.md)。

## Medium V2 集中质量与UI收口（2026-10-08）

- 全50题先审查，再执行用户明确授权的39题一轮版本化Revision；11题复用，保留Evidence、20/10/20、九Topic、Full/Legacy及人工Gate。真实检查不通过仍待处理，不自动接受风险。
- 修复业务Revision应用重校验丢失difficulty/expected_response导致预览身份不一致；校验业务难度和预期回复类型。QC可读取预期回复作为样本数据，不覆盖冻结行为标准。
- 增加只读本地数据集自然度/多样性诊断，结合已有业务审计展示原因、建议、前后差异，不新增硬Gate或页面Provider调用。
- Golden删除旧Full提示及两个动作菜单：新建为次级按钮；历史版本内保留运行审计和导出。候选池改三质量Chip/五列正常字重；剩余动作菜单使用原生Popover，Coverage技术审计下沉折叠区。
- 真实结果、调用计量限制、保护校验、截图和测试见[集中收口验收](MEDIUM_V2_POLISH_VERIFICATION.md)。架构关系未改变，唯一图源及导出文件不重画。

## Golden Dataset V2 Medium 业务题与候选池（2026-10-08）

- 新增独立business_v2策略，复用现有Knowledge九Topic材料与身份，Medium保持20/10/20；角色、业务场景、用户意图与难度目标持久化，不回填Full历史记录。
- Negative业务分类映射到既有Subtype/Expected Behavior；持久化材料Anchor用于Coverage，真实查询Embedding结果作为观察，Anchor不是答案Evidence。现有Hard Validation、Probe全文检查、QC与人工Gate不降低。
- 新业务工作集必须通过十维Business Quality Audit才能机器合格；缺失、失败、过期审计均阻断。失败Slot沿用版本化Revision，保留业务元数据，并仅重跑该Slot；修订漏场景/意图时只从当前问题补齐元数据一次，按新内容身份重验该题，不生成新问题；有限预算与实际Provider Usage记录见当前SPEC和本轮验收。
- Candidate Pool默认浏览：候选/可用/待治理摘要，来源/评测组/质量/搜索，五列列表；点击创建Golden才进入Profile配额和Slot匹配组建模式。保留30条分页、SWR、懒加载、导入、详情及800px Drawer；机器合格、人工通过与待治理分别标识，不把机器检查显示为人工批准；已执行未过的Probe/QC显示通过计数及待处理。
- 本轮真实运行、逐题审阅、保护核验与未解风险见[Medium V2验收](MEDIUM_V2_VERIFICATION.md)及[完整审阅](../backend/reports/golden_dataset_v2_medium_review.md)。不自动批准、冻结、Baseline或Agent。

## Golden Dataset 冻结阻塞修复（2026-10-08）

- 修复Full批次SQLite缓存溢写后，冻结写事务另开连接读取Snapshot/题目导致的自锁；所有写入后读取复用事务连接/已读取题目，保留原事务回滚与Run级幂等。
- Pending返回具体题目与条件，数据库失败返回带CORS的503结构化错误；前端同步防重复点击，继续刷新真实Snapshot，区分提交失败与已完成但刷新失败。
- 本轮只读核对当前100题与用户已保存13题批准；不执行正式确认、冻结、Provider、Baseline或Agent。隔离测试与真实数据库状态见[冻结修复验收](GOLDEN_FREEZE_FIX_VERIFICATION.md)。Profile、质量标准与Gate业务规则不变。

## Phase 1 最终冻结合同同步（2026-10-08）

- 唯一Drawer宽度来自当前Golden单题详情800px，删除Standard/Wide尺寸体系；Search Space/Coverage适配共享宽度，保持全高及正文滚动。
- SPEC文首明确当前有效合同，纠正当前正文20/49/98和旧Drawer冲突；历史Run、Snapshot和旧说明保留Historical身份。
- README/Current Demo Truth/平台架构说明同步真实Current与Legacy边界；业务/技术图从概览同一SVG及Computed Style导出，旧HTML标记Historical。
- 新增AGENTS.md，要求涉及产品合同的代码、SPEC、Changelog、相关文档及架构同Commit同步；纯Bug允许No SPEC Change。
- Q68仅一次自然改写及冻结预算内校验，失败不应用；实际运行结果见本轮验收。其他题不改写，未执行人工Gate、冻结、Baseline、Agent或发布。

## Phase 1 Knowledge Pipeline（2026-10-05）

- 用户批准真实 MinerU VLM / Parent-Child / text-embedding-v4 / qwen3-rerank 升级，以及项目概览、知识库两个入口重构；旧技术限制由唯一 SPEC 新 Phase 1 节覆盖，保留原历史正文。
- 复用现有索引激活、Coverage、Golden、治理流程及 SQLite JSON 字段。新增版本身份、产物校验、Legacy 索引绑定、只读 Cluster / Slot API；其他六页与人工 Gate 规则保持。
- 真实 Provider 配置、测试结果和仍阻塞的运行阶段见 [Phase 1 验收](PHASE1_KNOWLEDGE_VERIFICATION.md)，不沿用历史测试数量。

## V1.4 最终集成闭环追加记录（2026-10-02）

- 一次完整修复 `8c674c6` 关闭整体审查五项 Important：事实 Validator→Probe 判定、质量晚到结果身份保存、Corpus 最终提交锁、实际当前 Preview UI、persisted Why 字段。限定复审 Spec Approved / Quality Approved with Minor，无未解决 Critical/Important。
- 新运行 296 后端、121 前端、构建通过；Chromium 四个要求尺寸 208 检查 / 149 截图，52 必需 Drawer、ABC/footer/Why/迟到 Preview 具名断言。54 Test ID、需求 ID、唯一 SPEC 历史存档保持。
- 保留 M3 局部提示：同一修订草案换材重新生成成功后关闭可能多一次误提示，仅关闭 UI，不丢已存草案或改原题；不写成所有发现全闭。
- 25 张真实表完整内容与四个 active SHA 不变；备份可读。4 PDF/157 页的备份全文 Staging 已验证，未切 active、未重启旧服务、未执行真实 Provider/Gate/发布。详细证据与三条手动验证见 [实施验收](V1_4_IMPLEMENTATION_VERIFICATION.md)。下面检查点数字和当时状态作为历史保留。

## V1.4 实施追加记录（2026-10-02）

- 用户在文档/图交付后明确批准完整业务代码实施，原桌面任务书作为输入依据而非改写对象；需求 ID 与 54 个 Test ID 保留，原 V1.3 历史正文不改。
- P0 统一对象身份、Monitoring 幂等 Confirm/首轮、A/B/C 全批原子保存；Golden V2 Planner、Group × Construction、统一 Validator、独立 Plan/Slot 最大匹配已实施。
- 双层 Probe、原解析页全文 bundle、失败与零召回区分、版本化价格和真实 TTFT 已实施；截至本检查点 284 项阶段隔离后端测试及阶段复审通过。UI 与整合生命周期已通过 286 项隔离后端、105 项前端、构建和 Chromium 四尺寸 187 检查，阶段复审已通过，最终整体审查中；54 ID 具名断言和最终证据见 [实施验收](V1_4_IMPLEMENTATION_VERIFICATION.md)。
- 用户已关闭 `[OPEN-QC-P0]`：机器 QC P0 可明确人工理由接受，确定性证据错误、Fake Negative、数量错误及执行失败不可豁免。旧条目保留当时未决状态。
- 新增 Preview 路由已注册，旧客户端省略 plan_id 由服务端创建当前 Plan，不跳过校验。保留既有 API、Gate、Regression、12 次预算、D 失败保留赢家及 Production 独立来源。
- 真实业务表和冻结内容不改，全文只在备份 Staging 验证，旧服务没有重启；不运行真实 Provider/Golden/Evaluation/发布。保留两张 V1.4 目标图及 HTML/PNG 路径，不把离线通过称为真实数据重跑。

## V1.4 — Golden Engine V2 & Identity-Bound Evolution（2026-09-30）

- 来源：`RAG_SELF_EVOLUTION_CODEX_MASTER_PROMPT_20260930.md` 及用户确认的文档同步范围；唯一目标规格升为 V1.4，旧规则在 SPEC 文末标为 Superseded。
- 纳入 P0-01–04、GV2-01–05、COST-01、UI-01、SAFE-01、QA-01：当前对象绑定、Monitoring 首轮、动态 Coverage/Slot、双维度构造、统一校验、双层 Probe、原解析全文与原子 bundle、Usage/Cost、逐页 UI、兼容及离线验收矩阵。
- Search Space、11 Hard Gates、固定 Regression、12 次 Sandbox 预算、条件 D 和 Gate 1/2/3 人工边界未变；QC P0 接受范围的材料冲突记录为 `[OPEN-QC-P0]`，本次不改变现有行为。
- README、平台架构说明同步；业务架构与技术架构从头重绘为 V1.4 目标架构，重新生成 HTML/内嵌 SVG 与 PNG，不复用旧布局。
- **交付类型：仅文档与图。** 没有业务代码、API、数据或索引迁移，没有真实 Provider/Golden/Baseline/Agent/Sandbox/发布重跑。目标规格同步不代表 V1.4 已实现或已验收；当前静态差异记录于 SPEC 第 3 节，Phase 1 报告保留历史事实。

## V1.3 — Friend-Aligned Evaluation & Experiment UX（2026-09-28）

- 2026-09-28 UI 收口实现：八个现有 Hash 工作区按 Lifecycle 排列；Pipeline 的只读配置与 Search Space 直接读取现有冻结策略；Baseline、Tuning、Release 首屏显示已保存审计结论，长证据保留在详情中。
- Before / After 仅按已持久化 Baseline、Candidate、Production Version ID 解析配置；发布后默认 Previous Production 对 Current Production，发布前默认 Baseline 对 Qualified Candidate。固定 Bad Case 来自当前 Baseline；历史 Evaluation 与主动实时预览分别标注来源。此条记录实现，不改变 Gate、D 或发布规则。
- 唯一当前产品规则；V1.2 与 V1.1 均为 Superseded / Historical。
- Golden Profile 增加 Mini / Medium / Full，配额按冻结 Profile 计算；Hard Validation 与三类 Probe 展示真实诊断记录。
- Baseline 以冻结配置、11 Gate 和逐题结果组织报告及诊断；Tuning 展示同一条真实 A/B/C → Sandbox → Gate 2 → D → Gate 3 主线。
- 八页导航和问答试验命名统一；真实 `demo.db` 与 Provider 主链不参与本轮开发验证。

## V0.2 — Core Lifecycle

- **Date:** 2026-09-21
- **Status:** Confirmed

### Confirmed Decisions

- 产品定位为评测驱动的企业 RAG 持续优化、验证、发布与监控平台；Evaluation 负责发现 Bad Case，Optimization Agent 从已识别 Bad Case 开始工作。
- 冻结一级信息架构：概览、知识库、测试集治理、评测、进化实验室、版本与发布、问答验证；设置独立。
- Knowledge Base 与 Golden Dataset 分离；历史 40 题保留为 Legacy / Historical Data，不能直接成为新版正式 Golden Snapshot。
- 冻结 Coverage-Aware Golden Generation、Positive / Ablation / Negative 题型、Mini / Medium / Full 默认 Profile，以及 Candidate → Hard Validation → Probe → QC → Human Review → Approved Golden → Golden Snapshot 治理链路。
- 冻结 Baseline、四维 Evaluation、Question-Type-Aware Evaluation、Bad Case Detection、Observed-Evidence-Driven Agent Diagnosis、可解释 Candidate A/B/C 与条件 Composite D。
- 冻结 Sandbox、独立 Regression、Recommendation、Human Approval、Release Gate、Version Snapshot、Production Version 保留与 Rollback。
- V1 使用 Direct Release，不伪造 Canary / Gray Release；采用轻量 Monitoring，且 Monitoring Signal 必须经 Evaluation 才能进入下一轮优化。
- 冻结完整 Self-Evolution Lifecycle 与问答验证模块职责。

### OPEN / TBD Summary

Pipeline Search Space、参数 Range、Agent 修改边界与迭代限制、各题型与各 Gate 阈值、Overall Score 权重、Probe 细则、QC Judge Model、Monitoring 指标与触发规则、页面字段与 Layout、Demo 数据、A/B/C 初始配置，以及各核心 Snapshot / Report Schema 均未冻结。完整清单见 [SPEC 的 OPEN / TBD 清单](RAG_SELF_EVOLUTION_SPEC.md#12-open--tbd-清单)。

### Implementation Status

Implementation NOT Authorized。Current Implementation 与 Target SPEC 的差异已接受并保留；SPEC V1.0 Frozen 前不得因此启动业务重构或 SpecKit Implementation。

## V0.3 — Optimization Agent & Search Space

- **Date:** 2026-09-22
- **Status:** Confirmed

### Changed Items

- 将 Target Baseline 的 Pipeline 默认参数、V0.3 Agent 自动 Search Space、参数依赖与明确排除项写入正式 SPEC。
- 将 A/B/C 生成、Root Cause Cluster、Candidate 去重、Sandbox 保存范围、`max_evals = 12`、停止条件、Composite D、Recommendation、Human Release Gate、Direct Release、Version Snapshot / Rollback 细化为正式决策。
- 将 Monitoring 更新为“生成待处理 Optimization Trigger → Human Confirm → Agent”的半自动闭环；不允许自动调参或自动发布。

### Confirmed Decisions

- Baseline 在一次 Optimization Run 中固定；每轮必须生成三个并列、可解释的 A/B/C Candidate，且每个 Candidate 使用服务于单一 Hypothesis 的最小必要参数集合。
- 冻结 CandidateK、TopK、MinScore、Hybrid / Alpha、Rerank、Rewrite、MultiQuery、HyDE、Metadata Filter、Alias Mapping、Prompt Strategy 的允许值与规则；Rerank TopN 及模型、Chunk、Parser / OCR、Temperature、Query Decompose、Retrieval MaxTokens 不进入自动 Search Space。
- 冻结 Root Cause 诊断、Cluster、Search Guidance、Parameter Rule Check、历史去重、Sandbox Result 最低保存项、12 次累计 Evaluation 上限、失败处理和停止条件。
- 冻结 Recommendation 的 Hard Gate 优先比较、无合格 Candidate 的 `No Qualified Candidate` 状态、条件 Composite D 的完整复验与退回最佳 A/B/C 的规则。
- 冻结 Human Release Gate、受审计的 Direct Release、发布前 Version Snapshot、人工 Rollback 与 Monitoring 人工确认触发链路。

### Closed OPEN / TBD Items

Pipeline Search Space、TopK、CandidateK、Query Rewrite、MultiQuery、HyDE、Hybrid、BM25 / Vector Weight、Min Similarity、Rerank、Rerank TopN、Metadata Filter、Alias Mapping、Prompt Optimization、Agent 每轮最大修改范围、Agent Iteration Limit、A/B/C Generation Rule、Composite D Rule。

### Remaining OPEN / TBD

Overall Score 与各题型 / Gate 阈值、Probe 细则、QC Judge Model、Monitoring 指标与 Trigger 数值、页面字段与最终 Layout、Demo 数据、A/B/C 初始实验配置、`max_evals` 的 D 计数与预算处理、有效提升判定、Candidate 去重范围、Prompt 受控变换边界、Hybrid Alpha 融合细则、MinScore 生效细则、Direct Release 验证顺序，以及各核心 Schema 的剩余字段定义仍未冻结。完整清单见 [SPEC 的 OPEN / TBD 清单](RAG_SELF_EVOLUTION_SPEC.md#12-open--tbd-清单)。

## V0.4 — Evaluation, Gate & Quality Governance

- **Date:** 2026-09-22
- **Status:** Confirmed

### Changed Items

- 将正式 Evaluation 固定为 Positive、Ablation、Negative 三组，并废弃 40/20/40 或其他新的 Overall Score 加权公式。
- 冻结 Positive、Ablation、Safety / Negative、Latency 的 11 项 Release Hard Gate 与 11 / 11 全部 PASS 规则。
- 冻结 TTFT、Token Cost、Recall@K、Precision@K、MRR 为 Candidate Comparison Metrics；它们当前不设 Hard Threshold。
- 冻结 Probe `Score ≥ 90`、QC 使用既有 DeepSeek Judge 且 `Score ≥ 85`，并保留 Human Review。
- 明确 Regression 必须验证但数值 Gate 仍未冻结；Monitoring 保留 Human Confirm 后才进入 Agent 的半自动链路。

### Confirmed Decisions

- Candidate 不能用平均分、Overall Score 或其他指标抵消任一 Hard Gate 失败；仅 11 / 11 全部 PASS 的 Candidate 可进入 Recommendation。
- Safety / Negative Hard Metrics 仅为 Safe Rejection Rate、Safety Critical Accuracy、Prompt Injection Resistance，均为 `≥ 95%`。
- Latency P50 `≤ 25s` 与 Latency P99 `≤ 60s` 为 Performance Hard Gate；TTFT 必须记录但不是当前 Release Gate。
- Token Cost、Recall@K、Precision@K、MRR 必须进入 Baseline / A / B / C / D 的比较与 Recommendation 解释，但不新增 Cost、Recall、Precision、MRR 的 Hard Gate。

### Closed OPEN / TBD Items

Positive / Ablation / Negative Evaluation Threshold、Safety Gate Threshold、Performance Gate Threshold、QC Judge Model、Release Gate Threshold。

### Remaining OPEN / TBD

Overall Score 的未来展示、Regression 数值规则、Monitoring Numeric Trigger、TTFT / Token Cost / Retrieval Metrics 的未来 Target、Probe Detailed Score Rule、Hybrid / MinScore 技术细则、Direct Release 验证顺序、Composite D 预算、有效提升、Candidate 去重、Prompt 边界、Schema、UI、Demo 数据与 A/B/C 初始配置仍未冻结。完整清单见 [SPEC 的 OPEN / TBD 清单](RAG_SELF_EVOLUTION_SPEC.md#12-open--tbd-清单)。

## V1.0 — Final SPEC Closure

- **Date:** 2026-09-22
- **Status:** Confirmed

### Changed Items

- 将 Regression、Monitoring Trigger、有效提升、Probe 评分、Hybrid Alpha、MinScore、Direct Release、Composite D 预算、Candidate 去重、Prompt Strategy、实验记录、Overall Score、TTFT、Token Cost、Retrieval Metrics、UI、Demo 数据链与 A/B/C 原则固化为当前有效规格。
- 将正式 SPEC 的遗留产品待定项全部关闭；未列出的 Report 字段、像素级 UI 与具体演示题材仅为实现表现层细节。

### Confirmed Decisions

- Regression：Safety / Critical 不允许新增失败；普通题最多新增 `1` 个失败；超出即 Failed。Qualified Candidate 必须 11 / 11 Hard Gate PASS、Regression PASS、修复至少 `1` 个目标 Bad Case，且全量 Bad Case 总数至少减少 `1` 个。
- Monitoring 满足 `1` 个 Safety Critical Bad Case 或最近 `20` 次完整可判定问答中 Bad Case `≥ 4` 时，生成 Trigger；流程始终为 `Monitoring → Optimization Trigger → Human Confirm → Optimization Agent`。
- Probe 总分 `100`，Question Quality / Golden Answer Quality / Evidence Support 分别为 `30 / 30 / 40`；Evidence 无法支撑 Golden Answer 直接 Failed。Hybrid Alpha 是归一化后 Vector 权重；MinScore 在最终 Evidence 进入 LLM Context 前执行。
- Direct Release 可跳过 Agent 搜索，但不能跳过 Sandbox、11 / 11 Gate、Regression、Snapshot、审计、Rollback 与 Human Release。D 与所有完整评测 Candidate 同样计入 `max_evals = 12`。
- Overall Score 仅可作为 `0–100` UI 展示和快速比较，绝不作为发布 Hard Gate；TTFT `≤ 5s` 仅为 Warning Target；Token Cost 仅展示比较；Recall@K / Precision@K / MRR 的 Diagnostic Target 分别为 `≥ 85% / ≥ 50% / ≥ 75%`，均不覆盖 V0.4 的 11 项 Gate。
- 实验记录的最低字段、卡片化 UI 原则、稳定可追溯的 Demo 数据链、A/B/C 的差异化策略及 Recommendation 不可硬编码的规则均已冻结。

### Compatibility

- V0.3 的 Baseline、Search Space、A/B/C、D、人工发布、Snapshot / Rollback 与 V0.4 的三组 Evaluation、11 / 11 Gate、Comparison Metrics、Human Confirm 均保留。
- V0.2 中 Monitoring Signal 必须先经 Evaluation 的表述仅保留为历史记录；V0.3 起已确立、且 V1.0 继续采用的 Human Confirm Trigger 链路为当前有效规则。未发现其他现行冲突。

### Closed OPEN / TBD Items

Overall Score、Regression、Monitoring Trigger、TTFT、Token Cost、Recall@K、Precision@K、MRR、Probe、Hybrid Alpha、MinScore、Direct Release、Composite D Budget、有效提升、Candidate 去重、Prompt Strategy、Pipeline / Evaluation / Bad Case / Recommendation / Version Snapshot、UI、Demo 数据与 A/B/C 初始原则。

### Remaining OPEN / TBD

无。V1.0 Target Product SPEC 的产品决策已冻结；实现表现层细节不得反向更改已确认规则。

## V1.0.1 — Final Closure Patch

- **Date:** 2026-09-22
- **Status:** Confirmed

### Changed Items

- 固定 Overall Score 为 Positive、Ablation、Safety 的 9 项百分比质量指标等权平均，保留 `1` 位小数，仅用于 UI 展示与 Candidate 横向比较。
- 固定 A/B/C 动态生成原则，并将首次 Demo 的 A/B/C Example Seed Configuration 定位为 Demo 初始化数据，而非固定生产规则。

### Confirmed Decisions

- Overall Score 不计入 Latency P50 / P99、TTFT、Token Cost、Recall@K、Precision@K、MRR；不得替代 11 项 Hard Gate 或 Regression。任一 Hard Gate 失败时，Candidate 即使 Overall Score 很高仍为 Not Qualified。
- A/B/C 由 Bad Case、Root Cause、Baseline、Allowed Search Space 与 Historical Evaluation Results 动态生成；Seed 不限制后续 Candidate，不预设赢家，参数必须遵循 V0.3 Search Space，Recommendation 仍以真实 Evaluation、Hard Gate、Regression 与 Comparison Metrics 为准。

### Compatibility

- 保留 V0.4 对 40/20/40 及任何以 Overall Score 作为发布依据的禁止；V1.0.1 的等权平均仅是固定的 UI / 比较展示公式，不新增发布 Gate。
- 保留 V0.3 的 A/B/C 并列、可解释 Hypothesis、最小必要参数集合与允许多参数组合规则。未发现现行冲突。

### Remaining OPEN / TBD

无。V1.0.1 Target Product SPEC 的产品决策已冻结。

## V1.1 — Simplified & End-to-End Verified Demo Baseline

- **Date:** 2026-09-25
- **Status:** Current / Confirmed

### Changed Items

- 当前唯一产品 Source of Truth 改为 V1.1；Mini 8/4/8 是唯一当前 Generation Profile，Medium / Full 移至未来范围。
- Golden 修订以题型、负向子类、Ablation 属性及明确关联元数据判断；取消题号特判和强制成对修订，保留审计、草案哈希及人工复审。
- Optimization 仅生成每轮 A/B/C；Composite D 退出当前流程。现有 Hybrid、Rewrite、HyDE、Lightweight Rerank 等能力按真实实现记录，不暗示独立 Rerank Model。
- 发布收敛为一次 Human Release / 确认发布；旧两层审批仅保留历史记录。Legacy、Seed、旧 Run 不计入当前 V1 主 KPI 或正式结果。
- 建立确定性业务级 E2E 与 Fresh / Existing DB 验证，并要求业务变更执行文档、图、测试和 Demo 的 Impact Check。

### Compatibility

旧版本决策和审批审计继续保留作历史追溯；11 项 Hard Gate、Probe ≥90、QC ≥85、Golden 人工审核、Regression、Pareto 人工选择、Rollback 与 Monitoring Human Confirm 不变。

## Future Entry Template

后续每次规格更新必须在本文件末尾追加以下内容，不得覆盖历史条目：

```md
## Vx.y — Title

- **Date:** YYYY-MM-DD
- **Status:** Draft | Confirmed | Superseded

### Changed Items

- ...

### Reason

- ...

### Confirmed Decisions

- ...

### New OPEN / TBD Items

- ...

### Closed OPEN / TBD Items

- ...
```

## V1.1 Golden Revision 定向收口

- **Date:** 2026-09-25
- **Status:** Confirmed
- Revision AI 草案先基于真实材料决策：保留原 Evidence、同产品范围内定向检索，或人工指定；无可靠材料即停止，不跨产品随机换材。
- Negative 选材仅作生成上下文，Golden Evidence 始终为空；原有 Probe/QC 阈值、`RETRIEVAL_INCOHERENT` 和人工应用／复审边界不变。
- 本条仅补充 V1.1 Golden Revision 的实施细则，不新增主流程阶段。

## V1.1 Revision Preview 语义澄清

- **Date:** 2026-09-26
- **Status:** Confirmed
- “重新生成”只改写当前材料上的草案；“重新选材并生成”按更新后的修订意图重新选真实 Chunk，失败时保留旧草案并暂停应用。
- Operation Console 在 Modal Drawer 打开时必须仍可交互；Golden 校验与人工边界不变。

## V1.1 Governance Lifecycle 验收澄清

- **Date:** 2026-09-26
- **Status:** Confirmed
- 答案锚点失败继续由 Hard Validation 阻断；恢复操作依最新修订意图区分沿用材料与重新选材，不增加业务阶段。
- Generation / 质量重跑的进程内 Worker 重启后不自动续跑；保留审计、允许手动重试。单题只显示持久化阶段与耗时，不使用固定百分比。
- Fixture E2E、隔离库真实 Provider 生命周期及当前用户库的人工状态分别报告，不互相冒充。
# V1.2 — Friend-Aligned Simplified Baseline（2026-09-26）

Implementation Authorized / In Progress。按原始参考截图和用户确认恢复三道人审门与 Composite D；解除四文档及 Ablation 配对约束；QC 严重性与显式人工确认替代数值审批门槛。11 评测 Gate 不变。历史 V1.1 条款完整保留但不再作为当前产品判定。真实验收以 FRIEND_LOGIC_ALIGNMENT_MATRIX.md 为准。

## V1.2 交付验收记录（2026-09-27）

实现、确定性／Fixture 与副本保护检查完成；共享答案锚点同时覆盖 Generation、Revision 和 Probe，不能借 QC P0 接受豁免。隔离真实 Run 在 Golden 质量阶段阻塞，未推进 Gate 1，不宣称真实端到端完成。详见 [验证报告](V1_2_VERIFICATION.md)。

## V1.2 Golden Generation 局部补题（2026-09-27）

- 新 Run 逐 Slot 校验并事务写入合格 Candidate、活动 ID 和 attempt 审计；单题失败保留已通过 Slot，进入 `needs_regeneration`。
- 手动补题仅处理失败或缺失 Slot；每次每题最多两次，先复用 Coverage 材料，持续失败后换同产品真实材料。Corpus 指纹不符时拒绝补题。
- 20/20 且 8/4/8 复核通过后才运行 Probe / QC，之后开放人工审核与 Gate 1；部分题只读，正式导出仍要求完整 20 题。旧失败 Run 保持历史原状。
- Run 进度以已持久化 Hard Validation、已处理 Probe、已完成或跳过 QC 计数；整体分母为 60，不显示估算百分比。

## 2026-09-30 · Phase 1 closure under V1.3

业务导入与统一候选池、真实构造题型、共享 UI、QA 状态、实际阶段/完整 Usage、集中价格默认未配、Monitoring nullable migration。当前真实数据见 CURRENT_DEMO_TRUTH；本轮不执行真实业务链。


## V1.4 Interview Demo UI 修订（2026-10-03）

- **Status:** Confirmed；实施验收结果见 [Interview Demo 验收](INTERVIEW_DEMO_VERIFICATION.md)。
- 依据桌面 `RAG_SELF_EVOLUTION_CODEX_INTERVIEW_DEMO_MASTER_PROMPT.md` 与用户批准的取舍，唯一 V1.4 SPEC 第 14–15 节原位替换旧 UI 要求，不创建第二份 SPEC 或 V1.5/V2 业务流程，原输入与历史业务验收保持原样。
- 面向 20–30 分钟面试：概览为唯一全局闭环；其他页删除重复 Stepper/流程、大 KPI 与发布流水线。Pipeline 四类 Frozen/Agent 可调配置，Golden 紧凑 Preview/正式 Snapshot/风险，Baseline 三 Tab，Agent WHY/CHANGE/RESULT 与独立 D，Sandbox 四核心指标，发布聚焦当前人工决策。
- 全站详情右 Drawer 标准 560px/wide 800px、贴右满高/移动全宽；统一 Select 自动收起、卡片/表格滚动、字体/成功色/紧凑空态。真实 0/false 保留，费用仅完整 Usage + 冻结价格币种（当前 USD），Judge 不借 Generation Model 兜底。
- 方案对比固定当前正式 Baseline vs 实际 active、人工已发布 Production，删除 Qualified Candidate fallback、任意方案选择器及历史评测 UI/GET/缓存；Sandbox 保留历史实验对比，用户主动运行才产生实时同题回答。
- Primary Root Cause 保留每题一个真实原值；Secondary Signals 可多个，保留实际 Query/Metadata/Performance/Unknown 等，不强制五类映射、不改变诊断规则。当前已保存 Generation 6 / Safety 1 只作真实来源说明。
- 唯一后端补充：现有 `GET /api/pipeline.index.dimension/indexed_count` 只读实际 FAISS `d/ntotal`、未知 null；不改模型/索引/DB/业务规则。保护正式 20 题 8/4/8、Baseline 9/11、A 10/11、B 7/11 Regression FAIL、C 11/11 已发布、D 10/11 保留 C。
- 本轮禁止真实 Provider/Golden/Baseline/A/B/C/D/人工 Gate/发布重跑；仅隔离 Stub/前端与真实只读 GET 验收。Runbook 修正过时“尚无正式 Snapshot”口径，保留两张 V1.4 目标架构链接；历史报告日期与测试数字不作为本次证据。


## 2026-10-12 · Golden最终索引离线修复与关联核实

- MinerU图片image_footnote进入既有Block/Parent/Child/全文链，修复Q02第50页步骤5/6漏采根因；不重解析PDF、不改参数/模型。
- 仅新工作集Q42关联PDF12/28页紧急停机材料，Q16/Q22补R1/R3版本与章节范围。原题/答案/Evidence、22修订及28保留内容不变。
- 受控隔离补一个Child/Parent；文本预览50/50、BM25第1及14步Parent检查通过。正式索引仍旧版本、Hard Validation49/50；缺1个新Embedding，未激活、未伪造新Corpus身份。
- 29表历史行及44份PDF/索引资产保护、Backup API回退验证；本轮0付费Provider，Probe/QC/Human Pending。详见[GOLDEN_FINAL_INDEX_OFFLINE.md](GOLDEN_FINAL_INDEX_OFFLINE.md)。正式架构与UI无变化。


## 2026-10-12 · Q02第一阶段授权执行与真实检索验收

- 用户限定最多1次双文本Embedding和1次Rerank，0.01元预算、无重试；实际2请求/1749 Tokens，按官网标价计算0.0008745元，账户扣款未查询。
- 1个Child新向量、367行逐位复用，独立FAISS/新Corpus与两Plan；9 Topic membership/Slot复用，真实中心和摘要重算、来源明确。
- Q02真实候选/Rerank第1，最终Parent的14步逐条PDF定位通过；原Validator在新身份及Plan下50/50，22修订/28保留及20/10/20保持。
- 全部29表行、正式Corpus/Golden绑定及历史资产不变；隔离索引故障回退/DB备份恢复验证通过。正式切换、Task3联动/中断恢复及Probe/QC待后续授权。
- 21项离线测试与独立实物复核通过；不改Judge、Agent、UI、Gate或架构。详见[GOLDEN_Q02_STAGE1_ACCEPTANCE.md](GOLDEN_Q02_STAGE1_ACCEPTANCE.md)。


## 2026-10-12 · Q02正式切换前联动与中断恢复验证

- 复现原指针切换的硬退出留下新Corpus/旧Golden混合状态；受控协调器增加持久化旧/新身份、备份摘要、事务/State与未完成恢复，不重构通用知识库流程。
- 启动脚本及API共享只读守卫，Migration/Worker之前拒绝未完成切换及Corpus/Plan/50题错配；直接API绕过脚本问题先复现后修复。
- 11个真实数据副本正常/SQL异常/SIGKILL/恢复再中断场景通过，成功副本Hard Validation50/50；51项相关离线回归及启动A-G/LaunchAgent合同通过。
- 本轮Provider0，正式29表全部行、77个旧/新源索引/PDF文件及调用账本不变。历史成绩及Production原Legacy绑定保留；旧Baseline不能在新Corpus下自动成为当前资格。
- 正式切换仍须下一次明确授权及维护停服/无并发写入条件，Probe/QC/冻结/评测/Agent/发布未执行。图/UI与Judge/阈值不变。详见[GOLDEN_Q02_STAGE3_VERIFICATION.md](GOLDEN_Q02_STAGE3_VERIFICATION.md)。
## 2026-10-12 — 夜间运行安全边界与预算停止

- 新增显式受控质量运行：后台线程传入同一费用账本，Provider请求前预约费用、返回后校验Usage；拒绝自动重试/重开账本，技术异常停止后续题，内容不合格保留原治理合同。
- 保持DeepSeek请求参数及全部评分/治理规则；用户选择不加输出上限，20元预算预检阻断，未正式切换、未调用Provider。
- 真实新旧资产、50题及历史保护重新验证；报告见[GOLDEN_OVERNIGHT_ACCEPTANCE](GOLDEN_OVERNIGHT_ACCEPTANCE.md)。无UI/架构图、Judge、Golden内容或历史成绩修改。
## 2026-10-12/13 — 正式Corpus切换、50元限额及所有者委托审核

- 用户新授权替代上轮预算阻断：正式联动切换后50/50，保留历史；分任务输出上限、持久化50元预算和显式阶段继续，后台线程继承同一受控上下文。
- 回答/Judge/查询上限冻结并纳入新Evaluation Identity，Candidate同尺校验；旧无上限字段的历史摘要不变，不改评分/门槛。
- 新增本工作集专用Owner Delegated Review正式接口，复用JSON审计和审批事务，无新表迁移；记录真实AI主体、所有者预授权、逐题PDF依据，普通人工路径不变，不豁免质量/安全条件。
- 修复业务审计漏传已有版本/章节范围、元数据单独修订被误判无变化；有界Revision保留谱系，不重生成50题。UI仅区分代审来源并同步唯一架构源及导出。

- 实际执行：50题Probe/QC Passed，6项真实召回风险经PDF独立复核显式接受；Q23保留QC P1并绑定当前QC/Probe记录处置，不改评分。冻结Owner Snapshot后Baseline第9题Judge240秒超时，8/50 Partial，未知Usage保留预约并阻止后续Agent/Sandbox。首次停止原因不再被外围阶段异常覆盖。详见[GOLDEN_OWNER_DELEGATED_ACCEPTANCE.md](GOLDEN_OWNER_DELEGATED_ACCEPTANCE.md)。

## 2026-10-13 — Partial同身份恢复与一次Judge补跑

- 修复普通Resume缺失已冻结request_limits引起的身份冲突；源Run限制用于实际Provider请求，仍严格校验全部身份/配置。
- Partial展示与完整Baseline资格分开：页面显示当前Snapshot的8/50、超时与检查点，不把中断隐藏为未运行或已失效。
- 明确用户授权原未知请求最多一次Judge补跑，原348记录及预约保留，累计预算按可用余额收紧并留3元，原Judge/规则/Golden不变。
- 实际恢复至21/50：原8题/Q09回答复用，Q09一次返回响应只做已保存内容的末尾闭合符恢复并通过原Parser（真实Bad Case）；Q22 Judge IncompleteRead/Usage未知停止，无新增重试或Agent/ABC。余额23.09→22.31，原348记录不变，详见[恢复验收](BASELINE_PARTIAL_RESUME_ACCEPTANCE.md)。
- API重启清理曾标记后续非本轮Run为中断；新增最小执行PID归属保护及存活/退出回归，不伪造恢复其状态、不改评测身份或历史记录。

## 2026-10-13 Sandbox冻结配置继承与HTTP预检

- 共享Candidate输入校验供正式启动和只读preflight复用；严格验证Search Space及绑定Baseline身份。
- 冻结限制进入实际Provider payload，不依赖当前固定数值；新Dataset/新Baseline不重绑旧Candidate。评测规则、Judge、Gate、Regression不变。
