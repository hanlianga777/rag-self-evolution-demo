# Golden Dataset Full Candidate Draft

本报告为基于当前正式 PDF Corpus 的 40 道 Golden Dataset Candidate Draft，不是正式 Evaluation Dataset；未修改 Evaluation、Retrieval、Chunking、Agent、`seed.py` 或 Demo。

## 汇总

- Total：40
- grounded_single：24
- grounded_multi：8
- ambiguous：4
- unanswerable：4
- standard：8
- paraphrase：10
- colloquial：6
- multi：8
- special：8
- normal：20
- high：20
- Reviewed：0
- Pending Review：40
- Grounded Source Check：32 / 32（继承 [Source-faithful Audit](golden_grounded_audit.md)）。
- Ambiguous Check：4 / 4。
- Near-domain Absence Check：2 / 2。
- Out-of-domain Check：2 / 2。
- 不使用 R1/R3 遥控器“充满指示”的冲突事实。

## 完整候选题

### GGC-001 · KIRA B 50 第一次调试前应如何处理操作说明书？

- Question Type：grounded_single
- Query Style：standard
- Product Scope：KIRA B 50
- Criticality：normal
- Review Status：Pending Review
- Reference Answer：第一次调试前应完整阅读操作说明书；可在设备显示屏查阅或下载到智能手机，并为后续使用妥善保管说明书。
- Answer Key Points：
  - 第一次调试前完整阅读操作说明书。
  - 可在设备显示屏查阅或下载到智能手机。
  - 为后续使用妥善保管说明书。
- Acceptable Evidence：
  - 卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001，P.2–2，一般提示）
    - 第一次调试前完整阅读操作说明书。
    - 为后续使用妥善保管说明书。
    - 当前版本 trace：KIRA-B50-CHUNK-0003
- Source Evidence IDs：EV-KIRA-001
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。
### GGC-002 · 操作 KIRA B 50 前有哪些基本安全前提？

- Question Type：grounded_single
- Query Style：standard
- Product Scope：KIRA B 50
- Criticality：high
- Review Status：Pending Review
- Reference Answer：仅在护罩和所有盖子关闭时操作；紧急情况下按下急停；运行场地不得超过技术数据规定的最大允许坡度。
- Answer Key Points：
  - 护罩和所有盖子关闭后才能操作。
  - 紧急情况下按下急停立即停用。
  - 不得超过最大允许坡度。
- Acceptable Evidence：
  - 卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001，P.3–3，安全提示）
    - 护罩和所有盖子关闭。
    - 紧急停机按钮。
    - 最大允许坡度。
    - 当前版本 trace：KIRA-B50-CHUNK-0006
- Source Evidence IDs：EV-KIRA-002
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-003 · KIRA B 50 在危险区域或面对危险物质时有哪些运行限制？

- Question Type：grounded_single
- Query Style：standard
- Product Scope：KIRA B 50
- Criticality：high
- Review Status：Pending Review
- Reference Answer：在危险区域须遵守相应安全规定，禁止在有爆炸危险的区域运行；不得喷洒或吸入爆炸性液体、易燃气体、爆炸性粉尘及未稀释的酸和溶剂。
- Answer Key Points：
  - 危险区域遵守相应安全规定。
  - 禁止在有爆炸危险的区域运行。
  - 不得处理爆炸性、易燃或未稀释酸和溶剂等物质。
- Acceptable Evidence：
  - 卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001，P.7–8，运行）
    - 危险区域安全规定。
    - 禁止爆炸危险区域运行。
    - 危险物质限制。
    - 当前版本 trace：KIRA-B50-CHUNK-0012
- Source Evidence IDs：EV-KIRA-003
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-004 · KIRA B 50 的日常维护需要关注哪些事项？

- Question Type：grounded_single
- Query Style：standard
- Product Scope：KIRA B 50
- Criticality：normal
- Review Status：Pending Review
- Reference Answer：日常维护包括清洁传感器、检修整机状态、开机后检查自动驾驶；运行期间操作人员应留在现场并经常检查清洁进度。
- Answer Key Points：
  - 清洁传感器。
  - 检修机器整体状态并检查自动驾驶。
  - 运行期间留在现场并检查清洁进度。
- Acceptable Evidence：
  - 卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001，P.24–24，日常维护）
    - 传感器清洁。
    - 整机状态检修。
    - 检查自动驾驶和清洁进度。
    - 当前版本 trace：KIRA-B50-CHUNK-0049
- Source Evidence IDs：EV-KIRA-007
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-005 · KIRA B 50 如何进入手动清洁操作？

- Question Type：grounded_single
- Query Style：standard
- Product Scope：KIRA B 50
- Criticality：normal
- Review Status：Pending Review
- Reference Answer：在触摸屏选择“手动清洁”功能后操作；菜单可显示或隐藏刷子功率和抽吸功率项。
- Answer Key Points：
  - 在触摸屏选择“手动清洁”。
  - 可操作刷子功率和抽吸功率菜单项。
- Acceptable Evidence：
  - 卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001，P.57–58，手动模式）
    - 触摸屏选择手动清洁。
    - 刷子功率和抽吸功率菜单。
    - 当前版本 trace：KIRA-B50-CHUNK-0093
- Source Evidence IDs：EV-KIRA-010
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-006 · B2 可以在什么环境下运行，操作时应保持什么安全距离？

- Question Type：grounded_single
- Query Style：standard
- Product Scope：B2 四足机器人
- Criticality：high
- Review Status：Pending Review
- Reference Answer：B2 应在 -20℃至55℃、天气良好的环境运行，恶劣天气不要运行；操作时保持在视线范围内，并与障碍物、复杂地面、人群、水面等保持至少2米安全距离。
- Answer Key Points：
  - 运行环境为 -20℃至55℃且天气良好。
  - 雷电、龙卷风等恶劣天气不运行。
  - 与障碍物、复杂地面、人群和水面保持至少2米。
- Acceptable Evidence：
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.10–10，使用环境要求）
    - -20℃至55℃和天气良好。
    - 恶劣天气不运行。
    - 至少2米安全距离。
    - 当前版本 trace：B2-MANUAL-CHUNK-0018, B2-MANUAL-CHUNK-0019
