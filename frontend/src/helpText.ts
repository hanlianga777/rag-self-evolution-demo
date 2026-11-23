export const coreTerm = {
  rag: "检索增强生成",
  pipeline: "处理流程",
  baseline: "基准评测",
  agent: "优化智能体",
};

export const pagePurpose = {
  overview: `从 RAG（${coreTerm.rag}）知识库到评测、优化和人工发布，查看各环节当前进度。`,
  knowledge: "查看文档如何变成可检索、可定位原页的知识片段（Chunk）。",
  governance: "查看评测题卷、证据检查和人工确认记录。",
  settings: `查看 Pipeline（${coreTerm.pipeline}）的技术选型、基准配置和参数范围。`,
  evaluation: `用 Baseline（${coreTerm.baseline}）定位错题，并查看 Judge（判分模型）的评测依据。`,
  evolution: `查看 Agent（${coreTerm.agent}）如何为失败案例（Bad Case）提出候选方案（Candidate），以及沙盒评测结果。`,
  versions: "核对候选方案（Candidate）的发布条件、人工审批和当前线上版本。",
  verification: `对照 Baseline（${coreTerm.baseline}）和推荐方案的保存回答，或用实际问答收集线上反馈。`
};

export const helpText = {
  "parent_child": "检索先找知识片段，再把命中片段的父段落交给模型，让它看到上下文。",
  "cluster": "按知识片段的语义划分主题，出题时按主题分配计划题目，覆盖说明书的不同部分。",
  "hard_gate": "上线门槛。每一项都要单独达标，综合分再高也不能抵消某一项没过。",
  "recall": "标准证据有没有出现在最终交给模型的前 K 段资料里。",
  "precision": "交给模型的 K 段资料里，有多少段是真正相关的。",
  "mrr": "第一段标准证据排第几：排第 1 得 1 分，排第 2 得 1/2，以此类推，越接近 1 越好。"
};
