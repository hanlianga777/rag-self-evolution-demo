# Retrieval Smoke Test

Total Tests：12

Grounded Tests：S-001 ～ S-009
Document Hit@1：7 / 9
Document Hit@4：9 / 9

Observation Tests：S-010 ～ S-012（仅记录真实召回，不作 Pass/Fail）

## S-001

Category：Grounded

Question：KIRA B 50 首次使用前应该做什么？

Expected Documents：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Expected Products：KIRA B 50

Rank 1
Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Product：KIRA B 50
Section：第 1 页
Section Path：第 1 页
Page：1 - 1
Chunk：KIRA-B50-CHUNK-0001
Similarity：0.6199
Preview：KIRA B 50
KIRA B 50
59802530 (02/24)
ZH


Rank 2
Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Product：KIRA B 50
Section：每周
Section Path：每周
Page：86 - 86
Chunk：KIRA-B50-CHUNK-0121
Similarity：0.4787
Preview：每周
1. 使用湿微纤维抹布清洁传感器。如有必要，请额外使用玻璃清洁剂。
2. ## 定期使用时，至少每周给蓄电池完全充电一次并且没有间断。

Rank 3
Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Product：KIRA B 50
Section：安全提示
Section Path：安全提示
Page：3 - 3
Chunk：KIRA-B50-CHUNK-0006
Similarity：0.4571
Preview：安全提示
首次使用本设备前，请注意仔细阅读本操作说明书以及完整操作说明书（设备显示屏中），然后按其操作。
在护罩和所有盖子均已关闭的情况下，才能操作本设备。
按下紧急停机按钮，在紧急情况下立即停用。
只能在不超过最大允许坡度的场地上操作设备（参见小节“技术数据”）。
在对接过程中，请勿将任何身体部位伸入对接站和设备之间。

Rank 4
Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Product：KIRA B 50
Section：维护间隔
Section Path：维护间隔
Page：85 - 86
Chunk：KIRA-B50-CHUNK-0119
Similarity：0.4441
Preview：维护间隔
运输期间用于捆扎的孔眼
1
小心
忽略重量
受伤与损坏危险
运输和存放时注意设备的重量。
危险
无意中启动设备，接触导电部件
受伤危险，触电
在执行任何工作之前，请将设备与对接站断开，或拔出电源插头。

提示：如果有一个对接站，则会自动执行标有“##”的维护工作。

Document Hit@1：True
Document Hit@4：True
Evidence Hit@4：Yes
Cross-product contamination：False
Retrieval latency_ms：1133.21
Notes：None.

## S-002

Category：Grounded

Question：B2 开机前手册要求关注哪些内容？

Expected Documents：宇树_B2四足机器人用户手册_中文版.pdf
Expected Products：B2 四足机器人

Rank 1
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 11 页（页级/段落 fallback）
Section Path：第 11 页（页级/段落 fallback）
Page：11 - 11
Chunk：B2-MANUAL-CHUNK-0021
Similarity：0.5876
Preview：tics
开机前准备
(1) 安装电池包
将 B2放在平坦的地面上，将电池包从机器人侧面插入电池槽，注意安装方向，防呆接口朝上，如无法完全
插入电池包，请调整电池包方向，不要强行按压，以免损坏电池接口和卡扣，当听到“咔哒~”声，电池包安装
完成。请确保卡扣卡到位！
tics
(2) 机身摆放（重要步骤！！！）
卧式开机：请确保开机运行前机器人放置在平整地面上，机器人腹部支撑垫需平贴地面，机身水平无倾斜
趴在地面，机器人小腿呈完全收起状态

Rank 2
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 7 页（页级/段落 fallback）
Section Path：第 7 页（页级/段落 fallback）
Page：7 - 7
Chunk：B2-MANUAL-CHUNK-0013
Similarity：0.573
Preview：tics
接口说明
B2 机身侧面提供 sdk 扩展口，以便开发者继续更多的扩展功能开发，如下图所示。
充
PC3 直连网口
12V上部
PC2 直连网口
12V 上部
PC2 USB3.0
主电池功率
主电池485
PC1 USB2.0
交换机网口
12V上部
交换机网口
电池输入
预留电机
电机58V
上电源板485
电源+网络
电源+网络
PC3 USB3.0
电源板急停
PC1 USB3.0
电源+网络
电源+网络
功率+485

Rank 3
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 15 页（页级/段落 fallback）
Section Path：第 15 页（页级/段落 fallback）
Page：15 - 15
Chunk：B2-MANUAL-CHUNK-0027
Similarity：0.572
Preview：tics
关闭 B2
关机前，请务必确保机器人站立在平整地面上，确保机器人处于静态站立状态（机器人机身位置处于开机
起立后的初始状态，机身水平，手柄无任何操作，静态站立时的状态）。
● 按2次L2+A 键，机器人依次完成关节锁定，卧倒动作；
● 机器人进入卧倒状态后，先短按电源键再长按电源键3秒以上关机。
tics
关机后，请按照机身摆放要求，摆放好机器人大小腿和髋关节位置，为下次开机做准备。若长时间不使用
B2，请及时取出电池包：往外

