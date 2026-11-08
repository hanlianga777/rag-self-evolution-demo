# 任务 021t：用本机 diagram skill 重画业务架构图、技术架构图、知识处理链路图，并替换页面里的旧图（不调用模型，自动值班）

用户已授权：中间所有确认默认同意，不要停下来等人。在 021s 之后执行。**用户 11-08 明确要求**：由总指挥设计图的内容和逻辑，再由 Codex 调用用户桌面上那个压缩包里的 skill 把图画出来，然后替换页面里的旧图。

## 1. 准备 skill
- **找到压缩包**：在 `~/Desktop` 里，解压后是一个名为"架构图、流程图、数据图"的文件夹，里面的 `SKILL.md` 写着 `name: diagram-design`。
- **解压位置**：解压到 `output/task021t/skill/`。这个目录不提交，不要放进前端源码目录，也不要提交到仓库。
- **先读规则**：先完整阅读 `SKILL.md`，再按需读 `references/` 下的 `style-guide.md`、`type-flowchart.md`、`type-swimlane.md`、`type-layers.md`、`type-architecture.md`、`type-data-flow.md`、`output-spec.md`、`export.md`。
- **风格选项**：SKILL.md 第 0 节会要求选择风格。**选 (d) 手动填写品牌色**，色值用 demo 现有的：
  - 页面底色 `#F3F5F8`
  - 卡片白 `#FFFFFF`
  - 主文字 `#142033`
  - 次文字 `#6A7990`
  - 线条 `#E3E8EF`
  - 深藏青（侧栏色）`#111A2B`
  - 强调绿（唯一强调色）`#0E7A5A`，浅绿 `#E5F3EC`
  - 风险红 `#B4432B`，只在需要表示"退化"时用
  - 字体：系统中文字体（PingFang SC / 微软雅黑），不要等宽字体
- **遵守 skill 的原则**：强调色只给 1–2 个焦点；目标密度约 4/10；超过 9 个节点就考虑拆分或分组。

## 2. 三张图的内容（总指挥定稿）
草稿在 `指挥/设计稿/021t-架构图草稿/`：`.mmd` 是逻辑草稿，`.png` 是预览。**草稿只定逻辑，版式和美观按 skill 来做**，不要照搬 Mermaid 的排版。术语按 021r 的英文规则。

### 图 1：业务架构（概览 →「业务架构」页签）
- **类型**：流程图或泳道图。主流程从左到右，必要时折成两行，阅读顺序一目了然。
- **图上方配一条"挑战 → 建设目标"**：三组，做成页面里的一排紧凑文字卡，不画进图里：
  - 质量难以衡量 → 可信评测（冻结 Golden + Judge + Hard Gate）
  - 专家调优成本高 → Agent 受控优化（白名单参数、多方向实验）
  - 修好一处、弄坏一处 → Regression 治理 + 人工发布
- **主流程节点**，文字尽量短：
  1. 知识库：4 份设备说明书，Parent-Child 切块，可溯源
  2. Golden Dataset：覆盖规划 → 出题 → 硬校验 · Probe · QC
  3. 人工关口 ①：题卷冻结
  4. Baseline 评测：Judge 逐题判分，11 项 Hard Gate，Bad Case 诊断
  5. **Agent 优化循环（焦点，用强调绿）**，内含 Candidate A/B/C 三个方向 → Sandbox（同一套 Golden）→ Regression Check（零新增 Bad Case）。"无合格 Candidate"时带着经验回到下一轮，循环上标"≤ 12 次评测"。
  6. Winner：出现合格 Candidate
  7. 人工关口 ②：实验报告确认
  8. Candidate D：在 Winner 上精修，预测 vs 实际
  9. 最终推荐
  10. 人工关口 ③：发布授权，可回滚
  11. 问答验证：实时问答 · Before/After · 线上反馈
- **回流线（虚线）**：问答验证 → "人工标记为 Bad Case，触发新一轮优化" → Agent 优化循环。
- **三个人工关口**用同一种醒目但不抢焦点的样式，例如深藏青描边加一个小锁图标，让人一眼看出"三道人工闸，作用不同"。
- **节点超过 9 个的处理**：把 Winner、实验报告确认、Candidate D、最终推荐编为一组"决策与精修"，或者分两行。目标是清楚，不是挤。

