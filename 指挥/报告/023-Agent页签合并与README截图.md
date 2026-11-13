# 023 Agent 页签合并与 README 截图

更新日期：2026-11-12（多伦多时间），手动执行。No SPEC Change。

## 本次结果

Agent 工作台现在只有「进化路线 / 方案对比 / 回归与推荐」三个页签，默认进化路线。旧链接可用，页头统一显示轮次、Candidate、预算和状态。原有概览信息保留在进化路线的折叠区；Round 3 下方可直接查看 D，也保留 Candidate D 按钮。回归表在最终推荐上方，落选原因是可打开详情的表格。

三条本轮经验已对照保存数据核实，含前缀分别为 60、54、49 字。六张 README 预览图已更新，都是 1440×900、deviceScaleFactor 2 的真实本机截图，转 JPG、质量 85，每张小于 600KB。README 现有“界面预览”节已经在闭环流程架构图之后，并已有六行说明，因此沿用原文，其余内容没有改动。

最终前端全量 113 文件、672 条通过；构建通过。后端全量 1459 项，0 失败、0 错误，21 项既有跳过的名称及原因与上次完全一致。两种尺寸浏览器验收通过。

来源：本次文件差异；`output/task023/manual-20261112/frontend-complete.txt`、`build-complete.txt`、`backend-full.txt/json`、`browser-acceptance.json`、`lessons-final.json`、`review-table-final.json`、`readme-screenshots-final.json`。

## 开工检查与范围

先执行 `git pull --ff-only`，结果为 Already up to date；开工分支 main，工作区干净，HEAD 为 `0720980`，本地已有一个尚未推送的“手动停止值班”提交。本次只执行 `指挥/当前任务.md` 的 023，不接手队列中其他任务。

历史 `e560b5c` 已做过 023，`946e204` 等后续提交已加入 README 六图；但开工代码又变成四个页签，默认概览，Round 2 经验也被改回简写。本次复用已有组件和成果，补齐当前任务单要求。没有重跑正式评测或付费题。截图刷新是为了与当前实际界面一致。

没有新写视觉 CSS。沿用 PageShell、AgentStats、EvolutionTimeline、DStory、CompareTable、DataTable、StoryDisclosure、原抽屉及现有工具类。Golden 候选池代码未改。

来源：`git status / git log / git diff`；`frontend/src/pages/EvolutionPage.tsx`、`frontend/src/ui/evolution/`；README 与截图目录。

## 信息迁移对照表

