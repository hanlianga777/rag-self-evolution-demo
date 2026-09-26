# 项目上下文（当前 V1.2）

- 唯一规则：[SPEC](docs/RAG_SELF_EVOLUTION_SPEC.md)。原始截图是参考证据，不是隐藏算法说明。
- 保留 FastAPI、SQLite、React、BGE/FAISS 和 DeepSeek；动态文档清单，最低元数据为文档 ID、Chunk ID、原文，四 PDF 仅为示例。
- Mini 8/4/8，Ablation 独立治理；检索不一致为 P1，QC 分数不作审批阈值。机器 P0 须明确接受理由，确定性错误与 Fake Negative 不可豁免。
- 批准／编辑／替换复用审计；采用替换才切换活动题。Gate 1 一次人工确认原子保存审核和不可变 Golden Version。
- Baseline、A/B/C/D 共用冻结 Golden、Judge 与评测器，保留 11 Gate。Tuning 唯一 Agent，失败假设进入历史。
- Gate 2 确认报告并选赢家；D 合并实测有效差异，冲突保留赢家，新组合重评，不胜则回退。12 次启动预算包含失败及 D，为 D 保留一次。
- Gate 3 一次人工发布；Monitoring、历史、Rollback 辅助，不作为主线前置条件。
- 真实数据以 API 为准；禁止用旧 Run 或 Fixture 证明真实主线。验收只在临时库，不操作用户 Preview。
- 线程不跨进程续跑；重启保留审计和预算并标记中断／失败，由用户手动重试。
