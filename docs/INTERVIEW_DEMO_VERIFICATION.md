# Interview Demo Product Refactor 验收

日期：2026-10-03（Asia/Shanghai）。**状态：八页重构、交互回归、四尺寸 Chromium 与数据保护验收通过；Git 交付见末节及交付消息。** 本文件记录本轮 UI 重排，不是第二份产品 SPEC；规则见 [唯一 V1.4 SPEC](RAG_SELF_EVOLUTION_SPEC.md)，演示见 [Runbook](INTERVIEW_DEMO_RUNBOOK.md)。原桌面任务书、前轮报告与其日期/测试数字保持原样。

## A. Product Refactor Summary

本轮将工程字段优先的页面重排为 20–30 分钟面试叙事：知识技术选型 → Frozen/Search Space → Golden → Baseline/Bad Case → 根因 → 受控实验 → Sandbox/Regression → 条件 D → 人工发布 → 同题问答差异 → Monitoring。

实施范围是八页展示层与全局交互。删除重复 Stepper/流程图、大 KPI、重复 A/B/C 方案卡、发布大流水线及方案对比历史评测；完整配置、审计、Case/Evidence 与高级指标进入右 Drawer。保留业务门槛、Snapshot/评测/发布身份和历史审计；唯一后端补充为既有 `GET /api/pipeline` 的 nullable 实际 FAISS `dimension/indexed_count` 只读字段。

以下 Before 来源于修改前源码与只读审计，After 已在保存的真实 GET 和明确 Fixture 交互下验证；不代表重新运行真实业务生命周期。

## B. Page-by-Page Changes

| 页面 | Before 问题 | After 结构 | 本轮浏览器状态 |
|---|---|---|---|
| RAG 自进化项目概览 | 全局闭环与工程字段混杂，页面主问题不突出 | 唯一全局闭环、当前下一步、真实 Golden/Baseline/Agent/Production 摘要；已有架构入口 | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| 知识库 | 入库流程和大 KPI 重复表达，文档表右侧空白 | 四技术策略卡、轻量 Corpus 数量、拉宽文档表、文档/Chunk/Evidence Drawer | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| Pipeline 配置 | Knowledge Preparation/Online QA 过程区与零散参数淹没调参边界 | 四类配置、Frozen/Agent 可调、轻量 Provider 状态；无新流程图 | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| Golden Dataset | 六段阶段 Stepper、巨大 Preview 与无风险空区 | 紧凑 Coverage、当前正式 Legacy Golden、仅真实风险、题表与一行候选池工具栏 | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| Baseline | 三张 KPI、顶部 Stepper 与报告字段重复 | 三 Tab、失败结论/配置摘要/Golden 与性能、Hard Gate 表、Case 详情 | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| Agent 工作台 | 顶部阶段重复、优化 Agent 重复 A/B/C、Sandbox 主表指标过密 | 动态真实根因、输入/边界/实验意图、统一 WHY/CHANGE/RESULT、独立 D、四核心指标与高级 Drawer | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| 发布 | 阶段条与 A/B/C/D 大流水线抢占主屏 | 当前实际 Production 来源与人工发布依据、仅变化参数、完整配置/其他 Candidate Drawer、版本/Rollback | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| 问答验证 | Chat 空白、历史对比与实时目的混杂、Monitoring 空信号过多 | Chat 主体；固定正式 Baseline vs active 已发布 Production 双答案；历史 UI/GET/缓存删除；轻量 Monitoring | 通过；见本轮 359 项 Chromium / 153 项前端回归 |

## C. Interaction Fixes

| 项目 | 本轮验收标准 | 结果 / 实际证据 |
|---|---|---|
| Drawer | 标准 560px / wide 800px，右侧贴边满高、移动全宽；Esc/关闭/焦点/内部滚动 | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| Select | 选项后自动关闭；外部/Esc/键盘可用；统一样式与当前值 | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| Card / Scroll | A/B/C 与双答案同高、同字段/Footer；长内容和表格内部滚动，sticky Header | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| Typography / Status | 同类字体一致；成功浅绿；缺历史值在详情解释，主屏无密集空占位 | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| Empty / Responsive | 紧凑空态；1440×900、1280×800、1024×768、390×844 无主文档横向溢出/遮挡 | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| Compare | 无任意方案 Selector/Qualified Candidate fallback；Bad Case 自动填框可编辑，真实请求前冻结双方身份，晚到响应不串台 | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| Truthful metrics | 0/false 保留；Token 与费用分开，完整 Usage + 冻结价格币种才估算；Judge 缺失不借生成模型 | 通过；见本轮 359 项 Chromium / 153 项前端回归 |

