# 051：换掉 2 道误判题 → 重新冻结 → 沿用 48 题旧回答、新判分重打分的 Baseline（允许付费）

**用户 2026-11-16 23:13 拍板**：
- Q23、Q48 被 Judge 的"看不到出处"缺陷误判，这两题换成更容易错的新题；
- 其余 48 题的**回答不重新生成**，沿用 049 Baseline `EVAL-20261117030059357816` 的原回答和原耗时；
- 全部 50 题用修好的 Judge（资料带出处，`rubric-text-source-2`，low，每题判 3 次）重新打分；
- 只有新换的 2 题现场生成回答；
- 启动 Agent 的条件不变：错题 ≥5 道。**本单跑完就停，不启动 Agent。**

**新题卷**：`指挥/报告/051-换题版题卷.csv`。只有 Q23、Q48 两行和 049 定稿不同，其余 48 行逐字相同。
- 新 Q23：消融·口语，与 Q13 配对，"那台洗地机满电能干多久活？没电了充满得等多长时间？"；
- 新 Q48：负向·资料不足，"B2 遥控器里的数传模块用的是哪个无线频段，2.4G 还是 5.8G？"。

**新代码**（本单一起推送）：判分回放增加 `allow_new_questions`。
- 新题卷只换了少数题（最多 5 道），而且题数、题型配比不变时，未换的题按"题面 + 题型 + 参考答案"匹配原回答并沿用；
- 换上的新题现场生成；
- 测试在 `tests/test_task050_answer_layout.py`。

## 要做的事

1. **先确认 050 已完成**。050 的诊断要在重启前做，所以 051 必须排在 050 之后。

2. **测试**：后端跑 `tests/test_task050_answer_layout.py`、`test_judge_replay_v5.py`、`test_replay_api_v5.py`、`test_task039_rubric_judge.py`、`test_task047_judge_median.py`，只列新增失败。然后按 047 的方法重启 8010 后端。

3. **导入**：
   - `PYTHONPATH=backend python3 backend/scripts/import_friend_golden.py --csv 指挥/报告/051-换题版题卷.csv`，`error_rows` 必须为 0；
   - 再加 `--apply` 导入；
   - 逐题断言 50 题与 CSV 一致。

4. **探针、QC、Gate 1、冻结**：做法同 049 的第 5–9 步和补充 4。
   - 50 题 Probe、QC 必须全部"通过"才冻结；
   - Gate 1 的 actor 写 `用户`，reason 写 `用户 2026-11-16 确认：换题版参考答案与整卷质检结果已审核`；
   - 冻结后核对新快照是 50 题，20 正向 / 10 消融 / 20 负向。

5. **回放预检**：`GET /api/evaluations/EVAL-20261117030059357816/judge-replay/preflight?judge_thinking=low&allow_new_questions=true`
   - 应为 `can_replay=true`、`reusable=48`；`new_question_ids` 只有新 Q23、新 Q48 两个 ID。
   - 不满足就贴出完整返回（含每题 blockers）后停下，不要绕过。

6. **启动**：`POST /api/evaluations/EVAL-20261117030059357816/judge-replay`，body 为 `{"judge_thinking":"low","allow_new_questions":true}`。
   - 等它跑完：48 题只判分，2 题生成加判分；
   - 不要带 `unattended_chain`，不要运行 `arm_agent_chain.py`。

7. **导出**：同 049 第 12 步。
   - 11 项门槛原始值、错题清单和 Judge 理由、`borderline_question_ids` 与每题 3 次是否一致、P50/P99、调用次数和费用；
   - 逐题表写到 `指挥/报告/051-Baseline逐题.csv`，列同 049；
   - 再加一列"相对 049 的对错变化"，逐题列出 049 和 051 的对错对比。

8. **页面核对**：只读浏览器打开概览页和 Baseline 页，确认显示的是本单的新 Baseline，门槛、答对数、错题清单都不为空。截图只留本机。

## 报告

写在 `指挥/报告/051.md`。

## 约束

- 跑完就停：不启动 Agent，不做 Gate 2/3，不发布。
- 不改 CSV，不改判分代码，不删旧版本和旧记录。
- 不提交数据库、`.env`、日志、截图。
- 结果如实认：不因客观原因加注解、不重跑、不剔除任何一项。
- 完成后按值班规则移入历史任务。