Rank 4
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 18 页（页级/段落 fallback）
Section Path：第 18 页（页级/段落 fallback）
Page：18 - 18
Chunk：B2-MANUAL-CHUNK-0036
Similarity：0.5498
Preview：日常保养与维护
botics
整机清洁
1. 清洁
当B2在恶劣环境下（雨天、沙尘、湿地)使用后，请及时清洁机身表面。
tics
清洗机身前请先关闭电源，使用干净的软布对机身进行擦拭，尤其关注多目深度相机是否擦拭干净。清洁
时严禁使用金属刷、砂纸等，以免刮伤零件表面。清洗后，请用软布将机身擦干。擦干后可用风扇或风枪将机
器人表面、关节缝隙处的积水吹干，避免留下水痕。
A
● 注意！B2 整机(含电池包)IP67 级防水，清洁时请勿取下电

Document Hit@1：True
Document Hit@4：True
Evidence Hit@4：Yes
Cross-product contamination：False
Retrieval latency_ms：12.74
Notes：None.

## S-003

Category：Grounded

Question：B2 遥控器低电量时如何充电？

Expected Documents：宇树_B2遥控器使用说明_中文版.pdf
Expected Products：B2 遥控器

Rank 1
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 9 页（页级/段落 fallback）
Section Path：第 9 页（页级/段落 fallback）
Page：9 - 9
Chunk：B2-MANUAL-CHUNK-0017
Similarity：0.7858
Preview：tics
遥控器充电
当遥控器电量指示灯显示低电量时，应将遥控器连接充电器，如下图所示：
R
④
④
交流电源
100-240V
USB 充电器
③
③
USB-Type C 线
otics
0
oo
Unitr
1. 请使用官方 USB 充电器。如不使用官方充电器，推荐使用符合 FCC/CE 标准，规格为 5V/2A 的 USB
充电器。
2. 给遥控器充电前，确保遥控器处于关闭状态。
3. 充电状态下电源指示灯会按1Hz（1秒/次）

Rank 2
Document：宇树_B2遥控器使用说明_中文版.pdf
Product：B2 遥控器
Section：第 5 页（页级/段落 fallback）
Section Path：第 5 页（页级/段落 fallback）
Page：5 - 5
Chunk：B2-REMOTE-CHUNK-0006
Similarity：0.751
Preview：B2遥控器使用手册
tics
音效/震动开关
●关闭振动/声音：快速按下F1按钮3次，关闭振动/声音。
●开启振动/声音：快速按下F1按钮3次，开启振动/声音。
Unitree
START
Robotics
快按3次F1
●修改遥控器反馈功能后，默认是不保存的，如果需要下次开机生效，则按住F1进行关机操作保存当前模式。
遥控器充电
当遥控器电量指示灯显示低电量时，应将遥控器连接充电器，如下图所示：
交流电源
100-240V
USB 充

Rank 3
Document：宇树_B2电池与充电器使用说明_中文版.pdf
Product：B2 电池与充电器
Section：第 8 页（页级/段落 fallback）
Section Path：第 8 页（页级/段落 fallback）
Page：8 - 8
Chunk：B2-BATTERY-CHUNK-0010
Similarity：0.7266
Preview：B2电池&充电器使用手册
tics
接触式充电器
1. 充电前检查：在每次充电前，请检查 B2机身底部的充电电极是否有异物遮挡，以及充电板充电电极表
面是否有异物遮挡。请使用干燥抹布擦拭充电电极表面，确保充电过程中良好接触。
2. 连接电源：将 B2 接触式充电器放置在空旷室内，先将锂电池充电器接入输入交流电源，然后连接接触
式充电板电源接口，如下图所示。
交流电源
①
110-220V
Un
☐。
②
ee Rdbotics
接触式充

Rank 4
Document：宇树_B2遥控器使用说明_中文版.pdf
Product：B2 遥控器
Section：第 3 页（页级/段落 fallback）
Section Path：第 3 页（页级/段落 fallback）
Page：3 - 3
Chunk：B2-REMOTE-CHUNK-0004
Similarity：0.7161
Preview：B2 遥控器使用手册
tics
技术规格
参数
规格
备注
充电电压
5.0V
充电电流
700mA
锂电池容量
780mAh
通信方式
数传模块，蓝牙
oics
运行时间
5h
遥控距离
100m 以上
空旷环境
Ur
安装摇杆
Step1：取出摇杆。如同所示，用右手将遥控器平稳缓慢的拉出，取出收纳槽当中的2个摇杆。
SELEOT
STNT
Step2：安装摇杆。如图所示，按照顺时针方向，将摇杆固定在遥控器上，拧紧。
Unitree

Document Hit@1：False
Document Hit@4：True
Evidence Hit@4：Yes
Cross-product contamination：True
Retrieval latency_ms：34.68
Notes：Top4 includes a product outside the expected product set.

