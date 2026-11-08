# 全局视觉系统统一验收 · 2026-10-25

基于 `origin/main` 的 `3374016`；本地 5174 Vite 直接读取整改后的源码与共享 CSS。原工作区的存储审计、数据文件及 `scripts/verify_self_evolution.py` 修改不属于本次提交。

## 结果与边界

- 真实 Chrome，1440×1000 / 390×844；共 **326 个视图检查**，包括页面、全部 Tab、下拉、页头折叠区、Drawer 默认/展开/嵌套状态。浏览器异常0，正式 API 写入0，Provider0。
- 47 个前端测试文件、267 项测试通过；TypeScript + Vite 构建通过。后台刷新期间不展示冗余顶部提示、不替换当前内容；实际读取错误和重试另有自动检查。
- 正式数据目录内 10 个 SQLite/附属 WAL 文件 SHA-256 前后相同；无后端改动，无业务文字改动，未改变冻结记录、评分、策略、发布资格或交互执行链。
- 真实页面只读。缺少实际发布/问答/回滚等状态时，使用独立浏览器上下文及现有 UI Fixture 的内存数据；所有真实网络 API 请求被拦截。Fixture 问答直接返回内存响应；确认界面只打开/取消，不确认执行。
- 条件界面均有 Fixture 验收；未执行真实 Provider、人工批准、发布、回滚或正式写入，视觉验收不代表业务链路已执行。
- 当前架构节点/连线、`KnowledgeDiagrams.tsx`及图形相关CSS未变，无需另画/重导架构。

[全部截图及整改前后对照](../output/playwright/design-system-20261025/index.html) · [计算样式/浏览器检查记录](../output/playwright/design-system-20261025/checks.json) · [原母版计算样式](../output/playwright/design-system-20261025/reference-styles-before.json) · [数据校验](../output/playwright/design-system-20261025/data-integrity.json)

## 实测母版及统一层级

系统字体保留 `-apple-system, BlinkMacSystemFont, PingFang SC, Microsoft YaHei, Noto Sans CJK SC, sans-serif`。母版A实测卡片标题12px/700、正文11px、辅助10px；母版B数据表12px，表头650；采用该现有层级。

| 类型 | 统一规范 |
|---|---|
| 页面主标题 | 桌面30px/700/36px，小屏22px；#1c2738 |
| 页面副标题 | 14px/400/22.4px；#59697d |
| 一级/二级Tab | 14px，选中700，沿用底部分割与下划线；有限筛选复用Golden选中颜色/700 |
| 卡片/分组标题 | 12px/700/18px；同级共享，成功/警告保留语义色 |
| 正文 / 辅助说明 | 11px/400/1.5；辅助10px/400/#59697d |
| 数据表头 / 正文 | 12px/650与12px/400/1.5；白色表头、共享分割线/悬停色；表头8px、正文6px 8px内边距；多行内容自然增高 |
| 指标数字 | 同级20px/700，紧凑运行指标按正文11px、标签10px |
| Badge | 11px/600/1.5，4px 8px，999px圆角；原PASS/FAIL等语义保持 |
| 操作按钮 / 下拉框 | 13px，按钮700；参数分段按钮按母版11px，筛选及紧凑表格按钮沿母版12px |
| Drawer / 弹窗 | 标题14px/750，内部卡片标题12px/700、正文11px、辅助10px；全部Drawer唯一800px/100dvh，小屏100vw，正文独立滚动 |
| Card与布局 | 共享9px圆角/内边距、8px间距；页面沿现有20px 28px，小屏12px边距；数据列宽和功能性聊天区域保持原职责 |

Pipeline原Search Space表格11px与Golden数据表12px存在差异；本轮统一到Golden的12px。母版的系统字体、标题、核心Card/状态色保持，消除其内部重复字重/圆角声明，不另创视觉方向。

## 消除的冲突

