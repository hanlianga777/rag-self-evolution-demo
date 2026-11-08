# Golden新Corpus正式切换前最终隔离验证

2026-10-12；Ponytail full；仅隔离验证与最小必要修复。依据[第一阶段验收](GOLDEN_Q02_STAGE1_ACCEPTANCE.md)及[受控更新计划](superpowers/plans/2026-10-12-golden-controlled-index-update.md)。

**结论：联动提交、进程中断恢复、历史保护与启动守卫验收通过。无本轮范围内的技术阻断，可在用户下一次明确授权后进入维护窗口执行正式切换。本轮没有正式切换，Provider请求为0。**

## A. 联动事务

源版本只读核实：旧Corpus `CORPUS-c6bbb042130820be7a1a`，新Corpus `CORPUS-38c90d5628b68c76d53e`，新Medium Plan `PLAN-89801791985fdfe13f1421cf`，工作集`GGEN-20261012120721324996`。

真实新旧Bundle及真实SQLite经Backup API复制到临时目录；脚本网络连接被禁止。所有变更只发生在副本，不导入正式`app.main`，不调用重建API，不触发自动Golden生成。

成功场景验证：

- 新指针、Generation Artifact的Corpus/Plan、全部50题Plan绑定和Corpus State一致。
- 原Validator对切换后的实际副本重新校验，**Hard Validation 50/50**。
- 只更新当前工作集必要派生字段、当前Run状态及Artifact；题干、答案、Evidence内容、业务/行为合同不变，Probe/QC/Human仍Pending。
- 所有历史行逐行摘要保持，表数量与原行集合不变；旧Bundle保留独立身份，仍可按历史配置定位。

这里的联动不是SQLite与文件系统拥有共同物理原子事务，而是**维护窗口＋持久化切换记录＋SQLite事务＋原子指针＋恢复前禁止服务启动**，保证不把未完成的混合状态提供给API。

## B. 缺陷、修复与中断恢复

实际复现：原`CorpusManager.activate_bundle()`只在捕获异常时回退。子进程在新指针已切换、Golden尚未提交时直接退出（退出码73），留下新Corpus指针与旧Golden绑定。复现结果保存在`output/playwright/golden-q02-stage3-repro/result.json`；正式环境未触碰。

最小修复：

1. `scripts/q02_switch_transaction.py`复用现有Bundle切换，切换前持久化旧/新完整身份、旧路径/State和SQLite备份摘要。完成前的任何中断均恢复旧DB、旧指针、旧State；恢复可重复执行。没有正式激活CLI，也不隐式重试。
2. 共享只读`require_consistent_switch()`检查记录是否完成、完整Bundle、工作集Corpus/Plan与50题Plan绑定、State；未完成或错配则拒绝启动。
3. 启动脚本在索引检查前调用守卫，`app.main`在数据库初始化、Migration和Worker中断处理前调用同一守卫。直接导入API绕过启动脚本的问题已先复现再修复；未完成记录时DB文件都不会创建。
4. 切换记录及恢复临时文件列为本地私有产物，不进入Git。正式恢复仍须在停服/无其他写入者的维护条件下执行，不在API启动时自动回滚业务数据。

**11个实际副本场景全部通过：**

|场景|注入方式|验证结果|
|---|---|---|
|正常切换|真实指针及SQLite联动提交|新指针/Corpus/Medium Plan/50题/State一致，50/50|
|指针已换后普通中断|回调抛RuntimeError|旧指针与旧Golden完整恢复|
|数据库异常|SQLite Trigger真实RAISE(ABORT)|事务回滚，旧指针/旧绑定/旧行恢复|
|准备记录后中断|父进程SIGKILL|启动被阻止，新进程恢复旧状态|
|旧目录归档、指针尚未建立|父进程SIGKILL|缺失指针重新指回保留的旧Bundle，旧绑定恢复|
|新指针已换、DB未写|父进程SIGKILL|旧指针与旧绑定恢复|
|事务已写、DB未提交|父进程SIGKILL|SQLite未提交数据回滚，旧配对恢复|
|DB提交后中断|父进程SIGKILL|依据备份恢复旧DB与旧指针，不冒认成功|
|State写入后中断|父进程SIGKILL|旧DB、旧指针、原State恢复|
|验证已完成、完成记录未写|父进程SIGKILL|仍按未完成操作恢复旧配对|
|恢复进程再次中断|切换进程及恢复进程分别SIGKILL|再次恢复成功，旧配对一致，恢复幂等|