- Source Evidence IDs：EV-B2M-001
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-007 · R3 遥控器的充电参数、运行时间和空旷环境遥控距离分别是什么？

- Question Type：grounded_single
- Query Style：standard
- Product Scope：B2 遥控器
- Criticality：normal
- Review Status：Pending Review
- Reference Answer：R3 遥控器充电电压为5.0V、充电电流为700mA；运行时间为5小时，空旷环境遥控距离为100米以上。
- Answer Key Points：
  - 充电电压5.0V、充电电流700mA。
  - 运行时间5小时。
  - 空旷环境遥控距离100米以上。
- Acceptable Evidence：
  - 宇树_B2遥控器使用说明_中文版.pdf（DOC-003，P.3–3，技术规格）
    - 5.0V。
    - 700mA。
    - 5小时和100米以上。
    - 当前版本 trace：B2-REMOTE-CHUNK-0004
- Source Evidence IDs：EV-B2R-002
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-008 · B2 电池第一次使用前有什么要求？

- Question Type：grounded_single
- Query Style：standard
- Product Scope：B2 电池与充电器
- Criticality：high
- Review Status：Pending Review
- Reference Answer：首次使用电池前，务必将电池充满。
- Answer Key Points：
  - 首次使用前务必充满电。
- Acceptable Evidence：
  - 宇树_B2电池与充电器使用说明_中文版.pdf（DOC-004，P.2–2，简介）
    - 首次使用电池前务必充满。
    - 当前版本 trace：B2-BATTERY-CHUNK-0002
- Source Evidence IDs：EV-B2B-001
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-009 · 结束 KIRA B 50 的清洁时，抽吸步骤应怎么收尾？

- Question Type：grounded_single
- Query Style：paraphrase
- Product Scope：KIRA B 50
- Criticality：normal
- Review Status：Pending Review
- Reference Answer：结束清洁时，继续行驶一小段线路以抽吸残余水分，然后停用抽吸装置。
- Answer Key Points：
  - 继续行驶一小段线路。
  - 抽吸残余水分。
  - 随后停用抽吸装置。
- Acceptable Evidence：
  - 卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001，P.58–58，结束清洁）
    - 行驶一小段抽吸残余水分。
    - 停用抽吸装置。
    - 当前版本 trace：KIRA-B50-CHUNK-0094
- Source Evidence IDs：EV-KIRA-011
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-010 · 没有对接站时，KIRA B 50 要从哪里开始排放污水？

- Question Type：grounded_single
- Query Style：paraphrase
- Product Scope：KIRA B 50
- Criticality：normal
- Review Status：Pending Review
- Reference Answer：在无对接站场景下，先打开设备舱门，再按“排放污水”章节规定进行后续操作。
- Answer Key Points：
  - 适用于无对接站场景。
  - 先打开设备舱门。
  - 按排放污水章节继续操作。
- Acceptable Evidence：
  - 卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001，P.82–83，排放污水）
    - 无对接站。
    - 打开设备舱的门。
    - 当前版本 trace：KIRA-B50-CHUNK-0114
- Source Evidence IDs：EV-KIRA-012
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-011 · KIRA B 50 每次运行结束后，污水箱和滤网应如何维护？

- Question Type：grounded_single
- Query Style：paraphrase
- Product Scope：KIRA B 50
- Criticality：normal
- Review Status：Pending Review
- Reference Answer：每次运行后应排放污水、冲洗污水箱、清洁涡轮机防护网，并取出和清洗污水箱中的粗大污染物滤网。
- Answer Key Points：
  - 排放污水并冲洗污水箱。
  - 清洁涡轮机防护网。
  - 清洗粗大污染物滤网。
- Acceptable Evidence：
  - 卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001，P.86–86，在每次运行之后）
    - 排放污水。
    - 冲洗污水箱。
    - 清洁防护网和粗大污染物滤网。
    - 当前版本 trace：KIRA-B50-CHUNK-0120
- Source Evidence IDs：EV-KIRA-013
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-012 · KIRA B 50 的急停被按下后，应先做什么？

- Question Type：grounded_single
- Query Style：paraphrase
- Product Scope：KIRA B 50
- Criticality：high
- Review Status：Pending Review
- Reference Answer：机器人会停止驾驶和清洁；先检查机器人及周围环境，确认没有危险后再松开紧急停止按钮。
- Answer Key Points：
  - 机器人停止驾驶和清洁。
  - 检查机器人和周围环境。
  - 确认没有危险后松开急停按钮。
- Acceptable Evidence：
  - 卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001，P.99–100，紧急停止按钮已激活）
    - 停止驾驶和清洁。
    - 检查机器人和环境。
    - 无危险后松开急停。
    - 当前版本 trace：KIRA-B50-CHUNK-0142
- Source Evidence IDs：EV-KIRA-015
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-013 · KIRA B 50 对接失败后该怎么重新处理？

- Question Type：grounded_single
- Query Style：paraphrase
- Product Scope：KIRA B 50
- Criticality：normal
- Review Status：Pending Review
- Reference Answer：将机器人驱动到位置代码处并开始清洁任务；若错误仍存在，重新示教路线。
- Answer Key Points：
  - 驱动到位置代码处。
  - 开始清洁任务。
  - 错误仍存在时重新示教路线。
- Acceptable Evidence：
  - 卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001，P.101–101，对接失败）
    - 驱动到位置代码处。
    - 错误仍存在时重新示教路线。
    - 当前版本 trace：KIRA-B50-CHUNK-0148
- Source Evidence IDs：EV-KIRA-016
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-014 · 第一次把 B2 接入 Explore App，需要完成哪些步骤？

- Question Type：grounded_single
- Query Style：paraphrase
- Product Scope：B2 四足机器人
- Criticality：normal
- Review Status：Pending Review
- Reference Answer：首次使用先绑定；打开手机蓝牙并靠近 B2 保持实时通讯，安装 Unitree Explore App 后使用 Unitree 提供的企业账号和密码登录；没有企业账号时联系宇树售后开通。
- Answer Key Points：
  - 首次使用先绑定并打开手机蓝牙。
  - 手机靠近B2并保持实时通讯。
  - 安装 App 后使用企业账号登录；无账号联系售后开通。
