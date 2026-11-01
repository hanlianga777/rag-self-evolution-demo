# 008b：Agent 输入补齐与规划器状态修复

状态：本单已完成。相关专项72项全部通过；全量1218个方法，1064通过、116未通过、38跳过，比008a少1个未通过方法，无新增失败。没有付费调用或正式库写入。No SPEC Change。

## 1. 从断点接着做

第一次开始时工作区干净，没有008b半成品。代码和7项新增测试完成后额度中断，值班脚本已保存为 `a2467a4`（“自动值班进行中，未完成，已做部分”）。恢复后读取该成果并继续全量测试、demo核对和报告，没有重写已完成的代码，没有重跑007/007b已花钱的步骤。来源：只读 `git log`、`git show --stat a2467a4`、现有文件和测试输出。

## 2. 改了哪些文件，为什么

- `backend/app/agent_inputs.py`：从保存的Trace、冻结题和Judge检查项计算客观事实；统一本轮冻结题来源。只读取已保存的复核状态和票数，不读取 `baseline_review.cases[].analysis`。
- `backend/app/optimization.py`：实际生成路径复用上述输入，每道题增加 `retrieval_facts`；原有题号、问题、产品自动归因和理由保留。
- `backend/app/agent_coverage.py`：同时接收 `ready` 和旧 `exploratory`；保留实际记录校验，提案不算真实已覆盖。规划诊断改用同一份冻结题。
- `backend/app/main.py`：列表复用规划已算出的诊断；没有预计算结果时，按同一份冻结题构造。
- `backend/scripts/preview_agent_input.py`：通用只读展示脚本。SQLite 使用 `mode=ro` 和 `PRAGMA query_only=ON`，只在内存拼首次A/B/C完整提示词及规划回放，不调用模型、不创建实验。
- `backend/tests/test_task008b_agent_input.py`：7项模拟测试，覆盖三种位置、父段包含子段、人工analysis隔离、实际生成请求接线、只读脚本、ready兼容、真实覆盖计数、缺记录阻断及冻结诊断复用。所有数据库在临时目录自动清除。
- 本报告及最终全量比较表；完成后普通mv归档本任务单。

没有改前端、题目、判分、门槛、合格规则、15个参数范围、SPEC或 `指挥/当前任务.md`。没有运行修改仓库状态的git命令，保存与推送交值班脚本。

### 字段和缺记录口径

`retrieval_facts.standard_evidence_positions[]` 按冻结题的标准chunk ID去重，`candidates / reranked / final` 是保存列表里从1开始的位置；父段保存的 `matched_child_ids` 也用于对应子段。完整列表中找不到写“未进入”；列表未保存、条目缺ID或Trace未完成时，不能证明未进入，写“记录缺失”。不以文字相似度猜chunk ID或重跑检索。

`candidate_k / top_k` 来自本次保存的Trace配置，缺字段时用该Baseline冻结配置，不用当前草稿或默认值补造。`unmet_required_points` 来自 `judge_result.checks[].met=false`，有冻结 `required_checks` 时只收必答项，必答判分记录不全则写“记录缺失”；不把可选加分项当必答遗漏。`baseline_review` 只投影产品保存的复核终态、`failed_votes / total_votes`；没有完整终态/票数时写“记录缺失”，不取人工analysis。

诊断的标准原文优先取本轮冻结题；旧题卷没有原文时，保留原生成路径从该错题已保存 `standard_evidence` 读取的兼容做法。chunk ID位置仍只从冻结题提取；没有冻结ID则写“记录缺失”。原有缺候选、缺最终内容、缺判分等阻断仍在。

## 3. 只读起点与实际Agent输入

确认起点仍是 `EVAL-20261101155246923769`，题卷 `GD-20261101151940`。现有接口 `/api/overview`、`/api/optimization?light=true&planning=true`、`/api/pipeline`、`/api/evaluation?light=true` 均返回这两个ID；没有当前实验（`current_experiment_id=null`）。来源：实际本机GET和正式库只读查询。

展示命令（默认只打印以下5道题；加 `--full` 打印完整system/user和规划回放）：

```sh
python3 backend/scripts/preview_agent_input.py --baseline-id EVAL-20261101155246923769
python3 backend/scripts/preview_agent_input.py --baseline-id EVAL-20261101155246923769 --full
```

