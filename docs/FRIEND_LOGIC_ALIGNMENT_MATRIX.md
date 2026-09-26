# Friend Logic Alignment Matrix — V1.2

Status: implementation delivered; Real Main Lifecycle BLOCKED. PASS below names its verification layer, never substitutes Fixture for live evidence. See [verification report](V1_2_VERIFICATION.md).

| Item | Disposition | Original evidence | Implementation / verification |
|---|---|---|---|
| Dynamic corpus and embedding coverage | SIMPLIFIED | 黄金测试集出图流程1；222140 | PASS — test_v12_corpus_coverage：1/2/4/6/10 文档；真实覆盖计划已持久化 |
| Aggregation / Bridge / Fact | RESTORED | 黄金测试集出图流程1 | PASS（确定性结构选择）— 显式事实／Bridge／普通 fallback 测试；未声称复杂知识图谱 |
| Independent Ablation | SIMPLIFIED | 黄金测试集出图流程1–4 | PASS — test_v12_governance + revision_workflow 独立答案与证据 |
| Deterministic evidence / OCR anchors | KEEP | 黄金测试集出图流程2 | PASS（确定性）— OCR 正反例 + 初次生成/Probe 复用；真实原题复核4项阻塞，未放行 |
| Positive retrieval miss is P1 | SIMPLIFIED | 223050；223406 | PASS — test_final_governance 检索未命中；真实 Q01/Q03/Q05 有 RETRIEVAL_INCOHERENT |
| Strict Negative vector/full-text checks | KEEP | 223152；223236 | PASS（测试及真实阻断）— 负向检查保留；真实 Q18 subtype mismatch |
| QC severity + explicit human acceptance | SIMPLIFIED | 223406 + user clarification | PASS（Fixture/UI）— P0 理由与非法豁免阻断；真实2个P0未自动接受 |
| Approve / Edit / Replace + one targeted fix | SIMPLIFIED | 黄金测试集出图流程4 | PASS（Fixture/UI）— replacement活动映射/历史、最多一次自动修复；本轮未真实替换 |
| Frozen Golden technical version | REMOVED/HIDDEN | 流程1 | PASS（Fixture/UI）— Gate1原子审核+冻结，逐题approved仍可确认；真实未到达 |
| Same evaluator / 11 project gates | KEEP | 流程5 + user choice of existing 11 gates | PASS（Fixture E2E）— snapshot_items同Golden/Judge；真实评测未到达 |
| Single Tuning Agent / evidence feedback | KEEP | 流程2；223628 | PASS（实现/Fixture）— 历史假设配置结果入Prompt；真实Agent未到达 |
| Report Human Confirm / Composite D | RESTORED | 流程3；223628 | PASS（Fixture/UI）— 报告确认与D完整评测；真实未到达 |
| D fallback to qualified winner | RESTORED | 流程4；223654 + user confirmation | PASS（Fixture）— D实际改善晋升/新增失败和中断回退；真实未到达 |
| A/B/C/D share 12 evaluations | KEEP | 223628 + explicit user budget choice | PASS（并发Fixture）— 12次总额，D预留，失败/重启保留消耗 |
| Monitoring / Versions auxiliary | REMOVED/HIDDEN | 流程1–5 main path | PASS（UI/图）— Overview主链不依赖Monitoring，辅助能力保留 |

Reference filenames abbreviated above are ScreenShot_2026-09-07_<suffix>.png inside the user-provided 产品成果参考.zip. These are screenshots, not source code. Existing BGE/DeepSeek/FAISS and 11 gates are explicit project adaptations, not claims about the friend's exact implementation.
