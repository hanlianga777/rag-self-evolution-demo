# Current Demo Truth

历史真实结果审计日期：2026-09-30（Asia/Shanghai）；2026-10-02 保护检查仍保留原日期。本轮 Interview Demo 的最新只读复核见文末 2026-10-03 小节。下列结果来自真实已保存 SQLite 与界面/API，不是 Fixture，也不是 UI 重构期间重新执行的 Provider 验收。

| 对象 | 当前已保存事实 |
|---|---|
| Corpus | 4 份文档、252 个 Chunk，BGE / FAISS；本轮不重建索引 |
| Golden | GGEN-20260927091054674908 → GD-20260927140329017939；20 题，8 Positive / 4 Ablation / 8 Negative；已冻结 |
| Baseline | EVAL-20260927140423956071；9/11 Gate，7 个 Bad Case |
| A | EVAL-20260928071935034110；10/11 Gate，6 个 Bad Case；Not Qualified |
| B | EVAL-20260928072359044087；7/11 Gate，9 个 Bad Case；Not Qualified，Regression 未通过 |
| C | EVAL-20260928072947134912；11/11 Gate，5 个 Bad Case；Qualified，已发布 |
| D | EVAL-20260928075347604329；10/11 Gate，6 个 Bad Case；Not Qualified，保留 C |
| Production | production-20260928080518；来自 C；Grounded → Abstention；baseline-v1 为初始配置 |

| 历史 Run | 已保存输入 Token | 已保存输出 Token |
|---|---:|---:|
| Baseline | 15518 | 23498 |
| A | 14489 | 18201 |
| B | 23824 | 26280 |
| C | 15758 | 21356 |
| D | 14729 | 22438 |

历史阶段耗时、完整调用 Usage、Judge 费用和计价依据未采集；不回填。历史总回答延迟/TTFT 仍按原记录展示。该次历史运行默认未配置单价。V1.4 新代码已提供版本化价格配置，但不回算这些历史结果。设置页的 Provider 状态仅是 Configured (Unverified)，不代表本轮已验证 DeepSeek。

真实 DB 修改前：SHA-256 `7dee55b5eca5779c6b07f85a5256a4f53f9fd39f95fc87112d5f0ae9a99e6784`，6037504 bytes，mtime_ns `1790582718511204144`。独立备份：`/tmp/rag-phase1-20260930/before.db`。本轮只允许 additive metrics migration；最终字段比对见 [验收报告](PHASE1_VERIFICATION.md)。

2026-09-26 的 V1.2 REAL BLOCKED 记录保留为 Historical；它描述当时的隔离运行，不覆盖以上当前已保存状态。本轮 Fixture E2E 只证明代码与 UI 交互，不替代真实 Provider 生命周期。

## V1.4 实施保护检查（2026-10-02）

上述真实业务身份、成绩和冻结内容保持原样，不能称为本轮 V2/Provider 实测。实施前 SQLite Backup API 备份及索引副本位于 `/Users/zhanghaohan/.codex/backups/rag-v14-20260930-3a44f2f/`，完整性为 `ok`。阶段只读比较 25 张业务表排序内容与四个 active 索引文件 SHA-256 均不变；最终比较见 [实施验收](V1_4_IMPLEMENTATION_VERIFICATION.md)。全文备份 Staging 与代码支持分开记录，未切真实 active。旧后台服务没有自动重启，默认库未由本次代码导入或迁移。


## Interview Demo 只读复核（2026-10-03）

本轮面试 UI 重构开始前，根代理以真实持久化记录和实际 FAISS 做只读复核；以下是历史业务结果的当前身份确认，不是重跑结果。

| 对象 | 本轮只读确认 |
|---|---|
| Corpus / Index | 4 文档、157 页、252 Chunks；实际 FAISS `IndexFlatIP`，`d=512`、`ntotal=252`；UI 数字由只读字段动态取得 |
| 正式 Golden | `GD-20260927140329017939`，20 题、8/4/8，已人工批准/冻结且匹配当前 Corpus；工艺来源仍为 Legacy，不能改标 V2 |
| Baseline / Root Cause | `EVAL-20260927140423956071`，9/11 Gate、7 Bad Case；当前主根因 Generation 6 / Safety 1 |
| A / B / C / D | A 10/11、6 Bad Case；B 7/11、9 Bad Case、Regression FAIL；C 11/11、5 Bad Case、Qualified/已发布；D 10/11、6 Bad Case、不合格并保留 C |
| 当前 Production | `production-20260928080518`，保存来源 `EXP-20260928071127593062-R1-C`，人工 Release 已批准；`Grounded → Abstention`；`baseline-v1` 是初始配置，不能冒充已发布 Production |

正式资格与生成工艺分别展示：Legacy 工艺不撤销实际已批准 Snapshot；V2 Preview 也不升级旧题身份。方案对比固定此正式 Baseline 与实际 active、人工已发布 Production，无合格候选 fallback；现场实时答案需要用户主动运行，历史成绩不能代替实时输出。

本轮 SQLite Backup API 备份为 `backend/data/interview-demo-before-20261003.bak`，备份完整性为 `ok`。保护基线记录 25 张表完整排序内容，以及 8 个索引/原 PDF 文件哈希；本机审计摘要为 `output/playwright/interview-demo/before.json`，原始真实审计 JSON/DB/备份/索引不提交仓库。修改后相同内容与哈希比对结果以 [Interview Demo 验收](INTERVIEW_DEMO_VERIFICATION.md) 为准，本轮最终核验 25 张表完整内容、数据库结构与 8 个文件哈希一致，详细证据见该报告。

本轮不重建索引、不写真实业务数据、不执行真实 Provider/Golden/Baseline/A/B/C/D/人工 Gate/发布。历史完整 Usage、Judge 费用、计价快照缺失不回填；当前估算只有完整真实 Usage 与冻结价格依据匹配时才显示，币种按价格快照（当前 USD），真实 0/false 保留。单元测试、隔离 Stub 和只读 GET 分别记录，不作为本轮真实 Provider 生命周期证明。
