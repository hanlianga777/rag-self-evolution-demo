# 021u2：概览讲解区与 Pipeline 紧凑参数验收报告

## 结果

本任务已完成：接入概览讲解区和 Pipeline 紧凑参数区，移除页面中的运行设置及内部机制说明，核对题号徽章随卡片滚动。没有改 `frontend/src/ui/` 的组件设计，没有改后端、正式数据、Golden、门槛、运行设置值，没有发布或回滚。No SPEC Change。

相关测试 105/105 通过，TypeScript 检查和生产构建通过。全量 507 项中 450 项通过、57 项失败；这些失败全部在开工前存在，也全部在 021s 的失败清单里，新增失败为 0。不能把全量说成全绿。来源：下方测试表和本机测试 JSON。

没有执行 Git 写命令。任务完成后用普通 `mv` 归档任务单，提交和推送交给值班脚本。原 demo 保持运行。

## 接手检查与理解

开工工作区干净，最近提交有 021u、021u1 和本任务开始记录，没有本任务半成品或已有报告。总指挥提供的 `OverviewStory`、`ParamGrid` 和徽章类名修复已经存在，页面尚未接入；本次从这些成果继续。来源：开工 `git status --short`、`git log -8 --oneline`，起点 `0b16d47`。

我是这样理解的：

- 原参数的 Top-K 选项会禁用大于候选数的值；新组件没有逐选项禁用字段，又不允许改组件设计，所以页面过滤这些暂不可选的值。候选数增大后，选项自动恢复。Hybrid Search 关闭时权重仍整行禁用，保存时仍移除无效权重。
- 草稿操作合并为同一个紧凑操作条；改动较多时 chip 自然换行，避免横向溢出。保存、放弃仍使用原接口、草稿身份和刷新逻辑。
- 日期按浏览器本地时区显示 `MM-DD HH:mm`。架构图本身属于技术讲解；保留架构关系，但删掉其中的“运行调度 / 平价时段 / 断点续跑”三处文字。
- 完整保存证据和原始审计数据继续保留在原有折叠审计中；业务展示中的内部 ID 改为状态文字。未挂载的 `RuntimeSettings`、`UnattendedAuthorization` 组件文件保留，不改其后端值或执行逻辑。

## 数据接入来源

| 展示 | 数据与处理 | 源码 |
| --- | --- | --- |
| 每轮优化过程 | 复用 `buildEvolutionModel` 的 rounds.summary；含 Winner 的轮次高亮；点击进入 `#evolution?tab=route` | `pages/OverviewPage.tsx`、`ui/evolution/model.ts` |
| Candidate D | 用 D 与保存 Winner 的修复题集合做差，再按 production.provenance 与 candidate_id 判断是否发布；当前是“多修好 Q04；已发布” | `pages/OverviewPage.tsx` |
| 修好的题 | 推荐方案完整结果的 all_fixed_question_ids；题目原文读取同次 Baseline 的 comparison-cases | `pages/OverviewPage.tsx` |
| 本题关键参数 | 读取两次保存的单题详情，复用 Before/After 的 `comparisonPoints`、`explanation`、`configChanges`；核对两次评测完成、Judge 身份及题卷一致；读取失败不猜原因 | `components/comparisonData.ts`、`pages/OverviewPage.tsx` |
| 当前四题 | Q04 为 Top-K 4 → 6；Q24、Q29 为 Candidate K 12 → 24；Q38 没有可确认的关键参数，留空 | 本机 `probe.json` 和概览截图，均来自已保存评测 |
| 直接选题 | `#verification?tab=compare&q=Q24` 等；匹配真实 question_id 或短题号；不带参数时仍用原页签和默认选题逻辑 | `pages/VerificationPage.tsx`、`components/SavedAnswerComparison.tsx` |
| Pipeline | 分组沿用 settingsGroups，选项来自 search_space.allowed；草稿、Baseline、已发布线上配置分别传给 value / baseline / online；提示复用 parameterNotes 和依赖说明 | `pages/SettingsPage.tsx` |

以上源码路径均相对于 `frontend/src/`。本次只读取保存结果，没有重新生成回答、重判或重新跑实验。

## 撞名检查与滚动验收

