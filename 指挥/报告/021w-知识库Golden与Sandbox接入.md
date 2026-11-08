# 021w：知识库、Golden 与 Sandbox 新版接入

## 结果

已接入总指挥提供的 `KnowledgeCoverage`、`GoldenPipeline`、`CompareTable`。实时问答顶部显示真实线上 Candidate D 及 Candidate K 24、Top-K 6、Thinking High。知识库主题详情、Golden 审核与候选池、Sandbox 轮次及高级指标、Pipeline 参数和草稿、问答会话操作继续使用原来的处理函数。`frontend/src/ui/` 没有改动，没有新增依赖。来源：本次文件差异、五个宿主页面及本机浏览器验收记录。

TypeScript 与最终 Vite 构建通过；本任务核心及相邻接入测试 **33/33 通过**，受本轮展示替换影响的原测试 **15/15 通过**。最终全量前端 **460 通过、57 条既有失败，共 517 条**；对照 021s 的 61 条失败清单，新增失败 **0**。全量没有变绿，原失败留给 021x。来源：`output/task021w/tsc-final.txt`、`build-final.txt`、`core-final.txt`、`related-final.txt`、`tests-complete.json`、`failure-comparison.json`、`output/task021s/tests-complete.txt`。

1440×900、1280×800 两个尺寸，各五页的正式截图已经保存；另拍八张样板组件图作对照。最终十个正式视图无全局/内容区横向滚动、无脚本错误和 console error，相关卡片可见字重只有 400/600。验收浏览器发到后端的写请求为 0。来源：`output/task021w/final-style-check.json`、`final-screenshots.txt`。

33 张正式数据库表，开工、验收后、收尾的行数和逐表内容哈希相同。模型调用 **0**，没有重跑题目、改 Golden、改评测、发布或回滚。开工已有的前端 5174（PID 1117）、后端 8010（PID 19536）保持运行，未重启；自己打开的测试浏览器均已关闭。来源：`before-hashes.json`、`after-hashes.json`、`final-hashes.json`、端口检查和各验收脚本的关闭流程。

## 我是这样理解的

1. 这是自动值班，只改文件；未运行任何 Git 写命令，也未改 `指挥/当前任务.md`。保存与推送交给值班脚本。任务单归档用普通 `mv`。
2. 本任务属于已有页面接入，布局和组件由总指挥确定；不重新设计组件。追加的安静配色、文字与字重要求在宿主页面和旧样式中处理，`src/ui/` 保持不变。
3. 追加的验收口径优先：相关测试通过、相对 021s 新增失败为 0 即通过，不因既有 57 条失败停住。
4. “demo 保持运行”优先于通用规则的测试服务清理。保留原服务，只关闭自己创建的浏览器。
5. “不改正式数据”意味着确认框全部取消。原本没有确认框的直写按钮不实际执行；草稿保存/放弃只在浏览器内存模拟接口，2 个模拟 POST 均未发送后端，不能当成正式保存结果。
6. Pipeline 已由 021u2 接入，本任务不改其参数业务逻辑。只删标题副标题、统一状态和一处草稿参数字重。
7. 任务单要求的关键数字留在页面；定义、分母收进 ⓘ。错误、缺失、进度、历史身份和审计内容不当作无用说明删除。

来源：本轮用户指令、任务单的追加要求与硬性约束、`AGENTS.md`、`指挥/README.md`。

## 断点与开工检查

开工工作区干净，HEAD 为 `193ce67`（值班脚本开始 021w 的记录），上一任务 021v 已完成。未发现 021w 半成品或报告，没有重做历史评测。按要求先运行 `npx tsc -b`，无错误；`npx vitest run src/ui`，3 个文件、20 条通过。

开工全量测试另外暴露了已有 CSS 语法错误：`frontend/src/components/SavedAnswerComparison.css` 文件末尾留有未闭合的空 `@media(max-height:760px) {`。当时 10 个测试文件无法加载，问答页动态模块也加载失败。仅删除这段无内容的声明，未补写任何响应式设计。开工原日志为 372 通过、45 条断言失败，不能拿这个被加载错误截短的总数与最终结果直接比较；最终按 021s 的完整失败名称清单逐条比较。来源：`tests-before.json`、`tests-before.txt`、初始浏览器错误和该 CSS 文件差异。

新增五条接入测试，初次运行均因新版界面尚未接入而失败，随后通过；后续给同一条 Sandbox 测试补上“保存字段为 2 时仍使用 Baseline 的 6 作分母”的断言。来源：`frontend/src/task021w-integration.test.tsx`、`red.txt`、`core-final.txt`。

## 数据来源与口径

### 知识库

