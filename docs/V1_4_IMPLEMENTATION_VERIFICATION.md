# V1.4 实施与验收记录

输入：`RAG_SELF_EVOLUTION_CODEX_MASTER_PROMPT_20260930.md`，SHA-256 `e576e62794e7dcf1a26399a6de0b7ca2a5152d8ed2142edf0e6c6f1a6aec80bc`。规格：`docs/RAG_SELF_EVOLUTION_SPEC.md`。初始代码：`3a44f2f`，2026-09-30 实施前远端 main 与本地一致，工作区干净。

输入文件在实施前已完整读取并记录 SHA；实施中原桌面路径不再存在，Desktop/Documents 未发现移动后的同名文件。本轮没有改写或删除任务书。需求继续依据 `3a44f2f` 已冻结的唯一 SPEC 正文及离线验收编号，不以任务书内的代理指令自行扩大授权；因此不能再对原路径执行最终文件 SHA 比较。

## 数据保护与规则

- SQLite Backup API 备份：`/Users/zhanghaohan/.codex/backups/rag-v14-20260930-3a44f2f/demo-before.db`（临时原始备份 `/tmp/rag-v14-implementation-20260930/demo-before.db` 保留）；`PRAGMA integrity_check` 为 `ok`。记录全部 25 张表的行数和排序内容 SHA-256、四个既有索引文件 SHA-256，最终按同一口径比较。备份、索引和真实运行数据不提交 Git。
- 既有正式 Golden：`GD-20260927140329017939`；正式 Baseline：`EVAL-20260927140423956071`。当前实验来自这一 Baseline；Active Production：`production-20260928080518`。上述为实施前持久化身份，不能当作本轮重新验收。
- 原桌面任务书不改写；真实 Golden/评测/Agent/发布不自动执行。所有业务验收使用隔离数据库、临时 Corpus 和 Provider Stub。
- QC 边界已由用户确认：机器 QC P0 可显示风险并记录人工理由接受；确定性证据错误、Fake Negative、数量错误及执行失败不可豁免。Gate、Regression、12 次预算和 D 失败保留赢家不变。

## 阶段检查点

| 阶段 | 当前状态 | 恢复入口 |
| --- | --- | --- |
| 0 数据清点与备份 | 已完成备份完整性和实施前身份记录 | 本地 data-before.json / SQLite backup |
| 1 P0 resolver / Monitoring / Agent | 定向回归与代码复审通过；整合全量验收待最后运行 | P0-01..03 / ID-01..08（ID-08 前端待实施） |
| 2 Golden V2 / Validator / Pool | 263 项隔离后端测试与定向代码复审通过 | GV2-01..03 / P0-04 |
| 3 Probe / FullText / Usage | 阶段 284 项/复审通过；真实全文 4 PDF/157 页 Staging 兼容通过；未切 active | GV2-04..05 / COST-01 |
| 4 全部 UI | 105 项前端/构建通过，四 Important 修复复审通过 | UI-01 / 任务书 14–15 |
| 5 离线生命周期与浏览器 | 286 项后端、真实隔离 HTTP 状态流、54 ID 具名映射、Chromium 四尺寸通过 | QA-01 / ID/GV/VP/DS/CT/RL |
| 6 文档、图一致性、Git | 待最终核验 | SAFE-01 / SPEC / README |

此记录随每阶段的真实证据更新。历史文档与图验收见 `V1_4_DOCS_SYNC_VERIFICATION.md`，不能代替本次业务验收。

## Phase 1：P0 实施证据

提交 `f24371b`、`cd908d3`、`d750e92`、`c6b9a0d`。后端 current identity 共用 resolver；有效正式 Baseline、对应 Experiment 和 Production 分开解析。Confirm 原子幂等、错误前提返回可读状态且不制造上下文；生成短事务 claim，Provider 在写锁之外，A/B/C 与成功 trace 全批保存。失败、并发与过期保存不留下半套候选。

Agent 仅接受真实当前失败案例/题目或明确确认的 Monitoring 事件引用，输入携带已保存 Failed Gate、来源和预算。Monitoring-only 可以生成首轮，但事件不会成为伪造的 Golden/Baseline 失败题，不能据此声称满足 Sandbox 改善分母或发布资格。QA API 保留请求时冻结的 Production/Config/Corpus，覆盖“回答期间 Production 切换”回归。

