# Baseline 与 Agent 工作台恢复验收（2026-10-09）

本报告对应用户 Markdown 任务书和已批准实施计划。Ponytail full：复用现有技术栈、组件与 API，完整恢复信息结构。真实状态与隔离 Fixture 分开；历史截图数值没有写入产品。

## A. Git / 环境

实施基线 main `88252aca1dcc63d2e1a160f6a6529784e9b66151`，开始时工作区干净。Node/Vite/React 与 Python/FastAPI/SQLite 保持原栈，无新增依赖、调度器、业务表或批执行接口。最终 Commit/Push 记录由交付消息及 `git log` 确认；该报告与产品代码同次提交。

## B. 已读资料 / 审计矩阵

主依据：桌面 `RAG_自进化_Demo_Baseline_Agent_UI_还原与产品逻辑优化_Codex总提示词.md`、当前 SPEC 文首、AGENTS、真实代码/API/持久化数据。全部九张主 UI 图实际打开；朋友产品包 34 图、视频截图包 22 图完整解压并选取实际图片观察，不把朋友项目结果当本项目证据。`HANDOFF.md` 未找到，列资料缺项。

| 审计对象 | 现状 / 风险 | 本次精准处理 | 冻结边界 |
|---|---|---|---|
| EvaluationPage / Shared CSS | 摘要弱、配置固定高、Bad Case td 自身被 line-clamp 改成 box | 四阶段/三摘要/来源/紧凑配置；独立表宽；保留 table-cell | 评分、11 Gate、历史结果不变 |
| CaseDetails / RetrievalEvidence | 证据与业务问题层级 | 期望与实际 → Golden → 候选/最终 → Judge → 初步判断 | Negative Anchor 不作为答案 Evidence |
| EvolutionPage | 缺完整计划，生成态空，历史 null | 六阶段、分组、实验概览/三列 Plan、六项 Candidate、目标 Drawer | 仅真实保存假设/参数/引用 |
| OperationProvider | 单项 API 已有，批执行缺失 | 浏览器生命周期串行；重复点击保护；运行失败独立 | 每项重验身份/状态/预算/Gate2，中断停止 |
| governance.reserve_candidate_run | 预约后身份竞态 | 同事务当前 Baseline/Experiment/状态/预算/报告冻结重验 | Direct Release 既有人工流程兼容 |
| EvaluationRunner | 失败标签顺序决定 Primary | 后续运行安全优先、证据支持方向、未知保留 | 不改 Failure Tags/分数/历史 Primary |
| Sandbox / D | 核心修复/新增失败不清晰 | 六行、Regression 说明、高级下沉、D 左右决策 | 资格、D 预留及晋升规则不变 |
| Versions / Experiment | 来源/配置变化弱 | 人审/推荐/谱系/历史；双版本配置/双答案/Evidence | 当前 active Production 独立于新 Baseline |
| KnowledgeDiagrams / 架构 | 模块/业务箭头未受影响 | 核对唯一图源，未产生新图或新流程 | 不另画或无理由导出不同版本 |

九图唯一对照按画面内容建立，时间戳仅用于定位原文件：

| 图 | 原图时间戳 | 内容 | 新页面 / 验收图后缀 | 继承 / 修正 |
|---|---|---|---|---|
| R01 | 22_17_58 | Baseline 报告 | `baseline-report` | 四组配置、组成、性能；真实 11/11 与 20 问题双结论 |
| R02 | 22_18_31 | Hard Gate | `gates` | 11 行及关联题，聚合门槛不掩盖逐题失败 |
| R03 | 22_18_39 | Bad Case | `cases`、`case-drawer` | 宽业务问题列、观察与证据层级 |
| R04 | 22_18_48 | Agent 诊断 | `evolution` | 问题分组/占比/代表案例/真实方向 |
| R05 | 22_18_59 | 优化 Agent | `agent-plan` | 概览、短诊断、三列 Experiment Plan |
| R06 | 22_19_09 | Candidate 与 D | `abc`、`candidate-drawer`、`D-Fixture` | 六项完整计划、同 Baseline 差异、条件组合 |
| R07 | 22_19_17 | Sandbox | `sandbox-wait`、`sandbox-Fixture` | 六核心行与资格；已评测图明确 Fixture |
| R08 | 22_19_26 | 发布 | `versions` | 来源/人审/配置变化/版本历史；旧 Production 不冒充新 Winner |
| R09 | 22_22_06 | 问答对比 | `compare-wait`、`compare-Fixture` | Baseline / active Production、同题双侧、真实版本身份 |

## C. Baseline

验收时当前保存 Golden `GD-20261008135532677480`，Medium 50（20/10/20）；Baseline `EVAL-20261008135547421930` completed，11/11 Gate、20 Bad Case。当前持久化 Overall 仅比较，不作资格覆盖。显示“整体达标，仍有 20 个单题问题”，不宣称无问题。页面数值从 API 读取。

