# Baseline 错题复核规则

正式 Baseline 的判分与两次独立复核合成三票，错至少两票为真错，其余为不稳定。复核只追加诊断，不改变正式 Baseline 的分数、题目、判分标准或门槛。

按决策 14，网络或格式问题经产品内部自动重试后得到有效判分，就是有效票。首次失败和后续成功的请求、Usage、`judge_result.response_recovery` 与阶段 attempts 继续保存在技术详情中；不能因为存在这些历史重试记录，就停止复核或把结论变成未知。只有产品内部重试结束后仍拿不到有效判分，才记录最终 `technical_error`、停止后台复核，并将该题列为未知而非优化目标。

读复核结论统一使用 `backend/app/agent_inputs.py:review_summary`。自动复核的 `stop_on_error=True` 表示遇到最终失败就停止，不禁用内部正常重判；后台进度的 `technical_failed` 也不把成功恢复的阶段错误计入最终失败。

Agent 的 `target_bad_cases` 支持当前 Baseline 的展示题号（如 Q04）、正式题目 ID、Bad Case ID。展示题号只按该 Baseline 的已保存对照转换为正式 ID，未知或有歧义的展示题号拒绝；原始回复保存在 Agent trace。格式和参数校验拒绝没有运行 Sandbox，不消耗试跑次数，不进入效果失败签名清单。逐参数预期影响仍须点名目标题号，风险仍须说明可能影响的题号或指标和原因。
