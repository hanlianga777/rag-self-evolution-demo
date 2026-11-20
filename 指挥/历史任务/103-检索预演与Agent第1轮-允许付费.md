# 103：检索预演表 → Agent 第 1 轮（A/B/C）→ 本轮跑完就停（允许付费）

**依据**：规则总表 v2026-11-20 的六、七、十一、十二.4（关卡 5：每一轮都要先经 Claude 与 GPT 审核，才能进下一轮）。

**前置**：102b 已完成，关卡 4 已放行（Claude 与 GPT 二审，见 `指挥/互审/19-…`）。Baseline 为 `EVAL-20261120213645613191`，45/50，门槛 11/11，真错 5 道：Q05、Q15、Q17、Q21、Q27。不加难，不改冻结卷。

**授权**：用户 11-20 08:47 已授权。**不做 Gate 2/3，不发布。**

## 开始前

1. 读 `指挥/报告/102b.md` 第一行（如果做过加难，读最后一次 Baseline 报告的第一行），取出：最终冻结题卷 M<n>、Baseline run ID、错题数。
2. 跑规则一致性测试和 `rules_e2e_check.py`，贴出结果。不通过就停下写报告。

## 1. 检索预演表（少量付费：阿里云，加关闭思考的 DeepSeek 小请求）

```
PYTHONPATH=backend python3 backend/scripts/retrieval_headroom.py --csv 指挥/报告/102-题卷M<n>.csv --output 指挥/报告/103-检索预演.csv --preview-for-baseline <Baseline run ID>
```

贴出 JSON 中的 `preview_file`、`baseline_gap`、`best_configs` 前 5。

## 2. 生成第 1 轮方案

1. `POST /api/experiments/run`，贴出实验 ID，以及 A/B/C 各自的：
   - `strategy_name`、`config_diff`
   - `target_bad_cases`、`predicted_fixed_question_ids`、`risks`
2. 只读确认以下三点，各贴出一处证据：
   - Agent 请求里包含 `retrieval_preview`；
   - 没有任何方案改动 `generation_thinking`；
   - 没有出现"降档补位"。
3. 先 dry-run，再加 `--apply`（把最多轮数写进实验，后面的轮次由后续任务单逐轮放开）：
   ```
   PYTHONPATH=backend python3 backend/scripts/arm_experiment_cycle.py --experiment-id <ID> --max-rounds 1
   ```

## 3. 只跑第 1 轮

1. `POST /api/experiments/<ID>/run-cycle?current_round_only=true`，**只发一次**。
2. 每 15 分钟看一次进度，技术失败按断点续跑。
3. 本轮跑完、复盘写完后，状态应为 `round_completed`。**不进入第 2 轮，不做 D。**
4. 原样贴出规则给出的下一步（`staged_decision`）。

## 3b. 本轮重点观察（GPT 关卡 4 要求，只读统计，不影响 Agent 的规则判定）

1. **错题分层**：在报告里标出每个 Candidate 主要针对哪一层。
   - 查询理解和别名：Q21、Q27
   - 候选排序和 TopK：Q17、Q27
   - 回答边界：Q05、Q17、Q21、Q27
   - 表格抽取：Q15。这一层现有参数可能修不好，修不好就如实写成限制，不准改题，也不准放宽 Judge。
2. **"说明书没有"类说法**：统计 Baseline 和每个 Candidate 的 30 道正向、消融题里，回答中出现"说明书/手册没有（提到/给出）"的题数。Baseline 是 21/30。对比是否下降，同时看有没有因此编造内容。
3. **临界题**：Q07、Q16、Q26、Q29 这 4 道当前判 PASS，但处在边缘。逐个 Candidate 看它们有没有变成 FAIL。
4. **风险类题逐题不能退步**：安全关键 5 题、提示注入 3 题、负向 20 题，逐题对比 Baseline。任何一题由对变错，都要单独列出。
5. **Q17 已知的 Judge 问题**：Baseline 的 Q17 忠实度给了 100，但回答里那句"说明书没有给出换油步骤"属于无依据说法，Judge 没有发现。各 Candidate 的 Q17 判分保持原样，但要附上回答原文，方便人工复核。

## 4. 导出（只读）

1. 每个 Candidate：
   - `strategy_name`、`config_diff`
   - 答对数、11 项门槛、P50/P99
   - 修好的题号、新错的题号
   - 是否合格及原因
   - 预测修好和实际修好的交集
   - 归因等级：目标题的标准证据，在最终送给模型的资料里有没有变化
2. 本轮 `round_conclusions` 原文。
3. `指挥/报告/103-逐题对比.csv`：每题一行，列为 Baseline、A、B、C，每格填"对"或"错"。
4. 调用次数、token 和费用。

## 报告

`指挥/报告/103.md`，开头单独一段：

> 第 1 轮：A（…）a/50；B（…）b/50；C（…）c/50；Baseline x/50；合格方案：…；规则下一步：…

## 约束

- 允许调用 DeepSeek 和阿里云，只用于本单。
- 不做第 2 轮，不做 D，不做 Gate 2/3，不发布，不回退，不改题卷和判分。
- 完成后移入历史任务。后续轮次和 D 等关卡 5 审核后另行安排。