- 删除App后台刷新提示的JSX节点，无新占位、状态栏或全屏Loading。
- 清除`evaluation-workspaces.css`中四页独立的30px/600页标题、18/16px分组标题、14px正文/表格、12px/500标签，以及Drawer再次放大到14/16px的覆盖。
- 参数/状态/运行指标/中文与英文策略描述复用共享文字层级；消除首列默认加粗与Agent首列底色分叉，复用Golden筛选选中态。
- 卡片内边距和圆角回到现有Card变量；删除相互对抗的Candidate问题字号、Drawer表格`!important`覆盖。未新增`!important`或CSS依赖。
- 高级审计原文统一换行；宽表在表格容器内滚动，不撑宽Drawer。共享Drawer宽度和关闭/焦点交互保持。

## 覆盖范围

- Baseline：3个Tab，11项Hard Gate详情，10道真实Bad Case及完整审计、逐题筛选、评测依据、完整配置、历史评测、独立回放和原费用授权Drawer。
- Agent：6个Tab，实验进度折叠区，全部真实A/B/C方案与目标Drawer、Search Space、Sandbox高级指标；Fixture补充历史实验、Composite D、Regression前后/双侧证据、Recommendation、方案完整审计和嵌套未变配置。
- 发布：当前版本、配置/审批来源、待发布方案/报告、资格阻断、版本详情；Fixture补充发布确认及回滚确认弹窗。发布页面当前没有一级Tab，未新造Tab。
- 问答验证：3个Tab、会话与回答、回答审计/引用证据、两侧比较和各自运行审计、运行指标、反馈记录、Trigger上下文；有数据的状态使用Fixture。
- 母版：Pipeline配置及全部下拉、Search Space；Golden当前测试集与候选池，均在两种尺寸实测。

## 逐项验收清单

每行的桌面/移动检查均包含截图和实际计算字号/字重记录；展开态进一步检查高级内容。`live`为正式页面只读，`fixture`为隔离内存界面。

