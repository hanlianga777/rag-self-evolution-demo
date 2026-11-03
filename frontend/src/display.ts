export const isMachineQualified = (status?: string) => status === "machine_qualified" || status === "owner_delegated_approved";

export const vocabulary: Record<string, string> = {
  "Hard Gate": "门槛", Gate: "门槛", Overall: "综合分", Candidate: "候选方案", Regression: "回归检查",
  Recommendation: "推荐方案", Release: "发布", Production: "线上版本", "Legacy Production": "线上版本",
  Rollback: "回滚", Monitoring: "监控", Coverage: "覆盖规划", "Coverage Planning": "覆盖规划",
  "Hard Validation": "硬校验", "Question Generation": "出题", "Human Gate": "人工确认", Snapshot: "冻结版本", Slot: "题位",
  "Config Draft": "配置草稿", "Search Space": "可调参数", "Optimization Agent": "优化 Agent",
};

const translations: Record<string, string> = {
  "round_completed": "本轮试跑完成",
  "owner_delegated": "所有者委托 AI 审核", "owner_delegated_confirmed": "所有者委托 AI 批准", "owner_delegated_approved": "机器合格", "ai_agent": "AI 代理",
  "unclassified": "待分类", "Ordinary": "普通", "ordinary": "普通", "Critical": "严重", "critical": "严重", "query_only": "原问题排序", "STRICT": "严格", "FALLBACK": "回退", "ON": "开启", "OFF": "关闭",
  "Grounded": "有据生成", "Completeness": "完整性优先", "Abstention": "谨慎拒答", "Tiered": "分级回答",
  "Query": "查询处理", "Retrieval": "检索", "Generation": "回答生成",
  "Pending": "待处理", "pending": "待处理", "needs_human_review": "待人工复核", "machine_qualified": "机器合格",
  "expected_improvement": "预期收益", "root_cause": "技术根因", "new_failures": "新增失败",
  "Completed": "已完成", "Running": "运行中", "Queued": "排队中", "Evaluating": "评测中",
  "completed": "已完成", "running": "运行中", "queued": "排队中", "evaluating": "评测中",
  "live": "服务回答", "mock": "本地响应", "Ready": "已验证可用", "Configured (Unverified)": "已配置（未验证）", "Unavailable": "不可用", "passed": "通过", "failed": "未通过", "skipped": "未执行",
  "Indexed": "已索引", "Reviewed": "已审核", "Open": "待优化", "Active": "已启用", "Current": "当前",
  "Recommended": "推荐", "Archived": "已归档", "Passed": "通过", "Failed": "未通过", "PASS": "通过", "FAIL": "未通过",
  "Rejected": "已拒绝", "Demo Active": "已启用", "Retrieval Failure": "检索失败",
  "Retrieval Noise": "检索噪声", "Over-Rejection": "过度拒答",
  "High": "高", "Medium": "中", "Low": "低", "Positive": "正向", "Ablation": "消融",
  "Negative": "负向", "AI Generated": "AI 生成", "Human Added": "人工补充",
  "Evaluation": "评测", "Optimization": "优化", "Bad Cases": "问题案例", "Agent Analysis": "Agent 分析", "Experiments": "实验",
  "Qualified": "合格", "Not Qualified": "不合格", "qualified": "合格", "not_qualified": "不合格",
  "Generated": "已生成", "generated": "已生成", "Evaluated": "已评测", "evaluated": "已评测", "Released": "已发布", "released": "已发布",
  "40 Cases": "40 个案例", "A / B / C": "A / B / C",
  "Overall Score": "综合分", "Overall": "综合分", "Correctness": "正确性", "Faithfulness": "忠实性", "Recall": "召回率", "P95 Latency": "P95 延迟",
  "Relevant": "相关", "Irrelevant": "不相关", "Not Configured": "未配置", "Configured": "已配置",
  "Recall First": "召回优先", "Balanced": "均衡方案", "Performance First": "性能优先",
  "Quality": "质量", "Safety": "安全", "Latency": "延迟", "Regression": "回归检查", "Result": "结果",
  "quality": "质量", "safety": "安全", "latency": "延迟", "regression": "回归", "result": "结果",
  "Load Evaluation Report": "加载评测报告", "Analyze 8 Bad Cases": "分析 8 个问题案例", "Cluster Failure Patterns": "聚类失败模式",
  "Identify Root Causes": "识别根因", "Generate Optimization Hypotheses": "生成优化假设", "Build Candidate Configurations": "构建候选配置",
  "Run Sandbox Experiments": "运行沙箱实验", "Regression Evaluation": "回归评测", "Recommendation": "推荐方案",
  "Balanced quality and latency": "平衡质量与延迟", "Quality ceiling remains": "质量提升空间有限",
  "EVAL-0042 loaded": "EVAL-0042 已加载", "Failure patterns extracted": "已提取失败模式", "4 retrieval failures": "4 个检索失败",
  "Query semantic gap": "Query 语义偏差", "3 viable strategies": "3 个可行策略", "A / B / C ready": "A / B / C 已就绪",
  "Historical run completed": "历史运行已完成", "40 / 40 completed": "40 / 40 已完成",
  "Maximize Retrieval Recall": "最大化检索召回率", "Expected Token and Latency increase": "预计增加 Token 与延迟",
  "Improve Recall while controlling response latency": "提升召回率，同时控制响应延迟", "Fix primary Retrieval issue while keeping low latency": "修复主要检索问题，同时保持低延迟",
  "Today 14:32": "今天 14:32", "Today 14:12": "今天 14:12", "Today 14:36": "今天 14:36", "Yesterday": "昨天", "Mon": "周一",
  "PDF text parser": "PDF 文本解析器", "512 tokens / 80 overlap": "512 tokens / 80 重叠", "Logical isolation · no containers": "逻辑隔离 · 不使用容器",
  "not_run": "未运行", "not_evaluable": "不可评测", "NOT_EVALUABLE": "不可评测",
  "positive": "正向", "ablation": "消融", "negative": "负向",
  "alias_entity": "实体别名", "colloquial": "口语化表达", "cross_chunk": "跨 Chunk", "weak_keywords": "弱关键词", "weak_clues": "弱线索",
  "clarify": "需要澄清", "insufficient_evidence": "证据不足", "prompt_injection_resistance": "提示注入抵抗", "safe_rejection": "安全拒答",
  "prompt_injection": "提示注入", "safety_critical": "安全关键",
  "probe_pending": "待 Probe", "probe_passed": "Probe 通过", "qc_pending": "待 QC", "qc_passed": "QC 通过", "qc_failed": "QC 未通过", "needs_revision": "待修订", "approved": "已批准", "rejected": "已拒绝", "human_review_pending": "待人工审核", "legacy_unverified": "历史未验证", "pending_human_confirm": "待人工确认",
  "QUALIFIED": "合格", "NOT_QUALIFIED": "不合格", "RETRIEVAL_INCOHERENT": "检索不一致（保留人工审核）", "EVIDENCE_VALID": "证据有效", "EVIDENCE_INVALID": "证据无效", "NEGATIVE_VALID": "负向边界有效", "FAKE_NEGATIVE_RISK": "疑似伪负向", "NEGATIVE_SUBTYPE_MISMATCH": "负向子类与题目不符", "NEGATIVE_UNDETERMINED": "负向可回答性未判定",
  "Programmatic evidence check": "证据检索已完成", "Negative may be answerable": "负向题可能可由现有证据回答", "Negative subtype does not match the question": "负向子类与题目不符",
  "active": "生产中", "archived": "已归档", "partial": "部分完成",
  "generating": "生成草案中", "validating": "硬校验中", "preview_ready": "草案待确认", "probing": "检索验证中", "qc": "质量检查中", "failed_quality": "质量未通过", "interrupted": "运行已中断", "cancelled": "已放弃", "discarded": "草案已放弃", "manual_edit": "人工编辑", "ai_regenerate": "AI 单题重生成", "hard_validation": "硬校验", "revision_applied": "已应用修订",
  "question": "问题", "reference_answer": "参考答案", "evidence": "证据", "raw": "元数据",
};

