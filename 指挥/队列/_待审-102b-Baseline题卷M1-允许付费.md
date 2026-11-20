# 102b：Baseline（题卷 M1）——只跑 Baseline 并导出，不加难、不启动 Agent

**依据**：规则总表 v2026-11-20 四.1、五、十一、十二.4。

**前置**：102 已完成，并通过关卡 3（Claude + GPT 审核 QC 结论与两遍一致性）。

**授权**：用户 11-20 08:47 已授权。

## 1. 开跑前核对（只读）

1. 运行规则一致性测试、`rules_e2e_check.py`，贴出规则指纹。
2. 核对 `baseline_inputs()` 的 config，逐项与规则总表四.1 一致。
3. 核对 `baseline_preflight().can_start=True`，且冻结快照为 102 报告第一行里的那个，`knowledge_identity` 与 101a 一致。

## 2. Baseline

`POST /api/evaluations/run`，body 为 `{"fresh": true}`。

- **只发一次**。
- 技术失败按断点续跑；不为挑结果而重跑。

## 3. 导出（只读）

1. 11 项门槛的逐项结果。
2. 错题清单，每题列出：题号、题型、出题方式、各维分数、Judge 理由原文、`issue_tags`、本题标准证据块是否进入最终送给模型的资料（是 / 否）、模型回答原文。
3. `borderline_question_ids`、P50/P99、费用。
4. 评测记录里的 `run_snapshot`：`rules_version`、`rules_hash`、`golden_version`、`knowledge_identity`。
5. 逐题表写入 `指挥/报告/102b-Baseline-M1逐题.csv`：每题一行，列出对/错、三维分数、证据是否进入资料。

## 报告

`指挥/报告/102b.md`。第一行写：

`Baseline（M1）：答对 X/50，门槛 Y/11，错题 Z 道：Q..；run ID <…>；指纹 <hash>`

## 约束

- 允许调用 DeepSeek 和阿里云，只用于本次 Baseline。
- 不加难，不启动 Agent，不改题卷和判分。
- 完成后移入历史任务。后续步骤（加难或 Agent）等关卡 4 审核后另行安排。