## D. Data Safety

保护基线来自根代理修改前真实只读审计，记录在本机 `output/playwright/interview-demo/before.json`；不把原始真实 JSON/DB/备份/索引纳入仓库。SQLite Backup API 备份为 `backend/data/interview-demo-before-20261003.bak`，已确认 integrity `ok`。修改后通过只读完整内容与哈希比对，额外确认 SQLite schema 与精确表数量一致。

| 保护对象 | 修改前只读事实 | 修改后比对 |
|---|---|---|
| Golden | 正式 `GD-20260927140329017939`，20 题 8/4/8，Legacy 工艺、已批准/冻结、匹配当前 Corpus | 通过；25 表完整内容及 schema 一致，8 文件 SHA-256 不变（data-proof.json） |
| Baseline | `EVAL-20260927140423956071`，9/11 Gate、7 Bad Case；Generation 6 / Safety 1 | 通过；25 表完整内容及 schema 一致，8 文件 SHA-256 不变（data-proof.json） |
| A/B/C/D | A 10/11 / 6 BC；B 7/11 / 9 BC、Regression FAIL；C 11/11 / 5 BC、Qualified；D 10/11 / 6 BC、不合格保留 C | 通过；25 表完整内容及 schema 一致，8 文件 SHA-256 不变（data-proof.json） |
| Production | `production-20260928080518`，来源 `EXP-20260928071127593062-R1-C`，人工 Release approved | 通过；25 表完整内容及 schema 一致，8 文件 SHA-256 不变（data-proof.json） |
| Corpus / Index | 4 文档 / 157 页 / 252 Chunks；实际 IndexFlatIP，d=512 / ntotal=252 | 通过；25 表完整内容及 schema 一致，8 文件 SHA-256 不变（data-proof.json） |
| SQLite 内容 | 25 张业务表的完整排序内容基线；备份可读、integrity ok | 通过；25 表完整内容及 schema 一致，8 文件 SHA-256 不变（data-proof.json） |
| 索引 / 原 PDF | 8 个文件 SHA-256 基线；不重建、写入或激活新 bundle | 通过；25 表完整内容及 schema 一致，8 文件 SHA-256 不变（data-proof.json） |
| 真实调用 / 操作 | 本轮授权仅真实只读 GET、隔离/Stub UI；禁止真实 Provider/Golden/Baseline/A/B/C/D/Gate/发布重跑 | 通过；135 个捕获 GET，24 个明确 Fixture POST 均本地履行，送往真实后端的写请求为 0 |

真实已保存业务成绩与本轮 Stub/只读验收分别记录。旧 Usage/Timing/价格依据缺失不回填；当前价格配置 USD 不自行换汇。`baseline-v1` 为初始配置，不是当前人工已发布 Production。详细对象身份见 [Current Demo Truth](CURRENT_DEMO_TRUTH.md)。

恢复边界：如修改后比对出现差异，先停验收并保留差异证据，不覆盖旧业务记录；由用户受控停止相关服务后，从已确认可读的本轮 SQLite 备份恢复目标库，并按对应文件备份恢复索引/PDF，再重复表内容与哈希核验。本轮不自动执行恢复、业务重跑或新发布。

## E. Manual Browser Acceptance

本轮验收仅 Chromium 与受控 Stub/真实只读 GET，不通过实时问答、Agent、评测或发布消耗真实 Provider。四个尺寸为 1440×900、1280×800、1024×768、390×844。实际执行右缘/宽度/焦点陷阱与恢复/Esc/关闭按钮命中、Select 选择/Esc/外部关闭、内部滚动/sticky Header、等高卡/答案区边界、确认框打开并取消、显式 Stub QA/对比/单侧失败/Preview。报告与截图保存在本机 ignored 输出，不把私有载荷上传 GitHub。

