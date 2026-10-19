# Evaluation VNext Implementation Plan

本轮设计已由用户附件批准，直接在当前工作区顺序实施；不分派子Agent，不新建工作树，不触碰其他任务文件。

目标：保留历史数据与知识资产，以同一二元合同贯通Judge、Matcher、诊断、Agent、Regression及现有UI。

1. `backend/app/evaluation_contract.py`：最小verdict/checks/issues/reason解析与真实片段验证、新身份；先跑新合同反例失败，再实现。Legacy函数只解释旧记录，不作为新版通过条件。
2. `diagnostics.py`、`optimization.py`：以已定位的事实/规范与真实阶段Trace诊断；不使用题号、旧标签或字符串缺失做语义推断。以合成不同阶段案例及200条显式测试响应验证。
3. `evaluation.py`、`policy.py`：新版结果、执行异常、完整比较、持续失败新风险；先补专项失败测试。恢复最多3次、600秒，成功生成复用，Unknown停止。
4. `providers.py`、`ai_service.py`：新版Judge结构、共享来源图例与生成安全边界；旧无context调用仅服务已有Golden工具，正式新评测强制VNext。
5. 现有UI最小展示调整、SPEC/CHANGELOG/README同步，保留现有视觉与导航，不改图形几何。
6. 新增版本化Owner裁决和200条小型离线测试响应。读取真实SQLite只读核对哈希；程序只验证结构/定位/诊断/比较，绝不宣称新LLM语义已验收。执行后端相关/全测试、前端test/build、隔离API smoke及资产指纹。
7. 交付报告逐项记录实际证据、限制、服务与Git状态；仅提交本轮文件。无Provider、正式评测、发布或历史数据写入。
