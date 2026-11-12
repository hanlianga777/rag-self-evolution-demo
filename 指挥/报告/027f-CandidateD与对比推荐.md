# 027f：Candidate D、Candidate 对比与回归推荐

本单已完成。前端全量 111 个文件、659 条测试通过；后端全量 1459 项，0 失败、0 错误、21 项既有跳过；生产构建和指定浏览器验收通过。DeepSeek、回答、Judge、Agent、Sandbox 等真实模型调用均为 0。没有运行 Git 写命令，保存和推送交给值班脚本。No SPEC Change。

## 我是这样理解的

- 先读根目录 `AGENTS.md`、`指挥/README.md`、027f 任务单和 027a 的本轮总背景。开始时工作区干净，最新提交为 `703f9f5`（本单开始记录），没有发现 027f 半成品；从 027e 既有页面接着改，没有重新运行任何已评测题。
- 只改前端展示、相关测试和本报告；不改后端产品代码、SPEC、Golden、门槛、Judge 或 Agent 保存原文，不发布、不回滚、不发送实时问答。
- “10 个 Candidate 中只有 2 个通过回归检查”按任务单理解为通过包含 Hard Gate 的最终资格检查，不能把它等同于单独的 Regression PASS 数。本机只读接口根据保存记录生成 R1-A 的 `regression_review.status=PASS`，但 P99 为 86.548 秒，超过 60 秒，所以最终不合格；最终合格的是 R3-C 和 D。总表“判定”沿用保存的最终资格，规则说明写明这个口径，点击 Candidate 仍能查看单独 Regression 结果，没有改写它的保存判定。`regression_review` 本身是 `backend/app/governance.py:_regression_review` 提供的只读视图，不是本单新增的评分或历史数据修改。
- 未解决问题的排名来自 **Winner 保存报告**，不是冒充 D 当前 Trace 的排名。下一轮先检查排序是依据该位置给出的建议，不声称已经做过新实验或证明了参数因果。
- 027a 要求 demo 保持运行，所以保留原有后端 8010（PID 816）和前端 5174（PID 827）；只关闭本单启动的测试进程和浏览器。

## 原来“更多”的三项究竟是什么

来源：原 `frontend/src/components/EvolutionStory.tsx:DStory`，以及本机保存实验 `EXP-20261105143048349606` 的 `result.d_facts` 和 D 的 `reasoning.changes`。

| 原来的项 | 实际保存内容 | 本次去向 |
| --- | --- | --- |
| 剩余问题 | Winner 剩余的 Q04、Q06、Q27，含召回、重排、最终证据位置和历史修好来源；这些不是三道 D 仍失败的题 | 根据 D 相对 Winner 的 `winner_comparison.fixed_cases` 及身份核对后的保存逐题结果，排除已修好的 Q04；Q06、Q27 放进默认展开的问题卡。原重复块删除 |
| 采纳理由 | 把 Top-K 调到 6；来源是 R1-C、R2-B；保留 Winner 的 Candidate K 24 与 Thinking High；保存文字解释了为何采纳及来源前提不同 | `changes[].reason / rationale` 并入推荐结论，明确标为“采纳时的依据”；来源和全文仍可从 D 完整报告、审计查看 |
| 副作用检查 | `historical_effects`、`protected_overlap`、`winner_fixed_risk`、`gate_risk`、`mitigation`、相同/不同前提证据、`risk_checklist` | D 问题区旁边的小卡显示完整的一条历史风险原文和实际保护题/门槛核对结果；详细风险与前提放进 D 完整报告抽屉。尚未完成评测的 D 仍展示保存的风险说明，不提前给安全结论 |

原“（3）”是当时 `facts.remaining_failures.length`，不是对三类内容的可靠计数；本单删除整行折叠入口，不再沿用这个容易混淆的数字。

## 每处改动

