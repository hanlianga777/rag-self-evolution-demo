"""One product vocabulary for saved-data diagnosis, Agent inputs and pages."""
DIAGNOSTIC_CATEGORIES = (
    {'label':'检索失败','severity':'严重','priority':1,'directions':['改写查询','HyDE','多路查询','候选数','混合检索','别名映射'],'repair_hint':'换几种问法查找、多找一些候选内容'},
    {'label':'检索噪声','severity':'严重','priority':2,'directions':['重排','保留条数','最低分数线','元数据筛选'],'repair_hint':'多保留几段内容、加强排序'},
    {'label':'回答问题','severity':'中等','priority':2,'directions':['回答策略','思考档位'],'repair_hint':'补齐回答要点、先问清关键条件'},
    {'label':'过度拒答','severity':'中等','priority':3,'directions':['回答策略','思考档位'],'repair_hint':'已有依据的部分直接回答'},
    {'label':'安全边界','severity':'致命','priority':1,'directions':['回答策略'],'repair_hint':'保留安全警告、拒绝越界操作'},
    {'label':'延迟','severity':'按是否超线标记','priority':None,'directions':['降低思考档位','关闭耗时环节','调整检索参数'],'repair_hint':'先减少耗时，再检查质量有没有下降'},
)


def category_definition(label):
    return next((dict(row) for row in DIAGNOSTIC_CATEGORIES if row['label']==label), {})
