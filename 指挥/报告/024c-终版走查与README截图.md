# 024c：终版走查与 README 截图

已完成终版路线走查、三处重复卡片外框修正、README 六张预览图及本机备份录屏。前端 102 个文件、600 条通过；后端运行 1459 项，0 失败、0 错误，21 项既有跳过。真实模型调用 0 次。demo 保持运行。No SPEC Change。

来源：本轮文件差异；`output/task024c/frontend-final.txt`、`build-final.txt`、`backend-full.txt/json`、`browser-acceptance.json`；`output/demo-backup/audit.json`。

## 开工与理解

- 已按顺序读取根目录 `AGENTS.md`、`指挥/README.md`、本单。首次开工 HEAD 为 `8f27d87`，工作区干净；024b 已完成。额度中断后，值班脚本已在 `26769ce` 保存样式、README 和六图半成品。恢复时 HEAD 为 `ca5f227`，工作区干净；沿用已完成的 600 条前端测试、1459 项后端测试和浏览器验收，没有重跑。最后一次录制只走到知识库，继续补完终版连续录制、媒体验收和报告；没有重跑任何付费题。
- **我是这样理解的**：自动值班只改文件，普通 `mv` 归档任务单，由脚本保存、提交和推送。没有运行 Git 写命令，也没有修改 `指挥/当前任务.md`。
- **我是这样理解的**：本单“demo 保持运行”优先于通用关服务要求。保留开工已有前端 5174 / PID 1117、后端 8010 / PID 19536，不重启；关闭本轮浏览器和测试进程。
- **我是这样理解的**：六张 README JPG 是本单明确允许提交的截图例外。路线 PNG、视频、审计原始响应及测试日志仍放在被忽略的 `output/` 下。
- **我是这样理解的**：不改 Golden、保存的模型回答及 Judge / Agent 原文。原文中出现“内部”按原文保留，不能为实现字面零命中而改评测资料；具体边界见“待回答问题”。

来源：任务单、仓库规则、只读 `git status / git log / git diff`、024b 报告；`output/task024c/state-before.json`。

## 走查发现和处理

| 发现 | 处理与复验 |
|---|---|
| 知识主题覆盖的外层折叠区与组件自身各有卡片外观 | 去掉内层背景、阴影与额外左右留白，保留九主题、98 个规划题位和全部交互。 |
| Candidate D 决策大卡内，预测 / 实际、Winner 对比及原因区重复画卡片 | 去掉内层卡片背景、边框、阴影，保留并排表格、保护题提示、原因展开及完整报告入口。 |
| Candidate 对比区外层白卡又包三张 Candidate 卡 | 去掉该外层卡片外观和留白，保留三张 Candidate、参数、风险、目标、报告按钮和下方 Sandbox。 |
| 概览刚返回时，保存题目及参数原因尚在异步读取 | 录制等待保存题目读完后开始，未把短暂“题目未保存”截图当作最终数据缺失。未修改其读取逻辑。 |
| Baseline 下方诊断区、实时问答示例在读取时出现暂态空白 / 示例不可用 | 本机录制脚本等待 `.ui-blb` 和可用的 `.chat-example` 后再截图、计时；未发送问题、未修改运行逻辑。 |
| Q45 首次详情冷读慢于 1 秒 | 初查分别约 3.0 秒、1.48 秒；最终开拍前实际走一遍只读路线并打开 Q45 预热，复用已有缓存。未改接口、缓存策略或后端。 |
| 旧 022d 录制脚本仍定位已合并的 Agent 页签 | 按 024a2 / 024b 的“进化路线 / Candidate 对比 / 回归与推荐”更新本机脚本；D 报告从进化路线原入口打开。 |
| 知识主题默认展开，处理链路位于下方；最终推荐表位于回归区下方 | 录屏明确滚动到处理链路，再返回主题覆盖；回归区和最终推荐各停一站，避免核心内容只露出半截。 |

产品代码只改 `frontend/src/pages/task024a-polish.css` 的 9 行样式。没有改组件状态、按钮回调、API、后端、配置、门槛或评测记录。三处外框检查修改前因白底 / 边框 / 阴影失败，修改后均为透明背景、0 边框、无阴影。来源：`surfaces-before.txt/json`、`surfaces-after.txt/json`、样式差异。

全站 38 项页头 / 页签检查、9 个原有入口及取消动作复验通过。主路线 34 站全局横向溢出 0、主内容区横向溢出 0、页面提示错误 0、脚本 / 控制台错误 0、HTTP 错误 0、写请求 0。已目视检查按序截图及六张 JPG：核心结论可读，无浏览器插件浮窗或原始身份编号。列表长问题有原有全文 / 抽屉入口；未通过删改原文来压短内容。实时问答保留引导，线上反馈保持真实 0 条空状态，没有补造记录。

来源：`browser-acceptance.json`、`read-controls.json`、`output/demo-backup/audit.json`、`output/demo-backup/contact-*.jpg`；截图尺寸与编码记录为 `screenshots.json`。

