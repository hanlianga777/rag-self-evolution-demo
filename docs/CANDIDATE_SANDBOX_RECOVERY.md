# Candidate Sandbox 断点恢复验收（2026-10-12）

## 结论

修复并离线验收后，具备人工启动本轮 A/B/C Sandbox 的技术条件。未执行真实 Provider 或 Sandbox；不声称真实网络稳定性已验证。

只读确认：正式 Baseline `EVAL-20261012024220100135` completed，50题已保存；实验 `EXP-20261012054110446321` 的 R1-A、R1-B、R1-C 均为 generated，预算0/12。规则仍为 judge-v3.1-claims / evidence-v3-scoped / v1.2.1-claim-consistency。

## 缺口与最小修复

1. 原 Candidate 已复用 Baseline 执行器保存逐题结果和生成答案/完整Trace，但再次启动新建空Run，重复已完成调用。现在复用 Baseline 的同身份子Run创建和检查点恢复逻辑，完成题直接复制并跳过；生成完成、Judge失败的题只补Judge。原Run及其逐题记录不改写。
2. 原预约与Run创建分离，重启前可能缺少Candidate→Run关联。现在预约、预算与身份重验、子Run及关联在同一SQLite事务中完成；拒绝整体回滚，不扣额度。重启仅终止状态，不清除检查点。
3. 原批量队列遇到非重启的Provider失败仍继续。现在任何未完整结束的单项均暂停后续Candidate；完整完成但资格不通过可继续。再次点击批量按钮仅启动generated项，failed不自动重试；失败项须单独点击“继续Sandbox”并确认费用。只改行为与必要提示，无视觉改动。

## 状态、预算与身份保护

- Generation/Judge超时或SSLEOFError：保存已有题目和可用答案，记录实际阶段、异常类型/原因与已采集Usage；单题执行错误不伪装Bad Case。Run为partial/failed，Candidate为failed，无发布资格。
- 再次授权启动另占一次额度；首次失败不退款，旧failed缺少attempt列表时保留原已消耗额度。上限12、A/B/C为D保留1次不变。
- 当前Baseline/Experiment、Golden完整Snapshot、Corpus、完整Judge及Evaluation Identity、Candidate配置须一致；活动评测、重复预约、预算不足、Gate2冻结均阻断。每次续跑新建子Run并保留原Candidate身份及历史Run。
- 只保证跳过**已持久化**的成功步骤。若进程在Provider返回与检查点落库之间退出，或请求结果不确定，无法证明外部调用是否成功/收费；inflight记录保留，不自动重试，人工再次启动仍可能产生该未保存步骤的费用。未返回Usage不能当零成本。
- 沿用既有API：`POST /api/candidates/{candidate_id}/run`。这是授权后的显式启动入口，不是后台自动恢复；刷新不续跑，不启动下一轮或Agent。

## 离线验收

导入app前隔离SQLite、Corpus、索引、uploads及.env；使用Stub，拦截真实urllib调用。复现测试在修复前确实失败。

- Generation/Judge分别覆盖ProviderTimeout与SSLEOFError，失败只调用一次，保留完成题；恢复跳过完成题，Judge恢复不重新生成答案。
- 校验原Run不变、重启保存Run关联、API显式续跑、预算增量、旧失败不退款、配置/Golden/Judge/Corpus不一致拒绝、重复预约拒绝。
- 前端验证Provider失败暂停、重复点击不重复启动、再次人工点击跳过failed、完整不合格项继续、身份/Gate2/预算阻断，以及单项续跑先费用确认。

最终验证：后端68项通过（Candidate恢复、Baseline恢复、既有E2E、API生命周期、身份、预算及Agent合同）；前端25项通过（批量Operation、Agent入口及共享状态）；TypeScript与生产Build通过；`git diff --check`通过。Fixture通过不替代真实Provider效果验收。

可复现命令：`python3 scripts/verify_self_evolution.py test_candidate_resume test_baseline_resume test_v11_e2e test_v14_api_lifecycle test_v14_identity test_v14_probe_cost test_optimization_contract`；前端目录执行 `npm test -- src/sandbox-batch.test.tsx src/agent-restoration.test.tsx src/operation.test.tsx` 和 `npm run build`。

## 真实环境与数据保护

修改前通过SQLite Backup API保存 `output/playwright/candidate-sandbox-recovery/protected.db`。前后摘要 `protection-before.json`、`protection-after.json` 覆盖29张表及31个Corpus/索引/报告资产文件，全部一致。本轮Candidate配置、实验身份、历史评测、Golden及Production未改动。

确认所有持久化活动任务为空后，仅替换8010工作进程（3242→6579），保留监督进程1592。启动日志确认索引最新、无需重建；只读workspace确认Baseline和Experiment身份不变。前端Vite加载行为补丁。Provider调用0，Sandbox启动0。

Judge、Evidence Matcher、Golden、Baseline成绩、Search Space、Agent策略、Hard Gate与Regression标准均未修改；不升级评测语义版本。唯一图源与组件边界/连线未变，无需重新导出图；同步架构说明文字。

保护备份与日志含真实材料，仅保存在忽略目录，不入Git。
