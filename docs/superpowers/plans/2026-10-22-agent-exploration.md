# Agent 假设驱动闭环实施与验收计划

目标：10个真实业务FAIL均有探索实验或能力修复路径；不把Unknown改写为已确认根因。按Owner本轮一次性实施授权执行，无中间付费或发布授权。

1. 审计最新main、冻结50题、全部10个FAIL的Golden/原答/Judge/Candidate/Rerank/Final与现有SPEC、朋友流程参考。记录整改前全量测试、原库与索引指纹。
2. 在现有diagnostic_view增加只读experiment_plan：先验证原Judge、Canonical三阶段及身份；按冻结来源的结构差异提出可证伪实验；来源/执行缺失生成具体修复任务。原技术诊断继续严格复验，不修改评分或补造语义。
3. 复用validate_intervention区分confirmed与exploratory。后者绑定实际观察/合法参数/证伪条件，Unknown不变；Sandbox创建前重新校验完整Diff及目标；D复验独立实测来源，仍完整评测。
4. 复用八导航/原列表和Drawer，展示全部业务问题、探索与能力缺口、真实目标关联。同步唯一架构源及导出、SPEC/README/验收文档。
5. 先运行会失败的准入/Trace/UI/篡改测试，再最小实现；临时50题Fixture走真实Agent→检索→Sandbox→Regression，检查修复/新增失败与不能跨配置相加；全量回归、原库哈希、浏览器预览、统一提交推送。

保护：Provider0；不加载真实.env，不重启正式服务；正式DB只读及一次临时SQLite Backup副本，Corpus/索引只读；无新增依赖、无题号特例；Gate1/2/3、11 Hard Gate、严重0/普通≤1 Regression、冻结身份保持。
