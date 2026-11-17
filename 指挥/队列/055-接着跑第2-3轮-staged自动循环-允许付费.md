# 055：第 1 轮核对无误，接着跑第 2、3 轮（staged-v1 自动循环，允许付费）

**用户 2026-11-17 07:07 授权**："只要保证底层逻辑没有问题，你就接着跑另外两轮，我授权你指挥我们的终端一直跑。"

总指挥已审完 054。第 1 轮数据可信，判断如下：
- 23 道对错翻转里，20 道是交给模型的资料变了（a 类），3 道是思考档位从 Max 降到 Low 引起的（b 类），c 类（纯随机嫌疑）为 0；
- Judge 每题判 3 次，结论分歧的有 18/200 组，取中间值后可以接受。

开跑前，总指挥修了 054 发现的 4 处问题（本单一起推送）：
1. **多标签没进 Agent 提示词**：`bad_cases` 每题现在都带 `issue_tags` 和 `judge_failure`（未达标维度的分数和 Judge 理由）。
2. **"问法改写"在回答问题，不在改写问题**：例如 Q03 改写出"可以设成相同代码"这类编造的结论。现在改写指令要求只输出一条检索查询，补全产品名，把口语换成说明书术语，不回答、不编造。
3. **手动实验没有开逐题对比**：下一轮 Agent 拿不到逐题证据变化。新脚本 `arm_experiment_cycle.py` 会给实验开启 `causal_evidence`，并接上 staged-v1 规则，`max_rounds=3`。
4. **staged 循环支持 `max_rounds`**：跑满第 3 轮仍没达到转入 D 的条件，就停下汇报，不自动开第 4 轮。

同时验证前端 c42b2d6：跑过 Sandbox 后，页面要显示"继续优化下一轮"按钮。

## 要做的事

1. **测试**：后端跑 `tests/test_task050_answer_layout.py`、`test_task038_rulebook.py`，以及用到 `build_agent_prompt`、`_retrieval_queries`、`optimization_cycle` 的相关测试，只列新增失败。前端跑 `npm run build`、`npm test`；只因旧文案断言失败的，改断言并列出。

2. **重启**：按 047 的方法重启 8010 后端；前端用新构建结果重启 5174 的 preview，确保页面加载的是新代码。

3. **页面核对（只读）**：Agent 工作台"进化路线"应能看到"继续优化下一轮"按钮。**不要点它。**

4. **接循环**：
   - 先 dry-run：`PYTHONPATH=backend python3 backend/scripts/arm_experiment_cycle.py --experiment-id EXP-20261117062621288609 --max-rounds 3`，贴出输出；
   - 再加 `--apply` 写入。

5. **启动**：`POST /api/experiments/EXP-20261117062621288609/run-cycle`，贴出返回。
   - 循环会依次做：第 1 轮结论 → 第 2 轮方案 → 3 个 Sandbox → 第 2 轮结论 → 第 3 轮方案 → 3 个 Sandbox → 第 3 轮结论。
   - 按 staged-v1，累计 2 个合格就自动确认 Winner，生成并跑 D，然后停在发布前。
   - 跑满第 3 轮仍未达到条件，就停在 `round_limit`。

6. **盯着跑完**：每 10–15 分钟看一次 `GET /api/experiments/EXP-20261117062621288609` 的 `result.optimization_cycle`（status、phase、round、used、last_error），以及 `指挥/运行状态.md`。
   - 终态为 `round_limit`、`recommended`、`agent_failed`、`failed` 或 `stopped` 时结束。
   - 中途技术失败按系统自带的断点续跑处理；同一故障 2 次续跑仍失败，系统会自己停，这时写清原因。
   - **不要做 Gate 2/3，不要发布，不要退回。**

7. **报告** `指挥/报告/055.md`（只读整理，不再调用模型）：
   - 每轮一节：
     - Agent 对上一轮的结论原文，含 case_reviews 和 lessons；
     - 本轮 A/B/C 各改了哪些参数、理由和预测原文；
     - 实际结果：答对数、11 项门槛、修好、新坏、仍错；
     - 合格与否。
   - 抽 3 道翻转题，核对标准证据排名的变化。
   - 问法改写开启时，贴 5 条改写结果原文，看是否还在回答问题。
   - 如果进入了 D：D 的配置、结果和推荐结论。
   - 全部调用次数、token、估算费用。
   - 逐题对错表写到 `指挥/报告/055-逐题对比.csv`，列：题号，以及 Baseline 和每个 Sandbox 的对错。

## 约束

- 允许调用 DeepSeek 和阿里云，只用于本循环。
- 不改题卷，不改判分，不删记录，不重跑已完成的 Sandbox。
- 不提交数据库、`.env`、日志、截图。
- 本单可能要跑 2–3 小时，不要因为时间长而中断。