## S-004

Category：Grounded

Question：B2 电池首次使用前有什么要求？

Expected Documents：宇树_B2电池与充电器使用说明_中文版.pdf
Expected Products：B2 电池与充电器

Rank 1
Document：宇树_B2电池与充电器使用说明_中文版.pdf
Product：B2 电池与充电器
Section：第 2 页（页级/段落 fallback）
Section Path：第 2 页（页级/段落 fallback）
Page：2 - 2
Chunk：B2-BATTERY-CHUNK-0002
Similarity：0.6673
Preview：B2电池&充电器使用手册
电池
obotics
简介
电池是专门为B2四足机器人设计的一款带有充放电管理功能的电池。该款电池采用高性能电芯，并使用
CS
宇树科技Unitree自主开发的先进电池管理系统(BMS)为 B2 四足机器人提供强劲的电力。
Unit
243.00
96.00
337.00
A
●首次使用电池前，务必将电池充满！
部件名称
[]
[1] 电源开关键
[2] LED 灯
[2]
[3] 提带
.
-[1]
[4]

Rank 2
Document：宇树_B2电池与充电器使用说明_中文版.pdf
Product：B2 电池与充电器
Section：第 12 页（页级/段落 fallback）
Section Path：第 12 页（页级/段落 fallback）
Page：12 - 12
Chunk：B2-BATTERY-CHUNK-0019
Similarity：0.6588
Preview：B2 电池&充电器使用手册
tics
注意事项
1. 严禁使用非 Unitree 官方提供的充电器进行充电。
2. 接触式充电器理想工作环境温度为 5℃-40℃，相对湿度≤95%，大气压力 70~106Kpa。
3. 使用接触式充电器充电时，上电后，请勿触摸充电板电极！！！表面请勿放置导电等金属物品。
4. 充电板有正反极性，充电时请将头部按照面贴箭头方向，请勿反冲！！！
5.使用时请确保充电板表面和接口无水滴，周边空旷无障碍物。
在使

Rank 3
Document：宇树_B2电池与充电器使用说明_中文版.pdf
Product：B2 电池与充电器
Section：第 10 页（页级/段落 fallback）
Section Path：第 10 页（页级/段落 fallback）
Page：10 - 10
Chunk：B2-BATTERY-CHUNK-0013
Similarity：0.6286
Preview：B2 电池&充电器使用手册
tics
电池安全使用指引
不正确地使用，充电或存储电池包可能会导致火灾或物权和人身伤害。请务必参照如下安全说明使用电池。
● 推荐使用
1. 每次使用之前，确保电池包有足够的电量。
2. 在使用、移动或者充电时，请小心电池和充电插头，以免被外力损坏。
3. 当电池包电量低于两格时，应尽快停止使用机器人，更换新电池包或者对电池包进行充电。
otics
5. 严禁使电池包接触任何液体，请勿将电池包浸入液体中或将

Rank 4
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 11 页（页级/段落 fallback）
Section Path：第 11 页（页级/段落 fallback）
Page：11 - 11
Chunk：B2-MANUAL-CHUNK-0021
Similarity：0.6269
Preview：tics
开机前准备
(1) 安装电池包
将 B2放在平坦的地面上，将电池包从机器人侧面插入电池槽，注意安装方向，防呆接口朝上，如无法完全
插入电池包，请调整电池包方向，不要强行按压，以免损坏电池接口和卡扣，当听到“咔哒~”声，电池包安装
完成。请确保卡扣卡到位！
tics
(2) 机身摆放（重要步骤！！！）
卧式开机：请确保开机运行前机器人放置在平整地面上，机器人腹部支撑垫需平贴地面，机身水平无倾斜
趴在地面，机器人小腿呈完全收起状态

Document Hit@1：True
Document Hit@4：True
Evidence Hit@4：Yes
Cross-product contamination：True
Retrieval latency_ms：44.51
Notes：Top4 includes a product outside the expected product set.

## S-005

Category：Grounded

Question：第一次启动 KIRA B 50 之前需要提前准备什么？

Expected Documents：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Expected Products：KIRA B 50

Rank 1
Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Product：KIRA B 50
Section：第 1 页
Section Path：第 1 页
Page：1 - 1
Chunk：KIRA-B50-CHUNK-0001
Similarity：0.5462
Preview：KIRA B 50
KIRA B 50
59802530 (02/24)
ZH


Rank 2
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 11 页（页级/段落 fallback）
Section Path：第 11 页（页级/段落 fallback）
Page：11 - 11
Chunk：B2-MANUAL-CHUNK-0021
Similarity：0.5404
Preview：tics
开机前准备
(1) 安装电池包
将 B2放在平坦的地面上，将电池包从机器人侧面插入电池槽，注意安装方向，防呆接口朝上，如无法完全
插入电池包，请调整电池包方向，不要强行按压，以免损坏电池接口和卡扣，当听到“咔哒~”声，电池包安装
完成。请确保卡扣卡到位！
tics
(2) 机身摆放（重要步骤！！！）
卧式开机：请确保开机运行前机器人放置在平整地面上，机器人腹部支撑垫需平贴地面，机身水平无倾斜
趴在地面，机器人小腿呈完全收起状态

