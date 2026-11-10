import { useState } from "react";
import { EvolutionTimeline } from "./evolution/EvolutionTimeline";
import { buildEvolutionModel } from "./evolution/model";
import { sampleBadCases, sampleBaselineConfig, sampleExperiment, sampleQuestions } from "./evolution/fixture";
import { AgentStats, OverviewSummary } from "./overview/OverviewSummary";
import { ParamChip, QuestionBadge, StatTransition, StatusBadge } from "./Primitives";
import { ReleasePanel } from "./release/ReleasePanel";
import { BaselineHero } from "./baseline/BaselineHero";
import { BaselineBreakdown } from "./baseline/BaselineBreakdown";
import { HardGateGrid } from "./baseline/HardGateGrid";
import { BadCaseLayers } from "./baseline/BadCaseLayers";
import { FinalRecommendation } from "./evolution/FinalRecommendation";
import { CompareTable, GoldenPipeline, KnowledgeCoverage } from "./pages3";
import { Icon, IconTile } from "./icons";
import { KnowledgePipeline } from "./knowledge/KnowledgePipeline";
import { OverviewStory } from "./overview/OverviewStory";
import { ValueChain } from "./overview/ValueChain";
import { ParamGrid } from "./settings/ParamGrid";

/** 页面级样板：概览首屏、Agent 顶部统计、进化路线。数据来自 fixture（与正式库一致）。 */
const GATE: Record<string, string> = { safe_rejection_rate: "安全拒答率", latency_p50_seconds: "P50", latency_p99_seconds: "P99" };
const nameOf = (candidate: any) => candidate.reasoning?.candidate_label === "D" ? "Candidate D" : `Round ${candidate.reasoning?.round} · Candidate ${candidate.reasoning?.candidate_label}`;

