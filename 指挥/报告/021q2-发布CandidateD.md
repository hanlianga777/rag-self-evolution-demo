# 021q2 发布 Candidate D 报告

执行日期：2026-11-08（America/Toronto）。

## 结论

已按任务单授权，通过正式 demo 发布页完成一次发布，返回 HTTP 201。当前线上版本为 Candidate D，版本号 `production-20261108080831`，Candidate K 24、Top-K 6、Thinking High。原初始配置已归档，有回滚入口；没有点击回滚。

模型调用 0 次，评测启动 0 次，实时提问 0 次，发布请求 1 次，回滚 0 次。没有修改产品代码、SPEC 或 `指挥/当前任务.md`，没有执行 Git 写命令。正式 demo 保持运行，操作浏览器已关闭。保存和推送由值班脚本负责。

来源：本机发布响应 `output/playwright/021q2-20261108/final-browser-audit.txt`；正式库 `production_versions`、`approvals`；本机 `verification.json` 和前后逐表哈希。

## 执行口径与已有进度

先读根目录 `AGENTS.md`、`指挥/README.md`，再读指定任务单。开始时只读 `git status --short` 无变更，最近提交 `e5e8ca9` 是开始本任务的值班记录；021q 已由 `4d1545f` 完成，随后值班记录为 `e14542e`。本任务报告此前不存在；正式库只有一个初始版本，没有已做过的发布需要续接。没有重做 021o/021q，也没有重跑历史付费题。

我是这样理解的：

- 任务单“demo 保持运行”优先于通用收尾关闭服务要求；保留原 5174 和 8010，仅关闭本次操作浏览器。
- “只点一次”指实际发布只提交一次。按产品流程先点击“确认发布”打开窗口，再在窗口点击一次“确认”；实际只有一个发布 POST。
- 确认窗口没有操作人输入框，不要求填写 actor；没有改写请求或数据库补填。前端实际发送 `{"decision":"approved"}`，后端按既有默认值保存 actor=`local_user`。本次代点授权及执行人身份记录在本报告和任务单中。
- 日常浏览器没有开启远程调试，改用独立 Playwright 浏览器访问同一正式本机 demo；没有另起前后端。

来源：任务单、只读 Git 记录、发布确认窗口、`frontend/src/pages/VersionsPage.tsx`、`backend/app/main.py:ReviewRequest`、浏览器请求记录。

## 前置条件逐条核对

| 前置条件 | 核对结果与来源 |
| --- | --- |
| 1. 021o 完成，展示过滤生效，8010 已重启 | 满足。`指挥/报告/021o-发布前收尾与彩排.md` 记录相关过滤与重启；后续 021q 报告记录再次重启为 PID 15862。本次确认该进程监听 8010，启动于 2026-11-08 02:58:51（Toronto），晚于 `main.py` 和 `read_view.py` 修改时间。发布前实时版本、概览、Pipeline、推荐返回不含任务禁止展示的信息，D 的当前回归重算为通过。 |
| 2. 021q 完成，D 与第 3 轮 C 合格，其余不合格，仍推荐 D | 满足。`指挥/报告/021q-回归检查审计.md` 明确最终资格不变；任务单已在历史任务目录。实时 `/api/optimization?light=true&planning=true` 的 10 个方案中，只有 `EXP-20261105143048349606-R3-C`、`EXP-20261105143048349606-D` 的 `result.release_qualification.qualified=true`。 |
| 3. 当前推荐指定 D | 满足。实时推荐的 `candidate_id=EXP-20261105143048349606-D`，状态 Recommended；D 的发布状态 sandbox、qualified、recommended、round_complete 均为 true，human_release 为 false。 |
| 4. 当前无活动评测 | 满足。正式库只读查询 `evaluation_runs`、`candidate_configs` 的 queued/running 均为空；正确活动评测接口 `/api/evaluations?active_only=true` 返回空数组。 |
| 5. 线上仍为初始配置，D 从未发布 | 满足。发布前 `/api/versions` 和正式库只有 `runtime-initial-20261014030238448891` 一条 active、bootstrap 版本，无 D 发布记录；发布页显示初始配置及 D 尚未发布。 |

上述五项全部满足后才提交发布。实时留底：本机 `before-api.json`、`before-db.json`、`active-api.json`。开始时曾探测不存在的 `/api/evaluation-runs`，收到 404；随后按代码确认正确路径 `/api/evaluations`，以正确接口及正式库查询交叉核对，不把 404 当作无活动评测的证据。

## 发布时间与版本

- 候选：`EXP-20261105143048349606-D`。
- 新版本：`production-20261108080831`。
- 数据库发布时间：`2026-11-08T08:08:31.441619+00:00`（UTC）。
- Toronto 时间：2026-11-08 03:08:31；北京时间：2026-11-08 16:08:31。
- 发布页按北京时间显示 `2026/11/08 16:08`；实时问答按浏览器本地时间显示 `2026/11/8 03:08:31`，指向同一发布时间。
- 发布请求：POST `/api/candidates/EXP-20261105143048349606-D/publish`，返回 HTTP 201；只发生一次，无重试。
- 前一版本：`runtime-initial-20261014030238448891`，由 active 变为 archived；新版本 `previous_version_id` 指向它。

