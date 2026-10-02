# RAG Evolution 平台架构说明

> **V1.4 目标架构 · 2026-09-30**。唯一目标规则见 [SPEC](../docs/RAG_SELF_EVOLUTION_SPEC.md)。本轮按用户批准的完整计划实施业务代码；分阶段证据见 [实施验收](../docs/V1_4_IMPLEMENTATION_VERIFICATION.md)，真实 Provider 未重跑。代码、active 产物与真实数据验收分开；既有数据来源见 [Current Demo Truth](../docs/CURRENT_DEMO_TRUTH.md)。

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

11 Hard Gates、固定 Regression、12 次 Sandbox 总预算、Gate 1/2/3、条件 D、人审发布/回滚与失效判断沿用 SPEC。Search Space 读取当前注册表，不抄朋友数字；Lightweight Rerank 不称独立模型。机器 QC P0 按用户决定可经明确人工理由接受；确定性证据错误、Fake Negative、数量错误、执行失败不可豁免，见 SPEC 4.2。

现有接口包括 `/api/evaluation`、`/api/optimization`、`/api/pipeline`、`/api/governance/generation-runs/from-pool`、`/api/monitoring/triggers/{trigger_id}/confirm`、`/api/experiments/run`、Candidate Sandbox/发布与版本回滚。新增 `POST /api/governance/coverage-preview` 与 `POST /api/governance/generation-runs/from-pool/preview` 已注册并在隔离测试验证；生成/Pool 提交可选 plan_id，省略也须建立当前 Plan。双层 trace、校验与价格版本为兼容追加字段，详见实施验收契约。

## 实现与运行证据的边界

- Current Baseline resolver、Experiment 强绑定、Monitoring Confirm 幂等 / Round 0 首轮和 A/B/C 原子保存已通过隔离回归及代码复审。Production 独立保留来源。
- V2 Dynamic K-means、小簇合并、主题 Slot、统一 Validator 和最大二分匹配已实施；Preview 复用既有 FAISS 向量。旧 Frozen Snapshot 仍为 Legacy/V1，不补造 Plan。
- Candidate Recall 与 Final Context、Raw Parsed Full-text 引擎与完整 bundle 校验已实施。检索执行错误不可当零召回，未知负向结论不可当通过。真实旧后端进程仍运行，真实 4 PDF/157 页备份 Staging 已完成兼容校验，原 252 Chunk/FAISS 字节不变；本轮尚未激活到真实 Corpus。
- 价格/Usage/Timing 版本化与明确缺失原因已实施，真实 TTFT 无采集不以 Total 代替；没有验证节假日数据时不能对工作日高峰精确估价。
- 全部 V1.4 UI 和完整隔离 HTTP 生命周期已实施，105 项前端、286 项后端、构建与 Chromium 四尺寸 187 检查通过，阶段复审已通过，最终整体审查中。54 ID 具名断言与最终结论见实施报告，历史 Phase 1 数字不能转记为本轮通过。

两图保持“V1.4 目标架构”标注，完整流程与职责没有因静态重绘升级历史数据。本轮保留图源和 PNG，已验证字体、边界、连线、尺寸与图源/PNG 像素一致；最终代码职责核对见实施验收。用户手动上传到 Demo 的架构图片为独立运行资产，未替换。
