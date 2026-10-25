# Golden VNext 内容治理与共享回答规范：实施报告

日期：2026-10-25。状态：**已交付离线内容草案及代码准备，人工待审，未启用新版、未冻结、未评测、未发布**。Provider调用0，正式数据库写入0。

## 已完成且可验证

- 50/50原题与真实question_id逐题治理，Positive20／Ablation10／Negative20保持；30份中文参考答案重写，20份负向行为要求保留。
- 每题含旧版对照、原意图/场景/难度/谱系、必答/条件必答/辅助、禁用操作、等价表达、真实Chunk全文/文档/页码/来源角色，以及人工复核问题。
- 两份内容交付：[逐题阅读清单](GOLDEN_VNEXT_50_REVIEW.md)、[机器可读草案](GOLDEN_VNEXT_50_DRAFT.json)。JSON保留原题整体摘要、原来源字段和既有审核事件；新版本为文件草案，不入数据库。
- 新版表达规则单一实现，显式选择generation-vnext-2；默认旧版及其请求正文保持。正式生成、续跑与Candidate预约前核验生成合同，回答重放不能跨生成版本。
- 只读验证50题配额、身份、原字段/难度/场景、负向行为、逐行来源引用和所有来源正文一致；6种损坏注入均被检出。来源真实可定位不等于模型语义验收。
- 29张正式数据库表逻辑摘要、17个索引文件哈希前后一致；原Baseline/A/B/C、Judge、Gate、Production及审核记录没有覆盖。

## 执行方案与边界

1. 只读读取当前SPEC、SQLite冻结Snapshot、全部50题、Canonical与相关完整Chunk；以题号和持久化ID绑定。验证：Snapshot/Corpus身份一致。
2. 内容写独立草案：按真实用户意图分开必答与辅助，条件项列触发条件，不添加第三种业务结果。验证：逐题审阅与结构/引文校验。
3. 在既有AiService内新增共享表达与显式版本选择，先写失败检查再实现；沿现有Evaluation Identity隔离，禁止泄漏Golden答案/检查点。验证：录制请求与冻结身份测试。
4. 原Hard Validation照常执行，回归与保护摘要复核；代码、SPEC与草案同一提交。验证：结果如下，不将未执行的人工/Provider步骤报通过。

没有新增数据库表、服务、依赖、UI入口、评分特例或独立Prompt副本。没有更改检索模型、切片、实际索引、参数、Agent策略或Search Space。

## 当前正式身份和审查状态

- Git起点：`f1a6ce226a9c47279de0c68511b37cb702584849`，分支`main`，origin为`hanlianga777/rag-self-evolution-demo`。
- 正式Snapshot：`GD-20261015135415953347`；工作生成Run：`GGEN-20261015110926448917`。
- Snapshot逻辑SHA256：`31ad9c589d18b4d7d046a06374a0f1896a587a507fee585e0080c9a966a91a82`。
- 当前chunks.json SHA256：`ed52f56b622f8b5d677d1828ec0dd745713f568c71e5412618e34f4131ee3ddd`。
- 50题当前数据库状态均为`approved / probe_passed / qc_passed`；原冻结批准方式为`owner_delegated`。此历史状态不代表新版草案获批。新草案50题均为`human_review=pending`，Probe/QC未运行。
- 当前合同以SPEC文首2026-10-21 V5.1及后续当前条款为准。此轮只增补草案/显式生成版本准备条款，不覆盖历史与现有治理合同。

```json
{
  "chunk_artifact_id": "CHUNK-2df5162a379082558b36",
  "corpus_snapshot_id": "CORPUS-38c90d5628b68c76d53e",
  "embedding_artifact_id": "EMB-586ab413e6f5e2e075ce",
  "index_artifact_id": "IDX-ee5bb4977dcf28f8e2f8",
  "pipeline_version_id": "KP-c39f689648f5a7cf3a4f",
  "sources": {
    "DOC-001": "453ac9da8f24b1bbec2245b7017e95038e390093c12edf5eced094dc775f3be2",
    "DOC-002": "b2dea9e4a93ba9e6e398a01bfb6e50d2369ee2b8227130215cb9ff7fdd12cceb",
    "DOC-003": "7c99af0259045dcc49d7c12533605fad9fa8b65e3f2aebbce16dcfb4e5809ab0",
    "DOC-004": "e9206d046f2641c4a2b144abde5b742905cb22d7927688f6caed564d3482960b"
  }
}
```

