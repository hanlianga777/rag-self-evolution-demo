export const pagePurpose = {
  overview: "从 RAG（检索增强生成）知识库到评测、优化和人工发布，查看各环节当前进度。",
  knowledge: "查看文档如何变成可检索、可定位原页的知识片段（Chunk）。",
  governance: "查看评测题卷、证据检查和人工确认记录。",
  settings: "查看 Pipeline（问答流程）的技术选型、基准配置和参数范围。",
  evaluation: "用 Baseline（基准评测）定位错题，并查看 Judge（判分模型）的评测依据。",
  evolution: "查看 Agent（优化助手）怎样从失败案例提出候选方案，并用评测验证。",
  versions: "核对候选方案（Candidate）的发布条件、人工审批和当前线上版本。",
  verification: "对照已保存的回答，或用实际问答收集线上反馈。"
};

export const helpText = {
  "parent_child": "Child 是检索用的小块，越小越容易精准命中；命中后换成它所在的完整段落 Parent 交给模型，回答时上下文才完整。",
  "cluster": "用 K-means 按语义把知识片段自动分成若干主题，出题时按主题的厚薄分配题位，保证考卷覆盖整本说明书，而不是扎堆在好出题的几页。",
  "hard_gate": "上线门槛。每一项都要单独达标，综合分再高也不能抵消某一项没过。",
  "recall": "标准证据有没有出现在最终交给模型的前 K 段资料里。",
  "precision": "交给模型的 K 段资料里，有多少段是真正相关的。",
  "mrr": "第一段标准证据排第几：排第 1 得 1 分，排第 2 得 1/2，以此类推，越接近 1 越好。"
};
