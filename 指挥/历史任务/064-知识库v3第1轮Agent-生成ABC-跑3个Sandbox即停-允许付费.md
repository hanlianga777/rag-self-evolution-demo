# 064：知识库 v3 第 1 轮 Agent：生成 A/B/C → 跑 3 个 Sandbox → 本轮复盘 → 停（允许付费）

**用户 2026-11-18 10:40 授权**：终点是第 1 轮 Agent 跑完（3 个 Candidate），先看整体效果，中途不停。用户在睡觉，本单无人值守。

**合格标准已改回朋友口径**：11 项门槛全过，且严重题不新增。错题数只用于在合格方案之间排序。

## 开始前先看 063

读 `指挥/报告/063.md`：
- **063 没有完成 Baseline**（例如可修空间不足、QC 有 P0、技术失败）：本单**什么都不做**，在报告里写"063 未完成，064 未执行"，然后移入历史任务。
- **Baseline 错题少于 5 道**（规则总表五 a）：不启动 Agent，写报告说明后结束。

## 要做的事

1. **确认 Baseline 是当前基线**：`GET /api/overview`（或现有的当前基线接口）显示的应是 063 的 Baseline run。
   - 不是的话，运行 `PYTHONPATH=backend python3 backend/scripts/why_baseline_hidden.py` 并贴出结果；
   - 看不出原因就停下写报告。不要改数据。

2. **生成第 1 轮方案**：`POST /api/experiments/run`。贴出：
   - 实验 ID；
   - 3 个 Candidate 各自的 `strategy_name`、`direction`、`config_diff`、`target_bad_cases`、`predicted_fixed_question_ids`、`risks`；
   - `audit.normalized_fields`（如果有）。

   如果因为格式被退回，系统最多会自动重试 3 次；3 次都失败就停下，贴出每次的拒绝原因原文。

3. **启用只跑本轮**：先跑 dry-run，再加 `--apply`：
   ```
   PYTHONPATH=backend python3 backend/scripts/arm_experiment_cycle.py --experiment-id <实验ID> --max-rounds 1
   ```
   原样贴出输出。

4. **跑 3 个 Sandbox**：`POST /api/experiments/<实验ID>/run-cycle?current_round_only=true`，**只 POST 一次**。
   - 系统会依次跑 A、B、C，每个 50 题，然后自动写本轮结论，状态停在 `round_completed`；不会进第 2 轮，也不会做 D。
   - 每 10–15 分钟看一次进度。技术失败按现有断点续跑。
   - 结束状态是 `failed` 或 `stopped`：贴出错误原文后停下，不要再次 POST。

5. **跑完后导出**（只读）：
   - 每个 Candidate：答对数、11 项门槛逐项、P50/P99、修好和新错的题号、是否合格及原因（`qualification.checks`）；
   - 本轮结论原文（`round_conclusions` 第 1 轮），重点看预测命中数，以及 `staged_decision`（规则判定的下一步，只记录、不执行）；
   - 前端打开 Agent 工作台，逐条写下看到的第 1 轮内容：方案名、思路、答对数、合格与否、本轮结论（只读，不截图入库，不点任何运行、跳过或发布按钮）；
   - 逐题对比写到 `指挥/报告/064-逐题对比.csv`，列为：题号、Baseline、A、B、C，每格写 对 或 错。

## 报告

`指挥/报告/064.md`：
- 上面每一步的原文；
- 调用次数、token、估算费用。

控制在 150KB 以内，不要整段贴大 JSON。

## 约束

- 允许调用 DeepSeek 和阿里云，只用于第 1 轮方案生成、3 个 Sandbox、本轮复盘。
- **不跑第 2 轮，不做 D，不做 Gate 2/3，不发布，不退回。**
- 不改题卷、判分代码，不删记录。
- 完成后移入历史任务。
