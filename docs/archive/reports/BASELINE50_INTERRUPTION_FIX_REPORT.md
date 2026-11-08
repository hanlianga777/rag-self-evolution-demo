# Baseline50中断修复报告

日期：2026-10-20。Ponytail Full。已完成最小共享修复、离线验证、服务重载；本轮Provider **0次/¥0**，未续跑或新建正式评测。

1. **为什么运行3题后失败？**
   Run为`EVAL-20261020105804727444`，已完成3题，实际失败为第4题Q04：`V1G-110926448917-04`，问题是KIRA B 50停用三个月的长期存放/电池维护。Judge原始结论为FAIL：遗漏“只在室内存放”和“注意设备重量”。最后一次响应将对应手册条款放在issue.support，然而该Child位于实际候选而非Final，因此校验拒绝；前一次还因遗漏issue没有答案原句而被拒绝。

2. **真正的问题是什么？**
   不是标点/换行差异，也不是本次引用凭空捏造。实际support为DOC-001-C-00180：“存放\n小心\n忽略重量受伤与损坏危险运输和存放时注意设备的重量\n只在室内存放设备”。它在实际12条候选中，未进入4条Final。Final为DOC-002-C-00055、DOC-004-C-00027、DOC-001-C-00185、DOC-001-C-00002；充电条款真实位于C185。上下文没有传错，是模型把“证明遗漏要求的候选资料”误放进要求Final定位的support，程序又未区分该证据角色。

   另一个关键原因：本次Run实际保存`judge-vnext-2-operation`，Prompt SHA `8ce7b7aaa08cbab3b537e52a40bd9507b79c7fc3510653a843ae3d6298ddad64`，缺少Guard与Parser身份。前端服务仍运行旧缓存进程，之前源码修复没有加载到该进程。267项测试验证的是隔离进程中的当前源码和显式模拟响应；没有覆盖“实际失败响应中候选规范混入issue.support”的组合，也没有证明运行中的Demo已重载。

3. **具体修复了什么？**
   共享Parser新增严格的FAIL-only遗漏证据关联：issue的引用必须逐条对应met=false检查中的规范引用，并在实际Final或实际候选中按来源身份和连续原文定位。遗漏本来没有答案原句时，仅在这种关联成立后允许空answer_quotes。met=true关键事实仍只能引用实际Final；不能从候选/其他Chunk/全库借证据判PASS。虚构、错来源、未关联引用继续技术异常，不改为业务FAIL。

   Provider、EvaluationRunner、诊断一致传实际候选；原JSON不改，`judge_support_locations`保存证据阶段。本次两份原响应都能离线形成原来的FAIL，并诊断为Ranking（候选有、Final遗漏），没有将候选伪装成Final或Safety Guard依据。Q42 Guard、V3 Prompt、11 Gate/Regression/资格阈值不变。Parser升级`business-output-3-evidence-roles`进入新Identity。

   API对旧Partial也准确返回requires_policy_upgrade；前端旧身份按钮使用已有`fresh:true`入口，不再默认要求恢复不兼容记录。相关改动仅涉及共享合同/调用方、该状态字段及按钮，未全面重构UI。

4. **是否通过真实失败响应离线复现与回归？**
   是。直接提取修改前提交的校验函数，原样回放两份真实JSON分别复现`answer quote is missing or not located`和`support is not located in actual full Final`；新函数原样处理两份均为FAIL/Ranking。共273项后端回归通过；前端42文件/243测试、TypeScript/Vite构建通过。新增测试覆盖真实两次失败、候选不能支持PASS、虚构/错来源、未关联遗漏、空格/换行/NFKC、相似片段仍绑定来源、否定/小数不被抹去、非连续拼接拒绝；原有辅助说明、Q42、Partial/Failed/恢复与Baseline/Candidate共享路径回归保持。

   200条历史原答案/Final经显式离线Judge响应仍为157 PASS/43 FAIL，哈希保持；不是新真实模型成绩。[完整失败题及Final/候选/两份原响应](../backend/reports/baseline50-interruption-20261020/failed-case.json)、[旧错/新结果对照](../backend/reports/baseline50-interruption-20261020/failure-replay.json)、[200条回归](../backend/reports/baseline50-interruption-20261020/explicit-200.json)。

5. **是否仍有同类系统性风险？**
   已处理共享证据角色冲突，Baseline与Candidate使用同一入口。对20份保存真实响应的扫描为19份可验证、1份保留技术异常：[扫描结果](../backend/reports/baseline50-interruption-20261020/saved-response-scan.json)。该1份是本Run Q02重试前的旧响应：把“纯UI操作无需额外安全条件”标为满足却无support；不能凭模型一句话证明安全，因此未追加句式特判强行接受。Q02随后有效响应已完成并保留。

   不能保证任意未来LLM一定输出可验证引用；不存在、未关联、真正缺证据的内容仍须技术异常，不假造PASS/FAIL。这一能力边界不能靠放宽Matcher消除。本次没有增加模型、调用轮数或堆新Prompt，也没有把离线通过说成真实Baseline已经完成。

6. **原来的3题保留了吗？**
   全部保留。正式29张表全量行数/逻辑SHA与本轮开始一致，包括3个完成结果、失败Checkpoint、原始响应、Usage、旧Identity和全部旧实验。16项索引制品、4份PDF不变，历史200条未改。重载前已通过SQLite Backup API备份至`/tmp/baseline50-before-service-reload.db`，没有清库、覆盖或回填成绩。[保护与版本验证](../backend/reports/baseline50-interruption-20261020/verification.json)。

7. **能继续运行Baseline50吗？**
   可以由Owner在前端明确确认付费后启动新版本完整运行。本轮没有替你点击。已确认无活动任务、Partial恢复状态stopped，索引无需重建后受控重载服务；8010 API与5174前端只读健康检查通过，新API已将旧记录标为requires_policy_upgrade。重载没有触发Provider或修改正式表。

8. **能续跑，还是必须新建版本？**
   本次必须新建版本。旧Run为V2且没有新Guard/Parser身份；当前V3及新Parser合同与之不兼容，不能把旧3题当作新版本结果继承。旧Partial及检查点保留供历史追溯，不直接从3/50继续。即使原回答可只读离线回放，也不等于获得同身份正式续跑资格。本轮未修改旧身份或制作迁移成绩。

9. **前端点击哪个按钮？**
   刷新页面，进入 **Baseline → 重新运行 Baseline（新版本）**，查看并确认“完整真实Baseline重评”的付费提示后再执行。该按钮向现有接口发送`fresh:true`，保留旧记录并创建新Run。不要选择旧Run恢复，不要新建Golden，也不要点击Candidate实验。当前页面可能展示历史已完成Baseline；只要身份失效，同样显示新版本按钮。

实际文件：`evaluation_contract.py`、`providers.py`、`evaluation.py`、`diagnostics.py`、`main.py`，Baseline按钮与直接测试，SPEC/CHANGELOG/README、本报告及隔离证据。没有改Golden、生成/检索策略、Guard规则或Gate。现已停止，等待Owner操作；不自动执行付费验证。
