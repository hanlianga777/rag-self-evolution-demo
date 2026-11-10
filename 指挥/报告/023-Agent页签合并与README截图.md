# 023 Agent 页签合并与本轮经验改写

## 当前结果

Agent 工作台已由五个页签合为「进化路线 / 方案对比 / 回归与推荐」，旧链接和旧页签记忆继续可用。本轮经验改成完整句，含前缀分别为 60、54、49 字。前端全量 99 文件、589 条通过，构建通过；两种尺寸浏览器验收无全局横向滚动、无脚本错误。后端从额度中断处续跑后，全量覆盖完成：运行计数 1459，0 失败、0 错误，保留 21 项既有跳过。

本次不调用模型，不改评测数据、Golden、门槛或 Agent 推理原文，不发布、不回滚、不新增问答。DeepSeek 及其他真实模型调用均为 0。现有 demo 保持运行。

来源：`frontend/src/pages/EvolutionPage.tsx`、`frontend/src/ui/evolution/model.ts`；本机 `output/task023/frontend-verified.txt`、`build.txt`、`browser-acceptance.json`、`state-verified.json`。

## 从哪里接着做

- 开工原工作区无未提交改动，先检查了规则、任务单和历史，没有找到 023 已有实现。
- 上轮额度中断后，值班脚本保存了 `49a5b37`「自动值班进行中（未完成，已做部分）」，`153bf9a` 记录额度用完。本次继续保留其中的页签、经验、测试和浏览器验收成果，没有重做已经完成的前端全量与截图。
- 后端原日志已有 998 个测试运行结果和 1 个类级跳过，最后停在 `test_sandbox_stability.FiftyQuestionMatrixTests.test_abc_fifty_question_fault_matrix_and_second_round_isolation`，没有最终汇总，也没有仍在运行的原进程。续跑按日志排除已完成项及已跳过的类，只补剩余 461 项；不把上轮进程停止说成测试通过。
- 当前任务单已由 `4b371fb` 调整：README 截图移到 024c，本任务不做。上轮按旧单拍摄并暂时加入 README 的 6 张图已移到本机 `output/task023/deferred-readme/`，撤下对应预览节，README 内容恢复到本任务开始前。没有重拍，也没有删除这些素材。024c 应在全站修改完成后产出正式预览。

**我是这样理解的**：以续跑时队列中的最新任务单为准；用户要求“已完成的不要重做”，所以复用已完成检查，从后端日志断点补齐。最新任务单不再授权本轮提交 README 截图，因此保留本机素材，撤下前次临时预览。demo 使用开工已有前端 5174、后端 8010，不重启服务。

来源：只读 `git status / git log / git show`，队列 023 任务单；本机 `backend-full.txt`、`backend-completed-before-interruption.json`、`backend-resume-plan.json`、`frontend-verified.txt`、`screenshots.json`。

## 信息迁移对照

