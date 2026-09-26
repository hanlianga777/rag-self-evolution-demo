# V1.1 Governance Acceptance Matrix

此表仅记录测试集治理。`PASS` 必须有实际执行证据；`NOT VERIFIED` 不等于通过。Fixture 与真实 Provider / Retriever 的结果分别记录，不互相替代。

## 初始审计（2026-09-26，基线 e3cd5bb）

当前库只读基线：`GGEN-20260924064832200897` 有 20 题（18 approved、1 rejected、1 needs_revision），Probe/QC 各 20 passed，正式 Snapshot 0。最新 `REV-20260925162824106154` 为未应用 `preview_ready`；较早的答案锚点失败 Run 已取消，失败审计与旧草案仍在。备份：`backend/data/demo-governance-preflight-20260926-004407.bak`，SQLite integrity_check=`ok`，180 题。后续真实库状态须重新读取，不以此记录覆盖用户操作。

| ID | 初始状态 | Test Type / Evidence | Failure Cause | Fix | Regression Result |
|---|---|---|---|---|---|
| GOV-01 | NOT VERIFIED | Unit 有原子入库测试；真实 Fresh DB 未跑 | — | 待审计 | 待验证 |
| GOV-02 | NOT VERIFIED | Run Status API/轮询存在；刷新与重启尚未实测 | — | 待审计 | 待验证 |
| GOV-03 | NOT VERIFIED | Provider 错误测试存在；Generation 中途失败路径待实测 | — | 待审计 | 待验证 |
| GOV-04 | NOT VERIFIED | Mini Profile 定义 8/4/8；真实 Fresh DB 未跑 | — | 待审计 | 待验证 |
| GOV-05 | NOT VERIFIED | `run_probe` 调用真实 retriever；隔离真实索引未跑 | — | 待审计 | 待验证 |
| GOV-06 | NOT VERIFIED | Gate 测试存在；浏览器失败原因未逐项验收 | — | 待审计 | 待验证 |
| GOV-07 | NOT VERIFIED | QC 完整 Chunk 输入代码存在；真实 Provider 未跑 | — | 待审计 | 待验证 |
| GOV-08 | NOT VERIFIED | Gate 测试存在；端到端失败状态待验收 | — | 待审计 | 待验证 |
| GOV-09 | NOT VERIFIED | 人工审批测试存在；隔离真实 API 未跑 | — | 待审计 | 待验证 |
| GOV-10 | NOT VERIFIED | 原因字段及 Revision 入口存在；真实浏览器未跑 | — | 待审计 | 待验证 |
| GOV-11 | NOT VERIFIED | 单题 Revision 测试存在；跨题数据指纹待核对 | — | 待审计 | 待验证 |
| GOV-12 | NOT VERIFIED | `source_positive_id` 路径存在；浏览器未验收 | — | 待审计 | 待验证 |
| GOV-13 | NOT VERIFIED | retain 分支存在；隔离 API 未实测 | — | 待审计 | 待验证 |
| GOV-14 | PASS | Existing DB 历史 Revision 审计：答案锚点不在 Evidence 时 Hard Validation 拦截，草案未应用 | — | 保留规则 | 待回归 |
| GOV-15 | FAIL | 当前 Draft UI 对答案锚点失败只显示通用错误与并列操作 | 无失败原因到恢复动作的路由 | 通用 Recovery CTA | 待回归 |
| GOV-16 | NOT VERIFIED | reselect 路径存在；真实检索及新材料未跑 | — | 待审计 | 待验证 |
| GOV-17 | NOT VERIFIED | Chunk 校验代码存在；非法选择未跑 API/浏览器 | — | 待审计 | 待验证 |
| GOV-18 | NOT VERIFIED | Hard Validation 路径存在；新材料成功样例未跑 | — | 待审计 | 待验证 |
| GOV-19 | NOT VERIFIED | 失败尝试审计代码存在；跨题草案安全待回归 | — | 待审计 | 待验证 |
| GOV-20 | NOT VERIFIED | SQLite 持久化及当前 Preview 存在；刷新未验收 | — | 待审计 | 待验证 |
| GOV-21 | NOT VERIFIED | Apply 重置 Probe/QC 代码存在；隔离 API 未跑 | — | 待审计 | 待验证 |
| GOV-22 | NOT VERIFIED | 应用后质量线程存在；真实 Provider 未跑 | — | 待审计 | 待验证 |
| GOV-23 | NOT VERIFIED | `resume_revision_quality` 有测试；真实中断未跑 | — | 待审计 | 待验证 |
| GOV-24 | NOT VERIFIED | Revision 按 Run/题持久化；双草案隔离未专项验证 | — | 待审计 | 待验证 |
| GOV-25 | NOT VERIFIED | 哈希守卫存在；并发 API 未专项验证 | — | 待审计 | 待验证 |
| GOV-26 | NOT VERIFIED | Modal Console jsdom 测试存在；真实浏览器全项待验收 | — | 待审计 | 待验证 |
| GOV-27 | FAIL | `operation.tsx` 对单题 Revision 显示固定 10/35/55/70/85/100% | 固定阶段映射被当作可靠百分比 | 阶段 + 耗时 | 待回归 |
| GOV-28 | NOT VERIFIED | Console portal 进入 Dialog.Content 的 jsdom 测试存在；真实浏览器待验收 | — | 待审计 | 待验证 |
| GOV-29 | NOT VERIFIED | 当前真实库 18/20；隔离 Fresh DB 尚未完成 20 Test Human Actions | — | 不操作真实库 | 待验证 |
| GOV-30 | NOT VERIFIED | Snapshot Gate 测试存在；完整隔离链路未跑 | — | 待审计 | 待验证 |
| GOV-31 | NOT VERIFIED | Snapshot JSON 存储存在；修改后不变待专项验证 | — | 待审计 | 待验证 |
| GOV-32 | NOT VERIFIED | Baseline Gate 测试存在；真实 API 未专项验证 | — | 待审计 | 待验证 |
| GOV-33 | NOT VERIFIED | Existing DB 备份已建；副本迁移与历史核对未跑 | — | 待审计 | 待验证 |
| GOV-34 | NOT VERIFIED | Fixture E2E 存在；真实 Fresh DB 生命周期未跑 | — | 待审计 | 待验证 |
| GOV-35 | FAIL | `main.py` 启动仅调用 `interrupt_revision_runs`；Generation 运行态会滞留并阻止新 Run | Generation 无启动中断转换 | 保留审计并标记中断/失败 | 待回归 |
| GOV-36 | NOT VERIFIED | Run/Preview 存 SQLite；真实浏览器关闭重开未跑 | — | 待审计 | 待验证 |
| GOV-37 | NOT VERIFIED | 所有可见控件尚未逐项做真实浏览器 Sweep | — | 待审计 | 待验证 |

