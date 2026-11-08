# 021v：Baseline 首屏、发布页与最终推荐接入

## 结果

三个新版组件已接到正式页面：Baseline 首屏使用 `BaselineHero`，发布页使用 `ReleasePanel`，Agent 最终推荐使用 `FinalRecommendation`。原耗时表、指标、抽屉、确认框、分页和筛选保留；耗时表与评测信息默认收进“更多指标”。`frontend/src/ui/` 没有改动，未新增依赖。来源：本次文件差异，三个页面和 `ProductDiagnostics.tsx`。

最终构建通过；相关测试 **36/36 通过**；全量前端 **455 通过、57 条既有失败**。与开工的 450 通过、57 失败相比新增失败 **0**，与 021s 本机 61 条失败清单相比新增失败也是 **0**。符合任务追加口径；全量没有变绿。来源：`output/task021v/build-final.txt`、`related-final.txt`、`tests-before.json`、`tests-complete.json`、`failure-comparison.json`、`output/task021s/tests-complete.txt`。

正式数据开工时已是 **Candidate D 已发布**，本任务没有发布或回滚。Baseline 44/50、11/11 Hard Gate、6 个 Bad Case，Generation 95.8%；Winner C 47/50、P50 6.724 秒、P99 22.596 秒；D 48/50、P50 8.105 秒、P99 36.735 秒。页面沿用原精度显示为 C 6.7/22.6 秒、D 8.1/36.7 秒，C 更快的一方如实加粗。来源：开工接口 JSON（`evaluation-before.json`、`optimization-before.json`、`versions-before.json`）、`final-style-check.json`。

数据库 33 张表开工/验收后的行数和逐表内容哈希相同。DeepSeek / 其他模型调用 **0**；浏览器验收没有向后端发送写请求，所有生成、发布、回滚确认框均取消。正式服务 5174（PID 1117）与 8010（PID 19536）保持原进程运行，没有启动或重启它们；本任务启动的验收浏览器均已关闭。来源：`before-hashes.json`、`after-hashes.json`、`final-hashes.json`、浏览器检查 JSON、开工/收尾端口检查。

## 我是这样理解的

1. 自动值班只改文件；没有执行 Git 的 add、commit、push、pull、checkout、reset、stash、mv 等写命令。保存与推送交给值班脚本。根目录 README 的拉取要求按用户本轮“不运行 Git 写命令”的指示处理。
2. 追加口径优先：相关测试通过、对照 021s 新增失败 0，即完成本任务；57 条既有失败留给 021x。
3. 任务单“demo 保持运行”优先于根规则的测试进程清理，保留开工前已有服务，只关闭自己启动的浏览器。
4. 实际已经发布，因此上半部显示“已发布方案”，按钮显示“查看发布快照”“查看发布记录”；不会照搬样板里的待发布状态。
5. 已发布时左右对比使用保存的上一版本与当前推荐配置，避免变成 D 对 D；旧线上版本已发布不能冒充新的推荐已发布。
6. 新组件源码与 `ui.css` 保持不变；追加的文字精简和 400/600 字重通过宿主页面处理。隐藏新组件里重复的两条辅助小字；不改它们的数据或组件结构。
7. 运行中、历史规则、身份失效、技术异常或缺少关键数字时，Baseline 保留原提示和缺失值处理，不把缺失数据渲染成“全部通过”。
8. 分页与尚未出现的动作只在浏览器内存替换 GET 响应验证，未向正式数据库写夹具。正式截图全部使用真实保存数据；样板图明确属于 `/ui-gallery.html` 的 Fixture。

来源：用户指令、任务单追加要求与硬性约束，`AGENTS.md`、`指挥/README.md`，页面条件分支和本机验收脚本。

## 断点检查和初检

开工 Git 工作区干净；最近日志无 021v“已做部分”记录，未发现本任务报告或半成品。沿用 021u 的 `buildEvolutionModel`、数据源和确认流程，没有重跑任何评测题。

按任务要求首先执行 `npx tsc -b`，退出 0；`npx vitest run src/ui` 为 3 个文件、20 条通过。三个总指挥组件均无需类型修正。本轮新增 5 条接入测试，修改前均因新版界面尚未接入而失败，接入后全部通过。来源：开工工具输出、`output/task021v/red.txt`、`green-second.txt`、`related-final.txt`。

