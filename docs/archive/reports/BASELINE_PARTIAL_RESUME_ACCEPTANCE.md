# Partial Baseline恢复验收 — 2026-10-13

本轮修复同身份恢复及页面展示，原8题和Q09回答全部复用，真实评测推进至21/50。Q22 Judge发生新的HTTP IncompleteRead且Usage未知，已停止，未重发、未启动Agent/ABC。本轮目标尚未全部完成。

## 1. 原超时与本轮新异常

原Q09 Judge在240秒后触发读超时，原请求SHA为`8a6f6f59c58a85adb0ad3040c554750d428b69855e01fa17a750c5fd5400d27c`。无收到的Provider响应/请求ID/真实Usage，不能从账户余额差额反推Usage或断言服务端根因，原0.3311364元预约保持Unknown。

本轮受控HTTP等待调整至600秒，不改变模型、输出限制或Judge标准。唯一一次Q09付费补跑约36.917秒返回：输入6407、输出7672 Tokens（其中reasoning5838），finish_reason=stop。原响应缺一个末尾外层对象闭合括号，原Parser拒绝。保留原响应，仅对该已保存响应追加一个`}`后，原Parser及完整字段/评分/来源校验通过；无新增字段、无改分、无永久宽松Parser或额外Provider调用。Q09真实结果为Bad Case。

一次本地恢复尝试向已终止子Run写进度，被既有守卫正确拒绝；仅撤销本代理临时新增的Q09行并保留预览审计，随后通过正式Resume新子Run和正常Worker消费保存的响应。没有绕过终止状态或身份守卫。

新Q22 Judge发生`ProviderNetworkError`，底层`IncompleteRead(0 bytes read)`；Q22回答及最终上下文已保存，Judge无完整响应/Usage。新请求SHA为`695d55c947f5d590f67c46705250521c82d7d62ee9c58d5ee9679cd8bae3027a`，保留0.3073686元预约。不能伪造该Judge结果，本轮没有扩展Q09补跑授权重发Q22。

## 2. 恢复与身份

原Run `EVAL-20261012170221281218`仍为只读Partial8/50。

恢复谱系：原Run → `EVAL-20261013001146766683`（保存Q09返回但Parser失败）→ 当前 **`EVAL-20261013001822023449`**。

当前状态Partial **21/50**，不是完整Baseline。三个Run的冻结Snapshot、配置、Judge元数据及Evaluation Identity一致；当前Identity仍为`8cdc2a32aea37a069dd75557c34688a0cae64fa0a52c0361c8020377a8c19106`。

Snapshot `GD-20261012170200900815`、Corpus `CORPUS-38c90d5628b68c76d53e`及Plan均未修改。回答8192、Judge32768、查询4096和模型参数保持。

## 3. 避免重复执行

原Q01–Q08逐题结果JSON字节与当前子Run完全相同，仅按既有机制复制记录，不重生成、不重Judge。Q09检查点中成功Generation仍仅一次，复用原回答/检索上下文；本轮Q09付费Judge仅一次，语法恢复只读取同一实际响应。

Q10–Q21已完整生成并评分；Q22回答已保存但Judge失败。Q23–Q50未执行。原348条账本请求逐条一致，没有重算或覆盖。

## 4. Baseline成绩及完整性

当前Baseline ID：`EVAL-20261013001822023449`。

- 21/50有完整逐题结果，Q22只有生成检查点。
- Overall：null / NOT_EVALUABLE，不能当作50题成绩或准确率。
- 当前3个Bad Case，完整新版评测/Agent资格仍未建立。

## 5. 11项Hard Gate

以下仅为已完成子集结果：Positive20题、Ablation1题、Negative0题，不能称完整50题Gate通过。

| Gate | 当前值 | 状态 |
|---|---:|---|
| Positive Correctness | 98.75% | PASS |
| Positive Faithfulness | 99.50% | PASS |
| Positive Completeness | 98.50% | PASS |
| Ablation Correctness | 100% | PASS |
| Ablation Faithfulness | 100% | PASS |
| Ablation Completeness | 100% | PASS |
| Safe Rejection | 未采集 | NOT_EVALUABLE |
| Safety Critical Accuracy | 未采集 | NOT_EVALUABLE |
| Prompt Injection Resistance | 未采集 | NOT_EVALUABLE |
| 回答Latency P50 | 6.768秒 | PASS |
| 回答Latency P99 | 18.944秒 | PASS |

合计8项子集PASS、3项不可评估；完整资格未通过。延迟为回答阶段，不能把Judge等待或本地语法解析时间混作回答性能。

## 6. Bad Case及根因

Q06：Evidence Pending Review；Q07：Generation Failure / Evidence Pending Review；Q09：Evidence / Citation Failure。

Confirmed **0**，Needs Review **3**；Primary Root Cause均Unknown。不把症状推断成已确认Retrieval/Generation/Safety/Performance，不向Agent提供伪造可信根因。旧Bad Case不回填。

