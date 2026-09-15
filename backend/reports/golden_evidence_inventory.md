# Golden Evidence Inventory

本报告仅盘点正式 PDF 的真实证据，不是 Golden Dataset，未修改 Evaluation、Retrieval、Chunking、Agent 或前端。

## 汇总

- 总 Evidence Topic 数：40
- 产品覆盖：
  - B2 四足机器人：8
  - B2 电池与充电器：8
  - B2 遥控器：8
  - KIRA B 50：16
- Knowledge Type：
  - charging：4
  - maintenance：7
  - operation：11
  - safety：4
  - setup：7
  - specification：2
  - troubleshooting：3
  - usage_limit：2
- Question Potential：
  - multi_chunk：7
  - multi_document：0
  - single：33

## 发现的重复知识 / 多来源 Evidence

### EV-B2R-001 · 遥控器低电量充电

主来源：宇树_B2遥控器使用说明_中文版.pdf P.5。
- 可接受来源：宇树_B2四足机器人用户手册_中文版.pdf P.9–9（B2-MANUAL-CHUNK-0017）
- 可接受来源：宇树_B2遥控器使用说明_中文版.pdf P.10–10（B2-REMOTE-CHUNK-0012、B2-REMOTE-CHUNK-0013）

仅合并各来源一致步骤；遥控器 R1/R3 的“充满”指示存在版本差异，未写入共同结论。

### EV-B2B-006 · 插入式充电流程

主来源：宇树_B2电池与充电器使用说明_中文版.pdf P.7。
- 可接受来源：宇树_B2四足机器人用户手册_中文版.pdf P.8–8（B2-MANUAL-CHUNK-0015、B2-MANUAL-CHUNK-0016）

仅合并各来源一致步骤；遥控器 R1/R3 的“充满”指示存在版本差异，未写入共同结论。

## Evidence Topics

## KIRA B 50（16）

### EV-KIRA-001 · 首次使用前阅读操作说明

- Knowledge Type：setup
- Question Potential：single
- Evidence Summary：为后续使用或者为后续的车主保管好操作说明书。；在第一次调试设备之前，请完整阅读操作说明书，可以在设备显示屏上查阅本操作说明书，也可以下载到智能手机上。；本设备可能包含根据开源授权获得许可和/或由第三方开发的组件。可以在设备的触摸屏上显示设备中存在的开源软件组件的列表
- Key Points：
  - 为后续使用或者为后续的车主保管好操作说明书。
  - 在第一次调试设备之前，请完整阅读操作说明书，可以在设备显示屏上查阅本操作说明书，也可以下载到智能手机上。
  - 本设备可能包含根据开源授权获得许可和/或由第三方开发的组件。可以在设备的触摸屏上显示设备中存在的开源软件组件的列表
  - （包括版权所有者和许可条款）。若要查看，请打开主菜单，调用设置并打开系统信息。

- Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001）
- Page：2–2
- Section：一般提示
- Chunk：KIRA-B50-CHUNK-0003

<details><summary>Chunk Text</summary>

<pre>
[KIRA-B50-CHUNK-0003]
一般提示
在您第一次使用设备之前，请先阅读原厂操作说明书并遵守。
为后续使用或者为后续的车主保管好操作说明书。
在第一次调试设备之前，请完整阅读操作说明书，可以在设备显示屏上查阅本操作说明书，也可以下载到智能手机上。
本设备可能包含根据开源授权获得许可和/或由第三方开发的组件。可以在设备的触摸屏上显示设备中存在的开源软件组件的列表
（包括版权所有者和许可条款）。若要查看，请打开主菜单，调用设置并打开系统信息。

</pre>

</details>

### EV-KIRA-002 · 操作前的安全前提

- Knowledge Type：safety
- Question Potential：single
- Evidence Summary：在护罩和所有盖子均已关闭的情况下，才能操作本设备。；按下紧急停机按钮，在紧急情况下立即停用。；只能在不超过最大允许坡度的场地上操作设备（参见小节“技术数据”）。
- Key Points：
  - 在护罩和所有盖子均已关闭的情况下，才能操作本设备。
  - 按下紧急停机按钮，在紧急情况下立即停用。
  - 只能在不超过最大允许坡度的场地上操作设备（参见小节“技术数据”）。
  - 在对接过程中，请勿将任何身体部位伸入对接站和设备之间。

- Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001）
- Page：3–3
- Section：安全提示
- Chunk：KIRA-B50-CHUNK-0006

<details><summary>Chunk Text</summary>

<pre>
[KIRA-B50-CHUNK-0006]
安全提示
首次使用本设备前，请注意仔细阅读本操作说明书以及完整操作说明书（设备显示屏中），然后按其操作。
在护罩和所有盖子均已关闭的情况下，才能操作本设备。
按下紧急停机按钮，在紧急情况下立即停用。
只能在不超过最大允许坡度的场地上操作设备（参见小节“技术数据”）。
在对接过程中，请勿将任何身体部位伸入对接站和设备之间。
</pre>

</details>

### EV-KIRA-003 · 危险环境与物质限制

- Knowledge Type：safety
- Question Potential：single
- Evidence Summary：请遵守在“自动运行规定”一章中描述的自动运行规定。；在危险区域（如加油站）使用设备时要注意相关的安全规定。；禁止在有爆炸危险的区域运行设备。
- Key Points：
  - 请遵守在“自动运行规定”一章中描述的自动运行规定。
  - 在危险区域（如加油站）使用设备时要注意相关的安全规定。
  - 禁止在有爆炸危险的区域运行设备。
  - 切勿喷洒和吸入爆炸性液体、易燃气体、爆炸性粉尘以及未稀释的酸和溶剂。其中包括汽油、油漆稀释剂或取暖油，它们与吸

- Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001）
- Page：7–8
- Section：运行
- Chunk：KIRA-B50-CHUNK-0012

<details><summary>Chunk Text</summary>

<pre>
[KIRA-B50-CHUNK-0012]
运行
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
入空气混合后会形成爆炸性蒸气或混合物，此外还包括丙酮、未稀释的酸和溶剂，因为它们会侵蚀设备上使用的材料。
危险
不得吸入易燃或闷烧的物体。
警告
不得使用设备抽吸人或动物。
警告
请勿在湿滑地面上使用本设备。
警告

在倾斜表面上，请勿超过操作说明书中指定的侧向和行进方向的倾斜角度值。
警告
穿着紧身的衣服，以免被旋转的零件卷入（不打领带，不穿长裙等）。
小心
检查设备和附件，特别是电源连接导线和延长线缆，在每次运行前都要检查其是否状态正常以及是否具有运行安全性。如有损
坏，拔下电源插头，不得使用设备。
</pre>

</details>

### EV-KIRA-004 · 示教路线环境准备

- Knowledge Type：setup
- Question Potential：single
- Evidence Summary：清除设备无法吸取的污物（如胶带、托盘上的碎片和透明膜），因为这些可能会损坏设备。；请确保路线上不存在季节性陈列物，以及其他非永久性障碍物。；请在待清洁场地的工作负荷最低时，示教新路线。最好避开正常营业和工作时间。
- Key Points：
  - 清除设备无法吸取的污物（如胶带、托盘上的碎片和透明膜），因为这些可能会损坏设备。
  - 请确保路线上不存在季节性陈列物，以及其他非永久性障碍物。
  - 请在待清洁场地的工作负荷最低时，示教新路线。最好避开正常营业和工作时间。

- Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001）
- Page：17–17
- Section：环境准备工作
- Chunk：KIRA-B50-CHUNK-0036

<details><summary>Chunk Text</summary>

<pre>
[KIRA-B50-CHUNK-0036]
环境准备工作
清除设备无法吸取的污物（如胶带、托盘上的碎片和透明膜），因为这些可能会损坏设备。
请确保路线上不存在季节性陈列物，以及其他非永久性障碍物。
请在待清洁场地的工作负荷最低时，示教新路线。最好避开正常营业和工作时间。
</pre>

</details>

### EV-KIRA-005 · 自动路线空间限制

- Knowledge Type：usage_limit
- Question Potential：single
- Evidence Summary：墙壁与设备右侧之间的理想距；单向运行的最小通道宽度；掉头时的最小通道宽度
- Key Points：
  - 墙壁与设备右侧之间的理想距
  - 单向运行的最小通道宽度
  - 掉头时的最小通道宽度
  - 到跌落边缘的最小距离（并行

- Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001）
- Page：19–19
- Section：到危险点的距离和设备的限制
- Chunk：KIRA-B50-CHUNK-0041

<details><summary>Chunk Text</summary>

<pre>
[KIRA-B50-CHUNK-0041]
到危险点的距离和设备的限制
墙壁与设备右侧之间的理想距
离
10
cm
单向运行的最小通道宽度
1.05
m
掉头时的最小通道宽度
1.7
m
到跌落边缘的最小距离（并行
行驶）
1.5
m
为了让设备在自动模式下执行所示教的路线，必须遵守规定的极限值。可以考虑装入边刷，以保持边缘距离。
</pre>

</details>

### EV-KIRA-006 · 自动路线启动条件

- Knowledge Type：operation
- Question Potential：single
- Evidence Summary：执行清洁工作的工作负荷是否足够低，或者应当在正常营业时间之外执行清洁？；清水箱已满？；污水箱已空？
- Key Points：
  - 执行清洁工作的工作负荷是否足够低，或者应当在正常营业时间之外执行清洁？
  - 清水箱已满？
  - 污水箱已空？
  - 设备蓄电池已充电？

- Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001）
- Page：21–22
- Section：启动条件
- Chunk：KIRA-B50-CHUNK-0046

<details><summary>Chunk Text</summary>

