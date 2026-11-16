# 042：Judge 定为关闭思考 → 10 题小样全链路 → 达标后启动 Max 档 Baseline（允许付费）

**总指挥决定**（用户 2026-11-16 预先授权总指挥代为决定）：

- 041b 中，Judge 关闭思考加 temperature 0 时，两遍对错一致率 99%，技术失败为 0；low 档只有 93%，high 档只有 91%。判分稳定是用户的第一优先级，所以 **Judge 定为 off**。
- 题卷用 040c 冻结的 `GD-20261116184333`。

## 要做的事

1. **改 `.env`**：只把 `JUDGE_THINKING` 改为 `off`，确认 `BASELINE_THINKING=max`，其他行不动。`.env` 不提交。

2. **重启后端**：按 040c 的方式，向 8010 子进程发 TERM，由 supervisor 拉起新进程。之后确认：
   - 新进程启动时间晚于 `.env` 修改时间；
   - `/api/overview` 返回 200；
   - 只读执行 `load_settings()`，结果里 `judge_thinking == 'off'`，`baseline_thinking == 'max'`。

3. **10 题小样，先 dry-run**：
   ```
   cd "/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目" && PYTHONPATH=backend python3 backend/scripts/sample_chain.py --output /tmp/sample-chain-042
   ```
   核对 plan：
   - snapshot 是 `GD-20261116184333`；
   - config 是 Strict + max；
   - judge_thinking 为关闭；
   - judge 版本为 `rubric-friend-1`；
   - 共 10 题，含 4 道正向、2 道消融、4 道负向，负向里有安全关键题和提示注入题各一道。

   这个脚本是总指挥新写的，还没在真实数据库上跑过。如果报错，**只允许修这个脚本本身**，不改产品代码和判分逻辑，修改写进报告。

4. **正式跑小样**：同一条命令末尾加 `--apply`。允许调用 DeepSeek 和阿里云，约 10 次生成、10 次判分。中断了就用同一命令续跑。

5. **判断是否达标**，以下四条全部满足才算达标：
   - 10/10 完成，技术错误为 0；
   - 每题都有新 Judge 的结果：正向题和消融题有三维分数和理由，负向题有行为判断和安全判断；
   - 回答字数中位数不超过 600，单题回答不超过 1500 字；
   - 没有回答引导用户"查看第 X 页"，也没有大段照抄说明书。

   **用时不作为条件**：Max 档本来就可能超过时延门槛，这正是后面 Agent 要降档优化的地方。只需要如实记录用时。

6. **达标就启动 Baseline**：
   - 调用 `POST /api/evaluations/run`，body 为 `{"fresh": true}`。**不要**带 `unattended_chain`，也不要启动 Agent。
   - 启动前确认 `baseline_preflight().can_start=True`。
   - 等到至少 3 题完成判分，确认没有技术错误、进度在推进，本单就算完成，报告写"Baseline 已启动"和 run id。**不要干等 50 题跑完。**

   **不达标**：不启动 Baseline，在报告里写清楚哪一条没过，附原文，等总指挥处理。

## 报告

写在 `指挥/报告/042.md`，内容包括：

- `.env` 修改（只写键名和新值，不贴其他内容）；
- 重启核对结果；
- dry-run plan 原文；
- 小样 `summary.json` 原文；
- 逐题表：判定、分数和理由、字数、用时；
- 四条达标条件逐条判断；
- Baseline run id、启动时间、已完成题数；
- 调用次数和估算费用。

逐题明细复制成 `指挥/报告/042-小样逐题.csv`，内容来自公开说明书，可以提交。

## 约束

- 不启动 Agent，不做 Gate 2/3，不发布。
- 不改冻结题卷，不删旧记录。
- 不提交数据库、`.env`、密钥、日志。
- 完成后按值班规则移入历史任务。
