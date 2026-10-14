# RAG Evolution

当前规则以[唯一SPEC文首](docs/RAG_SELF_EVOLUTION_SPEC.md)为准。2026-10-14已按用户授权清空历史实验，知识资产保持；当前问答使用保留参数的**初始配置（未评测、未发布）**。新Golden、Baseline与受控候选需重新治理，不自动恢复历史审计。

评估按答案质量/检索效果/安全鲁棒/性能体验组织；Pending及Disputed仍阻断资格，与已确认失败分开解释。Agent允许0–3个有真实Trace支持、单一干预的候选；D同样验证，11 Gate与正式Regression阈值不变。真实模型效果未由本轮离线测试确认。

后台每分钟按完整对象和依赖清理，历史实验/评测非引用对象各50；当前/活动/被Production引用的完整审计链保留，Full100不截成50题。历史列表每页最多50，详情保存完整Trace。维护清理工具默认只读：`python3 scripts/reset_experiment_history.py`；真正清理须停写入、明确`--execute --maintenance --backup <唯一新路径>`，不能把它用于普通启动或自动清理。唯一备份和旧审计仅外部保留。

本轮依据、实测性能与Mini20准备见[验收报告](docs/RAG_DIAGNOSTIC_RESET_ACCEPTANCE.md)。`./start.sh`及5174/8010入口不变；不要自行启动Provider实验。


面向企业知识问答的评测驱动 RAG 质量运营与版本决策 Demo。

**唯一当前有效规格：[V1.4 + Phase 1 + Baseline/Agent UI 恢复（2026-10-09）](docs/RAG_SELF_EVOLUTION_SPEC.md)**。当前合同以SPEC文首为准；[ChangeLog](docs/SPEC_CHANGELOG.md)追加历史，[Current Demo Truth](docs/CURRENT_DEMO_TRUTH.md)区分真实Current与Legacy。历史验收只代表其日期的运行状态。

Baseline 与 Agent 已恢复阶段、完整方案及证据报告；本轮 A/B/C 批执行复用既有单候选接口，运行失败保留结果，重启后须再次显式继续。所有实验/批准/发布仍需原有人工操作，资格与预算不变。[恢复验收、九图对照与演示脚本](docs/BASELINE_AGENT_RESTORATION.md)。

当前真实Knowledge：4 PDF / 157页、349 Parent / 368 Child、text-embedding-v4 1024d、368 Indexed、9 Topics。原Full 100（40/20/40，机器87/用户批准13）已由用户冻结为GD-20261008024214127995，保留原题、审批、历史质量记录及Legacy Production。新建独立Golden Dataset V2 Medium 50（20/10/20），角色/场景/意图与真实Child/Parent页码持久化，十维业务审计参与资格；当前真实机器结果与未解决项见[Medium V2验收](docs/MEDIUM_V2_POLISH_VERIFICATION.md)和[50题审阅报告](backend/reports/medium_v2_polish_review.md)。本轮不自动批准、冻结、Baseline或Agent。

Pipeline与Golden采用身份隔离的内存Cache/SWR；Current/Pool保留后端30条分页、前端滚动增量加载及详情懒加载。所有右侧Drawer共享单题详情母版 `--drawer-width:800px`，全高100dvh，小屏100vw。长期SPEC/图源同步规则见[AGENTS.md](AGENTS.md)。

候选池默认一行质量筛选与业务用例菜单；下载中文四列Excel，上传后在紧凑窗口预览并明确确认有效行。旧CSV/XLSX继续兼容，处理经验保留为待核验材料，不直接充当Golden答案。选题按Corpus会话暂存；智能补齐只复用现有候选，不调用模型，缺口保持真实。完整工作集仍受Profile、Evidence、Coverage及人工Gate约束。[本轮验收与真实统计](docs/CANDIDATE_POOL_IMPORT_VERIFICATION.md)。业务/技术架构关系及唯一图源不变。

## 产品闭环

