# 任务 021u2：概览讲解区、Pipeline 紧凑参数区、清理内部设置与日志式文字，修复题号徽章悬浮 bug（不调用模型，自动值班）

用户已授权：中间所有确认默认同意，不要停下来等人。在 021u1 之后执行。**UI 代码由总指挥编写，Codex 负责接入、测试、验收。原有已跑通的功能和按钮一个都不能坏。**

## 用户 11-08 04:43 的反馈（原话摘要）
1. Agent 工作台进化路线：卡片里"修好"一行的题号徽章（Q38、Q06）**固定在屏幕上，滚动时不跟着走**。
2. 概览、问答验证 Before/After 下方有大片空白，"显得画面太空"。可以放有助于面试讲解的内容，但不要强行加。
3. Pipeline 配置的选择模块要换得更高级，而且不要占太多上下空间（"滚轮要滑好一会儿才能看到全部"）。
4. 最下面的"峰谷设置"等内部机制不需要在前端展示；"很像日志化的技术参数表达，这些都没有必要去呈现"。

## 总指挥已经提交的代码
| 文件 | 内容 |
| --- | --- |
| `frontend/src/ui/Primitives.tsx`、`ui.css` | **bug 修复**：题号徽章的状态类名原来是 `fixed`，和 Tailwind 的 `.fixed { position: fixed }` 撞名，所以"修好"的徽章被钉在屏幕上。已改成 `is-fixed / is-broken / is-open / is-neutral` |
| `frontend/src/ui/overview/OverviewStory.tsx` | 概览讲解区：左"优化过程"（每轮一句话 + Candidate D），右"修好的 N 道题"（题号 + 题目一行 + 本题关键变化，点击去 Before/After） |
| `frontend/src/ui/settings/ParamGrid.tsx` | Pipeline 紧凑参数区：按 Pipeline 位置分 4 组、两列排布，每个参数一行；参数名旁 ⓘ 悬停看说明；分段选择器（浅灰轨道 + 白色选中块）；选项右上角小点：灰 = Baseline、蓝 = 当前线上 |
| `frontend/src/ui/extra.css` | 以上两个组件的样式 |
| `frontend/src/components/SavedAnswerComparison.*` | Before/After 左侧题目列表下方加了"整体变化"小卡（验收在 021w2） |

目标效果见 `/ui-gallery.html`（"概览 · 项目概览"下方、"Pipeline 配置 · Agent 可调参数"）。第一步先跑 `npx tsc -b` 和 `npx vitest run src/ui`，有错误只做最小修正。

## 1. 题号徽章 bug
- 打开 Agent 工作台 → 进化路线，滚动页面，确认"修好"一行的题号跟着卡片走，排在"修好"标签右边。
- **全站检查同类撞名**：在 `frontend/src` 里查 `className` 中单独出现的 Tailwind 工具类名（`fixed`、`absolute`、`relative`、`sticky`、`hidden`、`block`、`flex`、`grid`、`table`、`truncate`、`invisible`、`collapse` 等）。
  - 本意不是用 Tailwind 工具类的，改名，加前缀或 `is-`。
  - 报告列出查到的位置和处理。

## 2. 概览讲解区（`OverviewSummary` 流程条下方）
- **`turns`**：
  - 用 021u 已接入的 `buildEvolutionModel` 结果：每轮一项，`label` = `Round N`，`text` = 该轮 `summary`；出现 Winner 的那轮 `key: true`。
  - 最后一项 Candidate D：`text` 用 D 比 Winner 多修好的题和当前状态（已发布 / 待发布）拼一句，例如"在 Winner 上精修，多修好 Q04；已发布"，`key: true`。
  - 每项 `onClick` 跳到 Agent 工作台进化路线。
- **`fixed`**：
  - 推荐方案（D）修好的题。`question` 用题目原文。
  - `cause` 用这道题的关键配置变化，例如"Top-K 4 → 6"，和 Before/After 因果链里标"本题关键"的是同一个。
  - 拿不到就不传 `cause`，**不许猜**。
- **`onOpenFixed(id)`**：跳到问答验证 → Before/After，并**直接选中这道题**。
  - 如果现在不支持带题号跳转，加一个最小实现（例如 hash `#verification?tab=compare&q=Q04`，或 App 级状态）。
  - 不影响直接点导航进入时的默认选中逻辑。
