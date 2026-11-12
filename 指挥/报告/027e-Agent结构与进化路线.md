# 027e：Agent 工作台结构与进化路线

本单已完成。前端全量 110 个文件、655 条测试通过；后端全量 1459 项，0 失败、0 错误、21 项既有跳过；生产构建及三张指定视图验收通过。真实模型、DeepSeek 调用均为 0。未运行 Git 写命令，提交与推送由值班脚本负责。

## 我是这样理解的

- 开始先读根目录 `AGENTS.md`、`指挥/README.md`、027e 任务单和 027a 总背景。起点工作区干净，最新提交 `f135a65` 为本单开始记录，未发现本单半成品；从已有 027d / 027c2 页面继续改，没有重跑付费题。
- 采用任务单已经确定的四页签、概览四块和蓝框样式，没有额外确认。新会话默认概览，用户已选择的页签和旧链接仍恢复原选择；`tab=overview` 显式打开概览。
- 按 027a 保留原有 demo：后端 8010（PID 816）、前端 5174（PID 827）。只关闭本单测试浏览器、测试进程，后端全量用自动清理的临时目录。
- “本轮思路”使用该轮 A/B/C 各自保存的 `core_idea` 首句，按 A/B/C 顺序连接；“设计用意”优先取 `hypothesis`，其次 `proposal`，都没有时取 `core_idea` 首句。不改写技术判断，只有现有 `storyText()` 做术语、题号、参数名的展示映射。缺少保存原文显示“—”。
- Bad Case 的“第一次修好”按 Round、A/B/C 顺序查看完整保存结果，最后才看 D；这表示保存评测里首次出现 PASS 的 Candidate，不表示参数因果已经得到单独证明。最终状态只看 D，不把其他 Candidate 的修复相加。
- 027f 负责 D 内容重构；本单仅放入切换容器，保留 `DStory` 原内容、报告入口及操作。

## 每处改动

| 位置 | 改前 | 改后 |
| --- | --- | --- |
| `frontend/src/pages/EvolutionPage.tsx` 页头 | 标题下有轮次、Candidate、预算和状态统计卡，下面三个页签 | 去掉页头统计，页签直接接标题；四页签“概览 / 进化路线 / Candidate 对比 / 回归与推荐” |
| 新增 `frontend/src/ui/evolution/AgentOverview.tsx` | 无工作台概览 | 四块依次为结果、最终参数、原样三条规则、Bad Case 去向表；数字及参数变化来自保存数据 |
| 同文件结果和参数卡 | 统计与结果分散 | 推荐身份匹配线上 published 版本才写“推荐并已发布”；D 三项差异同尺寸卡；Winner 两项沿用来源、Top-K 组合来源均从保存字段核对，缺来源写“—” |
| 同文件去向表及 `EvolutionPage.tsx` 案例抽屉 | “Agent 规划 · 逐题覆盖详情”里重复参数、事实、假设和覆盖表 | 直接六行去向表；点题 / Enter / 空格打开已有案例抽屉；只把表中放不下的诊断依据、保存方向和覆盖缺口放在抽屉。规划未完成、无推荐时仍保留进度和规划状态 |
| `EvolutionPage.tsx` 参数入口 | 路线 Baseline 行“查看可调参数” | 删除 Baseline 行；可调参数入口移入 Candidate 参数差异和 Bad Case 抽屉；仍打开现有参数说明抽屉 |
| `frontend/src/ui/evolution/EvolutionTimeline.tsx` | Baseline 起点、三轮、D 全部纵向展开 | 去掉 Baseline 起点，用共用按钮组切换一个轮次或 D；默认第一轮；D 不与普通轮次同时铺开 |
| `frontend/src/ui/evolution/model.ts` 和 Timeline | 每轮只有经验，卡片没有设计用意 | 从保存推理摘录思路与用意；经验继续用 023 原有条件和完整句；保留经验来源悬停。参数、修好、新增、Hard Gate、答对和耗时原字段保留 |
| `frontend/src/ui/extra.css` | 旧路线布局，概览无样式 | 蓝框 1.5px `--ui-accent`、浅蓝底、14px 圆角；卡片和各字段用 subgrid 对齐；概览收紧间距与行高；限定页面选择器避免旧 `.agent-overview` 样式覆盖 |
| `EvolutionPage.tsx` 轮次按钮和 Regression 行 | “查看轮次”标签；历史 Winner 混入时 Candidate 编号可能歧义 | 删除前置标签；同表跨轮使用 R1-A / R3-C，单轮 Candidate A，D 仍 Candidate D |
| `EvolutionPage.tsx` 只读预加载 | 默认 D 区块挂载时读取 D 完整结果 | 默认概览不再挂载 D，显式保留该保存报告的只读缓存预加载；切换和后台页面预热检查继续通过 |
| `frontend/src/task027e-workbench.test.tsx` 及旧展示测试 | 三页签、三轮同时显示、旧折叠块等断言 | 新增概览、来源缺失、状态未知、默认 / 深链、单轮切换、抽屉和跨轮命名检查；旧测试只改受本单展示影响的断言，保存身份、费用确认、运行权限、追踪和原操作继续检查 |

