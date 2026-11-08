import { useState } from "react";
import { EvolutionTimeline } from "./evolution/EvolutionTimeline";
import { buildEvolutionModel } from "./evolution/model";
import { sampleBadCases, sampleBaselineConfig, sampleExperiment, sampleQuestions } from "./evolution/fixture";
import { AgentStats, OverviewSummary } from "./overview/OverviewSummary";
import { ParamChip, QuestionBadge, StatTransition, StatusBadge } from "./Primitives";
import { ReleasePanel } from "./release/ReleasePanel";
import { BaselineHero } from "./baseline/BaselineHero";
import { FinalRecommendation } from "./evolution/FinalRecommendation";

/** 页面级样板：概览首屏、Agent 顶部统计、进化路线。数据来自 fixture（与正式库一致）。 */
const GATE: Record<string, string> = { safe_rejection_rate: "安全拒答率", latency_p50_seconds: "P50", latency_p99_seconds: "P99" };
const nameOf = (candidate: any) => candidate.reasoning?.candidate_label === "D" ? "Candidate D" : `Round ${candidate.reasoning?.round} · Candidate ${candidate.reasoning?.candidate_label}`;

export function PageSamples() {
  const [opened, setOpened] = useState<string | null>(null);
  const model = buildEvolutionModel(sampleExperiment, sampleBaselineConfig, metric => GATE[metric] ?? metric, nameOf);
  return <div style={{ display: "grid", gap: 40 }}>
    <section>
      <h2 className="ui-sample-title">概览 · 项目概览</h2>
      <OverviewSummary
        correct={{ from: 44, to: 48 }} total={50} fixedCount={4} newBadCount={0} gates={{ passed: 11, total: 11 }}
        p99={{ from: 42.2, to: 36.7 }} p50={{ from: 16.7, to: 8.1 }} safeRefusal={{ from: 95, to: 100 }} budget={{ used: 10, max: 12 }}
        status={{ kind: "pending_release", candidate: "Candidate D 推荐待发布", online: "初始配置" }}
        primaryAction={{ label: "去发布", onClick: () => {} }}
        flow={[
          { label: "知识库", fact: "4 份文档已索引", tips: ["9 个知识主题", "Parent-Child 分块"] },
          { label: "Golden Dataset", fact: "50 题已冻结", tips: ["Positive 20 · Ablation 10 · Negative 20", "硬校验 · Probe · QC 全部通过"] },
          { label: "Baseline", fact: "11/11 Hard Gate · 6 个 Bad Case", tips: ["Thinking Max", "检索层 5 · 生成层 1"] },
          { label: "Agent", fact: "3 轮 + Candidate D", tips: ["Round 3 · Candidate C 首次零新增 Bad Case", "Candidate D 再修好 Q04"] },
          { label: "发布", fact: "Candidate D 待发布" },
          { label: "问答验证", fact: "4 道修好的题可逐题对比" },
        ]}
      />
    </section>


    <section>
      <h2 className="ui-sample-title">Baseline · Baseline 报告</h2>
      <BaselineHero gates={{ passed: 11, total: 11 }} correct={44} total={50} badCount={6} layers={[{ label: "检索层", count: 5 }, { label: "生成层", count: 1 }]} thinking="Max" p50={16.7} p99={42.2}
        stages={[{ label: "Generation", seconds: 838.4, share: 95.8 }, { label: "Embedding Retrieval", seconds: 17.3, share: 2.0 }, { label: "Rerank", seconds: 16.2, share: 1.9 }, { label: "其他", seconds: 2.8, share: 0.3 }]} />
    </section>

    <section>
      <h2 className="ui-sample-title">发布 · 发布前</h2>
      <ReleasePanel
        online={{ name: "初始配置", params: [{ label: "Candidate K", value: "12" }, { label: "Top-K", value: "4" }, { label: "Thinking", value: "Max" }] }}
        candidate={{ name: "Candidate D", params: [{ label: "Candidate K", value: "24" }, { label: "Top-K", value: "6" }, { label: "Thinking", value: "High" }] }}
        changes={[{ key: "candidate_k", label: "Candidate K", from: "12", to: "24" }, { key: "top_k", label: "Top-K", from: "4", to: "6" }, { key: "thinking", label: "Thinking", from: "Max", to: "High" }]}
        results={{ correct: { from: 44, to: 48 }, total: 50, newBad: 0, gates: { passed: 11, total: 11 }, p99: { from: 42.2, to: 36.7 } }}
        steps={{ reportConfirmed: true, eligible: { ok: true, items: ["Hard Gate 11/11", "零新增 Bad Case", "修好 4 个"] }, released: { ok: false } }}
        canRelease onRelease={() => {}} onReport={() => {}} />
      <div style={{ height: 16 }} />
      <h2 className="ui-sample-title">发布 · 发布后</h2>
      <ReleasePanel
        online={{ name: "初始配置", params: [{ label: "Candidate K", value: "12" }, { label: "Top-K", value: "4" }, { label: "Thinking", value: "Max" }] }}
        candidate={{ name: "Candidate D", params: [{ label: "Candidate K", value: "24" }, { label: "Top-K", value: "6" }, { label: "Thinking", value: "High" }] }}
        changes={[{ key: "candidate_k", label: "Candidate K", from: "12", to: "24" }, { key: "top_k", label: "Top-K", from: "4", to: "6" }, { key: "thinking", label: "Thinking", from: "Max", to: "High" }]}
        results={{ correct: { from: 44, to: 48 }, total: 50, newBad: 0, gates: { passed: 11, total: 11 }, p99: { from: 42.2, to: 36.7 } }}
        steps={{ reportConfirmed: true, eligible: { ok: true, items: ["Hard Gate 11/11", "零新增 Bad Case", "修好 4 个"] }, released: { ok: true, at: "2026/11/08 03:10" } }}
        canRelease={false} onSnapshot={() => {}} onReport={() => {}} />
    </section>

    <section>
      <h2 className="ui-sample-title">Agent 工作台 · 顶部统计 + 进化路线</h2>
      <AgentStats rounds={3} candidates={10} budget={{ used: 10, max: 12 }} status={{ kind: "recommended", text: "推荐 Candidate D，待人工发布" }} />
      <div className="tabs" style={{ margin: "16px 0 18px" }}>
        {["进化路线", "A/B/C/D", "Sandbox", "Regression Check", "最终推荐"].map((tab, index) => <button key={tab} className={index === 0 ? "selected" : ""}>{tab}</button>)}
      </div>
      <EvolutionTimeline model={model} baseline={{ correct: 44, total: 50, badCases: sampleBadCases }} questionText={id => sampleQuestions[id]} onOpen={setOpened} onOpenDiagnosis={() => {}}>
        <article className="ui-evo-card winner" style={{ gap: 14 }}>
          <header className="ui-evo-card-head"><strong>Candidate D · 在 Winner 上精修</strong><span style={{ display: "flex", gap: 6 }}><StatusBadge kind="qualified" /><StatusBadge kind="recommended" /></span></header>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>Winner（Round 3 · Candidate C）+ <ParamChip label="Top-K" from={4} to={6} keyParam keyLabel="唯一新增" /></div>
          <div style={{ display: "flex", gap: 28, flexWrap: "wrap", fontSize: 15 }}>
            <span>答对 <StatTransition from={47} to={48} unit="/ 50" /></span>
            <span>新增 Bad Case <b>0</b></span>
            <span>P99 <StatTransition from={22.6} to={36.7} unit="秒" better="lower" digits={1} /></span>
          </div>
          <div style={{ fontSize: 13, color: "var(--ui-ink-2)", display: "grid", gap: 6 }}>
            <div>预测修好 <QuestionBadge id="Q04" tone="fixed" question={sampleQuestions.Q04} /> <QuestionBadge id="Q06" tone="open" question={sampleQuestions.Q06} />，实际修好 <QuestionBadge id="Q04" tone="fixed" question={sampleQuestions.Q04} /></div>
            <div>仍未修好：<QuestionBadge id="Q06" tone="open" question={sampleQuestions.Q06} detail="关键说明 Rerank 第 7 位，Top-K 6 仍纳入不了" /> <QuestionBadge id="Q27" tone="open" question={sampleQuestions.Q27} detail="关键说明 Rerank 第 24 位" /></div>
          </div>
          <p style={{ margin: 0, fontSize: 13, color: "var(--ui-muted)" }}>（正式页面这里沿用现有 DStory：预测 vs 实际、受保护题、门槛逐项、并列比较与结论句。）</p>
        </article>
      </EvolutionTimeline>
      <h2 className="ui-sample-title" style={{ marginTop: 32 }}>Agent 工作台 · 最终推荐</h2>
      {model.d && <FinalRecommendation chosen={model.d} runnerUp={model.rounds[2].candidates[2]} baselineCorrect={44}
        reason="Candidate D 修好了 Q04，Bad Case 比 Round 3 · Candidate C 少 1 个，且没有新增 Bad Case，满足发布条件，推荐 Candidate D。"
        others={model.rounds.flatMap(r => r.candidates).filter(c => !c.winner)} questionText={id => sampleQuestions[id]} onRelease={() => {}} onOpen={setOpened} />}
      {opened && <p style={{ marginTop: 8, color: "var(--ui-muted)" }}>点击了 {opened}（正式页面会打开方案详情抽屉）</p>}
    </section>
  </div>;
}