Rank 3
Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Product：KIRA B 50
Section：运行
Section Path：运行
Page：7 - 8
Chunk：KIRA-B50-CHUNK-0012
Similarity：0.5318
Preview：运行
危险
在调试前，请按照“检查设备”一章所述检查本设备。
危险
请遵守在“自动运行规定”一章中描述的自动运行规定。
危险
在危险区域（如加油站）使用设备时要注意相关的安全规定。
危险
禁止在有爆炸危险的区域运行设备。
危险
切勿喷洒和吸入爆炸性液体、易燃气体、爆炸性粉尘以及未稀释的酸和溶剂。其中包括汽油、油漆稀释剂或取暖油，它们与吸
入空气混合后会形成爆炸性蒸气或混合物，此外还包括丙酮、未稀释的酸和溶剂，因为它们会侵蚀设备上使用的材

Rank 4
Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Product：KIRA B 50
Section：启动条件
Section Path：启动条件
Page：21 - 22
Chunk：KIRA-B50-CHUNK-0046
Similarity：0.5259
Preview：启动条件
在自动模式下播放路线之前，请注意以下几点：
执行清洁工作的工作负荷是否足够低，或者应当在正常营业时间之外执行清洁？
清水箱已满？
污水箱已空？
设备蓄电池已充电？
提示
请确保智能填充 (Smart Fill) 功能起点和终点必须相同。为此请使用屏幕。在这里通过一个圆圈标记一条路线的起点。
将场地划分为无障碍物的区域。否则可能会导致该场地无法清洁。
在一条路线期间允许多次智能填充 (Smart Fill)。
请避免铺设地毯的地

Document Hit@1：True
Document Hit@4：True
Evidence Hit@4：Yes
Cross-product contamination：True
Retrieval latency_ms：28.53
Notes：Top4 includes a product outside the expected product set.

## S-006

Category：Grounded

Question：B2 的手柄快没电了，应该怎么补电？

Expected Documents：宇树_B2遥控器使用说明_中文版.pdf
Expected Products：B2 遥控器

Rank 1
Document：宇树_B2遥控器使用说明_中文版.pdf
Product：B2 遥控器
Section：第 5 页（页级/段落 fallback）
Section Path：第 5 页（页级/段落 fallback）
Page：5 - 5
Chunk：B2-REMOTE-CHUNK-0006
Similarity：0.6394
Preview：B2遥控器使用手册
tics
音效/震动开关
●关闭振动/声音：快速按下F1按钮3次，关闭振动/声音。
●开启振动/声音：快速按下F1按钮3次，开启振动/声音。
Unitree
START
Robotics
快按3次F1
●修改遥控器反馈功能后，默认是不保存的，如果需要下次开机生效，则按住F1进行关机操作保存当前模式。
遥控器充电
当遥控器电量指示灯显示低电量时，应将遥控器连接充电器，如下图所示：
交流电源
100-240V
USB 充

Rank 2
Document：宇树_B2电池与充电器使用说明_中文版.pdf
Product：B2 电池与充电器
Section：第 8 页（页级/段落 fallback）
Section Path：第 8 页（页级/段落 fallback）
Page：8 - 8
Chunk：B2-BATTERY-CHUNK-0010
Similarity：0.6347
Preview：B2电池&充电器使用手册
tics
接触式充电器
1. 充电前检查：在每次充电前，请检查 B2机身底部的充电电极是否有异物遮挡，以及充电板充电电极表
面是否有异物遮挡。请使用干燥抹布擦拭充电电极表面，确保充电过程中良好接触。
2. 连接电源：将 B2 接触式充电器放置在空旷室内，先将锂电池充电器接入输入交流电源，然后连接接触
式充电板电源接口，如下图所示。
交流电源
①
110-220V
Un
☐。
②
ee Rdbotics
接触式充

Rank 3
Document：宇树_B2遥控器使用说明_中文版.pdf
Product：B2 遥控器
Section：第 10 页（页级/段落 fallback）
Section Path：第 10 页（页级/段落 fallback）
Page：10 - 10
Chunk：B2-REMOTE-CHUNK-0012
Similarity：0.6201
Preview：ics
遥控器摇杆校准
手持遥控但不要触碰摇杆，按下遥控上按键F1和F3并同时松开，此时遥控器发出连续“嘀~嘀~”声(1
次/秒)代表已进入校准模式。进入校准模式后将左右摇杆打满舵并旋转数圈，直至“嘀~嘀~”声停止，此时校
准就绪。单按F3一次使校准生效，完成校准。
：●校准摇杆时，校准前请不要触碰摇杆，进入校准模式才可以动摇杆。校准后可通过 App查看校准后的摇杆状态。
Ics
开启/关闭遥控器
开启遥控器：短按电源按键一次，再长按电

