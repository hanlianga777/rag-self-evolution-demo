# Candidate、中文与全局 UI 整改验收

日期：2026-10-25。基于已 fetch 且与 origin/main 同步的 `db93afc`，真实页面为 `http://localhost:5174`。仅修改前端展示及对应文档/验证，不调用真实 Provider。

1. **Candidate 等高与对齐：通过。** A/B/C 在 1440px、1280px 桌面均为 884px 高；六个正文字段高度依次为 90/150/90/80/80/190px，标题、分割线、底部详情和按钮逐行对齐。名称、轮次、状态、资格位于统一头部；字段缺失保留真实空态。D 与历史方案复用同一组件，使用明确标识的隔离 Fixture 验证；未制造真实 D 或改写历史成绩。
2. **长文本滚动：通过。** 字段标题位于滚动区外，B 的多个目标可在「优化目标」内部滚动；不再使用截断 Tooltip 代替卡片正文。短字段按需滚动，无固定可见滚动条。390px 为单列，字段顺序不变。
3. **中文展示：完成本轮实际发现项。** `display.ts` 维护固定枚举及完整原文逐条对照：当前 A 的假设、收益、风险、证伪条件四段英文完整匹配后中文呈现；B/C 内嵌的 `candidate_k`/`rerank` 参数对象按真实值格式化，`query_only`、开关、Prompt 策略、普通/严重来源标签中文显示。参数分组、Token 指标、知识库流程与覆盖说明同步整理。未改 API 枚举或原始模型回复，未通过关键词拼凑翻译。
4. **Hard Gate 贡献题目：通过。** Faithfulness 的题目正文实测字重 400，题目、得分、状态与「查看案例」同属一行；移动端题目换行到首行，数值/状态/操作保持关联。11 项 Gate 与 10 道 Bad Case 的详情均实际打开检查。
5. **全局组件与浮层：通过已列出的入口检查。** 八导航和全部当前子 Tab 在 1440px、390px 遍历；1280px重点核查 Candidate 与 Pipeline。真实检查覆盖 Baseline 配置/依据/历史、Agent 方案/参数/目标诊断/Search Space/Sandbox/Regression、Golden 题目/历史/覆盖规划、知识文档/主题、发布配置/资格。隔离 Fixture 另验 D、历史轮次、发布/回滚/付费确认、反馈及问答引用，未确认任何真实审批或付费动作。Drawer 实测桌面 800px、小屏 390px、高度为视口 100dvh；Golden 沿原母版由内层 `.candidate-scroll` 独立滚动。Dropdown 原生顶层浮层不受父级裁剪；Tooltip 与底部标签 Popover 在移动视口边界内。保留 Pipeline/Golden 的共享字号、字重及 Card 变量。
6. **不能直接转换的历史英文：保留机制。** 只有确定的完整原文才有逐条中文对照；其余叙述标明「历史英文原文（未翻译）」并保留内容。原始假设、证据、技术对象与完整模型审计仍可展开查看。本轮没有付费翻译，也不承诺自动翻译未来模型输出。
7. **未解决项与验收边界：** 已检查入口未发现本轮遗留的展示错位或视口溢出。真实数据没有 D/新发布及相应问答引用状态，这些使用独立来源的内存 Fixture 验证，不能作为真实业务成绩。开发期间临时 Fixture 热更新曾出现重复 createRoot 警告；Fixture 源不进入产品构建。所有临时前端入口已清理，仅保留可审阅的 `.fixture` 资料。
8. **正式数据保护：通过。** SQLite 以只读连接逐表比较全部行：29 张表的行数与 SHA-256 全部一致。Golden、冻结快照、Baseline、A/B/C 参数/推理/成绩、Regression、Recommendation、版本、Trace/Usage 均未写入。真实 Provider 调用与新增 API 费用为 0。既有无关工作区改动未纳入提交。

## 验证证据

- 前端构建与 48 个测试文件、270 项测试结果见 [构建日志](../outputs/ui_consistency_20261025/build.log)、[测试日志](../outputs/ui_consistency_20261025/tests.log)。新增检查保护统一字段、空态/中断结果归属、只读请求、中文参数及原文保留；Tooltip 内部滚动不会关闭自身。
- 浏览器观测与布局断言见 [browser_checks.json](../outputs/ui_consistency_20261025/browser_checks.json)。包含重复视口、条件状态与真实入口；`fixture` 前缀明确区分隔离数据。保留代表截图，其他观测保留结构化记录。
- 正式数据逐表核对见 [完整性结论](../outputs/ui_consistency_20261025/data_integrity.json)、[整改前](../outputs/ui_consistency_20261025/data_before.json)、[整改后](../outputs/ui_consistency_20261025/data_after.json)。
- 架构影响检查：未修改正式图源 `KnowledgeDiagrams.tsx`、图专用 CSS、节点或连线，无需重新导出架构图。SPEC、CHANGELOG、README 与代码同次提交。

## 代表截图

| 检查项 | 截图 |
|---|---|
| 对齐修复前现场复现（已做部分中文处理） | [行高被覆盖时](../outputs/ui_consistency_20261025/candidate-before-alignment.png) |
| A/B/C 完整对齐 | [1440px](../outputs/ui_consistency_20261025/candidate-final-1440.png) · [1280px](../outputs/ui_consistency_20261025/candidate-final-1280.png) |
| B 长目标内部滚动 | [滚动后](../outputs/ui_consistency_20261025/candidate-b-internal-scroll.png) |
| 手机单列 | [390px](../outputs/ui_consistency_20261025/candidate-final-390.png) |
| Faithfulness 贡献题目 | [桌面](../outputs/ui_consistency_20261025/faithfulness-drawer-1440.png) · [移动](../outputs/ui_consistency_20261025/faithfulness-drawer-390.png) |
| 典型参数详情 | [参数 Drawer](../outputs/ui_consistency_20261025/parameter-drawer-0.png) |
| Dropdown / Tooltip | [Golden 下拉](../outputs/ui_consistency_20261025/golden-profile-dropdown.png) · [长证据提示](../outputs/ui_consistency_20261025/tooltip-final.png) |
| Pipeline 字体与标签母版 | [Pipeline](../outputs/ui_consistency_20261025/settings-1440.png)，与上方 Baseline/Agent 截图对照 |
| 条件状态，仅隔离 Fixture | [D 报告](../outputs/ui_consistency_20261025/fixture-d-report.png) · [历史卡片](../outputs/ui_consistency_20261025/fixture-history-candidate.png) · [发布确认](../outputs/ui_consistency_20261025/fixture-publish-confirm-390.png) · [引用](../outputs/ui_consistency_20261025/fixture-citation-390.png) · [底部标签 Popover](../outputs/ui_consistency_20261025/fixture-tag-popover-390.png) |