## 生成链路与版本隔离

`AiService.answer(question, config)`接收用户问题及实际检索证据，构建保留产品、型号、版本与章节范围的context，然后执行同一生成请求。Baseline `_case_result`、正式逐题执行以及Candidate Sandbox共用该运行时；在线问答与预览也路由到同一个answer。Golden生成、Probe/QC、Judge和检索改写不是这个回答表达合同的实现位置，本轮未改变它们。

新增`GENERATION_EXPRESSION`：准确优先、结论前置、事实一句话、操作编号、复合事项分组，安全条件前置、引用简短、不补造未知能力、不固定长度；安全边界沿旧版完整保留。Grounded／Completeness／Abstention仍由现有Search Space管理，候选不能独占一套更有利的基础规范。

显式采用方式（仅说明后续集成，不执行）：

```python
runtime = AiService(store, corpus, provider, force_mock=False,
                    generation_prompt_version="generation-vnext-2")
```

同一后续执行环境用该runtime创建Baseline和对应A/B/C；无参数时仍为`generation-vnext-1`。本轮未修改main.py的默认构造、环境变量或正在运行的服务，未引入新UI开关。

`generation_contract()`返回生成版本与边界SHA256。Baseline输入绑定沿现有judge元数据写入此身份，既有`evaluation_identity()`已包含两个字段，无需改评分身份算法。Candidate继承Baseline元数据并在预约前核验运行时；执行与续跑再次核验。旧/新合同不同则阻断，不混入历史Run。未知生成版本在构造时即拒绝。旧版默认Prompt正文与边界摘要逐字不变，新生成结果附合同身份，旧保存答案保持只读。

`judge_replay.py`这里只改回答重放的生成身份检查：源与目标必须使用同一已知版本及正确摘要。未改Judge输入、评分、11 Gate、Regression或发布资格。没有执行重放。

生成Prompt不读取草案文件，也不接收reference_answer、required_checks或历史Judge。检查点目前仅作后续人工复核数据，不成为本轮评分输入。离线录制请求验证调用参数和隔离，不能证明真实模型输出质量。

## 代码与文档变更清单

| 文件 | 目的 |
|---|---|
| backend/app/ai_service.py | 共享表达规则、显式版本参数、生成合同及结果身份 |
| backend/app/evaluation.py | 冻结所选生成合同；执行/续跑与Candidate预约前核验 |
| backend/app/judge_replay.py | 回答重放沿源/目标同版本核验，不改Judge判分 |
| backend/tests/test_generation_vnext.py | 6项离线请求/身份/预约保护测试 |
| scripts/verify_golden_vnext.py | stdlib只读草案校验、6种损坏自检、由JSON重建阅读稿 |
| docs/GOLDEN_VNEXT_50_DRAFT.json | 完整机器草案，不导入Frozen数据 |
| docs/GOLDEN_VNEXT_50_REVIEW.md | 完整50题旧新对照及原文与争议 |
| docs/GOLDEN_VNEXT_IMPLEMENTATION_REPORT.md | 本报告 |
| docs/RAG_SELF_EVOLUTION_SPEC.md、docs/SPEC_CHANGELOG.md、README.md | 同步合同、启用范围与冻结前置 |

架构影响仅在现有Golden草案和既有回答生成/身份内部。没有新增或修改正式业务/技术图节点、连线或图样式，未另画图，不需要重导`架构`产物。

## 50题具体优化

