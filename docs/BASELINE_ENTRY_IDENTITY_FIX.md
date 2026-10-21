# Baseline入口身份修复 — 2026-10-21

目标提交9afd8cf。仅入口和定向离线验证，Provider 0次，未运行3题或50题。

确定根因：Safari实际Operation `operation-1792544590934-1uwel`，北京时间2026-10-21 09:03:10.934开始，耗时0.3秒；当前页显示“恢复Baseline”。服务access log对应POST /api/evaluations/run返回409，未新建Run。日志没有保留原请求body，不能声称已抓到其JSON；通过页面动作代码路径、最新Run及数据库副本的显式恢复复现确定冲突。原无fresh/无明确目标路径会选择最新Baseline `EVAL-20261020145850446479`，该旧Run为Partial/0业务判定，保存原生成答案与Checkpoint。

逐字段差异只有4项：

| 字段 | 旧Run | 当前 |
|---|---|---|
| prompt_version | judge-vnext-3-safety-consistency | judge-vnext-4-output-contract |
| output_parser_version | business-output-3-evidence-roles | business-output-4-negative-facts |
| judge_prompt_sha256 | e6cdaba0… | d7369e24… |
| evaluation_identity | b94f1c25… | d18aab63… |

Golden GD-20261015135415953347及完整Snapshot、Corpus指纹、完整Pipeline配置、model/temperature、embedding/vector_index、generation边界、Provider请求执行参数均一致；不是资料变化或Pipeline漂移。实际8010已加载V4/Parser4。前端旧显示状态和恢复资格判断不一致，不能仅靠版本布尔和Partial/Failed状态决定恢复。

修复：原事务校验提取为validate_evaluation_start/validate_evaluation_resume，预检和真正创建均调用，Candidate条件原样保持。预检只读，返回can_start/can_resume、明确目标ID及阻断原因；公共Corpus阻断与POST共用。POST只接受明确fresh:true或目标ID，禁止挑选其他旧Run；事务最终复核保留，竞争变化不会自动切源或偷偷变成fresh。

前端仅使用后端资格决定恢复/新版本新建，Golden/Corpus不足禁用显示原因。页面状态/聚焦刷新资格，打开费用授权弹窗前再次预检，固定用户将批准的明确payload；没有授权不POST，失败后重新读取资格。没有改Judge V4、Negative合同、Golden、11项Gate、检索、评分、或架构图。

新增离线覆盖：完全同身份可恢复且只读；Judge/Parser/完整请求参数/GoldenSnapshot/Pipeline/Evaluation Identity改变禁止恢复；缺Golden或Knowledge/Corpus不匹配禁止新建；已有活动任务及重复子Run；无body/空body/fresh:false不隐式恢复；fresh不继承旧Case/Checkpoint；真正POST与GET共享Corpus原因。前端测试实际验证授权后的JSON分别为resume_source_id和fresh:true，以及无资格禁用/未授权不POST。

最终聚焦后端49项、前端11项和TypeScript/Vite构建通过；线上只读预检及独立本地页面已核对“重新运行Baseline（新版本）”，新建授权框明确“完整真实Baseline重评”，已取消而未授权。定向验证及运行证据见同目录backend-tests.log、frontend-tests.log、build.log、verification.json；独立复审后端32项通过，原守卫逐项一致。额外45项联动断言通过，但旧Candidate异步Fixture曾在临时DB已清理后刷新recommendation产生线程噪音；未据此改无关业务。最终聚焦复测日志单独保存。

原请求body不可恢复的限制已明确；实际线上没有点击费用授权，没有执行正式新建/恢复。正式表和历史Checkpoint以重载前后逻辑指纹比对保护。可正常进入V4 Medium50的显式新建授权流程，不代表已启动或完成50题。
