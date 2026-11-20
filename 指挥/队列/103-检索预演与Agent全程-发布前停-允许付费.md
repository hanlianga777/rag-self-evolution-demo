# 103：检索预演表 → Agent 全程（A/B/C 各轮 + D）→ 停在发布前（允许付费）

**依据**：规则总表 v2026-11-20 的六、七、八.2、十一。

**授权**：用户 11-20 08:47 已授权，本单无人值守，中途不停。**不做 Gate 2/3，不发布。**

## 开始前

1. 读 `指挥/报告/102.md` 第一行，取出最终冻结题卷 M<n>、Baseline run ID、错题数。
   - 如果 102 没有跑完 Baseline，本单不做，写明原因后移入历史任务。
   - **错题数不影响开跑**：按规则总表七.2，加难 2 轮后错题仍不足 5 道也照常启动。
2. 跑规则一致性测试和 `rules_e2e_check.py`，贴出结果。不通过就停下写报告。

## 1. 检索预演表（少量付费：阿里云，以及关闭思考的 DeepSeek 小请求）

```
PYTHONPATH=backend python3 backend/scripts/retrieval_headroom.py --csv 指挥/报告/102-题卷M<n>.csv --output 指挥/报告/103-检索预演.csv --preview-for-baseline <Baseline run ID>
```

贴出 JSON 中的 `preview_file`、`baseline_gap`、`best_configs` 前 5。确认预演文件已生成（文件本身不提交）。

## 2. 第 1 轮方案 + 全程循环

1. `POST /api/experiments/run`。贴出实验 ID，以及 A/B/C 各自的以下字段：
   - `strategy_name`、`config_diff`；
   - `target_bad_cases`、`predicted_fixed_question_ids`、`risks`。
2. 只读确认三件事，各贴出一处证据：
   - Agent 请求里包含 `retrieval_preview`；
   - 没有任何方案改动 `generation_thinking`；
   - 没有出现"降档补位"。
3. 先 dry-run，再 `--apply`：
   ```
   PYTHONPATH=backend python3 backend/scripts/arm_experiment_cycle.py --experiment-id <ID>
   ```
   最多 3 轮，然后做 D（规则总表六.6）。
4. `POST /api/experiments/<ID>/run-cycle`，**不带** `current_round_only`，**只发一次**。

## 3. 等待全程跑完

- 每 15 分钟看一次，贴出简要状态：当前轮次、正在跑的 Candidate、已用 Sandbox 次数。
- 技术失败按断点续跑恢复。续跑必须使用启动时的规则快照（101）。
- 状态变成 `failed` 或 `stopped`：
  - 网络、限流原因：允许恢复一次；
  - 其他原因：写报告后停下。
- 正常结束后停在发布前，由规则选出最终推荐（Winner 或 D）。

## 4. 导出（只读）

1. 每个 Candidate（含 D）：
   - 所在轮次、`strategy_name`、`config_diff`；
   - 答对数、11 项门槛、P50/P99；
   - 修好和新错的题号；
   - 是否合格及原因；
   - 预测修好与实际修好的交集；
   - **归因等级**（规则总表六.5）：目标题的标准证据在最终资料里是否有变化（有变化 / 只有结果变化）。
2. 每轮 `round_conclusions` 原文，以及 D 的复盘原文。
3. 最终推荐：哪个方案、为什么（规则判定原文）。相对 Baseline 的净修复数。
4. `指挥/报告/103-逐题对比.csv`：每道题一行，列为 Baseline、各 Candidate、D，每格写"对"或"错"。
5. 浏览器打开 Agent 工作台，逐条抄下每个 Candidate 首屏 5 行和总表的文字。只读：不点运行、跳过、发布按钮，截图不入库。
6. 调用次数、token 数和费用。

## 报告

`指挥/报告/103.md`，控制在 200KB 以内。开头单独一段写：

> 最终推荐：Candidate X（配置差异 …）；答对 a/50（Baseline b/50）；净修复 n；修好 Q..；新错 Q..；门槛 y/11；归因：…

## 约束

- 允许调用 DeepSeek 和阿里云，只用于本次 Agent 全程（方案生成、Sandbox、复盘、D）。
- 不做 Gate 2/3，不发布，不回退，不改题卷和判分。
- 完成后移入历史任务。
