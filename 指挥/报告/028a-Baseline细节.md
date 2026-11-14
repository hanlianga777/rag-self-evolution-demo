# 028a：Baseline 细节

## 本次修改

- “按题型答对”和 Bad Case 列表卡改为等高，三条进度条在剩余高度内均匀分布。来源：`frontend/src/ui/extra.css` 的 `.ui-blb`、`.ui-blb-cats`。
- 六题共用的诊断容器使用可收缩的单列网格，答案对比仍为两等分。修正旧规则给第二栏覆盖成 6px 顶部内边距的问题，两栏统一为 20px，正文 13px、次要信息 12px 灰色。来源：`frontend/src/pages/evaluation-workspaces.css` 的 `.bad-case-details` 和 `.case-answer-stack`。
- 耗时条下面原样采用任务单的“设计巧思”长句，占比来自保存的 `Stage.share`，缺失时才由耗时计算。当前为 95.8%，没有硬编码百分比。来源：`frontend/src/ui/baseline/BaselineHero.tsx`。
- 去掉“更多指标”折叠，检索与用量卡直接显示，标题加统一线性图标；重新评测按钮保留在该卡右下角，原预检、费用确认和取消路径保留。来源：`frontend/src/pages/EvaluationPage.tsx`、`components/ProductDiagnostics.tsx`。

## 删除和保留的文字

| 处理 | 原文或项目 | 原因 |
| --- | --- | --- |
| 删除 | 11 项 Hard Gate 全部通过，仍有 6 个 Bad Case | 与四项数字重复 |
| 删除 | 更多指标、组数标签 | 内容已直接显示 |
| 删除 | 评测信息整组：题卷、评测时间 | 任务要求删除讲解无关参数；不删除保存记录 |
| 替换 | Baseline 特意把思考档位拉到最高（Max）…… | 使用任务单指定长句 |
| 保留 | Recall@K、Precision@K、MRR、TTFT、Token 和费用的中文解释 | 说明指标口径，数字本身不能表达 |
| 保留 | Hard Gate 四组指标解释和逐项门槛 | 用来讲解独立判断依据；重复的页签摘要由 028b 统一处理 |
| 保留 | 诊断中的缺失信息、证据不足和预检阻断 | 这些内容反映真实状态，不能当作备注删除 |

## 验收证据

- 相关测试先验证新要求会失败，再修改；旧的“更多指标”和“评测信息”展示断言同步更新，保留重新评测确认、取消、预检阻断、保存数据不变、历史身份隔离和逐题诊断功能断言。来源：`output/task028a/red.txt`、`related.txt`，以及本次修改的前端测试文件。
- 六题逐一打开核对：Q04、Q06、Q24、Q27、Q29、Q38 的“实际回答”均为 347px 宽、左侧位置 1048px、20px 内边距、13px 正文。两张统计卡底边相等。来源：`output/task028a/drawers.json`、`browser.txt`、`output/task028-run/inspect_baseline.py`。
- 1440×900 截图仅存本机：`output/task028a/01-report.png` 及 `Q04.png`、`Q06.png`、`Q24.png`、`Q27.png`、`Q29.png`、`Q38.png`。Q27 已目视核对。长内容继续使用 `ClampText` 的黑底全文提示，额外截图在 `output/task028a-tooltip/tooltip.png`。
- 前端全量 113 个文件、671 项通过。来源：`output/task028a/frontend-full.txt`。
- 本单不要求报告一屏，检索与用量直接展开后由后续 028b 统一调整首屏高度；本单无全局横向滚动或脚本错误。来源：`output/task028a/browser.json`。

## 数据与运行约束

真实模型调用 0 次。没有发送问题、标注、发布、回滚，没有修改后端、正式问答或评测记录。浏览器请求仅允许本机 GET / HEAD / OPTIONS；测试数据库、空环境文件、索引及诊断路径均在临时目录内，结束自动清理，不复制正式库。沿用用户 8010 / 5174 服务，只关闭本次创建的验收浏览器。来源：`output/task028-run/browser_common.py`、`run_backend.py`、`data_check.py`。

## 最终核实

后端全量 1459 项，0 失败、0 错误、21 项跳过，跳过名称及原因与 027g2 完全一致；前端全量 671 项通过，构建通过。来源：`output/task028a/backend-full.json`、`frontend-full.txt`、`build.txt`。6 个正式接口响应哈希与本次会话开始时一致。长回答黑底悬停已验证，无脚本错误。任务已按手动模式归档并提交推送，无本单遗留项。
