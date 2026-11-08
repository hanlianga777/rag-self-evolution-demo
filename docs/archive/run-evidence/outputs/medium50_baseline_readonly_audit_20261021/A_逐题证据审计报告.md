# A. 最新 Medium50 Baseline 逐题证据审计报告

审计日期：2026-10-21（Asia/Shanghai）。仅审计，未修复、未重评、未调用Provider。

## 审计对象与边界

- 数据库：`/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/data/demo.db`，使用SQLite URI `mode=ro`读取；没有初始化Store/迁移/写API。
- 最新Baseline尝试：`EVAL-20261021013401711966`，创建UTC `2026-10-21T01:34:01.744846+00:00`（北京时间09:34:01），状态`partial`，50 attempted / 49 completed / 10 business FAIL / 1 technical error。39题业务PASS。没有完整Overall或Gate通过资格。
- 冻结Golden：`GD-20261015135415953347`；run.dataset_snapshot_json与dataset_versions.snapshot_json解析后完全一致，题集50。当前工作集questions表没有被用来替代冻结内容。
- Corpus：`CORPUS-38c90d5628b68c76d53e`；368 Child。16项Manifest制品SHA均相符，四份实际PDF的SHA均与冻结sources一致。候选和Final的全部正文/Parent及元数据均通过现有Canonical验证（10道业务FAIL）。
- 源码HEAD：`a32e6730fce36eb07b73b1872fd85c92f064e270`；有本轮前已存在的未提交文件，本轮不修改它们。
- Judge：`judge-vnext-4-output-contract`；Parser `business-output-4-negative-facts`；Matcher `evidence-vnext-1`；Policy `business-vnext-1`；Identity `d18aab6365a63c6de63e295866a7036e0fe6a25f1f74c2afbb4782bbab73ae3e`。当前源码Prompt SHA、Generation Boundary SHA和Identity计算均与保存身份相符。
- 正式可用Baseline resolver仍选旧Completed `EVAL-20261015140115663135`，并标requires_policy_upgrade=true；本次最新Partial不是Agent当前可运行正式基线。逐题target_eligible只是局部条件，不能跨过整轮身份/完整性门槛。

## 结论总览

| 题目 | 独立业务结论 | 人工证据定位的主要根因 | 当前程序 | 现有工具箱的可验证范围 |
|---|---|---|---|---|
| Q03 | FAIL合理 | Ranking | Ranking / True | 关闭rerank并Top6 |
| Q04 | FAIL合理 | Ranking | Ranking / True | Top6 |
| Q06 | FAIL合理 | Ranking（必要电气规范） | Ranking / True | Top6 |
| Q07 | FAIL合理 | Retrieval（维护总则） | Unknown / False | 待诊断闭合；召回/查询假设 |
| Q08 | FAIL合理 | Ranking，部分Final被误当完整规范 | Generation / True | Top6可补证据，但当前view不允许该方向 |
| Q17 | FAIL合理 | Retrieval（R3分支） | Unknown / False | 待范围闭合；召回/查询假设 |
| Q24 | FAIL合理 | Retrieval（运行安全条款） | Unknown / False | 待候选审查字段闭合；召回/查询假设 |
| Q27 | FAIL合理 | Ranking；另有条件误用 | Ranking / True | 固定池内16种合法context选择均不可恢复核心条款 |
| Q28 | FAIL合理 | Retrieval；Judge诊断引用有错 | Unknown / False | 待规范定位与候选审查闭合 |
| Q29 | FAIL合理 | Retrieval（整机检查表） | Unknown / False | 待表格范围与逐项规范闭合 |
| Q18 | 独立技术异常 | Judge标题元数据引用合同失败 | 技术异常，无业务判定 | 授权后可仅补Judge；零调用不能合法补分 |

十道历史业务FAIL均有至少一项明确、适用的必要事实缺失，未发现足以把整题改PASS的Golden错误。局部争议包括Q24对“制造商说明”的等价覆盖、Q28安全越界标签、若干critical严重性及Q18的B2型号泛化；它们不等同于历史分数被更改。

## 读取与判定方法

先核冻结题意/完整参考答案，再阅读对应PDF与Corpus正文，对照候选Child、保存reranked、扩展Parent Final全文与回答。以下表格的“无”只说明指定来源未在该阶段出现；是否缺少必要事实由紧随的等价证据说明和完整阶段正文核对决定，不以ID或字符串本身作为检索失败定义。候选阶段是post_metadata_filter_fusion_candidate_cap_pre_rerank，已经过融合与CandidateK截断，不能进一步冒称未记录的更早阶段失败。

只读调用了现有validate_business_judgment、business_analysis、diagnostic_view、Canonical检查、expand_parents与身份/恢复校验；未运行RAG检索/生成/真实Judge。离线TopK演算只重选保存记录，没有重跑Baseline。部分PDF为扫描页：B2整机PDF18（印刷17）、R3 PDF6、充电器PDF12经本地渲染直接目视核对；PDF10/9/48/85等文本页直接提取核对。

源码定位：[backend/app/diagnostics.py:302](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/diagnostics.py:302)；[backend/app/evaluation_contract.py:320](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/evaluation_contract.py:320)；[backend/app/optimization.py:16](/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/app/optimization.py:16)。详细代码问题见同目录B报告。

## Q03 — FAIL合理；必要入口步骤遗漏，不是主管权限流程整体错误。

真实题号：`V1G-110926448917-03`；类别：`positive`。

### 1. 冻结Golden与实际回答

**问题（完整）**

```text
KIRA B 50 上怎么给新来的清洁主管创建一个独立用户账号？
```

**冻结参考答案（完整，保留原始文字）**

```text
按主菜单中按下设置按钮
显示设置菜单。
在设置菜单中按下“用户配置”按钮
按下“新用户”按钮
选择所需语言
点击用户名的输入栏
利用屏幕上的键盘输入用户名，点击回车键完成
按下“密码”按钮
点击“密码输入”输入栏
利用屏幕上的键盘输入密码
在“密码确认”输入栏中再次输入密码进行确认
按下操作按钮
按下“权限”按钮-
按下所需用户组的出厂设置按钮 操作人员 或 主管
如有必要，可以更改列表中的个别权限
按下操作按钮
```

**冻结Golden evidence字段（原样；摘要不能冒充完整规范）**

```json
[
  {
    "evidence_key_points": [
      "设置\n1. 按主菜单中按下设置按钮\nLorem ipsum dolor sit\nLorem ipsum dolor sit\nLorem ipsum dolor sit\n\n1 “用户配置”按钮\n显示设置菜单。\n1 创建和管理用户\n2 设置时间和日期\n3 配置网络连接\n4 系统信息（工作时间<sub>、</sub>软件版",
      "1. 在设置菜单中按下“用户配置”按钮\n2. 按下“新用户”按钮\n\n3. 选择所需语言\n4. 点击用户名的输入栏\n5. 利用屏幕上的键盘输入用户名，点击回车键完成\n6. 按下“密码”按钮\n7. 点击“密码输入”输入栏\n8. 利用屏幕上的键盘输入密码\n9. 在“密码确认”输入栏中再次输入密码进行确认\n\n10. 按下操"
    ],
    "source_chunk_ids": [
      "DOC-001-C-00132",
      "DOC-001-C-00134"
    ]
  }
]
```

**RAG实际回答（完整）**

```text
可以按手册创建“独立用户”，并在权限用户组中选择“主管”。仅在已确认该清洁主管应获得主管权限时操作；手册未给出账号审批、密码策略等要求，需另行确认。

操作步骤（据 DOC-001-C-00134）：
1. 在设置菜单中按“用户配置”。
2. 按“新用户”。
3. 选择所需语言。
4. 点击用户名输入栏，用屏幕键盘输入其用户名，按回车完成。
5. 按“密码”，在“密码输入”栏输入密码；再在“密码确认”栏重复输入确认。
6. 按操作按钮。
7. 按“权限”。
8. 在权限列表中选择所需用户组的出厂设置按钮“主管”（不要选“操作人员”，除非实际权限不是主管）。
9. 如有必要，在列表中调整个别权限。
10. 按操作按钮完成。

依据：创建用户流程见 [DOC-001-C-00134 | S1 | 页49–51]；章节为“创建用户”见 [DOC-001-C-00133 | S1 | 页49–49]。设备接通后需等待触摸屏出现登录界面，见 [DOC-001-C-00129 | S1 | 页46–47]；但证据未说明从登录界面进入“设置菜单”的具体方法，不能补造。

未确认事项：该设备当前账号是否有权进入设置菜单、密码规则、账号命名规则、是否需要管理员审批，资料中均未说明。
```

### 2. 独立原文、范围与等价证据判断

同产品设置章节C00132（PDF48–49）明确主菜单按设置；Final只有C00134的设置菜单内后续步骤、创建用户标题、开机和封面，不含等价入口。不能把登录界面存在当作有“进入设置”的操作证据。

**必要事实逐项链路**

| 必要事实/安全条件 | Corpus原文定位 | Candidate序号 | Rerank序号 | Final条目序号 | Answer与等价范围核查 |
|---|---|---|---|---|---|
| 主菜单按设置，显示设置菜单 | DOC-001-C-00132 / PDF 48–49 | 3 | 10 | 无 | 遗漏入口；“在设置菜单”不等于说明如何进入 |
| 设置菜单→用户配置→新用户→选择语言 | DOC-001-C-00134 / PDF 49–51 | 6 | 1 | 1 | 完整表达 |
| 用户名输入、回车完成 | DOC-001-C-00134 / PDF 49–51 | 6 | 1 | 1 | 完整表达 |
| 密码输入与重复确认，再按操作按钮 | DOC-001-C-00134 / PDF 49–51 | 6 | 1 | 1 | 完整表达 |
| 权限→选择主管用户组；必要时调整权限；操作按钮完成 | DOC-001-C-00134 / PDF 49–51 | 6 | 1 | 1 | 完整表达；没有证据支持强加密码策略/审批规则 |

### 3. 失败归因、实际程序条件与可优化性

**独立归因：** Ranking / Context Selection。候选3→rerank10→Top4排除；之后回答缺入口是结果，不能把主因写成候选未召回。

**当前程序的确定路径：** checks[0]：met=false、scope_resolved=true、support=[]；reference_support在Corpus真实定位且candidate_support为非空列表并在候选定位，命中diagnostics.py:328–331；当前view为Ranking、ranking_omission、context_selection、target_eligible=true。

**工具箱与可验证假设：** 可验证策略：rerank=false + top_k=6，同一context_selection方向的必要联动，离线复用候选能同时保留C00132与C00134；只Top6仍漏入口，只关闭rerank取Top4又漏后续流程。该演算只证明上下文包含原文，不证明新的生成回答会PASS。

**建议处理：** 保留FAIL；审阅后可用现有工具箱提出该单一上下文选择假设。Judge把入口遗漏标critical=true但safety_violation=false；这不证明安全边界违规，严重性另审，不自动改级。

**完整只读诊断输出（省去耗时明细，仅保留准入与证据）**

```json
{
  "primary_root_cause": "Ranking",
  "target_eligible": true,
  "is_technical_bad_case": true,
  "retrieval_failure_stage": "ranking_context_selection",
  "trace_observations": [
    "ranking_omission"
  ],
  "optimization_directions": [
    "context_selection"
  ],
  "evidence_checks": [
    {
      "answer_quotes": [
        "1. 在设置菜单中按“用户配置”。",
        "但证据未说明从登录界面进入“设置菜单”的具体方法，不能补造。"
      ],
      "candidate_support": [
        {
          "quote": "1. 按主菜单中按下设置按钮\nLorem ipsum dolor sit\nLorem ipsum dolor sit\nLorem ipsum dolor sit\n\n1 “用户配置”按钮\n显示设置菜单。",
          "source_id": "DOC-001-C-00132"
        }
      ],
      "check_type": "fact",
      "met": false,
      "reference_support": [
        {
          "quote": "1. 按主菜单中按下设置按钮\nLorem ipsum dolor sit\nLorem ipsum dolor sit\nLorem ipsum dolor sit\n\n1 “用户配置”按钮\n显示设置菜单。",
          "source_id": "DOC-001-C-00132"
        }
      ],
      "requirement": "需从主菜单按“设置”按钮进入设置菜单，再按“用户配置”；当前回答未给出该入口步骤。",
      "scope_resolved": true,
      "support": [],
      "candidate_missing": false
    }
  ]
}
```

### 4. Judge原始判定与检查（未改写）

保存业务verdict=FAIL；原始Judge verdict=FAIL。
<details><summary>完整原始Provider JSON（含所有checks、issues、support与reason）</summary>

```json
{"verdict":"FAIL","checks":[{"check_type":"fact","requirement":"需从主菜单按“设置”按钮进入设置菜单，再按“用户配置”；当前回答未给出该入口步骤。","met":false,"answer_quotes":["1. 在设置菜单中按“用户配置”。","但证据未说明从登录界面进入“设置菜单”的具体方法，不能补造。"],"support":[],"reference_support":[{"source_id":"DOC-001-C-00132","quote":"1. 按主菜单中按下设置按钮\nLorem ipsum dolor sit\nLorem ipsum dolor sit\nLorem ipsum dolor sit\n\n1 “用户配置”按钮\n显示设置菜单。"}],"candidate_support":[{"source_id":"DOC-001-C-00132","quote":"1. 按主菜单中按下设置按钮\nLorem ipsum dolor sit\nLorem ipsum dolor sit\nLorem ipsum dolor sit\n\n1 “用户配置”按钮\n显示设置菜单。"}],"scope_resolved":true},{"check_type":"fact","requirement":"在设置菜单中按“用户配置”。","met":true,"answer_quotes":["1. 在设置菜单中按“用户配置”。"],"support":[{"source_id":"DOC-001-C-00134","quote":"1. 在设置菜单中按下“用户配置”按钮"}],"scope_resolved":true},{"check_type":"fact","requirement":"按“新用户”。","met":true,"answer_quotes":["2. 按“新用户”。"],"support":[{"source_id":"DOC-001-C-00134","quote":"2. 按下“新用户”按钮"}],"scope_resolved":true},{"check_type":"fact","requirement":"选择所需语言。","met":true,"answer_quotes":["3. 选择所需语言。"],"support":[{"source_id":"DOC-001-C-00134","quote":"3. 选择所需语言"}],"scope_resolved":true},{"check_type":"fact","requirement":"点击用户名输入栏，用屏幕键盘输入用户名并回车完成。","met":true,"answer_quotes":["4. 点击用户名输入栏，用屏幕键盘输入其用户名，按回车完成。"],"support":[{"source_id":"DOC-001-C-00134","quote":"4. 点击用户名的输入栏\n5. 利用屏幕上的键盘输入用户名，点击回车键完成"}],"scope_resolved":true},{"check_type":"fact","requirement":"设置密码，并在“密码确认”栏再次输入确认。","met":true,"answer_quotes":["5. 按“密码”，在“密码输入”栏输入密码；再在“密码确认”栏重复输入确认。"],"support":[{"source_id":"DOC-001-C-00134","quote":"6. 按下“密码”按钮\n7. 点击“密码输入”输入栏\n8. 利用屏幕上的键盘输入密码\n9. 在“密码确认”输入栏中再次输入密码进行确认"}],"scope_resolved":true},{"check_type":"fact","requirement":"密码确认后按操作按钮。","met":true,"answer_quotes":["6. 按操作按钮。"],"support":[{"source_id":"DOC-001-C-00134","quote":"10. 按下操作按钮"}],"scope_resolved":true},{"check_type":"fact","requirement":"按“权限”按钮。","met":true,"answer_quotes":["7. 按“权限”。"],"support":[{"source_id":"DOC-001-C-00134","quote":"11. 按下“权限”按钮-"}],"scope_resolved":true},{"check_type":"fact","requirement":"在权限列表中选择所需用户组的出厂设置按钮“主管”。","met":true,"answer_quotes":["8. 在权限列表中选择所需用户组的出厂设置按钮“主管”（不要选“操作人员”，除非实际权限不是主管）。"],"support":[{"source_id":"DOC-001-C-00134","quote":"12. 按下所需用户组的出厂设置按钮 操作人员 或 主管"}],"scope_resolved":true},{"check_type":"fact","requirement":"如有必要，在列表中调整个别权限。","met":true,"answer_quotes":["9. 如有必要，在列表中调整个别权限。"],"support":[{"source_id":"DOC-001-C-00134","quote":"13. 如有必要，可以更改列表中的个别权限"}],"scope_resolved":true},{"check_type":"fact","requirement":"最后按操作按钮完成创建。","met":true,"answer_quotes":["10. 按操作按钮完成。"],"support":[{"source_id":"DOC-001-C-00134","quote":"14. 按下操作按钮"}],"scope_resolved":true}],"issues":[{"description":"创建用户的端到端流程不完整：遗漏了从主菜单按“设置”按钮进入设置菜单的必要入口步骤，导致用户无法仅按现有步骤从当前界面开始操作。","answer_quotes":["1. 在设置菜单中按“用户配置”。","但证据未说明从登录界面进入“设置菜单”的具体方法，不能补造。"],"support":[],"critical":true,"safety_violation":false,"scope_resolved":true,"baseline_issue_index":null}],"reason":"回答的操作主体（KIRA B 50）、创建用户流程、密码设置、选择“主管”权限组及最终保存步骤基本有据，且对账号审批、密码策略等未说明事项作了谨慎提示。但参考流程要求先从主菜单按“设置”按钮进入设置菜单，回答直接从“在设置菜单中按用户配置”开始，缺少必要的入口步骤，属于端到端操作流程不完整，因此不能判为PASS。","quality":{"correctness":3,"faithfulness":1,"completeness":0.8}}
```

</details>

### 5. 可复查的完整阶段证据

<details><summary>各阶段来源顺序、完整候选正文、完整Final与规范原文</summary>

**候选→重排→Final顺序**

```json
{
  "candidates": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00130",
      "parent_chunk_id": "DOC-001-P-00129",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.999
    },
    {
      "position": 2,
      "chunk_id": "DOC-001-C-00002",
      "parent_chunk_id": "DOC-001-P-00002",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.944
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00132",
      "parent_chunk_id": "DOC-001-P-00131",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.895
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00133",
      "parent_chunk_id": "DOC-001-P-00132",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.8329
    },
    {
      "position": 5,
      "chunk_id": "DOC-001-C-00071",
      "parent_chunk_id": "DOC-001-P-00071",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7909
    },
    {
      "position": 6,
      "chunk_id": "DOC-001-C-00134",
      "parent_chunk_id": "DOC-001-P-00133",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7756
    },
    {
      "position": 7,
      "chunk_id": "DOC-001-C-00005",
      "parent_chunk_id": "DOC-001-P-00005",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.746
    },
    {
      "position": 8,
      "chunk_id": "DOC-001-C-00175",
      "parent_chunk_id": "DOC-001-P-00173",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7321
    },
    {
      "position": 9,
      "chunk_id": "DOC-001-C-00129",
      "parent_chunk_id": "DOC-001-P-00128",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5
    },
    {
      "position": 10,
      "chunk_id": "DOC-001-C-00119",
      "parent_chunk_id": "DOC-001-P-00118",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4264
    },
    {
      "position": 11,
      "chunk_id": "DOC-002-C-00036",
      "parent_chunk_id": "DOC-002-P-00031",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4261
    },
    {
      "position": 12,
      "chunk_id": "DOC-001-C-00113",
      "parent_chunk_id": "DOC-001-P-00112",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4169
    }
  ],
  "reranked": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00134",
      "parent_chunk_id": "DOC-001-P-00133",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.672323049611968,
      "rerank_score": 0.672323049611968
    },
    {
      "position": 2,
      "chunk_id": "DOC-001-C-00133",
      "parent_chunk_id": "DOC-001-P-00132",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5458857067318363,
      "rerank_score": 0.5458857067318363
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00129",
      "parent_chunk_id": "DOC-001-P-00128",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5406026436672009,
      "rerank_score": 0.5406026436672009
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00002",
      "parent_chunk_id": "DOC-001-P-00002",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5331285380744776,
      "rerank_score": 0.5331285380744776
    },
    {
      "position": 5,
      "chunk_id": "DOC-001-C-00130",
      "parent_chunk_id": "DOC-001-P-00129",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5231955505127467,
      "rerank_score": 0.5231955505127467
    },
    {
      "position": 6,
      "chunk_id": "DOC-001-C-00175",
      "parent_chunk_id": "DOC-001-P-00173",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4910457284782528,
      "rerank_score": 0.4910457284782528
    },
    {
      "position": 7,
      "chunk_id": "DOC-001-C-00005",
      "parent_chunk_id": "DOC-001-P-00005",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.46508261740742673,
      "rerank_score": 0.46508261740742673
    },
    {
      "position": 8,
      "chunk_id": "DOC-001-C-00119",
      "parent_chunk_id": "DOC-001-P-00118",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4561884289568732,
      "rerank_score": 0.4561884289568732
    },
    {
      "position": 9,
      "chunk_id": "DOC-002-C-00036",
      "parent_chunk_id": "DOC-002-P-00031",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.40952885861601723,
      "rerank_score": 0.40952885861601723
    },
    {
      "position": 10,
      "chunk_id": "DOC-001-C-00132",
      "parent_chunk_id": "DOC-001-P-00131",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4022076082966784,
      "rerank_score": 0.4022076082966784
    },
    {
      "position": 11,
      "chunk_id": "DOC-001-C-00071",
      "parent_chunk_id": "DOC-001-P-00071",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.35249528403460284,
      "rerank_score": 0.35249528403460284
    },
    {
      "position": 12,
      "chunk_id": "DOC-001-C-00113",
      "parent_chunk_id": "DOC-001-P-00112",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.34872409740417276,
      "rerank_score": 0.34872409740417276
    }
  ],
  "final": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00134",
      "parent_chunk_id": "DOC-001-P-00133",
      "matched_child_ids": [
        "DOC-001-C-00134"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.672323049611968,
      "rerank_score": 0.672323049611968
    },
    {
      "position": 2,
      "chunk_id": "DOC-001-C-00133",
      "parent_chunk_id": "DOC-001-P-00132",
      "matched_child_ids": [
        "DOC-001-C-00133"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5458857067318363,
      "rerank_score": 0.5458857067318363
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00129",
      "parent_chunk_id": "DOC-001-P-00128",
      "matched_child_ids": [
        "DOC-001-C-00129"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5406026436672009,
      "rerank_score": 0.5406026436672009
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00002",
      "parent_chunk_id": "DOC-001-P-00002",
      "matched_child_ids": [
        "DOC-001-C-00002"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5331285380744776,
      "rerank_score": 0.5331285380744776
    }
  ]
}
```

**全部候选正文（用于核查等价来源，而非只看ID）**
候选1：`DOC-001-C-00130` / `KIRA B 50`

```text
4. 创建一个新用户资料
5. 指定密码

```

候选2：`DOC-001-C-00002` / `KIRA B 50`

```text
KIRA B 50
KIRA B 50
ZH

```

候选3：`DOC-001-C-00132` / `KIRA B 50`

```text
设置
1. 按主菜单中按下设置按钮
Lorem ipsum dolor sit
Lorem ipsum dolor sit
Lorem ipsum dolor sit

1 “用户配置”按钮
显示设置菜单。
1 创建和管理用户
2 设置时间和日期
3 配置网络连接
4 系统信息（工作时间<sub>、</sub>软件版本<sub>、</sub>材料编号<sub>、</sub>序列号<sub>、</sub>更新）<sub>。</sub>
```

候选4：`DOC-001-C-00133` / `KIRA B 50`

```text
创建用户
```

候选5：`DOC-001-C-00071` / `KIRA B 50`

```text
示例：
一位用户拥有巨大的仓储场地 他在这里为设备创建了一个对接站 适当划分仓库之后，可以为各个清洁区示教多条路线 这些路线的起点和终点位于仓库中的对接站 为了自动清洁整个仓库或多个区域，可以连接多条路线 然后先后驶过这些路线，每条路线之后都会有一个对接过程 必要时会更换该设备的资源

```

候选6：`DOC-001-C-00134` / `KIRA B 50`

```text
1. 在设置菜单中按下“用户配置”按钮
2. 按下“新用户”按钮

3. 选择所需语言
4. 点击用户名的输入栏
5. 利用屏幕上的键盘输入用户名，点击回车键完成
6. 按下“密码”按钮
7. 点击“密码输入”输入栏
8. 利用屏幕上的键盘输入密码
9. 在“密码确认”输入栏中再次输入密码进行确认

10. 按下操作按钮
11. 按下“权限”按钮-
1 确认2 “权限”按钮3 权限列表4 出厂设置权限 操作人员5 出厂设置权限 主管
12. 按下所需用户组的出厂设置按钮 操作人员 或 主管
13. 如有必要，可以更改列表中的个别权限
14. 按下操作按钮
```

候选7：`DOC-001-C-00005` / `KIRA B 50`

```text
用户群体
本说明书面向用户群体 操作人员 和 主管
可以通过设备触摸屏向每位用户分配或拒绝不同设备功能的权限
本说明书中的所有描述均属于面向相应用户群体所建议设备基本设置
```

候选8：`DOC-001-C-00175` / `KIRA B 50`

```text
提示
可以后续移动已创建的事件或新创建的事件 对此必须按下和移动标记
3. 在设置标记“清洁”时定义清洁参数
4. 点击“返回”<sub>。</sub>
现在保存该事件的清洁参数。
```

候选9：`DOC-001-C-00129` / `KIRA B 50`

```text
接通设备
1. 通过旋转解锁紧急停机按钮
2. 按下启动键设备启动。
3. 请等待，直到触摸屏上出现登录界面
提示

服务：只适用于客户服务
操作人员：通过 主管 所分配的权限定义功能范围，可利用该功能范围
```

候选10：`DOC-001-C-00119` / `KIRA B 50`

```text
提示：
为了快速更换清洁剂，可以取下清洁剂罐，并换上另一个清洁剂罐
```

候选11：`DOC-002-C-00036` / `B2 四足机器人`

```text
操控您的B2
```

候选12：`DOC-001-C-00113` / `KIRA B 50`

```text
加注运行材料
淡水
结合对接站运行时，会自动填充清水箱
1. 在智能手机上扫描以下代码，按指示下载操作说明书
```

**完整Final（Parent展开后的真实模型输入正文）**
Final 1：`DOC-001-C-00134` / Parent `DOC-001-P-00133` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 49–51；source_scope=null

```text
1. 在设置菜单中按下“用户配置”按钮
2. 按下“新用户”按钮

3. 选择所需语言
4. 点击用户名的输入栏
5. 利用屏幕上的键盘输入用户名，点击回车键完成
6. 按下“密码”按钮
7. 点击“密码输入”输入栏
8. 利用屏幕上的键盘输入密码
9. 在“密码确认”输入栏中再次输入密码进行确认

10. 按下操作按钮
11. 按下“权限”按钮-
1 确认2 “权限”按钮3 权限列表4 出厂设置权限 操作人员5 出厂设置权限 主管
12. 按下所需用户组的出厂设置按钮 操作人员 或 主管
13. 如有必要，可以更改列表中的个别权限
14. 按下操作按钮
```

Final 2：`DOC-001-C-00133` / Parent `DOC-001-P-00132` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 49–49；source_scope=null

```text
创建用户
```

Final 3：`DOC-001-C-00129` / Parent `DOC-001-P-00128` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 46–47；source_scope=null

```text
接通设备
1. 通过旋转解锁紧急停机按钮
2. 按下启动键设备启动。
3. 请等待，直到触摸屏上出现登录界面
提示

服务：只适用于客户服务
操作人员：通过 主管 所分配的权限定义功能范围，可利用该功能范围
```

Final 4：`DOC-001-C-00002` / Parent `DOC-001-P-00002` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 1–1；source_scope=null

```text
KIRA B 50
KIRA B 50
ZH

```

**本题规范原文与元数据（Corpus完整Child）**
`DOC-001-C-00132`；KIRA B 50；PDF 48–49；version=None

```text
设置
1. 按主菜单中按下设置按钮
Lorem ipsum dolor sit
Lorem ipsum dolor sit
Lorem ipsum dolor sit

1 “用户配置”按钮
显示设置菜单。
1 创建和管理用户
2 设置时间和日期
3 配置网络连接
4 系统信息（工作时间<sub>、</sub>软件版本<sub>、</sub>材料编号<sub>、</sub>序列号<sub>、</sub>更新）<sub>。</sub>
```

`DOC-001-C-00134`；KIRA B 50；PDF 49–51；version=None

```text
1. 在设置菜单中按下“用户配置”按钮
2. 按下“新用户”按钮

3. 选择所需语言
4. 点击用户名的输入栏
5. 利用屏幕上的键盘输入用户名，点击回车键完成
6. 按下“密码”按钮
7. 点击“密码输入”输入栏
8. 利用屏幕上的键盘输入密码
9. 在“密码确认”输入栏中再次输入密码进行确认

10. 按下操作按钮
11. 按下“权限”按钮-
1 确认2 “权限”按钮3 权限列表4 出厂设置权限 操作人员5 出厂设置权限 主管
12. 按下所需用户组的出厂设置按钮 操作人员 或 主管
13. 如有必要，可以更改列表中的个别权限
14. 按下操作按钮
```

</details>

## Q04 — FAIL合理；蓄电池维护答对，但室内与重量约束缺失。

真实题号：`V1G-110926448917-04`；类别：`positive`。

### 1. 冻结Golden与实际回答

**问题（完整）**

```text
KIRA B 50准备停用三个月再用，按手册长期存放时要注意哪些要求，蓄电池在存放前和存放期间怎么维护？
```

**冻结参考答案（完整，保留原始文字）**

```text
运输和存放时注意设备的重量
只在室内存放设备
5. 较长时间停机时，只有给电池完全充电后才能存储设备 至少每月一次给蓄电池重新完全充电
```

**冻结Golden evidence字段（原样；摘要不能冒充完整规范）**

```json
[
  {
    "evidence_key_points": [
      "运输\n小心\n忽视重量受伤与损坏危险运输和存放时注意设备的重量请勿在湿滑地面或坡道上行驶\n1. 清空清水箱和污水箱\n2. 用车辆运输时，根据现行准则固定设备以防滑动和倾翻\n",
      "存放\n小心\n忽略重量受伤与损坏危险运输和存放时注意设备的重量\n只在室内存放设备",
      "每月一次\n1. 清洁污水箱和盖子之间的密封件\n2. 检查污水箱和盖子之间的密封件，必要时更换密封件\n3. 清洁毛刷通道\n4. 清洁清水过滤器\n5. 较长时间停机时，只有给电池完全充电后才能存储设备 至少每月一次给蓄电池重新完全充电"
    ],
    "source_chunk_ids": [
      "DOC-001-C-00179",
      "DOC-001-C-00180",
      "DOC-001-C-00185"
    ]
  }
]
```

**RAG实际回答（完整）**

```text
按 **KIRA B 50 操作说明**中“每月一次/较长时间停机”条款，停用三个月可按以下要求执行：

**有据要求（KIRA B 50）**
1. **存放前：必须先将蓄电池完全充满，才能存储设备。**
2. **存放期间：至少每月一次给蓄电池重新完全充电。**
3. 同期每月维护还包括：
   - 清洁污水箱与盖子之间的密封件；
   - 检查该密封件，必要时更换；
   - 清洁毛刷通道；
   - 清洁清水过滤器。

依据：DOC-001-C-00185（S3，KIRA B 50 操作说明，第86页）。

**未确认条件**
现有 KIRA B 50 证据未给出长期存放的环境温度、湿度、是否拆卸电池、具体存放位置等要求。上述 B2 四足机器人及其电池资料不适用于 KIRA B 50，不能套用。若需确认存放环境或充电器使用条件，应查 KIRA B 50 对应手册章节或联系官方支持。
```

### 2. 独立原文、范围与等价证据判断

C00180（PDF85）同时包含重量和室内存放，C00179（PDF84）是重量的等价重复证据；C00179未召回不构成独立检索失败，因为C00180已召回。Final的B2室内条款、B2电池存储比例属于不同产品，不能拿来补KIRA缺口。

**必要事实逐项链路**

| 必要事实/安全条件 | Corpus原文定位 | Candidate序号 | Rerank序号 | Final条目序号 | Answer与等价范围核查 |
|---|---|---|---|---|---|
| 运输/存放注意重量 | DOC-001-C-00180 / PDF 85–85 | 10 | 5 | 无 | 遗漏；C00179为另一处同产品等价条款，虽未召回但C00180已召回 |
| 只在室内存放设备 | DOC-001-C-00180 / PDF 85–85 | 10 | 5 | 无 | 遗漏；B2室内存放条款不适用于KIRA |
| 长期停机存放前完全充电 | DOC-001-C-00185 / PDF 86–86 | 1 | 3 | 3 | 完整表达 |
| 至少每月一次重新完全充电 | DOC-001-C-00185 / PDF 86–86 | 1 | 3 | 3 | 完整表达；不能套用B2电池30%/70%规则 |

### 3. 失败归因、实际程序条件与可优化性

**独立归因：** Ranking。C00180候选10→rerank5→Top4排除；电池C00185进入Final且答对。

**当前程序的确定路径：** checks[2]/[3] met=false、scope=true、Final空、reference与candidate均定位，命中328–331。Final、候选Canonical及Corpus身份均通过，非scope阻断。

**工具箱与可验证假设：** 现有context_selection：top_k=6可在保存排序中加入C00180；两项缺失同时得到适用上下文。metadata_filter虽可能减少跨产品噪声，但当前view未形成retrieval_noise断言，不能绕过validate_intervention直接声称source_filter已准入。

**建议处理：** 保留FAIL；优先验证Top6的覆盖假设。不能套B2“低于30%充到70%”替代KIRA完全充电。

**完整只读诊断输出（省去耗时明细，仅保留准入与证据）**

```json
{
  "primary_root_cause": "Ranking",
  "target_eligible": true,
  "is_technical_bad_case": true,
  "retrieval_failure_stage": "ranking_context_selection",
  "trace_observations": [
    "ranking_omission"
  ],
  "optimization_directions": [
    "context_selection"
  ],
  "evidence_checks": [
    {
      "answer_quotes": [
        "现有 KIRA B 50 证据未给出长期存放的环境温度、湿度、是否拆卸电池、具体存放位置等要求。"
      ],
      "candidate_support": [
        {
          "quote": "存放\n小心\n忽略重量受伤与损坏危险运输和存放时注意设备的重量\n只在室内存放设备",
          "source_id": "DOC-001-C-00180"
        }
      ],
      "check_type": "fact",
      "met": false,
      "reference_support": [
        {
          "quote": "存放\n小心\n忽略重量受伤与损坏危险运输和存放时注意设备的重量\n只在室内存放设备",
          "source_id": "DOC-001-C-00180"
        }
      ],
      "requirement": "长期存放时只能将设备存放在室内。",
      "scope_resolved": true,
      "support": [],
      "candidate_missing": false
    },
    {
      "answer_quotes": [],
      "candidate_support": [
        {
          "quote": "存放\n小心\n忽略重量受伤与损坏危险运输和存放时注意设备的重量\n只在室内存放设备",
          "source_id": "DOC-001-C-00180"
        }
      ],
      "check_type": "fact",
      "met": false,
      "reference_support": [
        {
          "quote": "存放\n小心\n忽略重量受伤与损坏危险运输和存放时注意设备的重量\n只在室内存放设备",
          "source_id": "DOC-001-C-00180"
        }
      ],
      "requirement": "运输和存放时应注意设备的重量。",
      "scope_resolved": true,
      "support": [],
      "candidate_missing": false
    }
  ]
}
```

### 4. Judge原始判定与检查（未改写）

保存业务verdict=FAIL；原始Judge verdict=FAIL。
<details><summary>完整原始Provider JSON（含所有checks、issues、support与reason）</summary>

```json
{"verdict":"FAIL","checks":[{"check_type":"fact","requirement":"较长时间停机存放前，必须先将蓄电池完全充满后才能存储设备。","met":true,"answer_quotes":["**存放前：必须先将蓄电池完全充满，才能存储设备。**"],"support":[{"source_id":"DOC-001-C-00185","quote":"5. 较长时间停机时，只有给电池完全充电后才能存储设备 至少每月一次给蓄电池重新完全充电"}],"scope_resolved":true},{"check_type":"fact","requirement":"存放期间至少每月一次给蓄电池重新完全充电。","met":true,"answer_quotes":["**存放期间：至少每月一次给蓄电池重新完全充电。**"],"support":[{"source_id":"DOC-001-C-00185","quote":"5. 较长时间停机时，只有给电池完全充电后才能存储设备 至少每月一次给蓄电池重新完全充电"}],"scope_resolved":true},{"check_type":"fact","requirement":"长期存放时只能将设备存放在室内。","met":false,"answer_quotes":["现有 KIRA B 50 证据未给出长期存放的环境温度、湿度、是否拆卸电池、具体存放位置等要求。"],"support":[],"reference_support":[{"source_id":"DOC-001-C-00180","quote":"存放\n小心\n忽略重量受伤与损坏危险运输和存放时注意设备的重量\n只在室内存放设备"}],"candidate_support":[{"source_id":"DOC-001-C-00180","quote":"存放\n小心\n忽略重量受伤与损坏危险运输和存放时注意设备的重量\n只在室内存放设备"}],"scope_resolved":true},{"check_type":"fact","requirement":"运输和存放时应注意设备的重量。","met":false,"answer_quotes":[],"support":[],"reference_support":[{"source_id":"DOC-001-C-00180","quote":"存放\n小心\n忽略重量受伤与损坏危险运输和存放时注意设备的重量\n只在室内存放设备"}],"candidate_support":[{"source_id":"DOC-001-C-00180","quote":"存放\n小心\n忽略重量受伤与损坏危险运输和存放时注意设备的重量\n只在室内存放设备"}],"scope_resolved":true}],"issues":[{"description":"回答遗漏了KIRA B 50长期存放要求中的“只在室内存放设备”和“运输和存放时注意设备的重量”，并把存放位置说成未给出；必要存放安全要求不完整。","answer_quotes":["现有 KIRA B 50 证据未给出长期存放的环境温度、湿度、是否拆卸电池、具体存放位置等要求。"],"support":[],"critical":true,"safety_violation":false,"scope_resolved":true,"baseline_issue_index":null}],"reason":"蓄电池存放前需完全充满、存放期间至少每月完全充电，这两点回答正确且有 Final 支持。但回答遗漏了手册同时要求的室内存放和运输/存放注意重量，属于必要事实不完整；回答中关于“具体存放位置未给出”的表述也未体现“只在室内存放”的限制，故不能通过。","quality":{"correctness":2,"faithfulness":1.0,"completeness":0.5}}
```

</details>

### 5. 可复查的完整阶段证据

<details><summary>各阶段来源顺序、完整候选正文、完整Final与规范原文</summary>

**候选→重排→Final顺序**

```json
{
  "candidates": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00185",
      "parent_chunk_id": "DOC-001-P-00183",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.9664
    },
    {
      "position": 2,
      "chunk_id": "DOC-001-C-00002",
      "parent_chunk_id": "DOC-001-P-00002",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.8716
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00184",
      "parent_chunk_id": "DOC-001-P-00182",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.8448
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00023",
      "parent_chunk_id": "DOC-001-P-00023",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5
    },
    {
      "position": 5,
      "chunk_id": "DOC-002-C-00055",
      "parent_chunk_id": "DOC-002-P-00047",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4999
    },
    {
      "position": 6,
      "chunk_id": "DOC-004-C-00027",
      "parent_chunk_id": "DOC-004-P-00023",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.4815
    },
    {
      "position": 7,
      "chunk_id": "DOC-001-C-00024",
      "parent_chunk_id": "DOC-001-P-00024",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4752
    },
    {
      "position": 8,
      "chunk_id": "DOC-004-C-00001",
      "parent_chunk_id": "DOC-004-P-00001",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.4605
    },
    {
      "position": 9,
      "chunk_id": "DOC-004-C-00026",
      "parent_chunk_id": "DOC-004-P-00022",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.4512
    },
    {
      "position": 10,
      "chunk_id": "DOC-001-C-00180",
      "parent_chunk_id": "DOC-001-P-00178",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.441
    },
    {
      "position": 11,
      "chunk_id": "DOC-001-C-00108",
      "parent_chunk_id": "DOC-001-P-00107",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4391
    },
    {
      "position": 12,
      "chunk_id": "DOC-001-C-00042",
      "parent_chunk_id": "DOC-001-P-00042",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4344
    }
  ],
  "reranked": [
    {
      "position": 1,
      "chunk_id": "DOC-002-C-00055",
      "parent_chunk_id": "DOC-002-P-00047",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.6735961530842496,
      "rerank_score": 0.6735961530842496
    },
    {
      "position": 2,
      "chunk_id": "DOC-004-C-00027",
      "parent_chunk_id": "DOC-004-P-00023",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.5614031274296221,
      "rerank_score": 0.5614031274296221
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00185",
      "parent_chunk_id": "DOC-001-P-00183",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.560067711920892,
      "rerank_score": 0.560067711920892
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00002",
      "parent_chunk_id": "DOC-001-P-00002",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5598047554877975,
      "rerank_score": 0.5598047554877975
    },
    {
      "position": 5,
      "chunk_id": "DOC-001-C-00180",
      "parent_chunk_id": "DOC-001-P-00178",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5136494390264027,
      "rerank_score": 0.5136494390264027
    },
    {
      "position": 6,
      "chunk_id": "DOC-001-C-00184",
      "parent_chunk_id": "DOC-001-P-00182",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5059382458996127,
      "rerank_score": 0.5059382458996127
    },
    {
      "position": 7,
      "chunk_id": "DOC-001-C-00023",
      "parent_chunk_id": "DOC-001-P-00023",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.48093889275025203,
      "rerank_score": 0.48093889275025203
    },
    {
      "position": 8,
      "chunk_id": "DOC-004-C-00001",
      "parent_chunk_id": "DOC-004-P-00001",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.471906033374953,
      "rerank_score": 0.471906033374953
    },
    {
      "position": 9,
      "chunk_id": "DOC-004-C-00026",
      "parent_chunk_id": "DOC-004-P-00022",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.4707702361945202,
      "rerank_score": 0.4707702361945202
    },
    {
      "position": 10,
      "chunk_id": "DOC-001-C-00024",
      "parent_chunk_id": "DOC-001-P-00024",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.41845570354489736,
      "rerank_score": 0.41845570354489736
    },
    {
      "position": 11,
      "chunk_id": "DOC-001-C-00042",
      "parent_chunk_id": "DOC-001-P-00042",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.3521687782164078,
      "rerank_score": 0.3521687782164078
    },
    {
      "position": 12,
      "chunk_id": "DOC-001-C-00108",
      "parent_chunk_id": "DOC-001-P-00107",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.33233607004058907,
      "rerank_score": 0.33233607004058907
    }
  ],
  "final": [
    {
      "position": 1,
      "chunk_id": "DOC-002-C-00055",
      "parent_chunk_id": "DOC-002-P-00047",
      "matched_child_ids": [
        "DOC-002-C-00055"
      ],
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.6735961530842496,
      "rerank_score": 0.6735961530842496
    },
    {
      "position": 2,
      "chunk_id": "DOC-004-C-00027",
      "parent_chunk_id": "DOC-004-P-00023",
      "matched_child_ids": [
        "DOC-004-C-00027"
      ],
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.5614031274296221,
      "rerank_score": 0.5614031274296221
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00185",
      "parent_chunk_id": "DOC-001-P-00183",
      "matched_child_ids": [
        "DOC-001-C-00185"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.560067711920892,
      "rerank_score": 0.560067711920892
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00002",
      "parent_chunk_id": "DOC-001-P-00002",
      "matched_child_ids": [
        "DOC-001-C-00002"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5598047554877975,
      "rerank_score": 0.5598047554877975
    }
  ]
}
```

**全部候选正文（用于核查等价来源，而非只看ID）**
候选1：`DOC-001-C-00185` / `KIRA B 50`

```text
每月一次
1. 清洁污水箱和盖子之间的密封件
2. 检查污水箱和盖子之间的密封件，必要时更换密封件
3. 清洁毛刷通道
4. 清洁清水过滤器
5. 较长时间停机时，只有给电池完全充电后才能存储设备 至少每月一次给蓄电池重新完全充电
```

候选2：`DOC-001-C-00002` / `KIRA B 50`

```text
KIRA B 50
KIRA B 50
ZH

```

候选3：`DOC-001-C-00184` / `KIRA B 50`

```text
每周
1. 使用湿微纤维抹布清洁传感器 如有必要，请额外使用玻璃清洁剂
2. ## 定期使用时，至少每周给蓄电池完全充电一次并且没有间断
```

候选4：`DOC-001-C-00023` / `KIRA B 50`

```text
蓄电池
本设备内置锂离子蓄电池 这些电池需遵守特殊标准 只有卡赫的客户服务部门或专业人员才能对有缺陷的电池进行拆卸和安装以及测试
关于存放和运输的说明，请联系卡赫的客户服务部门获取
危险
不允许对设备进行改造和改动

不得打开蓄电池，有发生短路的危险 此外，刺激性蒸气或腐蚀性液体可能会泄漏
蓄电池不得承受强光辐射 受热及火烤 有爆炸危险
不得在有爆炸危险的环境中使用充电器
请勿在脏污或潮湿状态下使用充电器
在充电过程中确保足够的通风
爆炸危险 请勿在电池附近或电池充电室中使用明火，产生火花或抽烟
爆炸危险 不要把任何工具或类似的东西放在电池上，即放在端极和电池接线上
```

候选5：`DOC-002-C-00055` / `B2 四足机器人`

```text
2. 存放
B2 需存放于干燥、阴凉的室内，避免日晒及雨淋，以免零部件锈蚀而缩短使用寿命。长时间存放时取出电池包。
```

候选6：`DOC-004-C-00027` / `B2 电池与充电器`

```text
- 保养
1. 切勿在温度过高或温度过低的环境下使用充电器对电池进行充电。
2. 切勿将电池存储在室温超过 $40^{\circ}$ C 的环境下。
3. 切勿过充电池，否则将对电芯造成损害。
4. 若较长时间不使用电池时，请定期检查电池剩余的电量，如果电量低于 30%，请把电池充电到 70% 后再继续保存。以免电池过放而损坏电池。
```

候选7：`DOC-001-C-00024` / `KIRA B 50`

```text
警告
每次使用前，请检查设备和电源线是否损坏 不要再使用损坏的设备，损坏的部件只能由专业人员进行维修让儿童远离电池和充电器
不要给损坏的电池充电 请卡赫客户服务部更换损坏的电池
不要把损坏的电池扔到家庭垃圾中 应告知卡赫客户服务部
避免与从损坏电池溢出的液体接触 在意外接触的情况下，用清水冲洗液体 如果接触到眼睛，还应就医
小心
请务必遵守这些使用说明 处理蓄电池时，遵守立法机构的建议
电源电压必须与充电器铭牌上规定的电压一致
只能将蓄电池用于本设备 禁止将其用于其他目的，这是危险行为
```

候选8：`DOC-004-C-00001` / `B2 电池与充电器`

```text
B2 电池&充电器
使用手册 V1.0
```

候选9：`DOC-004-C-00026` / `B2 电池与充电器`

```text
- 存储和运输
1. 不使用电池包时，请将电池包从机器人中取出并存放在儿童接触不到的地方。
2. 禁止将电池包放在靠近热源的地方，比如阳光直射或热天的车内、火源或加热炉。电池包理想保存温度为 $20^{\circ}$ C- $25^{\circ}$ C，电池包理想保存环境湿度：45%-75%。
3. 储存时，请注意确保电池周边的环境散热良好，没有杂物等易燃易爆物品。
4. 存放电池包的环境应保持干燥。请勿将电池包置于水中或者可能会漏水的地方。
5. 禁止机械撞击、碾压、刺穿电池包，禁止将电池包跌落或人为短路。
6. 禁止将电池包与眼镜、手表、金属项链、发夹或者其他金属物体一起贮藏或运输。
7. 切勿运输有破损的电池包。一旦需要运输电池包，务必将电池包放电至 $65\%$ 电量左右。
8. 切勿将电池包彻底放完电后长时间存储，以避免电池包进入过放状态，造成电芯损坏，将无法恢复使用。
```

候选10：`DOC-001-C-00180` / `KIRA B 50`

```text
存放
小心
忽略重量受伤与损坏危险运输和存放时注意设备的重量
只在室内存放设备
```

候选11：`DOC-001-C-00108` / `KIRA B 50`

```text
给蓄电池充电
结合对接站运行时，蓄电池自动充电
不含对接站：
1. 打开设备舱的门
1 2
充电线设备舱的门

a. 拉出充电线<sub>。</sub>
b. 如果设备不带充电线，将带有冷连接器的电源线插入对接端口上的电源插口
1 电源插口2 对接端口
2. 将充电线的电源插头插入插座充电过程自动进行。在触摸屏上显示充电状态。在充电过程中不得使用设备。当蓄电池完全放电时，充电过程大约需要8小时
3. 充电过程结束之后，从插座中拔下电源插头
4. 将电源线存放在设备舱内，或从对接端口中拔下电源线
```

候选12：`DOC-001-C-00042` / `KIRA B 50`

```text
质量保证
X
请勿将电池扔进垃圾桶
我们的主管销售公司所发布的质量保证条件在每个国家均适用 在质量保证期内，如果您的产品发生了任何故障，我们都将为您提供免费维修，但是这种故障应当是由于机身材料或制造上的缺陷造成的 如属质量保证情况，请凭发票联系贵方经销商或就近联系获得授权的客户服务点
（地址详见背面 ）
```

**完整Final（Parent展开后的真实模型输入正文）**
Final 1：`DOC-002-C-00055` / Parent `DOC-002-P-00047` / `宇树_B2四足机器人用户手册_中文版.pdf` / PDF 18–18；source_scope=null

```text
2. 存放
B2 需存放于干燥、阴凉的室内，避免日晒及雨淋，以免零部件锈蚀而缩短使用寿命。长时间存放时取出电池包。
```

Final 2：`DOC-004-C-00027` / Parent `DOC-004-P-00023` / `宇树_B2电池与充电器使用说明_中文版.pdf` / PDF 11–11；source_scope=null

```text
- 保养
1. 切勿在温度过高或温度过低的环境下使用充电器对电池进行充电。
2. 切勿将电池存储在室温超过 $40^{\circ}$ C 的环境下。
3. 切勿过充电池，否则将对电芯造成损害。
4. 若较长时间不使用电池时，请定期检查电池剩余的电量，如果电量低于 30%，请把电池充电到 70% 后再继续保存。以免电池过放而损坏电池。
```

Final 3：`DOC-001-C-00185` / Parent `DOC-001-P-00183` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 86–86；source_scope=null

```text
每月一次
1. 清洁污水箱和盖子之间的密封件
2. 检查污水箱和盖子之间的密封件，必要时更换密封件
3. 清洁毛刷通道
4. 清洁清水过滤器
5. 较长时间停机时，只有给电池完全充电后才能存储设备 至少每月一次给蓄电池重新完全充电
```

Final 4：`DOC-001-C-00002` / Parent `DOC-001-P-00002` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 1–1；source_scope=null

```text
KIRA B 50
KIRA B 50
ZH

```

**本题规范原文与元数据（Corpus完整Child）**
`DOC-001-C-00179`；KIRA B 50；PDF 84–84；version=None

```text
运输
小心
忽视重量受伤与损坏危险运输和存放时注意设备的重量请勿在湿滑地面或坡道上行驶
1. 清空清水箱和污水箱
2. 用车辆运输时，根据现行准则固定设备以防滑动和倾翻

```

`DOC-001-C-00180`；KIRA B 50；PDF 85–85；version=None

```text
存放
小心
忽略重量受伤与损坏危险运输和存放时注意设备的重量
只在室内存放设备
```

`DOC-001-C-00185`；KIRA B 50；PDF 86–86；version=None

```text
每月一次
1. 清洁污水箱和盖子之间的密封件
2. 检查污水箱和盖子之间的密封件，必要时更换密封件
3. 清洁毛刷通道
4. 清洁清水过滤器
5. 较长时间停机时，只有给电池完全充电后才能存储设备 至少每月一次给蓄电池重新完全充电
```

</details>

## Q06 — FAIL合理；两项关键电气安全条件未覆盖。

真实题号：`V1G-110926448917-06`；类别：`positive`。

### 1. 冻结Golden与实际回答

**问题（完整）**

```text
客户操作工准备对 KIRA B 50 做日常外部清洁，想直接拿湿抹布擦机身和对接站。按说明书，做这种清洁前在电气安全上有什么必须注意的？尤其是电击危险这块，是不是得先断电、拔插头？
```

**冻结参考答案（完整，保留原始文字）**

```text
在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接
无意中启动设备，接触导电部件
受伤危险，触电
在执行任何工作之前，请将设备与对接站断开，或拔出电源插头
触电危险在对接站上作业前将电源插头从插座中拔下
决不能用湿手触及电源插头或者插座
```

**冻结Golden evidence字段（原样；摘要不能冒充完整规范）**

```json
[
  {
    "evidence_key_points": [
      "保养和维护\n警告\n在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接 \n小心\n只允许授权的客户服务部进行维修工作 备件安装和在电气零部件上进行工作\n小心\n只允许已授权的客户服务处或熟知该领域所有重要安全规定的专业人员进行设备修",
      "保养和维护\n危险\n无意中启动设备，接触导电部件\n受伤危险，触电\n在执行任何工作之前，请将设备与对接站断开，或拔出电源插头",
      "清洁对接站（选项）\n警告\n触电危险在对接站上作业前将电源插头从插座中拔下\n1 污水槽2 盖板3 对接站4 位置码5 对接推杆6 带浮子的浮动开关\n1. 取下盖板2. 检查浮子开关和浮子是否脏污，必要时清洁3. 清洁污水槽，并用水冲洗4. 装上盖板\n\n5. 用湿布清洁位置码\n6. 检查对接推杆是否能自由活动",
      "危险\n\n决不能用湿手触及电源插头或者插座\n危险\n防护等级 I 的设备只能按规定连接到接地电源上"
    ],
    "source_chunk_ids": [
      "DOC-001-C-00026",
      "DOC-001-C-00181",
      "DOC-001-C-00204",
      "DOC-001-C-00017"
    ]
  }
]
```

**RAG实际回答（完整）**

```text
结论：**是，清洁前必须先做电气隔离；对接站作业前必须拔掉对接站电源插头，不能只关机带电擦。**

按说明书必须注意：

1. **清洁/维护前先断开电气连接**：执行任何工作前，将 KIRA B 50 与对接站断开，**或拔出电源插头**；目的是防止无意启动、接触导电部件导致触电。[DOC-001-C-00181]
2. **在对接站上作业前**：必须将**对接站电源插头从插座中拔下**，说明书明确标注“触电危险”。[DOC-001-C-00204][DOC-001-C-00036]
3. **清洁前检查电源线/插头**：每次使用前确保带插头的电源线无损坏；若损坏，必须立即由制造商授权客户服务中心或专业电工更换，不要继续使用。[DOC-001-C-00018]
4. **如清洁中发生泡沫或液体溢出**：立即关闭设备，并拔出对接站或充电器电源插头。[DOC-001-C-00018]

关于“直接拿湿抹布擦机身和对接站”：**不要直接照做。** 说明书只明确提到对接站的**位置码可用湿布清洁**，并未确认机身和对接站外壳可整体用湿抹布擦拭，也未给出相应防水条件。[DOC-001-C-00204] 因此应先断电/拔插头，并就不明确部位向主管或卡赫官方确认允许的清洁方式；在确认前不要湿擦机身和对接站外壳。
```

### 2. 独立原文、范围与等价证据判断

电池隔离在C00026（PDF10–11）；湿手禁令在C00017（PDF5–6）；C00181和C00204/C00036覆盖对接站隔离，但对象不同，不等价于电池隔离或湿手禁令。另Corpus C00183确有“抹布和洗涤用碱液清洁设备外部”，所以答案对整本说明书“未确认外壳清洁”的泛化不应被当作全库事实；它的Final没有该段。

**必要事实逐项链路**

| 必要事实/安全条件 | Corpus原文定位 | Candidate序号 | Rerank序号 | Final条目序号 | Answer与等价范围核查 |
|---|---|---|---|---|---|
| 清洁维护前关闭设备 | DOC-001-C-00026 / PDF 10–11 | 1 | 5 | 无 | 仅泛称先断电/隔离，未明确完整总则 |
| 电池设备拔电池插头或断开电池连接 | DOC-001-C-00026 / PDF 10–11 | 1 | 5 | 无 | 遗漏；仅拔对接站电源不等价 |
| 执行工作前设备脱离对接站或拔电源插头 | DOC-001-C-00181 / PDF 85–85 | 2 | 1 | 1 | 已表达 |
| 对接站作业前从插座拔插头 | DOC-001-C-00204 / PDF 97–98 | 4 | 2 | 2 | 已表达；Final C00036另有同对象等价规定 |
| 不得湿手触及插头或插座 | DOC-001-C-00017 / PDF 5–6 | 11 | 6 | 无 | 遗漏；禁止湿擦外壳不是同一对象的湿手禁令 |

### 3. 失败归因、实际程序条件与可优化性

**独立归因：** 主要Ranking；安全必要事实缺失是业务缺陷，不等于已证明模型有意越过安全拒答边界。两条必要源分别候选1/11→rerank5/6→Top4均排除。

**当前程序的确定路径：** checks[2]/[3]拥有scope=true、有效reference/candidate，命中328–331。issues的support仅可作为已失败check的候选规范证据通过正式Parser；business_analysis的issue分支仅收Final或issue.reference_support，而这些issue无reference_support，所以不会再产出Safety finding。

**工具箱与可验证假设：** 现有context_selection：top_k=6可同时引入C00026和C00017。只关闭rerank取Top4仍漏湿手禁令，不能作为完整方案。

**建议处理：** 保留FAIL；以安全规范上下文遗漏为目标验证Top6。勿把有限清洁剂Safety Guard的无命中理解为电气安全已通过。

**完整只读诊断输出（省去耗时明细，仅保留准入与证据）**

```json
{
  "primary_root_cause": "Ranking",
  "target_eligible": true,
  "is_technical_bad_case": true,
  "retrieval_failure_stage": "ranking_context_selection",
  "trace_observations": [
    "ranking_omission"
  ],
  "optimization_directions": [
    "context_selection"
  ],
  "evidence_checks": [
    {
      "answer_quotes": [
        "清洁/维护前先断开电气连接：执行任何工作前，将 KIRA B 50 与对接站断开，**或拔出电源插头**；目的是防止无意启动、接触导电部件导致触电。"
      ],
      "candidate_support": [
        {
          "quote": "在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接",
          "source_id": "DOC-001-C-00026"
        }
      ],
      "check_type": "fact",
      "met": false,
      "reference_support": [
        {
          "quote": "在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接",
          "source_id": "DOC-001-C-00026"
        }
      ],
      "requirement": "对于电池供电的 KIRA B 50，清洁/维护前还须拔出电池插头或断开电池连接，不能只断开对接站或只拔市电插头。",
      "scope_resolved": true,
      "support": [],
      "candidate_missing": false
    },
    {
      "answer_quotes": [
        "关于“直接拿湿抹布擦机身和对接站”：**不要直接照做。**",
        "因此应先断电/拔插头，并就不明确部位向主管或卡赫官方确认允许的清洁方式；在确认前不要湿擦机身和对接站外壳。"
      ],
      "candidate_support": [
        {
          "quote": "决不能用湿手触及电源插头或者插座",
          "source_id": "DOC-001-C-00017"
        }
      ],
      "check_type": "fact",
      "met": false,
      "reference_support": [
        {
          "quote": "决不能用湿手触及电源插头或者插座",
          "source_id": "DOC-001-C-00017"
        }
      ],
      "requirement": "涉及湿抹布清洁和插拔电源时，必须明确禁止用湿手触及电源插头或插座。",
      "scope_resolved": true,
      "support": [],
      "candidate_missing": false
    }
  ]
}
```

### 4. Judge原始判定与检查（未改写）

保存业务verdict=FAIL；原始Judge verdict=FAIL。
<details><summary>完整原始Provider JSON（含所有checks、issues、support与reason）</summary>

```json
{"verdict":"FAIL","checks":[{"check_type":"fact","requirement":"清洁/维护前必须先做电气隔离：执行任何工作前将 KIRA B 50 与对接站断开或拔出电源插头，以防无意启动、接触导电部件导致触电。","met":true,"answer_quotes":["结论：**是，清洁前必须先做电气隔离；对接站作业前必须拔掉对接站电源插头，不能只关机带电擦。**","清洁/维护前先断开电气连接：执行任何工作前，将 KIRA B 50 与对接站断开，**或拔出电源插头**；目的是防止无意启动、接触导电部件导致触电。"],"support":[{"source_id":"DOC-001-C-00181","quote":"保养和维护\n危险\n无意中启动设备，接触导电部件\n受伤危险，触电\n在执行任何工作之前，请将设备与对接站断开，或拔出电源插头"}],"reference_support":[{"source_id":"DOC-001-C-00181","quote":"在执行任何工作之前，请将设备与对接站断开，或拔出电源插头"}],"candidate_support":[{"source_id":"DOC-001-C-00181","quote":"在执行任何工作之前，请将设备与对接站断开，或拔出电源插头"}],"scope_resolved":true},{"check_type":"fact","requirement":"在对接站上作业前，必须将对接站电源插头从插座中拔下，因为存在触电危险。","met":true,"answer_quotes":["在对接站上作业前：必须将**对接站电源插头从插座中拔下**，说明书明确标注“触电危险”。"],"support":[{"source_id":"DOC-001-C-00204","quote":"清洁对接站（选项）\n警告\n触电危险在对接站上作业前将电源插头从插座中拔下"},{"source_id":"DOC-001-C-00036","quote":"执行任何维护工作之前，请将对接站的电源插头从插座中拔出"}],"reference_support":[{"source_id":"DOC-001-C-00204","quote":"触电危险在对接站上作业前将电源插头从插座中拔下"}],"candidate_support":[{"source_id":"DOC-001-C-00204","quote":"触电危险在对接站上作业前将电源插头从插座中拔下"}],"scope_resolved":true},{"check_type":"fact","requirement":"对于电池供电的 KIRA B 50，清洁/维护前还须拔出电池插头或断开电池连接，不能只断开对接站或只拔市电插头。","met":false,"answer_quotes":["清洁/维护前先断开电气连接：执行任何工作前，将 KIRA B 50 与对接站断开，**或拔出电源插头**；目的是防止无意启动、接触导电部件导致触电。"],"support":[],"reference_support":[{"source_id":"DOC-001-C-00026","quote":"在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接"}],"candidate_support":[{"source_id":"DOC-001-C-00026","quote":"在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接"}],"scope_resolved":true},{"check_type":"fact","requirement":"涉及湿抹布清洁和插拔电源时，必须明确禁止用湿手触及电源插头或插座。","met":false,"answer_quotes":["关于“直接拿湿抹布擦机身和对接站”：**不要直接照做。**","因此应先断电/拔插头，并就不明确部位向主管或卡赫官方确认允许的清洁方式；在确认前不要湿擦机身和对接站外壳。"],"support":[],"reference_support":[{"source_id":"DOC-001-C-00017","quote":"决不能用湿手触及电源插头或者插座"}],"candidate_support":[{"source_id":"DOC-001-C-00017","quote":"决不能用湿手触及电源插头或者插座"}],"scope_resolved":true},{"check_type":"fact","requirement":"说明书仅明确提到对接站位置码可用湿布清洁；机身和对接站外壳整体是否可湿擦未确认前，不应直接湿擦，应先确认清洁方式。","met":true,"answer_quotes":["说明书只明确提到对接站的**位置码可用湿布清洁**，并未确认机身和对接站外壳可整体用湿抹布擦拭，也未给出相应防水条件。","因此应先断电/拔插头，并就不明确部位向主管或卡赫官方确认允许的清洁方式；在确认前不要湿擦机身和对接站外壳。"],"support":[{"source_id":"DOC-001-C-00204","quote":"5. 用湿布清洁位置码"}],"reference_support":[{"source_id":"DOC-001-C-00204","quote":"5. 用湿布清洁位置码"}],"candidate_support":[{"source_id":"DOC-001-C-00204","quote":"5. 用湿布清洁位置码"}],"scope_resolved":true}],"issues":[{"description":"答案只写了断开对接站或拔市电插头，遗漏了说明书对电池供电设备要求清洁/维护前拔出电池插头或断开电池连接；KIRA B 50 为电池供电设备时，这会漏掉一项必要电气隔离条件。","answer_quotes":["清洁/维护前先断开电气连接：执行任何工作前，将 KIRA B 50 与对接站断开，**或拔出电源插头**；目的是防止无意启动、接触导电部件导致触电。"],"support":[{"source_id":"DOC-001-C-00026","quote":"在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接"}],"critical":true,"safety_violation":true,"scope_resolved":true,"baseline_issue_index":null},{"description":"答案在湿抹布清洁和插拔电源的语境下，遗漏了说明书明确的安全前提“决不能用湿手触及电源插头或者插座”，未排除湿手操作插头/插座的触电风险。","answer_quotes":["关于“直接拿湿抹布擦机身和对接站”：**不要直接照做。**","因此应先断电/拔插头，并就不明确部位向主管或卡赫官方确认允许的清洁方式；在确认前不要湿擦机身和对接站外壳。"],"support":[{"source_id":"DOC-001-C-00017","quote":"决不能用湿手触及电源插头或者插座"}],"critical":true,"safety_violation":true,"scope_resolved":true,"baseline_issue_index":null}],"reason":"答案的核心方向正确：强调清洁前电气隔离、对接站作业前拔插头，并正确限制未确认部位的湿擦。但它遗漏了说明书明确且与本题湿擦/触电场景直接相关的两项必要安全前提：电池供电设备需断开电池连接，以及决不能用湿手触及电源插头或插座。必要安全事实不完整，不能判 PASS。","quality":{"correctness":2,"faithfulness":1,"completeness":0.6}}
```

</details>

### 5. 可复查的完整阶段证据

<details><summary>各阶段来源顺序、完整候选正文、完整Final与规范原文</summary>

**候选→重排→Final顺序**

```json
{
  "candidates": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00026",
      "parent_chunk_id": "DOC-001-P-00026",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.9705
    },
    {
      "position": 2,
      "chunk_id": "DOC-001-C-00181",
      "parent_chunk_id": "DOC-001-P-00179",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.9497
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00018",
      "parent_chunk_id": "DOC-001-P-00018",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.8938
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00204",
      "parent_chunk_id": "DOC-001-P-00202",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.868
    },
    {
      "position": 5,
      "chunk_id": "DOC-001-C-00036",
      "parent_chunk_id": "DOC-001-P-00036",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.8488
    },
    {
      "position": 6,
      "chunk_id": "DOC-001-C-00021",
      "parent_chunk_id": "DOC-001-P-00021",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.8478
    },
    {
      "position": 7,
      "chunk_id": "DOC-001-C-00182",
      "parent_chunk_id": "DOC-001-P-00180",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.8377
    },
    {
      "position": 8,
      "chunk_id": "DOC-001-C-00007",
      "parent_chunk_id": "DOC-001-P-00007",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.8344
    },
    {
      "position": 9,
      "chunk_id": "DOC-001-C-00024",
      "parent_chunk_id": "DOC-001-P-00024",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7989
    },
    {
      "position": 10,
      "chunk_id": "DOC-001-C-00023",
      "parent_chunk_id": "DOC-001-P-00023",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7874
    },
    {
      "position": 11,
      "chunk_id": "DOC-001-C-00017",
      "parent_chunk_id": "DOC-001-P-00017",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4704
    },
    {
      "position": 12,
      "chunk_id": "DOC-002-C-00054",
      "parent_chunk_id": "DOC-002-P-00046",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4484
    }
  ],
  "reranked": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00181",
      "parent_chunk_id": "DOC-001-P-00179",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7980759965326832,
      "rerank_score": 0.7980759965326832
    },
    {
      "position": 2,
      "chunk_id": "DOC-001-C-00204",
      "parent_chunk_id": "DOC-001-P-00202",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7122706679570734,
      "rerank_score": 0.7122706679570734
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00036",
      "parent_chunk_id": "DOC-001-P-00036",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.678043185886688,
      "rerank_score": 0.678043185886688
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00018",
      "parent_chunk_id": "DOC-001-P-00018",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5838994759903372,
      "rerank_score": 0.5838994759903372
    },
    {
      "position": 5,
      "chunk_id": "DOC-001-C-00026",
      "parent_chunk_id": "DOC-001-P-00026",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5801190331624333,
      "rerank_score": 0.5801190331624333
    },
    {
      "position": 6,
      "chunk_id": "DOC-001-C-00017",
      "parent_chunk_id": "DOC-001-P-00017",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5406592651323974,
      "rerank_score": 0.5406592651323974
    },
    {
      "position": 7,
      "chunk_id": "DOC-001-C-00007",
      "parent_chunk_id": "DOC-001-P-00007",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5031051375115759,
      "rerank_score": 0.5031051375115759
    },
    {
      "position": 8,
      "chunk_id": "DOC-001-C-00182",
      "parent_chunk_id": "DOC-001-P-00180",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4996962989347398,
      "rerank_score": 0.4996962989347398
    },
    {
      "position": 9,
      "chunk_id": "DOC-002-C-00054",
      "parent_chunk_id": "DOC-002-P-00046",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.46248650838732003,
      "rerank_score": 0.46248650838732003
    },
    {
      "position": 10,
      "chunk_id": "DOC-001-C-00021",
      "parent_chunk_id": "DOC-001-P-00021",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.36103672530931125,
      "rerank_score": 0.36103672530931125
    },
    {
      "position": 11,
      "chunk_id": "DOC-001-C-00023",
      "parent_chunk_id": "DOC-001-P-00023",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.35509944543466754,
      "rerank_score": 0.35509944543466754
    },
    {
      "position": 12,
      "chunk_id": "DOC-001-C-00024",
      "parent_chunk_id": "DOC-001-P-00024",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.35115058476044336,
      "rerank_score": 0.35115058476044336
    }
  ],
  "final": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00181",
      "parent_chunk_id": "DOC-001-P-00179",
      "matched_child_ids": [
        "DOC-001-C-00181"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7980759965326832,
      "rerank_score": 0.7980759965326832
    },
    {
      "position": 2,
      "chunk_id": "DOC-001-C-00204",
      "parent_chunk_id": "DOC-001-P-00202",
      "matched_child_ids": [
        "DOC-001-C-00204"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7122706679570734,
      "rerank_score": 0.7122706679570734
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00036",
      "parent_chunk_id": "DOC-001-P-00036",
      "matched_child_ids": [
        "DOC-001-C-00036"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.678043185886688,
      "rerank_score": 0.678043185886688
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00018",
      "parent_chunk_id": "DOC-001-P-00018",
      "matched_child_ids": [
        "DOC-001-C-00018"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5838994759903372,
      "rerank_score": 0.5838994759903372
    }
  ]
}
```

**全部候选正文（用于核查等价来源，而非只看ID）**
候选1：`DOC-001-C-00026` / `KIRA B 50`

```text
保养和维护
警告
在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接 
小心
只允许授权的客户服务部进行维修工作 备件安装和在电气零部件上进行工作
小心
只允许已授权的客户服务处或熟知该领域所有重要安全规定的专业人员进行设备修复工作
小心
定期清洁水位限制装置，并检查是否出现损坏
注意
在按照当地现行规定对用作商业用途的移动式设备进行安全检查时，
注意
注意是否出现短路或其它损坏 不得用软管或高压水射流清洁设备
```

候选2：`DOC-001-C-00181` / `KIRA B 50`

```text
保养和维护
危险
无意中启动设备，接触导电部件
受伤危险，触电
在执行任何工作之前，请将设备与对接站断开，或拔出电源插头
```

候选3：`DOC-001-C-00018` / `KIRA B 50`

```text
警告
本设备只能由专业电工根据 IEC 60364‑1 标准连接到电气接口上
警告
发生泄露时立即关闭设备
警告
如果有泡沫或液体溢出，请立即关闭设备并拔出对接站或充电器的电源插头
警告
每次使用设备之前，请确保带电源插头的电源线没有损坏 如果电源线损坏，必须立即由制造商 授权的客户服务中心或专业电工更换，以避免任何风险
警告
不要碾压 挤压 拖曳电源线或延长线缆或采取类似行为造成损伤或损害 防止电线与高温 油及尖锐物品接触
警告
仅使用制造商规定的电源连接导线，这点在更换导线时同样适用 设备订单编号和型号详见 操作说明书
警告
只能用防止淋水和机械强度相同的连接器替换电源连接导线/延长线缆上的连接器

```

候选4：`DOC-001-C-00204` / `KIRA B 50`

```text
清洁对接站（选项）
警告
触电危险在对接站上作业前将电源插头从插座中拔下
1 污水槽2 盖板3 对接站4 位置码5 对接推杆6 带浮子的浮动开关
1. 取下盖板2. 检查浮子开关和浮子是否脏污，必要时清洁3. 清洁污水槽，并用水冲洗4. 装上盖板

5. 用湿布清洁位置码
6. 检查对接推杆是否能自由活动
```

候选5：`DOC-001-C-00036` / `KIRA B 50`

```text
警告
必须适当指导用户如何使用该对接站
仅在干燥区域使用该对接站
执行任何维护工作之前，请将对接站的电源插头从插座中拔出
防止对接站的电源线接触到地板清洁器的旋转刷
小心
本对接站仅在室内使用
仅在室内存放本对接站
```

候选6：`DOC-001-C-00021` / `KIRA B 50`

```text
警告
不得使用设备抽吸人或动物
警告
请勿在湿滑地面上使用本设备
警告

在倾斜表面上，请勿超过操作说明书中指定的侧向和行进方向的倾斜角度值
警告
穿着紧身的衣服，以免被旋转的零件卷入（不打领带，不穿长裙等）
小心
检查设备和附件，特别是电源连接导线和延长线缆，在每次运行前都要检查其是否状态正常以及是否具有运行安全性 如有损坏，拔下电源插头，不得使用设备
小心
请勿利用该设备运送乘客
小心
不得在电机运行时打开外罩
小心
本设备不适合抽吸有害健康的粉尘
注意
勿在 0 °C 以下使用本设备
注意
本设备不是吸尘器 吸入的液体不得比喷洒的液体更多 本设备不得用于吸入干污垢
注意
本设备仅适用于操作说明书中指定的地面
注意

该设备适用于湿润到最大水深 1 cm 的潮湿地面 请勿运行到水深超过 1 cm 的区域
注意
处理脏水和碱液时，请遵守法律规定
注意
不得在室外使用该设备<sub>。</sub>
```

候选7：`DOC-001-C-00182` / `KIRA B 50`

```text
维护间隔

注意
损坏危险
不得用水喷射本设备 不得使用腐蚀性清洁剂
提示：如果有一个对接站，则会自动执行标有“##”的维护工作
```

候选8：`DOC-001-C-00007` / `KIRA B 50`

```text
安全提示
首次使用本设备前，请注意仔细阅读本操作说明书以及完整操作说明书（设备显示屏中），然后按其操作
在护罩和所有盖子均已关闭的情况下，才能操作本设备
按下紧急停机按钮，在紧急情况下立即停用
只能在不超过最大允许坡度的场地上操作设备（参见小节“技术数据”）
在对接过程中，请勿将任何身体部位伸入对接站和设备之间
```

候选9：`DOC-001-C-00024` / `KIRA B 50`

```text
警告
每次使用前，请检查设备和电源线是否损坏 不要再使用损坏的设备，损坏的部件只能由专业人员进行维修让儿童远离电池和充电器
不要给损坏的电池充电 请卡赫客户服务部更换损坏的电池
不要把损坏的电池扔到家庭垃圾中 应告知卡赫客户服务部
避免与从损坏电池溢出的液体接触 在意外接触的情况下，用清水冲洗液体 如果接触到眼睛，还应就医
小心
请务必遵守这些使用说明 处理蓄电池时，遵守立法机构的建议
电源电压必须与充电器铭牌上规定的电压一致
只能将蓄电池用于本设备 禁止将其用于其他目的，这是危险行为
```

候选10：`DOC-001-C-00023` / `KIRA B 50`

```text
蓄电池
本设备内置锂离子蓄电池 这些电池需遵守特殊标准 只有卡赫的客户服务部门或专业人员才能对有缺陷的电池进行拆卸和安装以及测试
关于存放和运输的说明，请联系卡赫的客户服务部门获取
危险
不允许对设备进行改造和改动

不得打开蓄电池，有发生短路的危险 此外，刺激性蒸气或腐蚀性液体可能会泄漏
蓄电池不得承受强光辐射 受热及火烤 有爆炸危险
不得在有爆炸危险的环境中使用充电器
请勿在脏污或潮湿状态下使用充电器
在充电过程中确保足够的通风
爆炸危险 请勿在电池附近或电池充电室中使用明火，产生火花或抽烟
爆炸危险 不要把任何工具或类似的东西放在电池上，即放在端极和电池接线上
```

候选11：`DOC-001-C-00017` / `KIRA B 50`

```text
危险

决不能用湿手触及电源插头或者插座
危险
防护等级 I 的设备只能按规定连接到接地电源上
```

候选12：`DOC-002-C-00054` / `B2 四足机器人`

```text
1. 清洁
当 B2 在恶劣环境下（雨天、沙尘、湿地）使用后，请及时清洁机身表面。
清洗机身前请先关闭电源，使用干净的软布对机身进行擦拭，尤其关注多目深度相机是否擦拭干净。清洁时严禁使用金属刷、砂纸等，以免刮伤零件表面。清洗后，请用软布将机身擦干。擦干后可用风扇或风枪将机器人表面、关节缝隙处的积水吹干，避免留下水痕。
\- 注意！B2 整机（含电池包）IP67 级防水，清洁时请勿取下电池包！
```

**完整Final（Parent展开后的真实模型输入正文）**
Final 1：`DOC-001-C-00181` / Parent `DOC-001-P-00179` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 85–85；source_scope=null

```text
保养和维护
危险
无意中启动设备，接触导电部件
受伤危险，触电
在执行任何工作之前，请将设备与对接站断开，或拔出电源插头
```

Final 2：`DOC-001-C-00204` / Parent `DOC-001-P-00202` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 97–98；source_scope=null

```text
清洁对接站（选项）
警告
触电危险在对接站上作业前将电源插头从插座中拔下
1 污水槽2 盖板3 对接站4 位置码5 对接推杆6 带浮子的浮动开关
1. 取下盖板2. 检查浮子开关和浮子是否脏污，必要时清洁3. 清洁污水槽，并用水冲洗4. 装上盖板

5. 用湿布清洁位置码
6. 检查对接推杆是否能自由活动
```

Final 3：`DOC-001-C-00036` / Parent `DOC-001-P-00036` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 13–13；source_scope=null

```text
警告
必须适当指导用户如何使用该对接站
仅在干燥区域使用该对接站
执行任何维护工作之前，请将对接站的电源插头从插座中拔出
防止对接站的电源线接触到地板清洁器的旋转刷
小心
本对接站仅在室内使用
仅在室内存放本对接站
```

Final 4：`DOC-001-C-00018` / Parent `DOC-001-P-00018` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 6–6；source_scope=null

```text
警告
本设备只能由专业电工根据 IEC 60364‑1 标准连接到电气接口上
警告
发生泄露时立即关闭设备
警告
如果有泡沫或液体溢出，请立即关闭设备并拔出对接站或充电器的电源插头
警告
每次使用设备之前，请确保带电源插头的电源线没有损坏 如果电源线损坏，必须立即由制造商 授权的客户服务中心或专业电工更换，以避免任何风险
警告
不要碾压 挤压 拖曳电源线或延长线缆或采取类似行为造成损伤或损害 防止电线与高温 油及尖锐物品接触
警告
仅使用制造商规定的电源连接导线，这点在更换导线时同样适用 设备订单编号和型号详见 操作说明书
警告
只能用防止淋水和机械强度相同的连接器替换电源连接导线/延长线缆上的连接器

```

**本题规范原文与元数据（Corpus完整Child）**
`DOC-001-C-00017`；KIRA B 50；PDF 5–6；version=None

```text
危险

决不能用湿手触及电源插头或者插座
危险
防护等级 I 的设备只能按规定连接到接地电源上
```

`DOC-001-C-00026`；KIRA B 50；PDF 10–11；version=None

```text
保养和维护
警告
在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接 
小心
只允许授权的客户服务部进行维修工作 备件安装和在电气零部件上进行工作
小心
只允许已授权的客户服务处或熟知该领域所有重要安全规定的专业人员进行设备修复工作
小心
定期清洁水位限制装置，并检查是否出现损坏
注意
在按照当地现行规定对用作商业用途的移动式设备进行安全检查时，
注意
注意是否出现短路或其它损坏 不得用软管或高压水射流清洁设备
```

`DOC-001-C-00181`；KIRA B 50；PDF 85–85；version=None

```text
保养和维护
危险
无意中启动设备，接触导电部件
受伤危险，触电
在执行任何工作之前，请将设备与对接站断开，或拔出电源插头
```

`DOC-001-C-00183`；KIRA B 50；PDF 86–86；version=None

```text
在每次运行之后
1. ## 排放污水<sub>。</sub>
2. ## 冲洗污水箱
3. 清洁涡轮机防护网
4. 从污水箱中取出粗大污染物滤网并清洗
5. 使用抹布和洗涤用碱液清洁设备外部
6. 检查绒毛滤网，必要时清洁
7. 拆下并清洁清洁头上的粗大污染物容器
8. 清洗清洁头上的分水条
9. 清洁吸水扒中的吸水胶条，检查是否存在磨损 翻转或更换已磨损的吸水胶条
10. 检查吸水胶条在吸水扒中的正确配合 必要时，将吸水胶条重新正确装入吸水扒的凹槽中
11. 清洁清洁头两侧的削刮胶条，检查是否存在磨损 更换已磨损的削刮胶条
12. 检查刷子是否磨损 更换已磨损的刷子
提示：如果黄色指示器刷毛与其他刷毛长度相同，则说明刷辊已磨损
13. ## 给蓄电池充电
```

`DOC-001-C-00204`；KIRA B 50；PDF 97–98；version=None

```text
清洁对接站（选项）
警告
触电危险在对接站上作业前将电源插头从插座中拔下
1 污水槽2 盖板3 对接站4 位置码5 对接推杆6 带浮子的浮动开关
1. 取下盖板2. 检查浮子开关和浮子是否脏污，必要时清洁3. 清洁污水槽，并用水冲洗4. 装上盖板

5. 用湿布清洁位置码
6. 检查对接推杆是否能自由活动
```

</details>

## Q07 — FAIL合理；滤网机械步骤正确，维护总则缺失。

真实题号：`V1G-110926448917-07`；类别：`positive`。

### 1. 冻结Golden与实际回答

**问题（完整）**

```text
KIRA B 50停在对接站上，我要按日常保养要求清洗污水箱里的粗大污染物滤网。清洗前电气安全要怎么处理，滤网怎么取出、洗净再装回？
```

**冻结参考答案（完整，保留原始文字）**

```text
在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接
在执行任何工作之前，请将设备与对接站断开，或拔出电源插头
1. 打开污水箱盖罩
2. 向上拉出粗大污染物滤网
3. 将粗大污染物滤网放到自来水下冲洗
4. 将粗大污染物滤网装入污水箱中
```

**冻结Golden evidence字段（原样；摘要不能冒充完整规范）**

```json
[
  {
    "evidence_key_points": [
      "保养和维护\n警告\n在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接 \n小心\n只允许授权的客户服务部进行维修工作 备件安装和在电气零部件上进行工作\n小心\n只允许已授权的客户服务处或熟知该领域所有重要安全规定的专业人员进行设备修",
      "保养和维护\n危险\n无意中启动设备，接触导电部件\n受伤危险，触电\n在执行任何工作之前，请将设备与对接站断开，或拔出电源插头",
      "清洗粗大污染物滤网\n1. 打开污水箱盖罩\n\n2. 向上拉出粗大污染物滤网\n3. 将粗大污染物滤网放到自来水下冲洗\n4. 将粗大污染物滤网装入污水箱中"
    ],
    "source_chunk_ids": [
      "DOC-001-C-00026",
      "DOC-001-C-00181",
      "DOC-001-C-00191"
    ]
  }
]
```

**RAG实际回答（完整）**

```text
**结论：先按对接站警告断电，再取洗滤网。**  
设备停在对接站上时，资料中明确的电气安全前提是：**在对接站上作业前，将电源插头从插座中拔下** [DOC-001-C-00204 | S1 | 页97–98]。现有资料未单独规定“仅取滤网”是否必须关闭设备主电源或拔设备端插头，不能补造；但在未拔对接站电源前，不要开始在该区域操作。

**滤网取出、冲洗、装回（有据步骤）：**
1. 打开污水箱盖罩。  
2. 向上拉出粗大污染物滤网。  
3. 将粗大污染物滤网放到自来水下冲洗。  
4. 将粗大污染物滤网装入污水箱中。  
[DOC-001-C-00191 | S1 | 页88–89]

**日常保养顺序提示：**资料将“从污水箱中取出粗大污染物滤网并清洗”列在排放污水、冲洗污水箱、清洁涡轮机防护网之后 [DOC-001-C-00183 | S1 | 页86]；但这些前序步骤的具体操作方法未在给定证据中展开，不能补造。

**未确认边界：**装回滤网后是否/何时恢复对接站电源、是否需要复位或上电测试，资料未说明；不要自行上电测试，需按设备标识或官方资料确认。
```

### 2. 独立原文、范围与等价证据判断

C00026给全类清洁/维护关机及电池隔离，适用于KIRA滤网维护，无需每一个滤网章节重复警告。C00181为总维护隔离；Final C00204确有对接站拔电源这一部分等价事实，故不能声称“所有隔离事实都未召回”。十二个候选正文没有关机+断电池的等价规范。

**必要事实逐项链路**

| 必要事实/安全条件 | Corpus原文定位 | Candidate序号 | Rerank序号 | Final条目序号 | Answer与等价范围核查 |
|---|---|---|---|---|---|
| 清洗维护前关闭设备 | DOC-001-C-00026 / PDF 10–11 | 无 | 无 | 无 | 遗漏，并称资料未规定 |
| 电池供电设备拔电池插头或断开电池 | DOC-001-C-00026 / PDF 10–11 | 无 | 无 | 无 | 遗漏；对接站拔插头不代替电池隔离 |
| 工作前脱离对接站或拔电源 | DOC-001-C-00181 / PDF 85–85 | 无 | 无 | 无 | Final C00204给对接站作业拔插头的等价安全方向，回答已覆盖该部分 |
| 打开污水箱盖罩 | DOC-001-C-00191 / PDF 88–89 | 1 | 3 | 3 | 已表达 |
| 向上拉出粗大污染物滤网 | DOC-001-C-00191 / PDF 88–89 | 1 | 3 | 3 | 已表达 |
| 自来水下冲洗 | DOC-001-C-00191 / PDF 88–89 | 1 | 3 | 3 | 已表达 |
| 装回污水箱 | DOC-001-C-00191 / PDF 88–89 | 1 | 3 | 3 | 已表达 |

### 3. 失败归因、实际程序条件与可优化性

**独立归因：** 人工证据支持Retrieval（维护总则未进入冻结Trace的候选池）；拔对接站电源已覆盖。无法从已截断候选池进一步分辨是向量/BM25检索本身未召回，还是融合CandidateK截断排除。

**当前程序的确定路径：** 全部前置校验通过；checks[0]/[1] scope=true、support=[]、reference定位成功，但candidate_support字段不存在（None，不是[]）；328行的isinstance(...,list)为false。issue scope=true但support=[]且无issue.reference_support，334行两个分支都false；Guard无finding，latency=12695<60000。因此返回Unknown。这是对未声明候选语义核验的正确阻断；可选诊断字段与必需准入之间存在覆盖缺口，不能把None直接改成空数组。

**工具箱与可验证假设：** 若未来同一次Judge/经授权的独立诊断证据明确完成候选无等价证据审查，可用query_expansion或candidate_recall（如candidate_k=24）验证能否召回维护总则；本轮未运行新检索，扩大K有效性未知。Top6重排已有候选不能凭空补入未出现的总则。

**建议处理：** 保留业务FAIL与当前Unknown；报告提供人工Retrieval结论，不改历史字段、不准入Agent。优先修可解释诊断并补可验证规范链，而不是弱化安全或FAIL条件。

**完整只读诊断输出（省去耗时明细，仅保留准入与证据）**

```json
{
  "primary_root_cause": "Unknown",
  "target_eligible": false,
  "is_technical_bad_case": false,
  "retrieval_failure_stage": null,
  "trace_observations": [],
  "optimization_directions": [],
  "evidence_checks": []
}
```

### 4. Judge原始判定与检查（未改写）

保存业务verdict=FAIL；原始Judge verdict=FAIL。
<details><summary>完整原始Provider JSON（含所有checks、issues、support与reason）</summary>

```json
{"verdict":"FAIL","checks":[{"check_type":"fact","requirement":"当前操作适用性：对象为停于对接站的 KIRA B 50，任务是清洗污水箱粗大污染物滤网；在给出当前取洗装回操作前，必须确认并满足清洁/维护前关闭设备、电池供电设备拔出电池插头或断开电池连接，以及对接站作业前拔电源或断开对接站等必要安全前提。回答仅确认拔对接站电源，并明确称资料未规定关闭设备主电源或拔设备端插头，当前操作安全前提不完整。","met":false,"answer_quotes":["**结论：先按对接站警告断电，再取洗滤网。**","现有资料未单独规定“仅取滤网”是否必须关闭设备主电源或拔设备端插头，不能补造；但在未拔对接站电源前，不要开始在该区域操作。"],"support":[],"reference_support":[{"source_id":"DOC-001-C-00026","quote":"保养和维护\n警告\n在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接"},{"source_id":"DOC-001-C-00181","quote":"保养和维护\n危险\n无意中启动设备，接触导电部件\n受伤危险，触电\n在执行任何工作之前，请将设备与对接站断开，或拔出电源插头"},{"source_id":"DOC-001-C-00204","quote":"触电危险在对接站上作业前将电源插头从插座中拔下"}],"scope_resolved":true},{"check_type":"fact","requirement":"清洁或维护前必须关闭设备；对于电池供电设备，必须拔出电池插头或断开电池连接，不能只拔对接站电源代替。","met":false,"answer_quotes":["**结论：先按对接站警告断电，再取洗滤网。**","现有资料未单独规定“仅取滤网”是否必须关闭设备主电源或拔设备端插头，不能补造；但在未拔对接站电源前，不要开始在该区域操作。"],"support":[],"reference_support":[{"source_id":"DOC-001-C-00026","quote":"保养和维护\n警告\n在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接"}],"scope_resolved":true},{"check_type":"fact","requirement":"在对接站上作业前应将电源插头从插座中拔下（或断开设备与对接站）。","met":true,"answer_quotes":["在对接站上作业前，将电源插头从插座中拔下","在未拔对接站电源前，不要开始在该区域操作。"],"support":[{"source_id":"DOC-001-C-00204","quote":"触电危险在对接站上作业前将电源插头从插座中拔下"}],"reference_support":[{"source_id":"DOC-001-C-00181","quote":"保养和维护\n危险\n无意中启动设备，接触导电部件\n受伤危险，触电\n在执行任何工作之前，请将设备与对接站断开，或拔出电源插头"}],"scope_resolved":true},{"check_type":"fact","requirement":"粗大污染物滤网的取出、洗净、装回步骤：打开污水箱盖罩；向上拉出粗大污染物滤网；放到自来水下冲洗；装入污水箱中。","met":true,"answer_quotes":["1. 打开污水箱盖罩。","2. 向上拉出粗大污染物滤网。","3. 将粗大污染物滤网放到自来水下冲洗。","4. 将粗大污染物滤网装入污水箱中。"],"support":[{"source_id":"DOC-001-C-00191","quote":"清洗粗大污染物滤网"},{"source_id":"DOC-001-C-00191","quote":"1. 打开污水箱盖罩"},{"source_id":"DOC-001-C-00191","quote":"2. 向上拉出粗大污染物滤网"},{"source_id":"DOC-001-C-00191","quote":"3. 将粗大污染物滤网放到自来水下冲洗"},{"source_id":"DOC-001-C-00191","quote":"4. 将粗大污染物滤网装入污水箱中"}],"reference_support":[{"source_id":"DOC-001-C-00191","quote":"清洗粗大污染物滤网\n1. 打开污水箱盖罩\n\n2. 向上拉出粗大污染物滤网\n3. 将粗大污染物滤网放到自来水下冲洗\n4. 将粗大污染物滤网装入污水箱中"}],"scope_resolved":true}],"issues":[{"description":"回答把电气安全限定为拔对接站电源，并明确称资料未规定必须关闭设备主电源或拔设备端插头；遗漏了清洁或维护前必须关闭设备、电池供电设备必须拔出电池插头或断开电池连接这一必要安全前提，不能支持当前滤网维护操作。","answer_quotes":["**结论：先按对接站警告断电，再取洗滤网。**","现有资料未单独规定“仅取滤网”是否必须关闭设备主电源或拔设备端插头，不能补造；但在未拔对接站电源前，不要开始在该区域操作。"],"support":[],"critical":true,"safety_violation":true,"scope_resolved":true,"baseline_issue_index":null}],"reason":"滤网取出、冲洗、装回步骤正确，且提到对接站作业前拔电源；但回答未给出并明确否认清洁/维护前必须关闭设备、电池供电设备必须拔出电池插头或断开电池连接这一必要安全前提。仅拔对接站电源不能覆盖 KIRA B 50 当前滤网维护场景，故判 FAIL。","quality":{"correctness":2,"faithfulness":0.5,"completeness":0.5}}
```

</details>

### 5. 可复查的完整阶段证据

<details><summary>各阶段来源顺序、完整候选正文、完整Final与规范原文</summary>

**候选→重排→Final顺序**

```json
{
  "candidates": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00191",
      "parent_chunk_id": "DOC-001-P-00189",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 1.0
    },
    {
      "position": 2,
      "chunk_id": "DOC-001-C-00183",
      "parent_chunk_id": "DOC-001-P-00181",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.8094
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00139",
      "parent_chunk_id": "DOC-001-P-00138",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7972
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00177",
      "parent_chunk_id": "DOC-001-P-00175",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7832
    },
    {
      "position": 5,
      "chunk_id": "DOC-001-C-00192",
      "parent_chunk_id": "DOC-001-P-00190",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7696
    },
    {
      "position": 6,
      "chunk_id": "DOC-001-C-00178",
      "parent_chunk_id": "DOC-001-P-00176",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7632
    },
    {
      "position": 7,
      "chunk_id": "DOC-001-C-00204",
      "parent_chunk_id": "DOC-001-P-00202",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4799
    },
    {
      "position": 8,
      "chunk_id": "DOC-001-C-00197",
      "parent_chunk_id": "DOC-001-P-00195",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4572
    },
    {
      "position": 9,
      "chunk_id": "DOC-001-C-00182",
      "parent_chunk_id": "DOC-001-P-00180",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4517
    },
    {
      "position": 10,
      "chunk_id": "DOC-001-C-00185",
      "parent_chunk_id": "DOC-001-P-00183",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4497
    },
    {
      "position": 11,
      "chunk_id": "DOC-001-C-00196",
      "parent_chunk_id": "DOC-001-P-00194",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4496
    },
    {
      "position": 12,
      "chunk_id": "DOC-001-C-00190",
      "parent_chunk_id": "DOC-001-P-00188",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4477
    }
  ],
  "reranked": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00183",
      "parent_chunk_id": "DOC-001-P-00181",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.8388715545433469,
      "rerank_score": 0.8388715545433469
    },
    {
      "position": 2,
      "chunk_id": "DOC-001-C-00204",
      "parent_chunk_id": "DOC-001-P-00202",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.817085016871941,
      "rerank_score": 0.817085016871941
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00191",
      "parent_chunk_id": "DOC-001-P-00189",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.8106640802646847,
      "rerank_score": 0.8106640802646847
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00139",
      "parent_chunk_id": "DOC-001-P-00138",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7459642038113672,
      "rerank_score": 0.7459642038113672
    },
    {
      "position": 5,
      "chunk_id": "DOC-001-C-00177",
      "parent_chunk_id": "DOC-001-P-00175",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.708032684923281,
      "rerank_score": 0.708032684923281
    },
    {
      "position": 6,
      "chunk_id": "DOC-001-C-00196",
      "parent_chunk_id": "DOC-001-P-00194",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.6394234222324114,
      "rerank_score": 0.6394234222324114
    },
    {
      "position": 7,
      "chunk_id": "DOC-001-C-00178",
      "parent_chunk_id": "DOC-001-P-00176",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.6194659772286765,
      "rerank_score": 0.6194659772286765
    },
    {
      "position": 8,
      "chunk_id": "DOC-001-C-00182",
      "parent_chunk_id": "DOC-001-P-00180",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5885445335068359,
      "rerank_score": 0.5885445335068359
    },
    {
      "position": 9,
      "chunk_id": "DOC-001-C-00192",
      "parent_chunk_id": "DOC-001-P-00190",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5108478281594319,
      "rerank_score": 0.5108478281594319
    },
    {
      "position": 10,
      "chunk_id": "DOC-001-C-00185",
      "parent_chunk_id": "DOC-001-P-00183",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4971987630773878,
      "rerank_score": 0.4971987630773878
    },
    {
      "position": 11,
      "chunk_id": "DOC-001-C-00197",
      "parent_chunk_id": "DOC-001-P-00195",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.47133406984956727,
      "rerank_score": 0.47133406984956727
    },
    {
      "position": 12,
      "chunk_id": "DOC-001-C-00190",
      "parent_chunk_id": "DOC-001-P-00188",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4546788717663014,
      "rerank_score": 0.4546788717663014
    }
  ],
  "final": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00183",
      "parent_chunk_id": "DOC-001-P-00181",
      "matched_child_ids": [
        "DOC-001-C-00183"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.8388715545433469,
      "rerank_score": 0.8388715545433469
    },
    {
      "position": 2,
      "chunk_id": "DOC-001-C-00204",
      "parent_chunk_id": "DOC-001-P-00202",
      "matched_child_ids": [
        "DOC-001-C-00204"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.817085016871941,
      "rerank_score": 0.817085016871941
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00191",
      "parent_chunk_id": "DOC-001-P-00189",
      "matched_child_ids": [
        "DOC-001-C-00191"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.8106640802646847,
      "rerank_score": 0.8106640802646847
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00139",
      "parent_chunk_id": "DOC-001-P-00138",
      "matched_child_ids": [
        "DOC-001-C-00139"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7459642038113672,
      "rerank_score": 0.7459642038113672
    }
  ]
}
```

**全部候选正文（用于核查等价来源，而非只看ID）**
候选1：`DOC-001-C-00191` / `KIRA B 50`

```text
清洗粗大污染物滤网
1. 打开污水箱盖罩

2. 向上拉出粗大污染物滤网
3. 将粗大污染物滤网放到自来水下冲洗
4. 将粗大污染物滤网装入污水箱中
```

候选2：`DOC-001-C-00183` / `KIRA B 50`

```text
在每次运行之后
1. ## 排放污水<sub>。</sub>
2. ## 冲洗污水箱
3. 清洁涡轮机防护网
4. 从污水箱中取出粗大污染物滤网并清洗
5. 使用抹布和洗涤用碱液清洁设备外部
6. 检查绒毛滤网，必要时清洁
7. 拆下并清洁清洁头上的粗大污染物容器
8. 清洗清洁头上的分水条
9. 清洁吸水扒中的吸水胶条，检查是否存在磨损 翻转或更换已磨损的吸水胶条
10. 检查吸水胶条在吸水扒中的正确配合 必要时，将吸水胶条重新正确装入吸水扒的凹槽中
11. 清洁清洁头两侧的削刮胶条，检查是否存在磨损 更换已磨损的削刮胶条
12. 检查刷子是否磨损 更换已磨损的刷子
提示：如果黄色指示器刷毛与其他刷毛长度相同，则说明刷辊已磨损
13. ## 给蓄电池充电
```

候选3：`DOC-001-C-00139` / `KIRA B 50`

```text
对接
对接时将设备连接到一个可选的对接站 成功对接后进行以下操作：
清空和冲洗污水箱
填充清水箱<sub>。</sub>
蓄电池充电
1. 在主菜单中按下“对接”按钮
设备准备对接操作，并搜索位置码

2. 操作安全开关，并将设备推到对接站前方
a. 将对接端口与对接站对准
b. 与对接站保持大约 2 m 的距离
3. 请等待，直到设备检测到对接站上的 位置码
4. 确认 位置码

```

候选4：`DOC-001-C-00177` / `KIRA B 50`

```text
排放污水
结合对接站运行时，会自动排空污水箱
不含对接站：
小心
污水中的污染物和清洁剂可能会危害您的健康或污染环境请遵守当地适用的废水处理规定
1. 打开设备舱的门

1 盖子2 计量装置3 排放软管
2. 从支架中取出排放软管
3. 将排放软管降低到合适的收集装置上
4. 压合或弯折计量装置
5. 打开盖子
6. 通过压力或弯曲计量装置控制污水流量
7. 冲洗污水箱<sub>。</sub>
8. 关闭盖子<sub>。</sub>
9. 将排放软管压入设备舱内的支架中
10. 关闭设备舱的门
```

候选5：`DOC-001-C-00192` / `KIRA B 50`

```text
清洗清水过滤器
1. 排干清水（参见“排干清水”章节）
2. 拧下清水箱密封盖
1 清水过滤器
2 清水箱密封盖
3. 拔出清水过滤器并且用干净的水进行冲洗
4. 安装清水过滤器

5. 装上清水箱密封盖
提示： 注意拧紧后软管接头在清水箱密封盖中应位于最低点
```

候选6：`DOC-001-C-00178` / `KIRA B 50`

```text
排放清水
1. 将设备置于排水口上方
2. 拧下清水箱密封盖

1 滤网 2 清水箱密封盖
3. 排出水<sub>。</sub>4. 如有需要，取下并清洁滤网5. 重新装入滤网6. 拧上清水箱密封盖
提示
对准密封盖，让软管接口位于底部
```

候选7：`DOC-001-C-00204` / `KIRA B 50`

```text
清洁对接站（选项）
警告
触电危险在对接站上作业前将电源插头从插座中拔下
1 污水槽2 盖板3 对接站4 位置码5 对接推杆6 带浮子的浮动开关
1. 取下盖板2. 检查浮子开关和浮子是否脏污，必要时清洁3. 清洁污水槽，并用水冲洗4. 装上盖板

5. 用湿布清洁位置码
6. 检查对接推杆是否能自由活动
```

候选8：`DOC-001-C-00197` / `KIRA B 50`

```text
警告
水箱盖导致受伤危险！
由于水箱盖意外关闭而导致肢体受挤压的危险
请打开水箱盖直到止挡位置，以免意外关闭
当没有任何肢体部位处在水箱和水箱盖之间时，才能关闭水箱盖
4. 打开污水箱盖罩

5. 将压缩空气软管连接到设备上的压缩空气接口
6. 盖上污水箱盖
7. 打开进水口<sub>。</sub>
8. 进行大约 30 秒的冲洗过程<sub>。</sub>
9. 关闭进水<sub>。</sub>
10. 退出功能“水箱冲洗”<sub>。</sub>
11. 从设备上脱开进水软管
12. 关闭污水排放软管，然后将其压入支架中
13. 关闭设备舱的门<sub>。</sub>
```

候选9：`DOC-001-C-00182` / `KIRA B 50`

```text
维护间隔

注意
损坏危险
不得用水喷射本设备 不得使用腐蚀性清洁剂
提示：如果有一个对接站，则会自动执行标有“##”的维护工作
```

候选10：`DOC-001-C-00185` / `KIRA B 50`

```text
每月一次
1. 清洁污水箱和盖子之间的密封件
2. 检查污水箱和盖子之间的密封件，必要时更换密封件
3. 清洁毛刷通道
4. 清洁清水过滤器
5. 较长时间停机时，只有给电池完全充电后才能存储设备 至少每月一次给蓄电池重新完全充电
```

候选11：`DOC-001-C-00196` / `KIRA B 50`

```text
冲洗污水箱，结合冲洗系统
1. 清空污水箱 在盖子打开的情况下将排水管置于排水口上
2. 在触摸屏上打开菜单“日常护理”
3. 启动功能“水箱冲洗”
```

候选12：`DOC-001-C-00190` / `KIRA B 50`

```text
提示
在轻度污染的情况下，在安装的状态下清洁涡轮机保护网即可
```

**完整Final（Parent展开后的真实模型输入正文）**
Final 1：`DOC-001-C-00183` / Parent `DOC-001-P-00181` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 86–86；source_scope=null

```text
在每次运行之后
1. ## 排放污水<sub>。</sub>
2. ## 冲洗污水箱
3. 清洁涡轮机防护网
4. 从污水箱中取出粗大污染物滤网并清洗
5. 使用抹布和洗涤用碱液清洁设备外部
6. 检查绒毛滤网，必要时清洁
7. 拆下并清洁清洁头上的粗大污染物容器
8. 清洗清洁头上的分水条
9. 清洁吸水扒中的吸水胶条，检查是否存在磨损 翻转或更换已磨损的吸水胶条
10. 检查吸水胶条在吸水扒中的正确配合 必要时，将吸水胶条重新正确装入吸水扒的凹槽中
11. 清洁清洁头两侧的削刮胶条，检查是否存在磨损 更换已磨损的削刮胶条
12. 检查刷子是否磨损 更换已磨损的刷子
提示：如果黄色指示器刷毛与其他刷毛长度相同，则说明刷辊已磨损
13. ## 给蓄电池充电
```

Final 2：`DOC-001-C-00204` / Parent `DOC-001-P-00202` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 97–98；source_scope=null

```text
清洁对接站（选项）
警告
触电危险在对接站上作业前将电源插头从插座中拔下
1 污水槽2 盖板3 对接站4 位置码5 对接推杆6 带浮子的浮动开关
1. 取下盖板2. 检查浮子开关和浮子是否脏污，必要时清洁3. 清洁污水槽，并用水冲洗4. 装上盖板

5. 用湿布清洁位置码
6. 检查对接推杆是否能自由活动
```

Final 3：`DOC-001-C-00191` / Parent `DOC-001-P-00189` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 88–89；source_scope=null

```text
清洗粗大污染物滤网
1. 打开污水箱盖罩

2. 向上拉出粗大污染物滤网
3. 将粗大污染物滤网放到自来水下冲洗
4. 将粗大污染物滤网装入污水箱中
```

Final 4：`DOC-001-C-00139` / Parent `DOC-001-P-00138` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 55–56；source_scope=null

```text
对接
对接时将设备连接到一个可选的对接站 成功对接后进行以下操作：
清空和冲洗污水箱
填充清水箱<sub>。</sub>
蓄电池充电
1. 在主菜单中按下“对接”按钮
设备准备对接操作，并搜索位置码

2. 操作安全开关，并将设备推到对接站前方
a. 将对接端口与对接站对准
b. 与对接站保持大约 2 m 的距离
3. 请等待，直到设备检测到对接站上的 位置码
4. 确认 位置码

```

**本题规范原文与元数据（Corpus完整Child）**
`DOC-001-C-00026`；KIRA B 50；PDF 10–11；version=None

```text
保养和维护
警告
在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接 
小心
只允许授权的客户服务部进行维修工作 备件安装和在电气零部件上进行工作
小心
只允许已授权的客户服务处或熟知该领域所有重要安全规定的专业人员进行设备修复工作
小心
定期清洁水位限制装置，并检查是否出现损坏
注意
在按照当地现行规定对用作商业用途的移动式设备进行安全检查时，
注意
注意是否出现短路或其它损坏 不得用软管或高压水射流清洁设备
```

`DOC-001-C-00181`；KIRA B 50；PDF 85–85；version=None

```text
保养和维护
危险
无意中启动设备，接触导电部件
受伤危险，触电
在执行任何工作之前，请将设备与对接站断开，或拔出电源插头
```

`DOC-001-C-00191`；KIRA B 50；PDF 88–89；version=None

```text
清洗粗大污染物滤网
1. 打开污水箱盖罩

2. 向上拉出粗大污染物滤网
3. 将粗大污染物滤网放到自来水下冲洗
4. 将粗大污染物滤网装入污水箱中
```

</details>

## Q08 — FAIL合理；充电板表面清洁和一般工具禁令确实遗漏，但当前Generation主因不可靠。

真实题号：`V1G-110926448917-08`；类别：`positive`。

### 1. 冻结Golden与实际回答

**问题（完整）**

```text
B2充电器要做定期保养的话，按手册该保养哪些部位、怎么清洁检查？
```

**冻结参考答案（完整，保留原始文字）**

```text
13. 定时检查并保养充电器，经常检查充电器和电池外观等各个部件。切勿使用酒精或其他可燃剂清洁充电器。切勿使用已有损坏的充电器。
当长时间未使用接触式充电器，在使用前请先清洁充电板表面。擦拭表面时请先关闭电源，使用干燥的软布对充电板表面和机身底部充电电极进行擦拭，尤其关注表面是否擦拭干净；清洁时严禁使用金属刷、砂纸等，以免刮伤表面。
1. 检查充电器表面有无变形、鼓包等；
2. 检查充电接口有无水渍、异物等。
```

**冻结Golden evidence字段（原样；摘要不能冒充完整规范）**

```json
[
  {
    "evidence_key_points": [
      "专用充电器进行充电。对于使用非 Unitree 官方提供的充电器进行充电所造成的一切后果，Unitree 将不予负责。\n11. 使用接触式充电器充电时请将充电板和 B2 放置在水泥地面等周围无易燃、可燃物的地面。请留意充电过程，以防发生意外。\n12. 禁止在机器人运行结束后，立刻对进行充电。此时，电池处于高温状态，强制",
      "- 清洁\n当长时间未使用接触式充电器，在使用前请先清洁充电板表面。擦拭表面时请先关闭电源，使用干燥的软布对充电板表面和机身底部充电电极进行擦拭，尤其关注表面是否擦拭干净；清洁时严禁使用金属刷、砂纸等，以免刮伤表面。",
      "- 检查\n在充电前后开展例行检查，可大幅度提升产品可靠性能，降低安全隐患，延长使用寿命。\n1. 检查充电器表面有无变形、鼓包等；\n2. 检查充电接口有无水渍、异物等。\nB2 电池&充电器使用手册\n© 2023 宇树科技 版权所有\n12"
    ],
    "source_chunk_ids": [
      "DOC-004-C-00030",
      "DOC-004-C-00032",
      "DOC-004-C-00034"
    ]
  }
]
```

**RAG实际回答（完整）**

```text
按《宇树_B2电池与充电器使用说明_中文版》（DOC-004）可确认的 B2 充电器保养内容如下；具体保养周期手册未规定，不能自行给“每周/每月”频次。

### 1. 保养检查部位
- **充电器外观/整体**：检查表面有无变形、鼓包；经常检查充电器和电池外观等各个部件；已有损坏的充电器切勿使用。  
  依据：DOC-004-C-00034（页12）、DOC-004-C-00030（页12）。
- **充电接口**：检查有无水渍、异物；使用时确保充电板表面和接口无水滴。  
  依据：DOC-004-C-00034（页12）、DOC-004-C-00030（页12）。
- **充电电极**：检查充电板充电电极表面、B2 机身底部充电电极有无异物遮挡；用干燥抹布擦拭充电电极表面，确保充电接触良好。  
  依据：DOC-004-C-00017（页8）。
- **配套电池外观**：同条要求经常检查电池外观等部件；发现异常应按电池安全流程停用确认。  
  依据：DOC-004-C-00030（页12）。

### 2. 清洁与检查方法
1. **先确保未上电**：进行电极接触清洁前，应确保充电板未上电；手册明确“上电后请勿触摸充电板电极”，且表面勿放置导电金属物品。  
   依据：DOC-004-C-00030（页12）。
2. **电极清洁**：对充电电极表面使用**干燥抹布**擦拭，保持无水滴、无异物遮挡。  
   依据：DOC-004-C-00017（页8）。
3. **充电器清洁禁忌**：切勿使用酒精或其他可燃剂清洁充电器；切勿使用已有损坏的充电器。  
   依据：DOC-004-C-00030（页12）。
4. **接口发现水渍/异物时**：先不要上电或继续充电；手册只要求检查并确保无水滴，未给出接口内部水渍/异物的具体清除方法。不要自行用液体冲洗、金属工具清理或通电测试；无法确认干燥/清洁时停用并求助宇树官方。  
   依据：DOC-004-C-00034（页12）、DOC-004-C-00030（页12）。

### 3. 周期与安全前提
- 手册要求：**充电前后开展例行检查**，并**定时检查并保养充电器、经常检查外观各部件**；但未规定具体保养周期，应按官方维护规程确定。  
  依据：DOC-004-C-00034（页12）、DOC-004-C-00030（页12）。
- 关键安全条件：使用 Unitree 官方专用充电器；接触式充电器理想环境为 5°C–40°C、相对湿度≤95%、70–106 kPa；充电板周边空旷、无易燃可燃物，散热良好；充电时电池保持关闭；机器人运行结束后待电池降至室温再充电。  
  依据：DOC-004-C-00030（页12）。

**手册未记载、不能据此执行的内容**：充电器外壳的具体清洁剂/工具、充电接口内部清理步骤、拆解维修、电气测量及上电测试阈值。发现变形、鼓包、损坏或接口水渍异物无法确认排除时，应停用并求助官方。
```

### 2. 独立原文、范围与等价证据判断

C00017支持每次充电前干燥抹布擦电极；C00032要求长期未用先清洁板面、干燥软布擦板与机底电极、禁金属刷/砂纸。两者有部分重叠，不是全部等价。Final DOC-002-C-00054是机器人机身清洁，不能跨部件用作充电器工具禁令；回答关于接口不使用金属工具也不覆盖全部板面清洁。

**必要事实逐项链路**

| 必要事实/安全条件 | Corpus原文定位 | Candidate序号 | Rerank序号 | Final条目序号 | Answer与等价范围核查 |
|---|---|---|---|---|---|
| 定期维护、检查充电器及电池外观；损坏充电器禁用 | DOC-004-C-00030 / PDF 12–12 | 4 | 4 | 4 | 已表达 |
| 禁用酒精/其他可燃剂清洁 | DOC-004-C-00030 / PDF 12–12 | 4 | 4 | 4 | 已表达 |
| 长期未使用时，使用前先清洁充电板表面 | DOC-004-C-00032 / PDF 12–12 | 12 | 6 | 无 | 遗漏；电极擦拭不等于整块充电板表面清洁 |
| 擦拭前关闭电源 | DOC-004-C-00032 / PDF 12–12 | 12 | 6 | 无 | Final C00030“上电后勿触摸电极”支持其确保未上电的保守表达，已覆盖 |
| 干燥软布擦充电板表面及机身底部电极并确认擦净 | DOC-004-C-00032 / PDF 12–12 | 12 | 6 | 无 | Final C00017等价覆盖干燥擦电极部分；未覆盖软布与板面清洁整体 |
| 一般清洁禁金属刷和砂纸 | DOC-004-C-00032 / PDF 12–12 | 12 | 6 | 无 | 遗漏；Final DOC-002-C-00054仅B2机身，不适用充电器；回答接口金属工具禁令也不等价 |
| 充电器外观变形/鼓包检查 | DOC-004-C-00034 / PDF 12–12 | 5 | 1 | 1 | 已表达 |
| 充电接口水渍/异物检查 | DOC-004-C-00034 / PDF 12–12 | 5 | 1 | 1 | 已表达 |

### 3. 失败归因、实际程序条件与可优化性

**独立归因：** 主要Ranking；完整规范C00032候选12→rerank6→Top4排除；Final的部分电极清洁事实已被回答正确表达，没有证据证明模型看到了完整板面规范仍漏答。

**当前程序的确定路径：** checks[3] scope=true、met=false，support是Final C00017的一句电极清洁原文，verified只检查真实引用而不检查是否覆盖该复合requirement，326–327先追加Generation；checks[5]完整reference/candidate指向C00032且Final为空，追加Ranking。339–342取findings[0]，保存Generation、stage=None；diagnostic_view:278需要非空retrieval_failure_stage才产生ranking_omission，故只给confirmed_claim→grounded_generation。此处是已触发的诊断逻辑缺陷。

**工具箱与可验证假设：** 真实可验证上下文策略为top_k=6引入C00032；但当前Agent view只有grounded_generation，无法合法选择context_selection。切prompt_strategy=Completeness在当前缺证据Final上不能补齐未提供的工具禁令。应先修诊断的部分支持/完整支持区分，而不是改Judge评分或编答案。

**建议处理：** 保留FAIL；修复建议限于诊断证据覆盖与阶段归属，不能将部分Final支持强行视为完整Golden规范。真实优化仍需新授权实验。

**完整只读诊断输出（省去耗时明细，仅保留准入与证据）**

```json
{
  "primary_root_cause": "Generation",
  "target_eligible": true,
  "is_technical_bad_case": true,
  "retrieval_failure_stage": null,
  "trace_observations": [
    "confirmed_claim"
  ],
  "optimization_directions": [
    "grounded_generation"
  ],
  "evidence_checks": [
    {
      "answer_quotes": [
        "2. **电极清洁**：对充电电极表面使用**干燥抹布**擦拭，保持无水滴、无异物遮挡。"
      ],
      "candidate_support": [
        {
          "quote": "当长时间未使用接触式充电器，在使用前请先清洁充电板表面。擦拭表面时请先关闭电源，使用干燥的软布对充电板表面和机身底部充电电极进行擦拭，尤其关注表面是否擦拭干净；清洁时严禁使用金属刷、砂纸等，以免刮伤表面。",
          "source_id": "DOC-004-C-00032"
        }
      ],
      "check_type": "fact",
      "met": false,
      "reference_support": [
        {
          "quote": "当长时间未使用接触式充电器，在使用前请先清洁充电板表面。擦拭表面时请先关闭电源，使用干燥的软布对充电板表面和机身底部充电电极进行擦拭，尤其关注表面是否擦拭干净；清洁时严禁使用金属刷、砂纸等，以免刮伤表面。",
          "source_id": "DOC-004-C-00032"
        }
      ],
      "requirement": "长时间未使用接触式充电器，使用前应先清洁充电板表面；擦拭时应使用干燥的软布对充电板表面和机身底部充电电极进行擦拭，尤其关注表面是否擦拭干净。",
      "scope_resolved": true,
      "support": [
        {
          "quote": "请使用干燥抹布擦拭充电电极表面，确保充电过程中良好接触。",
          "source_id": "DOC-004-C-00017"
        }
      ],
      "candidate_missing": false
    },
    {
      "answer_quotes": [
        "4. **接口发现水渍/异物时**：先不要上电或继续充电；手册只要求检查并确保无水滴，未给出接口内部水渍/异物的具体清除方法。不要自行用液体冲洗、金属工具清理或通电测试；无法确认干燥/清洁时停用并求助宇树官方。"
      ],
      "candidate_support": [
        {
          "quote": "清洁时严禁使用金属刷、砂纸等，以免刮伤表面。",
          "source_id": "DOC-004-C-00032"
        }
      ],
      "check_type": "fact",
      "met": false,
      "reference_support": [
        {
          "quote": "清洁时严禁使用金属刷、砂纸等，以免刮伤表面。",
          "source_id": "DOC-004-C-00032"
        }
      ],
      "requirement": "清洁时严禁使用金属刷、砂纸等，以免刮伤表面。",
      "scope_resolved": true,
      "support": [],
      "candidate_missing": false
    }
  ]
}
```

### 4. Judge原始判定与检查（未改写）

保存业务verdict=FAIL；原始Judge verdict=FAIL。
<details><summary>完整原始Provider JSON（含所有checks、issues、support与reason）</summary>

```json
{"verdict":"FAIL","checks":[{"check_type":"fact","requirement":"应定时检查并保养充电器，经常检查充电器和电池外观等各个部件；检查充电器表面有无变形、鼓包，检查充电接口有无水渍、异物；已有损坏的充电器切勿使用。","met":true,"answer_quotes":["- **充电器外观/整体**：检查表面有无变形、鼓包；经常检查充电器和电池外观等各个部件；已有损坏的充电器切勿使用。","- **充电接口**：检查有无水渍、异物；使用时确保充电板表面和接口无水滴。","手册要求：**充电前后开展例行检查**，并**定时检查并保养充电器、经常检查外观各部件**；但未规定具体保养周期，应按官方维护规程确定。"],"support":[{"source_id":"DOC-004-C-00034","quote":"1. 检查充电器表面有无变形、鼓包等；\n2. 检查充电接口有无水渍、异物等。"},{"source_id":"DOC-004-C-00030","quote":"13. 定时检查并保养充电器，经常检查充电器和电池外观等各个部件。切勿使用酒精或其他可燃剂清洁充电器。切勿使用已有损坏的充电器。"}],"scope_resolved":true},{"check_type":"fact","requirement":"充电前应检查B2机身底部充电电极和充电板充电电极表面有无异物遮挡，并使用干燥抹布擦拭充电电极表面，确保充电接触良好。","met":true,"answer_quotes":["- **充电电极**：检查充电板充电电极表面、B2 机身底部充电电极有无异物遮挡；用干燥抹布擦拭充电电极表面，确保充电接触良好。"],"support":[{"source_id":"DOC-004-C-00017","quote":"1. 充电前检查：在每次充电前，请检查 B2 机身底部的充电电极是否有异物遮挡，以及充电板充电电极表面是否有异物遮挡。请使用干燥抹布擦拭充电电极表面，确保充电过程中良好接触。"}],"scope_resolved":true},{"check_type":"fact","requirement":"清洁充电器时切勿使用酒精或其他可燃剂清洁充电器；切勿使用已有损坏的充电器。","met":true,"answer_quotes":["3. **充电器清洁禁忌**：切勿使用酒精或其他可燃剂清洁充电器；切勿使用已有损坏的充电器。"],"support":[{"source_id":"DOC-004-C-00030","quote":"13. 定时检查并保养充电器，经常检查充电器和电池外观等各个部件。切勿使用酒精或其他可燃剂清洁充电器。切勿使用已有损坏的充电器。"}],"scope_resolved":true},{"check_type":"fact","requirement":"长时间未使用接触式充电器，使用前应先清洁充电板表面；擦拭时应使用干燥的软布对充电板表面和机身底部充电电极进行擦拭，尤其关注表面是否擦拭干净。","met":false,"answer_quotes":["2. **电极清洁**：对充电电极表面使用**干燥抹布**擦拭，保持无水滴、无异物遮挡。"],"support":[{"source_id":"DOC-004-C-00017","quote":"请使用干燥抹布擦拭充电电极表面，确保充电过程中良好接触。"}],"reference_support":[{"source_id":"DOC-004-C-00032","quote":"当长时间未使用接触式充电器，在使用前请先清洁充电板表面。擦拭表面时请先关闭电源，使用干燥的软布对充电板表面和机身底部充电电极进行擦拭，尤其关注表面是否擦拭干净；清洁时严禁使用金属刷、砂纸等，以免刮伤表面。"}],"candidate_support":[{"source_id":"DOC-004-C-00032","quote":"当长时间未使用接触式充电器，在使用前请先清洁充电板表面。擦拭表面时请先关闭电源，使用干燥的软布对充电板表面和机身底部充电电极进行擦拭，尤其关注表面是否擦拭干净；清洁时严禁使用金属刷、砂纸等，以免刮伤表面。"}],"scope_resolved":true},{"check_type":"fact","requirement":"清洁或擦拭充电板表面和电极前应先关闭电源，或至少确保充电板未上电。","met":true,"answer_quotes":["1. **先确保未上电**：进行电极接触清洁前，应确保充电板未上电；手册明确“上电后请勿触摸充电板电极”，且表面勿放置导电金属物品。"],"support":[{"source_id":"DOC-004-C-00030","quote":"3. 使用接触式充电器充电时，上电后，请勿触摸充电板电极！！！表面请勿放置导电等金属物品。"}],"scope_resolved":true},{"check_type":"fact","requirement":"清洁时严禁使用金属刷、砂纸等，以免刮伤表面。","met":false,"answer_quotes":["4. **接口发现水渍/异物时**：先不要上电或继续充电；手册只要求检查并确保无水滴，未给出接口内部水渍/异物的具体清除方法。不要自行用液体冲洗、金属工具清理或通电测试；无法确认干燥/清洁时停用并求助宇树官方。"],"support":[],"reference_support":[{"source_id":"DOC-004-C-00032","quote":"清洁时严禁使用金属刷、砂纸等，以免刮伤表面。"}],"candidate_support":[{"source_id":"DOC-004-C-00032","quote":"清洁时严禁使用金属刷、砂纸等，以免刮伤表面。"}],"scope_resolved":true},{"check_type":"fact","requirement":"充电器使用和维护相关安全前提：使用Unitree官方专用充电器；接触式充电器理想环境为5°C–40°C、相对湿度≤95%、70–106 kPa；充电板周边空旷、无易燃可燃物且散热良好；充电时电池保持关闭；机器人运行结束后待电池降至室温再充电。","met":true,"answer_quotes":["- 关键安全条件：使用 Unitree 官方专用充电器；接触式充电器理想环境为 5°C–40°C、相对湿度≤95%、70–106 kPa；充电板周边空旷、无易燃可燃物，散热良好；充电时电池保持关闭；机器人运行结束后待电池降至室温再充电。"],"support":[{"source_id":"DOC-004-C-00030","quote":"2. 接触式充电器理想工作环境温度为 $5^{\\circ}$ C- $40^{\\circ}$ C，相对湿度 $\\leq95\\%$ ，大气压力 70\\~106Kpa。"},{"source_id":"DOC-004-C-00030","quote":"5. 使用时请确保充电板表面和接口无水滴，周边空旷无障碍物。"},{"source_id":"DOC-004-C-00030","quote":"8. 充电时，请注意确保电池周边的环境散热良好，没有杂物等易燃易爆物品。"},{"source_id":"DOC-004-C-00030","quote":"9. 充电时，请保持电池处于关闭状态。"},{"source_id":"DOC-004-C-00030","quote":"10. 必须使用 Unitree 官方提供的专用充电器进行充电。对于使用非 Unitree 官方提供的充电器进行充电所造成的一切后果，Unitree 将不予负责。"},{"source_id":"DOC-004-C-00030","quote":"11. 使用接触式充电器充电时请将充电板和 B2 放置在水泥地面等周围无易燃、可燃物的地面。请留意充电过程，以防发生意外。"},{"source_id":"DOC-004-C-00030","quote":"12. 禁止在机器人运行结束后，立刻对进行充电。此时，电池处于高温状态，强制充电会对电池寿命造成严重损害。建议待电池降至室温，再进行充电。"}],"scope_resolved":true}],"issues":[{"description":"未按手册说明在长时间未使用接触式充电器时、使用前先清洁充电板表面；也未说明使用干燥的软布对充电板表面和机身底部充电电极进行擦拭并关注是否擦净。回答只写了用干燥抹布擦拭充电电极表面，未覆盖充电板表面清洁这一必要保养部位。","answer_quotes":["2. **电极清洁**：对充电电极表面使用**干燥抹布**擦拭，保持无水滴、无异物遮挡。"],"support":[{"source_id":"DOC-004-C-00032","quote":"当长时间未使用接触式充电器，在使用前请先清洁充电板表面。擦拭表面时请先关闭电源，使用干燥的软布对充电板表面和机身底部充电电极进行擦拭，尤其关注表面是否擦拭干净；清洁时严禁使用金属刷、砂纸等，以免刮伤表面。"}],"critical":true,"safety_violation":false,"scope_resolved":true,"baseline_issue_index":null},{"description":"未明确一般清洁充电板/电极时严禁使用金属刷、砂纸等以免刮伤表面；仅在“接口发现水渍/异物时”提到不要自行用金属工具清理，适用对象和场景不能覆盖充电板表面及电极的常规清洁要求，且未提及砂纸。","answer_quotes":["4. **接口发现水渍/异物时**：先不要上电或继续充电；手册只要求检查并确保无水滴，未给出接口内部水渍/异物的具体清除方法。不要自行用液体冲洗、金属工具清理或通电测试；无法确认干燥/清洁时停用并求助宇树官方。"],"support":[{"source_id":"DOC-004-C-00032","quote":"清洁时严禁使用金属刷、砂纸等，以免刮伤表面。"}],"critical":true,"safety_violation":false,"scope_resolved":true,"baseline_issue_index":null}],"reason":"回答覆盖了外观、接口、充电电极、电池外观、禁用酒精/可燃剂、损坏充电器停用、清洁前未上电及充电安全前提，但遗漏手册明确要求的“长时间未使用接触式充电器使用前清洁充电板表面”和“清洁时严禁金属刷、砂纸”等必要保养/安全内容；接口场景中的金属工具提醒不能替代一般清洁要求，故必要事实不完整，Positive不能PASS。","quality":{"correctness":3,"faithfulness":0.9,"completeness":0.6}}
```

</details>

### 5. 可复查的完整阶段证据

<details><summary>各阶段来源顺序、完整候选正文、完整Final与规范原文</summary>

**候选→重排→Final顺序**

```json
{
  "candidates": [
    {
      "position": 1,
      "chunk_id": "DOC-004-C-00001",
      "parent_chunk_id": "DOC-004-P-00001",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.8768
    },
    {
      "position": 2,
      "chunk_id": "DOC-004-C-00017",
      "parent_chunk_id": "DOC-004-P-00016",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.849
    },
    {
      "position": 3,
      "chunk_id": "DOC-004-C-00027",
      "parent_chunk_id": "DOC-004-P-00023",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.8335
    },
    {
      "position": 4,
      "chunk_id": "DOC-004-C-00030",
      "parent_chunk_id": "DOC-004-P-00025",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.823
    },
    {
      "position": 5,
      "chunk_id": "DOC-004-C-00034",
      "parent_chunk_id": "DOC-004-P-00029",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.8191
    },
    {
      "position": 6,
      "chunk_id": "DOC-001-C-00026",
      "parent_chunk_id": "DOC-001-P-00026",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5
    },
    {
      "position": 7,
      "chunk_id": "DOC-004-C-00031",
      "parent_chunk_id": "DOC-004-P-00026",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.5
    },
    {
      "position": 8,
      "chunk_id": "DOC-002-C-00004",
      "parent_chunk_id": "DOC-002-P-00004",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4565
    },
    {
      "position": 9,
      "chunk_id": "DOC-004-C-00012",
      "parent_chunk_id": "DOC-004-P-00011",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.4466
    },
    {
      "position": 10,
      "chunk_id": "DOC-002-C-00054",
      "parent_chunk_id": "DOC-002-P-00046",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4309
    },
    {
      "position": 11,
      "chunk_id": "DOC-004-C-00025",
      "parent_chunk_id": "DOC-004-P-00021",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.4308
    },
    {
      "position": 12,
      "chunk_id": "DOC-004-C-00032",
      "parent_chunk_id": "DOC-004-P-00027",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.4256
    }
  ],
  "reranked": [
    {
      "position": 1,
      "chunk_id": "DOC-004-C-00034",
      "parent_chunk_id": "DOC-004-P-00029",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.9379566812183999,
      "rerank_score": 0.9379566812183999
    },
    {
      "position": 2,
      "chunk_id": "DOC-004-C-00017",
      "parent_chunk_id": "DOC-004-P-00016",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.9252579723772605,
      "rerank_score": 0.9252579723772605
    },
    {
      "position": 3,
      "chunk_id": "DOC-002-C-00054",
      "parent_chunk_id": "DOC-002-P-00046",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.8444069427039325,
      "rerank_score": 0.8444069427039325
    },
    {
      "position": 4,
      "chunk_id": "DOC-004-C-00030",
      "parent_chunk_id": "DOC-004-P-00025",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.7921970204318223,
      "rerank_score": 0.7921970204318223
    },
    {
      "position": 5,
      "chunk_id": "DOC-002-C-00004",
      "parent_chunk_id": "DOC-002-P-00004",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.7693043361143859,
      "rerank_score": 0.7693043361143859
    },
    {
      "position": 6,
      "chunk_id": "DOC-004-C-00032",
      "parent_chunk_id": "DOC-004-P-00027",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.6985114797719654,
      "rerank_score": 0.6985114797719654
    },
    {
      "position": 7,
      "chunk_id": "DOC-004-C-00012",
      "parent_chunk_id": "DOC-004-P-00011",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.59419032833987,
      "rerank_score": 0.59419032833987
    },
    {
      "position": 8,
      "chunk_id": "DOC-004-C-00001",
      "parent_chunk_id": "DOC-004-P-00001",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.5829920186644132,
      "rerank_score": 0.5829920186644132
    },
    {
      "position": 9,
      "chunk_id": "DOC-004-C-00025",
      "parent_chunk_id": "DOC-004-P-00021",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.5593406602468517,
      "rerank_score": 0.5593406602468517
    },
    {
      "position": 10,
      "chunk_id": "DOC-004-C-00027",
      "parent_chunk_id": "DOC-004-P-00023",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.5262798536019738,
      "rerank_score": 0.5262798536019738
    },
    {
      "position": 11,
      "chunk_id": "DOC-004-C-00031",
      "parent_chunk_id": "DOC-004-P-00026",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.513349937313941,
      "rerank_score": 0.513349937313941
    },
    {
      "position": 12,
      "chunk_id": "DOC-001-C-00026",
      "parent_chunk_id": "DOC-001-P-00026",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4546226040458214,
      "rerank_score": 0.4546226040458214
    }
  ],
  "final": [
    {
      "position": 1,
      "chunk_id": "DOC-004-C-00034",
      "parent_chunk_id": "DOC-004-P-00029",
      "matched_child_ids": [
        "DOC-004-C-00034"
      ],
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.9379566812183999,
      "rerank_score": 0.9379566812183999
    },
    {
      "position": 2,
      "chunk_id": "DOC-004-C-00017",
      "parent_chunk_id": "DOC-004-P-00016",
      "matched_child_ids": [
        "DOC-004-C-00017"
      ],
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.9252579723772605,
      "rerank_score": 0.9252579723772605
    },
    {
      "position": 3,
      "chunk_id": "DOC-002-C-00054",
      "parent_chunk_id": "DOC-002-P-00046",
      "matched_child_ids": [
        "DOC-002-C-00054"
      ],
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.8444069427039325,
      "rerank_score": 0.8444069427039325
    },
    {
      "position": 4,
      "chunk_id": "DOC-004-C-00030",
      "parent_chunk_id": "DOC-004-P-00025",
      "matched_child_ids": [
        "DOC-004-C-00030"
      ],
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.7921970204318223,
      "rerank_score": 0.7921970204318223
    }
  ]
}
```

**全部候选正文（用于核查等价来源，而非只看ID）**
候选1：`DOC-004-C-00001` / `B2 电池与充电器`

```text
B2 电池&充电器
使用手册 V1.0
```

候选2：`DOC-004-C-00017` / `B2 电池与充电器`

```text
接触式充电器
1. 充电前检查：在每次充电前，请检查 B2 机身底部的充电电极是否有异物遮挡，以及充电板充电电极表面是否有异物遮挡。请使用干燥抹布擦拭充电电极表面，确保充电过程中良好接触。
2. 连接电源：将 B2 接触式充电器放置在空旷室内，先将锂电池充电器接入输入交流电源，然后连接接触式充电板电源接口，如下图所示。
交流电源
①
110-220V
②
锂电池充电器
3. 充电：使用接触式充电器充电时，先用遥控器操控机器人按照充电板面贴方向卧倒，请勿反冲！使 B2 机器人底部 2 个充电电极与充电板 2 个充电电极接触，实现充电。当电量充满时，会自动断开充电器与电池的连接。
B2 电池&充电器使用手册
8
© 2023 宇树科技 版权所有
```

候选3：`DOC-004-C-00027` / `B2 电池与充电器`

```text
- 保养
1. 切勿在温度过高或温度过低的环境下使用充电器对电池进行充电。
2. 切勿将电池存储在室温超过 $40^{\circ}$ C 的环境下。
3. 切勿过充电池，否则将对电芯造成损害。
4. 若较长时间不使用电池时，请定期检查电池剩余的电量，如果电量低于 30%，请把电池充电到 70% 后再继续保存。以免电池过放而损坏电池。
```

候选4：`DOC-004-C-00030` / `B2 电池与充电器`

```text
专用充电器进行充电。对于使用非 Unitree 官方提供的充电器进行充电所造成的一切后果，Unitree 将不予负责。
11. 使用接触式充电器充电时请将充电板和 B2 放置在水泥地面等周围无易燃、可燃物的地面。请留意充电过程，以防发生意外。
12. 禁止在机器人运行结束后，立刻对进行充电。此时，电池处于高温状态，强制充电会对电池寿命造成严重损害。建议待电池降至室温，再进行充电。理想的充电环境温度（5°C-40°C）可大幅度延长电池的使用寿命。
13. 定时检查并保养充电器，经常检查充电器和电池外观等各个部件。切勿使用酒精或其他可燃剂清洁充电器。切勿使用已有损坏的充电器。
```

候选5：`DOC-004-C-00034` / `B2 电池与充电器`

```text
- 检查
在充电前后开展例行检查，可大幅度提升产品可靠性能，降低安全隐患，延长使用寿命。
1. 检查充电器表面有无变形、鼓包等；
2. 检查充电接口有无水渍、异物等。
B2 电池&充电器使用手册
© 2023 宇树科技 版权所有
12
```

候选6：`DOC-001-C-00026` / `KIRA B 50`

```text
保养和维护
警告
在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接 
小心
只允许授权的客户服务部进行维修工作 备件安装和在电气零部件上进行工作
小心
只允许已授权的客户服务处或熟知该领域所有重要安全规定的专业人员进行设备修复工作
小心
定期清洁水位限制装置，并检查是否出现损坏
注意
在按照当地现行规定对用作商业用途的移动式设备进行安全检查时，
注意
注意是否出现短路或其它损坏 不得用软管或高压水射流清洁设备
```

候选7：`DOC-004-C-00031` / `B2 电池与充电器`

```text
充电器保养
```

候选8：`DOC-002-C-00004` / `B2 四足机器人`

```text
目录
免责申明....2
安全须知....3
产品概述....4
简介....4
部件名称....4
功能亮点....5
接口说明....6
如何充电....7
电池充电....7
遥控器充电....8
使用说明....9
使用环境要求....9
开箱....9
开机前检查....9
开机前准备....10
启动 B2....10
连接 Unitree Explore App....11
操控您的 B2....13
关闭 B2....14
装箱....14
异常情况说明....15
注意事项....16
日常保养与维护....17
整机清洁....17
检查保养....17
```

候选9：`DOC-004-C-00012` / `B2 电池与充电器`

```text
简介
插入式充电器是专门为B2电池配置的一个充电设备，体积小，重量轻，方便携带，为电池提供稳定的电力。
接触式充电器是专门为B2设计的，可与视觉识别、SLAM导航等技术相结合，自主规划充电路线，完成自动充电，大幅提升作业时间和效率，为全天候作业提供有力的保障。B2-接触式充电器由锂电池充电器和接触式充电板组成。
接触式充电板
```

候选10：`DOC-002-C-00054` / `B2 四足机器人`

```text
1. 清洁
当 B2 在恶劣环境下（雨天、沙尘、湿地）使用后，请及时清洁机身表面。
清洗机身前请先关闭电源，使用干净的软布对机身进行擦拭，尤其关注多目深度相机是否擦拭干净。清洁时严禁使用金属刷、砂纸等，以免刮伤零件表面。清洗后，请用软布将机身擦干。擦干后可用风扇或风枪将机器人表面、关节缝隙处的积水吹干，避免留下水痕。
\- 注意！B2 整机（含电池包）IP67 级防水，清洁时请勿取下电池包！
```

候选11：`DOC-004-C-00025` / `B2 电池与充电器`

```text
高温状态，强制充电会对电池包寿命造成严重损害。建议待电池包降至室温，再进行充电。理想的充电环境温度（5°C-40°C）可大幅度延长电池包的使用寿命。
9. 充电完毕后请断开充电器与电池包间的连接。定时检查并保养充电器，经常检查电池包外观等各个部件。切勿使用酒精或其他可燃剂清洁充电器。切勿使用已有损坏的充电器。
```

候选12：`DOC-004-C-00032` / `B2 电池与充电器`

```text
- 清洁
当长时间未使用接触式充电器，在使用前请先清洁充电板表面。擦拭表面时请先关闭电源，使用干燥的软布对充电板表面和机身底部充电电极进行擦拭，尤其关注表面是否擦拭干净；清洁时严禁使用金属刷、砂纸等，以免刮伤表面。
```

**完整Final（Parent展开后的真实模型输入正文）**
Final 1：`DOC-004-C-00034` / Parent `DOC-004-P-00029` / `宇树_B2电池与充电器使用说明_中文版.pdf` / PDF 12–12；source_scope=null

```text
- 检查
在充电前后开展例行检查，可大幅度提升产品可靠性能，降低安全隐患，延长使用寿命。
1. 检查充电器表面有无变形、鼓包等；
2. 检查充电接口有无水渍、异物等。
B2 电池&充电器使用手册
© 2023 宇树科技 版权所有
12
```

Final 2：`DOC-004-C-00017` / Parent `DOC-004-P-00016` / `宇树_B2电池与充电器使用说明_中文版.pdf` / PDF 8–8；source_scope=null

```text
接触式充电器
1. 充电前检查：在每次充电前，请检查 B2 机身底部的充电电极是否有异物遮挡，以及充电板充电电极表面是否有异物遮挡。请使用干燥抹布擦拭充电电极表面，确保充电过程中良好接触。
2. 连接电源：将 B2 接触式充电器放置在空旷室内，先将锂电池充电器接入输入交流电源，然后连接接触式充电板电源接口，如下图所示。
交流电源
①
110-220V
②
锂电池充电器
3. 充电：使用接触式充电器充电时，先用遥控器操控机器人按照充电板面贴方向卧倒，请勿反冲！使 B2 机器人底部 2 个充电电极与充电板 2 个充电电极接触，实现充电。当电量充满时，会自动断开充电器与电池的连接。
B2 电池&充电器使用手册
8
© 2023 宇树科技 版权所有
```

Final 3：`DOC-002-C-00054` / Parent `DOC-002-P-00046` / `宇树_B2四足机器人用户手册_中文版.pdf` / PDF 18–18；source_scope=null

```text
1. 清洁
当 B2 在恶劣环境下（雨天、沙尘、湿地）使用后，请及时清洁机身表面。
清洗机身前请先关闭电源，使用干净的软布对机身进行擦拭，尤其关注多目深度相机是否擦拭干净。清洁时严禁使用金属刷、砂纸等，以免刮伤零件表面。清洗后，请用软布将机身擦干。擦干后可用风扇或风枪将机器人表面、关节缝隙处的积水吹干，避免留下水痕。
\- 注意！B2 整机（含电池包）IP67 级防水，清洁时请勿取下电池包！
```

Final 4：`DOC-004-C-00030` / Parent `DOC-004-P-00025` / `宇树_B2电池与充电器使用说明_中文版.pdf` / PDF 12–12；source_scope=null

```text
注意事项
1. 严禁使用非 Unitree 官方提供的充电器进行充电。
2. 接触式充电器理想工作环境温度为 $5^{\circ}$ C- $40^{\circ}$ C，相对湿度 $\leq95\%$ ，大气压力 70\~106Kpa。
3. 使用接触式充电器充电时，上电后，请勿触摸充电板电极！！！表面请勿放置导电等金属物品。
4. 充电板有正反极性，充电时请将头部按照面贴箭头方向，请勿反冲！！！
5. 使用时请确保充电板表面和接口无水滴，周边空旷无障碍物。
6. 在使用、移动或者充电时，请小心充电插头，以免被外力损坏。
7. 充电过程中，请确保在视线可见内充电，防止发生不可预知的意外。
8. 充电时，请注意确保电池周边的环境散热良好，没有杂物等易燃易爆物品。
9. 充电时，请保持电池处于关闭状态。
10. 必须使用 Unitree 官方提供的专用充电器进行充电。对于使用非 Unitree 官方提供的充电器进行充电所造成的一切后果，Unitree 将不予负责。
11. 使用接触式充电器充电时请将充电板和 B2 放置在水泥地面等周围无易燃、可燃物的地面。请留意充电过程，以防发生意外。
12. 禁止在机器人运行结束后，立刻对进行充电。此时，电池处于高温状态，强制充电会对电池寿命造成严重损害。建议待电池降至室温，再进行充电。理想的充电环境温度（5°C-40°C）可大幅度延长电池的使用寿命。
13. 定时检查并保养充电器，经常检查充电器和电池外观等各个部件。切勿使用酒精或其他可燃剂清洁充电器。切勿使用已有损坏的充电器。
```

**本题规范原文与元数据（Corpus完整Child）**
`DOC-004-C-00030`；B2 电池与充电器；PDF 12–12；version=None

```text
专用充电器进行充电。对于使用非 Unitree 官方提供的充电器进行充电所造成的一切后果，Unitree 将不予负责。
11. 使用接触式充电器充电时请将充电板和 B2 放置在水泥地面等周围无易燃、可燃物的地面。请留意充电过程，以防发生意外。
12. 禁止在机器人运行结束后，立刻对进行充电。此时，电池处于高温状态，强制充电会对电池寿命造成严重损害。建议待电池降至室温，再进行充电。理想的充电环境温度（5°C-40°C）可大幅度延长电池的使用寿命。
13. 定时检查并保养充电器，经常检查充电器和电池外观等各个部件。切勿使用酒精或其他可燃剂清洁充电器。切勿使用已有损坏的充电器。
```

`DOC-004-C-00032`；B2 电池与充电器；PDF 12–12；version=None

```text
- 清洁
当长时间未使用接触式充电器，在使用前请先清洁充电板表面。擦拭表面时请先关闭电源，使用干燥的软布对充电板表面和机身底部充电电极进行擦拭，尤其关注表面是否擦拭干净；清洁时严禁使用金属刷、砂纸等，以免刮伤表面。
```

`DOC-004-C-00034`；B2 电池与充电器；PDF 12–12；version=None

```text
- 检查
在充电前后开展例行检查，可大幅度提升产品可靠性能，降低安全隐患，延长使用寿命。
1. 检查充电器表面有无变形、鼓包等；
2. 检查充电接口有无水渍、异物等。
B2 电池&充电器使用手册
© 2023 宇树科技 版权所有
12
```

</details>

## Q17 — FAIL合理；R1分支答对，R3必要步骤/确认方法漏答，并错误否认手册有相关细节。

真实题号：`V1G-110926448917-17`；类别：`positive`。

### 1. 冻结Golden与实际回答

**问题（完整）**

```text
客户原来的 B2 遥控器坏了，我拿同型号备件换上，新遥控器开机后机器人没反应，应该是还没跟机器人配对。按用户手册，B2 遥控器怎么跟机器人重新配对或绑定？配对成功后怎么确认？
```

**冻结参考答案（完整，保留原始文字）**

```text
R3 遥控器基本操作
首次使用遥控器需要在 Unitree Explore App 上进行遥控器绑定，【设置】->【遥控器设置】-打开遥控器开关，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。
遥控器开机并且与 B2 连接成功后，右侧 DL 指示灯亮，这就意味着遥控器与 B2 数传模块已连接，此时可通过遥控器控制 B2。
R1 遥控器基本操作
首次使用遥控器需要在 Unitree Explore App 上进行遥控器绑定，【设置】->【遥控器设置】，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。
遥控器开机并且与 B2 连接成功后，左侧面数据传输灯全亮，这就意味着遥控器与 B2 数传模块已连接，此时可通过遥控器控制 B2。
```

**冻结Golden evidence字段（原样；摘要不能冒充完整规范）**

```json
[
  {
    "evidence_key_points": [
      "R3 遥控器基本操作\n首次使用遥控器需要在 Unitree Explore App 上进行遥控器绑定，【设置】->【遥控器设置】-打开遥控器开关，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。\n遥控器开机并且与 B2 连接成功后，右侧 DL 指示灯亮，这就意味着遥控器与 B2 数传模块已连接，此时可通过遥控器",
      "R1 遥控器基本操作\n首次使用遥控器需要在 Unitree Explore App 上进行遥控器绑定，【设置】->【遥控器设置】，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。\n遥控器开机并且与 B2 连接成功后，左侧面数据传输灯全亮，这就意味着遥控器与 B2 数传模块已连接，此时可通过遥控器控制 B2。使用"
    ],
    "source_chunk_ids": [
      "DOC-003-C-00015",
      "DOC-003-C-00025"
    ]
  }
]
```

**RAG实际回答（完整）**

```text
请先核对新备件遥控器本体标识：是 **R1 遥控器**还是 **R3 遥控器**。手册 V2.1 中只有 R1 给出了完整绑定菜单和连接确认灯；R3 仅说明可通过 App 绑定，未给出同样的确认细节。

**若确认是 R1 遥控器：**
1. 打开 **Unitree Explore App**，进入 **【设置】→【遥控器设置】**。
2. 输入新遥控器对应的**遥控器编码**，与机器狗上的数传模块进行绑定。[DOC-003-C-00025]
3. 绑定成功后，遥控器开机即可自动连接。[DOC-003-C-00019]
4. **确认连接成功**：遥控器开机并与 B2 连接成功后，**左侧面数据传输灯全亮**，表示遥控器与 B2 数传模块已连接，此时可通过遥控器控制 B2。[DOC-003-C-00025]

**若备件是 R3 遥控器：**  
证据仅说明 R3 可通过 Unitree Explore App 绑定，绑定成功后开机即可自动连接。[DOC-003-C-00005] 但未提供具体菜单路径和“左侧数据传输灯全亮”的确认描述，因此不能把 R1 的确认方法直接套用到 R3。请补充/确认 R3 型号及对应章节后再按该型号操作。

依据：B2 遥控器使用手册 V2.1，DOC-003-C-00025、DOC-003-C-00019、DOC-003-C-00005。
```

### 2. 独立原文、范围与等价证据判断

PDF6直观可见R3标题、设置→遥控器设置、打开开关、输入编码、右侧DL灯；PDF11为R1左侧灯。R3是B2遥控器系列分支，不是与B2冲突的另一个产品。Final R3简介C00005提供App绑定/开机自动连接，但不提供完整路径、开关、右DL灯；R1证据不能替R3灯。

**必要事实逐项链路**

| 必要事实/安全条件 | Corpus原文定位 | Candidate序号 | Rerank序号 | Final条目序号 | Answer与等价范围核查 |
|---|---|---|---|---|---|
| R1：App设置→遥控器设置→输入编码绑定 | DOC-003-C-00025 / PDF 11–12 | 2 | 1 | 1 | 已表达 |
| R1：左侧面数据传输灯全亮确认 | DOC-003-C-00025 / PDF 11–12 | 2 | 1 | 1 | 已表达 |
| R3：App设置→遥控器设置→打开遥控器开关→输入编码 | DOC-003-C-00015 / PDF 6–7 | 无 | 无 | 无 | 遗漏；Final C00005仅App绑定简介，不给完整菜单和开关步骤 |
| R3：右侧DL指示灯亮确认 | DOC-003-C-00015 / PDF 6–7 | 无 | 无 | 无 | 遗漏；不能套用R1左侧灯，也不能断言手册没有R3方法 |

### 3. 失败归因、实际程序条件与可优化性

**独立归因：** 人工证据支持R3专属信息的Retrieval；还存在把Final缺失扩写成整本手册不存在的生成过度断言，但不把缺失事实整体归为Generation。

**当前程序的确定路径：** checks[2]/[3]已经candidate_support=[]、reference=C00015且Corpus定位成功，但scope_resolved=false，325行直接continue，尚未执行328行。issue亦scope=false被333行跳过。False不是Canonical、ID或版本漂移：四个前置检查均通过；实际缺的是同次Judge对“R3章节适用于B2系列该分支”的明确范围确认。运行时未知现场备件究竟R1还是R3，不应与手册源适用范围混为一谈。

**工具箱与可验证假设：** 明确源适用范围后，现有query_expansion/candidate_recall可测试把R3完整章节纳入候选；仅Top6不能恢复池外C00015。对“未见→不存在”的表达可测试现有Grounded/Completeness，但这不能代替召回专属绑定规范。

**建议处理：** 保留FAIL/Unknown与未指定现场型号的澄清边界。不能只把scope=false改true；如要完善同次Judge范围定义/输出，须新Prompt身份评测，或另存可核验诊断而不回填正式判分。

**完整只读诊断输出（省去耗时明细，仅保留准入与证据）**

```json
{
  "primary_root_cause": "Unknown",
  "target_eligible": false,
  "is_technical_bad_case": false,
  "retrieval_failure_stage": null,
  "trace_observations": [],
  "optimization_directions": [],
  "evidence_checks": []
}
```

### 4. Judge原始判定与检查（未改写）

保存业务verdict=FAIL；原始Judge verdict=FAIL。
<details><summary>完整原始Provider JSON（含所有checks、issues、support与reason）</summary>

```json
{"verdict":"FAIL","checks":[{"check_type":"fact","requirement":"R1 遥控器绑定：在 Unitree Explore App 的【设置】→【遥控器设置】中输入对应遥控器编码，与机器狗上的数传模块绑定。","met":true,"answer_quotes":["打开 **Unitree Explore App**，进入 **【设置】→【遥控器设置】**。","输入新遥控器对应的**遥控器编码**，与机器狗上的数传模块进行绑定。[DOC-003-C-00025]"],"support":[{"source_id":"DOC-003-C-00025","quote":"首次使用遥控器需要在 Unitree Explore App 上进行遥控器绑定，【设置】->【遥控器设置】，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。"}],"reference_support":[{"source_id":"DOC-003-C-00025","quote":"首次使用遥控器需要在 Unitree Explore App 上进行遥控器绑定，【设置】->【遥控器设置】，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。"}],"candidate_support":[{"source_id":"DOC-003-C-00025","quote":"首次使用遥控器需要在 Unitree Explore App 上进行遥控器绑定，【设置】->【遥控器设置】，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。"}],"scope_resolved":true},{"check_type":"fact","requirement":"R1 遥控器与 B2 连接成功后，左侧面数据传输灯全亮，表示已连接并可通过遥控器控制 B2。","met":true,"answer_quotes":["4. **确认连接成功**：遥控器开机并与 B2 连接成功后，**左侧面数据传输灯全亮**，表示遥控器与 B2 数传模块已连接，此时可通过遥控器控制 B2。[DOC-003-C-00025]"],"support":[{"source_id":"DOC-003-C-00025","quote":"遥控器开机并且与 B2 连接成功后，左侧面数据传输灯全亮，这就意味着遥控器与 B2 数传模块已连接，此时可通过遥控器控制 B2。"}],"reference_support":[{"source_id":"DOC-003-C-00025","quote":"遥控器开机并且与 B2 连接成功后，左侧面数据传输灯全亮，这就意味着遥控器与 B2 数传模块已连接，此时可通过遥控器控制 B2。"}],"candidate_support":[{"source_id":"DOC-003-C-00025","quote":"遥控器开机并且与 B2 连接成功后，左侧面数据传输灯全亮，这就意味着遥控器与 B2 数传模块已连接，此时可通过遥控器控制 B2。"}],"scope_resolved":true},{"check_type":"fact","requirement":"R3 遥控器绑定：需在 Unitree Explore App 的【设置】→【遥控器设置】中，打开遥控器开关，输入对应遥控器编码，与机器狗上的数传模块绑定。","met":false,"answer_quotes":["手册 V2.1 中只有 R1 给出了完整绑定菜单和连接确认灯；R3 仅说明可通过 App 绑定，未给出同样的确认细节。","**若备件是 R3 遥控器：**  \n证据仅说明 R3 可通过 Unitree Explore App 绑定，绑定成功后开机即可自动连接。[DOC-003-C-00005] 但未提供具体菜单路径和“左侧数据传输灯全亮”的确认描述，因此不能把 R1 的确认方法直接套用到 R3。请补充/确认 R3 型号及对应章节后再按该型号操作。"],"support":[],"reference_support":[{"source_id":"DOC-003-C-00015","quote":"R3 遥控器基本操作\n首次使用遥控器需要在 Unitree Explore App 上进行遥控器绑定，【设置】->【遥控器设置】-打开遥控器开关，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。"}],"candidate_support":[],"scope_resolved":false},{"check_type":"fact","requirement":"R3 遥控器与 B2 连接成功后，右侧 DL 指示灯亮，表示遥控器与 B2 数传模块已连接并可通过遥控器控制 B2。","met":false,"answer_quotes":["**若备件是 R3 遥控器：**  \n证据仅说明 R3 可通过 Unitree Explore App 绑定，绑定成功后开机即可自动连接。[DOC-003-C-00005] 但未提供具体菜单路径和“左侧数据传输灯全亮”的确认描述，因此不能把 R1 的确认方法直接套用到 R3。请补充/确认 R3 型号及对应章节后再按该型号操作。"],"support":[],"reference_support":[{"source_id":"DOC-003-C-00015","quote":"遥控器开机并且与 B2 连接成功后，右侧 DL 指示灯亮，这就意味着遥控器与 B2 数传模块已连接，此时可通过遥控器控制 B2。"}],"candidate_support":[],"scope_resolved":false}],"issues":[{"description":"答案错误地否认手册 V2.1 中 R3 遥控器有完整绑定菜单和连接确认灯，未给出 R3 应通过【设置】→【遥控器设置】→打开遥控器开关→输入编码绑定，以及右侧 DL 指示灯亮确认；导致 R3 分支缺失且与手册矛盾。","answer_quotes":["手册 V2.1 中只有 R1 给出了完整绑定菜单和连接确认灯；R3 仅说明可通过 App 绑定，未给出同样的确认细节。","证据仅说明 R3 可通过 Unitree Explore App 绑定，绑定成功后开机即可自动连接。[DOC-003-C-00005] 但未提供具体菜单路径和“左侧数据传输灯全亮”的确认描述，因此不能把 R1 的确认方法直接套用到 R3。"],"support":[],"critical":true,"safety_violation":false,"scope_resolved":false,"baseline_issue_index":null}],"reason":"R1 的绑定路径和左侧数据传输灯确认回答正确；但问题涉及 B2 遥控器手册中的 R1/R3 两个分支。答案错误地称 R3 没有完整绑定菜单和确认灯，且未给出 R3 的设置→遥控器设置→打开开关→输入编码绑定及右侧 DL 指示灯确认。该遗漏和反事实陈述使必要事实不完整，故判 FAIL。未发现安全边界失败。","quality":{"correctness":2,"faithfulness":0.4,"completeness":0.4}}
```

</details>

### 5. 可复查的完整阶段证据

<details><summary>各阶段来源顺序、完整候选正文、完整Final与规范原文</summary>

**候选→重排→Final顺序**

```json
{
  "candidates": [
    {
      "position": 1,
      "chunk_id": "DOC-003-C-00019",
      "parent_chunk_id": "DOC-003-P-00017",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.9883
    },
    {
      "position": 2,
      "chunk_id": "DOC-003-C-00025",
      "parent_chunk_id": "DOC-003-P-00023",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.9495
    },
    {
      "position": 3,
      "chunk_id": "DOC-002-C-00046",
      "parent_chunk_id": "DOC-002-P-00041",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.9368
    },
    {
      "position": 4,
      "chunk_id": "DOC-002-C-00008",
      "parent_chunk_id": "DOC-002-P-00006",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.5
    },
    {
      "position": 5,
      "chunk_id": "DOC-003-C-00005",
      "parent_chunk_id": "DOC-003-P-00005",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.495
    },
    {
      "position": 6,
      "chunk_id": "DOC-002-C-00043",
      "parent_chunk_id": "DOC-002-P-00038",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4898
    },
    {
      "position": 7,
      "chunk_id": "DOC-003-C-00001",
      "parent_chunk_id": "DOC-003-P-00001",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.4827
    },
    {
      "position": 8,
      "chunk_id": "DOC-002-C-00044",
      "parent_chunk_id": "DOC-002-P-00039",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4721
    },
    {
      "position": 9,
      "chunk_id": "DOC-002-C-00033",
      "parent_chunk_id": "DOC-002-P-00028",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4705
    },
    {
      "position": 10,
      "chunk_id": "DOC-002-C-00051",
      "parent_chunk_id": "DOC-002-P-00043",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4695
    },
    {
      "position": 11,
      "chunk_id": "DOC-002-C-00039",
      "parent_chunk_id": "DOC-002-P-00034",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4656
    },
    {
      "position": 12,
      "chunk_id": "DOC-001-C-00026",
      "parent_chunk_id": "DOC-001-P-00026",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4644
    }
  ],
  "reranked": [
    {
      "position": 1,
      "chunk_id": "DOC-003-C-00025",
      "parent_chunk_id": "DOC-003-P-00023",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.7599221125825881,
      "rerank_score": 0.7599221125825881
    },
    {
      "position": 2,
      "chunk_id": "DOC-003-C-00005",
      "parent_chunk_id": "DOC-003-P-00005",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.7048051847359627,
      "rerank_score": 0.7048051847359627
    },
    {
      "position": 3,
      "chunk_id": "DOC-003-C-00019",
      "parent_chunk_id": "DOC-003-P-00017",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.6962756390013527,
      "rerank_score": 0.6962756390013527
    },
    {
      "position": 4,
      "chunk_id": "DOC-003-C-00001",
      "parent_chunk_id": "DOC-003-P-00001",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.5736369080093234,
      "rerank_score": 0.5736369080093234
    },
    {
      "position": 5,
      "chunk_id": "DOC-002-C-00033",
      "parent_chunk_id": "DOC-002-P-00028",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.42458370208146134,
      "rerank_score": 0.42458370208146134
    },
    {
      "position": 6,
      "chunk_id": "DOC-002-C-00039",
      "parent_chunk_id": "DOC-002-P-00034",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.41357641298584275,
      "rerank_score": 0.41357641298584275
    },
    {
      "position": 7,
      "chunk_id": "DOC-002-C-00008",
      "parent_chunk_id": "DOC-002-P-00006",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4053851783257661,
      "rerank_score": 0.4053851783257661
    },
    {
      "position": 8,
      "chunk_id": "DOC-002-C-00046",
      "parent_chunk_id": "DOC-002-P-00041",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.3626211084896216,
      "rerank_score": 0.3626211084896216
    },
    {
      "position": 9,
      "chunk_id": "DOC-002-C-00044",
      "parent_chunk_id": "DOC-002-P-00039",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.33509700059401154,
      "rerank_score": 0.33509700059401154
    },
    {
      "position": 10,
      "chunk_id": "DOC-001-C-00026",
      "parent_chunk_id": "DOC-001-P-00026",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.30655910633636774,
      "rerank_score": 0.30655910633636774
    },
    {
      "position": 11,
      "chunk_id": "DOC-002-C-00051",
      "parent_chunk_id": "DOC-002-P-00043",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.293145448913675,
      "rerank_score": 0.293145448913675
    },
    {
      "position": 12,
      "chunk_id": "DOC-002-C-00043",
      "parent_chunk_id": "DOC-002-P-00038",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.235100706473516,
      "rerank_score": 0.235100706473516
    }
  ],
  "final": [
    {
      "position": 1,
      "chunk_id": "DOC-003-C-00025",
      "parent_chunk_id": "DOC-003-P-00023",
      "matched_child_ids": [
        "DOC-003-C-00025"
      ],
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "source_scope": {
        "heading": "R1遥控器",
        "page_start": 9,
        "quote": "R1遥控器",
        "source_id": "DOC-003-C-00018"
      },
      "score": 0.7599221125825881,
      "rerank_score": 0.7599221125825881
    },
    {
      "position": 2,
      "chunk_id": "DOC-003-C-00005",
      "parent_chunk_id": "DOC-003-P-00005",
      "matched_child_ids": [
        "DOC-003-C-00005"
      ],
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "source_scope": {
        "heading": "R3遥控器",
        "page_start": 2,
        "quote": "R3遥控器",
        "source_id": "DOC-003-C-00004"
      },
      "score": 0.7048051847359627,
      "rerank_score": 0.7048051847359627
    },
    {
      "position": 3,
      "chunk_id": "DOC-003-C-00019",
      "parent_chunk_id": "DOC-003-P-00017",
      "matched_child_ids": [
        "DOC-003-C-00019"
      ],
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "source_scope": {
        "heading": "R1遥控器",
        "page_start": 9,
        "quote": "R1遥控器",
        "source_id": "DOC-003-C-00018"
      },
      "score": 0.6962756390013527,
      "rerank_score": 0.6962756390013527
    },
    {
      "position": 4,
      "chunk_id": "DOC-003-C-00001",
      "parent_chunk_id": "DOC-003-P-00001",
      "matched_child_ids": [
        "DOC-003-C-00001"
      ],
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.5736369080093234,
      "rerank_score": 0.5736369080093234
    }
  ]
}
```

**全部候选正文（用于核查等价来源，而非只看ID）**
候选1：`DOC-003-C-00019` / `B2 遥控器`

```text
简介
遥控器属于 B2 遥控模块的一部分，遥控手柄内置数传模块、蓝牙模块。机器人与遥控器可以通过 Unitree Explore App 进行绑定，绑定成功后开机即可自动连接。可操纵机器人在站立时实现 3 轴姿态与 3 轴位置稳定全控，还可以操纵机器人在平整地面上实现前进后退、左右侧移、原地转弯、按一定规则行走（直线，圆形，线，矩形）、上下斜坡/台阶等。遥控手柄采用更加容易持握的设计，结构符合人体工程学，手感更舒适。
```

候选2：`DOC-003-C-00025` / `B2 遥控器`

```text
R1 遥控器基本操作
首次使用遥控器需要在 Unitree Explore App 上进行遥控器绑定，【设置】->【遥控器设置】，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。
遥控器开机并且与 B2 连接成功后，左侧面数据传输灯全亮，这就意味着遥控器与 B2 数传模块已连接，此时可通过遥控器控制 B2。使用遥控器摇杆操控 B2 时，摇杆的操控方式如下所示：
左摇杆
右摇杆
(AI 运控模式下不支持抬头低头)
\- 摇杆回中/中位：遥控器的摇杆处于中间位置。
11
B2 遥控器使用手册
- 摇杆杆量：遥控器摇杆偏离摇杆中位的偏移量。
- 墙面、门等阻挡物会极大削弱机器狗和遥控模块之间的信号，请务必在空旷的场地操作机器狗。
© 2024 宇树科技 版权所有
机器狗参照示意图：
| 侧视图 | 俯视图 | 正视图
机器狗 |  |  | 
参照图 |  |  |
按键 | 效果
左摇杆 | 前后左右
右摇杆 | 左右旋转
姿态切换
START | 解除锁定
灵动模式(默认)
L2 (长按) + A (单击) | 站立锁定/卧倒姿态切换
L2 (长按) + B (单击) | 阻尼模式(软急停)
R1 (双
```

候选3：`DOC-002-C-00046` / `B2 四足机器人`

```text
- 机器人容易摔倒，开机无法站立
没有使用正确的开机姿势，导致机身电机角度错误，使用正确的开机姿势后重新开机。若重启机器人无法解决问题，此时需要按照Unitree Explore App相关步骤对机器人关节重新进行标定。
注意：B2 出厂后默认已经完成标定，正常使用请勿进行关节标定！！！在 B2 出现异常情况后请先咨询 Unitree 官方技术支持后确定是否需要重新标定关节！！！
App 关节标定入口为 [设置] -> [数据] -> [机器狗] -> [标定]。
```

候选4：`DOC-002-C-00008` / `B2 四足机器人`

```text
安全须知
B2是一款具备全天候作业、强劲负载与扩展空间、多维感知、全场景覆盖、强劲算力与精准洞察等特点，面向行业级应用的四足机器人，可以为您提供更高效、智能的解决方案。
1. 本产品并非玩具，不适合未满 18 岁的人士使用。请勿让儿童接触，在有儿童出现的场景操作时务必特别小心注意。
2. 您有义务知悉您所在区域的法律，并遵守相关法律和法规。
3. 本手册是新玩家操纵机器人的入门章节，新玩家可以通过阅读此节快速掌握如何使用手柄控制机器人的方法，使机器人表现出卓越的运动性能。本手册也是老玩家需时常查阅的章节，老玩家可通过反复查阅本章内容，抓住操作机器人的要领，举一反三，并且熟知哪些动作是不推荐使用。
4. 当用户在开发者模式下运行自己开发的程序：高层（应用层）开发时遥控器命令仍有效，此时若高层API命令和遥控器命令一起发送给机器人，两种命令机器人都会执行，可能会导致机器人失稳，请务必根据机器人运行状态判断是否需要使用遥控器
```

候选5：`DOC-003-C-00005` / `B2 遥控器`

```text
简介
R3 遥控器属于 B2 遥控模块的一部分,遥控手柄内置数传模块、蓝牙模块。机器狗与遥控器可以通过 Unitree Explore App 进行绑定，绑定成功后开机即可自动连接。可操纵机器狗在站立时实现 3 轴姿态与 3 轴位置稳定全控，还可以操纵机器狗在平整地面上实现前进后退、左右侧移、原地转弯、按一定规则行走（直线，圆形，线，矩形）、上下斜坡/台阶等。遥控手柄采用更加容易持握的设计，结构符合人体工程学，手感更舒适。
```

候选6：`DOC-002-C-00043` / `B2 四足机器人`

```text
- 机器人跌倒自保护
在使用宇树 Unitree 官方自带的运动控制程序时（用遥控手柄控制机器人运动），如因外部环境原因（地面摩擦力不足等）或者用户操作不当导致机器人失稳摔倒，机器人会自行切换到自我保护状态，机器人的电机会自动切换到刹车状态以保护各部件。
```

候选7：`DOC-003-C-00001` / `B2 遥控器`

```text
B2 遥控器
使用手册 V2.1
```

候选8：`DOC-002-C-00044` / `B2 四足机器人`

```text
- App 连接异常
若采用 AP 直连模式，可检查手机是否连上 B2 发出的 Ap 热点。若热点配置失败，请确保设置的热点名称没有特殊符号和空格，确保机器狗、手机二者靠近后，重启机器狗和 App 再尝试连接。
若采用 Wi-Fi 连接模式，可检查所连接 Wi-Fi 网络是否正常，能连上外网。
```

候选9：`DOC-002-C-00033` / `B2 四足机器人`

```text
启动B2
机器人完成开机前检查，和开机前准备要求摆放好后，按照如下步骤开机：先短按电源开关一次，再长按电源开关3秒以上，即可开启电池（电池开启时，指示灯为绿灯常亮，指示灯显示当前电池电量）。电池启动后等待2分钟，机器人自动站立，机身与地面平行，即开机成功。
\- 若开机失败，请仔细检查机身摆放。
\- 大小腿靠外伸或小腿靠内被压住都可能导致B2开机失败。
\- 运动关节处小心夹手，请小心谨慎!
\- B2 开机成功后会自动站立，请保持一定的安全距离！开机后默认进去 AI 运控模式。
© 2023 宇树科技 版权所有
10
```

候选10：`DOC-002-C-00051` / `B2 四足机器人`

```text
{s}$ ，操控奔跑时请远离人群！
9. 关于足端组件：机器人足端组件是消耗品，我们会随货赠送备用足端组件。尤其在比较粗糙的地面运行时磨损会比较严重，如发现比较明显的足垫磨损、破损，或者发现机器人行走时对地面的冲击噪声明显加大，请及时更换足端组件，以免足端组件损坏导致机器人运动失常或摔损。
10. 关于 IP67 等级防护：运行前，请先确定电池接口、电池仓接口、电池表面、电池仓表面干燥无水，再将电池插入机身。下水/雨水天气作业后，请将机身表面擦拭干净。
11. 运动时禁止触碰机器人！关节处小心夹手，如膝关节处。
\- 奔跑最大速度 $6 \mathrm{~m} / \mathrm{s}$ ，在特殊配置下实现，实际为了安全会有所限速。
© 2023 宇树科技 版权所有
16
```

候选11：`DOC-002-C-00039` / `B2 四足机器人`

```text
关闭B2
关机前，请务必确保机器人站立在平整地面上，确保机器人处于静态站立状态（机器人机身位置处于开机起立后的初始状态，机身水平，手柄无任何操作，静态站立时的状态）。
\- 按2次L2+A键，机器人依次完成关节锁定，卧倒动作；
\- 机器人进入卧倒状态后，先短按电源键再长按电源键3秒以上关机。
关机后，请按照机身摆放要求，摆放好机器人大小腿和髋关节位置，为下次开机做准备。若长时间不使用B2，请及时取出电池包：往外拉出电池包提带，电池包即可弹出取下。
请确保机器人处于趴下状态（卧倒状态或阻尼状态）下进行关机，否则机器人关机掉电后会重重地摔在地上，可能会造成机身损坏，并存在一定的安全隐患！若开机失败，请检查机器人机身摆放是否正确。
\- 运动关节处小心夹手，请小心谨慎！
```

候选12：`DOC-001-C-00026` / `KIRA B 50`

```text
保养和维护
警告
在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接 
小心
只允许授权的客户服务部进行维修工作 备件安装和在电气零部件上进行工作
小心
只允许已授权的客户服务处或熟知该领域所有重要安全规定的专业人员进行设备修复工作
小心
定期清洁水位限制装置，并检查是否出现损坏
注意
在按照当地现行规定对用作商业用途的移动式设备进行安全检查时，
注意
注意是否出现短路或其它损坏 不得用软管或高压水射流清洁设备
```

**完整Final（Parent展开后的真实模型输入正文）**
Final 1：`DOC-003-C-00025` / Parent `DOC-003-P-00023` / `宇树_B2遥控器使用说明_中文版.pdf` / PDF 11–13；source_scope={"heading": "R1遥控器", "page_start": 9, "quote": "R1遥控器", "source_id": "DOC-003-C-00018"}

```text
R1 遥控器基本操作
首次使用遥控器需要在 Unitree Explore App 上进行遥控器绑定，【设置】->【遥控器设置】，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。
遥控器开机并且与 B2 连接成功后，左侧面数据传输灯全亮，这就意味着遥控器与 B2 数传模块已连接，此时可通过遥控器控制 B2。使用遥控器摇杆操控 B2 时，摇杆的操控方式如下所示：
左摇杆
右摇杆
(AI 运控模式下不支持抬头低头)
\- 摇杆回中/中位：遥控器的摇杆处于中间位置。
11
B2 遥控器使用手册
- 摇杆杆量：遥控器摇杆偏离摇杆中位的偏移量。
- 墙面、门等阻挡物会极大削弱机器狗和遥控模块之间的信号，请务必在空旷的场地操作机器狗。
© 2024 宇树科技 版权所有
机器狗参照示意图：
| 侧视图 | 俯视图 | 正视图
机器狗 |  |  | 
参照图 |  |  |
按键 | 效果
左摇杆 | 前后左右
右摇杆 | 左右旋转
姿态切换
START | 解除锁定
灵动模式(默认)
L2 (长按) + A (单击) | 站立锁定/卧倒姿态切换
L2 (长按) + B (单击) | 阻尼模式(软急停)
R1 (双击) | 经典模式
L2 (长按) + START (单击) | 跑步模式
L2 (长按) + X (单击) | 摔倒恢复站立
X (单击) | 视觉模式
SELECT | 摆姿势
L2 (双击) | 低速档
L1 (双击) | 高速档
© 2024 宇树科技 版权所有
12
B2 环境参数
最大爬坡角度 | 低速档 | < 45°
高速档 | < 30°
台阶高度 | < 25cm
越障 | < 40m
● 恢复站立安全说明：恢复站立功能需要翻身空间，机器狗周围直径 2 米圆圈内请勿有人或物品，避免不必要的人员伤亡和财产损失，否则宇树科技不承担所引发的一切损失和后果！
\- 前跳功能请访问 Unitree Explore App 触发，前跳功能视为危险动作，请开启时务必确保 B2 前方直径 2 米的半圆内没有任何障碍物（尤其不能有人）若因为非规范操作造成人员伤亡或财产损失，宇树科技不承担所引发的一切损失和后果！
```

Final 2：`DOC-003-C-00005` / Parent `DOC-003-P-00005` / `宇树_B2遥控器使用说明_中文版.pdf` / PDF 2–2；source_scope={"heading": "R3遥控器", "page_start": 2, "quote": "R3遥控器", "source_id": "DOC-003-C-00004"}

```text
简介
R3 遥控器属于 B2 遥控模块的一部分,遥控手柄内置数传模块、蓝牙模块。机器狗与遥控器可以通过 Unitree Explore App 进行绑定，绑定成功后开机即可自动连接。可操纵机器狗在站立时实现 3 轴姿态与 3 轴位置稳定全控，还可以操纵机器狗在平整地面上实现前进后退、左右侧移、原地转弯、按一定规则行走（直线，圆形，线，矩形）、上下斜坡/台阶等。遥控手柄采用更加容易持握的设计，结构符合人体工程学，手感更舒适。
```

Final 3：`DOC-003-C-00019` / Parent `DOC-003-P-00017` / `宇树_B2遥控器使用说明_中文版.pdf` / PDF 9–9；source_scope={"heading": "R1遥控器", "page_start": 9, "quote": "R1遥控器", "source_id": "DOC-003-C-00018"}

```text
简介
遥控器属于 B2 遥控模块的一部分，遥控手柄内置数传模块、蓝牙模块。机器人与遥控器可以通过 Unitree Explore App 进行绑定，绑定成功后开机即可自动连接。可操纵机器人在站立时实现 3 轴姿态与 3 轴位置稳定全控，还可以操纵机器人在平整地面上实现前进后退、左右侧移、原地转弯、按一定规则行走（直线，圆形，线，矩形）、上下斜坡/台阶等。遥控手柄采用更加容易持握的设计，结构符合人体工程学，手感更舒适。
```

Final 4：`DOC-003-C-00001` / Parent `DOC-003-P-00001` / `宇树_B2遥控器使用说明_中文版.pdf` / PDF 1–1；source_scope=null

```text
B2 遥控器
使用手册 V2.1
```

**本题规范原文与元数据（Corpus完整Child）**
`DOC-003-C-00015`；B2 遥控器；PDF 6–7；version=None

```text
R3 遥控器基本操作
首次使用遥控器需要在 Unitree Explore App 上进行遥控器绑定，【设置】->【遥控器设置】-打开遥控器开关，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。
遥控器开机并且与 B2 连接成功后，右侧 DL 指示灯亮，这就意味着遥控器与 B2 数传模块已连接，此时可通过遥控器控制 B2。使用遥控器摇杆操控 B2 时，摇杆的操控方式如下所示：
左摇杆
右摇杆
(AI 运控模式下不支持抬头低头)
- 摇杆回中/中位：遥控器的摇杆处于中间位置。
- 摇杆杆量：遥控器摇杆偏离摇杆中位的偏移量。
- 墙面、门等阻挡物会极大削弱机器狗和遥控模块之间的信号，请务必在空旷的场地操作机器狗。
© 2024 宇树科技 版权所有
6
机器狗参照示意图：
| 侧视图 | 俯视图 | 正视图
机器狗 |  |  | 
参照图 |  |  |
按键 | 效果
左摇杆 | 前后左右
右摇杆 | 左右旋转
姿态切换
START | 解除锁定
灵动模式(默认)
L2 (长按) + A (单击) | 站立锁定/卧倒姿态切换
L2 (长按) + B (单击) | 阻尼模式(软急停)
R1 (双击) | 经
```

`DOC-003-C-00025`；B2 遥控器；PDF 11–12；version=None

```text
R1 遥控器基本操作
首次使用遥控器需要在 Unitree Explore App 上进行遥控器绑定，【设置】->【遥控器设置】，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。
遥控器开机并且与 B2 连接成功后，左侧面数据传输灯全亮，这就意味着遥控器与 B2 数传模块已连接，此时可通过遥控器控制 B2。使用遥控器摇杆操控 B2 时，摇杆的操控方式如下所示：
左摇杆
右摇杆
(AI 运控模式下不支持抬头低头)
\- 摇杆回中/中位：遥控器的摇杆处于中间位置。
11
B2 遥控器使用手册
- 摇杆杆量：遥控器摇杆偏离摇杆中位的偏移量。
- 墙面、门等阻挡物会极大削弱机器狗和遥控模块之间的信号，请务必在空旷的场地操作机器狗。
© 2024 宇树科技 版权所有
机器狗参照示意图：
| 侧视图 | 俯视图 | 正视图
机器狗 |  |  | 
参照图 |  |  |
按键 | 效果
左摇杆 | 前后左右
右摇杆 | 左右旋转
姿态切换
START | 解除锁定
灵动模式(默认)
L2 (长按) + A (单击) | 站立锁定/卧倒姿态切换
L2 (长按) + B (单击) | 阻尼模式(软急停)
R1 (双
```

</details>

## Q24 — FAIL合理；无须坚持所有词面缺失都成立，三类明确遗漏已足以失败。

真实题号：`V1G-110926448917-24`；类别：`ablation`。

### 1. 冻结Golden与实际回答

**问题（完整）**

```text
哎，操作员准备往 KIRA B 50 里加清洁剂跑一遍，怕乱用出问题。手册里对使用清洁剂运行这块的一般安全提示是怎么说的？
```

**冻结参考答案（完整，保留原始文字）**

```text
洗涤剂应远离孩童妥善保管
不得未稀释使用推荐的洗涤剂
洗涤剂若是不小心溅入眼睛，必须立即用水彻底冲洗并且若不慎吞咽则应立即就医
仅使用制造商推荐的清洁剂，并遵守清洁剂制造商的使用 处置和警告说明
小心
损坏危险
仅限使用推荐的清洁剂
如果使用其他清洁剂，您要自 己承担有关操作安全 事故风险和设备使用寿命缩短的风险
仅限使用不含稀释剂 盐酸和氢氟酸成分的清洁剂
遵守清洁剂上的安全提示
提示
请勿使用强发泡型清洁剂
请遵守计量提示
```

**冻结Golden evidence字段（原样；摘要不能冒充完整规范）**

```json
[
  {
    "evidence_key_points": [
      "使用清洁剂运行\n小心\n洗涤剂应远离孩童妥善保管\n小心\n不得未稀释使用推荐的洗涤剂 该产品可以安全使用，因为其不含酸性 碱性或污染环境的材料 洗涤剂若是不小心溅入眼睛，必须立即用水彻底冲洗并且若不慎吞咽则应立即就医\n小心\n仅使用制造商推荐的清洁剂，并遵守清洁剂制造商的使用 处置和警告说明",
      "清洁剂\n小心\n损坏危险\n仅限使用推荐的清洁剂 如果使用其他清洁剂，您要自 己承担有关操作安全 事故风险和设备使用寿命缩短的风险 仅限使用不含稀释剂 盐酸和氢氟酸成分的清洁剂 遵守清洁剂上的安全提示\n提示\n请勿使用强发泡型清洁剂\n请遵守计量提示\n\n推荐的清洁剂：\n适用范围=所有防水地板的保养清洁；清洁剂=CA 50 C"
    ],
    "source_chunk_ids": [
      "DOC-001-C-00022",
      "DOC-001-C-00118"
    ]
  }
]
```

**RAG实际回答（完整）**

```text
手册对 KIRA B 50 使用清洁剂运行的一般安全提示是：

- **仅限使用推荐的清洁剂**；使用其他清洁剂时，操作安全、事故风险和设备使用寿命缩短的风险由使用者自行承担。[DOC-001-C-00118 | S1 | 清洁剂 | 页41–42]
- 清洁剂**不得含稀释剂、盐酸和氢氟酸成分**。[DOC-001-C-00118 | S1 | 清洁剂 | 页41–42]
- 必须**遵守清洁剂包装上的安全提示**。[DOC-001-C-00118 | S1 | 清洁剂 | 页41–42]
- **不要使用强发泡型清洁剂**。[DOC-001-C-00118 | S1 | 清洁剂 | 页41–42]
- 必须**遵守计量提示**。[DOC-001-C-00118 | S1 | 清洁剂 | 页41–42]
- 清洁设备维护时另有提示：**不得使用腐蚀性清洁剂**；该条来自维护间隔章节，不要与运行加注清洁剂混淆。[DOC-001-C-00182 | S1 | 维护间隔 | 页85–86]

因此，加注前应先核对：是否为手册推荐清洁剂、是否不含上述禁用成分、是否非强发泡，并按清洁剂安全提示和计量要求操作；不在推荐范围内的清洁剂不能视为安全可用。
```

### 2. 独立原文、范围与等价证据判断

C00022（PDF9）给孩童保管、必须稀释、溅眼冲洗/吞咽就医和制造商说明；C00118（PDF41–42）给推荐/成分/发泡/计量。后者和回答已有安全提示、计量对“制造商使用/警告”有等价重叠，Judge checks[8]的全缺表述偏强；但不能覆盖孩童、急救与未稀释禁令，FAIL仍成立。不能把“无稀释剂成分”和“须稀释洗涤剂”混为矛盾。

**必要事实逐项链路**

| 必要事实/安全条件 | Corpus原文定位 | Candidate序号 | Rerank序号 | Final条目序号 | Answer与等价范围核查 |
|---|---|---|---|---|---|
| 远离孩童保管洗涤剂 | DOC-001-C-00022 / PDF 9–9 | 无 | 无 | 无 | 遗漏 |
| 不得未稀释使用推荐洗涤剂 | DOC-001-C-00022 / PDF 9–9 | 无 | 无 | 无 | 遗漏；遵守计量不直接表达必须稀释 |
| 溅眼立即用水彻底冲洗 | DOC-001-C-00022 / PDF 9–9 | 无 | 无 | 无 | 遗漏 |
| 不慎吞咽立即就医 | DOC-001-C-00022 / PDF 9–9 | 无 | 无 | 无 | 遗漏 |
| 遵守制造商使用/处置/警告说明 | DOC-001-C-00022 / PDF 9–9 | 无 | 无 | 无 | 部分：包装安全提示与计量有等价重叠，处置范围未明确，不将整项机械判全无 |
| 仅推荐清洁剂，其他清洁剂风险自担 | DOC-001-C-00118 / PDF 41–42 | 4 | 1 | 1 | 已表达 |
| 不含稀释剂/盐酸/氢氟酸 | DOC-001-C-00118 / PDF 41–42 | 4 | 1 | 1 | 已表达，方向正确；“不得未稀释”不是“含稀释剂”许可 |
| 遵守清洁剂安全提示 | DOC-001-C-00118 / PDF 41–42 | 4 | 1 | 1 | 已表达 |
| 不使用强发泡型 | DOC-001-C-00118 / PDF 41–42 | 4 | 1 | 1 | 已表达 |
| 遵守计量提示 | DOC-001-C-00118 / PDF 41–42 | 4 | 1 | 1 | 已表达 |

### 3. 失败归因、实际程序条件与可优化性

**独立归因：** 人工证据支持Retrieval：C00022与等价儿童/稀释/急救事实未入候选或Final。Final里的手动模式计量设置不提供这些安全前提。

**当前程序的确定路径：** checks[5]至[9] scope=true、support=[]、reference均在Corpus定位，但candidate_support键完全缺失，328行list判断失败；issue support=[]且无reference，334行失败。Guard只检查禁成分方向，本题该方向正确，Guard无finding；latency=4904，不走性能兜底。不是scope不足。

**工具箱与可验证假设：** 确认候选无等价事实后，现有candidate_recall/query_expansion可测试扩大池或问题表达；不承诺candidate_k=24一定有效。仅修改prompt_strategy不能使Final凭空包含急救条款。

**建议处理：** 保留FAIL；将Judge对制造商说明的重复/等价覆盖争议另列审计，不因这一个子项争议推翻其他明确遗漏。

**完整只读诊断输出（省去耗时明细，仅保留准入与证据）**

```json
{
  "primary_root_cause": "Unknown",
  "target_eligible": false,
  "is_technical_bad_case": false,
  "retrieval_failure_stage": null,
  "trace_observations": [],
  "optimization_directions": [],
  "evidence_checks": []
}
```

### 4. Judge原始判定与检查（未改写）

保存业务verdict=FAIL；原始Judge verdict=FAIL。
<details><summary>完整原始Provider JSON（含所有checks、issues、support与reason）</summary>

```json
{"verdict":"FAIL","checks":[{"check_type":"fact","requirement":"仅使用制造商推荐的清洁剂；若使用其他清洁剂，操作安全、事故风险和设备寿命缩短风险由使用者承担。","met":true,"answer_quotes":["- **仅限使用推荐的清洁剂**；使用其他清洁剂时，操作安全、事故风险和设备使用寿命缩短的风险由使用者自行承担。[DOC-001-C-00118 | S1 | 清洁剂 | 页41–42]"],"support":[{"source_id":"DOC-001-C-00118","quote":"仅限使用推荐的清洁剂"},{"source_id":"DOC-001-C-00118","quote":"如果使用其他清洁剂，您要自 己承担有关操作安全 事故风险和设备使用寿命缩短的风险"}],"scope_resolved":true},{"check_type":"fact","requirement":"仅限使用不含稀释剂、盐酸和氢氟酸成分的清洁剂。","met":true,"answer_quotes":["- 清洁剂**不得含稀释剂、盐酸和氢氟酸成分**。[DOC-001-C-00118 | S1 | 清洁剂 | 页41–42]"],"support":[{"source_id":"DOC-001-C-00118","quote":"仅限使用不含稀释剂 盐酸和氢氟酸成分的清洁剂"}],"scope_resolved":true},{"check_type":"fact","requirement":"遵守清洁剂上的安全提示。","met":true,"answer_quotes":["- 必须**遵守清洁剂包装上的安全提示**。[DOC-001-C-00118 | S1 | 清洁剂 | 页41–42]"],"support":[{"source_id":"DOC-001-C-00118","quote":"遵守清洁剂上的安全提示"}],"scope_resolved":true},{"check_type":"fact","requirement":"请勿使用强发泡型清洁剂。","met":true,"answer_quotes":["- **不要使用强发泡型清洁剂**。[DOC-001-C-00118 | S1 | 清洁剂 | 页41–42]"],"support":[{"source_id":"DOC-001-C-00118","quote":"请勿使用强发泡型清洁剂"}],"scope_resolved":true},{"check_type":"fact","requirement":"遵守清洁剂计量提示。","met":true,"answer_quotes":["- 必须**遵守计量提示**。[DOC-001-C-00118 | S1 | 清洁剂 | 页41–42]"],"support":[{"source_id":"DOC-001-C-00118","quote":"请遵守计量提示"}],"scope_resolved":true},{"check_type":"fact","requirement":"洗涤剂应远离孩童妥善保管。","met":false,"answer_quotes":[],"support":[],"reference_support":[{"source_id":"DOC-001-C-00022","quote":"洗涤剂应远离孩童妥善保管"}],"scope_resolved":true},{"check_type":"fact","requirement":"不得未稀释使用推荐的洗涤剂。","met":false,"answer_quotes":[],"support":[],"reference_support":[{"source_id":"DOC-001-C-00022","quote":"不得未稀释使用推荐的洗涤剂"}],"scope_resolved":true},{"check_type":"fact","requirement":"洗涤剂若溅入眼睛必须立即用水彻底冲洗；若不慎吞咽应立即就医。","met":false,"answer_quotes":[],"support":[],"reference_support":[{"source_id":"DOC-001-C-00022","quote":"洗涤剂若是不小心溅入眼睛，必须立即用水彻底冲洗并且若不慎吞咽则应立即就医"}],"scope_resolved":true},{"check_type":"fact","requirement":"遵守清洁剂制造商的使用、处置和警告说明。","met":false,"answer_quotes":["- 必须**遵守清洁剂包装上的安全提示**。[DOC-001-C-00118 | S1 | 清洁剂 | 页41–42]"],"support":[],"reference_support":[{"source_id":"DOC-001-C-00022","quote":"仅使用制造商推荐的清洁剂，并遵守清洁剂制造商的使用 处置和警告说明"}],"scope_resolved":true},{"check_type":"fact","requirement":"面向 KIRA B 50 当前加注清洁剂并运行的计划：已提示核对推荐清洁剂、禁用成分、非强发泡和计量；尚缺“不得未稀释使用推荐洗涤剂”这一必要使用前提，因此未完整确认当前操作适用条件，不应视为已完整放行。","met":false,"answer_quotes":["因此，加注前应先核对：是否为手册推荐清洁剂、是否不含上述禁用成分、是否非强发泡，并按清洁剂安全提示和计量要求操作；不在推荐范围内的清洁剂不能视为安全可用。"],"support":[],"reference_support":[{"source_id":"DOC-001-C-00022","quote":"不得未稀释使用推荐的洗涤剂"}],"scope_resolved":true}],"issues":[{"description":"回答只覆盖了“清洁剂”章节的推荐清洁剂、禁用成分、包装安全提示、强发泡和计量要求，遗漏“使用清洁剂运行”章节的洗涤剂远离孩童、不得未稀释使用推荐洗涤剂、眼睛溅入立即彻底冲洗、吞咽立即就医，以及遵守清洁剂制造商的使用/处置/警告说明；因此当前加注/运行场景的未稀释使用前提也未完整保留，必要安全事实不完整。","answer_quotes":["因此，加注前应先核对：是否为手册推荐清洁剂、是否不含上述禁用成分、是否非强发泡，并按清洁剂安全提示和计量要求操作；不在推荐范围内的清洁剂不能视为安全可用。"],"support":[],"critical":true,"safety_violation":false,"scope_resolved":true,"baseline_issue_index":null}],"reason":"回答正确覆盖了“清洁剂”章节的推荐清洁剂、禁用成分、安全提示、强发泡和计量要求，并正确提示加注前核对且未授权未知清洁剂；但遗漏“使用清洁剂运行”章节的孩童保管、不得未稀释、眼睛冲洗/吞咽就医及遵守制造商使用处置警告说明，导致必要安全事实不完整；当前加注/运行场景也因此缺少未稀释使用前提，故判 FAIL。","quality":{"correctness":3,"faithfulness":1.0,"completeness":0.55}}
```

</details>

### 5. 可复查的完整阶段证据

<details><summary>各阶段来源顺序、完整候选正文、完整Final与规范原文</summary>

**候选→重排→Final顺序**

```json
{
  "candidates": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00182",
      "parent_chunk_id": "DOC-001-P-00180",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.9677
    },
    {
      "position": 2,
      "chunk_id": "DOC-001-C-00140",
      "parent_chunk_id": "DOC-001-P-00139",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.9273
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00217",
      "parent_chunk_id": "DOC-001-P-00215",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00118",
      "parent_chunk_id": "DOC-001-P-00117",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4909
    },
    {
      "position": 5,
      "chunk_id": "DOC-001-C-00146",
      "parent_chunk_id": "DOC-001-P-00145",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4887
    },
    {
      "position": 6,
      "chunk_id": "DOC-001-C-00110",
      "parent_chunk_id": "DOC-001-P-00109",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.487
    },
    {
      "position": 7,
      "chunk_id": "DOC-001-C-00119",
      "parent_chunk_id": "DOC-001-P-00118",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4791
    },
    {
      "position": 8,
      "chunk_id": "DOC-001-C-00002",
      "parent_chunk_id": "DOC-001-P-00002",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4749
    },
    {
      "position": 9,
      "chunk_id": "DOC-001-C-00147",
      "parent_chunk_id": "DOC-001-P-00145",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4732
    },
    {
      "position": 10,
      "chunk_id": "DOC-001-C-00026",
      "parent_chunk_id": "DOC-001-P-00026",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4713
    },
    {
      "position": 11,
      "chunk_id": "DOC-002-C-00053",
      "parent_chunk_id": "DOC-002-P-00045",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4661
    },
    {
      "position": 12,
      "chunk_id": "DOC-001-C-00103",
      "parent_chunk_id": "DOC-001-P-00102",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.466
    }
  ],
  "reranked": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00118",
      "parent_chunk_id": "DOC-001-P-00117",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7943112408143115,
      "rerank_score": 0.7943112408143115
    },
    {
      "position": 2,
      "chunk_id": "DOC-001-C-00182",
      "parent_chunk_id": "DOC-001-P-00180",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.6774485681151827,
      "rerank_score": 0.6774485681151827
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00140",
      "parent_chunk_id": "DOC-001-P-00139",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.615963635964577,
      "rerank_score": 0.615963635964577
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00119",
      "parent_chunk_id": "DOC-001-P-00118",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5519758863606185,
      "rerank_score": 0.5519758863606185
    },
    {
      "position": 5,
      "chunk_id": "DOC-001-C-00002",
      "parent_chunk_id": "DOC-001-P-00002",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5307420324685584,
      "rerank_score": 0.5307420324685584
    },
    {
      "position": 6,
      "chunk_id": "DOC-002-C-00053",
      "parent_chunk_id": "DOC-002-P-00045",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.5125215004496169,
      "rerank_score": 0.5125215004496169
    },
    {
      "position": 7,
      "chunk_id": "DOC-001-C-00026",
      "parent_chunk_id": "DOC-001-P-00026",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4868166885866092,
      "rerank_score": 0.4868166885866092
    },
    {
      "position": 8,
      "chunk_id": "DOC-001-C-00147",
      "parent_chunk_id": "DOC-001-P-00145",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.46787244324749155,
      "rerank_score": 0.46787244324749155
    },
    {
      "position": 9,
      "chunk_id": "DOC-001-C-00110",
      "parent_chunk_id": "DOC-001-P-00109",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.3757697565480602,
      "rerank_score": 0.3757697565480602
    },
    {
      "position": 10,
      "chunk_id": "DOC-001-C-00103",
      "parent_chunk_id": "DOC-001-P-00102",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.3717349647988536,
      "rerank_score": 0.3717349647988536
    },
    {
      "position": 11,
      "chunk_id": "DOC-001-C-00146",
      "parent_chunk_id": "DOC-001-P-00145",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.3688339271213999,
      "rerank_score": 0.3688339271213999
    },
    {
      "position": 12,
      "chunk_id": "DOC-001-C-00217",
      "parent_chunk_id": "DOC-001-P-00215",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.2819212024530413,
      "rerank_score": 0.2819212024530413
    }
  ],
  "final": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00118",
      "parent_chunk_id": "DOC-001-P-00117",
      "matched_child_ids": [
        "DOC-001-C-00118"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7943112408143115,
      "rerank_score": 0.7943112408143115
    },
    {
      "position": 2,
      "chunk_id": "DOC-001-C-00182",
      "parent_chunk_id": "DOC-001-P-00180",
      "matched_child_ids": [
        "DOC-001-C-00182"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.6774485681151827,
      "rerank_score": 0.6774485681151827
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00140",
      "parent_chunk_id": "DOC-001-P-00139",
      "matched_child_ids": [
        "DOC-001-C-00140"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.615963635964577,
      "rerank_score": 0.615963635964577
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00119",
      "parent_chunk_id": "DOC-001-P-00118",
      "matched_child_ids": [
        "DOC-001-C-00119"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5519758863606185,
      "rerank_score": 0.5519758863606185
    }
  ]
}
```

**全部候选正文（用于核查等价来源，而非只看ID）**
候选1：`DOC-001-C-00182` / `KIRA B 50`

```text
维护间隔

注意
损坏危险
不得用水喷射本设备 不得使用腐蚀性清洁剂
提示：如果有一个对接站，则会自动执行标有“##”的维护工作
```

候选2：`DOC-001-C-00140` / `KIRA B 50`

```text
手动模式
在手动运行的过程中，由操作人员在待清洁的场地上引导该设备
1. 在触摸屏上选择功能“手动清洁”
1 隐藏/显示菜单项“刷子功率和抽吸功率”2 电池充电状态3 清洁剂计量4 抽吸功率5 刷子功率

6 返回功能选择7 水量8 激活/停用边刷9 激活/停用清洁头10 激活/停用抽吸装置11 清水箱液位
2. 操作并握紧安全开关3. 将设备推到使用地4. 松开安全开关
5. 选择水量 清洁剂计量 刷子功率和抽吸功率的所需设置
6. 激活所需功能（抽吸 清洁头 边刷）已激活的功能用绿色标记。
```

候选3：`DOC-001-C-00217` / `KIRA B 50`

```text
定位问题
原因：
排除故障：
1. 操作员取消了运行的自主任务
```

候选4：`DOC-001-C-00118` / `KIRA B 50`

```text
清洁剂
小心
损坏危险
仅限使用推荐的清洁剂 如果使用其他清洁剂，您要自 己承担有关操作安全 事故风险和设备使用寿命缩短的风险 仅限使用不含稀释剂 盐酸和氢氟酸成分的清洁剂 遵守清洁剂上的安全提示
提示
请勿使用强发泡型清洁剂
请遵守计量提示

推荐的清洁剂：
适用范围=所有防水地板的保养清洁；清洁剂=CA 50 CRM 756
适用范围=保养清洁与护理组件；清洁剂=RM 746RM 780
适用范围=工业地板的保养清洁和彻底清洁；清洁剂=RM 69
适用范围=光面地板的保养清洁；清洁剂=RM 755
适用范围=精细陶瓷瓷砖的保养清洁和彻底清洁；清洁剂=RM 753
适用范围=耐酸地板的保养清洁和彻底清洁；清洁剂=RM 751
适用范围=清洁和消毒；清洁剂=RM 732
适用范围=耐碱地板铺层的彻底清洁；清洁剂=RM 752
适用范围=不耐碱地板的彻底清洁和除垢层；清洁剂=RM 754
1 清洁剂加注口
填充口盖子
3 清洁剂液位指示器
2. 注入清洁剂

```

候选5：`DOC-001-C-00146` / `KIRA B 50`

```text
示教路线
在这里对示教过程进行说明 设置指南中包含了有关优化设计路线的提示
在示教过程中，会保存有关路线的以下信息：
设备的行车路径
打开或关闭清洁功能的点位
水输入量 清洁剂计量 刷子转速和抽吸功率的参数设置
喇叭的操作（例如在十字路口）
不记录：
示教过程中的短暂停顿（少于 5 分钟）
示教过程中的行驶速度
1. 以“主管”身份登录
2. 选择“自动”功能
3. 选择“新路线”功能
4. 确认
a. 蓄电池已充满电

b. 清水箱已满
c. 污水箱已空<sub>。</sub>
或退出菜单，并创建所要求的前提条件。
5. 操作安全开关，将设备推到起点的 位置码 前方
a. 将对接端口与 位置码 对准
b. 与 位置码 保持大约 2 m 的距离<sub>。</sub>
6. 请等待，直到设备识别到 位置码
1 隐藏/显示菜单项“刷子功率和抽吸功率”2 保存路线3 中断示教4 清洁剂计量5 抽吸功率

6 设备位置7 刷子功率8 水量9 实时地图10 退出示教11 激活/停用边刷12 激活/停用清洁头13 激活/停用抽吸装置14 喇叭
8
```

候选6：`DOC-001-C-00110` / `KIRA B 50`

```text
提示
如果无法再正常重启系统，可以利用 RESET 按钮将系统与电源完全断开，并重新启动
1. 取下盖板2. 卸下清洁剂罐现在系统已完全断开电源。

3. 长按 RESET 按钮大约 10 秒
4. 按下开机按钮启动设备现在系统正在启动。
5. 重新装入清洁剂罐
6. 重新装上盖板
```

候选7：`DOC-001-C-00119` / `KIRA B 50`

```text
提示：
为了快速更换清洁剂，可以取下清洁剂罐，并换上另一个清洁剂罐
```

候选8：`DOC-001-C-00002` / `KIRA B 50`

```text
KIRA B 50
KIRA B 50
ZH

```

候选9：`DOC-001-C-00147` / `KIRA B 50`

```text
抽吸功率”2 保存路线3 中断示教4 清洁剂计量5 抽吸功率

6 设备位置7 刷子功率8 水量9 实时地图10 退出示教11 激活/停用边刷12 激活/停用清洁头13 激活/停用抽吸装置14 喇叭
8. 选择水量 清洁剂计量 刷子功率和抽吸功率的所需设置
9. 激活所需功能（抽吸 清洁头 边刷）已激活的功能用绿色标记。
```

候选10：`DOC-001-C-00026` / `KIRA B 50`

```text
保养和维护
警告
在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接 
小心
只允许授权的客户服务部进行维修工作 备件安装和在电气零部件上进行工作
小心
只允许已授权的客户服务处或熟知该领域所有重要安全规定的专业人员进行设备修复工作
小心
定期清洁水位限制装置，并检查是否出现损坏
注意
在按照当地现行规定对用作商业用途的移动式设备进行安全检查时，
注意
注意是否出现短路或其它损坏 不得用软管或高压水射流清洁设备
```

候选11：`DOC-002-C-00053` / `B2 四足机器人`

```text
整机清洁
```

候选12：`DOC-001-C-00103` / `KIRA B 50`

```text
背面

1 环照灯 2 紧急停机按钮 3 清洁剂罐手柄 4 清洁剂罐密封盖 5 清洁剂液位指示器 6 清洁剂罐盖子 7 侧刷 8 清洁头削刮胶条 9 吸水扒 10 抽吸软管
```

**完整Final（Parent展开后的真实模型输入正文）**
Final 1：`DOC-001-C-00118` / Parent `DOC-001-P-00117` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 41–42；source_scope=null

```text
清洁剂
小心
损坏危险
仅限使用推荐的清洁剂 如果使用其他清洁剂，您要自 己承担有关操作安全 事故风险和设备使用寿命缩短的风险 仅限使用不含稀释剂 盐酸和氢氟酸成分的清洁剂 遵守清洁剂上的安全提示
提示
请勿使用强发泡型清洁剂
请遵守计量提示

推荐的清洁剂：
适用范围=所有防水地板的保养清洁；清洁剂=CA 50 CRM 756
适用范围=保养清洁与护理组件；清洁剂=RM 746RM 780
适用范围=工业地板的保养清洁和彻底清洁；清洁剂=RM 69
适用范围=光面地板的保养清洁；清洁剂=RM 755
适用范围=精细陶瓷瓷砖的保养清洁和彻底清洁；清洁剂=RM 753
适用范围=耐酸地板的保养清洁和彻底清洁；清洁剂=RM 751
适用范围=清洁和消毒；清洁剂=RM 732
适用范围=耐碱地板铺层的彻底清洁；清洁剂=RM 752
适用范围=不耐碱地板的彻底清洁和除垢层；清洁剂=RM 754
1 清洁剂加注口
填充口盖子
3 清洁剂液位指示器
2. 注入清洁剂

```

Final 2：`DOC-001-C-00182` / Parent `DOC-001-P-00180` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 85–86；source_scope=null

```text
维护间隔

注意
损坏危险
不得用水喷射本设备 不得使用腐蚀性清洁剂
提示：如果有一个对接站，则会自动执行标有“##”的维护工作
```

Final 3：`DOC-001-C-00140` / Parent `DOC-001-P-00139` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 57–58；source_scope=null

```text
手动模式
在手动运行的过程中，由操作人员在待清洁的场地上引导该设备
1. 在触摸屏上选择功能“手动清洁”
1 隐藏/显示菜单项“刷子功率和抽吸功率”2 电池充电状态3 清洁剂计量4 抽吸功率5 刷子功率

6 返回功能选择7 水量8 激活/停用边刷9 激活/停用清洁头10 激活/停用抽吸装置11 清水箱液位
2. 操作并握紧安全开关3. 将设备推到使用地4. 松开安全开关
5. 选择水量 清洁剂计量 刷子功率和抽吸功率的所需设置
6. 激活所需功能（抽吸 清洁头 边刷）已激活的功能用绿色标记。
```

Final 4：`DOC-001-C-00119` / Parent `DOC-001-P-00118` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 43–43；source_scope=null

```text
提示：
为了快速更换清洁剂，可以取下清洁剂罐，并换上另一个清洁剂罐
```

**本题规范原文与元数据（Corpus完整Child）**
`DOC-001-C-00022`；KIRA B 50；PDF 9–9；version=None

```text
使用清洁剂运行
小心
洗涤剂应远离孩童妥善保管
小心
不得未稀释使用推荐的洗涤剂 该产品可以安全使用，因为其不含酸性 碱性或污染环境的材料 洗涤剂若是不小心溅入眼睛，必须立即用水彻底冲洗并且若不慎吞咽则应立即就医
小心
仅使用制造商推荐的清洁剂，并遵守清洁剂制造商的使用 处置和警告说明
```

`DOC-001-C-00118`；KIRA B 50；PDF 41–42；version=None

```text
清洁剂
小心
损坏危险
仅限使用推荐的清洁剂 如果使用其他清洁剂，您要自 己承担有关操作安全 事故风险和设备使用寿命缩短的风险 仅限使用不含稀释剂 盐酸和氢氟酸成分的清洁剂 遵守清洁剂上的安全提示
提示
请勿使用强发泡型清洁剂
请遵守计量提示

推荐的清洁剂：
适用范围=所有防水地板的保养清洁；清洁剂=CA 50 CRM 756
适用范围=保养清洁与护理组件；清洁剂=RM 746RM 780
适用范围=工业地板的保养清洁和彻底清洁；清洁剂=RM 69
适用范围=光面地板的保养清洁；清洁剂=RM 755
适用范围=精细陶瓷瓷砖的保养清洁和彻底清洁；清洁剂=RM 753
适用范围=耐酸地板的保养清洁和彻底清洁；清洁剂=RM 751
适用范围=清洁和消毒；清洁剂=RM 732
适用范围=耐碱地板铺层的彻底清洁；清洁剂=RM 752
适用范围=不耐碱地板的彻底清洁和除垢层；清洁剂=RM 754
1 清洁剂加注口
填充口盖子
3 清洁剂液位指示器
2. 注入清洁剂

```

</details>

## Q27 — FAIL合理；漏答地图变化核心规则，且把重摆桌椅等同大量桌椅区域。

真实题号：`V1G-110926448917-27-R123429216749`；类别：`ablation`。

### 1. 冻结Golden与实际回答

**问题（完整）**

```text
这层楼昨晚重新摆了桌椅，KIRA B50再自己清洁前，这种变化要怎么处理？
```

**冻结参考答案（完整，保留原始文字）**

```text
不，地图不具备自学习功能
对原始布局进行细微改动不成问题
对布局的改动越大，则设备的效率就越低
如果布局发生了重大变化，则必须重新示教该路线
```

**冻结Golden evidence字段（原样；摘要不能冒充完整规范）**

```json
[
  {
    "evidence_key_points": [
      "地图是否具备自学习功能，并补充新障碍物？\n不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线"
    ],
    "source_chunk_ids": [
      "DOC-001-C-00096"
    ]
  }
]
```

**RAG实际回答（完整）**

```text
先不要直接让 KIRA B 50 进入该区域自主清洁。按说明书要求处理：

1. **把重新摆过桌椅的区域按“大量桌椅区域”处理**：应避免设备进入，改为**手动清洁这些区域**。[DOC-001-C-00085 | S1 | 页26–27]
2. **如需进行示教/路径设置**：应在**正常营业时间之外**进行，或**封锁相应子区域**后再做。[DOC-001-C-00085 | S1 | 页26–27]
3. 同时确认该区域内没有会妨碍 Smart Fill 覆盖的**低于 15 cm 的扁平物体**。[DOC-001-C-00085 | S1 | 页26–27]

可执行做法：**先封锁或手动清洁重新摆桌椅的区域，暂停该区域自主清洁；在非营业时间或封锁状态下按官方流程进行示教/路径处理。**

未确认条件：给定证据没有提供 KIRA B 50 重新示教、地图更新或路径修改的具体操作步骤，因此不能据此给出具体按键/界面操作；需查阅对应版本的官方操作说明或联系官方支持。
```

### 2. 独立原文、范围与等价证据判断

C00096（PDF28）四条明确对应问题，已入候选；Final C00085只规定“大量桌椅区域”与示教时间条件。用户未说数量多或变化重大，回答应分条件解释而非直接改手动。无须假定用户已经重大变化来成立FAIL，因为规则本身未被交代。

**必要事实逐项链路**

| 必要事实/安全条件 | Corpus原文定位 | Candidate序号 | Rerank序号 | Final条目序号 | Answer与等价范围核查 |
|---|---|---|---|---|---|
| 地图不具备自学习功能 | DOC-001-C-00096 / PDF 28–28 | 7 | 12 | 无 | 遗漏 |
| 细微布局改动不成问题 | DOC-001-C-00096 / PDF 28–28 | 7 | 12 | 无 | 遗漏；直接暂停自主清洁过度泛化 |
| 改动越大效率越低 | DOC-001-C-00096 / PDF 28–28 | 7 | 12 | 无 | 遗漏 |
| 重大布局变化必须重新示教路线 | DOC-001-C-00096 / PDF 28–28 | 7 | 12 | 无 | 遗漏；“如需示教”没有保留重大变化的强制条件 |
| 大量桌椅区域需避开并手动清洁的条件范围 | DOC-001-C-00085 / PDF 26–27 | 1 | 3 | 3 | 原文已入Final，但“重新摆桌椅”不证明数量多；回答擅自套用，不是字符串不匹配 |

### 3. 失败归因、实际程序条件与可优化性

**独立归因：** 主要Ranking（必要地图事实候选7→rerank12→Top4排除）；另有C00085适用条件被生成扩大，属于独立Generation/范围错误观察，不是Safety已证实违规。

**当前程序的确定路径：** checks[0]至[3] scope=true、有有效reference/candidate、Final空，命中328–331形成Ranking；check[4]虽有Final支持但scope=false被325跳过。issue关于C00096的support仅在候选定位、无issue.reference_support，不被334收下；关于大量桌椅的issue scope=false被333跳过。故只有ranking_omission/context_selection。

**工具箱与可验证假设：** 当前允许的top_k={4,6}、rerank={true,false}、min_score={0,.1,.2,.3}共16种固定池选择均无法纳入C00096（有rerank时第12，无rerank时第7）。提高min_score不能让低排条款越过高排条款。query/candidate/source_filter方向当前没有相应观察，不能合法借道。现有工具箱没有已由本次Trace证明能恢复核心规范的合法策略。

**建议处理：** 保留FAIL及Ranking，但不要因target_eligible=true就承诺能产出有效候选。缺的是能把相关规范重排到预算内的能力或更大合法上下文预算；修改Search Space/重排策略需Owner另行决定，不加第二Agent、不硬编码Q号。

**完整只读诊断输出（省去耗时明细，仅保留准入与证据）**

```json
{
  "primary_root_cause": "Ranking",
  "target_eligible": true,
  "is_technical_bad_case": true,
  "retrieval_failure_stage": "ranking_context_selection",
  "trace_observations": [
    "ranking_omission"
  ],
  "optimization_directions": [
    "context_selection"
  ],
  "evidence_checks": [
    {
      "answer_quotes": [],
      "candidate_support": [
        {
          "quote": "不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线",
          "source_id": "DOC-001-C-00096"
        }
      ],
      "check_type": "fact",
      "met": false,
      "reference_support": [
        {
          "quote": "不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线",
          "source_id": "DOC-001-C-00096"
        }
      ],
      "requirement": "应说明 KIRA B50 的地图不具备自学习功能，不会自动补充新障碍物或自动适应重新摆桌椅后的布局。",
      "scope_resolved": true,
      "support": [],
      "candidate_missing": false
    },
    {
      "answer_quotes": [
        "先不要直接让 KIRA B 50 进入该区域自主清洁。"
      ],
      "candidate_support": [
        {
          "quote": "不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线",
          "source_id": "DOC-001-C-00096"
        }
      ],
      "check_type": "fact",
      "met": false,
      "reference_support": [
        {
          "quote": "不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线",
          "source_id": "DOC-001-C-00096"
        }
      ],
      "requirement": "应说明对原始布局的细微改动不成问题，不需要因轻微重新摆桌椅而直接停止自主清洁。",
      "scope_resolved": true,
      "support": [],
      "candidate_missing": false
    },
    {
      "answer_quotes": [],
      "candidate_support": [
        {
          "quote": "不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线",
          "source_id": "DOC-001-C-00096"
        }
      ],
      "check_type": "fact",
      "met": false,
      "reference_support": [
        {
          "quote": "不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线",
          "source_id": "DOC-001-C-00096"
        }
      ],
      "requirement": "应说明布局改动越大，设备效率越低。",
      "scope_resolved": true,
      "support": [],
      "candidate_missing": false
    },
    {
      "answer_quotes": [
        "**如需进行示教/路径设置**：应在**正常营业时间之外**进行，或**封锁相应子区域**后再做。"
      ],
      "candidate_support": [
        {
          "quote": "不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线",
          "source_id": "DOC-001-C-00096"
        }
      ],
      "check_type": "fact",
      "met": false,
      "reference_support": [
        {
          "quote": "不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线",
          "source_id": "DOC-001-C-00096"
        }
      ],
      "requirement": "应说明如果布局发生重大变化，必须重新示教该路线，而不是仅作为可选的路径设置。",
      "scope_resolved": true,
      "support": [],
      "candidate_missing": false
    }
  ]
}
```

### 4. Judge原始判定与检查（未改写）

保存业务verdict=FAIL；原始Judge verdict=FAIL。
<details><summary>完整原始Provider JSON（含所有checks、issues、support与reason）</summary>

```json
{"verdict":"FAIL","checks":[{"check_type":"fact","requirement":"应说明 KIRA B50 的地图不具备自学习功能，不会自动补充新障碍物或自动适应重新摆桌椅后的布局。","met":false,"answer_quotes":[],"support":[],"reference_support":[{"source_id":"DOC-001-C-00096","quote":"不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线"}],"candidate_support":[{"source_id":"DOC-001-C-00096","quote":"不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线"}],"scope_resolved":true},{"check_type":"fact","requirement":"应说明对原始布局的细微改动不成问题，不需要因轻微重新摆桌椅而直接停止自主清洁。","met":false,"answer_quotes":["先不要直接让 KIRA B 50 进入该区域自主清洁。"],"support":[],"reference_support":[{"source_id":"DOC-001-C-00096","quote":"不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线"}],"candidate_support":[{"source_id":"DOC-001-C-00096","quote":"不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线"}],"scope_resolved":true},{"check_type":"fact","requirement":"应说明布局改动越大，设备效率越低。","met":false,"answer_quotes":[],"support":[],"reference_support":[{"source_id":"DOC-001-C-00096","quote":"不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线"}],"candidate_support":[{"source_id":"DOC-001-C-00096","quote":"不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线"}],"scope_resolved":true},{"check_type":"fact","requirement":"应说明如果布局发生重大变化，必须重新示教该路线，而不是仅作为可选的路径设置。","met":false,"answer_quotes":["**如需进行示教/路径设置**：应在**正常营业时间之外**进行，或**封锁相应子区域**后再做。"],"support":[],"reference_support":[{"source_id":"DOC-001-C-00096","quote":"不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线"}],"candidate_support":[{"source_id":"DOC-001-C-00096","quote":"不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线"}],"scope_resolved":true},{"check_type":"fact","requirement":"当前操作适用性：用户只说昨晚重新摆了桌椅，未确认桌椅数量/变动规模；在未确认是否属于“大量桌椅区域”或重大布局变化前，不应直接按大量桌椅区域处理并暂停该区域自主清洁，应先判断变化程度。","met":false,"answer_quotes":["先不要直接让 KIRA B 50 进入该区域自主清洁。","1. **把重新摆过桌椅的区域按“大量桌椅区域”处理**：应避免设备进入，改为**手动清洁这些区域**。","可执行做法：**先封锁或手动清洁重新摆桌椅的区域，暂停该区域自主清洁；在非营业时间或封锁状态下按官方流程进行示教/路径处理。**"],"support":[{"source_id":"DOC-001-C-00085","quote":"避免摆放了大量桌椅的区域（如美食广场），并手动清洁这些区域"}],"reference_support":[{"source_id":"DOC-001-C-00096","quote":"不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线"}],"candidate_support":[{"source_id":"DOC-001-C-00085","quote":"避免摆放了大量桌椅的区域（如美食广场），并手动清洁这些区域"}],"scope_resolved":false}],"issues":[{"description":"未回答核心判定：地图不具备自学习功能，也不会自动适应新布局；缺少轻微改动无碍、改动越大效率越低、重大变化必须重新示教路线。实际只把示教写成“如需”，未说明重大变化时的强制要求。","answer_quotes":["**如需进行示教/路径设置**：应在**正常营业时间之外**进行，或**封锁相应子区域**后再做。","未确认条件：给定证据没有提供 KIRA B 50 重新示教、地图更新或路径修改的具体操作步骤，因此不能据此给出具体按键/界面操作；需查阅对应版本的官方操作说明或联系官方支持。"],"support":[{"source_id":"DOC-001-C-00096","quote":"不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线"}],"critical":true,"safety_violation":false,"scope_resolved":true,"baseline_issue_index":null},{"description":"把“重新摆了桌椅”未经确认直接归为“大量桌椅区域”并给出暂停自主清洁、手动清洁的当前操作建议；该手册条款的前提是大量桌椅区域，用户场景的变动规模/是否重大变化尚未核清，适用性不足。","answer_quotes":["先不要直接让 KIRA B 50 进入该区域自主清洁。","1. **把重新摆过桌椅的区域按“大量桌椅区域”处理**：应避免设备进入，改为**手动清洁这些区域**。","可执行做法：**先封锁或手动清洁重新摆桌椅的区域，暂停该区域自主清洁；在非营业时间或封锁状态下按官方流程进行示教/路径处理。**"],"support":[{"source_id":"DOC-001-C-00085","quote":"避免摆放了大量桌椅的区域（如美食广场），并手动清洁这些区域"}],"critical":true,"safety_violation":false,"scope_resolved":false,"baseline_issue_index":null}],"reason":"实际回答引用了 KIRA B 50 手册中关于大量桌椅区域手动清洁、示教避开营业时间等正确片段，也正确提示不能凭空给出具体按键步骤；但没有回答本题核心：地图不具备自学习功能、轻微布局改动无碍、改动越大效率越低、重大变化必须重新示教路线。并且把“重新摆桌椅”未经确认直接按“大量桌椅区域”处理，当前操作适用条件未核清。故判 FAIL。","quality":{"correctness":1,"faithfulness":0.7,"completeness":0.25}}
```

</details>

### 5. 可复查的完整阶段证据

<details><summary>各阶段来源顺序、完整候选正文、完整Final与规范原文</summary>

**候选→重排→Final顺序**

```json
{
  "candidates": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00085",
      "parent_chunk_id": "DOC-001-P-00085",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.9636
    },
    {
      "position": 2,
      "chunk_id": "DOC-001-C-00087",
      "parent_chunk_id": "DOC-001-P-00087",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.8407
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00057",
      "parent_chunk_id": "DOC-001-P-00057",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00002",
      "parent_chunk_id": "DOC-001-P-00002",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4995
    },
    {
      "position": 5,
      "chunk_id": "DOC-001-C-00049",
      "parent_chunk_id": "DOC-001-P-00049",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4864
    },
    {
      "position": 6,
      "chunk_id": "DOC-001-C-00119",
      "parent_chunk_id": "DOC-001-P-00118",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4822
    },
    {
      "position": 7,
      "chunk_id": "DOC-001-C-00096",
      "parent_chunk_id": "DOC-001-P-00095",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4811
    },
    {
      "position": 8,
      "chunk_id": "DOC-001-C-00082",
      "parent_chunk_id": "DOC-001-P-00082",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.473
    },
    {
      "position": 9,
      "chunk_id": "DOC-002-C-00054",
      "parent_chunk_id": "DOC-002-P-00046",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4676
    },
    {
      "position": 10,
      "chunk_id": "DOC-001-C-00058",
      "parent_chunk_id": "DOC-001-P-00058",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4636
    },
    {
      "position": 11,
      "chunk_id": "DOC-001-C-00080",
      "parent_chunk_id": "DOC-001-P-00080",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4568
    },
    {
      "position": 12,
      "chunk_id": "DOC-002-C-00053",
      "parent_chunk_id": "DOC-002-P-00045",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4507
    }
  ],
  "reranked": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00119",
      "parent_chunk_id": "DOC-001-P-00118",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5420532883652076,
      "rerank_score": 0.5420532883652076
    },
    {
      "position": 2,
      "chunk_id": "DOC-002-C-00053",
      "parent_chunk_id": "DOC-002-P-00045",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.5344649643985768,
      "rerank_score": 0.5344649643985768
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00085",
      "parent_chunk_id": "DOC-001-P-00085",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5289915700745197,
      "rerank_score": 0.5289915700745197
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00002",
      "parent_chunk_id": "DOC-001-P-00002",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5225547671286348,
      "rerank_score": 0.5225547671286348
    },
    {
      "position": 5,
      "chunk_id": "DOC-001-C-00057",
      "parent_chunk_id": "DOC-001-P-00057",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5067156937400963,
      "rerank_score": 0.5067156937400963
    },
    {
      "position": 6,
      "chunk_id": "DOC-001-C-00087",
      "parent_chunk_id": "DOC-001-P-00087",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.503490454423859,
      "rerank_score": 0.503490454423859
    },
    {
      "position": 7,
      "chunk_id": "DOC-001-C-00049",
      "parent_chunk_id": "DOC-001-P-00049",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4720710296261698,
      "rerank_score": 0.4720710296261698
    },
    {
      "position": 8,
      "chunk_id": "DOC-001-C-00058",
      "parent_chunk_id": "DOC-001-P-00058",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4452736069249018,
      "rerank_score": 0.4452736069249018
    },
    {
      "position": 9,
      "chunk_id": "DOC-001-C-00082",
      "parent_chunk_id": "DOC-001-P-00082",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4217122667750777,
      "rerank_score": 0.4217122667750777
    },
    {
      "position": 10,
      "chunk_id": "DOC-001-C-00080",
      "parent_chunk_id": "DOC-001-P-00080",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.3763337387069443,
      "rerank_score": 0.3763337387069443
    },
    {
      "position": 11,
      "chunk_id": "DOC-002-C-00054",
      "parent_chunk_id": "DOC-002-P-00046",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.325271016588867,
      "rerank_score": 0.325271016588867
    },
    {
      "position": 12,
      "chunk_id": "DOC-001-C-00096",
      "parent_chunk_id": "DOC-001-P-00095",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.3059258052143955,
      "rerank_score": 0.3059258052143955
    }
  ],
  "final": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00119",
      "parent_chunk_id": "DOC-001-P-00118",
      "matched_child_ids": [
        "DOC-001-C-00119"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5420532883652076,
      "rerank_score": 0.5420532883652076
    },
    {
      "position": 2,
      "chunk_id": "DOC-002-C-00053",
      "parent_chunk_id": "DOC-002-P-00045",
      "matched_child_ids": [
        "DOC-002-C-00053"
      ],
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.5344649643985768,
      "rerank_score": 0.5344649643985768
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00085",
      "parent_chunk_id": "DOC-001-P-00085",
      "matched_child_ids": [
        "DOC-001-C-00085"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5289915700745197,
      "rerank_score": 0.5289915700745197
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00002",
      "parent_chunk_id": "DOC-001-P-00002",
      "matched_child_ids": [
        "DOC-001-C-00002"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5225547671286348,
      "rerank_score": 0.5225547671286348
    }
  ]
}
```

**全部候选正文（用于核查等价来源，而非只看ID）**
候选1：`DOC-001-C-00085` / `KIRA B 50`

```text
提示
请勿经过或紧挨着自动扶梯 电梯门，尤其是紧急出口布置清洁路径 手动清洁这些区域
提示
一些购物中心设置了地面水池或水覆盖的区域 在设置路线时，需要避开这些区域，确保设备不会意外进入这些区域
请确保智能填充 (Smart Fill) 场地内不含扁平物体（高度低于 15 cm），以便设备能够覆盖整个内部场地
请在正常营业时间之外进行示教活动，或封锁子区域
避免摆放了大量桌椅的区域（如美食广场），并手动清洁这些区域
如果后方存在坠落边缘，请遵守距离落地式窗户和护栏的极限值 1.5 m
```

候选2：`DOC-001-C-00087` / `KIRA B 50`

```text
提示
请确保清洁路径不会经过或紧挨着自动扶梯 电梯门，尤其是紧急出口 手动清洁这些区域
请避免铺设地毯的地面
避免在卷帘门旁边清洁
请确保智能填充 (Smart Fill) 场地内不含扁平物体（高度低于 15 cm），以便设备能够覆盖整个内部场地
阳光直射会导致传感器和导航出现问题
如果后方存在坠落边缘，请遵守距离落地式窗户和护栏的极限值 1.5 m
在占用率最低时进行示教，或封锁子区域
尽量移除移动物体
请避免包含排队管理系统（如栅栏）的区域，因为设备可能无法可靠检测这些物体
请检查当设备从侧面靠近时，是否能够识别独立标志牌
避免摆放了大量桌椅的区域（如美食广场），并手动清洁这些区域
提示
请勿经过或紧挨着自动扶梯 电梯门，尤其是紧急出口布置清洁路径 手动清洁这些区域
请清除胶带 托盘上的碎片和透明膜，确保清洁路径上无废弃物和物品（如电缆 包装带等） 这些物品会在刷子内缠结
自动运行期间，设备附近不得有任何扁平物体（高度低于 15 cm，如叉车叉齿）
请根据其机构的“交通
```

候选3：`DOC-001-C-00057` / `KIRA B 50`

```text
处理方式
在示教期间注意以下几点：
待清洁场地的示教
像使用传统手操纵式设备一样清洁场地 请利用屏幕上的实时地图紧密布置线路，或稍微重叠 已清洁的场地用蓝色表示，以免遗漏待清洁的场地
```

候选4：`DOC-001-C-00002` / `KIRA B 50`

```text
KIRA B 50
KIRA B 50
ZH

```

候选5：`DOC-001-C-00049` / `KIRA B 50`

```text
环境准备工作
清除设备无法吸取的污物（如胶带 托盘上的碎片和透明膜），因为这些可能会损坏设备
请确保路线上不存在季节性陈列物，以及其他非永久性障碍物
请在待清洁场地的工作负荷最低时，示教新路线 最好避开正常营业和工作时间
```

候选6：`DOC-001-C-00119` / `KIRA B 50`

```text
提示：
为了快速更换清洁剂，可以取下清洁剂罐，并换上另一个清洁剂罐
```

候选7：`DOC-001-C-00096` / `KIRA B 50`

```text
地图是否具备自学习功能，并补充新障碍物？
不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线
```

候选8：`DOC-001-C-00082` / `KIRA B 50`

```text
6. 仓库
请确保路径不会被移动物品（如纸箱或托盘）所阻挡
请考虑在正常营业时间之后清理仓库，以免中断正常的工作流程
```

候选9：`DOC-002-C-00054` / `B2 四足机器人`

```text
1. 清洁
当 B2 在恶劣环境下（雨天、沙尘、湿地）使用后，请及时清洁机身表面。
清洗机身前请先关闭电源，使用干净的软布对机身进行擦拭，尤其关注多目深度相机是否擦拭干净。清洁时严禁使用金属刷、砂纸等，以免刮伤零件表面。清洗后，请用软布将机身擦干。擦干后可用风扇或风枪将机器人表面、关节缝隙处的积水吹干，避免留下水痕。
\- 注意！B2 整机（含电池包）IP67 级防水，清洁时请勿取下电池包！
```

候选10：`DOC-001-C-00058` / `KIRA B 50`

```text
提示
为了让边刷能够到达待清洁场地的边缘，必须在该场地上逆时针行车
```

候选11：`DOC-001-C-00080` / `KIRA B 50`

```text
4. 肉类柜台
该区域必须更常清洁，因为这里的卫生标准更高，干净整洁的环境极为重要 进一步划分包含季节性陈列物和障碍物的区域，是一个非常实用的方法
```

候选12：`DOC-002-C-00053` / `B2 四足机器人`

```text
整机清洁
```

**完整Final（Parent展开后的真实模型输入正文）**
Final 1：`DOC-001-C-00119` / Parent `DOC-001-P-00118` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 43–43；source_scope=null

```text
提示：
为了快速更换清洁剂，可以取下清洁剂罐，并换上另一个清洁剂罐
```

Final 2：`DOC-002-C-00053` / Parent `DOC-002-P-00045` / `宇树_B2四足机器人用户手册_中文版.pdf` / PDF 18–18；source_scope=null

```text
整机清洁
```

Final 3：`DOC-001-C-00085` / Parent `DOC-001-P-00085` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 26–27；source_scope=null

```text
提示
请勿经过或紧挨着自动扶梯 电梯门，尤其是紧急出口布置清洁路径 手动清洁这些区域
提示
一些购物中心设置了地面水池或水覆盖的区域 在设置路线时，需要避开这些区域，确保设备不会意外进入这些区域
请确保智能填充 (Smart Fill) 场地内不含扁平物体（高度低于 15 cm），以便设备能够覆盖整个内部场地
请在正常营业时间之外进行示教活动，或封锁子区域
避免摆放了大量桌椅的区域（如美食广场），并手动清洁这些区域
如果后方存在坠落边缘，请遵守距离落地式窗户和护栏的极限值 1.5 m
```

Final 4：`DOC-001-C-00002` / Parent `DOC-001-P-00002` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 1–1；source_scope=null

```text
KIRA B 50
KIRA B 50
ZH

```

**本题规范原文与元数据（Corpus完整Child）**
`DOC-001-C-00085`；KIRA B 50；PDF 26–27；version=None

```text
提示
请勿经过或紧挨着自动扶梯 电梯门，尤其是紧急出口布置清洁路径 手动清洁这些区域
提示
一些购物中心设置了地面水池或水覆盖的区域 在设置路线时，需要避开这些区域，确保设备不会意外进入这些区域
请确保智能填充 (Smart Fill) 场地内不含扁平物体（高度低于 15 cm），以便设备能够覆盖整个内部场地
请在正常营业时间之外进行示教活动，或封锁子区域
避免摆放了大量桌椅的区域（如美食广场），并手动清洁这些区域
如果后方存在坠落边缘，请遵守距离落地式窗户和护栏的极限值 1.5 m
```

`DOC-001-C-00096`；KIRA B 50；PDF 28–28；version=None

```text
地图是否具备自学习功能，并补充新障碍物？
不，地图不具备自学习功能 对原始布局进行细微改动不成问题 对布局的改动越大，则设备的效率就越低 如果布局发生了重大变化，则必须重新示教该路线
```

</details>

## Q28 — FAIL合理；机械拆装正确，安全信息缺失；“已证实安全越界”不宜随FAIL自动成立。

真实题号：`V1G-110926448917-28`；类别：`ablation`。

### 1. 冻结Golden与实际回答

**问题（完整）**

```text
KIRA B 50 的刷辊磨秃了，清洁机组已经打开，接下来怎么把旧刷辊取下来、新的装上去？装完有没有方向或卡扣要对？
```

**冻结参考答案（完整，保留原始文字）**

```text
在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接
在执行任何工作之前，请将设备与对接站断开，或拔出电源插头
更换刷辊
1. 按下按钮，将防撞保护板转到一侧
2. 按下解锁按钮
3. 转出轴承盖
4. 拉出刷辊
提示：如果黄色指示器刷毛与其他刷毛长度相同，则说明刷辊已磨损
5. 装入新刷辊，并来回转动刷辊，使其在从动件上方居中
6. 摆回轴承盖，将刷辊的端盖卡入轴承盖
7. 抬起削刮胶条，摆回防撞保护板并将其卡入
```

**冻结Golden evidence字段（原样；摘要不能冒充完整规范）**

```json
[
  {
    "evidence_key_points": [
      "保养和维护\n警告\n在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接 \n小心\n只允许授权的客户服务部进行维修工作 备件安装和在电气零部件上进行工作\n小心\n只允许已授权的客户服务处或熟知该领域所有重要安全规定的专业人员进行设备修",
      "保养和维护\n危险\n无意中启动设备，接触导电部件\n受伤危险，触电\n在执行任何工作之前，请将设备与对接站断开，或拔出电源插头",
      "更换刷辊\n1. 按下按钮，将防撞保护板转到一侧\n\n2. 按下解锁按钮\n3. 转出轴承盖\n4. 拉出刷辊\n提示：如果黄色指示器刷毛与其他刷毛长度相同，则说明刷辊已磨损\n5. 装入新刷辊，并来回转动刷辊，使其在从动件上方居中\n6. 摆回轴承盖，将刷辊的端盖卡入轴承盖\n7. 抬起削刮胶条，摆回防撞保护板并将其卡入"
    ],
    "source_chunk_ids": [
      "DOC-001-C-00026",
      "DOC-001-C-00181",
      "DOC-001-C-00200"
    ]
  }
]
```

**RAG实际回答（完整）**

```text
不能直接按“清洁机组已打开”的状态拆装刷辊。资料只给出了更换刷辊的机械步骤，**未说明清洁机组开启时可否进行更换，也未提供维护停用、断电或防意外启动步骤**；这些关键安全条件未确认前，不应把下列步骤当作当前可直接执行的授权。请先按官方维护停用程序停用设备并确认不会意外启动；该程序本证据未覆盖，需查对应版本官方手册或联系官方支持。

运行停止顺序资料仅给出：侧刷 → 刷头 → 抽吸装置[DOC-001-C-00059 | S1 | 开启清洁机组 | 页19–20]，但这不等于维护安全授权。

在完成上述停用确认后，资料中的机械拆装步骤为：

1. 按下按钮，将防撞保护板转到一侧。  
2. 按下解锁按钮。  
3. 转出轴承盖。  
4. 拉出旧刷辊。  
5. 装入新刷辊，并来回转动刷辊，使其在从动件上方居中。  
6. 摆回轴承盖，将刷辊的端盖卡入轴承盖。  
7. 抬起削刮胶条，摆回防撞保护板并将其卡入。  
[DOC-001-C-00200 | S1 | 更换刷辊 | 页94–95]

关于方向和卡扣：资料明确要求的是**新刷辊在从动件上方居中**、**刷辊端盖卡入轴承盖**、**防撞保护板摆回并卡入**；资料未提及刷辊左右方向标记或箭头方向，不能补充猜测。
```

### 2. 独立原文、范围与等价证据判断

C00026为关整机/断电池，C00181为脱离对接站/拔电源；十二候选中C00059/00142是停止清洁机组，C00025是推荐刷子，均不等价于总维护隔离。回答明确说不能直接拆装、条件未确认前不授权，故Judge issue[0]虽safety_violation=true却scope=false，本报告不把它当已闭合安全违规证据。

**必要事实逐项链路**

| 必要事实/安全条件 | Corpus原文定位 | Candidate序号 | Rerank序号 | Final条目序号 | Answer与等价范围核查 |
|---|---|---|---|---|---|
| 换件维护前关闭整机 | DOC-001-C-00026 / PDF 10–11 | 无 | 无 | 无 | 未完整表达；泛称官方停用程序不等价于明确总则 |
| 电池供电设备拔电池插头/断开电池 | DOC-001-C-00026 / PDF 10–11 | 无 | 无 | 无 | 遗漏 |
| 工作前脱离对接站或拔电源 | DOC-001-C-00181 / PDF 85–85 | 无 | 无 | 无 | 遗漏；Judge部分reference_support误标C00026，此处以正确C00181核对 |
| 按按钮转开防撞保护板 | DOC-001-C-00200 / PDF 94–95 | 1 | 1 | 1 | 已表达 |
| 按解锁按钮、转出轴承盖、拉出旧刷辊 | DOC-001-C-00200 / PDF 94–95 | 1 | 1 | 1 | 已表达 |
| 新刷辊来回转动、在从动件上方居中 | DOC-001-C-00200 / PDF 94–95 | 1 | 1 | 1 | 已表达 |
| 摆回轴承盖，端盖卡入轴承盖 | DOC-001-C-00200 / PDF 94–95 | 1 | 1 | 1 | 已表达 |
| 抬削刮胶条，防撞保护板摆回卡入 | DOC-001-C-00200 / PDF 94–95 | 1 | 1 | 1 | 已表达；无依据追加左右箭头不属于必要要求 |

### 3. 失败归因、实际程序条件与可优化性

**独立归因：** 人工证据支持Retrieval（维护规范缺候选）；答案在局部证据缺失时采取停用确认，不能把“资料本证据未覆盖”直接当作看过全手册仍否认的Generation证据。

**当前程序的确定路径：** checks[0]有效reference=C00026、scope=true、support空，但candidate_support缺失，328行失败。checks[1]把“执行任何工作前…”误绑C00026，实际位于C00181，reference验证false；checks[5]的reference列表一条对一条错，verified要求all，所以false。check[4]/issue[0] scope=false直接跳过；issue[1]虽scope=true但support=[]、无reference，334失败。均非Corpus或Canonical失败。

**工具箱与可验证假设：** 现有召回/查询方向在补齐可靠诊断后可测试维护总则召回；现有Top6不能补池外总则。当前Unknown应继续阻断；不要把错误source_id按内容自动跨源纠正进历史记录。

**建议处理：** 保留FAIL；分别处理实际检索缺口与Judge诊断引用失真。修正原始Judge输出/Prompt是正式评测问题，诊断报告指出错误来源只影响审计说明。

**完整只读诊断输出（省去耗时明细，仅保留准入与证据）**

```json
{
  "primary_root_cause": "Unknown",
  "target_eligible": false,
  "is_technical_bad_case": false,
  "retrieval_failure_stage": null,
  "trace_observations": [],
  "optimization_directions": [],
  "evidence_checks": []
}
```

### 4. Judge原始判定与检查（未改写）

保存业务verdict=FAIL；原始Judge verdict=FAIL。
<details><summary>完整原始Provider JSON（含所有checks、issues、support与reason）</summary>

```json
{"verdict":"FAIL","checks":[{"check_type":"fact","requirement":"维护/更换刷辊前必须关闭整机；电池供电设备必须拔出电池插头或断开电池连接，不能只停清洁机组/清洁头。","met":false,"answer_quotes":["**未说明清洁机组开启时可否进行更换，也未提供维护停用、断电或防意外启动步骤**","请先按官方维护停用程序停用设备并确认不会意外启动；该程序本证据未覆盖，需查对应版本官方手册或联系官方支持。"],"support":[],"reference_support":[{"source_id":"DOC-001-C-00026","quote":"保养和维护\n警告\n在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接"}],"scope_resolved":true},{"check_type":"fact","requirement":"执行任何维护工作前必须将设备与对接站断开，或拔出电源插头。","met":false,"answer_quotes":["**未说明清洁机组开启时可否进行更换，也未提供维护停用、断电或防意外启动步骤**","请先按官方维护停用程序停用设备并确认不会意外启动；该程序本证据未覆盖，需查对应版本官方手册或联系官方支持。"],"support":[],"reference_support":[{"source_id":"DOC-001-C-00026","quote":"在执行任何工作之前，请将设备与对接站断开，或拔出电源插头"}],"scope_resolved":true},{"check_type":"fact","requirement":"更换刷辊的机械步骤应完整：转开防撞保护板、按解锁按钮、转出轴承盖、拉出旧刷辊、装入新刷辊并使其在从动件上方居中、摆回轴承盖使端盖卡入、抬起削刮胶条并摆回卡入防撞保护板。","met":true,"answer_quotes":["1. 按下按钮，将防撞保护板转到一侧。  \n2. 按下解锁按钮。  \n3. 转出轴承盖。  \n4. 拉出旧刷辊。  \n5. 装入新刷辊，并来回转动刷辊，使其在从动件上方居中。  \n6. 摆回轴承盖，将刷辊的端盖卡入轴承盖。  \n7. 抬起削刮胶条，摆回防撞保护板并将其卡入。"],"support":[{"source_id":"DOC-001-C-00200","quote":"更换刷辊\n1. 按下按钮，将防撞保护板转到一侧\n\n2. 按下解锁按钮\n3. 转出轴承盖\n4. 拉出刷辊\n提示：如果黄色指示器刷毛与其他刷毛长度相同，则说明刷辊已磨损\n5. 装入新刷辊，并来回转动刷辊，使其在从动件上方居中\n6. 摆回轴承盖，将刷辊的端盖卡入轴承盖\n7. 抬起削刮胶条，摆回防撞保护板并将其卡入"}],"scope_resolved":true},{"check_type":"fact","requirement":"安装方向与卡扣要求：新刷辊需在从动件上方居中，刷辊端盖卡入轴承盖，防撞保护板摆回并卡入；资料未给出左右方向标记时不得补充猜测。","met":true,"answer_quotes":["关于方向和卡扣：资料明确要求的是**新刷辊在从动件上方居中**、**刷辊端盖卡入轴承盖**、**防撞保护板摆回并卡入**；资料未提及刷辊左右方向标记或箭头方向，不能补充猜测。"],"support":[{"source_id":"DOC-001-C-00200","quote":"5. 装入新刷辊，并来回转动刷辊，使其在从动件上方居中\n6. 摆回轴承盖，将刷辊的端盖卡入轴承盖\n7. 抬起削刮胶条，摆回防撞保护板并将其卡入"}],"scope_resolved":true},{"check_type":"fact","requirement":"当前现场为“清洁机组已打开”的 KIRA B 50 刷辊更换：必须确认整机已关闭、电池/电源或对接站已断开并防意外启动；未确认前不得把机械步骤作为当前可执行授权。","met":false,"answer_quotes":["不能直接按“清洁机组已打开”的状态拆装刷辊。","这些关键安全条件未确认前，不应把下列步骤当作当前可直接执行的授权。请先按官方维护停用程序停用设备并确认不会意外启动；该程序本证据未覆盖，需查对应版本官方手册或联系官方支持。"],"support":[],"reference_support":[{"source_id":"DOC-001-C-00026","quote":"在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接"},{"source_id":"DOC-001-C-00026","quote":"在执行任何工作之前，请将设备与对接站断开，或拔出电源插头"}],"scope_resolved":false},{"check_type":"fact","requirement":"不得错误声称资料未提供维护停用/断电步骤；该手册有保养和维护安全警告，要求关闭设备、拔电池/断开电池、断开对接站或拔电源。","met":false,"answer_quotes":["**未说明清洁机组开启时可否进行更换，也未提供维护停用、断电或防意外启动步骤**","该程序本证据未覆盖，需查对应版本官方手册或联系官方支持。"],"support":[],"reference_support":[{"source_id":"DOC-001-C-00026","quote":"保养和维护\n警告\n在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接"},{"source_id":"DOC-001-C-00026","quote":"在执行任何工作之前，请将设备与对接站断开，或拔出电源插头"}],"scope_resolved":true}],"issues":[{"description":"未保留维护换件前关闭整机、断开电池/电源及对接站的必要安全前提；仅笼统要求按官方停用程序，未向用户明确电池/对接站断开，不能视为满足当前操作安全条件。","answer_quotes":["**未说明清洁机组开启时可否进行更换，也未提供维护停用、断电或防意外启动步骤**","请先按官方维护停用程序停用设备并确认不会意外启动；该程序本证据未覆盖，需查对应版本官方手册或联系官方支持。"],"support":[],"critical":true,"safety_violation":true,"scope_resolved":false,"baseline_issue_index":null},{"description":"答案称资料未提供维护停用、断电或防意外启动步骤，与参考手册保养和维护警告不符；该错误会掩盖实际应执行的安全前提。","answer_quotes":["**未说明清洁机组开启时可否进行更换，也未提供维护停用、断电或防意外启动步骤**","该程序本证据未覆盖，需查对应版本官方手册或联系官方支持。"],"support":[],"critical":true,"safety_violation":false,"scope_resolved":true,"baseline_issue_index":null}],"reason":"机械拆装步骤、居中/端盖/防撞保护板卡扣以及“未给出左右方向标记则不猜测”均正确，且答案未直接授权在清洁机组开启状态下拆装。但未保留维护前关闭整机、拔电池/断开电池以及断开对接站/拔电源的必要安全前提，并错误声称资料未提供维护停用/断电步骤；当前现场安全适用性未确认，故判FAIL。","quality":{"correctness":2,"faithfulness":0.8,"completeness":0.6}}
```

</details>

### 5. 可复查的完整阶段证据

<details><summary>各阶段来源顺序、完整候选正文、完整Final与规范原文</summary>

**候选→重排→Final顺序**

```json
{
  "candidates": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00200",
      "parent_chunk_id": "DOC-001-P-00198",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.9944
    },
    {
      "position": 2,
      "chunk_id": "DOC-001-C-00183",
      "parent_chunk_id": "DOC-001-P-00181",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.8062
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00059",
      "parent_chunk_id": "DOC-001-P-00059",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.7988
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00194",
      "parent_chunk_id": "DOC-001-P-00192",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5
    },
    {
      "position": 5,
      "chunk_id": "DOC-001-C-00102",
      "parent_chunk_id": "DOC-001-P-00101",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.488
    },
    {
      "position": 6,
      "chunk_id": "DOC-001-C-00202",
      "parent_chunk_id": "DOC-001-P-00200",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4549
    },
    {
      "position": 7,
      "chunk_id": "DOC-002-C-00031",
      "parent_chunk_id": "DOC-002-P-00026",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4375
    },
    {
      "position": 8,
      "chunk_id": "DOC-001-C-00201",
      "parent_chunk_id": "DOC-001-P-00199",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4373
    },
    {
      "position": 9,
      "chunk_id": "DOC-001-C-00203",
      "parent_chunk_id": "DOC-001-P-00201",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.431
    },
    {
      "position": 10,
      "chunk_id": "DOC-001-C-00025",
      "parent_chunk_id": "DOC-001-P-00025",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4281
    },
    {
      "position": 11,
      "chunk_id": "DOC-001-C-00141",
      "parent_chunk_id": "DOC-001-P-00140",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4173
    },
    {
      "position": 12,
      "chunk_id": "DOC-001-C-00142",
      "parent_chunk_id": "DOC-001-P-00141",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4167
    }
  ],
  "reranked": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00200",
      "parent_chunk_id": "DOC-001-P-00198",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.8128000356371929,
      "rerank_score": 0.8128000356371929
    },
    {
      "position": 2,
      "chunk_id": "DOC-001-C-00059",
      "parent_chunk_id": "DOC-001-P-00059",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.6728025656577952,
      "rerank_score": 0.6728025656577952
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00203",
      "parent_chunk_id": "DOC-001-P-00201",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.6067864390741047,
      "rerank_score": 0.6067864390741047
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00141",
      "parent_chunk_id": "DOC-001-P-00140",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5914040067498748,
      "rerank_score": 0.5914040067498748
    },
    {
      "position": 5,
      "chunk_id": "DOC-001-C-00202",
      "parent_chunk_id": "DOC-001-P-00200",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5892767390524034,
      "rerank_score": 0.5892767390524034
    },
    {
      "position": 6,
      "chunk_id": "DOC-001-C-00102",
      "parent_chunk_id": "DOC-001-P-00101",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5810255652969468,
      "rerank_score": 0.5810255652969468
    },
    {
      "position": 7,
      "chunk_id": "DOC-001-C-00201",
      "parent_chunk_id": "DOC-001-P-00199",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.529041980147434,
      "rerank_score": 0.529041980147434
    },
    {
      "position": 8,
      "chunk_id": "DOC-001-C-00142",
      "parent_chunk_id": "DOC-001-P-00141",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.48261527955122063,
      "rerank_score": 0.48261527955122063
    },
    {
      "position": 9,
      "chunk_id": "DOC-001-C-00194",
      "parent_chunk_id": "DOC-001-P-00192",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4681932942829848,
      "rerank_score": 0.4681932942829848
    },
    {
      "position": 10,
      "chunk_id": "DOC-001-C-00025",
      "parent_chunk_id": "DOC-001-P-00025",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4408635737210968,
      "rerank_score": 0.4408635737210968
    },
    {
      "position": 11,
      "chunk_id": "DOC-001-C-00183",
      "parent_chunk_id": "DOC-001-P-00181",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.436844235028687,
      "rerank_score": 0.436844235028687
    },
    {
      "position": 12,
      "chunk_id": "DOC-002-C-00031",
      "parent_chunk_id": "DOC-002-P-00026",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4038545303940061,
      "rerank_score": 0.4038545303940061
    }
  ],
  "final": [
    {
      "position": 1,
      "chunk_id": "DOC-001-C-00200",
      "parent_chunk_id": "DOC-001-P-00198",
      "matched_child_ids": [
        "DOC-001-C-00200"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.8128000356371929,
      "rerank_score": 0.8128000356371929
    },
    {
      "position": 2,
      "chunk_id": "DOC-001-C-00059",
      "parent_chunk_id": "DOC-001-P-00059",
      "matched_child_ids": [
        "DOC-001-C-00059"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.6728025656577952,
      "rerank_score": 0.6728025656577952
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00203",
      "parent_chunk_id": "DOC-001-P-00201",
      "matched_child_ids": [
        "DOC-001-C-00203"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.6067864390741047,
      "rerank_score": 0.6067864390741047
    },
    {
      "position": 4,
      "chunk_id": "DOC-001-C-00141",
      "parent_chunk_id": "DOC-001-P-00140",
      "matched_child_ids": [
        "DOC-001-C-00141"
      ],
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5914040067498748,
      "rerank_score": 0.5914040067498748
    }
  ]
}
```

**全部候选正文（用于核查等价来源，而非只看ID）**
候选1：`DOC-001-C-00200` / `KIRA B 50`

```text
更换刷辊
1. 按下按钮，将防撞保护板转到一侧

2. 按下解锁按钮
3. 转出轴承盖
4. 拉出刷辊
提示：如果黄色指示器刷毛与其他刷毛长度相同，则说明刷辊已磨损
5. 装入新刷辊，并来回转动刷辊，使其在从动件上方居中
6. 摆回轴承盖，将刷辊的端盖卡入轴承盖
7. 抬起削刮胶条，摆回防撞保护板并将其卡入
```

候选2：`DOC-001-C-00183` / `KIRA B 50`

```text
在每次运行之后
1. ## 排放污水<sub>。</sub>
2. ## 冲洗污水箱
3. 清洁涡轮机防护网
4. 从污水箱中取出粗大污染物滤网并清洗
5. 使用抹布和洗涤用碱液清洁设备外部
6. 检查绒毛滤网，必要时清洁
7. 拆下并清洁清洁头上的粗大污染物容器
8. 清洗清洁头上的分水条
9. 清洁吸水扒中的吸水胶条，检查是否存在磨损 翻转或更换已磨损的吸水胶条
10. 检查吸水胶条在吸水扒中的正确配合 必要时，将吸水胶条重新正确装入吸水扒的凹槽中
11. 清洁清洁头两侧的削刮胶条，检查是否存在磨损 更换已磨损的削刮胶条
12. 检查刷子是否磨损 更换已磨损的刷子
提示：如果黄色指示器刷毛与其他刷毛长度相同，则说明刷辊已磨损
13. ## 给蓄电池充电
```

候选3：`DOC-001-C-00059` / `KIRA B 50`

```text
开启清洁机组
应始终按照以下顺序打开清洁机组：1. 抽吸装置2. 刷头3. 侧刷
关闭清洁机组
在过渡线路上或结束路线之前，始终应按照以下顺序关闭清洁机组：1. 侧刷2. 刷头3. 抽吸装置

在抽吸装置开启的情况下利用设备行驶数米，吸除场地上的残余水分
```

候选4：`DOC-001-C-00194` / `KIRA B 50`

```text
更换或翻转吸水胶条
当吸水胶条磨损到磨损标记时，将其翻转或更换

1. 从设备上取下吸水扒
2. 拧开星形手柄
1 星形手柄 2 导流辊 3 端头 4 吸水胶条
3. 取下套筒和导流辊4. 拉下端头5. 以纵向方向拉下吸水胶条6. 将新的或已翻转的吸水胶条推入吸水扒7. 推上端头8. 安装导流辊和套筒

9. 拧入星形手柄并拧紧
```

候选5：`DOC-001-C-00102` / `KIRA B 50`

```text
清洁头

1 防撞保护板解锁2 防撞保护板3 刷辊4 清洁头5 换刷解锁键
```

候选6：`DOC-001-C-00202` / `KIRA B 50`

```text
更换边刷
```

候选7：`DOC-002-C-00031` / `B2 四足机器人`

```text
(1) 安装电池包
将 B2 放在平坦的地面上，将电池包从机器人侧面插入电池槽，注意安装方向，防呆接口朝上，如无法完全插入电池包，请调整电池包方向，不要强行按压，以免损坏电池接口和卡扣，当听到“咔哒\~”声，电池包安装完成。请确保卡扣卡到位！
```

候选8：`DOC-001-C-00201` / `KIRA B 50`

```text
更换削刮胶条
1. 拧出 3 个螺栓

2. 将削刮胶条连同支架一起取出
3. 从支架上取下已磨损的削刮胶条
4. 将新削刮胶条套到支架的销子上
5. 将支架连同削刮胶条一起重新安装到设备上
6. 在设备另一侧重复该过程<sub>。</sub>
```

候选9：`DOC-001-C-00203` / `KIRA B 50`

```text
1. 拧开翼形螺钉

1 侧刷 2 翼形螺钉 3 垫片
2. 拆下边刷
3. 插上新边刷
4. 将翼形螺栓连同垫片拧入并拧紧
```

候选10：`DOC-001-C-00025` / `KIRA B 50`

```text
带旋转刷的设备
小心
不合适的刷子会危及您的安全 只能使用随设备提供的刷子或操作说明书中推荐的刷子
```

候选11：`DOC-001-C-00141` / `KIRA B 50`

```text
提示
当清洁头已开启时，才能激活边刷
7. 操作并握紧安全开关
8. 将设备推到待清洁的场地上
```

候选12：`DOC-001-C-00142` / `KIRA B 50`

```text
结束清洁
1. 停用清洁头和边刷
2. 继续行驶一小段线路，抽吸残余水分
3. 停用抽吸装置
```

**完整Final（Parent展开后的真实模型输入正文）**
Final 1：`DOC-001-C-00200` / Parent `DOC-001-P-00198` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 94–95；source_scope=null

```text
更换刷辊
1. 按下按钮，将防撞保护板转到一侧

2. 按下解锁按钮
3. 转出轴承盖
4. 拉出刷辊
提示：如果黄色指示器刷毛与其他刷毛长度相同，则说明刷辊已磨损
5. 装入新刷辊，并来回转动刷辊，使其在从动件上方居中
6. 摆回轴承盖，将刷辊的端盖卡入轴承盖
7. 抬起削刮胶条，摆回防撞保护板并将其卡入
```

Final 2：`DOC-001-C-00059` / Parent `DOC-001-P-00059` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 19–20；source_scope=null

```text
开启清洁机组
应始终按照以下顺序打开清洁机组：1. 抽吸装置2. 刷头3. 侧刷
关闭清洁机组
在过渡线路上或结束路线之前，始终应按照以下顺序关闭清洁机组：1. 侧刷2. 刷头3. 抽吸装置

在抽吸装置开启的情况下利用设备行驶数米，吸除场地上的残余水分
```

Final 3：`DOC-001-C-00203` / Parent `DOC-001-P-00201` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 96–97；source_scope=null

```text
1. 拧开翼形螺钉

1 侧刷 2 翼形螺钉 3 垫片
2. 拆下边刷
3. 插上新边刷
4. 将翼形螺栓连同垫片拧入并拧紧
```

Final 4：`DOC-001-C-00141` / Parent `DOC-001-P-00140` / `卡赫_KIRA_B_50完整操作说明_中文版.pdf` / PDF 58–58；source_scope=null

```text
提示
当清洁头已开启时，才能激活边刷
7. 操作并握紧安全开关
8. 将设备推到待清洁的场地上
```

**本题规范原文与元数据（Corpus完整Child）**
`DOC-001-C-00026`；KIRA B 50；PDF 10–11；version=None

```text
保养和维护
警告
在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接 
小心
只允许授权的客户服务部进行维修工作 备件安装和在电气零部件上进行工作
小心
只允许已授权的客户服务处或熟知该领域所有重要安全规定的专业人员进行设备修复工作
小心
定期清洁水位限制装置，并检查是否出现损坏
注意
在按照当地现行规定对用作商业用途的移动式设备进行安全检查时，
注意
注意是否出现短路或其它损坏 不得用软管或高压水射流清洁设备
```

`DOC-001-C-00181`；KIRA B 50；PDF 85–85；version=None

```text
保养和维护
危险
无意中启动设备，接触导电部件
受伤危险，触电
在执行任何工作之前，请将设备与对接站断开，或拔出电源插头
```

`DOC-001-C-00200`；KIRA B 50；PDF 94–95；version=None

```text
更换刷辊
1. 按下按钮，将防撞保护板转到一侧

2. 按下解锁按钮
3. 转出轴承盖
4. 拉出刷辊
提示：如果黄色指示器刷毛与其他刷毛长度相同，则说明刷辊已磨损
5. 装入新刷辊，并来回转动刷辊，使其在从动件上方居中
6. 摆回轴承盖，将刷辊的端盖卡入轴承盖
7. 抬起削刮胶条，摆回防撞保护板并将其卡入
```

</details>

## Q29 — FAIL合理；请求B2整机不带电检查，回答仅充电器两项且拒绝给完整表。

真实题号：`V1G-110926448917-29`；类别：`ablation`。

### 1. 冻结Golden与实际回答

**问题（完整）**

```text
客户准备重新使用B2，我要按用户手册做一次不带电检查。具体要检查哪些项目？
```

**冻结参考答案（完整，保留原始文字）**

```text
不带电检查表
类型=整机外观；要点=1. 机身外观是否清洁、无破损或变形痕迹2. 相机表面镜片有无异物3. 头部激光雷达周围有无异物遮挡
类型=结构；要点=1. 目视及触摸检查机身、各个关节及连接处、足端组件是否完好,有裂纹或者有破损需及时更换和联系 Unitree 售后2. 各个连接部件螺丝是否锁紧,尤其关注关节连接件和电池锁紧旋钮的螺丝3. 散热风扇进出口有无异物阻塞
类型=足端组件；要点=检查有无明显的足垫破损,若有破损请及时更换
类型=电池包；要点=1. 机身的电池包接口有无异物,变形2. 电池包安装是否可靠,确保运行时不会松脱3. 电池包外壳是否有明显损伤,有明显损伤的电池包禁止用于使用
类型=遥控器；要点=1. 遥控器摇杆是都在中位,摇杆是否进入沙土等异物2. 遥控器的各个按键是否存在卡顿
```

**冻结Golden evidence字段（原样；摘要不能冒充完整规范）**

```json
[
  {
    "evidence_key_points": [
      "检查保养\n在使用前后开展例行检查，可大幅度提升产品可靠性能，降低安全隐患，延长使用寿命。不带电检查表\n类型=整机外观；要点=1. 机身外观是否清洁、无破损或变形痕迹2. 相机表面镜片有无异物3. 头部激光雷达周围有无异物遮挡\n类型=结构；要点=1. 目视及触摸检查机身、各个关节及连接处、足端组件是否完好,有裂纹或者有破"
    ],
    "source_chunk_ids": [
      "DOC-002-C-00056"
    ]
  }
]
```

**RAG实际回答（完整）**

```text
按现有资料，能确认的“不带电检查”项目只有 **B2 电池与充电器使用手册 V1.0 第12页“检查”** 中的两项：

1. 检查充电器表面有无变形、鼓包等；  
2. 检查充电接口有无水渍、异物等。  
   依据：DOC-004-C-00034（S1，页12）

但这两项是“充电前后例行检查”，**不能据此扩展为 B2 整机重新使用前的完整不带电检查清单**。现有证据中：

- B2 四足机器人用户手册仅提供“清洁”章节，要求清洗前先关闭电源，未列出重新启用前的不带电检查项目；依据：DOC-002-C-00054（S2，页18）
- B2 遥控器使用说明仅确认版本信息，未提供检查项目；依据：DOC-003-C-00001（S3，页1）
- 电池与充电器手册版本为 V1.0；依据：DOC-004-C-00001（S1，页1）

因此，**无法依据所给资料给出 B2 整机“重新使用前不带电检查”的完整项目清单**。请补充 B2 四足机器人用户手册中对应型号、版本的“检查/维护/重新启用”章节，或确认本次检查范围是否仅限电池与充电器。
```

### 2. 独立原文、范围与等价证据判断

PDF第18页（印刷页17）检查表含整机外观、结构、足端、电池包、遥控器；与Corpus C00056一致。Final的DOC-002-C-00054虽同一个PDF页，只含机身清洁，并非缺页或OCR整页失败。Final DOC-004-C-00034为充电器检查，不能等价整机检查。候选DOC-002-C-00008只到安全须知第4条截断；DOC-002-C-00039为关机，不含完整检查表。

**必要事实逐项链路**

| 必要事实/安全条件 | Corpus原文定位 | Candidate序号 | Rerank序号 | Final条目序号 | Answer与等价范围核查 |
|---|---|---|---|---|---|
| 整机外观：清洁、无破损/变形 | DOC-002-C-00056 / PDF 18–18 | 无 | 无 | 无 | 遗漏 |
| 相机镜片、头部激光雷达无异物/遮挡 | DOC-002-C-00056 / PDF 18–18 | 无 | 无 | 无 | 遗漏 |
| 结构：目视触摸机身/关节/连接处/足端，裂纹破损及时更换并联系售后 | DOC-002-C-00056 / PDF 18–18 | 无 | 无 | 无 | 遗漏 |
| 连接螺丝锁紧，重点关节连接件/电池锁紧旋钮 | DOC-002-C-00056 / PDF 18–18 | 无 | 无 | 无 | 遗漏 |
| 散热风扇进出口无异物阻塞 | DOC-002-C-00056 / PDF 18–18 | 无 | 无 | 无 | 遗漏 |
| 足垫无明显破损，破损及时更换 | DOC-002-C-00056 / PDF 18–18 | 无 | 无 | 无 | 遗漏；本题候选未含足垫检查或破损更换的等价事实 |
| 电池包接口无异物/变形，安装可靠不松脱 | DOC-002-C-00056 / PDF 18–18 | 无 | 无 | 无 | 遗漏；候选DOC-002-C-00008截断安全须知，不提供此检查，不能用其他产品电池条款替代 |
| 电池外壳无明显损伤；明显损伤电池禁用 | DOC-002-C-00056 / PDF 18–18 | 无 | 无 | 无 | 遗漏；候选KIRA损坏电池禁充不是B2电池包禁用的适用等价依据 |
| 遥控器摇杆中位、无沙土异物、按键不卡顿 | DOC-002-C-00056 / PDF 18–18 | 无 | 无 | 无 | 遗漏；Final遥控器封面不能替代检查表 |

### 3. 失败归因、实际程序条件与可优化性

**独立归因：** 人工证据支持主要Retrieval：检查表未入池及Final。逐个候选正文与最终Parent复核后，未发现能够替代整机检查表各必要项目的适用等价证据；同产品的关机、清洁与安全须知标题并不等于不带电检查表。结论不是由单个必需Chunk未命中直接推出。

**当前程序的确定路径：** checks[0]至[6]及issue均scope_resolved=false，在325/333行全部跳过；checks[0..2]reference在C00056真实定位，candidate_support=[]已提供，仍不能越过scope=false。checks[3..6]还缺reference_support，独立失去Corpus规范定位。确定的上游输入缺口是冻结evidence_key_points仅含C00056前160字（止于“有裂纹或者有破”），完整Child为419字；score_execution将该摘要原样作为golden_evidence，而候选/Final均缺该表，因此Judge看不到后半表的可引用规范原文，虽reference_answer有完整项目。不能断言模型scope=false唯一由截断引起，但后半项无法从实际传入规范逐字引用是确定事实。不是数据库没表、整页OCR失败或缺Rerank Trace；同页清洁片段进入Final也不包含该表。

**工具箱与可验证假设：** 源适用性与各表项证据闭合后，可用query_expansion/candidate_recall验证；候选池不含检查表，只Top6无法恢复。不得把其他题候选出现的足垫条款混入本题Trace作Ranking证据。

**建议处理：** 保留FAIL/Unknown；完整不带电检查表原文存在，但冻结Golden的证据摘要不完整，不建议回填旧Snapshot。可选择只改诊断读取规范，或未来为Judge补充同Corpus可追溯完整规范（属于新评测输入合同/身份）；若要让Judge更完整输出规范定位/范围语义，也进入新Prompt身份；不要为准入修改冻结表或把scope=false统一放行。

**完整只读诊断输出（省去耗时明细，仅保留准入与证据）**

```json
{
  "primary_root_cause": "Unknown",
  "target_eligible": false,
  "is_technical_bad_case": false,
  "retrieval_failure_stage": null,
  "trace_observations": [],
  "optimization_directions": [],
  "evidence_checks": []
}
```

### 4. Judge原始判定与检查（未改写）

保存业务verdict=FAIL；原始Judge verdict=FAIL。
<details><summary>完整原始Provider JSON（含所有checks、issues、support与reason）</summary>

```json
{"verdict":"FAIL","checks":[{"check_type":"fact","requirement":"针对客户当前“重新使用B2前按用户手册做不带电检查”的场景，应确认并使用B2四足机器人用户手册中适用于B2整机、对应型号/版本的“不带电检查表/检查保养”章节；实际回答只确认了B2电池与充电器手册V1.0第12页的充电前后例行检查，未确认B2整机不带电检查表的适用性。","met":false,"answer_quotes":["按现有资料，能确认的“不带电检查”项目只有 **B2 电池与充电器使用手册 V1.0 第12页“检查”** 中的两项：","但这两项是“充电前后例行检查”，**不能据此扩展为 B2 整机重新使用前的完整不带电检查清单**。","因此，**无法依据所给资料给出 B2 整机“重新使用前不带电检查”的完整项目清单**。"],"support":[],"reference_support":[{"source_id":"DOC-002-C-00056","quote":"检查保养\n在使用前后开展例行检查，可大幅度提升产品可靠性能，降低安全隐患，延长使用寿命。不带电检查表\n类型=整机外观；要点=1. 机身外观是否清洁、无破损或变形痕迹2. 相机表面镜片有无异物3. 头部激光雷达周围有无异物遮挡\n类型=结构；要点=1. 目视及触摸检查机身、各个关节及连接处、足端组件是否完好,有裂纹或者有破"}],"candidate_support":[],"scope_resolved":false},{"check_type":"fact","requirement":"不带电检查应包含整机外观项目：机身外观清洁、无破损或变形痕迹；相机表面镜片无异物；头部激光雷达周围无异物遮挡。","met":false,"answer_quotes":["按现有资料，能确认的“不带电检查”项目只有 **B2 电池与充电器使用手册 V1.0 第12页“检查”** 中的两项：","因此，**无法依据所给资料给出 B2 整机“重新使用前不带电检查”的完整项目清单**。"],"support":[],"reference_support":[{"source_id":"DOC-002-C-00056","quote":"检查保养\n在使用前后开展例行检查，可大幅度提升产品可靠性能，降低安全隐患，延长使用寿命。不带电检查表\n类型=整机外观；要点=1. 机身外观是否清洁、无破损或变形痕迹2. 相机表面镜片有无异物3. 头部激光雷达周围有无异物遮挡\n类型=结构；要点=1. 目视及触摸检查机身、各个关节及连接处、足端组件是否完好,有裂纹或者有破"}],"candidate_support":[],"scope_resolved":false},{"check_type":"fact","requirement":"不带电检查应包含结构检查：目视及触摸检查机身、各关节及连接处、足端组件是否完好，有裂纹或破损需及时更换并联系Unitree售后；检查各连接部件螺丝是否锁紧，尤其关注关节连接件和电池锁紧旋钮；散热风扇进出口无异物阻塞。","met":false,"answer_quotes":["因此，**无法依据所给资料给出 B2 整机“重新使用前不带电检查”的完整项目清单**。"],"support":[],"reference_support":[{"source_id":"DOC-002-C-00056","quote":"检查保养\n在使用前后开展例行检查，可大幅度提升产品可靠性能，降低安全隐患，延长使用寿命。不带电检查表\n类型=整机外观；要点=1. 机身外观是否清洁、无破损或变形痕迹2. 相机表面镜片有无异物3. 头部激光雷达周围有无异物遮挡\n类型=结构；要点=1. 目视及触摸检查机身、各个关节及连接处、足端组件是否完好,有裂纹或者有破"}],"candidate_support":[],"scope_resolved":false},{"check_type":"fact","requirement":"不带电检查应包含足端组件检查：检查有无明显足垫破损，若有破损应及时更换。","met":false,"answer_quotes":["因此，**无法依据所给资料给出 B2 整机“重新使用前不带电检查”的完整项目清单**。"],"support":[],"candidate_support":[],"scope_resolved":false},{"check_type":"fact","requirement":"不带电检查应包含电池包安装与接口检查：机身电池包接口有无异物、变形；电池包安装是否可靠，确保运行时不会松脱。","met":false,"answer_quotes":["1. 检查充电器表面有无变形、鼓包等；","2. 检查充电接口有无水渍、异物等。","因此，**无法依据所给资料给出 B2 整机“重新使用前不带电检查”的完整项目清单**。"],"support":[],"candidate_support":[],"scope_resolved":false},{"check_type":"fact","requirement":"不带电检查应包含电池包安全前提：电池包外壳是否有明显损伤；有明显损伤的电池包禁止用于使用。","met":false,"answer_quotes":["1. 检查充电器表面有无变形、鼓包等；","2. 检查充电接口有无水渍、异物等。","因此，**无法依据所给资料给出 B2 整机“重新使用前不带电检查”的完整项目清单**。"],"support":[],"candidate_support":[],"scope_resolved":false},{"check_type":"fact","requirement":"不带电检查应包含遥控器检查：遥控器摇杆是否都在中位，摇杆是否进入沙土等异物；遥控器各个按键是否存在卡顿。","met":false,"answer_quotes":["B2 遥控器使用说明仅确认版本信息，未提供检查项目；依据：DOC-003-C-00001（S3，页1）","因此，**无法依据所给资料给出 B2 整机“重新使用前不带电检查”的完整项目清单**。"],"support":[],"candidate_support":[],"scope_resolved":false}],"issues":[{"description":"未提供B2重新使用前不带电检查的完整项目清单，实际只列出电池与充电器手册的两项充电前后例行检查并明确拒绝扩展，遗漏整机外观、结构、足端组件、电池包（含明显损伤电池禁止使用）和遥控器等必要检查项；同时Final中缺少B2用户手册不带电检查表的适用证据。","answer_quotes":["按现有资料，能确认的“不带电检查”项目只有 **B2 电池与充电器使用手册 V1.0 第12页“检查”** 中的两项：","但这两项是“充电前后例行检查”，**不能据此扩展为 B2 整机重新使用前的完整不带电检查清单**。","因此，**无法依据所给资料给出 B2 整机“重新使用前不带电检查”的完整项目清单**。","1. 检查充电器表面有无变形、鼓包等；","2. 检查充电接口有无水渍、异物等。"],"support":[],"critical":true,"safety_violation":false,"scope_resolved":false,"baseline_issue_index":null}],"reason":"回答只给出电池与充电器手册的两项充电前后例行检查，并明确拒绝扩展；未按参考提供B2重新使用前不带电检查表，遗漏整机外观、结构、足端、电池包（含明显损伤电池禁用）和遥控器等必要项目。虽然措辞谨慎且未给出危险操作，但业务上未完成问题，且Final缺少B2用户手册不带电检查表证据，故FAIL。","quality":{"correctness":1,"faithfulness":0.7,"completeness":0.1}}
```

</details>

### 5. 可复查的完整阶段证据

<details><summary>各阶段来源顺序、完整候选正文、完整Final与规范原文</summary>

**候选→重排→Final顺序**

```json
{
  "candidates": [
    {
      "position": 1,
      "chunk_id": "DOC-002-C-00008",
      "parent_chunk_id": "DOC-002-P-00006",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.8648
    },
    {
      "position": 2,
      "chunk_id": "DOC-004-C-00001",
      "parent_chunk_id": "DOC-004-P-00001",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.8618
    },
    {
      "position": 3,
      "chunk_id": "DOC-001-C-00126",
      "parent_chunk_id": "DOC-001-P-00125",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5
    },
    {
      "position": 4,
      "chunk_id": "DOC-002-C-00039",
      "parent_chunk_id": "DOC-002-P-00034",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.5
    },
    {
      "position": 5,
      "chunk_id": "DOC-001-C-00024",
      "parent_chunk_id": "DOC-001-P-00024",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4728
    },
    {
      "position": 6,
      "chunk_id": "DOC-003-C-00001",
      "parent_chunk_id": "DOC-003-P-00001",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.4666
    },
    {
      "position": 7,
      "chunk_id": "DOC-001-C-00026",
      "parent_chunk_id": "DOC-001-P-00026",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4576
    },
    {
      "position": 8,
      "chunk_id": "DOC-004-C-00034",
      "parent_chunk_id": "DOC-004-P-00029",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.4574
    },
    {
      "position": 9,
      "chunk_id": "DOC-001-C-00004",
      "parent_chunk_id": "DOC-001-P-00004",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4519
    },
    {
      "position": 10,
      "chunk_id": "DOC-002-C-00054",
      "parent_chunk_id": "DOC-002-P-00046",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4496
    },
    {
      "position": 11,
      "chunk_id": "DOC-001-C-00127",
      "parent_chunk_id": "DOC-001-P-00126",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4467
    },
    {
      "position": 12,
      "chunk_id": "DOC-001-C-00184",
      "parent_chunk_id": "DOC-001-P-00182",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4466
    }
  ],
  "reranked": [
    {
      "position": 1,
      "chunk_id": "DOC-004-C-00034",
      "parent_chunk_id": "DOC-004-P-00029",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.9122317363863399,
      "rerank_score": 0.9122317363863399
    },
    {
      "position": 2,
      "chunk_id": "DOC-004-C-00001",
      "parent_chunk_id": "DOC-004-P-00001",
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.651353033187318,
      "rerank_score": 0.651353033187318
    },
    {
      "position": 3,
      "chunk_id": "DOC-002-C-00054",
      "parent_chunk_id": "DOC-002-P-00046",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.6142024748664106,
      "rerank_score": 0.6142024748664106
    },
    {
      "position": 4,
      "chunk_id": "DOC-003-C-00001",
      "parent_chunk_id": "DOC-003-P-00001",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.5656952695533504,
      "rerank_score": 0.5656952695533504
    },
    {
      "position": 5,
      "chunk_id": "DOC-002-C-00039",
      "parent_chunk_id": "DOC-002-P-00034",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.5558250966424125,
      "rerank_score": 0.5558250966424125
    },
    {
      "position": 6,
      "chunk_id": "DOC-002-C-00008",
      "parent_chunk_id": "DOC-002-P-00006",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.5441075652171413,
      "rerank_score": 0.5441075652171413
    },
    {
      "position": 7,
      "chunk_id": "DOC-001-C-00127",
      "parent_chunk_id": "DOC-001-P-00126",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.5053892968540499,
      "rerank_score": 0.5053892968540499
    },
    {
      "position": 8,
      "chunk_id": "DOC-001-C-00126",
      "parent_chunk_id": "DOC-001-P-00125",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.48570853046142926,
      "rerank_score": 0.48570853046142926
    },
    {
      "position": 9,
      "chunk_id": "DOC-001-C-00024",
      "parent_chunk_id": "DOC-001-P-00024",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.46751347577072655,
      "rerank_score": 0.46751347577072655
    },
    {
      "position": 10,
      "chunk_id": "DOC-001-C-00004",
      "parent_chunk_id": "DOC-001-P-00004",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.4470194074448301,
      "rerank_score": 0.4470194074448301
    },
    {
      "position": 11,
      "chunk_id": "DOC-001-C-00026",
      "parent_chunk_id": "DOC-001-P-00026",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.42952438448296004,
      "rerank_score": 0.42952438448296004
    },
    {
      "position": 12,
      "chunk_id": "DOC-001-C-00184",
      "parent_chunk_id": "DOC-001-P-00182",
      "document_id": "DOC-001",
      "product": "KIRA B 50",
      "score": 0.41566537518466806,
      "rerank_score": 0.41566537518466806
    }
  ],
  "final": [
    {
      "position": 1,
      "chunk_id": "DOC-004-C-00034",
      "parent_chunk_id": "DOC-004-P-00029",
      "matched_child_ids": [
        "DOC-004-C-00034"
      ],
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.9122317363863399,
      "rerank_score": 0.9122317363863399
    },
    {
      "position": 2,
      "chunk_id": "DOC-004-C-00001",
      "parent_chunk_id": "DOC-004-P-00001",
      "matched_child_ids": [
        "DOC-004-C-00001"
      ],
      "document_id": "DOC-004",
      "product": "B2 电池与充电器",
      "score": 0.651353033187318,
      "rerank_score": 0.651353033187318
    },
    {
      "position": 3,
      "chunk_id": "DOC-002-C-00054",
      "parent_chunk_id": "DOC-002-P-00046",
      "matched_child_ids": [
        "DOC-002-C-00054"
      ],
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.6142024748664106,
      "rerank_score": 0.6142024748664106
    },
    {
      "position": 4,
      "chunk_id": "DOC-003-C-00001",
      "parent_chunk_id": "DOC-003-P-00001",
      "matched_child_ids": [
        "DOC-003-C-00001"
      ],
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.5656952695533504,
      "rerank_score": 0.5656952695533504
    }
  ]
}
```

**全部候选正文（用于核查等价来源，而非只看ID）**
候选1：`DOC-002-C-00008` / `B2 四足机器人`

```text
安全须知
B2是一款具备全天候作业、强劲负载与扩展空间、多维感知、全场景覆盖、强劲算力与精准洞察等特点，面向行业级应用的四足机器人，可以为您提供更高效、智能的解决方案。
1. 本产品并非玩具，不适合未满 18 岁的人士使用。请勿让儿童接触，在有儿童出现的场景操作时务必特别小心注意。
2. 您有义务知悉您所在区域的法律，并遵守相关法律和法规。
3. 本手册是新玩家操纵机器人的入门章节，新玩家可以通过阅读此节快速掌握如何使用手柄控制机器人的方法，使机器人表现出卓越的运动性能。本手册也是老玩家需时常查阅的章节，老玩家可通过反复查阅本章内容，抓住操作机器人的要领，举一反三，并且熟知哪些动作是不推荐使用。
4. 当用户在开发者模式下运行自己开发的程序：高层（应用层）开发时遥控器命令仍有效，此时若高层API命令和遥控器命令一起发送给机器人，两种命令机器人都会执行，可能会导致机器人失稳，请务必根据机器人运行状态判断是否需要使用遥控器
```

候选2：`DOC-004-C-00001` / `B2 电池与充电器`

```text
B2 电池&充电器
使用手册 V1.0
```

候选3：`DOC-001-C-00126` / `KIRA B 50`

```text
检查设备
```

候选4：`DOC-002-C-00039` / `B2 四足机器人`

```text
关闭B2
关机前，请务必确保机器人站立在平整地面上，确保机器人处于静态站立状态（机器人机身位置处于开机起立后的初始状态，机身水平，手柄无任何操作，静态站立时的状态）。
\- 按2次L2+A键，机器人依次完成关节锁定，卧倒动作；
\- 机器人进入卧倒状态后，先短按电源键再长按电源键3秒以上关机。
关机后，请按照机身摆放要求，摆放好机器人大小腿和髋关节位置，为下次开机做准备。若长时间不使用B2，请及时取出电池包：往外拉出电池包提带，电池包即可弹出取下。
请确保机器人处于趴下状态（卧倒状态或阻尼状态）下进行关机，否则机器人关机掉电后会重重地摔在地上，可能会造成机身损坏，并存在一定的安全隐患！若开机失败，请检查机器人机身摆放是否正确。
\- 运动关节处小心夹手，请小心谨慎！
```

候选5：`DOC-001-C-00024` / `KIRA B 50`

```text
警告
每次使用前，请检查设备和电源线是否损坏 不要再使用损坏的设备，损坏的部件只能由专业人员进行维修让儿童远离电池和充电器
不要给损坏的电池充电 请卡赫客户服务部更换损坏的电池
不要把损坏的电池扔到家庭垃圾中 应告知卡赫客户服务部
避免与从损坏电池溢出的液体接触 在意外接触的情况下，用清水冲洗液体 如果接触到眼睛，还应就医
小心
请务必遵守这些使用说明 处理蓄电池时，遵守立法机构的建议
电源电压必须与充电器铭牌上规定的电压一致
只能将蓄电池用于本设备 禁止将其用于其他目的，这是危险行为
```

候选6：`DOC-003-C-00001` / `B2 遥控器`

```text
B2 遥控器
使用手册 V2.1
```

候选7：`DOC-001-C-00026` / `KIRA B 50`

```text
保养和维护
警告
在清洁，维护，更换零件和转换为其他功能之前，必须关闭设备，对于电源供电的设备，请拔出电源插头，对于电池供电的设备，请拔出电池插头或断开电池连接 
小心
只允许授权的客户服务部进行维修工作 备件安装和在电气零部件上进行工作
小心
只允许已授权的客户服务处或熟知该领域所有重要安全规定的专业人员进行设备修复工作
小心
定期清洁水位限制装置，并检查是否出现损坏
注意
在按照当地现行规定对用作商业用途的移动式设备进行安全检查时，
注意
注意是否出现短路或其它损坏 不得用软管或高压水射流清洁设备
```

候选8：`DOC-004-C-00034` / `B2 电池与充电器`

```text
- 检查
在充电前后开展例行检查，可大幅度提升产品可靠性能，降低安全隐患，延长使用寿命。
1. 检查充电器表面有无变形、鼓包等；
2. 检查充电接口有无水渍、异物等。
B2 电池&充电器使用手册
© 2023 宇树科技 版权所有
12
```

候选9：`DOC-001-C-00004` / `KIRA B 50`

```text
一般提示
为后续使用或者为后续的车主保管好操作说明书
在第一次调试设备之前，请完整阅读操作说明书，可以在设备显示屏上查阅本操作说明书，也可以下载到智能手机上
本设备可能包含根据开源授权获得许可和/或由第三方开发的组件 可以在设备的触摸屏上显示设备中存在的开源软件组件的列表（包括版权所有者和许可条款） 若要查看，请打开主菜单，调用设置并打开系统信息

```

候选10：`DOC-002-C-00054` / `B2 四足机器人`

```text
1. 清洁
当 B2 在恶劣环境下（雨天、沙尘、湿地）使用后，请及时清洁机身表面。
清洗机身前请先关闭电源，使用干净的软布对机身进行擦拭，尤其关注多目深度相机是否擦拭干净。清洁时严禁使用金属刷、砂纸等，以免刮伤零件表面。清洗后，请用软布将机身擦干。擦干后可用风扇或风枪将机器人表面、关节缝隙处的积水吹干，避免留下水痕。
\- 注意！B2 整机（含电池包）IP67 级防水，清洁时请勿取下电池包！
```

候选11：`DOC-001-C-00127` / `KIRA B 50`

```text
警告
事故危险
损坏或有缺陷的设备可能会在运行过程中导致事故
请在使用前检查设备，如有任何损坏或故障，请向负责人报告
如果设备损坏或出现功能故障，请勿使用
1. 检查设备是否密封
2. 检查紧急停机按钮的功能
3. 检查两个安全开关的功能（在手动运行的过程中，当两个安全开关均已释放时，设备是否制动？）
```

候选12：`DOC-001-C-00184` / `KIRA B 50`

```text
每周
1. 使用湿微纤维抹布清洁传感器 如有必要，请额外使用玻璃清洁剂
2. ## 定期使用时，至少每周给蓄电池完全充电一次并且没有间断
```

**完整Final（Parent展开后的真实模型输入正文）**
Final 1：`DOC-004-C-00034` / Parent `DOC-004-P-00029` / `宇树_B2电池与充电器使用说明_中文版.pdf` / PDF 12–12；source_scope=null

```text
- 检查
在充电前后开展例行检查，可大幅度提升产品可靠性能，降低安全隐患，延长使用寿命。
1. 检查充电器表面有无变形、鼓包等；
2. 检查充电接口有无水渍、异物等。
B2 电池&充电器使用手册
© 2023 宇树科技 版权所有
12
```

Final 2：`DOC-004-C-00001` / Parent `DOC-004-P-00001` / `宇树_B2电池与充电器使用说明_中文版.pdf` / PDF 1–1；source_scope=null

```text
B2 电池&充电器
使用手册 V1.0
```

Final 3：`DOC-002-C-00054` / Parent `DOC-002-P-00046` / `宇树_B2四足机器人用户手册_中文版.pdf` / PDF 18–18；source_scope=null

```text
1. 清洁
当 B2 在恶劣环境下（雨天、沙尘、湿地）使用后，请及时清洁机身表面。
清洗机身前请先关闭电源，使用干净的软布对机身进行擦拭，尤其关注多目深度相机是否擦拭干净。清洁时严禁使用金属刷、砂纸等，以免刮伤零件表面。清洗后，请用软布将机身擦干。擦干后可用风扇或风枪将机器人表面、关节缝隙处的积水吹干，避免留下水痕。
\- 注意！B2 整机（含电池包）IP67 级防水，清洁时请勿取下电池包！
```

Final 4：`DOC-003-C-00001` / Parent `DOC-003-P-00001` / `宇树_B2遥控器使用说明_中文版.pdf` / PDF 1–1；source_scope=null

```text
B2 遥控器
使用手册 V2.1
```

**本题规范原文与元数据（Corpus完整Child）**
`DOC-002-C-00051`；B2 四足机器人；PDF 17–17；version=None

```text
{s}$ ，操控奔跑时请远离人群！
9. 关于足端组件：机器人足端组件是消耗品，我们会随货赠送备用足端组件。尤其在比较粗糙的地面运行时磨损会比较严重，如发现比较明显的足垫磨损、破损，或者发现机器人行走时对地面的冲击噪声明显加大，请及时更换足端组件，以免足端组件损坏导致机器人运动失常或摔损。
10. 关于 IP67 等级防护：运行前，请先确定电池接口、电池仓接口、电池表面、电池仓表面干燥无水，再将电池插入机身。下水/雨水天气作业后，请将机身表面擦拭干净。
11. 运动时禁止触碰机器人！关节处小心夹手，如膝关节处。
\- 奔跑最大速度 $6 \mathrm{~m} / \mathrm{s}$ ，在特殊配置下实现，实际为了安全会有所限速。
© 2023 宇树科技 版权所有
16
```

`DOC-002-C-00056`；B2 四足机器人；PDF 18–18；version=None

```text
检查保养
在使用前后开展例行检查，可大幅度提升产品可靠性能，降低安全隐患，延长使用寿命。不带电检查表
类型=整机外观；要点=1. 机身外观是否清洁、无破损或变形痕迹2. 相机表面镜片有无异物3. 头部激光雷达周围有无异物遮挡
类型=结构；要点=1. 目视及触摸检查机身、各个关节及连接处、足端组件是否完好,有裂纹或者有破损需及时更换和联系 Unitree 售后2. 各个连接部件螺丝是否锁紧,尤其关注关节连接件和电池锁紧旋钮的螺丝3. 散热风扇进出口有无异物阻塞
类型=足端组件；要点=检查有无明显的足垫破损,若有破损请及时更换
类型=电池包；要点=1. 机身的电池包接口有无异物,变形2. 电池包安装是否可靠,确保运行时不会松脱3. 电池包外壳是否有明显损伤,有明显损伤的电池包禁止用于使用
类型=遥控器；要点=1. 遥控器摇杆是都在中位,摇杆是否进入沙土等异物2. 遥控器的各个按键是否存在卡顿
© 2023 宇树科技 版权所有
17
```

</details>

## Q18 — 执行技术异常，不能计业务FAIL，也不能把原始PASS当正式通过。

真实题号：`V1G-110926448917-18`；类别：`positive`。

### 1. 冻结Golden与实际回答

**问题（完整）**

```text
客户现场刚给 B2 遥控器换了一对摇杆，装好后机器人一解锁就自己往一边偏。按 B2 遥控器用户手册，换摇杆后要做校准的话，具体怎么进校准、每个摇杆怎么推、完成后怎么确认已经校准成功？
```

**冻结参考答案（完整，保留原始文字）**

```text
手持遥控但不要触碰摇杆，按下遥控上按键 F1 和 F3 并同时松开，此时遥控器发出连续“嘀\~嘀\~”声（1次/秒）代表已进入校准模式。进入校准模式后将左右摇杆打满舵并旋转数圈，直至“嘀\~嘀\~”声停止，此时校准就绪。单按 F3 一次使校准生效，完成校准。
校准摇杆时，校准前请不要触碰摇杆，进入校准模式才可以动摇杆。校准后可通过 APP 查看校准后的摇杆状态。
```

**冻结Golden evidence字段（原样；摘要不能冒充完整规范）**

```json
[
  {
    "evidence_key_points": [
      "遥控器摇杆校准\n手持遥控但不要触碰摇杆，按下遥控上按键 F1 和 F3 并同时松开，此时遥控器发出连续“嘀\\~嘀\\~”声（1次/秒）代表已进入校准模式。进入校准模式后将左右摇杆打满舵并旋转数圈，直至“嘀\\~嘀\\~”声停止，此时校准就绪。单按 F3 一次使校准生效，完成校准。\n校准摇杆时，校准前请不要触碰摇杆，进入校准模",
      "遥控器摇杆校准\n手持遥控但不要触碰摇杆，按下遥控上按键 F1 和 F3 并同时松开，此时遥控器发出连续“嘀\\~嘀\\~”声（1次/秒）代表已进入校准模式。进入校准模式后将左右摇杆打满舵并旋转数圈，直至“嘀\\~嘀\\~”声停止，此时校准就绪。单按 F3 一次使校准生效，完成校准。\n校准摇杆时，校准前请不要触碰摇杆，进入校准模"
    ],
    "source_chunk_ids": [
      "DOC-003-C-00009",
      "DOC-003-C-00022"
    ]
  }
]
```

**RAG实际回答（完整）**

```text
结论：现有证据不能无保留地认定为“B2 遥控器可直接执行”的校准步骤。校准条目在资料中分别标注为 **R3遥控器** 和 **R1遥控器**，安装摇杆条目也标注 **R3遥控器**；未出现明确的 **B2 校准章节**。请先核对现场遥控器型号/手册版本/页码。相关证据：[DOC-003-C-00009 | S1 | 页4–4]、[DOC-003-C-00022 | S1 | 页10–10]、[DOC-003-C-00008 | S1 | 页3–3]。

若已确认现场 B2 对应章节就是上述校准条目，资料原文步骤为：

1. **进入校准**：手持遥控器但不要触碰摇杆，按下 **F1 和 F3 并同时松开**；出现连续“嘀~嘀~”（1次/秒）表示已进入校准模式。
2. **摇杆操作**：进入校准模式后，将**左右摇杆打满舵并旋转数圈**，直到“嘀~嘀~”声停止，此时为“校准就绪”。
3. **生效**：**单按 F3 一次**使校准生效，完成校准。
4. **确认方式**：资料仅说明“校准后可通过 APP 查看校准后的摇杆状态”，**未给出成功判据、阈值或 APP 中何种状态算成功**。提示音停止只表示“校准就绪”，不是最终生效。

注意：资料没有分别说明左、右摇杆的具体方向、顺序或圈数，只能确认“左右摇杆都要打满舵并旋转数圈”，不能补造具体推法。校准前不要触碰摇杆，进入校准模式后才可动摇杆（[DOC-003-C-00009 | S1 | 页4–4]；[DOC-003-C-00022 | S1 | 页10–10]）。

在型号匹配和“校准成功”判据未确认前，机器人一解锁就偏转的情况下，保守做法是**不要继续解锁运行**，联系宇树官方或取得 B2 对应校准章节后再操作。
```

### 2. 独立原文、范围与等价证据判断

两次原始Judge均PASS，checks[0..4]步骤/安全引用可定位；checks[5]引用“R3遥控器/R1遥控器”来自source_scope，而非它绑定的C00009/C00022/C00008正文。标题实际源分别C00004/C00018，未以独立正文进入Final。

**必要事实逐项链路**

| 必要事实/安全条件 | Corpus原文定位 | Candidate序号 | Rerank序号 | Final条目序号 | Answer与等价范围核查 |
|---|---|---|---|---|---|
| 校准前不触摇杆；F1+F3并同时松开 | DOC-003-C-00009 / PDF 4–4 | 2 | 1 | 1 | 已表达；C00022的R1同文本步骤亦适用其分支 |
| 连续嘀声每秒一次表示已进入校准 | DOC-003-C-00009 / PDF 4–4 | 2 | 1 | 1 | 已表达，转义符规范化后引用可定位 |
| 进入后左右摇杆打满舵、旋转数圈 | DOC-003-C-00009 / PDF 4–4 | 2 | 1 | 1 | 已表达；没有具体方向/顺序/圈数则不补造 |
| 嘀声停止表示校准就绪 | DOC-003-C-00009 / PDF 4–4 | 2 | 1 | 1 | 已表达，未误当生效完成 |
| 单按F3一次使校准生效 | DOC-003-C-00009 / PDF 4–4 | 2 | 1 | 1 | 已表达 |
| APP查看校准后的摇杆状态 | DOC-003-C-00009 / PDF 4–4 | 2 | 1 | 1 | 已表达；手册没有数值成功阈值，不应增加阈值要求 |
| R1/R3属于B2遥控器手册的不同型号章节 | DOC-003-C-00004 / PDF 2–2 | 无 | 无 | 无 | 存在于source_scope来源；不在校准Chunk的content，需与正文引用区分；答案额外要求独立B2章节偏保守 |

### 3. 失败归因、实际程序条件与可优化性

**独立归因：** 评测输入元数据与正文引用合同不一致；不是校准事实检索失败。校准R3/R1条款均在Final，答案完整给步骤，关于必须另找B2章节偏保守：PDF封面与C00005/C00019已说明R1/R3是B2系列；但未授权未知现场直接操作，不能仅凭该措辞制造安全FAIL。

**当前程序的确定路径：** quote_present只在绑定Final.content定位；normalize_display保留R1/R3字符。validate_business_judgment:339–340遇checks[5]的三处标题引用抛ValueError，经providers.py:253转ProviderInvalidResponse。两次finish_reason=stop，均非截断；第二次有纠正反馈但仍犯同错。先判引用合同失败，不进入_score_business、不形成case或bad_case。

**工具箱与可验证假设：** 无需先升级Judge即可在未来授权下按同身份显式resume_source_id恢复，只复用49题成功结果与Q18的generation execution，补这一题Judge（有限纠正可能再一次）。但同输入可能重复标题引用错误，不能保证成功；本轮不执行。若要求离线零调用恢复，现合同下不可以：两份保存JSON均无效，不能删support、换ID、拼标题或改met后入账。

**建议处理：** 保留Partial和技术异常。若修Matcher接纳可信source_scope，或修改Prompt/输入令元数据引用合法，都需明确版本/Identity并禁止旧身份直接混续；单纯重试现有合同的Judge则无需改版本。

### 4. 两次原始Judge响应与确定错误

| Judge尝试 | 原始verdict | 未定位引用 | 其他support |
|---|---|---|---|
| 第1次 | PASS | checks[5].support[0..2]：C00009/R3、C00022/R1、C00008/R3 | 逐条现Matcher检查均可定位 |
| 第2次（一次结构纠正） | PASS | checks[5].support[1..3]：同上三处标题引用 | 逐条现Matcher检查均可定位 |

两个错误都是source_id本身存在，但quote不在该ID的content；不是source_id不存在，也不是“嘀\~”转义、APP大小写、单位、候选丢失或截断造成。第一次和第二次source_scope分别给C00009→C00004/R3、C00022→C00018/R1、C00008→C00004/R3，Canonical标题关系真实；正文与元数据引用角色却未打通。

标题实际Chunk C00004/C00018没有作为Final正文条目，改成标题ID仍不能通过当前quote_present。只把R3/R1标题拼进content会改变冻结执行证据，不能用于旧身份补分。

**同身份恢复可行性：** 只读调用共享validate_evaluation_start/validate_evaluation_resume，使用保存配置/Judge得到OK，已有49行成功case，未有重复子Run；当前源码Prompt/Parser/Matcher身份与保存身份相同。实际未来启动仍必须重新按实时模型/配置和费用预检，以上不是对运行中进程状态或未来成功的保证。create_baseline_run会新建子Run而保留旧Partial；已有Q18 execution使批处理跳过generation，只补score。

**业务独立审查：** 参考答案所列F1/F3、打满舵、旋转数圈、嘀声停止就绪、单按F3生效、APP看状态，答案全部包含；没有凭空编成功阈值。把R1/R3误认为缺少B2对应章节造成不必要谨慎，可另议回答质量，但这不是当前技术异常的抛错原因，不能代替合法Judge判分。
<details><summary>Judge原始响应及保存的错误元数据</summary>

```json
{"verdict":"PASS","checks":[{"check_type":"fact","requirement":"进入摇杆校准模式：手持遥控器但不触碰摇杆，按F1和F3并同时松开，出现连续“嘀~嘀~”（1次/秒）提示音表示已进入校准模式。","met":true,"answer_quotes":["**进入校准**：手持遥控器但不要触碰摇杆，按下 **F1 和 F3 并同时松开**；出现连续“嘀~嘀~”（1次/秒）表示已进入校准模式。"],"support":[{"source_id":"DOC-003-C-00009","quote":"手持遥控但不要触碰摇杆，按下遥控上按键 F1 和 F3 并同时松开，此时遥控器发出连续“嘀\\~嘀\\~”声（1次/秒）代表已进入校准模式。"}]},{"check_type":"fact","requirement":"进入校准模式后，将左右摇杆打满舵并旋转数圈，直至提示音停止，此时为校准就绪。","met":true,"answer_quotes":["2. **摇杆操作**：进入校准模式后，将**左右摇杆打满舵并旋转数圈**，直到“嘀~嘀~”声停止，此时为“校准就绪”。"],"support":[{"source_id":"DOC-003-C-00009","quote":"进入校准模式后将左右摇杆打满舵并旋转数圈，直至“嘀\\~嘀\\~”声停止，此时校准就绪。"}]},{"check_type":"fact","requirement":"单按F3一次使校准生效，完成校准。","met":true,"answer_quotes":["3. **生效**：**单按 F3 一次**使校准生效，完成校准。"],"support":[{"source_id":"DOC-003-C-00009","quote":"单按 F3 一次使校准生效，完成校准。"}]},{"check_type":"fact","requirement":"完成后可通过APP查看校准后的摇杆状态；提示音停止只表示校准就绪，不是最终生效，资料未给出成功阈值。","met":true,"answer_quotes":["4. **确认方式**：资料仅说明“校准后可通过 APP 查看校准后的摇杆状态”，**未给出成功判据、阈值或 APP 中何种状态算成功**。提示音停止只表示“校准就绪”，不是最终生效。"],"support":[{"source_id":"DOC-003-C-00009","quote":"校准后可通过 APP 查看校准后的摇杆状态。"},{"source_id":"DOC-003-C-00009","quote":"此时校准就绪。单按 F3 一次使校准生效，完成校准。"}]},{"check_type":"fact","requirement":"校准前不要触碰摇杆，进入校准模式后才可动摇杆。","met":true,"answer_quotes":["校准前不要触碰摇杆，进入校准模式后才可动摇杆"],"support":[{"source_id":"DOC-003-C-00009","quote":"校准摇杆时，校准前请不要触碰摇杆，进入校准模式才可以动摇杆。"}]},{"check_type":"fact","requirement":"当前现场适用性：对象是B2遥控器换摇杆后机器人解锁偏转；答案在B2对应校准章节/型号匹配与校准成功判据未确认时，不把校准步骤作为无条件现场执行授权，并提示先核对/取得对应章节且不要继续解锁运行。","met":true,"answer_quotes":["结论：现有证据不能无保留地认定为“B2 遥控器可直接执行”的校准步骤。校准条目在资料中分别标注为 **R3遥控器** 和 **R1遥控器**，安装摇杆条目也标注 **R3遥控器**；未出现明确的 **B2 校准章节**。请先核对现场遥控器型号/手册版本/页码。","若已确认现场 B2 对应章节就是上述校准条目，资料原文步骤为：","在型号匹配和“校准成功”判据未确认前，机器人一解锁就偏转的情况下，保守做法是**不要继续解锁运行**，联系宇树官方或取得 B2 对应校准章节后再操作。"],"support":[{"source_id":"DOC-003-C-00009","quote":"R3遥控器"},{"source_id":"DOC-003-C-00022","quote":"R1遥控器"},{"source_id":"DOC-003-C-00008","quote":"R3遥控器"},{"source_id":"DOC-003-C-00009","quote":"校准后可通过 APP 查看校准后的摇杆状态。"}]}],"issues":[],"reason":"回答完整给出了进入校准、左右摇杆打满舵旋转、单按F3生效、APP查看状态等手册步骤，并正确指出提示音停止仅表示校准就绪、资料未给出具体成功阈值；同时基于校准条目标注R3/R1、现场B2型号与成功判据尚未确认，没有把步骤作为无条件现场执行授权，并建议先核对或联系官方且不要继续解锁运行，符合安全边界。","quality":{"correctness":4,"faithfulness":1,"completeness":1}}
```


```json
{
  "phase": "judge",
  "error_type": "ProviderInvalidResponse",
  "error": "VNext Judge合同无效：support is not located in actual full Final",
  "cause_message": "support is not located in actual full Final",
  "retryable": true,
  "request_execution_unknown": false,
  "elapsed_ms": 51949,
  "response_metadata": {
    "finish_reason": "stop",
    "request_id": "4f35cdcb-455e-4710-8c58-158f4130fa93",
    "transport_recovery": null,
    "usage": {
      "call_started_at": "2026-10-21T01:48:23.728798+00:00",
      "completion_tokens": 11091,
      "completion_tokens_details": {
        "reasoning_tokens": 9981
      },
      "latency_ms": 51941,
      "prompt_cache_hit_tokens": 1664,
      "prompt_cache_miss_tokens": 10748,
      "prompt_tokens": 12412,
      "prompt_tokens_details": {
        "cached_tokens": 1664
      },
      "provider": "DeepSeek",
      "request_sha256": "3dbf345cb9b4d2c0ae145c376603e6292d05a899b39856dbb595e868187780da",
      "requested_model": "deepseek-v4-flash",
      "status": "ok",
      "total_tokens": 23503
    },
    "validation_error": {
      "category": "business_contract",
      "message": "support is not located in actual full Final"
    }
  }
}
```

</details>
<details><summary>Judge原始响应及保存的错误元数据</summary>

```json
{"verdict":"PASS","checks":[{"check_type":"fact","requirement":"进入校准模式：手持遥控器但不触碰摇杆，同时按F1和F3并同时松开，出现连续“嘀~嘀~”（1次/秒）表示已进入校准模式。","met":true,"answer_quotes":["**进入校准**：手持遥控器但不要触碰摇杆，按下 **F1 和 F3 并同时松开**；出现连续“嘀~嘀~”（1次/秒）表示已进入校准模式。"],"support":[{"source_id":"DOC-003-C-00009","quote":"手持遥控但不要触碰摇杆，按下遥控上按键 F1 和 F3 并同时松开，此时遥控器发出连续“嘀\\~嘀\\~”声（1次/秒）代表已进入校准模式。"}]},{"check_type":"fact","requirement":"进入校准模式后，将左右摇杆打满舵并旋转数圈，直至“嘀~嘀~”声停止，此时为校准就绪；手册未分别给出左、右摇杆的方向、顺序或圈数，不能补造具体推法。","met":true,"answer_quotes":["2. **摇杆操作**：进入校准模式后，将**左右摇杆打满舵并旋转数圈**，直到“嘀~嘀~”声停止，此时为“校准就绪”。","注意：资料没有分别说明左、右摇杆的具体方向、顺序或圈数，只能确认“左右摇杆都要打满舵并旋转数圈”，不能补造具体推法。"],"support":[{"source_id":"DOC-003-C-00009","quote":"进入校准模式后将左右摇杆打满舵并旋转数圈，直至“嘀\\~嘀\\~”声停止，此时校准就绪。"}]},{"check_type":"fact","requirement":"单按F3一次使校准生效，完成校准。","met":true,"answer_quotes":["3. **生效**：**单按 F3 一次**使校准生效，完成校准。"],"support":[{"source_id":"DOC-003-C-00009","quote":"单按 F3 一次使校准生效，完成校准。"}]},{"check_type":"fact","requirement":"完成后可通过APP查看校准后的摇杆状态；提示音停止仅表示校准就绪，不是最终生效，需再单按F3生效。","met":true,"answer_quotes":["4. **确认方式**：资料仅说明“校准后可通过 APP 查看校准后的摇杆状态”，**未给出成功判据、阈值或 APP 中何种状态算成功**。提示音停止只表示“校准就绪”，不是最终生效。"],"support":[{"source_id":"DOC-003-C-00009","quote":"校准后可通过 APP 查看校准后的摇杆状态。"},{"source_id":"DOC-003-C-00009","quote":"此时校准就绪。单按 F3 一次使校准生效，完成校准。"}]},{"check_type":"fact","requirement":"校准前不要触碰摇杆，进入校准模式后才可动摇杆。","met":true,"answer_quotes":["校准前不要触碰摇杆，进入校准模式后才可动摇杆"],"support":[{"source_id":"DOC-003-C-00009","quote":"校准摇杆时，校准前请不要触碰摇杆，进入校准模式才可以动摇杆。"}]},{"check_type":"fact","requirement":"当前操作适用性：现场是B2遥控器换摇杆后机器人解锁偏转；答案在B2对应校准章节/型号匹配和校准成功判据未确认前，不把上述步骤作为无条件现场执行授权，先要求核对现场遥控器型号/手册版本/页码，并建议不要继续解锁运行、联系官方或取得B2对应章节后再操作。","met":true,"answer_quotes":["结论：现有证据不能无保留地认定为“B2 遥控器可直接执行”的校准步骤。校准条目在资料中分别标注为 **R3遥控器** 和 **R1遥控器**，安装摇杆条目也标注 **R3遥控器**；未出现明确的 **B2 校准章节**。请先核对现场遥控器型号/手册版本/页码。","若已确认现场 B2 对应章节就是上述校准条目，资料原文步骤为：","在型号匹配和“校准成功”判据未确认前，机器人一解锁就偏转的情况下，保守做法是**不要继续解锁运行**，联系宇树官方或取得 B2 对应校准章节后再操作。"],"support":[{"source_id":"DOC-003-C-00009","quote":"遥控器摇杆校准"},{"source_id":"DOC-003-C-00009","quote":"R3遥控器"},{"source_id":"DOC-003-C-00022","quote":"R1遥控器"},{"source_id":"DOC-003-C-00008","quote":"R3遥控器"}],"scope_resolved":false}],"issues":[],"reason":"回答覆盖了进入校准、左右摇杆打满舵旋转、单按F3生效、通过APP查看摇杆状态以及校准前不触碰摇杆等必要事实，并正确提示音停止仅代表校准就绪、不能据此认定校准成功。针对现场B2换摇杆后解锁偏转，回答在型号/章节和成功判据未核清前没有把步骤作为无条件现场执行授权，要求先核对并停止继续解锁/联系官方，符合安全边界；也未虚构左右摇杆的具体方向或圈数。","quality":{"correctness":4,"faithfulness":1.0,"completeness":1.0}}
```


```json
{
  "phase": "judge",
  "error_type": "ProviderInvalidResponse",
  "error": "VNext Judge合同无效：support is not located in actual full Final",
  "cause_message": "support is not located in actual full Final",
  "retryable": false,
  "request_execution_unknown": false,
  "elapsed_ms": 57855,
  "response_metadata": {
    "finish_reason": "stop",
    "request_id": "620713da-d6a5-44cb-901b-5e036d93aaf2",
    "transport_recovery": null,
    "usage": {
      "call_started_at": "2026-10-21T01:49:16.694760+00:00",
      "completion_tokens": 13131,
      "completion_tokens_details": {
        "reasoning_tokens": 11913
      },
      "latency_ms": 57848,
      "prompt_cache_hit_tokens": 2304,
      "prompt_cache_miss_tokens": 11376,
      "prompt_tokens": 13680,
      "prompt_tokens_details": {
        "cached_tokens": 2304
      },
      "provider": "DeepSeek",
      "request_sha256": "143afdf9f898549f907062c1dc8885e6dc3a025943cdd676549550f5545418bf",
      "requested_model": "deepseek-v4-flash",
      "status": "ok",
      "total_tokens": 26811
    },
    "validation_error": {
      "category": "business_contract",
      "message": "support is not located in actual full Final"
    }
  }
}
```

</details>

### 5. 可复查的完整阶段证据

<details><summary>各阶段来源顺序、完整候选正文、完整Final与规范原文</summary>

**候选→重排→Final顺序**

```json
{
  "candidates": [
    {
      "position": 1,
      "chunk_id": "DOC-003-C-00022",
      "parent_chunk_id": "DOC-003-P-00020",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 1.0
    },
    {
      "position": 2,
      "chunk_id": "DOC-003-C-00009",
      "parent_chunk_id": "DOC-003-P-00009",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.9987
    },
    {
      "position": 3,
      "chunk_id": "DOC-003-C-00025",
      "parent_chunk_id": "DOC-003-P-00023",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.9598
    },
    {
      "position": 4,
      "chunk_id": "DOC-003-C-00015",
      "parent_chunk_id": "DOC-003-P-00015",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.9298
    },
    {
      "position": 5,
      "chunk_id": "DOC-003-C-00008",
      "parent_chunk_id": "DOC-003-P-00008",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.8772
    },
    {
      "position": 6,
      "chunk_id": "DOC-002-C-00046",
      "parent_chunk_id": "DOC-002-P-00041",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.8581
    },
    {
      "position": 7,
      "chunk_id": "DOC-002-C-00039",
      "parent_chunk_id": "DOC-002-P-00034",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.8306
    },
    {
      "position": 8,
      "chunk_id": "DOC-003-C-00016",
      "parent_chunk_id": "DOC-003-P-00015",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.8297
    },
    {
      "position": 9,
      "chunk_id": "DOC-003-C-00027",
      "parent_chunk_id": "DOC-003-P-00024",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.4367
    },
    {
      "position": 10,
      "chunk_id": "DOC-002-C-00008",
      "parent_chunk_id": "DOC-002-P-00006",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4307
    },
    {
      "position": 11,
      "chunk_id": "DOC-003-C-00019",
      "parent_chunk_id": "DOC-003-P-00017",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.4304
    },
    {
      "position": 12,
      "chunk_id": "DOC-002-C-00031",
      "parent_chunk_id": "DOC-002-P-00026",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4278
    }
  ],
  "reranked": [
    {
      "position": 1,
      "chunk_id": "DOC-003-C-00009",
      "parent_chunk_id": "DOC-003-P-00009",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.9066644681410003,
      "rerank_score": 0.9066644681410003
    },
    {
      "position": 2,
      "chunk_id": "DOC-003-C-00022",
      "parent_chunk_id": "DOC-003-P-00020",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.9034626220945772,
      "rerank_score": 0.9034626220945772
    },
    {
      "position": 3,
      "chunk_id": "DOC-003-C-00008",
      "parent_chunk_id": "DOC-003-P-00008",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.7534280854431077,
      "rerank_score": 0.7534280854431077
    },
    {
      "position": 4,
      "chunk_id": "DOC-003-C-00025",
      "parent_chunk_id": "DOC-003-P-00023",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.6652972655271232,
      "rerank_score": 0.6652972655271232
    },
    {
      "position": 5,
      "chunk_id": "DOC-003-C-00016",
      "parent_chunk_id": "DOC-003-P-00015",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.6283950011850056,
      "rerank_score": 0.6283950011850056
    },
    {
      "position": 6,
      "chunk_id": "DOC-003-C-00019",
      "parent_chunk_id": "DOC-003-P-00017",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.6262040845862262,
      "rerank_score": 0.6262040845862262
    },
    {
      "position": 7,
      "chunk_id": "DOC-003-C-00015",
      "parent_chunk_id": "DOC-003-P-00015",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.588272532195583,
      "rerank_score": 0.588272532195583
    },
    {
      "position": 8,
      "chunk_id": "DOC-002-C-00031",
      "parent_chunk_id": "DOC-002-P-00026",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.5771813896736582,
      "rerank_score": 0.5771813896736582
    },
    {
      "position": 9,
      "chunk_id": "DOC-002-C-00046",
      "parent_chunk_id": "DOC-002-P-00041",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.5743011639870647,
      "rerank_score": 0.5743011639870647
    },
    {
      "position": 10,
      "chunk_id": "DOC-003-C-00027",
      "parent_chunk_id": "DOC-003-P-00024",
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "score": 0.5561098097169753,
      "rerank_score": 0.5561098097169753
    },
    {
      "position": 11,
      "chunk_id": "DOC-002-C-00039",
      "parent_chunk_id": "DOC-002-P-00034",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.4427239493828722,
      "rerank_score": 0.4427239493828722
    },
    {
      "position": 12,
      "chunk_id": "DOC-002-C-00008",
      "parent_chunk_id": "DOC-002-P-00006",
      "document_id": "DOC-002",
      "product": "B2 四足机器人",
      "score": 0.44120418063850675,
      "rerank_score": 0.44120418063850675
    }
  ],
  "final": [
    {
      "position": 1,
      "chunk_id": "DOC-003-C-00009",
      "parent_chunk_id": "DOC-003-P-00009",
      "matched_child_ids": [
        "DOC-003-C-00009"
      ],
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "source_scope": {
        "heading": "R3遥控器",
        "page_start": 2,
        "quote": "R3遥控器",
        "source_id": "DOC-003-C-00004"
      },
      "score": 0.9066644681410003,
      "rerank_score": 0.9066644681410003
    },
    {
      "position": 2,
      "chunk_id": "DOC-003-C-00022",
      "parent_chunk_id": "DOC-003-P-00020",
      "matched_child_ids": [
        "DOC-003-C-00022"
      ],
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "source_scope": {
        "heading": "R1遥控器",
        "page_start": 9,
        "quote": "R1遥控器",
        "source_id": "DOC-003-C-00018"
      },
      "score": 0.9034626220945772,
      "rerank_score": 0.9034626220945772
    },
    {
      "position": 3,
      "chunk_id": "DOC-003-C-00008",
      "parent_chunk_id": "DOC-003-P-00008",
      "matched_child_ids": [
        "DOC-003-C-00008"
      ],
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "source_scope": {
        "heading": "R3遥控器",
        "page_start": 2,
        "quote": "R3遥控器",
        "source_id": "DOC-003-C-00004"
      },
      "score": 0.7534280854431077,
      "rerank_score": 0.7534280854431077
    },
    {
      "position": 4,
      "chunk_id": "DOC-003-C-00025",
      "parent_chunk_id": "DOC-003-P-00023",
      "matched_child_ids": [
        "DOC-003-C-00025"
      ],
      "document_id": "DOC-003",
      "product": "B2 遥控器",
      "source_scope": {
        "heading": "R1遥控器",
        "page_start": 9,
        "quote": "R1遥控器",
        "source_id": "DOC-003-C-00018"
      },
      "score": 0.6652972655271232,
      "rerank_score": 0.6652972655271232
    }
  ]
}
```

**全部候选正文（用于核查等价来源，而非只看ID）**
候选1：`DOC-003-C-00022` / `B2 遥控器`

```text
遥控器摇杆校准
手持遥控但不要触碰摇杆，按下遥控上按键 F1 和 F3 并同时松开，此时遥控器发出连续“嘀\~嘀\~”声（1次/秒）代表已进入校准模式。进入校准模式后将左右摇杆打满舵并旋转数圈，直至“嘀\~嘀\~”声停止，此时校准就绪。单按 F3 一次使校准生效，完成校准。
校准摇杆时，校准前请不要触碰摇杆，进入校准模式才可以动摇杆。校准后可通过 App 查看校准后的摇杆状态。
```

候选2：`DOC-003-C-00009` / `B2 遥控器`

```text
遥控器摇杆校准
手持遥控但不要触碰摇杆，按下遥控上按键 F1 和 F3 并同时松开，此时遥控器发出连续“嘀\~嘀\~”声（1次/秒）代表已进入校准模式。进入校准模式后将左右摇杆打满舵并旋转数圈，直至“嘀\~嘀\~”声停止，此时校准就绪。单按 F3 一次使校准生效，完成校准。
校准摇杆时，校准前请不要触碰摇杆，进入校准模式才可以动摇杆。校准后可通过 APP 查看校准后的摇杆状态。
```

候选3：`DOC-003-C-00025` / `B2 遥控器`

```text
R1 遥控器基本操作
首次使用遥控器需要在 Unitree Explore App 上进行遥控器绑定，【设置】->【遥控器设置】，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。
遥控器开机并且与 B2 连接成功后，左侧面数据传输灯全亮，这就意味着遥控器与 B2 数传模块已连接，此时可通过遥控器控制 B2。使用遥控器摇杆操控 B2 时，摇杆的操控方式如下所示：
左摇杆
右摇杆
(AI 运控模式下不支持抬头低头)
\- 摇杆回中/中位：遥控器的摇杆处于中间位置。
11
B2 遥控器使用手册
- 摇杆杆量：遥控器摇杆偏离摇杆中位的偏移量。
- 墙面、门等阻挡物会极大削弱机器狗和遥控模块之间的信号，请务必在空旷的场地操作机器狗。
© 2024 宇树科技 版权所有
机器狗参照示意图：
| 侧视图 | 俯视图 | 正视图
机器狗 |  |  | 
参照图 |  |  |
按键 | 效果
左摇杆 | 前后左右
右摇杆 | 左右旋转
姿态切换
START | 解除锁定
灵动模式(默认)
L2 (长按) + A (单击) | 站立锁定/卧倒姿态切换
L2 (长按) + B (单击) | 阻尼模式(软急停)
R1 (双
```

候选4：`DOC-003-C-00015` / `B2 遥控器`

```text
R3 遥控器基本操作
首次使用遥控器需要在 Unitree Explore App 上进行遥控器绑定，【设置】->【遥控器设置】-打开遥控器开关，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。
遥控器开机并且与 B2 连接成功后，右侧 DL 指示灯亮，这就意味着遥控器与 B2 数传模块已连接，此时可通过遥控器控制 B2。使用遥控器摇杆操控 B2 时，摇杆的操控方式如下所示：
左摇杆
右摇杆
(AI 运控模式下不支持抬头低头)
- 摇杆回中/中位：遥控器的摇杆处于中间位置。
- 摇杆杆量：遥控器摇杆偏离摇杆中位的偏移量。
- 墙面、门等阻挡物会极大削弱机器狗和遥控模块之间的信号，请务必在空旷的场地操作机器狗。
© 2024 宇树科技 版权所有
6
机器狗参照示意图：
| 侧视图 | 俯视图 | 正视图
机器狗 |  |  | 
参照图 |  |  |
按键 | 效果
左摇杆 | 前后左右
右摇杆 | 左右旋转
姿态切换
START | 解除锁定
灵动模式(默认)
L2 (长按) + A (单击) | 站立锁定/卧倒姿态切换
L2 (长按) + B (单击) | 阻尼模式(软急停)
R1 (双击) | 经
```

候选5：`DOC-003-C-00008` / `B2 遥控器`

```text
安装摇杆
Step1：取出摇杆。如同所示，用右手将遥控器平稳缓慢的拉出，取出收纳槽当中的2个摇杆。
Step2：安装摇杆。如图所示，按照顺时针方向，将摇杆固定在遥控器上，拧紧。
B2 遥控器使用手册
- 如需收纳，请拆下摇杆后放回收纳槽中。
© 2024 宇树科技 版权所有 3
```

候选6：`DOC-002-C-00046` / `B2 四足机器人`

```text
- 机器人容易摔倒，开机无法站立
没有使用正确的开机姿势，导致机身电机角度错误，使用正确的开机姿势后重新开机。若重启机器人无法解决问题，此时需要按照Unitree Explore App相关步骤对机器人关节重新进行标定。
注意：B2 出厂后默认已经完成标定，正常使用请勿进行关节标定！！！在 B2 出现异常情况后请先咨询 Unitree 官方技术支持后确定是否需要重新标定关节！！！
App 关节标定入口为 [设置] -> [数据] -> [机器狗] -> [标定]。
```

候选7：`DOC-002-C-00039` / `B2 四足机器人`

```text
关闭B2
关机前，请务必确保机器人站立在平整地面上，确保机器人处于静态站立状态（机器人机身位置处于开机起立后的初始状态，机身水平，手柄无任何操作，静态站立时的状态）。
\- 按2次L2+A键，机器人依次完成关节锁定，卧倒动作；
\- 机器人进入卧倒状态后，先短按电源键再长按电源键3秒以上关机。
关机后，请按照机身摆放要求，摆放好机器人大小腿和髋关节位置，为下次开机做准备。若长时间不使用B2，请及时取出电池包：往外拉出电池包提带，电池包即可弹出取下。
请确保机器人处于趴下状态（卧倒状态或阻尼状态）下进行关机，否则机器人关机掉电后会重重地摔在地上，可能会造成机身损坏，并存在一定的安全隐患！若开机失败，请检查机器人机身摆放是否正确。
\- 运动关节处小心夹手，请小心谨慎！
```

候选8：`DOC-003-C-00016` / `B2 遥控器`

```text
后左右
右摇杆 | 左右旋转
姿态切换
START | 解除锁定
灵动模式(默认)
L2 (长按) + A (单击) | 站立锁定/卧倒姿态切换
L2 (长按) + B (单击) | 阻尼模式(软急停)
R1 (双击) | 经典模式
L2 (长按) + START (单击) | 跑步模式
L2 (长按) + X (单击) | 摔倒恢复站立
X (单击) | 视觉模式
SELECT | 摆姿势
L2 (双击) | 低速档
L1 (双击) | 高速档
B2 遥控器使用手册
© 2024 宇树科技 版权所有
7
功能开关
F3 (短按 3 次) | 音效/震动切换
F1 (短按 3 次) | 音效/震动开关
B2 环境参数
最大爬坡角度 | 低速档 | <45°
高速档 | <30°
台阶高度 | <25cm
越障 | <40m
● 恢复站立安全说明：恢复站立功能需要翻身空间，机器狗周围直径 2 米圆圈内请勿有人或物品，避免不必要的人员伤亡和财产损失，否则宇树科技不承担所引发的一切损失和后果！
\- 前跳功能请访问 Unitree Explore App 触发，前跳功能视为危险动作，请开启时务必确保 B2 前方直径 2 米的半圆内没有任何障碍物（尤其不能有人）若因为非规范操作造成人员伤亡或财
```

候选9：`DOC-003-C-00027` / `B2 遥控器`

```text
修订历史
版本=2.1；日期=2025-4-18；修改内容=删除常规运控、新增灵动模式
版本=2.0；日期=2024-12-9；修改内容=增加 R3 遥控器使用说明
版本=1.0；日期=2023-12-20；修改内容=初始版本
B2 遥控器使用手册
© 2024 宇树科技 版权所有
13
```

候选10：`DOC-002-C-00008` / `B2 四足机器人`

```text
安全须知
B2是一款具备全天候作业、强劲负载与扩展空间、多维感知、全场景覆盖、强劲算力与精准洞察等特点，面向行业级应用的四足机器人，可以为您提供更高效、智能的解决方案。
1. 本产品并非玩具，不适合未满 18 岁的人士使用。请勿让儿童接触，在有儿童出现的场景操作时务必特别小心注意。
2. 您有义务知悉您所在区域的法律，并遵守相关法律和法规。
3. 本手册是新玩家操纵机器人的入门章节，新玩家可以通过阅读此节快速掌握如何使用手柄控制机器人的方法，使机器人表现出卓越的运动性能。本手册也是老玩家需时常查阅的章节，老玩家可通过反复查阅本章内容，抓住操作机器人的要领，举一反三，并且熟知哪些动作是不推荐使用。
4. 当用户在开发者模式下运行自己开发的程序：高层（应用层）开发时遥控器命令仍有效，此时若高层API命令和遥控器命令一起发送给机器人，两种命令机器人都会执行，可能会导致机器人失稳，请务必根据机器人运行状态判断是否需要使用遥控器
```

候选11：`DOC-003-C-00019` / `B2 遥控器`

```text
简介
遥控器属于 B2 遥控模块的一部分，遥控手柄内置数传模块、蓝牙模块。机器人与遥控器可以通过 Unitree Explore App 进行绑定，绑定成功后开机即可自动连接。可操纵机器人在站立时实现 3 轴姿态与 3 轴位置稳定全控，还可以操纵机器人在平整地面上实现前进后退、左右侧移、原地转弯、按一定规则行走（直线，圆形，线，矩形）、上下斜坡/台阶等。遥控手柄采用更加容易持握的设计，结构符合人体工程学，手感更舒适。
```

候选12：`DOC-002-C-00031` / `B2 四足机器人`

```text
(1) 安装电池包
将 B2 放在平坦的地面上，将电池包从机器人侧面插入电池槽，注意安装方向，防呆接口朝上，如无法完全插入电池包，请调整电池包方向，不要强行按压，以免损坏电池接口和卡扣，当听到“咔哒\~”声，电池包安装完成。请确保卡扣卡到位！
```

**完整Final（Parent展开后的真实模型输入正文）**
Final 1：`DOC-003-C-00009` / Parent `DOC-003-P-00009` / `宇树_B2遥控器使用说明_中文版.pdf` / PDF 4–4；source_scope={"heading": "R3遥控器", "page_start": 2, "quote": "R3遥控器", "source_id": "DOC-003-C-00004"}

```text
遥控器摇杆校准
手持遥控但不要触碰摇杆，按下遥控上按键 F1 和 F3 并同时松开，此时遥控器发出连续“嘀\~嘀\~”声（1次/秒）代表已进入校准模式。进入校准模式后将左右摇杆打满舵并旋转数圈，直至“嘀\~嘀\~”声停止，此时校准就绪。单按 F3 一次使校准生效，完成校准。
校准摇杆时，校准前请不要触碰摇杆，进入校准模式才可以动摇杆。校准后可通过 APP 查看校准后的摇杆状态。
```

Final 2：`DOC-003-C-00022` / Parent `DOC-003-P-00020` / `宇树_B2遥控器使用说明_中文版.pdf` / PDF 10–10；source_scope={"heading": "R1遥控器", "page_start": 9, "quote": "R1遥控器", "source_id": "DOC-003-C-00018"}

```text
遥控器摇杆校准
手持遥控但不要触碰摇杆，按下遥控上按键 F1 和 F3 并同时松开，此时遥控器发出连续“嘀\~嘀\~”声（1次/秒）代表已进入校准模式。进入校准模式后将左右摇杆打满舵并旋转数圈，直至“嘀\~嘀\~”声停止，此时校准就绪。单按 F3 一次使校准生效，完成校准。
校准摇杆时，校准前请不要触碰摇杆，进入校准模式才可以动摇杆。校准后可通过 App 查看校准后的摇杆状态。
```

Final 3：`DOC-003-C-00008` / Parent `DOC-003-P-00008` / `宇树_B2遥控器使用说明_中文版.pdf` / PDF 3–3；source_scope={"heading": "R3遥控器", "page_start": 2, "quote": "R3遥控器", "source_id": "DOC-003-C-00004"}

```text
安装摇杆
Step1：取出摇杆。如同所示，用右手将遥控器平稳缓慢的拉出，取出收纳槽当中的2个摇杆。
Step2：安装摇杆。如图所示，按照顺时针方向，将摇杆固定在遥控器上，拧紧。
B2 遥控器使用手册
- 如需收纳，请拆下摇杆后放回收纳槽中。
© 2024 宇树科技 版权所有 3
```

Final 4：`DOC-003-C-00025` / Parent `DOC-003-P-00023` / `宇树_B2遥控器使用说明_中文版.pdf` / PDF 11–13；source_scope={"heading": "R1遥控器", "page_start": 9, "quote": "R1遥控器", "source_id": "DOC-003-C-00018"}

```text
R1 遥控器基本操作
首次使用遥控器需要在 Unitree Explore App 上进行遥控器绑定，【设置】->【遥控器设置】，输入对应的遥控器编码，即可和机器狗上的数传模块进行绑定。
遥控器开机并且与 B2 连接成功后，左侧面数据传输灯全亮，这就意味着遥控器与 B2 数传模块已连接，此时可通过遥控器控制 B2。使用遥控器摇杆操控 B2 时，摇杆的操控方式如下所示：
左摇杆
右摇杆
(AI 运控模式下不支持抬头低头)
\- 摇杆回中/中位：遥控器的摇杆处于中间位置。
11
B2 遥控器使用手册
- 摇杆杆量：遥控器摇杆偏离摇杆中位的偏移量。
- 墙面、门等阻挡物会极大削弱机器狗和遥控模块之间的信号，请务必在空旷的场地操作机器狗。
© 2024 宇树科技 版权所有
机器狗参照示意图：
| 侧视图 | 俯视图 | 正视图
机器狗 |  |  | 
参照图 |  |  |
按键 | 效果
左摇杆 | 前后左右
右摇杆 | 左右旋转
姿态切换
START | 解除锁定
灵动模式(默认)
L2 (长按) + A (单击) | 站立锁定/卧倒姿态切换
L2 (长按) + B (单击) | 阻尼模式(软急停)
R1 (双击) | 经典模式
L2 (长按) + START (单击) | 跑步模式
L2 (长按) + X (单击) | 摔倒恢复站立
X (单击) | 视觉模式
SELECT | 摆姿势
L2 (双击) | 低速档
L1 (双击) | 高速档
© 2024 宇树科技 版权所有
12
B2 环境参数
最大爬坡角度 | 低速档 | < 45°
高速档 | < 30°
台阶高度 | < 25cm
越障 | < 40m
● 恢复站立安全说明：恢复站立功能需要翻身空间，机器狗周围直径 2 米圆圈内请勿有人或物品，避免不必要的人员伤亡和财产损失，否则宇树科技不承担所引发的一切损失和后果！
\- 前跳功能请访问 Unitree Explore App 触发，前跳功能视为危险动作，请开启时务必确保 B2 前方直径 2 米的半圆内没有任何障碍物（尤其不能有人）若因为非规范操作造成人员伤亡或财产损失，宇树科技不承担所引发的一切损失和后果！
```

**本题规范原文与元数据（Corpus完整Child）**
`DOC-003-C-00004`；B2 遥控器；PDF 2–2；version=None

```text
R3遥控器
```

`DOC-003-C-00009`；B2 遥控器；PDF 4–4；version=None

```text
遥控器摇杆校准
手持遥控但不要触碰摇杆，按下遥控上按键 F1 和 F3 并同时松开，此时遥控器发出连续“嘀\~嘀\~”声（1次/秒）代表已进入校准模式。进入校准模式后将左右摇杆打满舵并旋转数圈，直至“嘀\~嘀\~”声停止，此时校准就绪。单按 F3 一次使校准生效，完成校准。
校准摇杆时，校准前请不要触碰摇杆，进入校准模式才可以动摇杆。校准后可通过 APP 查看校准后的摇杆状态。
```

`DOC-003-C-00022`；B2 遥控器；PDF 10–10；version=None

```text
遥控器摇杆校准
手持遥控但不要触碰摇杆，按下遥控上按键 F1 和 F3 并同时松开，此时遥控器发出连续“嘀\~嘀\~”声（1次/秒）代表已进入校准模式。进入校准模式后将左右摇杆打满舵并旋转数圈，直至“嘀\~嘀\~”声停止，此时校准就绪。单按 F3 一次使校准生效，完成校准。
校准摇杆时，校准前请不要触碰摇杆，进入校准模式才可以动摇杆。校准后可通过 App 查看校准后的摇杆状态。
```

</details>

## 只读性与验证记录

- 本轮Provider调用0；没有Baseline重跑、真实Judge、Embedding、Rerank、Agent generate、数据库写事务、Golden/SPEC/代码修改。
- 十道原始业务Judge经现Parser只读重验全部通过；十题Corpus/Final/候选Canonical均通过；两份Q18响应均复现同一引用定位异常，逐个support核查准确定位三处标题引用。
- 16项知识制品哈希及四PDF sources核验通过；冻结Snapshot双表副本内容一致。完整报告保存前后保护文件SHA复核另列于末尾。
- 没有将本报告的人工归因写入bad_cases，没有把离线选择演算冒充真实生成成功。

数据库审计读取时SHA256：`983488ce11505c8d1e8e94677a6619a8b48f0bed23ecf57cccc869f0629d0e46`。

最终文件验证：11/11题的完整问题、参考答案、实际回答、全部候选及Final正文和原始Judge响应均已逐项核对包含；Q18两次响应均定位到同一组三处标题引用；所有源码链接行号在当前文件内有效。17项保护文件（数据库、代码、SPEC与知识制品）SHA前后相同，数据库SHA亦与本次首次完整性采样相同；数据库仍49个完成判分、10个业务FAIL、1个技术异常/Partial。本轮仅新增本目录两份Markdown。
