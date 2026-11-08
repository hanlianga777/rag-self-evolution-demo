# 候选池与中文业务导入验收 — 2026-10-08

范围：当前 main e994814 后的候选池浏览/组建、中文业务导入；遵循 ponytail，复用 Shared UI、openpyxl、原生 Popover、现有最大 Slot 匹配及 SWR。不调用 Provider，不重建 Knowledge，不修订 Medium 内容，不冻结或执行 Baseline/Agent。

## A. 候选池 UI

默认一行全部/可用/待治理与业务用例菜单、创建Golden；来源/组别/搜索仅移除前端控件，API保留。组建显示 Profile、已选/目标/还差数与三个操作，配额/覆盖统一收进选题要求。正常问题字重、表格、Chip和250px Shared Select沿用母版。

真实浏览器检查1440×900、1366×768、1024×768：八页无页面横向溢出、Load failed或脚本异常；其他Drawer仍800px，菜单外部点击/Escape/选项关闭；组建控件无重叠。截图在本地 `output/playwright/pool-business-closure/`：`pool-{width}.png`、`two-{width}.png`、`import-{width}.png`。导入截图来自隔离副本，正式截图来自真实服务。

## B. 业务导入

下载接口默认XLSX，业务问题Sheet只有业务问题（必填）、产品/型号（选填）、业务场景（选填）、参考答案/处理经验（选填）。填写示例独立3条，说明4条；统一微软雅黑、浅灰表头、边框、列宽、换行与冻结首行，无公式/宏。

中文字段进入business_import候选：unclassified、Probe/QC待执行、Hard Validation待分类/校验；产品/场景/处理经验原样保留，reference_answer为空，Evidence为空。详情显示业务材料待核验。旧14列英文CSV/XLSX保留原字段校验。

隔离副本浏览器真实上传含4题的文件：有效2、错误2（重复与公式），预览展示具体Excel行号；仅点击“仅导入2个有效行”后创建2条待治理候选、关闭Dialog并刷新数量。错误行随回执持久化。重复确认API复用回执，新增0；部分导入未明确确认返回422，错误摘要返回422，事务中重复题导致整批回滚。正式库未写入测试业务题。

## C. 创建 Golden

选择2题显示Medium已选2/50、还差48题，创建禁用；返回浏览后选题保留。会话暂存按Corpus身份隔离，不代表质量合格，不替换冻结题。

无凭据真实Corpus/数据库隔离副本的补齐：保留2题，选出48题（18/10/20），仍4个Slot缺口、2个未匹配选题；valid=false，不能创建。缺口数量与缺题数量不相等，因为保留的已选题可能不能匹配目标Slot。无Provider调用，不宣称完整。

独立离线Fixture（4 Topic、160条材料）验证：50题20/10/20、有效证据、最大匹配及Gap0，实际HTTP创建返回201、创建50条未批准副本；Probe/QC待执行、人工待审，Snapshot不增。测试明确隔离，不能冒充真实50题已完成新的质量治理。真实工作集未另建。

## D. 数据保护与审计

SQLite Backup API备份与30个Corpus/PDF/索引/Manifest产物SHA-256保护已完成。537条题目内容、答案、Evidence和原始元数据保留；已有Probe/QC、Revision、Snapshot、Evaluation、Production等历史表记录保留，30个文件校验通过。

活跃候选314，可用216、待治理98（39待处理+59待检查）；原默认408按真实修订/复制来源谱系隐去94个旧表示，不物理删除。Revision Run129，superseded89；旧显示有81组相同题干，现仍4组来自不同来源谱系，保留历史且匹配时仍做去重。两个approved Snapshot直接引用120个唯一题目；所有5个Dataset Version保留。候选、Run、Revision、Snapshot、Evaluation及来源关系均计入引用后，无引用临时候选0。

本轮期间有7条local_user人工批准，审核事件与时间可追溯；这7条只改变stage/review_status/updated_at，不能报告为所有数据库行字节不变，也未回滚人工操作。Medium仍50题20/10/20、9 Topics：机器36、人工7、待关注7，Probe/QC45，Gate1 Pending。初始14项内容/质量未由本轮修订；关注数变化来自用户审核。

## E. 性能

本地浏览器首次列表可见327ms，返回列表33ms；只读API本次首请求675.2ms、随后160.9–164.3ms。环境/缓存影响实测值，不构成性能保证。分页每次30，滚动增量到60；筛选结果正确。列表不返回完整Evidence，详情懒加载，创建/导入失效缓存并刷新。智能补齐隔离实测8300ms，显示忙碌及真实缺口。

## F. 文档与架构

同一次提交同步当前有效SPEC、SPEC_CHANGELOG、README和本报告；保留被替代合同的历史说明。Baseline/Agent/Gate规则不重定义。业务/技术架构关系未改变，KnowledgeDiagrams.tsx及同源SVG/PNG不重画、不另生成图。

## G. 验证

- Backend全量359通过（含新增9项隔离测试）；旧并发质量测试的两个不同导入文件改用不同Fixture摘要，符合新增幂等合同，质量断言保留。
- Frontend全量170通过；TypeScript与生产Build通过；git diff --check通过。
- 浏览器24个路由/尺寸检查、三尺寸浏览/组建/Drawer、菜单、三质量筛选、30→60增量、下载、隔离上传/确认/详情通过；单行工具栏按可见按钮中心线核对，关闭菜单内不可见按钮不纳入几何判断。
- 所有Provider调用0；无新的正式人工批准、Snapshot冻结、Baseline、Agent或发布。

## H. Git

按范围提交并push origin/main，提交号由本次Git日志给出；运行备份、浏览器脚本、日志与截图为本地忽略产物，不包含凭据。

## I. 后续

Medium剩余7题仍需按真实关注原因由用户处理，Gate1 Pending；本轮不追加内容修订或外部调用。新导入业务题等待后续分类、Evidence匹配及既定质量治理；处理经验不能直接当作标准答案。独立来源的同题干保留，历史物理清理未执行。
