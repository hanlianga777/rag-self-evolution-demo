# RAG 200条历史回答独立复核报告

> 2026-10-19 · Ponytail Full · 统一修复前的验收标准草案。以下PASS/FAIL是对已保存回答的独立审计判断，不是重新运行Judge的成绩，不改正式Regression/Qualification，不授予候选资格或发布许可。

## 管理摘要

200条均已逐条核对完整回答、实际Final（含Parent展开）、冻结题意和适用PDF。建议 **157 PASS、42 FAIL、1项Owner裁决**。Baseline为37/13；A为41/9；B为40/9并有1项未裁决；C为39/11。旧Baseline的26个Fail中14条建议PASS、12条仍FAIL；旧24个Pass中Q39改为FAIL。没有以减少失败数量为目标，也没有将原始93.1等分数重新解释为本轮通过率。

已存数据证实的是原答案、Final、检索阶段、参数和原评分；“必要事实是否满足、额外操作是否越界”是本轮独立语义判断；B/Q36源文操作歧义需要Owner裁决。这三层不能互相替代。

最小修复方向：复用现有Judge与评测链，统一必要事实、来源适用性、二元业务结果及有限执行异常；删除逐句七类Claim的强制分类负担。不得新增审核Agent，不得修改题号规则、旧Golden或Gate来追求通过。

## 证据身份与方法

- 工作树HEAD：`0ee1d5ef9857decfe07f68ace5fc6fa1a753d1fe`；复用前轮报告 `docs/RAG_EVALUATION_FULL_AUDIT_REPORT.md`，SHA-256 `6f515bddb899f57d3b3f5d32906c470e811421e302b1d4c1e184caeddf041616`。
- Golden：`GD-20261015135415953347`；生成Run：`GGEN-20261015110926448917`；Plan：`PLAN-2e284ba3cc81d33dca08c279`；Corpus：`CORPUS-38c90d5628b68c76d53e`。
- 四组保存的Evaluation Identity相同：`1125dcba813c8264a9ca4c37d6a603320bbe93a6bf4f60259466dfd88f74e6c4`；Judge `judge-v3.4-scoped-reference`，Matcher `evidence-v7-scoped-reference`，Scoring `v1.6-evidence-diagnosis`。请求参数相同不证明供应商内部推理完全确定。
- 读取真实SQLite持久化内容，与上一轮导出7张核心表逐行相同；四组题目/参考答案绑定同一冻结50题，无重复/漏题/混组。按保存的候选、重排、Final追踪，未运行Retriever/Judge或任何Provider。
- 四PDF共157页；复用已核查原页，重点复看遥控器R1/R3、维护电气安全、路线连接条件及清洁剂方向。PDF只用于确认规范与来源范围，不能把未进入Final的规范倒灌成模型当时证据。
- 每个唯一Run+Question键、全部Final入口/Parent/PDF页、完整回答及Final SHA-256在[200条矩阵](RAG_200_CASES_ACCEPTANCE_MATRIX.md)。没有重复粘贴200份完整答案。

## 200条统计

| 组 | Run ID | 历史P/F | 本轮P/F/待裁决 |
|---|---|---|---|
| BL | EVAL-20261015140115663135 | 24/26 | 37/13/0 |
| A | EVAL-20261015153348988021 | 30/20 | 41/9/0 |
| B | EVAL-20261015162452484736 | 33/17 | 40/9/1 |
| C | EVAL-20261015171658194453 | 27/23 | 39/11/0 |

待裁决不计PASS，也不作为第三类业务Bad Case。现有已裁决199条中157P/42F；不得把未裁决排除后给候选颁发资格。O1若判PASS，总158P/42F；若判FAIL，总157P/43F。

## Baseline真实缺陷与技术准入建议

13道业务FAIL不等于13道可以直接交给现有参数Agent的目标。下表按实际证据链逐题建议；不以缺某个Golden ID直接归因。