## props 来源

### Baseline

| props / 展示 | 真实来源与处理 |
| --- | --- |
| `gates` | `run.result.gates.passed_count / total`，沿用原 Hard Gate 保存结果 |
| `correct / total / badCount` | 沿用 `result.bad_case_count` 与原逐题诊断回退，答对为 `total - badCount` |
| `layers` | 原 `businessDiagnosisRows()` 的业务 Bad Case，按 `caseData(row).diagnostic_view.diagnosis_category` 计数；本轮检索层问题 5、生成层问题 1 |
| `thinking` | `run.config.generation_thinking`，缺失时沿用保存的执行快照；用原 `thinkingLabel()`，实际 Max |
| `p50 / p99` | 保存的 Hard Gate 条目 `latency_p50_seconds / latency_p99_seconds.actual`，实际 16.676 / 42.240 秒 |
| `stages` | 原 `ProductDiagnostics` 的 `objective_metrics.stage_breakdown`；抽出 `timingStages()` 供原表与首屏共用，排除 Judge，原样聚合小于 0.5% 的“其他环节”；秒数 `total_ms / 1000`，`share` 直接取保存占比，Generation 95.849468…% 显示 95.8% |
| 更多指标 | 原 `ProductDiagnostics` 表、展开/收起明细、Thinking 对照抽屉逻辑保留；Recall@K、Precision@K、MRR、首字时间、Token、费用及综合分、评测信息收进同一折叠 |

来源：`frontend/src/pages/EvaluationPage.tsx`，`frontend/src/components/ProductDiagnostics.tsx`。

### 发布

| props / 动作 | 真实来源与处理 |
| --- | --- |
| `candidate` | 保存的 `recommendationOf(data.optimization).recommended_candidate` 对应 Candidate；仅没有当前推荐而线上已发布时回读线上保存快照 |
| `online` | 发布前用 `currentVersion.config`；本轮已发布，用 `previous_version_id` 对应版本，缺失才用快照 `previous_version`，缺资料显示未知 |
| `params` | 两者 `candidate_k / top_k / generation_thinking`，复用 021r 的 `PARAM_LABELS / paramValue`；回答策略兼容旧字段使用原 `formatValue()` |
| `changes` | 线上/发布前配置与 Candidate 配置的标量差异，只列现有可读参数，不列内部知识身份对象 |
| `results` | Baseline 与推荐保存结果的答对数、保存 Hard Gate P99、推荐新增 Bad Case 题号数组长度和 Gate 计数；缺失为未知，已知历史 Baseline 不匹配时不混用当前 Baseline 数字 |
| `reportConfirmed` | 原 `reportConfirmation`，仅回读已发布快照时可用保存的报告确认 |
| `eligible` | 原 checks：评测完成且 Hard Gate 全过、零新增 Bad Case、至少修好 1 题；步骤只保留修好数和不满足项，Gate/新增数字集中在成绩区显示一次 |
| `released` | 原 `currentReleased`（published + Candidate ID + 人工 approved），再核对与当前面板 Candidate 相同；时间来自保存 `release_time / created_at`，用原本地时间格式 |
| `canRelease` | 原 `canRelease(candidate)`，叠加原 `busy` 禁用条件，未改变资格规则 |
| `onRelease` | `setConfirmation({kind: "release", item: panelCandidate})` → 原 `ConfirmDialog` → 原 `release()`；无旁路请求 |
| 查看报告 / 快照 | 原 `setReport` / `setDetail("config")` 抽屉 |
| 旧线上与新推荐并存 | 下半部保留不同线上版本的 Gate、Regression 与批准来源；这些是另一版本的证据，不当作重复成绩删除 |

来源：`frontend/src/pages/VersionsPage.tsx`；开工 `versions-before.json`、`optimization-before.json`。

### 最终推荐