| 原页签 / 原区块 | 现在的页签与位置 | 保留方式 |
|---|---|---|
| 进化路线：Baseline 起点、答对数、Bad Case 分层和题号、诊断入口 | 进化路线，顶部起点行 | 原 EvolutionTimeline 与诊断跳转保留 |
| 进化路线：Round 1–3 标题、每轮结论 | 进化路线，按轮次顺序排列 | 原保存结果生成，不改判定 |
| 进化路线：各轮 A/B/C 方向、参数变化、修好题、新增题、Hard Gate、答对数、P50/P99、Winner 与最快标记 | 进化路线，每轮三张卡片 | 卡片与详情抽屉入口保留 |
| 进化路线：本轮经验、三套方案依据 HoverCard | 进化路线，各轮标题下 | 完整句；悬停和键盘聚焦依据保留 |
| 进化路线和 A/B/C/D：重复的 D 决策区 | 只留进化路线，Round 3 后 | 共用原 DStory；不再在方案对比重复放整块 |
| D 决策：头部结论、参数、唯一新增、Top-K 历史依据提示、Agent 预测原文 | 进化路线，D 决策区上部 | 原字段和 HoverCard 保留 |
| D 决策：预测 vs 实际、预期修复与保护题、Winner vs D、未修好原因卡 | 进化路线，D 决策区内部 | 原组件与保存事实保留 |
| D 决策：未生成、排队、运行、评测完成、无有效组合等状态 | 进化路线，D 决策区 | 原状态分支保留；未完成不编造结果 |
| D 完整报告、D 运行 / 继续按钮、最终推荐跳转 | 进化路线，D 决策区末尾 | 原抽屉及运行确认框保留；推荐跳到回归与推荐 |
| 进化路线：已验证配置与处理进度 | 进化路线，下方“Agent 规划 · 逐题覆盖详情”内 | 原折叠详情保留 |
| 进化路线：Baseline 运行参数 | 进化路线，同一规划详情内 | 原参数 chip 保留 |
| 进化路线：Agent 读到的事实、每题证据、优化方向、查看问题证据 | 进化路线，同一规划详情内 | 原内容与证据抽屉保留 |
| 进化路线：基线诊断摘要表 | 进化路线，同一规划详情内 | 原摘要折叠块保留 |
| 进化路线：Agent 提出的假设、问题与策略关联、详情、可调参数 | 进化路线，同一规划详情内 | 原摘要和入口保留 |
| 进化路线：Agent 得出的三张完整方案卡（与 A/B/C/D 重复） | 方案对比，上半部三张方案卡 | 重复区块合为一处；规划内仍保留独有事实、假设摘要和覆盖矩阵 |
| 进化路线：逐题实际覆盖矩阵、实际候选来源、参数与假设、验证要求及缺口 | 进化路线，规划详情末尾 | 原表完整保留 |
| A/B/C/D：Round 1/2/3 切换、继续优化下一轮 | 方案对比，轮次切换行及方案区操作 | 原轮次状态与按钮保留；回归与推荐也可切轮次 |
| A/B/C/D：每轮 A/B/C 方案卡 | 方案对比，上半部 | 思路、改动参数、针对的题、预期效果、风险、结果六字段及对齐保留 |
| A/B/C/D：方案目标、完整报告、跳过、Sandbox 运行 / 继续 | 方案对比，各方案卡底部 | 原入口、禁用条件和确认框保留 |
| Sandbox：Baseline + 本轮 A/B/C + D 对比表 | 方案对比，方案卡下方 | 原 CompareTable；Winner/D 高亮和数据口径保留 |
| Sandbox：更多指标、修复口径提示、D 等待 / 跳过状态 | 方案对比，Sandbox 对比表内及下方 | 原展开按钮、分母提示和状态保留 |
| Sandbox：高级指标抽屉（Token、费用、检索等） | 方案对比，Sandbox 区“查看高级指标” | 原抽屉完整保留 |
| Regression Check：每方案一行的修好、新增严重 / 普通、上限、Regression、最终资格 | 回归与推荐，上方表格 | 原表默认展开，首屏能看到保存判定 |
| Regression Check：Winner 与 D 的独立质量表 | 进化路线 D 区的 Winner vs D；回归与推荐下方合格方案对比 | 原答对数、P99、安全拒答、Hard Gate 均有位置；删除重复的独立比较块 |
| Regression Check：逐题追踪、新增失败 / 原问题修复、严重程度筛选、前后对比、双方证据 | 回归与推荐，上方表格后的折叠详情 | 原 CandidateCaseComparison、前后对比及证据抽屉保留 |
| 最终推荐：推荐结果、推荐理由、Baseline 起点、Winner vs D、比 Winner 多修好的题、去发布 / 查看发布记录 | 回归与推荐，下半部 | 原 FinalRecommendation 保留；跳转只导航，不执行发布 |
| 最终推荐：其他 Candidate 落选原因表、Winner 方案详情、人工确认记录 | 回归与推荐，最终推荐下方 | 原表、点击 / 键盘详情入口保留 |
| 最终推荐：未完成或未知状态、保存原因、生成组合建议、人工选择 Winner 与确认报告 | 回归与推荐，相应条件下的原操作区 | 条件判断和确认框保留，不改保存状态 |
| 全页：轮次 / Candidate / 预算 / 当前状态、历史实验、可调参数、暂停与错误状态、主按钮 | 三个页签共用页头和状态区 | 页头仍是 3 轮、10 Candidate、10/12 预算及保存的已发布状态 |