Rank 4
Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Product：KIRA B 50
Section：电池没电了
Section Path：电池没电了
Page：104 - 104
Chunk：KIRA-B50-CHUNK-0163
Similarity：0.6191
Preview：电池没电了
原因:
排除故障:
1. 立即为电池充电。

Document Hit@1：True
Document Hit@4：True
Evidence Hit@4：Yes
Cross-product contamination：True
Retrieval latency_ms：26.44
Notes：Top4 includes a product outside the expected product set.

## S-007

Category：Grounded

Question：B2 机器启动之前要检查些什么？

Expected Documents：宇树_B2四足机器人用户手册_中文版.pdf
Expected Products：B2 四足机器人

Rank 1
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 11 页（页级/段落 fallback）
Section Path：第 11 页（页级/段落 fallback）
Page：11 - 11
Chunk：B2-MANUAL-CHUNK-0021
Similarity：0.6818
Preview：tics
开机前准备
(1) 安装电池包
将 B2放在平坦的地面上，将电池包从机器人侧面插入电池槽，注意安装方向，防呆接口朝上，如无法完全
插入电池包，请调整电池包方向，不要强行按压，以免损坏电池接口和卡扣，当听到“咔哒~”声，电池包安装
完成。请确保卡扣卡到位！
tics
(2) 机身摆放（重要步骤！！！）
卧式开机：请确保开机运行前机器人放置在平整地面上，机器人腹部支撑垫需平贴地面，机身水平无倾斜
趴在地面，机器人小腿呈完全收起状态

Rank 2
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 16 页（页级/段落 fallback）
Section Path：第 16 页（页级/段落 fallback）
Page：16 - 16
Chunk：B2-MANUAL-CHUNK-0029
Similarity：0.6741
Preview：异常情况说明
botics
在使用B2四足机器人时，可能会出现机器人异常的情况。大部分异常情况是可控的（有解决方案），客户
在遇到这些问题时不要慌张，详细阅读下列内容并按步骤解决问题。
如有疑问，可联系宇树 Unitree官方技术支持：support@unitree.cc
● 开机自检不成功
tics
机器人趴在地上开机时，若等待2分钟后机器人未起立，则说明开机自检失败，机器人无法起立，此时需
要按照“开机前检查”和“开机前准备”两个步

Rank 3
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 18 页（页级/段落 fallback）
Section Path：第 18 页（页级/段落 fallback）
Page：18 - 18
Chunk：B2-MANUAL-CHUNK-0036
Similarity：0.6726
Preview：日常保养与维护
botics
整机清洁
1. 清洁
当B2在恶劣环境下（雨天、沙尘、湿地)使用后，请及时清洁机身表面。
tics
清洗机身前请先关闭电源，使用干净的软布对机身进行擦拭，尤其关注多目深度相机是否擦拭干净。清洁
时严禁使用金属刷、砂纸等，以免刮伤零件表面。清洗后，请用软布将机身擦干。擦干后可用风扇或风枪将机
器人表面、关节缝隙处的积水吹干，避免留下水痕。
A
● 注意！B2 整机(含电池包)IP67 级防水，清洁时请勿取下电

Rank 4
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 15 页（页级/段落 fallback）
Section Path：第 15 页（页级/段落 fallback）
Page：15 - 15
Chunk：B2-MANUAL-CHUNK-0027
Similarity：0.6695
Preview：tics
关闭 B2
关机前，请务必确保机器人站立在平整地面上，确保机器人处于静态站立状态（机器人机身位置处于开机
起立后的初始状态，机身水平，手柄无任何操作，静态站立时的状态）。
● 按2次L2+A 键，机器人依次完成关节锁定，卧倒动作；
● 机器人进入卧倒状态后，先短按电源键再长按电源键3秒以上关机。
tics
关机后，请按照机身摆放要求，摆放好机器人大小腿和髋关节位置，为下次开机做准备。若长时间不使用
B2，请及时取出电池包：往外

Document Hit@1：True
Document Hit@4：True
Evidence Hit@4：Yes
Cross-product contamination：False
Retrieval latency_ms：9.45
Notes：None.

## S-008

Category：Grounded

Question：B2 用户手册里有哪些安全使用注意事项？

Expected Documents：宇树_B2四足机器人用户手册_中文版.pdf
Expected Products：B2 四足机器人

Rank 1
Document：宇树_B2电池与充电器使用说明_中文版.pdf
Product：B2 电池与充电器
Section：第 12 页（页级/段落 fallback）
Section Path：第 12 页（页级/段落 fallback）
Page：12 - 12
Chunk：B2-BATTERY-CHUNK-0019
Similarity：0.6311
Preview：B2 电池&充电器使用手册
tics
注意事项
1. 严禁使用非 Unitree 官方提供的充电器进行充电。
2. 接触式充电器理想工作环境温度为 5℃-40℃，相对湿度≤95%，大气压力 70~106Kpa。
3. 使用接触式充电器充电时，上电后，请勿触摸充电板电极！！！表面请勿放置导电等金属物品。
4. 充电板有正反极性，充电时请将头部按照面贴箭头方向，请勿反冲！！！
5.使用时请确保充电板表面和接口无水滴，周边空旷无障碍物。
在使

