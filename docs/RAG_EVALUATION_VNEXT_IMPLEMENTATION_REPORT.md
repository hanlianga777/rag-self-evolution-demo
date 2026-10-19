# RAG Evaluation VNext 统一修复实施报告

日期：2026-10-20（Asia/Shanghai）。模式：Ponytail Full；代码实施、隔离离线验收及本地只读 Smoke Test。

本轮完成二元业务合同、证据定位、技术诊断、Agent准入、Regression、有限恢复和必要UI调整。没有调用真实Retriever、Generation或Judge重新评测，没有写入正式成绩、修改冻结Golden、审批或发布。本报告的157/43是独立业务基准及显式测试响应的程序验收结果，**不是新版LLM Judge的真实成绩**。

## 1. 实施依据、范围与修改文件

依据当前SPEC、原全面审计、200条独立复核、验收矩阵、VNext草案及Owner本轮指令。原四份审计/草案文件保留原字节，随本轮纳入版本控制，不回填历史数字。开始源码为`0ee1d5ef9857decfe07f68ace5fc6fa1a753d1fe`。

| 范围 | 实际文件 |
|---|---|
| 合同、Matcher、比较 | `backend/app/evaluation_contract.py` |
| 评分、执行恢复与Sandbox | `backend/app/evaluation.py` |
| 技术证据链、Agent准入 | `backend/app/diagnostics.py`、`backend/app/optimization.py` |
| 单次Judge与请求时限 | `backend/app/providers.py`、`backend/app/knowledge_pipeline.py` |
| Generation、来源图例与范围 | `backend/app/ai_service.py` |
| 新Revision来源与Case幂等 | `backend/app/governance.py` |
| 现有页面表达 | `frontend/src/pages/EvaluationPage.tsx`、`EvolutionPage.tsx`、`OverviewPage.tsx`、`frontend/src/components/EvaluationDiagnosis.tsx` |
| 新专项验收 | `backend/tests/test_evaluation_vnext.py`、`backend/tests/fixtures/rag_200_vnext_review.json`、`scripts/verify_evaluation_vnext.py`、`frontend/src/evaluation-vnext.test.tsx` |
| 恢复合同对应旧测试 | `backend/tests/test_baseline_resume.py`、`test_candidate_resume.py`、`test_evaluation_autorecovery.py`、`test_judge_q38_format.py` |
| 当前合同及说明 | `docs/RAG_SELF_EVOLUTION_SPEC.md`、`docs/SPEC_CHANGELOG.md`、`docs/EVALUATION_POLICY_V121.md`、`README.md`、本报告及`docs/superpowers/plans/2026-10-19-evaluation-vnext.md` |

未修改依赖、数据库Schema、11 Gate定义/阈值、知识资产或正式架构图节点关系；没有新增Agent、一级导航或Drawer尺寸。新实现文件的`git diff --cached --check`通过；纳入版本控制的原始全面审计含引用回答的Markdown行尾空白，按原文SHA保护保留，未为消除格式警告改写历史证据。并行存储清理任务产生的文件及`verify_self_evolution.py`既有修改不纳入本轮提交。

实际按合同→Matcher→诊断→Agent→比较→Prompt→UI→200条→全链路的顺序实施；发现共享根因后补最小回归测试并修复，没有按题号修改生产逻辑。

## 2. 当前版本合同

| 内容 | 新身份 |
|---|---|
| Judge | `judge-vnext-1` |
| Evidence Matcher | `evidence-vnext-1` |
| 业务评分合同 | `business-vnext-1` |
| Generation安全边界 | `generation-vnext-1` |

新Identity保存Judge Prompt SHA、Generation版本/边界SHA、Golden/Corpus、模型请求配置、Gate和恢复限制。旧身份不回填，新旧合同不能混用实验。SPEC文首明确覆盖冲突旧条款，下文历史记录继续保留。

完成的业务判断只有PASS/FAIL。来源损坏、解析、超时、Worker失联等保留执行异常，不制造业务FAIL或Agent目标；不完整评测不能获得正式资格。quality连续指标继续独立供11 Gate使用，不替代业务判断。

## 3. 简化了什么

新版正式路径取消逐句七类Claim强制分类、题型互斥和重复布尔判分；不按Golden换行、标点、指定Chunk逐字要求覆盖。Judge只需核心`verdict/checks/issues/reason`及既有Gate所需quality。

复用同一次Judge提供语义覆盖、诊断证据与新旧问题对应，没有增加审核Agent或额外Judge请求。历史解析函数保留用于旧响应及既有工具兼容，不能作为新版业务通过条件。无新的依赖、队列、迁移或整仓备份。