- Acceptable Evidence：
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.12–13，连接 Unitree Explore App）
    - 首次绑定、手机蓝牙和靠近B2。
    - 安装 App 并用企业账号登录。
    - 无企业账号联系售后。
    - 当前版本 trace：B2-MANUAL-CHUNK-0023, B2-MANUAL-CHUNK-0024
- Source Evidence IDs：EV-B2M-005
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-015 · B2 正常关机前应先完成什么动作？

- Question Type：grounded_single
- Query Style：paraphrase
- Product Scope：B2 四足机器人
- Criticality：normal
- Review Status：Pending Review
- Reference Answer：先按两次 L2+A，让机器人完成关节锁定和卧倒；卧倒后短按电源键一次，再长按3秒以上关机，并按机身摆放要求放好关节位置。
- Answer Key Points：
  - 按两次 L2+A，完成关节锁定和卧倒。
  - 卧倒后短按再长按电源键3秒以上。
  - 关机后按要求摆放大小腿和髋关节。
- Acceptable Evidence：
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.15–15，关闭 B2）
    - L2+A 两次后卧倒。
    - 短按再长按3秒以上关机。
    - 关机后按要求摆放机身。
    - 当前版本 trace：B2-MANUAL-CHUNK-0027
- Source Evidence IDs：EV-B2M-006
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-016 · 遥控模块失效、无法让 B2 卧倒待机时，怎样强制关机？

- Question Type：grounded_single
- Query Style：paraphrase
- Product Scope：B2 四足机器人
- Criticality：high
- Review Status：Pending Review
- Reference Answer：与障碍物、复杂地面、人群和水面保持至少2米，抬住头部和尾部，短按电源键一次再长按3秒以上；掉电后缓慢将机器人抬至地面。
- Answer Key Points：
  - 先保持至少2米安全距离。
  - 抬住头部和尾部，短按再长按电源键3秒以上。
  - 掉电后缓慢放至地面。
- Acceptable Evidence：
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.16–16，如何在遥控模块失效时关闭机器人）
    - 至少2米安全距离。
    - 短按再长按3秒以上强制关机。
    - 掉电后缓慢放至地面。
    - 当前版本 trace：B2-MANUAL-CHUNK-0030
- Source Evidence IDs：EV-B2M-007
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-017 · R3 遥控器的摇杆要怎样装回去，收纳时又怎么放？

- Question Type：grounded_single
- Query Style：paraphrase
- Product Scope：B2 遥控器
- Criticality：normal
- Review Status：Pending Review
- Reference Answer：从收纳槽平稳缓慢取出两个摇杆，按顺时针方向固定并拧紧；收纳时拆下摇杆后放回收纳槽。
- Answer Key Points：
  - 平稳缓慢取出两个摇杆。
  - 顺时针固定并拧紧。
  - 收纳前拆下并放回收纳槽。
- Acceptable Evidence：
  - 宇树_B2遥控器使用说明_中文版.pdf（DOC-003，P.3–3，安装摇杆）
    - 取出收纳槽中的两个摇杆。
    - 顺时针固定并拧紧。
    - 拆下后放回收纳槽。
    - 当前版本 trace：B2-REMOTE-CHUNK-0004
- Source Evidence IDs：EV-B2R-003
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-018 · 摇杆校准时怎样进入、操作并使校准生效？

- Question Type：grounded_single
- Query Style：paraphrase
- Product Scope：B2 遥控器
- Criticality：normal
- Review Status：Pending Review
- Reference Answer：校准前不要触碰摇杆，同时按下并松开 F1 与 F3 进入校准；将左右摇杆打满舵并旋转数圈，提示音停止后单按 F3 使校准生效。
- Answer Key Points：
  - 校准前不触碰摇杆，F1 与 F3 同时按下松开。
  - 左右摇杆打满舵并旋转数圈。
  - 提示音停止后单按 F3 生效。
- Acceptable Evidence：
  - 宇树_B2遥控器使用说明_中文版.pdf（DOC-003，P.4–4，遥控器摇杆校准）
    - F1 和 F3 进入校准。
    - 摇杆打满舵并旋转。
    - 单按 F3 生效。
    - 当前版本 trace：B2-REMOTE-CHUNK-0005
- Source Evidence IDs：EV-B2R-004
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-019 · B2 淋雨或进沙后，机身到底怎么清理和晾干？

- Question Type：grounded_single
- Query Style：colloquial
- Product Scope：B2 四足机器人
- Criticality：normal
- Review Status：Pending Review
- Reference Answer：恶劣环境使用后及时清洁；先关闭电源，用干净软布擦拭并重点清洁多目深度相机，不能用金属刷或砂纸；清洗后擦干并吹干机器人表面和关节缝隙积水。
- Answer Key Points：
  - 恶劣环境使用后及时清洁，先关闭电源。
  - 用软布擦拭，重点清洁多目深度相机。
  - 禁止金属刷和砂纸，清洗后擦干并吹干积水。
- Acceptable Evidence：
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.18–19，日常保养与维护）
    - 恶劣环境后及时清洁。
    - 先关闭电源并用软布。
    - 禁止金属刷和砂纸，擦干及吹干。
    - 当前版本 trace：B2-MANUAL-CHUNK-0036, B2-MANUAL-CHUNK-0037, B2-MANUAL-CHUNK-0038
- Source Evidence IDs：EV-B2M-008
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-020 · B2 开机前我得先检查哪些容易漏掉的事？

- Question Type：grounded_single
- Query Style：colloquial
- Product Scope：B2 四足机器人
- Criticality：high
- Review Status：Pending Review
- Reference Answer：确认固件已更新；操作者不处于醉酒、药物影响或无法集中注意力状态；熟悉步态和紧急制动，并确认机器人及部件内部没有水、油、沙、土等异物。
- Answer Key Points：
  - 确认固件更新。
  - 操作者状态可安全专注操控。
  - 熟悉步态与紧急制动，检查内部无异物。
- Acceptable Evidence：
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.10–10，开机前检查）
    - 固件更新。
    - 操作者状态要求。
    - 熟悉紧急制动并检查内部异物。
    - 当前版本 trace：B2-MANUAL-CHUNK-0020
