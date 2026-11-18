# 066：063 续接——修好 Judge 费用合并后，跑小样 → Baseline → 导出（允许付费）

**用户 2026-11-18 10:40 授权**：知识库 v3 上一路跑到第 1 轮 A/B/C 跑完，中途不停，不发布。本单无人值守。

## 背景

063 已完成第 5–12 步，这些步骤**不要重做**：
- 扫描：缺口 9 道，可修 5 道；
- 导入、硬校验、Probe 和 QC：P0=0、P1=0；
- Gate 1 与冻结：快照 `GD-20261118174750`。

063 停在第 13 步小样，原因是 `ai_service.py` 把三次 Judge 的费用报告字典直接 `sum()` 了。总指挥已修复：现在按三次的真实用量合并后重算一次 `cost_fields`。`test_task047_judge_median.py` 也改成用真实的字典形状模拟，8 项全部通过。

## 要做的事

1. **拉代码、跑测试、重启**：`git pull`；跑 `test_task047_judge_median.py`，再跑 063 第 2 步那 6 组测试，只列新增失败；按 047 的方法重启 8010。

2. **只读确认**：`GD-20261118174750` 仍是当前冻结题卷；`baseline_preflight().can_start=True`。

3. **小样**：用**同一个**输出目录续跑：
   ```
   PYTHONPATH=backend python3 backend/scripts/sample_chain.py --output /tmp/sample-chain-063 --apply
   ```
   - 总指挥知情并授权：第一次中断时 7 题只有回答没有成绩，Q38、Q31、Q33 也未完成，脚本会重新生成这几题的回答，多花几分钱。这是技术续跑，不是为挑结果重跑，不违反规则。
   - 验收：10 题都有 `result`；每题判了 3 次；有 `borderline` 字段；检索 trace 里有 `enhancement`；Judge 有 `cost_estimation`。出现新的技术错误就停下，贴出原文。

4. **Baseline**：同 063 第 14 步。`POST /api/evaluations/run`，body 为 `{"fresh": true}`，**只 POST 一次**。每 10–15 分钟看一次，技术失败按断点续跑。

5. **导出**：同 063 第 15 步，逐题表写到 `指挥/报告/066-Baseline逐题.csv`。

## 报告

`指挥/报告/066.md`：
- 小样验收；
- Baseline run ID；
- 11 项门槛逐项结果；
- 错题清单（含 issue_tags 和 Judge 理由）、borderline；
- P50/P99、费用。

控制在 150KB 以内。

## 约束

- 不重做 063 第 1–12 步；不改题卷、判分逻辑；不删记录。
- 不启动 Agent（由 067 做），不做 Gate 2/3，不发布。
- 完成后移入历史任务。
