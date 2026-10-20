# Baseline 评测框架根因修复与离线回归

日期：2026-10-20。Ponytail Full。未调用真实 Provider，未新建或恢复正式 Baseline/Candidate。

## 1. 确定根因与此前修复的关系

实际失败运行：`EVAL-20261020145850446479`，北京时间 22:58:50.482—22:59:35.106，约44.6秒，Q01 `V1G-110926448917-01`，业务判定0/50。界面45.5秒包含外围耗时。持久化记录没有独立的前端 Operation ID，因此使用 Run ID、时间和 Worker PID 93127 精确关联数据库与API访问日志，没有补造操作身份。

前端 `frontend/src/api.ts` 默认连接 `http://localhost:8010`；运行中的8010进程工作目录属于本项目，5174为对应Vite。失败Run保存的Judge为V3、安全Guard为finite-safety-1、Parser为business-output-3-evidence-roles，Prompt SHA为`e6cdaba08a037d96b3916f041d2513306233c60d35a10fd7c0f881a0afa80c9b`。这与b540559后的合同一致，排除了本次由旧V2进程/旧Parser造成的解释。

Q01询问KIRA B 50如何修改时区。Golden参考是进入一般设置并在“设定时区”设置时区。保存的检索链为12条Candidate、12条Rerank、4条Final；Final为C00002、C00138、C00132、C00202，均属DOC-001。C00138有一般设置/时区原文，C00132有设置菜单原文。两份Judge原始响应都把设置路径判为有Final支持，同时额外将“未虚构具体选项/保存按钮、界面不符时核对版本并咨询官方”列为`met=true`、`support=[]`，触发正确事实必须有真实Final支持的Validator。故障点在Judge解析/合同校验阶段，答案生成已成功并保存在Checkpoint。

根因是Prompt允许混合输出必要事实与泛化行为审查，而Validator对Positive/Ablation的正确检查统一要求真实Final；重试又没有提供上次错误反馈。再叠加批处理将重试耗尽视为整批终止，造成0/50收口。

这是b540559后暴露的另一类合同输出问题，并非Q04旧故障复发。b540559处理的是遗漏项的候选规范证据与Final支持角色混用；本次是肯定项无Final支持。旧Q04两份真实响应仍通过离线FAIL/Ranking回归。

## 2. 通用修改

- `evaluation_contract.py`：Judge升级`judge-vnext-4-output-contract`，明确必要事实/适用性检查和非必要行为审查的输出边界。后者写reason，不能替代必要事实、安全前提或引入无Final支持的正确事实。必要Final实际不足时，Judge应明确met=false/FAIL。未增加题号、措辞正则或Parser豁免。
- `providers.py`：保留原始回包及Usage，增加结构化合同错误诊断。
- `evaluation.py`：在既有重试额度内把上次非法输出/错误提供给Judge；每阶段最多3次/600秒，结构错误最多1次纠正。已知可恢复的单题耗尽保存技术异常后继续；连续两题耗尽保守熔断。认证/配置/身份失效、Unknown请求和Stop仍终止。完整晚到响应保留供恢复复用；Case提交后的旧异常标记不会导致永久Partial。
- `main.py`：既有只读API返回实际加载的Prompt/Validator/Parser/Scorer/Batch代码指纹，避免只检查磁盘文件。合同预检失败保留已加载的原检查点。
- Baseline页面：沿用既有组件展示持久化的题目级技术异常，独立于Bad Case。未完成批次Overall为NOT_EVALUABLE、11项Gate不可评估，不能按49题形成正式50题成绩。
- 同步SPEC、CHANGELOG和README；架构节点与关系不变。没有数据库迁移、新依赖或无关UI改造。

原始非法PASS响应不会被Parser改成业务FAIL或PASS。它们仍是技术异常；框架负责有界重试、持久化和恢复。显式离线的合法Judge响应另作Fixture验证，不能冒充真实模型输出。Golden、Candidate、Rerank、Final和原始响应均保持分离。

## 3. 验证证据

- 先以原始两份Q01回包复现同一错误；修复后原输入仍被严格拒绝，但进入受控题目级技术异常，不再未经处理地终止整批。
- 后端定向274项通过，包括新增16项稳定性测试；独立审查再次运行16项通过，无未关闭阻断发现。
- 按真实冻结50题的ID/问题/20 Positive+10 Ablation+20 Negative结构，在隔离DB中注入异常：孤立Judge异常后49题完成、1题技术异常；同身份显式恢复后50题完成，成功题不重评，成功生成答案不重生成。测试答案/Judge均明确为离线模拟，没有生成正式成绩。
- 覆盖Positive/Ablation/Negative合法与非法输出、缺失/伪造/错来源/冲突证据；真实Final不足记业务FAIL；技术错误不进入业务Bad Case/Agent。覆盖一次纠正、3次网络重试、连续两题熔断、401账户错误、429 Retry-After耗尽、完整响应晚到、Unknown/Stop、进程恢复、Case提交与Checkpoint清理之间中断、旧身份预检。
- 历史200条原答案/Final只读回放保持157 PASS/43 FAIL；BL37/13、A41/9、B40/10、C39/11。它们使用显式离线Judge响应，不是本轮真实LLM成绩。
- 前端42文件/244测试通过；TypeScript与Vite生产构建通过。新增测试核对Baseline、Hard Gate、Bad Case三个标签上的技术异常分离；隔离API测试核对持久化数量、资格阻断及11项NOT_EVALUABLE。
- 完成最终受控服务重载；8010实际加载代码指纹与修复源码一致，5174可访问。正式29张表逐表行数/逻辑SHA全部不变，21项索引/PDF文件不变，旧Run及全部Checkpoint、原始回包、Usage保持。重载前已用SQLite Backup API备份到`/tmp/rag-baseline-resilience-before.db`。

可重复入口：`python3 scripts/verify_self_evolution.py test_baseline_resilience`。该项目现有入口隔离DB/Corpus/环境变量并拦截外部Provider；不要直接用生产环境导入app.main运行测试。现有隔离脚本有用户原先未提交修改，本轮没有改动或提交该脚本。

## 4. 当前条件与风险

框架已具备在明确授权后新建V4 Medium50运行的条件。本轮未启动。旧0/50 Run属V3身份，检查点保留供追溯，不能混入新Prompt身份的正式运行；后续同V4身份的单题技术异常可以显式恢复。

真实LLM是否遵循V4输出约束尚未实测；离线回放只证明框架处理和证据定位，不证明模型永不漏判。Negative中是否漏列附加技术事实，仍属于同一次Judge的语义覆盖职责，Parser只严格校验已声明引用；本轮未声称新增独立语义审核。非法、伪造或未关联证据仍会保留技术异常，不能保证任意模型输出都得到业务结论。

本轮不需要追加Provider来完成代码与框架验收；真实模型遵循性验证或完整50题仍须另行授权。若先做小样本验证，应另行明确只复用保存答案/Final的Judge调用数量和当时价格/预算，再执行；本报告不将历史授权延续到新调用。

详细原始响应、保护指纹、运行版本、测试日志及200条回放结果位于仓库`backend/reports/baseline-resilience-20261020/`。