来源：`frontend/src/pages/EvolutionPage.tsx`、`frontend/src/components/EvolutionStory.tsx`、`frontend/src/ui/evolution/EvolutionTimeline.tsx`、`FinalRecommendation.tsx`、`frontend/src/components/CandidateCaseComparison.tsx`。D 比较表使用保存的安全拒答等指标，最终推荐另外保留 Hard Gate、P50 等原比较项；没有把这些不同指标一起删掉。

## 链接与样式

| 旧参数 | 新页签参数 | 新页签 |
|---|---|---|
| `tab=candidates`、`tab=sandbox` | `tab=comparison` | 方案对比 |
| `tab=regression`、`tab=recommendation` | `tab=review` | 回归与推荐 |
| `tab=route` | 保持 | 进化路线 |

同时兼容旧 `stage=` 参数和 sessionStorage 中保存的旧选择，恢复后规范化到新地址。旧诊断链接继续转到 Baseline 的 Bad Case 诊断。页头“查看 Sandbox 进度”、D 的“查看最终推荐”、发布页的推荐链接和内部步骤跳转都指向新页签；概览原来的 `tab=route` 继续有效。

未新增视觉 CSS，沿用现有 PageShell、方案卡、CompareTable、DStory、FinalRecommendation 及工具类。1440×900 首屏：进化路线可看到 Baseline 和首轮结论；方案对比可看到三套方案状态（Round 3 · C 合格）；回归与推荐可看到 A/B 未通过、C/D 通过的表格。

来源：`EvolutionPage.tsx`、`VersionsPage.tsx`；`task023-tabs.test.tsx`、本机 `browser-acceptance.json` 和对应截图。

## 本轮经验与保存事实

当前保存实验为 `EXP-20261105143048349606`，Winner 为 `EXP-20261105143048349606-R3-C`。重新只读核对了每套的参数、修复题号、新增题号、Hard Gate 实际值及 Winner 身份。

| 轮次 | 页面完整句（含前缀） | 字符数 | 核对依据 |
|---|---|---:|---|
| Round 1 | 本轮经验：扩候选+多路查询修好 3 题，但 P99 超标；降档+Top-K 6 修好 Q04、Q06，却拉低了安全拒答。 | 60 | A 为 Candidate K 24 + Multi-Query 2，修好 Q24/Q29/Q38，P99 86.548 秒未过 60 秒；C 为 Thinking High + Top-K 6，修好 Q04/Q06，安全拒答 90% 未过 95% |
| Round 2 | 本轮经验：三套方案都弄坏了 Q17；单独把 Top-K 提到 6 能修好 Q04、Q06，但会拉低安全拒答。 | 54 | 三套新增题均含 Q17；B 仅改 Top-K 6，修好 Q04/Q06/Q38，安全拒答 90% |
| Round 3 | 本轮经验：降低思考档、同时把候选扩到 24，首次做到零新增 Bad Case，成为 Winner。 | 49 | C 为 Thinking High + Candidate K 24，新增为 0、Hard Gate 全过且是保存 Winner；前六套及本轮 A/B 均有新增 |

**我是这样理解的**：Round 1 任务示例原有 64 字，而硬上限是含前缀 ≤60 字。因此仅去掉两个加号两侧共四个空格，句意、参数和题号不变。经验本身的适用条件、缺数据不显示和 HoverCard 依据文本均保留；浏览器核对三条均完整显示、不截断，鼠标悬停有三套依据。

