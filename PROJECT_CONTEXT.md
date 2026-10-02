# 项目上下文（V1.4 目标 / Phase 1 现有实现）

> **V1.4 业务实施（2026-10-02）：** 用户已批准完整代码实施与 GitHub 同步。唯一规则源为 [SPEC V1.4](docs/RAG_SELF_EVOLUTION_SPEC.md)，阶段证据见 [实施与验收记录](docs/V1_4_IMPLEMENTATION_VERIFICATION.md)。P0、Golden V2、Probe / FullText 引擎与成本已通过隔离后端回归和代码复审；最终 296 项后端、121 项前端、构建和四尺寸 Chromium 208 检查通过；整体审查及一次修复后的限定复审通过，保留一个 Drawer 换材后误提示的非阻断 Minor；其他运行边界按 SPEC 第 3 节记录。真实 Provider、评测与发布不自动执行；下方 Phase 1 / V1.3 为历史记录，不能替代 V1.4 验收。

历史阶段状态（2026-09-30）：见 [Current Demo Truth](docs/CURRENT_DEMO_TRUTH.md) 与 [Phase 1 验收](docs/PHASE1_VERIFICATION.md)。以下保留该历史阶段的规则与验收边界。

## Phase 1 当前实现（2026-09-30）

业务导入/AI 候选共用 SQLite questions 与 JSON provenance，Profile 选题创建新 Run 和副本，原治理链不变。未来构造题型、执行阶段和 Usage 进入 JSON，Monitoring 只增加 nullable metrics_json。价格配置默认无值；旧事件无伪回填。

共享 UI 保留当前风格；QA 本页证据、保存参数分组、sessionStorage 恢复；D 失败明确保留 C。当前 Production 的历史事实与本轮 Fixture 验证分层报告。


- 唯一规则：[SPEC](docs/RAG_SELF_EVOLUTION_SPEC.md)。原始截图是参考证据，不是隐藏算法说明。
- 保留 FastAPI、SQLite、React、BGE/FAISS 和 DeepSeek；动态文档清单，最低元数据为文档 ID、Chunk ID、原文，四 PDF 仅为示例。
- Golden 默认 Mini 8/4/8，可选 Medium 20/9/20、Full 40/18/40；Ablation 独立治理；检索不一致为 P1，QC 分数不作审批阈值。机器 P0 须明确接受理由，确定性错误与 Fake Negative 不可豁免。
- 批准／编辑／替换复用审计；采用替换才切换活动题。Gate 1 一次人工确认原子保存审核和不可变 Golden Version。
- Baseline、A/B/C/D 共用冻结 Golden、Judge 与评测器，保留 11 Gate。Baseline 只用持久化 Run 显示报告、Gate 贡献题和逐题诊断；历史缺失字段标明未采集。Tuning 唯一 Agent，失败假设进入历史。
- Gate 2 确认报告并选赢家；D 合并实测有效差异，冲突保留赢家，新组合重评，不胜则回退。12 次启动预算包含失败及 D，为 D 保留一次。
- Gate 3 一次人工发布；Monitoring、历史、Rollback 辅助，不作为主线前置条件。
- 真实数据以 API 为准；禁止用旧 Run 或 Fixture 证明真实主线。验收只在临时库，不操作用户 Preview。
- 线程不跨进程续跑；重启保留审计和预算并标记中断／失败，由用户手动重试。