| Q | 已证实业务缺陷/证据 | 技术阶段及建议 |
|---|---|---|
| Q04 | 只回答电池充电，漏室内存放/重量要求；C180含重量等价内容已在候选但未进Final。 规范：D1C00179, D1C00180, D1C00185。 | Ranking / Context Selection。可作为对应阶段的技术诊断建议；只有当前Search Space内存在同方向可证伪干预时才准入Agent。 |
| Q06 | 对接站拔插头不能替代整机关机/电池隔离，且漏湿手禁忌；相应证据已召回却未入Final。 规范：D1C00026, D1C00181, D1C00204, D1C00017。 | Ranking / Context Selection（安全遗漏）。可作为对应阶段的技术诊断建议；只有当前Search Space内存在同方向可证伪干预时才准入Agent。 |
| Q07 | 滤网四步正确，但漏关机与电池隔离；脱离对接站/拔站插头不能代替整机电源处理。 规范：D1C00026, D1C00181, D1C00191。 | Retrieval（安全遗漏）。可作为对应阶段的技术诊断建议；只有当前Search Space内存在同方向可证伪干预时才准入Agent。 |
| Q08 | 干布/不酒精等正确，但漏擦拭前断电和禁金属刷砂纸；DOC4 C32在候选未入Final。 规范：D4C00030, D4C00032, D4C00034。 | Ranking / Context Selection（安全遗漏）。可作为对应阶段的技术诊断建议；只有当前Search Space内存在同方向可证伪干预时才准入Agent。 |
| Q15 | Final已有按钮9及分项激活，却否认可单独启动清洁头，误把完整机组顺序当排他要求。 规范：D1C00140, D1C00141。 | Generation。可作为对应阶段的技术诊断建议；只有当前Search Space内存在同方向可证伪干预时才准入Agent。 |
| Q17 | 型号未确定却只给R1左侧灯，漏R3右DL；不能确认现场配对成功。 规范：D3C00015, D3C00025, D3C00010, D3C00023。 | Retrieval（型号确认）。可作为对应阶段的技术诊断建议；只有当前Search Space内存在同方向可证伪干预时才准入Agent。 |
| Q22 | 把R3两声和R1一声当同型号冲突并拒绝区分；真实PDF范围明确，当前片段上级型号缺失是重要成因。 规范：D3C00010, D3C00005, D3C00019, D3C00023。 | Knowledge范围信息缺失＋检索上下文；暂不准入参数Agent。先修知识/型号范围身份，不由单一生成Prompt或候选池参数假装解决。 |
| Q24 | 漏儿童保管、不得未稀释使用和溅眼/误食处置；C22未召回，C118不能替代。 规范：D1C00022, D1C00118。 | Retrieval（安全信息）。可作为对应阶段的技术诊断建议；只有当前Search Space内存在同方向可证伪干预时才准入Agent。 |
| Q27 | 未说明地图不自学习、轻微可接受/重大必须重教的完整边界；C96已召回但未进Final，泛避障不能替代。 规范：D1C00096。 | Ranking / Context Selection。可作为对应阶段的技术诊断建议；只有当前Search Space内存在同方向可证伪干预时才准入Agent。 |
| Q28 | 更换刷辊步骤正确，但只停清洁机组不足以满足整机关机和电池隔离。 规范：D1C00026, D1C00181, D1C00200。 | Retrieval（安全遗漏）。可作为对应阶段的技术诊断建议；只有当前Search Space内存在同方向可证伪干预时才准入Agent。 |
| Q29 | 没有B2不带电检查表五类核心检查；如实说Final不足不等于可答业务完成。 规范：D2C00056。 | Retrieval。可作为对应阶段的技术诊断建议；只有当前Search Space内存在同方向可证伪干预时才准入Agent。 |
| Q39 | 把仍装机且表面沾液当擦拭充分条件；未先排除液体不明。只对吹干限制已知水、末尾询问液体，不能撤销前面当前可执行擦拭授权。 规范：D2C00054。 | Safety / Generation。可作为对应阶段的技术诊断建议；只有当前Search Space内存在同方向可证伪干预时才准入Agent。 |
| Q42 | “禁止/避免：不含稀释剂…”反转成分禁忌；后文含则禁用虽正确，安全操作答案内部给出相反方向，不能当显示符号噪声。 规范：D1C00118。 | Safety / Generation。可作为对应阶段的技术诊断建议；只有当前Search Space内存在同方向可证伪干预时才准入Agent。 |

**技术诊断建议12题**：Q04、Q06、Q07、Q08、Q15、Q17、Q24、Q27、Q28、Q29、Q39、Q42。其分布为Ranking/Context Selection 4题（04/06/08/27）、Retrieval 5题（07/17/24/28/29）、Generation 1题（15）、Safety/Generation 2题（39/42）。没有从本轮数据证实性能不达标，不能新增Performance Bad Case。Q22另记真实业务缺陷及Knowledge范围问题；其上下文不足和产品上级信息缺失未解决前，不强行准入现有参数Agent。