所有硬中断由父进程实际杀死子进程，退出码`-9`，不是仅抛Python异常。所有未完成记录都拒绝启动；恢复后或正常完成后，共享启动守卫通过。完成记录不自动重跑切换。

## C. 历史数据保护及影响

正式环境执行前后**29表所有行**摘要一致，包括当前50题和Artifact；正式指针、旧/新源Bundle、PDF与先前索引**77个文件**SHA256保持；第一阶段Provider调用账本摘要保持（仍是此前2次，本轮新增0次）。

正式记录数量保持：6个Dataset Snapshot、24个Evaluation Run、6个Experiment、16个Candidate、2个Production Version、9个Agent Trace。第一轮A/B/C仍evaluated，第二轮A/B/C仍generated，未启动任何实验。

在成功切换副本中，允许改变的仅当前50题raw派生字段、其唯一Generation Run及Artifact；其余所有旧行保持。未创建Snapshot、Baseline、ABC、审批、发布或Probe/QC结果。

历史配置定位验证：旧Baseline `EVAL-20261012024220100135`仍可按旧完整Knowledge身份找到保留Bundle；Production及归档Production配置仍定位原Legacy索引。未改Legacy绑定、不迁移Production配置、未执行实际生产回答。

**切换后的预期资格影响：**旧已批准Snapshot和旧Baseline仍绑定旧Corpus，不会自动变成新Corpus的评测尺。当前Baseline resolver会按既有规则返回“Corpus已变化，需新的Golden/Snapshot/Baseline”；旧第二轮ABC不能借新Corpus继续作为当前实验。历史成绩、状态、配置和证据保留，这不是数据丢失，也不是新评测已完成。本轮未修改该身份规则或UI。

## D. 离线回归与技术阻断

- 11个真实资产副本联动/中断场景通过，切换后50/50。
- 51项相关离线回归通过，覆盖直接API启动守卫、Q02请求守卫、Footnote、Knowledge Pipeline、既有Corpus切换和版本/质量流程；合成Fixture只证明功能，未作为Provider或Production实测结果。
- `test_startup.sh`的A–G场景及`test_launch_agent_contract.sh`通过；`git diff --check`通过。
- 有既有SQLite ResourceWarning、SWIG/joblib环境警告；首次扩大测试的import路径遗漏已用正确`PYTHONPATH=backend:backend/tests`重跑通过，不修改既有测试规则。
- **无未解决技术阻断。** 本修复范围为本轮受控Q02联动切换及启动防护，不宣称所有知识库更新入口都已具备跨资源恢复能力；正式执行须走经验证的协调器，不走会自动Generation的重建API。

## E. 是否可以正式切换

**可以在下一次明确授权后执行。当前未切换，正式仍49/50；隔离成功切换副本50/50。**

执行前必须重新核验：最新源完整身份/Bundle/Plan/50题内容、无活动任务、最新SQLite备份与旧索引保护。停止本项目API及其监督进程，确认无其他写入者；跨进程维护条件不能由单进程`CORPUS_LOCK`替代。完成后由新进程加载守卫及新指针，只读验证绑定、50/50、Pending状态与历史保护，失败则停服恢复旧配对。

本轮未停/重启正式服务，不创建正式切换记录，不改正式绑定。运行Probe/QC、批准/冻结Snapshot、Baseline/ABC、Agent及发布仍不在正式切换授权里。

## 本地证据

- 最终验证：`output/playwright/golden-q02-stage3-validated/report.json`、11个场景JSON、`protected-assets.json`和`before.db`。
- 日志：`output/playwright/golden-q02-stage3-final/validated-verification.log`、`final-regression.log`；启动测试日志在`golden-q02-stage3/`。
- 复现：`golden-q02-stage3-repro/result.json`。
- 临时变更副本由测试自行清理；保存的场景路径是审计记录，不是正式可激活版本。第一阶段新Bundle仍在原独立staging中。

架构图、Judge、Golden题目、评分/回归阈值和UI源文件未修改；SPEC与运行说明同步本次维护恢复边界。
