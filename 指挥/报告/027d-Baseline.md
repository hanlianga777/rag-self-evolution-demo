# 027d：Baseline 三个页签与加载状态

本单改造与验收完成。前端 108 个文件、642 条测试通过；后端全量 1459 项，0 失败、0 错误，21 项既有跳过的名称和原因不变；生产构建通过。真实模型和 DeepSeek 调用均为 0。没有运行 Git 写命令；保存和推送交给值班脚本。No SPEC Change。

## 我是这样理解的

- 开始先读根目录 `AGENTS.md`、`指挥/README.md`、本任务单及 027a 的总背景。开始时工作区干净，最新提交 `7336ee1` 是 027d 开始记录；027c 已归档，没有发现 027d 半成品或报告。没有重跑任何付费题目。
- 按 027a 的“demo 保持运行”，保留开始时的后端 8010（PID 816）和前端 5174（PID 827）。只关闭本次启动的测试程序和临时浏览器，不关闭原 demo。
- “更多指标”删除当前 Baseline 重复展示的 P50、P99、耗时构成、长卡综合分及冻结模型、Pipeline 参数。TTFT 是上方没有出现的首个 Token 等待时间，保留；原有“查看对照”及其跨运行比较抽屉保留，里面的 P50/P99 是不同保存运行的比较功能。
- 四张分类卡的小字统一解释分类，不再根据本轮数量或优先级切换成结果、修复建议；数量、严重程度、分类筛选和逐题操作保留。
- “读取中”与“读取完成但字段缺失”分开处理。已经成功读取的历史结果仍可显示真实的 0、未采集等状态；新字段未返回时显示灰色骨架。读取失败时显示失败信息或已有缺失提示，不用全局参数猜本题归因。

来源：上述任务单、开始时的 `git status --short` / `git log -8 --oneline`，及下述代码、浏览器记录。

## 每处改动

| 位置 | 改前 | 改后 |
| --- | --- | --- |
| `frontend/src/ui/baseline/BaselineHero.tsx:35` | “回答生成占 … → 降 Thinking 档位是提速主要抓手” | 原样采用任务单要求的完整长句，百分比仍取保存的回答生成阶段占比；放在图例下面，12px 浅灰。本机数据为 95.8%，没有写死该数字 |
| `frontend/src/ui/baseline/BaselineBreakdown.tsx:22`、`ui/extra.css` | 中英文混在同一文本里，标签宽度不足；另有“消融题最弱”结论 | 中文和 12px 灰色英文同一行不换行，标签列固定 144px，三条进度条起点一致；删除结论，增加行距，左右卡按各自内容高度显示 |
| `frontend/src/pages/EvaluationPage.tsx` 报告的 `onOpen` | 设置题目后跳到诊断页签 | 只设置题目，就地使用同一个 `BaselineCaseDetails` 抽屉；关闭后仍在报告页签 |
| `frontend/src/components/ProductDiagnostics.tsx`、`EvaluationPage.tsx:246` | 更多指标里重复耗时表、当前 P50、长卡综合分，模型和参数 | 去掉重复项及冻结信息；保留 Recall@K、Precision@K、MRR、TTFT、每题 Token、每题回答费用；英文指标名下面加 12px 灰色解释，再显示数字。题卷和评测时间继续保留 |
| `EvaluationPage.tsx:201`、`:254`、`ui/extra.css` | “重新运行 Baseline（新版本）” | “重新评测 Baseline”，白底次要按钮，放在更多指标最底部右侧；原有预检、费用确认、恢复请求和新建版本请求保留。更多指标仍用现有折叠组件，显示实际组数和箭头 |
| `EvaluationPage.tsx:40`、`:47`、`ui/baseline/HardGateGrid.tsx`、`ui/extra.css` | Hard Gate 四卡内容紧凑，页面下半部空；只有中文指标名 | 保持 2×2 并拉伸至内容区；行高增大。加指定的灰色英文和按模块写的 12px 定义；状态点、保存值、门槛、鼠标和 Enter/空格打开抽屉继续保留 |
| `EvaluationPage.tsx:264` | 指标抽屉从指标状态开始 | 顶部加浅灰说明长卡，写模块定义、聚合方式和本次保存门槛；保留原保存公式、贡献题目、查看案例等功能；“压线”标签及其悬停提示保留 |
| `ProductDiagnostics.tsx`、`ui/baseline/BadCaseLayers.tsx` | 有问题时显示修复建议，无问题时显示拒答率、延迟等结论 | 四张卡原样采用任务单的检索层、生成层、安全边界、性能解释；保留计数和严重程度 |
| `EvaluationPage.tsx:260`、`ui/extra.css` | “进入 Agent 处理”按钮；长答案受旧的 240px 滚动限制 | 删除该按钮；同一题从报告和诊断页打开的内容一致，抽屉白底；解除答案内部滚动，保留抽屉整体滚动。没有改保存的 Judge 原文 |
| `frontend/src/pages/OverviewPage.tsx`、`ui/overview/OverviewStory.tsx` | 修好题号先到，题目和归因未到时显示“题目未保存”“—” | 问题、归因分别显示骨架；题目返回后只保留归因骨架；成功、失败或确认缺失后才结束对应加载状态 |
| `ui/extra.css` 的概览架构规则 | `.ui-problems`、`.ui-arch`、`.ui-tech` 自带白底大外框和内边距 | 仅在概览架构页去掉这层白底、阴影和内边距；问题卡、架构节点卡直接放在浅灰页底上；业务架构两个区块仍相隔 16px，蓝色 Gate 和 Agent 区保留 |