| 位置 | 改前 | 改后 |
| --- | --- | --- |
| `EvolutionStory.tsx:DStory` | 一张大卡混放参数、预测、表格、折叠项及文字链接 | 四块独立白卡：D 的设计；预测 vs 实际；R3-C vs D；还没解决的问题。取消外层白色大底，四块边界清楚、左右对齐 |
| D 的设计 | 预测原文被两行截断，和结论挤在一起 | 参数标签保留 Winner 参数与 Top-K 唯一新增蓝框；保留“多修好 Q04，零新增 Bad Case，推荐 Candidate D”；完整预测放入与 027e 一致的蓝框，不修改保存原文 |
| D 的两张表 | 表头起点和宽度不一致 | 两张卡等宽等高，表格固定布局，三列按 32% / 34% / 34% 分配；关键信息换行显示；标题明确为 R3-C vs D |
| `DResultStory` 未解决问题 | 日志式“没修好与新弄坏的原因”默认折叠 | Q06、Q27 默认展开、并排小卡；显示预测/目标与实际状态、完整原因、Top-K 6 截止线和第 7 / 24 位标记。无保存位置时写原因未知，不画虚构排名；无实际结果时明确未知 |
| D 副作用 | 多段风险混在“更多”里 | 有保存文字才显示风险小卡；实际核对结果必须来自身份匹配的保存 D 逐题报告与门槛；缺失时仍是未知。完整风险移入报告抽屉，不丢原有内容 |
| D 底部操作 | 两个文字链接，位于大卡外，推荐入口带箭头文字 | 放到最后一张卡底部右侧，白底次要按钮并带线性图标；完整报告和推荐入口仍有效；完整 D 不显示灰色“已评测” |
| Candidate 对比轮次 | 027e 已去掉可见“查看轮次”文字 | 复查保留轮次按钮组，没有重新加文字；切换仍工作 |
| A/B/C 卡片底部 | “查看目标 N 题”“查看 Candidate 与完整报告”文字链接 | 两个小号白底次要按钮，带目标/报告图标，左右对齐；目标抽屉、完整报告和运行/续跑权限保留 |
| Sandbox 默认指标 | 答对、新增、Hard Gate、P99、安全拒答；P50 被收起 | 顺序改为答对、新增 Bad Case、Hard Gate、安全拒答率、P50、P99 |
| `ui/pages3.tsx:CompareTable` | 自动布局，展开后长内容可能撑宽；文字式展开入口 | 固定表格布局和列宽，指标列 22%，其余列均分 78%；展开只追加下方行；关闭该区域的滚动锚定，避免展开时跟随按钮移动；展开按钮改白底次要按钮，放在表格右下 |
| Sandbox 表头及高级指标 | 单轮字母和跨轮来源混用，费用占位长期保留 | Sandbox 表头使用 R1-A / R3-C 这种编号，D 保持 Candidate D；无法核算的当前费用行删除；有可信保存计费依据的记录仍保留金额，包括 0 元 |
| `FinalRecommendation.tsx` | 先 Regression，再推荐；落选方案折叠 | 从上到下为结论、全部 10 个 Candidate 的总表、合格方案对比、8 个落选原因；不再通过轮次筛选漏掉候选 |
| 推荐结论 | 推荐标题和采纳依据分散 | 24px 大字显示 10 / 2 / Candidate D；结合保存的多修好 Q04、零新增、36.7 秒 vs 22.6 秒且仍低于 60 秒门槛解释取舍；“采纳时的依据”取保存文字。右下保留唯一实心蓝色“查看发布记录”按钮 |
| Regression 总表 | 当前轮次加 Winner/D；无 Hard Gate 列 | 一表按 R1-A…R3-C、Candidate D 排列；列为修好、新增严重、新增普通、Hard Gate、判定；两条最终通过行浅蓝底；表下 12px 浅灰说明规则；可点 Candidate 打开详情 |
| 合格方案对比 | 重复显示 Hard Gate，且 Winner 详情入口和其他说明在后面 | 保留答对、新增 Bad Case、P50、P99、比 Winner 多修好；删除已在总表展示的 Hard Gate 行。保留“查看 Winner 详情”按钮 |
| 落选原因 | 8 行数据表藏在折叠项内 | 两列网格，8 个方案各一条完整主要原因；优先展示实际失败门槛及数值，否则写新增 Bad Case 数和保存资格；按钮可键盘访问并打开原抽屉 |
| 逐题追踪 | 页签底部全局折叠，和概览修复去向重复 | 删除重复全局入口；不重复的逐题回答、证据、严重程度筛选及前后对比放到各 Candidate 详情抽屉，仍能实际打开前后回答比较 |
| 参数差异抽屉 | 027a 已取消局部滚动 | 复查两个参数表 `overflowY=visible`，高度等于内容高度；没有加回内部滚动条 |
| 相关前端测试 | 依赖旧 5 行默认指标、折叠结构、旧轮次筛选与链接 | 按新展示同步断言；保留身份检查、真实结果/预测区分、费用 0、资格未知、严重程度筛选、付费确认与运行权限。新增 027f 四条专项测试 |

来源：本次文件差异、`frontend/src/task027f-candidates.test.tsx` 和本机 `output/task027f/browser.json`。

## 费用：为什么以前没采集，现在怎样处理

**结论：当前保存实验不能可靠回算历史 Sandbox 总费用，按任务单允许的做法删除费用整行。没有把缺失费用当作 0，没有用今天单价覆盖历史记录，也没有改后端计费。**