<pre>
[KIRA-B50-CHUNK-0046]
启动条件
在自动模式下播放路线之前，请注意以下几点：
执行清洁工作的工作负荷是否足够低，或者应当在正常营业时间之外执行清洁？
清水箱已满？
污水箱已空？
设备蓄电池已充电？
提示
请确保智能填充 (Smart Fill) 功能起点和终点必须相同。为此请使用屏幕。在这里通过一个圆圈标记一条路线的起点。
将场地划分为无障碍物的区域。否则可能会导致该场地无法清洁。
在一条路线期间允许多次智能填充 (Smart Fill)。
请避免铺设地毯的地面。

待清洁场地上的粗大污染物已清除？
环境已清理？
场地上不存在新的大型障碍物？
将设备置于正确的位置代码前方？
</pre>

</details>

### EV-KIRA-007 · 日常维护内容

- Knowledge Type：maintenance
- Question Potential：single
- Evidence Summary：传感器的清洁。；机器整体状态的检修。；开启机器后检查自动驾驶。
- Key Points：
  - 传感器的清洁。
  - 机器整体状态的检修。
  - 开启机器后检查自动驾驶。
  - 此外，操作人员在运行期间应当留在现场。经常检查清洁进度，尤其是对于极长的清洁工作。

- Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001）
- Page：24–24
- Section：日常维护
- Chunk：KIRA-B50-CHUNK-0049

<details><summary>Chunk Text</summary>

<pre>
[KIRA-B50-CHUNK-0049]
日常维护
日常维护包括：
传感器的清洁。
机器整体状态的检修。
开启机器后检查自动驾驶。
此外，操作人员在运行期间应当留在现场。经常检查清洁进度，尤其是对于极长的清洁工作。
</pre>

</details>

### EV-KIRA-008 · 开机前设备检查

- Knowledge Type：maintenance
- Question Potential：single
- Evidence Summary：2. 检查紧急停机按钮的功能。；3. 检查两个安全开关的功能（在手动运行的过程中，当两个安全开关均已释放时，设备是否制动？）；4. 检查传感器是否脏污，必要时清洁。
- Key Points：
  - 2. 检查紧急停机按钮的功能。
  - 3. 检查两个安全开关的功能（在手动运行的过程中，当两个安全开关均已释放时，设备是否制动？）
  - 4. 检查传感器是否脏污，必要时清洁。
  - 5. 重新启动设备。

- Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001）
- Page：46–46
- Section：检查设备
- Chunk：KIRA-B50-CHUNK-0084

<details><summary>Chunk Text</summary>

<pre>
[KIRA-B50-CHUNK-0084]
检查设备
1. 检查设备是否密封。
2. 检查紧急停机按钮的功能。
3. 检查两个安全开关的功能（在手动运行的过程中，当两个安全开关均已释放时，设备是否制动？）
4. 检查传感器是否脏污，必要时清洁。
5. 重新启动设备。
6. 检查传感器的功能（设备是否检测到障碍物？）
</pre>

</details>

### EV-KIRA-009 · 接通设备步骤

- Knowledge Type：operation
- Question Potential：single
- Evidence Summary：2. 按下启动键。；3. 请等待，直到触摸屏上出现登录界面。；将两个间隔滚轮设置为相同的高度。
- Key Points：
  - 2. 按下启动键。
  - 3. 请等待，直到触摸屏上出现登录界面。
  - 将两个间隔滚轮设置为相同的高度。
  - 损坏或有缺陷的设备可能会在运行过程中导致事故。

- Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001）
- Page：46–47
- Section：接通设备
- Chunk：KIRA-B50-CHUNK-0085

<details><summary>Chunk Text</summary>

<pre>
[KIRA-B50-CHUNK-0085]
接通设备
1. 通过旋转解锁紧急停机按钮。
2. 按下启动键。
设备启动。
3. 请等待，直到触摸屏上出现登录界面。
提示
将两个间隔滚轮设置为相同的高度。
警告
事故危险
损坏或有缺陷的设备可能会在运行过程中导致事故。
请在使用前检查设备，如有任何损坏或故障，请向负责人报告。
如果设备损坏或出现功能故障，请勿使用。
危险
由于安全开关故障而导致的事故危险
如果一个或两个安全开关不能可靠地返回未操作的位置，请立即停止设备。

主管：可用设备的全部功能，并拥有所有用户权限。
服务：只适用于客户服务。
操作人员：通过 主管 所分配的权限定义功能范围，可利用该功能范围。
4. 创建一个新用户资料。
5. 指定密码。
在主菜单中显示可执行的功能。
新用户
1
主管
2
服务
3
操作人员
4

</pre>

</details>

### EV-KIRA-010 · 手动清洁操作

- Knowledge Type：operation
- Question Potential：single
- Evidence Summary：1. 在触摸屏上选择功能“手动清洁”。；执行维护工作；完成对接，开始自动运行
- Key Points：
  - 1. 在触摸屏上选择功能“手动清洁”。
  - 执行维护工作
  - 完成对接，开始自动运行
  - 隐藏/显示菜单项“刷子功率和抽吸功率”

- Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001）
- Page：57–58
- Section：手动模式
- Chunk：KIRA-B50-CHUNK-0093

<details><summary>Chunk Text</summary>

<pre>
[KIRA-B50-CHUNK-0093]
手动模式
在手动运行的过程中，由操作人员在待清洁的场地上引导该设备。
1. 在触摸屏上选择功能“手动清洁”。
执行维护工作
1
完成对接
2
完成对接，开始自动运行
3
隐藏/显示菜单项“刷子功率和抽吸功率”
1
电池充电状态
2
清洁剂计量
3
抽吸功率
4
刷子功率
5

2. 操作并握紧安全开关。
3. 将设备推到使用地。
4. 松开安全开关。
5. 选择水量、清洁剂计量、刷子功率和抽吸功率的所需设置。
6. 激活所需功能（抽吸、清洁头、边刷）。
已激活的功能用绿色标记。
7. 操作并握紧安全开关。
8. 将设备推到待清洁的场地上。
</pre>

</details>

### EV-KIRA-011 · 结束清洁顺序

- Knowledge Type：operation
- Question Potential：single
- Evidence Summary：2. 继续行驶一小段线路，抽吸残余水分。；3. 停用抽吸装置。
- Key Points：
  - 2. 继续行驶一小段线路，抽吸残余水分。
  - 3. 停用抽吸装置。

- Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001）
- Page：58–58
- Section：结束清洁
- Chunk：KIRA-B50-CHUNK-0094

<details><summary>Chunk Text</summary>

<pre>
[KIRA-B50-CHUNK-0094]
结束清洁
1. 停用清洁头和边刷。
2. 继续行驶一小段线路，抽吸残余水分。
3. 停用抽吸装置。
</pre>

</details>

### EV-KIRA-012 · 无对接站排放污水

- Knowledge Type：maintenance
- Question Potential：single
- Evidence Summary：不含对接站：；1. 打开设备舱的门。；已清洁的面积，以平方米为单位
- Key Points：
  - 不含对接站：
  - 1. 打开设备舱的门。
  - 已清洁的面积，以平方米为单位
  - 清洁线路的长度

- Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001）
- Page：82–83
- Section：排放污水
- Chunk：KIRA-B50-CHUNK-0114

<details><summary>Chunk Text</summary>

<pre>
[KIRA-B50-CHUNK-0114]
排放污水
结合对接站运行时，会自动排空污水箱。
不含对接站：
1. 打开设备舱的门。
已清洁的面积，以平方米为单位
1
符合程度
2
清洁线路的长度
3
清洁时长
4
设备位置
5
已清洁的面积
6
未清洁的面积（障碍物）
7
速度。快速蓝色绿色黄色橙色红色慢速
8
小心
污水中的污染物和清洁剂可能会危害您的健康或污染环境。
请遵守当地适用的废水处理规定。

2. 从支架中取出排放软管。
3. 将排放软管降低到合适的收集装置上。
4. 压合或弯折计量装置。
5. 打开盖子。
6. 通过压力或弯曲计量装置控制污水流量。
7. 冲洗污水箱。
8. 关闭盖子。
9. 将排放软管压入设备舱内的支架中。
10. 关闭设备舱的门。
</pre>

</details>

### EV-KIRA-013 · 每次运行后维护

- Knowledge Type：maintenance
- Question Potential：single
- Evidence Summary：1. ## 排放污水。；2. ## 冲洗污水箱。；3. 清洁涡轮机防护网。
- Key Points：
  - 1. ## 排放污水。
  - 2. ## 冲洗污水箱。
  - 3. 清洁涡轮机防护网。
  - 4. 从污水箱中取出粗大污染物滤网并清洗。

- Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001）
- Page：86–86
- Section：在每次运行之后
- Chunk：KIRA-B50-CHUNK-0120

<details><summary>Chunk Text</summary>

<pre>
[KIRA-B50-CHUNK-0120]
在每次运行之后
1. ## 排放污水。
2. ## 冲洗污水箱。
3. 清洁涡轮机防护网。
4. 从污水箱中取出粗大污染物滤网并清洗。
5. 使用抹布和洗涤用碱液清洁设备外部。
6. 检查绒毛滤网，必要时清洁。
7. 拆下并清洁清洁头上的粗大污染物容器。
8. 清洗清洁头上的分水条。
9. 清洁吸水扒中的吸水胶条，检查是否存在磨损。翻转或更换已磨损的吸水胶条。
10. 检查吸水胶条在吸水扒中的正确配合。必要时，将吸水胶条重新正确装入吸水扒的凹槽中。
11. 清洁清洁头两侧的削刮胶条，检查是否存在磨损。更换已磨损的削刮胶条。
12. 检查刷子是否磨损。更换已磨损的刷子。
提示：如果黄色指示器刷毛与其他刷毛长度相同，则说明刷辊已磨损。
13. ## 给蓄电池充电。
</pre>

</details>

### EV-KIRA-014 · 清洁传感器

- Knowledge Type：maintenance
- Question Potential：single
- Evidence Summary：2. 清洁后重新启动设备。
- Key Points：
  - 2. 清洁后重新启动设备。

- Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001）
- Page：98–98
- Section：清洁传感器
- Chunk：KIRA-B50-CHUNK-0139

