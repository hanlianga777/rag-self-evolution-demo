# RAG Evolution 平台架构说明

> 当前正式架构同源于概览页面，2026-10-08同步；唯一规则见[SPEC当前合同](../docs/RAG_SELF_EVOLUTION_SPEC.md)。图表达流程设计，不表达当前阶段已执行；实际Full由用户冻结，新Medium业务V2独立停在人工治理，Legacy Production独立。

2026-10-27：Golden人工或有效Owner委托审核与负责人冻结为独立动作；完整题集审核及当前质量身份满足后Human Gate Ready，负责人再创建Snapshot。模型费用记账不按金额阻断，未知费用先对账；Sandbox次数限制保持。

![当前业务架构](业务流程图.svg)

![当前技术架构](技术架构图.svg)

唯一源：`frontend/src/components/KnowledgeDiagrams.tsx` + Shared CSS；运行 `python3 scripts/export_architecture.py` 从实际页面SVG/Computed Style导出16:9 SVG和2560×1440 PNG，源与产物摘要记录在architecture-manifest.json。旧业务/技术HTML是Historical，不能作为当前正式引用。

处理链为MinerU VLM→Table KV→Parent/Child 1400/400/80→text-embedding-v4 1024d→FAISS；检索链为Query Processing→Vector/BM25→CandidateK→qwen3-rerank→Parent Expand→TopK→DeepSeek。覆盖与Evidence支路保留。只有Optimization Agent是Main Agent。

## 业务架构：可信测量 → 可解释优化 → 人工发布与反馈

### 可信测量

知识库准备文档、解析/OCR、Chunk 与现有向量。Golden V2 在离线侧复用向量进行 Dynamic K-means、小簇合并、按厚度分配 Slot 与材料复用审计。Profile 是 Mini 20=8/4/8、Medium 50=20/10/20、Full 100=40/20/40；Evaluation Group 是 Positive/Ablation/Negative，Construction Type 是 Fact/Aggregation/Bridge/Ordinary，两个维度不互相替代。

Medium business_v2复用当前九Topic与Child材料，先识别用户角色、现场场景和意图，再构造自然业务题；十维Business Quality Audit参与机器资格，缺失/失败不得通过。材料Anchor与真实查询Embedding观察分开，负向Anchor不是Evidence，仍需全文Probe与QC。失败Slot只做有限版本化Revision，最终人工确认不自动执行。

AI 生成与 CSV/XLSX 业务导入进入统一候选池。浏览状态只展示候选/可用/待治理、来源/评测组/质量/搜索及五列题目列表；创建Golden才进入Profile配额与Slot匹配组建状态。Pool 组卷必须匹配已有 Coverage Plan/Slot，不能只满足题数，不能临时改 Plan 迎合所选题。Hard Validation 确认合法性；Probe 观察真实召回、Final Context 与负向可回答性风险；QC 判断质量；Gate 1 人工确认后冻结 Snapshot。Negative Coverage Anchor 不等于 Golden Evidence；检索难题不能仅因未命中被删掉。

### 可解释优化

Current Baseline resolver 解析有效、非 Sandbox 的 Baseline，其 Golden/Corpus/Judge/Gate/配置决定同尺范围。Experiment 强绑定 Baseline；新 Baseline 没实验时显示等待，旧实验只作历史，旧 Production 可继续独立运行。

Baseline 暴露 Failed Gate 和 Bad Case；Optimization Agent 基于可见证据诊断、提出 Hypothesis 和最小必要配置变更，输出 A/B/C。Sandbox 不修改 Production；完整 Golden 与固定 Regression 分别验证，资格先于 Overall。Gate 2 人工确认报告并选合格 Winner；条件 D 合并有实测证据的有效非冲突能力，完整复验，失败/无改进保留 Winner，无有效组合合法跳过。

### 人工发布与反馈

Gate 3 事务内重验来源/资格/Recommendation/D Decision，再由人发布保存 Production Version。版本和回滚保持人工边界。Production QA 与方案对比展示真实回答、证据、耗时及 Usage/Cost，不自动调用额外 Judge。

Monitoring 在问答验证二级 Tab。QA 信号先经人工判定，达到既有阈值形成 Pending Trigger；Human Confirm 创建或复用 Pending Context，由人明确启动 Agent。空 Round 0 不阻断真实首轮，实际已有候选但 Sandbox 未完成的轮次继续阻断下一轮。没有有效 Baseline 时保留 pending 并解释，不用最新 Sandbox 或虚构 Baseline 代替。

## 技术架构：离线治理、在线问答、数据支撑

