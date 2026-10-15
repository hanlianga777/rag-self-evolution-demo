# RAG 自进化 Demo · 产品叙事与 UI V2 最终验收

验收日期：2026-10-15（Asia/Shanghai）。范围：Baseline、Agent 工作台、发布、问答验证，按三大业务模块组织。前序 UI 已在 `dbcbcdb` 完成；Medium50 真实运行的有限停止保持，本轮没有续跑。

## A. 修改总览

| 模块 | 本轮修改 |
|---|---|
| Baseline | 质量结论解释 Overall、群组 Hard Gate、单题失败的关系；运行摘要与测试集构成合并；Gate 失败优先；现象/根因按钮各一组，质量审计下沉 |
| Agent | 问题页只引用技术目标；策略页按真实问题连接多个保存假设、参数 Diff、收益/风险摘要；删除重复方案概览；候选保留六段内容；Sandbox 汇总真实收益及副作用；Regression 用候选按钮、前后结果与影响表；Recommendation 以保存决策先行 |
| 发布 | 发布结论→真实决策关系→当前运行配置→待发布方案→版本历史/回滚；当前配置与待发布方案真实 Diff；资格、审批与完整版本审计统一分组 |
| 问答验证 | 有边界的输入/回答区域；正文、引用与版本分层，Token 进入审计；未发布时用紧凑前置条件空态替代空双栏；Monitoring 展示实际人工反馈闭环和记录 |

## B. 产品叙事

Baseline 先说明整体门槛与单题缺陷可以并存。Agent 用问题证据连接不同优化假设，显示真正改变的参数；Sandbox 验证收益，Regression 单独追踪副作用。因此门槛通过并不自动成为合格方案。Recommendation 解释保存的资格与决策；发布只承接已具备资格的方案，由 Gate 3 人工确认。实际问答与人工确认反馈可再进入既有 Agent 流程。

当前只读页面确认为 Mini20：Overall 95.80、Hard Gate 11/11、3 个原始失败、2 个技术问题；A 已评测但不合格，B/C 未完成，暂无最终 Winner；当前为初始运行配置，无经 Candidate 晋升的新 Production。上述数值由真实记录驱动，未写死进页面。

## C. 跨页面重复清理

| 内容 | 主归属 | 删除、合并或引用方式 |
|---|---|---|
| Golden 完整构成 | Golden Dataset | Baseline 仅在评测信息显示摘要 |
| Hard Gate 完整明细 | Baseline / Hard Gate | Agent / 发布只显示保存结果 |
| Bad Case 完整分类 | Baseline / Bad Case | Agent 删除重复分类与筛选，只引用技术目标 |
| 问题→策略 | 优化 Agent | 删除独立三张实验方案概览；同题多假设在一条问题主线呈现 |
| Candidate 完整参数 | A/B/C/D 与详情 | 策略只显示最小 Diff，Sandbox 不重复参数 |
| 完整实验指标 | Sandbox | Recommendation 仅资格、核心收益、风险与决策理由 |
| 新增失败逐题追踪 | Regression | Sandbox 仅数量和结论，不复制案例 |
| 最终推荐 | Recommendation | 发布只读取 release_state，不重新判资格 |
| 历史版本 / Rollback | 发布 | 删除发布顶部 Monitoring 说明，Monitoring 不承担版本管理 |
| 实时回答比较 | 问答验证 / 方案对比 | 发布只展示配置变化及资格，不重复答案 |

## D. UI 统一

- 复用 Shared Card、根字体、深藏青/浅灰/既有淡绿状态体系，未引入组件库或字体。标题、正文、辅助文字按同级统一；正文约 1.6 行距，问题正文正常字重。
- 四目标页面表头统一浅灰、14px 正文、细分割线、按任务设置列宽；长问题默认两行。宽表在自身容器滚动，页面和 Drawer 无横向溢出。
- 有限现象、根因、候选、严重程度使用统一按钮；保留历史/大题目集合的必要选择。删除重复下拉、每类首例与恢复按钮；返回诊断页签恢复全部。
- 目标展开统一 `StoryDisclosure`：现有 lucide Chevron、旋转、完整点击区、原生键盘行为与 `aria-expanded`。展开后按字段/证据分组，JSON 只在高级审计。
- 目标 Drawer 继承 Golden 白卡分组、统一字号与间距，继续使用唯一 `--drawer-width:800px`；390px 满屏，Header/Footer 固定、Body 独立滚动，Esc 关闭并恢复焦点。
- 初始配置、已发布 Candidate、生成/待运行、运行失败、完成但不合格分开。未知字段保留未采集，不补造 0、根因、答案或资格。
- 概览/知识库/Pipeline/Golden 源码与全局 CSS 未改；正式架构逻辑与唯一图源未变，无需重新绘制或导出另一套架构。