| 题号 | 类型 | 本题完成内容 |
|---|---|---|
| Q01 | positive | 合并重复的一般设置入口，删除无关警告灯与快速模式。 |
| Q02 | positive | 直接回答当前所在界面的下一步。 |
| Q03 | positive | 将菜单入口、语言和可选权限调整列为辅助，独立账号、密码与主管权限单独列必答。 |
| Q04 | positive | 按存放地点、存前、存中三个阶段整理；重量提醒保留为搬运条件项。 |
| Q05 | positive | 只保留有据的防护用品，不额外列采购清单。 |
| Q06 | positive | 安全条件前置；区分设备、电池和对接站的实际隔离。 |
| Q07 | positive | 合并盖罩与取出操作，保留完整电气隔离。 |
| Q08 | positive | 区分一般检查保养与长期闲置后接触式充电器的条件流程。 |
| Q09 | positive | 先回答能否丢弃，再列报废路径，不补造放电方法。 |
| Q10 | positive | 突出充满后的连接要求，灯态作辅助识别。 |
| Q11 | positive | 直接回答唯一性及范围。 |
| Q12 | positive | 把找到刚才任务的依据写清，删除图例编号。 |
| Q13 | positive | 明确清洁对象、设备和路线三个范围；消除66 cm cm的OCR重复。 |
| Q14 | positive | 只答紧急停机；恢复运行触发独立安全条件，不作为无条件必答。 |
| Q15 | positive | 保留有据控制入口和启动顺序，不将局部功能误判为不存在。 |
| Q16 | positive | 保留完整接口清单与SDK口，删应用案例和宣传。 |
| Q17 | positive | 按R1/R3分组，避免型号缺失时任选一种。 |
| Q18 | positive | 清理转义符，分成进入、运动范围、保存确认三步。 |
| Q19 | positive | 先给必须动作，再解释限定手动操作的条件。 |
| Q20 | positive | 按排障顺序两步表达，不承诺必然恢复。 |
| Q21 | ablation | 保留升级与随机发货关系，去宣传措辞。 |
| Q22 | ablation | 保留按键顺序、时长与R3两声提示。 |
| Q23 | ablation | 分级各一句，注意作辅助，等级含义不改。 |
| Q24 | ablation | 按选用、配制、保管、意外四阶段组织，安全条件保留。 |
| Q25 | ablation | 先列充电前状态，再按连接、识别、完成顺序合并。 |
| Q26 | ablation | 拆开OCR粘连的开关和文件夹操作。 |
| Q27 | ablation | 按变化程度分支，保留地图能力边界。 |
| Q28 | ablation | 合并拆卸动作，保留隔离、居中与双处卡合。 |
| Q29 | ablation | 保留五类全部子项，删除表格键值残片。 |
| Q30 | ablation | 保留原因与方向，去掉标题及原因排除故障标签。 |
| Q31 | negative | 区别正常开机步骤与未记载的强制复位。 |
| Q32 | negative | 区分资料缺失与功能不存在。 |
| Q33 | negative | 保留数值证据不足测试。 |
| Q34 | negative | 不将产品手册当维修工单。 |
| Q35 | negative | 缺失具体等级不等于否定防护必要性。 |
| Q36 | negative | 区分有冲洗动作与有达标定量。 |
| Q37 | negative | 保留情境澄清，避免跨报警处理。 |
| Q38 | negative | 强调外观检查不足以确认长期库存电池安全。 |
| Q39 | negative | 清洁需求保持澄清型，审查拒答后的所有附带操作。 |
| Q40 | negative | 保留目标不明确的决策边界。 |
| Q41 | negative | 一般安装规则不能替代现场选点依据。 |
| Q42 | negative | 否定方向明确：三种禁用成分均不得含有。 |
| Q43 | negative | 保留跨产品不明时的澄清。 |
| Q44 | negative | 隔离提醒不代替型号辨识。 |
| Q45 | negative | 不让恢复使用的紧迫性取代事实确认。 |
| Q46 | negative | 将首次绑定和运行网络选择分开。 |
| Q47 | negative | 保留完整性边界，不否认可查的单条事实。 |
| Q48 | negative | 区分硬件接口与协议配置证据。 |
| Q49 | negative | 负向行为与后续安全操作一并审核。 |
| Q50 | negative | 拒绝的是伪造要求，有据正常问题仍可回答。 |

## 现有Hard Validation与新版内容的真实衔接状态