1. 原因能定位到两层。`backend/app/evaluation.py:summarize_evaluation_cases` 的旧费用列只累计 `programmatic_metrics.provider_cost`；没有数值就保存 `token_cost=null` 和 unavailable 状态。现在的 `backend/app/telemetry.py:cost_fields` 返回的是 `cost_estimation / estimated_cost`，没有直接填入这条旧字段，所以旧表并不能因为有 token 就自动得到金额。每题生成和 Judge 的用量/估算是另外保存的字段，不可混成已实扣账单。
2. 本机实际 D 的 `comparison_metrics` 只有输入 65,775、输出 74,507 token。`request_accounting` 则是输入 1,240,066、输出 443,454，205 次调用事件，还有 1 次 Usage 未知；其 `cost_estimation.status=unavailable`、`reason=model_mismatch`。前者是回答结果汇总，后者覆盖逻辑任务及续跑历史，两者口径不同。其他 Candidate 的账本同样保存模型不匹配，部分有未知 Usage。不能拿前一组数字乘单价充当后一组完整费用，也不能推定模型不匹配的具体历史调用已经查明。
3. 已只读核查 [DeepSeek 官方人民币价格页](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)（查阅日期 2026-11-12）。Flash 每百万 token：空闲时段缓存命中输入 0.02 元、未命中输入 1 元、输出 4 元；高峰对应 0.04 / 2 / 8 元。官方按调用时段、缓存命中分类计价；当前汇总两项 token 也没有提供完整的逐调用分类。这张今天的价格页不是已验证的历史人民币价格快照，不能据此悄悄补历史总额。没有新增一个假装能够精确回算的单价常量。
4. 因此当前高级指标不再有 Provider Cost / “费用未采集”行和“无法准确回算”的尾注。对其他确实已经保存可信 `cost_estimation` 或账单依据的记录，继续使用原 `billedCostText()`，包括 0 元；某列没有可信金额时显示“—”，不伪装成金额。原来的美元保存金额仍按项目既有常量 7.2 换成人民币，没有改汇率，没有新增费用。

来源：`backend/app/evaluation.py`、`backend/app/ai_service.py`、`backend/app/telemetry.py`，本单开始时只读保存到本机的 `output/task027f/optimization.json`、`evaluation.json`、`pricing-source.json`，以及 `frontend/src/components/PipelineFields.tsx:billedCostText`。完整历史实际扣款仍是未知；这不影响展示分支完成。

## 删除和保留了哪些指标

- 默认区域：P50 从展开部分移到默认区，不是删除。
- 展开区域：删除“运行状态”“Candidate 合格”“可发布”，卡片、总表和报告已表达这些状态，继续放在指标表里重复。
- 展开区域：仍保留全部原 Bad Case 修好、指定目标修好、新增严重/普通明细、其他问题改善、净改善、Regression Check；前两者分母不同，原有口径说明保留。
- 高级指标：删除 `Fixed Bad Case / target_bad_cases_fixed`，与展开区指定目标修好重复；删除 `Safety / safe_rejection_rate`，与默认安全拒答率重复；删除当前无可信金额的费用整行。
- 对任何其他保存记录：展开行若全是“—”、未知、未采集、未判定等，或只有“未知分子 / 已知分母”，不展示；与默认区同名的重复行也不展示。零是有效数值，不会因等于 0 被删除。
- 当前实验高级抽屉实际保留 9 行：Positive、Ablation、综合分、TTFT、Input Tokens、Output Tokens、Recall@K、Precision@K、MRR。没有凭空把这些真实保存数字删掉。
- 推荐页的合格方案对比删掉重复 Hard Gate 行，Hard Gate 在上方十行总表保留；答对、新增、P50、P99、额外修好 Q04 保留。

来源：`EvolutionPage.tsx:compareRows`、高级指标行、`ui/pages3.tsx:CompareTable`、`FinalRecommendation.tsx`，以及 `browser.json` 中 `expandedRows / saved advanced metric rows`。

## 测试与浏览器验收

- 专项测试：新增 `frontend/src/task027f-candidates.test.tsx` 四条，先在旧页面上得到四条预期失败，再实现并通过；覆盖完整 D 预测、默认展开问题和排名、全部十行及页面顺序、白底按钮、六行默认指标、空指标/空风险不展示、只读数据不变。来源：本机 `output/task027f/red.txt`、专项测试文件、`related-final.txt`。
- 最终前端全量：`npm --prefix frontend test -- --maxWorkers=2 --minWorkers=2`，111 个文件、659 条通过，0 失败，56.29 秒。旧测试环境的 React act 警告仍有，不能把它说成真实浏览器错误。来源：`output/task027f/frontend-delivery.txt`。
- 最终生产构建：`npm --prefix frontend run build`，TypeScript、Vite 均通过，退出码 0。来源：`output/task027f/build-delivery.txt`。
- 后端全量：`python3 output/task027f/run_backend.py`，1459 项，0 失败、0 错误、21 项跳过，588.733 秒；与 027e 的 `backend-full.json` 比较，跳过名称和原因逐项完全一致。运行前设置临时 DB、空环境文件及临时索引等路径，离开自动清理；Mock 模式并通过 Python audit hook 阻止外网连接，没有复制正式数据库。来源：`output/task027f/backend-full.txt`、`backend-full.json`、`final-verification.json`。
- `git diff --check` 通过；只用 `git status / log / diff` 读取状态，没有 Git 写命令。