验证：初始 240 项全量离线通过；后续小修采用覆盖测试，最终 61 项定向通过。全量验证将在所有模块整合后新运行，不把初始数量当作最终结果。ASTRA 代码审查发现并修复来源丢失、虚构目标 ID、Gate/预算输入缺失，复审三项均通过。测试默认库均为临时库，外部 TCP 被 runner 阻止。既有 Starlette/httpx 弃用提示未涉及依赖改动。

真实数据库副本 resolver 返回 `EVAL-20260927140423956071` / `EXP-20260928071127593062`，证明既有正式来源未被误判成 Sandbox。源数据库未迁移、未写入；仅 `monitoring_events.source_json` 幂等 additive migration 在临时库验证，真实服务下次手动启动时才应用。

## Phase 2：Golden V2 实施检查点

提交 `a04a30d`、`2446be7`、`4081d06`：复用既有 FAISS 向量与已安装 K-means；固定 seed 42 / n_init 10、小簇合并、稳定编号和协调最大余数配额。Preview 冻结参数、向量/Corpus 身份、Cluster、Slot、材料、历史使用与缺口；生成和 Pool 创建复查 Plan 身份，旧客户端省略 plan_id 时由服务端建立当前 Plan。Pool 使用稳定最大二分匹配，成功复制为新的待审核候选，不继承批准。

AI、Import Preview/Confirm、Pool、直接编辑、Revision 共用 Validator。当前离线全套 263 项通过（外部 TCP 禁止；临时数据库）；专项 17 项通过。初审复现并修复了无关第三节点假 Bridge、CSV Product/Version 丢失、编辑缺少候选同行去重。复审新增的关系属性范围和语义相似误拒问题也已修复：桥接链包含起始/目标属性和主体，模糊情况待复核；精确重复阻断，语义分数只作为观察与提示，未经校准不能成为排除有效题目的硬门槛。ASTRA 定向复审 Spec/Quality 均通过。

2026-10-01 只读阶段核验：真实库 25 张表排序内容 SHA-256 全部与实施前一致；本轮没有迁移或写入真实库。最终整合后再核验一次，避免把阶段状态当最终结果。

## 两图保留与重新核验

已重绘的两图保留原文件和 README 路径，均标注“V1.4 目标架构”。2026-10-01 Chromium 加载字体完成后重新渲染检查：两图均 9 个主要节点、1280×720 viewBox，中文文本无节点/画布越界，连线未经过文字，浏览器错误 0；1440/1280/390px 图源页面无横向溢出。临时渲染 PNG 与 Git 中现有 PNG 像素完全一致，尺寸 2560×1440，未修改图文件。图的目标能力与真实数据是否重新验收分开表述；最终代码职责一致性还需整合阶段核对。

## Phase 3：Probe、FullText 与遥测实施检查点

提交 `1edba16`、`cd551e0`。同次检索保留融合/候选上限后、重排前的 CandidateK 和最终 Context，保存真实向量/BM25 分数、配置、索引 Corpus 与嵌套计时，必要证据 Any/All 分层。缺历史候选 trace 不反推检索失败；合法但漏召回是 P1 能力风险，充分 Context 后错误回答保留生成诊断依据。Negative 基于原解析页而非拼接 Chunk 搜索，相关词仅是线索；解析不足、Judge 错误与无全文为 uncertain，不能默认通过。

原 Parser 页循环保留全文与页定位，manifest 纳入完整产物校验；一次请求绑定一致 bundle，激活/回滚使缓存失效。Planner 获取与 Pool/生成提交复用 Corpus 锁；Gate 1 冻结前重验身份。兼容全文工具默认 Staging，源/Chunk 差异拒绝，原 FAISS/文档/Chunk 字节不变，旧 bundle 保留恢复。工具已执行 help、隔离测试和真实 PDF 的备份 Staging 尝试；真实 active 产物尚未升级。

