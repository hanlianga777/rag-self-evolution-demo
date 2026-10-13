# Q38 Judge重复失败根因与恢复验收

## 根因（真实记录，不依据前端通用报错推测）

修复前最新Baseline为`EVAL-20261013145213242299`，来源`EVAL-20261013142506137206` → `EVAL-20261013125822267156` → `EVAL-20261013124042679920` → `EVAL-20261013120614428980`。最新Run保留37题和Q38回答、最终Context。

Q38累计9次Judge失败：8次结构合同失败（早期1次ProviderUnavailable包装、7次ProviderInvalidResponse）、1次240秒网络读取超时。8份真实原始JSON均可解析，`claim_reviews`均为数组；`behavior_pass=false`且`behavior_evidence`均为数组，而Parser要求一个连续答案引文字符串，底层均为ValueError“Missing typed claim or behavior evidence”。有metadata的7次结构失败均finish_reason=stop，输出Tokens为8,486–18,554（含推理），不是max_tokens截断。早期无metadata不能补造finish_reason，超时Usage未知不能记0。

原JSON示例仅包含7个基础评分字段，遗漏evidence_sufficiency、claim_reviews、behavior_evidence；后续文字没有明示behavior_evidence必须单字符串。多失败主张的Q38因此反复输出数组。仅改超时或增加重试次数不能解决。

最新Run14:52:13.457 UTC创建、14:53:09.795结束，共56.34秒。Q38本次Judge用44.63秒，其余为启动/加载开销；它继承了源Run六次ProviderInvalidResponse记录，首次新结构失败即达到七次，马上终止，不是任务时长限制触发。谱系另有早期包装为ProviderUnavailable的一次格式失败，因此累计真实结构失败为八次。

## 最小修复

- Judge开头改为合法、完整JSON形状示例，补齐当前Context合同及claim_reviews嵌套字段。示例值只说明格式，评分仍必须依据样本；明确behavior_evidence为单个连续原文字符串，其他主张保留在claim_reviews。不合并多片段，不填造缺失判断。
- Parser仍严格拒绝数组/缺失依据/不存在于答案中的失败引文。语法错误、缺字段、合同错误区分记录，错误消息包含具体字段，metadata保存validation_error；supported_abstention缺依据显示claim_reviews[i].abstention_basis路径。
- 明确授权Resume新Run只统计自身recorded_by_run_id的连续失败，同一Run进程恢复仍累计，六次结构失败上限不变；旧尝试原文、费用和谱系全部保留。
- 未改Judge评分、Matcher、11 Gate、Regression、Golden、Corpus、请求模型/temperature/max_tokens或Evaluation Identity。Identity保持`44461d1d4c53a28480d6ff2b5bcfc28fa8e6c76cbddb6e36b7ddb00c8cb9755d`。

现有Chat Completions调用已经使用response_format=json_object。官方说明该模式约束合法JSON并建议提供格式示例；它不能取代应用字段合同。严格工具调用/Responses JSON Schema涉及切换调用协议，未经当前冻结链路验收，本次保留现有请求模式并严格本地校验。[官方JSON说明](https://api-docs.deepseek.com/guides/json_mode/)、[Chat Completions参数](https://api-docs.deepseek.com/api/create-chat-completion/)。

## 离线验收

72项相关后端测试通过，涵盖Judge完整格式/具体错误、同Run六次边界、子Run不继承旧失败窗口、Baseline/Candidate Resume、停止/自动恢复、评分治理和Claim一致性；git diff --check通过。

真实Q38八份保存响应全部离线复现精确数组类型错误。仅在离线测试内把已有数组中的一个实际连续原文作为字符串，六份通过原完整Parser、behavior_pass仍false，评分未改变；其余两份继续因缺abstention_basis失败，未补造字段或记录为评测结果。这些测试样本从不落入正式评测。

隔离Resume故障注入证明：旧失败历史完整保存，新Run仍可完成；已完成Case及回答不重复调用，冻结Judge/Identity一致。同Run已有五次结构失败再失败一次则停止，只发一次请求，不通过重启清空次数。

## 用户授权后的真实执行

用户追加授权修复通过后恢复Baseline；另外明确允许现有Agent生成新ABC草案、仅运行A Sandbox，B/C不运行。自动审批首次拒绝启动，要求明确外部数据发送授权；该命令未执行。用户随后明确授权现有DeepSeek接收题目、参考答案、保存回答和Context及后续可信Bad Case，允许现有Provider真实付费运行。

SQLite Backup API备份和29表原始行摘要保存在忽略的output/playwright/q38-judge。通过正式Resume创建`EVAL-20261013151016199140`，绑定上述源Run，冻结Judge完全一致；Q01–Q37复用原结果、Q38复用原回答，实际执行进度和最终验收见后续记录。

本报告不会把离线测试、格式示例或未完成阶段当作Provider真实成绩。
