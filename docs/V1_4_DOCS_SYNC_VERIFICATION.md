# V1.4 文档与架构同步验收

日期：2026-09-30（Asia/Shanghai）。检查基线：`f6ea03d`。使用 ponytail full 与 diagram-design；仅文档和图交付，业务实现保持 Phase 1，不执行真实 Provider、数据库迁移、Golden/评测/实验/人工发布或索引重建。

## 交付与需求覆盖

- 唯一 SPEC 升为 V1.4：保留完整第 5–16 节需求、需求 ID、第 17 节离线验收矩阵和第 18 节手动验证；历史 V1.3 原文折叠存档。
- 当前源码差异独立列示：固定最多 4 个中心的 Coverage、Pool 空 Plan、最新实验解析、Monitoring 最新 completed Evaluation 与目标机制有差距；这些是静态证据，不是新运行复现或 V1.4 验收通过。
- 两图从头设计为三个业务域和离线/在线/数据支撑边界，重新生成自包含 HTML / 内嵌 SVG / 2560×1440 PNG。旧分行流程和四列技术模板均未复用。
- README、平台架构说明、根目录架构/上下文/交接/待办/决策/ChangeLog 同步版本与目标/实现边界，保留历史证据。
- `[OPEN-QC-P0]`：任务书“P0 阻断”与既有机器 QC P0 可人工接受的范围冲突，已明确记录；没有改变旧 Validator/审批行为或替用户确定新门槛。

## 文档与图验证

下列检查仅针对此次文档与图，不替代业务或真实 Provider 验收：

| 检查 | 结果 |
| --- | --- |
| 输入关键章节 / 需求 ID / 离线 Test ID 覆盖 | PASS；正文需求保留，测试编号不丢失 |
| V1.3 历史原文、SPEC_CHANGELOG 既有条目保留 | PASS |
| 两图 `self_check.py` | PASS；accessible SVG、单文件资源与安全结构 |
| Chromium 字体就绪后导出 | PASS；1280×720 viewBox ×2，PNG 2560×1440 |
| 节点文本范围 / 画布范围 / 连线经过文字 | PASS；两图均无发现 |
| 浏览器 JavaScript 错误 | 0；图源无脚本、无外部资源 |
| 1440 / 1280 / 390px 页面尺寸 | PASS；SVG 按视口缩放，无 document 横向溢出；小尺寸需放大阅读图中文字 |
| 两图目视检查 | PASS；已调整经过分区标题的连线，关键 Gate / D / Monitoring 和数据边界可辨识 |
| 文档本地文件链接、图源 / PNG 一致 | PASS |
| `git diff --check` 与变更范围 | PASS；仅文档、HTML 图源、PNG |

运行证据保留于本地 `/tmp/rag-v14-docs-20260930/`，不提交临时脚本、浏览器输出或真实数据。

## 数据与运行边界

本次未调用业务 API，未导入 `app.main`、未启动/重启服务。对真实 DB 和索引既有文件做只读 SHA-256 前后比较，5 个文件全部一致；没有数据库/索引变更。Git diff 没有 backend/frontend 业务代码、配置或依赖变更。用户手动上传到 Demo 的架构图片为独立运行资产，本次不替换；GitHub README 引用的两图已重绘。

没有执行后端/前端业务全量测试、Fixture 生命周期、V1.4 三尺寸应用 UI 或 Safari/WebKit 验收，因为本次没有业务实现变更。本报告的三尺寸检查仅是图源页面。Phase 1 的 229/89 等历史测试数字没有转记为 V1.4 通过。

## Git 交付

目标为既有 `origin/main`，不 force push。只暂存此次文档和图；提交及推送后的准确 SHA、同步/clean 状态以本次最终交付和 Git 记录为准，不在 commit 内写循环引用的自身 SHA。远端更新时先保留并整合，不覆盖用户提交。