<details><summary>Chunk Text</summary>

<pre>
[KIRA-B50-CHUNK-0139]
清洁传感器
1. 使用湿微纤维抹布清洁图中所示的所有传感器。如有必要，请额外使用玻璃清洁剂。
2. 清洁后重新启动设备。
</pre>

</details>

### EV-KIRA-015 · 急停激活后处理

- Knowledge Type：troubleshooting
- Question Potential：single
- Evidence Summary：1. 机器人停止驾驶和清洁。检查机器人和周围环境。如果没有危险，请松开紧急停止按钮。
- Key Points：
  - 1. 机器人停止驾驶和清洁。检查机器人和周围环境。如果没有危险，请松开紧急停止按钮。

- Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001）
- Page：99–100
- Section：紧急停止按钮已激活
- Chunk：KIRA-B50-CHUNK-0142

<details><summary>Chunk Text</summary>

<pre>
[KIRA-B50-CHUNK-0142]
紧急停止按钮已激活

原因:
排除故障:
1. 机器人停止驾驶和清洁。检查机器人和周围环境。如果没有危险，请松开紧急停止按钮。
</pre>

</details>

### EV-KIRA-016 · 对接失败处理

- Knowledge Type：troubleshooting
- Question Potential：single
- Evidence Summary：1. 将机器人驱动到位置代码处，并开始清洁任务。如果错误仍然存在，重新示教路线。
- Key Points：
  - 1. 将机器人驱动到位置代码处，并开始清洁任务。如果错误仍然存在，重新示教路线。

- Document：卡赫_KIRA_B_50完整操作说明_中文版.pdf（DOC-001）
- Page：101–101
- Section：对接失败
- Chunk：KIRA-B50-CHUNK-0148

<details><summary>Chunk Text</summary>

<pre>
[KIRA-B50-CHUNK-0148]
对接失败
原因:
机器人失去了定位功能。
排除故障:
1. 将机器人驱动到位置代码处，并开始清洁任务。如果错误仍然存在，重新示教路线。
</pre>

</details>

## B2 四足机器人（8）

### EV-B2M-001 · 使用环境与地形限制

- Knowledge Type：usage_limit
- Question Potential：multi_chunk
- Evidence Summary：1. 在-20℃-55℃，天气良好的环境下运行。恶劣天气请勿运行，如雷电、龙卷风天气等。水中运行则务必；遵守IP67防护等级说明所述要求。；2.使用时，请保持机器人在视线范围内控制，使机器人时刻与障碍物、复杂地面、人群、水面等物体保持
- Key Points：
  - 1. 在-20℃-55℃，天气良好的环境下运行。恶劣天气请勿运行，如雷电、龙卷风天气等。水中运行则务必
  - 遵守IP67防护等级说明所述要求。
  - 2.使用时，请保持机器人在视线范围内控制，使机器人时刻与障碍物、复杂地面、人群、水面等物体保持
  - 至少2米以上的安全距离。

- Document：宇树_B2四足机器人用户手册_中文版.pdf（DOC-002）
- Page：10–10
- Section：使用环境要求
- Chunk：B2-MANUAL-CHUNK-0018、B2-MANUAL-CHUNK-0019

<details><summary>Chunk Text</summary>

<pre>
[B2-MANUAL-CHUNK-0018]
使用说明
botics
使用环境要求
1. 在-20℃-55℃，天气良好的环境下运行。恶劣天气请勿运行，如雷电、龙卷风天气等。水中运行则务必
遵守IP67防护等级说明所述要求。
tics
2.使用时，请保持机器人在视线范围内控制，使机器人时刻与障碍物、复杂地面、人群、水面等物体保持
至少2米以上的安全距离。
3. 请不要在电磁干扰环境下运行机器人。电磁干扰源包括但不仅限于：高压电线、高压输电站、移动电话
基站和电视广播信号塔。
4. 请不要在Wi-Fi信号干扰环境下运行机器人。Wi-Fi信号干扰通常由于同频干扰引起。受到干扰时，务必
关闭部分或全部其他无线设备Wi-Fi信号源，然后再使用遥控器操作机器人。
5. 由于实际操控人员的操控熟练水平不一，故为了可靠稳妥起见，请在空旷无遮挡平整地面环境使用。操
作机器人时应注意，AI运控模式下台阶需低于25cm、低速档时斜坡小于45°、高速档时斜坡小于30°；常规运

[B2-MANUAL-CHUNK-0019]
作机器人时应注意，AI运控模式下台阶需低于25cm、低速档时斜坡小于45°、高速档时斜坡小于30°；常规运
控模式下台阶需低于20cm，斜坡小于20°，不满足条件可能会导致机器人摔倒。机器人在复杂地面或有一定起
伏和坡度的地形行走时，操控人员应当降低机器人的行走速度，小心操控，以免机器人被障碍物绊倒。
6. 足式机器人对行走的地面有一定的要求。请勿在摩擦力非常小的地面使用机器人，如冰面。请勿在松软
的地面使用机器人，如较厚的海绵地面。如果在较光滑的地面使用，如玻璃、瓷砖等地面，请小心并柔顺的操
控机器人进行运动，避免剧烈运动，并降低机器人的行走速度，防止机器人足端打滑而摔倒。
开箱
在平整的地面上按照放置要求摆放箱体(正面朝上)，然后打开上箱体，把机器人整体抬出。将四足机器
人和遥控器、充电器等分别从箱内取出，将四足机器人平放在平整的地面上，然后进行开机准备。
CS
开机前检查
1. 仅使用Unitree正品部件并保证所有部件工作状态良好。
2
</pre>

</details>

### EV-B2M-002 · 开机前检查

- Knowledge Type：setup
- Question Potential：single
- Evidence Summary：确保固件等已经更新至最新版本。；3. 用户确保自己不在醉酒、药物影响或无法集中注意力情况下操控机器人。；4. 熟悉了解每种步态模式的特点。熟悉机器人失稳/失控情况下紧急制动方法。
- Key Points：
  - 确保固件等已经更新至最新版本。
  - 3. 用户确保自己不在醉酒、药物影响或无法集中注意力情况下操控机器人。
  - 4. 熟悉了解每种步态模式的特点。熟悉机器人失稳/失控情况下紧急制动方法。
  - 5. 确保机器人及各部件内部没有任何异物(如：水、油、沙、土等)。

- Document：宇树_B2四足机器人用户手册_中文版.pdf（DOC-002）
- Page：10–10
- Section：开机前检查
- Chunk：B2-MANUAL-CHUNK-0020

<details><summary>Chunk Text</summary>

<pre>
[B2-MANUAL-CHUNK-0020]
CS
开机前检查
1. 仅使用Unitree正品部件并保证所有部件工作状态良好。
2
确保固件等已经更新至最新版本。
3. 用户确保自己不在醉酒、药物影响或无法集中注意力情况下操控机器人。
Robo
4. 熟悉了解每种步态模式的特点。熟悉机器人失稳/失控情况下紧急制动方法。
Unit
5. 确保机器人及各部件内部没有任何异物(如：水、油、沙、土等)。
6. 保证遥控模块、电池包电量充足。
7. 若使用扩展接口，检查线缆连接是否正确。
©2023 宇树科技版权所有
9
Unitre
</pre>

</details>

### EV-B2M-003 · 电池安装与机身摆放

- Knowledge Type：setup
- Question Potential：single
- Evidence Summary：将 B2放在平坦的地面上，将电池包从机器人侧面插入电池槽，注意安装方向，防呆接口朝上，如无法完全；插入电池包，请调整电池包方向，不要强行按压，以免损坏电池接口和卡扣，当听到“咔哒~”声，电池包安装；完成。请确保卡扣卡到位！
- Key Points：
  - 将 B2放在平坦的地面上，将电池包从机器人侧面插入电池槽，注意安装方向，防呆接口朝上，如无法完全
  - 插入电池包，请调整电池包方向，不要强行按压，以免损坏电池接口和卡扣，当听到“咔哒~”声，电池包安装
  - 完成。请确保卡扣卡到位！
  - (2) 机身摆放（重要步骤！！！）

- Document：宇树_B2四足机器人用户手册_中文版.pdf（DOC-002）
- Page：11–11
- Section：开机前准备
- Chunk：B2-MANUAL-CHUNK-0021

<details><summary>Chunk Text</summary>

<pre>
[B2-MANUAL-CHUNK-0021]
tics
开机前准备
(1) 安装电池包
将 B2放在平坦的地面上，将电池包从机器人侧面插入电池槽，注意安装方向，防呆接口朝上，如无法完全
插入电池包，请调整电池包方向，不要强行按压，以免损坏电池接口和卡扣，当听到“咔哒~”声，电池包安装
完成。请确保卡扣卡到位！
tics
(2) 机身摆放（重要步骤！！！）
卧式开机：请确保开机运行前机器人放置在平整地面上，机器人腹部支撑垫需平贴地面，机身水平无倾斜
趴在地面，机器人小腿呈完全收起状态(如下图)，四个膝关节以及足端平放在地面上，确保机器人大腿和小
腿都没被机身压住。
启动 B2
机器人完成开机前检查，和开机前准备要求摆放好后，按照如下步骤开机：先短按电源开关一次，再长按
电源开关3秒以上，即可开启电池(电池开启时，指示灯为绿灯常亮，指示灯显示当前电池电量)。电池启动
后等待2分钟，机器人自动站立，机身与地面平行，即开机成功。
短按+长按3秒以上
Robotics
Unitree
A
●若开机失败，请仔细检查机身摆放。
</pre>

</details>

### EV-B2M-004 · 启动 B2

