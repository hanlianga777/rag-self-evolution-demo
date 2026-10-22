## 2026-10-21 · 当前V5合同与既有节点内部流程

## 2026-10-22 当前Agent内部合同

保持原业务节点和八导航。诊断输出分为严格技术根因与独立experiment_plan：Canonical完整性验证后，结构观察可支持exploratory Candidate，Unknown不改写。缺材料/执行进入明确修复任务；Resolver补证为辅助。confirmed沿原合同；两类候选都在Sandbox创建前重验真实Diff/当前目标，D逐来源复验。全量50题同尺Sandbox/Regression、11 Gate、推荐与三个人工Gate保持。旧本地检索补齐完整重排Trace与完成状态。详见[当前验收报告](docs/AGENT_EXPLORATION_E2E_REPORT.md)。下文互斥的“只有确诊可作实验目标”条款为历史。

沿用Golden → Baseline → Bad Case → Agent → Sandbox → Regression → Recommendation → 人工发布，四维指标与五类典型Bad Case不改。评测节点内部区分Final正文Fact与经Canonical标题/页序/结构绑定的Scope，完整冻结规范作为独立Judge输入，版本纳入新Identity。Diagnostic复用现有Provider做显式授权的一次语义补证，真实来源/覆盖经程序校验后单独保存sidecar；没有第二Agent，读取不调用模型。

Judge-only Baseline逐题核验旧生成执行，在同一创建事务核源并只种入execution，后续走原Baseline逐题保存、重试/异常、Gate及当前身份守卫。生成禁止条件随Checkpoint恢复保留；旧Judge/成绩不复制。前端只在原Baseline页/Drawer增补预检、费用授权及证据读取。正式图的节点、关系与图源不变，故无另画架构图或导出差异。[当前合同与离线验收](docs/CONTRACT_RESOLVER_REPLAY_V5_ACCEPTANCE.md)。

## 2026-10-21 · 既有诊断节点内部证据校验

产品节点及关系维持Golden → Baseline → Bad Case → Agent → Sandbox → Regression → Recommendation → 人工发布，正式图源及导出不改。原诊断模块增加独立只读审计事实校验：持久化Case/冻结Snapshot/Canonical Corpus/完整阶段/审计文件SHA闭合后推导阶段根因；独立审查与同次Judge字段分别溯源，不成为第二Judge或人工Gate，不写成绩或修正历史JSON。未知新证据仍阻断，Critical不充当Safety类别。

既有Optimization Agent只接收有真实来源和合法干预的目标；上下文选择在保存候选/重排/Parent上验证必要事实覆盖及已满足事实保留。能力不可达时保留技术根因而不产生该干预目标；不扩大Search Space。Baseline业务FAIL列表与可优化子集分开，现有Drawer展示技术证据。评测身份、11 Gate及发布治理保持。细节见[验收报告](docs/BASELINE_DIAGNOSTIC_EVIDENCE_FIX_REPORT.md)。

# 架构说明（V1.4 目标 / Phase 1 实现边界）

> **V1.4 业务实施（2026-10-02）：** 用户已批准完整代码实施与 GitHub 同步。唯一规则源为 [SPEC V1.4](docs/RAG_SELF_EVOLUTION_SPEC.md)，阶段证据见 [实施与验收记录](docs/V1_4_IMPLEMENTATION_VERIFICATION.md)。P0、Golden V2、Probe / FullText 引擎与成本已通过隔离后端回归和代码复审；最终 296 项后端、121 项前端、构建和四尺寸 Chromium 208 检查通过；整体审查及一次修复后的限定复审通过，保留一个 Drawer 换材后误提示的非阻断 Minor；其他运行边界按 SPEC 第 3 节记录。真实 Provider、评测与发布不自动执行；下方 Phase 1 / V1.3 为历史记录，不能替代 V1.4 验收。

完整 V1.4 模块与数据流见 [平台架构说明](架构/RAG自进化平台架构说明.md)；下方底座说明保留为升级前历史，当前实现以 SPEC 和实施验收为准。

历史阶段状态（2026-09-30）：见 [Current Demo Truth](docs/CURRENT_DEMO_TRUTH.md) 与 [Phase 1 验收](docs/PHASE1_VERIFICATION.md)。以下保留该历史阶段的规则与验收边界。

## Phase 1 增量架构（2026-09-30）

业务文件 → 标准库 CSV / openpyxl XLSX → 当前 Corpus 原文定位 → questions/raw_json → Profile 复制新 Run → 既有 Hard Validation / Probe / QC / Gate 1。无第二套 Golden 系统。

