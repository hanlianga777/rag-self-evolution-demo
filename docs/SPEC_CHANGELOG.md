# RAG Self-Evolution SPEC ChangeLog

本文件是产品规格变更的追加式历史记录。当前有效产品规则仅见 [V1.4 SPEC](RAG_SELF_EVOLUTION_SPEC.md)；以下旧版本条目不是并行生效规则。不得覆盖或重写既有条目。

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