## E. 视觉验收

[60 张截图图库](screenshots/storytelling-v2-20261015/index.html) · [布局/请求检查](screenshots/storytelling-v2-20261015/checks.json)。44 张真实只读截图（含8张冻结母版检查）与16张显式 Fixture 分开；全部覆盖 1440×1000 与390×844。Fixture 图片有固定水印，不代表真实成绩、答案或审批。

| 必验项 | 桌面 / 移动截图 |
|---|---|
| 1 Baseline报告 | [1440](screenshots/storytelling-v2-20261015/01-baseline-report-1440.jpg) / [390](screenshots/storytelling-v2-20261015/01-baseline-report-390.jpg) |
| 2 Hard Gate | [1440](screenshots/storytelling-v2-20261015/02-hard-gate-1440.jpg) / [390](screenshots/storytelling-v2-20261015/02-hard-gate-390.jpg) |
| 3 Bad Case诊断 | [1440](screenshots/storytelling-v2-20261015/03-bad-cases-1440.jpg) / [390](screenshots/storytelling-v2-20261015/03-bad-cases-390.jpg) |
| 4 Bad Case详情 | [1440](screenshots/storytelling-v2-20261015/04-bad-case-drawer-1440.jpg) / [390](screenshots/storytelling-v2-20261015/04-bad-case-drawer-390.jpg) |
| 5 Agent问题诊断 | [1440](screenshots/storytelling-v2-20261015/05-agent-diagnosis-1440.jpg) / [390](screenshots/storytelling-v2-20261015/05-agent-diagnosis-390.jpg) |
| 6 优化Agent | [1440](screenshots/storytelling-v2-20261015/06-agent-strategy-1440.jpg) / [390](screenshots/storytelling-v2-20261015/06-agent-strategy-390.jpg) |
| 7 A/B/C/D | [1440](screenshots/storytelling-v2-20261015/07-candidates-1440.jpg) / [390](screenshots/storytelling-v2-20261015/07-candidates-390.jpg) |
| 8 Candidate详情 | [1440](screenshots/storytelling-v2-20261015/08-candidate-drawer-1440.jpg) / [390](screenshots/storytelling-v2-20261015/08-candidate-drawer-390.jpg) |
| 9 Sandbox | [1440](screenshots/storytelling-v2-20261015/09-sandbox-1440.jpg) / [390](screenshots/storytelling-v2-20261015/09-sandbox-390.jpg) |
| 10 Regression | [1440](screenshots/storytelling-v2-20261015/10-regression-1440.jpg) / [390](screenshots/storytelling-v2-20261015/10-regression-390.jpg) |
| 11 Regression前后对比 | [1440](screenshots/storytelling-v2-20261015/11-regression-drawer-1440.jpg) / [390](screenshots/storytelling-v2-20261015/11-regression-drawer-390.jpg) |
| 12 Recommendation | [1440](screenshots/storytelling-v2-20261015/12-recommendation-1440.jpg) / [390](screenshots/storytelling-v2-20261015/12-recommendation-390.jpg) |
| 13 发布首页 | [1440](screenshots/storytelling-v2-20261015/13-release-1440.jpg) / [390](screenshots/storytelling-v2-20261015/13-release-390.jpg) |
| 14 版本详情 | [1440](screenshots/storytelling-v2-20261015/14-version-detail-1440.jpg) / [390](screenshots/storytelling-v2-20261015/14-version-detail-390.jpg) |
| 15 发布资格 | [1440](screenshots/storytelling-v2-20261015/15-release-eligibility-1440.jpg) / [390](screenshots/storytelling-v2-20261015/15-release-eligibility-390.jpg) |
| 16 问答验证 | [1440](screenshots/storytelling-v2-20261015/16-verification-1440.jpg) / [390](screenshots/storytelling-v2-20261015/16-verification-390.jpg) |
| 17 方案对比（未发布） | [1440](screenshots/storytelling-v2-20261015/17-comparison-unpublished-1440.jpg) / [390](screenshots/storytelling-v2-20261015/17-comparison-unpublished-390.jpg) |
| 18 Monitoring | [1440](screenshots/storytelling-v2-20261015/18-monitoring-1440.jpg) / [390](screenshots/storytelling-v2-20261015/18-monitoring-390.jpg) |
| 19 答案 / 反馈详情（隔离Fixture） | [1440](screenshots/storytelling-v2-20261015/fixture-qa-answer-drawer-1440.jpg) / [390](screenshots/storytelling-v2-20261015/fixture-qa-answer-drawer-390.jpg) |

