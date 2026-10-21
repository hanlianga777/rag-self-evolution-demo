# V5.1 正式评测前收口：离线验收及待授权探针

日期：2026-10-21。实施基线：`4bad9eaab96885eb4e68b0b2e264d0df21a4844a`。本轮第一步，仅离线代码、保存数据只读核验和临时副本 Mock；真实 Provider 调用 **0**。未启动真实 Q18、正式 Replay、Baseline、Agent 或 Sandbox；正式服务未重启，磁盘源码/隔离测试不代表已有服务进程加载新版。

## 1. 合同与身份

在通用 Validator 的必要检查总体验证处收口：Positive/Ablation 至少有一项必要 `fact`；Negative 至少有必要 `fact` 或 `negative_behavior`。Scope-only（包括只有 Scope/辅助范围项的组合）不能形成合法业务判分，保留为技术异常；不删除 checks、不重写 verdict、不放宽正文引用。

合法 Scope 仍可证明单个真实标题、型号和章节适用范围；操作、参数、安全前提仍需真实适用 Final 正文的 Fact 支持。Scope+真实 Fact 合法；Scope+met=false Fact 必须 FAIL，Scope+伪造 Fact/跨型号/跨产品/跨版本引用仍拒绝。Parser 不能保证 Judge 穷尽所有必要事实或语义判断正确，业务复核继续独立。

- 新 Parser：`business-output-5.1-substantive-checks`。
- 新 Evaluation Identity：`4c6e8a2da0f2e23deb6200551dc79f9894370ef01b15d4c914b1e78a1a66dccf`。
- Judge Prompt、Matcher、Scorer Policy、有限 Safety Guard、Generation 合同保持 V5 原值，Identity 因正式 Parser 合同升级而变化。
- 原 V5：`e7ff2e15737521518b0104dcf3d253a9726d7809fa77947f6325804e88f8119c`；原 V4：`d18aab6365a63c6de63e295866a7036e0fe6a25f1f74c2afbb4782bbab73ae3e`。均不冒充新版，不回填旧成绩。

## 2. Q18 独立探针

最小 CLI，无新页面或工作台。限定冻结问题 `V1G-110926448917-18`，复用源 Run `EVAL-20261021013401711966` 的已保存真实回答、Candidate/Rerank/Final。完整 50/50 复用资格先核验；实际只调用该题 Judge，禁止生成。

正式路径与探针共用 `judge_context()`、`business_judge_input()`、`score_execution()`、真实 Provider Parser/完整 Validator，沿用 model、temperature=0、JSON mode、max_tokens=32768、加载的 timeout。原 Baseline 阶段重试循环提取为共享 `perform_stage()`，不改变规则：最多三次尝试、600秒、合同无效最多纠正一次并携带原始输出/错误。

独立记录在数据库同级 `judge_probes/`，可用 `RAG_JUDGE_PROBE_DIR` 隔离，默认真实产物目录已加入 Git ignore。授权编号经摘要作为独占文件名，同编号不重入、不自动续跑。记录绑定新 Identity、源 Run 摘要、冻结 Q18、execution/三阶段、完整 Canonical 输入、实际 Judge 配置/请求摘要、原始响应、引用定位、业务结果、Usage 和费用。只读 SQLite 连接，不初始化/迁移正式库。

每次请求前重复资格/配置核验；实际已实例化 Provider 配置必须与预检一致，拒绝进程加载旧 endpoint/timeout。Unknown、在途未结算或费用/身份错误立即停止；已结算且符合原重试规则的可恢复响应才可继续，并记录停止标记的有限恢复依据。真实 Provider 的 length 截断路径已用假 HTTP 覆盖。

运行完成仅 `judge_complete`，**不自动认定业务验证通过**。人工复核必须记录 actor、决定及事实、安全、Scope/Fact 分离的证据说明。审批摘要包含题目/输入、原始判分、尝试记录及账本；读回重核冻结题目、Canonical 引用、原始响应及每次实际请求摘要。Mock、篡改、未知费用、身份变更、未复核或拒绝结果不解锁。正确的业务 FAIL 判定也可以经过复核，不要求为解锁而制造 PASS。

