# Bad Case有效性与Agent自动优化收口 · A—H验收

日期：2026-10-14。真实Provider调用0、费用0；未重跑评测、未创建正式Candidate、未执行Sandbox。停止等待用户在前端运行Agent。

## A · 当前正式基准与结论

只读核查Run `EVAL-20261014123620266091` 的数据库原始答案、同次Judge、Matcher、完整Trace、冻结Golden与真实PDF。Overall **95.80**、Hard Gate **11/11**，原始失败 **Q03/Q06/Q10共3题**，其中有证据的真实RAG技术失败 **2题：Q03 Generation、Q10 Retrieval**；Q06仅质量审计。原始失败、所有历史评测与资格阻断均保留，不制造20/20通过。

朋友两份参考ZIP的来源SHA复核一致，沿用 Baseline → Bad Case分类 → Agent策略 → A/B/C → Sandbox → Regression → Recommendation；未增加导航、工作台或人工审批。

## B · Q03：配置映射错误，Generation

PDF第40页“无对接站，含加注系统”对应软管接头流程，明确“填满清水箱之后自动停止加水”；第40页末“无对接站，无加注系统”接第41页加注口、手动关闭进水流程。

实际回答将当前“无对接站、含加注系统”确定解释为加注口流程，并总结“加水应观察液位、填满后手动关闭进水，资料未说明会自动停止”。Final已有C115自动停止与C117手动关闭两条原文；同次Judge定位了停水主张矛盾。因此主根因为Generation。C114/C116配置标题未进入候选/Final，是适用范围上下文不足的促成因素，不能称为“完全没有召回自动停止事实”，也不能据此把主根因改成Retrieval。

正式目标：Q03。可验证方向：`grounded_generation`，在原Search Space内选择生成策略，验证是否按适用配置使用证据、来源未闭合时是否避免确定映射。当前默认已为Grounded，不能再把相同参数冒充有效Diff；替代策略仍须由Agent说明假设与风险，Sandbox验证，未承诺效果。

## C · Q06：主体正确，附加版本断言未闭合

PDF第57—63页逐项核查：手动清洁必要步骤对应C140/C141，Judge Correctness/Faithfulness/Completeness为 **4/1/1**，Final充分。唯一pending为“该资料未给出版本号，以下不猜测其他版本”，原因是片段与version=null不能证明整份文档没有版本号。实际未出现answer_quote_unlocated或source_quote_unlocated；不能误称定位器故障。

补充实时地图图例来自示教路线章节，不能未经范围核验当成手动界面事实；补充结束清洁顺序在手动章节PDF58/C142也存在等价原文，不能只因另一引用跨章节就断言幻觉。现有证据没有证明RAG技术故障，不形成正式调参目标。保留具体附加主张/适用范围审计、原判定及正式资格阻断，不自动Passed，不为Q06硬编码放行，不修改Golden。

## D · Q10：候选召回阶段缺少必要检查事实

真实PDF46：C127列检查1—3；C128/P127包含传感器清洁、重新启动、障碍物检测及安全开关不能返回初始位置时停止运行等后续要求。本轮CandidateK=12、Rerank=12、Final TopK=4；C128及等效事实没有进入三个阶段；Final为C127/C24/C23/C126，C127并不包含后半清单。实际答案遗漏相应事实，同次Judge completeness=0.5，并保存必要事实缺失。

诊断还交叉核对冻结Corpus、源PDF SHA、完整Canonical Child/Parent Final、文档/产品/版本约束、Judge事实支持及回答遗漏；不单凭Chunk ID判失败。结论为 **Retrieval / candidate_recall**，不是Rerank把已召回证据丢弃。正式目标：Q10。允许提出`query_expansion`或`candidate_recall`中的一个单一假设；不证明增大K一定有效，不预设向量或BM25算法故障。

## E · 本次修复的通用机制

过去必要事实检索诊断被全题`pending`整体否决；Q10另一个附加“资料未给出测试步骤”等主张未闭合，掩盖了独立充分的召回遗漏依据。本次仅解除这条全局否决，原Corpus/适用范围/Final/等效事实/同次Judge全部防护继续保留。无法证明缺口仍不归因。

诊断视图分开技术证据与`evaluation_quality_audit`；二者可以同题并存。技术列表、根因统计及策略输入须四类技术根因、实际Trace和至少一个合法干预方向；旧状态、未证明的次级根因、质量审计标签不参与技术统计。质量审计保留具体原因与原始证据，通过既有详情卡/高级审计查看。

## F · Agent策略与残留路径

ABC及D共用策略输入投影，只传已验证失败、Golden必要事实/参考答案、实际回答与Trace；非技术案例和完整评测质量审计仅在本地审计保留。D亦不接收历史候选里的原始目标诊断及Baseline检查点。保存前仍由统一校验器验证实际Diff、单一假设/方向、同主根因、参数依赖、逐目标Trace断言与风险；未采集事实不作为假设依据。未知目标或Q06类审计目标被拒绝，0–3候选规则不变。

四类方向按证据选择，不固定参数：Retrieval先区分召回与排序，再验证查询/候选池/上下文假设；Generation验证证据使用与生成策略；Safety验证真实拒答边界及后续操作；Performance按实测独立瓶颈验证相应合法参数。隔离Mock分别产生四类合法且不同的策略/Diff并经过真实保存前校验；这是软件机制验收，不是模型效果证明。

当前正式数据库的隔离副本另完成一次本地Mock：仅Q03→生成策略、Q10→候选池策略生成两项隔离提案，Q06不进入策略输入；没有创建正式Candidate。原始3题及历史记录保留。

## G · Baseline与数据保护

仅诊断与Agent衔接修复，未改变评分语义，保持Judge `judge-v3.4-scoped-reference`、Matcher `evidence-v7-scoped-reference`、Policy `v1.6-evidence-diagnosis`。当前正式Run、20题Golden、Corpus、配置及Evaluation Identity一致，API `requires_policy_upgrade=false`、`requires_new_baseline=false`。**无需重新运行Baseline，可由用户直接启动Agent A/B/C，后续Sandbox继续以本Run为正式对照。**

已有原始失败、评测完整性、Regression与Candidate资格检查不能因独立质量审计而绕过。11项Hard Gate、三个Human Gate、Search Space、默认参数、Golden及知识资产不改。架构唯一源已检查，主流程与节点职责未变化，无须重画或导出另一套图。

## H · 验证与交付

- 后端全量610项通过（366.747秒）；变更后定向44项通过，覆盖四类策略Mock、质量审计隔离、真实缺口与来源/身份防护。
- 前端：39文件、221测试；TypeScript/Vite构建通过。
- 真实浏览器1440/390px：Baseline/Agent技术表仅Q03、Q10；Q06质量审计可打开，五卡详情及原始审计保留，原始失败3题；无溢出、控制台错误、写请求或外部请求。
- SQLite Backup API备份后重载本地API，无活动业务任务；29张表逐表内容摘要、78个知识资产文件SHA复核保持不变。
- 仅隔离Mock；Provider0、费用0，未执行任何人工Gate、评测、正式Candidate或Sandbox。

可复查本地产物位于 `output/playwright/badcase-validity-20261014/`：audit.json（原始PDF/Golden/Judge/Matcher/Trace）、derived.json、saved-data-mock.json、browser-report.json、桌面/手机截图及数据保护摘要。该目录为本地忽略产物，源代码与本验收文档进入Git。
