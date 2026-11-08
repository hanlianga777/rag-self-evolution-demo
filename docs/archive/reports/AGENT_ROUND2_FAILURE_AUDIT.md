# 第二轮Agent生成失败验收（2026-10-12）

## A. 具体失败Candidate

持久化 `agent_traces.id=8`，实验 `EXP-20261012054110446321`，2026-10-12 08:57:19 UTC，status=failed，failed_candidate_id=B，validation_stage=schema，错误“候选根因与可信目标不对应”。原始Provider文本和解析后的A/B/C均已保存。

DeepSeek成功返回结构化JSON；记录的请求耗时39.486秒，输入796287、输出4374、总800661 Token。界面约41.4秒属于整个操作耗时，不是网络超时。失败发生在本地根因校验，非Provider/JSON解析失败；候选只暂存于内存，第二轮未正式落库。

## B. 真实原因与证据

B的原始响应：root_cause=`Retrieval`，config_diff=`{"candidate_k":24,"top_k":6}`，target_bad_cases和root_cause_evidence均引用以下三题：

|目标Bad Case ID|保存的primary_root_cause / 可信度|保存诊断依据|
|---|---|---|
|BC-EVAL-20261012024220100135-V1G-050011728151-28-R060227052555-R074751575005|Generation / confirmed|答案“通常此处应为装回或拧紧密封盖”，实际上下文第7步为“拧开密封盖”，改变技术方向，无来源支持|
|BC-EVAL-20261012024220100135-V1G-050011728151-02-R055514738523|Generation / confirmed|答案新增“最后按下完成按钮”；孤立片段“4. 按下完成按钮”不能证明属于当前用户配置流程|
|BC-EVAL-20261012024220100135-V1G-050011728151-37-R060331318446-R074751753444-R134611725673|Generation / confirmed|答案新增“建议先小面积试清洁…”；最终上下文未支持该新增试验步骤|

B的hypothesis称部分幻觉来自“missing adjacent procedural steps at retrieval time”，why称这些目标在最终上下文缺少/含糊步骤，并用第一轮B的min_score过滤解释退化。这属于模型提出的因果假设，不能替代已确认诊断，也不能据此把Generation改标Retrieval。保存诊断对上述无依据新增操作有直接答案与来源定位，没有确认检索遗漏；Q28已有明确方向原文尤其不支持将其直接归为缺少检索步骤。

目标ID映射正确，全部属于当前Baseline的可信目标；不是读错题或根因数据映射错误。原Prompt虽提供完整Bad Case，但目标映射只列ID，没有明确root_cause必须取已确认根因，也未解释根因与参数干预的区别。模型根因标签错误与Prompt合同不明确共同导致此次失败。

## C. 最小修复

仅修改Optimization Agent输入合同与拒绝审计：

- target_reference_map显式提供primary_root_cause、confirmed可信度及结构化诊断依据；仍使用现有可信目标筛选，Unknown/needs_review不变成Confirmed。
- Prompt明确root_cause是持久化根因归属，必须符合所引用目标的根因集合；参数干预环节可不同。Generation案例可提出有答案/证据/Trace依据的检索干预假设，但不能把假设写成确认的Retrieval根因。
- 根因/根因引用拒绝审计补齐failed_field、actual_value、expected_type和allowed_values。原Trace 8不回填。
- prior_sandbox_results保留全部已有配置、假设、修复/新增退化、Regression、资格及状态字段，仅不重复发送执行checkpoints。检查点仍完整保存在数据库，避免无关执行审计反复占用Prompt。未做真实调用，不能宣称实际Token降幅。

不自动更正Provider输出，不自动重试，不固定下一轮参数。Judge、Matcher、Golden、Baseline成绩、第一轮候选参数/假设与结果、Gate、Regression、Production及预算均不变。SPEC/Changelog同步；组件边界与正式图源无变化，不新建图。

## D. Validator是否误判

**未发现这次拒绝属于Validator误判。** 现有校验检查声明根因与可信目标是否匹配，未要求Generation案例只能改生成参数。原B声明Retrieval而实际三个目标均为Generation，拒绝合理；因此保留原根因校验条件，没有取消或放宽。

保存原始响应离线重放仍准确拒绝B。另用内存反事实Fixture仅将B的根因声明改为Generation（原响应/历史数据库不改），保持相同检索参数，现有Validator可接受整个A/B/C；这证明它本就允许跨环节参数，不代表B的检索假设已证实或新候选会通过Sandbox。

## E. 手动生成条件与验收

**可以重新确认费用后，手动生成第二轮A/B/C。** 新Prompt可减少根因/参数混淆，但无法保证下一次模型一定输出合规方案；不合规仍应拒绝并保留审计，无自动重试。

27项离线测试通过，包括保存响应重放、根因拒绝字段、跨环节参数、Unknown排除、第一轮结果保留、身份与API生命周期。测试导入app前隔离DB/Corpus/索引/.env，并拦截真实urllib。真实库副本只在测试中产生模拟审计/候选，真实库未生成第二轮。

修改前SQLite Backup API备份；前后29张表内容摘要一致。第一轮A/B/C都evaluated且不合格，当前Sandbox预算5/12，失败Agent分析未增加Sandbox额度。原失败Trace、Baseline、候选与实验身份全部保持。本轮Provider调用0，Sandbox启动0。

确认无活动任务、新备份、索引无需重建后，8010工作进程10586→12194受控加载补丁，监督进程保留；只读workspace身份未变。保护备份、真实原始响应及测试日志位于忽略目录 `output/playwright/agent-round2-audit/`，不入Git；`git diff --check`通过。真实Provider新Prompt效果未执行。