真实 Monitoring 无问答反馈，且没有新发布 Production 或历史回滚目标，相关答案、完成态比较、反馈详情与回滚确认使用隔离 Fixture；真实 Regression 新增失败对比已在两尺寸打开。Fixture 补充图片均在图库中单独标记。

## F. 交互验收

- 真实页签全部切换；现象/根因按钮改变实际列表，复位全部后返回2条技术问题，未改变分类数据。
- 真实 Bad Case、Candidate、Regression 前后对比、版本与发布资格 Drawer 打开/关闭；高级审计展开/收起，`aria-expanded` 跟随；Esc 正常关闭。
- 当前策略关联为两个问题主线、三个已保存候选假设；未运行 B/C 不显示模拟成绩，A 不合格不出现发布按钮；未发布对比不渲染巨大空答案卡。
- 隔离 Fixture 验证候选切换、安全退化对比、问答输入/发送与答案审计、完成态同题对比、反馈详情、回滚确认后取消。所有 Fixture API 响应留在独立浏览器会话内存，无正式写入。
- 单元/组件测试覆盖历史分页、陈旧响应隔离、身份不一致阻断、0/false 保留、发布全部必要资格及独立确认、失败发布保留、Monitoring 判定→确认→绑定上下文的原请求载荷。
- 浏览器记录零页面异常、零正式非GET请求；宽表仅局部滚动，检查页面、Drawer 及内容宽度。截图已做逐页布局复核及总览检查。

## G. 工程验证

- 前端：41 个测试文件、234 项测试通过（原有230项 + 4项本轮合同检查）。
- `npx tsc -b --pretty false` 与 `npm run build` 通过；Vite 正式构建成功。
- 首轮18项失败来自旧 UI 结构断言和发布操作区按钮顺序；修正结构并更新已明确替代的合同断言后全部通过，保留原业务资格/身份/请求保护。既有 React `act(...)` 警告仍存在，无失败测试。
- 只读代码审查未发现资格/自动写入阻断问题；其发现的回答审计 Drawer 样式类遗漏已修复。
- 可复验脚本：`scripts/verify_storytelling_ui.mjs`；Fixture 源在 `scripts/fixtures/storytelling-ui.tsx.fixture`，脚本临时复制到前端、退出时删除，不进入产品构建。需要本地5174服务及已有 Playwright/Chrome；用 `RAG_PLAYWRIGHT_MODULE` 指定现有模块，不安装新依赖。

## H. 数据保护

修改前通过 SQLite Backup API 保存本轮对照。最终29张表内容摘要全部一致；已记录的21份PDF/索引资产摘要全部一致。[核对结果](screenshots/storytelling-v2-20261015/data-protection.json)。数据库备份和完整资产清单留在忽略的 `output/playwright/storytelling-v2/`，不提交真实数据库或凭据。

未修改后端源码/API、数据库结构或记录、RAG Pipeline、Golden/Probe/QC/Human Gate、Judge/Matcher/评分、11 Hard Gate、Agent真实诊断与12项Search Space、Candidate配置、Sandbox、Regression正式判断、Composite D、Recommendation资格、Production/回滚机制或Monitoring触发规则。没有重新运行Golden/Baseline/Candidate/Sandbox/正式问答，没有付费调用、自动审批/冻结/发布/回滚。页面请求处理器、资格条件与后端请求载荷保持原合同。

## I. Git交付

基准：`dbcbcdb`。实现、SPEC/Changelog、README、状态说明、验收报告及截图统一提交；具体提交及推送回执在交付后补记。本报告只说明 UI 验收，不将前序真实运行的停止改写为完成。