这12题仍是审计建议，不是写入系统的Confirmed目标：检索/上下文阶段需完整适用事实、实际Trace和可用参数方向；生成/安全问题须独立生成策略假设，不能因为能改检索参数就改称Retrieval。严格单候选单方向；目标不满足Search Space时允许零候选。

原5目标再核验：Q04是C180已召回但未入Final（其中含重量等价事实），应改阶段为Context Selection；Q08也是C32已召回但未入Final；Q13在当前仓库清洁对象范围内有等价Final，移出技术目标；Q15、Q24分别保留生成错误与检索遗漏。补出的8题有逐题证据，不是把5简单扩成12。

## A/B/C独立业务对照

| Q | BL | A | B | C |
|---|---|---|---|---|
| Q01 | PASS | PASS | PASS | PASS |
| Q02 | PASS | PASS | PASS | PASS |
| Q03 | PASS | PASS | PASS | PASS |
| Q04 | FAIL | FAIL | PASS | FAIL |
| Q05 | PASS | PASS | PASS | PASS |
| Q06 | FAIL | FAIL | PASS | FAIL |
| Q07 | FAIL | FAIL | FAIL | FAIL |
| Q08 | FAIL | FAIL | PASS | FAIL |
| Q09 | PASS | PASS | PASS | PASS |
| Q10 | PASS | PASS | PASS | PASS |
| Q11 | PASS | PASS | PASS | PASS |
| Q12 | PASS | PASS | PASS | PASS |
| Q13 | PASS | PASS | PASS | PASS |
| Q14 | PASS | PASS | FAIL | PASS |
| Q15 | FAIL | FAIL | PASS | PASS |
| Q16 | PASS | PASS | PASS | PASS |
| Q17 | FAIL | FAIL | FAIL | FAIL |
| Q18 | PASS | PASS | PASS | PASS |
| Q19 | PASS | PASS | PASS | PASS |
| Q20 | PASS | PASS | PASS | PASS |
| Q21 | PASS | PASS | PASS | PASS |
| Q22 | FAIL | FAIL | FAIL | FAIL |
| Q23 | PASS | PASS | PASS | PASS |
| Q24 | FAIL | PASS | FAIL | FAIL |
| Q25 | PASS | PASS | PASS | PASS |
| Q26 | PASS | PASS | PASS | PASS |
| Q27 | FAIL | FAIL | FAIL | FAIL |
| Q28 | FAIL | FAIL | FAIL | FAIL |
| Q29 | FAIL | PASS | FAIL | FAIL |
| Q30 | PASS | PASS | PASS | PASS |
| Q31 | PASS | PASS | PASS | PASS |
| Q32 | PASS | PASS | PASS | PASS |
| Q33 | PASS | PASS | PASS | PASS |
| Q34 | PASS | PASS | PASS | PASS |
| Q35 | PASS | PASS | PASS | PASS |
| Q36 | PASS | PASS | OWNER | PASS |
| Q37 | PASS | PASS | PASS | PASS |
| Q38 | PASS | PASS | PASS | PASS |
| Q39 | FAIL | PASS | PASS | PASS |
| Q40 | PASS | PASS | PASS | PASS |
| Q41 | PASS | PASS | FAIL | FAIL |
| Q42 | FAIL | PASS | PASS | PASS |
| Q43 | PASS | PASS | PASS | PASS |
| Q44 | PASS | PASS | PASS | PASS |
| Q45 | PASS | PASS | PASS | PASS |
| Q46 | PASS | PASS | PASS | PASS |
| Q47 | PASS | PASS | PASS | PASS |
| Q48 | PASS | PASS | PASS | PASS |
| Q49 | PASS | PASS | PASS | PASS |
| Q50 | PASS | PASS | PASS | PASS |

| 候选 | 真正修复BL失败题 | 相对BL新增失败题 | 原指定目标复核 |
|---|---|---|---|
| A：candidate_k 12→24 | Q24、Q29、Q39、Q42（4） | 无新增失败题；见下方同题新缺陷 | Q24修复；Q04未修；Q13原本不成立，不计修复 |
| B：top_k 4→6 | Q04、Q06、Q08、Q15、Q39、Q42（6） | Q14、Q41（2）；Q36未裁决 | Q04/Q08均修复；旧目标修复计数1遗漏了Q08业务改善 |
| C：Abstention→Grounded | Q15、Q39、Q42（3） | Q41（1） | Q15确实修复；旧目标修复计数0与本轮语义判断不同 |

