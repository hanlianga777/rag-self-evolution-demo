# 050：查清页面为什么看不到新 Baseline；验证 Judge 出处修复（不花钱）

**背景**：049 的 Baseline `EVAL-20261117030059357816` 已跑完，但用户在 demo 前端看不到结果，数据显示为空。总指挥审核时还发现一个 Judge 输入缺陷：
- 生成回答时，模型能看到每段资料的文档名和章节（例如"R1遥控器 / 技术规格""卡赫 KIRA B 50"）；
- Judge 只看到资料正文，看不到出处；
- 结果是回答里正确说出的型号、遥控器版本，被 Judge 判成"资料里没有、属于编造"（Q17、Q23、Q48、Q22、Q28 的判分理由里都出现了这一条）。

已修好：Judge 的每条资料前加"（出处：文档名 · 章节）"，仍不带任何 ID；Judge 输入版本改为 `rubric-text-source-2`。新增测试在 `tests/test_task050_answer_layout.py`。

## 要做的事（全程不调用 DeepSeek、阿里云）

1. **先诊断，再重启**。用**当前还在跑的后端和数据库**（不要先重启），执行只读诊断：
   ```
   PYTHONPATH=backend python3 backend/scripts/why_baseline_hidden.py
   ```
   把完整输出贴进报告。

2. **记录页面现状**。用只读浏览器打开概览页和 Baseline 页，逐块写下哪些地方为空、显示什么文字。截图只留本机。
   再贴出 `GET /api/evaluation`、`GET /api/overview` 返回的这些字段：`id`、`status`、`current_baseline_id`、`baseline_unavailable_reason`、`requires_policy_upgrade`。

3. **跑测试**：`tests/test_task050_answer_layout.py`、`test_task039_rubric_judge.py`、`test_task047_judge_median.py`、`test_task038_rulebook.py`，以及用到 `final_texts` / `rubric_input` 的其他测试。只列新增失败。

4. **重启 8010 后端**（方法同 047），再执行一次第 1 步的诊断和第 2 步的接口查询，贴出前后对比。

5. **只读预检判分回放**：调 `GET /api/evaluations/EVAL-20261117030059357816/judge-replay/preflight?judge_thinking=low`，贴出完整返回。
   **只做预检，不要启动回放**：回放要等用户批准，总指挥会另发任务单。

## 报告

写在 `指挥/报告/050.md`。只写事实；不确定的写"未知"。

## 约束

- 不跑 Baseline、Agent、回放；不改题卷；不删记录。
- 不提交数据库、`.env`、日志、截图。
- 完成后按值班规则移入历史任务。
