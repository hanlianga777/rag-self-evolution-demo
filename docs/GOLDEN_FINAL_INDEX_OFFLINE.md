# Golden 50题最终索引离线验收

2026-10-12；基线提交`27b7dde`；Ponytail full；工作集`GGEN-20261012120721324996`。

**结论：解析根因已修复，必要关联已写入新工作集，正式索引切换仍阻断。正式Hard Validation为49/50，隔离文本预览50/50。全部付费Provider调用为0；不能启动完整Probe/QC。**

## A. Q02缺失原因与修复

原始DOC-001 PDF第50页原生文本与页面图像均包含：

1. `5. 利用屏幕上的键盘输入用户名，点击回车键完成。`
2. `6. 按下“密码”按钮。`

保存的MinerU ZIP也包含这两步，位置为`DOC-001-BLOCK-00690`原始图片Block的`image_footnote`。并非MinerU未识别；本地`parent_child()`仅读取Caption/List等字段，漏读图片Footnote，导致正式Block文本为空，Child、Parent及页全文丢失两步。

共享转换函数增加读取`image_footnote`，不另建解析器、不重解析PDF、不新增依赖。回归测试先复现漏失，再验证Caption与Footnote按顺序进入Block、Parent、Child。

受控隔离产物只恢复一个Block、一个Parent、一个Child及第50页全文；步骤来自PDF已核实的原始MinerU结果，不从Golden答案反向生成。旧源PDF、旧解析ZIP和正式Corpus未写入。

## B. Child / Parent / Embedding / 索引

|项目|实际结果|
|---|---|
|正式旧Bundle|`validate_bundle(require_full_text=True)`通过；368 Child、349 Parent；1024维Embedding与FAISS逐行一致，原摘要完整|
|隔离Q02|`DOC-001-C-00134`→`DOC-001-P-00133`，PDF49–51页；Child及Parent文本一致、Block可追溯，235 BGE tokenizer tokens，282字符|
|离线召回|复用实际`VectorRetriever._bm25()`，Q02原问题排名第1，满足CandidateK12；复用`expand_parents()`后包含1–14步|
|Embedding|该Child文本已改变，旧向量不得冒用；本地历史Chunk中没有相同新文本可复用|
|新正式索引|未生成、未激活；隔离目录故意没有Embedding/FAISS/激活Manifest，无法冒充可运行Bundle|
|完整实际检索|Vector/Hybrid/qwen3-rerank未调用；BM25与Parent Expand检查不等于完整Provider检索验收|

正式Evidence仍引用旧Child，因此Q02步骤5、6目前仍未被正式证据覆盖。隔离预览引用可以定位两步，未把预览证据冒充正式证据。Q02原`pdf_supplement.blocks_freeze=true`继续保留。

## C. Q42 Anchor

旧`DOC-001-C-00072`是PDF第24页“日常维护”，与停机培训错配。

仅新工作集更正为：

- `DOC-001-C-00031`，PDF12页“紧急停机按钮”：所有清洁和行驶功能立即结束。
- `DOC-001-C-00095`，PDF28页“按下紧急停机按钮会发生什么？”：停止、机组关闭、屏幕及复位说明。

两页已查看原PDF；同步该题Anchor、Topic关联、Coverage Match及其新Plan Slot。原题干、Negative预期行为、空答案Evidence保留；不把KIRA操作建议应用到未知型号。Plan身份更新后50题仅必要的`plan_id`与当前Validation同步；不改历史Snapshot或Topic membership/center。

## D. Q16 / Q22范围

原Corpus的`section_path`只保存当前小标题，未持久化完整R1/R3祖先标题及文档版本；本轮不重构章节、不改索引Metadata，而在新工作集既有`source_scope`中明确章节边界与原PDF页码。

|题目|版本与定位|适用要求|
|---|---|---|
|Q16|DOC-002 ©2023整机手册PDF14页；DOC-003 V2.1的R1章节PDF9–13页，开关机PDF10页、绑定和连接PDF11页|R1开机一声、关机两声；连接成功为左侧数传灯全亮。不得套到R3|
|Q22|DOC-003封面V2.1；PDF13页修订表日期2025-04-18；R3章节PDF2–8页，开关机PDF4页|短按一次后长按2秒以上；R3开机两声、关机三声。不得按R1评分|

上述页面已查看扫描图像；Q16/Q22原题、参考答案及Evidence不变，仅补必要版本/章节关联。

## E. 50题离线验收