| 原页签 / 区块 | 现在的位置 | 保留内容或入口 |
|---|---|---|
| 全页：轮次、Candidate、评测预算、当前状态 | 三页签公共页头 | 当前保存值为 3、10、10/12、已发布 Candidate D；只显示一次统计块 |
| 全页：历史实验、暂停、错误、主操作 | 公共页头和内容区上方 | 历史实验抽屉、暂停提示、错误、生成/继续/运行/补齐规划等原条件和确认框保留 |
| 进化路线：Baseline 起点 | 进化路线顶部 | 44/50、6 个 Bad Case、检索/生成分层、题号及诊断入口 |
| 进化路线：Round 1–3 | 进化路线的轮次按钮 | 每轮思路、三张 Candidate 卡、完整本轮经验；沿用现有按轮次查看方式 |
| 进化路线：每轮 Candidate 事实 | 各轮三张卡 | 方向、设计用意、参数变化、修好题、新增题、Hard Gate、答对数、P50/P99、Winner/效率方向标记及详情入口 |
| 进化路线：经验依据 | 本轮经验 HoverCard | 每轮 A/B/C 修好/新增、参数、Hard Gate、P99、安全拒答；鼠标和键盘可读 |
| 进化路线和 A/B/C/D 重复的 D 决策区 | 只在进化路线 | 最后一轮卡片下方显示 D；Candidate D 按钮也能直接看，同一时刻只渲染一个 DStory |
| D：头部结论、参数、唯一新增、预测原文 | 进化路线 D 的设计区 | 原保存内容、Top-K 依据提示及完整预测原文保留 |
| D：预测 vs 实际、目标题与保护题 | 进化路线 D 下方 | 原逐题对账与详情保留，不重新判分 |
| D：Winner vs D、安全拒答、耗时及资格 | 进化路线 D 的比较区 | 原指标保留；最终推荐另保留原有合格方案比较 |
| D：未修好原因、排名与伴随风险 | 进化路线 D 的原因卡 | 保存的原因、证据位置、风险和未知状态保留 |
| D：排队、未完成、无有效组合、运行/继续 | 进化路线 D 相应状态 | 原条件分支和确认框保留，未完成不编造结论 |
| D：完整报告和最终推荐跳转 | D 决策区底部 | 原 Candidate 抽屉；推荐跳到 `tab=review` |
| A/B/C/D：轮次切换 | 方案对比顶部 | Round 1/2/3，当前轮次状态保留 |
| A/B/C/D：A/B/C 三张完整卡 | 方案对比上半部 | 思路、改动参数、针对的题、预期效果、风险、结果六字段和原对齐方式 |
| A/B/C/D：目标、完整报告、跳过、运行/继续 | 各方案卡及公共操作区 | 原抽屉、禁用条件、确认/取消逻辑保留 |
| Sandbox：Baseline、本轮 A/B/C、D 对比 | 方案对比三卡下方 | 原 CompareTable；默认六指标、Winner/D 高亮、更多指标和修复口径提示 |
| Sandbox：Token、费用、检索等高级指标 | 方案对比“查看高级指标” | 原高级指标抽屉；缺项仍按原规则显示 |
| Sandbox：D 等待/跳过提示 | 对比表下方相应状态 | 原排队、跳过、待确认分支保留 |
| Regression Check：每 Candidate 一行 | 回归与推荐最上方 | 全部 10 个方案、修好、新增严重/普通、Hard Gate、资格和上限说明 |
| Regression Check：逐题修复/退化、前后回答、证据与完整审计 | 点击回归表 Candidate 后的详情抽屉 | 原逐题追踪、前后对比、严重程度和证据组件保留 |
| 最终推荐：推荐结果、理由、Winner vs D、比 Winner 多修好的题 | 回归与推荐的回归表下方 | 原 FinalRecommendation 内容保留 |
| 最终推荐：落选理由和 Candidate 详情 | 推荐区下方落选原因表 | 8 个落选方案的原理由；名称按钮打开原详情，保留键盘操作 |
| 最终推荐：去发布/查看发布记录 | 推荐区按钮 | 只导航到发布页，本次未执行发布 |
| 最终推荐：无推荐、未知、确认报告、选择 Winner、生成组合 | 回归与推荐相应条件分支 | 原保存状态、权限及确认框保留 |
| 后续新增概览：已发布结果、参数来源、三条规则、Bad Case 去向 | 进化路线末尾“Agent 概览 · 参数来源、规则与 Bad Case 去向”折叠区 | 独有内容完整保留；六道题可打开原问题证据抽屉，统计移至公共页头 |
| 已验证配置与处理进度、覆盖缺口 | 同一概览折叠区及问题证据中的 Agent 规划 | 未推荐时原处理进度保留；每题保存的验证要求/缺口仍可查看 |
| Baseline 参数、Agent 假设、可调参数、原始记录 | 原 Candidate / 问题证据详情抽屉 | 参数差异、思路、完整逐题报告、原始 Candidate 审计、可调参数入口保留 |

这里的“保留”指开工实际存在的功能与保存字段，不把历史报告里后来已调整的旧版排版说成仍然存在。独有内容留有入口，重复的 D 大块没有复制到方案对比。

来源：`EvolutionPage.tsx`、`EvolutionTimeline.tsx`、`AgentOverview.tsx`、`FinalRecommendation.tsx`；未修改的 `EvolutionStory.tsx`、`CandidateCaseComparison.tsx`；本轮单元测试和浏览器记录。

## 旧链接兼容

| 旧参数 | 现在的参数 / 页签 |
|---|---|
| `tab=candidates`、`tab=sandbox` | `tab=comparison` / 方案对比 |
| `tab=regression`、`tab=recommendation` | `tab=review` / 回归与推荐 |
| 后续增加的 `tab=overview` | `tab=route` / 进化路线 |
| `tab=route` | 保持进化路线 |

旧 `stage=` 参数和 sessionStorage 记忆也经过同样迁移。原站内推荐/Sandbox 跳转已经使用 comparison/review，概览讲解区仍指向 route，无需重复修改。旧诊断链接仍转 Baseline 的 Bad Case 诊断。

来源：`EvolutionPage.tsx`、`usePageTab.ts`、`VersionsPage.tsx`；`task023-tabs.test.tsx` 五组旧链接测试和浏览器实际跳转。