其他加载状态的具体位置见下一节。没有修改后端代码、门槛、评测数据、Golden、Judge 原文、Agent 原文或 SPEC。

## 全站加载状态检查

| 检查位置 | 处理与核对结果 |
| --- | --- |
| `App.tsx` 页面首次读取、懒加载模块 | 原来已用整页灰色骨架，读取失败有重试；保留 |
| 概览修好题目列表 | 本单改为题目、归因分别加载；保存身份不一致或读取失败时结束等待，不伪造归因 |
| 知识库 Pipeline、主题簇、题位、文档分块/Parent、索引 | Pipeline 未返回时隐藏未知参数；主题与题位使用骨架；文档分块、Parent、索引读取中不用“加载中 / Unavailable”或“未采集”代替；失败显示错误，成功读取后才显示真实缺失状态 |
| Pipeline 配置与参数说明抽屉 | 请求未返回前显示骨架，避免先出现“0 项可调参数”“新 Baseline 待评测” |
| Golden 首次题卷和候选题读取 | 原有骨架保留；`QuestionTable` 加载时不再显示空列表结论；候选题详情与历史选中版本用骨架，失败状态仍有错误信息 |
| 共用 `ScrollablePagedTable` | 读取更多候选题改为灰色骨架条，继续保留已有行和加载控制 |
| Golden 手动选材、修订状态 | 同产品文档和分块未读完前显示骨架，不先报 0 个或“没有匹配的 Chunk”；返回、筛选、勾选等原控件保留；修订状态未到时用骨架条 |
| Baseline 保存案例详情 | 原有案例详情骨架保留；报告点题和诊断点题共用同一条详情链路 |
| Agent 受保护题实际结果 | 原有骨架保留；已有结果、未评测和缺失结果的区别保留 |
| Agent 可调参数、Bad Case 证据 | 读取中显示骨架，不先展示缺证据结论；失败显示错误；未返回时标题不显示“—” |
| Candidate 用量、逐题报告和审计 | 展开后等待完整保存数据时使用骨架；审计不先拿简版 Candidate 充当完整记录；读取错误单独显示 |
| Regression 逐题对照 | 保存对照未返回时用骨架；未完成实验、无评测来源、身份不一致、读取失败继续各自显示真实状态 |
| 问答验证 Before/After | 列表读取改用骨架；单题详情原有骨架及失败重试保留；不在读取中显示空列表结论 |
| 实时问答示例 | 原有读取骨架保留；本单没有发送真实问答 |
| 线上反馈的关联实验 | 主区和上下文抽屉读取中使用骨架，不先说“尚未确认，未创建上下文” |
| 发布、回滚和反馈历史 | 首次数据由 `App` 读取完成后显示；翻页沿用已保存的列表，并保留原有错误处理。没有发布、回滚或新增反馈 |

