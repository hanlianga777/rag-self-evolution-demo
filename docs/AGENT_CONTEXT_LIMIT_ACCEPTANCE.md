# Optimization Agent上下文超限修复

2026-10-14，Ponytail full。本轮Provider调用0、费用0，不重跑Baseline、不生成Candidate、不运行Sandbox。

## 确切根因

用户最新一次真实调用的错误审计已经保存Provider正文，request_id为`b4676d65-5152-422c-9c6e-29664f87d34d`，错误码invalid_request_error、HTTP400、不可重试：模型上下文上限1,048,576 Tokens，消息实际1,106,742 Tokens，completion为0。消息超过上限58,166 Tokens；不是JSON解析、model/temperature或输出截断导致。

原请求SHA为`0b41dd56f0bed4cf70ff420af1d31909b4e314c88abfd513e0bb2ebda484a756`。此前约935,605的字符Token估算低估了真实Tokenizer结果，不能据此声称请求已经符合实际上下文容量。先前[HTTP审计报告](AGENT_HTTP400_ACCEPTANCE.md)记录的是当时正文缺失的证据边界，本次取得真实正文后根因已确认。

## 最小修复与无损证明

数据库Bad Case行同时带result_json序列化字符串和result解析对象；全部13题逐项验证`json.loads(result_json)==result`。Agent原来把这两份重复内容同时发送，在Confirmed目标组与全量背景组均存在。

仅在optimization.py的Prompt投影中移除每行result_json，保留完整result及其他全部字段，不裁剪答案、Judge主张、Evidence、来源、检索候选/排序/Final Trace、评分和可信度。数据库行、本地完整审计、后续Candidate持久化输入不改。无新依赖、模型/temperature/JSON模式/max_tokens不变，One Candidate = One Explainable Hypothesis + Minimum Necessary Parameters、Search Space及全部评测治理规则不变。

隔离重建结果：

| 项目 | 原请求 | 修复后 |
|---|---:|---:|
| 请求字节 | 5,774,935 | 2,947,105 |
| 消息字符 | 2,533,157 | 1,309,689 |
| 字符Token粗估 | 935,605 | 484,134 |
| 真实背景Bad Case | 13 | 13 |
| Confirmed目标 | 7 | 7 |

请求体减少48.97%。修复后SHA为`04176084639b4fa6b3dd044ed8080147d31ad144db8f078cd08e0d1b02b18296`。对原/新Prompt所有组逐行深比较，除result_json外**全部字段相同**；规则、引用映射、历史配置、Gate及失败Gate完全相同。原请求私有产物仍保留，原SHA复核一致。

484,134仍只是原字符估算方法的观测值，不是Provider实测；本轮没有增加预算保护、粗估硬阈值或自动截断，也不把真实上下文检验描述为已经完成。

## 验收与历史保护

- 先写重复传输回归，旧代码失败；修复后30项相关测试全部通过，涵盖无损投影、Agent合同/可信目标/Search Space、HTTP审计、Provider及Q38回归。
- 真实13题加7目标输入隔离重建，JSON可解析、字段深比较及原/新SHA保存；Provider HTTP没有执行。
- SQLite Backup API备份及29表完整行摘要前后相同，Baseline `EVAL-20261013151016199140`和既有Experiment/失败Trace/历史评分未修改；Evaluation Identity未变。
- 私有原/新请求、备份、逐字段证明保存在忽略目录`output/playwright/agent-context/`及原`agent-http400/`，不进入Git。
- Python编译、git diff --check通过。无活动任务时安全加载修复，未自动启动任何真实调用。

## 下一步

修复已消除重复序列化造成的输入膨胀，可以在用户明确启动后进行一次真实A/B/C生成验证。新的实际Tokens与Provider是否接受仍待真实调用确认；成功响应继续受原Candidate Schema、可信目标和Search Space校验，不自动运行Sandbox或发布。
