# 024a2：Agent 三页签信息去重与精简

## 完成结论

三页签展示调整和验收均已完成。前端全量 101 个文件、596 条通过，构建通过；后端运行 1459 项，0 失败、0 错误，21 项既有跳过逐项不变。1440×900 浏览器验收通过，预热后首次进入 Agent 181.5ms；保存数据未变，真实模型调用 0 次。

## 开工检查和理解

- 已先读根目录 `AGENTS.md`、`指挥/README.md`，再读本任务单。开工 `git status --short` 为空，最近记录只有开始本单，没有 024a2 的部分实现或旧报告；023、024a 已完成，不重复其工作。
- **我是这样理解的**：以任务单列出的展示改法为本单边界。删除卡片、回归表中的指定重复字段，保留原表格、详情抽屉、逐题追踪及运行确认流程。原 Agent 思路、风险、经验、Judge 和审计原文不改；“弄坏”改“新增 Bad Case”针对结果字段标签，不重写保存原文。
- **我是这样理解的**：摘要列出当前实验所有已完成且保存为合格的方案，数量和 Winner、推荐身份由已有模型及保存推荐计算，不随轮次选择隐藏其他轮的合格方案。回归表仍按原轮次选择展示。
- 任务单明确要求 demo 保持运行，保留开工已有前端 5174、后端 8010，不重启。没有启动新的服务。
- 024a 已做好空闲时隐藏“查看 Sandbox 进度”、落选方案真实数量。本次保留并复验；落选行另补接现有折叠箭头样式。

来源：上述规则与任务单；只读 `git status / git log`；`frontend/src/pages/EvolutionPage.tsx`；023、024a 报告。

## 每处改动

| 位置 | 改前 | 改后 |
|---|---|---|
| 进化路线每轮标题 | Round 后带一行未合格、门槛失败的计数，下面又有本轮经验 | 标题只留 Round；保留原经验句及悬停证据，删除重复计数行，Round 3 同样处理 |
| 本轮经验与卡片 | 经验句贴近下方卡片 | 明确留 12px，浏览器逐轮核对 |
| 方案对比卡片顶部 | 左上角再显示 Round；失败徽章写“已评测未通过” | 删除重复轮次小字；已完成且已知资格使用“未通过 / 合格”，运行中、中断、资格未知等原状态保留 |
| 卡片结果 | 多项门槛、耗时、资格指标，加完整回归长句，再列修好、弄坏 | 收为答对 X / 总题数、修好全部题号、新增 Bad Case 题号三行；空数组显示“无”，缺少保存数据不算作无 |
| 卡片修好口径 | “修复原问题”数与全部修好题号口径不同 | 只显示保存的全部修复题号；指定目标题数移入“查看目标”抽屉，说明与全部修复集合重叠、不能相加 |
| 针对的题 | 题号和原题串在一起，长题截断 | 使用现有题号徽章；悬停或键盘聚焦显示原题 |
| 字段排版 | 标签与正文层次不够清楚 | 六个字段标签 12px、浅灰、常规字重，正文 13px |
| 卡片底部 | 有不可点击的“已评测”按钮 | 已评测卡删除该按钮，保留查看目标及方案完整报告；未评测运行、继续、跳过的原条件、回调和确认框不变 |
| 回归卡层级 | 外层卡又套“方案 Regression Check”卡 | 删除内层卡和重复标题，保留外层“Regression Check · 改善与副作用”及逐题追踪入口 |
| 回归表方案列 | 每行带“Round 3 ·”等轮次 | 只写 Candidate A/B/C/D，轮次选择不变 |
| 回归表列与说明 | 每行重复相同上限；表头“Regression 判定”可能折行 | 删除上限列，表头改“判定”且保持一行；表下用 12px 浅灰说明“新增严重上限 0，普通上限 1；修好的题不能抵消新增 Bad Case” |
| 合格方案对比表 | 单独一行“Baseline 答对”，跨列造成 D 列空白 | 删除该行；各方案答对单元格后用浅灰小字显示动态“较 Baseline +X” |
| 落选方案折叠行 | 024a 已有真实数量，未接统一箭头样式 | 保留真实数量，接现有 `story-disclosure` 箭头，展开后保留全部落选方案和详情入口 |
| 回归与推荐首屏 | 先看逐行回归，没有合格方案总览 | 表上增加现有数据生成的一行 13px 摘要，推荐方案可点并滚动到最终推荐 |
| 公共页头 | 024a 已仅在运行中显示进度 | 保留并复验，无重复实现 |
| 首次进入预热 | 022f 已预热 Agent 模块及 evaluation、badCases、optimization（含 planning）、versions；合并页签复用这些数据 | 未增加重复请求。补测试：预热后把后续接口挂起，Agent 及三个页签仍立即有内容；另做真实 demo 耗时检查 |

来源：`frontend/src/pages/EvolutionPage.tsx`、`frontend/src/pages/evaluation-workspaces.css`、`frontend/src/ui/evolution/EvolutionTimeline.tsx`、`frontend/src/ui/evolution/FinalRecommendation.tsx`；预热路径见 `frontend/src/App.tsx`、`frontend/src/api.ts`、`frontend/src/pageWarmup.ts`。

## 验证记录