使用 TypeScript 语法树扫描 `frontend/src` 所有非测试 TSX 的 className，包括字面量、模板片段和条件分支，检查单独的 `fixed / absolute / relative / sticky / hidden / block / flex / grid / table / truncate / invisible / collapse` 等指定名字，没有发现新的同类撞名。来源：本机 `collision-scan.json`（空数组）。CSS 中旧的 `.ui-q.fixed` 静态兜底和 `.truncate` 声明没有对应的当前同名 className，不改无关历史样式。

最终截图复查还发现：共享组件在 1320px 以下默认把事实字段改成单列，所以 1280px 下徽章虽然随卡片滚动，却落在“修好”下方。先用浏览器断言复现，再在 `styles.css` 加仅限 Agent 页、1200–1320px 的两列适配，恢复标签左、徽章右；共享组件文件未改。来源：`ui/ui.css` 的响应式规则、本机 `alignment-red.txt`、最终 `badges.json`。

原徽章已由总指挥改为 `is-fixed / is-broken / is-open / is-neutral`，本次没有重复修改。两种尺寸分别测了路线卡片中全部 17 个“修好”徽章，包含 Q38、Q06；页面滚动 350px，全部徽章的屏幕纵坐标也移动 350px，计算样式都不是 fixed。修好徽章位于“修好”标签右侧，卡片点击仍打开原详情抽屉。来源：`ui/Primitives.tsx`、`ui/evolution/EvolutionTimeline.tsx`、本机 `badges.json`、中段截图。

## 删除与改写的展示文字

| 位置 | 原文 / 原展示 | 处理 |
| --- | --- | --- |
| SettingsPage | “当前线上配置”整块及参数列表 | 删除，用参数选项蓝点标出线上值；图例“当前线上：Candidate D” |
| SettingsPage | “运行设置”、只在平价时段运行、无人值守授权、授权人/授权时间等 | 移除 RuntimeSettings 渲染及 import，组件文件保留 |
| EvolutionPage 规划详情 | “无人值守设置”及授权组件 | 删除页面渲染及 import |
| SettingsPage | “配置草稿尚未生效……”长句 | 收进草稿操作条的 ⓘ，仍说明需新 Baseline 才生效 |
| SettingsPage | “Baseline → 草稿参数变化”及独立差异块 | 删除，改为同一操作条中的 ParamChip |
| SettingsPage | 每个参数的大卡说明、依赖关系 | 收进参数名旁 ⓘ；固定技术基座压成四列字段 |
| OverviewPage | “等待平价时段继续 Sandbox”“已保存断点，等待平价时段” | 改为“Sandbox 已暂停”“已暂停，进度已保存”；移除下一步说明中的断点机制 |
| EvolutionPage | 阶段说明、状态栏、候选状态/进度中的“高峰时段暂停”“等待平价时段” | 改为“已暂停”“排队中”，保留已完成题数 |
| EvolutionStory.DStory | “Candidate D · 等待非高峰时段”“到可运行时段自动继续” | 改为“Candidate D · 排队中”“已排队，稍后自动继续” |
| RuntimeSettings.PricePauseNotice | 后端价格原因、原始暂停时刻、“将从断点继续” | 业务通知改为“已暂停，稍后自动继续”“已完成进度已保存” |
| 同一暂停通知确认区 | “高峰价运行确认”“立即运行会按高峰价计费；仅本任务临时忽略平价时段限制”“确认按高峰价运行本任务”“继续等待平价时段” | 改为“立即运行确认”“立即运行本任务将产生模型费用”“确认立即运行本任务”“继续等待”；原目标和 acknowledge_peak_price 请求字段不动 |
| operation | “保存断点”“断点已保存”“当前断点不能继续” | 改为保存进度/进度已保存/当前进度不能继续；停止和恢复逻辑不动 |
| EvolutionPage 候选详情与确认说明 | “续跑预检与费用”“使用保存的断点，只补……” | 改为“运行进度与费用”“继续完成尚未结束的评测”；保留实际费用及禁止继续的原因 |
| EvaluationPage | 预检提示中的“历史断点”、恢复状态中的“断点” | 改为进度，自动恢复逻辑不动 |
| EvaluationPage / VersionsPage / VerificationPage | 长日期、秒、固定时区或完整 toLocaleString | 统一调用 localShortTime，显示本地 `MM-DD HH:mm`；无效日期显示未知 |
| VerificationPage 进化上下文抽屉 | Trigger ID、实验 ID、Baseline ID | 改为反馈状态、关联优化是否建立、当前/历史 Baseline；人工确认和启动仍传原 ID |
| KnowledgePage | “Child Embedding → K-means 动态聚类 → 知识主题 → 覆盖分析 → …配额 → Golden 题位” | 改为“根据文档主题检查知识覆盖，并安排正向、消融和负向测试题” |
| KnowledgePage | “碎片保护 · 阈值 < N Child …”及技术解释 | 删除该展示，知识覆盖计算和详情按钮保留 |
| `docs/images/architecture-technical.svg`（页面实际引用资源） | “运行调度”“平价时段”“断点续跑” | 删除三个文字节点，保留其余架构图 |