| props / 动作 | 真实来源与处理 |
| --- | --- |
| `chosen / runnerUp / others` | 021u 已接入的 `buildEvolutionModel`：按保存推荐 ID 选 D，按 Winner ID 选 R3-C，其余 8 个 ABC 进入落选表，不按页面文字猜 Winner |
| `reason` | 原 `recommendationReason(experiment)`，沿用 `storyText()` 术语和短题号处理 |
| `baselineCorrect` | 保存的 Baseline `total - bad_case_count` |
| `questionText` | 原 `questionText(id, evaluation, badCases)`，悬停仍可查看题目 |
| `onRelease / releaseLabel` | 跳 `#versions`，实际已发布显示“查看发布记录”；不执行发布 |
| `onOpen` | 用 Candidate ID 回到原 `setSelectedCandidate()` 详情抽屉 |
| Winner 详情 | 新对比表没有 Winner 行点击回调，因此宿主页保留“查看 Winner 方案详情”，使原来第 9 个其他方案详情入口仍可达 |
| 人工确认 / 生成组合建议 | 原“人工报告确认已完成”及 `confirmation && !composite && !compositeWaiting` 按钮条件保留；未确认时的 Winner 选择和确认报告按钮保留 |
| `alternativeReason` | 删除已无引用的函数及导入；新表直接展示同一份保存的修好题、新增 Bad Case 和未过 Gate，不生成新的落选解释 |

来源：`frontend/src/pages/EvolutionPage.tsx`、`frontend/src/components/EvolutionStory.tsx`、`frontend/src/ui/evolution/model.ts`（只读取，未改）。

## 功能清单前后核对

改前按三页各页签抓取全部按钮、链接、summary、筛选控件，保存于 `inventory-before.json`；改后清单在 `browser-check.json.inventory`。抽屉和确认框的条件按钮另外按下表展开验证。

| 页面 / 原功能 | 改后处理与验收结果 |
| --- | --- |
| Baseline 三个页签 | 逐项切换；Hard Gate / Bad Case 页签结构未改 |
| Baseline 更多菜单、重新运行按钮 | 菜单可打开、按钮可用；按“不运行评测”约束未点启动 |
| 原耗时表、细小环节明细 | 移入“更多指标”，展开后数值相同；展开/收起明细均可用 |
| Thinking 对照入口 | 条件显示逻辑保留；本轮正式记录没有可比较列，故实际不显示；`src/ui` 与原 ProductDiagnostics 相关测试继续验证对照逻辑 |
| 11 项 Hard Gate → 指标详情 | 11 项逐项打开、关闭；贡献题“查看案例”可继续开题目抽屉 |
| Bad Case 全部 / 检索 / 生成筛选 | 分别为 6 / 5 / 1 行；安全、性能 0 行按钮禁用状态保留 |
| 六道题目详情、进入 Agent | 六道逐项打开关闭；Agent 跳转正常 |
| 发布前发布按钮 | 正式状态已发布故不显示；浏览器内存模拟未发布后只弹原确认框并取消；单测另验证取消前无请求、接口失败时保留错误 |
| 发布后面板 | 正式页面显示已发布，无确认发布按钮；三个独立状态和真实发布时间正确 |
| 完整配置、发布快照、评测报告 | 都能打开、关闭原抽屉 |
| 查看其他 Candidate | 原抽屉保留，10 个方案的发布报告逐项打开、关闭；不合格方案没有发布入口 |
| 版本详情、回滚 | 两条正式版本详情均可打开；回滚只弹确认框，取消不写后端 |
| 版本历史分页 | 正式 2 条，上一页/下一页禁用；浏览器内存 51 条响应验证 50 → 1 → 50 |
| Agent 五页签、Round 1–3 切换 | 逐项切换，原页签恢复/刷新状态保留 |
| 进化路线 9 张卡片 | 逐个打开原方案详情；Q 题号悬浮信息保留 |
| D 完整报告、更多、查看最终推荐 | 原入口可用；展开内容保留，跳转新版最终推荐正常 |
| 规划详情、六个问题证据、基线诊断摘要 | 展开/折叠、证据抽屉逐项核对；规划内 3 个方案的目标/报告入口、可调参数也分别点过 |
| 历史实验 / 可调参数菜单 | 抽屉可开关；历史 6 个方案的目标/报告共 12 个入口分别验证 |
| A/B/C/D 当前方案目标、报告 | 3 个 ABC 目标和完整报告逐个打开；原用量、耗时、审计仍可展开，50 道逐题报告可读取 |
| Candidate 报告分页 | 正式题卷 50 题无需翻页；浏览器内存 51 题响应验证 50 → 1 → 50 |
| Sandbox 高级指标 | 原抽屉可打开关闭，Recall@K、Token 等仍在 |
| Regression 类型、方案、严重程度筛选 | 原问题修复/新增失败、各 Candidate、严重/普通/未采集/全部逐项点击 |
| Regression 前后对比与证据 | 前后对比抽屉、Baseline/Candidate 两侧证据与审计可达 |
| 最终推荐 8 个落选方案 | 表格 8 行分别点开原详情；Winner 详情由保留按钮打开；D 报告保留在原 D 完整报告入口 |
| 已发布记录跳转 | 点击新版主按钮进入发布页，刷新后仍恢复最终推荐页签 |
| 人工报告确认提示 | 正式推荐下仍显示“人工报告确认已完成。” |
| 生成 / 运行 / 续跑 / 下一轮 / 确认报告 / 生成组合建议 | 浏览器内存分别触发 7 类原确认框，全部取消；没有调用模型 |

