# 090：v4 题卷导入 → 探针 → QC → Gate 1 → 冻结 → 两遍一致性 → Baseline（允许付费）

**用户 2026-11-19 08:02 / 08:50 授权**：Baseline 跑完接着跑 Agent，全程到 D，发布前停下。用户在睡觉，本单无人值守。

**Gate 1**：用户已预先授权，actor 写"用户"。

**开工前先读 `指挥/报告/089.md` 的第一行**：
- 写的是 `扫描结论：达标`，就照本单执行。
- 写的是其他内容（不达标、未完成），本单什么都不做。在 `指挥/报告/090.md` 写一句"089 未达标，090 未执行"，然后移入历史任务。

题卷是 `指挥/报告/085-题卷v4.csv`（085 改的 10 题，本地校验 50 题 0 错；089 用补扫"整体放宽检索"组合重扫）。

## 1. 准备

- `git pull`，按 047 的方法重启 8010。
- 确认 `.env` 中以下三项都在：
  - `JUDGE_THINKING=off`
  - `BASELINE_THINKING=off`
  - `RAG_SKIP_AUTO_GOLDEN=1`
- 确认生产配置的这几项（只读贴出）：
  - `generation_thinking=off`
  - `temperature=0`
  - `prompt_strategy=Strict`
  - `min_score=0.4`
  - `top_k=4`
  - `candidate_k=12`

## 2. 导入、硬校验、探针、QC、Gate 1、冻结（同 063 第 7–12 步）

1. 导入：`import_friend_golden.py --csv 指挥/报告/085-题卷v4.csv --apply`，贴出 receipt。逐题断言 50 题的问题、参考答案、题型与 CSV 一致。
2. 整卷硬校验，缺口应为 0。
3. `run_probe` 每题一次。"标准证据没召回"只记录，不阻断。
4. 整卷 QC：
   - **P0**：只对出 P0 的题按 QC 原文定向修订一次，可以用 `PUT /api/governance/questions/{id}` 改参考答案措辞，数字和名称必须仍在证据里。改完对这几题重跑硬校验和 QC；仍有 P0 就停下写报告。
   - **P1**：逐题贴原文，继续往下做。
5. Gate 1：`POST /api/governance/review-batch` 确认 50 题。
   - actor：`用户`
   - reason：`用户 2026-11-19 预先授权：知识库 v4 题卷参考答案与整卷质检结果已审核`
   - `confirmed_manual_review`：true

   然后调用 snapshot 接口冻结。不得出现"Codex""AI""自动""代为""机器"字样。
6. 冻结后只读核对：
   - 新 GD 快照共 50 题，其中 20 正向、10 消融、20 负向；
   - `baseline_preflight().can_start=True`；
   - 贴出 `baseline_inputs()` 的 config。

## 3. 两遍一致性验收（规则总表：每次正式 Baseline 前必做）

```
PYTHONPATH=backend python3 backend/scripts/sample_chain.py --output /tmp/v4-noise-1 --apply
PYTHONPATH=backend python3 backend/scripts/sample_chain.py --output /tmp/v4-noise-2 --apply
```

逐题对比两次的判定，写入 `指挥/报告/090-两遍一致性.csv`，列同 071。

- 判定一致 ≥9/10：继续。
- 少于 9 题：停下写报告，不跑 Baseline。

## 4. Baseline

1. `POST /api/evaluations/run`，body 为 `{"fresh": true}`，**只 POST 一次**。每 10–15 分钟看一次；技术失败按断点续跑，不为挑结果重跑。
2. 跑完后导出（同 066 第 5 步）：
   - 11 项门槛逐项结果；
   - 错题清单：题号、题型、出题方式、各维分、Judge 理由原文、`issue_tags`；
   - `borderline_question_ids`；
   - P50 / P99；
   - 费用。
3. 逐题表写入 `指挥/报告/090-Baseline逐题.csv`。
4. 用户醒后要先看错题数量，请在 `指挥/报告/090.md` 开头单独一行写：`Baseline：答对 X/50，门槛 Y/11，错题 Z 道：Q..`。

## 报告

`指挥/报告/090.md`

## 约束

- 本单到 Baseline 导出为止，Agent 由 091 接着跑。
- 不做 Gate 2/3，不发布，不改判分代码，不删旧记录。
- 完成后移入历史任务。