A有真实改善，检索池扩展后Q24 C22、Q29 DOC2 C56进入Final并被正确利用，有与干预相符的检索链证据。Q39/Q42最终表达改善不能仅凭单次前后结果归因于candidate_k，模型输入变化/生成差异都可能参与。A/Q15仍失败但缺陷变化：BL错误否认可单独开启，A指出入口却漏最终重新握紧安全开关；A/Q17补回R3右DL后，又新增把R1一声开机泛化到R3的错误。这些不是“新增失败题”，却是必须保留的新增具体错误；Q15涉及安全开关功能前提，Q17涉及型号操作确认，不能称A完全没有新增风险。

B有真实上下文改善，Q04 C180、Q06 C26/C17、Q08 DOC4 C32进入Final，解释top_k扩展的合理作用；Q15/Q39/Q42表达改善只有观察相关性，不能作确定因果。B/Q14将冷启动步骤无条件套入急停复位，B/Q41将多路线条件泛化，均为原历史Pass漏判；前者是新增操作流程错误，后者是场景适用错误，不因开头正确拒绝P12具体坐标而豁免。Q36若Owner判FAIL，B新增失败题增加为3，净失败数减少由4变为3。

C的Q15清洁头入口/最终安全开关、Q39不明液体停止边界、Q42成分方向改善与生成策略方向相符，但只有一次保存结果，不能证明策略稳定或每题因果。C/Q41新增条件泛化错误。Grounded不意味着所有可引用片段都可直接套用当前场景。

按当前已裁决题观察，失败数从BL13减少到A9、B9（另1未裁决）、C11。题目修复减新增分别为4、4、2；这不是同身份正式重算，不改已存候选得分/净收益，也不推出Winner。

### 原15条“新增失败”逐条复核

| 记录 | 本轮建议 | 核验依据与旧阻断含义 |
|---|---|---|
| A/Q12 | PASS | 完成任务报告查询与详情准确。 旧阻断：Evidence Pending Review；pending=supported_abstention / claim_classification_unverified。该阻断不构成本轮业务缺陷；按本行适用证据/完整性独立判定。 完整Final与身份见矩阵对应行。 |
| A/Q30 | PASS | 红杆向右与后续条件正确。 旧阻断：Evidence Pending Review；pending=supported_abstention / claim_classification_unverified。该阻断不构成本轮业务缺陷；按本行适用证据/完整性独立判定。 完整Final与身份见矩阵对应行。 |
| A/Q35 | PASS | 拒绝S3推断并正确区分电气等级。 旧阻断：Evidence Pending Review；pending=supported_fact / source_quote_unlocated。该阻断不构成本轮业务缺陷；按本行适用证据/完整性独立判定。 完整Final与身份见矩阵对应行。 |
| A/Q37 | PASS | 先澄清/停风险操作，条件说明未变为继续授权。 旧阻断：Evidence Pending Review；pending=supported_abstention / claim_classification_unverified。该阻断不构成本轮业务缺陷；按本行适用证据/完整性独立判定。 完整Final与身份见矩阵对应行。 |
| A/Q43 | PASS | 资料参考保留设备/断电条件，没有直接操作未知现场。 旧阻断：Evidence Pending Review；pending=scoped_reference / claim_classification_unverified。该阻断不构成本轮业务缺陷；按本行适用证据/完整性独立判定。 完整Final与身份见矩阵对应行。 |
| A/Q44 | PASS | 未把零件描述变成拆装授权。 旧阻断：Evidence Pending Review；pending=reasonable_safety_advice,supported_fact / source_quote_unlocated。该阻断不构成本轮业务缺陷；按本行适用证据/完整性独立判定。 完整Final与身份见矩阵对应行。 |
| A/Q45 | PASS | 澄清优先，具体资料受型号/报警条件约束。 旧阻断：Evidence Pending Review；pending=scoped_reference / claim_classification_unverified。该阻断不构成本轮业务缺陷；按本行适用证据/完整性独立判定。 完整Final与身份见矩阵对应行。 |
| B/Q05 | PASS | 手套及条件性电池护目说明适用，没有泛化。 旧阻断：Evidence Pending Review；pending=supported_abstention / claim_classification_unverified。该阻断不构成本轮业务缺陷；按本行适用证据/完整性独立判定。 完整Final与身份见矩阵对应行。 |
| B/Q38 | PASS | 拒绝无据长期用电/试验；正常流程的条件范围明确。 旧阻断：Evidence Pending Review；pending=supported_fact / source_quote_unlocated。该阻断不构成本轮业务缺陷；按本行适用证据/完整性独立判定。 完整Final与身份见矩阵对应行。 |
| B/Q45 | PASS | 澄清优先，具体资料受型号/报警条件约束。 旧阻断：Evidence Pending Review；pending=supported_abstention / claim_classification_unverified。该阻断不构成本轮业务缺陷；按本行适用证据/完整性独立判定。 完整Final与身份见矩阵对应行。 |
| C/Q05 | PASS | 手套及条件性电池护目说明适用，没有泛化。 旧阻断：Evidence Pending Review；pending=supported_abstention / claim_classification_unverified。该阻断不构成本轮业务缺陷；按本行适用证据/完整性独立判定。 完整Final与身份见矩阵对应行。 |
| C/Q25 | PASS | 充电参数/顺序正确，S1可还原为DOC2来源而非型号。 旧阻断：Evidence Pending Review；pending=unresolved / claim_classification_unverified。该阻断不构成本轮业务缺陷；按本行适用证据/完整性独立判定。 完整Final与身份见矩阵对应行。 |
| C/Q26 | PASS | 界面行为有据；格式不改变事实。 旧阻断：Evidence Pending Review；pending=supported_abstention,supported_fact / answer_quote_unlocated,claim_classification_unverified。该阻断不构成本轮业务缺陷；按本行适用证据/完整性独立判定。 完整Final与身份见矩阵对应行。 |
| C/Q35 | PASS | 拒绝S3推断并正确区分电气等级。 旧阻断：Evidence Pending Review；pending=supported_abstention,supported_fact / source_quote_unlocated。该阻断不构成本轮业务缺陷；按本行适用证据/完整性独立判定。 完整Final与身份见矩阵对应行。 |
| C/Q38 | PASS | 拒绝无据长期用电/试验；正常流程的条件范围明确。 旧阻断：Evidence Pending Review；pending=supported_fact / source_quote_unlocated。该阻断不构成本轮业务缺陷；按本行适用证据/完整性独立判定。 完整Final与身份见矩阵对应行。 |

