# Baseline / Sandbox自动恢复验收

2026-10-13，Ponytail full。基于 `3dad728` 做共用执行链路、Judge传输/解析、Worker与必要Baseline状态修复。**本轮真实Provider调用0次、费用0元，没有创建或执行新的真实50题Run，没有补跑Q38。**

## 真实中断原因

最新 `EVAL-20261013125822267156` 保存37/50题、Q38生成回答及最终Context。Q38错误原因是 `Missing typed claim or behavior evidence`，单次Judge约57秒；此前19/50的Run缺 `abstention_basis`，16/50的Run是JSON语法错误。没有证据表明1214秒累计时长触发了停止。

原后端已保存 `question_total_seconds=None`、`round_total_seconds=None`，未发现20/30分钟整批停止机制。本轮修复的是“任何Judge错误直接结束整批”和“恢复需要再次人工启动”的路径，同时移除了Baseline页面约300次轮询封顶。

## 取消哪些执行限制

|限制|本轮行为|
|---|---|
|整批累计时间|继续不设上限；离线模拟多小时任务仍完整结束|
|前端300次轮询|删除，网络读取失败也继续查询真实状态；350次以上轮询测试通过|
|累计人民币费用/预算预约|Baseline/Sandbox公共执行上下文采用accounting-only，超过预算仍记录并继续，不执行费用边界|
|余额至少3元|新API/Worker评测链路不查询余额、不执行最低余额预留，不需要按余额重新授权恢复|
|价格或Usage缺失|记录未知，不阻断；未知费用不计0，原未知预约不清零|
|内部Token财务上界|不再按UTF-8保守Token预估、价格max_output或累计费用预留拒绝请求|
|单次网络超时|保留，默认240秒，可按原配置；只表示一次连接/读取，不是整批时间上限|
|冻结单请求参数|保留原max_tokens/模型/temperature，不修改冻结Evaluation Identity；未冻结限制的Run不增加max_tokens|

这里取消的是**评测公共链路中的执行阻断**。PaidRun作为既有Golden/Probe/QC专属授权工具的旧约束仍保留，历史一次性夜间脚本的旧授权/余额预检不被新API或自动恢复调用；本轮没有扩大Golden/Agent生成权限。实验MAX_EVALS/D预留属于原实验治理，不是50题Token费用保护，本轮不改；同一个任务自动恢复不重新预约Sandbox次数。

Provider的余额不足、额度不足、认证、权限、请求非法与确定的配置/身份错误照常停止，不绕过Provider限制。账户402/401/403等不自动重试；429按暂时限流处理并遵守Retry-After，明确insufficient_quota/balance则停止。

## Judge异常自动恢复

每个未完成题分为generation和judge。成功生成后立即保存execution，Judge重试只读取该回答和冻结Context。Judge评分成功还先保存scored_result，再原子保存Case/BadCase；落库中断后可复用评分，不重新调用Judge。

网络超时、连接中断、可恢复408/429/5xx采用1、2、4、8…最多60秒退避，Provider要求更长等待时遵守其Retry-After；没有整批累计时间或网络重试次数上限。嵌套Embedding/Rerank网络异常按底层异常类型识别，不把索引/配置异常当作网络错误。

格式与字段异常先严格解析：只允许移除BOM或完整Markdown JSON外壳；IncompleteRead的partial本身是完整JSON时可本地恢复并继续原校验。不能闭合截断JSON、填缺失字段、修改评分或虚构证据。finish_reason=length明确归截断，原响应/Usage保留，重新调用当前Judge。

连续不合格结构最多六次请求；仍不满足合同则视为不可自动恢复，保存断点和具体原因并停止，不假装Completed。这个限制是结构合同故障判定，不是任务时间/费用上限。网络故障不套用六次上限。

审计包含阶段、错误类型/底层原因、HTTP状态、原始响应、finish_reason、真实Usage、请求摘要、耗时、退避和Run谱系。请求已返回真实Usage即记录；未知收费保留Unknown。任务request_accounting额外汇总含恢复谱系的已知Token与未知Usage，不用仅最后一次成功Judge代替全部重试成本；既有质量/资格指标算法不改。

## Worker与重复任务保护

首次显式启动保存auto_recovery授权。SQLite BEGIN IMMEDIATE领取、PID/线程/worker_token联合保护，存活Worker不会被接管。后台每5秒只检查授权的活动任务及尚未落Candidate资格的完成任务；进程退出后继承同Run断点，线程意外退出也可恢复。整批独立于页面生命周期。