export function displayText(value: string): string {
  return vocabulary[value] || translations[value] || value.replace("Demo", "运营系统");
}

// Exact whole-record translations only. Unknown prose stays explicitly marked; originals remain in the audit.
const savedNarratives: Record<string, string> = {
  "Increasing top_k from 4 to 6 during context selection will recover the omitted DOC-004-C-00032 requirement for V1G-110926448917-08 and reduce its Ranking omission without changing retrieval or generation stages.": "在上下文选择阶段将 TopK 从 4 调整为 6，假设可以补回 Q08 遗漏的 DOC-004-C-00032 要求，减少排序阶段遗漏；不改变检索和回答生成阶段。",
  "Recover DOC-004-C-00032 in Final for V1G-110926448917-08, satisfy checks 5, 6, and 8, and preserve baseline gate results.": "预期在 Q08 的最终上下文中补回 DOC-004-C-00032，满足检查项 5、6、8，并保持 Baseline 的 Gate 结果。",
  "May add noisy context and increase latency; only V1G-110926448113-08 is confirmed eligible, and the remaining 50-question regression plus 11 gates must still pass.": "可能引入上下文噪声并增加延迟；原文仅确认 V1G-110926448113-08 具备资格，仍须通过 50 题 Regression 与 11 项 Gate。",
  "If V1G-110926448917-08 still fails checks 5/6/8 with DOC-004-C-00032 absent from Final under top_k=6, or if any of the 50-question regression or 11 gates fail, this hypothesis is not supported.": "若 TopK 为 6 时，Q08 的最终上下文仍缺少 DOC-004-C-00032 且检查项 5、6、8 仍失败，或 50 题 Regression、11 项 Gate 中任一项未通过，则该假设不获支持。",
};

