# 039：新 Judge（朋友同款三维 Rubric）落地验证（不花钱）

**背景**：按 `指挥/规则总表.md` 第二节，总指挥写好了新 Judge，已推送：

- 新模块 `backend/app/rubric_judge.py`：
  - Prompt 约 1000 字（旧的 7317 字）；
  - 正向 / 消融题打 Correctness / Faithfulness / Completeness 三维分，每维只能取 0/20/40/60/80/100，并附一句理由；
  - 负向题判"行为是否正确"和"有没有危险或越界内容"；
  - Judge 输入只有正文，不含编号和 ID。
- `evaluation_contract.VERSIONS` 切到 `rubric-friend-1`。旧的 `business-vnext-1` 结果只读，旧 Baseline 不能再续跑，需要新 Baseline。
- `evaluation.py::_score_rubric`：
  - 逐题对错按门槛数字判：正向 80/80/75，消融 70/75/65，负向看行为和安全；
  - 门槛平均值来自同一组分数；
  - 不再跑本地正则安全守卫。
- `ai_service.judge`：判分复用键只看"题目 + 参考答案 + 回答正文 + 证据正文 + 判分版本 + Judge 档位"。
- `providers.py::_judge_rubric`：只做格式校验；格式不合格按技术失败重试，不算 Bad Case。
- 新测试 `backend/tests/test_task039_rubric_judge.py`（11 项，含假 Judge 的端到端打分），以及测试辅助 `backend/tests/rubric_fixture.py`。

## 已知问题（本单要处理）

下面这些旧测试里的假 Provider / 假 Runtime 的 `judge()` 仍返回旧格式，新判分把它当技术失败、按退避重试，**测试会卡住很久**：

`test_baseline_resume.py`、`test_agent_exploration_e2e.py`、`test_evaluation_context.py`、`test_restoration_diagnosis.py`、`test_governance.py`、`test_task013_cycle_stress.py`、`test_task033c2_judge.py`、`test_v14_api_lifecycle.py`、`test_v11_e2e.py`

请把这些假 judge 改为返回 `tests/rubric_fixture.py::rubric_judge_output(category, passed)` 的格式，保持原测试想表达的对错。旧格式专门测历史只读的用例，可以保留旧路径的单测，但不要让它走新评测主链路。

## 要做的事

1. 先确认 038 已完成；没完成就等。不要两单同时改同一批测试。
2. 新测试 `test_task039_rubric_judge.py`、`test_task038_rulebook.py` 必须全过。
3. 按上面的清单改假 judge，然后全量跑后端测试。必须加 `-o faulthandler_timeout=60`，防止再卡住。报告前后通过 / 失败数，剩下的失败逐条说明原因。
4. 只读核对 Judge 的真实请求长什么样：用一题已保存回答，在**不发请求**的前提下离线构造 `rubric_input(...)` 和请求体，确认三点并把请求体（去掉密钥）贴进报告：
   - 里面没有 chunk_id、DOC- 这类编号；
   - system prompt 是新的 `RUBRIC_JUDGE_PROMPT`；
   - Judge 档位取 `.env` 的 `JUDGE_THINKING`（报告写明当前值，不改）。
5. 重启后端，确认启动正常，主链路页面能打开。

## 约束

- 不调用付费模型，不跑 Baseline 或 Agent，不做 Gate，不发布。
- 不提交数据库、`.env`、密钥。
- 报告写在 `指挥/报告/039.md`。完成后按值班规则移入历史任务。

## 追加（总指挥 11:20 推送，一并验证）

- **防白跑**（规则总表五.3）：`evaluation.py::no_effect_source` 判断"A/B/C 的 50 题回答请求全部复用自同一个已有 Run"。命中时标 `result.no_effect`，该方案不算合格；`governance.sandbox_attempts_used` 退还预算，每个实验最多退 3 次；Agent 输入里可以看到 `no_effect`。
- **一致率测试开关**：环境变量 `JUDGE_REUSE_BYPASS=1` 时，判分不读也不写复用表，只供内部"同一批回答判两遍"的测试用，正式评测不要设置。
- 测试：`test_task039_rubric_judge.py` 末尾新增 2 项。