- 正式Corpus+当前工作集Plan：**49/50**，唯一阻断Q02。未改Hard Gate、Regression或Validation规则。
- 隔离文本+既有确定性Validator：**50/50文本预览通过**，不包含新Embedding/Topic center/正式索引身份资格。
- 50题题干、答案、行为合同、Evidence保持上轮工作集原样；所有Child引用均有对应PDF文件与合法页码，Negative只核实材料Anchor。这是定位检查，不宣称50题均完成新的语义QC。
- 22题既有修订成果保留；另28题对原冻结Snapshot除生命周期字段外逐字段一致。
- Positive/Ablation/Negative仍为**20/10/20**，仍为9 Topic。
- Probe、QC和Human Gate均Pending；没有重新生成Golden、冻结Snapshot、重跑Baseline或启动Agent Sandbox。
- 后端已由原监督进程受控重启：8010旧PID12194→新PID18474，启动于2026-10-12 20:26:50；启动索引检查确认PDF指纹不变、无重建。只读API返回该工作集`failed`及Human Gate `pending`。这是本轮运行记录，后续PID可变化。
- 18项相关离线测试通过；存在Python3.14 SQLite ResourceWarning、SWIG DeprecationWarning及joblib物理核数探测警告，非无警告验收。

## F. Golden / Corpus身份

正式工作集仍绑定旧Corpus，二者身份一致：

- Corpus：`CORPUS-c6bbb042130820be7a1a`
- Pipeline：`KP-6cb9388a1131f837dac2`
- Chunk：`CHUNK-7182246da10e41be7ade`
- Embedding：`EMB-1e5b0b16625163c0c3d3`
- Index：`IDX-26dff0254cecd3162cb5`

隔离文本摘要：`0a587b2e3c98d4198d3a1e85dd0a41dbc1705450d6d1b39aed0cb3a8da08f83c`。**该摘要不是新Corpus Fingerprint**。新Corpus身份必须在获得新向量、全Bundle一致性验证与新Plan/Golden身份复核之后产生；当前为未生成，绝不覆盖旧身份。

## G. 历史保护与回退

正式关联写入前使用SQLite Backup API备份，复制完整旧正式索引；先在隔离数据库验证同一修复。

本地产物根目录：`output/playwright/golden-index-final/applied/`（私有数据库及证据不入Git）。

- `before.db`摘要：`2008d13637099e08c52bd10978ddfd28ccf73d0bc16f0c93959b6cef77eb0d1c`。
- `before-index/`：完整旧索引备份。原PDF及旧/历史索引**44文件**前后SHA256全部相同。
- **29表**逐行摘要核对；仅当前工作集questions行的关联/Plan/Validation/updated_at，以及其唯一Generation Artifact允许变化。行数不变，所有历史行不变。
- `rollback-verification.db`由Backup API恢复，逐表逐行与写前数据库一致；旧正式Corpus未切换，回退验证不触碰正式库。
- 后端重启后再次核对通过；Snapshot、旧50题Baseline、第一轮A/B/C evaluated、第二轮A/B/C generated、Agent Trace、Production全部原样保留。
- `protection-after-restart.json`、`asset-hashes.json`、`report.json`、`working-set-preview.json`和`text-staging/`保留实证及写前引用；关联修复审计绑定备份路径。

可复现脚本：`scripts/repair_golden_index_offline.py`。默认仅备份和预览；`--apply-links`只更新指定Pending工作集关联，事务重验无活动任务/身份/待审核状态，验证失败回滚，禁止覆盖已有备份目录。脚本拒绝所有网络连接，Tokenizer仅读本地缓存；没有正式激活或Provider开关。

## H. 额外Embedding范围

需要另行授权：**1个变更Child的text-embedding-v4 / 1024维Embedding**，文本282字符（235为BGE计数，不能冒充实际计费Token）。另367个未变Child可按相同模型/文本身份复用已有向量，FAISS需完整重建，不能追加旧FAISS。

正式Q02检索验收另需至少**1条查询Embedding**及该次候选的qwen3-rerank；实际计费Token和金额未采集。本轮0次付费调用，不扩大为368条全文Embedding或重新调用MinerU。

## I. 是否可以启动完整Probe/QC

**不可以。** 当前欠缺变更Child的新向量、完整新Bundle、新Corpus/Plan/Golden身份及正式检索验收。需要先单独授权上述必要Embedding/检索范围，完成受控新版本构建、隔离/回退与50题正式复核，再另行授权完整Probe/QC。最终人工批准和Snapshot冻结仍由用户执行。

Git授权补充：用户随后明确同意先单独提交并推送已验证的离线修复；正式索引更新、付费调用及切换继续等待单独授权。本报告不代表完整索引收口通过。