已在内存重建完整提示词：首次A/B/C，历史方案为空，标签为A/B/C，与当前尚无实验的起点一致。正式数据没有调用 `OptimizationAgent.generate`，没有claim、新实验或检索/模型请求。以下是完整提示词 `bad_cases` 部分的原始字段和值（仅JSON缩进便于阅读），不是人工补写的分析：

```json
[
  {
    "id": "BC-EVAL-20261101155246923769-CSV-20261101100758945425-29",
    "question_id": "CSV-20261101100758945425-29",
    "question": "客户准备重新使用B2，我要按用户手册做一次不带电检查。具体要检查哪些项目？",
    "diagnosis_category": "检索失败",
    "reason": "第1、2、3段标准证据未进入该次候选，查找环节没有找全。",
    "retrieval_facts": {
      "standard_evidence_positions": [
        {
          "chunk_id": "DOC-002-C-00056",
          "candidates": "未进入",
          "reranked": "未进入",
          "final": "未进入"
        }
      ],
      "candidate_k": 12,
      "top_k": 4,
      "unmet_required_points": [
        "检查结构：机身、关节及连接处是否完好",
        "检查电池包接口、安装和外壳",
        "检查遥控器摇杆中位、异物和按键卡顿"
      ],
      "baseline_review": {
        "conclusion": "真错题",
        "failed_votes": 3,
        "total_votes": 3
      }
    }
  },
  {
    "id": "BC-EVAL-20261101155246923769-CSV-20261101100758945425-27",
    "question_id": "CSV-20261101100758945425-27",
    "question": "这层楼昨晚重新摆了桌椅，KIRA B50再自己清洁前，这种变化要怎么处理？",
    "diagnosis_category": "检索噪声",
    "reason": "标准证据已全部进入候选，但第1段未进入最终内容，筛选时漏掉了。",
    "retrieval_facts": {
      "standard_evidence_positions": [
        {
          "chunk_id": "DOC-001-C-00096",
          "candidates": 7,
          "reranked": 12,
          "final": "未进入"
        }
      ],
      "candidate_k": 12,
      "top_k": 4,
      "unmet_required_points": [
        "地图不具备自学习功能",
        "细微布局改动不成问题",
        "布局重大变化时必须重新示教该路线"
      ],
      "baseline_review": {
        "conclusion": "真错题",
        "failed_votes": 3,
        "total_votes": 3
      }
    }
  },
  {
    "id": "BC-EVAL-20261101155246923769-CSV-20261101100758945425-24",
    "question_id": "CSV-20261101100758945425-24",
    "question": "哎，操作员准备往 KIRA B 50 里加清洁剂跑一遍，怕乱用出问题。手册里对使用清洁剂运行这块的一般安全提示是怎么说的？",
    "diagnosis_category": "检索失败",
    "reason": "第1、2段标准证据未进入该次候选，查找环节没有找全。",
    "retrieval_facts": {
      "standard_evidence_positions": [
        {
          "chunk_id": "DOC-001-C-00022",
          "candidates": "未进入",
          "reranked": "未进入",
          "final": "未进入"
        }
      ],
      "candidate_k": 12,
      "top_k": 4,
      "unmet_required_points": [
        "不得未稀释使用推荐的洗涤剂",
        "遵守制造商使用、处置和警告说明"
      ],
      "baseline_review": {
        "conclusion": "真错题",
        "failed_votes": 3,
        "total_votes": 3
      }
    }
  },
  {
    "id": "BC-EVAL-20261101155246923769-CSV-20261101100758945425-06",
    "question_id": "CSV-20261101100758945425-06",
    "question": "客户操作工准备对 KIRA B 50 做日常外部清洁，想直接拿湿抹布擦机身和对接站。按说明书，做这种清洁前在电气安全上有什么必须注意的？尤其是电击危险这块，是不是得先断电、拔插头？",
    "diagnosis_category": "检索噪声",
    "reason": "标准证据已全部进入候选，但第3段未进入最终内容，筛选时漏掉了。",
    "retrieval_facts": {
      "standard_evidence_positions": [
        {
          "chunk_id": "DOC-001-C-00181",
          "candidates": 2,
          "reranked": 1,
          "final": 1
        },
        {
          "chunk_id": "DOC-001-C-00204",
          "candidates": 4,
          "reranked": 2,
          "final": 2
        },
        {
          "chunk_id": "DOC-001-C-00017",
          "candidates": 11,
          "reranked": 6,
          "final": "未进入"
        }
      ],
      "candidate_k": 12,
      "top_k": 4,
      "unmet_required_points": [
        "不得用湿手触及电源插头或插座"
      ],
      "baseline_review": {
        "conclusion": "真错题",
        "failed_votes": 3,
        "total_votes": 3
      }
    }
  },
  {
    "id": "BC-EVAL-20261101155246923769-CSV-20261101100758945425-04",
    "question_id": "CSV-20261101100758945425-04",
    "question": "KIRA B 50准备停用三个月再用，按手册长期存放时要注意哪些要求，蓄电池在存放前和存放期间怎么维护？",
    "diagnosis_category": "检索噪声",
    "reason": "标准证据已全部进入候选，但第1段未进入最终内容，筛选时漏掉了。",
    "retrieval_facts": {
      "standard_evidence_positions": [
        {
          "chunk_id": "DOC-001-C-00180",
          "candidates": 10,
          "reranked": 5,
          "final": "未进入"
        },
        {
          "chunk_id": "DOC-001-C-00185",
          "candidates": 1,
          "reranked": 3,
          "final": 3
        }
      ],
      "candidate_k": 12,
      "top_k": 4,
      "unmet_required_points": [
        "只在室内存放设备"
      ],
      "baseline_review": {
        "conclusion": "真错题",
        "failed_votes": 3,
        "total_votes": 3
      }
    }
  }
]
```