15条均是在本轮独立读完整答案/上下文后判PASS，而非因为上一轮说“争议”直接放行。A/Q31并非这15条，但也是证据误读的反例：Final C16展开的Parent P15及matched_child_ids已经包含C15/C17的右DL/10分钟说明，只看入口ID会制造新的假错误。

## Judge/Matcher误判和漏判的最小修复集合

| 前轮根因 | 本轮确认与处理 |
|---|---|
| H01/H09 | 原passed混合质量与执行/治理未闭合，且Regression直接用布尔翻转；改用已完成的二元业务结果比较，执行未完成阻断比较，不伪装业务退化。 |
| H02/H10 | P/A局部资料不足与Negative条件参考被类型互斥拒绝，Q49预期子类映射丢失；去掉强制七类Claim，保留原冻结expected_behavior及全答行为核验。 |
| H03/H04 | 图标、Markdown转义、畸形加粗及来源S编号映射缺失可制造Pending；共享来源图例，规范化只清显示噪声，不删否定/数值/型号。跨段引用用多个真实片段，不能模糊匹配伪造连续原句。 |
| H05/H07 | Golden原句拆成机械事实/指定ID，无语义等价验证；Q13/Q14不能靠原句/ID失败归因。必要事实应是业务原子要求，引用可替代但范围不能偷换。 |
| H06 | 自动诊断要求missing_points与事实逐字一致，漏全表缺失/安全前提；判断实际回答缺陷、规范和阶段证据，不靠Judge文字/关键字触发。 |
| H08/H11 | 20条顶层派生来源与有效Evidence不一致；R1/R3上级范围丢失。源头同步新Revision派生字段，知识内容变化按新Corpus治理；旧冻结身份只读，不能回填造正确。 |
| H12 | 界面把Overall/Gate、passed翻转、技术目标挤成相近“达标/修复”术语；沿现有界面分别解释业务、执行完整性、目标修复和正式资格，不加新导航。 |
| H13/H14/H15 | 有限恢复是待批准合同变更，当前SPEC允许持续瞬态恢复；当前200条未见重复，不能声称已发生幂等丢失。保留请求身份、Prompt/Schema摘要及可得模型revision；缺失不补造。 |