共用新骨架在 `frontend/src/components/Primitives.tsx:14`，样式复用全站灰色变量。运行中操作的进度、忙碌按钮文字和已保存的检查点属于真实运行状态，不替换成结论。

## 指标中文解释与代码出处

### 更多指标

这些数值继续读取 `product_diagnostics.objective_metrics`，不是 `result.comparison_metrics` 里另一种历史检索口径，没有混用。

| 指标 | 页面解释的真实口径 | 代码出处 |
| --- | --- | --- |
| Recall@K | 标准证据原文在最终前 K 条上下文中的命中段数 ÷ 标准证据段数；只对可评估的正向、消融题逐题平均，再乘 100 | `backend/app/diagnostics.py:151` 的归一化原文匹配、`:169`–`:173` 的公式；`backend/app/product_diagnostics.py:18`–`:21` 的纳入条件及 `:46` |
| Precision@K | 最终上下文中包含任一标准证据原文的条目数 ÷ 最终条目数；相同题目范围逐题平均，再乘 100；最终列表为空时该题为 0 | `diagnostics.py:170`–`:172`，`product_diagnostics.py:47` |
| MRR | 第一条包含标准证据原文的最终上下文排名的倒数；未命中为 0；逐题平均 | `diagnostics.py:170`、`:173`，`product_diagnostics.py:48` |
| TTFT | 已记录 `ttft_ms` 的回答请求取中位数，再从毫秒换算成秒；不是求平均 | `product_diagnostics.py:22`、`:50`；前端 `ProductDiagnostics.tsx` 的除以 1000 |
| 每题 Token | 每道保存回答的 `input_tokens + output_tokens` 均值；包含 Thinking；不含判分、向量、重排；不是每题都有记录时返回空值 | `product_diagnostics.py:23`–`:24`、`:51`–`:52` |
| 每题回答费用 | 全部题都有 USD 回答估算时取均值；不含判分、向量、重排，不是整轮账单 | `product_diagnostics.py:25`–`:26`、`:53`–`:54` |
| 人民币显示 | 继续用 027a 已有 `DISPLAY_USD_TO_CNY = 7.2`，美元估算乘 7.2，显示 `¥ 0.01（估算）` 这类人民币格式 | `frontend/src/components/PipelineFields.tsx:39`–`:42`，`ProductDiagnostics.tsx` 的 `costText` |

没有另造后端未提供的“命中率”数值。检索代码匹配的是标准证据原文经过现有归一化后的包含关系，不把这几个程序化指标说成语义 Judge 判定。

### Hard Gate

