# Optimization Agent HTTP 400离线修复验收

2026-10-14，Ponytail full。真实Provider调用0、费用0；未生成Candidate、未启动Sandbox、未重跑Baseline。

## 1. 历史证据与结论边界

Baseline `EVAL-20261013151016199140`仍Completed 50/50，Overall 95.0、Gate 10/11、Bad Case 13。失败实验`EXP-20261013152412702521`当前有三条HTTP 400失败Trace，请求SHA均为`0b41dd56f0bed4cf70ff420af1d31909b4e314c88abfd513e0bb2ebda484a756`；旧失败/未知Usage不回填、不当0费用。

检查真实DB、已有请求产物及`.demo-logs`：**未找到该400的Provider响应正文**。原Provider已经读取并脱敏错误正文，但Optimization Agent仅保存str(error)；旧ProviderAPIError的字符串不包含正文，导致错误码和具体拒绝原因在Agent捕获链路丢失。这是已定位、可以修复的审计缺陷。历史400真正拒绝原因仍证据不足，不能用通用400猜测上下文超限、max_tokens或模型不支持。

隔离SQLite副本中重建原请求，不执行HTTP、不改真实历史；构造后的SHA与历史完全相同。修复后再次重建SHA仍一致，证明未改变Agent Prompt、请求参数或策略。

## 2. 真实请求核对

| 项目 | 结果 |
|---|---|
| Model | deepseek-v4-flash |
| 消息 | 两个文本消息，system / user |
| temperature | 0.2 |
| stream | false |
| response_format | {type: json_object}；System明确要求JSON |
| max_tokens | 请求中未设置，不能伪造Provider默认输出量 |
| 顶层字段 | model/messages/stream/temperature/response_format，无不兼容扩展字段 |
| 请求体 | 5,774,935字节 |
| 消息字符 | 2,533,157 |
| Token粗估 | 935,605，字符比例估算，不是DeepSeek模型Tokenizer实测 |
| Bad Case输入 | 全部13个真实Bad Case，7个可信Confirmed作为目标 |

请求大头为bad_cases 852,029字符和all_bad_case_audit 1,596,496字符，存在大量重复携带。**大请求是值得下一次真实验证的风险，不是已证实的HTTP 400原因。** 本轮不猜测性裁剪真实答案/来源/证据，不改变目标或优化算法。

字符估算将ASCII按0.3、非ASCII按0.6推广为粗估，包含JSON符号等误差；仅观测，不据此截断/阻断调用。[官方Token估算说明](https://api-docs.deepseek.com/quick_start/token_usage/)给出英文/中文近似比例，并强调模型Usage才是实际值。

此前成功Agent `EXP-20261013065746494438`同样使用deepseek-v4-flash，真实输入822,754 Tokens、输出4,445 Tokens。旧成功调用完整请求体未找到，因此不能逐参数证明旧temperature/max_tokens/JSON模式与失败调用的差异；旧账本的agent默认配置16384不能代替该成功调用的真实请求。新的估算与旧的实际Usage也不能直接作精确差异结论。

已核对当前[官方Chat Completions接口](https://api-docs.deepseek.com/api/create-chat-completion/)：消息格式、temperature、JSON模式符合基础接口要求。网络中实际模型Token总量/默认输出窗口以及上游具体拒绝原因，离线检查无法确认。

## 3. 最小代码修复

- `providers.py`保留并解析脱敏HTTP正文：HTTP状态、Provider错误码、message、非JSON错误正文均可保存。实际API Key、Bearer凭据及authorization/api_key/access_token字段值脱敏；请求摘要不包含Headers、API Key、原始消息或带凭据URL。
- ProviderAPIError字符串包含具体错误码及详情；Agent返回的错误追加失败阶段和是否可重试，现有API/前端错误入口可以直接显示，无UI修改。
- `optimization.py`在调用前保存request_summary：模型、参数、角色、body_bytes、SHA、字符数、Token估算及方法、各Prompt字段大小。失败保存provider_error的脱敏正文、状态/码/详情、stage、retryable。
- 共用请求构造层本地校验model/消息为非空字符串、布尔开关、temperature为0–2有限数、显式max_tokens为接口支持的1–393216整数；非法请求先失败，不发HTTP。这是接口合法性校验，不是应用Token/费用预算，不改原参数或自动新增max_tokens。
- 400不可重试，503等按原有分类标记可重试；Agent没有新增自动付费重试。真实消息/评分证据/全部13题背景保留，可信目标仍只为7个Confirmed；One Candidate = One Explainable Hypothesis + Minimum Necessary Parameters、Search Space及根因验证保持。

未修改Golden/Corpus、Baseline/历史成绩、Judge Prompt或评分、Matcher/Policy、11 Gate、Regression及Candidate优化算法。历史错误不回填，新审计仅用于未来明确授权的新尝试。

## 4. 离线验证与保护

- 65项相关后端测试通过：HTTP正文/错误码/阶段/重试标记、HTTP API错误可显示、凭据脱敏、非JSON错误、非法参数零HTTP、冻结参数保留、Agent策略/Search Space/可信目标、Provider/PaidRun、Q38修复及自动恢复回归。
- 原失败请求SHA精确重建，两次重建一致；没有把粗估Token当作模型实测或费用限制。
- SQLite Backup API保存私有副本，29表逐行摘要对比全部一致；失败Experiment及三条Trace、50题Baseline和历史记录未修改。
- `git diff --check`、Python编译通过；私有请求、真实数据副本和审计位于忽略目录`output/playwright/agent-http400/`，不进入Git。

## 5. 是否可以重新生成A/B/C

**已具备本地预检及完整错误诊断的条件，尚未证明原400根因消失，也不能保证重新生成成功。** 下一步需要一次另行明确授权的真实Provider验证，取得真实错误正文或成功响应；必须保存新尝试审计并保护旧失败记录，不能自动重复相同失败请求。生成成功后仍须原Candidate Schema/Search Space/可信目标验证，本轮不自动启动Sandbox。
