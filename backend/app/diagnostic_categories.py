"""One product vocabulary for saved-data diagnosis, Agent inputs and pages."""
DIAGNOSTIC_CATEGORIES = (
    {'label':'检索层问题','severity':'严重','priority':1,'directions':['改写查询','HyDE','多路查询','候选数','保留条数','最低分数线','混合检索','向量检索权重','重排'],'repair_hint':'调整查找、排序和过滤，保留关键证据'},
    {'label':'生成层问题','severity':'中等','priority':2,'directions':['回答策略','思考档位','上下文窗口'],'repair_hint':'调整 Prompt 策略、Thinking 档位和上下文窗口'},
    {'label':'安全边界问题','severity':'致命','priority':1,'directions':['回答策略','思考档位'],'repair_hint':'调整 Prompt 策略和 Thinking 档位，保留安全边界'},
    {'label':'性能问题','severity':'按是否超线标记','priority':3,'directions':['降低思考档位','关闭耗时环节','调整检索参数'],'repair_hint':'降低 Thinking、关闭耗时环节，再用检索参数补质量'},
)


def category_definition(label):
    return next((dict(row) for row in DIAGNOSTIC_CATEGORIES if row['label']==label), {})