对原冻结题目在当前Corpus/coverage_plan上重新执行现有`validate_golden_candidate`：**50/50通过**。将新参考答案放到内存副本再执行同一校验：**20/50通过**，通过的是20道负向题；30道可答题均因`unsupported answer anchor`阻断。逐题结果保存在JSON的`validation.existing_hard_validation`和阅读稿。

原因是当前生产Validator要求参考答案可逐字定位，而本轮要求中文语义改写。此轮没有删除或放宽原验证，也没有把“引文真实”误报为“新参考答案已经通过生产Hard Validation”。草案校验只确认原题保护、引用和结构；语义改写与源文等价性仍需人工审核。正式冻结前必须另行审查可保留逐事实来源真实性的版本化验证方案，再走既有Revision/Probe/QC/Human Gate。本轮未实现或代行这一阶段。

现有Revision会保留前后身份与审核链路，适合后续受控导入；现有生产结构没有本轮独立检查点的消费合同，因此使用向后兼容的独立文件草案，没有覆盖reference_answer、原审核或冻结Snapshot。

## 来源字段不一致与人工争议

20题的顶层`source_chunk_ids`与嵌套`evidence[*].source_chunk_ids`不同。现有Canonical读取嵌套evidence；原Hard Validation仍通过，不应据此改写历史来源。建议在新Revision中同时重验顶层/嵌套来源、定位记录与主题/型号。

| 题号 | 原顶层来源 | Canonical嵌套来源 |
|---|---|---|
| Q03 | DOC-001-C-00131 | DOC-001-C-00132, DOC-001-C-00134 |
| Q04 | DOC-001-C-00118 | DOC-001-C-00179, DOC-001-C-00180, DOC-001-C-00185 |
| Q05 | DOC-001-C-00026 | DOC-001-C-00010 |
| Q06 | DOC-001-C-00013 | DOC-001-C-00026, DOC-001-C-00181, DOC-001-C-00204, DOC-001-C-00017 |
| Q07 | DOC-001-C-00241, DOC-001-C-00177, DOC-001-C-00196, DOC-001-C-00198 | DOC-001-C-00026, DOC-001-C-00181, DOC-001-C-00191 |
| Q08 | DOC-004-C-00034, DOC-004-C-00017, DOC-004-C-00024, DOC-004-C-00007, DOC-004-C-00008 | DOC-004-C-00030, DOC-004-C-00032, DOC-004-C-00034 |
| Q13 | DOC-001-C-00146, DOC-001-C-00147 | DOC-001-C-00047, DOC-001-C-00144, DOC-001-C-00045, DOC-001-C-00046 |
| Q14 | DOC-001-C-00140 | DOC-001-C-00007, DOC-001-C-00031, DOC-001-C-00095 |
| Q15 | DOC-001-C-00183 | DOC-001-C-00140, DOC-001-C-00141 |
| Q16 | DOC-002-C-00038 | DOC-002-C-00020, DOC-002-C-00021 |
| Q17 | DOC-003-C-00009, DOC-003-C-00022 | DOC-003-C-00015, DOC-003-C-00025 |
| Q18 | DOC-003-C-00021, DOC-003-C-00025 | DOC-003-C-00009, DOC-003-C-00022 |
| Q19 | DOC-001-C-00233, DOC-001-C-00234 | DOC-001-C-00236 |
| Q20 | DOC-001-C-00225 | DOC-001-C-00209 |
| Q22 | DOC-003-C-00010 | DOC-003-C-00010, DOC-003-C-00005 |
| Q23 | DOC-001-C-00127 | DOC-001-C-00008, DOC-001-C-00009 |
| Q24 | DOC-001-C-00128 | DOC-001-C-00022, DOC-001-C-00118 |
| Q27 | DOC-001-C-00045, DOC-001-C-00047, DOC-001-C-00071, DOC-001-C-00157 | DOC-001-C-00096 |
| Q28 | DOC-001-C-00120 | DOC-001-C-00026, DOC-001-C-00181, DOC-001-C-00200 |
| Q30 | DOC-001-C-00214 | DOC-001-C-00233 |

此外须人工决定或确认：

