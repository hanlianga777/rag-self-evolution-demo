# Golden 所有者委托夜间真实运行验收 — 2026-10-13

已完成正式 Corpus 切换、50题真实质量治理、所有者委托 AI 审核及新 Snapshot。新版 Baseline 在第9题 Judge 请求超时后停止，实际完成8/50，状态 Partial；Agent、A/B/C、Regression及Winner尚未运行/产生。未自动重试、确认Gate2、生成D、发布或回滚Production。

本报告覆盖上轮20元预算阻断的后续状态，旧报告保留。授权依据为本轮所有者直接指令：累计新增Provider预算50元、分任务输出上限、最多两轮有谱系修订及当前工作集有条件AI代理审核。不是人工专家审核。

## 1. 正式 Corpus 与切换

- 正式 Corpus：`CORPUS-38c90d5628b68c76d53e`。
- Medium Plan：`PLAN-89801791985fdfe13f1421cf`。
- 工作集：`GGEN-20261012120721324996`。
- Chunk / Embedding / Index / Pipeline：`CHUNK-2df5162a379082558b36` / `EMB-586ab413e6f5e2e075ce` / `IDX-ee5bb4977dcf28f8e2f8` / `KP-c39f689648f5a7cf3a4f`。

停止本项目监督进程及API，使用既有Stage3联动协调器、SQLite Backup API、旧索引/State备份切换。持久化切换日志为Completed，启动守卫通过，未走自动知识库重建。首次停服后子进程有短暂优雅退出过程，后续复核确认无监听者；联动验证通过。正式服务已重新加载本轮代码。

## 2. 正式 Hard Validation

修订完成后，使用原`golden-validator-v2.1`对当前50题、新Corpus、冻结Plan、原表格及同组题目重新离线验证：**50/50，无Blocking Error**。20 Positive / 10 Ablation / 20 Negative、9 Topic保持；负向为不足8、澄清10、安全1、注入1。实际难度为基础12、中等32、复杂6，冻结Plan原目标保留，不把目标配额冒充实际分布。

## 3. 真实 Probe / QC

首次完整运行Probe47/50；三题负向有效性风险导致QC按合同跳过。两轮定向修订后当前Probe **50 Passed**、QC **50 Passed**、业务十维审计全通过。QC为49个P2、1个P1（Q23），未改原评级。

六题Q07/Q08/Q09/Q18/Q22/Q23仍有`RETRIEVAL_INCOHERENT`真实召回风险；Q23仅召回C127，缺相邻C128。Golden事实由原PDF支持，这些是留给评测诊断的RAG缺口，**未宣称检索已修复**。

Q02本轮真实Probe最终上下文再次包含1–14全部步骤，包括PDF50页原漏失的5/6。Q42使用DOC-001-C-00031（PDF12页急停）及C00095（28页复位），不再使用不相关C00072。Q16为2023整机手册R1一声开机/左侧数据灯；Q22为V2.1、2025-04-18修订历史及R3两声开机/三声关机，未混用。

## 4. AI代理审核

独立读取50题问句、参考答案/负向合同、实际PDF页及Child/Parent来源，生成逐题12项检查、实际可定位引文、风险及审核依据。全部50题最终A类；实际执行主体Codex/AI代理，delegated_by=project_owner，approval_mode=owner_delegated。当前真实人工逐题审核数为0，未填虚假的confirmed_manual_review。

检索风险接受绑定当次Probe记录ID及Trace摘要，声明retrieval_not_fixed。Q23的P1逐条处置绑定QC记录：标准答案已明确损坏/功能故障勿使用及报告，涵盖异常开关停用；Q24专项测试该条件。接受实际召回缺口用于诊断，不改Judge、不豁免失败QC/P0或未解决安全问题。普通人工路径保持。

## 5. 风险与修订

共两轮、11个Revision Run，均Completed并保留原版本、草案及质量历史；不重生成50题。

第一轮9题：Q05/Q20难度标签；Q10改为同页充电前三项；Q34/Q36/Q44明确缺失信息；Q40消除与Q42重复意图；Q48纠正问句与冻结主题错配；Q50自然化注入情境。另重查Q16/Q22版本证据及Q42重复审计。

