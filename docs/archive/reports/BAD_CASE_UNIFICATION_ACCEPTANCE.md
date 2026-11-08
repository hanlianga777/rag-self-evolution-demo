# Baseline 与 Agent 产品收口验收 · 2026-10-22

基于 GitHub main `ef9ff8c3c43c38eae3eb57b688aaecdac4b8d3ad`，只修改业务展示和 Agent 目标选择，不修改评分与实验保护。

## 已完成的代码与离线验证

- Baseline 核心结果统一为 Overall、11 Hard Gate、Bad Case 数；FAIL 全部进入 Agent。
- 10 题列表展示失败要求 / 关键差异和最新 `experiment_plan.directions`，逐题可进优化规划、查看案例与来源。未知根因保留，不作为新业务分类。
- 隐藏主页面的程序错误字段；阶段约束和完整 JSON 保留在默认折叠审计。移除重复争议列表，全部 50 题保留在折叠只读记录。
- 维持深蓝导航、既有卡片与统一 800px 右侧 Drawer；无新增导航，无架构节点或连线变更。
- Agent 目标以业务 FAIL 为准，PASS 即使遗留技术标记也不进入处理。旧无业务合同记录仅读取保存的 `passed=false`；正式版本身份守卫保持。
- 前端 45 文件 / 258 测试通过，TypeScript + Vite 构建通过。后端 Agent / 实验 / 评测合同定向 108 测试通过（1 跳过）。
- 正式数据 SQLite Backup 副本离线走真实 Agent 目标构造、参数校验、检索、50 题 Sandbox / Regression 执行代码，外网 / Provider 阻断，答案与评分为明确标记的 Fixture。10/10 输入、10/10 有合法探索路径；不证明真实改善，真实修复数 0。

## 正式 Baseline

`EVAL-20261021141811373593`，50/50、40 PASS / 10 FAIL、Overall 91.5、11/11 Hard Gate。

保存与当前代码重新计算的评测身份均为 `4c6e8a2da0f2e23deb6200551dc79f9894370ef01b15d4c914b1e78a1a66dccf`；`require_current_baseline()` 通过，无需改冻结身份或重跑 Baseline。Agent 启动无新增 Q18 前置；新版 Judge-only 回放仍是独立 Q18 复核与费用授权流程，不在本轮执行。

## 操作与授权边界

用户下一步：Baseline → Bad Case 诊断 →「进入 Agent 处理」；在 Agent →「优化 Agent」查看全部 10 题的优化方向。后续获得费用授权后，才点击「生成 A / B / C」并确认费用；方案生成不自动运行 Sandbox。

真实 A/B/C 质量、全部冻结 50 题 Sandbox、Regression 改善与 Recommendation 尚待独立付费验证。未自动确认报告、发布、回滚；本轮 Provider 调用 0、费用 0。

## 实际服务验收

代码离线验证完成后，在本机安全识别并刷新本项目 5174 / 8010 服务；进程目录、加载指纹、只读 API、浏览器截图及正式数据保护结果由同目录验收产物记录。