- Q06：维护总则与对接站条款同时适用；现场供电结构与操作权限需人工确认，不能将“或”解释成免除另一适用隔离要求。
- Q07：断电组合须与Q06一并人工确认，不把停止充电等同物理断开。
- Q09：原文要求彻底放电，但没有受损电池安全放电方法；保留原要求，具体交由有资质渠道确认，不授权用户自行处理。
- Q13：不同路线共用与同设备不重复ID需人工核对原PDF上下文；草案采用可兼容解释，未改冻结来源。
- Q14：冻结急停片段未完整列恢复安全流程；恢复前提结合安全总则，需人工复核后才可纳入新机器规则。
- Q15：手册明确激活清洁头和握安全开关行进，未明确静止定点刷洗及机械下降细节，不额外保证。
- Q22：正文为“2秒以上”，配图为“2秒及以上”；草案保留正文措辞，阈值边界待人工确认，不放宽安全。
- Q28：需人工确认不同供电状态的实际隔离；不编造原文未提供的旋向。
- Q39：污染液体及电池现场状态未知，禁止推断可清洗复用；需人工复核附带建议。
- Q42：原Anchor是日常维护，不提供清洁剂配方规则；草案仅补充DOC-001-C-00022及00118，不回写历史Anchor。
- Q49：原Anchor为悬崖扫描器而题目为后部扫描器；补充DOC-001-C-00224，仅草案引用，不修写原Anchor。
- Q50：原Anchor为扫描器污染条款，与残水场景不直接匹配；仅保留注入抵抗性质，不以该Anchor证明残水处理流程。

全部来源中未提供的版本元数据保持未知，不以版权年份或相近产品补造版本。Q31/32/33/34/35/36/47/48保留全Corpus检索观察；关键词无命中不是语义缺失证明，尤其Q36有冲洗操作证据但未取得量化达标时长/水量。负向材料Anchor不证明整库可答或不可答。

## 离线测试及结果

- 本轮新增6项全部通过：不同问题类型及Baseline/Candidate共享请求、默认旧版与新版身份差异、未知版本拒绝、正式生成前合同核验、同版本重放/跨版本阻断、Candidate预约前合同核验。
- 最终相关回归：**197项，196通过、1项既有错误**。涉及ai_service、source_context、judge_replay_v5、evaluation_vnext/context/policy、baseline_resume、candidate_resume、sandbox_stability、manual_sandbox_resume、business_audit_sources、v14_golden_v2、golden_revision_22、v14_identity。
- 既有错误：`test_baseline_resume.ResumeTests.test_display_returns_partial_without_granting_current_baseline_eligibility`，main.py:1273新增读取使用`store.connection()`上下文，但旧测试用普通Mock。异常为`TypeError: Mock object does not support the context manager protocol`。在改动前HEAD独立导出的app上复现同一错误；保留夹具，不扩大本轮修改。不得称完整后端全绿。
- 草案只读核验通过：50题无遗漏重复、配额20/10/20、原字段一致、30答案与20行为结构、Canonical引文和身份，6类损坏注入均被检出。该检查不是语义判分。
- `py_compile`与`git diff --check`通过。既有Starlette/FastAPI弃用及joblib物理核心探测警告保留，不新增依赖处理。
- 后端测试在导入app前隔离RAG_DEMO_DB_PATH、INDEX_DIR、DOCUMENTS_DIR、UPLOADS_DIR、ENV_PATH，并去除Provider密钥，设置HF离线；全部Provider响应为显式测试录制/Stub。没有正式Provider、Judge、Probe/QC或真实Sandbox运行。测试用历史/Legacy夹具不构成真实效果证据。

复现只读内容核验：

```sh
python3 scripts/verify_golden_vnext.py --source-database backend/data/demo.db --self-test
```

测试命令（临时目录可替换）：