## 4. 保留的安全和来源约束

- 真实完整Final定位，支持Parent及matched_child_ids；多个不连续原文必须分别引用。
- 只规范显示层Markdown、Unicode、转义及已知装饰符；不模糊匹配数值、单位、否定、型号或安全条件。
- 来源S图例在生成与Judge侧共享；产品/版本约束保留。错误产品可作为失败反证，不能作为适用事实的通过证据。
- 必要断电、整机关机、隔离、电池安全等按实际操作核验，不能以无关安全套话代替。
- 未明确接口、介质、型号或安全条件不能转为当前可执行步骤；正确拒答后的危险操作仍FAIL。
- 诊断必须验证实际回答、适用规范、完整Final、候选Trace、Canonical内容及Corpus身份，不能只凭ID或标签推断。
- 不自动批准、冻结、推荐Winner或发布；原人工Gate及Regression阈值保留。

R1/R3范围仅利用已保存的独立型号标题块，为新调用附加可核验的标题来源、原句和页码。读取检索当次固定的Corpus快照，避免新旧活动索引漂移。跨范围Parent或缺少明确标题时不猜，旧Chunk/Final/索引完全不改。

## 5. 200条离线验收

只读访问真实`backend/data/demo.db`，使用`mode=ro`、`query_only`和只读事务。逐项核对Run+Question唯一性、冻结题目、原答案SHA、完整Final SHA及原passed；没有调用Retriever。

| 组 | 保存Run ID | 独立基准PASS | 独立基准FAIL |
|---|---|---:|---:|
| BL | EVAL-20261015140115663135 | 37 | 13 |
| A | EVAL-20261015153348988021 | 41 | 9 |
| B | EVAL-20261015162452484736 | 40 | 10 |
| C | EVAL-20261015171658194453 | 39 | 11 |
| 合计 | 200个唯一Run+Question | **157** | **43** |

Owner未决为0。B/Q36=FAIL单独记录于版本化fixture的`owner_decision`，绑定完整Run、题目ID、答案与Final哈希及裁决来源。旧报告157/42/1、原Judge、Usage和旧状态没有改写。

两层验收明确分开：

1. 真实记录完整性、来源定位、解析、诊断与比较规则验证。
2. 显式标注的结构化Judge测试响应，经真实Provider Parser和Runner评分入口离线处理；`complete`仅返回测试响应，外部请求被禁止。fixture中的quality为合成测试值，不是新质量得分；程序不据此重算历史Gate或授予资格。

可复核命令：`python3 scripts/verify_evaluation_vnext.py`。生产代码不导入该fixture/脚本，不读取验收矩阵评分，不包含Q编号或Run特判。

## 6. 新旧逻辑主要差异与H01—H15对应

| 审计项 | 本轮解决方式 |
|---|---|
| H01 | 业务二元判断与执行完成状态分离；消费者使用版本化outcome |
| H02/H10 | 统一必要事实/行为检查，取消P/A与Negative合法边界说明的旧互斥 |
| H03 | 有限显示规范化及连续原文片段验证；保留严格旧响应兼容 |
| H04 | 生成与Judge共享实际文档S图例 |
| H05 | 原子必要事实交给Judge理解，不以逐句同文作为通过条件 |
| H06/H07 | 完成业务FAIL后按真实规范与候选/Final证据诊断，未知范围不强准入 |
| H08 | 后续Revision/更新在既有Validator边界同步来源派生字段，不回填Frozen |
| H09 | 二元翻转、持续失败新问题、严重性升级和不完整比较统一阻断 |
| H11 | 从固定Corpus已有标题附加只读范围说明，缺证据不猜 |
| H12 | 原页面区分旧技术诊断、业务失败、执行异常与新合同目标 |
| H13 | 每题每Provider阶段最多3次、总600秒；Schema最多1次纠正占用同一额度 |
| H14 | 同一SQLite事务内验证重复Case等内容幂等、不同内容拒绝，无Schema迁移 |
| H15 | 新规则版本与Prompt/Generation摘要进入Identity；供应商不可变revision仍未采集 |

Evidence充分性与答对分开：Final已有充分证据而生成漏答，仍为业务FAIL和Generation问题，不能把“回答错”显示成“Final不足”。

## 7. Bad Case与Agent验证

在200条显式测试响应下，BL技术准入准确得到12题：Q04/Q06/Q07/Q08/Q15/Q17/Q24/Q27/Q28/Q29/Q39/Q42。题号只存在验收资产中。

