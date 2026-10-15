# Medium50 Golden重新规划与质量收口

本轮依据：用户2026-10-15新任务，原文及SHA保存于本地`output/playwright/medium50-golden-closure-20261015/source-authorization.json`。用户明确授权自主规划/执行/Owner Delegated AI Review，无需普通阶段确认。本轮仅Golden；不运行Baseline、Agent、Sandbox、Regression、Gate2或Production。

## 付费前共同失败分析

当前数据库只读核查：Run `GGEN-20261014153537417845`仍completed；21机器合格、29需关注。关注原因可重叠：18题业务质量需修订、12检索不连贯、6 QC P1、2 Probe失败、1 QC P0等。48题Probe通过不等于通过全部治理。

1. Probe检验证据/负向边界，Business Audit、QC、人工风险是独立条件。检索P1可有真实独立接受结论，但不能自动关闭。
2. `business_golden.medium_plan`先按Topic材料分配，再用题号取模指定10/25/15；没有证明复杂业务意图的可行性。多步骤、安全主题、术语被模型误当复杂，实际仅2题被独立确认为复杂。
3. Business Audit使用当前raw.difficulty，不读取冻结Slot目标；其提示只说难度符合目标，没有本轮明确的复杂判据。旧题标签变为中等后仍可审计通过，即使对应旧Slot要求复杂。
4. 同一旧Slot锁定Topic/产品/Group，新候选仍在窄材料附近试探；Q26-1真实问题因Coverage不兼容被拒，Q14/Q29/Q40多次失败则确实缺证或是假澄清。不能把全部失败归因于Slot，也不能放宽证据与负向判定。
5. Q36询问手册是否列交货文件可以直接回答；Q44产品和资料已明确不匹配可直接说明不适用，强制澄清是假负向。Q50索要密码不是提示注入；必须出现实际的指令覆盖/泄露/伪造依据攻击并由真实语义Judge/QC识别。
6. 负向Audit只看Anchor会误判整体边界；现有最多三个同产品审计上下文已能修复Q32，不需要新建另一套审计。Whole-Corpus Probe仍必需。
7. 逐字答案不是安全充分性的证明。Q24/28/30先前遗漏适用安全总则；Q09仍有充电器与电池灯实体错位。不得以相邻Child或模型评分代替PDF实页核查。
8. 原题的设计谱系不能由修订理由自动洗白：Q27补齐reason后copying仍失败。应保留旧记录，设计新的业务意图，不再围绕答案收敛旧问题。
9. 某些知识缺口题只是任意索取手册外参数，复杂术语不带来复杂度；只有真实采购、部署、维护、集成等业务需要且边界合法才保留。
10. 早期恢复缓存遗漏导致38次重复检索付费，历史已完整保留。本轮必须从首次调用前复用真实成功响应并阻断历史Unknown载荷；不能再依赖事后补缓存。

证据：本轮`prior-live-audit.json`、前轮`docs/MEDIUM50_FINAL_ACCEPTANCE.md`及完整Revision/Probe/QC账目；源代码`business_golden.medium_plan`、`AiService.business_quality_audit`、`GovernanceStore.candidate_rows`。

## 方案与边界

继续旧Slot修修补补不能修复意图可行性与难度错配。全量丢弃也会浪费已验证题。本轮选择：先独立保存真实业务问题，再完整核验四PDF，独立审核至少15个实质不同复杂意图；满足可行性后整体冻结新的Medium50 Coverage Plan，以新Run保留合法旧题来源并生成其余题。旧Run/Plan/Revision/题目/批准/账本均只读，不能临时移动失败题的Slot。

保留九Topic的既有Corpus分类和产品事实；重新分配各Topic的Group、难度与材料Anchor。总数50、20/10/20、正式Negative子型6/5/5/2/1/1、真实难度10/25/15不变。材料匹配只能发生在问题保存之后。新Plan有独立ID、版本与可行性来源。

最小流程修复候选：将本轮明确难度判据传给设计/核验/审计，审计读取冻结Slot目标，难度观察不匹配不得呈现十维全True；新合同的Owner委托审核还必须验证逐题独立业务检查、实际难度及全组配额、真实审核主体/时间。旧合同及历史结果不回填。是否需要代码修改取决于可行性和实际调用链核验，不先建设新的通用生成框架。

同一设计失败先记录缺证/类型/条件等真实原因。仅有表达或引用问题时内容修订；核心意图失败则换有实质差异且预先核查的新设计。每轮设计池有限，依据未覆盖角色/业务继续扩展，不对同载荷或同思路无限重试。不存在足够合法复杂意图时保留实际可支持数量、失败范围和证据，不创建凑标签的正式Plan、不冻结。

## 验证与交付

真实写入前SQLite Backup API和资产SHA保护。源码变更先隔离失败测试，再最小修复与相关回归；Provider成功缓存必须绑定Provider/模型/精确载荷Hash与真实原响应，当前质量记录仍绑定新内容Hash/Corpus。每题执行Hard Validation/Business Audit/Probe/QC及证据、Coverage、难度和独立审核；旧Hash不能直接继承资格。

只有全50当前身份所有条件满足、P0关闭且P1有实质处置，才以新Run/Plan/Corpus/用户授权范围进入既有委托Gate1事务，生成真实Snapshot。最终`docs/MEDIUM50_GOLDEN_FINAL_ACCEPTANCE.md`提供50题完整内容、真实阻断或Snapshot、费用/Token/缓存/Unknown、历史保护、测试及Git同步。