| 展示 | 来源与核对 |
| --- | --- |
| 主题名 / 片段 / 三类题位 | `/api/pipeline` 的 `knowledge.coverage.clusters`；名称用 `semantic_label`，缺失回读 `label`；片段用 `size`；题位用 `quotas.positive/ablation/negative` |
| 主题与 Child 合计 | 9 个主题合计 368 个 Child，与同一接口 `index.child_count=368` 一致 |
| 规划题位 | Full：Positive 40、Ablation 18、Negative 40，合计 98；来自覆盖规划的 `profile` 和各主题配额 |
| 当前冻结 Golden | Medium：20 / 10 / 20，合计 50；来自冻结记录及当前题表。**98 个规划题位不等于冻结 50 题**，知识库表头写“FULL 规划题位”，ⓘ 说明规划不等于已冻结测试集 |
| 保底 | 现有数据未提供“小主题题位保护”布尔标记；按任务默认，比较“主题实际三类题位总和”与 `98 × size / 368`。大于比例应得值则标保底；不把 `small_cluster_merged` 这种合并标记当作题位保护 |
| 保底实际结果 | T001、T002、T003、T004、T007、T008，共 6 个。此为按比例计算的展示标记，包含配额整数分配的上取整效果，不能推断为后端正式保护了 6 个小主题。样板只标警告，不照抄样板数据 |
| 旧记录缺配额 | 三类配额不完整时保留旧主题按钮与真实片段数，写“未完整记录”；不填造三个 0，原详情仍可打开 |
| 点击 | 用主题对应的 `cluster_id` 打开原 `/api/knowledge/clusters/{id}`，题位、材料、Child/Parent、PDF 链路保留 |

实际主题片段为 56、56、13、45、24、35、41、63、35。知识处理与证据链路技术页仍使用 021t 的 `KnowledgeDiagrams`，未改 SVG。来源：`pipeline-before.json`、`frontend/src/pages/KnowledgePage.tsx`、`backend/app/golden_v2.py`、`browser-check.json`、`extra-check.json`。

### Golden Dataset

六张状态卡换成 `GoldenPipeline`；出题、硬校验、Probe、QC 和人工确认沿用原状态条件与实际数量。分类数量从当前题目记录读取；覆盖规划若没有旧规划详情，用已有冻结记录，不把知识库 Full 的 9 主题硬套给当前 CSV 导入题卷。

当前冻结记录为 `GD-20261104115533`，冻结时间 **2026-11-04 11:55 UTC**；50 题，20/10/20。时间由匹配当前 generation run 和题号集合的冻结记录 `created_at` 转成 UTC，缺失则写未知。不是生成时间，也不是首次旧题卷冻结时间。来源：`snapshots-before.json`、`runs-before.json`、`GovernancePage.tsx`。

出处复用 021n 的同一文件名短名函数：去掉已知厂商前缀、扩展名、“完整”“中文版”，把下划线转空格；例如“宇树_B2四足机器人用户手册_中文版.pdf”显示“B2 用户手册”，页码保留。只导出已有 `ComparisonAnswer.tsx` 内的函数，没有改回答正文处理。评分列用“2 条必答”，加分详情仍在抽屉。题目继续通过 `TruncatedText → ClampText` 两行展示，全文与原详情入口保留。来源：`ComparisonAnswer.tsx`、`GovernancePage.tsx`、`FrozenQuestionDetails.tsx`、接入测试。

候选池有独立的上传业务用例、模板下载、质量筛选、暂存选题、覆盖匹配、智能补齐、创建待审核测试集以及未冻结题治理入口；正式当前题卷已冻结，页面按原规则只读，隐藏写入口。本任务保留整个页签，是否合并由总指挥另定。来源：`BusinessImportPanel.tsx`、`CandidateWorkspace.tsx`、`source-inventory-before.json`、`extra-check.json`。

### Sandbox 与线上版本

| 项目 | 来源与处理 |
| --- | --- |
| 各轮列 | 当前选择轮次的 A/B/C，加 D（若有），前置绑定 Baseline；不会把其他轮次的 Winner 混成“本轮 C”。原高级/Regression 视图的比较逻辑不动 |
| 答对 / 新增 | 完整结果 `total - bad_case_count`；新增用保存 `new_regression_question_ids` 去重计数，缺失可读保存 `new_regressions`；未知不写 0 |
| Gate / P99 / 安全拒答率 | 保存的 `gates.passed_count/total`，以及 `comparison_metrics`、`metrics`、`safety_metrics`、Gate 条目 `actual` 的原值；Gate 同分母时用数字与单位，使组件能加粗较好值 |
| 状态与强调 | 保存 Winner ID、推荐 ID、qualification；Winner 与 D 列浅底；没有完成或没有资格记录时不伪造合格。运行中/暂停保留原进度文字 |
| 全部原 Bad Case 修好 | 保存 `all_fixed_question_ids` 去重计数，**分母固定为绑定 Baseline 的 6 个原 Bad Case**。本轮 A/B/C/D 分别 1/6、1/6、3/6、4/6 |
| 指定目标修好 | 保存 `target_bad_cases_fixed`；分母按保存 `observed_evidence` / 兼容目标字段匹配 Baseline Bad Case，沿用已有 `targetRows()`；本轮 A/B/C/D 分别 1/3、1/1、2/3、1/2。没有可确认的目标集合时写未知 |
| 两个修复口径 | ⓘ 明确全体与子集关系、不能相加；D 也按原 Baseline 比较，不换成 Winner 的剩余问题作全体分母 |
| 防止误读旧字段 | 保存的 `initial_bad_case_count` 在实际 A/B/C/D 中为 8/7/3/2，不能用作此处 Baseline 分母，否则会出现“4/2”。前端不修改这个历史字段 |
| 更多指标 | 保留运行状态、全体/目标修复、严重/普通新增明细、其他改善、净改善、Regression、候选/发布资格、P50；可比数字由组件加粗较优值。不同目标分母的比值保留原值，不把分母不同的比例按修好题数强排好坏 |
| 实时问答 | `/api/versions` 中 active 线上版本的 `config` 和保存 Candidate ID；参数不从当前实验默认配置猜。已发布显示 Candidate D（24 / 6 / High），未发布显示“当前线上：初始配置” |

