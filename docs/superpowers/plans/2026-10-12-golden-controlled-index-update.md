# Golden Q02正式索引受控更新执行计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 不改Golden题目内容，仅补Q02正式Corpus中的步骤5/6，以一个新Child向量、367个复用向量完成新版本构建和50题正式硬校验；正式切换单独授权。

**Architecture:** 从已验证旧Bundle复制独立staging，应用已核实的单Block/Child/Parent/页全文补丁；一次Embedding请求包含变更Child和Q02查询，复用367行旧向量，本地完整重建FAISS。复用既有检索与激活函数，保留旧版本；不走全量Knowledge重建/自动Golden生成入口。

**Tech Stack:** 当前Python、SQLite Backup API、NumPy、FAISS IndexFlatIP、既有text-embedding-v4 / qwen3-rerank客户端；无新依赖。

**Spec:** `docs/RAG_SELF_EVOLUTION_SPEC.md`文首当前合同；修复实证为`docs/GOLDEN_FINAL_INDEX_OFFLINE.md`。

## 当前授权与约束

- 2026-10-12用户已授权先推送离线修复，提交`57b193b`已推送origin/main。
- **第一阶段随后获得用户明确授权并通过：实际2请求/1749 Tokens，计算费用0.0008745元；隔离新Bundle与50/50通过。Task3正式切换仍未授权，正式Corpus与Golden绑定不变。**
- 不再修改Golden题干、答案、Evidence内容、行为合同；只允许后续授权执行时必要的Corpus/Plan身份、引用定位及当前Validation更新。
- 不修改Judge、Agent、UI、Hard Gate、Regression、Search Space；不跑Generation、DeepSeek、Probe/QC、Baseline、Sandbox，不批准/冻结/发布。
- 保留全部旧Snapshot、旧50题Baseline、两轮A/B/C、Agent记录、Production、原PDF、旧正式与Legacy索引。
- 构建验证授权与正式切换授权分开；授权只覆盖写明的请求数，失败停止，不自动重试或扩大输入。

## 已核实的复用条件

当前有效Corpus：`CORPUS-c6bbb042130820be7a1a`，Pipeline：`KP-6cb9388a1131f837dac2`。

|检查|当前只读验证结果|
|---|---|
|旧Bundle完整性|`validate_bundle(require_full_text=True)`通过；Embedding与FAISS逐行一致|
|模型及维度|text-embedding-v4，1024d；新请求沿用当前北京业务空间端点，不输出Key|
|Child数量及顺序|368；隔离文本补丁与原版本逐行比较，所有Child ID及顺序相同|
|变更行|仅0-based第133行：`DOC-001-C-00134`|
|其余向量|367个Child完整记录、文本、顺序不变，可复用对应旧向量；保存复用矩阵摘要并逐行验证`array_equal`|
|Parent|349；仅`DOC-001-P-00133`改变，另外348个不变；Parent不参与现有Embedding|
|新增解析|0；原PDF及MinerU原ZIP已包含步骤，补同一个Block即可|

本地检查附件：`output/playwright/golden-index-final/vector-reuse-preflight.json`。367行复用矩阵SHA256为`556641bf5b3bc2da30d32c645bfc3eac2be5044b8cfde182ce9114cc8f41a852`。

结论：**当前补丁确实只需重算1个文档Child向量**。Q02查询另需一个临时查询向量，不进入Corpus的368行矩阵。如果执行时源文件/旧Bundle/模型/维度/文本/顺序任何一项变化，停止并重新报告范围，不能继续声称只需1行。

## Provider次数与预计费用

