# RAG自进化Demo：Agent端到端整改报告

2026-10-22。起点为GitHub最新main `88c4f77832ebf6d35b0f188204bd9513bd6123e6`（HTTPS fetch已核对）。本轮只证明流程打通，**没有证明10题已被真实修复**。真实Provider调用0、API费用0；正式服务未重启，发布/回滚和人工审批未操作。

## 1. 核心根因：把“允许实验”误当成“根因已经证明”

正式Baseline仍是 `EVAL-20261021141811373593`，50/50完成、40 PASS/10 FAIL、Overall 91.5、11/11 Hard Gate通过。

此前只有Q08可以实验。Q03虽已有Ranking发现，但`context_selection_options`在实验前要求一次配置同时恢复全部必要规范并保留旧通过项引用，结果没有可用配置。其余8题仍为Unknown；新版代码虽然全量送入Agent输入，但`validate_intervention()`仍要求`target_eligible=true`且所有目标根因已经确认一致。`root_cause`字段也不接受Unknown。于是“进入Agent输入”并不意味着能成为合法Candidate。

诊断任务又统一指向`resolve_saved_execution`；真实9次补证全部未闭合，Agent被困在补证阶段。继续修改JSON或语义Prompt不能消除这一产品设计循环。另有前端双重过滤：策略关联图和目标Drawer只保留已确认技术目标，Unknown即使关联候选也不可见。

本轮把两件事分开：**已证实的技术诊断仍需严格证据；未证实的原因可以基于真实观察开展可证伪实验。** 受控试验可以失败；正式推荐仍必须经过同一冻结50题验证。

## 2. 审计范围与问题分类

- 产品设计缺陷：诊断确认与实验资格绑定；补证成为唯一前置；策略关联只展示技术子集。已整改。
- 代码衔接缺陷：Unknown枚举/干预验证无法表达探索；合法配置缺少执行前的完整Diff复验；旧本地检索路径未保存完整重排列表/完成状态。已整改。
- 数据与证据状态：已只读核对全部10题的冻结Golden、参考答案、原答、原Judge以及12候选/12重排/4个Final；全部冻结规范来源在368个Canonical Child中可读。**没有发现足以认定这10题必须先修解析器的证据**。语义复合要求、型号分支与现场适用性仍有未知，原Judge/Resolver记录不回写。
- 真实RAG能力限制：TopK最多6、CandidateK最多24，来源切片/OCR/元数据与Prompt存在能力上限。参数实验不保证修复。若规范不可读、身份不匹配、Judge无效或完整Trace缺失，则明确形成`repair_sources_or_trace`/`review_evaluation`任务，不能伪造参数方案或强制通过。

已检查diagnostics、evidence_resolver、optimization、governance、evaluation、policy、retrieval，以及AiService实际参数传递和前端两工作台。Resolver本轮保持原校验，不再作为未知根因实验的必经付费前置；policy、Judge合同、11 Gate与Regression评分函数未改。

朋友原始参考已实际查看：产品成果参考中的`流程2.png`、`流程3.png`及视频截图`163306_737.png`，并核对现有朋友对齐矩阵。沿用“Baseline→诊断/假设→A/B/C→全量沙箱回归→人工Gate2→条件D→人工发布”，没有照搬其分数、模型或隐藏实现。

## 3. 逐题处理路径

表中配置是绑定真实历史观察后通过验证器的**离线方案样例**，不是新模型输出或真实改善。来源ID覆盖差异只证明结构观察，不能证明语义缺失、事实等价或现场可执行性；Unknown保持Unknown。

