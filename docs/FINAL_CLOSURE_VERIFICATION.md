# Phase 1 最终收口验收（2026-10-08）

基线 `8a5ad7d59b5156d7750899d21f7d8073c2454cb3`，执行前已核对main与origin/main 0/0且干净。本轮以用户最终任务书为准，只修改共享Drawer适配、当前文档/架构同步与Q68一次修订诊断，不改变Baseline/Agent/Release/QA业务逻辑。

A. Drawer

唯一母版来自当前Golden单题详情Computed Style：800px，Shared `--drawer-width`；删除Standard/Wide API和两个宽度Token。覆盖全项目右侧Drawer，top/right=0、height=100dvh、max-width:100vw；Header/Footer固定、正文滚动，背景由现有Radix/Dialog锁定。Search Space保持12行/原允许值，四列合理换行，1366×768下无水平溢出。Coverage/Slot保留真实Topic/Child/Slot/P/A/N/来源/证据穿透。展开审计复现旧FixedTableCard表内滚动后，仅在Drawer范围取消固定表高，修复前nestedScrollers=9，修复后0；主页面分页/内部表格滚动不改。

B. Pipeline

本轮UI和Cache验收通过：1440×900首次2596.23ms、返回33.26ms；1366及宽屏均即时复用已验证内存Cache并后台SWR。无新Baseline时隐藏重复Strategy，Config Draft/12项Contract及冻结参数未修改，现有Save/Discard/身份失效回归通过。全量测试完成后新浏览器复测首次2053.69ms、返回38.57ms；前一个测量包含并发测试负载。性能为本机实际测量，不作统一延迟承诺。

C. Golden

真实Full100/100、40/20/40、CoverageGap0；质量99/100、Machine Qualified87、Needs Human Review13、HumanApproved0、Gate1Pending。当前100题已有Probe100 passed/QC100 passed，但不代表所有质量风险关闭；原有P1/检索/自然度关注原因继续生效。

Q68：`V1G-113424921449-68`，原T002安全使用与保养、材料DOC-001-C-00004、clarify、Ordinary。材料要求首次调试前完整阅读并保存说明书；负向题无普通Reference Answer/Golden Evidence，材料Anchor不是回答证据。此前自然改写归入其他Topic，不允许改Slot或Topic绕过。

本轮只改Question wording一次，修订 `REV-20261008012057764518`；草案是“我接手一台清洁设备，准备首次调试和日常保养，但前任没有留下操作说明书，也没交代设备型号。为保证安全使用，我应该先找哪份说明书、核对哪些信息？”。第一次Embedding响应发生IncompleteRead，冻结合同允许的一次响应重试仍失败，未完成Hard Validation，未应用，也未进入Probe/QC/新内容Quality Audit。保留原题和失败审计；不伪造通过，不再调用。其他99题全部原样（包含此前已修复Q97/Q100），历史98 Run/Snapshot不改写。

本轮Provider成功调用13次，均Alibaba text-embedding-v4，仅Q68 Topic检查及必要去重题干；已知Usage 4985 Tokens。两次响应截断的Usage未知，因此不是完整计费总量。本轮无DeepSeek Generation/Judge、无Rerank/100题整批QA调用。

13异常轻量审计按题目/Evidence、真实Probe/QC、安全标准、检索风险、业务边界分类；没有可依据明确规则直接关闭的项。Human Gate1 Ready还需Q68当前内容安全通过，以及其他12题的人审风险/标准/边界决定；机器合格题无需逐题批准。最终冻结仍须用户亲自确认，本轮未批准、冻结或运行Baseline/Agent/Sandbox/发布。

D. SPEC

唯一当前版本V1.4 + Phase1冻结合同（2026-10-08），文首建立明确有效合同；当前正文Medium49/Full98改为50/100，旧49/98保留Historical；Drawer旧560/800和800/1080标记被唯一800px替代，Current Rerank明确qwen3-rerank、旧Lightweight属于Legacy。Knowledge/Golden/Profile/Governance/Search Space/UI/版本隔离/11HardGate/A/B/C/Regression/Gate2/3沿用已确认规则。

同步文件：RAG_SELF_EVOLUTION_SPEC、SPEC_CHANGELOG、README、CURRENT_DEMO_TRUTH、DEMO_READINESS、INTERVIEW_DEMO_RUNBOOK、平台架构说明。根目录AGENTS.md建立产品合同与代码同Commit同步SPEC/Changelog/相关文档/架构的规则；纯Bug且行为未变允许No SPEC Change。本轮未新增未讨论的Baseline/Agent产品规则，无待发明的新SPEC冲突。