## 与 022d 数字核对

| 项目 | 本轮读取和页面核对 |
|---|---|
| 正式身份 | Baseline `EVAL-20261104115541869274`；Golden `GD-20261104115533`；实验 `EXP-20261105143048349606`，均未变。 |
| 答对 / 新增 Bad Case | Baseline 44 / 50；Winner 47 / 50、0 新增；D 48 / 50、0 新增。 |
| Hard Gate | Baseline、Winner、D 均 11 / 11。 |
| P50 / P99 | Baseline 16.7 / 42.2 秒；Winner 6.7 / 22.6 秒；D 8.1 / 36.7 秒。 |
| 安全拒答 | Baseline 95%；Winner、D 100%。 |
| 预算 | 10 / 12，不把上限 12 写成已用。 |
| 修好 / 剩余 | 修好 Q04、Q24、Q29、Q38；剩余 Q06、Q27；D 比 Winner 只多修好 Q04。 |
| Bad Case 分层 | 检索层 5、生成层 1。 |
| 知识库 | 4 文档、157 页、349 Parent、368 Child、9 主题。 |
| Golden 与规划 | 冻结 50 题：20 正向、10 消融、20 负向；主题规划 40 / 18 / 40 合计 98，口径分开。 |
| 配置 | Baseline 12 / 4 / Max；线上 D 24 / 6 / High，分别指 Candidate K / Top-K / Thinking。 |

来源：022d 报告“数字一致性审计”；本轮只读 API 响应 `overview.json`、`evaluation.json`、`optimization.json`、`pipeline.json`、`versions.json`；`numeric-audit.json` 的 13 组断言；路线截图。没有重评分或重生成回答。

## README 预览图

在“闭环流程”架构图之后、技术架构之前新增“界面预览”，每图一行说明这一页证明什么。程序比对确认移除新增一节后，README 与开工版本逐字相同。

六张均为 1440×900 视口、deviceScaleFactor 2，实际 2880×1800，JPG 质量 85、均小于 600,000 字节。

| 页面 | 路径 | 字节 |
|---|---|---:|
| 概览首屏（含逻辑链） | `docs/images/screenshots/01-overview.jpg` | 338,744 |
| Golden 当前测试集 | `docs/images/screenshots/02-golden-dataset.jpg` | 323,777 |
| Baseline 报告 | `docs/images/screenshots/03-baseline.jpg` | 250,479 |
| Agent Round 3 + D | `docs/images/screenshots/04-agent-evolution.jpg` | 289,894 |
| 发布页上半部 | `docs/images/screenshots/05-release.jpg` | 232,043 |
| Before/After Q04 | `docs/images/screenshots/06-before-after.jpg` | 414,569 |

来源：`README.md`、`output/task024c/screenshots.json`；六张图已逐图目视检查。

## 录屏、截图与切换耗时

- 覆盖文件：`output/demo-backup/demo-route.webm`；1440×900，VP8 / WebM，无旁白，时长 **129.28 秒**，22,625,019 字节。
- 已在 Chromium 读取媒体尺寸和时长，并解码、跳转检查开头 / 中间 / 结尾三个位置，均可显示。
- 每站截图后停留 3.3 秒；截图实际 2880×1800，共 34 张，按 01–34 编号。已替换旧的编号路线截图，旧 supplemental 证据另存保留，没有混入本轮清单。
- 开拍前先在概览等 30 秒，再实际走完只读路线预热，包括 Before/After 和 Q45 详情；等待保存题目和保护题结果完整载入后回到概览。成片裁去开拍前预热等待，保留真实点击、切换、滚动及停留。
- 时间从导航 / 点击 / 滚动开始到本站内容就绪，排除 JPG / PNG 编码及人为停留；最终最大 **1.567 秒**。仍有超过 1 秒的站点：golden-q04 1.003 秒；baseline-report 1.567 秒。未声称全部达标。

来源：`record-final.txt`、`output/demo-backup/audit.json`、`video-accepted.json`、`video-encoding.txt`。上述时间是本机本次预热后的测量，不保证仅等待概览 30 秒就能让所有首次详情冷读都小于 1 秒。

