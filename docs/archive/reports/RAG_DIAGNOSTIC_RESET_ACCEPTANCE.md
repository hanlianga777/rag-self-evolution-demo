# RAG机制修复与清理验收 — 2026-10-14

## A. 修改摘要

Ponytail full执行：统一四维指标与诊断展示，约束Agent单一技术干预，修复评测治理状态和混合注入拒答合同，补齐生成输入来源与操作边界，局部完善两工作台，事务清空旧实验并建立完整对象保留。复用现有JSON reasoning、后台监控和UI组件，无新依赖、一级导航或数据库架构重建。

本轮真实Provider调用0、费用0元；真实Baseline/Candidate/Sandbox/Probe/QC/Mini均未执行。没有冻结、人工批准、发布或重建正式Knowledge。

## B. 根因修复

| 原问题 | 通用修复与证据 |
|---|---|
| 某Golden Chunk未进Final便描述为召回失败 | 同时检查实际候选、Final和语义充分性；必要Chunk全在候选、Final遗漏且Judge确认不足才确认排序遗漏；语义充分时不派生检索失败。离线完整/缺失成对测试。 |
| 现象、根因、评测争议混用 | 复用四根因及三种可信度；多标签现象独立，治理争议不得直接成为Confirmed调参目标。无依据技术操作和注入失败读取已保存结构化证据。 |
| Pending正式阻断被称作已确认退步 | 保存evaluation_outcome，Regression分正式阻断与confirmed/pending/disputed/unclassified；资格仍保守阻断。 |
| 正文拼接丢失来源适用范围 | 文档身份共享一次，每Chunk保留ID、章节、页范围和原正文；真实版本才传，不推断。测试真实answer请求结构。 |
| Agent参数合法但缺少可验证因果链 | 保存前验证真实目标、Trace、证据断言、声明方向、实际Diff及必要联动；D复用同一约束。 |

历史审计中Q07/22/23/30/38/39/47/48提供机制背景；生产逻辑没有按题号分支。测试构造对应结构化输入验证一般机制，不将历史模型输出重新评分或冒充新Provider结果。

## C. Agent控制变量

Search Space仍使用原校验；新增validate_intervention检查：所有目标均为真实Confirmed、同一主要技术根因、实际候选和Final Trace齐备、观测断言符合Trace、一个明确干预方向、非空Hypothesis/Why/Expected Improvement/Risk，以及Baseline到Candidate的真实有效差异。同方向多参数须以依赖说明覆盖全部变化。

会拒绝：Final已充分却声称recall_missing；没有Trace的人工Monitoring判断；CandidateK与TopK直接混改；Metadata Filter与Prompt直接混改；Rewrite与MultiQuery同开却无必要联动说明；D的完整组合跨方向；无实际变化或非Confirmed目标。无足够依据可返回0个或少于3个候选，保存insufficient_evidence，不制造A/B/C。

## D. Judge / Matcher

Judge=`judge-v3.3-operation-scope`，Matcher=`evidence-v5-claim-scope`，Policy标识=`v1.4-governance-outcomes`。policy.py与修改前完全一致：11 Hard Gate、Overall和Regression严重0/普通≤1均不变。

确定性成对检查覆盖保守停用/求助与新增技术操作、排他性主张一致性、reason称“不阻断”但结构仍pending、条件式资料与授权、来源适用性，以及混合注入中的严格supported_abstention。后者仍要求连续引文、完整依据和无后续技术操作。Pending/Disputed不自动PASS，Judge不能决定Qualified。

结构化“confirmed”不等于独立业务事实确证。真实LLM的忠实性、产品适用性、拒答合理性、技术操作分类仍待同一新Evaluation Identity的Mini验证；本轮只证明代码、输入合同和确定性规则。

生成输入对历史150组Final的本地字节统计：Baseline/A由123,084增至144,133（各50组），B由168,424增至195,592。共享身份避免逐Chunk重复；保留全部正文。约16–17%的字节增量仅为输入观测，不能当Tokenizer结果或费用改善。

## E. 历史数据清理

先核实无活动任务、停止现有API写入，只做一次SQLite Backup API备份：`/private/tmp/rag-experiment-reset-20261014.sqlite`（0600）。在原库事务清理，随后VACUUM；没有删除demo.db或重建数据库。外部原审计留在output且不入Git，不导回活动库。

| 对象 | 清理前 → 后 |
|---|---:|
| questions / datasets / Golden runs | 590 / 7 / 17 → 0 / 0 / 0 |
| Probe / QC / review / quality audit | 650 / 544 / 382 / 300 → 全0 |
| Evaluation runs / cases / Bad Cases | 43 / 1,337 / 364 → 全0 |
| Experiments / Candidates / Agent traces | 8 / 22 / 15 → 全0 |
| Approvals / recommendations / Monitoring | 264 / 5 / 4 → 全0 |
| Revisions / artifacts / previews / demo_state | 145 / 17 / 6 / 2 → 全0 |
| Production | 2 → 1个全新bootstrap运行配置 |
| migrations / tool registry | 6 / 5 → 7 / 5 |