| 模块与指标 | 卡内含义与抽屉计算方式 | 代码出处 |
| --- | --- | --- |
| 正向正确性 Correctness | 回答的事实与说明书一致；该类题 Judge 的 0–4 分乘 25 后算术平均 | `backend/app/evaluation.py:103`–`:118`、`:167`；Judge 质量输出合同 `evaluation_contract.py:538`–`:539` |
| 消融正确性 Correctness | 任务单原句“问法改成口语或带干扰后，事实仍然答对”；按消融题分组，计算与正向相同 | 同上。代码按 `test_category=ablation` 纳入，没有另设一套质量分算法 |
| 正向 / 消融忠实性 Faithfulness | 回答技术事实有实际检索证据支持；消融模块强调问法变化后仍保持支持。该类题逐题 0–1 分乘 100 后平均 | `evaluation.py:103`–`:118`、`:167`；`evaluation_contract.py` 的实际 Final 证据与质量合同 |
| 正向 / 消融完整性 Completeness | 回答覆盖必要事实和安全条件；消融模块强调问法变化后仍覆盖。该类题逐题 0–1 分乘 100 后平均 | 同上；`evaluation_contract.py` 中 checks 覆盖必要事实及安全条件的要求 |
| 安全拒答率 Safe Refusal | 全部负向题是否按预期拒答、追问、说明证据不足或抵抗注入。预期行为通过题数 ÷ 纳入题数 × 100%，并非只数说了“不”的题 | `evaluation.py:71`–`:73`、`:121`–`:127`。优先读取 `behavior_contract.effective_pass`，旧记录回退 `judge_result.behavior_pass` |
| 安全关键准确率 Safety-critical Accuracy | 冻结 `negative_subtype=safety_critical` 的负向题预期行为通过比例 | `evaluation.py:125`、`:168`–`:171` |
| 提示注入抵抗 Prompt-injection Resistance | 冻结 `negative_subtype=prompt_injection` 的负向题预期行为通过比例 | `evaluation.py:126`、`:168`–`:171` |
| 回答耗时 P50 / P99 | 全部保存回答耗时排序，以从 0 开始的 `floor((n−1)×p)` 位置取值，p 为 .50 / .99；毫秒换算秒，不含判分 | `evaluation.py:60`–`:64`、`:128`–`:132`、`:174`；`product_diagnostics.py` 的回答阶段口径 |
| 门槛 | 页面始终显示该保存 Run 的 `operator`、`threshold`，没有从现行默认值覆盖历史门槛 | `EvaluationPage.tsx` 的 `gateThreshold` 与 `BaselineGates`；现行门槛定义供核对：`backend/app/policy.py:26`–`:38` |
| 压线 | 百分制差距不超过 1 分，耗时距门槛不超过门槛的 5%；缺少数值不标。沿用 026a | `EvaluationPage.tsx` 的 `tight`；`frontend/src/task026a-story.test.tsx` 的边界检查 |

质量分和逐题 PASS/FAIL 保持独立。页面没有把 Hard Gate 通过说成逐题全对，也没有改任何分母、原始分数或门槛。

## 验证记录

- 新增 `frontend/src/task027d-baseline.test.tsx`，最初 5 条检查均因旧行为失败；扩展配置加载检查时再记录 2 条失败，然后实现。后续补了手动选材等待及原控件检查。覆盖就地抽屉、报告去重、重新评测确认、模块定义与保存门槛、概览分阶段加载和失败、配置读取、Before/After 列表及手动选材。来源：本机 `output/task027d/red.txt`、`loading-red.txt`、`picker-tests.txt`。
- 旧测试只同步任务要求变更的展示断言；保留预检禁用、确认后才请求、恢复/新建请求参数、保存对象不变、筛选、鼠标、键盘、原对照抽屉等功能检查。没有添加跳过或删除整条测试。
- 所有测试日志、截图、检查 JSON、脚本仅保存在本机 `output/task027d/`，不提交。
- 真实浏览器只允许本机 GET/HEAD/OPTIONS；写请求和外网请求会被阻止。截图期间没有点击付费确认、发布、回滚或提交问答。

### 最终全量与保护核对

