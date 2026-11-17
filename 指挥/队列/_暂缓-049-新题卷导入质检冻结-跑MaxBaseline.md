# 049：取消高峰限制 → 导入新题卷 → 探针、质检、Gate 1、冻结 → 10 题小样 → Max Baseline → 导出成绩（允许付费）

**背景**：用户 2026-11-16 19:05 拍板：题卷按朋友同款结构重做（总指挥出题并审核），Judge 用 low + 3 次取中间值，门槛保留 11 项，一路做到 Baseline 跑完为止，**跑完就停，不启动 Agent**。19:10 用户又要求取消 DeepSeek 高峰时段限制。

新题卷：`指挥/报告/049-新题卷定稿.csv`（50 题）。
- Q01–Q20 正向：10 道单段标准、4 道跨段综合、2 道统计、2 道桥接、2 道台账事实；
- Q21–Q30 消融：每题都配一道正向题（"配对题号"列），4 道口语、3 道别名、2 道弱关键词、1 道跨段；
- Q31–Q50 负向：与上一版题卷逐字相同。
- 全卷没有必答、加分、禁止。

导入脚本已改（本单一起推送）：`桥接`、`台账事实` 改走 Ordinary 构造类型；统计题新增"统计条目"列，逐条核对。总指挥已在本地用 046 导出的切块逐题跑过 `validate_friend_content` 和 `validate_golden_candidate`，50 题 0 错。

## 要做的事

### 一、准备（不花钱）

1. **先确认 047 已完成并通过**：`judge_thinking=low`、`judge_samples=3`、`baseline_thinking=max`，前端构建通过。没完成就等；047 有未解决的产品代码问题就停下写报告。

2. **取消高峰时段限制**：调用 `POST /api/runtime-settings`，body 为
   `{"off_peak_only": false, "audit_note": "用户 2026-11-16 19:10 要求取消高峰时段限制"}`。
   再 `GET /api/runtime-settings` 确认 `off_peak_only=false`。不改代码，不改 `.env`。

3. **dry-run**：
   ```
   PYTHONPATH=backend python3 backend/scripts/import_friend_golden.py --csv 指挥/报告/049-新题卷定稿.csv
   ```
   - `error_rows` 必须为 0。不为 0：**停下**，把每题报错原文贴进报告，不要改 CSV。

### 二、导入、探针、质检、Gate 1、冻结（允许调用 DeepSeek 和阿里云）

4. **导入**：同一命令加 `--apply`。贴出 receipt（候选版本 ID）。逐题断言 50 题的问题、参考答案、题型与 CSV 一致。

5. **硬校验**：对新候选版本跑整卷硬校验，列出仍有缺口的题号，正常应为 0。

6. **探针**：和 040b 第 4 步一样，用 `store.run_probe` 对 50 题各跑一次。每题只跑一次，技术失败可以重试。"标准证据没召回"不算阻断，如实记录。

7. **整卷 QC**：用现有 `quality_check` 对 50 题各做一次（新题卷会走朋友同款质检规则）。
   - 有 **P0**：停下，不做 Gate 1，不冻结，逐题贴原文，等总指挥处理。
   - 有 **P1**：继续，但逐题贴原文。
   - 不要为了挑分数重跑 QC，格式错误的自动修正除外。

8. **Gate 1 与冻结**（第 7 步没有 P0 才做）：和 040b 第 6 步相同。
   - `POST /api/governance/review-batch` 确认 50 题，actor 写 `用户`，reason 写 `用户 2026-11-16 确认：参考答案定稿与整卷质检结果已审核`，`confirmed_manual_review` 为 true；
   - 再 `POST /api/governance/generation-runs/{id}/snapshot` 冻结，得到新 GD 快照。
   - actor 和 reason 里不得出现"Codex""AI""自动""代为""机器"等字样。

9. **冻结后只读核对**：
   - `store.dataset_snapshots()[0]` 是新快照：50 题，20 正向 / 10 消融 / 20 负向；
   - `baseline_preflight().can_start=True`；贴出 `baseline_inputs()` 的完整 config，应为 Strict + max；
   - 抽查 Q15、Q17、Q27 的参考答案与 CSV 一致。

### 三、10 题小样 → Max Baseline（允许付费）

10. **10 题小样**：和 042 一样跑
    ```
    PYTHONPATH=backend python3 backend/scripts/sample_chain.py --output /tmp/sample-chain-049
    ```
    确认：每题 Judge 都判了 3 次（`judge_aggregation.count=3`），有 `borderline` 字段，检索 trace 里有 `enhancement`。小样出现技术失败或这三项缺失：**停下**写报告，不跑 Baseline。小样的对错不作为是否继续的条件。

