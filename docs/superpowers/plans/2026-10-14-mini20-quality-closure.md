# Mini20业务质量收口 Implementation Plan

**Goal:** 按用户2026-10-14完整附件，在本轮独立预算内合法组卷、逐题治理及所有者委托审核；仅条件全部真实满足才冻结。
**Spec:** docs/RAG_SELF_EVOLUTION_SPEC.md；授权源 /Users/zhanghaohan/.codex/attachments/de77008d-285d-4ee1-8d11-07be46e7c105/已粘贴的文本.txt。
**Architecture:** 保留现有Mini Coverage，以Business V2装饰业务输入，原20题仅作新候选内容来源，兼容优先复用，缺槽定向补齐。复用PaidRun、逐Slot持久化、十维审计、Probe/QC、Revision及现有委托事务。
**Tech Stack:** 现有Python/SQLite/React；无新依赖、知识索引重建或评测运行。

- [x] 核实授权、main、当前Corpus、上轮预览及价格/余额/旧未知费用；独立预算不复用旧授权。
- [x] Mini Business V2保留原Plan要求；先失败测试再适配Mini业务Prompt/十维审计路径。
- [x] Mini owner delegation按20题及显式profile约束；保留Medium旧授权、PDF/质量约束；UI不冒充真人审核。
- [x] 停止写入前核查任务；SQLite Backup API备份；创建新Run，按冻结Slot重新核验复用题，保留外部来源SHA，不恢复旧历史。
- [x] 只补缺槽，现有每Slot两次尝试边界；真实失败持久化；逐题Business/Probe/QC及受控Revision，不重跑未变化的通过题。
- [x] Codex逐题独立审核已保存；19建议通过、Q18因Business补审外发被拒待复核。未绑定正式授权/批准或冻结，不冒充全部完成。
- [x] 记录实际Token、保守金额与账户扣款观测；资产SHA不变，接口/UI及相关测试、独立代码审查和SPEC/文档同步已完成；Git交付状态以最终消息为准。

**实际暂停点：** 两个本轮新Run、11次正式受控Revision保留；最终Run Hard Validation20、Probe20、QC20通过，Business19/20，Q18旧grounding=false未覆盖。必要禁令3-Child窄范围重审也被自动审批拒绝（未调用），须用户具体外发授权后只补Q18 Business。逐题独立审核已保存（19建议通过、1待复核），未运行批准/冻结事务。

**验收记录：** 后端全套575项通过（隔离Legacy离线Fixture），最终相关102项通过；前端209项及构建通过；当前20题Hard Validation20/20；8实际导航无页面错误。Provider288次真实Usage保守上界7.118210元，DeepSeek余额减少3.43元，Alibaba标价0.073268元、实扣未知。API已恢复；最终Commit/push状态见交付消息。