来源：`EvolutionPage.tsx`、`VerificationPage.tsx`、`optimization-before.json`、`evaluation-before.json`、`versions-before.json`、`backend/app/evaluation.py:finalize_saved_candidate`、`final-style-check.json`。

## 去 AI 味、去重复、颜色和字体

### 文字清单

| 原文 / 位置 | 处理 |
| --- | --- |
| 知识库“Child Embedding → K-means … → Golden 题位”链式说明 | 开工源码中已经没有这一行，保持不出现 |
| “根据文档主题检查知识覆盖，并安排正向、消融和负向测试题”及“主题聚类 · 初始 … → 最终 …” | 删除旧日志式说明；规划口径用标题和 ⓘ 一句人话 |
| Golden 六个阶段的“已完成”等大卡 | 换流水线，保留各步骤完成条件和数量 |
| Golden 标题下“50 题 · 已冻结 · 日期” | 删除重复；数字与冻结时间集中到流水线。初次读取中的状态移到加载区域保留 |
| Sandbox“候选收益与副作用已保存，资格以正式结果为准”等说明横幅 | 删除。结果与资格直接由表格和状态呈现；运行进度/未知不删除 |
| `frontend/src/pages/EvolutionPage.tsx`：<p>读取 Bad Case 诊断，多轮提出 A/B/C 方案并在 Sandbox 验证；出现合格 Winner 后，由 Candidate D 判断能否在 Winner 基础上融合精修。</p> | 删掉标题下副标题 |
| `frontend/src/pages/SettingsPage.tsx`：<p>固定知识处理与评测规则，让 Agent 在允许的参数范围内优化。</p> | 删掉标题下副标题 |
| `frontend/src/pages/OverviewPage.tsx`：<p>评测驱动的 RAG 持续优化与版本决策系统</p> | 删掉标题下副标题 |
| `frontend/src/pages/VersionsPage.tsx`：<p>将已验证的优化方案交由人工决策，保留版本变化与回滚依据。</p> | 删掉标题下副标题 |
| `frontend/src/pages/VerificationPage.tsx`：<p>{tab === "compare" ? "同一道题，看优化前后的真实回答差在哪里。" : "通过实时问答验证线上版本，并观察同一道问题优化前后的实际回答。"}</p> | 删掉标题下副标题 |
| `frontend/src/pages/GovernancePage.tsx`：<p>{loadingWorkspace ? checkingSnapshot ? "正在读取当前冻结题卷…" : "正在读取题卷…" : frozen ? `${current.length.toLocaleString()} 题 · 已冻结 · ${frozenDate}` : "检查题目与来源，完成人工确认后冻结题卷。"}</p> | 删掉标题下副标题 |
| `frontend/src/pages/EvaluationPage.tsx`：<p>用冻结 Golden 评测当前版本，识别质量 Hard Gate、单题失败及可优化问题。</p> | 删掉标题下副标题 |
| `frontend/src/pages/KnowledgePage.tsx`：<p>将原始文档加工为可检索、可评测、可追溯的知识资产。</p> | 删掉标题下副标题 |
| `frontend/src/components/ProductDiagnostics.tsx`：<p className="muted">判分耗时不计入回答延迟。耗时和占比来自本轮保存的回答阶段记录。</p> | 收进 ⓘ |
| `frontend/src/components/ProductDiagnostics.tsx`：<p className="muted">{comparison.note \|\| '对照来自保存的评测记录。'} 回答耗时和回答费用沿用保存记录，判分费用另计。</p> | 收进 ⓘ |
| `frontend/src/pages/KnowledgePage.tsx`：<p className="muted">小块负责找得准，大块负责答得全。点击 Parent-Child 查看真实分块及原文。</p> | 删，步骤本身已有说明和入口 |
| `frontend/src/pages/AssistantPage.tsx`：<p>在输入区提交问题，核对实际回答及来源证据。</p> | 删，输入框已有提示 |
| `frontend/src/pages/AssistantPage.tsx`：对话标题旁重复的线上版本 / 当前线上配置 | 删，保留顶部当前线上 |
| `frontend/src/pages/EvolutionPage.tsx`：<p className="round-heading">Round {round} · {displayedCandidates.length} 个候选 · {displayedCandidates.filter(c=>c.status==="evaluated").length} 个完成评测</p> | 删，轮次切换和方案卡已分别显示 |
| `frontend/src/pages/EvolutionPage.tsx`：已发布 Candidate D 已发布 | 删掉传入状态文本中的重复已发布，保留徽章的已发布与方案名 |
| 异常、缺失、预算/运行进度、历史身份、冻结限制、审计原文 | 保留；删除会影响操作或把不完整结果当正式结果 |