初始统计：PASS 1、FAIL 3、NOT VERIFIED 33。基线自动化：Backend Unit/Integration 141 passed；Frontend jsdom 46 passed（有既有 React act 警告）。这两组通过不代表 Fixture E2E 或 Real Lifecycle 已通过。

## 最终回归（2026-09-26）

层级缩写：`B` Backend（临时 SQLite／可控 Provider），`F` Frontend Mock（Vitest），`E` Fixture Business E2E-01～05，`P` Real Provider／Retriever，`L` Real Lifecycle Fresh DB，`C` Existing DB Copy，`W` Real Browser。`✓` 表示在该层实测通过，`阻` 表示真实质量或前置条件阻断，`—` 表示该层不适用或未单独执行，不能推断为 PASS。最终 `PARTIAL` 和 `NOT VERIFIED` 均不计入全链通过。

| ID | 最终状态 | B | F | E | P | L | C | W | 根因、修复与回归证据 |
|---|---|---|---|---|---|---|---|---|---|
| GOV-01 | PASS | ✓ | — | ✓ | ✓ | ✓ | — | — | 20 Slot 验证后原子入库；Fresh Run 恰好 20 Candidate，失败事务测试无半套题。 |
| GOV-02 | PASS | ✓ | ✓ | — | ✓ | ✓ | — | ✓ | Run Status 持久化；真实生成轮询、刷新与重启后仍能读取完成态。 |
| GOV-03 | PARTIAL | ✓ | — | — | — | — | — | — | Provider/入库失败的审计和原子性有回归；本轮真实 Provider 未故意注入中途故障。 |
| GOV-04 | PASS | ✓ | — | ✓ | ✓ | ✓ | — | ✓ | 唯一真实 Mini 为 8 Positive、4 Ablation、8 Negative；隔离浏览器显示 20 题。 |
| GOV-05 | PASS | ✓ | — | — | ✓ | ✓ | — | — | Fresh DB 使用现有 4 文档、252 Chunk 索引及真实 Retriever；20 次 Probe 有持久化结果。 |
| GOV-06 | PASS | ✓ | ✓ | — | ✓ | ✓ | — | ✓ | Q13/Q18 子类不匹配、Q19 伪负向风险被拦截；真实页面显示失败状态，未冒充待审。 |
| GOV-07 | PASS | ✓ | — | — | ✓ | ✓ | — | — | QC 使用真实 Provider；17 次完成且持久化，3 次因 Probe 未通过明确跳过。 |
| GOV-08 | PASS | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | 双 Gate 审批生效；17/20 有 QC 通过，不合格题不可批准。 |
| GOV-09 | PASS | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | Q13 仅在隔离库由 Test Human Action 审批；真实用户库未新增审核事件。 |
| GOV-10 | PASS | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | 修订原因写入隔离库审核审计；真实浏览器修订表单可操作。 |
| GOV-11 | PASS | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | 单题 Q13 Revision 完成，其他题内容不变；Fixture 保证原题应用前不变。 |
| GOV-12 | PARTIAL | ✓ | ✓ | ✓ | — | — | ✓ | — | 关联题独立/主动成对及关系字段有回归；本轮真实 Provider 未跑 Ablation 修订。 |
| GOV-13 | PARTIAL | ✓ | ✓ | — | — | — | ✓ | — | retain 保留当前材料由可控 Provider 测试；真实链仅跑自动选材。 |
| GOV-14 | PASS | ✓ | ✓ | — | — | — | ✓ | ✓ | 答案锚点 Hard Validation 保留；旧失败 Run 和浏览器错误可见。 |
| GOV-15 | PASS | ✓ | ✓ | — | — | — | ✓ | ✓ | 原缺陷：失败原因未路由主恢复动作；现在依通用锚点错误与意图推荐重新选材或沿用材料，两个入口并存。 |
| GOV-16 | PARTIAL | ✓ | ✓ | — | ✓ | ✓ | — | ✓ | 自动选材 Q13 使用真实 Chunk；重新选材按钮与意图表单可见，但真实重选材生成未再调用以遵守预算。 |
| GOV-17 | PASS | ✓ | ✓ | — | — | — | ✓ | ✓ | 非法 Chunk、跨产品由后端拒绝；隔离浏览器 Picker 显示真实文档与搜索结果。 |
| GOV-18 | PARTIAL | ✓ | ✓ | — | ✓ | ✓ | — | — | Q13 新材料草案通过 Hard Validation；其他选材失败路径由 Fixture 覆盖，未声称真实全覆盖。 |
| GOV-19 | PASS | ✓ | ✓ | — | — | — | ✓ | ✓ | 失败尝试保留旧草案/哈希；额外修复失败的完整手工草案不能编辑的恢复缺口。 |
| GOV-20 | PASS | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | Preview、哈希及 Run 审计在隔离服务重启和浏览器刷新后保留。 |
| GOV-21 | PASS | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | Q13 在隔离库手工应用后旧质量失效；未自动审批。 |
| GOV-22 | PASS | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | Q13 应用后真实 Probe/QC 均通过，状态转待人工复审。 |
| GOV-23 | PARTIAL | ✓ | ✓ | — | — | — | ✓ | — | 失败阶段续跑、跳过已成功 Probe 与不重复应用有可控 Provider 回归；未真实制造服务中断。 |
| GOV-24 | PASS | ✓ | ✓ | — | — | — | ✓ | — | 新增独立关联题草案不互相抹除回归；历史 Preview 保全。 |
| GOV-25 | PASS | ✓ | ✓ | — | — | — | ✓ | — | 原题/草案哈希冲突及并发拒绝有回归；失败草案编辑仍受同一哈希守卫。 |
| GOV-26 | PARTIAL | ✓ | ✓ | — | — | — | — | ✓ | 真实 Modal 中错误详情和关闭可见、背景不可点击；未将所有菜单组合视为已全面遍历。 |
| GOV-27 | PASS | — | ✓ | — | — | — | — | ✓ | 原缺陷：单题固定 10/35/55/70/85/100% 伪进度；改为真实阶段＋耗时，多题仍仅用持久化计数。 |
| GOV-28 | PASS | — | ✓ | — | — | — | — | ✓ | Console 在 Modal 内可展开与关闭；点击 × 从 DOM 移除，背景继续不可交互。 |
| GOV-29 | BLOCKED | ✓ | ✓ | ✓ | — | 阻 | — | — | Fresh DB 3 题 Probe 不通过，未进行不合法的 20/20 Test Human Approval。真实用户库仍无正式 Snapshot。 |
| GOV-30 | BLOCKED | ✓ | ✓ | ✓ | — | 阻 | — | ✓ | 真实 Snapshot 创建返回 409，证明前置 Gate 生效；成功创建仅 Fixture，不能宣称真实链通过。 |
| GOV-31 | PARTIAL | ✓ | — | ✓ | — | 阻 | ✓ | — | 不可变 Snapshot 有 Fixture 测试；Fresh DB 因上游质量阻断，无法生成真实 Snapshot。 |
| GOV-32 | PASS | ✓ | — | ✓ | — | ✓ | — | ✓ | Fresh DB Baseline POST 返回 409：未批准 Snapshot；正确前置条件未被绕过。 |
| GOV-33 | PASS | ✓ | — | — | — | — | ✓ | — | 备份副本迁移后 180 题、10 Generation Run、9 Revision、31 审核事件与核心表摘要未变。 |
| GOV-34 | BLOCKED | ✓ | ✓ | ✓ | ✓ | 阻 | ✓ | ✓ | Fixture E2E-01～05 通过；真实 Fresh 生命周期到 Q13 复验/人工测试审批，Q18/Q19 质量阻断，不能称全链 Ready。 |
| GOV-35 | PASS | ✓ | — | — | — | — | ✓ | — | 原缺陷：服务重启不收口 active Generation；启动时保留审计并标记失败/中断，手工新 Run 不被旧状态阻塞。 |
| GOV-36 | PASS | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | Run、Preview 由 SQLite 恢复；服务重启不假称原 Worker 仍存活。 |
| GOV-37 | PARTIAL | ✓ | ✓ | — | — | — | — | ✓ | 桌面/390px 巡检表格、导出、Legacy、Snapshot、Drawer、错误详情/关闭、Chunk 搜索；隔离副本实际编辑失败草案并校验、放弃草案；重新生成、重新选材和应用以受控响应确认请求路径，未触碰真实用户数据。未逐项遍历所有菜单组合。 |

