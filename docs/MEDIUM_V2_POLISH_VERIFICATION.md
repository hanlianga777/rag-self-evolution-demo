# Medium V2 集中质量与UI收口验收（2026-10-08）

实施基线：main/origin main `cc60b38799d997db2cda8747ae75db507b916939`，开始时工作区干净。当前Run `GGEN-20261008050011728151`，Knowledge `KNOW-20261005060656904283`，Plan `PLAN-5bc41ca6f943757baa34de61`。

## A. 50题审查与范围

全部50题先审查，再集中修订：11直接保留、21轻量改写、18实质修订。用户明确授权仅39题一轮真实Revision和必要DeepSeek/Alibaba调用；未重新生成50题，也未改11题或调用其Provider。39题保存原题/修订历史，最终仍有14题待关注；不宣称达到质量收口完成。

逐题原问/新问/原因/当前资格，以及角色、场景、意图、难度、答案、负向行为、Child/Parent/页码见[50题集中审阅](../backend/reports/medium_v2_polish_review.md)。初次生成报告和验收保留Historical标签。

## B. 真实质量

- 50/50，Positive20 / Ablation10 / Negative20；九Topic Slot数8/8/2/6/3/5/5/8/5；Gap0；Corpus/Profile/Slot/Evidence身份一致。
- Hard Validation50/50：39新内容验证，11复用仍有效结果。改题不换Evidence来消除检索失败。
- Probe45通过、5失败（Q31/Q34/Q37/Q42/Q48）；失败题跳过QC，当前QC45通过、5未执行。已执行QC：P2=43、P1=2（Q25/Q32）、P0=0；不能把未执行QC视为通过。
- 业务十维审计43/50通过，7题有失败项。机器合格36、待人工关注14、Human Approved0；Human Gate1 Pending。相对前轮机器38/关注12，本轮新内容独立检查暴露了更多真实关注项，未强制维持旧数字。
- 实际标注难度11基础/31中等/8复杂；计划目标仍10/25/15。独立Judge的难度/重复结果保留，不为比例调结果。
- 本地表达频次：师傅25→0、客户现场25→3、你帮我3→0、我在客户15→1；词面近似清单0不等于没有语义重复，Q42/Q44独立审计仍判重复。
- 本地数据集诊断只作建议，无新硬Gate/自动资格改变。高级审计差异追溯最近一次Revision（含历史）；本轮39题范围以本轮执行记录及审阅报告为准。

## C. 原12题的真实处置

| Slot | 本轮处置 | 最终结果/剩余风险 |
|---|---|---|
| Q01 | 轻量自然改写，原Evidence不变 | 机器合格 |
| Q08 | 收敛到电池负载检测，按真实任务标难度 | Probe/QC通过；仍检索不连贯，待人工关注 |
| Q10 | 收敛到铭牌电压核对 | 机器合格 |
| Q13 | 去重复背景，保留路线记录边界 | 机器合格 |
| Q18 | 限定坡度/台阶真实字段 | 检索不连贯及难度不匹配，待关注 |
| Q22 | 自然改写开关机操作问法 | 机器合格 |
| Q25 | 收敛交流电源频率/电压核对 | QC P1，待关注 |
| Q41 | 改为路线示教中缺失关闭清洁点位 | Probe/QC和业务审计通过，机器合格 |
| Q44 | 改为未知型号保养表，修正原澄清误标场景 | 原P0未复现；与Q42语义重复仍阻塞资格 |
| Q47 | 改为日志字段/故障判定信息边界 | 机器合格 |
| Q48 | 自然改写遥控失效下安全距离咨询 | 新Probe判可能可答；QC未执行，仍阻塞 |
| Q49 | 仅禁用悬崖检测危险请求，去掉混杂伪造任务 | Probe/QC和业务审计通过，机器合格 |

## D. UI与浏览器证据

- Golden删除当前主屏旧Full提示；新建测试集为次级按钮，保留确认及Provider提示；历史版本内保留审计/导出，审核主区不再有两个三点菜单。
- Candidate Pool全部/可用/待治理三Chip，真实数量408/289/119；删除质量下拉。来源/评测组/搜索/导入/创建保留，浏览五列、组建模式保留配额/Topic/选择。
- 五列候选表问题12px/400、54px行高、两行截断，与Golden列表统一；统计与筛选不改资格规则。
- 剩余动作菜单采用原生Popover：外部/Escape/选择关闭、视口约束；共享Drawer先关闭菜单再处理自身Escape，CustomSelect不改。Coverage技术审计保留普通折叠区。
- 1440×900、1280×800、1024×768：八导航、浏览/组建、800px Drawer及菜单共36项真实检查，无页面异常、Load failed或横向溢出。只读交互检查确认三质量筛选、导出、数据集审计、取消新建，无业务写请求。人工检查真实截图文字/布局。