来源：宿主页面与 `ProductDiagnostics.tsx` 的文件差异、`output/task021w/copy-changes.json`。`AgentStats` 中原“已发布 Candidate D 已发布”已减为一次状态加方案名；方案卡上重复的轮次/候选数/已完成串删除，轮次按钮和各卡状态保留。

### 颜色和字体

旧 `styles.css` 的红绿蓝硬编码色改为 `var(--ui-*)`；状态底色和大段彩色字改为中性色，红绿留给语义圆点，Winner/推荐使用蓝色强调。旧问答样式的白色和灰色字面值也改为变量，黑色阴影透明度保留。所有布局、SVG 和 `ui.css` 未改。

删去不一致的页面字号和非 400/600 字重覆盖共 **97 项**；公共标题统一使用已有 `--text-title`，保留各页共同的标题层级。组件本身仍用总指挥源码，在宿主把 `ui-kc-name` 的 550、标签/汇总的 650/700、CompareTable 表头/最佳值的 650/700、行名 500，以及 Pipeline 草稿 ParamChip 的 650 统一为 400/600。最终十个页面的相关卡片逐节点扫描符合两种字重。来源：`styles.css`、`golden-workspace.css`、`typography-removed.json`、`final-style-check.json`。

以下逐项列出删除的原覆盖，保留原布局声明；已有空规则未顺手清理。