| 页面 / Tab | 必须实际检查 | 本轮结果 / 截图或断言证据 |
|---|---|---|
| 概览 | 一级导航/H1、闭环/下一步、架构入口 | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| 知识库 | 四策略、动态数量、文档/Chunk/Evidence Drawer、表格滚动 | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| Pipeline | 四配置、Frozen/Search Space、无流程、Judge/actual FAISS 字段 | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| Golden / 候选池 | Legacy 与 Preview 分离、Profile Select、Coverage/题目/History/Import Drawer、风险隐藏 | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| Baseline 三 Tab | 无 KPI/Stepper；Hard Gate 行 Drawer、真实 Primary/Secondary、Evidence 穿透 | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| Agent 四 Tab | 无 Stepper/重复方案卡；真实根因、Search Space Drawer、等高 A/B/C、独立 D、四行 Sandbox/高级指标 | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| 发布 | 无大流水线；当前来源与差异、完整配置/其他 Candidate、版本/确认 Dialog | 通过；见本轮 359 项 Chromium / 153 项前端回归 |
| 问答验证三 Tab | Tab 顺序；Chat、固定双答案、Select/可编辑输入、单侧失败/迟到身份、Monitoring 详情 | 通过；见本轮 359 项 Chromium / 153 项前端回归 |

| 本轮命令 / 证据 | 实际结果 |
|---|---|
| 前端测试 / 构建 | `cd frontend && npm test`：153/153；`npm run build`：通过；`python3 scripts/test_v14_offline.py`：298/298，隔离 DB、外网 TCP 禁用 |
| 只读 index 字段定向验证 | `PYTHONPATH=backend ... python3 -m unittest discover -s backend/tests -p test_interview_index.py`：2/2，文件字节不变、损坏/缺失 index 返回 null |
| 四尺寸 Chromium / Stub 交互 | 通过；`output/playwright/interview-demo/browser/report.json`：Chromium 153.0.8010.12，359 checks、212 截图、0 页面/非预期控制台错误、0 未捕获请求、0 后端写请求；`output/playwright/interview-demo/data-proof.json`：25 表/8 文件一致 |
| 真实只读 GET / 修改后保护证明 | 通过；`output/playwright/interview-demo/browser/report.json`：Chromium 153.0.8010.12，359 checks、212 截图、0 页面/非预期控制台错误、0 未捕获请求、0 后端写请求；`output/playwright/interview-demo/data-proof.json`：25 表/8 文件一致 |
| 文档一致性 / `git diff --check` | 文档范围检查通过：历史 SPEC 第 19 节逐字保持、ChangeLog 仅追加、架构与当前链接有效、过时 active UI 指令关闭；最终全部 `git diff --check` 通过；两图 HTML/PNG 与修改前逐字节一致，原任务书 SHA-256 不变 |

## F. Remaining Minor Issues

已修复审查与浏览器发现的问题：概览误用最新工作 Run 的 Golden 资格、Legacy Frozen 分类缺失、单侧回答失败的区域错位、手机知识库固定首列遮挡操作、手机菜单遮挡 Drawer 关闭，以及修订成功后的误报 dirty。修订等待期间新增原因继续受保护，两个独立回归验证关闭行为。

WebKit 本机未安装，未下载/未验证。Headless PDF 正文渲染未作为通过项；已验证中文来源请求返回本地捕获 PDF、文档/Chunk/Evidence 详情，现场可用原 PDF 阅读器核对正文。真实 Provider 未重跑；历史计价依据缺失不回填。现有 :8010 后端保持原进程，本轮没有自动重启；新增只读 index 字段已在隔离新代码下验证，真实运行进程须受控重启后才提供该字段，旧接口缺失时 UI 如实显示未知。真实 active 全文 sidecar 仍未切换，沿用前轮边界。

用户主动真实验证仍是手动清单：一次正式 Baseline vs 已发布 Production 同题问答；一次 Production QA → Bad Case → Confirm → 手动首轮 Agent；一次 V2 Planner Preview。上述手动流程不计入本轮无真实调用 UI 验收，详见 [Runbook](INTERVIEW_DEMO_RUNBOOK.md)。

## G. Commit

本报告、代码、测试与同步文档属于同一提交；提交 SHA 与推送后 `origin/main` / 本地 HEAD / 工作区核对结果见交付消息，可从 GitHub 本文件的提交历史定位。提交前远端复核为 `3b74a0533adc436c28bb1b287815255fd63b9889`，采用正常提交和推送，不强推。数据库、备份、密钥、索引、原 PDF、捕获的真实 payload 与截图均不加入提交。