| 顺序 | 站点 / 本机截图 | 就绪秒 |
|---:|---|---:|
| 1 | `output/demo-backup/01-overview.png` | 0.286 |
| 2 | `output/demo-backup/02-overview-story.png` | 0.119 |
| 3 | `output/demo-backup/03-overview-business.png` | 0.164 |
| 4 | `output/demo-backup/04-knowledge-pipeline.png` | 0.268 |
| 5 | `output/demo-backup/05-knowledge-topics.png` | 0.120 |
| 6 | `output/demo-backup/06-golden-summary.png` | 0.343 |
| 7 | `output/demo-backup/07-golden-negative.png` | 0.145 |
| 8 | `output/demo-backup/08-golden-q45.png` | 0.242 |
| 9 | `output/demo-backup/09-golden-q04.png` | 1.003 |
| 10 | `output/demo-backup/10-pipeline.png` | 0.277 |
| 11 | `output/demo-backup/11-baseline-report.png` | 1.567 |
| 12 | `output/demo-backup/12-baseline-more-metrics.png` | 0.158 |
| 13 | `output/demo-backup/13-baseline-gates.png` | 0.163 |
| 14 | `output/demo-backup/14-baseline-safety-details.png` | 0.179 |
| 15 | `output/demo-backup/15-baseline-bad-cases.png` | 0.165 |
| 16 | `output/demo-backup/16-baseline-retrieval.png` | 0.169 |
| 17 | `output/demo-backup/17-baseline-q04.png` | 0.216 |
| 18 | `output/demo-backup/18-agent-round1.png` | 0.455 |
| 19 | `output/demo-backup/19-agent-round2.png` | 0.119 |
| 20 | `output/demo-backup/20-agent-round3.png` | 0.126 |
| 21 | `output/demo-backup/21-agent-route-d.png` | 0.119 |
| 22 | `output/demo-backup/22-agent-d-report.png` | 0.201 |
| 23 | `output/demo-backup/23-agent-abc.png` | 0.200 |
| 24 | `output/demo-backup/24-agent-sandbox.png` | 0.118 |
| 25 | `output/demo-backup/25-agent-regression-recommendation.png` | 0.166 |
| 26 | `output/demo-backup/26-agent-final-recommendation.png` | 0.117 |
| 27 | `output/demo-backup/27-release.png` | 0.263 |
| 28 | `output/demo-backup/28-release-report.png` | 0.147 |
| 29 | `output/demo-backup/29-release-config.png` | 0.167 |
| 30 | `output/demo-backup/30-comparison-q04.png` | 0.353 |
| 31 | `output/demo-backup/31-comparison-q24.png` | 0.151 |
| 32 | `output/demo-backup/32-comparison-q38.png` | 0.168 |
| 33 | `output/demo-backup/33-live-interface-only.png` | 0.937 |
| 34 | `output/demo-backup/34-online-feedback.png` | 0.133 |

## 测试、数据与服务

- 前端最终 `npm test`：102 个文件、600 条通过，0 失败。`npm run build`：TypeScript 与 Vite 通过。来源：`frontend-final.txt`、`build-final.txt`。
- 后端 `python3 output/task024c/run_backend.py`：运行 1459 项，0 失败、0 错误，21 项既有跳过，615.108 秒。跳过名称与原因和 024b 的结果逐项一致，没有新增跳过、删测试或改断言。来源：`backend-full.txt/json` 与 `output/task024b/backend-full.json`。
- 后端 runner 在导入 app 前设置临时数据库、空 env、索引、文档、上传与诊断目录，强制 Mock，并阻止外网 socket；使用 TemporaryDirectory 自动清理。没有复制正式数据库或调用真实 Provider。来源：`run_backend.py`。
- React act / 服务端 useLayoutEffect 仍有既有测试警告；后端故障注入有预期异常输出。套件通过不等于所有日志零警告。来源：最终前后端测试日志。
- workspace、evaluation、optimization、versions、monitoring、documents、dataset 七组保存响应，开工与最终规范化 SHA-256 相同。这只证明核对的 API 响应未变，不声称整个 DB 文件字节不变。来源：`state-before.json`、`state-final.json`。
- DeepSeek 调用 0 次，其他真实模型调用 0 次；没有启动评测、发布、回滚或新增问答 / 线上反馈，没有修改 Golden、评测数据及门槛。来源：全部浏览器写请求为 0、隔离后端网络限制、最终数据核对和代码差异。
- 截图例外仅有 README 六张 JPG；本机视频、路线 PNG、原始响应和日志均被 Git 忽略。单张 JPG 小于 600KB。只读 `git diff --check` 通过。

## 待回答问题

1. “没有禁用词”是否也要求隐藏题目和参考答案原文中的词？本轮按硬约束保留 Q20 的“内部错误”、Q45 参考答案的“内部指令”等保存原文。页面自写展示说明未发现其余禁用词或原始内部编号；字面上的整页零命中没有达成，也没有等待用户确认。
2. 本次成片采用“概览 30 秒 + 实际只读路线预热”。完整内容就绪计时仍有 Golden Q04 抽屉 1.003 秒、Baseline 诊断区 1.567 秒，未达到每站不超过 1 秒；Q45 首次冷读也曾超过 1 秒。该项未完全达标，保留现有读取 / 缓存策略，未把读取中或尚缺诊断区的首帧算成就绪，也没有扩大到后端改造。其余各站不超过 1 秒。
3. 21 项既有跳过依赖未分发的私有 Judge 回包、历史源码或只读 CSV，相关历史证据验证仍为未知；本次没有新增跳过。

上述边界已留证，其余工作完成，不等待回复。保存、提交和推送由值班脚本负责，脚本后续推送结果未知。已用普通 `mv` 将本单归档至 `指挥/历史任务/024c-终版走查README截图与备份录屏.md`；demo 服务保留，本轮浏览器与测试进程已退出。