- Knowledge Type：operation
- Question Potential：multi_chunk
- Evidence Summary：将 B2放在平坦的地面上，将电池包从机器人侧面插入电池槽，注意安装方向，防呆接口朝上，如无法完全；插入电池包，请调整电池包方向，不要强行按压，以免损坏电池接口和卡扣，当听到“咔哒~”声，电池包安装；完成。请确保卡扣卡到位！
- Key Points：
  - 将 B2放在平坦的地面上，将电池包从机器人侧面插入电池槽，注意安装方向，防呆接口朝上，如无法完全
  - 插入电池包，请调整电池包方向，不要强行按压，以免损坏电池接口和卡扣，当听到“咔哒~”声，电池包安装
  - 完成。请确保卡扣卡到位！
  - (2) 机身摆放（重要步骤！！！）

- Document：宇树_B2四足机器人用户手册_中文版.pdf（DOC-002）
- Page：11–11
- Section：启动 B2
- Chunk：B2-MANUAL-CHUNK-0021、B2-MANUAL-CHUNK-0022

<details><summary>Chunk Text</summary>

<pre>
[B2-MANUAL-CHUNK-0021]
tics
开机前准备
(1) 安装电池包
将 B2放在平坦的地面上，将电池包从机器人侧面插入电池槽，注意安装方向，防呆接口朝上，如无法完全
插入电池包，请调整电池包方向，不要强行按压，以免损坏电池接口和卡扣，当听到“咔哒~”声，电池包安装
完成。请确保卡扣卡到位！
tics
(2) 机身摆放（重要步骤！！！）
卧式开机：请确保开机运行前机器人放置在平整地面上，机器人腹部支撑垫需平贴地面，机身水平无倾斜
趴在地面，机器人小腿呈完全收起状态(如下图)，四个膝关节以及足端平放在地面上，确保机器人大腿和小
腿都没被机身压住。
启动 B2
机器人完成开机前检查，和开机前准备要求摆放好后，按照如下步骤开机：先短按电源开关一次，再长按
电源开关3秒以上，即可开启电池(电池开启时，指示灯为绿灯常亮，指示灯显示当前电池电量)。电池启动
后等待2分钟，机器人自动站立，机身与地面平行，即开机成功。
短按+长按3秒以上
Robotics
Unitree
A
●若开机失败，请仔细检查机身摆放。

[B2-MANUAL-CHUNK-0022]
后等待2分钟，机器人自动站立，机身与地面平行，即开机成功。
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
</pre>

</details>

### EV-B2M-005 · 首次绑定 Explore App

- Knowledge Type：setup
- Question Potential：multi_chunk
- Evidence Summary：首次使用需要先绑定，绑定过程中，请打开手机蓝牙，将手机靠近B2，保证蓝牙实时通讯。；① 下载并安装 Unitree Explore App，根据 Unitree 提供的企业账号和密码完成登录。；若无全业账号请联系字树科技新售服务人员开通
- Key Points：
  - 首次使用需要先绑定，绑定过程中，请打开手机蓝牙，将手机靠近B2，保证蓝牙实时通讯。
  - ① 下载并安装 Unitree Explore App，根据 Unitree 提供的企业账号和密码完成登录。
  - 若无全业账号请联系字树科技新售服务人员开通
  - 共已同法并同热《的私政策》《用户协议》《法律声明》

- Document：宇树_B2四足机器人用户手册_中文版.pdf（DOC-002）
- Page：12–13
- Section：连接 Unitree Explore App
- Chunk：B2-MANUAL-CHUNK-0023、B2-MANUAL-CHUNK-0024

<details><summary>Chunk Text</summary>

<pre>
[B2-MANUAL-CHUNK-0023]
icS
连接 Unitree Explore App
首次使用需要先绑定，绑定过程中，请打开手机蓝牙，将手机靠近B2，保证蓝牙实时通讯。
① 下载并安装 Unitree Explore App，根据 Unitree 提供的企业账号和密码完成登录。
登录
手机号
若无全业账号请联系字树科技新售服务人员开通
密码
共已同法并同热《的私政策》《用户协议》《法律声明》
登录
Robotics
Unitree
●若无企业账号请联系宇树科技销售服务人员开通账号！
B2 电源启动后，在 Unitree Explore App 添加机器狗：打开手机系统蓝牙->首页点击添加机器人->选
择您要添加的设备。
图库
我的
添加设备
请选择要添加的设备
正在扫描
B2_10001
B2_10001
B2_10001
添加机器人
B2_10001
十
添加机器人
绑定 B2：您可以选择 AP直连模式和 Wi-Fi 连接模式进行连接，连接成功后您可以学习内置教程来快
速掌握操控技巧。
AP 直连模式
AP 直连模式
Wi-Fi 连接模式
设置机器狗热点名称
手机连接机器狗热点
手机通过路由器连接机器狗
设置密码
下一步
© 2023
3 宇树科技版权所有
11
Unit

[B2-MANUAL-CHUNK-0024]
ics
①帮助？
正在连接设备
①请先关闭手机4G/5G蜂窝网络
请保持网络通畅耐心等待
②手机请连接Wi-Fi:100111001110011
与去连接
00:14
热点设置
热点连接
连接机器狗
热点设置
热点连接
连接机器构
ucs
Wi-Fi 连接模式
Wi-Fi 连接模式
选择 Wi-Fi 网络并输入密码
输入Wi-Fi名称
输入Wi-Fi密码
连接成功
下一步
返回首页
●如何更换账户绑定？
首页点击【设置】-[机器人设置]，选择点击解除绑定，可以对已绑定的机器狗进行解绑。机器狗解除绑定后，
可以被其他账户绑定。
机器狗设置
AP 路由器模式
设备SN
B42940000N832MX8X
复材
型号
B2 EDU
Wi-Fi 连接模式
(011)
切换连接
AP 路由器模式
解除绑定
确定要解除与机器狗的绑定关系吗?
解除绑定后，
将无法通过 App 控制机器狗
取消
确定
obotics
●连接过程中请保持手机蓝牙开启！
Unitree Rob
● 蓝牙连接报错：Unitree Explore App 需要获取蓝牙权限，请在手机 App 中打开 Unitree Explore 蓝牙权限。
●若忘记绑定账户、账户丢失，请与Unitree相关人员联系！
© 2023
3 宇树科技版权所有
12
Unitre
</pre>

</details>

### EV-B2M-006 · 关闭 B2

- Knowledge Type：operation
- Question Potential：single
- Evidence Summary：起立后的初始状态，机身水平，手柄无任何操作，静态站立时的状态）。；● 按2次L2+A 键，机器人依次完成关节锁定，卧倒动作；；● 机器人进入卧倒状态后，先短按电源键再长按电源键3秒以上关机。
- Key Points：
  - 起立后的初始状态，机身水平，手柄无任何操作，静态站立时的状态）。
  - ● 按2次L2+A 键，机器人依次完成关节锁定，卧倒动作；
  - ● 机器人进入卧倒状态后，先短按电源键再长按电源键3秒以上关机。
  - 关机后，请按照机身摆放要求，摆放好机器人大小腿和髋关节位置，为下次开机做准备。若长时间不使用

- Document：宇树_B2四足机器人用户手册_中文版.pdf（DOC-002）
- Page：15–15
- Section：关闭 B2
- Chunk：B2-MANUAL-CHUNK-0027

<details><summary>Chunk Text</summary>

<pre>
[B2-MANUAL-CHUNK-0027]
tics
关闭 B2
关机前，请务必确保机器人站立在平整地面上，确保机器人处于静态站立状态（机器人机身位置处于开机
起立后的初始状态，机身水平，手柄无任何操作，静态站立时的状态）。
● 按2次L2+A 键，机器人依次完成关节锁定，卧倒动作；
● 机器人进入卧倒状态后，先短按电源键再长按电源键3秒以上关机。
tics
关机后，请按照机身摆放要求，摆放好机器人大小腿和髋关节位置，为下次开机做准备。若长时间不使用
B2，请及时取出电池包：往外拉出电池包提带，电池包即可弹出取下。
A
● 请确保机器人处于趴下状态(卧倒状态或阻尼状态)下进行关机，否则机器人关机掉电后会重重地摔在地上，
可能会造成机身损坏，并存在一定的安全隐患！若开机失败，请检查机器人机身摆放是否正确。
●运动关节处小心夹手，请小心谨慎！
装箱
装箱前准备：将四足机器人的腿转动到如图示的位置(后腿收起步骤：旋转后腿髋关节电机使后大腿摆放
至上图示位置，同时收起后小腿摆放至图示位置。
otics
</pre>

</details>

### EV-B2M-007 · 遥控失效强制关机

- Knowledge Type：troubleshooting
- Question Potential：single
- Evidence Summary：若采用 AP直连模式，可检查手机是否连上B2发出的Ap热点。若热点配置失败，请确保设置的热点名称；没有特殊符号和空格，确保机器狗、手机二者靠近后，重启机器狗和App再尝试连接。；若采用Wi-Fi连接模式，可检查所连接Wi-Fi网络是否正常，能连上外网。
- Key Points：
  - 若采用 AP直连模式，可检查手机是否连上B2发出的Ap热点。若热点配置失败，请确保设置的热点名称
  - 没有特殊符号和空格，确保机器狗、手机二者靠近后，重启机器狗和App再尝试连接。
  - 若采用Wi-Fi连接模式，可检查所连接Wi-Fi网络是否正常，能连上外网。
  - ●如何在遥控模块失效时关闭机器人

- Document：宇树_B2四足机器人用户手册_中文版.pdf（DOC-002）
- Page：16–16
- Section：如何在遥控模块失效时关闭机器人
- Chunk：B2-MANUAL-CHUNK-0030

<details><summary>Chunk Text</summary>

<pre>
[B2-MANUAL-CHUNK-0030]
● App 连接异常
nitr
若采用 AP直连模式，可检查手机是否连上B2发出的Ap热点。若热点配置失败，请确保设置的热点名称
没有特殊符号和空格，确保机器狗、手机二者靠近后，重启机器狗和App再尝试连接。
若采用Wi-Fi连接模式，可检查所连接Wi-Fi网络是否正常，能连上外网。
●如何在遥控模块失效时关闭机器人
当遇到由于遥控模块失效(如遥控器、手机电量耗尽等原因)导致的无法使用遥控模块使机器人趴地待机。
只能采用按电池电源键强制关机。
强制关机：使机器人与障碍物、复杂地面、人群、水面等物体保持至少2米以上的安全距离。抬住机器人
头部和尾部，短按电源开关一次，再长按电源开关3秒以上关闭电源。机器人掉电后缓慢将其抬至地面上。
●机器人容易摔倒，开机无法站立
没有使用正确的开机姿势，导致机身电机角度错误，使用正确的开机姿势后重新开机。若重启机器人无法
解决问题，此时需要按照 Unitree Explore App 相关步骤对机器人关节重新进行标定。
</pre>

</details>

### EV-B2M-008 · 整机清洁存放与例检

- Knowledge Type：maintenance
- Question Potential：multi_chunk
- Evidence Summary：当B2在恶劣环境下（雨天、沙尘、湿地)使用后，请及时清洁机身表面。；清洗机身前请先关闭电源，使用干净的软布对机身进行擦拭，尤其关注多目深度相机是否擦拭干净。清洁；时严禁使用金属刷、砂纸等，以免刮伤零件表面。清洗后，请用软布将机身擦干。擦干后可用风扇或风枪将机
- Key Points：
  - 当B2在恶劣环境下（雨天、沙尘、湿地)使用后，请及时清洁机身表面。
  - 清洗机身前请先关闭电源，使用干净的软布对机身进行擦拭，尤其关注多目深度相机是否擦拭干净。清洁
  - 时严禁使用金属刷、砂纸等，以免刮伤零件表面。清洗后，请用软布将机身擦干。擦干后可用风扇或风枪将机
  - 器人表面、关节缝隙处的积水吹干，避免留下水痕。

