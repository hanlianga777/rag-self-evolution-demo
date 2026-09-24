# 3–5 分钟面试演示说明

1. **概览（30 秒）**：说明系统将上线后的 RAG 问题变成可审计闭环，而非自动上线调参。
2. **测试集治理（45 秒）**：展示 Coverage Plan、Hard Validation、Probe、QC 与人工审核；强调历史题只是 Legacy。
3. **评测（45 秒）**：打开固定 Golden Snapshot 的 Baseline，查看 11 项 Gate、Bad Case 与逐题证据。
4. **进化实验室（45 秒）**：从真实 Bad Case、根因到并列 A/B/C，说明每项只改服务于假设的必要参数。
5. **沙箱与推荐（45 秒）**：比较 Baseline 与候选的 Gate、Regression、检索指标、TTFT 和 Token；说明 Overall 仅展示。
6. **发布与监控（30 秒）**：展示一次“确认发布”、版本快照、Rollback 与 Monitoring 的 Human Confirm；结论是 AI 不会自动发布。

当前用户库尚无正式 Golden Snapshot，故步骤 3–6 的真实结果仍未运行；演示时应说明前置条件，不用隔离测试或历史 Seed 冒充已发布成果。
