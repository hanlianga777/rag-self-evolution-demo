# Sandbox费用对账与A/B/C安全续跑准备（2026-10-23）

本轮真实Provider调用0、API费用0；未重跑Baseline、未生成A/B/C、未续跑Sandbox。基于4d061bc及正式数据库统一审计，只修复共用费用入口。以下“可运行”均指通过本轮离线检查后的技术条件，尚未获得下一轮付费授权。

## 1. A未知费用：未完成对账，继续阻断

- 时间：2026-10-22 14:26:52.696248 UTC，即北京时间10月22日22:26:52.696248；耗时61974ms后超时。模型text-embedding-v4。
- Run：`EVAL-20261022140653311827`，题目`V1G-110926448917-39`。Checkpoint标记generation执行结果未知，没有第39题完整回答。
- 保存记录没有云端Request ID、HTTP状态或有效Token Usage；当时没有独立PaidRun账本（ledger_path为null）。不能恢复成“未收费”，也不能造一个请求ID。旧包装把远程超时显示成本地检索错误；4d061bc已修复后续错误保留，不可能补回旧响应未收到的信息。
- 本会话没有可用阿里云账单连接器或已核实的账单读取权限；模型API Key不代表费用账单权限。本轮不使用该Key试调Embedding、不重试、不标已对账。
- 用户需在阿里云百炼的模型用量/模型监控，按北京业务空间、相关API Key ID、text-embedding-v4筛选22:26–22:29（注意控制台时区）；同时在费用与成本→账单详情选择2026年10月22日/10月，商品“大模型服务平台百炼/百炼模型推理”，按API Key ID、业务空间、模型、输入类型和调用渠道导出费用及Token明细。若只有小时/分钟聚合且同时还有其他调用，不能以汇总差额断言此请求0元，需向阿里云支持提交时间、业务空间、API Key ID与模型，请其关联执行及计费记录。不要提供完整密钥。
- 请保留可验证的Request ID（若支持查得）、是否执行、Token数、费用/抵扣和账单记录。账单证据确认后还需核清是否存在可复用结果；新增付费授权不等于自动消除Checkpoint的unknown。A本次不解锁。

