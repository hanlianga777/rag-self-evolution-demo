# RAG 自进化平台

面向机器人售后知识问答的 RAG 自进化平台。系统将客户提供的设备手册整理成可检索、可追溯到原文的知识库，用冻结的黄金测试集衡量当前问答质量，再让 Agent 针对错题提出改动。在 Sandbox 中用同一题卷检验修复和回归，经过人工审批后才能发布新配置，发布后可用问答验证和监控继续观察。

## 业务流程

客户手册 → 知识库 → 黄金测试集 → Baseline → Bad Case 诊断 → Agent 多轮优化与 Sandbox 回归 → 人工 Gate → 发布 → 问答验证。

- **建立基准。** 从手册整理出题证据，经 Gate 1 确认后冻结题卷。Baseline 按冻结题卷运行，保存得分、检索证据和 Bad Case。
- **试验改动。** Agent 依据检索、生成、安全和性能诊断提出 Candidate。规则 `2026-11-20b` 要求 11 项硬门槛全过、无新增严重错题、相对 Baseline 无新增错题，并至少修好 1 题。
- **确认和发布。** Gate 2 确认实验报告并锁定 Winner，再试跑组合方案 D。D 合格、逐题无回退且错题更少时才替换 Winner。Gate 3 由用户批准发布，保存版本快照。问答验证可查看保存的前后对比，并针对当前线上版本提问。

[查看业务架构、技术架构、知识库流程和 Agent 优化循环](docs/architecture.md)

## 正式评测结果

评测使用 ABB IRB 1300 产品手册与 IRB 1200 产品规格。E2、E3 共用同一知识库、冻结题卷、Baseline 和 Judge 评测身份。题卷共 50 题，**Baseline 答对 45/50**。

### E3 最新实验

| 轮次 | Candidate A | Candidate B | Candidate C | 轮次决定 |
| --- | --- | --- | --- | --- |
| 第 1 轮 | 46/50 · 不合格 | 48/50 · 合格 | 46/50 · 合格 | 累计两个合格方案，进入 D |
| 第 2、3 轮 | — | — | — | 按规则跳过 |
| 组合方案 D | — | — | — | 48/50 · 合格，与 R1-B 逐题打平 |

**推荐方案（待发布）为 E3 R1-B，48/50。** R1-B 开启问题拆解，相对 Baseline 修好 3 题、无新增错题，通过 11 项硬门槛。Gate 2 已确认，Gate 3 尚未执行，当前线上仍是初始配置。

### E2 对照实验

| 轮次 | Candidate A | Candidate B | Candidate C |
| --- | --- | --- | --- |
| 第 1 轮 | 48/50 · 不合格 | 43/50 · 不合格 | 46/50 · 不合格 |
| 第 2 轮 | 46/50 · 不合格 | 48/50 · 合格 | 45/50 · 不合格 |
| 第 3 轮 | 47/50 · 不合格 | 47/50 · 合格 | 47/50 · 合格 |

E2 的 D 答对 47/50，新增 2 道错题，Sandbox 判为不合格。该实验保留 48/50 的 R2-B 为推荐方案，停在发布前。更早的实验也有一套名为 R2-B 的方案，答对 31/50、仅过 4/11 项硬门槛，被 Sandbox 拦下。两次试验中的同名方案属于不同实验。

以上为冻结题卷上的正式结果，适用范围是这套题卷。汇总来源为任务报告 105d、111a–111d 和 114a–114d。

## 本地运行

使用可安装 [后端依赖](backend/requirements.txt) 的 Python 和前端构建所需的 Node.js、npm。项目规则 CI 使用 Python 3.14 和 Node.js 24。

```sh
./start.sh
```

`start.sh` 检查本地依赖，启动 FastAPI、构建前端并用 Vite 提供 Demo。macOS 安装依赖后也可运行 `./start_demo.command`，在后台启动服务、注册登录启动项，并在就绪后打开 Demo。

- Demo：[127.0.0.1:5174](http://127.0.0.1:5174)
- API 文档：[127.0.0.1:8010/docs](http://127.0.0.1:8010/docs)

仓库提供源码与说明，演示数据由本地环境准备。启动脚本默认使用已有的本地 SQLite 库。全新环境可通过 `RAG_SAFE_START` 关闭安全启动以初始化数据库，之后接入自己的手册并建立索引、题卷和评测结果。运行模型操作会调用相应供应商接口。 [启动设置](backend/app/main.py#L62-L78)

| 用途 | 环境变量名 |
| --- | --- |
| DeepSeek 生成与 Judge | `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`、`DEEPSEEK_TIMEOUT_SECONDS` |
| Embedding 与 Rerank | `DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL` |
| MinerU PDF 解析 | `MINERU_API_KEY`、`MINERU_BASE_URL` |
| 本地运行 | `RAG_SAFE_START`、`RAG_DEMO_ENV_PATH`、`RAG_DEMO_DB_PATH`、`RAG_DEMO_INDEX_DIR`、`RAG_DEMO_DOCUMENTS_DIR`、`RAG_DEMO_UPLOADS_DIR` |

当前规则见 [规则总表](指挥/规则总表.md)。第三方材料与手册版权见 [第三方声明](THIRD_PARTY_NOTICES.md)。