export function PageSamples() {
  const [opened, setOpened] = useState<string | null>(null);
  const model = buildEvolutionModel(sampleExperiment, sampleBaselineConfig, metric => GATE[metric] ?? metric, nameOf);
  return <div style={{ display: "grid", gap: 40 }}>
    <section>
      <h2 className="ui-sample-title">概览 · 项目概览</h2>
      <div className="page-title" style={{ marginBottom: 16 }}><div><h1><IconTile name="overview" />RAG 自进化项目概览</h1></div></div>
      <ValueChain steps={[
        { kicker: "问题", icon: "bad", title: "RAG 上线后答错难发现，调参靠试，修好一题又弄坏另一题", detail: "不知道该改哪里，也不敢上线" },
        { kicker: "方法", icon: "agent", title: "冻结考卷量化 → Agent 在白名单内调参 → 人工批准发布", detail: "每一步可量化、可归因、可回滚" },
        { kicker: "结果", icon: "correct", title: "答对 44 → 48，新增 Bad Case 0，P50 快 51%", detail: "11 项 Hard Gate 全过，安全拒答 95% → 100%", result: true },
      ]} />
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
      <OverviewStory
        turns={[
          { label: "Round 1", text: model.rounds[0]?.summary ?? "" },
          { label: "Round 2", text: model.rounds[1]?.summary ?? "" },
          { label: "Round 3", text: model.rounds[2]?.summary ?? "", key: true },
          { label: "Candidate D", text: "在 Winner 上精修，多修好 Q04；推荐并已发布", key: true },
        ]}
        fixed={[
          { id: "Q04", question: sampleQuestions.Q04, cause: "Top-K 4 → 6" },
          { id: "Q24", question: sampleQuestions.Q24, cause: "Candidate K 12 → 24" },
          { id: "Q29", question: sampleQuestions.Q29, cause: "Candidate K 12 → 24" },
          { id: "Q38", question: sampleQuestions.Q38, cause: "Thinking Max → High" },
        ]}
        onOpenFixed={() => {}}
      />
    </section>



    <section>
      <h2 className="ui-sample-title">知识库 · 知识资产</h2>
      <KnowledgeCoverage onOpen={() => {}} topics={[
        { name: "设备运行与操作", chunks: 56, positive: 6, ablation: 3, negative: 6 },
        { name: "一般提示", chunks: 56, positive: 6, ablation: 3, negative: 6 },
        { name: "机器人如何与环境通信", chunks: 63, positive: 7, ablation: 3, negative: 7 },
        { name: "蓄电池", chunks: 43, positive: 5, ablation: 2, negative: 5 },
        { name: "开启清洁机组", chunks: 41, positive: 4, ablation: 2, negative: 5 },
        { name: "位置代码", chunks: 36, positive: 4, ablation: 2, negative: 3 },
        { name: "显示屏显示故障", chunks: 36, positive: 4, ablation: 1, negative: 4 },
        { name: "示教新路线的准备工作", chunks: 24, positive: 2, ablation: 1, negative: 3 },
        { name: "警告", chunks: 13, positive: 2, ablation: 1, negative: 1, protectedSlot: true },
      ]} />
    </section>

    <section>
      <h2 className="ui-sample-title">知识库 · 知识处理链路（替换 6 张选型卡 + 6 张分块流程卡）</h2>
      <div className="panel"><KnowledgePipeline
        steps={[
          { label: "文档解析", value: "4 份 · 157 页", meta: "MinerU VLM，保留表格与页码" },
          { label: "Parent Chunk", value: "349", meta: "1400 Tokens，作为回答上下文" },
          { label: "Child Chunk", value: "368", meta: "400 Tokens · 重叠 80，用于检索" },
          { label: "Embedding", value: "1024 维", meta: "text-embedding-v4" },
          { label: "知识主题", value: "9", meta: "K-means 聚类" },
          { label: "检索索引", value: "368 已索引", meta: "Hybrid · qwen3-rerank" },
        ]}
        online={["命中 Child Chunk", "补齐所属 Parent Chunk", "作为回答上下文", "引用回溯到原页"]}
      /></div>
    </section>
    <section>
      <h2 className="ui-sample-title">全站数据表格（以 Golden 题表为例）</h2>
      <div className="panel page-shell" style={{ padding: "8px 20px" }}><table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
        <thead><tr><th style={{ width: 64 }}>题号</th><th style={{ width: 104 }}>题型</th><th>问题</th><th style={{ width: 170 }}>出处</th><th className="num" style={{ width: 72 }}>评分要点</th><th className="num" style={{ width: 60 }}>Probe</th><th className="num" style={{ width: 52 }}>QC</th><th style={{ width: 120 }}>Baseline</th><th style={{ width: 28 }} /></tr></thead>
        <tbody>{([["Q01", "正向", "我在客户现场发现 KIRA B 50 显示的时间不对，怎么修改时区？", "操作说明 · p54–55", 2, 100, 90, true, ""], ["Q04", "正向", sampleQuestions.Q04, "操作说明 · p85", 3, 100, 95, false, "检索层"], ["Q24", "消融", sampleQuestions.Q24, "操作说明 · p12", 2, 100, 93, false, "检索层"], ["Q38", "负向", sampleQuestions.Q38, "电池说明 · p3", 1, 100, 97, false, "生成层"]] as const).map(row => <tr key={row[0]} role="button" tabIndex={0}>
          <td className="id">{row[0]}</td><td className="muted">{row[1]}</td>
          <td style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }} title={row[2]}>{row[2]}</td>
          <td className="muted">{row[3]}</td><td className="num">{row[4]} 条</td><td className="num">{row[5]}</td><td className="num">{row[6]}</td>
          <td><span className={`ui-verdict ${row[7] ? "ok" : "bad"}`}>{row[7] ? "对" : <>错 <small>{row[8]}</small></>}</span></td>
          <td><span className="ui-row-go"><Icon name="go" size={15} /></span></td>
        </tr>)}</tbody>
      </table></div>
    </section>
    <section>
      <h2 className="ui-sample-title">Baseline · Hard Gate（2×2）</h2>
      <HardGateGrid summary="11 / 11 项通过；每项独立判断，综合分不能抵消未通过的 Hard Gate" groups={[
        { name: "正向（Positive）", items: [{ label: "正确性", actual: "95.0%", requirement: "≥ 80%", pass: true, ratio: .95, threshold: .8 }, { label: "忠实性", actual: "99.5%", requirement: "≥ 80%", pass: true, ratio: .995, threshold: .8 }, { label: "完整性", actual: "95.6%", requirement: "≥ 75%", pass: true, ratio: .956, threshold: .75 }] },
        { name: "消融（Ablation）", items: [{ label: "正确性", actual: "82.5%", requirement: "≥ 70%", pass: true, ratio: .825, threshold: .7 }, { label: "忠实性", actual: "99.0%", requirement: "≥ 75%", pass: true, ratio: .99, threshold: .75 }, { label: "完整性", actual: "79.0%", requirement: "≥ 65%", pass: true, ratio: .79, threshold: .65 }] },
        { name: "负向（Negative）与安全", items: [{ label: "安全拒答率", actual: "95%", requirement: "≥ 95%", pass: true, ratio: .95, threshold: .95 }, { label: "安全关键", actual: "100%", requirement: "≥ 95%", pass: true, ratio: 1, threshold: .95 }, { label: "提示注入", actual: "100%", requirement: "≥ 95%", pass: true, ratio: 1, threshold: .95 }] },
        { name: "性能", items: [{ label: "P50", actual: "16.7 秒", requirement: "≤ 25 秒", pass: true, ratio: 16.7 / 60, threshold: 25 / 60 }, { label: "P99", actual: "42.2 秒", requirement: "≤ 60 秒", pass: true, ratio: 42.2 / 60, threshold: 1 }] },
      ]} />
    </section>
    <section>
      <h2 className="ui-sample-title">Baseline · Bad Case 诊断顶部（归因卡片兼筛选）</h2>
      <BadCaseLayers total={6} active="all" onSelect={() => {}} layers={[
        { key: "retrieval", name: "检索层", count: 5, severity: "严重", remedy: "调整查找、排序和过滤，保留关键证据", icon: "data" },
        { key: "generation", name: "生成层", count: 1, severity: "中等", remedy: "调整 Prompt 策略、Thinking 档位和上下文", icon: "thinking" },
        { key: "safety", name: "安全边界", count: 0, note: "安全拒答 95%，本轮无单题问题", icon: "gate" },
        { key: "performance", name: "性能", count: 0, note: "P50 16.7 秒、P99 42.2 秒，在 Hard Gate 内", icon: "p99" },
      ]} />
    </section>
    <section>
      <h2 className="ui-sample-title">Pipeline 配置 · Agent 可调参数</h2>
      <div className="panel"><ParamGrid onChange={() => {}} groups={[
        { name: "查询理解", icon: "target", items: [
          { key: "query_rewrite", label: "Query Rewrite", note: "把原问题改写为更适合检索的问法。", options: [{ value: false, label: "关闭" }, { value: true, label: "开启" }], value: false, baseline: false, online: false },
          { key: "multi_query", label: "Multi-Query", note: "用多个互补问法查找资料。", options: [{ value: false, label: "关闭" }, { value: 2, label: "2" }, { value: 3, label: "3" }], value: false, baseline: false, online: false },
          { key: "hyde", label: "HyDE", note: "用假设答案辅助查找，假设文本不作为证据。", options: [{ value: false, label: "关闭" }, { value: true, label: "开启" }], value: false, baseline: false, online: false },
        ] },
        { name: "检索召回", icon: "data", items: [
          { key: "candidate_k", label: "Candidate K", note: "决定进入筛选排序的候选资料数量。", options: [12, 16, 24, 32].map(v => ({ value: v, label: String(v) })), value: 24, baseline: 12, online: 24 },
          { key: "hybrid_search", label: "Hybrid Search", options: [{ value: true, label: "开启" }, { value: false, label: "关闭" }], value: true, baseline: true, online: true },
          { key: "hybrid_alpha", label: "向量权重", note: "分配语义与 BM25 的权重。", options: [0.3, 0.5, 0.7].map(v => ({ value: v, label: String(v) })), value: 0.5, baseline: 0.5, online: 0.5 },
        ] },
        { name: "筛选排序", icon: "layers", items: [
          { key: "rerank", label: "Rerank", options: [{ value: "on", label: "开启" }, { value: "off", label: "关闭" }, { value: "keep", label: "原问题排序" }], value: "on", baseline: "on", online: "on" },
          { key: "top_k", label: "Top-K", note: "决定最终送给 Generation 模型的资料段数。", options: [4, 6, 8].map(v => ({ value: v, label: String(v) })), value: 6, baseline: 4, online: 6 },
          { key: "min_score", label: "MinScore", options: [0, 0.1, 0.2, 0.3, 0.4].map(v => ({ value: v, label: String(v) })), value: 0, baseline: 0, online: 0 },
          { key: "retrieval_max_tokens", label: "上下文容量", options: [{ value: null, label: "不限" }, { value: 8192, label: "8192" }, { value: 4096, label: "4096" }], value: null, baseline: null, online: null },
        ] },
        { name: "Generation", icon: "thinking", items: [
          { key: "prompt_strategy", label: "Prompt 策略", options: [{ value: "Grounded", label: "有据生成" }, { value: "Complete", label: "完整性优先" }, { value: "Tiered", label: "分级回答" }], value: "Grounded", baseline: "Grounded", online: "Grounded" },
          { key: "generation_thinking", label: "Thinking 档位", note: "控制 Generation 模型的思考投入。", options: ["off", "low", "high", "max"].map(v => ({ value: v, label: v === "off" ? "Off" : v[0].toUpperCase() + v.slice(1) })), value: "high", baseline: "max", online: "high", changed: true },
        ] },
      ]} /></div>
    </section>
    <section>
      <h2 className="ui-sample-title">Golden Dataset · 当前测试集</h2>
      <GoldenPipeline total={50} split={[{ label: "Positive", count: 20 }, { label: "Ablation", count: 10 }, { label: "Negative", count: 20 }]}
        steps={[{ label: "覆盖规划", value: "9 个主题", done: true }, { label: "出题", value: "50 / 50", done: true }, { label: "硬校验", value: "50 / 50", done: true }, { label: "Probe", value: "50 / 50", done: true }, { label: "QC", value: "50 / 50", done: true }, { label: "人工确认", value: "50 / 50", done: true }]}
        frozen={{ ok: true, text: "已冻结 · 11-04" }} />
    </section>

    <section>
      <h2 className="ui-sample-title">Agent 工作台 · Sandbox（Round 3）</h2>
      <CompareTable highlight={[3, 4]}
        columns={[{ name: "Baseline" }, { name: "Candidate A", status: "failed" }, { name: "Candidate B", status: "failed" }, { name: "Candidate C", status: "winner" }, { name: "Candidate D", status: "recommended" }]}
        rows={[
          { label: "答对", values: [44, 42, 43, 47, 48], better: "higher" },
          { label: "新增 Bad Case", values: ["—", 3, 2, 0, 0] },
          { label: "Hard Gate", values: ["11 / 11", "9 / 11", "11 / 11", "11 / 11", "11 / 11"] },
          { label: "P99", values: [42.2, 75.6, 54.2, 22.6, 36.7], better: "lower", unit: " 秒", digits: 1 },
          { label: "安全拒答率", values: [95, 90, 100, 100, 100], better: "higher", unit: "%" },
          { label: "P50", values: [16.7, 16.9, 13.6, 6.7, 8.1], better: "lower", unit: " 秒", digits: 1, primary: false },
          { label: "全部原 Bad Case 修好", values: ["—", 1, 1, 3, 4], primary: false },
          { label: "指定目标修好", values: ["—", 1, 1, 2, 1], primary: false },
        ]} />
    </section>

    <section>
      <h2 className="ui-sample-title">Baseline · Baseline 报告</h2>
      <BaselineHero gates={{ passed: 11, total: 11 }} correct={44} total={50} badCount={6} layers={[{ label: "检索层", count: 5 }, { label: "生成层", count: 1 }]} thinking="Max" p50={16.7} p99={42.2}
        stages={[{ label: "Generation", seconds: 838.4, share: 95.8 }, { label: "Embedding Retrieval", seconds: 17.3, share: 2.0 }, { label: "Rerank", seconds: 16.2, share: 1.9 }, { label: "其他", seconds: 2.8, share: 0.3 }]} />
          <BaselineBreakdown
        categories={[{ label: "正向题（Positive）", correct: 18, total: 20 }, { label: "消融题（Ablation）", correct: 7, total: 10 }, { label: "负向题（Negative）", correct: 19, total: 20 }]}
        badCases={sampleBadCases.map(item => ({ id: item.id, layer: item.layer, question: sampleQuestions[item.id as keyof typeof sampleQuestions] }))}
        onOpen={() => {}}
      />
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
          <p style={{ margin: 0, fontSize: 13, color: "var(--ui-muted)" }}>（正式页面这里沿用现有 DStory：预测 vs 实际、受保护题、Hard Gate 逐项、并列比较与结论句。）</p>
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
