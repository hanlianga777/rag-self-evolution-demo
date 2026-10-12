# Candidate C Sandbox 异常及恢复验收（2026-10-12）

## A. C失败原因

真实记录：Candidate `EXP-20261012054110446321-R1-C` 为failed，Run `EVAL-20261012072612744729` 为partial。第44题 `V1G-050011728151-44-R061119366859-R074751864797`：

> 现场有KIRA B 50和宇树B2，一份“每月一次”保养表没有标注设备型号，附件来源也没核实。这份表对应哪台设备？使用前还要核对什么资料？

Generation成功，答案和完整Final Context已保存在execution检查点。Judge请求成功返回（39.338秒），但Parser/合同校验抛出ValueError，外层ProviderUnavailable显示“DeepSeek Judge 未返回有效 JSON”。这次不是已记录的超时或SSLEOFError。Run历时2577.700秒；整轮耗时不能当作单请求超时。

**能确认至解析/校验失败，无法锁定具体字段。** 旧执行器只保存cause_type=ValueError，未保存cause_message或异常携带的raw_provider_response；SQLite及所检查执行日志未找到本次失败请求原文。JSON语法、截断、字段缺失/类型及结构化证据哪个具体原因不能据此指定；记录没有提供直接JSONDecodeError证据。成功题的原文不能替代第44题失败响应。

## B. A/B不合格原因

|项|A|B|
|---|---|---|
|Candidate|EXP-20261012054110446321-R1-A|EXP-20261012054110446321-R1-B|
|Run|EVAL-20261012061128978124|EVAL-20261012064820942747|
|状态/完整题数|evaluated / completed / 50|evaluated / completed / 50|
|Hard Gate|11/11通过|11/11通过|
|指定目标修复|3/4|1/1|
|全部原问题修复|5|6|
|新增严重/普通失败|0 / 5|0 / 8|
|Bad Case|11，未减少|13，比Baseline多2|
|Regression|FAIL：普通超过最多1道|FAIL：普通超过最多1道|
|Qualification|NOT_QUALIFIED：Regression及问题总数改善条件失败|NOT_QUALIFIED：Regression及问题总数改善条件失败|

A/B是完整评测后的质量不合格；C是技术中断且未完整，不可混同。C当前partial的Gate/Regression/净改善包含缺题影响，不能当作最终50题质量结论；原记录不改，续跑子Run完整后重新计算资格。

## C. 持久化及Token核对

C保存43条完整逐题结果；第44题只有生成检查点，未被记成回答Bad Case，后6题尚未执行。失败Judge请求已采集输入3682、输出6814（含reasoning5936）、合计10496 Token，计入C总量。原始响应/finish_reason未采集，不能判断截断。请求网络成功不等于Parser成功。

按各Run检查点的Usage累计（避免与逐题汇总重复相加）：

|Run|DeepSeek调用记录|输入Token|输出Token|合计Token|Alibaba合计Token|
|---|---:|---:|---:|---:|---:|
|A|100|240480|357466|597946|113951|
|B|100|244569|358230|602799|216692|
|C|176|216435|426100|642535|103854|

DeepSeek上述Usage总量均已保存；Alibaba包含Embedding/Rerank，其输出Token部分未采集，不当作0。实际人民币费用/账单未采集，Token不是账单金额。本轮检查新增Provider调用0，新增Sandbox启动0。

## D. 修复范围

没有足够保存材料证明Parser兼容缺陷，**未修改Parser**，未猜测或放宽任何字段/安全/证据规则。

仅修复共享执行器的可复现审计缺口：失败检查点追加cause_message及异常已携带的原始raw_provider_response；缺失不补造，不写控制台原文，不回填旧Run。新增离线测试证明补丁前缺字段失败、补丁后保存原因/原文/Usage且不产生成绩或自动重试。SPEC/Changelog同步，评测语义版本不变。

## E. 安全续跑与保护

现有Baseline/Candidate共享恢复机制足够，无需再设计。真实库只读备份的隔离副本实际验证：创建同身份独立子Run，复制43题，跳过调用，第44题复用生成答案；原C失败Run及逐题结果不变，A/B全部Candidate结果不变。当前Golden/Corpus/Judge/配置/Evaluation Identity检查通过，人工启动预算由3/12变为4/12（仅副本），失败不退款，D预留1。

正式库未预约任何Run。SQLite Backup API保护副本与29表前后摘要在 `output/playwright/candidate-c-audit/`，摘要全部一致。Golden、Baseline真实成绩、候选配置/假设、历史Run和Production未改。测试在app导入前隔离DB/Corpus/索引/.env并拦截外部urllib。

验收：17项后端专项测试通过（含真实C副本Mock恢复、Parser异常审计、原有身份/预算/重启恢复）；6项前端队列测试通过（异常暂停、完整但不合格继续、重复点击及人工再点击）；git diff --check通过。前端源码/视觉、Judge/Matcher/评分、Search Space、Agent均未改。共享模块边界及正式架构图无变化。

## F. 剩余执行规模

剩7题：第44题仅补1次Judge，后6题Generation+Judge。因此基础Judge调用7次、Generation步骤6次；C现有multi-query等配置可能产生额外真实模型/Embedding/Rerank调用，不能将6个Generation步骤当6次总Provider调用。不重新调用43道完整题，也不重复第44题的已保存Generation。

每次人工启动占1次Sandbox预算，不自动重试；如果再次技术失败，保留新子Run检查点，仍须再次授权。未满50题不能Completed或Qualified。无法保证下一次Provider输出必然满足合同；若再失败，可用新审计确定具体原因。

## G. 是否可以手动继续

**可以在重新确认费用后，单独点击Candidate C“继续Sandbox”。** A/B已完成，不应重跑；批量仅运行generated，不隐式重试failed。任一单项Provider/Judge技术异常都会暂停后续未启动项，完整质量不合格不暂停队列。

本报告不构成真实调用费用授权；本轮未运行模型或Sandbox。新增审计补丁在确认无活动任务、重新备份及索引无需重建后受控加载8010；只读API确认实验身份保持不变。