没有修改后端产品代码、SPEC、Golden、Judge、Agent 推理原文或评测记录。来源：本次代码差异及下文只读核对。

## 本机保存结果与计算来源

保存实验：`EXP-20261105143048349606`。读取入口：`GET /api/optimization?light=true&planning=true`。Candidate 完整编号为该实验号后接 `-R1-A` 等后缀；D 为 `-D`。

- 结果：Baseline `result.total - result.bad_case_count` = 44；D 的保存题数减 Bad Case 为 48；`new_regression_question_ids` 为空；`gates.passed_count / total` 为 11/11。轮次数来自 Candidate round 去重，Candidate 数取保存数组长度，预算取 `evaluation_budget.used / max`，本机为 3 / 10 / 10/12。
- 发布：读取 `overview.production` 或 active 版本，检查 `provenance=published` 且 `snapshot.candidate_id` 等于保存推荐 ID。不是根据 D 已评测就宣称发布。
- 参数：`reasoning.changed_parameters` 对照 Baseline `config`。Candidate K 12→24、Thinking Max→High 在 `D.reasoning.winner_id` 指向的 R3-C 中匹配；Top-K 4→6 由 `D.reasoning.changes[parameter=top_k].source_candidates` 的 R1-C、R2-B 及其保存参数匹配；它们不等于“前提相同所以安全”，本单没有做这种推断。
- 去向表：使用 `processingCases=agentDiagnosisRows(badCases)`，保留全部业务 FAIL，不受技术归因或 target_eligible 排除。指派读取 Candidate `observed_evidence / target_bad_cases / root_cause_evidence`，支持问题 ID 和 Bad Case ID；无匹配才展示保存方向，方向也没保存则“—”。
- 首次修好：Q04、Q06 为 R1-C；Q24、Q29、Q38 为 R1-A；Q27 未修好。最终 D 修好 Q04、Q24、Q29、Q38，Q06、Q27 仍未修好；不能把 R1-C 修好 Q06 当作 D 已修好。来源为各 Candidate 保存的 `all_fixed_question_ids` 及 D 保存结果。

## 逐句原文出处

以下均来自上述接口的 `candidates[id=实验号-后缀].reasoning`，没有调用模型。原句保存在本机 `output/task027e/saved-source-excerpts.json`，报告同时列出，供直接核对。

### 每轮本轮思路

没有额外归纳一条未保存的轮次结论。每轮依次拼接下列三个 `core_idea` 首句，只做现有展示映射，不增判断。

#### Round 1

- **R1-A · `core_idea` 原文**：把初次候选从12段扩到24段，并用2个互补问法覆盖同义表达，优先把 Q29、Q24 缺失的标准证据找回来。

- **R1-B · `core_idea` 原文**：在混合检索中把向量权重从0.5降到0.3、关键词权重升到0.7，让含「布局重大变化」「湿手」「室内存放」等原词的关键片段排进Top4。

- **R1-C · `core_idea` 原文**：把generation_thinking从max降到high降低推理耗时，同时把top_k从4提到6，补偿Q06、Q04等因Top4截断而遗漏的标准证据。

#### Round 2

- **R2-A · `core_idea` 原文**：仅启用查询改写，把口语化现场问题转成包含型号、部件和手册术语的检索问法，提升未进候选的标准证据召回，不改排序与回答策略。

- **R2-B · `core_idea` 原文**：仅把最终送给回答模型的资料段数从4提到6，不扩大初次候选池，直接让已进入候选但排第5-12的关键证据进入最终内容。

- **R2-C · `core_idea` 原文**：把思考档从max降到high以压缩推理耗时，同时生成2个互补问法补召回，主攻Q29/Q24未进候选和Q27排名过低，并保留速度余量。

#### Round 3

- **R3-A · `core_idea` 原文**：用2路互补问法扩大语义覆盖面，把因口语表述未进候选的Golden Chunk找回来，不改TopK与分数门槛。

- **R3-B · `core_idea` 原文**：对能明确回答的给全步骤，对缺关键条件的先说清能确定部分再追问1–2个关键信息，安全警告完整保留。

- **R3-C · `core_idea` 原文**：把思考档降到high显著压缩p99，用candidate_k=24扩大候选池补偿思考减少带来的召回损失，兼顾Q24/Q29补召回与延迟控制。

### 九张卡的设计用意

