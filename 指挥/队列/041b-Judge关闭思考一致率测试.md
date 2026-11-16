# 041b：Judge 关闭思考的一致率测试（只判分，允许少量付费）

**背景**：总指挥已审核 041。low 档一致率 93%，high 档 91%，都没有达到 97%。翻转的题目分数都卡在门槛边上，例如完整性在 60 和 80 之间来回跳。

开着思考时，temperature 不起作用，所以每次判分都有随机性。新的判分提示词只有约 1000 字，规则很明确。本单测试**关闭思考 + temperature 0**，看判分能否稳定。

## 要做的事

1. **先确认 040c 已完成**，没完成就等。

2. **Dry-run，再正式跑**。正式跑在下面命令末尾加 `--apply`。允许调用 DeepSeek，约 200 次：

   ```
   cd "/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目" && PYTHONPATH=backend python3 backend/scripts/rubric_consistency.py --runs EVAL-20261115170609095674 EVAL-20261115174123118797 --answers 指挥/报告/040c-参考答案定稿.csv --effort off --passes 2 --output /tmp/rubric-off
   ```

   中断了就用同一命令续跑。用 041 的方式核对每个请求：`thinking` 为关闭，请求体里 temperature 为 0。

3. **对照 low 档**：用 off 第 1 遍逐题对比 041 low 第 1 遍（`/tmp/rubric-low`）。
   - 列出对错不同的题，贴出两边的分数和理由原文。
   - 注意：Q06、Q07、Q17、Q18、Q26 的参考答案已删减，这几题的差异要单独标出。

4. **不要改 `.env`**，档位由总指挥看报告后决定。

## 报告

写在 `指挥/报告/041b.md`，内容包括：

- off 档 `summary.json` 原文：一致率、翻转题号、技术失败、费用；
- 与 low 的逐题差异表和理由原文；
- 请求核对结果。

逐题明细复制成 `指挥/报告/041b-off-逐题判分.csv`。

## 约束

- 只判分，不生成回答，不跑 Baseline 或 Agent，不冻结题卷，不做 Gate。
- 不改 `.env`，不提交数据库、密钥。
- 完成后按值班规则移入历史任务。