- Source Evidence IDs：EV-B2M-002
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-021 · R3 手柄怎么开、怎么关？

- Question Type：grounded_single
- Query Style：colloquial
- Product Scope：B2 遥控器
- Criticality：normal
- Review Status：Pending Review
- Reference Answer：开机时短按电源键一次，再长按2秒以上，听到两声提示音；关机时同样短按一次再长按2秒以上，听到三声提示音。
- Answer Key Points：
  - 开机：短按一次再长按2秒以上。
  - 开机提示为两声。
  - 关机：短按一次再长按2秒以上，提示为三声。
- Acceptable Evidence：
  - 宇树_B2遥控器使用说明_中文版.pdf（DOC-003，P.4–4，开启/关闭遥控器）
    - 短按再长按2秒以上。
    - 两声开启提示。
    - 三声关闭提示。
    - 当前版本 trace：B2-REMOTE-CHUNK-0005
- Source Evidence IDs：EV-B2R-005
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-022 · 想把 R3 的声音和震动切一下，该按哪个键？

- Question Type：grounded_single
- Query Style：colloquial
- Product Scope：B2 遥控器
- Criticality：normal
- Review Status：Pending Review
- Reference Answer：快速按 F3 按钮3次即可切换：可切换到振动模式或声音模式。
- Answer Key Points：
  - 快速按 F3 3次。
  - 可切换到振动模式。
  - 可切换到声音模式。
- Acceptable Evidence：
  - 宇树_B2遥控器使用说明_中文版.pdf（DOC-003，P.4–4，音效/震动切换）
    - 快速按 F3 3次。
    - 切换到振动模式或声音模式。
    - 当前版本 trace：B2-REMOTE-CHUNK-0005
- Source Evidence IDs：EV-B2R-006
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-023 · B2 电池自己会防哪些充电或放电风险？

- Question Type：grounded_single
- Query Style：colloquial
- Product Scope：B2 电池与充电器
- Criticality：high
- Review Status：Pending Review
- Reference Answer：电池具有平衡充电、过充、充电温度、充电电流、过放、短路和负载检测等保护；例如满电自动停止充电，温度低于0℃或高于50℃会触发充电异常。
- Answer Key Points：
  - 具有平衡充电和过充保护，满电自动停止充电。
  - 温度低于0℃或高于50℃会触发充电异常。
  - 具有过放、短路和负载检测保护。
- Acceptable Evidence：
  - 宇树_B2电池与充电器使用说明_中文版.pdf（DOC-004，P.3–3，电池功能）
    - 平衡充电和过充保护。
    - 充电温度和电流保护。
    - 过放、短路和负载检测保护。
    - 当前版本 trace：B2-BATTERY-CHUNK-0003, B2-BATTERY-CHUNK-0004
- Source Evidence IDs：EV-B2B-002
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-024 · 接触式充电板接触不稳或短路时会怎样保护电池？

- Question Type：grounded_single
- Query Style：colloquial
- Product Scope：B2 电池与充电器
- Criticality：high
- Review Status：Pending Review
- Reference Answer：极板短路时会切断短路极板与充电器/电池连接，短路解除后自动恢复；接触不可靠时会切断充电器与电池连接以避免打火，机器人起身再卧下可自动恢复充电。
- Answer Key Points：
  - 短路时切断短路极板与充电器/电池的连接。
  - 短路解除后自动恢复。
  - 接触不可靠时切断连接避免打火，起身再卧下可恢复充电。
- Acceptable Evidence：
  - 宇树_B2电池与充电器使用说明_中文版.pdf（DOC-004，P.6–6，接触式充电器功能）
    - 极板短路保护。
    - 短路解除后自动恢复。
    - 极板抖动保护与自动恢复。
    - 当前版本 trace：B2-BATTERY-CHUNK-0007, B2-BATTERY-CHUNK-0008
- Source Evidence IDs：EV-B2B-005
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-025 · KIRA B 50 示教并启动自动路线前，如何同时准备环境、空间和设备状态？

- Question Type：grounded_multi
- Query Style：multi
- Product Scope：KIRA B 50
- Criticality：high
- Review Status：Pending Review
- Reference Answer：先清除无法吸取的污物和非永久障碍物，并在低工作负荷时示教；自动路线须满足规定的通道和危险点距离限制；启动前确认工作负荷合适、清水箱满、污水箱空且蓄电池已充电。
- Answer Key Points：
  - 清除无法吸取的污物和非永久障碍物，低负荷时示教。
  - 遵守通道宽度和到危险点距离等空间限制。
  - 确认清水箱满、污水箱空、蓄电池已充电及工作负荷合适。
- Acceptable Evidence：
  - 卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001，P.17–17，环境准备工作）
    - 清除污物和非永久障碍物。
    - 低工作负荷时示教。
    - 当前版本 trace：KIRA-B50-CHUNK-0036
  - 卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001，P.19–19，到危险点的距离和设备的限制）
    - 通道宽度。
    - 到跌落边缘距离。
    - 当前版本 trace：KIRA-B50-CHUNK-0041
  - 卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001，P.21–22，启动条件）
    - 清水箱满。
    - 污水箱空。
    - 蓄电池充电。
    - 当前版本 trace：KIRA-B50-CHUNK-0046
- Source Evidence IDs：EV-KIRA-004, EV-KIRA-005, EV-KIRA-006
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-026 · KIRA B 50 开机前检查和接通设备应如何连贯执行？

- Question Type：grounded_multi
- Query Style：multi
- Product Scope：KIRA B 50
- Criticality：high
- Review Status：Pending Review
- Reference Answer：开机前检查急停、两个安全开关和传感器脏污情况，必要时清洁并重新启动；接通时按启动键，等待触摸屏出现登录界面，并将两个间隔滚轮调至相同高度。
- Answer Key Points：
  - 检查急停、两个安全开关和传感器。
  - 传感器脏污时清洁并重新启动设备。
  - 按启动键等待登录界面，并将两个间隔滚轮设为相同高度。