真实截图（本地output不提交Git）：[工作集](../output/playwright/medium-v2-polish/01-workset.png)、[全部题](../output/playwright/medium-v2-polish/02-question-list.png)、[正向详情](../output/playwright/medium-v2-polish/03-positive.png)、[消融详情](../output/playwright/medium-v2-polish/04-ablation.png)、[负向详情](../output/playwright/medium-v2-polish/05-negative.png)、[候选池](../output/playwright/medium-v2-polish/06-pool-browse.png)、[组建模式](../output/playwright/medium-v2-polish/07-pool-assemble.png)、[Coverage](../output/playwright/medium-v2-polish/08-coverage.png)、[数据集审计](../output/playwright/medium-v2-polish/09-dataset-audit.png)。

## E. 数据保护

写前SQLite Backup API备份 `output/playwright/medium-v2-polish/before.db`，复制30份Corpus/PDF/Index/Manifest/关联产物并保存SHA-256。

完成后逐表旧记录比较：39题允许版本化替换，旧问题/答案/Evidence及旧Probe/QC/audit不覆盖；11题完全原样。其他Run、全部旧审计/审批、5 Snapshot、Baseline/Evaluation/Agent及2 Production旧行一致。Full100原题及用户87机器/13人工资格、GD-20261008024214127995原样保留；30文件SHA-256一致。未重建知识库或索引，未操作Legacy Corpus。

## F. 本轮Provider与工程恢复

| Provider/模型 | 已记录调用 | 成功/失败 | 已采集Token | 已测累计耗时 |
|---|---:|---|---:|---:|
| DeepSeek deepseek-v4-flash | 96 | 89 / 7 HTTP402 | 2,200,457 | 1,393,908ms |
| Alibaba text-embedding-v4 | 125 | 125 / 0 | 10,466 | 47,914ms |
| Alibaba qwen3-rerank | 39 | 39 / 0 | 83,914 | 13,346ms |

合计已记录260调用、已采集2,294,837 Token；7次402没有Usage，不算零Token。另8次业务预览身份重校验被保护机制拦截的工程尝试未完整保留调用计量，因此实际总调用/Token不能精确宣称，以上为已采集下界。耗时按调用/失败尝试累加（2并发），不是墙钟时间或账单。初次39任务因本地属性拼写错误，在Provider调用前停止，该次零外部调用；随后恢复同一Revision。7次HTTP402后暂停，用户确认恢复后仅续检未完成阶段。没有增加内容修订轮次。

修复preview/apply丢失difficulty/expected_response的根因，9个延迟草案通过同一Revision的哈希保护编辑/应用；Q41/Q44/Q47/Q49场景/意图元数据只在新内容检查开始前按同一Revision留痕对齐。Q48完成已持久化失败Probe的状态收尾，无额外调用、不强制通过。

## G. 自动化验证

最终源码全量离线后端350/350、前端170/170通过；TypeScript、Build及git diff --check通过。后端在无.env临时副本、隔离DB/Corpus/Index中运行，禁止外网。新增本地审计无副作用、只读API不调用Provider/写题、业务字段预览应用身份一致/无效输入拒绝检查。真实Provider结果独立于离线fixture，不把测试通过视为Gate Ready。

## H. 合同与架构

同步当前SPEC、SPEC_CHANGELOG、README、AGENTS、Current Demo Truth、新验收和审阅；保留初次生成审阅/验收。架构说明同步现有治理边界；关系未变，KnowledgeDiagrams.tsx唯一图源与SVG/PNG不重画、不重复导出。

## I. Git交付

仅提交本轮代码、相关测试、当前合同/说明和审阅报告；真实DB、备份、Provider凭据、日志及截图不进入Git。Commit/push及干净同步证据在最终答复。

## J. 剩余阻塞与用户下一步

Gate1仍Pending。待关注Q08/Q17/Q18/Q20/Q24/Q25/Q30/Q31/Q32/Q34/Q37/Q42/Q44/Q48；其中Q31/Q34/Q37/Q42/Q48真实Probe失败、QC未执行，不可直接用最终确认绕过。其余按详情中的证据/业务审计/检索风险做真实人工判断。

本轮一轮内容预算结束，未继续生成或全批重跑，未接受风险、冻结Medium、运行Baseline或Agent。需要先解决明确阻塞，待后端真实Ready，用户才可亲自勾选最终确认并点击“确认并冻结Golden Dataset”；冻结成功后再由用户进入Baseline启动正式评测。
