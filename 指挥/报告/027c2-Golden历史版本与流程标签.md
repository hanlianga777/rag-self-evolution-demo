# 027c2：Golden 历史版本与流程标签

历史版本抽屉与六步流程条已完成修改。前端全量 109 个文件、647 条测试通过；最终生产构建通过；1440×900 浏览器专项检查通过。后端全量 1459 项，0 失败、0 错误，21 项既有跳过的名称和原因不变。真实模型与 DeepSeek 调用均为 0。没有运行 Git 写命令，保存和推送交给值班脚本。No SPEC Change。

## 我是这样理解的

- 开始先读根目录 `AGENTS.md`、`指挥/README.md`、027c2 任务单及 027a 的本轮总背景，再检查工作区、提交记录和本机产出。起点工作区干净；`582409d` 虽写“已做部分已保存”，实际只改了一行值班记录；没有发现 027c2 的代码改动、报告或本机验收目录。因此保留已完成的 027c、027d，在它们的成果上完成本单，没有重跑任何付费题目。来源：起点 `git status --short`、`git log -8 --oneline`、`git show --stat 582409d`。
- “第 N 版”按现有版本保存时间从旧到新编号，列表仍沿用原有顺序；时间沿用浏览器本地时区的 `localShortTime`。没有写回版本号或时间。当前五份冻结版本显示第 5 版至第 1 版。来源：`GovernancePage.tsx:73`、`:292`，`output/task027c2/browser.json`。
- “当前使用”按 `workspace.current_golden_id` 标记，选中其他版本也不移动该标签；选中与当前使用是两个状态。来源：`GovernancePage.tsx:72`、`:294`，新回归测试与浏览器切换记录。
- 覆盖规划优先显示工作集保存的 `frozen_plan.clusters.length`；该字段缺失时，读取已有 GET `/api/pipeline` 的 `knowledge.coverage.clusters.length`，再回退到 `final_k`。当前 CSV 工作集没有保存覆盖计划，因此本机显示的 9 来自当前知识库覆盖数据，并非声称历史 CSV 考卷保存过 9 个主题。请求中用骨架，失败或缺字段显示“未知 个主题”，不把 9 写死。来源：`GovernancePage.tsx:102`–`:111`、`:269`，本机 GET 返回与 `browser.json`。
- Gate 1 按任务单原文采用上行“Gate 1”、下行“人工审核”，不再在该节点另加题数；完成状态仍取原来的冻结记录判定。来源：任务单第 2 节、`GovernancePage.tsx:274`。
- 按 027a 的“demo 保持运行”，保留起点已有后端 8010（PID 816）和前端 5174（PID 827）；只关闭本次启动的测试程序与临时浏览器。

## 改了什么

| 位置 | 修改结果 |
| --- | --- |
| `frontend/src/pages/GovernancePage.tsx:291` 历史版本抽屉 | 删除顶部“版本操作”卡；每行显示“第 N 版 · 月-日 时:分 · 题数”及原状态徽章。GD 编号仅放进已有黑底白字悬停提示；当前版本额外显示蓝色“当前使用”标签 |
| 同文件 `:297` 选中版本题目 | 标题右侧依次放“导出 Markdown”“导出 CSV”“导出 JSON”“查看审计”；均为小号白底次要按钮。查看题目、版本选择和审计原 GET 链路保留 |
| 同文件原 `historyExportable`、`historyRunId` 条件 | 可用条件不变：有来源工作集才能审计；导出继续使用原有完整题量条件和来源判断。不可用操作现在保留为灰色按钮，并通过黑色悬停提示说明“没有关联的工作集”或“题目尚未齐全” |
| 同文件 `:269`、`:274` 与 `frontend/src/ui/pages3.tsx:11` | 第一节点读真实主题数；Gate 1 上行蓝色小字，下行人工审核。其他四个节点的题数、状态和判定保持原样 |
| `frontend/src/pages/golden-workspace.css:59`–`:69` | 仅针对本抽屉落实小按钮尺寸、蓝色当前标签和列表布局；仅针对 Golden Gate 节点落实字号、颜色和不换行。没有修改全站徽章或按钮规则 |
| `frontend/src/task027c2-history.test.tsx` 与相关旧测试 | 新增 5 条回归检查；旧测试只同步本单要求的审计入口名称和流程标签断言，保留原有冻结、审计、候选题、预览、筛选等功能检查；没有删测试或新增跳过 |

没有修改后端代码、评测数据、Golden 保存内容、门槛、Judge 原文、Agent 推理原文或 SPEC。来源：本次 `git diff`、下列只读浏览器与数据保护检查。

## 验证记录

### 前端和构建

