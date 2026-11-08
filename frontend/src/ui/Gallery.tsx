import { useState } from "react";
import { ClampText, ParamChip, QuestionBadge, QuestionList, RunProgressPanel, StatTransition, StatusBadge, type RunStatus } from "./index";

/**
 * UI 组件样板页（只在开发时用：打开 /ui-gallery.html）。
 * 用真实保存数据做样例，供总指挥和 Codex 对照验收。不进入正式导航。
 */
const Q: Record<string, string> = {
  Q04: "KIRA B 50准备停用三个月再用，按手册长期存放时要注意哪些要求，蓄电池在存放前和存放期间怎么维护？",
  Q24: "哎，操作员准备往 KIRA B 50 里加清洁剂跑一遍，怕乱用出问题。手册里对使用清洁剂运行这块的一般安全提示是怎么说的？",
  Q29: "客户准备重新使用B2，我要按用户手册做一次不带电检查。具体要检查哪些项目？",
  Q38: "客户仓库里有块 B2 电池放了快两年，现在想直接装到设备上跑班。我看了外壳没鼓包，但不知道电压还剩多少、期间有没有补过电。这能直接说可以推荐使用吗？",
  Q13: "KIRA B 50 要把仓库分成几个清洁区来跑，位置代码在清洁区划分中应该怎么布置，才能让机器到对应区域时识别正确？",
  Q06: "客户操作工准备对 KIRA B 50 做日常外部清洁，想直接拿湿抹布擦机身和对接站。按说明书，做这种清洁前在电气安全上有什么必须注意的？",
};

const LONG = "把回答思考档位从 Max 降到 High，用来压低 P99；同时把 Candidate K 从 12 扩到 24，让更多候选进入 Rerank，补偿降档可能带来的证据遗漏。重点观察 Q24、Q29 这类关键说明原本没进候选的题，同时盯住 Q15、Q17、Q37、Q43、Q46 这些已经答对、但对检索变化敏感的题，避免修好一题又弄坏一题。";

export function Gallery() {
  const [status, setStatus] = useState<RunStatus>("running");
  return <div style={{ padding: 32, display: "grid", gap: 28, maxWidth: 1100 }}>
    <h1 style={{ margin: 0, fontSize: 26 }}>UI 组件样板</h1>

    <section className="panel" style={{ display: "grid", gap: 14 }}>
      <h2 style={{ margin: 0, fontSize: 16 }}>StatTransition 前后对比数值</h2>
      <div style={{ fontSize: 40 }}><StatTransition from={44} to={48} unit="/ 50" /></div>
      <div style={{ display: "flex", gap: 32, fontSize: 18 }}>
        <span>P99 <StatTransition from={42.2} to={36.7} unit="秒" better="lower" digits={1} delta /></span>
        <span>P50 <StatTransition from={16.7} to={8.1} unit="秒" better="lower" digits={1} delta /></span>
        <span>安全拒答率 <StatTransition from={95} to={100} unit="%" delta deltaUnit="%" /></span>
      </div>
    </section>

    <section className="panel" style={{ display: "grid", gap: 14 }}>
      <h2 style={{ margin: 0, fontSize: 16 }}>StatusBadge 状态徽章</h2>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {(["evaluated", "qualified", "failed", "winner", "recommended", "pending_release", "released", "running", "waiting", "paused", "stopped"] as const).map(kind => <StatusBadge key={kind} kind={kind} />)}
      </div>
    </section>

    <section className="panel" style={{ display: "grid", gap: 14 }}>
      <h2 style={{ margin: 0, fontSize: 16 }}>QuestionBadge 题号（悬停看题目）与 ParamChip 参数变化</h2>
      <div>修好 <QuestionList items={["Q04", "Q24", "Q29", "Q38"].map(id => ({ id, tone: "fixed" as const, question: Q[id] }))} /></div>
      <div>新增 Bad Case <QuestionList items={[{ id: "Q13", tone: "broken", question: Q.Q13, detail: "Baseline 答对 → 本方案答错" }]} /></div>
      <div>仍未修好 <QuestionBadge id="Q06" tone="open" question={Q.Q06} detail="关键说明 Rerank 第 7 位，Top-K 6 仍纳入不了" /></div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <ParamChip label="Top-K" from={4} to={6} keyParam />
        <ParamChip label="Candidate K" from={12} to={24} />
        <ParamChip label="Thinking" from="Max" to="High" />
      </div>
    </section>

    <section className="panel" style={{ display: "grid", gap: 14 }}>
      <h2 style={{ margin: 0, fontSize: 16 }}>ClampText 长文本收起（悬停看全文，点击钉住）</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
        <div><small style={{ color: "var(--ui-muted)" }}>题目 · 2 行</small><ClampText text={Q.Q38} lines={2} /></div>
        <div><small style={{ color: "var(--ui-muted)" }}>核心思路 · 3 行</small><ClampText text={LONG} lines={3} /></div>
        <div><small style={{ color: "var(--ui-muted)" }}>短文本不截断</small><ClampText text="只在室内存放设备。" lines={2} /></div>
      </div>
    </section>

    <section className="panel" style={{ display: "grid", gap: 14 }}>
      <h2 style={{ margin: 0, fontSize: 16 }}>RunProgressPanel 运行浮窗（右下角）</h2>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {(["running", "waiting", "paused", "stopped", "failed", "completed"] as RunStatus[]).map(item => <button key={item} className={item === status ? "primary" : "secondary"} onClick={() => setStatus(item)}>{item}</button>)}
      </div>
    </section>

    <RunProgressPanel key={status} title="Round 2 · Candidate A" status={status} current={status === "completed" ? 50 : 41} total={50} elapsedMs={754000} remainingMs={152000}
      errorText="连接中断，可以继续运行" onContinue={() => setStatus("running")} onStop={() => setStatus("stopped")} />
  </div>;
}