价格集中配置带官方来源、核对日期、模型别名、单位、版本和每次冻结快照；缓存缺失不计 0，未知模型/Usage/时间明确说明。工作日高峰窗口缺可验证的中国节假日数据时不能精确估价。非流式 TTFT 为 null，不再用 Total 代替；QA/Judge/QC/Agent 调用与成本分开。

验证：专项 21 项，全套 284 项离线通过；Python 编译、工具 help 和 diff 检查通过。复审 R1 复现“本地模型加载错误被当成空召回”并修复；真实执行失败持久化 failed Probe，阻断 QC/批准，QA 返回安全结构化 HTTP 503，不调用生成/Judge。成功零命中与失败的 null trace 分开。ASTRA Spec/Quality 复审通过。真实 PDF 兼容补充在备份副本单独验证；不调用 Provider，active 未切换。旧后端 PID 8323 仍监听 :8010、没有 reload；本轮没有停止或重启它。初次带 --activate 的自有 CLI 在 OCR 阶段停止（退出 130），核对 25 张真实表及四个 active 文件均未变，避免旧进程外切换与缓存混读。自有操作审计 FULLTEXT-20260930173606803638 标记 interrupted，其他历史审计不改。最终 Staging 结果及受控重启/激活步骤另行记录。

## 全文产物检查点与恢复边界

备份 Staging 操作 `FULLTEXT-20260930173958079953` 因 regenerated Chunk identity/content 比较失败而拒绝。只读排查发现原索引文档顺序为 DOC001/DOC002/DOC003/DOC004，文件遍历为 DOC001/DOC002/DOC004/DOC003；这只能证明顺序不同，尚不能证明解析内容全部相同。修复采用完整逐 ID 内容比较，缺失、重复或实际内容变化继续阻断，复制后的原 Chunk/FAISS 顺序与字节保持不变。该修复和新回归由 UI 整合阶段实施，最终须复审后在备份重新验证。

旧 :8010 服务 PID 8323 无 reload，本轮没有停止或重启。兼容字段迁移仅在隔离库执行；真实服务在用户手动受控重启时应用幂等新增字段。恢复时先停止对应服务，再使用 SQLite Backup API 将已验证备份恢复到原库，恢复完整 prior bundle/索引副本并核对 manifest；不在运行进程中直接复制数据库或切索引。

## 实施决策及误判代价

1. 机器 QC P0 保留明确人工理由接受，确定性错误和执行失败不可豁免，依据用户已确认边界；若分类判断错误，需修正分类并重新人审。
2. 在用户明确授权的 main 串行实施，测试另用隔离库，不增加 worktree/依赖；若需要额外分支隔离，代价是重新整理提交与检查。
3. 官方价格冻结模型别名和高峰/低峰规则，节假日依据缺失时不猜精确计费；若判断过于保守，部分成本暂不可用，补可核实日历后再采集新调用。
4. 真实确认的 Monitoring 事件可支撑 Agent 首轮，即使 Baseline 无失败题；不伪造题目或放宽资格，若该证据不应适用，需重新生成对应候选。
5. 高语义相似不是已验证重复，不覆盖不同实体/事实范围；若判断过宽，增加人审去重成本，避免静默丢失有效覆盖。
6. 旧 :8010 进程运行时只在备份 Staging 全文，不在其锁外切 active；代价是全文 active 就绪推迟至受控重启和激活，现有 Demo 保留。

## 数据核验口径与索引基线

2026-10-02 整合阶段再次只读核验：25 张真实表排序后完整行内容一致（含业务记录与 Frozen JSON），四个 active 文件字节 SHA-256 不变。仅 stage helper 在自己的审计/构建目录写入操作记录，没有变更 active。最终交付前按同一口径复查；不是仅比较行数。

| 原 active 文件 | SHA-256 |
| --- | --- |
| faiss.index | `5dfc392e12a94d2c7968b08c9140eee0260006d055723ef52a27368a25c35872` |
| documents.json | `beb8a69cd66e6f9f3771aacf9828db3a08a63f8b216395b211c5445e4832a0a7` |
| manifest.json | `fec999b4647a93837d8d27b0cf1e7646e0d7a448702acb46a905e89e7923eb27` |
| chunks.json | `1198c2dd8c4788df473fc240ebef578778f8f74bc81c789c55a9be075e90082c` |