第二轮：Q23补齐原PDF46页检查项4–6并引用实际相邻C128；Q07明确“无对接站、含加注系统”前提并引用标题C114。两次草案被原Validator拦截时均未写入正式题，补齐真实来源后通过；未改变验证规则或启动第三轮。

一次本地源复核脚本持有SQLite读取游标期间进行慢OCR，导致Q40 QC落库锁异常。该读游标已关闭；对照已保存实际QC响应、原请求SHA与现行内容/身份恢复同一结果，**未再次调用Provider**。恢复审计及原账本副本保留。后续源复核先取完并关闭DB连接再处理PDF。

现仍有六项实际召回缺口及新版评测不完整，不能据此声明系统整体合格或生产可发布。扫描封面仅用已安装RapidOCR核实，未下载模型、未付费OCR。

## 6. Golden Snapshot

真实正式HTTP委托治理接口返回：**`GD-20261012170200900815`**。

新Corpus/Plan、50题、20/10/20、9 Topic、50份Owner事件与Approval已核验。冻结后题目内容与当前工作集逐题一致；未继承旧Snapshot审批。任务停止后关闭本轮服务器委托授权有效期，原授权及审核证据保留，未来任务没有永久代审资格。

## 7. 新 Baseline

**`EVAL-20261012170221281218`**，real / real，新Snapshot和新Corpus。

真实正式业务ASGI接口启动，不是Fixture。完成Q01–Q08的生成及Judge，共8/50；Q09回答与最终上下文已保存，Judge在240246ms后出现ProviderTimeout（底层The read operation timed out）。运行已持久化为Partial，没有自动重发或继续后续题。

Evaluation Identity：`8cdc2a32aea37a069dd75557c34688a0cae64fa0a52c0361c8020377a8c19106`；冻结回答8192、Judge32768、查询4096，同一Baseline/Candidate必须一致。模型及评分提示词保持。

## 8. Overall 与11 Gate

Overall为**NOT_EVALUABLE / null**，不能称准确率或完整新版成绩。

仅已完成子集得到Positive三指标96.88/98.75/98.75、回答Latency P50/P99为4.870/9.843秒；对应5项为PASS。其余6项为NOT_EVALUABLE，完整Gate资格未通过。这里的延迟是回答阶段，不把240秒Judge超时混作回答耗时。未下调任何阈值。

## 9. Bad Case 与根因

已保存2个真实Bad Case：Q06为Evidence Pending Review；Q07为Generation Failure及Evidence Pending Review。两题primary_root_cause均Unknown、诊断preliminary、依据unresolved_evaluation_evidence。不能强行归入四类已确认根因，也不能把待核实问题直接作为可信Agent优化目标。

既有界面已读取Failure Tags、主要/次要根因及诊断证据；本轮未重构诊断UI。Answerability解释中的额外建议不作为标准答案依据，负向审核保留“不在拒答后补造危险/无来源操作”合同；完整50题实际回答行为尚未评测完成。

## 10. Agent 参数

**未运行**。没有新版Agent Trace或新A/B/C配置；旧实验及参数只作为历史保留。

## 11. Candidate 成绩

**A/B/C均未运行**，第一/第二轮新版50题Sandbox均未启动，没有可报告的新Candidate成绩。

## 12. Regression / Qualified

**未运行、不可判定**。未调用Sandbox、未消耗新评测额度，11Gate及新增严重0/普通≤1规则保持。

## 13. Winner / Recommendation

**没有新版真实Winner或Recommendation**。不采用旧Winner替代，不调用会确认Gate2的选择推荐接口；未生成D、发布或回滚Production。

## 14. Provider、Tokens 与费用

| 模型 | 请求尝试 | 返回真实Usage | 已知输入Tokens | 已知输出Tokens |
|---|---:|---:|---:|---:|
| deepseek-v4-flash | 164 | 163 | 3,115,681 | 446,956 |
| text-embedding-v4 | 114 | 114 | 15,332 | 0 |
| qwen3-rerank | 70 | 70 | 157,128 | 0 |
| 合计 | **348** | **347** | **3,288,141** | **446,956** |

输出包含Provider记录的reasoning Tokens。Embedding均为实际查询/相似性验证用途，本轮没有再次更新知识库向量。所有347份实际响应及Usage已保存；超时请求没有收到响应/Usage，不能伪造原始响应或计作零费用。