每题立即持久化，恢复跳过所有已保存题号；已完成Run再次调用执行器不会重评。同题的scored_result与Case/BadCase原子写入避免完整评分后的重复支付。重复启动入口已有活动Run时409；重复Worker领取不发生Provider调用。恢复重新校验Snapshot、Corpus、配置、Judge模型、规则与Evaluation Identity；发生真实冲突则保存阻断，不能混合结果。

旧Partial/Failed/历史Run没有新授权标记，不自动激活、不写回旧成绩。本轮原始37/50属于这类历史断点，需要用户下一次正式恢复启动一个继承子Run；随后网络/可恢复Judge故障不再反复点击授权。本轮明确不执行该启动。

## 当前37/50是否可恢复

**可恢复。** 在真实数据库的隔离副本，仅调用输入校验，确认：

- Snapshot、当前Corpus、Pipeline配置、Judge及完整身份与源Run相同。
- 37条唯一题号完整保存，剩余13题。
- Q38回答/Context可复用，只需补缺失Judge；Q01–Q37不重做。
- Evaluation Identity保持 `44461d1d4c53a28480d6ff2b5bcfc28fa8e6c76cbddb6e36b7ddb00c8cb9755d`。
- 校验没有Provider调用，没有创建新的真实Run。

Baseline页面刷新通过 `GET /api/evaluation?active_task=true`找到37/50，而非旧完成Baseline；completed计数取数据库实际题号，不信过期缓存。默认概览仍返回原正式完成Baseline，未提前授予Partial Agent资格。自动重试/后台执行/不可恢复停止有明确状态，全部失败Checkpoint与费用统计在评测依据折叠区保留。

## 验证结果

|要求|证据|
|---|---|
|无整批时限|多小时模拟完成，runtime_limits总时限为空|
|无内部费用/余额阻断|费用远高于预算、价格缺失及未知Usage仍继续的Fixture通过|
|Judge JSON恢复|外壳本地恢复、截断/字段缺失重试、六次失败保留断点通过|
|网络自动恢复|Timeout/HTTP分类/嵌套检索异常、账户额度不可重试通过|
|完成题不重复|已完成题/保存回答/已评分断点复用通过|
|自动断点|死亡归属queued恢复同Run、存活归属不接管通过|
|真实进度|DB计数覆盖过期999缓存，页面37/50只读检查通过|
|重复任务|SQLite领取第二次拒绝，Provider未调用通过|
|Token/费用|已知Usage/未知收费分别保存，截断不丢真实Tokens通过|
|身份|同Snapshot/配置/Judge/冻结限制继承，版本常量不变|
|历史保护|任务前SQLite Backup API与本轮末29表全行完全相同|
|Baseline/Sandbox共用|恢复、Sandbox继承、原Regression/Gate相关回归通过|

后端相关 **109项通过**；前端 **37文件197项通过**；TypeScript/Vite构建与diff检查通过。测试使用隔离DB/Corpus/PDF/env、Mock和本地响应，没有真实Provider。旧timeout测试仍假设60秒，已更正为现行240秒，未修改请求默认值或性能Gate。未重跑整个历史全库，也不把Fixture当作真实50/50验收。

安全窗口核验无活动评测、无自动授权任务后，仅重载受原监督进程管理的API，已只读验证新接口返回当前37/50；未停独立Worker、未触发恢复调用。浏览器全部非GET阻断，显示“37/50”和“恢复Baseline”，无页面异常、无写请求。截图：[真实Partial页面](../output/evaluation-autorecovery-20261013/baseline-partial37.png)。

## 保护、交付与下一步

Judge `judge-v3.2-governance`、Matcher `evidence-v4-fragments`、Policy `v1.3-abstention-scope`保留；未改评测标准、11 Gate、Regression、Candidate算法、Golden、Corpus或其他一级导航。原Baseline和A（97.20 / Gate11/11 / Bad12 / FAIL / NOT_QUALIFIED）原样保留。检查唯一架构图源后，图中的Golden有限修复与12次实验治理仍有效，无需改动其他页面的图。

私有备份/日志/原始响应/截图位于忽略的 `output/evaluation-autorecovery-20261013/`，不进Git。代码、SPEC、变更日志、必要测试与本报告同次提交推送main；最终Commit与干净同步在交付回复确认。

下一次用户明确启动“恢复Baseline”即可从当前断点进入新版持续运行；本轮不执行该动作，不运行B/C，不自动Agent、Gate2或发布。没有承诺Provider账户余额、服务可用性或模型永远返回合格结构；这些真实不可恢复条件会保留断点并明确停止。
