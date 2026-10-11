# RAG 自进化 Demo 一次性收口验收报告

日期：2026-10-11。依据用户批准计划与最新附件实施，Ponytail full。完成范围是代码、离线功能验收、文档与架构交付；真实Provider效果验收未执行。

## A. SPEC 更新与历史边界

唯一规范为 `docs/RAG_SELF_EVOLUTION_SPEC.md` 文首「当前有效合同 — 2026-10-11」。替代旧Child全命中直接判定失败、历史修复字段用于新目标资格、自动合并D及跨评测规则正式比较；历史原值保留。11 Gate、Regression严重新增0/普通≤1、12次Sandbox及D预留1、Search Space和人工Gate保持。

新身份冻结Golden/Corpus、Judge配置（模型、temperature=0、完整最终上下文）、Prompt/Matcher/Scoring版本及Gate定义，不随调优参数变化。历史字段缺失显示历史规则/未采集。新规则身份为judge-v2-context / evidence-v2-parent / v1.1-evidence-gates。

仍待真实验证：新版Judge在真实题目上的语义、合理补充、未知材料归属及冲突判断；新版Baseline和候选效果；真实用量/计价。旧Baseline不能继续正式运行第二轮，须另行授权新Baseline。运行中的旧后端未自动重启，不把本次代码验收表述为真实服务已升级。

## B. 代码修改与复用

| 模块 | 修改、原因与复用 |
|---|---|
| evaluation_contract / evaluation | 独立保存Final Evidence Sufficiency、全部必要事实定位/来源约束；Child覆盖继续作为观察。最终上下文缺失为待核实，不冒充检索零命中。不同规则身份阻断，正式与回放分开；复用已有运行、逐题结果、SQLite JSON。 |
| providers / ai_service | 同一次Judge收到完整上下文、Golden、负向子型/预期行为和来源。样本作为数据，原评分维度/门槛不变；不开发第二套Judge。充分结论必须有全部事实及真实引用定位/适用来源，冲突保持待核实。 |
| optimization | 全量Bad Case审计，已确认目标才进入调参引用；保存目标组、根因依据、假设、最小差异、预期与风险。读取历史配置/结果供新提案，不继承资格；复用现有Agent/Validator。 |
| governance / policy使用方 | 分项目标修复/附带修复/新增退化/净改善题号；程序质量优先Winner。D先筛选同身份改善来源/合法配置/预算，授权后一次调用，事务外网络、事务前后重验；重复/失败/不确定不自动再调用。推荐计算和保存使用同一写事务，防迟到工作覆盖新Gate2/D决定。 |
| main / 版本治理 | 新增授权回放API；回放上下文不完整时在创建记录前阻断。发布事务重验配置、资格与评测身份；回滚人审、Corpus/索引/模型兼容检查，保留配置恢复的真实范围。Monitoring建议仅引用已采集、已判定QA信号。 |
| config / corpus / 验收脚本 | 可显式隔离DB、Corpus、索引、uploads及.env；导入app前设置。既有默认路径不变。验收脚本禁止真实Provider请求。 |

未新增数据库业务表、调度器、后台轮次循环、新视觉体系或依赖；不迁移/回填历史成绩。复用单候选API和共享Operation串行生命周期，刷新后只有用户再次点击才能启动剩余generated项目，failed不隐式重试。

## C. Baseline / Agent UI

- Baseline主层：业务结论、Gate/Overall/Bad Case、可信度分组、代表案例和下一步；配置/组成/性能与保存来源继续可查。11/11仍有Bad Case清楚区分。
- Case Drawer：结论→问题→期望/实际→Golden与最终上下文→Matcher→Judge→初步诊断。Candidate/Child命中/排名与身份审计折叠；负向Anchor明确不是答案Evidence。真实问题、答案和原文按保存记录读取。
- Agent：主层仅最新轮次，历史进入共享右侧Drawer；WHY/TARGET/CHANGE/EXPECTED/RISK/RESULT保留；目标与附带修复分开，历史字段保留原统计解释。Winner显示来源轮次。
- D：Gate2确认后显示组合操作及条件/来源/理由/风险/结果。D无效、失败、打平保留Winner。已预约结果未确定时不自动重试。D建议与D Sandbox分别授权。
- 费用：操作前显示题量、候选规模、回答+Judge与可能的改写/检索调用、预算和D预留。无法核实预计输入/输出与价格时明确无法估算；取消不发起运行请求，授权仅限此操作。
- 旧规则实验运行入口阻断；历史查看不改写数据。八导航、固定Header/Tabs、共享组件和唯一800px Drawer保持。

## D. 其他六个页面

| 页面 | 本次实际变更 |
|---|---|
| 项目概览 | 仅更新内嵌唯一架构图；整体布局与阶段结构保持。 |
| 知识库 | 未修改页面代码；唯一共享架构组件仍复用。 |
| Pipeline配置 | 未修改页面代码/冻结技术栈/Search Space。 |
| Golden Dataset | 未修改页面、题目、Probe/QC/审批/冻结规则。 |
| 发布 | 增加已有Monitoring建议和回滚兼容范围说明；原来源、配置差异、历史及人工确认保持，后端增加事务校验。 |
| 问答验证 | 未修改页面结构/问答流程；既有左右答案、Evidence、真实Token与阶段耗时及参数差异保留，实时QA不自动Judge。 |

所有一级标题与导航名称逐页核对；没有整体重构其他六页。

## E. 架构交付