- Acceptable Evidence：
  - 卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001，P.46–46，检查设备）
    - 检查急停和安全开关。
    - 检查并清洁传感器。
    - 重新启动设备。
    - 当前版本 trace：KIRA-B50-CHUNK-0084
  - 卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001，P.46–47，接通设备）
    - 按下启动键。
    - 等待登录界面。
    - 两个间隔滚轮同高。
    - 当前版本 trace：KIRA-B50-CHUNK-0085
- Source Evidence IDs：EV-KIRA-008, EV-KIRA-009
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-027 · B2 从开机前检查到成功启动，哪些准备和动作缺一不可？

- Question Type：grounded_multi
- Query Style：multi
- Product Scope：B2 四足机器人
- Criticality：high
- Review Status：Pending Review
- Reference Answer：先完成固件、操作者状态、紧急制动和异物等开机前检查；在平坦地面按方向装入电池并确保卡扣到位，按要求摆放机身；随后短按一次再长按电源键3秒以上，等待机器人自动站立。
- Answer Key Points：
  - 完成固件、操作者状态、紧急制动和异物检查。
  - 平坦地面正确安装电池并按要求摆放机身。
  - 短按再长按电源键3秒以上，等待自动站立。
- Acceptable Evidence：
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.10–10，开机前检查）
    - 固件更新和操作者状态。
    - 紧急制动和内部异物检查。
    - 当前版本 trace：B2-MANUAL-CHUNK-0020
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.11–11，开机前准备）
    - 平坦地面安装电池。
    - 卡扣到位与正确摆放机身。
    - 当前版本 trace：B2-MANUAL-CHUNK-0021
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.11–11，启动 B2）
    - 短按再长按3秒以上。
    - 等待机器人自动站立。
    - 当前版本 trace：B2-MANUAL-CHUNK-0021, B2-MANUAL-CHUNK-0022
- Source Evidence IDs：EV-B2M-002, EV-B2M-003, EV-B2M-004
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-028 · B2 准备在场地内运行时，如何同时确认使用环境和开机前安全条件？

- Question Type：grounded_multi
- Query Style：multi
- Product Scope：B2 四足机器人
- Criticality：high
- Review Status：Pending Review
- Reference Answer：选择 -20℃至55℃且天气良好的环境，避开雷电、龙卷风等恶劣天气；控制时保持在视线范围内并与障碍物等保持至少2米；同时确认操作者能集中注意力、熟悉紧急制动且机器人内部无异物。
- Answer Key Points：
  - 选择天气良好、-20℃至55℃的运行环境，避开恶劣天气。
  - 保持在视线范围内，并保持至少2米安全距离。
  - 操作者可安全专注、熟悉紧急制动，机器人内部无异物。
- Acceptable Evidence：
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.10–10，使用环境要求）
    - 天气良好和温度范围。
    - 避开恶劣天气。
    - 至少2米安全距离。
    - 当前版本 trace：B2-MANUAL-CHUNK-0018, B2-MANUAL-CHUNK-0019
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.10–10，开机前检查）
    - 操作者状态要求。
    - 熟悉紧急制动。
    - 内部无异物。
    - 当前版本 trace：B2-MANUAL-CHUNK-0020
- Source Evidence IDs：EV-B2M-001, EV-B2M-002
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-029 · B2 的遥控器和电池分别低电量时，充电前和连接顺序要注意什么？

- Question Type：grounded_multi
- Query Style：multi
- Product Scope：B2 遥控器、B2 电池与充电器
- Criticality：high
- Review Status：Pending Review
- Reference Answer：遥控器充电前确保处于关闭状态并使用5V/2A、符合 FCC/CE 标准的 USB 充电器；电池充电时先将充电器接入匹配的交流电源，再连接电池，且电池包需从机身取出。
- Answer Key Points：
  - 遥控器充电前关闭，使用符合要求的5V/2A USB充电器。
  - 电池充电前确认交流电源与额定输入电压匹配。
  - 电池充电时先接交流电源再接电池，并将电池包从机身取出。
- Acceptable Evidence：
  - 宇树_B2遥控器使用说明_中文版.pdf（DOC-003，P.5–5，遥控器充电）
    - 5V/2A 且符合 FCC/CE 的 USB 充电器。
    - 充电前遥控器关闭。
    - 当前版本 trace：B2-REMOTE-CHUNK-0006
  - 宇树_B2电池与充电器使用说明_中文版.pdf（DOC-004，P.7–7，电池充电）
    - 交流电源与额定输入电压匹配。
    - 先接交流电源再接电池。
    - 电池包从机身取出。
    - 当前版本 trace：B2-BATTERY-CHUNK-0009
- Source Evidence IDs：EV-B2R-001, EV-B2B-006
- Reviewer Note：需人工复核原始 PDF 的措辞与页码；不包含 R1/R3 充满指示。

### GGC-030 · 首次让 B2 开机并用 R3 遥控器控制前，如何完成机身启动和遥控器连接确认？

- Question Type：grounded_multi
- Query Style：multi
- Product Scope：B2 四足机器人、B2 遥控器
- Criticality：high
- Review Status：Pending Review
- Reference Answer：先在平坦地面正确装入电池、确保卡扣到位并按要求摆放机身，再短按并长按电源键3秒以上启动；在 Explore App 的遥控器设置中输入编码绑定，R3 开机且连接成功后右侧 DL 指示灯亮。
- Answer Key Points：
  - 平坦地面正确装入电池、卡扣到位并摆放机身。
  - 短按再长按电源键3秒以上启动B2。
  - 在 Explore App 输入遥控器编码绑定，DL灯亮确认连接。
- Acceptable Evidence：
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.11–11，开机前准备）
    - 正确安装电池和摆放机身。
    - 当前版本 trace：B2-MANUAL-CHUNK-0021
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.11–11，启动 B2）
    - 短按再长按3秒以上启动。
    - 当前版本 trace：B2-MANUAL-CHUNK-0021, B2-MANUAL-CHUNK-0022
  - 宇树_B2遥控器使用说明_中文版.pdf（DOC-003，P.6–6，R3 遥控器基本操作）
    - Explore App 中绑定遥控器。
    - 输入遥控器编码。
    - DL指示灯亮确认连接。
    - 当前版本 trace：B2-REMOTE-CHUNK-0007
