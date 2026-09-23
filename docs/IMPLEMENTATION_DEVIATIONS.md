# Implementation Deviations（2026-09-23）

- Generation、Baseline 和 Sandbox 的后台任务仍由当前 FastAPI 进程内线程执行。本轮没有加入队列或跨进程续跑；浏览器断开或刷新不会抹掉已经写入 SQLite 的进度，但服务进程重启会中断线程。若进程在终态写入前退出，Run 可能留在 `running` 等状态，界面从持久化记录恢复的是“最后记录的状态”，不能据此断言 Worker 仍在执行。操作者需核对服务日志并手动处理或重新发起；本轮不自动重试。
- 同步操作（治理人工决策、Agent 生成候选、审批发布、回滚、问答与 Provider 验证）没有服务端细分阶段，Operation Runtime Console 只显示请求中和真实成功/失败，不展示模拟百分比或模型内部推理。
- 自适应 Chunking 候选未通过离线检索质量 Gate，生产继续使用 `section-aware-v2`。详见 [Chunking Strategy 审计](CHUNKING_STRATEGY_AUDIT.md)。