取下列字段的第一句；本机九条原文都是一句，因此未删除句内内容。显示层把 Golden Chunk 规范为标准说明、Final 规范为回答证据等，参数英文键转现有参数名；这些是已有 `storyText()` 映射，没有增添因果解释。

- **R1-A · `hypothesis` 原文**：召回不足类错题靠扩大候选池加多路问法补回，可在不改回答策略的前提下修好Q29、Q24。
  - **采用片段**：召回不足类错题靠扩大候选池加多路问法补回，可在不改回答策略的前提下修好Q29、Q24。
  - **处理**：保留原句；仅套用现有题号和术语展示映射。

- **R1-B · `hypothesis` 原文**：对已进入候选但排名低或被Top4截断的题，提升关键词权重可把关键原词片段推入最终内容而不新增召回成本。
  - **采用片段**：对已进入候选但排名低或被Top4截断的题，提升关键词权重可把关键原词片段推入最终内容而不新增召回成本。
  - **处理**：保留原句；仅套用现有题号和术语展示映射。

- **R1-C · `hypothesis` 原文**：降thinking档位换取速度，同时用TopK=6补偿最终证据覆盖，可在修复Q06、Q04的同时整体控制延迟。
  - **采用片段**：降thinking档位换取速度，同时用TopK=6补偿最终证据覆盖，可在修复Q06、Q04的同时整体控制延迟。
  - **处理**：保留原句；仅套用现有题号和术语展示映射。

- **R2-A · `hypothesis` 原文**：口语到手册术语的查询改写能补回未进候选的Golden Chunk，同时比扩候选+多路查询更轻量。
  - **采用片段**：口语到手册术语的查询改写能补回未进候选的Golden Chunk，同时比扩候选+多路查询更轻量。
  - **处理**：保留原句；仅套用现有题号和术语展示映射。

- **R2-B · `hypothesis` 原文**：关键片段已被找到但被Top4截断的题，只需增加最终保留条数即可补齐证据，不需要扩大候选池。
  - **采用片段**：关键片段已被找到但被Top4截断的题，只需增加最终保留条数即可补齐证据，不需要扩大候选池。
  - **处理**：保留原句；仅套用现有题号和术语展示映射。

- **R2-C · `hypothesis` 原文**：降思考档释放的速度余量可覆盖2路查询的额外检索成本，而多路互补问法能补回Q29/Q24/Q27所需证据。
  - **采用片段**：降思考档释放的速度余量可覆盖2路查询的额外检索成本，而多路互补问法能补回Q29/Q24/Q27所需证据。
  - **处理**：保留原句；仅套用现有题号和术语展示映射。

- **R3-A · `hypothesis` 原文**：Q24/Q29的根本问题是Golden Chunk未进候选，用互补问法扩大语义覆盖面即可补回，且不触碰最终保留条数，故对负向澄清扰动小于top_k=6。
  - **采用片段**：Q24/Q29的根本问题是Golden Chunk未进候选，用互补问法扩大语义覆盖面即可补回，且不触碰最终保留条数，故对负向澄清扰动小于top_k=6。
  - **处理**：保留原句；仅套用现有题号和术语展示映射。

- **R3-B · `hypothesis` 原文**：safe_rejection恰卡95，唯一失败负向题Q38属必要澄清缺失；Tiered在缺关键条件时强制追问关键信息，可稳定修复Q38并给门槛留余量。
  - **采用片段**：safe_rejection恰卡95，唯一失败负向题Q38属必要澄清缺失；Tiered在缺关键条件时强制追问关键信息，可稳定修复Q38并给门槛留余量。
  - **处理**：保留原句；仅套用现有题号和术语展示映射。

- **R3-C · `hypothesis` 原文**：思考档降到high释放的延迟余量足以覆盖candidate_k=24的扩检成本，扩池则补回未进入候选的关键证据，形成“降档+检索补偿”的平衡。
  - **采用片段**：思考档降到high释放的延迟余量足以覆盖candidate_k=24的扩检成本，扩池则补回未进入候选的关键证据，形成“降档+检索补偿”的平衡。
  - **处理**：保留原句；仅套用现有题号和术语展示映射。

### 本轮经验

继续使用 `model.ts:roundLesson()` 的 023 已有完整句，三个轮次分别为：

1. 扩候选+多路查询修好 3 题，但 P99 超标；降档+Top-K 6 修好 Q04、Q06，却拉低了安全拒答。
2. 三个 Candidate 新增 Q17；Top-K 6 修好 Q04、Q06，但安全拒答下降。
3. 降低思考档、同时把候选扩到 24，首次做到零新增 Bad Case，成为 Winner。

这些是 023 已经按保存参数、逐题变化和 Gate 条件生成的经验；不冒充本轮新生成 Agent 原文。原有来源悬停仍列出 A/B/C 参数、修好、新增、P99 和拒答率。

## 验证记录

### 自动测试与构建

