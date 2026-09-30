# RAG Evolution 平台架构说明

> **V1.4 目标架构 · 2026-09-30**。唯一目标规则见 [SPEC](../docs/RAG_SELF_EVOLUTION_SPEC.md)。本次仅同步文档并从头重绘两图，没有升级业务代码或运行真实 Provider。当前实现差异见 SPEC 第 3 节；既有数据来源见 [Current Demo Truth](../docs/CURRENT_DEMO_TRUTH.md)。

![V1.4 业务架构图](业务流程图.png)

![V1.4 技术架构图](技术架构图.png)

图源：[业务架构 HTML](业务流程图.html) · [技术架构 HTML](技术架构图.html)。两者均为内嵌 SVG 的自包含 HTML；PNG 为 2560×1440。文件名保留用于兼容 README，图的内容、结构、布局和连线依据最新需求重新生成。

## 业务架构：可信测量 → 可解释优化 → 人工发布与反馈

### 可信测量

知识库准备文档、解析/OCR、Chunk 与现有向量。Golden V2 在离线侧复用向量进行 Dynamic K-means、小簇合并、按厚度分配 Slot 与材料复用审计。Profile 是 Mini 20=8/4/8、Medium 49=20/9/20、Full 98=40/18/40；Evaluation Group 是 Positive/Ablation/Negative，Construction Type 是 Fact/Aggregation/Bridge/Ordinary，两个维度不互相替代。

AI 生成与 CSV/XLSX 业务导入进入统一候选池。Pool 组卷必须匹配已有 Coverage Plan/Slot，不能只满足题数，不能临时改 Plan 迎合所选题。Hard Validation 确认合法性；Probe 观察真实召回、Final Context 与负向可回答性风险；QC 判断质量；Gate 1 人工确认后冻结 Snapshot。Negative Coverage Anchor 不等于 Golden Evidence；检索难题不能仅因未命中被删掉。

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

11 Hard Gates、固定 Regression、12 次 Sandbox 总预算、Gate 1/2/3、条件 D、人审发布/回滚与失效判断沿用 SPEC。Search Space 读取当前注册表，不抄朋友数字；Lightweight Rerank 不称独立模型。机器 QC P0 的材料冲突见 SPEC `[OPEN-QC-P0]`，本次不改既有行为。

现有接口包括 `/api/evaluation`、`/api/optimization`、`/api/pipeline`、`/api/governance/generation-runs/from-pool`、`/api/monitoring/triggers/{trigger_id}/confirm`、`/api/experiments/run`、Candidate Sandbox/发布与版本回滚。V2 Preview、双层 trace、Plan 匹配和价格版本是目标语义，本图不承诺已存在的新 URL。

## 当前实现与目标的差异

- 当前 Coverage 最多选 4 个代表中心；V2 动态 K、小簇合并和按厚度 Slot 是待实施目标。
- 当前 Pool Run 检查 Profile/证据/构造，Coverage Plan 为空；V2 Slot Matching 待实施。
- 当前 optimization 取最新实验，Monitoring Confirm 取最新 completed Evaluation；强绑定 resolver、排除 Sandbox 和首轮/幂等行为待实施或回归。
- 现有 Probe 保存检索/检查信息；双层召回 trace 和原解析全文 bundle 尚未在本次实现/验收。旧图中的 Chunk 文本检查不能等同 Raw Parsed Full-text。
- 现有 Usage、Timing、可选价格与共享 UI 有 Phase 1 历史证据；V1.4 的全部字段、页面和离线矩阵没有在本次验收。

这两张图表示目标系统如何协作。当前演示 Snapshot 仍保留自己的 V1/Legacy 来源，不因重绘升级成 V2 生成；本次也未改动用户手动上传到 Demo 的独立架构图片。