## 本轮经验：重新核对保存数据

保存实验为 `EXP-20261105143048349606`，保存 Winner 为 Round 3 · Candidate C。

| 轮次 | 最终显示句（含前缀） | 字数 | 保存事实 |
|---|---|---:|---|
| Round 1 | 本轮经验：扩候选+多路查询修好 3 题，但 P99 超标；降档+Top-K 6 修好 Q04、Q06，却拉低了安全拒答。 | 60 | A 改 Candidate K 24 + Multi-Query 2，修好 Q24/Q29/Q38，P99 86.548 秒；C 改 High + Top-K 6，修好 Q04/Q06，安全拒答 90% |
| Round 2 | 本轮经验：三套方案都弄坏了 Q17；单独把 Top-K 提到 6 能修好 Q04、Q06，但会拉低安全拒答。 | 54 | A/B/C 新增均含 Q17；B 只改 Top-K 6，修好 Q04/Q06/Q38，安全拒答 90% |
| Round 3 | 本轮经验：降低思考档、同时把候选扩到 24，首次做到零新增 Bad Case，成为 Winner。 | 49 | C 改 High + Candidate K 24，新增 0，Hard Gate 全过，是保存 Winner；之前八个 A/B/C 均有新增 |

Round 1 任务示例含空格为 64 字，沿用已有处理：仅去掉两个加号两侧的四个空格，满足 ≤60 字，句意不变。Round 2 恢复当前任务单的完整句。显示条件和 HoverCard 事实来源没有放宽，数据不符时仍不生成经验。

来源：本轮只读 `/api/optimization` 的 `reasoning.changed_parameters`、修复/新增题号、gates、report_confirmation；`ui/evolution/model.ts`；`lessons-final.json`。本机原始响应不提交。

## 测试和浏览器验收

- 最终 `npx vitest run`：113 文件、672 条通过，0 失败；`npm run build` 通过。
- 后端隔离全量：1459 项，0 失败、0 错误，21 项既有跳过不变。缺少的私有回包/审计材料仍按原测试跳过，没有补造材料。
- 测试用新建临时目录、临时库、空密钥和 Mock，不复制正式数据库；审计钩子阻止外网连接。首轮因当前实际高峰时间进入调度等待，中断后只在测试进程内固定默认时钟；调度专项测试仍可覆盖自己的高峰/低峰时间。未改产品调度代码。
- 页签及完整句断言在改动前确实失败，分别留在 `red.txt`、`lessons-red.txt`；最终全量通过，没有删除失败断言或加跳过。
- 首轮迁移后有 6 条旧入口/旧统计位置断言需要同步，原功能断言保留。后续全量均通过。
- 单元测试仍有既有 React act/useLayoutEffect 警告；真实浏览器脚本错误、控制台错误、HTTP 错误、写请求均为 0。
- 1440×900 和 1280×800：三页签首屏均能看到核心事实；经验完整显示，悬停依据可读，无全局横向滚动。三个轮次、更多指标、高级指标、方案详情、问题证据、落选详情、旧链接和发布导航已实际操作。主导航八页可打开。
- 只读代码审查发现落选表沿用旧双列 grid 类，会只占半宽；已去掉该类，沿用 table-scroll。最终浏览器确认两尺寸表宽等于容器宽，八个详情入口可用；CSS 文件未改。

浏览器原始全流程记录 `browser-acceptance.json` 保留第一次检查事实（其中 Round 2 当时仍为 52 字）；完整句修改后的最终依据是 `lessons-final.json`。表格修正后的最终依据是 `review-table-final.json`。没有改写旧记录冒充它覆盖了后来的变动。截图最终字节数和摘要以 `readme-screenshots-final.json` 为准。

### 改动测试的原意与继续验证方式

