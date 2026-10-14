# Bad Case自动诊断、Agent衔接与详情UI验收

2026-10-14，Ponytail Full。起点main `9c84a08706c9b757dd7c0f6a9771caa21f697163`，开始时fetch核实与origin/main一致。真实Provider **0次，新增费用0元**。本轮没有运行正式Baseline、Optimization Agent、Candidate、Sandbox、Gate或发布；测试中的Stub/Fixture仅为离线功能验证。

## A. 修改范围及文件

- `backend/app/diagnostics.py`：复用原诊断链路增加证据驱动自动分析，视图v2；原保存状态/根因继续可查，当前分析独立展示。
- `evaluation.py`：新正式执行使用同一纯诊断函数；`evaluation_contract.py`及`providers.py`：安全拒答兼容与版本；`optimization.py`：全量背景、证据准入与保存校验。
- `frontend/src/pages/EvaluationPage.tsx`、`components/CaseAnswer.tsx`及`evaluation-workspaces.css`：仅Baseline详情五张业务卡与收起的完整技术审计。Agent共享旧详情不重构；`EvolutionPage.tsx`仅同步两处目标准入提示。
- 对应后端/前端测试及隔离Fixture；SPEC、SPEC_CHANGELOG、README、ARCHITECTURE、平台架构说明及唯一正式图源/导出同步。没有新增依赖，没有改Pipeline默认值、Search Space或11 Gate。

## B. 朋友方案对齐

实际核验Desktop项目资料中的《产品成果参考.zip》《视频截图.zip》及其已解压图，CRC均无错误；SHA/目录见本地`reference-provenance.json`。重点阅读视频`163515_809`五类Bad Case地图、产品工作机制和流程图，结合当前真实Baseline/Agent保存数据及CandidateWorkspace视觉母版。

保留Retrieval/Generation/Safety/Performance四方向与五类非穷尽现象；主流程仍为Baseline→全量自动分析→证据与假设→0–3 Candidate→Sandbox/Regression→Recommendation/Gate2。朋友演示中的业务结论和后台机制没有冒充本项目实测。未迁移其与当前SPEC冲突的规则。

## C. 当前三题真实保存数据验证

Baseline `EVAL-20261014055224093665`，Golden `GD-20261014054547532018`。

|题目|证据与判断|当前只读分析|
|---|---|---|
|Q03|KIRA无对接站、含加注系统；C115/实页40自动停止已入Final，模型却引用C117/页41手工观察关闭进水，并排除C115。已有可定位矛盾优先于召回现象。|Generation可信目标；保留原Confirmed及原未解决附属审计，不冒充全部事实都已解决。|
|Q10|Golden C127+C128；Candidate12仅C127，Rerank仍仅C127，Final4及完整Parent无C128的必要事实。C128当前同身份Corpus存在且同产品/来源；原完整上下文Judge不足结论、逐事实支持及missing_points相符。|Retrieval候选召回阶段可信目标；定位5项遗漏事实。不推断向量/BM25具体算法，也不承诺CandidateK增加有效。|
|Q18|真实拒答由Final C182高压/水喷射禁令支持；原Judge4/1/1、behavior=true。原唯一Pending是supported_abstention类型兼容，其他操作均有原文或保守安全建议依据。|evaluation_issue；不进入调参目标。原保存五条主张离线核验accepted5/pending0/confirmed0，未重评分或覆盖历史。|

原PDF资料第11/86页禁令及现有Corpus/原审计依据保留，未重新解析PDF、Embedding或FAISS。当前知识资产的完整哈希另作验证。

## D. Bad Case到Agent

全部Bad Case在同一个`diagnostic_view`/`automatic_analysis`中分析并保留完整答案、Golden/Final/Trace/Judge及争议背景；`all_bad_case_audit`不受目标过滤。没有可信目标时零Provider返回insufficient_evidence，并保存完整背景。

目标与引用映射、候选根因/Trace断言校验均使用证据推导结果，历史展示状态不单独准入。评测问题与证据不足不能作为正式目标。Q03/Q10可形成不同方向假设，每Candidate一个可验证假设/单一干预/必要参数，允许不足三个，不强凑ABC。D继续复用同一验证器。

## E. 误判防护与版本