| 文件 | 原选择器 | 删除的字号 / 字重 |
| --- | --- | --- |
| `frontend/src/styles.css` | `.brand` | `font-weight: 500;` |
| `frontend/src/styles.css` | `.page-title h1, .page-title h2, .assistant-intro h2` | `font-size: 28px;` |
| `frontend/src/styles.css` | `.page-title h1, .page-title h2, .assistant-intro h2` | `font-weight: 700;` |
| `frontend/src/styles.css` | `.page-title p, .muted` | `font-size: 14px;` |
| `frontend/src/styles.css` | `.eyebrow` | `font-weight: 750;` |
| `frontend/src/styles.css` | `.primary, .secondary, .text-button` | `font-weight: 700;` |
| `frontend/src/styles.css` | `.stage-stepper .current small` | `font-weight: 700;` |
| `frontend/src/styles.css` | `.next-action-label` | `font-weight: 700;` |
| `frontend/src/styles.css` | `.production-details dd` | `font-weight: 650;` |
| `frontend/src/styles.css` | `th` | `font-weight: 650;` |
| `frontend/src/styles.css` | `.tabs button, .filters button` | `font-size: 14px;` |
| `frontend/src/styles.css` | `.tabs button.selected, .tabs button.active` | `font-weight: 700;` |
| `frontend/src/styles.css` | `.filters button.selected` | `font-weight: 700;` |
| `frontend/src/styles.css` | `.review-filters button` | `font-size: 12px;` |
| `frontend/src/styles.css` | `.review-filters button.active, .review-filters button[aria-pressed="true"]` | `font-weight: 700;` |
| `frontend/src/styles.css` | `.review-table td` | `font-size: 12px;` |
| `frontend/src/styles.css` | `.review-table .secondary` | `font-size: 12px;` |
| `frontend/src/styles.css` | `.review-batch` | `font-size: 12px;` |
| `frontend/src/styles.css` | `.review-batch .muted` | `font-size: 12px;` |
| `frontend/src/styles.css` | `.drawer-head` | `font-weight: 750;` |
| `frontend/src/styles.css` | `.drawer-body h3` | `font-weight:700;` |
| `frontend/src/styles.css` | `.document-reader header span` | `font-weight: 650;` |
| `frontend/src/styles.css` | `.document-reader h3` | `font-weight: 650;` |
| `frontend/src/styles.css` | `.inspector-tabs button` | `font-weight: 650;` |
| `frontend/src/styles.css` | `.pipeline-selector select` | `font-weight: 700;` |
| `frontend/src/styles.css` | `.evidence-list > span` | `font-weight: 700;` |
| `frontend/src/styles.css` | `.recommended-text` | `font-weight: 750;` |
| `frontend/src/styles.css` | `.settings-grid .panel` | `font-size: 13px;` |
| `frontend/src/styles.css` | `.settings-grid .muted, .two-column > .panel > p` | `font-size: 13px;` |
| `frontend/src/styles.css` | `.conversation-item strong` | `font-size: 12px;` |
| `frontend/src/styles.css` | `.conversation-item span` | `font-size:12px;` |
| `frontend/src/styles.css` | `.chat-header strong` | `font-size: var(--card-title);` |
| `frontend/src/styles.css` | `.chat-header strong` | `font-weight:700;` |
| `frontend/src/styles.css` | `.chat-header span` | `font-size:12px;` |
| `frontend/src/styles.css` | `.chat-message` | `font-size: 14px;` |
| `frontend/src/styles.css` | `.message-label > span` | `font-weight: 750;` |
| `frontend/src/styles.css` | `.empty-chat h2` | `font-size: var(--card-title);` |
| `frontend/src/styles.css` | `.empty-chat h2` | `font-weight:700;` |
| `frontend/src/styles.css` | `.empty-chat p` | `font-size: 13px;` |
| `frontend/src/styles.css` | `.chat-composer input` | `font-size: 13px;` |
| `frontend/src/styles.css` | `.operation-head strong` | `font-weight: 650;` |
| `frontend/src/styles.css` | `.page-title h1, .page-title h2` | `font-size: var(--text-title);` |
| `frontend/src/styles.css` | `.section-head h2` | `font-weight: 650;` |
| `frontend/src/styles.css` | `.d-result-grid strong` | `font-weight:700;` |
| `frontend/src/styles.css` | `.experiment-page > .page-title h2` | `font-size: 22px;` |
| `frontend/src/styles.css` | `.verification-page .assistant-intro h2` | `font-size: 22px;` |
| `frontend/src/styles.css` | `.golden-composition` | `font-size: 13px;` |
| `frontend/src/styles.css` | `.chat-message.assistant .answer-text` | `font-size: var(--card-body);` |
| `frontend/src/styles.css` | `.qa-production-tag` | `font-size:12px;` |
| `frontend/src/styles.css` | `.answer-config strong` | `font-weight: 500;` |
| `frontend/src/styles.css` | `.overview-page .overview-intro` | `font-size: 13px;` |
| `frontend/src/styles.css` | `.knowledge-notice` | `font-size: 13px;` |
| `frontend/src/styles.css` | `.coverage-explainer` | `font-size: 13px;` |
| `frontend/src/styles.css` | `:is(.settings-page,.governance-page,.evaluation-page,.evolution-page,.versions-page,.verification-page).page-shell .page-content, .drawer, .confirm-dialog` | `font-size:var(--card-body);` |
| `frontend/src/styles.css` | `:is(.settings-page,.governance-page,.evaluation-page,.evolution-page,.versions-page,.verification-page).page-shell :is(.section-head h2,h3,.field-label), .drawer :is(.section-head h2,h3,h4,.field-label), .confirm-dialog h3` | `font-size:var(--card-title);` |
| `frontend/src/styles.css` | `:is(.settings-page,.governance-page,.evaluation-page,.evolution-page,.versions-page,.verification-page).page-shell :is(.section-head h2,h3,.field-label), .drawer :is(.section-head h2,h3,h4,.field-label), .confirm-dialog h3` | `font-weight:700;` |
| `frontend/src/styles.css` | `:is(.settings-page,.governance-page,.evaluation-page,.evolution-page,.versions-page,.verification-page).page-shell :is(.muted,small), .drawer :is(.muted,small), .confirm-dialog :is(.muted,small)` | `font-size:var(--card-support);` |
| `frontend/src/styles.css` | `:is(.settings-page,.governance-page,.evaluation-page,.evolution-page,.versions-page,.verification-page).page-shell .page-title p` | `font-size:var(--text-subtitle);` |
| `frontend/src/styles.css` | `:is(.settings-page,.governance-page,.evaluation-page,.evolution-page,.versions-page,.verification-page).page-shell :is(th,td), .drawer :is(th,td)` | `font-size:var(--text-table);` |
| `frontend/src/styles.css` | `:is(.settings-page,.governance-page,.evaluation-page,.evolution-page,.versions-page,.verification-page).page-shell th, .drawer th` | `font-weight:650;` |
| `frontend/src/styles.css` | `:is(.settings-page,.governance-page,.evaluation-page,.evolution-page,.versions-page,.verification-page).page-shell :is(.report-grid dd,.report-grid dt,.compact-config-diff,.candidate-result,.answer-markdown,.answer-text), .drawer :is(.report-grid dd,.report-grid dt,.compact-config-diff,.candidate-result,.technical-record,.case-answer), .drawer .story-details p` | `font-size:var(--card-body);` |
| `frontend/src/styles.css` | `.drawer .drawer-head h2, .confirm-dialog h2` | `font-weight:750;` |
| `frontend/src/styles.css` | `.page-content :is(.metric, .stage-stepper li, .asset-card, .knowledge-strategy-card, .flow-step, .cluster-card, .diagnosis-card, .candidate-card, .conclusion-card, .report-decision, .pending-note, .parameter-list > div, .next-action)` | `font-size: var(--card-body);` |
| `frontend/src/styles.css` | `.page-content :is(.metric, .asset-card, .knowledge-strategy-card, .flow-step, .cluster-card, .diagnosis-card, .candidate-card, .conclusion-card, .report-decision, .next-action, .stage-stepper) :is(h2,h3,strong)` | `font-size: var(--card-title);` |
| `frontend/src/styles.css` | `.page-content :is(.metric, .asset-card, .knowledge-strategy-card, .flow-step, .cluster-card, .diagnosis-card, .candidate-card, .conclusion-card, .report-decision, .next-action, .stage-stepper) :is(h2,h3,strong)` | `font-weight: 700;` |
| `frontend/src/styles.css` | `.page-content :is(.metric, .asset-card) > strong` | `font-size: var(--text-metric);` |
| `frontend/src/styles.css` | `.page-content :is(.asset-card, .knowledge-strategy-card, .cluster-card, .flow-step, .metric) small, .stage-stepper small` | `font-size: var(--card-support);` |
| `frontend/src/styles.css` | `.page-content :is(.knowledge-strategy-card,.diagnosis-card,.candidate-card,.next-action) p` | `font-size: var(--card-body);` |
| `frontend/src/styles.css` | `.knowledge-page .asset-card > strong` | `font-size:16px;` |
| `frontend/src/styles.css` | `.coverage-status` | `font-size:var(--card-body);` |
| `frontend/src/styles.css` | `.search-space-groups h3` | `font-weight:700;` |
| `frontend/src/styles.css` | `.search-space-control strong` | `font-weight:700;` |
| `frontend/src/styles.css` | `.golden-summary-strip,.pool-summary-strip,.pool-profile-match` | `font-size:var(--card-body);` |
| `frontend/src/styles.css` | `.golden-workspace .gate-one-action label` | `font-size:var(--card-body);` |
| `frontend/src/styles.css` | `.candidate-workspace .candidate-card p,.candidate-workspace .candidate-card span` | `font-size:var(--card-body);` |
| `frontend/src/styles.css` | `.candidate-workspace .candidate-card small` | `font-size:var(--card-support);` |
| `frontend/src/styles.css` | `.coverage-topic-list summary` | `font-size:var(--card-body);` |
| `frontend/src/styles.css` | `.coverage-topic-list summary small` | `font-size:var(--card-support);` |
| `frontend/src/styles.css` | `.settings-page .section-head h2,.golden-workspace .section-head h2,.governance-page .page-content > .panel > .section-head h2` | `font-size:var(--card-title);` |
| `frontend/src/styles.css` | `.settings-page .section-head h2,.golden-workspace .section-head h2,.governance-page .page-content > .panel > .section-head h2` | `font-weight:700;` |
| `frontend/src/styles.css` | `.golden-workspace .golden-summary-strip .coverage-summary` | `font-size:var(--card-body);` |
| `frontend/src/styles.css` | `.golden-workspace .golden-review-role` | `font-size:var(--card-support);` |
| `frontend/src/styles.css` | `.golden-workspace .history-pagination` | `font-size:var(--card-body);` |
| `frontend/src/styles.css` | `.section-head h2, .settings-page .section-head h2, .golden-workspace .section-head h2, .governance-page .page-content > .panel > .section-head h2` | `font-size:16px;` |
| `frontend/src/styles.css` | `.overview-page .stage-stepper span` | `font-size:12px;` |
| `frontend/src/styles.css` | `.knowledge-page .asset-card > strong` | `font-size:24px;` |
| `frontend/src/styles.css` | `.knowledge-page .asset-card small` | `font-size:12px;` |
| `frontend/src/styles.css` | `.parent-child-groups h3` | `font-size:14px;` |
| `frontend/src/styles.css` | `.flow-number` | `font-size:12px;` |
| `frontend/src/styles.css` | `.knowledge-page .asset-card[data-asset="Embedding"] > strong` | `font-size:16px;` |
| `frontend/src/pages/golden-workspace.css` | `.governance-page .golden-metrics .metric small` | `font-size: 12px;` |
| `frontend/src/pages/golden-workspace.css` | `.governance-page .review-table td` | `font-size: 13px;` |
| `frontend/src/pages/golden-workspace.css` | `.frozen-question-details .drawer-section h3` | `font-size: 16px;` |
| `frontend/src/pages/golden-workspace.css` | `.frozen-question-details .drawer-section p, .frozen-question-details li, .frozen-question-details blockquote` | `font-size: 14px;` |
| `frontend/src/pages/golden-workspace.css` | `.frozen-question-details .golden-evidence strong` | `font-size: 14px;` |
| `frontend/src/pages/golden-workspace.css` | `.frozen-question-details .golden-quality-results strong` | `font-size: 14px;` |
| `frontend/src/pages/golden-workspace.css` | `.frozen-question-details pre` | `font-size: 12px;` |

