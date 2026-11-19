# 073：Pipeline 参数统一用英文名；Prompt 三版改名为 Strict / Looser / Safe；Temperature 固定显示；前端全面对齐（不花钱）

## 用户决定（2026-11-19 08:43）

1. 回答提示词三个版本改用英文名 **Strict / Looser / Safe**，与 Colin 的 `prompt=strict` / `PromptLooser` 对齐。
2. **Temperature** 进入 Pipeline 配置，固定为 0（关闭 Thinking 时的实际请求值），不给 Agent 调。
3. Pipeline 配置里被强行翻成中文的参数名，统一改用英文。

## 总指挥已推送的改动（先跑测试）

**后端：**
- `policy.py`：
  - `prompt_strategy` 可选值为 `Strict / Looser / Safe`；
  - `FIXED_PIPELINE_PARAMETERS={"temperature":0}`；
  - `FRIEND_BASELINE_CONFIG` 带 `temperature: 0`；
  - 新增 `query_decompose`。
- `ai_service.py`：`PROMPT_STRATEGIES`，Looser 和 Safe 都以 Strict 为底。
- `composite.py`：D 的配置保留固定参数。
- `display_summaries.py`：参数名映射改为英文。

**前端：**
- `display.ts`、`components/comparisonData.ts`：`parameterNames` 改为英文。
- `parameterValue` 和 `PipelineFields` 的取值显示：
  - 开关类显示 ON / OFF；
  - 档位显示 Off / Low / High / Max。
- `parameterGroups.Generation` 增加 `temperature`。
- `EvolutionStory` 不再把参数名翻成中文。

## 要做的事

1. **后端测试**：在 `backend` 跑以下测试，只列新增失败：
   ```
   test_task073_prompt_and_decompose.py test_task072_retrieval_preview.py test_task070_thinking_lock.py test_task038_rulebook.py test_round0_pipeline.py test_task004_agent.py test_task009b_acceptance.py test_task033c_stability.py test_task021a_composite.py test_final_policy.py
   ```
   `test_task038_rulebook.py::test_candidate_and_release_use_one_rule` 的 3 个参数化用例改动前就失败（11-18 改朋友口径时遗留），请顺手把它们的期望改成朋友口径：普通新增题不设上限。

2. **前端全面扫一遍**：凡是把 Pipeline 参数名或参数取值显示成中文的地方，一律改用下表的英文名。至少检查以下文件：
   - `helpText.ts`、`components/PipelineFields.tsx`、`components/EvolutionStory.tsx`、`components/comparisonData.ts`；
   - `ui/PageSamples.tsx`、`ui/architecture/TechArchitecture.tsx`、`ui/evolution/model.ts`；
   - `pages/VersionsPage.tsx`、`pages/VerificationPage.tsx`；
   - 以及 `grep` 出来的其他位置。

   | 参数键 | 英文名 |
   |---|---|
   | candidate_k | Candidate K |
   | top_k | Top-K |
   | min_score | Min Score |
   | hybrid_search | Hybrid Search |
   | hybrid_alpha | Hybrid Alpha |
   | rerank | Rerank |
   | query_rewrite | Query Rewrite |
   | multi_query | Multi-Query |
   | hyde | HyDE |
   | query_decompose | Query Decompose |
   | retrieval_max_tokens | Max Context Tokens |
   | prompt_strategy | Prompt Strategy |
   | generation_thinking | Thinking |
   | temperature | Temperature |
   | metadata_filter | Metadata Filter |
   | alias_mapping | Alias Mapping |

   - **取值**：Strict / Looser / Safe；ON / OFF；Off / Low / High / Max；Query Only。
   - **说明文字可以继续用中文**，比如表格的"说明"列、悬停提示，只有参数名和取值用英文。
   - 页面标题、按钮、业务说明不在本单范围，不改。

3. **前端测试与构建**：
   - 把断言中文参数名的测试改成英文；
   - 跑 `npm test` 和 `npm run build`，都要通过；
   - 在浏览器打开 Pipeline 配置页，确认 Generation 分组显示 Prompt Strategy、Thinking、Temperature（0，固定），Query 分组显示 Query Decompose。只读，不截图入库。

4. **生产配置**：
   - 先 dry-run `set_friend_baseline_config.py`，差异应只有新增 `temperature: 0`、`query_decompose: false`；
   - 再 `--apply`；
   - 按 047 的方法重启 8010，加载最新代码。

## 报告

`指挥/报告/073.md`：
- 测试结果；
- 改了哪些文件、哪些显示位置；
- 构建结果；
- 生产配置的 dry-run 和 apply 输出。

## 约束

- 不调用任何付费接口。
- 不改题卷、判分逻辑。
- 不跑 Baseline，不启动 Agent。
- 完成后移入历史任务。