## 4. 规划器内存回放

基于这5题和Baseline冻结的15个参数，未保存任何提案。结果：`total=5`、`planned_count=5`、`covered_count=0`、`status=incomplete`、`provider_calls=0`，生成2条提案：

| 标签 | 实际改参 | 目标题 | 来源 |
| --- | --- | --- | --- |
| A | candidate_k：12→24 | Q29、Q24 | 原有候选召回模板，保存的候选未含标准证据 |
| B | top_k：4→6 | Q27、Q06、Q04 | 原有上下文选择模板，标准证据已进候选但没进最终内容 |

15项起点：

```json
{
  "candidate_k": 12,
  "top_k": 4,
  "min_score": 0,
  "hybrid_search": true,
  "hybrid_alpha": 0.5,
  "rerank": true,
  "query_rewrite": false,
  "multi_query": false,
  "hyde": false,
  "metadata_filter": "OFF",
  "alias_mapping": false,
  "prompt_strategy": "Grounded",
  "generation_thinking": "max",
  "query_decompose": false,
  "retrieval_max_tokens": false
}
```

“规划5题”只说明有合法待验证提案，不等于修好5题，更不是已有5题覆盖的实测证据。Q27原重排第12位，单改top_k到6并不能根据原Trace证明它会进入最终内容；原有规划器是有界结构模板，不会据此认定修复。本单只修状态兼容，没有扩展模板或给Agent注入人工参数建议。正式A/B/C仍需Agent独立判断并实测。

## 5. 诊断复用

已做。规划、Agent生成、列表统一用 `prepare_baseline_rows` 读取本轮 `dataset_snapshot_json`；列表有规划结果就直接复用，不再读取Run和重算。保持完整本地审计不变，轻列表仍裁掉大Trace/原始Provider内容。

实际5题分别比较“原规划诊断”“原列表按冻结题诊断”“新的统一诊断”，三个字典逐题完全相等，类别和可执行资格均不变：Q04/Q06/Q27检索噪声，Q24/Q29检索失败，5题均可作为目标。来源：正式库只读逐项比较；模拟测试另验证有冻结题时两入口一致，以及列表不重复调用诊断。原 `test_page_performance.PagePerformanceTests.test_light_planning_reuses_case_diagnosis_and_preserves_full_audit` 已在专项中通过。

## 6. 测试

修改前先复现：新增输入相关测试及原诊断复用测试共6项，2失败、4报错（新模块尚不存在），证明问题与测试路径实际触发。

修改后第一轮专项：

```sh
python3 scripts/test_v14_offline.py test_task008b_agent_input test_page_performance test_task004_agent test_task004_diagnosis test_task004_policy test_task004_release_wiring test_task004_judge_retry test_round0_thinking test_agent_context test_task006_transport_retry test_task007_baseline_thinking
```

当时新增测试为5项，合计70项全部通过，22.225秒。随后补了真实生成路径接线测试和只读预览脚本测试；新增7项单独全部通过，0.380秒。所有Provider均为模拟，不是实际付费调用。全量包含最终7项新增测试。