其余tool_calls、triggers、rollback、导入批次均0；别名及Pipeline草稿原来即0并原样保留。保留当前Provider/Pipeline文件与原活动参数：Abstention、CandidateK12、TopK4、Hybrid=true/alpha0.5、Rerank=true，其余扩展关闭。原Legacy索引绑定语义不改，bootstrap明确无评测、审批、成绩及正式发布资格。

正式Corpus=`CORPUS-38c90d5628b68c76d53e`，4 PDF、157页、368 Child、349 Parent、9 Topics及索引不变；28个资产/绑定文件SHA-256完全一致。完整性检查ok；全部实验关联表归零，没有旧孤立引用。最终重启后行数与摘要再次一致，旧Seed未恢复。旧Q02启动日志只豁免已清除Golden依赖，仍严格检查Corpus/索引/State身份。

后续每60秒按依赖闭包保留最近50个非引用已结束实验/评测和历史Golden对象；活动、当前及引用对象豁免。保留Production回滚审计链、续跑/答案回放父Run、题目谱系、完整导入批次和进行中的修订。Case/Trace随对象，Full100不截断；预览最多50，导入回执最近50加引用豁免；历史API/UI每页最多50。

## F. 性能结果

同机只读HTTP，每接口3次取中位数；响应体为实际字节。前后同时包含代码、数据库和缓存状态变化，不能归因于单一因素；没有推导改善百分比。

| API | 中位耗时ms：前 → 后 | 返回字节：前 → 后 |
|---|---:|---:|
| `/api/overview` | 1221.93 → 144.29 | 2,446,816 → 580,043 |
| `/api/workspace` | 120.45 → 23.36 | 1,095 → 1,089 |
| `/api/evaluation` | 457.89 → 23.57 | 1,748,356 → 960 |
| `/api/optimization` | 217.57 → 22.99 | 4,727,298 → 960 |
| `/api/dataset?light=true` | 216.29 → 22.93 | 613,882 → 2 |
| `/api/bad-cases` | 1150.22 → 22.89 | 56,173,993 → 2 |
| `/api/versions` | 3.24 → 0.84 | 120,554 → 1,137 |
| `/api/readiness` | 0.61 → 0.54 | 118 → 118 |
| `/api/monitoring` | 111.14 → 23.71 | 6,262 → 999 |

SQLite 295,555,072 → 225,280字节；WAL 0 → 0。唯一外部备份仍保留，不能宣称总磁盘空间净减少同等大小。

相同浏览器流程（打开Baseline，再切Agent；含networkidle）：Baseline冷加载11,161.01 → 1,178.59ms；Agent暖切换106.26 → 58.99ms。单次样本，不作为稳定性分位数。发现的真实负载为历史Bad Case接口56MB及重复序列化；改为当前Baseline集合、历史分页、列表去重复JSON及Checkpoint正文，详情完整。

## G. 测试结果

- 后端：隔离DB/Corpus/.env并封禁出站TCP的全量563项通过（335.906s）；最后诊断展示调整后额外定向33项通过。Fixture索引仅临时离线副本，不能当正式Knowledge重建或Provider验收。
- 前端：38文件、208项通过；TypeScript检查及Vite Build通过。既有测试按新合同更新输入与精确文案，保留Winner回退、重启保护及资格断言；未删除失败测试或降低生产阈值。
- 最终8010重启后：数据库integrity_check=ok、清理计数一致、28文件摘要一致；只读接口Smoke通过，历史limit=51均422。
- 5174八导航全部正确标题，无pageerror/错误提示；Golden/Baseline/Agent空状态、发布bootstrap及问答入口正常。浏览器阻断非GET/HEAD/OPTIONS，不实际问答。
- Knowledge来源Drawer实测800px且可关闭；诊断筛选/详情/Full100两页由前端离线测试验证。真实库已空，没有冒造Case供演示。
- 正式架构由唯一KnowledgeDiagrams.tsx源导出SVG/PNG/manifest；SPEC、Changelog、README同批同步。

## H. Mini20准备情况

仅设计修订清单，没有创建、导入、冻结、Probe/QC或评测：

- Positive8：Q01、04、07、08、11、13、14、20。
- Ablation4：Q22、23、29、30。
- Negative8：Q33、38、39、42、45、48、49、50。

从外部原审计快照核实类别为8/4/8、主Topic覆盖T001–T009；Negative含clarify4、insufficient_evidence2、safety_critical1、prompt_injection1，含Q45/Q49 critical。Q23/38/39加入，原Q25/32/34不再覆盖，存在诊断选题偏差；不称随机代表集。安全拒答95%在8题下仍需8/8，不降低阈值。

已有Mini治理路径具备技术基础，但清理后原Question ID/Medium Slot与来源Run已不在活动候选池，原Medium槽位不能证明新Mini Slot合法。本轮没有正式Slot预览或新Golden身份；不能直接创建正式Mini Snapshot。

下一阶段须用户授权以外部原内容建立新治理候选身份及来源哈希，保持题面，校验当前Corpus/Child/Parent/Topic、Mini Coverage和Slot，完成必要业务审核、Probe/QC及人工Gate1，再独立冻结Snapshot。不得恢复旧实验历史。正式Mini Baseline/Candidate必须同新规则与身份；Probe/QC、Baseline/Candidate及Agent可能产生Provider费用，需后续明确授权和预算。本轮到此停止。