官方查询说明：[账单与费用管理](https://help.aliyun.com/zh/model-studio/bill-query-and-cost-management)、[模型用量](https://help.aliyun.com/zh/model-studio/model-usage-statistics)。

## 2. 逐候选、复用与独立启动

| Candidate | 完成/复用 | 下一题 | 未完成 | 正常请求 | 当前结论 |
|---|---|---|---|---|---|
| A | 38/50 | V1G-110926448917-39 | 12回答＋12Judge | 48 | 未知费用未对账，禁止续跑 |
| B | 1/50 | V1G-110926448917-02 | 49回答＋49Judge | 196 | 可独立授权启动；本轮未授权 |
| C | 0/50 | V1G-110926448917-01 | 50回答＋50Judge | 150 | 可独立授权启动；本轮未授权 |

A的38题、B的Q01中回答与Judge均已完整保存并原样复用；当前没有“已有完整回答只缺Judge”的待处理题。A续跑仍须先对账才能从Q39开始；B从Q02开始，C从Q01开始。原A祖先13题在当前Run逐字节复用，旧分支不能再次预约。各题完整/未完成ID、Checkpoint、来源Run、Evaluation Identity、配置与内容摘要见[逐候选审计](cost_and_checkpoint_audit.json)。

全部Candidate共用正式Baseline `EVAL-20261021141811373593`和冻结50题Snapshot/评测身份；A/B/C的策略、配置、来源和历史Run均未修改。C保留query_only本地排序，不调用远程Rerank，不能按A/B每题4次计费。

## 3. 后端硬预算：原来未生效，本轮已修复

原4d061bc的Sandbox只有authorize_provider布尔确认；未创建受限PaidRun，执行在accounting_only模式，即使有账本也只记账、不拒绝超额。此次共用修复：

- POST候选run除显式authorize_provider外必须提供正数budget_yuan；缺失/无效在预约前拒绝，不能只凭前端弹窗启动。
- 同一Experiment共用唯一持久化人民币账本；A/B/C不因切换、刷新、失败或服务重启重置累计费用。作用域是**下一轮新授权的Sandbox费用**；旧已发生费用及A未知费用单独审计，不当0、不冒充被新预算追溯限制。
- 全程绑定当前Baseline/Snapshot/完整Candidate配置与身份；保存每次显式授权、核价时间和来源。只准收紧已有上限，不能通过换Candidate或扩大金额重置已花费用。
- 共用Provider边界在发送前预留UTF-8输入＋框架开销＋Rerank重复query＋冻结最大输出的费用；DeepSeek回答/Judge/额外查询及Alibaba Embedding/Rerank全部走该边界。缺费率、金额/Usage不明、超限、身份漂移、输入超费用上界均在后续请求前停止。
- 显式硬预算不能被accounting_only覆盖；独占文件锁防同Experiment并发花钱。正常、重试与未结算请求保留各自记录，未知保留预留费用，不能作为完成Case。
- 当前核实DeepSeek官方端点及Alibaba北京业务空间；其他端点需重新核价。费率证据24小时失效，在每次请求前复核；费率缺失/变动时停止。 本次核价UTC：`2026-10-23T03:07:38.228054+00:00`。
- 后台恢复不自动加载已授权硬预算Sandbox；重启保留断点，下一次启动仍需用户明确授权。页面关闭后已授权的后台任务受同一硬上限控制，未启动项不会凭页面刷新自动开始。
- 输入费用保护上界：DeepSeek回答65536字节、Judge131072字节、额外查询16384字节，Embedding32768字节、Rerank262144字节（含重复query/1024开销）；超出在发送前阻断。这是费用保护，不改冻结策略或Judge合同。

新账本仅在下一次明确授权时创建，本轮没有创建正式付费账本或预约Sandbox。API只读preflight返回cost_budget及原resume_plan。

## 4. 剩余394次的费用

| 项目 | 正常请求数 | 历史Token均值按峰值价外推（元） | 硬输入/输出限制下正常上界（元） |
|---|---|---|---|
| DeepSeek回答 | 111 | 1.199062 | 21.823488 |
| DeepSeek Judge | 111 | 9.469944 | 58.195968 |
| Alibaba Embedding | 111 | 0.002155 | 1.818624 |
| Alibaba Rerank | 61 | 0.058696 | 7.995392 |

正常路径估算 **5.40–10.73元**（DeepSeek峰谷/缓存及题目长度会变化，不是完成承诺）；按当前输入费用上限、冻结输出上限、全部缓存未命中与峰时价，正常路径保守上界 **89.833472元**。按全部请求最多3次尝试的保守费用包络为 **269.500416元**，其中重试可能增加最多约179.67元；不是允许Unknown自动重试。

建议下一轮对剩余请求的新授权累计硬上限为**300元**，以覆盖上述保守包络，预计消费仍约5.40–10.73元。若只愿授权更小金额，可以更低硬停，但不能保证覆盖极端输出/恢复场景。300元未在本轮授权或消耗；不是将全部账单认定为300元。历史已发生费用另列，A未知金额未决，因此现在无法给出“历史＋未来”精确实扣总额。

历史保存记录分为：首次路径156个事件，按峰时/缓存未命中保守核算3.733058元；额外Judge恢复3次，保守0.309740元；A未知请求1次，金额**未知**。无效Judge但Usage已结算的付费没有被删掉，也没当0。这些核算不是账户扣款。

官方计价（2026-10-23查询）：DeepSeek Flash每百万Token输入峰时2元/缓存命中0.04元/输出8元，谷时半价；Alibaba北京text-embedding-v4与qwen3-rerank输入均每百万Token0.5元，不计免费额度或折扣。无需USD汇率推算。[DeepSeek价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)、[Alibaba价格](https://help.aliyun.com/zh/model-studio/model-pricing)。

## 5. 完成、资格与剩余中断风险

保存的未完成Run保持Partial/未完成：不产生最终11 Gate、Bad Case修复、Regression、Candidate资格、推荐或Gate 2。50题完整后仍由原11 Gate、同身份逐题对比、Regression及原人工批准机制计算；Regression复用已评分结果不再调用Provider，不合并不同配置的修复。离线50题Fixture证明38题恢复和已有回答仅补Judge的路径，不代表真实完整实验通过。

61项相关后端离线测试通过，覆盖预算绕过复现与修复、跨加载累计、并发锁、上限不重置、未知费用阻断、预算/费率/身份/输入拒绝、单RPC恢复、复用Checkpoint及50题完成后才汇总；前端3文件34项通过，TypeScript/Vite构建通过。测试DB/索引/.env隔离、TCP禁用；Fixture不是Provider结果。

仍可能因远程超时/网络中断、429恢复耗尽、余额或鉴权/配额、Judge无效输出、输入费用上界超出、费率超过24小时或身份变化而停止；不能零调用保证394次全程成功。已知保护会在该停时停，保留已付费结果，不通过重试未知请求或放松Gate强求完成。A已知未知费用继续阻断；B/C无需等待A才能独立合法运行，但同一新共享预算将对以后新发生的未知费用整体暂停。

## 6. 下一步点击与推荐顺序

本轮到此停止。下一轮明确授权后：进入5174“Agent优化→Sandbox”，填写“本Experiment剩余Sandbox累计硬上限（人民币元）”；先点Candidate C的**运行 Sandbox**（Q01起、150次、没有远程Rerank），完成后点Candidate B的**继续 Sandbox**（Q02起、196次）。两个动作都需费用确认且共用同一累计上限。不要点“生成A/B/C”或重新Baseline。

A待阿里云证据完成对账并经本地核验解除未知费用后，再点击Candidate A的**继续 Sandbox**（Q39起、48次）。当前不点“运行本轮A/B/C”批处理，因为A仍阻断；不能因新授权而绕过对账。当前建议的分开顺序不改变策略、参数或原结果。

## 7. 证据与修改范围

- [Checkpoint/身份/费用审计](cost_and_checkpoint_audit.json)、[原中断审计脱敏摘要](checkpoints.json)、[离线验收](validation.json)、[数据保护](protection_after.json)、[服务加载核验](service_verification.json)。
- 共用预算：backend/app/sandbox_budget.py、paid_run.py、main.py；生命周期绑定：evaluation.py、governance.py；费率：backend/config/sandbox_prices.json。
- 前端只增加明确的人民币累计上限输入与传参，沿用Card/Drawer/授权按钮：EvolutionPage.tsx、operation.tsx、ProviderAuthorization.tsx。
- 对应测试及零调用审计脚本：test_sandbox_budget.py、test_candidate_resume.py、scripts/audit_sandbox_costs.py。
- SPEC/CHANGELOG/README及中断文档同步。架构沿原Sandbox内的费用门禁，无新业务节点/关系，无需另画版本。原Golden、Baseline、10道Bad Case、A/B/C、历史Run、已有费用审计与人工发布保护保留；正式DB/Corpus/索引哈希前后不变。