### 图 2：技术架构（概览 →「技术架构」页签）
- **类型**：分层图（layer stack），从上到下 5 层。
  1. **展示层**：React Demo，8 个页面
  2. **治理服务层（FastAPI）**：
     - 评测治理：Golden 生命周期 · Judge · Hard Gate · Regression
     - Agent 优化：Candidate 生成 · Sandbox 执行 · Candidate D 精修
     - 版本发布：推荐 · 发布快照 · 回滚
     - 运行调度：平价时段 · 断点续跑
  3. **RAG Pipeline（被优化对象，焦点，用强调绿）**：Query 理解 → Hybrid Search → Rerank → Generation。
     - Agent 可调的参数用一个统一的小标记，例如绿色小圆点或 ★：
       - Query Rewrite · Multi-Query · HyDE
       - Candidate K · 向量权重
       - Top-K
       - Thinking 档位 · Prompt 策略
     - 图例写"● = Agent 可调参数（白名单）"。
     - 具体参数名以 Pipeline 配置页的真实 12 项为准，不要发明。
  4. **知识处理层（离线）**：PDF → MinerU 解析 → Parent-Child 分块（1400 / 400 / 重叠 80）→ text-embedding-v4（1024 维）→ FAISS 索引 + BM25
  5. **数据与模型层**：
     - SQLite：Run · Golden · 版本 · 审计
     - 模型 Provider：DeepSeek 负责 Generation、Judge；Qwen 负责 Embedding、Rerank
- **连线只画关键关系**：治理服务层调度 Pipeline；知识处理层产出索引给 Pipeline；各层读写数据层。用"层的上下关系"表达即可的，不画线。

### 图 3：知识处理与证据链路（知识库 →「技术架构」页签）
- **类型**：数据流，从左到右一行。
- **节点**：PDF 说明书（4 份）→ MinerU 解析（保留页码）→ Parent-Child 分块（Child 用于检索，Parent 用于回答）→ Embedding Retrieval + BM25 → Hybrid 融合（Candidate K 条）→ Rerank → Parent 展开（Top-K 段进入回答）→ 回答引用（文档 · 章节 · 页码）。
- **焦点**：最后一个节点"回答引用"用强调绿，表达"每个回答都能追溯到说明书原页"。
- **和图 2 的分工**：不重复图 2 的分层，只讲证据怎么一路走到回答里。

### 三张图共同要求
- **技术细节核对**：模型名、分块参数、维度、参数名都要和代码、Pipeline 配置页一致。发现草稿写错，以代码为准，并在报告里写明。
- **数字核对**：图上出现的数字只能是确定不变的，例如 4 份文档、11 项 Hard Gate、12 次评测上限。不放 44→48 这类成绩。

## 3. 替换页面里的旧图
- 旧图由 `frontend/src/components/KnowledgeDiagrams.tsx` 等组件绘制，用新图替换。
- **页面用法**：用 skill 导出的 SVG 内联或作为静态资源加载，保证清晰、不模糊，在 1440×900 和 1280×800 下完整可见，不出现横向滚动。图里的文字要能被选中或保持清晰。
- **概览「业务架构」页签**：上面是"挑战 → 建设目标"一排卡片，下面是图 1。
- **知识库「技术架构」页签**：图 3。
- **概览「技术架构」页签**：图 2。
- 删掉不再使用的旧图代码。

## 4. 导出给 GitHub 首页用
导出三张图的 PNG（2 倍清晰度）和 SVG，放到 `docs/images/`：
- `architecture-business.png` / `.svg`
- `architecture-technical.png` / `.svg`
- `knowledge-evidence-flow.png` / `.svg`

**这几个文件要提交**。总指挥会把它们放进 README。

## 硬性约束
- 不调用模型，不改评测数据，不发布。
- skill 解压目录不提交。
- 相关测试、构建通过。
- 不要运行 git 写命令；不改 `指挥/当前任务.md`；demo 保持运行。

## 报告
写到 `指挥/报告/021t-架构图.md`，写明：
- skill 的位置和读过的文件；
- 选用的图类型及理由；
- 和草稿相比改了哪里、为什么；
- 技术细节核对结果；
- 三个页签的 1440×900 截图路径（只存本机）。

## 完成后
用普通的 `mv` 把本任务单移到 `指挥/历史任务/`。