## 功能清单前后核对

开工先读取原按钮/抽屉/筛选/编辑/草稿处理，并抓取可见页面控件。Golden 初次异步清单尚未完全加载，另外用开工 HEAD 的源码清单补全条件入口，最终在真实数据加载后核对。源码清单涉及 Knowledge、Golden、Agent、Pipeline、Assistant、Verification、CandidateWorkspace、BusinessImportPanel；没有把冻结时不可用的编辑按钮说成可写功能。来源：`inventory-before.json`、`source-inventory-before.json`、`browser-check.json.inventory`、`extra-check.json.inventory`。

| 原功能 | 改后核对与结果 |
| --- | --- |
| 知识资产 / 技术架构 | 两个页签切换正常，021t 技术图不变 |
| 9 主题与详情 | 九行逐项打开/关闭；规划与保底 ⓘ 悬停可见；旧缺配额记录的详情入口由原测试继续覆盖 |
| 题位 / 材料 / Child / Parent / PDF | 从主题进入 Q01，读取材料，打开原 Child/Parent，再定位 PDF，全链路可达 |
| 文档搜索 / 四份文档 | 搜索 KIRA 得一份，清空恢复四份；四份分别打开 PDF 原文、分块结果、索引信息 |
| 新增文档 | 点击弹文件选择器，未选文件，无上传 |
| 删除 / 重建 Knowledge Pipeline | 原来直接写接口，无确认框；核对按钮与原处理函数，未实际触发。相关删除单测仍验证同一 DELETE 和刷新行为 |
| Golden 当前 / 候选池 | 两页签保留；Positive/Ablation/Negative/全部筛选为 20/10/20/50，滚动加载从 30 到 50 正常 |
| 50 题详情 | 50 道逐项打开、关闭；问题/答案/来源/评分保留，编辑/替换/批准保持冻结禁用 |
| Probe / QC | 原入口和触发函数保留；正式记录不重跑，避免调用模型。失败 Probe 的“待处理”由原测试继续覆盖 |
| 新建测试集 / Profile | Profile 入口保留，新建只打开费用确认框后取消 |
| 历史 / 导出 / 审计 | 历史抽屉、三种导出下载（Markdown/CSV/JSON）、运行审计正常；只读 GET，无正式数据改动 |
| 候选池质量筛选 | 全部/可用/待治理逐项切换，原只读题详情可打开；当前冻结状态无上传/创建写入口 |
| 未冻结治理 / 编辑 / 替换 / 草案 | `CandidateWorkspace`、`BusinessImportPanel` 原业务代码未改；正式冻结状态下不能执行。原有条件分支保留，不解除冻结来测试 |
| Sandbox Round 1–3 | 每轮均为 Baseline + 本轮 ABC + D；五项主指标正常；更多指标可展开/收起，分母 ⓘ 正常 |
| 查看高级指标 | 原抽屉能开关，Recall@K、Input Tokens 等仍在 |
| Agent 原收费/写操作 | 生成 ABC、批跑、单跑、续跑、下一轮、确认 Winner、组合建议、发布共八类确认框，在浏览器内存替换 GET 状态后分别打开并取消。未执行按钮的确认动作 |
| Pipeline 12 项选择 / Baseline 与线上标记 | 原 ParamGrid、参数选项、说明、两类标记保留；可选参数抽屉正常 |
| Pipeline 草稿保存 / 放弃 | 只在浏览器内存模拟两次 POST。改 Candidate K → 保存 → 放弃后，Candidate K 恢复原默认值；已有 Thinking 差异说明见待回答问题 |
| 实时问答 | 当前线上提示正确；输入/清空草稿、发送按钮可用性、新建对话、清空本机记录正常；没有发送提问，也未点击推荐问题触发模型 |
| 会话列表 / 删除 / 回答审计 / 引用 / 反馈线索 | 原处理函数保持。实际空会话视图没有历史回答可以点击；未造正式回答，相关既有测试和源码清单保留这些路径 |