- 已知Usage按官方非高峰/缓存价格及USD/CNY 6.7313估算约**4.430723元**。
- 同一预算账本按冻结保守峰值价格、不享缓存结算的已知规划费用：**10.3835905元**。
- 超时未结请求继续保留**0.3311364元**规划预约，总保留额度**10.7147269元**；未把未知费用释放成零。
- 50元规划限额未超，账户实际扣款尚未核验。总实际账单仍未知；上述价格估算不是服务商扣款凭证。
- 未知Usage/停止账本拒绝next_stage，已离线验证；没有付费自动重试。

价格依据：[DeepSeek官方价格](https://api-docs.deepseek.com/quick_start/pricing)、[阿里云百炼模型价格](https://help.aliyun.com/zh/model-studio/model-pricing)、[2026-10-12中国外汇交易中心中间价公告](https://www.chinamoney.org.cn/chinese/ccprnoticecontent/index.html?searchDate=2026-10-12)。本轮冻结价不自动随后续价格改变。

## 15. 历史保护及回退

29表逐条比较正式切换前Backup：无原行丢失。旧6 Snapshot、24评测及703逐题结果、6 Experiment、16 Candidate、9 Agent Trace、2 Production和全部历史质量/审批记录不变。仅本工作集50题的生命周期/授权修订、1个Run/Artifact必要更新，以及新增真实质量、Revision、审核、Snapshot/8评测结果。

旧索引完整备份及原版本保留，与新指针目录隔离；367个向量再次逐位验证，复用字节SHA为`556641bf5b3bc2da30d32c645bfc3eac2be5044b8cfde182ce9114cc8f41a852`，仅row133不同。新Bundle的Child/Parent/Embedding/FAISS验证通过，4份PDF文件SHA与Manifest一致。SQLite Backup、State、原索引及Stage3恢复日志可定位；既有11个隔离恢复场景保留，本轮未为了验证而再切回正式Corpus。

Production版本记录未变；旧Baseline不再是新Corpus的当前评测资格，不宣称旧Production因此获得新版发布资格。后续质量失败不自动回退已合法完成的Corpus切换。

## 16. 代码、SPEC与验证

最小复用现有流程：受控任务上限/线程上下文、累计预约与阶段身份守卫、实际响应保存、首次停止原因保留；Owner审核仅服务器授权的当前工作集，复用JSON审计/审批/冻结事务，无新Schema；版本章节输入及metadata-only Revision修复；UI仅区分Owner来源。同步SPEC、变更日志、README及唯一KnowledgeDiagrams架构导出。

最终相关后端**202项通过**；Frontend **187项通过**，Owner治理定向22项通过，生产Build通过，实际本地页面Owner标签可见、无pageerror。原Validator正式50/50、367向量逐位检查、历史29表保护通过。Fixture测试只证明合同/错误处理，真实执行证据来自本报告明确列出的Provider/API/DB记录。

最终API已重启加载当前代码；启动守卫通过，重启不自动恢复Partial评测或付费账本。

## 17. GitHub 与私有审计

本报告与必要代码、SPEC及正式架构文件范围内提交；最终Commit SHA及origin/main同步结果见本次交付回复。私有数据库、授权文件、索引、凭据和原始运行产物不入Git。

本地私有审计根为`output/playwright/golden-delegated-20261012/`：切换/备份、逐题PDF审核、11 Revision及预览拦截、原Provider响应、费用账本、Owner API返回、新Snapshot、新Baseline检查点、未知Usage阻断、历史摘要及测试日志均保留。

## 18. 次日操作

1. 先核对Q09超时请求对应Provider Usage/费用；本轮不自动重新请求，不把未知费用当零。
2. 查看Q06/Q07真实回答、Judge争议及六项召回风险。保留冻结Golden，新Baseline尚不具备完整诊断/发布资格。
3. 明确授权续跑后，再使用既有Checkpoint/Resume流程，复用已完成8题及Q09已保存回答；不得自动重复生成或直接启动Agent。重新验证Snapshot/Corpus/规则/限制与累计费用。
4. 完整Baseline合法结束、可信诊断条件满足后再继续Agent及最多两轮ABC；Gate2与发布仍须人工，不自动执行。

无需重新下载模型或重建知识库。当前没有新版Winner或可直接发布的结论。