| 题目 | 原Judge失败现象（摘要） | 当前根因 | 优化假设与验证方向 | 离线执行路径 |
|---|---|---|---|---|
| Q03 | 创建用户前需从KIRA B 50主菜单按下设置按钮，显示并进入设置菜单。 | Ranking | 候选有设置入口却未进Final；扩大TopK或改排序可能恢复入口，需同时检查已满足内容是否退化。 | `{"top_k": 6}` 合法；未验证效果 |
| Q04 | 长期存放/运输时应注意设备重量（手册存放/运输注意事项）。；设备只能在室内存放。；当前操作适用性：对 KIRA B 50 停用三个月存放，执行前需确认型号、只在室内存放及设备重量安全前提；回答确认了 KIRA B 50 … | Unknown | 存放/重量规范有候选与Final双重缺口；先扩大候选池，对照安全前提覆盖。 | `{"candidate_k": 24}` 合法；未验证效果 |
| Q06 | 对于电池供电的设备，清洁前必须拔出电池插头或断开电池连接。；决不能用湿手触及电源插头或者插座。 | Unknown | 电池隔离、湿手禁令来源在候选中却未完整进入Final；排序/上下文实验，不能把只断对接站电源当充分。 | `{"rerank": "query_only"}` 合法；未验证效果 |
| Q07 | 清洗/保养 KIRA B 50 前必须关闭设备；对于电池供电设备，必须拔出电池插头或断开电池连接。；对当前 KIRA B 50 停在对接站上、清洗污水箱粗大污染物滤网的现场操作，开始前必须确认设备已关机、电池已断开/拔电… | Unknown | 滤网步骤已有，维护前断电来源未召回；扩大候选，检查断电与机械步骤是否同时覆盖。 | `{"candidate_k": 24}` 合法；未验证效果 |
| Q08 | 长时间未使用接触式充电器，使用前先清洁充电板表面；擦拭时先关闭电源，使用干燥软布擦拭充电板表面和机身底部充电电极，尤其确保擦拭干净。；清洁充电板表面/充电电极时严禁使用金属刷、砂纸等，以免刮伤表面。；当前B2充电器定期保… | Ranking | 已核验排序遗漏清洁规范；可走已确认top_k=6方案，也可作为有证据的对照。 | `{"top_k": 6}` 合法；未验证效果 |
| Q17 | R3 遥控器首次绑定的具体步骤：在 Unitree Explore App 中进入【设置】->【遥控器设置】，打开遥控器开关，输入对应的遥控器编码，与机器狗上的数传模块绑定。；R3 遥控器配对成功后的确认标志：遥控器开机… | Unknown | R3/R1分支来源未全召回；扩大候选后核配对步骤、DL指示与未知现场型号，不能混用分支。 | `{"candidate_k": 24}` 合法；未验证效果 |
| Q24 | 使用清洁剂运行时，洗涤剂应远离孩童妥善保管。；不得未稀释使用推荐的洗涤剂（应按要求稀释使用）。；洗涤剂不慎溅入眼睛时必须立即用水彻底冲洗；若不慎吞咽应立即就医。；遵守清洁剂制造商的使用、处置和警告说明，而不仅是笼统的包装… | Unknown | 清洁剂安全规范候选缺口；扩大候选验证稀释、孩童隔离、急救与制造商要求。 | `{"candidate_k": 24}` 合法；未验证效果 |
| Q27 | KIRA B 50 的地图不具备自学习功能，不能自动补充新障碍物或吸收布局变化。；对原始布局进行细微改动通常不成问题。；布局改动越大，设备清洁效率越低。；如果布局发生重大变化，必须重新示教该路线。；当前场地重摆桌椅的规模… | Unknown | 地图规范已在候选却完全未进Final；query_only排序作为探索，核重大变化/重新示教与现场条件。 | `{"rerank": "query_only"}` 合法；未验证效果 |
| Q28 | 更换刷辊属维护换件：更换前必须关闭设备；电池供电的设备必须拔出电池插头或断开电池连接；执行任何工作前必须将设备与对接站断开，或拔出电源插头。当前现场仅知清洁机组已打开，未确认整机停机、断开电池/电源及对接状态，不能把机械… | Unknown | 机械换件步骤已答，维护停机/供电/对接前提来源未召回；候选扩展并保留原有机械步骤。 | `{"candidate_k": 24}` 合法；未验证效果 |
| Q29 | 重新使用B2前不带电检查应覆盖整机外观：机身外观清洁、无破损或变形痕迹，相机表面镜片无异物，头部激光雷达周围无异物遮挡。；重新使用B2前不带电检查应覆盖结构：目视及触摸检查机身、各个关节及连接处、足端组件是否完好，有裂纹… | Unknown | 整机不带电检查表来源未召回；扩候选/查询实验，核整机与充电器范围，不能靠改Judge修复检索。 | `{"candidate_k": 24}` 合法；未验证效果 |

离线策略Fixture按“根因状态+相同干预”分为3个配置：分别为Q03/Q08的TopK对照、6题候选扩展、Q06/Q27的query_only排序；标签按保存顺序分配。所有10题均有路径，不是一题一个Candidate。模型在下一轮也可基于相同真实资料提出其他有据方案；这里不硬编码题号到生产代码，不强迫真实Agent复现Fixture。

## 4. 修改机制与保护

