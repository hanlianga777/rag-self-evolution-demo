# 待办（V1.4 目标 / Phase 1 历史记录）

> **V1.4 业务实施（2026-10-02）：** 用户已批准完整代码实施与 GitHub 同步。唯一规则源为 [SPEC V1.4](docs/RAG_SELF_EVOLUTION_SPEC.md)，阶段证据见 [实施与验收记录](docs/V1_4_IMPLEMENTATION_VERIFICATION.md)。P0、Golden V2、Probe / FullText 引擎与成本已通过隔离后端回归和代码复审；最终 296 项后端、121 项前端、构建和四尺寸 Chromium 208 检查通过；整体审查及一次修复后的限定复审通过，保留一个 Drawer 换材后误提示的非阻断 Minor；其他运行边界按 SPEC 第 3 节记录。真实 Provider、评测与发布不自动执行；下方 Phase 1 / V1.3 为历史记录，不能替代 V1.4 验收。

V1.4 的 P0-01–04、GV2-01–05、COST-01、UI-01、SAFE-01、QA-01 按 SPEC 需求追踪及离线验收矩阵实施。旧勾选状态不代表新目标已完成；阶段状态与恢复入口见实施验收记录。

历史阶段状态（2026-09-30）：见 [Current Demo Truth](docs/CURRENT_DEMO_TRUTH.md) 与 [Phase 1 验收](docs/PHASE1_VERIFICATION.md)。以下保留该历史阶段的规则与验收边界。

## Phase 1 验收状态（2026-09-30）

本轮实现与验收见 PHASE1_VERIFICATION；Current Demo Truth 是真实已保存状态。历史阶段耗时/完整 Usage/费用未采集，不能补造。真实 Provider 新链路验证本轮明确未执行；不属于可自动推进的任务。

以下原待办保留为历史追踪，是否仍适用须依据当前 SPEC 与 Truth 判断。


## 本轮验收

- 用临时库、Fixture 和 Mock 验证三个 Profile、11 Gate 与浏览器八页；真实主链由用户按人工 Gate 推进，确定性测试不冒充 Provider 验收。
- 更新 [参考对齐矩阵](docs/FRIEND_LOGIC_ALIGNMENT_MATRIX.md)，未实测项明确标注。
- 真实用户审核及 Preview 留给用户，不为验收自动推进。

## 范围外

- 新模型、独立重排服务、队列、多 Agent、生产部署和新一级页面。


## V1.4 交付后的明确事项

- 非阻断 M3：同一草案换材料重新生成后同步已保存 clean 基线，验证未输入时关闭不误提示、真实未保存输入仍提示；当前确认只关闭 UI，不删除已保存草案。
- 受控停止旧服务、检查迁移和兼容全文激活，再按实施验收的三条真实手动步骤验证；本轮不自动消耗 Provider 或执行发布。
- WebKit 可执行文件缺失，保留未验证边界。
