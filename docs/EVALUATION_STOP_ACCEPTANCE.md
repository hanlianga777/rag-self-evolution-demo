# Baseline / Sandbox“停止运行”验收

2026-10-13，Ponytail full，最小共用链路修复，无新增依赖。

## 用户行为

右下角持久化评测窗口新增“停止运行”。点击后禁用按钮并显示停止中；后台在当前请求返回或网络超时后保留回答、评分、真实Usage及断点，再结束为Partial。退避期间每秒检查停止请求，不再发下一次请求。已发出的Provider请求不能撤回或免除费用。

停止后显示“已停止，断点已保存”、实际完成数，计时冻结。停止接口失败显示真实错误，允许重新提交，不假装已停止。窗口×仍只隐藏。手动停止的Run不会自动恢复；后续明确续跑通过既有正式Resume机制创建子Run，不重新生成已保存回答、不重复已完成题目。Sandbox中停止当前Candidate会中止串行队列，不自动启动剩余Candidate。

## 实现及数据保护

- 可信Origin保护的POST `/api/evaluations/{run_id}/stop`，重复请求幂等，已结束的历史Run不变。
- SQLite事务持久化stop_request，请求时间/原因保留；进度与结束事务读取并保留停止标记，不能被Worker旧内存覆盖。
- 存活Worker未确认前仍占用活动任务槽，不提前放开并发执行；失联Worker可保留断点结束。停止请求阻止重新领取及自动恢复。
- 共用Baseline/Sandbox执行器检查停止；不强杀共享API或独立Worker，不改变Judge/Matcher/Gate/Regression/Identity。

## 离线验收

- 相关后端47项通过（停止5项、自动恢复、Baseline Resume、Candidate Resume、Sandbox继承）；最终恢复入口增加stop_request守卫后再跑停止5项通过。
- 全部前端199项通过，生产构建通过；包括重复点击只提交一次、接口失败保留运行状态、停止后37/50及计时冻结。
- Playwright独立浏览器拦截模拟评测，验证按钮、1次停止请求、37/50保留、计时冻结；模拟写入0，不向真实停止接口发送请求。
- 首次后端回归出现既有Candidate异步结束时临时目录清理竞态；原样重跑47项全部通过，没有修改该历史测试或业务规则。
- `git diff --check`与Python编译通过。

## 当前服务与真实运行

只读发现EVAL-20261013142506137206原处于running，Q38 Judge重试。实施过程中它自行结束为Partial，37/50，错误“DeepSeek Judge 未返回有效 JSON”；Q38生成回答完整保留。本轮未停止该真实Run，也未创建/恢复评测。

确认无queued/running评测后，通过SQLite Backup API保存私有备份及29表摘要，再重载受监督API加载停止接口。OpenAPI确认接口存在，真实Run仍Partial、37个Case及Q38回答可读；加载前后29表摘要一致。备份、截图、原始运行资料位于忽略的`output/playwright/evaluation-stop/`，不进入Git。

本轮主动Provider调用0，新增费用0；既有Worker在自行结束前的调用属于原授权任务，未将其未知费用当0或改写旧费用记录。
