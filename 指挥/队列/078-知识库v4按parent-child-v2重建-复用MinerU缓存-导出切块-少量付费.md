# 078：知识库 v4 按 parent-child-v2 重建（复用 MinerU 缓存，只重新切块和向量化）→ 导出切块（少量付费：阿里云向量化）

## 问题与根因（用户 2026-11-19 08:57 指出，总指挥已查实）

- 072 重建出来是 **2,131 个子块 / 1,767 个父块**，约 1.2:1。父块几乎退化成"一个标题一块"，"命中子块 → 交出整段父块"的设计基本失效。
- 根因在 `/api/knowledge/rebuild`：它调用 `KnowledgePipeline.build` 时没有传 `chunk_version`，用的是默认的 **v1**（按每个标题切 Parent，连"注意""续前页""下一页继续"这类标题都单独成块）。
- 11-14 用户定的是 **parent-child-v2**，031c 也是按 v2 手工重建的，验收标准为：平均每个 Parent ≥3 个 Child、单 Child 的 Parent ≤15%、碎块为 0。但之后 062（v3）、072（v4）都走了接口，悄悄退回了 v1。这是总指挥写任务单时没有要求 v2 的失误。

**总指挥已推送修复：**
- `knowledge_pipeline.ACTIVE_CHUNK_VERSION='parent-child-v2'`。
- 重建接口固定用 v2，并通过新的 `CachedMinerUParser` 复用旧索引目录里保存的 `<文档ID>-mineru.zip`。只要缓存在，就不重新调用 MinerU。
- 操作记录会写下 `mineru_cache.reused` / `parsed` 和 `chunk_version`。
- 测试：`test_task078_v2_rebuild.py`。

## 要做的事

1. **拉代码、测试、重启**：
   - `git pull`；
   - 在 `backend` 跑 `test_task078_v2_rebuild.py test_knowledge_pipeline.py test_task031b.py test_task031b2.py test_corpus_management.py`，只列新增失败；
   - 按 047 的方法重启 8010。
   - 若 073 还没做完，等它做完再开始本单。

2. **重建**：
   - 调用**一次** `POST /api/knowledge/rebuild`，每 5 分钟查一次 `GET /api/corpus-operations/{id}`，直到完成。
   - 贴出操作记录中的 `chunk_version`（应为 `parent-child-v2`）和 `mineru_cache`。6 份文档都应在 `reused` 里；如果有文档进了 `parsed`，说明重新调用了 MinerU，写明是哪份。
   - 失败就贴出错误原文后停下，不要退回 v1。

3. **v2 验收**（只读，写进报告）：

   | 指标 | 标准 |
   |---|---|
   | 子块总数、父块总数 | 按文档分列 |
   | 平均每个 Parent 的 Child 数 | ≥3 |
   | 只有 1 个 Child 的 Parent 占比 | ≤15% |
   | 少于 30 字的碎块数 | 0 |
   | 子块平均字数、最大字数 | 只报告 |
   | "续前页""下一页继续"、版权页脚这类重复行 | 抽 10 个子块确认已去掉，并贴出原文 |
   | 表格切块 | 抽 3 个，确认是 table-kv-v2 的"列名=值"按行格式，并贴出原文 |
   | `knowledge_identity` | 已更新，贴出新值 |
   | 自动出题 | 没有发生 |

   前三项任一不达标：**照常完成导出**，但在报告开头写清楚不达标的项和数值，交由总指挥判断。

4. **导出**：格式同 072。文件名前缀改为 `078`：
   - `指挥/报告/078-切块全量.csv`：列与 072 相同，超过 9MB 就拆分；
   - `078-全文-<doc_id>.txt`；
   - `078-文档清单.csv`。

## 报告

`指挥/报告/078.md`

## 约束

- 只允许阿里云向量化（重建必需）。如有文档缓存缺失，允许为它调用 MinerU。
- 不调用 DeepSeek，不导入题卷，不跑扫描、Baseline 或 Agent。
- 不删旧索引版本和旧记录。
- 完成后移入历史任务。
