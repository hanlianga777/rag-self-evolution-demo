# Baseline证据诊断与Agent准入修复验收

日期：2026-10-21。基础提交 `a32e6730fce36eb07b73b1872fd85c92f064e270`。本轮只改变诊断解释、合法干预验证和必要的业务列表展示；Provider调用为0，没有Baseline、Q18恢复、Agent或Sandbox执行。

## 共同根因与改动

1. 过去非空Final support即推Generation，未证明复合必要规范完整覆盖。现在真实定位与完整覆盖分开，部分引用输出明确gap；只有完整必要规范才支持该路径。Q08完整规范位于被Top4排除的候选，独立/原Judge的其他失败项足以确认Ranking。
2. 可选诊断字段缺失与scope=false不能当不存在证据，也不能改写。原路径保留missing、错误引用和原scope字段；独立审计记录验证后可提供另一条规范/阶段证据来源。五道Unknown没有被改字段或改分。
3. 主因不再取findings[0]。来源绑定确定性Guard确认违规优先；其余按必要规范最早缺失的Retrieval→Ranking阶段，再考虑Safety/Generation，Performance只用原实测条件。critical严重性不再单独产生Safety。
4. Ranking干预枚举现有16种TopK/Rerank/min_score组合，复用保存排序与完整Parent选择。方案必须恢复所有已证明缺失规范，并保留原Judge已满足的事实支持；删除无必要额外参数。validate_intervention复核实际diff，不只相信Agent的自然语言。Q03关闭rerank且Top6是必要联动，不能只补入口而丢后续步骤。Q27没有可恢复组合，保持Ranking但不准入该工具箱，不扩Search Space、不强制生成Candidate。
5. 原Judge诊断回退同样核来源文档/产品/版本，拒绝跨产品同文支持；保存正文中的适用完整规范可反证空阶段声明，但字符串缺失不能证明语义缺失。缺score或Parent等不能回放的情况与“已回放无策略”分别说明，均阻断上下文干预，保留已证实根因。独立只读评审发现的三项边界均先补失败回归再收紧，复核通过。
6. Baseline业务列表不再以技术准入过滤历史FAIL。列表显示业务结果、现象、方向；技术根因/阶段/独立规范和完整原记录保留在原Drawer。五类典型现象不变，技术异常独立提示。

## 独立证据的真实性边界

`backend/reports/diagnostic_evidence.json`转录两份已完成审计中的26项规范/阶段观察，涵盖10个实际保存Case。它不包含预期根因、分数、target_eligible或人工批准；不是按题号进入特殊代码分支。必要事实通过完整Golden参考答案片段、冻结证据引用的Child、Canonical原文和产品/版本校验。Q29使用完整419字Canonical表，原160字冻结摘要未改，也未向历史Judge补材料。

`diagnostic_evidence.saved_review()`通过只读SQLite查询验证实际Case、冻结Snapshot和审计文件SHA；`review_findings()`再校验同Corpus身份、完整Candidate/Rerank/Final摘要、规范来源、显式覆盖/等价证据审查、阶段实际引用及范围。原scope=false可以与独立“规范来源范围已核清”并存；purpose固定为normative_requirement_only，不代表未知现场可执行。来源错误仍拒绝，不按文本跨Chunk替换Q28错误引用。

等价证据/适用性语义来自原审计及其独立记录，不是程序仅由字符串缺失推断。源码只读验证与推导，不声称能为任意新Unknown自动完成语义核验。新Case、Snapshot、Corpus或阶段变化使旧记录不能复用；缺少同等审查时继续Unknown并列出具体缺口。原始Judge路径仍可处理自己已闭合的有效证据。部分引用不能充当完整事实，即使记录声称complete也要拒绝；同ID与不同ID的实际原文都核查。

这些记录随源码提交，原审计报告随同提交供哈希溯源。没有新增数据库表、写API、第二Judge、第二Agent或人工Gate。诊断记录受版本控制的审查与原三个人工业务Gate不是同一件事。

## 10题只读诊断及局部可干预性

| 题目 | 主要根因 | 可用方向/保存Trace证明 | 原Judge缺口仍保存 |
|---|---|---|---|
| Q03 | Ranking | rerank=false与top_k=6联动 | 无新增猜测 |
| Q04 | Ranking | top_k=6加入室内/重量规范 | 不套B2存储条款 |
| Q06 | Ranking | top_k=6加入电池隔离和湿手禁令 | Safety标签不替代阶段根因 |
| Q07 | Retrieval | 候选召回/查询扩展可提出可证伪假设，未验证新检索效果 | 原candidate_support缺失 |
| Q08 | Ranking | top_k=6加入充电板完整保养规范 | 原Final仅部分支持，不能归完整Generation |
| Q17 | Retrieval | 召回B2手册R3分支规范；未知现场型号仍需分支确认 | 原scope=false保留 |
| Q24 | Retrieval | 召回孩童/稀释/急救规范 | 原candidate_support缺失 |
| Q27 | Ranking | 无现有可恢复组合，target_eligible=false | 已定位根因不等于有工具策略 |
| Q28 | Retrieval | 召回维护总则 | 错绑C00026的C00181引用严格拒绝；独立事实不修原引用 |
| Q29 | Retrieval | 召回完整B2不带电检查表 | 160字历史输入/缺诊断字段/scope=false保留 |

