# Judge Parser最小兼容修复验收（2026-10-12）

**具备再次真实验证的技术条件；需先受控加载本次补丁并获得新的调用授权。** 本轮真实Provider调用0次，未重启后端、运行Baseline或ABC；不能把离线保存响应回放表述为新的真实Judge验证。

## 实际修复

唯一生产代码改动在providers.py：完整上下文Judge合同明确行为通过时behavior_evidence可缺省，内部规范化为空字符串；行为失败必须给出非空字符串，并复用现有normalize在实际答案中定位，否则拒绝解析，不形成Safety确认结果。未改Matcher、评分、主张分类、operation_basis、changes_operation、11Gate、Regression、Golden、Agent或UI。

原始Provider响应字符串作为raw_provider_response随成功Judge结果返回，后续运行复用现有judge_result JSON存储；解析错误异常亦携带原字符串供调用方审计，不自动回显或写日志。本轮没有回填历史。仅兼容字段适用性，不升级judge-v3.1-claims/evidence-v3-scoped/v1.2.1-claim-consistency或Evaluation Identity规则。

## 可选字段核对

- missing_points、unsupported_claims缺省已有[]默认，离线测试覆盖，未再修改。
- reason及四项评分/行为字段属于基础合同必返；claim_reviews、evidence_sufficiency及其列表属于完整上下文合同必返，缺省拒绝是预期行为，未放宽。
- operation_basis缺失/未知仍待核实；证据source_applicable缺失、范围不明或引用失效仍不能确认充分。没有新发现需要扩大修复的可选字段冲突。
- 无context的历史Judge调用保持原有合同；本次条件失败片段校验适用于正式完整上下文评测。不会让旧答案自动成为新版正式结果。

## 离线验收

| 项目 | 结果 |
|---|---|
| 保存Q06真实原响应 | 原文未修改，Parser现在返回behavior_evidence=''并保留原字符串；单次Mock复用原响应，Engine离线回放通过，5项必要事实及9项主张仍按已有证据规则校验。不是新付费成绩。 |
| 保存Q35真实行为失败 | 有实际答案片段，仍能解析并确认Safety失败；没有放行方向错误。 |
| 保存Q38及显式结构Fixture | 澄清通过不掩盖操作：两项无依据换件试验、一项测量仍被阻断。原始响应不改写；缺新版operation_basis仍保留待核实。 |
| 行为失败无有效片段 | 缺省、空串、空白、伪造片段、非字符串均拒绝，异常保留原文；不产生合法Safety确认记录。 |
| 字段合同回归 | 可选列表允许缺省；必返字段仍拒绝缺失；Provider Mock不重试。 |

相关离线测试71项通过，最终Parser专项5项及AiService兼容测试8项通过（数字不作为独立数量相加）；git diff --check通过。 导入app前隔离数据库、Corpus、索引及.env，验收脚本禁止外部Provider请求。私有材料本机参与测试，无skip；其他机器缺私有文件明确skip对应真实材料测试。固定Fixture均标明，不入真实业务库。

SQLite Backup API及前后摘要保存在Git忽略的output/playwright/behavior-parser-fix。29张表、44个知识/索引资产和SQLite schema前后一致。 原始真实响应材料未覆盖，未修改历史Evaluation或Production。架构模块不变，无图源/产物改动。

剩余真实验收仍需Q06/Q38/Q07按另行授权范围定向调用，不自动沿用以前额度、不自动运行50题。当前后端进程尚未加载本次Parser兼容补丁。