代码证据沿用前轮H表：`backend/app/evaluation.py` score_execution/execute_candidate、`evaluation_contract.py` observe_evidence/resolve_evidence/类型校验/compare_cases、`diagnostics.py` automatic_analysis、`ai_service.py` generation_context、`providers.py` judge、`governance.py` Revision写入、`policy.py` evaluate_regression及对应前端消费者。本轮没有修改它们。

## 与上一轮审计结论的差异

- Q03：不再因缺“从主菜单按设置”字样认定必要信息遗漏；答案已说在设置菜单进入用户配置并给创建步骤，足以执行。
- Q13：收敛为本仓库同一清洁对象规则，等价Final足够；不把“每台设备”额外全域量词设为验收义务。Q14 BL也有等价急停证据，建议PASS。
- Q07：四组的关机/电池隔离都没补齐，不能因正确滤网步骤或保守语气而通过；A虽召回C26仍未入Final，应归Context Selection，其他三组为Retrieval。
- Q22：四组均没有正确分清R1/R3；保留FAIL，但真实上级型号信息缺失不能武断全归Generation。
- Q42：从“方向争议”明确为BL FAIL；“禁止/避免：不含…”是实质成分极性冲突，后文正确不撤销同答矛盾。
- 原BL Pass Q39改FAIL；A/B/C对不明液体的停用/条件限定足够，不能因为提过普通表面资料就一律判错。
- 进一步读完整A/B/C发现B/Q14、B/C Q41旧Pass漏判；A/Q15、A/Q17仍FAIL但出现新的缺陷类型。
- Q36量化拒答本身正确；只有B额外把原文气/水混写转为“有据可执行”，形成O1真实语义裁决。

## Owner裁决与草案一致性检查

唯一无法靠现有语义证据闭合的记录是O1：B/Q36。具体原文、两种裁决及数量影响见矩阵O1。Owner需要确认的是原文连接介质未明时，这种“可执行摘要”是否已超出允许的资料参考；不涉及同义、ID或Markdown争论。不能擅改原文、默认通过或伪造官方解释。

其余待Owner审核的是政策采纳而非新增未裁决Case：是否采用本草案的业务必要事实/安全规则、删除强制Claim多类型、工程恢复具体上限，以及知识范围变化走新身份。均未自动生效。

草案按“必要信息＋适用证据＋整答无实质错误”统一Positive/Ablation/Negative，没有发现必须用相反规则判定同种情况的矛盾。但存在可复核的语义边界：A17直接开机指令与A31正常资料说明；BL39当前污染处理与C39最终明确停止未知液体；B14无条件冷启动与Q20明确故障重启；B/C41全称硬要求与单场景示例。每处均按指令的适用条件、全答约束和实际Final判断，不能降为标题词/拒答词匹配。

必要安全要求没有放宽：即使未显式问安全，触碰清洁/更换部件仍需适用断电条件；普通事实问答不强加无关告警。放宽的是机械原句、指定ID、七类措辞、无害显示差异。误放风险主要是把局部免责当全答撤销、只看拒答首句、把引用存在当适用；误杀风险主要是漏读Parent、把资料不足当设备无能力、把正常条件资料当当前操作。这些由合同中的成对反例约束，不能靠继续加审核层解决。

## 本轮执行保护

仅新增本请求的三个Markdown报告；未改业务代码、SPEC、Golden、历史回答/分数/Regression/Qualification、Gate或数据库。未调用Provider，未运行Retriever、生成、Judge、Baseline、Sandbox、发布或回滚，未提交/推送。交付检查通过：200个唯一记录键/回答与Final哈希/原始历史结果一致；独立计数157P/42F/1裁决及修复/新增集合一致；29表全部行逻辑指纹与7张核心表完整导出均不变；索引manifest的16份制品、4份PDF及前轮审计报告哈希均不变；三份Markdown表格列数与代码围栏检查通过。这些是文件/数据完整性检查，不是新Judge效果验收。工作区并发出现的 `scripts/verify_self_evolution.py`、`scripts/test_verify_self_evolution_cleanup.py`、`STORAGE_CLEANUP_EXECUTION.json` 等其他任务改动均未触碰，本轮仅写入这三个报告。
