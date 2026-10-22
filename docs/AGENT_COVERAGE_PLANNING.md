# 同轮完整覆盖规划

问题列表是输入，只有通过严格验证并保存的 Candidate 目标才计入实际覆盖。Agent 工作台显示实际覆盖率、逐题候选、完整参数差异、假设、来源与验证要求；不能用候选数量代替覆盖率。

生成前，结构规划器按每题当前 `experiment_plan` 的真实观察和允许方向分组，枚举冻结 Search Space 中的单阶段最小参数模板，并通过原干预验证器。模型仍负责策略推理，结构规划仅提供覆盖义务。生成后，保存的模型候选优先复用；工作台“补齐本轮规划（不收费）”可在同一 Experiment、同一轮补齐空余 B/C，不需要先运行 A 的 Sandbox，也不重新调用模型。

规则方案明确持久化 `deterministic_coverage_planner` 来源与结构模板假设，绝不冒充模型输出或改写原始响应。跨根因探索组必须完整保存 `target_root_causes`，逐题等于当前可信诊断；混合组总根因为 Unknown，不修改任何题的诊断。确认型实验沿原规则。所有方案仍通过统一 JSON/目标/证据断言/完整 Diff/Search Space/重复配置/干预验证器。

有限枚举优先最大覆盖，已保存方案不覆盖。草案不计入实际覆盖；无合法模板明确记录规划能力缺口，容量不足保持“规划未完成”。模板目前覆盖候选池深度、上下文深度/排序和有据回答策略；未找到模板不等于已证明所有 Search Space 都无解。不存在已验证效果或自动发布的含义。

写入前校验当前 Baseline/Experiment、预览绑定和运行状态，使用 SQLite Backup 和 BEGIN IMMEDIATE，只追加候选与规划 Trace，并给 Experiment 增加独立 `coverage_plan`。原 A、原响应、历史 Trace、Usage、费用、Golden、Baseline、Judge、Corpus 不改。事务失败整体回滚。Sandbox 只读预检与事务预留都检查实际规划状态；未完成时阻断付费启动。明确能力缺口不冒称已覆盖。

离线入口（脚本封锁网络）：

```sh
python3 scripts/plan_agent_coverage.py --database /path/demo.db --index /path/index --experiment EXP-ID --output /path/preview.json
# 检查预览后显式追加；保留原数据库备份，不启动任何评测。
python3 scripts/plan_agent_coverage.py --database /path/demo.db --index /path/index --experiment EXP-ID --output /path/accepted.json --apply --binding PREVIEW_BINDING --backup /path/new-backup.db
python3 scripts/test_agent_offline.py test_agent_coverage test_agent_exploration test_optimization_contract test_intervention_contract test_agent_response_recovery
```

离线准入只证明可以执行实验。完整冻结题集 Sandbox、11 Hard Gate、Regression、人工报告确认、Composite D 和人工发布要求保持原样；真实效果、延迟、来源适用性与原有必要事实保留必须另行授权后实测。