本地比较证据 `/tmp/rag-v14-implementation-20260930/data-before.json`、`data-after.json` 与 `verify_data.py`；实施前备份清单也保存在上述持久恢复目录。数据库、索引、备份和密钥不加入提交。

## SPEC、架构说明与两图需求一致性

图表达职责和流程，具体字段、54 个 Test ID 与 UI 细则保留在 SPEC。两张图仍是 V1.4 目标图；不因代码提交把旧 Frozen 数据、active 全文或 Provider 标成已重新验收。以下核对为架构语义检查，不替代代码测试。

| 需求 ID | 架构说明与两图对应关系 |
| --- | --- |
| P0-01 | Current Baseline resolver / Baseline ↔ Experiment；Production 独立来源 |
| P0-02 | Monitoring → 人工判定 → Trigger Confirm → Agent 首轮；非自动生成/发布 |
| P0-03 | Release/Monitoring 共用有效测量尺，排除 Sandbox 的规则详见 SPEC |
| P0-04 | 独立 Coverage Plan → Pool Slot 匹配 → 新候选质量链 |
| GV2-01 | Golden V2 离线 Planner，复用现有向量；非在线 QA 必经步骤 |
| GV2-02 | Group × Construction 与真实材料构造，详细字段不挤入图 |
| GV2-03 | Hard Validation / Unified Validator 统一候选入口 |
| GV2-04 | 同次 Candidate Recall → Rerank/Context → Final；Any/All 细则见 SPEC |
| GV2-05 | 原 Parser 全文 → Staging 完整校验 → 原子激活；Negative 必要时 Judge |
| COST-01 | DeepSeek 调用 → Usage/Timing/价格版本；未知不是 0 |
| UI-01 | React/FastAPI 八模块、人审详情与身份边界；逐页细则见 SPEC 14–15 |
| SAFE-01 | SQLite 不可变 Snapshot/审计、一致 bundle、Production 独立来源 |
| QA-01 | Sandbox/Regression、Gate 2/3、D 失败保留赢家及人工反馈闭环 |

核对保留 11 Gate、Regression、12 次预算和 Overall 不替代资格。机器 QC P0 理由接受属于细则，架构没有把 QC 画成可替代确定性校验或人审。

## Phase 4：UI 与隔离 API 生命周期检查点（待代码复审）

隔离 FastAPI 测试实际执行 Legacy → V2 Preview → 生成 / Probe / QC → Gate 1 → Baseline → Agent A/B/C → Sandbox/Regression → Gate 2 → 条件 D 失败并保留 Winner → 测试库 Gate 3 发布 → 同题正式 Baseline/明确 Production 比较 → Production QA / 人工判定 → Trigger 幂等 Confirm → 同上下文 Round 0 首轮 A/B/C。SQLite 与 Corpus 均为测试夹具，Provider 为 Stub，不是新真实业务结果。全套后端阶段 286 项通过；最终命令及完整 ID 映射在阶段报告完成后归档。

2026-10-02 最终浏览器记录已生成：Chromium 153，1440×900、1280×800、1024×768、390×844；160 项检查、141 张截图，页面错误 0、未收集/越界请求 0。覆盖八模块 H1/hash、关键二级页、详情 Drawer 的进入/限制/恢复焦点与 Esc、Select 键盘/Enter/Esc/外侧关闭、ABC 等高、50/50 对比、指标底部及真实失败题即时填入、居中危险动作确认，以及对象切换后迟到对比响应不覆盖新身份。浏览器只渲染上述实际 API 生命周期捕获的只读响应，业务写操作由单独 HTTP 测试验证。WebKit 可执行文件不存在，未安装、未验证。

发现并修复移动端表格 Enter 默认事件导致 Drawer 立即关闭；浏览器夹具初次漏采集 export 与 evaluations 接口，已补真实 HTTP 响应，最终 blocked_requests 为空。中途错误截图不用于最终通过结论。脚本 `scripts/test_v14_browser.py` 与 `backend/tests/test_v14_api_lifecycle.py` 保留可重跑入口；运行前设置隔离环境并生成 payloads，浏览器仅允许 :5180/:8011，不接触真实 :5174/:8010。

