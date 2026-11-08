# V1.2 验证与交付记录

日期：2026-09-27。基线：`93486f23db4bb4711bba332dd0063b330838af47`。采用 Ponytail full；复用现有模块，无新依赖／数据库表／一级页面。原图及截图仅作参考，不推测隐藏实现。

## 确定性与 Fixture

- 后端全量 185 项通过，包含原业务 E2E-01～05、新 Golden Gate／替换／P0 显式接受、不可豁免答案锚点、D 完整逐题复验晋升／失败回退、并发预算和重启 D 回退测试。
- 前端 Vitest 55 项、TypeScript／生产构建通过；Gate 1 以当前活动题对应 Snapshot 判定完成，逐题批准不能假称已冻结。
- 1、2、4、6、10 文档 Coverage Fixture 通过；缺产品／章节、不同实体、单块材料、缺 Embedding、无结构材料及跨文档 Bridge 均有确定性测试。不是这些规模的真实 Provider 全链证明。
- 启动脚本契约、`git diff --check` 通过；项目未配置独立 lint 命令。
- 保留已存在的 httpx deprecation、部分测试资源清理／React act 警告，不把有警告说成无警告。

## 隔离真实运行（未完成主链）

数据库：`/tmp/rag-v12.bVmzUQ/fresh.db`；API：127.0.0.1:8022。真实 Corpus／FAISS／Retriever／DeepSeek（deepseek-v4-flash）／SQLite／API；未使用 Fixture Provider 或 Retriever。

唯一 Generation Run：`GGEN-20260926172007153103`。未重新生成整集，未运行 Revision、人工批准、Snapshot、Baseline、Agent 或发布。

| 阶段 | 实际结果 |
|---|---|
| Generation | 20 入库，8/4/8 |
| Probe（运行时记录） | 19 通过、1 未通过 |
| QC | 19 次完成：17 非 P0、2 P0；1 跳过 |
| Test Human Review | 0；质量阻塞后未推进 |
| Gate 1 / Golden Version | 未确认／未创建 |
| Baseline → Bad Case → A/B/C → Gate 2 → D → Gate 3 → Production Q&A | NOT VERIFIED（真实链路未到达，不用 Fixture 填 PASS） |

明确阻塞：Q18 为 safe_rejection，但题目询问内部错误的故障代码／维修步骤；Probe 分类 `NEGATIVE_SUBTYPE_MISMATCH`。Q04、Q20 为 QC P0，未替用户接受。

**运行版本边界：** 这条真实 Generation 已开始后，最终代码审查发现旧初次生成／Probe 未复用 Revision 的确定性答案锚点。已补共享调用并通过正反例回归，但没有重启在途 Worker、改写当次结果或再生成一套。对同批原题与真实 Chunk 使用最终校验做只读复核，Q09、Q10、Q11、Q12 返回 `unsupported answer anchor`。这四项是确定性阻塞，不因 QC 非 P0 而放行；本轮不继续调整锚点规则，也不将旧 Worker 的 19 次 Probe 通过冒充最终代码全链通过。

结论：代码／Fixture 验证通过，**Real Main Lifecycle Blocked / NOT VERIFIED**。不能宣称 V1.2 真实端到端 Ready。

## 浏览器与图

- Playwright 独立浏览器，本地5182页面读取隔离8022 API；仅为独立端口转发 GET 的 CORS 响应，不模拟业务数据、不发送浏览器写请求。
- 桌面1440×900及窄屏390×844巡检七页和治理 Drawer；移动导航通过“菜单”进入，桌面导航保持七项。控制台未观察到 error，仅 React 开发提示。
- 业务／技术 HTML 为唯一图源，同目录 PNG 由浏览器重渲染。Monitoring／版本／回滚独立标为辅助能力。
- 前端受控响应测试覆盖三 Gate 按钮和 P0 理由；不等于真实 Provider 已走完三 Gate。

## 数据保护

SQLite Backup API 备份：`/tmp/rag-v12.bVmzUQ/user-before.db`。兼容副本：`user-copy.db`；初始化前后逐表内容相同。25 个用户表与备份逐行只读比较相同，包括180题、10 Generation Run、16 Revision Run、32审核事件和3历史版本。没有向用户库提交迁移、生成、应用、审核或发布。Q01／Q09及现有 Preview 同样保全。

## 已接受的工程限制

- 线程仍为进程内执行；重启保留审计及预算，标记中断后手动恢复，不引入队列。
- 主题聚类和显式事实结构识别为轻量确定性实现；复杂图谱关系不推测。
- D 合并引用整组实验差异证据，不声称单参数因果。
- 本次真实质量阻塞是上述实测未完成项，不列作“已接受且不影响主线”的限制。
