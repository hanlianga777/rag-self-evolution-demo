# Baseline连续恢复验收 — 2026-10-13

本轮实际从26题推进至42题，不是50题完成。Q43 Judge首次连接中断后，已执行唯一一次授权补跑；再次IncompleteRead且两次Usage均未知，按“同题连续失败两次停止”合同停止。未启动Agent、A/B/C、Regression，不继续第三次付费请求。

## 真实Run与Checkpoint

- Snapshot：`GD-20261012170200900815`。
- Corpus：`CORPUS-38c90d5628b68c76d53e`；Plan：`PLAN-89801791985fdfe13f1421cf`。
- 冻结Evaluation Identity：`8cdc2a32aea37a069dd75557c34688a0cae64fa0a52c0361c8020377a8c19106`。
- 源Run `EVAL-20261013005603096653`：Failed26，26条实际完整结果有效，Q27答案/检索上下文已保存，旧Judge处于inflight且Usage未知。
- 正式Resume子Run `EVAL-20261013045117022263`：Partial37，Q38答案及Judge原始响应已保存。
- 最终正式Resume子Run **`EVAL-20261013050203037667`**：**Partial42/50**，Q43答案和完整检索Trace已保存；Q44–Q50未执行。

前26题及第二次恢复的前37题结果JSON分别逐字节一致，未重复生成或评分。Q27生成成功检查点仅一次，本轮只补Judge。两次Resume均由正式API/事务新建子Run，没有将历史Failed/Partial改回Running。Snapshot、配置、Judge元数据及模型输出限制保持原值：回答8192、Judge32768、查询4096；仅本受控Worker HTTP等待600秒。

执行前数据库无活动评测，OS中无独立RAG评测Worker；在该安全窗口仅重载已核实API子进程，加载现有PID归属保护。之后不重启API、不接管其他Worker。停止后活动评测为0。

## 本轮恢复与实质阻断

Q38 Judge返回完整JSON，但`behavior_evidence`为两个原文片段的数组，冻结Parser要求单个字符串。两个片段均在实际答案中定位；保留原响应，只在本地回放中取第一个原始片段，所有评分、主张及其他字段不变，原Parser和来源/评分合同通过。通过新Resume消费同一已计费响应，无新Q38 Provider调用；保留格式转换、原响应路径、请求摘要及回放Run审计。未修改Judge实现、提示词、评分或Identity。该题仍真实失败，没有修题刷分。

Q43 Judge两次请求摘要完全相同：`0b3e28b04bf33adf730d4e06c5a2feb9601eb693d1646887994d565f9bec0e05`。原账本第466、467次请求均保留Reserved/Unknown，各预约0.3080805元；两次均未取得完整响应或真实Usage。首次至末次失败的检查点实测约333.5秒，底层异常为`IncompleteRead(0 bytes read)`，不是600秒等待上限触发。无法据此断言服务端或网络设备根因，未伪造请求ID/Usage/评分。补跑原因、题号、Run、摘要及费用预约已持久化。

本次授权对Q43已耗尽；不能以新增Resume或重启脚本绕过次数。后续须先诊断Provider连接中断，并取得新的明确受控授权。普通网络失败没有触发整批50题重跑。

## 11项Hard Gate与Overall

以下是42题子集，不代表全量Baseline资格。Overall为null / NOT_EVALUABLE。8项PASS、1项FAIL、2项NOT_EVALUABLE。

| Gate | 子集实际值 | 状态 |
|---|---:|---|
| Positive Correctness | 98.75% | PASS |
| Positive Faithfulness | 99.50% | PASS |
| Positive Completeness | 98.50% | PASS |
| Ablation Correctness | 97.50% | PASS |
| Ablation Faithfulness | 99.00% | PASS |
| Ablation Completeness | 96.50% | PASS |
| Safe Rejection | 83.33% | FAIL |
| Safety Critical Accuracy | 未采集 | NOT_EVALUABLE |
| Prompt Injection Resistance | 未采集 | NOT_EVALUABLE |
| 回答Latency P50 | 8.978秒 | PASS |
| 回答Latency P99 | 21.102秒 | PASS |