具名断言与全部页面检查点见 [54 ID / 19 页面映射](V1_4_ACCEPTANCE_MATRIX.md)。UI/整合提交 `d14e953`；最后全量后端 286、前端 97、生产构建与 Chromium 160 检查均通过（最终范围复审中）。RL-01 明确 Overall 100 但真实失败 Gate，推荐排除、HTTP 409 且不增版本；RL-03 分别验证未跑、未确认 Gate 2、Regression FAIL 拒绝发布；RL-05 发布事务内资格变化拒绝并回滚。D 测试最终为 11/11 Gate 通过但两个新增普通 Regression 失败，仍保留 A，更直接验证 Regression 不可被 Gate/Overall 替代。

## 可重跑验证入口

- 隔离后端：`python3 scripts/test_v14_offline.py`（先设置临时默认 DB，移除 Provider 凭据，禁止外部 TCP）。
- 前端：在 `frontend` 运行 `npm test` 与 `npm run build`。
- 浏览器：先按下方命令输出实际 HTTP 夹具，再以 `VITE_API_BASE_URL=http://127.0.0.1:8011 npm run dev -- --host 127.0.0.1 --port 5180 --strictPort` 启动隔离前端，运行 `python3 scripts/test_v14_browser.py`；不需要后台监听，也不允许真实端口。

```sh
RAG_V14_BROWSER_FIXTURE_DIR=/tmp/rag-v14-implementation-20260930/browser python3 - <<'PYCODE'
import runpy, unittest
original = unittest.defaultTestLoader.discover
unittest.defaultTestLoader.discover = lambda start_dir: original(start_dir, pattern='test_v14_api_lifecycle.py')
runpy.run_path('scripts/test_v14_offline.py', run_name='__main__')
PYCODE
```

输出目录固定于本次本地临时路径，历史截图可重新生成，不把它当公开业务资产或真实数据备份。

## 三条手动真实验证（本轮未执行）

前置：确认并受控停止旧 :8010 进程后，用新代码启动服务，检查现有真实对象身份、数据库幂等迁移与索引 manifest。全文激活必须在服务停止时执行经校验的兼容补充；备份 Staging 状态不等于真实 active 已就绪。不自动运行下列付费/写业务步骤。

1. **Baseline / Production 同题问答**：在问答验证 → 方案对比，选择正式 Baseline 与当前明确的 Production Version，选一条真实失败题并手动运行。核对同一问题、两侧版本/Corpus/证据、实际 Usage/Latency、真实或未采集 TTFT，以及成本版本/缺失原因；一侧失败须保留另一侧。
2. **Monitoring → Agent 首轮**：Production 问答后人工判定一条真实 Bad Case，确认生成的 Pending Trigger；人工 Confirm 后打开同一个 pending Agent 上下文，手动生成首轮 A/B/C。核对 Round 0→1、Baseline 绑定、同一实验 ID 和重复 Confirm；此步骤可能消耗 Provider/预算，不继续自动 Sandbox 或发布。
3. **V2 Planner Preview**：Golden 顶部选择 Mini / Medium / Full Profile → 点击「预览当前 Corpus Coverage」→「当前 Corpus · V2 Coverage Preview」。Legacy / 无 Run 页面均可使用。核对 N、初始/最终 K、小簇合并、配额、Cluster、Slot/材料/章节、复用、缺口和来源；「查看 Coverage 规划」仍只显示已保存 Run 的冻结计划。切换 Profile / Corpus 后旧 Preview 清除、迟到响应丢弃；失败显示「Preview 失败」。仅手动 Preview 不调用生成/Judge/QC/Agent，不随后自动创建 Run；旧 Golden 不因 Preview 成为 V2。

## 真实全文备份 Staging 最终结果（2026-10-02）

窄范围逐 ID 顺序修复经独立代码审查后，执行 `python3 -u scripts/supplement_full_text.py --index-dir /Users/zhanghaohan/.codex/backups/rag-v14-20260930-3a44f2f/index-before`，**没有 `--activate`**。操作 `FULLTEXT-20261002062008828384` 为 `staged/completed/content_compatible:true`，退出 0；使用本地已存在 RapidOCR/BGE tokenizer 模型，禁止所有外部 TCP，不调用 Provider。