Matcher `evidence-v6-safe-abstention`，Policy `v1.5-diagnostic-targets`，Judge仍`judge-v3.3-operation-scope`。旧规则原样归档`docs/evaluation_rules/v1.4-governance-outcomes.py`。Evaluation Identity已有守卫拒绝旧Baseline直接驱动新版正式实验或跨规则公平比较。

safe_rejection不能仅凭类型通过：原行为合同、完整且唯一主张审计、真实答案片段、实际Final来源、保守拒答支持、全部附加操作及缺证据范围须一致；无据操作、矛盾、遗漏安全限制、未知/缺失引用仍阻断。历史Pending只有确切的安全拒答兼容差异才能标记评测问题，不能因空审计消失而通过。

检索确认不靠ID遗漏或字面缺词：保存的完整上下文Judge语义审计与当前完整规范Child/Parent原文/产品/版本/来源身份、Corpus及产物SHA交叉绑定。Final篡改/Parent截断/同义新内容不允许套用旧Judge结论。缺少可信语义审计保持待核实。明确空候选/空Final的历史兼容分支拒绝running/failed等非完成Trace。

**需要另行授权运行新版正式Baseline**，之后正式Sandbox用相同新版规则。本轮未执行。三个人工Gate、11 Hard Gate、Regression严重新增0/普通≤1及Search Space全部保持。

## F. 前端详情与截图

五张白卡按案例结论、业务问题、预期与实际/差异、证据、诊断与优化方向组织，沿Golden Candidate Token和800px唯一Drawer；手机390px为全宽。具体错误片段、原文引文及遗漏事实可读；技术JSON、全部Trace/Judge/Matcher/Token及完整原答案默认折叠。

只在渲染层解析段落、数字/嵌套列表、Markdown与HTML；无危险HTML注入。保留小数/版本/章节、型号/页码、引用URL及替代文字。数字/项目列表显式恢复标记，未改数据库原答案。Agent历史列表仍展示保存的根因/可信度，不能把它误读为本轮新正式评分；详情明确区分当前分析与历史判定。

本地截图：

- [桌面Q03详情](../output/playwright/badcase-closure-20261014/1440-Q03-drawer.png)、[具体配置矛盾](../output/playwright/badcase-closure-20261014/1440-Q03-diagnosis.png)
- [Q10详情](../output/playwright/badcase-closure-20261014/1440-Q10-drawer.png)、[五项遗漏事实](../output/playwright/badcase-closure-20261014/1440-Q10-diagnosis.png)
- [Q18评测问题](../output/playwright/badcase-closure-20261014/1440-Q18-drawer.png)、[手机Q18](../output/playwright/badcase-closure-20261014/390-Q18-drawer.png)

## G. 测试与历史保护

- 后端全量 **596项通过**（DB、索引/PDF副本、uploads与缺省.env在导入前隔离；RAG_FORCE_MOCK=1）。首次空索引环境暴露旧Fixture不足，补齐可定位证据和真实临时回滚产物；正式资产未用于写入。最终Trace状态收紧后相关**31项复测通过**。
- 前端 **39文件/216项通过**，production build通过；测试输出中的既有act/嵌套警告不冒充页面错误。
- Playwright在真实保存数据上验收三题×1440/390px，共6种详情；默认折叠、列表标记、原始审计、Escape、背景锁定及零横向溢出通过。控制台/页面错误0，写请求0，外部请求0。架构由唯一图源及已保存GET Fixture离线导出。
- 独立代码复审发现并修复四项问题：同义Final与旧Judge绑定、多片段答案定位、安全兼容差异限定、HTML出处保留；限定复审无未解决P1。
- 重载API前SQLite Backup API备份。重载后**29张表逐行摘要完全一致，78项PDF/索引资产SHA一致**；Golden、20条人工审批、原Judge/Matcher/答案/Trace均未改。原Overall **96.20**、Hard Gate **11/11**、Bad Case **3**保持。保护证据见本地`protection-after.json`；原始DB/运行材料/截图不进Git。

## H. Git与停止点

所有范围内源码、测试、SPEC/文档与同源架构产物同一Commit提交并推送origin/main；实际Commit及干净同步状态在交付回复给出。本轮不生成真实Candidate、不评测、不执行任何人工Gate。离线规则修复不代表RAG模型效果已经改善。
