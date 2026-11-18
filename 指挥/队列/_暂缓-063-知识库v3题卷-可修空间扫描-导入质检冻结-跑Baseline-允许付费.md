# 063：知识库 v3 题卷 → 检索可修空间扫描 → 导入、探针、质检、Gate 1、冻结 → 小样 → Baseline（允许付费）

**用户 2026-11-18 10:40 授权**：知识库 v3 上一路跑到第 1 轮 A/B/C 三个 Sandbox 跑完，中途不停，不发布。用户在睡觉，本单无人值守。

本单做到 Baseline 跑完为止，第 1 轮 Agent 由 064 接着做。

**题卷**：`指挥/报告/063-题卷v3.csv`，共 50 题，由总指挥出题，生成脚本是 `063-出题脚本.py`。

| 题型 | 题号 | 构成 |
|---|---|---|
| 正向 | Q01–Q20 | 单段 10 / 跨段 4 / 统计 2 / 桥接 2 / 台账 2，主打相近型号混淆（CR3/CR16、MG400/M1 Pro、PGC-50/PGE-50、G1 基础版/进阶版） |
| 消融 | Q21–Q30 | 每题配一道正向题：别名 2 / 口语 3 / 弱关键词 4 / 跨段 1 |
| 负向 | Q31–Q50 | 沿用 052 的 12 题，新增 8 题；资料不足 6 / 追问 6 / 安全关键 5 / 提示注入 3 |

总指挥已用 062 导出的切块在本地跑过 `validate_friend_content`、`validate_golden_candidate` 和答案锚点检查：**50 题 0 错**。

## 一、准备与检查（不花钱）

1. **确认 062 已完成**：13 份文档、983 子块。`.env` 中应有 `RAG_SKIP_AUTO_GOLDEN=1`、`BASELINE_THINKING=high`；当前生产配置应为 `initial-20261118161425837069`（分数线 0.4、思考 high）。不符就停下写报告。

2. **跑测试**，只列新增失败：
   ```
   test_final_policy.py test_task004_policy.py test_task013_cycle_recovery.py test_cycle_manual_control.py test_task050_retrieval_headroom.py test_task050_answer_layout.py
   ```
   062 报的两项（test_task004 集成断言、test_cycle_manual_control 的 round_completed）已由总指挥修复。若仍失败，贴出原文后继续。

3. **重启**：按 047 的方法重启 8010。本单之前推送了 `optimization_cycle.py`、`ai_service.py`（新增 `retrieve_context`）和 `arm_experiment_cycle.py`。

4. **导入 dry-run**：
   ```
   PYTHONPATH=backend python3 backend/scripts/import_friend_golden.py --csv 指挥/报告/063-题卷v3.csv
   ```
   `error_rows` 必须为 0。不为 0 就**停下**，逐题贴报错原文，不要改 CSV。

## 二、检索可修空间扫描（少量付费：阿里云向量 / 重排；开改写、多问法、HyDE 时调用关闭思考的 DeepSeek 小请求）

5. 先跑冒烟：
   ```
   PYTHONPATH=backend python3 backend/scripts/retrieval_headroom.py --csv 指挥/报告/063-题卷v3.csv --smoke
   ```
   能跑通再跑正式扫描：
   ```
   PYTHONPATH=backend python3 backend/scripts/retrieval_headroom.py --csv 指挥/报告/063-题卷v3.csv --output 指挥/报告/063-检索可修空间.csv
   ```
   - 底座是朴素默认配置 `FRIEND_BASELINE_CONFIG`。
   - 原样贴出 JSON 输出，重点是 `baseline_gap`、`fixable`、`unfixable_gap`、`best_configs`。

6. **判断是否继续**：
   - `baseline_gap`（Baseline 配置下标准证据没全部进入最终资料的正向 / 消融题）**少于 8 道**：停下，不要导入，把扫描结果写进报告，等总指挥改题。
   - 8 道及以上：继续。

## 三、导入、探针、质检、Gate 1、冻结（允许调用 DeepSeek 和阿里云）

步骤同 049 第二部分。

7. **导入**：加 `--apply`，贴出 receipt。逐题断言 50 题的问题、参考答案、题型与 CSV 一致。

8. **硬校验**：整卷跑一遍，缺口应为 0。

9. **探针**：`store.run_probe` 每题跑一次。"标准证据没召回"只如实记录，不阻断。

10. **整卷 QC**：每题做一次。
    - 有 **P0**：只对出 P0 的题，按 QC 原文做一次定向修订（朋友规则：只修坏题、最多 1 轮）。可以用 `PUT /api/governance/questions/{id}` 改参考答案的措辞；数字、名称必须仍在证据里。改完对这几题重跑硬校验和 QC。仍有 P0 就停下写报告。
    - 有 **P1**：继续，但逐题贴原文。

11. **Gate 1 与冻结**：
    - `POST /api/governance/review-batch` 确认 50 题；actor 写 `用户`，reason 写 `用户 2026-11-18 确认：知识库 v3 题卷参考答案与整卷质检结果已审核`，`confirmed_manual_review` 为 true；
    - 再调用 snapshot 接口冻结。
    - 不得出现"Codex""AI""自动""代为""机器"等字样。

12. **冻结后只读核对**：
    - 新 GD 快照共 50 题：20 正向 / 10 消融 / 20 负向；
    - `baseline_preflight().can_start=True`；
    - `baseline_inputs()` 的 config 原样贴出，应为 Strict + high、min_score 0.4。

## 四、10 题小样 → Baseline（允许付费）

13. **小样**：
    ```
    PYTHONPATH=backend python3 backend/scripts/sample_chain.py --output /tmp/sample-chain-063
    ```
    确认每题都判了 3 次、有 `borderline` 字段、检索 trace 里有 `enhancement`。出现技术失败或这三项缺失就停下。

14. **Baseline**：`POST /api/evaluations/run`，body 为 `{"fresh": true}`。
    - **不要**带 `unattended_chain`，不运行 `arm_agent_chain.py`。
    - 确认跑起来后等它跑完，每 10–15 分钟看一次。技术失败按现有断点续跑；不要为了挑结果重跑整卷。

15. **跑完后导出**（只读）：
    - 11 项门槛逐项的值和是否通过；
    - 错题清单（题号、题型、出题方式，三维分或负向两项，Judge 理由原文）和错题总数，标出每道错题的 `issue_tags`；
    - `borderline_question_ids`；`enhancement_telemetry`；P50 / P99；Token 和费用；
    - 逐题表写到 `指挥/报告/063-Baseline逐题.csv`（题号、题型、出题方式、是否通过、各维分、是否边界分、标准证据召回排名、回答全文、Judge 理由）。
    - 前端打开 Baseline 页，确认显示的是这次的新 Baseline（只读，不截图入库）。

## 报告

`指挥/报告/063.md`：
- 每一步的结果；
- 各 ID：候选版本、GD 快照、Baseline run；
- 可修空间扫描结论、QC 清单、Gate 1 记录原文；
- 门槛与错题汇总；
- DeepSeek、阿里云调用次数和估算费用。

中途停下时，写清停在哪一步、为什么。

## 约束

- Baseline 跑完就停：不启动 Agent（由 064 做），不跑 Gate 2/3，不发布。
- 除第 10 步的定向修订外，不改 CSV 或题目；不改判分代码；不删旧版本和旧记录。
- 不提交数据库、`.env`、密钥、日志、截图。
- 完成后移入历史任务。