| 区域 | 目标职责 | 主要输入 / 输出 |
| --- | --- | --- |
| React / FastAPI 接入 | 八个现有工作区、ID 驱动读取、统一异步状态、人工动作与后端约束 | 对象 ID、当前状态、结构化报告；旧异步结果不能覆盖新身份 |
| Golden V2 治理 | Planner / Pool Slot / Unified Validator / Probe / QC | 当前 Corpus、向量、导入候选 → Plan/Slot、候选、检查/风险、人工冻结 Snapshot |
| Evaluation / Optimization | Current Baseline resolver、Bad Case、唯一 Agent、A/B/C、Sandbox / Regression、条件 D | 冻结测量尺与配置 → 可解释诊断、方案、资格、Recommendation、D Decision |
| Release / Monitoring | Gate 2/3、Version、人工 Rollback、QA Event / Trigger / Pending Context | Qualified 方案与人审 → Production；生产反馈 → 经确认的待优化上下文 |
| 在线问答 Runtime | Query Processing → Vector/BM25 Hybrid → 可选 Lightweight Rerank / MinScore → TopK Context → DeepSeek | 明确版本配置 + 同一问题 → Answer / Evidence / 实际调用指标 |
| Corpus 产物 | 现有 Parser/OCR/Section-aware Chunk、BGE/FAISS/BM25、原解析全文 | Staging 全部产物一致校验后原子 Activate；全文含未切成 Chunk 的原文及页定位 |
| SQLite / Telemetry | 不可变 Snapshot、Evaluation/配置/Judge/Gate、Candidate、Version、人审与失败审计；真实 Usage/Timing/价格版本 | 可追踪身份与证据；未知值不计为 0、不回填历史 |

Golden 聚类是离线工艺，Evaluation 不是每次 Production QA 的必经步骤。Candidate Recall 与 Final Context 是同一次真实 pipeline 的两个位置；前者未命中支持检索失败，前者命中而 Final 缺证据支持排序/选择失败，充分 Final 证据后回答错才构成生成失败依据。Any hit 不能替代 Bridge 所需 All hit。

Raw Parsed Full-text Negative Probe → 必要时 Answerability Judge；字面相关不等于能回答，解析不足或 Judge 异常为 uncertain/review。原全文产物和 Chunk/FAISS/manifest 使用一致 Corpus 身份，构建失败不切 active pointer。只新增兼容全文 sidecar 与真实内容变化分开处理，不改写旧 fingerprint。

DeepSeek 是既有 Provider，显式服务于回答、生成、QC、Judge、Agent，不新增模型。Usage 与 Timing 记录真实调用点；价格由集中版本化配置提供，缺模型/价格/Usage/cache 拆分时说明原因。TTFT 是首个真实输出 Token，不能拿 Total 代替；Estimated Cost 是估算，不是账单。

## 不变的治理约束与现有接口

11 Hard Gates、固定 Regression、12 次 Sandbox 总预算、Gate 1/2/3、条件 D、人审发布/回滚与失效判断沿用 SPEC。Search Space 读取当前注册表，不抄朋友数字；Lightweight Rerank 不称独立模型。机器 QC P0 按用户决定可经明确人工理由接受；确定性证据错误、Fake Negative、数量错误、执行失败不可豁免，见 SPEC 4.2。

现有接口包括 `/api/evaluation`、`/api/optimization`、`/api/pipeline`、`/api/governance/generation-runs/from-pool`、`/api/monitoring/triggers/{trigger_id}/confirm`、`/api/experiments/run`、Candidate Sandbox/发布与版本回滚。新增 `POST /api/governance/coverage-preview` 与 `POST /api/governance/generation-runs/from-pool/preview` 已注册并在隔离测试验证；生成/Pool 提交可选 plan_id，省略也须建立当前 Plan。双层 trace、校验与价格版本为兼容追加字段，详见实施验收契约。

## 实现与运行证据的边界

- Current Baseline resolver、Experiment 强绑定、Monitoring Confirm 幂等 / Round 0 首轮和 A/B/C 原子保存已通过隔离回归及代码复审。Production 独立保留来源。
- V2 Dynamic K-means、小簇合并、主题 Slot、统一 Validator 和最大二分匹配已实施；Preview 复用既有 FAISS 向量，Golden 显式手动预览当前 Corpus，与 Run 冻结 Plan 分开。旧 Frozen Snapshot 仍为 Legacy/V1，不补造 Plan。
- Candidate Recall 与 Final Context、Raw Parsed Full-text 引擎与完整 bundle 校验已实施。检索执行错误不可当零召回，未知负向结论不可当通过。真实旧后端进程仍运行，真实 4 PDF/157 页备份 Staging 已完成兼容校验，原 252 Chunk/FAISS 字节不变；本轮尚未激活到真实 Corpus。
- 价格/Usage/Timing 版本化与明确缺失原因已实施，真实 TTFT 无采集不以 Total 代替；没有验证节假日数据时不能对工作日高峰精确估价。
- 全部 V1.4 UI 和完整隔离 HTTP 生命周期已实施，121 项前端、296 项后端、构建与 Chromium 四尺寸 208 检查通过，最终整体审查及一次限定复审通过，保留换材重新生成后的关闭提示 Minor。54 ID 具名断言与最终结论见实施报告，历史 Phase 1 数字不能转记为本轮通过。