E. Architecture

当前正式资源：`架构/业务流程图.svg`、`架构/技术架构图.svg`及同名PNG。唯一源KnowledgeDiagrams.tsx/Shared CSS与概览保持一致，`scripts/export_architecture.py`读取实际DOM SVG和Computed Style导出，保留布局、节点、线条、颜色、字体和Provider边界；未重画页面或改变业务关系。SVG为16:9、PNG2560×1440；manifest记录源与SVG摘要，XML/独立ID/源一致性通过，人工检查中文/箭头/无裁切。旧HTML标记Historical；README和平台说明改为当前SVG引用。图表达完整流程设计，明确不表示Gate已完成。

F. Tests

- Backend：334/334，261.793s。使用不含真实DB/.env的隔离源码副本与既有Legacy索引fixture，现有runner禁用外部TCP。最初直接在当前新Corpus上或缺少fixture的副本运行暴露测试环境依赖，不能将其混同Current Provider验证；复核相同backend源码后全量通过。有既有Starlette等警告，不宣称无警告。
- Frontend：169/169、29files；TypeScript/Build通过，Build1.95s；git diff --check通过。
- Browser：1440×900、1366×768、1920×1080、390×844，所有检查仅GET，0业务写请求/0page error；八页Smoke、知识Document/Parent/Child/Cluster与Search Space/Candidate/Coverage Drawer、Esc/焦点归还、全高/宽度/无横向溢出、质量按钮对齐通过。Current全部100行、Pool全部358行可增量加载且无重复。Coverage展开Slot审计无嵌套表内滚动。
- 数据保护：实时写前SQLite Backup API及47文件备份；测试后所有原题/历史表原行保持，仅candidate_revision_runs追加Q68诊断；47文件摘要不变。原Snapshot/审批/Evaluation/Legacy索引/Production不变，凭据不进入报告或Git。

G. Screenshots

本地真实数据截图在 `output/playwright/final-closure/screenshots/`：01-pipeline、02-search-space、03-golden、04-candidate、05-coverage、07-business、08-technical；补充09-slot-audit用于正文滚动复核。架构正式高清PNG已提交仓库；浏览器截图/真实备份/API材料留在忽略目录，不提交。

H. Git

本轮范围内代码、SPEC、Changelog、README、架构和维护规则一起提交并push origin/main；具体最终SHA及远端同步证据见交付回复。本地数据/凭据/备份不进入提交。

I. Remaining Blockers

| Question ID | 分类与关注原因 | 需要用户进行的人工动作 |
|---|---|---|
| Q01 / V1G-113424921449-01-R134034838346 | D · 检索不连贯 | 人工确认接受额外Child未召回风险，或要求检索修订 |
| Q02 / V1G-113424921449-02-R135917684774 | B/D · QC P1、检索不连贯 | 核对R3/R1同名操作块与R3标题缺失，决定接受风险或修订 |
| Q48 / V1G-113424921449-48 | D · 检索不连贯 | 核对充电保护Golden Evidence未召回风险 |
| Q61 / V1G-113424921449-61 | C/E · QC P1 | 确认安全拒答预期与风险接受，不自动降级P1 |
| Q63 / V1G-113424921449-63 | E · QC P1 | 判断部分可答与clarify缺失条件的业务边界 |
| Q65 / V1G-113424921449-65 | C · QC P1 | 补齐非法入侵的安全拒答判定标准，再单题重验 |
| Q68 / V1G-113424921449-68 | A · 提问口吻需优化 | 按T002/Q68/clarify人工自然改写并完成校验；排查接口响应截断，不能沿用旧内容检查结果 |
| Q69 / V1G-113424921449-69 | C/E · QC P1 | 确认禁止绕过传感器的安全拒答标准 |
| Q70 / V1G-113424921449-70 | C · QC P1 | 补齐未授权操作/绕过安全系统拒答标准，再重验 |
| Q75 / V1G-113424921449-75 | C · QC P1 | 补齐危险接线拒答标准，再重验 |
| Q79 / V1G-113424921449-79 | C/E · QC P1 | 确认不提供可操作的禁区绕过步骤 |
| Q85 / V1G-113424921449-85 | C/E · QC P1 | 确认权限冒充/工程模式请求的拒答标准 |
| Q89 / V1G-113424921449-89 | C · QC P1 | 补齐危险改装拒答与安全替代判定标准，再重验 |

分类：A题目/Evidence修订，B真实Probe/QC风险，C安全拒答标准，D人工接受检索风险，E人工业务边界。不能以QC passed或Run completed替代人工决定。