- Source Evidence IDs：EV-B2M-003, EV-B2M-004, EV-B2R-007
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-031 · 给 B2 准备首次使用时，电池充满和装入机身分别要怎么做？

- Question Type：grounded_multi
- Query Style：multi
- Product Scope：B2 四足机器人、B2 电池与充电器
- Criticality：high
- Review Status：Pending Review
- Reference Answer：首次使用前先将电池充满；充电时先接入匹配额定输入的交流电源，再接电池，并从机身取出电池包；装机时在平坦地面从侧面按正确方向插入，防呆接口朝上并确认卡扣到位。
- Answer Key Points：
  - 首次使用前将电池充满。
  - 充电时先接交流电源再接电池，且从机身取出电池包。
  - 在平坦地面按正确方向装入，防呆接口朝上并确认卡扣到位。
- Acceptable Evidence：
  - 宇树_B2电池与充电器使用说明_中文版.pdf（DOC-004，P.2–2，简介）
    - 首次使用前务必充满。
    - 当前版本 trace：B2-BATTERY-CHUNK-0002
  - 宇树_B2电池与充电器使用说明_中文版.pdf（DOC-004，P.7–7，电池充电）
    - 先接交流电源再接电池。
    - 电池包从机身取出。
    - 当前版本 trace：B2-BATTERY-CHUNK-0009
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.11–11，开机前准备）
    - 平坦地面安装。
    - 防呆接口朝上。
    - 确认卡扣到位。
    - 当前版本 trace：B2-MANUAL-CHUNK-0021
- Source Evidence IDs：EV-B2B-001, EV-B2B-006, EV-B2M-003
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-032 · 如果 B2 要长期停用，机器人关机和电池存放应分别怎么处理？

- Question Type：grounded_multi
- Query Style：multi
- Product Scope：B2 四足机器人、B2 电池与充电器
- Criticality：high
- Review Status：Pending Review
- Reference Answer：先按两次 L2+A 使机器人卧倒，再短按并长按电源键3秒以上关机，按要求摆放关节；电池避免靠近热源，宜在20℃至25℃、湿度45%至75%的干燥、通风且无易燃易爆杂物环境中存放。
- Answer Key Points：
  - L2+A 两次卧倒后短按再长按3秒以上关机，并按要求摆放关节。
  - 电池远离阳光直射、车内高温、火源或加热炉等热源。
  - 在20℃至25℃、湿度45%至75%的干燥通风环境存放，周边无易燃易爆杂物。
- Acceptable Evidence：
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.15–15，关闭 B2）
    - L2+A 两次后卧倒。
    - 短按再长按3秒以上关机。
    - 关机后按要求摆放机身。
    - 当前版本 trace：B2-MANUAL-CHUNK-0027
  - 宇树_B2电池与充电器使用说明_中文版.pdf（DOC-004，P.11–11，存储和运输）
    - 远离热源。
    - 20℃至25℃、45%至75%湿度。
    - 干燥、通风且无易燃易爆杂物。
    - 当前版本 trace：B2-BATTERY-CHUNK-0017, B2-BATTERY-CHUNK-0018
- Source Evidence IDs：EV-B2M-006, EV-B2B-008
- Reviewer Note：需人工复核原始 PDF 的措辞与页码。

### GGC-033 · 这个机器人怎么维护？

- Question Type：ambiguous
- Query Style：special
- Product Scope：KIRA B 50；B2 四足机器人
- Expected Behavior：clarify
- Criticality：normal
- Review Status：Pending Review
- Ambiguity Reason：当前语料同时包含 KIRA B 50 的日常维护和 B2 四足机器人的日常保养，操作内容与部件明显不同；未说明产品时直接作答有较高误答风险。
- Missing Context：
  - 具体产品
- Acceptable Clarifying Questions：
  - 你指的是 KIRA B 50，还是 B2 四足机器人？
- Ambiguity Candidates：
  - KIRA B 50：日常维护（卡赫_KIRA_B_50完整操作说明_中文版.pdf，DOC-001，P.24–24，日常维护；KIRA-B50-CHUNK-0049）
  - B2 四足机器人：日常保养与维护（宇树_B2四足机器人用户手册_中文版.pdf，DOC-002，P.18–18，第 18 页（页级/段落 fallback）；B2-MANUAL-CHUNK-0036）
- Reviewer Note：需人工确认用户是否提供具体产品。

### GGC-034 · 第一次使用前要做什么？

- Question Type：ambiguous
- Query Style：special
- Product Scope：KIRA B 50；B2 四足机器人；B2 遥控器；B2 电池与充电器
- Expected Behavior：clarify
- Criticality：high
- Review Status：Pending Review
- Ambiguity Reason：KIRA B 50 要求先阅读操作说明书；B2 电池要求首次使用前充满；B2 遥控器首次使用需在 App 中绑定。未说明设备或部件时不存在唯一正确步骤。
- Missing Context：
  - 具体产品或部件
- Acceptable Clarifying Questions：
  - 你指的是 KIRA B 50、B2 主机、B2 电池，还是 R3 遥控器？
- Ambiguity Candidates：
  - KIRA B 50：首次使用前阅读操作说明（卡赫_KIRA_B_50完整操作说明_中文版.pdf，DOC-001，P.2–2，一般提示；KIRA-B50-CHUNK-0003）
  - B2 电池与充电器：首次使用前充满电池（宇树_B2电池与充电器使用说明_中文版.pdf，DOC-004，P.2–2，第 2 页（页级/段落 fallback）；B2-BATTERY-CHUNK-0002）
  - B2 遥控器：首次使用遥控器绑定（宇树_B2遥控器使用说明_中文版.pdf，DOC-003，P.6–6，第 6 页（页级/段落 fallback）；B2-REMOTE-CHUNK-0007）
- Reviewer Note：需先限定设备或部件，再提供对应流程。

### GGC-035 · 怎么给它充电？

- Question Type：ambiguous
- Query Style：special
- Product Scope：KIRA B 50；B2 四足机器人；B2 遥控器；B2 电池与充电器
- Expected Behavior：clarify
- Criticality：high
- Review Status：Pending Review
- Ambiguity Reason：KIRA B 50 蓄电池、B2 电池包和 B2 遥控器的充电接口、连接顺序及前置条件不同；代词“它”未指明充电对象。
- Missing Context：
  - 具体产品或充电对象