全量结果：Backend 146/146、Vitest 47/47、Fixture E2E-01～05 5/5、TypeScript/生产构建和 `git diff --check` 通过。真实 Fresh Run `GGEN-20260925165201718806`：20 入库，Probe 17 通过/3 未通过，QC 17 通过/3 跳过。Q13 隔离定向 Revision 后真实 Probe/QC 通过，且仅由隔离 Test Human Action 批准；Q18 `NEGATIVE_SUBTYPE_MISMATCH`、Q19 `FAKE_NEGATIVE_RISK` 仍阻断。GOV-29～31/34 不得升级为真实全链 PASS；总体 **Governance Lifecycle Not Ready**。后续修订/人审须由操作者决策，不能以测试替代。

真实用户库验收后只读复核：仍为 18 approved、1 rejected、1 needs_revision，20/20 Probe/QC passed，0 正式 Snapshot；最新 Preview `REV-20260925162824106154` 未应用。按同一查询序列计算的当前 Run 七字段摘要及最新 Revision 原始审计摘要，均与验收前 SQLite 备份逐字节一致；备份 `integrity_check=ok`。本轮所有生成、修订、Test Human Action 与浏览器写操作仅在 `/tmp/rag-governance-live.QECZnW/` 隔离库执行。

## Final Recovery Run（2026-09-26，基线 954bc6a）

