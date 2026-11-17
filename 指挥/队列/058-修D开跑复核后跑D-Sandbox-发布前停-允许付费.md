# 058：修好 D 开跑前复核后，跑 D 的 Sandbox，停在发布前（允许付费）

**用户 2026-11-17 09:19**："让他完整跑到有 Candidate D，到发布前等我的命令再决定要不要发布。"本单无人值守，一路跑完。

**背景**：057 中 D 规划已通过（Winner R4-B 上加 `multi_query=2`），D 状态是 `generated`。但开跑前复核把整条 `changes` 和保存的建议比较，比较时没有剔除首次规划附带的规整审计 `normalized_fields`，于是报"D配置与已审查建议不一致"。057 报告已确认：剔除这个字段后两边完全相同。循环停在 `failed / sandbox`，预算 11/12，D 还没跑题。

**本单推送的修复**（提交见 git log）：
- `backend/app/evaluation.py`：D 开跑前的复核在比较 `changes` 时不计 `normalized_fields`（它只是审计记录）。配置、参数差异和其余字段照旧逐项比对，被篡改照样拦截。
- 新测试 `tests/test_task021a_composite.py::test_sandbox_entry_accepts_d_whose_overlap_was_normalized`。改动前该测试失败，改动后通过。总指挥本地跑了 `test_task021a_composite.py`、`test_evaluation_context.py`、`test_task019a_full_flow.py`：仍是改动前就有的 5 项失败，没有新增失败。

## 要做的事

1. **先看现状（只读）**：`GET /api/experiments/EXP-20261117062621288609`，贴出：
   - `optimization_cycle` 和 `composite.status`；
   - D 的 id、状态、config；
   - `report_confirmation.winner_id`（应为 R4-B）。
   
   有 Candidate 在 running/queued 就每 2 分钟看一次，等它结束。

2. **测试**：跑 `tests/test_task021a_composite.py`、`test_evaluation_context.py`、`test_task019a_full_flow.py`、`test_v14_api_lifecycle.py`，只列新增失败。

3. **重启**：按 047 的方法重启 8010 后端。

4. **启动**：`POST /api/experiments/EXP-20261117062621288609/run-cycle`，**只 POST 一次**。
   - 报告已确认、D 已生成，循环会直接复用已保存的 D，**不会再付费做规划**；
   - 然后跑 D 的 Sandbox（第 12 次），做 D 复盘，停在 `recommended / before_release`。
   - 不运行 arm 脚本，不改 round_policy，不改 Winner。
   
   POST 后 2 分钟内确认 D 已经有 `evaluation_run_id`，并且在跑题。

5. **盯着跑完**：每 10–15 分钟看一次。
   - 终态是 `recommended`、`failed`、`stopped` 时结束。
   - 如果又失败：贴出错误原文，停下等总指挥，不要再次 POST。
   - **不做 Gate 2/3，不发布，不退回。**

6. **报告** `指挥/报告/058.md`：
   - D 的配置和实际结果：对几道、门槛几项、P50/P99、新错和修好的题号、是否合格；
   - D 复盘原文；
   - 最终推荐是谁（D 还是 R4-B），理由原文；
   - 调用次数、token、估算费用。
   
   逐题对比写到 `指挥/报告/058-逐题对比.csv`，列与 056 相同，再加一列 D。报告控制在 100KB 以内，只贴上面列的字段。

## 约束

- 允许调用 DeepSeek 和阿里云，只用于 D Sandbox 和 D 复盘。
- 不改题卷、判分，不删记录，不重跑已完成的 Sandbox。
- 完成后，本单和 `_暂缓-056`、`_暂缓-057` 两张草稿一起移入历史任务。
