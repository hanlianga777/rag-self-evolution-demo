# 028d：Agent 工作台复核与细节

## 撤回结果逐项复核

| 项目 | 结果 | 来源 |
| --- | --- | --- |
| 概览、进化路线、Candidate 对比、回归与推荐四页签，默认概览 | 已符合，不重做结构 | `pages/EvolutionPage.tsx`、`output/task028d/01-overview.png` |
| 页签在页面标题下方，上方无统计卡、窄卡 | 已符合，不重做 | `output/task028-run/browser028d.py` 的页头 DOM 检查 |
| 进化路线无 Baseline 行或 Bad Case 诊断按钮 | 已符合 | `output/task028d/02-route.png`、浏览器断言 |
| Agent 概览为独立页签，内容默认直接展示 | 已符合，没有恢复旧折叠块或 023 三页签结构 | `ui/evolution/AgentOverview.tsx`、`01-overview.png` |
| README 的 Agent 截图 | 留给任务单指定的 029 统一重拍 | 当前任务顺序 |

已参考 027e、027f、027f2 的现有报告及对应代码。本单对撤回结果没有额外修正需求。

## 本次修改

- D “还没解决的问题”中原有三等分网格由顶部对齐改为等高拉伸；两张原因卡用纵向 flex，排名条推到底部，避免段落长短影响位置。只改 CSS，不改保存的原因或排名。来源：`frontend/src/ui/extra.css`。
- Sandbox 对比移除展开 / 收起状态和按钮，原主指标和有值的次要指标全部直接展示，保留空值行过滤和固定 colgroup。没有恢复运行状态、Candidate 合格等已删的无意义行。来源：`frontend/src/ui/pages3.tsx:CompareTable`。
- 第一组仍按“答对、新增 Bad Case、Hard Gate、安全拒答率、P50、P99”排序，其余沿用既有定义。当前保存数据还显示全部原 Bad Case 修好、指定目标修好、新增明细、其他改善、净改善和 Regression Check；“指定目标修好”有真实分母时保留，缺乏有效值的测试样例继续不显示。来源：`EvolutionPage.tsx:compareRows`、`output/task028d/details.json`。
- 更新依赖展开按钮的测试，直接核对结果、修复分母、正式阻断、Gate 与回归的区别、轮次切换、抽屉和数据不变，未删除这些功能断言。来源：本次前端测试 diff。

## 浏览器验收

- 1440×900，三张小卡宽度分别为 363.328、363.328、363.344 CSS px；高度均 212px，顶部和底部相同，两个排名条顶部均为 978.219px。来源：`output/task028d/details.json`。
- Round 1、Round 3 的 Sandbox 六列宽度逐列相同；页面直接显示 12 行有效指标，没有展开 / 收起控件。来源：同文件 `metrics`、`columnWidths`。
- 截图仅存本机：`output/task028d/01-overview.png`、`02-route.png`、`03-comparison.png`、`04-review.png`、`05-d-lower.png`、`06-sandbox.png`。D 三卡已目视核对。
- 无全局横向滚动、脚本错误或被阻止的写请求。来源：`output/task028d/browser.json`。

## 测试和数据约束

真实模型调用 0 次。只查看保存的正式实验，不运行新 Sandbox、不发送问题、不标注、不发布、不回滚；不更改 Golden、Judge、Agent 原文、门槛或正式评测记录。后端全量用临时目录、Mock 和外网连接阻断；没有复制正式数据库。浏览器已关闭，用户 5174 / 8010 服务保留。来源：`output/task028-run/run_backend.py`、`browser_common.py`。

最终核实：前端全量 114 个文件、672 项通过；后端全量 1459 项、0 失败、0 错误、21 项既有跳过，与 028c 名称和原因相同；构建通过。来源：`output/task028d/frontend-full.txt`、`backend-full.json`、`build.txt`。6 个正式接口响应哈希一致。本单已归档并提交推送，无本单遗留项。
