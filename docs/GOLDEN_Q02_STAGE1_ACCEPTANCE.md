# Golden Q02第一阶段：隔离构建与真实检索验收

2026-10-12；Ponytail full；用户明确授权最多1次双文本text-embedding-v4及1次qwen3-rerank，预算0.01元，无重试。依据[受控更新计划](superpowers/plans/2026-10-12-golden-controlled-index-update.md)。

**第一阶段验收通过：真实新向量/FAISS/检索链与新Corpus/Plan下Hard Validation 50/50；正式Corpus及Golden绑定未切换，全部业务数据库行保持不变。**

## A. 实际Provider调用、Tokens与费用

|模型|实际请求|实际返回Usage|按官网标价计算费用|
|---|---:|---|---:|
|text-embedding-v4 / 1024d|1|prompt_tokens=263，total_tokens=263|0.0001315元|
|qwen3-rerank|1|total_tokens=1486|0.000743元|
|合计|**2**|**1749 Tokens**|**0.0008745元**|

Embedding同一请求仅包含补齐后的Q02 Child与Q02原查询。查询向量不是Corpus新行，仅在本次真实检索验证进程复用，未发生第三次请求。Rerank输入为真实融合召回的12个Child，没有人为加候选。

2026-10-12再次核对北京[官方模型价格](https://help.aliyun.com/zh/model-studio/model-pricing)：两模型均0.5元/百万输入Token。上述费用由实际返回Usage计算，低于0.01元预算；**账户实际扣款未查询，免费额度/折扣未假定**。非BGE Token估算，非原先0.003元规划量级冒充实际费用。

全部2请求成功，未自动重试、未扩大输入；MinerU、DeepSeek、Judge、Probe/QC及回答生成请求均0。请求前持久化消耗记录，重复脚本运行或重复模型请求被拒绝，不存在重试/续跑开关。凭据未进入日志/数据库/Git。

## B. 新Corpus及Plan身份

|身份|隔离新版本|
|---|---|
|Corpus|`CORPUS-38c90d5628b68c76d53e`|
|Pipeline|`KP-c39f689648f5a7cf3a4f`|
|Chunk|`CHUNK-2df5162a379082558b36`|
|Embedding|`EMB-586ab413e6f5e2e075ce`|
|Index|`IDX-ee5bb4977dcf28f8e2f8`|
|Corpus Coverage Plan|`PLAN-23ab9016c62047d2807ae8c2`|
|Medium50隔离Plan|`PLAN-89801791985fdfe13f1421cf`|

新Bundle：`backend/data/index_versions/Q02-STAGE1-20261012130314899614-building/`。该目录是完整可验证的staging，**不表示已激活**。

正式旧版本仍为`CORPUS-c6bbb042130820be7a1a` / `KP-6cb9388a1131f837dac2`；正式工作集仍为`GGEN-20261012120721324996`、旧Plan `PLAN-34a4cc54b4452ab7a549d549`。源PDF及MinerU ZIP不变，新产物使用新身份，不覆盖旧身份。

Coverage按批准计划复用既有9 Topic membership和Slot；使用新矩阵重算真实簇中心、排序/归一化后的Embedding摘要，保存旧Plan来源及`reclustered=false`。这不是重新执行K-means，也不是冒用旧center。独立复核所有簇中心和Embedding Fingerprint与新矩阵逐项一致；Medium保留原50 Slot与20/10/20。

## C. Q02真实检索与14步

复用原`VectorRetriever.retrieve()`，输入Q02原问题及冻结默认检索配置：Vector/BM25融合、CandidateK12、真实qwen3-rerank、Parent Expand、TopK4；没有Rewrite/MultiQuery/HyDE，也不进入回答生成或Judge。

- 真实融合候选12个，`DOC-001-C-00134`排名**第1**。
- 真实Rerank后该Child仍**第1**，进入4个最终Parent之一`DOC-001-P-00133`。
- 完整步骤1–14按顺序出现在最终上下文；逐步使用完整原文定位，并与DOC-001原PDF49–51页核对，全部通过。
- 第5步“利用屏幕上的键盘输入用户名，点击回车键完成”、第6步“按下密码按钮”完整存在；第13步“如有必要”保持可选语义。
- `matched_child_ids`保留实际命中Child；没有通过强制TopK、换题或手工插入候选取得通过。

实证为本地`retrieval-trace.json`、`pre-rerank-trace.json`与`q02-fourteen-steps.json`。这是真实检索验收，不是LLM回答正确性或语义QC验收。

## D. Hard Validation与50题保护

**新隔离Corpus/Medium Plan下原Validator：50/50。** 使用当前`validate_golden_candidate()`，输入新完整身份、Slot、Evidence、重复检查及新Plan，没有改Validator或门槛。独立再次执行确定性校验仍50/50，没有再调用Provider。

50题题干、参考答案、Evidence内容、行为合同、来源/业务内容均保持；隔离预览只刷新必要Plan/Validation/定位派生信息，并记录Q02缺口已由新Bundle验证。22题既有修订成果完整，另28题与原冻结Snapshot除生命周期/派生字段外一致；20 Positive、10 Ablation、20 Negative保持。Q42材料Anchor及R1/R3范围关联保持。

正式DB工作集的Q02缺口标记、正式旧Validation与绑定**未修改**，因此正式页面仍是49/50；隔离50/50不能显示为已完成正式切换。Probe/QC/Human仍Pending，未批准或冻结任何对象。

## E. 367行逐位复用

- Child总数368，向量1024维；仅0-based第133行`DOC-001-C-00134`换为真实新向量，未新增行。
- 其余367行`array_equal`及原始矩阵字节比对均一致，未重复归一化/重新Embedding这些行。
- 367行复用矩阵SHA256：`556641bf5b3bc2da30d32c645bfc3eac2be5044b8cfde182ce9114cc8f41a852`，与阶段前预检一致。
- 用完整368行矩阵在独立目录新建FAISS IndexFlatIP；`reconstruct_n`与新矩阵逐位一致，不向旧FAISS追加文本或向量。
- Child及顺序不变；只有Q02 Child、对应Parent、原Footnote Block及PDF50页全文补齐。349 Parent中另外348个保持。
- `validate_bundle(require_full_text=True)`及独立复核通过：所有摘要、Embedding/FAISS、Child→Parent及页源身份一致。

## F. 隔离、数据保护与回退

执行前重新使用SQLite Backup API备份并复制完整旧索引，原始资料只读。备份`before.db` SHA256：`e615b5eae61478628d3a7a1b2d9bced4ff3ef14c6b48688b373cadd1cf6aee30`。

全部**29表所有行**前后摘要一致，包括当前50题及Generation Artifact；本轮无正式数据库写入。所有先前PDF/索引资产SHA256保持，保护检查覆盖60文件（含本轮已完成的离线dry-run来源产物）；原44份正式/历史PDF及索引保持。旧Snapshot、50题Baseline、两轮A/B/C、Agent、Production完整，不重跑。

回退测试仅在`rollback-copy/`副本执行：使用真实新Bundle及真实旧Bundle复制品，调用既有`CorpusManager.activate_bundle()`，注入激活回调故障后旧指针恢复、旧Bundle完整身份及摘要校验通过；DB由Backup API恢复到副本后逐表逐行与写前一致。正式指针/Corpus State未参与演练。

此测试证明隔离索引异常回退与数据库备份恢复；**不冒充下一阶段正式DB绑定+文件指针的联动提交或进程中断恢复已验收**。这些检查仍按计划Task3在正式切换前完成。

## G. 是否具备正式切换条件

**第一阶段已通过，已具备进入下一阶段的真实新Bundle及50/50工作集预览。正式切换仍未授权、未执行。**

下一阶段先完成Task3隔离联动事务与中断恢复验证，再检查无活动任务、最新备份及源身份，之后才能在用户明确授权范围内切换指针/当前工作集身份。不能调用现有重建API触发Full Golden自动生成；不得借切换运行Probe/QC或批准/冻结。

## 产物与代码

私有运行审计：`output/playwright/golden-q02-stage1-20261012/`，包括`report.json`、`provider-calls.json`、两个原始响应、`requested-vectors.npy`、备份、真实检索Trace、14步检查、Hard Validation与隔离工作集预览。不进入Git。

脚本：`scripts/build_q02_stage1.py`。该脚本没有正式激活或DB写入入口；本次固定授权账本已消耗，禁止再次以`--execute-authorized`运行。未来新授权必须另行定义范围，不能删除账本重试。

离线守卫及相关回归共**21项测试通过**；独立实物复核通过。仍有Python3.14 SQLite ResourceWarning、SWIG与joblib环境警告，不称无警告验收。业务/技术架构与UI没有变化。