来源：本机 `optimization.json`，字段 `reasoning.changed_parameters / candidate_label / round`、`result.all_fixed_question_ids / new_regression_question_ids / gates`、保存的报告确认 Winner；`frontend/src/ui/evolution/model.ts`、`task022f-lessons.test.tsx`。

## 测试与验收

### 前端与构建

- `frontend/` 下 `npx vitest run`：**99 文件、589 条通过，0 失败、0 跳过**。最终日志 `output/task023/frontend-verified.txt`。
- `npm run build`：通过。日志 `output/task023/build.txt`。
- 最初新增页签兼容和完整句断言在旧实现先失败，见 `red.txt`；新增五个页签用例最终全部通过，包含四类旧链接、旧 sessionStorage、`stage=`、轮次、更多指标、方案抽屉、回归表与不修改输入数据。
- 迁移后发现未保存逐题评测编号的候选可令回归追踪读取空 `runs`。原因是 `runs?.runId` 与缺失 `runId` 同为 undefined 时比较成立。只增加 `runs` 存在检查；旧链接测试与合并页测试覆盖该未完成数据状态，不补造逐题结果。
- 前端第二轮全量曾有 1 条既有 `task022g-confirmation` 检查失败：并行测试时异步详情预取 GET 恰好落在“确认前不得有请求”的断言中。该测试原样保留，单独复核 18 条通过，后续完整全量 589 条全部通过。没有通过删除断言或跳过测试掩盖它。
- 单元测试日志仍有既有 React act / 服务端 useLayoutEffect 警告，不把它说成日志零警告；真实浏览器的脚本错误和控制台错误均为 0。

来源：本机 `frontend-all.txt`、`frontend-final.txt`、`confirmation-recheck.txt`、`frontend-verified.txt`、`build.txt`；`frontend/src/components/CandidateCaseComparison.tsx`。

### 改了哪些旧测试，原来验证什么，怎样继续验证

| 测试组 | 原来验证什么 | 这次怎样保留 |
|---|---|---|
| agent-restoration、evaluation-governance、task021u、task018a、fixed-workspaces | 页签、状态、轮次记忆、详情、确认与取消 | 页签数量改 3，入口改新名称，原状态/权限/确认断言保留；旧 sandbox 链接现在验证迁移后恢复 |
| candidate-presentation、interview-evaluation、task013c、task016a、v14-ui-contract | A/B/C 字段顺序、D 资格/排队/无组合、费用与报告 | A/B/C 仍在方案对比逐字段检查；D 相关检查改在进化路线；费用、高级指标、原文、资格和中断断言保留 |
| task021b、task021q、workbench-expression | 历史轮次、冻结严重程度、Regression、未完成时不误推荐 | 两个合并详情页仍验证切轮次；回归表断言原样；最终推荐断言改查合并页下方推荐区 |
| task022f-lessons | 参数/结果/Winner 依据、来源 HoverCard、缺项不编造、40 字上限 | 改为完整句和 60 字上限；原事实条件、缺项和键盘 HoverCard 断言保留 |
| bad-case-unification、closure-authorization、diagnostic-workspaces、storytelling-v2、task015a、task021e/i/o/v/w、task022c、v12-flow | 原目标、身份、授权、报告、表格、布局与发布导航 | 只同步入口或迁移位置，原功能断言保留 |

来源：`49a5b37` 中的前端测试差异和最终全量测试日志。新增用例为 `frontend/src/task023-tabs.test.tsx`。

### 后端

后端全量覆盖完成：**运行计数 1459，0 失败、0 错误，21 项既有跳过不变**。上轮已完成 998 项测试运行（另有 1 个类级跳过），本次补齐 461 项，没有重复运行已有明确结果的项。21 个跳过条目包含 1 个类级跳过，不用简单相减冒充实际成功数。