全量已完整执行结束。沿用008a报告附录相同的隔离运行方法：`unittest.defaultTestLoader.discover(backend/tests)`；临时数据库/目录、空密钥、禁止TCP和正式库访问，`isolated_corpus(legacy_fixture=True)` 只在临时目录放检索fixture；仍跳过会复制正式库的Closeout组，不把跳过算通过。没有复制正式数据库。

| 统计口径 | 008a | 本次008b |
| --- | ---: | ---: |
| 收集到的方法 | 1211 | 1218 |
| 通过的方法 | 1056 | 1064 |
| 未通过的方法（去重，失败或错误） | 117 | 116 |
| 跳过的方法 | 38 | 38 |
| unittest testsRun | 1209 | 1216 |
| 失败断言记录（含子场景） | 112 | 111 |
| 执行错误记录（含子场景） | 47 | 47 |
| unittest跳过记录 | 37 | 37 |

全量测试耗时1138.755秒；含发现、隔离准备及统计共1140.131秒。原始摘要为 `Ran 1216 / failures=111 / errors=47 / skipped=37`。类级跳过覆盖2个方法，仍按008a相同口径展开，因此方法总数为1064+116+38=1218。新增7项全部通过，原有诊断复用测试从失败变为通过，所以通过数增加8。

比008a少的唯一失败方法：`test_page_performance.PagePerformanceTests.test_light_planning_reuses_case_diagnosis_and_preserves_full_audit`。失败/错误方法集合没有新增；跳过的方法集合完全相同。完整117个旧失败方法的前后状态见 [008b-全量失败对比.csv](008b-全量失败对比.csv)。表里的“原分类”和原因来自008a逐项分类，本单核对当前失败集合，没有重做范围外旧测试的根因分析或改写其断言。

最终代码对应的同一组相关专项在全量中共72项，72通过、0失败、0跳过，包含最终7项新增测试、`test_page_performance`、全部 `test_task004_*`、`test_round0_thinking`，以及008a相关的Agent输入、006传输和007思考专项。全量仍有116个方法未通过，不能称全量绿色。

## 7. demo与数据保护

现有后端起初加载旧代码；只读核对所有带status的正式表，未发现运行/排队中的评测、实验、生成、修订、Agent或工具任务。确认8010监听进程的命令和工作目录属于本项目后，发送TERM正常退出，由现有守护进程恢复（默认 `RAG_SAFE_START=1`，不迁移、不自动恢复任务）。5174前端保留。重新GET的运行时指纹与当前 `agent_generate / coverage_planner` 对象一致，起点ID不变。来源：进程命令、cwd、正式表状态、`/api/evaluation?light=true`。

已用真实无头Chromium逐页检查overview、knowledge、settings、governance、evaluation、evolution、versions、verification共8页，正文和标题均加载完成，pageerror=0、HTTP错误=0，未产生非GET或外部请求；finally已关闭浏览器。全量测试及后端重启前后，正式库29张表的行数和逐行内容SHA256摘要29/29完全一致，没有新增实验或更改Baseline、review、题卷、配置等正式记录。来源：原地只读SQLite查询与逐表摘要比较。DeepSeek实际调用0次，其他模型/向量/重排服务调用0次。正式库只使用只读连接，测试不复制正式数据库。

## 8. 我是这样理解的 / 待回答问题

- 无人值守任务按任务单默认继续，不加审批等待；不执行README手动模式的pull/commit/push。额度恢复后沿用已保存半成品继续。
- “demo保持运行”按任务单优先执行；只关闭本次测试进程和浏览器，现有demo服务保留。
- 复核“结论和次数”指产品已保存 `regression_review` 的终态和票数，不指007b人工 `analysis` 的文字或参数建议。5题均为3次里错3次。
- 当前无本单执行所必需的待回答问题。旧模板对Q27的方案不等于能修好，本单如实报告，不自行改变规划策略。008a记录的tokenizer和历史私有夹具缺失继续保留，未下载资源或扩大修复范围。

## 9. 有没有没做完的

本单要求全部完成：客观输入补齐、ready兼容、缺记录阻断、冻结诊断复用、只读提示词/规划回放、相关专项、全量对比与demo验证均完成。全量保留116个旧失败方法、38个旧跳过方法，已按任务要求报告，不表示这些范围外问题已修复。

任务单以普通 `mv` 归档到 `指挥/历史任务/008b-Agent输入补齐.md`。正式demo继续运行，测试浏览器和测试进程均已结束，临时测试数据库/目录自动清除；没有执行修改仓库状态的git命令，保存推送由值班脚本负责。