- Q04/Q06/Q08/Q27按证据阶段归Ranking/Context Selection。
- Q07/Q17/Q24/Q28/Q29归Retrieval；Q15归Generation；Q39/Q42归Safety。
- Q13为正确等价事实，不再作为确认检索目标。
- Q22保持业务FAIL，但旧来源型号范围尚未闭合，不强行交给参数Agent。
- Q07在BL/A/B/C分别为Retrieval/Ranking/Retrieval/Retrieval，证明相同业务缺陷按各自Trace归因。

通用测试还覆盖：伪造Canonical/Corpus、缺规范、坏候选引用、未完成执行、未定范围均不准入；真实阶段延迟才能支持Performance。Agent沿用原Search Space、单主要假设和必要联动校验，允许零候选，不为凑A/B/C制造目标。

## 8. A/B/C离线比较

| 组 | 真正修复FAIL→PASS | 新增失败PASS→FAIL | 持续失败新具体错误 |
|---|---:|---:|---|
| A | 4 | 0 | Q15与Q17 |
| B | 6 | 3（含Owner确认Q36） | 未额外记录持续FAIL新问题 |
| C | 3 | 1 | 未额外记录持续FAIL新问题 |

A/Q15遗漏不同的操作安全内容，A/Q17把R1确认条件套用R3，单列为持续FAIL中的新缺陷，没有增加“新增失败题”数量。fixture保留原题严重性，另标已证实安全边界；不为了演示阻断而把普通问题伪造为critical。

## 9. Regression与资格验证

原门槛严重新增=0、普通新增≤1不变。新增失败同时核验题目原严重性和Judge确认的问题严重性；普通题新增危险操作也必须计入严重新增。已由先失败后通过的Sandbox资格反例验证。持续FAIL内**新的critical问题或严重性升级**额外阻断，不被题目失败数掩盖。通用合成反例已验证新增失败题为0仍可被新增严重操作风险阻断。

Candidate同次Judge读取Baseline findings：同一问题提供旧索引及理由，新问题明确null。缺失或无效对应使比较未完成、不能取得资格；仅措辞不同不制造新增严重错误。旧严重问题换一种说法不算新风险，普通升级严重仍算。

200条离线结果不授予A/B/C资格，不覆盖旧Regression，不选Winner；连续质量测试值也不能代替真实Hard Gate。

## 10. 专项与自动化结果

以下结果以本轮最终命令日志为准；开发中的失败用例修复后重新运行，没有skip、删除失败测试或降低业务安全断言。

| 验收 | 结果 |
|---|---|
| 200条只读身份/哈希/Parser/Runner/诊断/比较 | 200通过；157/43；0 Provider调用 |
| VNext专项（包含继承复用的合同测试） | 61通过 |
| 后端隔离全量 | 693通过，0失败/错误，885.006秒；最终安全计数补丁另经下项140测试复验 |
| 最终安全计数修复后受影响后端专项 | 140通过，0失败/错误 |
| Revision/来源同步专项 | 59通过，旧Snapshot保持 |
| 固定Corpus及相关专项 | 109通过 |
| 前端Vitest | 42文件、240测试通过 |
| TypeScript及Vite生产构建 | 通过 |
| 本地关键API GET | overview/evaluation/optimization/pipeline/versions均200 |
| 页面只读Smoke | Baseline旧合同标识与Agent旧实验保护已核验 |

十类通用规则均有显式Judge响应和程序反例：同义正确、型号不能混用、断电条件、合法范围声明、无依据操作、Negative拒答、拒答后危险操作、等价Final、无Final不能可信PASS、格式差异。另覆盖连接介质歧义、急停复位/冷启动、多路线、未知液体、持续FAIL严重风险、Unknown/Stop、原始Owner裁决保护。

恢复测试证明：成功生成复用；超时/暂态最多3次；结构错误最多2次；阶段600秒截止传递至DeepSeek和Embedding/Rerank请求；Unknown Usage及Worker未知执行停止，不自动重发。原恢复测试按本轮明确替代旧无限恢复合同更新断言。

复核命令：

```sh
python3 scripts/verify_self_evolution.py
python3 scripts/verify_self_evolution.py test_evaluation_vnext
python3 scripts/verify_evaluation_vnext.py
cd frontend
npm test
npm run build
```

后端运行前已通过隔离脚本设置临时DB、Corpus/索引、空.env及Mock配置，并禁止外部URL请求。不会将真实DB当测试库。

## 11. 数据、磁盘与本地服务保护

29张表的完整行数及逻辑SHA与实施前一致；16项manifest知识制品、4个PDF来源SHA一致。200条原答案/Final逐项一致，四份历史审计/草案SHA一致。Golden配额20/10/20、原11 Gate文件未改。

