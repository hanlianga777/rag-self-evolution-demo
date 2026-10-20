# Baseline V4 最终合同验收

基线84dc841；本轮真实Provider 0次，未运行50题，无架构改造。定向140项通过，独立复审23项通过；8010运行指纹已核对为最终修复版，正式表与Checkpoint保持不变。

1. Negative缺口成立，没有独立严格校验。离线Fixture证明：Negative的met=true技术事实、support=[]会被原Provider与Scorer接受。现在check_type默认fact，所有类别事实均要求真实适用Final；仅Negative显式negative_behavior纯拒答/澄清可无support，答案引用仍定位。非法/遗漏行为类型不会由空support自动补成行为。Parser版本business-output-4-negative-facts进入Identity，仍属V4。
2. 修复后定向140项通过，涵盖混合行为/事实、假来源、错产品/版本、候选不能替Final、事实缺失FAIL、非法输出技术异常、Baseline断点及历史回放Partial/Failed。旧真实JSON不改写；不兼容旧回包保持技术异常。回放出口原先仍直接汇总部分成绩，本轮已改用与Baseline共用的未完成屏蔽，不能形成有效Overall/Gate，技术异常不造业务Bad Case。
3. 程序能保证声明为事实的检查不会因Negative类别免证据，不能独立保证LLM不漏列/错分事实；因此不能把“没有Parser错误”当成真实语义验收。3题将独立审查原问题/Golden、完整回答与Final、每条必要事实和附加技术事实、行为类型、引用适用性、冲突及PASS/FAIL合理性。
4. 三题均使用冻结Golden GD-20261015135415953347的保存答案/完整Final：Q01来自失败Run EVAL-20261020145850446479；Q21与Q40来自历史Baseline EVAL-20261015171658194453。同一Golden/Corpus，不重生成、不补造Final。请求与答案/Final SHA已冻结在requests.json及manifest.json。

| 题目 | 验证目标 | 调用 |
|---|---|---|
| Q01 Positive：KIRA B 50时区设置 | 必要路径覆盖、Final真实；非必要谨慎行为不生成无据正确事实 | 1次Judge |
| Q21 Ablation：R1/R3升级与发货关系 | 升级日期、操作方式一致、随机发货/实物为准逐项Final支持 | 1次Judge |
| Q40 Negative：区域未明的路线选择 | 拒绝猜选并澄清；清洁分区/多路线附加事实拆分并定位Final | 1次Judge |

最多3次，无自动重试；首个技术/语义验收失败即停止，不追加调用或自动修Prompt。沿用配置模型deepseek-v4-flash；官方说明其按Flash价格计费，记录实际响应模型，不擅改模型配置。

参考历史3题用量（含思考token），预计合计¥0.08–0.20；3题输入按UTF-8字节数+消息开销作保守token上界80,913，输出沿现有Judge上限32,768/次，总98,304。按高峰全输入未命中¥2/百万、输出¥8/百万估算上界¥0.9483；建议授权预算¥1。实际按返回Usage结算，不将Unknown当0。

价格已只读核对[DeepSeek官方价格页](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)（2026-10-20）：空闲输入未命中¥1/百万、输出¥4/百万；高峰翻倍。估算不是实际账单。

3题按上述内容标准通过，且Prompt/Parser/Golden/Corpus/配置身份保持不变后，可直接申请完整V4 Medium50授权，不以此启动新一轮架构修改。模型未来仍可能产生非法或语义错误；沿既有受控重试、技术异常持久化和熔断处理，不保证50题必得全套业务判定。

当前状态：仅准备，尚未获得3题真实调用授权，也未获得50题授权。