- Document：宇树_B2四足机器人用户手册_中文版.pdf（DOC-002）
- Page：18–19
- Section：日常保养与维护
- Chunk：B2-MANUAL-CHUNK-0036、B2-MANUAL-CHUNK-0037、B2-MANUAL-CHUNK-0038

<details><summary>Chunk Text</summary>

<pre>
[B2-MANUAL-CHUNK-0036]
日常保养与维护
botics
整机清洁
1. 清洁
当B2在恶劣环境下（雨天、沙尘、湿地)使用后，请及时清洁机身表面。
tics
清洗机身前请先关闭电源，使用干净的软布对机身进行擦拭，尤其关注多目深度相机是否擦拭干净。清洁
时严禁使用金属刷、砂纸等，以免刮伤零件表面。清洗后，请用软布将机身擦干。擦干后可用风扇或风枪将机
器人表面、关节缝隙处的积水吹干，避免留下水痕。
A
● 注意！B2 整机(含电池包)IP67 级防水，清洁时请勿取下电池包！
2. 存放
B2需存放于干燥、阴凉的室内，避免日晒及雨淋，以免零部件锈蚀而缩短使用寿命。长时间存放时取出电
池包。
检查保养
在使用前后开展例行检查，可大幅度提升产品可靠性能，降低安全隐患，延长使用寿命。
不带电检查表
类型
要点
1. 机身外观是否清洁、无破损或变形痕迹
整机外观
2. 相机表面镜片有无异物
3. 头部激光雷达周围有无异物遮挡
1. 目视及触摸检查机身、各个关节及连接处、足端组件是否完好，有裂纹或者有破损需及时更

[B2-MANUAL-CHUNK-0037]
3. 头部激光雷达周围有无异物遮挡
1. 目视及触摸检查机身、各个关节及连接处、足端组件是否完好，有裂纹或者有破损需及时更
换和联系 Unitree 售后
结构
2. 各个连接部件螺丝是否锁紧，尤其关注关节连接件和电池锁紧旋钮的螺丝
3. 散热风扇进出口有无异物阻塞
足端组件
检查有无明显的足垫破损，若有破损请及时更换
1. 机身的电池包接口有无异物，变形
电池包
2. 电池包安装是否可靠，确保运行时不会松脱
Robotics
3. 电池包外壳是否有明显损伤，有明显损伤的电池包禁止用于使用
Unitr
1. 遥控器摇杆是都在中位，摇杆是否进入沙土等异物
遥控器
2. 遥控器的各个按键是否存在卡顿
© 2023 宇树科技版权所有
17
Unitre

[B2-MANUAL-CHUNK-0038]
上电检查
类型
要点
potics
遥控器
1. 确认摇杆的基本操作功能是否正常
2. 确认当前电量是否充足
电池
确认当前电量是否充足
散热风扇
用耳朵仔细听，确认散热风扇正常工作，且无剐蹭等声音
电池包保养
1. 切勿在温度过高或温度过低的环境下使用充电器对电池包进行充电
2. 切勿将电池包存储在室温超过40℃的环境下。
3. 切勿过充电池包，否则将对电芯造成损害。
ee Robotics
4. 若较长时间不使用电池时，请定期检查电池剩余的电量，如果电量低于30%，请把电池充电到70%后再继续
保存。以免电池过放而损坏电池。
●建议每次外出使用前，执行以上检查！
●若有配件损坏需要更换，请及时联系Unitree售后!
Unitree Robotics
©2023 宇树科技版权所有
18
Unitree Robotics
</pre>

</details>

## B2 遥控器（8）

### EV-B2R-001 · 遥控器低电量充电

- Knowledge Type：charging
- Question Potential：single
- Evidence Summary：当遥控器电量指示灯显示低电量时，应将遥控器连接充电器。；推荐使用符合 FCC/CE 标准、规格为 5V/2A 的 USB 充电器。；给遥控器充电前，确保遥控器处于关闭状态。；充电状态下电源指示灯按 1Hz 频率闪烁并指示当前电量。
- Key Points：
  - 当遥控器电量指示灯显示低电量时，应将遥控器连接充电器。
  - 推荐使用符合 FCC/CE 标准、规格为 5V/2A 的 USB 充电器。
  - 给遥控器充电前，确保遥控器处于关闭状态。
  - 充电状态下电源指示灯按 1Hz 频率闪烁并指示当前电量。

- Document：宇树_B2遥控器使用说明_中文版.pdf（DOC-003）
- Page：5–5
- Section：遥控器充电
- Chunk：B2-REMOTE-CHUNK-0006

<details><summary>Chunk Text</summary>

<pre>
[B2-REMOTE-CHUNK-0006]
B2遥控器使用手册
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
USB 充电器
0
USB-Type C 线
SELEOT
1. 推荐使用符合 FCC/CE 标准，规格为 5V/2A的 USB 充电器。
2. 给遥控器充电前，确保遥控器处于关闭状态。
3. 充电状态下电源指示灯会按1Hz(1秒/次)频率闪烁，并指示当前电量。
4. 电量指示灯全部常亮时表示电池包已经充满，请取下充电器，完成充电。
tics
充电指示灯
LED1
LED2
LED3
LED4
当前电量
OOOOO
0
O
O
0%-25%
Ur
OOOO
O OOO
O
25%-50%
50%-75%
75%-100%
充满
©2024 宇树科技版权所有
5
</pre>

</details>

### EV-B2R-002 · R3 遥控器规格

- Knowledge Type：specification
- Question Potential：single
- Evidence Summary：780mAh；数传模块，蓝牙；100m 以上
- Key Points：
  - 780mAh
  - 数传模块，蓝牙
  - 100m 以上
  - Step1：取出摇杆。如同所示，用右手将遥控器平稳缓慢的拉出，取出收纳槽当中的2个摇杆。

- Document：宇树_B2遥控器使用说明_中文版.pdf（DOC-003）
- Page：3–3
- Section：技术规格
- Chunk：B2-REMOTE-CHUNK-0004

<details><summary>Chunk Text</summary>

<pre>
[B2-REMOTE-CHUNK-0004]
B2 遥控器使用手册
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
Unitree Rol
ree Robotics
如需收纳，请拆下摇杆后放回收纳槽中。
© 2024
宇树科技版权所有
3
Unitr
</pre>

</details>

### EV-B2R-003 · 安装收纳遥控器摇杆

- Knowledge Type：setup
- Question Potential：single
- Evidence Summary：从收纳槽中平稳缓慢地取出两个摇杆。；按顺时针方向将摇杆固定在遥控器上并拧紧。；收纳时拆下摇杆后放回收纳槽。
- Key Points：
  - 从收纳槽中平稳缓慢地取出两个摇杆。
  - 按顺时针方向将摇杆固定在遥控器上并拧紧。
  - 收纳时拆下摇杆后放回收纳槽。

- Document：宇树_B2遥控器使用说明_中文版.pdf（DOC-003）
- Page：3–3
- Section：安装摇杆
- Chunk：B2-REMOTE-CHUNK-0004

<details><summary>Chunk Text</summary>

<pre>
[B2-REMOTE-CHUNK-0004]
B2 遥控器使用手册
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
Unitree Rol
ree Robotics
如需收纳，请拆下摇杆后放回收纳槽中。
© 2024
宇树科技版权所有
3
Unitr
</pre>

</details>

### EV-B2R-004 · 遥控器摇杆校准

- Knowledge Type：operation
- Question Potential：single
- Evidence Summary：手持遥控但不要触碰摇杆，按下遥控上按键F1和F3并同时松开，此时遥控器发出连续“嘀~嘀~”声（1；次/秒)代表已进入校准模式。进入校准模式后将左右摇杆打满舵并旋转数圈，直至“嘀~嘀~”声停止，此时校；准就绪。单按F3一次使校准生效，完成校准。
- Key Points：
  - 手持遥控但不要触碰摇杆，按下遥控上按键F1和F3并同时松开，此时遥控器发出连续“嘀~嘀~”声（1
  - 次/秒)代表已进入校准模式。进入校准模式后将左右摇杆打满舵并旋转数圈，直至“嘀~嘀~”声停止，此时校
  - 准就绪。单按F3一次使校准生效，完成校准。
  - ●校准摇杆时，校准前请不要触碰摇杆，进入校准模式才可以动摇杆。校准后可通过APP查看校准后的摇杆状态。

