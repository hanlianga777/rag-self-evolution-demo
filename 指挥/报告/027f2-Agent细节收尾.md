# 027f2：Agent 工作台细节收尾

本单已完成。前端全量 112 个文件、668 条测试通过；后端全量 1459 项，0 失败、0 错误、21 项既有跳过保持不变；生产构建、指定截图及浏览器验收通过。真实模型调用 0 次，没有运行 Git 写命令，保存推送交给值班脚本。No SPEC Change。

## 我是这样理解的

- 已依次阅读根目录 `AGENTS.md`、`指挥/README.md`、本任务单及 027a 开头的本轮总背景。开始时工作区干净，最新提交为 `0508485`；检查了 027f、027g 的报告、提交记录及现有实现，没有发现 027f2 的半成品，直接在它们的成果上收尾。没有重跑任何保存评测题。
- 只改本任务要求的前端展示、相关测试和本报告；不改后端产品代码、评测数据、Golden、门槛、Judge 或 Agent 保存原文，不发布、不回滚、不发送问答。
- 任务要求无人值守，按已授权的文案方向直接执行，不增加确认步骤。027a 要求 demo 保持运行，因此保留原有 8010 后端和 5174 前端，只关闭本单启动的测试浏览器与测试进程。
- “题号、数值都从保存数据生成”：风险摘要按 D 的 `changes[].source_candidates` 找对应已完成 Candidate，读取新增题号及保存的 Gate 数值；实际保护题沿用原来的评测身份核对。没有足够来源时保留保存的风险文字，保护题核对不足仍显示未知。
- “采纳依据压缩”：只对本机保存的这一种明确句式作展示压缩。提取保存的题号、Top-K 上限及历史值；其他句式保留原意。未将这段采纳前的判断改写成 D 当前逐题根因，Agent 原文仍能在完整报告中查看。

## 修改与来源

| 项目 | 结果 | 来源 |
| --- | --- | --- |
| D 的外层与空隙 | 去掉外层通用 `panel` 类，消除继承来的 20px 内边距、22px 外边距；轮次按钮外边距归零，保留网格 16px 间距。D 卡片直接排在页面上，与 Round 卡片左右对齐 | `frontend/src/pages/EvolutionPage.tsx`、`frontend/src/ui/extra.css`；本机 `output/task027f2/browser.json` |
| Top-K 副作用检查 | 完整句子、顿号题号、百分号与一位小数秒数；明确同时出现不能证明因果。完整报告抽屉仍保留历史风险及其他风险原文 | `frontend/src/components/EvolutionStory.tsx:DSideEffects`；实验 `EXP-20261105143048349606` 的 D `reasoning.changes`、R1-C/R2-B 保存结果 |
| 推荐说明 | 保留大字标题，下方只显示取舍与采纳依据两句，不再重复原推荐句，没有斜杠写法 | `EvolutionStory.tsx:recommendationTradeoff`；D `winner_comparison`、D/Winner P99 Gate、`changes[].reason` |
| 落选原因 | 使用接口根据保存结果生成的只读 `regression_review` 新增严重/普通数量及 `limits`，写明超出哪条上限；同时没过 Hard Gate 的追加该项数值和门槛。没有明细时不猜上限 | `frontend/src/ui/evolution/model.ts`、`FinalRecommendation.tsx:rejectionReason`；`backend/app/governance.py:_regression_review` 的只读投影与各 Candidate 保存的 `gates` |
| Candidate 对比 | 删除轮次按钮下方的小标题；保留原卡片、继续下一轮按钮及所有原有回调 | `frontend/src/pages/EvolutionPage.tsx` |

来源接口为本机只读 `GET /api/optimization?light=true&planning=true`，开始时响应留在 `output/task027f2/data-before.json`。截图及接口响应只保存在本机。

## 采纳依据原文与压缩对照

保存原文（D 的 `reasoning.changes[0].reason`，未修改）：

> 剩余Q04、Q06属于已进入候选/重排但被Top4截断的context_selection问题；历史保存结果中top_k=6伴随修好Q04和Q06，且该值在search_space允许范围内，不撤销Winner的candidate_k=24与generation_thinking=high。

页面两句（从实际浏览器读取）：