| 来源 | 页面 / Tab / Drawer / 状态 | 1440px | 390px |
|---|---|---|---|
| live | settings | [通过](<../output/playwright/design-system-20261025/live-settings-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-settings-390.jpg>) |
| live | pipeline-search-space | [通过](<../output/playwright/design-system-20261025/live-pipeline-search-space-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-pipeline-search-space-390.jpg>) |
| live | pipeline-search-space-expanded | [通过](<../output/playwright/design-system-20261025/live-pipeline-search-space-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-pipeline-search-space-expanded-390.jpg>) |
| live | governance | [通过](<../output/playwright/design-system-20261025/live-governance-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-governance-390.jpg>) |
| live | governance-当前测试集 | [通过](<../output/playwright/design-system-20261025/live-governance-当前测试集-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-governance-当前测试集-390.jpg>) |
| live | governance-候选池 | [通过](<../output/playwright/design-system-20261025/live-governance-候选池-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-governance-候选池-390.jpg>) |
| live | evaluation | [通过](<../output/playwright/design-system-20261025/live-evaluation-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-evaluation-390.jpg>) |
| live | evaluation-Baseline 报告 | [通过](<../output/playwright/design-system-20261025/live-evaluation-Baseline 报告-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-evaluation-Baseline 报告-390.jpg>) |
| live | evaluation-Hard Gate | [通过](<../output/playwright/design-system-20261025/live-evaluation-Hard Gate-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-evaluation-Hard Gate-390.jpg>) |
| live | evaluation-Bad Case 诊断 | [通过](<../output/playwright/design-system-20261025/live-evaluation-Bad Case 诊断-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-evaluation-Bad Case 诊断-390.jpg>) |
| live | baseline-config | [通过](<../output/playwright/design-system-20261025/live-baseline-config-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-config-390.jpg>) |
| live | baseline-config-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-config-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-config-expanded-390.jpg>) |
| live | baseline-audit | [通过](<../output/playwright/design-system-20261025/live-baseline-audit-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-audit-390.jpg>) |
| live | baseline-audit-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-audit-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-audit-expanded-390.jpg>) |
| live | baseline-history | [通过](<../output/playwright/design-system-20261025/live-baseline-history-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-history-390.jpg>) |
| live | baseline-history-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-history-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-history-expanded-390.jpg>) |
| live | baseline-gate-0 | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-0-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-0-390.jpg>) |
| live | baseline-gate-0-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-0-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-0-expanded-390.jpg>) |
| live | baseline-gate-1 | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-1-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-1-390.jpg>) |
| live | baseline-gate-1-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-1-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-1-expanded-390.jpg>) |
| live | baseline-gate-2 | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-2-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-2-390.jpg>) |
| live | baseline-gate-2-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-2-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-2-expanded-390.jpg>) |
| live | baseline-gate-3 | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-3-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-3-390.jpg>) |
| live | baseline-gate-3-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-3-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-3-expanded-390.jpg>) |
| live | baseline-gate-4 | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-4-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-4-390.jpg>) |
| live | baseline-gate-4-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-4-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-4-expanded-390.jpg>) |
| live | baseline-gate-5 | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-5-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-5-390.jpg>) |
| live | baseline-gate-5-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-5-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-5-expanded-390.jpg>) |
| live | baseline-gate-6 | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-6-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-6-390.jpg>) |
| live | baseline-gate-6-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-6-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-6-expanded-390.jpg>) |
| live | baseline-gate-7 | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-7-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-7-390.jpg>) |
| live | baseline-gate-7-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-7-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-7-expanded-390.jpg>) |
| live | baseline-gate-8 | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-8-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-8-390.jpg>) |
| live | baseline-gate-8-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-8-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-8-expanded-390.jpg>) |
| live | baseline-gate-9 | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-9-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-9-390.jpg>) |
| live | baseline-gate-9-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-9-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-9-expanded-390.jpg>) |
| live | baseline-gate-10 | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-10-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-10-390.jpg>) |
| live | baseline-gate-10-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-10-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-gate-10-expanded-390.jpg>) |
| live | baseline-case-0 | [通过](<../output/playwright/design-system-20261025/live-baseline-case-0-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-0-390.jpg>) |
| live | baseline-case-0-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-case-0-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-0-expanded-390.jpg>) |
| live | baseline-case-1 | [通过](<../output/playwright/design-system-20261025/live-baseline-case-1-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-1-390.jpg>) |
| live | baseline-case-1-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-case-1-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-1-expanded-390.jpg>) |
| live | baseline-case-2 | [通过](<../output/playwright/design-system-20261025/live-baseline-case-2-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-2-390.jpg>) |
| live | baseline-case-2-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-case-2-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-2-expanded-390.jpg>) |
| live | baseline-case-3 | [通过](<../output/playwright/design-system-20261025/live-baseline-case-3-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-3-390.jpg>) |
| live | baseline-case-3-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-case-3-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-3-expanded-390.jpg>) |
| live | baseline-case-4 | [通过](<../output/playwright/design-system-20261025/live-baseline-case-4-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-4-390.jpg>) |
| live | baseline-case-4-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-case-4-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-4-expanded-390.jpg>) |
| live | baseline-case-5 | [通过](<../output/playwright/design-system-20261025/live-baseline-case-5-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-5-390.jpg>) |
| live | baseline-case-5-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-case-5-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-5-expanded-390.jpg>) |
| live | baseline-case-6 | [通过](<../output/playwright/design-system-20261025/live-baseline-case-6-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-6-390.jpg>) |
| live | baseline-case-6-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-case-6-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-6-expanded-390.jpg>) |
| live | baseline-case-7 | [通过](<../output/playwright/design-system-20261025/live-baseline-case-7-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-7-390.jpg>) |
| live | baseline-case-7-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-case-7-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-7-expanded-390.jpg>) |
| live | baseline-case-8 | [通过](<../output/playwright/design-system-20261025/live-baseline-case-8-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-8-390.jpg>) |
| live | baseline-case-8-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-case-8-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-8-expanded-390.jpg>) |
| live | baseline-case-9 | [通过](<../output/playwright/design-system-20261025/live-baseline-case-9-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-9-390.jpg>) |
| live | baseline-case-9-expanded | [通过](<../output/playwright/design-system-20261025/live-baseline-case-9-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-case-9-expanded-390.jpg>) |
| live | baseline-advanced | [通过](<../output/playwright/design-system-20261025/live-baseline-advanced-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-baseline-advanced-390.jpg>) |
| live | evolution | [通过](<../output/playwright/design-system-20261025/live-evolution-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-evolution-390.jpg>) |
| live | evolution-header-details-0 | [通过](<../output/playwright/design-system-20261025/live-evolution-header-details-0-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-evolution-header-details-0-390.jpg>) |
| live | evolution-问题诊断 | [通过](<../output/playwright/design-system-20261025/live-evolution-问题诊断-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-evolution-问题诊断-390.jpg>) |
| live | evolution-优化 Agent | [通过](<../output/playwright/design-system-20261025/live-evolution-优化 Agent-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-evolution-优化 Agent-390.jpg>) |
| live | evolution-A-B-C-D | [通过](<../output/playwright/design-system-20261025/live-evolution-A-B-C-D-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-evolution-A-B-C-D-390.jpg>) |
| live | evolution-Sandbox | [通过](<../output/playwright/design-system-20261025/live-evolution-Sandbox-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-evolution-Sandbox-390.jpg>) |
| live | evolution-Regression | [通过](<../output/playwright/design-system-20261025/live-evolution-Regression-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-evolution-Regression-390.jpg>) |
| live | evolution-Recommendation | [通过](<../output/playwright/design-system-20261025/live-evolution-Recommendation-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-evolution-Recommendation-390.jpg>) |
| live | agent-case-0 | [通过](<../output/playwright/design-system-20261025/live-agent-case-0-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-0-390.jpg>) |
| live | agent-case-0-expanded | [通过](<../output/playwright/design-system-20261025/live-agent-case-0-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-0-expanded-390.jpg>) |
| live | agent-case-1 | [通过](<../output/playwright/design-system-20261025/live-agent-case-1-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-1-390.jpg>) |
| live | agent-case-1-expanded | [通过](<../output/playwright/design-system-20261025/live-agent-case-1-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-1-expanded-390.jpg>) |
| live | agent-case-2 | [通过](<../output/playwright/design-system-20261025/live-agent-case-2-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-2-390.jpg>) |
| live | agent-case-2-expanded | [通过](<../output/playwright/design-system-20261025/live-agent-case-2-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-2-expanded-390.jpg>) |
| live | agent-case-3 | [通过](<../output/playwright/design-system-20261025/live-agent-case-3-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-3-390.jpg>) |
| live | agent-case-3-expanded | [通过](<../output/playwright/design-system-20261025/live-agent-case-3-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-3-expanded-390.jpg>) |
| live | agent-case-4 | [通过](<../output/playwright/design-system-20261025/live-agent-case-4-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-4-390.jpg>) |
| live | agent-case-4-expanded | [通过](<../output/playwright/design-system-20261025/live-agent-case-4-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-4-expanded-390.jpg>) |
| live | agent-case-5 | [通过](<../output/playwright/design-system-20261025/live-agent-case-5-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-5-390.jpg>) |
| live | agent-case-5-expanded | [通过](<../output/playwright/design-system-20261025/live-agent-case-5-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-5-expanded-390.jpg>) |
| live | agent-case-6 | [通过](<../output/playwright/design-system-20261025/live-agent-case-6-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-6-390.jpg>) |
| live | agent-case-6-expanded | [通过](<../output/playwright/design-system-20261025/live-agent-case-6-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-6-expanded-390.jpg>) |
| live | agent-case-7 | [通过](<../output/playwright/design-system-20261025/live-agent-case-7-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-7-390.jpg>) |
| live | agent-case-7-expanded | [通过](<../output/playwright/design-system-20261025/live-agent-case-7-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-7-expanded-390.jpg>) |
| live | agent-case-8 | [通过](<../output/playwright/design-system-20261025/live-agent-case-8-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-8-390.jpg>) |
| live | agent-case-8-expanded | [通过](<../output/playwright/design-system-20261025/live-agent-case-8-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-8-expanded-390.jpg>) |
| live | agent-case-9 | [通过](<../output/playwright/design-system-20261025/live-agent-case-9-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-9-390.jpg>) |
| live | agent-case-9-expanded | [通过](<../output/playwright/design-system-20261025/live-agent-case-9-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-case-9-expanded-390.jpg>) |
| live | agent-search-space | [通过](<../output/playwright/design-system-20261025/live-agent-search-space-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-search-space-390.jpg>) |
| live | agent-search-space-expanded | [通过](<../output/playwright/design-system-20261025/live-agent-search-space-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-search-space-expanded-390.jpg>) |
| live | agent-candidate-0 | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-0-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-0-390.jpg>) |
| live | agent-candidate-0-expanded | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-0-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-0-expanded-390.jpg>) |
| live | agent-candidate-0-unchanged-config | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-0-unchanged-config-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-0-unchanged-config-390.jpg>) |
| live | agent-candidate-1 | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-1-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-1-390.jpg>) |
| live | agent-candidate-1-expanded | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-1-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-1-expanded-390.jpg>) |
| live | agent-candidate-1-unchanged-config | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-1-unchanged-config-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-1-unchanged-config-390.jpg>) |
| live | agent-candidate-2 | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-2-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-2-390.jpg>) |
| live | agent-candidate-2-expanded | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-2-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-2-expanded-390.jpg>) |
| live | agent-candidate-2-unchanged-config | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-2-unchanged-config-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-candidate-2-unchanged-config-390.jpg>) |
| live | agent-target-0 | [通过](<../output/playwright/design-system-20261025/live-agent-target-0-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-target-0-390.jpg>) |
| live | agent-target-0-expanded | [通过](<../output/playwright/design-system-20261025/live-agent-target-0-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-target-0-expanded-390.jpg>) |
| live | agent-target-1 | [通过](<../output/playwright/design-system-20261025/live-agent-target-1-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-target-1-390.jpg>) |
| live | agent-target-1-expanded | [通过](<../output/playwright/design-system-20261025/live-agent-target-1-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-target-1-expanded-390.jpg>) |
| live | agent-target-2 | [通过](<../output/playwright/design-system-20261025/live-agent-target-2-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-target-2-390.jpg>) |
| live | agent-target-2-expanded | [通过](<../output/playwright/design-system-20261025/live-agent-target-2-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-agent-target-2-expanded-390.jpg>) |
| live | sandbox-advanced | [通过](<../output/playwright/design-system-20261025/live-sandbox-advanced-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-sandbox-advanced-390.jpg>) |
| live | sandbox-advanced-expanded | [通过](<../output/playwright/design-system-20261025/live-sandbox-advanced-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-sandbox-advanced-expanded-390.jpg>) |
| live | versions | [通过](<../output/playwright/design-system-20261025/live-versions-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-versions-390.jpg>) |
| live | production-config | [通过](<../output/playwright/design-system-20261025/live-production-config-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-production-config-390.jpg>) |
| live | production-config-expanded | [通过](<../output/playwright/design-system-20261025/live-production-config-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-production-config-expanded-390.jpg>) |
| live | release-qualification | [通过](<../output/playwright/design-system-20261025/live-release-qualification-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-release-qualification-390.jpg>) |
| live | release-qualification-expanded | [通过](<../output/playwright/design-system-20261025/live-release-qualification-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-release-qualification-expanded-390.jpg>) |
| live | version-0 | [通过](<../output/playwright/design-system-20261025/live-version-0-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-version-0-390.jpg>) |
| live | version-0-expanded | [通过](<../output/playwright/design-system-20261025/live-version-0-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-version-0-expanded-390.jpg>) |
| live | version-0-unchanged-config | [通过](<../output/playwright/design-system-20261025/live-version-0-unchanged-config-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-version-0-unchanged-config-390.jpg>) |
| live | verification | [通过](<../output/playwright/design-system-20261025/live-verification-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-verification-390.jpg>) |
| live | verification-问答验证 | [通过](<../output/playwright/design-system-20261025/live-verification-问答验证-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-verification-问答验证-390.jpg>) |
| live | verification-方案对比 | [通过](<../output/playwright/design-system-20261025/live-verification-方案对比-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-verification-方案对比-390.jpg>) |
| live | verification-Monitoring | [通过](<../output/playwright/design-system-20261025/live-verification-Monitoring-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/live-verification-Monitoring-390.jpg>) |
| fixture | baseline-report | [通过](<../output/playwright/design-system-20261025/fixture-baseline-report-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-baseline-report-390.jpg>) |
| fixture | baseline-provider-authorization | [通过](<../output/playwright/design-system-20261025/fixture-baseline-provider-authorization-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-baseline-provider-authorization-390.jpg>) |
| fixture | baseline-history | [通过](<../output/playwright/design-system-20261025/fixture-baseline-history-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-baseline-history-390.jpg>) |
| fixture | baseline-history-expanded | [通过](<../output/playwright/design-system-20261025/fixture-baseline-history-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-baseline-history-expanded-390.jpg>) |
| fixture | historical-replay | [通过](<../output/playwright/design-system-20261025/fixture-historical-replay-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-historical-replay-390.jpg>) |
| fixture | agent-diagnosis | [通过](<../output/playwright/design-system-20261025/fixture-agent-diagnosis-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-agent-diagnosis-390.jpg>) |
| fixture | agent-history | [通过](<../output/playwright/design-system-20261025/fixture-agent-history-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-agent-history-390.jpg>) |
| fixture | agent-history-expanded | [通过](<../output/playwright/design-system-20261025/fixture-agent-history-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-agent-history-expanded-390.jpg>) |
| fixture | agent-history-unchanged-config | [通过](<../output/playwright/design-system-20261025/fixture-agent-history-unchanged-config-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-agent-history-unchanged-config-390.jpg>) |
| fixture | agent-plan | [通过](<../output/playwright/design-system-20261025/fixture-agent-plan-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-agent-plan-390.jpg>) |
| fixture | candidate-abcd | [通过](<../output/playwright/design-system-20261025/fixture-candidate-abcd-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-candidate-abcd-390.jpg>) |
| fixture | composite-d-report | [通过](<../output/playwright/design-system-20261025/fixture-composite-d-report-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-composite-d-report-390.jpg>) |
| fixture | composite-d-report-expanded | [通过](<../output/playwright/design-system-20261025/fixture-composite-d-report-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-composite-d-report-expanded-390.jpg>) |
| fixture | composite-d-report-unchanged-config | [通过](<../output/playwright/design-system-20261025/fixture-composite-d-report-unchanged-config-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-composite-d-report-unchanged-config-390.jpg>) |
| fixture | regression | [通过](<../output/playwright/design-system-20261025/fixture-regression-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-regression-390.jpg>) |
| fixture | regression-前后对比 | [通过](<../output/playwright/design-system-20261025/fixture-regression-前后对比-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-regression-前后对比-390.jpg>) |
| fixture | regression-前后对比-expanded | [通过](<../output/playwright/design-system-20261025/fixture-regression-前后对比-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-regression-前后对比-expanded-390.jpg>) |
| fixture | regression-Baseline证据 | [通过](<../output/playwright/design-system-20261025/fixture-regression-Baseline证据-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-regression-Baseline证据-390.jpg>) |
| fixture | regression-Baseline证据-expanded | [通过](<../output/playwright/design-system-20261025/fixture-regression-Baseline证据-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-regression-Baseline证据-expanded-390.jpg>) |
| fixture | regression-Candidate证据 | [通过](<../output/playwright/design-system-20261025/fixture-regression-Candidate证据-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-regression-Candidate证据-390.jpg>) |
| fixture | regression-Candidate证据-expanded | [通过](<../output/playwright/design-system-20261025/fixture-regression-Candidate证据-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-regression-Candidate证据-expanded-390.jpg>) |
| fixture | recommendation | [通过](<../output/playwright/design-system-20261025/fixture-recommendation-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-recommendation-390.jpg>) |
| fixture | agent-generation-authorization | [通过](<../output/playwright/design-system-20261025/fixture-agent-generation-authorization-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-agent-generation-authorization-390.jpg>) |
| fixture | sandbox-batch-authorization | [通过](<../output/playwright/design-system-20261025/fixture-sandbox-batch-authorization-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-sandbox-batch-authorization-390.jpg>) |
| fixture | sandbox-single-authorization | [通过](<../output/playwright/design-system-20261025/fixture-sandbox-single-authorization-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-sandbox-single-authorization-390.jpg>) |
| fixture | sandbox-resume-authorization | [通过](<../output/playwright/design-system-20261025/fixture-sandbox-resume-authorization-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-sandbox-resume-authorization-390.jpg>) |
| fixture | pending-release | [通过](<../output/playwright/design-system-20261025/fixture-pending-release-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-pending-release-390.jpg>) |
| fixture | pending-report | [通过](<../output/playwright/design-system-20261025/fixture-pending-report-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-pending-report-390.jpg>) |
| fixture | pending-report-expanded | [通过](<../output/playwright/design-system-20261025/fixture-pending-report-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-pending-report-expanded-390.jpg>) |
| fixture | pending-report-unchanged-config | [通过](<../output/playwright/design-system-20261025/fixture-pending-report-unchanged-config-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-pending-report-unchanged-config-390.jpg>) |
| fixture | release-confirmation | [通过](<../output/playwright/design-system-20261025/fixture-release-confirmation-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-release-confirmation-390.jpg>) |
| fixture | rollback-confirmation | [通过](<../output/playwright/design-system-20261025/fixture-rollback-confirmation-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-rollback-confirmation-390.jpg>) |
| fixture | qa-answer | [通过](<../output/playwright/design-system-20261025/fixture-qa-answer-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-qa-answer-390.jpg>) |
| fixture | qa-answer-audit | [通过](<../output/playwright/design-system-20261025/fixture-qa-answer-audit-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-qa-answer-audit-390.jpg>) |
| fixture | qa-answer-audit-expanded | [通过](<../output/playwright/design-system-20261025/fixture-qa-answer-audit-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-qa-answer-audit-expanded-390.jpg>) |
| fixture | qa-evidence | [通过](<../output/playwright/design-system-20261025/fixture-qa-evidence-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-qa-evidence-390.jpg>) |
| fixture | compare-dropdown | [通过](<../output/playwright/design-system-20261025/fixture-compare-dropdown-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-compare-dropdown-390.jpg>) |
| fixture | comparison-completed | [通过](<../output/playwright/design-system-20261025/fixture-comparison-completed-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-comparison-completed-390.jpg>) |
| fixture | comparison-evidence | [通过](<../output/playwright/design-system-20261025/fixture-comparison-evidence-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-comparison-evidence-390.jpg>) |
| fixture | comparison-evidence-expanded | [通过](<../output/playwright/design-system-20261025/fixture-comparison-evidence-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-comparison-evidence-expanded-390.jpg>) |
| fixture | monitoring | [通过](<../output/playwright/design-system-20261025/fixture-monitoring-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-monitoring-390.jpg>) |
| fixture | feedback-audit | [通过](<../output/playwright/design-system-20261025/fixture-feedback-audit-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-feedback-audit-390.jpg>) |
| fixture | feedback-audit-expanded | [通过](<../output/playwright/design-system-20261025/fixture-feedback-audit-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-feedback-audit-expanded-390.jpg>) |
| fixture | trigger-context | [通过](<../output/playwright/design-system-20261025/fixture-trigger-context-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-trigger-context-390.jpg>) |
| fixture | trigger-context-expanded | [通过](<../output/playwright/design-system-20261025/fixture-trigger-context-expanded-1440.jpg>) | [通过](<../output/playwright/design-system-20261025/fixture-trigger-context-expanded-390.jpg>) |

## 复现

在已安装Playwright的环境运行 `RAG_PLAYWRIGHT_MODULE=<Playwright的index.mjs绝对路径> node scripts/verify_visual_system.mjs`。脚本临时创建Fixture入口，结束清除；正式页面拦截非GET API及外网请求，Fixture禁止网络API。前端验证：`npm --prefix frontend test`、`npm --prefix frontend run build`。

**未验收项：无已识别且可渲染的目标Tab或Drawer遗漏。** 不在本轮范围内：真实付费执行、正式数据写入和发布/回滚执行。旧测试环境仍有既有React `act`警告，267项断言通过。