Rank 2
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 4 页（页级/段落 fallback）
Section Path：第 4 页（页级/段落 fallback）
Page：4 - 4
Chunk：B2-MANUAL-CHUNK-0006
Similarity：0.6051
Preview：安全须知
botics
B2是一款具备全天候作业、强劲负载与扩展空间、多维感知、全场景覆盖、强劲算力与精准洞察等特点，
面向行业级应用的四足机器人，可以为您提供更高效、智能的解决方案。
1. 本产品并非玩具，不适合未满18岁的人士使用。请勿让儿童接触，在有儿童出现的场景操作时务必
1cs
特别小心注意。
O
2. 您有义务知悉您所在区域的法律，并遵守相关法律和法规。
法，使机器人表现出卓越的运动性能。本手册也是老玩家需时常查阅的章节，老

Rank 3
Document：宇树_B2电池与充电器使用说明_中文版.pdf
Product：B2 电池与充电器
Section：第 10 页（页级/段落 fallback）
Section Path：第 10 页（页级/段落 fallback）
Page：10 - 10
Chunk：B2-BATTERY-CHUNK-0013
Similarity：0.5947
Preview：B2 电池&充电器使用手册
tics
电池安全使用指引
不正确地使用，充电或存储电池包可能会导致火灾或物权和人身伤害。请务必参照如下安全说明使用电池。
● 推荐使用
1. 每次使用之前，确保电池包有足够的电量。
2. 在使用、移动或者充电时，请小心电池和充电插头，以免被外力损坏。
3. 当电池包电量低于两格时，应尽快停止使用机器人，更换新电池包或者对电池包进行充电。
otics
5. 严禁使电池包接触任何液体，请勿将电池包浸入液体中或将

Rank 4
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 17 页（页级/段落 fallback）
Section Path：第 17 页（页级/段落 fallback）
Page：17 - 17
Chunk：B2-MANUAL-CHUNK-0035
Similarity：0.593
Preview：10.关于IP67等级防护：运行前，请先确定电池接口、电池仓接口、电池表面、电池仓表面干燥无水，
Uni
再将电池插入机身。下水/雨水天气作业后，请将机身表面擦拭干净。
11.运动时禁止触碰机器人！关节处小心夹手，如膝关节处。
A
●奔跑最大速度6m/s，在特殊配置下实现，实际为了安全会有所限速。
©2023 宇树科技版权所有
16
Unitree

Document Hit@1：False
Document Hit@4：True
Evidence Hit@4：Needs Manual Review
Cross-product contamination：True
Retrieval latency_ms：26.67
Notes：Top4 includes a product outside the expected product set.

## S-009

Category：Grounded

Question：KIRA B 50 在使用和维护过程中有哪些需要注意的事项？

Expected Documents：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Expected Products：KIRA B 50

Rank 1
Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Product：KIRA B 50
Section：第 1 页
Section Path：第 1 页
Page：1 - 1
Chunk：KIRA-B50-CHUNK-0001
Similarity：0.6179
Preview：KIRA B 50
KIRA B 50
59802530 (02/24)
ZH


Rank 2
Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Product：KIRA B 50
Section：维护间隔
Section Path：维护间隔
Page：85 - 86
Chunk：KIRA-B50-CHUNK-0119
Similarity：0.5895
Preview：维护间隔
运输期间用于捆扎的孔眼
1
小心
忽略重量
受伤与损坏危险
运输和存放时注意设备的重量。
危险
无意中启动设备，接触导电部件
受伤危险，触电
在执行任何工作之前，请将设备与对接站断开，或拔出电源插头。

提示：如果有一个对接站，则会自动执行标有“##”的维护工作。

Rank 3
Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Product：KIRA B 50
Section：每周
Section Path：每周
Page：86 - 86
Chunk：KIRA-B50-CHUNK-0121
Similarity：0.5386
Preview：每周
1. 使用湿微纤维抹布清洁传感器。如有必要，请额外使用玻璃清洁剂。
2. ## 定期使用时，至少每周给蓄电池完全充电一次并且没有间断。

Rank 4
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 18 页（页级/段落 fallback）
Section Path：第 18 页（页级/段落 fallback）
Page：18 - 18
Chunk：B2-MANUAL-CHUNK-0036
Similarity：0.5362
Preview：日常保养与维护
botics
整机清洁
1. 清洁
当B2在恶劣环境下（雨天、沙尘、湿地)使用后，请及时清洁机身表面。
tics
清洗机身前请先关闭电源，使用干净的软布对机身进行擦拭，尤其关注多目深度相机是否擦拭干净。清洁
时严禁使用金属刷、砂纸等，以免刮伤零件表面。清洗后，请用软布将机身擦干。擦干后可用风扇或风枪将机
器人表面、关节缝隙处的积水吹干，避免留下水痕。
A
● 注意！B2 整机(含电池包)IP67 级防水，清洁时请勿取下电

