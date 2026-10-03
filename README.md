# RAG Evolution

面向企业知识问答的评测驱动 RAG 质量运营与版本决策 Demo。

**唯一当前目标规格：[SPEC V1.4](docs/RAG_SELF_EVOLUTION_SPEC.md)**（业务规则冻结 2026-09-30；Interview Demo UI 修订 2026-10-03）。本轮按 20–30 分钟 AI 解决方案 / AI 产品经理面试重排八个页面，验证与剩余问题见 [Interview Demo 验收](docs/INTERVIEW_DEMO_VERIFICATION.md)，演示路径见 [面试 Runbook](docs/INTERVIEW_DEMO_RUNBOOK.md)。[SPEC ChangeLog](docs/SPEC_CHANGELOG.md) 记录历史；真实已保存来源见 [Current Demo Truth](docs/CURRENT_DEMO_TRUTH.md)。前轮 [V1.4 业务实施验收](docs/V1_4_IMPLEMENTATION_VERIFICATION.md) 和 [Phase 1 报告](docs/PHASE1_VERIFICATION.md) 保留其日期与运行边界，不能替代本轮 UI 验收。

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

## Interview Demo 产品叙事（2026-10-03）

每个页面只回答当前阶段的问题：知识库技术选型 → Pipeline 的 Frozen / Agent Search Space → Golden 稳定评测基准 → Baseline 的 Hard Gate / Bad Case → 根因与受控 A/B/C 实验 → Sandbox / Regression 与条件 D → 人工发布 → 同题真实问答差异 → Monitoring 下一轮。只有概览保留全局闭环；其他页面删除重复 Stepper、流程图、大 KPI 与发布流水线。

主结论优先，文档/Evidence/Case/Search Space/完整配置/高级指标进入统一右侧 Drawer（标准 560px、wide 800px，移动端全宽）。Sandbox 主表聚焦 Hard Gate、Bad Case、Regression、Qualification；A/B/C 统一 WHY / CHANGE / RESULT，D 独立说明组合失败为何保留 Winner。当前真实根因为 Generation 6 / Safety 1，不借示例虚构 Retrieval 失败。

方案对比固定正式 Baseline 对实际 active、人工已发布 Production，不提供任意方案选择器或 Qualified Candidate fallback，删除历史评测 UI/GET/缓存。Bad Case 选择后填入可编辑问题，只有主动点击才运行实时对比；答案双栏为重点。问答验证 Tab 顺序为问答验证 → 方案对比 → Monitoring。Input/Output Tokens 与费用分开；真实 0/false 保留，估算只使用完整 Usage 与冻结价格币种（当前 USD），缺历史计费依据不回算。

本轮业务与真实数据保护边界不变；唯一后端补充为现有 `GET /api/pipeline` 的实际索引 `dimension/indexed_count` 可空只读字段，不重建 FAISS、不调用真实 Provider。20–30 分钟完整讲解及现场手动调用边界见 [Runbook](docs/INTERVIEW_DEMO_RUNBOOK.md)。

## 目标架构（V1.4）

两张图依据最新设计从头生成，表达目标职责与数据流，不证明当前 Demo 已具备全部新能力。

![V1.4 RAG Evolution 业务架构图](架构/业务流程图.png)

![V1.4 RAG Evolution 技术架构图](架构/技术架构图.png)

可编辑图源：[业务架构 HTML](架构/业务流程图.html) · [技术架构 HTML](架构/技术架构图.html)。模块边界及现有/目标差异见 [平台架构说明](架构/RAG自进化平台架构说明.md)。PNG 为 2560×1440；HTML 内嵌 SVG，可独立浏览。

## 本地启动与恢复

前置条件：Python 3.10+、Node.js 20+、npm。保留现有启动入口：

```bash
./start.sh
```

前端：[http://127.0.0.1:5174](http://127.0.0.1:5174)；API 文档：[http://127.0.0.1:8010/docs](http://127.0.0.1:8010/docs)。已有后台服务重启后先检查端口/PID/目录，避免另开重复进程；本次不启动或重启服务。

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

以下三项是 V1.4 实施及离线验收后的手动验证清单，本次未执行：

1. 手动运行一次 Baseline vs Production 实时问答对比，查看真实回答、证据、Usage、Latency 与成本缺失原因。
2. Production QA → 人工判 Bad Case → Confirm Trigger → 手动启动首轮 Agent；可能创建实验并耗用 Provider/预算，不自动 Sandbox 或发布。
3. 运行 V2 Planner Preview，核对动态 K、小簇合并与 Slot，不接着自动生成 Golden。

若要将当前演示数据称为 V2，需要另行生成、人工审核并冻结 V2 Golden，然后在同一新 Snapshot 上执行 Baseline/实验与验证。未批准的 Seed / Legacy 候选不能冒充正式 Golden；当前正式 Legacy Snapshot 保留已有的人审资格与历史实测结果。Fixture / 离线 Stub 不能冒充真实 Provider 结果。

## 验证入口

隔离后端测试：`python3 scripts/test_v14_offline.py`；`cd frontend && npm test && npm run build`。测试必须使用隔离 DB/Stub，不消耗真实 Provider 配额；`scripts/test_phase1_ui.mjs` 仅允许隔离 :5180/:8011。

本轮 UI 与只读数据保护结果见 [Interview Demo 验收](docs/INTERVIEW_DEMO_VERIFICATION.md)；前轮业务代码结果见 [V1.4 实施验收](docs/V1_4_IMPLEMENTATION_VERIFICATION.md)，之前的文档/图交付记录见 [同步验收](docs/V1_4_DOCS_SYNC_VERIFICATION.md)。历史或 Stub 结果不代表真实 Provider 重跑。