perf_counter 测量实际 Query、Retrieval 子阶段、Context、Generation 与 Judge；保留 UTC 时间、原回答 Gate 延迟和完整 Provider Usage。价格仅集中配置；Monitoring additive nullable JSON。React 复用 Radix Dialog / 原组件，不增加框架或状态库。架构 HTML 与 PNG 同步。


## 运行时

React/Vite + FastAPI + SQLite + 本地 BGE/FAISS，复用已有八个一级工作区。动态文档清单与 Embedding 主题配额；文档 ID、Chunk ID、原文必需，产品／章节可选。原四 PDF 仅示例。

## 主链与事务

Golden（Mini 20／Medium 50／Full 100）→ Gate 1 人工确认并冻结 → Baseline 报告／门禁／逐题诊断 → Tuning A/B/C Sandbox → Gate 2 报告确认并选择赢家 → D 决策／重评 → Gate 3 人工发布 → 问答试验。

只有 Tuning 是 Agent。Generation、QC、Evaluation 是受控工作流；编辑和替换复用 Revision JSON、哈希与后台线程。采用替换才原子切换活动题映射，历史不删除。Gate 1 原子保存审核和不可变 Golden Version。

Baseline/A/B/C/D 共用冻结 Golden、Judge、逐题评测器。新 Run 保存 Profile 计数、Hard Validation 逐项检查与 Probe 审计；历史缺失字段不推断。Baseline 页面按持久化 Snapshot、配置、逐题结果和相同聚合公式解释 Gate。12 次启动预算含失败并为 D 留一次；SQLite 写锁防并发超支。Gate 2 等已启动评测全部终结。D 合并实测有效配置差异，冲突保留赢家，新组合完整重评；无新增失败且有实际修复才替代赢家。Gate 3 重验报告／D 决策、Sandbox、11 Gate 与 Regression，同事务写 Human Release 及 Version Snapshot。

Monitoring、版本历史和回滚是辅助能力。重启不假称线程仍在执行：运行标为中断／失败，审计和已消费预算保留。

八个现有 Hash 工作区共用只读 Lifecycle 导航。`GET /api/pipeline` 汇总活动版本、最近 Baseline、索引信息和 `policy.py` 冻结 Search Space；`POST /api/preview/scheme` 只按已保存 Baseline、Candidate 或 Production Version ID 解析配置，不接收客户端配置。该预览由人主动触发，历史逐题 Evaluation 仍从保存的 Run 读取。

## Provider 与证据

DeepSeek 只经后端显式调用，密钥不返回前端。检索是 Vector/BM25 Hybrid + 可选 Lightweight Rerank，不是独立重排模型。Provider 错误不伪装为质量结论；Legacy、Fixture 与真实生命周期分别报告。

[业务图源](架构/业务流程图.html) 与 [技术图源](架构/技术架构图.html) 是唯一可编辑图源，PNG 从对应 HTML 导出。


## 2026-10-11 统一评测与受控优化

当前产品合同见 docs/RAG_SELF_EVOLUTION_SPEC.md 文首。Child命中指标与最终Parent证据充分性分开；统一Judge读取完整证据，Baseline/A/B/C/D冻结同评测身份。旧实验保留只读，历史答案回放不成为正式Baseline或发布依据。新目标修复/附带改善/新增失败分开，程序推荐Winner，Gate2人工确认；有效来源下D最多一次授权LLM建议，经程序校验后另行授权Sandbox。Gate3及兼容配置回滚仍由人工执行。图形表达设计，离线验收不证明真实Provider效果。

## 2026-10-14 自动诊断与版本边界

Baseline全部Bad Case → 既有诊断模块（实际回答、Golden、当前Corpus及Child/Parent/Trace、同一次Judge）→ 真实RAG失败 / 评测机制问题 / 证据不足 → Agent全量背景、仅证据合格目标 → 单一干预候选 → 同新版身份Sandbox/Regression → 原Gate2/3。评测问题不驱动RAG调参；分析不新增审批。旧Run和成绩只读，跨规则比较被身份守卫拒绝。正式图仍唯一来源于KnowledgeDiagrams.tsx；本轮不运行Provider或实验。


2026-10-14最终机制收口：业务层与Agent决策移除诊断可信度分类；四类根因由实际失败证据决定。普通事实行为失败与真实安全违规分离，主体正确但附加流程范围未闭合只作评测核验缺口。原Judge、Matcher、Trace、历史诊断与Regression阻断继续审计；新版单Judge条件资料引用按实际来源身份验证，正式Baseline/Sandbox不得跨身份比较。三个Human Gate职责不变。
