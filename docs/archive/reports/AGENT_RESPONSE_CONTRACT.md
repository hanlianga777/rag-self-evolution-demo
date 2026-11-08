# Agent 响应校验与已付费结果恢复

`agent-response-2` 由 `optimization.prepare_response` 共用验证新生成和已保存响应，不执行模型或评测调用。

## 输出与逐项校验

- `candidates` 必须为数组；合法候选最多使用本轮允许的 A/B/C 标签。1、2个合法候选均可进入下一阶段，不要求凑齐。
- `insufficient_evidence` 和 `target_group` 是可选说明。原响应缺失时保留缺失，不生成模型没有给出的理由。
- 必需的假设、提出理由、预期改善、风险、目标、根因、Config Diff 和真实证据仍严格核验。Unknown 仅按已有探索合同验证。
- JSON重复键、非有限数值和错误包结构拒绝。错误标签、重复目标/别名、非法类型、超出Search Space、重复配置、根因/证据/方向不一致均记录拒绝项，禁止自动改成合法值。
- 合法子集与审计一次事务保存。所有非法则失败；模型返回空数组则明确没有可运行候选，不能宣称优化成功。原始响应与解析内容完整保留。
- 持久化失败复用响应时保留原请求Usage和费用及复用来源，恢复本身的新调用数为0，历史未知费用仍未知。

## 恢复命令

只读预检（始终强制阻断网络，不加载正式服务或迁移数据库）：

```sh
python3 scripts/recover_agent_response.py --database <正式库> --index <正式索引> --trace <失败Trace编号> --output <本地预检.json>
```

预检有合法候选后，显式使用返回的绑定和一个不存在的备份路径：

```sh
python3 scripts/recover_agent_response.py --database <正式库> --index <正式索引> --trace <失败Trace编号> --output <本地恢复.json> --apply --binding <预检binding> --backup <新备份.db>
```

工具拒绝已确认报告、已有候选、不兼容身份、来源响应/题目/分数/回答/Trace变化及有更新实验的恢复。SQLite Backup 后，在 `BEGIN IMMEDIATE` 内复核绑定，仅追加恢复Experiment、合法Candidate和恢复Trace；原失败Experiment/Trace不覆盖，恢复来源和原费用记录保留。重复操作返回同一恢复结果，不重复插入。

恢复不会生成答案、执行Judge、补证或Sandbox，也不确认报告或发布。下一步需要独立授权，使用现有「运行 Sandbox」入口，执行前继续核验冻结Baseline、完整干预、全部冻结题集和既有保护。

## 离线验证

`python3 scripts/test_agent_offline.py test_agent_response_recovery test_optimization_contract test_v14_identity` 验证0/1/2/3个候选、部分合法/全部非法、ID与类型、事务回滚、幂等和原记录不变。真实响应回放、运行记录与数据库备份仅存本地，不推送。