9题有局部合法干预方向，Q27保留业务FAIL与Ranking但不给现工具箱目标。Retrieval的candidate_k=24/查询扩展只是有来源的优化假设，本轮未执行，不能承诺改善。全轮仍Partial，不能据此调用正式Agent；原完整Baseline/同身份/人工授权守卫均保持。

## 历史成绩、身份和Q18

- 原49个完成Case、39个PASS、10个业务FAIL的原JSON/回答/分数不变；Q18没有case/bad_case，也未从原始PASS输出补分。
- Judge Prompt、正式Parser/Matcher、Scorer、Provider输入、Generation Boundary、Gate定义、Search Space源码未改。Identity仍 `d18aab6365a63c6de63e295866a7036e0fe6a25f1f74c2afbb4782bbab73ae3e`。
- 原数据库及知识制品/原文前后SHA相同，所有表行内容摘要相同；Frozen Golden仍 `GD-20261015135415953347`，Corpus仍 `CORPUS-38c90d5628b68c76d53e`。
- Q18两份保存响应继续在现Parser复现 `support is not located in actual full Final`。真实标题在source_scope，不在绑定校准/安装正文；本轮未改变该合同。
- 使用保存配置的共享start/resume只读守卫仍通过，可在以后明确授权并重新实时预检后，按原身份新建恢复子Run，仅补Q18 Judge，复用49个成功Case和已有generation execution。相同标题引用错误可能再次发生；本轮没有恢复，不能保证以后成功。

## 源码定位

- `backend/app/diagnostics.py:304`：business_analysis；原输出严格校验、Canonical各阶段、gap、覆盖判断及主因选择。
- `backend/app/diagnostic_evidence.py:25`：saved_review；不可变Case/Snapshot/审计溯源。
- `backend/app/diagnostic_evidence.py:50`：review_findings；逐事实来源、范围、覆盖与阶段证据校验。
- `backend/app/diagnostic_evidence.py:123`：context_selection_options；保存Trace上的合法组合演算，非真实Rerank调用。
- `backend/app/optimization.py:26`：validate_intervention；逐目标准入、方向与可恢复diff。
- `frontend/src/components/EvaluationDiagnosis.tsx`、`frontend/src/pages/EvaluationPage.tsx`：业务FAIL保留与既有Drawer技术证据。
- `scripts/verify_baseline_diagnostics.py`：原10题只读回归、49个Case不变、Q18仍异常、同身份恢复守卫与禁Provider检查。

## 验证

最终结果见下节。首次全量运行发现既有Safety Guard模拟Negative检查缺check_type，按当前合同补显式negative_behavior，仅修改测试夹具；未放宽Parser。旧200条验证脚本对Q27的可优化期望同步为“Ranking但工具箱不可达”，其157P/43F判定不改。前端旧测试随本轮明确列表合同更新，费用预览夹具补既有preflight与当前按钮文案，POST禁调用断言保持。

正式服务未重启，未触发生产数据库初始化/自动恢复；源码、隔离接口测试与构建验证不冒充正在运行的旧进程已重新加载。

## 最终验收证据

- 最终全量后端784项通过（0 failure / 0 error，393.839秒）。前次全量出现既有Candidate API测试后台线程与临时目录清理竞态：`test_existing_candidate_api_resumes_after_explicit_request`在tearDown删除目录时失败；无产品代码改动地复跑全量通过，保留该测试稳定性限制。
- 相关后端141项通过，包含本轮覆盖/范围/阶段矛盾/准入边界回归；独立评审发现的三项问题均已红后绿并复核。
- 前端44个测试文件、248项通过；`npm run build`（TypeScript与Vite）通过。
- 旧200条结构化离线响应回归通过：157 PASS / 43 FAIL，Provider 0；这些仍是离线夹具，不冒充真实Judge新评测。
- 真实保存10 FAIL只读复核通过：5 Ranking / 5 Retrieval，9个局部可干预目标，Q27阻断；49个成绩原样、Q18仍异常、原Identity及同身份resume守卫通过。
- [真实10题验证JSON](../outputs/medium50_baseline_diagnostic_fix_20261021/verification.json)；[23个受保护文件SHA与数据库完整性](../outputs/medium50_baseline_diagnostic_fix_20261021/integrity.json)。完整数据库逐字节SHA相同，因此其中所有表、Frozen Snapshot、历史Case/原始Judge JSON均不变。
- 新代码与文档diff检查通过；原审计A中原始回答的Markdown双空格/表格尾空格原样保留，未为格式检查改写历史证据。
- 工作区原有存储审计文件及`verify_self_evolution.py`等用户改动未纳入本轮提交。全量验证使用该既有隔离脚本，空env、Mock及网络禁调用生效。