人工复核至少逐条检查：Golden 校准/安装要求是否完整；R1 与 R3 的规范分支和现场型号边界；必要操作/安全前提的 Fact 正文引用；Scope 标题只解释适用范围；整段答案中的冲突、遗漏和业务 verdict 是否合理。仅有 Parser 通过或合法标题引用不满足这一复核。

## 3. 探针与正式 Replay 权限隔离

只读预检仍返回 `can_replay` 表示生成数据可复用，新增 `can_start_replay` 表示探针门禁也满足。当前 **50/50 可复用，但 can_start_replay=false**，因为本轮没有真实探针或人工批准。

门禁在后端 Replay start、创建事务、执行以及同身份恢复创建/执行处复核；前端原按钮同步禁用并说明原因。探针结果不插入 evaluation_case_results，不写正式 Baseline 分数，不创建 50 题 Completed。通过探针后仍须独立授权正式 50 题；探针 run/review 不会调用 Replay。

架构沿既有 Baseline Evaluation 内部增加执行前守卫；业务链、节点/连线、原 Drawer、五类 Bad Case 和唯一 Optimization Agent 保持。本轮未修改 Evidence Resolver 架构、参数空间或 11 Gate。

## 4. 启动方式（真实执行尚未授权）

只读预检，可以立即使用：

```bash
python3 scripts/q18_judge_probe.py preflight
```

获得 Owner **本轮第二步的新授权后**，再次核官方价格、当前身份/加载配置和全50资格；超过24小时的价格快照会被拒绝。以下仅为授权后操作示例，本轮没有执行：

```bash
python3 scripts/q18_judge_probe.py run \
  --expected-binding BINDING_FROM_FRESH_PREFLIGHT \
  --authorization-id UNIQUE_OWNER_AUTHORIZATION_ID \
  --authorize-provider --budget-usd 0.50 \
  --price-snapshot backend/config/q18-probe-prices-20261021.json
```

单次授权最多3次 Judge；结构错误最多1次纠正仍占额度；Unknown 停止且不盲目重发。同编号重试命令也被拒绝，新的授权不得从旧授权自行推定。

只有 Owner 实际审阅结果并明确批准后，才可用 `review` 写独立复核记录：

```bash
python3 scripts/q18_judge_probe.py review --artifact ACTUAL_PROBE_PATH \
  --actor ACTUAL_REVIEWER --decision approved \
  --facts '逐项必要事实及原文判断依据' \
  --safety '必要安全前提与整答冲突核查依据' \
  --scope-separation 'R1/R3适用范围与Fact正文分离的核查依据'
```

此处文字须来自真实审阅，不能照抄占位说明当作批准。review 不调用 Provider、不启动50题。若业务复核不通过，使用 rejected 并保留原始结果。新的正式50题仍使用既有费用确认，另行授权。

## 5. 费用预检与停止规则