报告展示 Judge、规则、配置来源与本地时间。Case Drawer 首屏是问题和期望/实际，后续是 Golden 与检索链、Judge、已存归因。Negative 材料 Anchor 独立标注。历史缺 usage/cost/trace 时显示未采集；没有回算或假 0。逐题 Judge 正确性 0–4 在主表按对应百分比展示，历史百分数不二次缩放，仅展示换算，不改成绩。

## D. Agent

当前实验 `EXP-20261008141549298005` 第 1 轮 A/B/C generated，预算 0/12，D 预留 1。真实方案展示 WHY/TARGET/CHANGE/EXPECTED/RISK/RESULT；历史无 EXPECTED 仅按保存假设标注“预期（据保存假设）”。目标引用只匹配本 Baseline 问题，可打开真实详情。

“运行本轮”由共享 Operation 串行复用 `/api/candidates/{id}/run`，前后持久化状态作权威。已评测/failed 不隐式重跑；普通失败保留并继续合法剩余项；身份、预算、Gate2、请求不确定或服务器 interrupted 立即停止。刷新后未启动项需显式再次点击。生成下一轮失败明确阻断，不用旧候选掩盖失败。

## E. Sandbox / Regression / Gate 2 / D

核心表六行：Gate、Bad Case、修复原问题、新增失败、Regression、资格。`target_bad_cases_fixed` 实际统计所有原失败题修复，标为“原问题”，不冒充目标题修复；目标题数单独展示。新增严重上限 0、普通上限 1；实际缺失不得伪填。

Gate2 只在 A/B/C 都结束且存在合格候选时提供人工确认。D 保留条件组合、无有效组合合法跳过、失败/打平保留 Winner，以及完整评测/资格后晋升既有规则。展示已评测/D 状态使用明确标注 Fixture 验收，真实本轮仍未评测。

## F. 发布 / 问答

active Production 仍为 `production-20260928080518`，有独立 Legacy 来源；新实验没有被批准或发布。发布页面展示保存推荐、人审、配置变化、历史；无合格推荐不可发布。所有审批、冻结、Gate2、D 与发布仍由用户显式执行。

方案对比使用正式 Baseline 与 active Production 两个保存配置，回答仅来自主动运行；本次浏览器双答案为 Fixture Stub，带可见标签，未真实调用问答。组件测试覆盖单侧失败保留另一侧、身份切换及迟到响应拒绝。Evidence 点击复用已有来源入口。

## G. 真实数据保护

Phase 0 SQLite Backup API 备份：`output/playwright/baseline-agent-restoration/business-backup.db`，完整性检查通过。`data-before.json` / `data-after.json` 保存 29 表行数/内容摘要和 23 个 Corpus/索引/产物文件 SHA-256。最终核对 **29/29 表、23/23 文件摘要一致**，无新增删除/修改；对 SQLite Backup 的逐行集合核对也一致。

GET/API Smoke 使用备份的临时 SQLite 与解引用复制的 Corpus/索引/PDF/上传资源，导入 app 前隔离空 `.env` 并清空 Provider key；不运行 lifespan。进程内 TestClient，TCP 封禁。捕获证明 `browser/capture-proof.json`。后端全量测试另用明确 Legacy 离线 Fixture，不能作为当前 Knowledge 或 Provider 验收。

浏览器全部 API locally fulfill，禁止真实后端 fallback 和业务写入。真实付费调用 **0**；真实 Baseline/Sandbox/QA/批准/发布次数 **0**。保护证据不含凭据、不提交数据库和完整私有 payloads 到 Git。

## H. 验证 / 场景矩阵

后端 **367/367** 通过（394.919 秒，完整日志 `backend-offline-tests.log`）；前端 **182/182** 通过（33 文件），TypeScript 与 Vite Build 通过，`git diff --check` 通过。API Smoke 捕获 **278** 个只读路径，符合既有200/允许的404/409合同，未执行生命周期。独立只读审查发现的三项问题均修复并通过回归。

截图结果记录于最终交付证据，复现命令：

```sh
python3 scripts/test_v14_offline.py
cd frontend
npm test
npm run build
cd ..
python3 scripts/capture_interview_payloads.py --backup output/playwright/baseline-agent-restoration/business-backup.db --output output/playwright/baseline-agent-restoration/browser
# Vite 隔离端口 5180，VITE_API_BASE_URL=http://127.0.0.1:8011
python3 scripts/test_restoration_browser.py
python3 scripts/verify_restoration_data.py
git diff --check
```