来源：浏览器发布响应、正式版本 API、正式库 `production_versions`。

## 发布后核对

| 页面 | 实测结果 |
| --- | --- |
| 发布 | 显示“已发布方案”“最终推荐方案已发布”，当前配置来源为方案 D。完整配置抽屉确认 CandidateK 24、TopK 6、Thinking High；页面参数变化为 12→24、4→6、最高→高。历史中初始配置已归档，有“回滚至此版本”按钮，仅查看未点击。 |
| 概览 | 发布节点变为“当前推荐已发布”。答对数仍为 44/50→48/50，P99 仍为 42.2→36.7 秒，安全拒答率仍为 95%→100%，Agent 仍为 3 轮、10 个方案。 |
| 问答验证 → 实时问答 | 显示“线上版本：方案 D · 发布于 2026/11/8 03:08:31”。未填写问题、未点击推荐问题或发送。 |
| Agent → 最终推荐 | 仍推荐方案 D，成绩相同，人工报告确认已完成；入口改为“查看发布记录”，正文没有“待发布”“尚未发布”。 |

未发现需要修正的已发布/待发布措辞矛盾，本次没有代码改动。发布页正文及已展开技术详情的完整配置抽屉没有 `internal_trial`、`_evaluation_audit`、`internal.db` 或被替换运行编号。对正式库候选审计字段读取到的被替换编号进行交叉检查；版本、概览、Pipeline、推荐的实时 JSON（包含原始 JSON 字符串）也未出现这些内容。原始审计仍留在数据库，没有删除。

额外只读核对：Pipeline 的 `active_version_id` 和 config 与新版本完全一致；概览的 production 指向新版本；推荐内容、Baseline 保存结果和全部 10 个候选的 result 在发布前后逐字段相同。

来源：四页实际 DOM/截图、`release-dom.txt`、`browser-audit.txt`、`final-browser-audit.txt`、`after-api.json`、`verification.json`。浏览器监控在实际发布前安装，仅放行第一个 D 发布请求，其余 API 写请求拦截；实际 blocked 为空，发布后未发生其他写请求。最终浏览器 pageerror 和控制台 error 均为 0。

## 本机截图

完整本机目录：`/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/output/playwright/021q2-20261108/`。

| 页面/内容 | 文件 |
| --- | --- |
| 发布页 | `01-release.png` |
| 概览 | `02-overview.png` |
| 实时问答 | `03-live-qa.png` |
| Agent 最终推荐 | `04-agent-recommendation.png` |
| 补充：原初始配置及回滚入口 | `01b-version-history.png` |
| 补充：已发布完整配置和快照 | `01c-published-config.png` |
| 补充：Agent 查看发布记录入口 | `04b-agent-release-record.png` |

7 张均检查尺寸为 1440×900，四张主页截图已实际查看。`git check-ignore` 确认截图由现有 output 忽略规则排除，只在本机，不上传。

## 数据与运行验证

正式库一直以 SQLite `mode=ro`、`PRAGMA query_only=ON` 查询，前后采集各使用同一读事务；发布写入仅由真实产品接口完成，没有直接修改数据库，没有复制正式库。

逐表按列顺序序列化每行，计算 SHA-256，再对排序后的行哈希列表计算表哈希。33 张表比较结果：

- `approvals`：225→226，仅新增本次发布审批。
- `production_versions`：1→2，新增 D 版本并归档初始版本。
- 其余 31 张表的行数和内容哈希全部不变，包含 `tool_calls`、`evaluation_runs`、`evaluation_case_results`、`candidate_configs`、`experiments`、`recommendations`、`questions`、`dataset_versions`。
- 发布后无 queued/running 评测。没有新增模型调用记录、评测或问答记录；成绩数据未修改。

本机可复核脚本和证据：`verify.py`、`before-hashes.json`、`after-hashes.json`、`verification.json`。脚本已完成断言：唯一 active 版本为指定 D、参数正确、旧版本已归档、接口过滤有效、成绩推荐不变、变更仅限两表、截图尺寸正确。

本次没有产品代码变更，因此未运行单元测试或构建；也没有以验证名义运行模型、评测或付费问答。正式 5174 仍为原 PID 1117、8010 仍为原 PID 15862；没有重启它们。Playwright `021q2` 会话已关闭，未留下本次启动的 demo 服务。

## 待回答问题

无。本任务全部完成，没有跳过项。按自动值班规则，用普通 `mv` 将本任务单移至 `指挥/历史任务/021q2-发布CandidateD.md`。No SPEC Change。