服务修改前核对无运行中的评测、Golden、Revision或实验；只对8010后端子进程发送受控TERM，由原有supervisor重启，5174仍由原前端服务提供。最后后端监听PID64259、前端PID61408；API明确返回`requires_policy_upgrade=true`，旧成绩仍显示旧合同，未被离线数字覆盖。

本轮只在临时目录使用一份SQLite Backup API服务前备份，不做整仓或重复大库备份，不安装依赖。隔离测试临时制品自动释放，服务后完整性验证通过后删除该临时备份。未清理其他任务或既有历史文件。

## 12. 仍存在的限制

**没有发现未解决的程序验收阻断；新版真实LLM语义能力尚未通过Provider验证。**

部分既有异步API测试在临时库释放后打印后台线程SQLite收尾异常，测试断言汇总无失败/错误；这是隔离Fixture线程收尾的验证限制，不代表正式数据库损坏。29张正式表另行完整指纹核验，未变更。

- 测试响应表达独立业务复核，不证明真实Judge必然输出157/43或穷尽所有必要事实。真实同义、漏安全条件和范围理解仍需下一轮代表性真实验收。
- 供应商不可变模型revision尚未采集；请求模型、Prompt SHA和temperature不能证明服务端永不漂移或输出完全确定。
- 标题范围适配只覆盖已有明确独立标题；复杂层级/跨范围Parent继续保守，不冒充完成Knowledge重建。若修改知识制品，必须新Corpus及兼容性检查。
- 冻结Golden旧派生字段、Ablation谱系及旧Q22范围缺口没有回填；后续新Revision同步不等于修复全部历史治理元数据。
- 新的语义对应、事实覆盖和critical判定仍依赖同次Judge；Parser只验证结构与片段，不凭空补判断。缺诊断证据会保守排除技术目标。

## 13. 正式Baseline是否需要重跑

需要。旧Baseline只读保留，不能沿用旧身份套用新成绩。新Prompt/Matcher/Policy/恢复规则必须创建新Identity，完整真实50题后才能形成新版Baseline与可信技术目标。本轮没有执行，也不将未来执行视为已获Provider授权。

## 14. A/B/C是否需要重跑

若要获得新版正式优化结论，需要基于新Baseline形成新实验/候选，并在同Golden、Corpus、模型和评测合同下完整Sandbox。旧A/B/C只是历史及离线对照，禁止直接续跑或覆盖。是否保留原优化策略要由新技术目标决定，不能为凑三组复制旧候选。

## 15. 下一轮推荐顺序及交付状态

1. 另行获得明确Provider/数据外发/预算授权，先选择少量代表性问题验证新Judge输出与安全语义；不以重试低分寻求漂亮数字。
2. 核验冻结Golden与当前Corpus兼容、服务和版本身份；如知识内容确需改，先按既有治理建立新身份。
3. 运行新版完整Baseline50，检查执行完整、真实Usage、11 Gate和业务FAIL证据。
4. Optimization Agent仅使用真实合格技术目标产生新候选，再按相同Identity执行Sandbox。
5. 检查修复、新增失败及持续失败新严重风险，形成资格和Recommendation；继续原人工批准/发布流程。

代码、SPEC和测试同一提交交付；Git及最终全量测试回执在收尾核验后记于下方。最终安全计数补丁是在全量套件启动后补充，另以补丁后140项受影响测试及61项VNext专项复验，记录两者范围，不混称为真实Provider验收。没有本轮真实Provider请求或新增Provider Token费用；本地开发/测试耗时不冒充模型成本。

## 最终交付回执

- 后端全量693项通过；最终安全计数修复后140项相关测试与61项VNext专项通过；前端42文件240项及构建通过。
- 200条基准及原始身份/哈希验证通过：157 PASS / 43 FAIL / 0未决；A/B/C修复及新增分别4/0、6/3、3/1。没有真实Provider调用。
- 最终服务已重载：8010后端PID64259、5174前端PID61408；五个只读API均200，旧评测身份被阻断用于新实验。
- 正式29表、16项知识制品、4个PDF、四份原审计SHA均保持；临时126MiB服务备份已删除。
- 本轮30个文件单独提交并推送`origin/main`；代码与SPEC同一提交，最终Commit SHA见交付回复及Git记录。其他任务的未提交文件原样保留，不能把整个共享工作区称为干净。
- 真实LLM语义尚未验证；下一轮正式Baseline及新候选Sandbox需要另行授权，不自动沿用历史Provider委托，不自动发布。