- Document：宇树_B2遥控器使用说明_中文版.pdf（DOC-003）
- Page：4–4
- Section：遥控器摇杆校准
- Chunk：B2-REMOTE-CHUNK-0005

<details><summary>Chunk Text</summary>

<pre>
[B2-REMOTE-CHUNK-0005]
ics
遥控器摇杆校准
手持遥控但不要触碰摇杆，按下遥控上按键F1和F3并同时松开，此时遥控器发出连续“嘀~嘀~”声（1
次/秒)代表已进入校准模式。进入校准模式后将左右摇杆打满舵并旋转数圈，直至“嘀~嘀~”声停止，此时校
准就绪。单按F3一次使校准生效，完成校准。
ics
●校准摇杆时，校准前请不要触碰摇杆，进入校准模式才可以动摇杆。校准后可通过APP查看校准后的摇杆状态。
开启/关闭遥控器
开启遥控器：短按电源按键一次，再长按电源按键2秒以上，听到“嘀~嘀~”两声，即遥控开启。
● 关闭遥控器：短按电源按键一次，再长按电源按键2秒以上，听到“嘀~嘀~嘀~”三声，即遥控关闭。
PH0
START
短按+长按2秒及以上
音效/震动切换
●切换振动：快速按下F3按钮3次，切换到振动模式。
●切换声音：快速按下F3按钮3次，切换到声音模式。
Unitree
Robotics
SELEOT
START
快按3次F3
© 2024 宇树科技 版权所有
4
Unitr
</pre>

</details>

### EV-B2R-005 · 开关 R3 遥控器

- Knowledge Type：operation
- Question Potential：single
- Evidence Summary：开启遥控器：短按电源按键一次，再长按电源按键 2 秒以上，听到两声提示音。；关闭遥控器：短按电源按键一次，再长按电源按键 2 秒以上，听到三声提示音。
- Key Points：
  - 开启遥控器：短按电源按键一次，再长按电源按键 2 秒以上。
  - 听到两声提示音，即遥控开启。
  - 关闭遥控器：短按电源按键一次，再长按电源按键 2 秒以上。
  - 听到三声提示音，即遥控关闭。

- Document：宇树_B2遥控器使用说明_中文版.pdf（DOC-003）
- Page：4–4
- Section：开启/关闭遥控器
- Chunk：B2-REMOTE-CHUNK-0005

<details><summary>Chunk Text</summary>

<pre>
[B2-REMOTE-CHUNK-0005]
ics
遥控器摇杆校准
手持遥控但不要触碰摇杆，按下遥控上按键F1和F3并同时松开，此时遥控器发出连续“嘀~嘀~”声（1
次/秒)代表已进入校准模式。进入校准模式后将左右摇杆打满舵并旋转数圈，直至“嘀~嘀~”声停止，此时校
准就绪。单按F3一次使校准生效，完成校准。
ics
●校准摇杆时，校准前请不要触碰摇杆，进入校准模式才可以动摇杆。校准后可通过APP查看校准后的摇杆状态。
开启/关闭遥控器
开启遥控器：短按电源按键一次，再长按电源按键2秒以上，听到“嘀~嘀~”两声，即遥控开启。
● 关闭遥控器：短按电源按键一次，再长按电源按键2秒以上，听到“嘀~嘀~嘀~”三声，即遥控关闭。
PH0
START
短按+长按2秒及以上
音效/震动切换
●切换振动：快速按下F3按钮3次，切换到振动模式。
●切换声音：快速按下F3按钮3次，切换到声音模式。
Unitree
Robotics
SELEOT
START
快按3次F3
© 2024 宇树科技 版权所有
4
Unitr
</pre>

</details>

### EV-B2R-006 · 音效/震动模式切换

- Knowledge Type：operation
- Question Potential：single
- Evidence Summary：切换振动：快速按下 F3 按钮 3 次，切换到振动模式。；切换声音：快速按下 F3 按钮 3 次，切换到声音模式。
- Key Points：
  - 快速按下 F3 按钮 3 次。
  - 切换到振动模式。
  - 切换到声音模式。

- Document：宇树_B2遥控器使用说明_中文版.pdf（DOC-003）
- Page：4–4
- Section：音效/震动切换
- Chunk：B2-REMOTE-CHUNK-0005

<details><summary>Chunk Text</summary>

<pre>
[B2-REMOTE-CHUNK-0005]
ics
遥控器摇杆校准
手持遥控但不要触碰摇杆，按下遥控上按键F1和F3并同时松开，此时遥控器发出连续“嘀~嘀~”声（1
次/秒)代表已进入校准模式。进入校准模式后将左右摇杆打满舵并旋转数圈，直至“嘀~嘀~”声停止，此时校
准就绪。单按F3一次使校准生效，完成校准。
ics
●校准摇杆时，校准前请不要触碰摇杆，进入校准模式才可以动摇杆。校准后可通过APP查看校准后的摇杆状态。
开启/关闭遥控器
开启遥控器：短按电源按键一次，再长按电源按键2秒以上，听到“嘀~嘀~”两声，即遥控开启。
● 关闭遥控器：短按电源按键一次，再长按电源按键2秒以上，听到“嘀~嘀~嘀~”三声，即遥控关闭。
PH0
START
短按+长按2秒及以上
音效/震动切换
●切换振动：快速按下F3按钮3次，切换到振动模式。
●切换声音：快速按下F3按钮3次，切换到声音模式。
Unitree
Robotics
SELEOT
START
快按3次F3
© 2024 宇树科技 版权所有
4
Unitr
</pre>

</details>

### EV-B2R-007 · R3 绑定与连接状态

- Knowledge Type：setup
- Question Potential：single
- Evidence Summary：首次使用遥控器需要在Unitree Explore App上进行遥控器绑定，【设置】->【遥控器设置】-打开遥控器开；关，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。；123456
- Key Points：
  - 首次使用遥控器需要在Unitree Explore App上进行遥控器绑定，【设置】->【遥控器设置】-打开遥控器开
  - 关，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。
  - 123456
  - 遥控器开机并且与 B2 连接成功后，右侧DL 指示灯亮，这就意味着遥控器与 B2 数传模块已连接，此时可

- Document：宇树_B2遥控器使用说明_中文版.pdf（DOC-003）
- Page：6–6
- Section：R3 遥控器基本操作
- Chunk：B2-REMOTE-CHUNK-0007

<details><summary>Chunk Text</summary>

<pre>
[B2-REMOTE-CHUNK-0007]
ics
R3 遥控器基本操作
首次使用遥控器需要在Unitree Explore App上进行遥控器绑定，【设置】->【遥控器设置】-打开遥控器开
关，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。
设置
遥控器设置
机器人设置
遥控器ID
123456
修改
Ics
数据
遥控器设置
报警信息
遥控器开机并且与 B2 连接成功后，右侧DL 指示灯亮，这就意味着遥控器与 B2 数传模块已连接，此时可
通过遥控器控制 B2。使用遥控器摇杆操控 B2 时，摇杆的操控方式如下所示：
左摇杆
右摇杆
nitre
(AI运控模式下不支持抬头低头)
tics
iteuc
Unitree
Robotics
●摇杆回中/中位：遥控器的摇杆处于中间位置。
●摇杆杆量：遥控器摇杆偏离摇杆中位的偏移量。
●墙面、门等阻挡物会极大削弱机器狗和遥控模块之间的信号，请务必在空旷的场地操作机器狗。
©2024 宇树科技版权所有
6
Unit
</pre>

</details>

### EV-B2R-008 · R3 遥控指令映射

