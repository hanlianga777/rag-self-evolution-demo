> Historical：本页保留初次生成结果；当前集中修订结果见[最新收口验收](MEDIUM_V2_POLISH_VERIFICATION.md)。

# Medium Golden V2 实施与真实验收（2026-10-08）

独立Run `GGEN-20261008050011728151`，Plan `PLAN-5bc41ca6f943757baa34de61`，Knowledge `KNOW-20261005060656904283`。实施基线与origin/main均为 `cdce03549cd5694c09c391ef6680f8d74258fc1c`。

## 当前实际结果

- 新生成50题，Positive20 / Ablation10 / Negative20；Hard Validation50通过。
- 九Topic Slot数：T0018、T0028、T0032、T0046、T0053、T0065、T0075、T0088、T0095；Slot Gap0。这是材料主题覆盖，不等于全部业务领域或50题全部合格。
- Business Audit46通过/4失败；语义重复风险2题（Q41、Q49），保留原始Judge结论。
- Probe49通过/1失败；QC48通过/1失败P0/1因Probe失败未执行；Machine Qualified38 / Human Review12 / Human Approved0。
- Human Gate1 Pending：保留12项真实人工关注，不能冻结。未执行批准、Snapshot冻结、Baseline或Agent。
- 难度目标10基础/25中等/15复杂；独立Judge实际观察11基础/26中等/13复杂，不为了比例修改合格题。角色30售后/现场运维、10终端客户/操作员、10技术支持/客服。
- 负向业务配额6无答案/5缺条件/5产品混淆/2范围外/2安全权限；映射Subtype及拒答/澄清规则保持。现有手册不足以证明价格、保修、远程权限或不存在的版本等领域可答；Negative Anchor仅是材料Topic锚点，不是答案Evidence。

## 有限修复与真实Provider

- 初次50题构造仅1个Slot触发一次Hard Validation重试。初始Business Audit35 / Probe40 / QC40 / Machine27。
- 一轮18个失败Slot定向内容修订：17个替代版本入库；15个Revision流程completed、2个failed_quality；Q49草案未过冻结安全契约，未应用。Revision completed不代表机器资格通过。
- 6个修订响应遗漏业务场景/意图：各一次仅元数据提取，问题/答案/Evidence不变；新内容身份下重新执行Audit/Probe/QC，六题Probe/QC均通过。Q48原needs_revision标记保留给人工处理。
- 原工作集中27个初始机器合格题没有重生成、替代或修改；其记录逐行比较保持不变。
- 记录可去重的DeepSeek调用203次，输入3,071,853 / 输出641,266 / 总3,713,119 tokens，调用累计耗时3,423,830ms。
- Alibaba真实Embedding/Rerank调用166次，总205,199 tokens，调用累计耗时58,287ms。不是重新Embedding整个Corpus或重建索引。
- 已记录传输失败0；存在4次已知schema拒绝响应未保存Usage（3次初始格式错误+Q01一次格式重试），及1次中断时在途响应状态未知。以上统计是已保存记录的下界，不声明准确总费用或全部调用均成功；格式失败未伪装成质量通过。

## Candidate Pool与验证

- 默认浏览摘要/来源/评测组/质量/搜索、五列列表；Profile/PAN/Topic/复选框仅在创建Golden组建模式出现，返回浏览清空选择。机器合格/人工通过/待治理准确区分；已执行但未通过的Probe/QC显示实际通过数量与待处理，不能显示待开始。
- 保留30条分页、SWR、详情懒加载、导入与800px Drawer；八页设计系统和业务规则复用。
- 后端346项隔离离线测试通过（324.481s），测试副本隔离DB/Corpus/索引/.env、阻断外网；Fixture不是真实Provider验收。前端170项测试通过，TypeScript/Vite Build通过，git diff --check通过。
- Chromium：1440×900、1280×800、1024×768，八页及Pool浏览/组建/Drawer共33项；无页面脚本错误、Load failed或水平溢出。浏览5列/30行、无配额和选择框，组建显示配额和复选框；Drawer800px/Escape通过。截图另作人工视觉检查。
- 不修改正式架构SVG关系；业务处理说明更新于架构文档，图形仍以KnowledgeDiagrams.tsx为唯一源。