Document Hit@1：True
Document Hit@4：True
Evidence Hit@4：Needs Manual Review
Cross-product contamination：True
Retrieval latency_ms：27.09
Notes：Top4 includes a product outside the expected product set.

## S-010

Category：Observation

Question：巡检机器人能解决什么问题？

Expected Documents：Observation
Expected Products：Ambiguous

Rank 1
Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Product：KIRA B 50
Section：清洁任务已完成
Section Path：清洁任务已完成
Page：102 - 102
Chunk：KIRA-B50-CHUNK-0153
Similarity：0.5907
Preview：清洁任务已完成
原因:
机器人停了下来，因为它的路径被挡住了。
排除故障:
1. 检查机器人的周围情况。清除路径上的障碍物。

Rank 2
Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Product：KIRA B 50
Section：清洁模块检查
Section Path：清洁模块检查
Page：105 - 105
Chunk：KIRA-B50-CHUNK-0169
Similarity：0.5753
Preview：清洁模块检查
原因:
检查清洁模块是否正常工作。
排除故障:
1. 等待，直到机器人完成对清洁模块的检查。这一过程可能最多需要 30 秒

Rank 3
Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Product：KIRA B 50
Section：机器人离开了指定路径
Section Path：机器人离开了指定路径
Page：102 - 102
Chunk：KIRA-B50-CHUNK-0152
Similarity：0.5697
Preview：机器人离开了指定路径
原因:
排除故障:
1. 机器人成功完成清洁任务。

Rank 4
Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Product：KIRA B 50
Section：日常维护
Section Path：日常维护
Page：24 - 24
Chunk：KIRA-B50-CHUNK-0049
Similarity：0.5468
Preview：日常维护
日常维护包括：
传感器的清洁。
机器整体状态的检修。
开启机器后检查自动驾驶。
此外，操作人员在运行期间应当留在现场。经常检查清洁进度，尤其是对于极长的清洁工作。

Document Hit@1：Observation
Document Hit@4：Observation
Evidence Hit@4：Observation
Cross-product contamination：Observation
Retrieval latency_ms：9.56
Notes：Observation only; no pass/fail conclusion.

## S-011

Category：Observation

Question：B2 的电池和遥控器分别应该怎么充电？

Expected Documents：宇树_B2遥控器使用说明_中文版.pdf；宇树_B2电池与充电器使用说明_中文版.pdf
Expected Products：B2 遥控器；B2 电池与充电器

Rank 1
Document：宇树_B2电池与充电器使用说明_中文版.pdf
Product：B2 电池与充电器
Section：第 8 页（页级/段落 fallback）
Section Path：第 8 页（页级/段落 fallback）
Page：8 - 8
Chunk：B2-BATTERY-CHUNK-0010
Similarity：0.7772
Preview：B2电池&充电器使用手册
tics
接触式充电器
1. 充电前检查：在每次充电前，请检查 B2机身底部的充电电极是否有异物遮挡，以及充电板充电电极表
面是否有异物遮挡。请使用干燥抹布擦拭充电电极表面，确保充电过程中良好接触。
2. 连接电源：将 B2 接触式充电器放置在空旷室内，先将锂电池充电器接入输入交流电源，然后连接接触
式充电板电源接口，如下图所示。
交流电源
①
110-220V
Un
☐。
②
ee Rdbotics
接触式充

Rank 2
Document：宇树_B2遥控器使用说明_中文版.pdf
Product：B2 遥控器
Section：第 3 页（页级/段落 fallback）
Section Path：第 3 页（页级/段落 fallback）
Page：3 - 3
Chunk：B2-REMOTE-CHUNK-0004
Similarity：0.7355
Preview：B2 遥控器使用手册
tics
技术规格
参数
规格
备注
充电电压
5.0V
充电电流
700mA
锂电池容量
780mAh
通信方式
数传模块，蓝牙
oics
运行时间
5h
遥控距离
100m 以上
空旷环境
Ur
安装摇杆
Step1：取出摇杆。如同所示，用右手将遥控器平稳缓慢的拉出，取出收纳槽当中的2个摇杆。
SELEOT
STNT
Step2：安装摇杆。如图所示，按照顺时针方向，将摇杆固定在遥控器上，拧紧。
Unitree

Rank 3
Document：宇树_B2遥控器使用说明_中文版.pdf
Product：B2 遥控器
Section：第 5 页（页级/段落 fallback）
Section Path：第 5 页（页级/段落 fallback）
Page：5 - 5
Chunk：B2-REMOTE-CHUNK-0006
Similarity：0.7269
Preview：B2遥控器使用手册
tics
音效/震动开关
●关闭振动/声音：快速按下F1按钮3次，关闭振动/声音。
●开启振动/声音：快速按下F1按钮3次，开启振动/声音。
Unitree
START
Robotics
快按3次F1
●修改遥控器反馈功能后，默认是不保存的，如果需要下次开机生效，则按住F1进行关机操作保存当前模式。
遥控器充电
当遥控器电量指示灯显示低电量时，应将遥控器连接充电器，如下图所示：
交流电源
100-240V
USB 充

