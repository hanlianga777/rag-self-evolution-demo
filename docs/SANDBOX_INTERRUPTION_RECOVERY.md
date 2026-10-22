# Sandbox 中断、费用安全与续跑

远程 Alibaba Embedding / Rerank 的超时不等于本地模型故障。检索包装保留阶段、异常类别、HTTP状态、Provider代码、请求ID、重试次数及脱敏正文。历史包装若已吞掉HTTP状态或请求ID，只能报告保存材料能证明的超时/网络类别；不能反推限流、余额、授权错误或伪造云端账单。

- 明确收到的拒绝响应与请求结果未知分开。已确认拒绝的429按共用有限恢复器最多尝试3次/600秒，遵守Retry-After及停止指令；余额、鉴权、无效请求等永久性拒绝不重试。超时、连接中断、无法解析成功响应及结果不明的服务错误停止并要求对账。
- 恢复粒度是单个RPC。Rerank拒绝只重试Rerank，不重跑已成功且已付费的Embedding；外层生成阶段不能再叠加重试。已有PaidRun账本保留每次拒绝与成功，确认拒绝标为rejected，不伪造Token Usage；Unknown/reserved继续保留，不能当0元或自动释放。
- 新Run预约事务重验完整Snapshot、配置、Judge与Evaluation Identity，并在提交预约前拒绝未对账的Checkpoint和账本。拒绝不消耗新的Sandbox次数。已完成Case原样复制；有完整回答的Checkpoint只补Judge。原Run与历史费用保持。
- Sandbox进程重启不继承旧进程的付费授权；保留断点并等待新授权。HTTP启动/续跑显式要求authorize_provider；既有UI付费确认后才发送。未知请求对账和再次付费授权是两件事，后者不能替代前者。
- 未完成50题不产生最终Gate、Bad Case、Regression、Qualification或Recommendation。部分计数仅用于进度与审计；既有历史部分比较不回写，UI按未完成展示。Gate 2等待全部候选完整评测。完成后的11 Gate、评分、Regression及人工发布合同不变。
- 既有FAISS缓存与冻结索引不改；远程Knowledge Pipeline不导入或实例化本地SentenceTransformer，旧本地管线按需加载。

零网络只读审计：

```sh
python3 scripts/audit_sandbox_resume.py --database /path/demo.db --index /path/index --output /private/audit.json
python3 scripts/test_agent_offline.py test_sandbox_failure_contract test_candidate_resume test_paid_run test_knowledge_pipeline
```

审计输出逐候选真实完成/复用数、仅缺Judge数、身份与完整配置核验、Unknown阻断原因、调用量估算及不可确定的费用。调用预测不含重试，历史样本/峰谷费率外推不构成硬预算；未提供真实Alibaba费率或未结算请求时不得报完整总价。

Fixture仅验证执行与保护逻辑：包括38题中断、已生成第39题回答只补Judge、50题后才形成最终统计；不代表真实Sandbox结果或云端恢复验证。架构节点/连线未变，使用原有工作台、卡片及800px抽屉。