- 新回归测试先记录 5 条失败，再实现到 5 条通过；验证版本编号、当前使用和选中版本分离、四项操作的位置及导出绑定、禁用原因、主题数真实读取、两行 Gate 标签。来源：`output/task027c2/red.txt`、`green-first.txt`。
- 相关测试首轮发现一条旧断言仍要求 Gate 1 下行是“20/20”，已按任务单更新为“人工审核”，原完成状态断言保留。来源：`related.txt`、`frontend/src/governance-ui.test.tsx`。
- 前端全量：`npm --prefix frontend test -- --maxWorkers=2 --minWorkers=2`，109 个测试文件、647 条通过，0 失败；首次全量 55.16 秒，最后样式调整后的复验 56.34 秒。来源：`output/task027c2/frontend-full.txt`、`frontend-final.txt`。仍有原有 React 测试环境警告，未当作浏览器脚本错误。
- 最终构建：`npm --prefix frontend run build`，TypeScript 与 Vite 通过。来源：`output/task027c2/build-final.txt`。

### 后端全量

本次运行 `python3 output/task027c2/run_backend.py`，1459 项，0 失败、0 错误，21 项跳过，耗时 569.564 秒。与 027d 的后端结果逐项比较，跳过名称和原因完全一致。来源：`output/task027c2/backend-full.txt`、`backend-full.json`、`final-verification.json`。运行器复用 027d 已验证的方式：自动清理的临时数据库、索引、文档、上传和诊断目录，空 env，强制 Mock，并阻断外网 socket。没有复制正式数据库，也没有付费模型调用。

### 浏览器与截图

- 专项脚本 `output/task027c2/browser_acceptance.py` 只允许本机 GET/HEAD/OPTIONS。最终 11 项检查通过；脚本错误、控制台错误、HTTP 错误、被阻断写入或外网请求均为 0。来源：`browser.txt`、`browser.json`。
- 当前测试集首屏正文高度 / 可用高度为 **739 / 739px**，外层不滚动；首步是“9 个主题”，Gate 1 两行高度分别为 17.25px / 18.75px，与其他节点的结构对齐。来源：`browser.json`。
- 抽屉已检查 5 个版本的显示、编号悬停提示、当前标签与选择分离；逐一切换版本并核对三种格式导出链接，最后核对查看审计请求绑定所选工作集。无全局或抽屉横向溢出，抽屉内没有额外嵌套滚动区。来源：`browser.json`。
- 目视验收发现现有 `accent` 徽章样式实际为灰色，小号操作类也被基础按钮样式覆盖。先用浏览器断言记录不符，再加本抽屉的局部样式。最终当前标签颜色为 `rgb(0, 113, 227)`，底色为 `rgb(234, 243, 254)`；四按钮均为 28px 高、12px 字号、4px/8px 内边距。来源：`browser-blue-red.txt`、最终 `browser.json`。
- 初次抽屉验收曾因定位器失效中断，重启临时浏览器后完整专项通过；没有以中断那轮当作通过证据。来源：早期命令输出与最终 `browser.txt`。
- 复用 027a 的 `scripts/check_viewport_fit.py` 读取主链路共 17 个页面/页签，0 脚本错误、0 被阻断请求、0 全局横向溢出；每个视口蓝色主按钮不超过 1 个。Pipeline 配置为 790/790px，Golden 当前测试集与候选池均为 739/739px。来源：`output/task027c2/fit-check.json`、`fit.txt`。
- 已保存并目视复核两张 **1440×900** 截图，只存本机，不提交：`output/task027c2/01-golden-first-screen.png`、`output/task027c2/02-history-versions.png`。

### 数据与运行边界

- 本单未发送实时问答，未新增反馈、评测、质量检查、冻结、发布或回滚记录。真实 DeepSeek / Embedding / Rerank 调用次数均为 **0**；Mock 测试不作为真实模型证据。
- 正式数据库及已有审计备份在本次改代码前后采样的 SHA-256 一致；最终检查结果见 `output/task027c2/final-verification.json`。起始采样见 `data-before.json`。此项只证明本次采样间文件未变。
- 没有使用 Git 写命令；没有修改 `指挥/当前任务.md`。截图、数据库、日志和测试运行器只放本机 `output/task027c2/`，不作为公开提交内容。

## 待回答问题

无。主题数回退口径和版本编号口径已在“我是这样理解的”说明。

## 完成状态

本单要求已完成，无剩余工作。`git diff --check` 通过；原 demo 的 PID 816、827 保持运行，本次测试程序和临时浏览器已结束。来源：`output/task027c2/final-verification.json` 和各测试进程的正常退出结果。

任务单归档位置为 `指挥/历史任务/027c2-Golden历史版本与流程标签.md`，通过普通 `mv` 移动；保存和推送由值班脚本负责。