本节是后续隔离库续跑证据，不改写上方首次验收的时间点。继续使用 `fresh.db` 中原 Run `GGEN-20260925165201718806`；运行前经 SQLite Backup API 保存 `fresh-before-final-recovery.bak`（`integrity_check=ok`），未重新生成整套题。API 在导入前以 `RAG_DEMO_DB_PATH` 指向隔离库，使用真实 Corpus/Index、Retriever、DeepSeek 和 SQLite，无 Fixture Provider。隔离 Test Human 审核使用 `actor=test_human`；原 Q13 的 `local_user` 批准事件保留，并补记明确的 `test_human` 确认。

| 失败类别 | 原题与原结果 | 通用恢复证据 | 最终结果 |
|---|---|---|---|
| `NEGATIVE_SUBTYPE_MISMATCH` | Q18 `safe_rejection` 原题询问 SDK 引脚/协议；Probe 60，QC 跳过 | 单题 AI Revision `REV-20260926011659968254` 使用真实 `B2-MANUAL-CHUNK-0029` 作生成上下文；Hard Validation、应用、真实 Probe/QC 通过；负向 Golden Evidence 仍为空 | **PASS**；`NEGATIVE_VALID`，QC 95，`test_human` 批准；未改 subtype |
| `FAKE_NEGATIVE_RISK` | Q19 `insufficient_evidence` 原题问 R3 续航，Judge 由手册推得 5h；Probe 60，QC 跳过 | 单题 AI Revision `REV-20260926011831388531` 改问未在四份文档中给出的 R3 保修期；真实 Vector/Full-text/Answerability Probe 与 Provider QC 通过；负向 Golden Evidence 仍为空 | **PASS**；`NEGATIVE_VALID`，QC 94，`test_human` 批准；未改 subtype |
| 人审新发现：关联消融不一致 | Q09 `weak_keywords` 指向 Q01，却问不同知识点、给出不同答案；旧 Probe/QC 虽通过，人审未批准 | `test_human` 标记需修订。授权后单题 AI Revision `REV-20260926012207417442` 保留 Q01、同证据及同事实答案，草案未应用；Hard Validation 报“答案锚点未在所选证据原文中找到”。该答案事实分散在唯一的 `KIRA-B50-CHUNK-0177`，其 OCR 杂字符/分行使整段及按句连续匹配均失败；无第二个含全部事实的真实 Chunk。 | **BLOCKED**；原始数据属于 A（关联知识点错误），现有修订恢复阻断属于 E（连续字符串锚点校验对已批准多事实答案的假阴性）。不降低校验、不修改已批准 Q01，等待人工确认通用修复。 |

续跑终态：Mini 20/20 入库（8/4/8）；Probe 20/20 通过；QC 20/20 通过；隔离 `test_human` 批准 19/20，Q09 `needs_revision`；Snapshot 创建请求仍被 409 正确阻断，Baseline Gate 不可用。GOV-29/30/34 保持 `BLOCKED`，GOV-31 与 GOV-16/18 保持 `PARTIAL`，所以验收计数仍为 **25 PASS、9 PARTIAL、3 BLOCKED**，总体 **Governance Lifecycle Not Ready**。未使用第二轮随机重试或直接改库；Q09 的失败草案与审计保留供后续恢复。
