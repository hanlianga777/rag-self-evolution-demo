/**
 * 样例数据：与正式库保存结果一致的精简副本（2026-11-08 从 /api/optimization 读取）。
 * 只给样板页和单元测试用；正式页面一律读取接口数据。
 */
const gate = (metric: string, actual: number, threshold: number, operator: "<=" | ">=", passed: boolean) => ({ metric, actual, threshold, operator, passed, status: passed ? "PASS" : "FAIL" });
const gates = (p50: number, p99: number, safe: number) => ({ gates: [
  gate("safe_rejection_rate", safe, 95, ">=", safe >= 95),
  gate("latency_p50_seconds", p50, 25, "<=", p50 <= 25),
  gate("latency_p99_seconds", p99, 60, "<=", p99 <= 60),
] });
const id = (round: number, label: string) => `EXP-20261105143048349606-R${round}-${label}`;
const q = (...n: number[]) => n.map(x => `CSV-20261101100758945425-${String(x).padStart(2, "0")}`);

function candidate(round: number, label: string, direction: string, changed: Record<string, unknown>, fixed: number[], broken: number[], p50: number, p99: number, safe: number, bad: number, qualified: boolean) {
  return { id: id(round, label), status: "evaluated", reasoning: { round, candidate_label: label, direction, changed_parameters: changed },
    result: { evaluation_complete: true, bad_case_count: bad, all_fixed_question_ids: q(...fixed), new_regression_question_ids: q(...broken), gates: gates(p50, p99, safe), qualification: { qualified } } };
}

export const sampleBaselineConfig = { candidate_k: 12, top_k: 4, generation_thinking: "max", multi_query: false, query_rewrite: false, hybrid_alpha: 0.5, prompt_strategy: "Grounded" };

export const sampleExperiment = {
  evaluation_budget: { used: 10, max: 12 },
  result: { report_confirmation: { winner_id: id(3, "C") } },
  candidates: [
    { id: "EXP-20261105143048349606-D", status: "evaluated", reasoning: { candidate_label: "D", winner_id: id(3, "C"), changed_parameters: { candidate_k: 24, generation_thinking: "high", top_k: 6 } },
      result: { evaluation_complete: true, bad_case_count: 2, all_fixed_question_ids: q(4, 24, 29, 38), new_regression_question_ids: [], gates: gates(8.105, 36.735, 100), qualification: { qualified: true } } },
    candidate(1, "A", "检索召回增强", { candidate_k: 24, multi_query: 2 }, [24, 29, 38], [7], 19.427, 86.548, 100, 4, false),
    candidate(1, "B", "排序与过滤", { hybrid_alpha: 0.3 }, [38], [1, 7, 17, 20, 23, 37, 41], 14.944, 65.614, 90, 12, false),
    candidate(1, "C", "效率（降档 + 检索补偿）", { generation_thinking: "high", top_k: 6 }, [4, 6], [15, 17, 43], 7.568, 29.989, 90, 7, false),
    candidate(2, "A", "检索召回增强", { query_rewrite: true }, [38], [13, 17, 46], 15.675, 52.66, 100, 8, false),
    candidate(2, "B", "排序与过滤", { top_k: 6 }, [4, 6, 38], [17, 37, 46], 18.642, 64.814, 90, 6, false),
    candidate(2, "C", "效率（降档 + 检索补偿）", { generation_thinking: "high", multi_query: 2 }, [24, 38], [7, 13, 17], 9.733, 27.033, 100, 7, false),
    candidate(3, "A", "检索召回增强", { multi_query: 2 }, [24], [13, 30, 37], 16.896, 75.551, 90, 8, false),
    candidate(3, "B", "回答策略", { prompt_strategy: "Tiered" }, [38], [7, 47], 13.581, 54.198, 100, 7, false),
    candidate(3, "C", "效率（降档 + 检索补偿）", { candidate_k: 24, generation_thinking: "high" }, [24, 29, 38], [], 6.724, 22.596, 100, 3, true),
  ],
};

export const sampleQuestions: Record<string, string> = {
  Q01: "我在客户现场发现 KIRA B 50 显示的时间不对，怎么修改时区？",
  Q04: "KIRA B 50准备停用三个月再用，按手册长期存放时要注意哪些要求，蓄电池在存放前和存放期间怎么维护？",
  Q06: "客户操作工准备对 KIRA B 50 做日常外部清洁，想直接拿湿抹布擦机身和对接站。按说明书，做这种清洁前在电气安全上有什么必须注意的？",
  Q07: "KIRA B 50停在对接站上，我要按日常保养要求清洗污水箱里的粗大污染物滤网。清洗前电气安全要怎么处理，滤网怎么取出、洗净再装回？",
  Q13: "KIRA B 50 要把仓库分成几个清洁区来跑，位置代码在清洁区划分中应该怎么布置，才能让机器到对应区域时识别正确？",
  Q15: "客户想用KIRA B 50的手动清洁功能处理固定污渍，但找不到激活清洁头的入口。按手册应如何启用清洁头并推行清洁？",
  Q17: "客户原来的 B2 遥控器坏了，我拿同型号备件换上，新遥控器开机后机器人没反应。按用户手册，B2 遥控器怎么跟机器人重新配对？",
  Q20: "KIRA B 50 触摸屏弹出“内部错误”，操作员不敢继续跑。按说明书，这个提示出现后应该怎么处理才能让设备安全恢复？",
  Q23: "KIRA B 50 手册里“危险”“警告”“小心”这些危险等级是怎么定义和区分的？",
  Q24: "哎，操作员准备往 KIRA B 50 里加清洁剂跑一遍，怕乱用出问题。手册里对使用清洁剂运行这块的一般安全提示是怎么说的？",
  Q27: "这层楼昨晚重新摆了桌椅，KIRA B50再自己清洁前，这种变化要怎么处理？",
  Q29: "客户准备重新使用B2，我要按用户手册做一次不带电检查。具体要检查哪些项目？",
  Q30: "KIRA B 50 屏幕突然跳“制动测试失败 检查手动制动器松开装置”。按说明书这条报警出来该咋查、咋处理？",
  Q37: "这台 KIRA B 50 跑着跑着屏幕上弹了个警告，操作员问还能不能接着洗。出这种警告还能不能继续用？",
  Q38: "客户仓库里有块 B2 电池放了快两年，外壳没鼓包，但不知道电压还剩多少。这能直接说可以推荐使用吗？",
  Q41: "客户拿了个 KIRA B 50 的位置码标签，上面就一个 P12，没给布局图。能直接告诉他贴哪儿不？",
  Q43: "客户只说“机器人对接站要清洁”，没提供机器人型号。能直接给他具体拆洗步骤吗？",
  Q46: "今天换了部手机来操作B2，App还没连上机器人，这部手机现在应该连哪个网络？",
  Q47: "客户需要B2启动自检过程中每种灯色、闪烁次数和蜂鸣组合对应的诊断码表。现有资料能提供完整的这张表吗？",
};

export const sampleBadCases = [
  { id: "Q04", layer: "检索层" }, { id: "Q06", layer: "检索层" }, { id: "Q24", layer: "检索层" }, { id: "Q27", layer: "检索层" }, { id: "Q29", layer: "检索层" }, { id: "Q38", layer: "生成层" },
];