| 任务书场景 | 证据 / 验证边界 |
|---|---|
| BL01/02/05/06/11 | 原有 v14、UI Contract + restoration 组件覆盖未运行/运行/零问题/失效/缺失；不重新运行真实库 |
| BL03 | 当前真实保存 11/11 +20 Bad Case 的四尺寸截图 |
| BL04/08 | 旧/新组件失败 Gate 与逐题穿透；真实 11 行截图 |
| BL07/09/10 | 四尺寸几何、筛选、Case Drawer、真实保存 Evidence；正常桌面无主体溢出/竖排 |
| AG01–04 | 当前真实 generated 截图 + agent-restoration 测试，完整 Plan/六项/等待态/null 清理 |
| AG05/06/14/15 | sandbox-batch 与后端 restoration 并发/重复/预算/D保留/身份测试；Stub，不付费 |
| AG07–09 | 既有 v12 tuning/flow 与报告反馈；失败生成不被上一轮覆盖；新配置仍走冻结去重 |
| AG10–13 | v14 UI Contract、v12 frozen promotion / recommendation / D 失败与跳过；Synthetic D 图明确 Fixture |
| RL01–04 | 既有版本测试及 restoration-release，发布资格、人审与回滚确认；真实只读发布图 |
| QA01–05 | 既有 experiment-schemes/interview-release + restored双配置组件，单侧失败/身份/Monitoring；浏览器答案 Fixture |

最终 Chromium **92/92 项检查通过，84 张截图**，控制台/页面错误、未捕获请求、意外写入均为0。首次大体积历史快照编码下有等待超时，测试改为缓存编码并延长初次加载窗口；没有以该超时宣称产品已通过，最终完整重跑通过。

四尺寸：1536×960、1440×900、1366×768、390×844。八一级页面和各主要 Tab 截图；核心页面检查文档溢出与桌面表格列宽，Drawer 唯一 800px/手机100vw、右边缘、关闭命中、焦点进入/捕获/返回、Escape、背景锁与单Body滚动。截图、JSON 存 `output/playwright/baseline-agent-restoration/browser/`；Fixture 文件名与底栏均标注。

## I. SPEC 覆盖

SPEC 文首新增 2026-10-09 UI 覆盖：恢复阶段条、完整计划、六项卡片及六行 Sandbox，不受旧“删减主层”展示条款约束。Shared Token/PageShell/Select/800px Drawer 保持。未来归因和预约事务的真实行为同步 SPEC/Changelog/README；历史说明保留。架构图无模块/流向变更，唯一图源未另画。

## J. 已知限制 / 未执行

- P0/P1：独立审查发现的中断继续与旧 Experiment 预约漏洞已补回归验证；最终若仍有失败，会在证据及交付中列明。
- P2：`HANDOFF.md` 缺项；现行 SPEC/源码/数据提供可验证依据。历史未保存完整观察/预期字段不补造，界面明确来源及缺项。
- Provider 生命周期、真实 Candidate 结果、Golden冻结、Gate2、D晋升与Gate3发布没有本轮授权且未执行。本地测试通过不意味着这些阶段完成。
- 浏览器验收范围为本机已安装 Chromium；没有以单引擎验收宣称跨所有浏览器兼容。最终保留独立失败明细与实际截图数量。

## K. 交付 / 3–5 分钟面试脚本

源码、SPEC/Changelog/README、该报告及可复现脚本同次提交；本地截图/保护证明保留，证据包不含业务库/完整payload。交付时已启动本地前端 Demo `http://127.0.0.1:5173`，连接既有8010后端；截图验收隔离端口 5180 用快照。未重启真实后端 lifespan，避免启动恢复改写历史运行；后端代码以本次提交与隔离测试为验收依据，真实 Provider 生命周期仍未验证。

1. **0:00–0:40 概览/Knowledge**：解释冻结知识底座与人工治理边界；当前材料/索引为真实保存对象。
2. **0:40–1:40 Baseline**：展示 Medium50、11/11 Gate 与20 Bad Case。“群组门槛过线不等于每题都正确”；切换 Gate 与 Bad Case，打开一个案例比较期望、实际、Golden、召回/上下文和 Judge。
3. **1:40–2:50 Agent**：展示保存的诊断、三列 Plan、三张完整 A/B/C。说明三者同一Baseline，只改变允许Search Space；目标/风险/参数差异可追溯。本轮 generated、预算0/12，现场展示等待态，不把Fixture当运行成果。
4. **2:50–3:40 Sandbox / D**：解释真实改善须修复原问题并限制新增严重/普通失败；11 Gate/Regression/净改善共同决定资格。需要用户点击运行，后续 Gate2 选择合格Winner；D可合法跳过或失败保留Winner。
5. **3:40–4:30 发布 / 问答验证**：当前 Production 仍旧版本，尚未用本轮候选替换。展示人工版本决策与双版本配置；若无额外Provider授权只展示未运行答案栏，不运行真实问答。测试答案只能称 Fixture 交互验证。
