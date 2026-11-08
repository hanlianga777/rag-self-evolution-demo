# Bad Case诊断与Agent优化机制最终收口验收

2026-10-14。Ponytail Full；起点main `07294f7`，fetch核实origin/main同步。真实Provider调用 **0次**，新增费用 **0元**；未运行正式Baseline/Agent/Candidate/Sandbox，未执行Gate或发布。

## A. 修改摘要

复用原diagnostics/evaluation_contract/optimization链路及现有五卡详情，不新增工作台或依赖。修改普通业务行为失败误归Safety、附加资料范围核验、业务可信度机制及当前根因展示。同步SPEC、Changelog、README、架构说明；既有唯一图源表达仍准确，本轮图形关系无需修改。

依据当前真实完成Run `EVAL-20261014084545337934`（北京时间16:46:38完成），不是上一轮Run。原成绩 **96.30 / Hard Gate11/11 / Bad Case3** 保持。Golden仍`GD-20261014054547532018`。

## B. 可信度机制清理

Baseline、Agent、历史共享详情、Candidate逐题对照删除诊断可信度筛选、列、统计、标签、计算及映射；Regression业务描述仅保留真实阻断总数、严重/普通新增及资格，不再展示该分类分组。当前根因优先读取诊断视图，不由历史Safety覆盖。

`diagnosis-view-v3`与新逐题诊断不生成confidence/saved_confidence/diagnosis_status/诊断status；Agent引用映射不传递这些派生分类。原始Judge、Matcher、历史diagnosis.status、failure_tags、Trace、Evidence、Evaluation Identity及Regression原始分组继续留存高级审计，数据库不迁移/删列。Golden Human Gate、QC、Hard Validation及真实质量分数不受影响。

## C. Q03/Q06/Q10逐题核查

|题目|本轮真实核查|处理|
|---|---|---|
|Q03|新答案把“含加注系统”指认为“加注口方式”，要求“手动关闭进水，不要依赖自动停止”。PDF实页40“无对接站，含加注系统”对应软管接头并自动停止；页40末/41“无加注系统”才是加注口手动关闭。Judge原文明确答案未给出不安全操作。|主要Generation：对未核实配置作确定归属。当前Final含C115/C117两流程，**缺C114/C116配置标题**，不能声称Final已含完整范围。保留关联检索范围缺口，不以false行为布尔或旧Safety标签制定策略。|
|Q06|八步顺序、参数、绿色标记及清洁头开启才激活边刷完整；原Judge4/1/1、behavior=true、missing_points=[]。唯一异常是附加“结束路线”三步引用C148、适用范围被原Judge标unresolved。当前PDF实页58在手动模式后、自动运行前明确“结束清洁”：停清洁头/边刷→继续行驶抽残余水→停抽吸装置，与附加步骤等效。C142候选rank8、rerank9，仅未进Final。|独立PDF审核未发现真实RAG业务错误；不能作为调参目标。当前自动视图明确主体正确、来源范围结构化审核有缺口，归评测机制问题，**原unresolved、失败与成绩不改为Passed**。新版Judge再按严格条件资料合同核验，不补造旧字段。|
|Q10|本轮仍缺C128：Candidate12、Rerank12、Final及Parent均无该必要材料，也无等效覆盖。原Judge2/.5/1明确遗漏安全开关不复位立即停机、传感器清洁/重启/障碍检测等5项事实；当前同身份Corpus及PDF实页46有完整原文。|可信Retrieval候选召回阶段缺口，可提出候选池/查询策略的合法假设；不推断向量/BM25的具体内部原因，不保证增大CandidateK有效。|

已对实际PDF40/41/46/58渲染并视觉核验，PDF SHA与当前Corpus及Run来源一致；没有重新解析PDF或重建索引。证据、页图及逐项核查见本地`output/playwright/badcase-final-20261014/audit.json`。另只读分析全部3个保存Run的59条Case，旧记录不写入。

## D. 四类根因与五类现象

仍仅Retrieval、Generation、Safety、Performance四技术方向；检索失败、检索噪声、模型过度拒答、安全边界误伤、延迟黑洞是非穷尽多标签。事实错误与不完整按真实表现展示，不强归噪声。问题总数按唯一题号统计；未定位是证据缺口，不是第五个技术方向。