1. `diagnostic_view.experiment_plan`增加独立实验路径，先复用现有Judge/Canonical/完整阶段/Corpus身份检查，再根据冻结来源的候选、Final差异形成观察、失败要求、假设、风险、证伪条件或能力任务。保留原`target_eligible`及技术根因，不把探索标成确诊。
2. Candidate区分`confirmed`和`exploratory`。后者只接受计划中的方向/观察、真实Diff、合法离散参数和证伪说明；禁止虚构根因、无依据跨阶段改动、空Diff及越界参数。多参数仍需必要依赖，已确认方案原合同保持。
3. 新合同`agent-closure-3`在Sandbox创建/预算预留前重新检查保存配置、完整Diff和当前目标。D只组合已全量验证、同身份、Regression通过且有真实修复来源的参数；逐来源干预复验，组合之后仍须独立完整Sandbox，不继承来源成绩。
4. Agent工作台展示全部业务FAIL的处理路径与策略关联，明确区分已确认、可探索、能力修复；沿用八个一级导航、原列表和Drawer。已确认技术统计仍不混入Unknown。唯一架构源已同步并导出SVG/PNG/manifest。
5. `EvaluationRunner`继续以Candidate实际配置调用AiService/检索，全部冻结50题同时构成Sandbox与Regression；不额外再收费重复跑一遍Regression。修复/新增失败按唯一题号逐题比较，剩余问题按同一个已验证配置计算，不把不同候选修复相加。

没有修改Golden、人工审核、正式Baseline/原Judge、Corpus、索引或历史实验；没有放宽任何引用/来源/安全要求、11 Gate或严重0/普通≤1 Regression标准；没有安装新依赖或对10题写专用逻辑。测试产物全部在临时库或隔离副本；每次核验仅建立一个SQLite Backup临时副本，结束即删除，不保留数据库备份。

## 5. 验证结果与真实效果边界

- 真实数据只读/隔离核验：10/10进入Agent，10/10能形成合法探索干预；生成3个隔离Fixture候选。Q08原确诊路径保留，其余9题不再必须补证闭合才能试验。当前未出现必需先修材料的题；能力缺口分支另有缺来源/错身份/缺Trace/非法Judge测试。
- 正式冻结50题的隔离端到端：10题驱动3个合法候选，3个候选各完成原冻结50题，共150条隔离逐题结果。生产BM25/融合/选择/Parent/TopK、身份/存储/回归照常执行；向量分数、云重排、回答和Judge明确使用Fixture。固定失败占位输出各0修复/40新增失败，全部不合格、不推荐；这验证真实冻结链路能执行和拒绝失败方案，不是业务效果。原Baseline记录及原库哈希不变。
- 可控50题离线统计测试：真实OptimizationAgent→保存Candidate→AiService→VectorRetriever（仅向量模型/回答/Judge用Fixture）→Sandbox→逐题存储→Regression→Recommendation状态。TopK由4到6，50题实际Final均为6条。故障注入得到修复2题（目标1/附带1）、新增普通失败1题、净改善1、总失败9；11 Gate仍真实计算，未通过资格不推荐，直接发布被拒绝。
- 额外保护：无依据参数、虚构根因、无证伪条件、配置篡改、来源/身份缺失拒绝；不同候选修复不相加；原版本、预算、人工批准、D和发布/回滚保护定向测试覆盖。
- 浏览器隔离预览：8导航、10行问题、9行可探索、10个策略关联，无页面异常、无写请求。[问题列表截图](../outputs/agent_e2e_20261022/agent-offline.png)与[策略关联截图](../outputs/agent_e2e_20261022/agent-links-offline.png)只代表本地Fixture预览，不代表正式服务已经加载新代码。

**离线模拟**：Agent策略响应、向量候选、生成回答与Judge，及上述“修复2/新增1”均为Fixture；它们只验证执行和统计。

**历史真实证据**：正式50题原答/原Judge、10题三阶段Trace、冻结Golden/Canonical正文与原Q08诊断。真实9次补证历史仍是0/9闭合，未改成成功。

**尚待真实验证**：新Agent能否提出有效差异化方案，扩召回/排序/Prompt是否改善实际答案，全部50题安全/质量/成本/延迟是否满足正式资格。真实新答案0，真实新增修复0。不能宣称10题已修复。

## 6. 可重复命令与全量失败披露

在仓库根目录，使用已有Python/Node环境（不需新增依赖）：

```sh
# 禁出站TCP、空凭据、隔离DB/索引/.env；以下定向检查应通过
python3 scripts/test_agent_offline.py test_agent_exploration test_agent_exploration_e2e test_agent_closed_loop test_intervention_contract test_optimization_contract test_candidate_resume test_evaluation_governance test_evaluation_vnext test_paid_run test_governance
# 全量；有下表既有失败，命令诚实返回非0
python3 scripts/test_agent_offline.py
npm --prefix frontend test -- --maxWorkers=2 --minWorkers=1 --no-cache
npm --prefix frontend run build
# 只读真实库核验；在原资料所在仓库，默认路径即可；在独立副本须显式指定真实库/只读索引/文档
python3 scripts/verify_agent_closed_loop.py --run EVAL-20261021141811373593 --output /tmp/agent-exploration-check.json
```