浏览器运行 `python3 output/task027f/browser_acceptance.py`，本机 Chrome 无头临时上下文，全部截图为 **1440×900**，已逐张打开检查。拦截非 GET/HEAD/OPTIONS 和外部 HTTP 请求，实际被拦截请求为 0；结束自动关闭浏览器。

| 本机截图 | 实际检查 |
| --- | --- |
| `output/task027f/01-candidate-d.png` | D 的设计、蓝框完整预测、参数、新增项、独立卡片；两张表各宽 552px、高 266.5px，表头同为 y=615.22px；四块都有白底和 1px 边框 |
| `output/task027f/02-d-unresolved.png` | 向下滚动展示问题区；Q06 / Q27 的第 7 / 24 位排名、Top-K 6 截止线、旁边风险小卡和底部两个次要按钮；详细风险仍可在报告查看 |
| `output/task027f/03-comparison-collapsed.png` | Sandbox 默认六行顺序正确，R3-C / D 高亮，展开入口白底右对齐；A/B/C 底部按钮保留 |
| `output/task027f/04-comparison-expanded.png` | 点击展开后，只往下追加；表格顶部仍为 y=419.66px、宽 1118px，每列 x/宽度及前六行 y 前后一致，页面滚动位置也都是 606px，没有跳动 |
| `output/task027f/05-review-first-screen.png` | 24px 结论在上，十行总表在下；两条浅蓝通过行；结论卡底 y=391.09px，总表含规则说明底 y=854.89px，均在 900px 首屏内 |
| `output/task027f/06-review-tradeoff-and-rejections.png` | 人工向下滚动后检查合格方案取舍、Winner 详情入口及 8 个不折叠的落选原因，两列排列 |
| `output/task027f/07-expanded-metrics-scrolled.png` | 展开后再人工滚动，完整查看追加指标；与 03 / 04 的展开跳动检查分开记录，不把人工滚动当成自动跳动 |

浏览器还实际验证了轮次 1 / 3 切换、三个目标/完整报告按钮、D 完整报告与推荐跳转、参数说明整体滚动、Candidate 逐题追踪中的普通严重程度及前后回答对比、“查看发布记录”导航，以及概览、知识库、Pipeline、Golden、Baseline 的页面打开。只做读取，没有点击发布或问答发送。

- 参数差异的两个 `.table-scroll`：`overflowY=visible`，高度/内容高度分别 123/123px 和 77/77px，无局部滚动条。
- 所有截图视图都检查 `document.documentElement.scrollWidth <= innerWidth`，没有全局横向滚动。
- 最终 `pageerror=[]`、`consoleErrors=[]`、`httpErrors=[]`、`blockedRequests=[]`。来源：`output/task027f/browser.txt`、`browser.json`、`final-verification.json`。
- `/api/evaluation`、`/api/optimization?light=true&planning=true`、`/api/versions`、`/api/monitoring`、`/api/documents`、`/api/workspace` 六组排序后 JSON 的 SHA-256 前后一致；本单开始时保存的 Baseline 和实验响应也分别比对一致。这证明所核对保存响应未变，不声称整个数据库文件字节未变。来源：`output/task027f/data-before.json`、`data-after.json`、`final-verification.json`。
- 原有 demo 的 `http://127.0.0.1:8010/api/evaluation` 和 `http://127.0.0.1:5174/` 均 HTTP 200；后端根路径不是 demo API 入口。前后端进程身份仍为 816 / 827。本单测试、构建和浏览器均已退出，未留下自启动服务。

截图、运行记录、保存响应均仅存本机 `output/task027f/`，不作为公开提交内容。Provider / DeepSeek / 回答 / Judge / Agent / Sandbox 的真实调用次数为 **0**，没有新增正式问答、反馈、发布或回滚记录。

## 待回答问题

无阻塞问题。历史实际扣款未知，已按任务单“算不出就整行删除”的默认分支完成，没有为此暂停任务。

## 完成与归档

任务单已用普通 `mv` 移到 `指挥/历史任务/027f-CandidateD与对比推荐.md`。本单要求均已完成，没有留下阻塞项；没有运行 Git add / commit / push / pull / checkout 等写命令，保存与推送由自动值班脚本负责，其结果未知。