`知识库 → Golden 规划与治理 → Gate 1 → Baseline / Bad Case → Optimization Agent → A/B/C → Sandbox / Regression → Gate 2 → 条件 D → Gate 3 人工发布 → Production → 问答验证 / Monitoring → 人工确认 Trigger → 下一轮优化`

只有 Optimization Agent 是主 Agent。Hard Gate 与 Regression 决定资格，Overall 仅用于比较；D 未通过或未优于 Winner 时保留 Winner。不自动改知识、调参、发布或回滚。

目标一级模块顺序：RAG 自进化项目概览、知识库、Pipeline 配置、Golden Dataset、Baseline、Agent 工作台、发布、问答验证。Monitoring 为问答验证二级 Tab；保留现有 Hash/兼容入口，目标名称与 H1 一致。

## V1.4 业务实施历史状态（截至 2026-10-02）

| 能力 | 当前证据与运行边界 |
| --- | --- |
| Current Baseline resolver、Experiment 绑定、Monitoring Confirm/首轮 | 共用身份解析、幂等 Confirm、Provider 锁外执行与 A/B/C 原子保存；P0 定向复审通过 |
| Golden V2、统一 Validator、Pool 匹配 | 现有 FAISS 向量规划、冻结 Plan/Slot、最大二分匹配；263 项阶段离线后端测试通过 |
| 双层 Probe、原解析全文、原子 bundle | CandidateK/Final Context 分层、失败与空召回分开；真实 4 PDF/157 页备份 Staging 兼容校验通过，真实 active 尚未升级 |
| Usage/Timing、价格版本与缺失原因 | 284 项阶段离线测试及复审通过；缺历史数据不补造，节假日计费不明时不报精确成本 |
| 八个模块与完整离线生命周期 | 296 项隔离后端、121 项前端、构建通过；Chromium 四尺寸 208 检查，54 ID 具名映射；最终复审通过，当时保留换材草案重新生成后关闭多一次提示的 Minor |