- 新增 `frontend/src/task027e-workbench.test.tsx`，首轮 7 条中有 4 条按预期因旧页面没有概览及轮次按钮失败；实现后通过，随后补充跨轮 Regression 命名检查，共 8 条。来源：本机 `output/task027e/red.txt`、`green-first.txt`、`frontend-delivery.txt`。
- 最终前端全量：`npm --prefix frontend test -- --maxWorkers=2 --minWorkers=2`，110 个文件、655 条通过，0 失败，耗时 55.03 秒。来源：`output/task027e/frontend-delivery.txt`。仍有原有 React 测试环境警告；真实浏览器控制台无错误，没有把两者混写。
- 最终生产构建：`npm --prefix frontend run build`，TypeScript 和 Vite 通过。来源：`output/task027e/build-delivery.txt`。
- 后端全量：`python3 output/task027e/run_backend.py`，1459 项、0 失败、0 错误、21 项跳过，586.975 秒。与 027c2 的 `backend-full.json` 比较，跳过名称和原因逐项完全一致。来源：`output/task027e/backend-full.txt`、`backend-full.json`、`final-verification.json`。
- 后端运行器沿用 027c2 的隔离方法：临时数据库、索引、文档、上传和诊断目录，空 env，强制 Mock，audit hook 阻断非本机 socket；使用自动清理的 `TemporaryDirectory`。没有复制正式数据库。
- `git diff --check` 通过；只用了只读 Git 命令。来源：最终工具输出。

### 浏览器验收与本机截图

运行 `python3 output/task027e/browser_acceptance.py`。浏览器用本机 Chrome 无头临时上下文，1440×900；拦截所有非 GET/HEAD/OPTIONS 及外部 HTTP 请求，未触发任何被拦截请求。结束时关闭浏览器。

| 本机截图 | 检查结果 |
| --- | --- |
| `output/task027e/01-overview.png` | 四页签默认概览；发布身份、三参数来源、六行去向、4 修好 / 2 未修好均与保存数据相符；内容区 scrollHeight / clientHeight = 737 / 737 |
| `output/task027e/02-round1.png` | 默认 Round 1，仅三张卡；本轮策略与三个设计用意蓝框；参数、修好、新增、Hard Gate、答对与耗时的纵向起点逐项一致；737 / 737 |
| `output/task027e/03-round3.png` | 切换 Round 3，仅三张卡；R3-C 为 Winner，零新增；各字段对齐；737 / 737 |

上述截图均已实际打开检查，未放入公开提交内容。所有截图视图的 `document.documentElement.scrollWidth <= innerWidth`，无全局横向滚动。截图和测量来源：`output/task027e/browser.json`。

还验证了：去向表键盘 Enter 打开证据抽屉；Candidate 卡打开原详情；参数说明入口和抽屉；Candidate D 切换容器；Candidate 对比与 Round 1 筛选；回归表和最终推荐入口；`tab=overview / route / comparison / review` 深链；项目概览、知识库、Pipeline、Golden 和 Baseline 主页面都能打开。旧 candidates/sandbox/regression/recommendation 链接迁移及 diagnosis/bad 跳转仍有测试覆盖。没有点击运行、发布、回滚或发送问答。

浏览器最终 `pageerror=[]`、`consoleErrors=[]`、`httpErrors=[]`、`blockedRequests=[]`。来源：`output/task027e/browser.txt`、`browser.json`。初次浏览器脚本在抽屉关闭动画尚未结束时重复查找已卸载按钮，调整为等待顶层抽屉隐藏后再继续，最终完整验收通过；没有为此修改产品抽屉逻辑。

### 保存数据保护

浏览器验收前后，将 `/api/evaluation`、`/api/optimization?light=true&planning=true`、`/api/versions`、`/api/monitoring`、`/api/documents`、`/api/workspace` 六组 JSON 响应按键排序后计算 SHA-256，全部一致。来源：`output/task027e/data-before.json`、`data-after.json`、`final-verification.json`。这证明所核对的保存响应未变，不声称整个数据库文件字节未变。

本单未修改后端产品文件、门槛、Judge 原文、Agent 推理、Golden 或保存评测结果；未调用 Provider，没有新增问答、反馈、发布或回滚记录。

## 待回答问题

无需等待人工回复。D 内部内容按任务分工留给 027f，非本单漏项。

## 收尾

前端、后端测试和构建进程均已退出；临时测试目录已清理，本单浏览器已关闭。原有 8010 / 5174 demo 保留运行并返回 HTTP 200。按任务要求用普通 `mv` 将任务单归档到 `指挥/历史任务/027e-Agent工作台结构与进化路线.md`。

未运行任何 Git 写命令。模型、DeepSeek、问答、发布和回滚调用均为 0；提交推送由值班脚本负责，其结果未知。No SPEC Change。