2026-10-21 08:56:04 UTC 核查 [DeepSeek 官方价格](https://api-docs.deepseek.com/quick_start/pricing/)：Flash 每百万输入 cache-miss **USD 0.15/0.30**、输出 **USD 0.60/1.20**（低峰/高峰）；保守按高峰 cache-miss 0.30/1.20 预算。独立价格快照见 `backend/config/q18-probe-prices-20261021.json`，不覆盖原价格配置。

官方说明旧 `deepseek-v4-flash` 别名现由 **DeepSeek-V4.1-Flash-1017** 服务并按 Flash 计费。请求模型字符串及历史 generation 身份没有自动改写；远端别名实际服务修订变化仍是需在真实响应/授权中核实的风险，不能据旧字符串保证服务端权重完全相同。

- 单次 Q18 首轮输入约 **11,724 tokens**，为既有字符比例估算，非精确 tokenizer；输出预估1,000–6,000 tokens。
- 单次普通区间约 **USD 0.00472–0.01072**；纠正反馈会增加后续输入。
- 每次输出上限 **32,768**；首轮完整请求88,462字节，按既有 UTF-8 字节+1,024 framing 的保守输入界及输出上限预留约 **USD 0.06617**。
- 建议本次 Q18 单独授权硬预算上限 **USD 0.50**，最多3次；每次按实际完整请求/纠正反馈字节与剩余预算重新预留，不承诺任意反馈下预算足够完成3次。超预算、600秒、两次非法响应、身份/配置漂移或 Unknown 都停止。
- 复用既有 PaidRun 硬预算和原始响应存取；其 legacy `_yuan` 字段在本独立账本中数值单位明确为 USD，记录同时保存 `budget_currency=USD` 与单价 currency，未推算人民币汇率，也不声称是账户实际扣款。

真实调用信息以预检输出、最终用户授权和独立账本为准。本轮费用为0；上述预算尚未获真实执行授权。

## 6. 离线核验与历史保护

- [逐题 Replay 资格](../outputs/v51_preflight_closeout_20261021/replay_preflight.json)：50/50；49份保存生成记录+Q18 checkpoint，生成0。临时副本 Mock 50 Judge 完成、原11 Gate 聚合与 require_current_baseline 通过；测试明确临时替换探针门禁，不保存假真实探针或人工批准，不能用此文件解锁生产门禁。
- [探针假HTTP验收](../outputs/v51_preflight_closeout_20261021/probe_offline.json)：实际保存Q18、隔离DB/Corpus/环境、真实 Parser/Validator、纠正/Unknown/已结算截断、单授权重入、未批准/Mock/篡改/旧价格/旧加载配置及 start/transaction 拒绝。全部只作程序机制证明，不证明真实 Judge 业务质量。
- [旧10题诊断](../outputs/v51_preflight_closeout_20261021/historical_fail_diagnostics.json)：原49成绩保持39 PASS/10 FAIL，Q18仍原技术异常。五道 Retrieval 与五道 Ranking 不变，Q08仍Ranking、Q27保留工具箱边界。
- [旧200条离线响应回归](../outputs/v51_preflight_closeout_20261021/historical_200_offline.json)：157 PASS/43 FAIL，不冒充新真实 Judge 结果。
- [完整性校验](../outputs/v51_preflight_closeout_20261021/integrity.json)：25个保护文件逐字节相同，包括完整正式数据库、原PDF/索引、policy.py（Gate/参数域）、evidence_resolver.py、旧审计证据。数据库SHA仍 `983488ce11505c8d1e8e94677a6619a8b48f0bed23ecf57cccc869f0629d0e46`。旧Golden、原Judge/Checkpoint及历史分数未改。
- 后端823项（369.683秒，0 failure / 0 error）、前端44文件251项及TypeScript/Vite构建通过；完整统计见同目录 verification.json；新 Parser 身份测试、Scope反例和探针机制独立验证。独立代码审查发现并修正冻结题目绑定及已结算截断重试两处问题，复核确认解决。

## 7. 可核验源码

- `backend/app/evaluation_contract.py:351 validate_business_judgment`、`:403` 实质检查；`:475 business_judge_input` 共享正式输入；`:10` Parser版本。
- `backend/app/q18_probe.py:24 probe_binding`、`:32 probe_preflight`、`:54 validate_artifact`、`:106 require_reviewed_probe`、`:118 run_probe`、`:165 review_probe`。
- `backend/app/evaluation_stage.py:7 perform_stage`、`:78 correction_for`：原有限重试与错误反馈，共用逻辑。
- `backend/app/evaluation.py:235 judge_context`、`:248 score_execution`、`:368 judge_replay_preflight`、`:388 start_judge_replay`、`:431 execute_baseline`：正式输入/评分及门禁。
- `backend/app/governance.py:2003 create_baseline_run`：事务及恢复门禁；`backend/app/providers.py:233 _judge_business`：真实 Parser 路径。
- `scripts/q18_judge_probe.py`：只读库 CLI；`scripts/verify_q18_probe_offline.py`：真实Provider方法+假HTTP反例；`frontend/src/pages/EvaluationPage.tsx:136/167`：只读预检与原按钮保护。

第一步结束后停止；待Owner看完报告并明确授权，才执行真实Q18。真实Q18业务复核通过后，正式50题仍另行授权。