| 测试文件组 | 原来验证什么 | 本次怎样继续验证 |
|---|---|---|
| agent-restoration、evaluation-governance、fixed-workspaces、interview-evaluation、task018a-agent、task021u-integration | 页签、运行状态、保存记忆、禁用和授权 | 改为三页签/新名称，统计在公共页头；运行进度、确认/取消及数据不变断言保留 |
| bad-case-unification、candidate-presentation、closure-authorization、diagnostic-workspaces、storytelling-v2、task013c-agent、task015a-offline、task021b-story、task021w-integration、task022c-layout、task022f-warmup、v12-flow、v14-ui-contract | 目标问题、字段、费用/预算、预热、详情、轮次和受控操作 | 只同步“方案对比”入口或统计位置，原业务及请求断言保留 |
| task021o-release、task021v-integration、task024a2-dedup、task027f-candidates | 落选原因、推荐理由、Winner 取舍、详情与发布导航 | 选择器改为表格行/按钮；仍逐项验证原因、数量、详情和导航；回归表改在推荐上方 |
| task027e-workbench | 概览结果、参数来源、六道题去向、缺数据不编造、轮次/D 入口 | 独有信息改在路线折叠区，原来源、题号和未知断言保留；增加 Baseline 起点检查 |
| task023-tabs | 老链接、轮次、更多指标、抽屉、回归、只读 | 增加旧 overview 的 URL/stage/sessionStorage 迁移；补验默认路线、公共统计、Baseline 起点、R3 与 D 同页、回归先于推荐和八行落选表 |
| task022f-lessons | 跨方案事实依据、字数、缺数据不生成、键盘 HoverCard | Round 2 精确验证任务完整句；60 字上限、条件限制、来源与键盘交互断言保留 |

来源：本轮测试差异；上述最终测试日志与浏览器记录。未修改后端测试或产品代码。

## 截图路径

README 使用以下六张图，原文和六行中文说明保留：

| 提交文件 | 大小（十进制 KB） |
|---|---:|
| `docs/images/screenshots/01-overview.jpg` | 281.9 KB |
| `docs/images/screenshots/02-golden-dataset.jpg` | 295.8 KB |
| `docs/images/screenshots/03-baseline.jpg` | 280.0 KB |
| `docs/images/screenshots/04-agent-evolution.jpg` | 382.6 KB |
| `docs/images/screenshots/05-release.jpg` | 231.8 KB |
| `docs/images/screenshots/06-before-after.jpg` | 401.6 KB |

截图已经逐张预览，未见插件浮窗、长内部编号或报错。第 4 张选中 Round 3，并滚到 Winner 三卡与 Candidate D 的设计结论。第 6 张使用保存的 Q04 Before/After，没有提交实时问答。

本机验收文件全部留在忽略的 `output/task023/manual-20261112/`：

| 文件 | 内容 |
|---|---|
| `1440-route.png`、`1440-comparison.png`、`1440-review.png` | 1440×900 三页签首屏 |
| `1280-route.png`、`1280-comparison.png`、`1280-review.png` | 1280×800 三页签首屏 |
| `1440-round-1-lesson.png` 至 `1440-round-3-lesson.png` | 三条最终经验，1440×900 |
| `1280-round-1-lesson.png` 至 `1280-round-3-lesson.png` | 三条最终经验，1280×800 |
| `1440-rejection-table.png`、`1280-rejection-table.png` | 审查修正后的落选表 |
| `01-overview.png` 至 `06-before-after.png`（对应主题名） | README 截图原图 |

来源：Playwright 实际截图、Pillow 文件尺寸/字节数检查、最终图片摘要。除六张明确允许的 README JPG 外，不提交这些截图、原始响应或日志。

## 数据边界与收尾

本轮工具没有调用真实模型：DeepSeek 0 次，其他真实模型 0 次。浏览器 API 写请求全部阻断，测试使用隔离临时库及 Mock；未执行真实发布、回滚或问答提交，没有改 Golden、评测数据、门槛或 Agent 推理原文。

前后摘要核对：evaluation、optimization、versions、documents、workspace 五组响应完全一致。Monitoring 有一条新增记录，时间为多伦多 11-12 20:17:35；只在本机副本中去掉这条新记录后，摘要与开工一致。来源未知。本轮浏览器写请求记录为 0，现有 demo 访问日志另有 `/api/preview` 请求；不能据此认定是谁提交，也不能说整个运行中的 demo 没有变化。该记录原样保留，不删除、不回滚。当前 Golden/Baseline/实验/线上版本身份均未变。

来源：`state-before.json`、`state-after.json`、`state-delta.json`、浏览器写请求记录，以及现有 `.demo-logs/api.log`（只读；不提交日志）。

保留开工已有前端 5174 / PID 827、后端 8010 / PID 816，按本任务特别要求让 demo 继续运行。测试临时库自动清理；本轮浏览器、驱动及测试进程结束后退出。报告、前端代码/测试及六张 JPG 由本轮手动提交并推送 main；数据库、密钥、运行日志和本机原始材料不提交。
