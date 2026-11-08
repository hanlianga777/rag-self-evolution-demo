# 任务 021v：接入总指挥写好的 Baseline 首屏、发布页上半部、最终推荐新版（不调用模型，自动值班）

用户已授权：中间所有确认默认同意，不要停下来等人。在 021u 之后执行。**UI 代码由总指挥编写，Codex 负责接入、测试、验收。原有已跑通的功能和按钮一个都不能坏。**

## 总指挥已经提交的代码
| 文件 | 用在哪 |
| --- | --- |
| `frontend/src/ui/baseline/BaselineHero.tsx` | Baseline →「Baseline 报告」首屏：一行转折小字（"11 项 Hard Gate 全部通过，仍有 6 个 Bad Case"）、四格（Hard Gate / 答对 / Bad Case 分层 / Thinking 档位 + P50、P99）、耗时构成堆叠条（Generation 最大块高亮） |
| `frontend/src/ui/release/ReleasePanel.tsx` | 发布页上半部：当前线上 ↔ 待发布方案、配置差异、成绩摘要、**三个独立状态**（① 推荐报告确认 ② 满足发布条件 ③ 发布批准）、确认发布按钮；发布后自动切换为"已发布方案" |
| `frontend/src/ui/evolution/FinalRecommendation.tsx` | Agent →「最终推荐」：推荐理由，Winner 与 Candidate D 两个合格方案的对比表（较好的一方加粗，C 更快也如实加粗），其他 Candidate 落选理由表 |
| `frontend/src/ui/PageSamples.tsx` | 以上三块的目标效果，见 `/ui-gallery.html` |

第一步先跑 `npx tsc -b` 和 `npx vitest run src/ui`，有错误只做最小修正。

## 1. Baseline 报告
- **替换**：原来的"门槛已通过"横幅和四个指标卡，加上耗时拆解表，换成 `BaselineHero`。
- **props 的来源**：
  - `gates`、`correct`、`badCount`：现有的 Hard Gate 和答对数据；
  - `layers`：Bad Case 按现有分类计数；
  - `thinking`：Baseline 运行配置里的 Thinking 档位，显示 Max；
  - `p50`、`p99`：Hard Gate 里的实际值；
  - `stages`：现有耗时拆解的每一行，`share` 直接用页面原来算好的占比，保证和原表数字一致（Generation 95.8%）。
- **原耗时拆解表**：不删，移进本页"更多指标"折叠，和 Recall@K、Precision@K、MRR、Token、费用、首字时间放在一起。GPT 方案的原则是"下沉，不删除"。
- 「Hard Gate」「Bad Case 诊断」页签不动。

## 2. 发布页上半部
- **替换**：原"待发布方案 / 已发布方案"区块，以及"当前线上配置"区块里重复的成绩部分，换成 `ReleasePanel`。
- **props 的来源**：
  - `online`、`candidate`：现有的 `currentVersion.config` 和推荐方案的 `config`；参数显示 Candidate K、Top-K、Thinking，术语按 021r。
  - `changes`：两者差异。
  - `results`：Baseline 对推荐方案。
  - `steps.reportConfirmed`：用 `reportConfirmation`。
  - `steps.eligible`：用 Hard Gate 全过、零新增 Bad Case、修好数，沿用现有 `checks` 的数据。
  - `steps.released`：用 `currentReleased` 和发布时间。
- **两个回调**：
  - `onRelease` **必须走现有流程**：`setConfirmation({ kind: "release", item: candidate })` → 现有 `ConfirmDialog` → 现有 `release()`。
  - `canRelease` 用现有的 `canRelease(candidate)`。
- **下半部不动**：当前线上版本详情、完整配置抽屉、"查看其他候选方案"抽屉、版本历史与回滚表、回滚确认框，结构都保留，只跟随 `ui.css` 换肤。

## 3. 最终推荐
- **替换**：「最终推荐」页签的内容换成 `FinalRecommendation`。
- **props 的来源**：
  - `chosen`、`runnerUp`、`others`：用 021u 已接入的 `buildEvolutionModel` 结果。`chosen` 是推荐方案（D），`runnerUp` 是 Winner（Round 3 · C），`others` 是其余 8 个。
  - `reason`：用现有的 `recommendationReason(experiment)` 输出，术语按 021r。
  - `onRelease`：跳到发布页。已发布时 `releaseLabel` 写"查看发布记录"。
  - `onOpen`：打开现有方案详情抽屉。
- **保留**："人工报告确认已完成"的提示，以及"生成智能组合建议"按钮在需要时的显示逻辑，放到合适位置，**不能丢**。
- 021o 写的 `alternativeReason` 如果不再使用，可以删除，但要确认没有别处引用。

## 4. 现有功能一个都不能坏
- **改之前**：列出这三页的所有按钮、抽屉、确认框、分页、筛选。
- **改之后**：逐项点一遍。发布、回滚、生成方案这类按钮只确认能弹出确认框，**不真的执行**。如果 021q2 已经发布，就检查发布后的状态显示。
- **测试**：全部前端测试通过。改了测试的，写明原测试在验证什么、新测试怎样继续验证同一件事。

## 5. 验收
- **截图**：1440×900 和 1280×800 两个尺寸，拍以下画面，并和 `/ui-gallery.html` 对照：
  - Baseline 报告首屏；
  - 发布页上半部（按实际状态，发布前或发布后）；
  - 最终推荐页签。
- **差异**要在报告里列出并说明原因。
- **检查**：没有全局横向滚动、没有脚本错误；数字和改前一致。

## 硬性约束
- 不调用模型，不改评测数据，**本任务不发布、不回滚**。
- 不改 `frontend/src/ui/` 组件的设计，只允许最小类型修正。
- 不要运行 git 写命令；不改 `指挥/当前任务.md`；demo 保持运行。

## 报告
写到 `指挥/报告/021v-Baseline发布推荐接入.md`，写明：
- tsc 和 vitest 结果；
- props 的数据来源；
- 功能清单前后核对表；
- 截图路径（只存本机）；
- 和样板的差异。

## 完成后
用普通的 `mv` 把本任务单移到 `指挥/历史任务/`。