- Acceptable Clarifying Questions：
  - 你要充的是 KIRA B 50、B2 电池包，还是 B2 的 R3 遥控器？
- Ambiguity Candidates：
  - KIRA B 50：给蓄电池充电（卡赫_KIRA_B_50完整操作说明_中文版.pdf，DOC-001，P.36–37，给蓄电池充电；KIRA-B50-CHUNK-0071）
  - B2 电池与充电器：插入式充电流程（宇树_B2电池与充电器使用说明_中文版.pdf，DOC-004，P.7–7，第 7 页（页级/段落 fallback）；B2-BATTERY-CHUNK-0009）
  - B2 遥控器：遥控器低电量充电（宇树_B2遥控器使用说明_中文版.pdf，DOC-003，P.5–5，第 5 页（页级/段落 fallback）；B2-REMOTE-CHUNK-0006）
- Reviewer Note：不得将不同设备的充电流程合并为唯一答案。

### GGC-036 · 开机前该检查什么？

- Question Type：ambiguous
- Query Style：special
- Product Scope：KIRA B 50；B2 四足机器人
- Expected Behavior：clarify
- Criticality：high
- Review Status：Pending Review
- Ambiguity Reason：KIRA B 50 的设备检查涵盖密封性、安全开关和传感器；B2 的开机前检查涵盖固件、操作者状态、紧急制动和异物等。未说明产品时答案会遗漏或错配安全前提。
- Missing Context：
  - 具体产品
- Acceptable Clarifying Questions：
  - 你是准备启动 KIRA B 50，还是 B2 四足机器人？
- Ambiguity Candidates：
  - KIRA B 50：检查设备（卡赫_KIRA_B_50完整操作说明_中文版.pdf，DOC-001，P.46–46，检查设备；KIRA-B50-CHUNK-0084）
  - B2 四足机器人：开机前检查（宇树_B2四足机器人用户手册_中文版.pdf，DOC-002，P.10–10，第 10 页（页级/段落 fallback）；B2-MANUAL-CHUNK-0020）
- Reviewer Note：开机前安全检查必须按具体产品回答。

### GGC-037 · R3 遥控器能同时绑定并控制两台 B2 吗？

- Question Type：unanswerable
- Query Style：special
- Product Scope：B2 四足机器人；B2 遥控器
- Expected Behavior：insufficient_evidence
- Criticality：normal
- Review Status：Pending Review
- Unanswerable Type：near_domain
- Reference Answer：null
- Acceptable Evidence：[]
- Absence Reason：正式语料说明遥控器可与机器狗绑定并在连接成功后控制 B2，但没有说明一个 R3 遥控器能否同时绑定或控制两台 B2。
- Corpus Absence Check：
  - Scope：4 份正式 PDF 的全部 chunks.json 原始 chunk text
  - Keywords Checked：R3、遥控器、绑定、控制、同时、两台、多台
  - Keyword Matches：
    - R3：B2-REMOTE-CHUNK-0002, B2-REMOTE-CHUNK-0007, B2-REMOTE-CHUNK-0009, B2-REMOTE-CHUNK-0016
    - 遥控器：B2-MANUAL-CHUNK-0002, B2-MANUAL-CHUNK-0006, B2-MANUAL-CHUNK-0007, B2-MANUAL-CHUNK-0017, B2-MANUAL-CHUNK-0018, B2-MANUAL-CHUNK-0019, B2-MANUAL-CHUNK-0025, B2-MANUAL-CHUNK-0026, B2-MANUAL-CHUNK-0028, B2-MANUAL-CHUNK-0030, B2-MANUAL-CHUNK-0037, B2-MANUAL-CHUNK-0038, B2-REMOTE-CHUNK-0001, B2-REMOTE-CHUNK-0002, B2-REMOTE-CHUNK-0004, B2-REMOTE-CHUNK-0005, B2-REMOTE-CHUNK-0006, B2-REMOTE-CHUNK-0007, B2-REMOTE-CHUNK-0008, B2-REMOTE-CHUNK-0009, B2-REMOTE-CHUNK-0010, B2-REMOTE-CHUNK-0012, B2-REMOTE-CHUNK-0013, B2-REMOTE-CHUNK-0014, B2-REMOTE-CHUNK-0016, B2-BATTERY-CHUNK-0010
    - 绑定：B2-MANUAL-CHUNK-0023, B2-MANUAL-CHUNK-0024, B2-MANUAL-CHUNK-0025, B2-REMOTE-CHUNK-0002, B2-REMOTE-CHUNK-0007, B2-REMOTE-CHUNK-0010, B2-REMOTE-CHUNK-0014
    - 控制：KIRA-B50-CHUNK-0067, KIRA-B50-CHUNK-0114, B2-MANUAL-CHUNK-0005, B2-MANUAL-CHUNK-0006, B2-MANUAL-CHUNK-0007, B2-MANUAL-CHUNK-0011, B2-MANUAL-CHUNK-0018, B2-MANUAL-CHUNK-0024, B2-MANUAL-CHUNK-0025, B2-MANUAL-CHUNK-0026, B2-MANUAL-CHUNK-0029, B2-MANUAL-CHUNK-0032, B2-MANUAL-CHUNK-0033, B2-MANUAL-CHUNK-0034, B2-REMOTE-CHUNK-0007, B2-REMOTE-CHUNK-0014
    - 同时：KIRA-B50-CHUNK-0038, KIRA-B50-CHUNK-0073, B2-MANUAL-CHUNK-0010, B2-MANUAL-CHUNK-0012, B2-MANUAL-CHUNK-0027, B2-MANUAL-CHUNK-0028, B2-REMOTE-CHUNK-0005, B2-REMOTE-CHUNK-0012, B2-BATTERY-CHUNK-0003, B2-BATTERY-CHUNK-0004
    - 两台：无匹配
    - 多台：无匹配
  - Related Chunks Reviewed：
  - 宇树_B2遥控器使用说明_中文版.pdf（DOC-003，P.2–2，第 2 页（页级/段落 fallback）；B2-REMOTE-CHUNK-0002）：仅说明机器狗与遥控器可通过 App 绑定，未说明多机器人并发绑定或控制。
  - 宇树_B2遥控器使用说明_中文版.pdf（DOC-003，P.6–6，第 6 页（页级/段落 fallback）；B2-REMOTE-CHUNK-0007）：仅说明输入遥控器编码后与机器狗数传模块绑定、连接成功后控制 B2，未说明同时控制两台。
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.14–14，第 14 页（页级/段落 fallback）；B2-MANUAL-CHUNK-0025）：仅说明首次使用遥控器的单设备绑定与控制流程，未定义多设备关系。
  - Highest Related Result：宇树_B2遥控器使用说明_中文版.pdf（DOC-003，P.6–6，第 6 页（页级/段落 fallback）；B2-REMOTE-CHUNK-0007）：这是语料中最直接的 R3 绑定与控制说明，但仅指向单个机器狗/B2，不能推出多设备并发能力。
  - Conclusion：“两台”“多台”在全 Corpus 中无匹配；相关绑定与控制内容也未给出并发设备能力，因此没有足够 Evidence 回答。
