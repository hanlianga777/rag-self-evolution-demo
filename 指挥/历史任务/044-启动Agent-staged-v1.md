# 044：把新 Baseline 绑到 Agent 串联并启动（允许付费）

**总指挥审核 043b 的结论**（用户 2026-11-16 预先授权总指挥代为决定）：Baseline `EVAL-20261116205556542256` 合格，可以作为 Agent 的起点。
- 50 题完整，技术失败 0；
- 11 项门槛全过，P50=16.7 秒，P99=58.5 秒（贴近 60 秒）；
- 错题 2 道（Q21、Q30），都是普通题，都是"完整性"不达标。

Agent 合格要满足：错题不多于 1 道，新增错题最多 1 道且只能是普通题，不能新增严重错题。

043b 查到，现有 designation 仍指向旧 run。本单**不走** designate_baseline，改用串联：串联在 advance_chain 里把 designated 置为 true，`baseline_designation()` 会优先采用当前题卷下的串联 Baseline，不需要再跑一次对照评测。

## 要做的事

1. **Dry-run**：
   ```
   cd "/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目" && PYTHONPATH=backend python3 backend/scripts/arm_agent_chain.py --baseline-id EVAL-20261116205556542256
   ```
   核对以下各项：
   - snapshot 为 `GD-20261116184333`；
   - round_policy 为 `{"mode":"full_rounds","max_rounds":4,"stop_rule":"staged-v1"}`；
   - causal_evidence 为 true；
   - audit_note 为 `用户 2026-11-16 预先授权`；
   - 上一个串联指向 `EXP-20261115174011968589`，其 cycle 为 `recommended`。

2. **正式绑定**：同一条命令末尾加 `--apply`。
   - 脚本会在需要时把无人值守授权设为 actor `用户`，然后调用 `arm_chain`。
   - 如果 arm_chain 报"前次串联尚未结束"之类的错误：停下，贴出原文，不要手改数据库。

3. **确认后端已接手**：后端已有的 5 秒监控会调用 `advance_chain`，大约 1 分钟内应当出现以下变化：
   - 串联状态变为 `agent_running`，有 experiment_id；
   - 这个 experiment 的 result 里，`round_policy.stop_rule='staged-v1'`、`causal_evidence=true`、`strategy_contract='agent-strategy-4'`；
   - `optimization_cycle.status='running'`；
   - `require_current_baseline()` 解析出的就是本 Baseline。

   如果 3 分钟仍没启动，只读查 `chain_status` 的 error，以及后端进程有没有在 043 之后被重启或卡住。**不要**自行重复 arm，也不要另开实验。

4. **等第 1 轮 A/B/C 方案生成，并且第 1 个候选开始评测**，然后本单结束。期间只读查看，不要干等整轮。

## 报告

写在 `指挥/报告/044.md`，内容包括：
- dry-run 原文、apply 返回原文；
- experiment_id；
- 第 1 轮 A/B/C 各自改了哪些参数、理由原文，有没有降档；
- 校验错误和重试次数；
- 第 1 个候选的 run id 和开始时间。

## 约束

- 不做 Gate 3，不发布，不改代码、`.env`、题卷。
- 不删旧记录，不提交数据库、密钥、日志。
- 完成后按值班规则移入历史任务。
