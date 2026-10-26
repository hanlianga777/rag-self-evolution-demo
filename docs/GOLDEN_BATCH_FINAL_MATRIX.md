# Golden真实运行50题诊断矩阵

未运行不是低分；Probe业务失败的QC按规则跳过；机器合格不是Human Gate批准。

|QID|Probe执行/结果|QC执行/分数/优先级|业务审计|人工关注原因|归因/需补跑|处置|
|---|---|---|---|---|---|---|
|Q01|completed/passed|completed/100.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q02|completed/passed|completed/96.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q03|completed/passed|completed/93.0/P2|passed|检索不连贯|retrieval_risk_not_answer_error / 无缺失阶段|进入现有异常审核，按证据明确处置；不重复付费|
|Q04|completed/passed|completed/88.0/P1|passed|QC P1、检索不连贯|retrieval_risk_not_answer_error、explicit_owner_review / 无缺失阶段|进入现有异常审核，按证据明确处置；不重复付费|
|Q05|completed/passed|completed/96.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q06|completed/passed|completed/90.0/P2|passed|检索不连贯|retrieval_risk_not_answer_error / 无缺失阶段|进入现有异常审核，按证据明确处置；不重复付费|
|Q07|completed/passed|completed/90.0/P1|passed|QC P1、检索不连贯|retrieval_risk_not_answer_error、explicit_owner_review / 无缺失阶段|进入现有异常审核，按证据明确处置；不重复付费|
|Q08|completed/passed|completed/90.0/P1|passed|QC P1、检索不连贯|retrieval_risk_not_answer_error、explicit_owner_review / 无缺失阶段|进入现有异常审核，按证据明确处置；不重复付费|
|Q09|completed/passed|completed/88.0/P1|passed|QC P1、语义/安全争议待复核|explicit_owner_review / 无缺失阶段|进入现有异常审核，按证据明确处置；不重复付费|
|Q10|completed/passed|completed/90.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q11|completed/passed|completed/96.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q12|completed/passed|completed/95.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q13|completed/passed|completed/95.0/P2|passed|检索不连贯|retrieval_risk_not_answer_error / 无缺失阶段|进入现有异常审核，按证据明确处置；不重复付费|
|Q14|completed/passed|completed/92.0/P2|passed|检索不连贯|retrieval_risk_not_answer_error / 无缺失阶段|进入现有异常审核，按证据明确处置；不重复付费|
|Q15|completed/passed|completed/93.0/P2|passed|语义/安全争议待复核|explicit_owner_review / 无缺失阶段|进入现有异常审核，按证据明确处置；不重复付费|
|Q16|completed/passed|completed/96.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q17|completed/passed|completed/90.0/P1|passed|QC P1、检索不连贯|retrieval_risk_not_answer_error、explicit_owner_review / 无缺失阶段|进入现有异常审核，按证据明确处置；不重复付费|
|Q18|completed/passed|completed/98.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q19|completed/passed|completed/98.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q20|completed/passed|completed/96.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q21|completed/passed|completed/100.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q22|completed/passed|completed/95.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q23|completed/passed|completed/95.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q24|completed/passed|completed/96.0/P2|passed|检索不连贯|retrieval_risk_not_answer_error / 无缺失阶段|进入现有异常审核，按证据明确处置；不重复付费|
|Q25|completed/passed|completed/100.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q26|completed/passed|completed/96.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q27|completed/passed|completed/92.0/P2|passed|检索不连贯|retrieval_risk_not_answer_error / 无缺失阶段|进入现有异常审核，按证据明确处置；不重复付费|
|Q28|completed/passed|completed/96.0/P2|passed|检索不连贯|retrieval_risk_not_answer_error / 无缺失阶段|进入现有异常审核，按证据明确处置；不重复付费|
|Q29|completed/passed|completed/92.0/P2|passed|检索不连贯|retrieval_risk_not_answer_error / 无缺失阶段|进入现有异常审核，按证据明确处置；不重复付费|
|Q30|completed/passed|completed/100.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q31|completed/passed|completed/95.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q32|completed/passed|completed/90.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q33|completed/passed|completed/90.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q34|completed/passed|completed/96.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q35|completed/passed|completed/94.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q36|completed/passed|completed/96.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q37|completed/passed|completed/90.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q38|completed/passed|completed/92.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q39|completed/passed|completed/95.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q40|completed/passed|completed/95.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q41|completed/passed|completed/95.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q42|completed/passed|completed/95.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q43|completed/passed|completed/95.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q44|completed/passed|completed/95.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q45|completed/passed|completed/95.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q46|completed/passed|completed/90.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q47|completed/passed|completed/90.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q48|completed/passed|completed/92.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q49|completed/passed|completed/95.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
|Q50|completed/passed|completed/96.0/P2|passed|无|machine_qualified / 无缺失阶段|机器合格，等待整组Human Gate确认|