## 7. Agent A/B/C配置

**未运行**。没有本轮新Agent Trace或候选参数；没有用历史A/B/C冒充新结果。

## 8. A/B/C成绩

**未运行**。完整Baseline技术前置条件未满足，未启动任何新50题Sandbox。

## 9. Regression与Qualified

**未运行/不可判定**；没有新版Winner或Recommendation。不自动Gate2、D、发布或Production回滚。既有阈值未改变。

## 10. 新增费用与未知费用

官方免费余额GET：执行前23.09元，结束后22.31元，账户净减少0.78元。该差额不是可归属到逐请求的完整账单，不能据此结算两笔Unknown。

本轮新增53次模型请求尝试：DeepSeek27、Embedding13、Rerank13。其中52次返回真实Usage，1次新Q22未知；已知输入108368、输出79196 Tokens（含reasoning）。Embedding只用于查询，没有改知识库向量。

- 新增已知Usage按官方非高峰/缓存价格及冻结汇率估算 **0.395179元**；账户逐请求实际扣款尚未核验。
- 原账本保守规划新增 **0.8422496元**，累计已知规划11.2258401元。
- 原Q09未知预约0.3311364元，新Q22未知预约0.3073686元，合计 **0.638505元**，均未当作零或释放。
- 累计规划上限从50元收紧为30.4735905元：原已知规划10.3835905 + 可用余额23.09 − 至少3元余量，未用理论384K输出计算全轮费用。
- 每次新请求继续预算预约/真实Usage结算。停止账本拒绝后续阶段；Q09补跑额度已用完，没有无限重试。

价格依据：[DeepSeek价格](https://api-docs.deepseek.com/quick_start/pricing/)、[阿里云模型价格](https://help.aliyun.com/zh/model-studio/model-pricing)。余额来自[官方余额接口](https://api-docs.deepseek.com/api/get-user-balance/)，不是50元假定账户余额。

## 11. 页面身份错误修复

根因是普通Resume入口没有读取冻结的request_limits，导致与原Run的Evaluation Identity/配置真实不同；没有忽略校验。现在入口从源Run读取限制，并通过执行上下文用于真实请求，Candidate也复用冻结限制。源Snapshot/config/Judge全部严格比较，原Identity不改。

当前Snapshot下的Running/Partial/Failed报告可显示，完整Baseline的Agent/发布资格判定仍保持独立。页面正确显示当前Snapshot下最新Running/Partial/Failed进度与失败原因，不显示“尚未运行”或误称身份失效。本轮受控Run为21/50；之后另有Run推进至26题，当前页面选择其真实26题记录，不能把它归入本轮付费账本。仅最小文字/状态修复，未重构UI。

隔离后端91项回归通过，Partial页面定向3项测试及生产Build通过；真实浏览器只读验证结果另存审计，不点击付费按钮。

## 12. 历史保护、交付与下一步

使用SQLite Backup API备份本轮前DB及原账本。比较29表：所有本轮前既有行逐条不变，包括原Snapshot、8题Partial、历史Baseline、两轮ABC、Agent及Production。仅新增恢复子Run、真实结果/Bad Case及审计；Golden、Corpus/索引没有写入。

必要代码、SPEC、变更日志及本报告同范围提交推送origin/main，最终SHA/同步状态见交付回复。私有DB、账本、原响应、余额及检查点不入Git。本地审计根为`output/playwright/baseline-resume-20261013/`。

新的实质阻断是Q22 Judge响应丢失且Usage未知。后续须先核对该请求费用，并明确是否授权缺失Judge的受控补跑；如获授权，应从最新21题子Run继续，复用Q22回答，不能重跑前21题或直接启动Agent。无需重新下载模型、重建知识库、修改Golden/评分或冻结新Snapshot。

### 后续并行状态与启动保护

在本轮受控Worker已停止后，数据库另出现后续恢复Run；最新`EVAL-20261013005603096653`为Failed、26题，源`EVAL-20261013005144644305`，仍为同一Evaluation Identity。其运行来源不能凭Run记录确定，不纳入本轮53次计费请求/21题成果。本轮未发起这两条Run，不并发接管或重发其请求。

工具中断后本地API无监听，恢复服务的既有启动清理将该后续Run标记为“进程重启，评测已中断”。恢复前未重新核验所有独立Worker活跃状态，判断不充分；不把它归为本轮Provider故障。已补最小归属保护：新Run记录进程PID，有归属的新Run保留存活进程及相关Candidate；历史无归属记录沿原中断行为、不回填；审计字段不进入评测身份，历史不回填。没有自行将已Failed的26题Run改回Running或Completed。进程归属保护代码已验证；为避免再次干预并行任务，本轮不再重启服务，后续在确认无活动任务的维护窗口加载。继续前应先核对最新检查点、活跃Worker及后续独立费用，避免重复执行。
