# 项目协作规则

- 修改前读取 `docs/RAG_SELF_EVOLUTION_SPEC.md` 文首当前有效合同及真实代码/数据。历史说明不覆盖当前合同，Fixture不冒充Provider结果。
- 每次修改产品逻辑、业务流程、参数、评测规则、Gate、版本治理或UI Contract，必须检查并同步当前SPEC、`docs/SPEC_CHANGELOG.md`、相关README/文档、受影响架构。代码与SPEC必须在同一次Commit提交。
- 纯代码Bug且SPEC行为不变，可在提交说明记录 `No SPEC Change`，不机械改文档；有不确定冲突先列明，不发明新规则。
- 正式业务/技术图唯一源为 `frontend/src/components/KnowledgeDiagrams.tsx` 及Shared CSS。页面改图后运行 `python3 scripts/export_architecture.py`，同步 `架构` 中SVG/PNG/manifest及引用，不另画不同版本。
- 所有右侧Drawer使用唯一 `--drawer-width`，不得新增页面自定义宽度；复用现有Card/Select/PageShell。
- 后端测试必须在导入app前使用隔离 `RAG_DEMO_DB_PATH`，同时隔离Corpus/索引和.env；既有Legacy索引fixture只能用于明确标注的离线测试，不混入当前Knowledge或冒充真实Provider验收；真实写入前SQLite Backup API及产物备份。凭据不回显、不入日志/数据库/Git。
- 人工批准、Snapshot冻结、Gate和发布不得自动代行；Provider调用严格遵守本轮用户授权范围及冻结预算。
- 最小精准修改；验证源码、接口、数据与页面一致后提交范围内文件、push origin/main并确认干净同步。

- Business Golden V2复用既有Topic及资格审计，角色/场景/意图/难度与Child/Parent来源必须持久化；负向Topic材料Anchor不是答案Evidence，真实Probe仍校验整个Corpus边界。已有Full与Snapshot只读保护，新工作集不自动冻结。

- 数据集自然度/多样性诊断只作建议；内容修订保留Revision History并按新身份检查，不用词面规则或旧审计自动关闭风险。
