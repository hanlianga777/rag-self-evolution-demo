# 022b：Hard Gate 2×2 与 Bad Case 归因卡片

状态：本任务接入、测试与验收全部完成。模型实际调用 0 次。No SPEC Change。

## 我是这样理解的

- 自动值班只改文件，不执行 Git 写命令；未拉取、提交、推送或改动 `指挥/当前任务.md`，保存和推送交给值班脚本。
- 总指挥提供的 `HardGateGrid`、`BadCaseLayers` 和 `ClampText` 直接复用，`frontend/src/ui/` 没有修改。布局修正放在页面自己的 CSS。
- 任务单明确要求 demo 保持运行，优先于根目录一般性的“用完要关掉”；保留原有前端 5174、后端 8010，测试浏览器和测试进程用完退出。
- 当前后端分类为“检索层问题 / 生成层问题 / 安全边界问题 / 性能问题”。直接映射到四张卡；历史记录中的“检索失败 / 检索噪声”并入检索层，“回答问题 / 过度拒答”并入生成层，“安全边界”并入安全卡。不重做归因，不改评分。
- 性能沿用原页面的整轮口径，不增加单题 Bad Case。未归因记录保留在“全部”列表并提示缺失；未保存的指标写未采集，未判定用灰色，不能当成通过或失败。
- 题数沿用原优化优先级表的计算口径，从保存的业务 Bad Case 数出；严重程度、修复思路和门槛导致的优先提示沿用 `diagnostic_categories` 与 `product_diagnostics.optimization_priorities`。旧分类合并时保留最高严重程度，修复思路按已保存优先级排列并去重。

来源：本任务单、根目录 `AGENTS.md`、`指挥/README.md`；`backend/app/diagnostic_categories.py`、`backend/app/diagnostics.py`；`frontend/src/components/ProductDiagnostics.tsx`。

## 断点检查

开工只读 `git status --short` 没有输出，工作区干净。只读 `git log -8 --oneline` 显示上一张 022a 已完成（`8b21fb8`），本张最新记录是 `de36da6` 开始值班；没有 022b 的中断成果或旧报告。本轮从已完成的 022a 接着改，没有重新运行任何付费题。

任务要求的第一步已执行：`npx tsc -b` 成功；`npx vitest run src/ui` 为 3 文件、20 条通过。新增接入测试先在旧页面失败（3 条），来源：`output/task022b/red.txt`。

## 接入结果

### Hard Gate

- 四类卡片显示 11 项既有指标。实际值、要求沿用原页面的 `gateValue` / `gateThreshold` 格式；通过状态读取保存的 `status`。
- 百分比条的实际值和门槛都除以 100；延迟实际值和门槛都除以 60 秒。没有重新计算门槛或判定。
- 正向、消融卡内只保留“正确性 / 忠实性 / 完整性”，去掉重复题型前缀。
- 提供的组件只有展示接口。页面侧的 `BaselineGates` 在现有列表项上接回鼠标点击、Enter / 空格、焦点和无障碍名称，仍打开原来的六区块指标详情，不改组件设计。
- 页面适配同时处理未判定、空组以及数据刷新后的状态，避免空组显示“0/0 通过”或旧灰色状态残留。

来源：`frontend/src/pages/EvaluationPage.tsx`；`frontend/src/task022b-baseline.test.tsx`；`output/playwright/022b/browser.json`。

### Bad Case

- 顶部优化优先级表、旧筛选按钮和独立延迟说明合并为“全部 + 四类归因卡”。本轮真实结果为全部 6、检索层 5、生成层 1、安全边界 0、性能 0。
- 安全卡读取本轮安全拒答 95.0%；性能卡读取 P50 16.7 秒、P99 42.2 秒以及保存的 Hard Gate 状态。不是写死的样板数字。0 题卡片变灰并禁用。
- 点检索层筛出 5 条、点生成层筛出 1 条、点全部恢复 6 条；原行点击与键盘详情入口保留。切换输入题目后筛选恢复“全部”。
- 标题改为“6 个 Bad Case”；“进入 Agent 处理”保留浅蓝按钮和原导航，真实浏览器验证能进入 Agent。
- 列表保留题号、问题、分类、缺了什么、严重程度与末尾详情指示，删除判定方式和优化方向列。缺失内容直接使用 `ClampText` 两行；悬停完整显示，点击可固定全文，不误开整行抽屉。
- `DataTable` 仅增加对已有 `ClampText` 的识别，避免它被再次套入单行截断；严重程度改为 `.ui-verdict`，保留完整文本，单列给 90px。
- 页面 CSS 统一数据行 72px，并把删除列留下的空间交给“缺了什么”。没有改 UI 基础组件或全站表格设计。

来源：`frontend/src/components/ProductDiagnostics.tsx`、`frontend/src/components/DataTable.tsx`、`frontend/src/pages/evaluation-workspaces.css`；真实 GET `/api/evaluation`，Baseline `EVAL-20261104115541869274`；浏览器验收记录。

## 测试与验收