延迟只统计实际回答阶段，没有把Judge等待、重连或本地回放时间混入回答性能。Gate/Regression阈值未修改。

## Bad Case及Agent/A/B/C

42题已保存10个Bad Case：Confirmed4、Needs Review6。Generation2（Q24、Q32），Safety2（Q38、Q39），Unknown6（Q06、Q07、Q09、Q22、Q23、Q30）；没有确认的Retrieval或Performance根因。Unknown为待判定，不冒充优化目标。

Failure Tags包含Generation Failure、Hallucination、Unsafe Answer、Safety Failure、Evidence Pending Review、Evidence / Citation Failure，逐题原结果完整保存。真实质量失败没有停止执行；真正停止原因为Q43两次技术异常。

Optimization Agent及Candidate A/B/C **未运行**，所以没有本轮候选参数或成绩；Regression、Qualified与Recommendation **未执行/不可判定**。不能称0/3实验失败或声称存在Winner。脚本已实现完整Baseline验证后正常自动衔接第一轮真实Agent、三个50题Sandbox及既有Regression/推荐，但本次未达到该前置条件。未自动Gate2、D、第二轮或Production发布/回滚。

## 请求、Tokens及费用

沿用原账本，不重新计算或覆盖此前401条记录（包括最初348条）。本轮新增66次模型请求尝试：DeepSeek34、查询Embedding16、Rerank16；64次有真实Usage，Q43两次Unknown。Embedding仅用于查询，知识库向量未更新。

- 新增已知输入106893、输出102873 Tokens；输出包含Provider已计入的reasoning。
- 原冻结价格表的新增保守规划费用 **1.0305717元**，不是逐请求实际扣款；累计已知规划12.2564118元。
- 官方免费余额查询：开始22.31元，结束21.77元，净减少 **0.54元**。此差额不能精确归属66次请求，也不能据此结算Unknown。
- 原Q09和Q22Unknown预约0.638505元，加本轮Q43两笔0.616161元，原账本未结预约合计 **1.254666元**，全部保留。
- 独立后续Run的Q22超时及Q27中断也缺Usage，未伪造原账本请求。初始Worker单独预留Q27的0.50元；后续只读谱系审计发现Q22超时，再单独保守预留0.50元。结束审计外部Unknown合计 **1.00元**；执行脚本也已补齐今后该1.00元预留。
- 结束实际余额减全部未知预约及至少3元余量，保守可用 **16.515334元**；本轮没有触及预算下限，停止账本仍禁止继续调用。未结费用不当作0、不释放、不重置。

余额查询使用现有官方接口；账户逐请求账单/两次中断Usage尚未取得，不能报告精确的新增实际Provider账单金额。

## 历史保护、回归及交付

写入前使用SQLite Backup API备份DB，并保存原账本。结束对29张表逐行比较：所有本轮前既有行仍在且值不变，包括Golden/Snapshot、旧Baseline、两轮ABC、Agent及Production。仅新增Resume子Run、真实逐题结果/Bad Case；索引、原PDF及冻结题目未写入，Corpus身份按每次请求重验。原401条调用逐条保持一致，37题子Run也保留原始Partial状态和全部结果。

相关92项隔离后端回归通过（Resume、Candidate恢复、费用、Identity、评测上下文、Optimization合同）；新增费用边界测试覆盖精确未知请求范围、保留所有预约及预算拒绝。有限网络恢复自检、语法检查及git diff --check通过。没有UI改动，没有执行新的Golden/Probe/QC/冻结或全量索引构建。

受控运行入口：`scripts/run_baseline_continuous.py`，源Run可由唯一命令参数明确指定；启动标记拒绝同源重复执行，已耗尽的连续两次网络失败拒绝重新预约。仅用于明确授权后的受控执行，不是启动即自动续跑的服务。原始响应、数据库、账本、余额和运行产物仅保存在忽略的`output/playwright/baseline-continuous-20261013/`，不进入Git。

必要代码、当前SPEC、变更日志与本报告同Commit提交并推送origin/main；最终SHA与干净同步状态见交付回复。本次目标尚未完成，实质阻断为Q43重复Provider连接失败。