来源：`browser-check.json`、`extra-check.json`、`confirmation-check.json`、相关测试；浏览器内存响应均为验收夹具，不是正式业务执行成功的证据。

## 测试改动说明

| 测试文件 | 原保证 | 现在怎样继续验证 |
| --- | --- | --- |
| 新增 `task021w-integration.test.tsx` | 新接入覆盖 | 五条：真实主题配额与详情、冻结时间与状态、短名/必答/题目全文、Sandbox 数字/强调/轮次/分母、线上参数不取实验默认值 |
| `agent-restoration.test.tsx` | 运行状态、修复与资格独立、不能提前确认 Winner | 默认五行，展开更多后继续检查原修复/资格，保留禁用确认与批跑入口断言 |
| `diagnostic-workspaces.test.tsx` | 正式阻断与待处理记录不能被清除 | 展开更多后检查原严重/普通新增明细，原 pending/disputed 数组不变断言保留 |
| `golden-redesign.test.tsx` | 冻结题卷缓存与冻结控件 | 冻结状态改定位新摘要，题目、控件、无写请求等断言保留 |
| `task009c-ui.test.tsx` | 冻结题卷、导入来源及加载中不能冻结 | 新摘要核对冻结时间与阶段；加载状态仍可见，冻结按钮仍隐藏 |
| `interview-assets.test.tsx` | 六阶段与失败 Probe 状态 | 定位新流水线的六步；仍核对 0/1、待处理，而非待开始 |
| `interview-evaluation.test.tsx` | 八个原决策/状态指标及高级信息可达 | 先核对五项主行，再展开更多核对原状态/修复/Regression/两类资格，保留 Input Tokens 与原数据不变断言 |
| `task018b-pages.test.tsx` | 真实覆盖优先、配额合计、删除与刷新 | 改定位规划题位标题和三类配额 2/1/3，原 DELETE 与刷新断言不变 |
| `task019a.test.tsx` | 真实字段、缺失列不虚构 | 文案从“必答 3 · 加分 1”改成“3 条必答”；字段和缺失列断言保留 |