> Candidate D 在 R3-C 的基础上多修好了 Q04，新增 Bad Case 仍为 0；它的 P99 是 36.7 秒，比 R3-C 慢一些，但仍在 60 秒门槛以内，按质量优先的规则推荐 D。 采纳依据：Q04、Q06 的关键证据已经进入候选，却被“只取 4 条”的上限截掉；前几轮的结果显示 Top-K 6 能修好这两题，所以 D 只在 Winner 上加了这一项。

压缩对应关系：

| 原文信息 | 压缩表达 |
| --- | --- |
| 剩余 Q04、Q06 已进入候选/重排、被 Top4 截断 | Q04、Q06 的关键证据已经进入候选，却被“只取 4 条”的上限截掉 |
| 历史保存结果中 top_k=6 伴随修好 Q04 和 Q06 | 前几轮的结果显示 Top-K 6 能修好这两题 |
| 该值在 search_space 允许范围内，不撤销 Winner 的 candidate_k=24 与 generation_thinking=high；D 只有一项新增 change | 所以 D 只在 Winner 上加了这一项 |

前一句中的“多修好 Q04、零新增”来自 D 相对 Winner 的保存结果，36.7 秒与 60 秒来自保存 P99 实际值及门槛，R3-C 的 P99 为 22.6 秒。没有把“能修好这两题”写成 D 已经修好 Q06，D 页仍明确显示 Q06 实际未修好。

## 副作用与落选原因的实际展示

Top-K · 副作用检查

前几轮里，Top-K 6 出现时伴随过副作用：R1-C 新增了 Q15、Q17、Q43，安全拒答降到 90%；R2-B 新增了 Q17、Q37、Q46，安全拒答 90%、P99 64.8 秒。这些只是同时出现，不能证明是 Top-K 造成的，所以 D 把这些题列为重点盯防。

实际结果：8 道受保护题全部守住，安全拒答 100%。

落选原因从实际浏览器读取：

- R1-A回答耗时 P99 86.5 秒（上限 60 秒），未通过 Hard Gate。
- R1-B新增 7 个 Bad Case，超过普通新增最多 1 个的上限。 安全拒答率 90%（下限 95%）；回答耗时 P99 65.6 秒（上限 60 秒），未通过 Hard Gate。
- R1-C新增 3 个 Bad Case，超过普通新增最多 1 个的上限。 安全拒答率 90%（下限 95%），未通过 Hard Gate。
- R2-A新增 3 个 Bad Case，超过普通新增最多 1 个的上限。
- R2-B新增 3 个 Bad Case，超过普通新增最多 1 个的上限。 安全拒答率 90%（下限 95%）；回答耗时 P99 64.8 秒（上限 60 秒），未通过 Hard Gate。
- R2-C新增 3 个 Bad Case，超过普通新增最多 1 个的上限。
- R3-A新增 3 个 Bad Case，超过普通新增最多 1 个的上限。 安全拒答率 90%（下限 95%）；回答耗时 P99 75.6 秒（上限 60 秒），未通过 Hard Gate。
- R3-B新增 2 个 Bad Case，超过普通新增最多 1 个的上限。

以上均为保存结果的展示，没有重新计算或覆盖最终资格。`regression_review` 是后端现有 `_regression_review` 生成的只读视图，普通 1 个、严重 0 个的上限由现有接口提供，不声称它是旧资格原文；本单未修改这段后端逻辑。R1-A 的普通新增只有 1 个，没有超出普通上限，所以其落选说明只列 P99 86.5 秒超过 60 秒；R2-A / R2-C / R3-B 列普通新增超限；同时超限且 Hard Gate 不通过的方案两条都写。

## 验证结果