- **验收**：1440×900 下首屏到讲解区底部基本没有大块空白。不要为了填满再加别的内容。

## 3. Pipeline 配置页
1. **参数区**：「Agent 可选参数」里原来的大卡片换成 `ParamGrid`。
   - **分组**：沿用 `settingsGroups`，icon 依次用 `target` / `data` / `layers` / `thinking`。
   - **`options`**：来自 `search_space[key].allowed`，文字用现有 `formatValue`。
   - **其他字段**：
     - `value` = 草稿值；
     - `baseline` = `baseline_config[key]`；
     - `online` = 当前线上配置值（仅当线上版本是已发布方案时传，否则不传）；
     - `note` = 现有 `parameterNotes`，依赖说明（"仅开启 Hybrid Search 时生效"等）拼进 `note`；
     - `disabled` 沿用原逻辑；
     - `changed` = 草稿与 Baseline 不同。
   - **`onChange`**：直接用现有 `change(key, value)`。**草稿保存 / 放弃的行为不变。**
2. **删掉「当前线上配置」区块**：同样的信息已由蓝点标在参数上，图例写"当前线上：Candidate D"即可（通过 `legend.online` 传文字）。
3. **草稿操作区压缩成一行**：
   - 一行包括："N 项已修改" + 每项一个 `ParamChip`（Baseline 值 → 草稿值）+ 放弃修改 + 保存草稿；
   - 删除"配置草稿尚未生效……"长句，必要的话收进 ⓘ；
   - 删除"Baseline → 草稿参数变化"整块，chip 已经表达。
4. **「固定技术基座」**：保留，排成紧凑的两列或四列小字段，不要占大块高度。
5. **删除「运行设置」**（无人值守授权、只在平价时段运行）：从页面移除 `<RuntimeSettings />` 的渲染。
   - **后端设置值和逻辑不动**，组件文件先保留。
   - 如果有测试专门测这个页面区块，改为直接测组件或删掉该断言，报告写明。
6. **验收**：1440×900 下参数区（4 组 12 个参数）一屏内看完，或者最多滚半屏。

## 4. 全站清理内部机制和日志式文字
**范围**：搜索所有页面上**会显示出来**的文字。
- **删掉以下关键词对应的展示**：平价、高峰、峰谷、价格时段、无人值守、授权人、授权时间、断点续跑（指运行机制说明的地方）。
  - 逻辑保留，只删展示。
  - 运行浮窗等待状态里如果还有"等待平价时段"之类，改成中性的"排队中 / 已暂停"。
- **日志式表达改成人话或删掉**：
  - 原始时间戳，例如 `2026-11-05T14:30:48.354337+00:00`，统一改成"11-05 09:30"这类本地短格式，或者不显示；
  - 内部 ID，例如 `EXP-…`、`MON-…`、`run_…`；
  - 带箭头的长串处理流程、阈值、内部开关名。
- **报告**：每处列出位置、原文、处理（删 / 改写 / 收进 ⓘ）。

## 5. 现有功能一个都不能坏
- 逐项点：
  - Pipeline 每个参数切换、放弃修改、保存草稿、"查看可选参数"抽屉；
  - 概览讲解区每一项跳转；
  - 进化路线卡片点击。
- **测试**：相关测试通过；全量和 021s 基线对照，新增失败为 0。改了测试的，写明原测试验证什么、新测试怎样继续验证。

## 6. 截图验收
- 1440×900 和 1280×800 两个尺寸；
- 页面：概览、Pipeline 配置、Agent 进化路线（滚动到中段）；
- 与 `/ui-gallery.html` 对照；
- 检查：无全局横向滚动、无脚本错误。

## 硬性约束
- 不调用模型，不改评测数据、Golden、门槛，不发布，不回滚，不改后端运行设置的值。
- 不改 `frontend/src/ui/` 组件的设计，只允许最小类型修正。
- 不要运行 git 写命令；不改 `指挥/当前任务.md`；demo 保持运行。

## 报告
写到 `指挥/报告/021u2-概览讲解区与Pipeline紧凑参数.md`，写明：
- tsc 和测试结果；
- 撞名检查结果；
- 数据来源；
- 删除和改写的文字清单；
- 截图路径（只存本机）。

## 完成后
用普通的 `mv` 把本任务单移到 `指挥/历史任务/`。