完成后对 8 页、20 个页签/视图的可见文字扫描：没有发现指定内部关键词、EXP/MON/run_ 编号或 ISO 长时间戳；这 20 个视图无全局横向滚动、无脚本错误。未挂载组件和源码注释内仍有内部词，不属于页面可见文字。来源：本机 `text-scan.json`、`text-scan.txt`。

## 功能点验与截图

使用真实保存数据读取页面；所有浏览器非 GET API 请求均被拦截。仅 `/api/pipeline/draft` 的两次请求在浏览器内返回模拟结果，未送正式后端。未点击实时提问、模型生成、发布或回滚。

| 项目 | 验收事实 |
| --- | --- |
| Pipeline | 12 个参数逐项切换，共点 35 个可用选项；核对选中状态；Hybrid 关闭后 3 个权重按钮禁用，开启后恢复 |
| 草稿 | 点保存和放弃，核对原接口、请求体与身份；模拟保存后出现已保存状态；放弃请求 config=null |
| 可选参数 | 抽屉可打开、12 行范围表完整、关闭正常 |
| 概览 | 4 项优化过程均跳进化路线；4 道修复题均跳 Before/After 并直接选中对应题号 |
| 进化路线 | 9 张 A/B/C 卡片逐项点击，原详情抽屉打开和关闭正常 |
| 徽章 | 两个尺寸的全部 17 个修好徽章随滚动移动，无固定悬浮 |
| 1440×900 | 概览讲解区底部约 850px；参数区高 480px；整个 Pipeline 内容只需约 79px 滚动即可到底 |
| 1280×800 | 参数区仍高 480px；整个 Pipeline 内容滚动约 179px 即可到底，小于半屏；另保存概览和 Pipeline 底部截图 |
| Gallery 对照 | 已打开 `/ui-gallery.html`，保存讲解区与参数区截图，使用原组件的两列、浅灰轨道、选中块和标记点设计；真实选项/顺序以原 search_space 为准 |
| 错误检查 | 核心点验脚本 errors=0；全站 20 视图脚本 errors=0；均无全局横向滚动 |

来源：本机 `acceptance.json`、`badges.json`、`text-scan.json`。本机截图与记录目录：`output/task021u2/`（忽略目录，不上传）。

截图文件：

- `1440x900-overview.png`、`1280x800-overview.png`；同尺寸 `overview-bottom.png`。
- `1440x900-settings.png`、`1280x800-settings.png`；同尺寸 `settings-bottom.png`。
- `1440x900-evolution-middle.png`、`1280x800-evolution-middle.png`。
- `gallery-overview.png`、`gallery-parameters.png`。

## 测试与旧断言调整

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 开工第一步 `npx tsc -b` | 通过 | 前端目录命令退出 0 |
| 开工 `npx vitest run src/ui` | 3 文件、20 项通过 | 开工工具结果 |
| 新接入测试先失败后通过 | 3 个功能缺失断言先失败，接入后通过；另为技术架构残留内部文字加失败断言，再删除对应 SVG 文字通过 | `red.txt`、`architecture-red.txt`、相关测试 JSON |
| 最终相关测试 | 105/105 通过 | `related.json` |
| 最终 `npm run build` | TypeScript + Vite 通过 | `build.txt`，退出 0 |
| 开工全量 | 504 项：446 通过、58 失败 | `tests-before.json` |
| 最终全量 | 507 项：450 通过、57 失败 | `tests-final.json` |
| 与开工比较 | 新增失败 0；修复 1 条已有过期测试断言 | 两份 JSON 按文件和用例名做集合差 |
| 与 021s 比较 | 剩余 57 条全部包含在原 61 条失败清单中，新增失败 0 | `指挥/报告/021s-UI基础层接入.md` 和最终 JSON |
| Diff | `git diff --check` 通过 | 本轮命令输出 |