11. **启动 Max Baseline**：`POST /api/evaluations/run`，body 为 `{"fresh": true}`。
    - **不要**带 `unattended_chain`，**不要**运行 `arm_agent_chain.py`，不启动 Agent。
    - 确认已经跑起来后，等它跑完（大约 1 小时，每隔一段时间看一次即可）。中途技术失败按现有断点续跑；不要为了挑结果重跑整卷。

12. **跑完后导出**（只读）：
    - 11 项门槛逐项的值和是否通过；
    - 错题清单（题号、题型、出题方式、三维分或负向两项、Judge 理由原文）、错题总数；
    - `borderline_question_ids` 和每题是否 3 次一致；
    - `enhancement_telemetry` 原文；
    - P50 / P99、Token 和费用。
    - 逐题表放 `指挥/报告/049-Baseline逐题.csv`（题号、题型、出题方式、是否通过、各维分、是否边界分、标准证据召回排名、回答全文、Judge 理由）。内容来自公开说明书，可以提交。

## 报告

写在 `指挥/报告/049.md`：每一步的结果、各 ID（候选版本、GD 快照、Baseline run）、QC 清单、Gate 1 记录原文、门槛与错题汇总、DeepSeek 和阿里云调用次数与估算费用。中途停下时写清停在哪一步、为什么。

## 约束

- Baseline 跑完就停：不启动 Agent，不跑 Gate 2/3，不发布。
- 不改 CSV、不改判分代码、不删旧版本和旧记录。`.env` 不动（047 已改好）。
- 不提交数据库、`.env`、密钥、日志、截图。
- 完成后按值班规则移入历史任务。

## 补充（总指挥 2026-11-16 20:05，接着上次报告做）

上次停在第 3 步 dry-run：19 题报错，原因是导入器读取 CSV 时丢失了单元格内的换行。已修好，同时按用户 19:45 的要求做了下面几项改动，一起推送：

1. **导入器**：改用 `io.StringIO` 读取 CSV，单元格内换行不再丢失。
2. **参考答案改为结构化分行**：
   - 正向题、消融题：多步骤一步一行、用 1. 2. 3. 编号，可以有"按以下步骤操作："这类引导句和"存放地点："这类小标签；
   - 负向题：内容不变，改成"结论 + 分行要点"。
   - **CSV 已重新生成，SHA-256 会和上次不同。上次 dry-run 的结果作废，从第 3 步重新开始。**
3. **答案锚点**：朋友同款题卷改用 `friend_answer_supported`。
   - 硬要求：数字、型号等必须出现在证据里；引号里的按钮名、提示文字必须逐字出现；"共 N 条"必须和实际列出的条数一致。
   - 允许适度润色：每个分句与证据的用词重合率 ≥ 0.5。
   - 意思是否走样，由整卷 QC 判 P0。
4. **QC（朋友同款分支）**：新增一条 P1——参考答案不通顺、照抄拼接原句、多步骤没有分行编号。
5. **生成 Prompt**：要求每个步骤单独占一行，语句通顺易懂，不生硬拼接原句。Baseline 和 Agent 的回答都走这个 Prompt。
6. **前端**：Golden 题目详情的参考答案改用和回答相同的排版组件，按原文的分行和编号显示，不再在整段前面多套一个"1."。

### 本次要做

- 先跑后端测试 `tests/test_task050_answer_layout.py`、`test_task048_friend_import.py`、`test_task047_judge_median.py`、`test_task005_golden_check.py`。
- 前端跑 `npm run build` 和 `npm test`。只因旧文案、旧结构断言失败的测试，改断言并在报告里列出；功能问题停下写清楚。
- 重启 8010 后端（方法同 047），确认新代码已加载。
- 然后从第 2 步核对 `off_peak_only=false`（上次已设置，不用重复 POST），从第 3 步 dry-run 开始往下执行原第 3–12 步，停止条件不变。
- 冻结后用只读浏览器打开 Golden 的 Q02、Q15、Q40 详情，确认参考答案分行显示、编号从 1 开始、没有重复的"1."；截图只留本机。
- Baseline 跑完后，报告里随机贴 5 道题的回答原文，看是否分行、通顺。

## 补充 2（总指挥 2026-11-16 20:25）

Q14 题面已改为「B2 四足机器人开机和 B2 遥控器开机，长按电源键分别要按多久？」，题面写全了两个产品名，答案和证据不变。CSV 已重新生成，SHA-256 会变。

已经通过的测试、构建和重启都不用重做（代码没变）。直接从第 3 步 dry-run 开始往下做。用户要求一路做到 Baseline 跑完，中间不要停；只有任务单列出的硬停止条件才停。