- 前端全量：`npm --prefix frontend test -- --maxWorkers=2 --minWorkers=2`，108 个文件、642 条测试，0 失败，耗时 57.11 秒。来源：`output/task027d/frontend-delivery.txt`。前端仍有原有 React act/useLayoutEffect 测试警告，没有把这些警告说成浏览器脚本错误。
- 后端全量：`python3 output/task027d/run_backend.py`，1459 项，0 失败、0 错误，21 项既有跳过，耗时 612.986 秒。跳过项名称、原因与 027c 的记录逐项一致。来源：`output/task027d/backend-full.json`、`backend-full.txt` 及 `output/task027c/backend-full.json`。
- 后端 runner 在导入前设置临时 DB、环境文件、索引、文档、上传、诊断目录，强制 Mock；外网连接被本机审计钩子阻止。未复制正式数据库，临时目录由 `TemporaryDirectory` 自动清理。
- 生产构建：`npm --prefix frontend run build`，TypeScript 和 Vite 通过。来源：`output/task027d/build-delivery.txt`。
- 浏览器：报告和诊断打开同一道题的抽屉文本逐字一致；三条题型进度条起点一致；更多指标无被要求删除的重复项，人民币显示、重新评测确认与取消正常；Hard Gate 键盘打开、公式、保存门槛、白底抽屉与无答案内部滚动通过；分类筛选后可回到全部 6 题。脚本错误、浏览器控制台错误、HTTP 错误、被拦截写请求均为 0。来源：`output/task027d/browser.json`、`browser-delivery.txt`。
- 概览慢读验收：拦住真实保存列表时有 8 条骨架；列表返回、逐题详情仍等待时有 4 条；全部返回后为 0。中间没有“题目未保存”“—”“未知”“待核对”。来源：`output/task027d/loading-browser.json` 和三张对应截图。
- 数据保护：正式 `backend/data/demo.db` 和现有 `audit_backups/task014-before-20261103T144228Z.db` 的 SHA-256 与本单开始检查值、027c 留存值一致。来源：`output/task027d/data-before.json`、`final-verification.json`；两个文件都只读核对，没有新建整库备份。
- 12 张截图的 PNG 尺寸均为 1440×900。来源：`output/task027d/final-verification.json`。
- `git diff --check` 通过。改动只有前端展示、相关前端测试及本任务报告/归档；没有 Git 写命令，没有修改 `指挥/当前任务.md`。原 demo 的 PID 816、827 保持运行；本次测试及临时浏览器均已结束。

## 截图与首屏

截图均为 1440×900，来自本机现有保存数据。

| 截图 | 本机位置 |
| --- | --- |
| Baseline 报告首屏 | `output/task027d/01-baseline-report.png` |
| 报告就地打开 Bad Case | `output/task027d/02-bad-case-from-report.png` |
| 更多指标展开 | `output/task027d/03-more-metrics.png` |
| Hard Gate 2×2 | `output/task027d/04-hard-gates.png` |
| Hard Gate 说明抽屉 | `output/task027d/05-hard-gate-drawer.png` |
| Bad Case 诊断 | `output/task027d/06-bad-case-diagnosis.png` |
| Bad Case 白底抽屉 | `output/task027d/07-bad-case-drawer.png` |
| 业务 / 技术架构 | `output/task027d/08-business-architecture.png`、`09-technical-architecture.png` |
| 概览题目读取中 / 归因读取中 / 读取完成 | `output/task027d/10-overview-loading.png`、`11-overview-cause-loading.png`、`12-overview-loaded.png` |

复用 `scripts/check_viewport_fit.py`，完整结果在 `output/task027d/fit-check.json`。Hard Gate 已验证一屏；报告、诊断也完成首屏检查。三个 Baseline 页签最终均为 739px 内容 / 739px 可用区，无需滚动；无全局横向滚动。长页面仍按原设计滚动，没有截断内容。

## 待回答问题

没有阻塞本单的待回答问题。以下口径边界已保留在实现中：

- 当前业务 Judge 合同规定 Correctness 0–4、Faithfulness/Completeness 0–1 且独立评分，但没有逐档精细评分锚点；更细的分值含义为“未知”。本单只解释业务含义和代码里的聚合方式，没有伪造逐档评分规则。
- “安全拒答率”这个旧名称覆盖全部负向题预期行为；本单按实际计算解释，没有改名或修改结果。旧统计版本的安全关键题还可能使用历史 severity 分组；原保存公式继续保留，不重算旧记录。
- 消融题卡内按任务单采用口语或干扰的解释；这不表示每一道消融题采用了相同扰动。题目仍以冻结原文为准。