来源：`output/task021v/browser-check.json`（50 个检查记录）、`remaining-check.json`（19 个额外入口）、`confirmation-check.json`（8 类确认框，含发布）、`pagination-check.json`（2 类分页）、`release-fixture-check.json`。这些浏览器检查的写请求与脚本错误均为 0。

## 去掉的重复信息和字体覆盖

### 文字与位置

| 原文 / 位置 | 处理 |
| --- | --- |
| “Baseline Hard Gate 已通过”横幅及旧四指标卡 | 正常完整报告由首屏一句转折与四格替换；综合分下沉“更多指标”；不完整/历史状态仍保留原提示 |
| 答对格辅助行“6 个 Bad Case” | 与首屏转折重复，宿主页隐藏；真实 Bad Case 数与分层不变 |
| 耗时标题右侧“Generation 占 95.8%” | 与下方图例重复，宿主页隐藏右侧辅助小字，图例保留 95.8% |
| “Generation 模型和档位 … Max”等评测信息 | 与首屏档位重复，整组原评测信息下沉“更多指标”，没有删除 |
| 原“本轮推荐，尚未发布”、已发布空提示 | 由 `ReleasePanel` 单一实际状态替换，不再留旧横幅 |
| 原当前线上区 Hard Gate/人工确认/发布确认及参数变化 | 同一方案的重复结果并入新面板；当前线上基本信息、配置/其他候选/历史抽屉保留；新推荐与旧线上不是同一方案时保留旧线上的不同证据 |
| 步骤②重复的 Gate 计数和新增 Bad Case 数 | 数字只在成绩摘要显示；步骤②仅显示修好数及不满足项，ok 仍由全部原 checks 决定 |
| 原最终推荐的“为什么选它”+九段其他方案长文 | 换成一条现有推荐理由、Winner/D 表、其他 8 行落选表；Winner 单独详情入口保留 |

来源：三个页面及 `evaluation-workspaces.css`。只在宿主做去重，`src/ui` 文件未改。

### 字体与颜色

`pages/evaluation-workspaces.css` 原来已经没有硬编码颜色，也没有 font-size/font-weight 覆盖；本轮没有为三页增加任何硬编码色值。新增的状态适配使用 `var(--ui-*)`：旧状态徽章改成透明背景、灰字、小圆点；失败说明正文恢复中性色，红绿只用于语义标记。新组件的布局和 ui.css 本身未改。

三页新摘要区域统一可见字重为 400/600，主按钮、题号、数字、表头也纳入检查。两个尺寸共 6 个正式视图逐节点验证，只发现 400/600；页面内容区与文档均无横向溢出。来源：`final-style-check.json`。原旧字体覆盖从 `frontend/src/styles.css` 移除，具体如下（其他布局声明保持）：