```sh
env -u DEEPSEEK_API_KEY -u DASHSCOPE_API_KEY HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  RAG_DEMO_DB_PATH=/tmp/golden-vnext-final/demo.db \
  RAG_DEMO_INDEX_DIR=/tmp/golden-vnext-final/index \
  RAG_DEMO_DOCUMENTS_DIR=/tmp/golden-vnext-final/documents \
  RAG_DEMO_UPLOADS_DIR=/tmp/golden-vnext-final/uploads \
  RAG_DEMO_ENV_PATH=/tmp/golden-vnext-final/no-env PYTHONPATH=backend:backend/tests \
  python3 -m unittest -v test_generation_vnext test_ai_service test_source_context \
  test_judge_replay_v5 test_evaluation_vnext test_evaluation_context test_evaluation_policy \
  test_baseline_resume test_candidate_resume test_sandbox_stability test_manual_sandbox_resume \
  test_business_audit_sources test_v14_golden_v2 test_golden_revision_22 test_v14_identity
```

## 历史保护审计

所有正式数据库操作均以SQLite `mode=ro`读取。未触发真实写入，故未为写入执行Backup或导入；测试写入仅发生于临时隔离库。对全部29张表按rowid序列化并计算SHA256，对索引目录全部17个文件计算SHA256，前后完全一致。包括所有Frozen Dataset、questions、历史Case/Run/Checkpoint、审核/Approval、Candidate/Experiment、发布和回滚记录。

以下为前后相同的逻辑摘要/文件哈希，便于独立复核：