- 最终前端全量：92 文件、545 条通过，0 失败、0 跳过。命令：在 `frontend/` 执行 `npx vitest run`。来源：`output/task022b/frontend-all.txt`。日志仍有项目既有的 React `act` 测试环境警告，不能称为零警告；真实浏览器脚本/控制台错误为 0。
- 本次接入相关：5 条通过。来源：`output/task022b/targeted-final.txt`。
- TypeScript + Vite 生产构建成功。命令：在 `frontend/` 执行 `npm run build`。来源：`output/task022b/build.txt`。
- 后端全量：执行 1459 条，0 失败、0 错误，`OK (skipped=21)`；21 处跳过包含 20 个测试和 1 个测试类，原因是既有私有材料缺失。逐名与 022a 的记录比对，跳过项完全相同，没有新增跳过；缺材料的项目不能算通过。命令：仓库根目录执行 `python3 output/task022b/run_backend.py`。来源：`output/task022b/backend-full.txt`、`backend-full.json`、`backend-summary.json` 与 `output/task022a/backend-full.json`。
- 最终浏览器检查：39 项，脚本/控制台错误 0，真实写请求 0；两个尺寸的八张必需截图及六张全文/抽屉截图，共 14 张，尺寸逐张核对。来源：`output/playwright/022b/browser.json`、`screenshots.json`。
- 八个主页面均可打开；11 项指标在两种尺寸下分别以鼠标或键盘打开原详情。来源：同上。


已核验的真实浏览器状态：

| 尺寸 | Hard Gate 布局 | 内容区纵向滚动 | 全部 / 检索层 / 生成层 |
|---|---|---|---|
| 1440×900 | 2×2，四卡底部 y=637.5 | 无 | 6 / 5 / 1 |
| 1280×800 | 2×2，四卡底部 y=637.5 | 无 | 6 / 5 / 1 |

Bad Case 列表可按窗口高度纵向查看；任务单只要求 Hard Gate 四卡首屏展示。两种尺寸均无全局或内容区横向溢出，实际行高一致、严重程度标记宽度小于单元格宽度。

### 测试调整原因

- `interview-evaluation.test.tsx`：四长表改为四卡、11 个指标；保留保存的实际值、门槛、身份和数据不变检查。
- `baseline-restoration.test.tsx`、`ui-polish.test.tsx`：按任务要求删掉旧两列的表头断言，其余详情与数据恢复断言保留。
- `evaluation-governance.test.tsx`：优化优先级表入口改查归因卡，保留报告/页签隔离和缺失诊断检查。
- `task009-product.test.tsx`：七个旧分类按钮改为五张卡；仍验证层筛选、原行回调、业务题数和保存的性能事实，门槛导致的优先提示随修复思路保留。
- `task012b-redesign.test.tsx`、`storytelling-v2.test.tsx`、`v13-evaluation-ui.test.tsx`：用新卡片找到相同操作，保留零题禁用、键盘打开、回访与全部恢复行为。
- 新增 `task022b-baseline.test.tsx`：5 条，覆盖动态指标与比例、原详情入口、新旧分类筛选、缺失/超线事实、输入变更恢复筛选，以及未判定刷新后的状态。

### 数据和费用边界

- 不调用 DeepSeek 或其他真实模型；没有运行新的 Baseline、Sandbox、Probe/QC，没有发布或回滚。
- 后端测试使用 `TemporaryDirectory`，DB、env、索引、文档、上传和诊断均指向临时路径，退出自动删除；启用 Mock，审计钩子阻止外网 socket 连接。没有复制正式数据库。脚本来源：复用上张 `output/task022a/run_backend.py` 的隔离方式，输出到 `output/task022b/`。
- 浏览器真实写请求为 0。验收前后将保存的 Baseline 身份、状态、冻结题卷、结果、逐题记录、配置、Judge 和指标详情取 SHA-256，均为 `f2e1579183b44d97b2141704724b44a9c28cd1e2a0b084bf662006c88b835749`。这证明所比对保存字段未变，不声称对整个正式数据库做了逐字节比较。
- 后端、门槛、评分代码以及 SPEC 均未修改。`git diff --check` 通过。推送结果由值班脚本负责，本轮未知。

## 截图与本机证据

截图在 `output/playwright/022b/`，不会提交到公开仓库：

- `hard-gate-1440x900.png`、`hard-gate-1280x800.png`。
- `bad-case-all-1440x900.png`、`bad-case-retrieval-1440x900.png`、`bad-case-generation-1440x900.png`。
- `bad-case-all-1280x800.png`、`bad-case-retrieval-1280x800.png`、`bad-case-generation-1280x800.png`。
- 两种尺寸各有 `missing-content-hover-*`、`bad-case-details-*`、`gate-details-*`，证明全文与原抽屉可用。
- `browser.json` 保存 39 项状态和交互检查，含两种尺寸、22 次指标详情打开、Agent 导航与八个主页面访问。
- `output/task022b/` 保留预期失败、测试、构建、浏览器输出和隔离测试脚本，均由现有 `.gitignore` 的 `/output/` 规则排除。

## 待回答问题

- 没有需要阻塞本任务的新问题。
- 后端既有 21 处跳过需要私有历史材料，本任务不补造、不付费重跑，不能声称缺材料分支已验收。
- 所有真实指标为通过；失败、未判定、缺失数据、安全问题非零等分支由隔离的合成测试验证，没有为截图制造正式失败。
- 自动值班提交和推送结果由值班脚本负责，本轮未执行、也未验证最终推送状态。

## 收尾

前端和后端测试进程及测试浏览器已退出，任务隔离临时目录无残留。原前端 5174 和后端 8010 继续运行，最终读取分别返回 HTTP 200。来源：`output/task022b/services.json`、`backend-summary.json`；本轮未新启动 demo 服务。

任务单已使用普通 `mv` 移入 `指挥/历史任务/022b-Baseline硬门槛2x2与BadCase诊断.md`；队列原路径已不存在。未执行 Git 保存或推送。
