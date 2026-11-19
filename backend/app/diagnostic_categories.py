"""One product vocabulary for saved-data diagnosis, Agent inputs and pages.

规则总表四：四层根因；严重度按冻结题卷的严重题名单定（见 diagnostics.py），不在这里按大类写死。
priority 只是展示和排序的默认值，导致门槛未过的类别会在 optimization_priorities 里升为 1。
2026-11-19 起回答提示词（Strict 及其补全要点版、安全强化版）重新作为修复方向；Baseline 固定 Strict。
"""
DIAGNOSTIC_CATEGORIES = (
    {'label':'检索层问题','priority':1,'directions':['Query Rewrite','HyDE','Multi-Query','问题拆解','候选数','保留条数','最低分数线','Hybrid Search','Embedding Retrieval 权重','Rerank'],'repair_hint':'调整查找、排序和过滤，保留关键证据'},
    {'label':'生成层问题','priority':2,'directions':['回答提示词','Thinking 档位','上下文窗口','保留条数'],'repair_hint':'换回答提示词版本（补全要点版），或调整交给模型的资料范围'},
    {'label':'安全边界问题','priority':1,'directions':['回答提示词','Thinking 档位','保留条数','最低分数线'],'repair_hint':'换回答提示词版本（安全强化版），或调整资料范围，保留安全边界'},
    {'label':'性能问题','priority':3,'directions':['降低 Thinking 档位','关闭耗时环节','调整检索参数'],'repair_hint':'降低 Thinking、关闭耗时环节，再用检索参数补质量'},
)


def category_definition(label):
    return next((dict(row) for row in DIAGNOSTIC_CATEGORIES if row['label']==label), {})
