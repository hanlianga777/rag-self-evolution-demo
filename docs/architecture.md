# RAG 自进化平台架构

[返回仓库首页](../README.md)

## 业务架构

```mermaid
flowchart TD
    customer["客户与设备用户"] --> manuals["客户设备手册"]
    operator["售前与运维"] --> knowledge["知识库"]
    manuals --> knowledge
    knowledge --> golden["黄金测试集"]
    operator --> golden
    reviewer["人工审批"] -.-> freeze["Gate 1 确认并冻结题卷"]
    golden --> freeze
    freeze --> baseline["Baseline 评测"]
    baseline --> diagnosis["Bad Case 诊断"]
    diagnosis --> agent["Agent 多轮优化与 Sandbox 回归"]
    agent --> report["Gate 2 确认实验报告"]
    reviewer -.-> report
    report --> approve["Gate 3 批准发布"]
    reviewer -.-> approve
    approve --> publish["发布版本"]
    publish --> verify["问答验证与监控"]
    customer -.-> verify
```

## 技术架构

```mermaid
flowchart TD
    ui["React / Vite 前端"] --> api["FastAPI 后端"]
    api --> knowledge["知识库构建"]
    api --> governance["评测治理 · Baseline · Sandbox"]
    api --> agent["Agent 优化"]
    api --> release["发布与回滚"]
    api --> qa["问答 RAG Pipeline"]
    agent --> governance
    governance --> qa
    governance --> judge["DeepSeek Judge"]
    agent --> generation["DeepSeek 生成"]
    qa --> generation
    qa --> retrieval["向量与 BM25 召回 · 去重 · 重排"]
    knowledge --> parser["MinerU 解析"]
    knowledge --> embedding["Embedding 服务"]
    retrieval --> embedding
    retrieval --> rerank["Rerank 服务"]
    knowledge --> files[("FAISS 与知识库索引文件")]
    retrieval --> files
    governance --> sqlite[("SQLite 评测与审批记录")]
    agent --> sqlite
    release --> sqlite
    qa --> sqlite
```

## 知识库流程

```mermaid
flowchart TD
    pdf["手册 PDF"] --> parse["MinerU 解析或复用已有解析"]
    parse --> clean["去噪 · 页眉页脚、图片编号、留白页"]
    clean --> section["识别编号章节与小节路径"]
    section --> chunk["Parent / Child 分块 · 表格绑定表头"]
    chunk --> text["子块嵌入文本 · 文档名 + 小节路径 + 正文"]
    text --> faiss["Embedding 与 FAISS 向量索引"]
    chunk --> bm25["子块正文供 BM25 检索"]
    faiss --> fusion["向量与 BM25 混合召回"]
    bm25 --> fusion
    chunk --> equivalence["建立同文与证据等价映射"]
    equivalence --> dedup["候选池去重 · 证据等价核对"]
    fusion --> dedup
    faiss --> topics["第一层 · 业务主题"]
    chunk --> topics
    topics --> groups["第二层 · 主题内编号小节分组"]
```

向量和子块同时支持检索与主题分组。候选池按查询融合分选同文代表，逐题证据等价还核对编号小节、型号和版本。主题分组使用索引中保存的子块和向量。 [检索规则与证据等价](../指挥/规则总表.md#四生成与-baseline-配置) · [业务主题实现](../backend/app/business_topics.py)

## Agent 优化循环

```mermaid
flowchart TD
    diagnose["诊断 · 检查错题与证据"]
    diagnose --> strategy["策略 · 错因分布、检索预演、历史经验采纳"]
    strategy --> candidates["生成并校验 A / B / C Candidate"]
    candidates --> sandbox["用冻结题卷运行 Sandbox"]
    sandbox --> qualify["资格 2026-11-20b · 11 项门槛全过 · 新增严重和普通错题均为 0 · 至少修好 1 题"]
    qualify --> review["轮次复盘 · 实测与预测对账"]
    review --> next{"轮次与预算规则"}
    next -->|继续试验| strategy
    next -->|无合格方案且结束| stop["结束优化 · 保持 Baseline"]
    next -->|进入推荐阶段| gate2["Gate 2 确认报告 · 锁定 Winner"]
    gate2 -->|有试跑预算| d["Candidate D · 组合或追加参数"]
    d --> dsandbox["D Sandbox · 资格判定和复盘"]
    dsandbox --> recommend["最终推荐 · 比 Winner 少错且逐题无回退才采用合格 D"]
    gate2 -->|D 无剩余预算| recommend
    recommend --> gate3["Gate 3 · 用户批准发布"]
    gate3 --> release["发布版本 · 保存快照"]
```

当剩余预算无法试跑 D 时，保留合格 Winner 进入发布前审核。 [轮次和 D 的规则](../指挥/规则总表.md#六agent-与-sandbox) · [优化循环实现](../backend/app/optimization_cycle.py)