两图保持“V1.4 目标架构”标注，完整流程与职责没有因静态重绘升级历史数据。本轮保留图源和 PNG，已验证字体、边界、连线、尺寸与图源/PNG 像素一致；最终代码职责核对见实施验收。用户手动上传到 Demo 的架构图片为独立运行资产，未替换。

## 2026-10-08 Medium V2集中收口

本轮39题受控Revision与只读数据集诊断复用已有Candidate→Hard Validation→Probe→QC→人工Gate关系。自然度诊断是高级审计建议，不是新增Gate；用户确认、Snapshot、Baseline、Agent、Production边界不变。唯一KnowledgeDiagrams.tsx图形源和导出SVG/PNG关系无变化，不重新导出。实际结果见[集中收口验收](../docs/MEDIUM_V2_POLISH_VERIFICATION.md)。


## 2026-10-11 统一评测与受控优化

当前产品合同见 docs/RAG_SELF_EVOLUTION_SPEC.md 文首。Child命中指标与最终Parent证据充分性分开；统一Judge读取完整证据，Baseline/A/B/C/D冻结同评测身份。旧实验保留只读，历史答案回放不成为正式Baseline或发布依据。新目标修复/附带改善/新增失败分开，程序推荐Winner，Gate2人工确认；有效来源下D最多一次授权LLM建议，经程序校验后另行授权Sandbox。Gate3及兼容配置回滚仍由人工执行。图形表达设计，离线验收不证明真实Provider效果。

## Evaluation运行保护补充（2026-10-12）

共享Evaluation模块内部增加逐题检查点与失败阶段/Usage记录；同身份手动续跑使用独立子Run，复用已保存案例和生成上下文，不覆盖历史。复用既有SQLite JSON与API，不新增调度器、Provider或Judge，组件边界和正式图连线不变，因此图源及导出图不变。请求等待配置与冻结评分/性能Gate分离。细则见[Baseline稳定性报告](../docs/BASELINE_STABILITY.md)。

Candidate Sandbox复用同一检查点/子Run路径，预约与预算、身份、Run关联原子保存；人工续跑仅补未保存步骤。浏览器共享Operation在单项未完整结束时暂停后续候选，人工再次点击才继续。仍使用既有SQLite JSON、单候选API及Evaluation模块，不新增调度器或改变图形边界，图源与导出产物不变。见[Candidate恢复验收](../docs/CANDIDATE_SANDBOX_RECOVERY.md)。


## 2026-10-14 当前诊断与历史对象生命周期

组件边界仍为同一个Evaluation/Optimization/SQLite模块。正式图A/B/C表示最多3个有据候选，允许不足；每个候选及D的参数方向与Trace由程序校验。Matcher确定定位及结构合同，Judge判断语义，Policy保守阻断与计算11 Gate/Regression；正式阻断和结构化确证分列，语义争议不变成第五个调参方向。生成共享文档身份和逐Chunk章节/页码/全文，避免把Trace元数据误认为模型原来已经收到的信息。

SQLite历史管理以对象依赖闭包保留，非引用历史实验/评测各50，活动/当前/发布及恢复链保护，不对Case/Trace机械限行。此次用户授权重新开始将旧发布依赖迁为无资格bootstrap配置后事务清空；唯一备份与审计在库外保留。清理标记只解除旧Golden绑定，不豁免Corpus State/索引身份。上述流程不声明真实模型已改善或人工Gate已通过。

## 2026-10-14 Mini业务治理适配

Mini显式Business V2保留现有8/4/8、动态Topic及Slot产品/子型要求，通用业务选材后据真实材料确定Construction，专项无支持在新Plan记录Ordinary fallback，复用Medium的业务Prompt与十维审计链。限定Run/Corpus/Plan/Profile的所有者委托AI逐题审核复用原事务与实际PDF核验；只有真实全部合格才冻结。流程节点无新增，正式图继续同源；实际结果见Mini20验收文档，不预设通过。

负向十维审计保持材料Anchor身份，必要时显式追加最多3个当前同产品Child作为审计输入上下文，保存来源ID/Corpus；默认不扩张，不改Golden Evidence，也不发送整个Corpus。原Probe全文/向量边界与QC不降级。


2026-10-14：全部Bad Case进入原诊断与Agent背景，证据充分的真实RAG失败才进入单一干预目标；评测规则问题、证据不足单独保留，不新增Human Gate。后续正式Baseline/Sandbox须统一新版Evaluation Identity；历史结果只读。


2026-10-14机制最终收口：全量Bad Case事实核查→四类技术归因→证据支持的单一干预，不使用诊断可信度标签准入。来源范围核验缺口不驱动RAG调参；旧状态只在高级审计保留。普通业务错误与安全失败分离，所有正式比较继续冻结同一Evaluation Identity，原三个人工Gate保持。图源流程关系不变，无新增独立工作台。
