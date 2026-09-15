# Grounded Golden Source-faithful Audit

审计对象为 `golden_dataset_grounded_draft.json` 中 32 道 `Pending Review` Case。每题以 `backend/data/index/chunks.json` 的原始 chunk text 为首要依据；B2 遥控器的 F1/F3 相邻章节另回查正式 PDF P.4/P.5。未以 Inventory 的 Evidence Summary 或 Key Points 作为正确性依据。

## 汇总

- 总 Case：32
- 完全正确：31
- 修正 Evidence Metadata：1
- 修正 Reference Answer：0
- 替换 Case：0
- Source Check：32 / 32
- Review Status：全部保持 `Pending Review`
- Evidence Inventory：已同步修复 4 个 Topic（EV-B2R-001、EV-B2R-003、EV-B2R-005、EV-B2R-006）

现有分布保持不变：`standard` 8、`paraphrase` 10、`colloquial` 6、`multi` 8；`grounded_single` 24、`grounded_multi` 8。

## Case 审计结果

无需修改：GGC-001 至 GGC-021、GGC-023 至 GGC-032。上述 31 题的问题、Reference Answer、Answer Key Points、Evidence ID、文档、页码、章节和 source chunk 均可在直接来源中定位；8 道 Multi Case 均有至少两个互补来源支撑完整答案。

| Case ID | 问题类型 | 发现的问题 | 修改前 | 修改后 | 原始 Evidence Page / Chunk |
|---|---|---|---|---|---|
| GGC-022 | Evidence Metadata | F3 三次的“音效/震动切换”错误绑定为 P.5 的 F1 “音效/震动开关”；题目和答案本身均正确。 | DOC-003 P.5，`音效/震动开关`，`B2-REMOTE-CHUNK-0006` | DOC-003 P.4，`音效/震动切换`，`B2-REMOTE-CHUNK-0005`；证据关键点为 F3 快按三次后切换振动或声音模式。 | 宇树_B2遥控器使用说明_中文版.pdf P.4 / `B2-REMOTE-CHUNK-0005` |

## Evidence Inventory 源资料同步修正

以下修正不改变任何 Golden Case 的题目或答案；其中 EV-B2R-006 同时是 GGC-022 的直接 Evidence 绑定。

| Evidence ID | 问题类型 | 发现的问题 | 修改前 | 修改后 | 原始 Evidence Page / Chunk |
|---|---|---|---|---|---|
| EV-B2R-001 | Summary / Key Points 错位 | P.5 同一 chunk 的 F1 音效/震动开关内容被写入“遥控器低电量充电”。 | F1 三次开关振动/声音等内容。 | 低电量连接充电器、FCC/CE 5V/2A、充电前关闭遥控器、1Hz 指示灯闪烁；R1/R3 的充满指示差异不进入共同结论。 | DOC-003 P.5 / `B2-REMOTE-CHUNK-0006`；交叉来源 DOC-002 P.9、DOC-003 P.10 |
| EV-B2R-003 | Summary / Key Points 错位 | P.3 的技术规格（780mAh、蓝牙、100m）被写入“安装收纳遥控器摇杆”。 | 技术规格及一条取出摇杆文字。 | 平稳取出两个摇杆、顺时针固定并拧紧、拆下后放回收纳槽。 | DOC-003 P.3 / `B2-REMOTE-CHUNK-0004` |
| EV-B2R-005 | Summary / Key Points 错位 | P.4 的摇杆校准内容被写入“开关 R3 遥控器”。 | F1+F3 校准和单按 F3 生效。 | 短按一次后长按电源键 2 秒以上；两声提示音开启、三声提示音关闭。 | DOC-003 P.4 / `B2-REMOTE-CHUNK-0005` |
| EV-B2R-006 | Topic / Metadata / Summary 错位 | P.5 的 F1 音效/震动开关被标为模式切换来源。 | `音效震动设置`，P.5，`音效/震动开关`，`B2-REMOTE-CHUNK-0006`，F1 三次开关。 | `音效/震动模式切换`，P.4，`音效/震动切换`，`B2-REMOTE-CHUNK-0005`，F3 三次切换振动或声音模式。 | DOC-003 P.4 / `B2-REMOTE-CHUNK-0005` |

## Source-faithful 检查

- 对每个 Case 的 `source_evidence_ids`、文档 ID、页码、章节、source chunk 和 `acceptable_evidence` 逐项解析并与 `chunks.json` 交叉核对。
- 对 F1/F3、按键次数、2 秒、1Hz、5V/2A、0℃/50℃、100m 等精确事实逐项回查直接来源；GGC-022 另用正式 PDF P.4/P.5 确认 F3 切换与 F1 开关为不同功能。
- 仅在跨文档来源共同支持的范围内保留充电结论；未混入 R1/R3 “充满”指示差异。
- 未运行 Evaluation；未修改正式 Dataset、`seed.py`、Retrieval、Chunking、Agent、Demo、原始 chunk 或 PDF。