- 新增 3 条 027f2 行为测试，先确认旧实现 3 条预期失败、原有 4 条通过，再实现。覆盖外层卡片与重复标题、普通/严重新增上限及 Hard Gate 双原因、两句推荐与保存来源风险摘要、数据对象不变。来源：`frontend/src/task027f-candidates.test.tsx`、本机 `output/task027f2/red.txt`。
- 第一次前端全量为 667 通过、1 失败。失败说明：旧测试的来源 Candidate 没有新增 Bad Case，新摘要错误替代了已有风险原文。已收紧生成条件，没有新增题的来源不拼接风险摘要，继续展示原文；同时只有保存的安全 Gate 明确未通过时才使用“降到”。没有通过删除旧断言绕过问题。相关测试最终 20 条通过。来源：`frontend-full.txt`、`related-final.txt`、`task021b-story.test.tsx`。
- 最终前端全量：`npm --prefix frontend test -- --maxWorkers=2 --minWorkers=2`，112 个文件、668 条通过，0 失败，64.90 秒。原有 React act 测试环境警告仍有，实际浏览器控制台错误为 0。来源：`frontend-delivery.txt`、`browser.json`。
- 最终生产构建：`npm --prefix frontend run build`，TypeScript、Vite 均通过，退出码 0。来源：`build-delivery.txt`。
- 后端全量：`python3 output/task027f2/run_backend.py`，1459 项，0 失败、0 错误、21 项跳过，579.009 秒。跳过测试的名称和原因与上一单 `output/task027g/backend-full.json` 逐项完全一致，结束自动删除临时目录。来源：`backend-full.txt`、`backend-full.json`、`final-verification.json`。
- 最终浏览器专项验收：16 组检查通过，`errors / consoleErrors / httpErrors / blockedRequests` 均为空；禁止外部请求及非 GET/HEAD/OPTIONS 请求，实际被拦截写请求为 0。结束已关闭临时浏览器。来源：`browser_acceptance.py`、`browser-delivery.txt`、`browser.json`。
- 复用 `scripts/check_viewport_fit.py --output output/task027f2/fit-check.json`，18 个页面/页签无脚本错误、无全局横向滚动、无被拦截写请求，每屏至多一个实心蓝按钮。内容较多的页面保持原有整页滚动。来源：`fit-check.json`、`fit-check.txt`。
- 六组响应 `/api/evaluation`、`/api/optimization?light=true&planning=true`、`/api/versions`、`/api/monitoring`、`/api/documents`、`/api/workspace` 的按键排序 JSON SHA-256 前后一致。这说明本次核对的保存响应未变，不声称整个数据库文件字节未变。来源：`data-before.json`、`data-after.json`、`data-unchanged.json`。
- 真实 DeepSeek / Provider / 回答生成 / Judge / Agent / Sandbox 调用次数均为 **0**。单元测试使用 Mock；后端在导入前设置临时数据库、空环境文件、临时索引/文档/上传/诊断路径，并用 Python audit hook 拒绝外网连接，不复制正式数据库。浏览器只查看已有记录。来源：`run_backend.py`、`browser_acceptance.py`。
- `git diff --check` 已通过；没有运行 Git 写命令。

## 截图与页面验收

截图均为 1440×900，保存在本机 `output/task027f2/`，已打开检查：

| 文件 | 核对结果 |
| --- | --- |
| `01-candidate-d.png` | 上半页：按钮到 D 的设计为 16px；D 与 Round 卡片左右对齐，外层无白底内边距；原预测与两张对比表仍可见 |
| `02-d-unresolved.png` | 下半页：Q06/Q27、排名图、自然风险摘要及“8 道受保护题全部守住，安全拒答 100%”完整可见；两个查看按钮正常 |
| `05-review-first-screen.png` | 推荐大字标题、两句说明和十行总表均完整放入首屏 |
| `06-review-tradeoff-and-rejections.png` | 合格方案对比和全部 8 条落选原因可读；超限与 Hard Gate 原因同时保留 |

浏览器还检查了 D 完整报告、参数差异无内部滚动、逐题追踪及前后回答对比、推荐入口、发布记录入口、Candidate 轮次切换、目标问题抽屉、Candidate 报告、Sandbox 展开表格和高级指标。并打开项目概览、知识库、Pipeline、Golden、Baseline 主链路页面。只查看，不提交发布、回滚或付费操作。

## 待回答问题

无阻塞项。缺少来源或评测身份不一致时的具体结果仍按原逻辑显示未知，不编造安全结论。

## 完成与归档

全部产出及验收完成，任务单用普通 `mv` 移至 `指挥/历史任务/027f2-Agent细节收尾.md`。原有后端 PID 816、前端 PID 827 继续运行，本单启动的测试进程及临时浏览器均已结束。本单没有使用任何 Git 写命令；保存与推送交给值班脚本。截图、接口响应、测试日志和辅助脚本只留本机，不作为公开提交内容。
