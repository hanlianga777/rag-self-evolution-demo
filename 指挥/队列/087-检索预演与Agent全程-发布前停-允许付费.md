# 087：生成检索预演表 → Agent 全程（A/B/C 各轮 + D）→ 发布前停（允许付费）

**用户 2026-11-19 08:50 授权**：用户在睡觉，醒来要看到 Agent 最终选择的结果。本单无人值守，中途不停。**不做 Gate 2/3，不发布。**

## 开始前

读 `指挥/报告/086.md`：
- 如果 086 没有跑完 Baseline，本单什么都不做，在报告里写明后移入历史任务。
- 按规则总表五 a 判断是否值得跑：Baseline 错题少于 5 道**且**门槛全过时，不启动 Agent，写报告后结束。

## 1. 生成检索预演表（少量付费：阿里云 + 关闭思考的 DeepSeek 小请求）

```
PYTHONPATH=backend python3 backend/scripts/retrieval_headroom.py --csv 指挥/报告/085-题卷v4.csv --output 指挥/报告/087-检索预演.csv --preview-for-baseline <086 的 Baseline run ID>
```

- 原样贴出 JSON 中的 `preview_file`、`baseline_gap`、`best_configs` 前 5。
- 确认 `backend/data/retrieval_preview/<run ID>.json` 文件已生成（文件不提交）。

## 2. 生成第 1 轮方案并启用全程循环

1. `POST /api/experiments/run`，贴出实验 ID，以及 A/B/C 各自的 `strategy_name`、`config_diff`、`target_bad_cases`、`predicted_fixed_question_ids`、`risks`。
2. 只读确认：Agent 的请求里包含 `retrieval_preview`。可以从实验 `audit` 中保存的 prompt 摘要，或 provider 请求日志里查，贴出一处证据。
3. 先 dry-run，再加 `--apply`：
   ```
   PYTHONPATH=backend python3 backend/scripts/arm_experiment_cycle.py --experiment-id <ID>
   ```
   默认最多 3 轮，然后做 D。贴出输出，确认 `strategy_contract=agent-strategy-4`。
4. `POST /api/experiments/<ID>/run-cycle`，**不带** `current_round_only`，**只 POST 一次**。

## 3. 等待全程跑完

- 每 15 分钟看一次进度，贴出简要状态：当前轮次、正在跑哪个 Candidate、已用几次 Sandbox。
- 技术失败按现有断点续跑（`run-cycle` 恢复）。
- 状态变为 `failed` 或 `stopped`：贴出错误原文，再判断原因：
  - 网络、限流这类技术原因：允许恢复一次；
  - 其他原因：停下写报告。
- 正常结束：停在发布前，规则选出最终推荐方案（Winner 或 D）。

## 4. 导出（只读）

1. 每个 Candidate（含 D）的以下信息：
   - 所在轮次、`strategy_name`、`config_diff`；
   - 答对数、11 项门槛、P50/P99；
   - 修好和新错的题号；
   - 是否合格及原因；
   - 预测修好与实际修好的交集。
2. 每轮 `round_conclusions` 原文，以及 D 的复盘原文。
3. 最终推荐：哪个方案、为什么（规则判定原文）。
4. `指挥/报告/087-逐题对比.csv`：每道题一行，列为 Baseline、各 Candidate、D，每格写 对 或 错。
5. 浏览器打开 Agent 工作台，按 088 的新首屏（若 088 尚未完成则写"088 未完成"），逐条写下每个 Candidate 首屏 5 行和总表的实际文字。只读，不截图入库，不点任何运行、跳过或发布按钮。
6. 调用次数、token 和费用。

## 报告

`指挥/报告/087.md`，控制在 200KB 以内。

开头单独一段写：

> 最终推荐：Candidate X（配置差异 …）；答对 a/50（Baseline b/50）；修好 Q..；新错 Q..；门槛 y/11。

## 约束

- 允许调用 DeepSeek 和阿里云，只用于本次 Agent 全程（方案生成、Sandbox、复盘、D）。
- 不做 Gate 2/3，不发布，不退回，不改题卷和判分。
- 完成后移入历史任务。