## 数据保护

- SQLite Backup API与文件副本先于真实写入建立：本机 `output/playwright/medium-v2/before.db` / `protected/`，未提交含真实数据的DB、日志或凭据。
- 实施前28张非系统表的全部原始行保持；原431题、121审计、164审批、202事件保留。允许新增本轮Run/题目/质量/修订记录。
- 原Full100题及13人工批准不变；原5个Snapshot不变，包括用户已冻结 `GD-20261008024214127995`。Production2、Legacy及历史Evaluation/Agent记录不变。
- 30个Corpus/Index/Manifest/PDF/Legacy关联文件SHA-256全部一致；仍4PDF157页349Parent368Child1024d9Topic。

## 剩余12题：必须由人工处理

| Slot / Question ID | 真实原因 | 建议人工动作 |
|---|---|---|
| Q01 / `V1G-050011728151-01-R055355561504` | 检索不连贯 | 对照召回Child/Parent与Golden Evidence，决定接受P1风险或定向修订 |
| Q08 / `V1G-050011728151-08` | 检索不连贯 | 对照召回Child/Parent与Golden Evidence，决定接受P1风险或定向修订 |
| Q10 / `V1G-050011728151-10-R055750541498` | 题目质量需修订；Business Audit：diversity | 重新审阅难度目标与题目价值，人工要求定向修订；不要把false改为true |
| Q13 / `V1G-050011728151-13` | 检索不连贯 | 对照召回Child/Parent与Golden Evidence，决定接受P1风险或定向修订 |
| Q18 / `V1G-050011728151-18` | QC P1；检索不连贯 | 对照召回Child/Parent与Golden Evidence，决定接受P1风险或定向修订 |
| Q22 / `V1G-050011728151-22` | QC P1 | 核对QC依据与业务预期，人工决定是否接受P1风险 |
| Q25 / `V1G-050011728151-25-R060037640076` | 题目质量需修订；Business Audit：diversity | 重新审阅难度目标与题目价值，人工要求定向修订；不要把false改为true |
| Q41 / `V1G-050011728151-41-R060640861960` | 题目质量需修订；Business Audit：duplicates | 对照其他题干去重，要求本Slot差异化修订与重验 |
| Q44 / `V1G-050011728151-44-R061119366859` | QC 未通过；QC P0；人工标记需修订 | P0阻断，不建议直接接受；确认跨产品预期，另行授权定向修订后重验 |
| Q47 / `V1G-050011728151-47` | QC P1 | 核对QC依据与业务预期，人工决定是否接受P1风险 |
| Q48 / `V1G-050011728151-48-R061624696809` | 人工标记需修订 | 最新Audit/Probe/QC已通过，但需人工处理原需修订标记，不能自动清除 |
| Q49 / `V1G-050011728151-49` | Probe 未通过；QC 未通过；证据需复核；题目质量需修订；人工标记需修订；Business Audit：diversity,duplicates | Probe失败且语义重复；未应用安全草案，不放宽规则；另行授权定向修订并只验该Slot |

逐题原问题、答案/预期、角色/场景/意图、Child/Parent、PDF页码、质量记录：[完整50题审阅报告](../backend/reports/golden_dataset_v2_medium_review.md)。

## 八类真实截图（本机）

- `01-workset.png`：`output/playwright/medium-v2/01-workset.png`
- `02-question-list.png`：`output/playwright/medium-v2/02-question-list.png`
- `03-positive.png`：`output/playwright/medium-v2/03-positive.png`
- `04-ablation.png`：`output/playwright/medium-v2/04-ablation.png`
- `05-negative.png`：`output/playwright/medium-v2/05-negative.png`
- `06-pool-browse.png`：`output/playwright/medium-v2/06-pool-browse.png`
- `07-pool-assemble.png`：`output/playwright/medium-v2/07-pool-assemble.png`
- `08-coverage.png`：`output/playwright/medium-v2/08-coverage.png`