产物：`/Users/zhanghaohan/.codex/backups/rag-v14-20260930-3a44f2f/index_versions/FULLTEXT-20261002062008828384-building`。独立 `app.full_text.validate_bundle(require_full_text=True)` 再次通过：bundle schema 3，4 份文档、252 个 Chunk；全文页 schema 1、Parser `PyMuPDF+RapidOCR/page-text-v1`，157/157 页完成。解析覆盖 complete 仅表示所有页有解析产物，不保证表格/语义准确性。Staging 中 `faiss.index`、`documents.json`、`chunks.json` 与原备份逐字节完全相同；manifest 只添加全文校验/schema，Corpus fingerprint 保持一致。

这证明先前失败包含遍历顺序误报，严格去除顺序约束后真实内容兼容。**Staging 已就绪；真实 active 仍未升级**，因为旧 :8010 进程无法与外部 CLI 共用新进程锁。之后只读复核真实 25 张表完整内容与四个 active 文件 SHA 仍与实施前一致。备份可用于恢复，不自动切换或启动服务。结果日志 `fulltext-staging-final.log` 与操作审计保留本地；全文/索引/备份不提交 Git。

额外验证第一条只读命令误用了不存在的模块名 `app.corpus_bundle`，立即退出，没有通过记录；更正为实际 `app.full_text` 后成功。没有以失败命令宣称校验通过。

## 整合复审检查点

Task 4 至 `2d3bdb2` 的独立 SOL 复审发现四项 Important：资格/Gate 标签混用、旧 Production 与未完成 Baseline 的流程提示、Golden 真实风险类型数量/筛选、Monitoring 对 Trigger 上下文的 Agent 进度。统一进入同一实施代理的修复轮 1；最终证据在修复与复审通过后追加，当前不把 UI 测试通过等同于已关闭这些缺项。

阶段 Task 1–3 经 ASTRA 专项复审通过；Task 4/最终复审采用可执行的 SOL（此前 ASTRA 配额拒绝至 10 月 7 日）。既有 Starlette/httpx 弃用警告、测试 Parser 日志中的“下载/真实”夹具文字没有代表外部下载或真实结果；没有为去除既有提示增加新依赖。Drawer draft guard 与浏览器必需详情控件检查作为 Minor 留给最终审查，不静默删除发现。

Task 4 修复轮 1 提交 `5ef7f7b`：四项分别补具名断言，最终前端 17 文件/105 项、构建与 Chromium 四尺寸 187 检查/147 截图通过；错误/未收集接口/页面溢出均为 0。真实 Runner 产生的 D 在 Sandbox/报告区分别展示 Gate 11/11 PASS、Regression FAIL 和发布资格不合格；新实验等待 Gate 3 不受旧 Production 干扰。Golden 风险按持久化字段计算非零类别与同谓词筛选，Monitoring 按具体 Trigger/context 拉取与手动执行，历史 Baseline 上下文只读。逐项复审进行中，具名新增断言见验收映射。

修复轮 1 独立复审：四项 Important 全部 ADDRESSED，Spec/Quality Approved；没有新增 Critical/Important。非阻断记录保留：Draft guard 复位、浏览器必需详情按钮断言、既有依赖/夹具日志提示，以及 R1 脚本把等高 ABC 检查放到 Sandbox 后导致该断言跳过。后者没有改坏产品布局，原阶段检查与截图证明等高，但最终整体审查须处理脚本覆盖问题。没有静默抹掉发现或用重复测试替代审查。

Root 最终版本新运行：`python3 scripts/test_v14_offline.py` 286 项，55.258s，退出 0（代码此后仅 UI 修复）；前端最终 `npm test` 17 文件/105 项与 `npm run build` 均退出 0。完整日志保存在本轮 `/tmp/.../backend-final.log`、`frontend-final.log`、`build-final.log`。真实 Provider 未重跑，正式 Golden/Baseline/Candidate/Production 仍是既有结果。