| 保护对象 | SHA256（前后相同） |
|---|---|
| tables/agent_traces | `8d209e61c3e04306f2b46693b215e9ffab3247d3b02765aed16459066afb1dcf` |
| tables/alias_mappings | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| tables/approvals | `d1564657b4d2a790c8d329a5bd39fe94b67b251717a40f169b56563cd1305d81` |
| tables/bad_cases | `4e25616205b9dc81e0d126a739263066ea61a329fea1f16b330a531acccfb1df` |
| tables/business_import_batches | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| tables/candidate_configs | `401a6f5cb7a99797e808e6fb8dca25d67837edbd19a80149c8785b491191785d` |
| tables/candidate_revision_runs | `47b1de834ab4e586b92f2836e0baf0893d0ec0daada9310327bbd75d831a17f6` |
| tables/coverage_plan_previews | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| tables/dataset_versions | `7730b5ac17b38045452f44852e2a8b8bd82b27517bab843e0a70b2286230611d` |
| tables/demo_state | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| tables/evaluation_case_results | `958a5a28eaa2e3e5cad456b620b07450799da3bb6a870dfff8e3c7973efce39f` |
| tables/evaluation_runs | `3876b6624cf0fc853fa31dbc62747f26bf1bfb6c93b4a8e78b4bdc3efa8ea785` |
| tables/experiments | `16d48afe8cd085801cbd48562a509c319f9c772a8f91c6d7b660ad25810858c5` |
| tables/golden_generation_artifacts | `b020547d4937085ddbb39c5e9f5015eab2f9c85e9ff5821e731aae5d6241320f` |
| tables/golden_generation_runs | `93851ce0b4b982d9b53d889dfced05bead5076bf4e4832bb1302a818ef3aa402` |
| tables/monitoring_events | `c5ecef65ea1f5032362f8076d0c4cd9afc19cf28c6867d1043daa7b66e54fcdc` |
| tables/optimization_triggers | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| tables/pipeline_config_draft | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| tables/probe_results | `0661e6260a5d41bca9a592044a87347fc6a503f70ff8ff328afcb0fae3ca97ff` |
| tables/production_versions | `2f6b374d972f5fcebe858d900c61178492c843e5f1a9296b22e4e367599a91e3` |
| tables/qc_results | `a7ede6dc5243482a1fa5c8fa66feca6dedc1f7c6e42672a70891a1c895a0ccd2` |
| tables/question_quality_audits | `7405915b0eacb62c3c4251779a80427be96930bb0d750521acf2940e35c7e126` |
| tables/questions | `dddb84a62bd4035c462cc9a982cfdaa8fffbfaa5837197295ca193dfab2fbdaa` |
| tables/recommendations | `ab1cdabb4b203c66e3c09fd5796cfac9e44858b9cd8f130a11c2c96926c93d6c` |
| tables/review_events | `5449540639c5dacb5ae8bd24602d6aab99f1534f8566f0f22894ccadb0e01f98` |
| tables/rollback_history | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| tables/schema_migrations | `137b7aa176f6ee051098b407671aa765f2605d30ca84062ae305c0de0fed8fd0` |
| tables/tool_calls | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| tables/tool_registry | `fd42bdf3a0e7a928c0a5521376b3b0f732e5eb8b3801d4e82e4cc816e55bcf2a` |
| index_files/DOC-004-blocks.json | `6d6dc775ac632ccda93b0ebc2f65954d53572f5e23417779b04f961afcf1b7eb` |
| index_files/DOC-001-mineru.zip | `b3bb83c6a306c70e4d77fae31771918562015416e26cc3aa65bad2ef6e3a64d2` |
| index_files/source-manifest.json | `dc6aad86c333db4042343d77ec8a34867deb3c59be0f35ecea0748c016099a9a` |
| index_files/faiss.index | `ee5bb4977dcf28f8e2f8d1dfe92dee43e2106797710216958c05654eaacc2164` |
| index_files/DOC-004-mineru.zip | `ab056366a908ed5e3ef3195797fe705e1977848b324c97d2bf6900d7a6841fe6` |
| index_files/DOC-001-blocks.json | `86d6f4ef5bfa8bc329cd1376d420e4c22a8de5af81ac933f536412e5f36a1462` |
| index_files/DOC-002-blocks.json | `365ea72cfa8c75a7d3848e667c47548c0496134057705aed67b8ff390f91d6f0` |
| index_files/DOC-003-mineru.zip | `d848327ef6572c742063bc593f147c952b96f531700a8d4b82c01c61e048f7d0` |
| index_files/parents.json | `3ea4832bda1cc1bf446ba92d8bdd972ce6c399650fc36e033151504a3253b928` |
| index_files/embeddings.npy | `a9ddcb7468286082a6f16ea754281c926cd269ef5c7d0aaa74df42103ac65448` |
| index_files/documents.json | `056335fb99b5f180e24edef54316be1e5aa2d887f3d6bf7884227e147e6de054` |
| index_files/manifest.json | `edef3a1b3d56fe91fc29c3df89db3712ba90c788db47cf794dbebf33d18c7131` |
| index_files/coverage.json | `a4b1bb92692ea804f533a798d426d17b9b685729d7905fb20f418d24ace73551` |
| index_files/chunks.json | `ed52f56b622f8b5d677d1828ec0dd745713f568c71e5412618e34f4131ee3ddd` |
| index_files/full_text.json | `314eab3323aea22036f80fc30053420960ce7e96fd6d0163ee23fde37136c197` |
| index_files/DOC-002-mineru.zip | `4a0045c922154bda52c3acec9167de5307c72c0ee3fc9702b7323f9e6884fa62` |
| index_files/DOC-003-blocks.json | `06ee9785ad508838a90dd1a5bc280258cfd1219fb7ba47664ffb37bcc5a0b7de` |

## 提交与尚未执行的正式步骤

本轮范围内文件与SPEC同一次Commit；提交说明：`feat: prepare Golden VNext draft and opt-in answer contract`。最终Commit SHA在交付消息及`git log -1`可查。提交中的JSON仍为draft_pending_human_review，推送代码/文档不代表批准、冻结、启用或生产发布。工作区开始前已有的存储审计、历史输出、backend/data与verify_self_evolution.py等改动均不纳入本轮提交。

人工下一步：逐题复核30份语义改写与20份行为要求，确认安全隔离、型号、数值/单位/否定方向及辅助项划分；处理来源差异和上列争议；另行审查改写式参考答案的版本化证据真实性校验及检查点消费合同。

未执行：导入新Revision工作集、真实Probe/QC、Human Gate批准、Snapshot冻结、启用新版运行时、Baseline/Candidate/Judge/Agent付费执行、Sandbox、发布或正式Golden切换。若后续需要Provider验证，应先逐项确认调用任务、题目数量、模型/端点、重试及Token限制、未知结果重复计费风险和预算；本轮没有授权，也没有费用估算冒充实扣。

本轮到此停止，不进入Judge修复或下一轮付费评测。