export function narrativeText(value: string): string {
  const translated = savedNarratives[value] || translations[value];
  if (translated) return translated;
  return /[a-z]+(?:[ ,;]+[a-z]+){3}/i.test(value)
    ? `历史英文原文（未翻译）：${value}` : value;
}

// These are display names only; metric keys and saved rules stay unchanged.
export const gateNames: Record<string, string> = {
  positive_correctness: "正向正确性", positive_faithfulness: "正向忠实性", positive_completeness: "正向完整性",
  ablation_correctness: "消融正确性", ablation_faithfulness: "消融忠实性", ablation_completeness: "消融完整性",
  safe_rejection_rate: "安全拒答率", safety_critical_accuracy: "安全关键准确率", prompt_injection_resistance: "提示注入抵抗",
  latency_p50_seconds: "回答耗时 P50", latency_p99_seconds: "回答耗时 P99",
};
export const gateEnglishNames: Record<string, string> = {
  positive_correctness: "Positive Correctness", positive_faithfulness: "Positive Faithfulness", positive_completeness: "Positive Completeness",
  ablation_correctness: "Ablation Correctness", ablation_faithfulness: "Ablation Faithfulness", ablation_completeness: "Ablation Completeness",
  safe_rejection_rate: "Safe Rejection Rate", safety_critical_accuracy: "Safety Critical Accuracy", prompt_injection_resistance: "Prompt Injection Resistance",
  latency_p50_seconds: "Latency P50", latency_p99_seconds: "Latency P99",
};

export const shortDate = (value?: string) => value && !Number.isNaN(Date.parse(value))
  ? new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai", month: "2-digit", day: "2-digit" }).format(new Date(value)).replace("/", "-") : "日期未知";
export function baselineName(run: any): string {
  const level = { off: "关闭", low: "低档", high: "高档", max: "最高档" }[run?.config?.generation_thinking as string] || "档位未知";
  return `Baseline · ${level} · ${shortDate(run?.created_at)}`;
}
export function productionName(version: any): string {
  return version ? "当前线上配置" : "版本未知";
}
export function questionSource(row: any): string {
  const source = row?.raw?.source;
  if (source === "reviewed_csv_machine_checks") return "人工审核导入";
  if (source === "business_import") return "业务导入";
  return row?.raw?.generation_run_id ? "AI 生成" : "来源未知";
}

export const parameterNames: Record<string, string> = {
  candidate_k: "CandidateK", top_k: "TopK", min_score: "MinScore", hybrid_search: "Hybrid Search", hybrid_alpha: "向量检索权重",
  generation_thinking: "Thinking 档位", query_decompose: "Query Decompose", retrieval_max_tokens: "上下文容量",
  rerank: "Rerank", query_rewrite: "Query Rewrite", multi_query: "Multi-Query", hyde: "HyDE",
  metadata_filter: "元数据筛选", alias_mapping: "别名映射", prompt_strategy: "Prompt 策略",
};

export const descriptions: Record<string, string> = {
  generation_thinking: "可选择 OFF / Low / High / Max", query_decompose: "拆解独立意图并分别检索；默认关闭", retrieval_max_tokens: "不限 / 8192 / 4096；缺少 tokenizer 时按字符数估算 token",
  candidate_k: "初始候选召回数量", top_k: "进入回答上下文的证据数量", min_score: "进入上下文前的最低相关分",
  hybrid_search: "组合向量与关键词检索", hybrid_alpha: "向量检索在混合检索中的权重", rerank: "模型重排、原排序或仅原问题的 BM25 排序",
  query_rewrite: "生成标准化检索问法", multi_query: "生成互补检索问法", hyde: "先写一段假设答案，再拿去检索",
  metadata_filter: "按可靠元数据筛选", alias_mapping: "使用已审核别名映射", prompt_strategy: "分级回答：能确定的先回答，条件缺失时追问，资料无关时转人工，并保留安全警告",
};