项目端点位于北京。2026-10-12核对[官方模型价格](https://help.aliyun.com/zh/model-studio/model-pricing)：text-embedding-v4及qwen3-rerank均按输入Token计费，**0.5元/百万Token，即0.0005元/千Token**；输出不计费。本估算不假定账户还有免费额度，不改产品的价格配置或历史费用。

|请求|次数|输入范围|输出用途|
|---|---:|---|---|
|Embedding|1|数组`[补齐后的Q02 Child文本, 原Q02问题]`，指定1024维|第一行替换Corpus第133行；第二行供一次真实检索验收复用|
|Rerank|1|原Q02问题 + 真实Hybrid召回的最多12个Child|既有qwen3-rerank排序，然后Parent Expand/TopK4|
|MinerU/DeepSeek/Judge/Probe/QC|0|无|无|
|本地FAISS/BM25/Coverage/Validation|0付费请求|本地真实产物|构建及确定性验收|

**总计2次HTTP Provider请求，涉及2条Embedding文本（1条文档+1条查询）及1次Rerank。** 官方[Embedding接口](https://help.aliyun.com/zh/model-studio/text-embedding-synchronous-api)支持v4同请求最多10条，因此两条可以一次提交；这是同步数组输入，不是另开Batch半价任务。

实际费用公式：`0.5 × (Embedding实际输入Token + Rerank实际total_tokens) / 1,000,000 元`。两个请求均保存返回Usage、请求ID（若返回）、输入摘要、调用时间和模型；凭据不进入日志/产物。

规划估算：Child282字符、Q02查询79字符；本地BGE计数分别235与71。12个Child的BGE总量最多4800；保守把查询按12份计入，Rerank规模5652，合计5958，按上述单价推算约**0.00298元，约0.003元量级**。BGE tokenizer不是Provider计费Tokenizer，该数值不是实际账单或严格上限。

**建议授权预算0.01元，总请求最多2次、无自动重试。** 预算是规划限额，不宣称Provider提供硬扣费封顶；调用前再次核价及估算，返回Usage异常/超估立即停止后续请求。若模型价格或计费条件变化，先重新报告，不继续调用。

省请求的做法：一次取得两个真实向量，把查询向量仅在该次验证进程按查询原文摘要+模型+维度复用。检索仍调用真实`VectorRetriever.retrieve()`、真实FAISS/BM25与真实Rerank，不能用Fixture代替Query向量或改产品检索逻辑。若无法可靠复用查询向量，则停止；按现有入口直接执行会变成**2次Embedding + 1次Rerank = 3请求**，不在2请求授权内隐式降级。

## Task 1：隔离构建新Bundle

**Files:** 后续只扩展`scripts/repair_golden_index_offline.py`或同目录一个受控补丁脚本；测试使用`backend/tests/test_image_footnote.py`及一个针对受控Bundle的一致性检查。复用`backend/app/full_text.py`、`knowledge_pipeline.py`和`corpus_management.py`，不重构生产模块。

**Interfaces:** 输入旧Bundle完整身份、已核实文本补丁、当前Pending工作集及授权预算；输出独立可验证的新Bundle、向量复用审计、新Corpus身份和待绑定Golden预览，默认不激活。

- [x] 先写隔离检查：未经授权禁止Provider；非单Child变更、模型/维度/旧身份不同、活动任务、旧向量不一致均拒绝；证实失败后实现最小受控构建。
- [x] 新做SQLite Backup API备份及完整旧索引/PDF摘要；不能只依赖上轮备份。固定旧Bundle路径及全身份，新staging位于`index_versions/<operation>-building`，不覆盖原版本。
- [x] 验证恰好1个Child、1个Parent、1个Block及第50页全文变化；所有其他Child记录与向量顺序完全一致。保留原ZIP，修订Block与PDF源、旧版本及补丁摘要绑定。
- [x] 获得阶段1授权后执行上述**一次**Embedding，验证恰好两条、响应顺序、float32、1024维、有限非零向量，沿用现有L2归一化；保存两个真实输出及Usage，失败保留诊断并停止。
- [x] 复制368×1024旧矩阵，仅替换第133行；另外367行逐位相同。**本地从完整新矩阵重建一个FAISS IndexFlatIP**，不向旧FAISS追加、不重算367个Embedding。
- [x] 生成新Chunk/Embedding/Index/Pipeline/Corpus身份，沿用当前`KnowledgePipeline.build()`的内容摘要算法；保留旧源PDF指纹，新产物身份不得冒用旧Corpus身份。
- [x] Coverage复制既有9 Topic membership与既有Slot，在新Plan中用新矩阵重算真实簇中心，更新Chunk/Embedding摘要及Corpus身份并记录旧Plan来源；不冒充重新执行K-means，不复用旧center/旧空间资格。若当前合同或校验无法接受受控membership复用，停止报告，不强行变更Topic或规则。
- [x] Corpus Bundle Coverage与Medium工作集Plan分别更新必要派生身份；Medium仍原50 Slot、20/10/20，不重新选题或生成题目。受影响Plan中心/摘要基于同一新矩阵。
- [x] 完整生成documents/chunks/parents/full_text/embeddings/faiss/coverage/manifest摘要；Child状态仅新向量验证后改为Indexed；完整`validate_bundle(require_full_text=True)`通过。

**验证：** 368行、1024d、FAISS重构矩阵逐行一致；367复用行摘要不变；所有Child→Parent→Block→PDF页可追溯；Manifest及Coverage均新身份；旧Bundle仍独立通过验证。

## Task 2：Q02真实检索与50题验收

**Interfaces:** 输入Task1完整新Bundle、真实Q02查询向量和未改内容的50题；输出检索Trace、50个完整Validator结果、内容不变与历史保护报告。

- [x] 将检索器固定到新staging，不借用正式Corpus指针；读取原Q02题干。采用现有冻结默认配置CandidateK12/TopK4、Hybrid/Rerank开启；无Rewrite/MultiQuery/HyDE，不进入AiService回答生成。
- [x] 复用Task1的真实查询向量，运行现有FAISS/BM25融合；留存Vector、BM25、融合后Candidate及内容。
- [x] 若Q02目标Child未进入真实候选，停止并保存检索失败，不能人为补入Rerank候选。正常候选进入**一次**真实qwen3-rerank请求，保存排序与Usage。
- [x] 执行既有Parent Expand，验证目标Child及`DOC-001-P-00133`在最终上下文；逐条检查14步、顺序、步骤5用户名回车、步骤6密码入口及第13步可选含义。使用PDF来源定位，不仅搜索“1.”到“14.”数字。
- [x] 将50题仅在隔离预览中绑定新Corpus/Plan，运行原`validate_golden_candidate()`，包含新Plan、Slot、来源身份与重复检查，要求**正式新Bundle对应Hard Validation 50/50**；不能只报无Coverage的文本50/50。
- [x] 更新Q02已有pdf_supplement状态为“已由新Bundle验证”，保留原遗漏和修复审计；只有新身份完整校验通过才解除该证据缺口标记，其他质量/人工风险不自动关闭。
- [x] 50题内容与当前工作集逐字段不变，22修订完整、28保留完整，配额20/10/20，Q42材料Anchor及R1/R3范围保持；Probe/QC/Human仍Pending，旧资格不继承。
- [x] 整体验收失败则停在staging；不继续付费请求，不切换、不重写Golden。报告2次调用实际用量/费用、50题结果与新旧身份，等待正式切换授权。

**成功标准：** 新Bundle完整、Q02真实最终上下文覆盖14步、带新身份与Plan的50/50硬校验、所有保护检查通过。计划不提前保证Provider召回必然成功。

## Task 3：正式切换与可回滚验证（单独授权）

**Interfaces:** 输入已验收新Bundle、旧Bundle完整身份、工作集预览、新备份及人工切换授权；输出原子指针切换、当前工作集新绑定、旧版本完整可寻址及回退记录。

- [x] 隔离测试指针切换/DB失败/进程中断：成功时新Bundle与新工作集同身份；失败时旧指针、旧工作集及Corpus State一起恢复。没有通过此测试不得正式切换。
- [ ] 只读确认无活动任务；切换时短暂停本项目API以阻止跨进程读写。独立脚本中的`CORPUS_LOCK`不能锁住另一个运行中的后端，不能靠它宣称跨进程安全。
- [ ] 新做DB/索引备份，保存持久化操作记录：旧/新Bundle路径及身份、旧指针、旧State、工作集旧行及备份摘要。切换前再次校验`expected_active`与全Manifest身份，拒绝迟到产物。
- [ ] 直接复用`CorpusManager.activate_bundle()`原子symlink切换和异常回退，**禁止调用`POST /api/knowledge/rebuild`或`CorpusManager._run()`**：其`on_knowledge_activated`会启动新的Full Golden生成，不在授权范围。
- [ ] 以SQLite事务仅提交当前Pending工作集必要Corpus/Plan/Validation/pdf_supplement审计字段，并记录旧绑定；不改题目内容、不新增Snapshot。指针切换及事务提交间用操作记录标明阶段，异常回退；启动前若有未完成记录，必须先恢复一致旧状态，不能带混合身份服务。
- [ ] 外部脚本不依赖内存缓存失效：重启已确认归属本项目的后端后只读验证新身份、新Manifest、新工作集、50/50及Pending状态；确认未触发任何Worker/Provider。
- [ ] 重新核对全部历史表行与PDF/旧索引摘要；验证`index_for_config()`仍能按旧完整身份定位旧Baseline/Candidate/Production索引，Legacy绑定不迁移。
- [ ] 回退演练在副本执行：恢复旧指针、State和该工作集旧绑定；检查旧Bundle、旧身份及历史数据。正式回滚仍需人工授权，不自动发布或回滚Production。
- [ ] 同次Commit同步实际SPEC/Changelog/验收，明确“Hard Validation通过、Probe/QC未运行”，推送并确认干净同步；不修改架构/UI，除非实际结构发生必要变化且另有授权。

## 授权建议

第一阶段建议仅授权：**1次Embedding（1个Child+1条Q02查询）、1次Rerank、预计0.003元量级、预算0.01元、无重试；仅独立构建及验收，不正式切换**。

验收报告通过后，再决定是否授权正式切换。完整50题Probe/QC仍是第三项单独授权，不包含在本计划的2请求中。


## 第一阶段执行记录

已完成Task1/Task2，未执行Task3。实际结果及保留边界见[第一阶段验收](../../GOLDEN_Q02_STAGE1_ACCEPTANCE.md)。正式切换及完整Probe/QC仍须后续单独授权。


## Stage3切换前隔离验证

联动、真实SIGKILL、SQL异常、恢复再中断和共享启动守卫已验证，详情见[Stage3验收](../../GOLDEN_Q02_STAGE3_VERIFICATION.md)。只完成Task3的隔离验证部分，正式操作仍待下一次授权。未调用新的Provider。