| 原位置 / 选择器 | 删除的原覆盖 | 处理 |
| --- | --- | --- |
| `.candidate-row` | `font-size: 13px` | 沿用公共样式；本次清空的规则删除 |
| `.candidate-card h3` | `font-weight: 650` | 沿用公共样式；本次清空的规则删除 |
| `.candidate-question` | `font-size:var(--card-body)；font-weight:700` | 沿用公共样式；本次清空的规则删除 |
| `.candidate-quality-links .text-button` | `font-size: 12px；font-weight: 400` | 沿用公共样式；本次清空的规则删除 |
| `.candidate-readonly-hint` | `font-size: 12px` | 沿用公共样式；本次清空的规则删除 |
| `.candidate-card dd` | `font-weight: 700` | 沿用公共样式；本次清空的规则删除 |
| `.candidate-config-diff td, .candidate-config-diff th` | `font-size:12px` | 沿用公共样式；本次清空的规则删除 |
| `.candidate-config-diff details` | `font-size:12px` | 沿用公共样式；本次清空的规则删除 |
| `.candidate-result span` | `font-size:12px` | 沿用公共样式；本次清空的规则删除 |
| `.agent-hypotheses` | `font-size: 13px` | 沿用公共样式；本次清空的规则删除 |
| `.evolution-page .candidate-result dt` | `font-size: 12px` | 沿用公共样式；本次清空的规则删除 |
| `.release-summary span` | `font-size:12px` | 沿用公共样式；本次清空的规则删除 |
| `.release-summary strong` | `font-size: 13px` | 沿用公共样式；本次清空的规则删除 |
| `.candidate-workspace .candidate-card h3` | `font-size:var(--card-title)；font-weight:700` | 沿用公共样式；本次清空的规则删除 |
| `.candidate-workspace .candidate-question` | `font-size:var(--card-body)；font-weight:700` | 沿用公共样式；本次清空的规则删除 |
| `.baseline-run-summary,.comparison-identities` | `font-size:var(--card-support)` | 沿用公共样式；本次清空的规则删除 |
| `.evaluation-page .baseline-metrics span,.evaluation-page .baseline-metrics small` | `font-size:var(--card-support)` | 沿用公共样式；本次清空的规则删除 |
| `.evaluation-page .baseline-metrics strong` | `font-size:var(--text-metric)` | 沿用公共样式；本次清空的规则删除 |
| `.evaluation-page .baseline-conclusion` | `font-size:var(--card-body)` | 沿用公共样式；本次清空的规则删除 |
| `.evaluation-page .baseline-conclusion h2` | `font-size:var(--card-title)` | 沿用公共样式；本次清空的规则删除 |
| `.story-changes strong` | `font-weight:500` | 沿用公共样式；本次清空的规则删除 |

完整原声明/处理后声明保存在本机 `output/task021v/typography-removed.json`。

## 测试修改说明

| 文件 | 原来验证什么 | 新测试如何保留同一保证 |
| --- | --- | --- |
| 新增 `task021v-integration.test.tsx` | 本轮新增覆盖 | 5 条：保存 Gate/耗时占比及原表可展开；发布确认取消无请求；发布后上一配置/快照/回滚；旧线上不能冒充新推荐；Winner/D 优劣加粗、8 个详情、发布记录跳转 |
| `task021o-release.test.tsx` | 落选原因必须源于保存的修好/新增/Gate，已发布后跳记录 | 定位到新落选表，仍核对 Q24/Q13、P99 86.5/上限 60、Winner 合格与 D 多修 Q04；发布链接改为点击新按钮并检查 hash；夹具明确 ABC 标签与 Winner 身份，符合共用模型输入 |
| `interview-release.test.tsx` | 旧线上与新推荐分开、只显示变化参数、完整配置抽屉、不虚构批准 | 对新面板检查参数差异；旧线上独有成绩仍在下半部核对；原不虚构与抽屉断言保留 |
| `storytelling-v2.test.tsx` | 差异来自线上 12→24，不能误用无关 Baseline 99 | 只把 `.pending-release .story-changes` 改为 `.ui-rel-changes`，12/24/非99 断言不变 |
| `task021b-story.test.tsx` | 首屏只放保存推荐、显示新增 Bad Case、禁用不合格发布 | 更新容器/标题定位，新增 1 个与禁用断言不变 |
| `versions-release.test.tsx` | 发布只一个入口、确认前不发请求、按原接口确认 | 更新旧 `.pending-release` 定位到 `.ui-rel`；确认与请求断言不改；其中无关既有失败没有借机修复 |
| `v14-ui-contract.test.tsx` | 原发布确认和提交失败不能伪装成功 | 仅更新原发布区容器选择器，确认后 409 错误仍留在框里、原请求数和无假版本断言不变；其余既有失败未扩修 |

