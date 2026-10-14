# RAG诊断修复与清空 Implementation Plan

**Goal:** 执行用户已批准的集中修复任务；Provider调用0，真实评测0。
**Spec:** docs/RAG_SELF_EVOLUTION_SPEC.md，用户2026-10-14完整附件为本轮设计及实施授权。
**Architecture:** 复用diagnostics/JSON reasoning/现有UI；新增小型历史对象生命周期模块，不重建数据库结构或Knowledge。Pending继续阻断，正式计数与语义确证分列。当前运行参数另存无评测/审批/发布资格的bootstrap配置。
**Tech Stack:** Python标准库、现有FastAPI/SQLite/React/TypeScript；不新增依赖。

- [x] 保存修改前身份、数据库各表数量、服务进程、API负载与延迟及Knowledge文件摘要；核对无运行任务。
- [x] 离线测试先行：评测主张合同与成对案例、Agent干预方向、证据元数据输入、事务清理与对象保留、重启不恢复Seed。
- [x] 分文件并行：评测与Agent只改各自合同文件；前端只改现有诊断/详情；主代理负责ai_service、governance、main及数据生命周期。共享数据库禁止分工写入。
- [x] 保留11 Gate及Regression严重0/普通≤1；升级语义版本，不回写历史；来源元数据与操作边界按输入合同验证，真实模型效果不做承诺。
- [x] 实现对象依赖闭包保留（历史实验/评测各50，完整题组，不按表50行）；活动/被引用对象保护。历史列表服务器分页≤50。
- [x] 受控停后端、一个SQLite Backup API备份；事务清理全部实验/Seed数据，保留迁移/工具/Pipeline及运行参数，VACUUM后核验原Knowledge产物逐字节不变。
- [x] 重启同一8010/5174启动入口；只读HTTP/UI八导航、空状态及接口验收；所有Provider方法测试拦截，不运行真实问答。
- [x] Mini20仅从外部原审计CSV核查类别/Topic/Slot，提出含Q23/38/39的诊断提案；不创建、冻结、导入或评测。
- [x] 同步SPEC/Changelog/README和受影响架构说明；执行后端、前端、TypeScript/Build，检查diff；最终A–H报告记录证据及限制；提交推送main的结果由最终交付消息核验。
