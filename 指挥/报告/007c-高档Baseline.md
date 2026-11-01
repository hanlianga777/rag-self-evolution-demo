# 任务007c：高档回答Baseline已启动

任务来源：拉取到 `2e9c953` 后的 `指挥/当前任务.md`。本次只启动对照组并验证前三题，没有等待50题结束，没有改题、检索参数、判分规则或产品代码。

## 启动记录

| 项目 | 结果 |
| --- | --- |
| 新运行编号 | **EVAL-20261101230802799801** |
| 启动时间UTC | 2026-11-01 23:08:02.828180+00:00 |
| 启动时间多伦多 | **2026-11-01 18:08:02，America/Toronto，UTC-05:00** |
| 题卷 | GD-20261101151940，完整50题 |
| 回答档位 | high |
| 判分档位 | max |
| 产品入口 | POST /api/evaluations/run，`{"fresh":true}`，HTTP 201 |
| 取证时间 | 2026-11-01 23:10:03 UTC，即多伦多18:10:03 |
| 取证时状态 | running，已完成3/50 |

启动前通过正式库只读查询确认：没有运行或排队的评测、题卷生成、题卷质量检查、局部修订、Agent生成或实验任务。随后用SQLite备份接口备份正式库，把本机 `.env` 中唯一的 `BASELINE_THINKING=max` 改为 `BASELINE_THINKING=high`，其他行保留。

正常停止已核实的本项目后端守护进程后，通过macOS Terminal打开原始 `start_demo.command`，沿日常守护链路重启后端。8010、5174均正常；只读 `GET /api/evaluation/preflight` 返回 `can_start=true` 后才启动新轮。

新轮启动在任务所述多伦多20:00之前。是否能在20:00前完成尚未知，本次没有等待整轮结束。

## 前三题与实际请求档位

以下来自新轮保存的逐题结果和请求Usage中的 `request_parameters.reasoning_effort`，不是仅看页面配置或环境变量。

| 题号 | 有回答 | 有判分 | 结果 | 回答实际档位 | 判分实际档位 | 技术错误 |
| --- | --- | --- | --- | --- | --- | --- |
| Q01 | 是 | 是 | PASS | high | max | 无 |
| Q02 | 是 | 是 | PASS | high | max | 无 |
| Q03 | 是 | 是 | PASS | high | max | 无 |

新旧两轮完整 `config_json` 比较，**唯一差异为 `generation_thinking: max → high`**；其余检索参数、知识库身份及配置一致。两轮 `dataset_snapshot_json` 字节完全一致。Judge元数据仅 `execution_snapshot` 中的回答档位随之变化，判分配置仍是max。

没有出现任务规定的停止条件，因此未停止新轮。前三题核实后结束本段跟进，没有循环轮询后续进度。

## 概览和Agent现在指向哪里

取证时读取三个产品接口，结果如下：

| 页面/接口 | 当前Baseline |
| --- | --- |
| 工作区 `/api/workspace` | EVAL-20261101155246923769（原max轮） |
| 概览 `/api/overview?light=true` | current_baseline_id和latest_evaluation.id均为原max轮 |
| Agent `/api/optimization?light=true` | current_baseline_id为原max轮 |

新high轮当时仍在运行。现有系统从已完成且有效的Baseline中解析当前指向，所以本次取证时仍是原max轮；没有手动改指向。新轮完成后指向可能按产品规则变化，后续以实际接口为准。

原max轮 `EVAL-20261101155246923769` 的运行记录、全部逐题结果和关联Bad Case行分别做了前后哈希核对，均完全一致，没有删除、覆盖或改写。

## 备份和调用费用

SQLite备份位置：

`/Users/zhanghaohan/Documents/ChatGPT/智能客服RAG自进化项目/backend/data/audit_backups/baseline-007c-20261101230733.db`

同类备份使用现有 `keep_recent_two` 管理，最多保留最近2份。写入前正式库SHA256为 `cff806d9a9128215f93f26db2a6200566aa7849c57755495135d81fec62014e3`。数据库和备份仅保存在本机，未提交。

调用统计取自新轮checkpoint，使用现有 `checkpoint_usage` 去重，不含原max轮。以下是23:10:03 UTC的固定截点；之后后台还会继续产生调用。

| 服务 | 已返回且Usage为ok | 正在执行 |
| --- | ---: | --- |
| DeepSeek deepseek-flash | 7次（回答4次、判分3次） | 判分1次 |
| Alibaba text-embedding-v4 | 4次 | 0 |
| Alibaba qwen3-rerank | 4次 | 0 |

第4题的回答当时已返回，判分尚在执行，故调用数超过前三题的6次DeepSeek请求。已返回7次DeepSeek Usage按项目现有 `deepseek-flash-2026-09-30` 价格配置估算为 **0.01642732美元**，配置判定这些请求处于off_peak。此数是返回token用量的配置价估算，不是账户账单；实际扣款未知。向量和重排的费用未知，整轮最终费用也未知，不写成0。

## 启动与交付检查

临时无头浏览器实际打开项目概览、知识库、Pipeline配置、Golden Dataset、Baseline、Agent工作台、发布、问答验证8页，均等到对应标题和内容加载，无pageerror。测试浏览器已关闭，日常demo及新Baseline后台继续运行。

**本机 `.env` 保持 `BASELINE_THINKING=high`**，没有恢复max；后续用哪一档由用户和总指挥决定。`.env`、密钥、数据库、日志、截图不上传。本次没有修改产品代码，只提交本报告。

本单要求的启动和前三题验证已完成；50题最终成绩、与max轮错题对照、最终调用次数及费用尚未完成统计，本单不提前下结论。
