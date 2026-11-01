# Judge VNext 实施前初步核查（2026-10-29）

本文件仅记录本次初步只读核查，不构成实施或验收报告。

- 工作树 HEAD 为 `2403e63`，分支 `main`，相对本地记录的 `origin/main` 领先 7 个提交。工作区已有修改 `scripts/verify_self_evolution.py` 及多项未跟踪数据、报告和工具；未清理或覆盖。
- 附件包含六轮最终 SPEC 和唯一实施提示词；本次已读取提示词并检查最终 SPEC 章节目录，尚未完成逐条比对及合并。
- 本机 `127.0.0.1:8010/health` 和 `127.0.0.1:5174/` 连接失败，不能认定运行态通过或推断加载版本。
- `backend/app/evaluation.py` 中 Judge context 包含 `baseline_findings`，且候选执行路径向题目附加基线问题；`backend/app/evaluation_contract.py` 的现行提示词要求同次比较。这与新规范要求独立评分后再映射的目标不一致，需整体调整并验证 Regression，不能仅删除字段。
- 当前 `backend/app/evaluation.py` 根据结果 severity 选择安全关键题，且 severity 可受 Judge issue 影响；需核查并改为冻结题集定义的固定分母，保留历史读取兼容。
- 未核实实际数据库、Snapshot、Corpus/Index 哈希、历史 25 项测试失败、F01–F10、厂家原文或完整最终 SPEC；未实施 Golden Revision、代码修改、离线验收、启动服务或调用 Provider。不得据此宣称新合同已生效或具备正式 Baseline 准入资格。
- 后续按附件任务书先完成保护资产与合同差异审计，再进行有隔离测试的统一实施。真实 Provider、完整 Baseline 和远端推送均不在本次授权内。

## 后续补充核查

- 隔离 SQLite、索引、文档、上传及空环境配置，设置 `RAG_FORCE_MOCK=1` 后执行 `test_evaluation_vnext.py`：61 项通过。该结果只验证现有合同，不代表六轮新合同已实现。
- 沙箱内对 8010/5174 的连接和监听受限；经授权的 `lsof` 显示 8010 有 Python PID 29401、5174 有 Node PID 1419 监听。进程归属、代码版本及页面内容尚未核实，先前端口连接失败不能认定服务未启动。
- 安全启动 API 的尝试因 8010 已被占用而退出；未停止或替换原有进程。进一步读取进程命令及健康接口的权限审核超时，运行态验收未完成。
