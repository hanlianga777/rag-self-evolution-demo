> 后续V1.2.1最小补丁及真实验证发现见[EVALUATION_POLICY_V121](EVALUATION_POLICY_V121.md)。下文保留V1.2交付时事实。

# 16题审计后的评测规则修复验收

依据：真实Baseline `EVAL-20261011142700759144` 的16条保存记录。Ponytail full；仅Evaluation Engine、Evidence Matcher、Judge合同、必要诊断及相关测试/规范。没有修改前端、Golden、Corpus、11Gate阈值、Regression、Agent或发布逻辑。

## 修复结果

| 通用问题 | 最小修复与限制 |
|---|---|
| HTML伪事实 | HTML实体解码和标签清理先于分句，过滤无内容片段；Q11不再产生`</sub>`事实，原Golden不改。 |
| 差异与冲突混淆 | conflict记录status/scope/reason/support；只有resolved且两处实际上下文引用可核实才解除该冲突阻断。非结构化历史备注、未解决范围或伪造引用仍unknown；不删除冲突审计。 |
| Unsupported Claims一刀切 | 单次Judge逐项claim_reviews：有来源事实、合理安全建议、无依据具体操作、矛盾、未核实。答案片段须定位、来源须真实存在。合理建议需警告依据且changes_operation=false；新测量/换件/试验/技术参数/复用条件不得借安全建议放行。原UC与新审计分别保存。 |
| 技术方向错误 | Prompt核验上下限、否定、单位和对象；critical技术矛盾不允许correctness>2或faithfulness=1，不一致JSON拒绝，不悄悄改分。不用词面规则自动断言事实对错。 |
| Negative后续指导 | 主拒答/澄清正确不免除逐项回答审计；定位的无依据具体操作/矛盾仍失败。Anchor仍not_applicable；行为失败必须有答案片段才确认归因。 |
| 根因过度确认 | 不再以充分性非空确认；未知不默认Retrieval。有定位的回答错误归Generation，行为错误Safety优先，实测超限Performance；候选/最终上下文明确均空且证据不足才确认Retrieval。无法判检索或上下文选择遗漏保持Unknown/needs_review。 |

版本：`judge-v3-claims` / `evidence-v3-scoped` / `v1.2-grounded-diagnosis`。Evaluation Identity随新版本变化；旧Baseline、Candidate、历史回放不能继承新版资格或跨尺比较。JSON增量存储复用现有字段，不迁移业务库。仅修改共享评测规则，业务/技术组件边界不变，未修改架构图源或导出产物。

## 16题回归覆盖与未解决争议

保存题目、答案、Final/Candidate Trace及旧Judge均从只读SQLite提取。私有材料仅存Git忽略的`output/playwright/evaluation-policy-v12/`；其他机器对应测试明确skip。每题均走离线Engine/Matcher并验证旧Judge未被修改，缺新版结构化主张时不自动通过或确认，不输出新版真实成绩。

| 保存题目 | 本轮覆盖；仍需真实新Judge验证的内容 |
|---|---|
| Q02、Q32 | 孤立“完成”按钮的流程归属、无依据具体步骤与来源缺口分开；不强推原Retrieval根因。 |
| Q06、Q20、Q24、Q30、Q42 | 保守安全/澄清建议与具体操作条件区分；不预设这些题应通过，新增维修/复用条件不能自动视作安全建议。 |
| Q07、Q10、Q13、Q16 | 历史冲突备注保持待核实；有真实引用/适用范围的resolved结构可解除阻断；最终语义须新Judge验证。 |
| Q11 | 保存HTML参考答案的清理分句；旧Judge中伪事实标签不回填为新版通过。 |
| Q22 | 型号范围与冲突来源定位，历史Judge冲突引用倒置不能用于确认根因。 |
| Q27 | 从排除障碍物扩展到手动清洁是否改变操作条件，仍未得到新真实Judge结论。 |
| Q35 | 保存“不得低于”与来源“请勿超过”；方向矛盾Fixture及矛盾评分JSON拒绝检查，不预设历史原评分/根因应保留。 |
| Q38 | 负向澄清之后的换件/测量指导仍审计、仍可能失败，不以Behavior Pass放行。 |

离线分类只验证合同、引用与防误通过守卫。真实Judge是否正确识别范围、合理建议及方向性仍未执行；同义表达的逐字引用定位、未声明型号范围与不完整源步骤仍可能导致待核实。

## 验证与保护

隔离后端兼容测试400项通过（完整测试运行期间仍有最后的引用校验细化）；最终相关测试81项通过，私有材料路径调整后10项专项再次通过且无skip。以上不是相加的独立测试数量。隔离在导入app前设置DB/Corpus/索引/.env，禁用外部Provider请求。`git diff --check`通过。

真实SQLite Backup API备份及前后逐表摘要、知识/索引/PDF/上传文件哈希存于忽略目录。29张表内容、44个受保护文件以及SQLite schema前后一致；备份、私有逐题数据与测试日志不入Git。

原Baseline的50条记录、16题失败、已确认6/待核实10、98.90及11/11均保留原样。运行中的后端没有重启，本次源代码版本不等于当前进程已加载；没有Provider请求、真实重评/回放、Agent或人工Gate。

## 小范围真实Judge验证条件

代码具备离线验证后的选样验证条件，**真实语义效果未验收**。后续须用户明确授权费用和范围，并受控加载新版本；可用隔离副本中的少量保存答案/完整上下文只调用一次新Judge验证分类与引用，不生成RAG回答、不冒充正式Baseline。现有回放接口为完整Run，本轮没有新增小范围API或自动发起调用。

建议选样覆盖HTML、已解释差异、安全建议、方向错误、Negative后续具体指导；不得预设通过数量。历史结果不覆盖，小范围验证也不能代替新的正式同尺Baseline。