源码证据和需求 ID 对照见 [SPEC 第 3 节](docs/RAG_SELF_EVOLUTION_SPEC.md#3-需求追踪与当前实现证据)。当前冻结 Golden 不能因为文档更新而称为 V2 生成；历史未采集字段不回填。Snapshot、Baseline、Candidate 与 Production 分别保留自己的来源。

## Interview Demo 产品叙事（2026-10-03，Historical）

每个页面只回答当前阶段的问题：知识库技术选型 → Pipeline 的 Frozen / Agent Search Space → Golden 稳定评测基准 → Baseline 的 Hard Gate / Bad Case → 根因与受控 A/B/C 实验 → Sandbox / Regression 与条件 D → 人工发布 → 同题真实问答差异 → Monitoring 下一轮。只有概览保留全局闭环；其他页面删除重复 Stepper、流程图、大 KPI 与发布流水线。

主结论优先，文档/Evidence/Case/Search Space/完整配置/高级指标进入统一右侧 Drawer（当时标准560px/wide800px；已被当前唯一800px合同覆盖）。Sandbox 主表聚焦 Hard Gate、Bad Case、Regression、Qualification；A/B/C 统一 WHY / CHANGE / RESULT，D 独立说明组合失败为何保留 Winner。当前真实根因为 Generation 6 / Safety 1，不借示例虚构 Retrieval 失败。

方案对比固定正式 Baseline 对实际 active、人工已发布 Production，不提供任意方案选择器或 Qualified Candidate fallback，删除历史评测 UI/GET/缓存。Bad Case 选择后填入可编辑问题，只有主动点击才运行实时对比；答案双栏为重点。问答验证 Tab 顺序为问答验证 → 方案对比 → Monitoring。Input/Output Tokens 与费用分开；真实 0/false 保留，估算只使用完整 Usage 与冻结价格币种（当前 USD），缺历史计费依据不回算。

本轮业务与真实数据保护边界不变；唯一后端补充为现有 `GET /api/pipeline` 的实际索引 `dimension/indexed_count` 可空只读字段，不重建 FAISS、不调用真实 Provider。20–30 分钟完整讲解及现场手动调用边界见 [Runbook](docs/INTERVIEW_DEMO_RUNBOOK.md)。

## 当前正式架构（同源于项目概览）

以下图表达完整流程设计，当前运行结果仍由应用持久化对象决定；不代表Gate已批准或Baseline/Agent已运行。

![当前业务架构](架构/业务流程图.svg)

![当前技术架构](架构/技术架构图.svg)

唯一图源：[KnowledgeDiagrams.tsx](frontend/src/components/KnowledgeDiagrams.tsx) + [Shared CSS](frontend/src/styles.css)；[导出脚本](scripts/export_architecture.py)读取实际页面SVG和Computed Style，生成16:9 SVG/2560×1440 PNG与[校验Manifest](架构/architecture-manifest.json)。[平台说明](架构/RAG自进化平台架构说明.md)。旧HTML为Historical归档，不作为当前正式图。

## 本地启动与恢复

前置条件：Python 3.10+、Node.js 20+、npm。保留现有启动入口：

```bash
./start.sh
```

前端：[http://127.0.0.1:5174](http://127.0.0.1:5174)；API 文档：[http://127.0.0.1:8010/docs](http://127.0.0.1:8010/docs)。已有后台服务重启后先检查端口/PID/目录，避免另开重复进程。

手动启动方式仍为：

```bash
python3 -m pip install -r backend/requirements.txt
PYTHONPATH=backend python3 -m uvicorn app.main:app --port 8010
cd frontend && npm install && npm run dev
```

真实调用前在本地 `.env` 配置 `DEEPSEEK_API_KEY`。Key、真实 DB、备份和索引产物不提交 GitHub。Provider 不可用时返回明确状态，不创建模拟回答、评测或发布结果。相关 Chunk 会随显式回答/QC/Judge/Agent 请求发送给 Provider。

Golden 失败时保留已合格 Slot，使用现有补失败题入口；Probe/QC 中断使用现有重试入口，不重做已应用修订、不自动批准。历史 Snapshot 只读；历史详情与统一 Drawer 的最终验收见实施报告。

## Preview 与真实验证边界

**V1.4 Planner Preview 已实施**：Golden 当前测试集紧凑 Coverage 入口选择 Profile 后点击「预览当前 Corpus Coverage」，Legacy / 无 Run 页面也可使用；保存 Run 的冻结规划单独查看。`POST /api/governance/coverage-preview` 使用当前已存向量，返回动态 K、merge、Slot、材料与缺口；不调用生成/Judge/QC，不改变当前 Golden/Baseline/Production。Pool Preview 为 `POST /api/governance/generation-runs/from-pool/preview`。旧后台服务没有自动重启，使用新代码前须手动受控重启。

以下为Historical V1.4阶段手动验证清单，不能视为当前阶段授权；Baseline/Agent须后续单独授权：

1. 手动运行一次 Baseline vs Production 实时问答对比，查看真实回答、证据、Usage、Latency 与成本缺失原因。
2. Production QA → 人工判 Bad Case → Confirm Trigger → 手动启动首轮 Agent；可能创建实验并耗用 Provider/预算，不自动 Sandbox 或发布。
3. 运行 V2 Planner Preview，核对动态 K、小簇合并与 Slot，不接着自动生成 Golden。

若要将当前演示数据称为 V2，需要另行生成、人工审核并冻结 V2 Golden，然后在同一新 Snapshot 上执行 Baseline/实验与验证。未批准的 Seed / Legacy 候选不能冒充正式 Golden；当前正式 Legacy Snapshot 保留已有的人审资格与历史实测结果。Fixture / 离线 Stub 不能冒充真实 Provider 结果。

## 验证入口

隔离后端测试：`python3 scripts/test_v14_offline.py`；`cd frontend && npm test && npm run build`。测试必须使用隔离 DB/Stub，不消耗真实 Provider 配额；`scripts/test_phase1_ui.mjs` 仅允许隔离 :5180/:8011。

本轮 UI 与只读数据保护结果见 [Interview Demo 验收](docs/INTERVIEW_DEMO_VERIFICATION.md)；前轮业务代码结果见 [V1.4 实施验收](docs/V1_4_IMPLEMENTATION_VERIFICATION.md)，之前的文档/图交付记录见 [同步验收](docs/V1_4_DOCS_SYNC_VERIFICATION.md)。历史或 Stub 结果不代表真实 Provider 重跑。

## Phase 1 Knowledge Pipeline

本轮仅重构项目概览和知识库，新增真实 MinerU VLM → Table KV Normalize → Parent-Child → text-embedding-v4 → FAISS 与 qwen3-rerank / Parent Expand 检索。唯一规则源仍为 `docs/RAG_SELF_EVOLUTION_SPEC.md`，运行证据见 `docs/PHASE1_KNOWLEDGE_VERIFICATION.md`。

在本地 `.env` 配置独立 `MINERU_API_KEY`、`DASHSCOPE_API_KEY` 和与 Key 匹配的业务空间根地址 `DASHSCOPE_BASE_URL`。不把 Key 发到聊天或提交 Git。知识库点击“重建 Knowledge Pipeline”后展示持久化阶段；失败保留旧有效资产，成功激活后自动以 Full Profile 构建 Golden，并停在真实 Human Gate 1。新激活不迁移 Legacy Production，不自动评测或发布。


## 2026-10-11 统一评测与受控优化

当前产品合同见 docs/RAG_SELF_EVOLUTION_SPEC.md 文首。Child命中指标与最终Parent证据充分性分开；统一Judge读取完整证据，Baseline/A/B/C/D冻结同评测身份。旧实验保留只读，历史答案回放不成为正式Baseline或发布依据。新目标修复/附带改善/新增失败分开，程序推荐Winner，Gate2人工确认；有效来源下D最多一次授权LLM建议，经程序校验后另行授权Sandbox。Gate3及兼容配置回滚仍由人工执行。图形表达设计，离线验收不证明真实Provider效果。

评测规则V1.2通用缺陷修复、16题离线回归及真实验证边界见 [EVALUATION_POLICY_V12](docs/EVALUATION_POLICY_V12.md)。本次未重新运行真实Baseline。

## Baseline请求超时与手动续跑

DeepSeek请求/socket等待默认240秒，可用DEEPSEEK_TIMEOUT_SECONDS覆盖；不等于整题/50题限时，也不改性能Gate。既有重新运行按钮在最新Baseline为partial/failed时会尝试同身份续跑，新建子Run保留原记录；完成题不重复调用，保存生成答案时只补Judge。身份不匹配返回409。若明确需要全新评测，原POST /api/evaluations/run可传 `{"fresh":true}`；显式来源用 `{"resume_source_id":"EVAL-..."}`。两者互斥，调用仍需用户费用授权，无后台自动重试。旧partial未保存的中间答案/用量无法补回。详见[中文验收报告](docs/BASELINE_STABILITY.md)。


Golden 50题前轮离线修复过程：见[最终索引离线验收](docs/GOLDEN_FINAL_INDEX_OFFLINE.md)。最新真实隔离构建结果见下方第一阶段验收；正式49/50，不可启动完整Probe/QC。

按[正式索引最小执行计划](docs/superpowers/plans/2026-10-12-golden-controlled-index-update.md)，[Q02第一阶段](docs/GOLDEN_Q02_STAGE1_ACCEPTANCE.md)已获授权并通过：真实2请求/1749 Tokens，隔离新Corpus下50/50，367向量逐位复用；正式Corpus及Golden绑定未切换，正式仍49/50。下一阶段切换须明确授权及联动/中断恢复验证，Probe/QC未运行。

[Stage3切换前隔离验证](docs/GOLDEN_Q02_STAGE3_VERIFICATION.md)已通过：11个联动/中断场景、51项回归及启动守卫；本轮Provider0，正式仍未切换。新Corpus会使旧Baseline失去当前身份资格，历史成绩和Production原Legacy索引保留。正式切换须下一次明确授权及维护窗口重验。
# 2026-10-12 夜间受控验收

本轮因保持DeepSeek请求配置下的20元预算预检阻断，未切换正式Corpus、未调用付费Provider。完整状态见[中文执行报告](docs/GOLDEN_OVERNIGHT_ACCEPTANCE.md)。只读复核入口为 `python3 scripts/preflight_golden_overnight.py --output <全新本地审计目录>`；不导入API、不联网、不激活。

受控质量Worker内部可显式传入 `paid_run`，使用 `app.paid_run.PaidRun` 的全新账本、经核实的人民币保守费率/模型输出范围及实时身份校验函数。该上下文必须传至线程入口；它不改变请求参数、不自动重试或续跑，也不替代维护切换、预算预检或人工Gate。现有公共API没有新增执行入口，普通任务不自动使用本轮账本。正式执行前仍须重新核价、完成预算校验及按Stage3要求停服备份。
# 2026-10-12/13 所有者授权连续运行

新授权允许分任务输出上限和累计50元预算；正式Corpus已按Stage3切换，新工作集正式Hard Validation50/50。既有20元预检报告为历史记录。当前请求上限见`app.paid_run.REQUEST_LIMITS`，不改变模型/评分；Baseline和Candidate须冻结相同限制。

本次受控入口为`scripts/run_golden_owner_night.py`，必须具备本轮原始用户授权，使用原持久化账本逐阶段显式继续，禁止重复阶段/未知费用续跑。`--stage repair-1/repair-2`只按审核过的局部变更走真实Revision接口；Baseline/Agent/Candidate通过真实应用ASGI接口写正式DB并调用真实Provider，不使用Fixture替代。Owner委托接口另核服务器授权文件、50题真实机器资格、逐题内容/风险/PDF依据；审批来源标记AI代理，不能冒充人工专家。普通人工审核和发布Gate保持。所有私有授权、账本、原始响应及回滚资产不入Git。

真实结果见[本轮中文验收报告](docs/GOLDEN_OWNER_DELEGATED_ACCEPTANCE.md)：已冻结Owner委托Snapshot；Baseline因Judge超时停于8/50 Partial，未知Usage禁止自动续跑，Agent/ABC未启动。重启服务不会恢复付费任务。对已有人工路径允许复核的检索不连贯，可通过具名独立PDF审核显式接受；同一召回问题的QC P1须逐条处置并绑定当次质量记录，不豁免P0/失败/安全风险。

Candidate启动前可调用 `GET /api/candidates/{id}/preflight` 只读核对绑定Baseline、冻结身份/限制及优化配置，不预约或调用Provider。旧Dataset/旧Baseline实验不会重绑当前Baseline。

评测运行窗口支持“停止运行”：等待当前请求结束并保存断点后停止，已完成题目保留；窗口×仅隐藏状态。手动停止后不自动恢复，需明确续跑。见[验收说明](docs/EVALUATION_STOP_ACCEPTANCE.md)。

Q38 Judge结构异常修复：完整输出示例与原Parser一致，错误显示具体字段；显式Resume保留原审计、使用新Run的有限重试窗口。同Run重启不重置计数。见[Q38验收](docs/Q38_JUDGE_ACCEPTANCE.md)。

Optimization Agent请求和HTTP错误审计保存模型/参数/大小/SHA及脱敏Provider错误码、正文、阶段和重试判断；Token估算仅为观测，不当作精确Tokenizer结果或费用阻断。见[离线验收](docs/AGENT_HTTP400_ACCEPTANCE.md)。

Agent上下文超限已通过传输去重修复：省去重复的result_json字符串，完整result及证据仍保留，数据库历史不变。见[验收](docs/AGENT_CONTEXT_LIMIT_ACCEPTANCE.md)。

Mini20支持显式Business V2业务出题与十维审计，保留原Coverage/Construction约束。所有者委托AI审核必须绑定唯一Run、当前Corpus/Plan、明确Profile及实际授权来源，不冒充真人。具体本次结果见[Mini20收口验收](docs/MINI20_QUALITY_CLOSURE_ACCEPTANCE.md)。