- Reviewer Note：不得依据通用蓝牙或遥控器常识推断多机控制能力。

### GGC-038 · B2 加装 5G 组网后支持哪些运营商和频段？

- Question Type：unanswerable
- Query Style：special
- Product Scope：B2 四足机器人
- Expected Behavior：insufficient_evidence
- Criticality：normal
- Review Status：Pending Review
- Unanswerable Type：near_domain
- Reference Answer：null
- Acceptable Evidence：[]
- Absence Reason：正式语料只说明 B2 可适配 5G 组网外设，未提供模块型号、运营商兼容性或频段信息。
- Corpus Absence Check：
  - Scope：4 份正式 PDF 的全部 chunks.json 原始 chunk text
  - Keywords Checked：B2、5G、5G组网、运营商、频段
  - Keyword Matches：
    - B2：B2-MANUAL-CHUNK-0001, B2-MANUAL-CHUNK-0002, B2-MANUAL-CHUNK-0006, B2-MANUAL-CHUNK-0007, B2-MANUAL-CHUNK-0009, B2-MANUAL-CHUNK-0010, B2-MANUAL-CHUNK-0011, B2-MANUAL-CHUNK-0012, B2-MANUAL-CHUNK-0013, B2-MANUAL-CHUNK-0015, B2-MANUAL-CHUNK-0021, B2-MANUAL-CHUNK-0022, B2-MANUAL-CHUNK-0023, B2-MANUAL-CHUNK-0024, B2-MANUAL-CHUNK-0025, B2-MANUAL-CHUNK-0027, B2-MANUAL-CHUNK-0029, B2-MANUAL-CHUNK-0030, B2-MANUAL-CHUNK-0031, B2-MANUAL-CHUNK-0034, B2-MANUAL-CHUNK-0036, B2-REMOTE-CHUNK-0001, B2-REMOTE-CHUNK-0002, B2-REMOTE-CHUNK-0004, B2-REMOTE-CHUNK-0006, B2-REMOTE-CHUNK-0007, B2-REMOTE-CHUNK-0008, B2-REMOTE-CHUNK-0009, B2-REMOTE-CHUNK-0010, B2-REMOTE-CHUNK-0014, B2-REMOTE-CHUNK-0016, B2-BATTERY-CHUNK-0001, B2-BATTERY-CHUNK-0002, B2-BATTERY-CHUNK-0005, B2-BATTERY-CHUNK-0006, B2-BATTERY-CHUNK-0007, B2-BATTERY-CHUNK-0010, B2-BATTERY-CHUNK-0013, B2-BATTERY-CHUNK-0019, B2-BATTERY-CHUNK-0020
    - 5G：B2-MANUAL-CHUNK-0012, B2-MANUAL-CHUNK-0024
    - 5G组网：B2-MANUAL-CHUNK-0012
    - 运营商：无匹配
    - 频段：无匹配
  - Related Chunks Reviewed：
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.6–6，第 6 页（页级/段落 fallback）；B2-MANUAL-CHUNK-0012）：仅列出“5G组网”为可适配外设之一，未说明运营商、频段或通信模块规格。
  - 宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.4–4，第 4 页（页级/段落 fallback）；B2-MANUAL-CHUNK-0006）：列出 B2 的接口和功能亮点，但未提供 5G 网络兼容性参数。
  - Highest Related Result：宇树_B2四足机器人用户手册_中文版.pdf（DOC-002，P.6–6，第 6 页（页级/段落 fallback）；B2-MANUAL-CHUNK-0012）：这是唯一直接出现“5G组网”的 chunk，但其内容只支持可适配外设，不能支持运营商或频段结论。
  - Conclusion：“运营商”“频段”在全 Corpus 中无匹配；唯一 5G 相关内容没有规格或兼容性说明，因此没有足够 Evidence 回答。
- Reviewer Note：不得用模型预训练知识补充 5G 频段或运营商信息。

### GGC-039 · 今天东京天气怎么样？

- Question Type：unanswerable
- Query Style：special
- Product Scope：无（Out-of-domain）
- Expected Behavior：insufficient_evidence
- Criticality：normal
- Review Status：Pending Review
- Unanswerable Type：out_of_domain
- Reference Answer：null
- Acceptable Evidence：[]
- Absence Reason：当前正式 Corpus 仅包含 KIRA B 50、B2 主机、遥控器和电池/充电器说明，不包含天气数据。
- Reviewer Note：不得以模型常识或实时外部信息作答。

### GGC-040 · MacBook 怎么开机？

- Question Type：unanswerable
- Query Style：special
- Product Scope：无（Out-of-domain）
- Expected Behavior：insufficient_evidence
- Criticality：normal
- Review Status：Pending Review
- Unanswerable Type：out_of_domain
- Reference Answer：null
- Acceptable Evidence：[]
- Absence Reason：当前正式 Corpus 不含 Apple 电脑或其他消费电子设备的操作说明。
- Reviewer Note：不得以模型常识作答。