Rank 4
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 9 页（页级/段落 fallback）
Section Path：第 9 页（页级/段落 fallback）
Page：9 - 9
Chunk：B2-MANUAL-CHUNK-0017
Similarity：0.7243
Preview：tics
遥控器充电
当遥控器电量指示灯显示低电量时，应将遥控器连接充电器，如下图所示：
R
④
④
交流电源
100-240V
USB 充电器
③
③
USB-Type C 线
otics
0
oo
Unitr
1. 请使用官方 USB 充电器。如不使用官方充电器，推荐使用符合 FCC/CE 标准，规格为 5V/2A 的 USB
充电器。
2. 给遥控器充电前，确保遥控器处于关闭状态。
3. 充电状态下电源指示灯会按1Hz（1秒/次）

Document Hit@1：True
Document Hit@4：True
Evidence Hit@4：Observation
Cross-product contamination：True
Retrieval latency_ms：28.81
Notes：Top4 includes a product outside the expected product set. Observation only; no pass/fail conclusion.

## S-012

Category：Observation

Question：MacBook 怎么开机？

Expected Documents：Observation
Expected Products：Out of Domain

Rank 1
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 11 页（页级/段落 fallback）
Section Path：第 11 页（页级/段落 fallback）
Page：11 - 11
Chunk：B2-MANUAL-CHUNK-0021
Similarity：0.5866
Preview：tics
开机前准备
(1) 安装电池包
将 B2放在平坦的地面上，将电池包从机器人侧面插入电池槽，注意安装方向，防呆接口朝上，如无法完全
插入电池包，请调整电池包方向，不要强行按压，以免损坏电池接口和卡扣，当听到“咔哒~”声，电池包安装
完成。请确保卡扣卡到位！
tics
(2) 机身摆放（重要步骤！！！）
卧式开机：请确保开机运行前机器人放置在平整地面上，机器人腹部支撑垫需平贴地面，机身水平无倾斜
趴在地面，机器人小腿呈完全收起状态

Rank 2
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 11 页（页级/段落 fallback）
Section Path：第 11 页（页级/段落 fallback）
Page：11 - 11
Chunk：B2-MANUAL-CHUNK-0022
Similarity：0.5309
Preview：后等待2分钟，机器人自动站立，机身与地面平行，即开机成功。
短按+长按3秒以上
Robotics
Unitree
A
●若开机失败，请仔细检查机身摆放。
●大小腿靠外伸或小腿靠内被压住都可能导致B2开机失败。
● 运动关节处小心夹手，请小心谨慎!
● B2开机成功后会自动站立，请保持一定的安全距离！开机后默认进去AI运控模式。
© 2023
宇树科技版权所有
10
Un

Rank 3
Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf
Product：KIRA B 50
Section：一般提示
Section Path：一般提示
Page：2 - 2
Chunk：KIRA-B50-CHUNK-0003
Similarity：0.516
Preview：一般提示
在您第一次使用设备之前，请先阅读原厂操作说明书并遵守。
为后续使用或者为后续的车主保管好操作说明书。
在第一次调试设备之前，请完整阅读操作说明书，可以在设备显示屏上查阅本操作说明书，也可以下载到智能手机上。
本设备可能包含根据开源授权获得许可和/或由第三方开发的组件。可以在设备的触摸屏上显示设备中存在的开源软件组件的列表
（包括版权所有者和许可条款）。若要查看，请打开主菜单，调用设置并打开系统信息。


Rank 4
Document：宇树_B2四足机器人用户手册_中文版.pdf
Product：B2 四足机器人
Section：第 16 页（页级/段落 fallback）
Section Path：第 16 页（页级/段落 fallback）
Page：16 - 16
Chunk：B2-MANUAL-CHUNK-0030
Similarity：0.5152
Preview：● App 连接异常
nitr
若采用 AP直连模式，可检查手机是否连上B2发出的Ap热点。若热点配置失败，请确保设置的热点名称
没有特殊符号和空格，确保机器狗、手机二者靠近后，重启机器狗和App再尝试连接。
若采用Wi-Fi连接模式，可检查所连接Wi-Fi网络是否正常，能连上外网。
●如何在遥控模块失效时关闭机器人
当遇到由于遥控模块失效(如遥控器、手机电量耗尽等原因)导致的无法使用遥控模块使机器人趴地待机。
只能采用按电池电源键强制

Document Hit@1：Observation
Document Hit@4：Observation
Evidence Hit@4：Observation
Cross-product contamination：Observation
Retrieval latency_ms：35.4
Notes：Observation only; no pass/fail conclusion.
