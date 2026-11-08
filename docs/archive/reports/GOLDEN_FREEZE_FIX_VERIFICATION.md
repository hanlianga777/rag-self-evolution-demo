# Golden Dataset 冻结阻塞修复验收（2026-10-08）

本轮基线：main / e1264a3，实施前fetch确认与origin/main同步、工作区干净。只修复最终冻结接口与必要状态一致性，不调用Provider、不修改题目/审核、不确认正式Gate、不运行正式Baseline/Agent。

## 根因与真实请求

实际两次 `POST /api/governance/review-batch` 均返回500，Backend Trace定位 `_review_generation_batch` 写入100题后调用另开连接的 `dataset_snapshots`，发生 `sqlite3.OperationalError: database is locked`。数据库使用DELETE journal、默认约2MB page cache；Full批次写入缓存溢写取得排他锁后，写事务被自己的读取连接阻塞，等待约5秒。

该同步冻结入口没有持久化的Operation ID；本轮以真实Run、请求路由、Backend Trace和数据库副本复现关联定位，没有虚构请求身份。

SQLite Backup API隔离副本完整复现：5.46秒失败，同一栈位置；没有新增Snapshot，写事务回滚。修复后同一副本冻结及重复提交两次合计3.57秒，返回同一个100题Snapshot，资格来源87 machine / 13 human，Corpus身份一致，Baseline所需Golden前置条件满足。此结果仅属于隔离副本，不是正式人工确认。

默认FastAPI未处理500经过外层错误处理生成，不携带CORS允许头；相同Middleware配置的隔离检查得到500 / CORS header缺失 / Internal Server Error，解释浏览器跨域Fetch的Load failed。冻结请求不是“成功但响应丢失”。失败后的日志中数据GET均200，重启后的真实浏览器Network也全部200，未发现独立的数据加载故障；冻结失败同时在页面和Operation提示显示。

## 最小修复

- 写入后Snapshot查询使用同一事务连接，Snapshot原题复用写入前已读取内容，消除跨连接自锁。原有BEGIN IMMEDIATE、事务回滚及CORPUS_LOCK保留；同一Run、同一question_ids复用原Snapshot。
- Gate Pending返回真实题目及未满足条件；冻结SQLite异常记录Trace并返回带CORS的503 JSON，可读地要求刷新核对Snapshot后重试。
- Governance共享Action增加同步Ref防止同一事件循环连续点击。成功后沿用Cache失效与持久化Snapshot刷新；已完成但刷新失败继续用单独提示，未隐藏错误。

## 正式数据库只读核验

| 检查 | 结果 |
|---|---|
| Current Run | GGEN-20261005113424921449 / completed |
| Golden Profile / Slot | Full 100/100，100个唯一Slot，Positive40 / Ablation20 / Negative40 |
| Coverage | PLAN-3d48577c2206557bf85c3bb3，100 Slot，Gap0，与Group/Topic匹配 |
| Hard Validation | 持久化passed |
| Qualification | Machine Qualified87 + Human Approved13 =100；待关注0 |
| Probe / QC | 均100已完成并通过；当前资格没有未关闭Blocking Risk |
| 人工记录 | 13题approved/local_user记录持久化；13题stage=golden，87题stage=candidate、review_status=human_review_pending。后者是机器资格，不是87个未处理异常 |
| Human Gate 1 | 后端真实计算ready，Profile及Coverage完整，当前Corpus身份一致 |
| Knowledge | KP-6cb9388a1131f837dac2 / CORPUS-c6bbb042130820be7a1a，Run与当前manifest一致 |
| Snapshot | 当前Run为0；历史4条版本记录保留，其中1 approved、1 candidate、2 legacy_unverified |
| 最终确认 | 当前100题dataset_confirmed事件0；本轮未代行确认 |
| Baseline | 当前Corpus仍缺用户冻结的新Snapshot，不能运行当前正式Baseline；Legacy结果保留 |

保护位置：忽略目录 `output/playwright/freeze-fix/`。正式数据库SQLite Backup API副本为before.db、pre-restart.db；Corpus/Index/Manifest/关联产物副本在protected。受控重启前核对8010 PID、工作目录及父级supervise_api.sh；只重启本项目API子进程。重启前后28张业务表逐行内容一致、43个受保护文件SHA-256一致，integrity_check=ok。

## 验证

- 新cache_spill回归先在旧实现失败（database is locked），修复后通过。
- 隔离测试覆盖Ready成功、Pending拒绝并返回题目原因、重复提交不重复Snapshot/确认事件、Snapshot INSERT异常时题目/人工记录/审计全部回滚、可读503/CORS、Snapshot到Baseline前置校验及跨Corpus拒绝。
- 前端冻结交互测试连续点击只产生一个POST，刷新后读取Snapshot并显示已确认。正式浏览器仅GET，确认Full100/100、40/20/40、Ready待确认，无控制台错误；截图golden-ready.png。本轮没有勾选正式确认或点击冻结。
- 全量后端338项通过（306.184秒）；使用临时源码副本、无.env、隔离数据库、Legacy离线索引fixture，测试器禁止外部TCP。Fixture不代表真实Provider验收。
- 前端169项通过，TypeScript及Vite Build通过；git diff --check通过。

## 用户下一步

刷新Golden Dataset，核对Ready，亲自勾选“我确认异常已关闭，并冻结当前Golden Dataset”，点击“确认并冻结Golden Dataset”。成功后应看到当前Run对应Snapshot；随后才具备运行当前Baseline所需的Golden前置条件。本轮不替用户执行这一步。
