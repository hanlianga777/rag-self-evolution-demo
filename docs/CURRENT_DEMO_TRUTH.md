# Current Demo Truth

审计日期：2026-09-30（Asia/Shanghai）。依据：本轮修改前真实 SQLite 备份及只读界面/API；不是 Fixture，也不是本轮重新执行的 Provider 验收。

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

历史阶段耗时、完整调用 Usage、Judge 费用和计价依据未采集；不回填。历史总回答延迟/TTFT 仍按原记录展示。默认未配置单价。设置页的 Provider 状态仅是 Configured (Unverified)，不代表本轮已验证 DeepSeek。

真实 DB 修改前：SHA-256 `7dee55b5eca5779c6b07f85a5256a4f53f9fd39f95fc87112d5f0ae9a99e6784`，6037504 bytes，mtime_ns `1790582718511204144`。独立备份：`/tmp/rag-phase1-20260930/before.db`。本轮只允许 additive metrics migration；最终字段比对见 [验收报告](PHASE1_VERIFICATION.md)。

2026-09-26 的 V1.2 REAL BLOCKED 记录保留为 Historical；它描述当时的隔离运行，不覆盖以上当前已保存状态。本轮 Fixture E2E 只证明代码与 UI 交互，不替代真实 Provider 生命周期。