- 新增 `frontend/src/task024a2-dedup.test.tsx`，旧实现先得到 3 条预期失败，再验证精简后的结果、全部修好与指定目标的不同口径、摘要真实计数随数据变化、点击推荐滚动和数据入口。
- 同步原有 013c、021q、022c、023、024a、interview-evaluation 展示断言；原状态、风险、轮次、资格、原题悬停、抽屉、只读请求及逐题严重级别验证保留，没有删除测试或新增跳过。
- 扩充 `task022f-warmup.test.tsx`，验证完整 Agent 输入已预热，接口重读挂起时三个页签仍可用。补齐旧模拟接口的 Bad Case 列表类型。
- 最终前端全量 `npx vitest run`：101 个测试文件、596 条通过，0 失败。日志为本机 `output/task024a2/frontend-final.txt`。
- TypeScript / Vite 构建结果记录在本机 `output/task024a2/build-final.txt`。
- 测试期间既有 React act、服务端 useLayoutEffect 警告仍可能出现；通过结论取测试最终汇总，不宣称零警告。

## 浏览器与本机截图

真实 demo、1440×900 验收通过，22 条检查记录；无全局横向滚动，浏览器脚本错误 0、控制台错误 0、写请求 0。检查了三个页签、Round 1/2/3 切换、原题与经验悬停、目标抽屉、方案报告、高级指标、更多指标、推荐滚动、落选方案展开和详情，并打开全部八个主导航页面。

- 概览空闲预热完成后，首次进入 Agent 实测 **181.5ms**，方案对比页签切换 60.6ms、回归与推荐 90.3ms。这是本机本次预热后的测量，不承诺未预热的直达冷启动也在 1 秒内。
- 三轮经验句与卡片间距均为 12px；字段标签实际计算为 12px、`rgb(110,110,115)`、字重 400，正文 13px。
- 实际保存数据显示合格 2 个：Round 3 · Candidate C（Winner）、Candidate D（推荐）。卡片 C 列出全部修好 Q24/Q29/Q38；目标抽屉显示指定目标修好 2 / 3，两种口径分别展示。
- 合格方案答对显示 47 / 50、较 Baseline +3；48 / 50、较 Baseline +4。落选方案数量为 8，可展开及打开详情，箭头可见。
- 推荐摘要点击后，下方最终推荐进入可见区；保留固定页头和原内容滚动容器。

截图只存本机 `output/task024a2/`，没有放进报告目录：

| 文件 | 内容 |
|---|---|
| `1440-route.png` | 进化路线首屏 |
| `1440-comparison.png` | 方案对比首屏 |
| `1440-review.png` | 回归与推荐首屏 |
| `1440-comparison-cards-viewport.png` | 1440×900 滚动到三张卡片 |
| `1440-comparison-cards.png` | 同一视口下三张卡片的完整元素截图 |
| `1440-final-recommendation.png` | 摘要点击后的最终推荐、合格方案对比及落选折叠行 |

来源：本机 `output/task024a2/acceptance.py`、`browser-acceptance.txt`、`browser-acceptance.json` 及六张截图；已实际查看三页签和卡片截图。验收脚本调整过对固定页头、页面底部最大滚动距离的判断，不把“未贴浏览器顶端”当作滚动失败。

## 保存数据与模型调用

对 workspace、evaluation、optimization、versions、monitoring、documents、dataset 七组 GET 响应做规范化 SHA-256 前后比较，全部一致。这证明本次核对的保存响应未变化，不声称整个数据库文件字节未变。

**真实模型调用 0 次，DeepSeek 调用 0 次。** 浏览器只允许 GET，未发起付费评测、问答、发布或回滚。后端测试在导入 app 之前设置临时数据库和文件目录，启用 Mock 并阻止外网连接；没有复制正式数据库。没有修改后端产品代码、Golden、评测门槛、Judge 或 Agent 原文。

来源：`output/task024a2/state-before.json`、`state-verified.json`、`browser-acceptance.json`、`run_backend.py`；只读 `git diff`。

## 后端全量与既有跳过

本机 `run_backend.py` 用自动清理的临时目录、独立临时数据库运行 `unittest`，599.584 秒完成 1459 项，0 失败、0 错误，21 项跳过。将跳过名称与原因同 024a 的 `backend-full.json` 逐项排序比较，完全一致，未增加或删除跳过。

| 模块 | 跳过条目数 | 原因 |
|---|---:|---|
| test_behavior_parser | 2 | 私有真实 Judge 回包未分发 |
| test_claim_consistency | 2 | 私有真实 Judge 回包未分发 |
| test_evaluation_policy | 3 | 私有保存材料未分发 |
| test_intervention_contract | 1（类级） | 私有只读审计 CSV 未分发 |
| test_judge_equivalent_output_contract | 3 | 私有原始回包缺失 |
| test_judge_forbidden_nonclaim_contract | 5 | 私有原始回包缺失 |
| test_judge_omission_protocol | 5 | 历史源码或私有原始回包缺失 |

来源：`output/task024a2/backend-full.txt`、`backend-full.json`、`run_backend.py`；`output/task024a/backend-full.json` 仅用于核对跳过名单。测试中的 Mock 只证明相应用例行为，不冒充真实 Provider 或正式实验结果。

## 待回答问题

没有本次未完成项，不需要等待人工确认。21 项既有跳过缺少私有材料，其历史证据验证仍为未知；本单没有编造材料或改成假通过。

## 收尾

本轮测试、构建和测试浏览器已退出，临时测试目录已自动清理。开工已有 demo 仍使用原 PID 1117 / 19536；前端首页和后端 `/api/workspace` 均返回 HTTP 200。`指挥/当前任务.md`、后端产品代码、SPEC 无修改，差异空白检查通过。本机截图、原始数据与日志仅在被忽略的 `output/task024a2/` 中，不提交公开仓库。

验收和报告均已完成，使用普通 `mv` 将本任务单归档到 `指挥/历史任务/024a2-Agent三页签信息去重与精简.md`。

No SPEC Change。未运行 Git 写命令，保存与推送由自动值班脚本负责，脚本后续推送结果未知。