跳过名称和原因逐项与 022g 一致：

| 模块 | 跳过条目数 | 原因 |
|---|---:|---|
| test_behavior_parser | 2 | 私有真实 Judge 回包未分发 |
| test_claim_consistency | 2 | 私有真实 Judge 回包未分发 |
| test_evaluation_policy | 3 | 私有保存材料未分发 |
| test_intervention_contract | 1（类级） | 私有只读审计 CSV 未分发 |
| test_judge_equivalent_output_contract | 3 | 私有原始回包缺失 |
| test_judge_forbidden_nonclaim_contract | 5 | 私有原始回包缺失 |
| test_judge_omission_protocol | 5 | 历史 Judge 源码或私有原始回包缺失 |

最终汇总 `backend-full.json`、续跑日志 `backend-resumed.txt` 和校验记录 `final-verified.json` 保存在本机。原中断日志 `backend-full.txt` 未覆盖。

测试使用独立临时目录和临时数据库，在任何 app 导入前设置 `RAG_DEMO_DB_PATH` 等路径，启用 Mock 并阻止外网连接；没有复制正式数据库。首轮已完成项与剩余项取自真实 unittest 日志和当前测试发现列表。

来源：本机 `run_backend.py`、`resume_backend.py`、`backend-full.txt`、`backend-completed-before-interruption.json`、`backend-resume-plan.json`。

### 浏览器与截图

浏览器验收使用真实本机 demo 的只读保存数据，1440×900 与 1280×800 两种尺寸；主导航八页均能打开。检查三个新页签、四种旧链接、三个轮次、更多指标、高级指标抽屉、方案详情抽屉、三条完整经验及 HoverCard。记录到的脚本错误 0、控制台错误 0、写请求 0；无全局横向滚动。

| 本机截图 | 内容 |
|---|---|
| `output/task023/1440-route.png`、`1280-route.png` | 进化路线首屏 |
| `output/task023/1440-comparison.png`、`1280-comparison.png` | 方案对比首屏 |
| `output/task023/1440-review.png`、`1280-review.png` | 回归与推荐首屏 |
| `output/task023/1440-round-1-lesson.png` 至 `1440-round-3-lesson.png` | 三轮经验，1440×900 |
| `output/task023/1280-round-1-lesson.png` 至 `1280-round-3-lesson.png` | 三轮经验，1280×800 |
| `output/task023/agent-round3-d.png` | Round 3 与 Candidate D |

这些截图只留本机。前次临时 README 素材另放 `output/task023/deferred-readme/`，不是本任务对 024c 终版截图的验收。来源：本机 `acceptance.py`、`browser-acceptance.json`、`screenshots.json`。

## 保存数据未变

对本轮实际读到的 `/api/evaluation`、`/api/optimization`、`/api/versions`、`/api/monitoring`、`/api/documents`、`/api/workspace` 六组响应做前后 SHA-256 比较，**全部一致**。这说明所核对的保存响应未变，不声称整个数据库文件字节未变。Golden 候选池未改；无后端产品代码修改。

来源：本机 `output/task023/state-before.json` 与 `state-verified.json`。初次与续跑的浏览器都只允许 GET。

## 待回答问题

无需等待人工回复。README 界面预览按新版任务单交给 024c，保留素材供其参考。后端 21 项既有跳过已核对一致；缺少的私有材料仍无法验证，未用模拟材料冒充通过。

## 收尾

前端全量、构建、浏览器及后端测试进程均已退出；本轮临时测试目录已清理。现有前后端 demo 返回 HTTP 200，保留运行。后端结果、21 项跳过名单、保存数据、报告与任务范围已核对，以普通 `mv` 将任务单归档至 `指挥/历史任务/023-Agent页签合并本轮经验与README截图.md`。全程未运行任何 git 写命令，保存与推送由值班脚本负责；后续脚本的推送结果未知。No SPEC Change。