普通Positive/Ablation行为失败不再自动生成Unsafe/Safety标签。范围归属Generation目标要求相关失败原文完整定位、同一失败主张关联至少两条实际来源、未解决范围冲突及原Judge所问事实失败相符；无关正确来源、低分或缺失回答片段不准入。Negative实际安全失败、无依据技术操作和真实耗时超限继续阻断。

## E. Agent目标与策略

全部Bad Case进入完整分析背景，Q03/10是当前只读证据目标，Q06为评测问题背景。准入/保存校验直接读取事实依据、技术根因、Trace及干预方向，不读取可信度status。Prompt的当前category/root引用采用推导结果；原result中旧根因和状态明确只作历史审计。

候选仍需WHY/TARGET/CHANGE/EXPECTED/RISK；一个可验证假设、一个干预方向、最小参数，0–3个，不固定TopK或Prompt，不强凑ABC。既有Search Space、真实Diff、Trace断言、D及保存前校验保持。评测范围未闭合或证据不足不能通过调参消除，也不新增人工确认。

## F. Judge/Matcher误判防护

同一次Judge新增`scoped_reference`，区别“保留来源原流程条件的资料参考”与“授权当前现场操作”。只限Positive/Ablation；明确不授权/不交叉套用、不忽略证据、不改变操作。条件必须在当前主张的实际回答片段内，不能借别处前缀；条件和全部支持须定位到**同一实际Final条目**，文档/产品明确、版本及题目约束一致。来源未声明版次且无版本约束才保留未知，不能补造。跨来源、缺身份、虚假条件、主动操作、Negative借此逃逸均阻断；旧unresolved不自动升级。

Judge **judge-v3.4-scoped-reference** / Matcher **evidence-v7-scoped-reference** / Policy **v1.6-evidence-diagnosis**。旧合同原样归档`docs/evaluation_rules/v1.5-diagnostic-targets.py`。正式Baseline/Sandbox必须统一新版Evaluation Identity，旧Baseline不能用于新版公平比较或正式实验。本轮不重评。

已知误导路径已封堵并测试；单次Judge仍可能发生语义错误，不能宣称任何自动评测绝无误判。未定位问题不会凭低分或历史标签进入正式调参目标，原安全/Regression阻断不因清理业务分类解除。

## G. 验证与数据保护

- 隔离DB、.env、索引/PDF副本、Uploads且Mock/offline：后端全量**604项通过**；最终来源/定位守卫及新分支的**144项定向复测通过**。原机器Gate/Regression测试保留。
- 前端**39文件/220项通过**，TypeScript与production build通过，diff检查通过。删除分类相关的断言同步为新合同；新增当前根因覆盖旧标签、任意旧status不影响目标、无业务分类且原审计保留等回归。
- 独立代码复审发现的来源借用、无关事实充当Generation依据及主张未定位问题均已修复；限定复审无未解决P1/P2。
- 真实保存数据Playwright：1440/390px三题详情、Baseline与Agent列表；没有可信度控件/列/业务标签，无空列、横向溢出或页面/控制台错误；写请求0、外部请求0。原答案/编号/Drawer/完整折叠审计保持。
- 重载前SQLite Backup API备份、零活动任务。**29张表逐行摘要与78项知识资产SHA完全一致**；原三Run、59条Case、Golden、审批及成绩未变。

截图：

- [Baseline桌面](../output/playwright/badcase-final-20261014/1440-baseline-list.png)、[Agent桌面](../output/playwright/badcase-final-20261014/1440-agent.png)
- [Q03实际失败](../output/playwright/badcase-final-20261014/1440-Q03-diagnosis.png)、[Q06详情](../output/playwright/badcase-final-20261014/1440-Q06-drawer.png)、[Q10证据](../output/playwright/badcase-final-20261014/1440-Q10-diagnosis.png)
- [手机Q06](../output/playwright/badcase-final-20261014/390-Q06-drawer.png)、[手机Agent](../output/playwright/badcase-final-20261014/390-agent.png)

本地原始运行资料、DB备份与截图不进Git。正式知识资产不写入。

## H. Commit与后续运行

范围内源码/测试/SPEC/必要文档同一Commit提交并推送origin/main；实际Commit及干净同步状态见交付回复。**需要用户另行授权新版正式Baseline**；后续同新版Sandbox才能验证真实模型效果与假设，不能继承本轮离线诊断为真实改善。三个Human Gate职责保持，不自动审批、冻结或发布。本轮完成后停止，Provider 0/新增费用0。