唯一源：`frontend/src/components/KnowledgeDiagrams.tsx`及Shared CSS。补充统一Matcher+Judge、可信诊断、程序Winner、12次含D预算、授权LLM D与保留Winner/晋升D；沿用原节点、连线和导出流程。

正式交付：`架构/业务流程图.svg`、对应PNG、`技术架构图.svg`、对应PNG、`architecture-manifest.json`；同步README、ARCHITECTURE和平台架构说明。以 `python3 scripts/export_architecture.py --fixture /tmp/rag-closure-browser-fixture.json` 从实际React SVG/Computed Style导出，Fixture只提供页面数据，不另画图。产物表示流程设计，不代表Gate或运行已完成。

## F. 验收与数据保护

后端全量隔离验收：**392项通过，失败0、错误0**。新版证据/回放/D守卫及API生命周期专项26项通过；真实Candidate B仅只读作为回归输入，没有模型重评分。

前端185项/34个测试文件通过；TypeScript与Vite Build通过；`git diff --check`通过。新增费用取消、旧规则阻断、最新轮次/历史Drawer测试。隔离API生命周期覆盖Golden→Baseline→A/B/C→Gate2→D→保留Winner→人工发布守卫/Monitoring；这些全部为Stub/Fixture，不是真实Provider生命周期。

浏览器在1536×960、1440×900、1366×768、390×844完成八页32个主页面检查，另有Case/历史Drawer、方案卡、Sandbox和费用取消。全部API被Fixture拦截，运行POST未发起；页面错误0、主页面横向溢出0。Drawer右侧边界/焦点进入/关闭命中检查通过，复用唯一正文滚动容器。截图均明确标记Fixture。架构源/导出哈希一致，SVG节点文字边界检查通过。

本地证据目录：`output/playwright/closure-2026-10-11/`，含截图、`browser-checks.json`、SQLite Backup API生成的`protected-backup.db`、前后保护摘要、Corpus核对和只读Candidate B回归材料。该目录被Git忽略，不提交真实库、私人材料或大量截图。

保护复核：29张表排序后的全部行与备份完全一致；数据库schema不变；36个已记录数据/索引文件哈希不变；4份原PDF SHA-256与受保护的原manifest一致。Snapshot原JSON摘要不变，Medium为`c8644387e71dd7687102d5ac77305fcd89138ec7276394aef6fa9d39971c8a19`。没有历史成绩/资格/审批/Production改写。

真实Candidate B回归材料：当前第一轮50题均已保存最终上下文；按旧判定只读计算为修复8、新增5、净改善3，但指定的2个目标均仍失败（0/2）。旧字段8继续解释为全部原失败题修复，不能冒充目标题修复。回归只检查证据观察、身份与缺失新版字段的兼容，不预设新版都应通过，也未进行Judge重评分。

| 场景 | 对应离线检查与边界 |
|---|---|
| G01–G05 | Parent全事实而Child部分命中、部分事实/伪造引用、多来源替代、负向Anchor、明确产品/版本及来源冲突守卫。 |
| J01–J05 | Judge输入/数据边界、来源/版本/单位冲突及未知状态、负向评分路径、跨规则阻断；真实Judge语义效果待授权。 |
| B01–B05 | 原Snapshot复用、历史不改、规则/Judge配置身份、独立回放/完整上下文校验、费用取消/真实API生命周期Stub。 |
| A01–A06 | 全量审计/可信目标、目标依据引用、非固定A/B/C方向、Search Space与依赖、分项修复、重复配置/历史反馈。 |
| S01–S06 | 共享Operation串行、12次预算并发、D预留、失败不退款、身份/中断、11Gate/Regression冻结测试。 |
| D01–D08 | Qualified与Gate2、确定性排序/缺失成本、人工确认、无来源零调用、单次/并发/失败/调用后身份失效、非法参数、D独立Sandbox与保留Winner。 |
| R01–R06 | 不合格/非推荐阻断、人审、事务资格/身份/配置重验、历史来源、人工回滚及索引/模型/Corpus兼容。 |
| UI01–UI15 | 185项前端测试、八页四尺寸浏览器检查、Drawer与费用取消、历史折叠/状态、双答案/指标、唯一图源/导出。 |

## G. Token与真实验收边界

本轮真实Provider调用：**未执行**。真实Baseline、A/B/C/D、历史答案Judge回放：**未执行**。实际真实调用Usage、Token、账单Cost：**未采集**，不填零冒充已测。测试中的固定回答/评分和D调用计数仅验证代码守卫。

后续需单独授权：新版完整Baseline，或仅历史答案Judge回放；随后新实验/候选Sandbox、可选D建议与D Sandbox按各自范围授权。Gate1/2/3与发布/回滚继续由人确认。旧配置仅作为新提案，旧资格不能继承。实际价格/用量缺项不能作为零成本参与Winner比较。

## H. Git同步

实施基线：本地与远端`main`均为`e875d558b345e9da5e329d2ee0945d1ae9f2226d`，初始工作区干净。提交范围为代码、SPEC、Changelog、直接相关文档、必要测试与正式架构产物；真实数据库、凭据、附件和大量测试截图不入Git。

最终交付消息提供实际Commit SHA及`origin/main`同步/干净工作区核验结果；本报告与实现同批提交。复现后端：`python3 scripts/verify_self_evolution.py`；前端：在frontend执行`npm test`、`npm run build`。私有Candidate B材料未提交，其他机器对应只读回归测试会明确skip，不冒充已测。