没有通过删用例或改业务预期清除既有失败。15 条展示适配相关原用例单独全过；同文件中的 49 条非此次筛选目标用例不是这次单独运行的验收范围，全量运行中仍覆盖。来源：各测试文件差异、`related-final.txt` 和全量 JSON。

## 截图及样板差异

全部只存本机 `output/task021w/`，不提交截图和运行日志。正式页面：

| 页面 | 1440×900 | 1280×800 |
| --- | --- | --- |
| 知识库 | `1440x900-knowledge.png` | `1280x800-knowledge.png` |
| Golden | `1440x900-golden.png` | `1280x800-golden.png` |
| Sandbox Round 3 | `1440x900-sandbox.png` | `1280x800-sandbox.png` |
| Pipeline | `1440x900-pipeline.png` | `1280x800-pipeline.png` |
| 实时问答 | `1440x900-qa.png` | `1280x800-qa.png` |

更多指标为对应 `*-sandbox-more.png`；样板为 `{尺寸}-gallery-{knowledge,golden,sandbox,pipeline}.png`。Pipeline 最终截图已等待 `.ui-pg-row` 参数实际加载后拍摄，没有把初次空骨架当成正式截图。来源：`final_screenshots.py`、`final-style-check.json`。

| 与 `/ui-gallery.html` 的差异 | 原因 |
| --- | --- |
| 知识库有 FULL 规划题位标题和定义入口 | 明确 98 规划与 50 冻结的口径；样板未说明两套题数 |
| 主题顺序和片段数不同 | 用真实聚类顺序和数据；蓄电池 45（样板 43）、位置代码 35（样板 36）、故障 35（样板 36），双方合计均 368，不修改真实值迎合样板 |
| 6 个保底而非样板只标警告 | 按任务明确的比例判定，样板是手工 Fixture 标记 |
| Golden 覆盖规划写冻结记录，显示完整 UTC 冻结时间 | 当前冻结题卷没有保存可直接用的覆盖主题详情，不能把样板 9 主题当正式记录；日期来自当前冻结记录 |
| Sandbox B 安全拒答率 95.0%，样板 100% | 读取保存指标；不改数据来对齐 Fixture |
| Sandbox 列名含 Round 3；更多指标 10 项（样板 3 项） | 保留轮次辨识、原状态/Regression/资格等功能；修复数显示明确分母 |
| Winner 状态无整块蓝色底，字体限定 400/600 | 按任务追加安静规则在宿主适配；Winner/推荐列仍浅蓝强调 |
| Pipeline 选项、冻结模型和配置差异与样板不同 | 继续读取真实 `/api/pipeline` 合同，021u2 实现不重写 |
| 实时问答没有独立画廊页面样板 | Gallery 的 PageSamples 没有实时问答组件，按现有会话页面和本任务版本提示验收，不虚构样板 |

来源：`frontend/src/ui/PageSamples.tsx`（只读）、真实接口快照、两尺寸正式/样板截图。

## 待回答问题与未实际执行的部分

1. **知识库直写按钮没有原确认框。** 重建、删除会直接写接口；实时发送/推荐问题也会直接调用模型。本任务没有改这些原行为，也没有实际触发。若总指挥希望全部先确认，需要另列行为修改任务。本轮只核对原入口/处理及相关单测，新增文档只打开文件选择器。
2. **Pipeline 原默认值与 Baseline 有一个 Thinking 差异。** `baseline_defaults` 为 High，保存 Baseline 为 Max；原 `startDraft()` 优先取 defaults，放弃修改后 Candidate K 恢复，但仍显示 Thinking Max → High 的 1 项差异。这是原代码/原接口数据的组合结果，正式数据哈希不变，本任务按“Pipeline 跳过”没有修复。是否以后调整默认来源，由总指挥决定。来源：`SettingsPage.tsx:startDraft`、`pipeline-before.json`、`extra-check.json.draft_after_discard`。
3. 未调用模型，未修改正式配置草稿、知识库、Golden 或评测，未发布/回滚；正式问答响应、收费运行与真实保存结果因此不在此次验收声明内。原有 57 条前端失败也未扩展修复。

## 交付与清理

报告保存在本路径。截图、测试日志、接口快照、哈希和浏览器脚本位于被忽略的本机 `output/task021w/`。本任务不保存 commit、不推送，由值班脚本接手；完成后仅用普通 `mv` 把任务单移入 `指挥/历史任务/`。No SPEC Change。