- Knowledge Type：operation
- Question Potential：single
- Evidence Summary：机器狗参照示意图：；灵动模式(默认）；L2(长按) + A (单击)
- Key Points：
  - 机器狗参照示意图：
  - 灵动模式(默认）
  - L2(长按) + A (单击)
  - 站立锁定/卧倒姿态切换

- Document：宇树_B2遥控器使用说明_中文版.pdf（DOC-003）
- Page：7–7
- Section：遥控指令
- Chunk：B2-REMOTE-CHUNK-0008

<details><summary>Chunk Text</summary>

<pre>
[B2-REMOTE-CHUNK-0008]
B2 遥控器使用手册
机器狗参照示意图：
otics
侧视图
俯视图
正视图
机器狗
6tics
参照图
Unitr
遥控指令：
按键
效果
左摇杆
前后左右
右摇杆
左右旋转
姿态切换
解除锁定
START
灵动模式(默认）
L2(长按) + A (单击)
站立锁定/卧倒姿态切换
L2 (长按) + B (单击)
阻尼模式（软急停）
R1 (双击)
经典模式
L2 (长按) + START (单击)
跑步模式
otics
L2 (长按) + X (单击)
摔倒恢复站立
X(单击)
视觉模式
SELECT
摆姿势
L2 (双击)
低速档
L1 (双击)
© 2024 宇树科技 版权所有
Unit
</pre>

</details>

## B2 电池与充电器（8）

### EV-B2B-001 · 电池首次使用要求

- Knowledge Type：charging
- Question Potential：single
- Evidence Summary：obotics；电池是专门为B2四足机器人设计的一款带有充放电管理功能的电池。该款电池采用高性能电芯，并使用；宇树科技Unitree自主开发的先进电池管理系统(BMS)为 B2 四足机器人提供强劲的电力。
- Key Points：
  - obotics
  - 电池是专门为B2四足机器人设计的一款带有充放电管理功能的电池。该款电池采用高性能电芯，并使用
  - 宇树科技Unitree自主开发的先进电池管理系统(BMS)为 B2 四足机器人提供强劲的电力。
  - 243.00

- Document：宇树_B2电池与充电器使用说明_中文版.pdf（DOC-004）
- Page：2–2
- Section：简介
- Chunk：B2-BATTERY-CHUNK-0002

<details><summary>Chunk Text</summary>

<pre>
[B2-BATTERY-CHUNK-0002]
B2电池&充电器使用手册
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
[4] 卡扣
[3]
-[4]
[5] 泄压阀孔
[6]充电器接口
[5]
Unitr
[]]
[7] 防呆接口
obotics
O
-[6]
3宇树科技版权所有
2
</pre>

</details>

### EV-B2B-002 · 电池保护功能

- Knowledge Type：safety
- Question Potential：multi_chunk
- Evidence Summary：DC 50.4V；充电限制电压；DC 58.5V
- Key Points：
  - DC 50.4V
  - 充电限制电压
  - DC 58.5V
  - 45000mA，2268Wh

- Document：宇树_B2电池与充电器使用说明_中文版.pdf（DOC-004）
- Page：3–3
- Section：电池功能
- Chunk：B2-BATTERY-CHUNK-0003、B2-BATTERY-CHUNK-0004

<details><summary>Chunk Text</summary>

<pre>
[B2-BATTERY-CHUNK-0003]
ics
技术规格
电池
参数
规格
备注
尺寸
337mm*243mm*96mm
额定电压
DC 50.4V
ics
充电限制电压
DC 58.5V
额定容量
45000mA，2268Wh
运行时长
4-6h
Ur
电池功能
1. 电量显示：电池自带电量指示灯，可以显示当前电池电量。
2. 平衡充电保护：自动平衡电池内部电芯电压，以保护电池。
nitr
3. 过充电保护：过度充电会严重损伤电池，当电池充满后将自动停止充电。
4. 充电温度保护：在温度为0℃以下或50℃以上时充电会损坏电池，在此温度时电池将触发充电异常。
5. 充电电流保护：大电流充电将严重损伤电池，当充电电流大于20A，电池会触发充电过流异常。
6. 过放电保护：过度放电会严重损伤电池，当电池放电至39V，电池会切断输出，当电芯电压低于35V时
复充会先使用预充电功能，电流约300mA，直至恢复至42V电压为止等待时间较久。
7. 短路保护：在电池检测到短路的情况下，会切断输出，以保护电池；同时电池将使用指示灯提示故障。

[B2-BATTERY-CHUNK-0004]
7. 短路保护：在电池检测到短路的情况下，会切断输出，以保护电池；同时电池将使用指示灯提示故障。
8. 电池负载检测保护：当电池未插入机器狗时，电池将无法开启。当从机器狗拔出已开启的电池时，电池
将自动关闭。
9. 异常显示：电池LED灯可显示由异常导致的电池自保护的相关信息。
Unitree
©2023 宇树科技版权所有
3
Unitree Robotics
</pre>

</details>

### EV-B2B-003 · 查看与开关电池包

- Knowledge Type：operation
- Question Potential：single
- Evidence Summary：在电池包关闭状态下，短按电池开关一次，可查看当前电量。；电量指示灯可用于显示电池包充放电过程中的电池电量，指示灯定义如下。；表示LED灯常亮
- Key Points：
  - 在电池包关闭状态下，短按电池开关一次，可查看当前电量。
  - 电量指示灯可用于显示电池包充放电过程中的电池电量，指示灯定义如下。
  - 表示LED灯常亮
  - 表示LED灯闪烁

- Document：宇树_B2电池与充电器使用说明_中文版.pdf（DOC-004）
- Page：4–4
- Section：电量指示
- Chunk：B2-BATTERY-CHUNK-0005

<details><summary>Chunk Text</summary>

<pre>
[B2-BATTERY-CHUNK-0005]
B2电池&充电器使用手册
tics
电量指示
在电池包关闭状态下，短按电池开关一次，可查看当前电量。
电量指示灯可用于显示电池包充放电过程中的电池电量，指示灯定义如下。
O
表示LED灯常亮
表示LED灯闪烁
O
表示LED 灯熄灭
ics
电量指示灯
LED1
LED2
LED3
LED4
当前电量
O
87.5%-100%
O
O
75%-87.5%
O
62.5%-75%
O
O
50%-62.5%
O
O
37.5%-50%
O
O
O
25%-37.5%
O
O
O
O
12.5%-25%
O
O
O
0%-12.5%
O
O
O
O
=0%
开启/关闭电池
●开启电池：在关闭状态下，先短按池开关（按键）一次，再长按
电池开关（按键)3秒以上，即可开启电池。电池开启时，指示灯为绿
灯且显示当前电池电量。
●关闭电池：在开启状态下，先短按电池开关（按键）一次，再长
LED4
按电源开关3秒以上，即可关闭电池。电池关闭后，指示灯均熄灭。
LED2
O
LED1
6tics
Unitree
LED3
宇树科技版权所有
4
</pre>

</details>

### EV-B2B-004 · 插入式充电器规格

- Knowledge Type：specification
- Question Potential：single
- Evidence Summary：Unitre；ree Roboti；接触式充电器是专门为B2设计的，可与视觉识别、SLAM导航等技术相结合，自主规划充电路线，完成
- Key Points：
  - Unitre
  - ree Roboti
  - 接触式充电器是专门为B2设计的，可与视觉识别、SLAM导航等技术相结合，自主规划充电路线，完成
  - 自动充电，大幅提升作业时间和效率，为全天候作业提供有力的保障。B2-接触式充电器由锂电池充电器和接触

- Document：宇树_B2电池与充电器使用说明_中文版.pdf（DOC-004）
- Page：5–5
- Section：充电器
- Chunk：B2-BATTERY-CHUNK-0006

<details><summary>Chunk Text</summary>

<pre>
[B2-BATTERY-CHUNK-0006]
充电器
botics
简介
插入式充电器是专门为B2电池配置的一个充电设备，体积小，重量轻，方便携带，为电池提供稳定的电
CS
力。
0.
Unitre
ree Roboti
接触式充电器是专门为B2设计的，可与视觉识别、SLAM导航等技术相结合，自主规划充电路线，完成
自动充电，大幅提升作业时间和效率，为全天候作业提供有力的保障。B2-接触式充电器由锂电池充电器和接触
式充电板组成。
【充电电极】
0.
Hics
【电源接口】
锂电池充电器
接触式充电板
技术规格
YCS
插入式充电器
参数
规格
备注
产品尺寸
268mm*133mm*68.5mm
输入
100-240V~50/60Hz 7.5A
输出
58.8V, 10A, 588W
充电时长
3h'20min
© 2023 宇树科技 版权所有
5
Unit
</pre>

</details>

### EV-B2B-005 · 接触式充电器保护

- Knowledge Type：safety
- Question Potential：multi_chunk
- Evidence Summary：接触式充电器；684mm*390mm*19.5mm；100-240V~50/60Hz 7.5A
- Key Points：
  - 接触式充电器
  - 684mm*390mm*19.5mm
  - 100-240V~50/60Hz 7.5A
  - 58.8V, 10A, 588W

- Document：宇树_B2电池与充电器使用说明_中文版.pdf（DOC-004）
- Page：6–6
- Section：接触式充电器功能
- Chunk：B2-BATTERY-CHUNK-0007、B2-BATTERY-CHUNK-0008

<details><summary>Chunk Text</summary>

<pre>
[B2-BATTERY-CHUNK-0007]
B2 电池&充电器使用手册
tics
接触式充电器
参数
规格
备注
适用型号
B2
充电板尺寸
684mm*390mm*19.5mm
输入
100-240V~50/60Hz 7.5A
输出
58.8V, 10A, 588W
ics
充电时长
3h'20min
工作环境温度
5℃-40℃
理想充电温度
防护等级
IP67
不小于IP67
存储温度
22℃-28℃
理想保存温度
相对湿度
≤95%
大气压力
70~106Kpa
冷却方式
自冷+风冷
接触式充电器功能
1. 型号识别：充电板可识别机器人型号，避免不同电池型号(电压)的机器人错误连接充电板，避免充电
板对未知型号的机器人/电池/负载进行供电。
2. 过流保护：大电流充电将严重损伤电池，当充电电流大于15A，充电板会触发充电过流异常提醒。
3. 极板短路保护：在充电极板短路瞬间触发，保护会切断短路极板与充电器/电池的连接，短路点断开后自
动恢复充电。
4. 极板抖动保护：在充电极板不可靠接触时，保护会切断充电器与电池的连接，避免接触时产生的极板打
火现象，机器人起身并再次卧下后可自动恢复充电。

[B2-BATTERY-CHUNK-0008]
火现象，机器人起身并再次卧下后可自动恢复充电。
5. 充满断路保护：充电电流<1A时，自动断开充电器与电池的连接。
Unitre
6
</pre>

</details>

### EV-B2B-006 · 插入式充电流程

- Knowledge Type：charging
- Question Potential：single
- Evidence Summary：1. 连接充电器到交流电源(100-240V，50/60Hz)。连接前必须确保外接电源电压与充电器额定输入电压；匹配，否则会导致充电器损坏（在充电器铭牌上有标识该充电器的额定输入电压）。；2. 给电池充电前，先插入输入交流电源，然后充电器接电池。
- Key Points：
  - 1. 连接充电器到交流电源(100-240V，50/60Hz)。连接前必须确保外接电源电压与充电器额定输入电压
  - 匹配，否则会导致充电器损坏（在充电器铭牌上有标识该充电器的额定输入电压）。
  - 2. 给电池充电前，先插入输入交流电源，然后充电器接电池。
  - 4. 对电池包进行充电时，需要将电池包从机身内取出。

- Document：宇树_B2电池与充电器使用说明_中文版.pdf（DOC-004）
- Page：7–7
- Section：电池充电
- Chunk：B2-BATTERY-CHUNK-0009

<details><summary>Chunk Text</summary>

<pre>
[B2-BATTERY-CHUNK-0009]
电池充电
botics
插入式充电器
1. 连接充电器到交流电源(100-240V，50/60Hz)。连接前必须确保外接电源电压与充电器额定输入电压
匹配，否则会导致充电器损坏（在充电器铭牌上有标识该充电器的额定输入电压）。
2. 给电池充电前，先插入输入交流电源，然后充电器接电池。
4. 对电池包进行充电时，需要将电池包从机身内取出。
5. 充电状态下电池包电量指示灯会按1Hz(1 秒/次）频率闪烁，并指示当前电量。
Robotics
6. 电量指示灯全部熄灭时表示电池包已充满。请取下电池包和充电器，完成充电。
7. 机器人运行结束后电池包温度可能较高，必须待电池包温度降至室温后再对电池包进行充电。
8. 充电连接示意图：
Unit
tics
。
Unitree R
© 2023 宇树科技 版权所有
7
Unitree Robotics
</pre>

</details>

### EV-B2B-007 · 接触式充电流程

- Knowledge Type：charging
- Question Potential：single
- Evidence Summary：接触式充电器；1. 充电前检查：在每次充电前，请检查 B2机身底部的充电电极是否有异物遮挡，以及充电板充电电极表；面是否有异物遮挡。请使用干燥抹布擦拭充电电极表面，确保充电过程中良好接触。
- Key Points：
  - 接触式充电器
  - 1. 充电前检查：在每次充电前，请检查 B2机身底部的充电电极是否有异物遮挡，以及充电板充电电极表
  - 面是否有异物遮挡。请使用干燥抹布擦拭充电电极表面，确保充电过程中良好接触。
  - 2. 连接电源：将 B2 接触式充电器放置在空旷室内，先将锂电池充电器接入输入交流电源，然后连接接触

- Document：宇树_B2电池与充电器使用说明_中文版.pdf（DOC-004）
- Page：8–8
- Section：接触式充电器
- Chunk：B2-BATTERY-CHUNK-0010

<details><summary>Chunk Text</summary>

<pre>
[B2-BATTERY-CHUNK-0010]
B2电池&充电器使用手册
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
接触式充电板
锂电池充电器
3. 充电：使用接触式充电器充电时，先用遥控器操控机器人按照充电板面贴方向卧倒，请勿反冲！使 B2
机器人底部2个充电电极与充电板2个充电电极接触，实现充电。当电量充满时，会自动断开充电器与
电池的连接。
Robot
botics
Unitre
8
</pre>

</details>

### EV-B2B-008 · 电池长期存放维护

- Knowledge Type：maintenance
- Question Potential：multi_chunk
- Evidence Summary：2. 禁止将电池包放在靠近热源的地方，比如阳光直射或热天的车内、火源或加热炉。电池包理想保存温度；为 20℃-25℃，电池包理想保存环境湿度：45%-75%。；3. 储存时，请注意确保电池周边的环境散热良好，没有杂物等易燃易爆物品。
- Key Points：
  - 2. 禁止将电池包放在靠近热源的地方，比如阳光直射或热天的车内、火源或加热炉。电池包理想保存温度
  - 为 20℃-25℃，电池包理想保存环境湿度：45%-75%。
  - 3. 储存时，请注意确保电池周边的环境散热良好，没有杂物等易燃易爆物品。
  - 4. 存放电池包的环境应保持干燥。请勿将电池包置于水中或者可能会漏水的地方。

- Document：宇树_B2电池与充电器使用说明_中文版.pdf（DOC-004）
- Page：11–11
- Section：存储和运输
- Chunk：B2-BATTERY-CHUNK-0017、B2-BATTERY-CHUNK-0018

<details><summary>Chunk Text</summary>

<pre>
[B2-BATTERY-CHUNK-0017]
存储和运输
itre
1. 不使用电池包时，请将电池包从机器人中取出并存放在儿童接触不到的地方。
2. 禁止将电池包放在靠近热源的地方，比如阳光直射或热天的车内、火源或加热炉。电池包理想保存温度
为 20℃-25℃，电池包理想保存环境湿度：45%-75%。
3. 储存时，请注意确保电池周边的环境散热良好，没有杂物等易燃易爆物品。
4. 存放电池包的环境应保持干燥。请勿将电池包置于水中或者可能会漏水的地方。
5. 禁止机械撞击、碾压、刺穿电池包，禁止将电池包跌落或人为短路。
6. 禁止将电池包与眼镜、手表、金属项链、发夹或者其他金属物体一起贮藏或运输。
7. 切勿运输有破损的电池包。一旦需要运输电池包，务必将电池包放电至65%电量左右。
8. 切勿将电池包彻底放完电后长时间存储，以避免电池包进入过放状态，造成电芯损坏，将无法恢复使用。
●保养
1. 切勿在温度过高或温度过低的环境下使用充电器对电池进行充电。
2. 切勿将电池存储在室温超过 40℃的环境下。

[B2-BATTERY-CHUNK-0018]
●保养
1. 切勿在温度过高或温度过低的环境下使用充电器对电池进行充电。
2. 切勿将电池存储在室温超过 40℃的环境下。
3. 切勿过充电池，否则将对电芯造成损害。
tics
若较长时间不使用电池时，请定期检查电池剩余的电量，如果电量低于30%，请把电池充电到70%后
再继续保存。以免电池过放而损坏电池。
Uni
废弃
Ro
鼓包、跌落、进水、破损等损坏的电池需要进行报废处理，不得继续使用，以免引起安全风险。务必将电
池彻底放完电后，才将电池置于指定的电池回收箱中。电池是危险化学品，严禁废置于普通垃圾箱。相关细节，
请遵循当地电池回收和弃置的法律法规。
©2023 宇树科技版权所有
11
Unitr
</pre>

</details>

## 随机 Evidence Check

方法：固定种子 20260914；按 evidence_id 字典序以 LCG 排序取前 10 条。每条核对 Chunk 元数据、逐字 Chunk Text、摘要/要点与原始 PDF 页。
抽查数量：10
通过数量：10

### EV-KIRA-004

- 来源：卡赫_KIRA_B_50完整操作说明_中文版.pdf · P.17–17 · KIRA-B50-CHUNK-0036
- 结论：Passed
  - Chunk ID uniquely resolved in chunks.json
  - Document, page, and section match selected chunk metadata
  - evidence_text equals current chunk_text
  - Summary and key points manually checked against source chunk and PDF page

### EV-KIRA-008

- 来源：卡赫_KIRA_B_50完整操作说明_中文版.pdf · P.46–46 · KIRA-B50-CHUNK-0084
- 结论：Passed
  - Chunk ID uniquely resolved in chunks.json
  - Document, page, and section match selected chunk metadata
  - evidence_text equals current chunk_text
  - Summary and key points manually checked against source chunk and PDF page

### EV-KIRA-009

- 来源：卡赫_KIRA_B_50完整操作说明_中文版.pdf · P.46–47 · KIRA-B50-CHUNK-0085
- 结论：Passed
  - Chunk ID uniquely resolved in chunks.json
  - Document, page, and section match selected chunk metadata
  - evidence_text equals current chunk_text
  - Summary and key points manually checked against source chunk and PDF page

### EV-KIRA-011

- 来源：卡赫_KIRA_B_50完整操作说明_中文版.pdf · P.58–58 · KIRA-B50-CHUNK-0094
- 结论：Passed
  - Chunk ID uniquely resolved in chunks.json
  - Document, page, and section match selected chunk metadata
  - evidence_text equals current chunk_text
  - Summary and key points manually checked against source chunk and PDF page

### EV-KIRA-013

- 来源：卡赫_KIRA_B_50完整操作说明_中文版.pdf · P.86–86 · KIRA-B50-CHUNK-0120
- 结论：Passed
  - Chunk ID uniquely resolved in chunks.json
  - Document, page, and section match selected chunk metadata
  - evidence_text equals current chunk_text
  - Summary and key points manually checked against source chunk and PDF page

### EV-B2M-001

- 来源：宇树_B2四足机器人用户手册_中文版.pdf · P.10–10 · B2-MANUAL-CHUNK-0018、B2-MANUAL-CHUNK-0019
- 结论：Passed
  - Chunk ID uniquely resolved in chunks.json
  - Document, page, and section match selected chunk metadata
  - evidence_text equals current chunk_text
  - Summary and key points manually checked against source chunk and PDF page

### EV-B2R-001

- 来源：宇树_B2遥控器使用说明_中文版.pdf · P.5–5 · B2-REMOTE-CHUNK-0006
- 结论：Passed
  - Chunk ID uniquely resolved in chunks.json
  - Document, page, and section match selected chunk metadata
  - evidence_text equals current chunk_text
  - Summary and key points manually checked against source chunk and PDF page

### EV-B2R-005

- 来源：宇树_B2遥控器使用说明_中文版.pdf · P.4–4 · B2-REMOTE-CHUNK-0005
- 结论：Passed
  - Chunk ID uniquely resolved in chunks.json
  - Document, page, and section match selected chunk metadata
  - evidence_text equals current chunk_text
  - Summary and key points manually checked against source chunk and PDF page

### EV-B2B-003

- 来源：宇树_B2电池与充电器使用说明_中文版.pdf · P.4–4 · B2-BATTERY-CHUNK-0005
- 结论：Passed
  - Chunk ID uniquely resolved in chunks.json
  - Document, page, and section match selected chunk metadata
  - evidence_text equals current chunk_text
  - Summary and key points manually checked against source chunk and PDF page

### EV-B2B-006

- 来源：宇树_B2电池与充电器使用说明_中文版.pdf · P.7–7 · B2-BATTERY-CHUNK-0009
- 结论：Passed
  - Chunk ID uniquely resolved in chunks.json
  - Document, page, and section match selected chunk metadata
  - evidence_text equals current chunk_text
  - Summary and key points manually checked against source chunk and PDF page

## 边界确认

- 是否生成 Golden Dataset：否
- 是否修改 Evaluation：否
- 是否运行 Baseline Evaluation：否
- 是否修改 Retrieval、Chunking、Agent 或前端：否
