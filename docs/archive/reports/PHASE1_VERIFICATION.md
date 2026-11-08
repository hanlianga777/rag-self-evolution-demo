# Phase 1 验收与交付记录

审计日期：2026-09-30（Asia/Shanghai）。主提示词与 SPEC V1.3 为产品依据；ponytail full，复用现有技术栈、八个导航及治理接口。当前保存的真实 Demo 事实见 [Current Demo Truth](CURRENT_DEMO_TRUTH.md)，逐表数据证明见 [PHASE1_DATA_PROOF.json](PHASE1_DATA_PROOF.json)。

## A–G 实施与验证

| 阶段 | 本轮实现 | 验证依据 |
|---|---|---|
| A：基线与参考 | 备份真实库；区分当前与 Historical；截图只作为产品表达参考 | 当前 Truth、朋友对齐矩阵、原始指纹与索引清单 |
| B：Golden | 原始 Coverage 与冻结覆盖分开；独立构造题型；CSV/XLSX 预览/确认；统一来源候选池及按配额复制新 Run | 字段/证据/重复项/XLSX 测试；Mini 8/4/8、候选副本、QC Pending、禁止未审核冻结；已有各 Profile 与治理测试 |
| C：共享 UI | Select 关闭与键盘；长文 Tooltip；标签 +N；固定表格；共享 Drawer；StageStepper | component tests、三尺寸 E2E、详情关闭焦点恢复 |
| D：Baseline/Tuning/Release | Gate 失败与贡献详情；真实案例诊断；Agent 案例/技术详情；稳定 ABC；D 保留 C；Sandbox 状态；发布配置差异 | 现有业务回归、页面/内部 Tabs、候选等高与详情检查 |
| E：QA/Monitoring | 保存配置直接比较；版本化 session 状态；禁止同源同配置自比；证据 Drawer 不改路由；事件实际信号与人工边界 | 单元与 Fixture E2E：返回恢复结果、不重复请求、证据路由不变、人工触发测试 |
| F：耗时/Usage/兼容 | 实际执行点计时、单调时钟；回答/Judge 分离；完整 Usage、可选集中价格；可空 metrics 列；显式 INSERT 列名 | 实际执行路径使用 Mock Provider 的测试、价格缺失/部分 Usage、Fresh/旧列序/idempotent migration |
| G：收口 | 中文界面术语、SPEC/README/交接/上下文/架构同步、数据证明、最终测试与 Git 交付 | 下列验收及 Git 提交记录 |

Fact 要求显式属性值，Aggregation 要求完整事实与穷举答案，Bridge 要求共享实体与两段共同证据；可靠事实/聚合正向槽位确定性生成，不足回普通槽位。Bridge 复用现有结构选择及支持性校验，没有新增知识图谱。历史冻结题不补题型。导入题复用 Hard Validation → Probe → QC → 人工审核 → Gate 1，确认导入只写候选；新 Run 不继承审批。未新增第二套 Golden 系统。

## 测试与浏览器

- 后端：`cd backend && python3 -m unittest discover -s tests`，**229 tests，OK**。所有 API 测试入口在临时库初始化；业务写入使用 Fresh DB/副本。Python 3.14 的既有 ResourceWarning / SWIG DeprecationWarning 不影响测试结果。
- 前端：`cd frontend && npm test`，**16 files / 89 tests passed**；`npm run build` 成功。
- 隔离 E2E：`scripts/test_phase1_ui.mjs`，仅允许 :5180 前端/:8011 副本 API。**73 项路由/内部 Tab/尺寸检查通过**，1536×1024、1440×900、390×844 均无 document 横向溢出；Console error 为 0。额外验证候选等高、Drawer 边界/可见关闭按钮/恢复焦点、Select、QA 配置与状态恢复、证据、导入与混合副本。Radix 延后触发关闭自动焦点，测试等待该事件完成后断言。
- QA 模型回答采用明确标识的 **Fixture**；导入/混合 Run 的真实写入仅在副本。Fixture 不能作为 DeepSeek 实际生命周期验收。
- 真实 :5174/:8010 仅只读检查当前保存状态、配置差异与错误日志；没有执行 Golden、Baseline、A/B/C/D、人工 Gate、发布或真实模型 QA。Provider 仍为 Configured (Unverified)。
- `git diff --check` 通过。截图及运行日志位于本地 `output/playwright/` 与 `/tmp/rag-phase1-20260930/`，不提交测试副本或用户数据库。

## 数据安全证明

真实库修改前 SHA-256：`7dee55b5eca5779c6b07f85a5256a4f53f9fd39f95fc87112d5f0ae9a99e6784`；修改后：`f4e3dc728c95620bb060dedfbd77e0edc3e094a08f6ea73e5b40a8ba2694a5df`。大小均为 6037504 bytes。SQLite 备份重新布局后的文件哈希不同，证明中另存 original_database_before，不能把备份哈希误当原始文件哈希。

`verify_phase1_data.py` 对比 **25 张表所有原有字段/记录**，全部相等；仅允许 `monitoring_events.metrics_json` 可空新增列与 `phase1-monitoring-metrics` 迁移登记。历史 metrics 全为 NULL。审批、Snapshot、Baseline、A/B/C/D、Production 原记录不变；documents/manifest/chunks/FAISS 四个索引文件哈希不变。副本迁移重复执行通过，旧 questions 列顺序不同也通过显式列名 INSERT 回归。最终测试后再次比对通过。

迁移时序偏差：原有测试模块在收集时导入 `app.main`，初始化默认真实库，提前应用了本轮已授权的 additive migration。发现后把所有这些入口统一改为临时库 `tests/api_fixture.py`；随后全量测试与逐字段比对证明没有真实业务记录改写。该问题已告知用户并保留审计记录。

## 耗时、费用与历史边界

未来实际 Query Processing、Retrieval（含 Vector/BM25/Hybrid 子阶段）、可选 Rerank、Context Build、Generation/Judge 保存实际阶段与 Usage。子阶段不重复累计；不显示未执行阶段；原回答 P50/P99 Gate 口径不变。历史只有已保存回答延迟/TTFT 与输入输出 Token，阶段、完整 Usage 与费用显示“未采集”。

`RAG_PRICE_CONFIG` 指向集中 JSON，要求 model/currency/source/effective_date/cache_billing 与三种每百万 Token 单价。默认没有价格；完整 Provider 计数不足或模型不匹配不估价；未来费用保留当次依据。没有查入当前价格或计算历史费用。

## Impact Check

SPEC V1.3、SPEC_CHANGELOG、README、CHANGELOG、CODEX_HANDOFF、PROJECT_CONTEXT、DECISIONS、TODO、ARCHITECTURE、朋友对齐矩阵、Current Truth 已同步。业务/技术架构 HTML、PNG 与架构说明已同步导入/候选池/Profiling；用户已上传的架构图片为独立手动资产，保留原文件。历史 V1.2 文档与结果标注 Historical/Legacy，不覆盖当前状态。前后端兼容已有 API 字段、JSON 存储、治理阈值与人工边界；唯一新增后端依赖 openpyxl，没有新前端库。

Git 提交包含实现、测试与本报告；最终 Commit Hash、origin/main 同步和 clean 状态以交付回复及仓库提交记录为准。