最终相关测试命令：`npx vitest run src/ui src/task021v-integration.test.tsx src/task021o-release.test.tsx src/interview-release.test.tsx`，6 个文件、36 条通过。全量命令 `npx vitest run --reporter=json --outputFile=../output/task021v/tests-complete.json` 返回非零是上述 57 条既有失败；已逐条用文件名和完整测试名对照 021s，新增 0。`npm run build` 同时包含最终 `tsc -b` 与 Vite 构建，通过。来源：本机测试结果及 `test-originals/` 的修改前备份。

## 截图与样板对照

均只存本机 `output/task021v/`（Git 忽略），未把截图、接口 JSON、数据库或日志放进提交。

| 尺寸 | Baseline 首屏 | 发布上半部 | 最终推荐首屏 |
| --- | --- | --- | --- |
| 1440×900 | `1440x900-baseline.png` | `1440x900-release.png` | `1440x900-recommendation.png` |
| 1280×800 | `1280x800-baseline.png` | `1280x800-release.png` | `1280x800-recommendation.png` |

另有两个尺寸的 `*-baseline-more.png`；样板组件图 `*-gallery-baseline.png`、`*-gallery-release.png`、`*-gallery-recommendation-top.png`、`*-gallery-recommendation-compare.png`。并排检查图为 `comparison-{1440或1280}-{baseline、release、recommendation-top、recommendation-compare}.png`。样板截图只在捕捉时隐藏无关的固定运行浮窗，未更改样板源码。

| 与样板的差异 | 原因 |
| --- | --- |
| 正式页含现有侧栏、标题、页签，下方保留原功能；可用宽度与 gallery 不同 | 是原 demo 宿主结构，没有为追求像素相同删除功能 |
| Baseline 显示“检索层问题 / 生成层问题”“其他环节”，样板为短标题“检索层 / 生成层”“其他” | 保留现有分类与原耗时表标签，计数和占比一致 |
| Baseline 少一条重复 Bad Case 小字与一条重复 Generation 占比，原评测信息折叠 | 追加的“同屏一次”“次要数据收进更多”要求 |
| 发布面板按实际“已发布”，日期为保存的本地时间 11-08 03:08；gallery 的 03:10 是固定示例 | 以保存发布记录为准；本任务没有发布 |
| 差异标签顺序为 Candidate K、Thinking、Top-K；样板先 K、Top-K、Thinking | 正式顺序沿用保存配置键顺序，三个变化内容相同 |
| 发布资格步骤不再重复 Gate/新增计数，只显示修好 4 个及阻断项 | 按追加去重要求；三个状态仍分开，资格算法未改 |
| 最终推荐按钮“查看发布记录”，样板是“去发布” | 正式 D 已发布；宿主页防止较长按钮文字换行 |
| 最终推荐保留 Winner 详情按钮和人工确认提示，条件下保留生成组合建议 | 明确要求原功能不能丢，样板仅演示新版内容 |
| 正式落选表使用完整 Gate 中文名；失败文字中性灰、摘要字重 400/600 | 名称来自现有 gateNames，颜色与字体按追加要求；样板原文件保留不改 |
| 推荐与表格在 1280 尺寸按原内容区纵向滚动，其他 8 行不硬塞首屏 | 原页面高度与侧栏保留；无全局或内容区横向滚动 |

来源：最终 6 个正式视图、8 张并排对照、`final-style-check.json`、`browser-check.json`。最终截图无脚本错误，数字已与修改前保存数据核对。

## 待回答问题

无阻塞项。未执行正式模型调用、评测、发布、回滚，这是本任务硬性约束；相关动作已验证到确认框并取消。全量的 57 条既有失败不属于本任务扩修范围，留给 021x。

## 交接

本任务为 No SPEC Change。没有修改 `指挥/当前任务.md`，没有执行 Git 写命令。本任务单已用普通 `mv` 移入 `指挥/历史任务/021v-接入Baseline首屏发布页与最终推荐新版.md`，提交与推送由自动值班脚本负责。