测试调整只对应本任务的控件和文案变化：

| 测试文件 | 原来验证什么 | 现在怎样继续验证 |
| --- | --- | --- |
| pipeline-draft-ui、round0-pipeline | 选中参数、保存后恢复草稿、无效 Alpha 移除 | aria-pressed 改成 radio 的 aria-checked；差异改查 chip；参数说明先聚焦 ⓘ 再断言。原 POST 请求体、Baseline 不变断言保留 |
| freeze-polish | 草稿只显示不同于 Baseline 的值 | 改查 pipeline-draft-chips，继续检查 4 → 6 和不显示未改参数 |
| interview-assets、operation | 页面分组和 Pipeline 请求不含 Provider 操作 | 移除已删除的运行设置区块/GET 断言，继续核对当前分组、只读 Pipeline 请求及无 Provider 入口 |
| interview-evaluation | Agent 规划区结构 | 列表移除已删除的“无人值守设置”，保存假设及决策验证继续保留 |
| task021o-release | 线上配置与 Baseline 区分 | 夹具补真实 allowed 选项，逐项核对蓝点在线上值、灰点在 Baseline 值，确认旧线上配置块删除 |
| task016a-runtime | 暂停轮询、确认后才覆盖、精确传目标、错误后仍暂停 | 继续直接测保留组件；只把内部时段文字换成中性提示。旧“问题诊断”入口改查现有路线规划及 D 排队状态，原恢复与请求断言保留；这修复了 021s 已记录的 1 项失败 |
| task018a-agent、task021b-story | 保存暂停题数、D 状态优先级 | 换中性暂停/排队文字，计数和状态优先级断言不动 |
| ui-polish | Baseline 本地时间与内部 ID 不外露 | 检查本地短日期时间，继续检查不显示运行 ID |
| interview-release、v14-ui-contract | 关联监控上下文、历史上下文不能在新 Baseline 启动 | 抽屉改查状态及关联是否建立，保留原 trigger_id 请求、历史只读、禁用启动和无写请求断言 |
| overview-architecture | 内联架构图、无开发者披露 | 增加不含平价/断点续跑文字的断言，原图结构与 ID 唯一性验证保留 |
| 新增 task021u2-integration | 紧凑参数及跳转接入 | 核对 Top-K 依赖过滤、Alpha 禁用、chip、原题和证据支持的关键参数；直接打开默认修复筛选以外的题目 |

除上表外，没有为消除旧失败而改业务逻辑或冻结规则。相关命令输出有原有 React act 环境警告，不影响通过计数。全量失败明细继续保存在本机 JSON；不是全部通过。

## 数据、调用与进程

本任务发起模型调用 0 次。浏览器正式 API 只允许 GET；草稿保存/放弃使用浏览器内模拟，未送服务器。没有新建评测或实验。来源：验收脚本、拦截记录、单测 fetch 模拟。

正式库以 `mode=ro` 和 `PRAGMA query_only=ON` 读取，验收前后全部 33 张表的行数及全内容摘要一致，包括运行设置、监控、评测、实验和草稿。来源：本机 `before-hashes.json`、`after-hashes.json`。没有复制正式数据库，也没有生成备份；没有把截图、日志或数据库放进公开产出。

原前端 127.0.0.1:5174（PID 1117）和后端 127.0.0.1:8010（PID 19536）保持运行，没有启动或重启它们。验收浏览器均已关闭；临时测试不写正式库。

## 待回答问题

本任务没有阻塞项。全量仍有 57 项历史失败，是否另开任务处理未知；它们均在 021s 基线中，详细用例可对照该报告与本机 `tests-final.json`。本轮按“新增失败为 0”的任务标准完成，不等待确认。