55份正式库/索引/诊断资产逐文件哈希前后完全一致。测试完整输出和数据保护见[验证摘要](../outputs/agent_e2e_20261022/verification.json)。整改前845项，5失败/2错误/14既有跳过；整改后854项：833通过、5失败、2错误、14既有跳过；新增失败0。定向168项：165通过、3既有跳过。前端255项通过，构建通过。未删除/跳过失败测试；一个旧Trace成功状态断言由collected改为completed，与本轮补齐真实阶段记录的合同一致。

| 既有问题 | 本轮核对 |
|---|---|
| `test_api` 四份正式PDF | 隔离空索引不包含原API初始化资产；整改前后均失败 |
| `test_api` Mini生成状态 | 旧初始化/生成Fixture不满足当前入口；整改前后均失败 |
| `test_api` Partial禁止新生成 | 先被隔离索引缺失阻断，与旧预期顺序不同；整改前后均失败 |
| `test_machine_gate` Knowledge身份 | 旧Fixture缺少knowledge_identity；整改前后均错误 |
| `test_baseline_resilience` 原无效响应 | 旧Judge Fixture与当前业务合同不符；整改前后均失败 |
| `test_judge_evidence_roles` Ranking预期 | 历史响应不足以证明当前严格Ranking；仍Unknown；整改前后均失败 |
| `test_generation_storage_legacy` 子进程 | 当前独立副本无私有backend/data/legacy_index.json；额外环境错误，整改前已复现，不冒充新增代码故障 |

上述前6项就是此前报告中的6项，既有跳过也保留。没有为得到绿灯放宽正式代码。新增测试曾暴露Fixture空Corpus身份和历史UI兼容问题，已修正隔离Fixture和对应产品过滤；末次结果单独留存，不用中间失败冒充历史。

## 7. 下一轮一次性调用与预算方案（未授权、未执行）

建议一次性限定A/B/C为TopK、CandidateK、query_only三个有据对照；其余冻结配置保持（含Abstention、Rewrite/MultiQuery/HyDE关闭）。可先由1次Agent规划，无法按证据形成方案则停止，不强行凑3个。下表是不重试的最大完整范围；实际少于3候选则减少。**Regression就是每个Sandbox的同次全50题比较，不重复算调用。** 不补跑Baseline，也不要求先付9次诊断费用。

| 阶段 | DeepSeek | Alibaba Query Embedding | Alibaba Rerank |
|---|---:|---:|---:|
| A/B/C规划 | 1 | 0 | 0 |
| A/B/C各50题回答+Judge（含Regression） | 300 | 150 | 100（C为query_only，0次云重排） |
| 有条件D规划：仅人工Gate2后有有效来源 | 1 | 0 | 0 |
| D全50题回答+Judge（含Regression） | 100 | 50 | ≤50 |
| 合计上限 | **402** | **200** | **≤150** |

即A/B/C正常范围551次远端请求（301 DeepSeek+150 Embedding+100 Rerank）；含有条件D最多752次。Query-only本地排序0费用。无真实响应前不知道是否具备D来源，Gate2不自动批准；没有来源或人工Gate2则不运行D。若Agent建议启用Rewrite/MultiQuery/HyDE或其他请求拓扑，不在此预算方案内自动执行。失败重试也占同一总调用上限，不承诺出错后仍能完成全部范围。

2026-10-22只读取官方价格页：DeepSeek Flash按高峰未缓存输入2元/百万、输出8元/百万；北京区text-embedding-v4及qwen3-rerank输入均0.5元/百万，输出不收费。[DeepSeek官方定价](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)、[阿里云官方定价](https://help.aliyun.com/zh/model-studio/model-pricing)。旧模型别名的实际服务模型遵官方说明；执行前仍重新核价与加载配置，不擅自改冻结模型身份。

预算示例以2次Agent各输入≤200k/输出≤16,384，200次回答各输入≤20k/输出≤8,192，200次Judge各输入≤80k/输出≤32,768，Alibaba输入合计≤20M估算：1.062144+21.1072+84.4288+10=**116.60元**。输入是规划预留，绝非实测Token或费用保证；大请求由现有PaidRun按实际payload逐请求预留，仍保留Baseline冻结输出上限。

建议下轮一次性申请**人民币200元硬预算、上述总调用范围**，按真实Usage结算；预算/身份不符或Unknown未结算请求即停止，不自动加钱或补授权，不跨拆批重发。200元是建议上限，本轮没有建立付费授权或调用Provider。若超出输入预留需要减少请求或停止，不能隐瞒费用。人工发布/回滚不在授权范围内。

本轮整改完成后停止，等待下一次真实实验授权。
