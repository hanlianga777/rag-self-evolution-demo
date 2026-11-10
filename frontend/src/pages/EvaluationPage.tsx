import { judgePresentation } from "../components/judgePresentation";
import { shortSourceName } from "./FrozenQuestionDetails";
import { Icon, IconLabel, IconTile } from "../ui/icons";
import { BaselineBreakdown } from "../ui/baseline/BaselineBreakdown";
import { HardGateGrid } from "../ui/baseline/HardGateGrid";
import { BaselineHero } from "../ui/baseline/BaselineHero";
import { caseData } from "../components/EvaluationDiagnosis";
import { usePageTab } from "../usePageTab";
import { savedSnapshot } from "../evaluationProgress";
import { DataTable } from "../components/DataTable";
import { PricePauseNotice } from "../components/RuntimeSettings";
import { mergeEvaluationProgress, hasEvaluationDetails } from "../evaluationProgress";
import { StoryDisclosure } from "../components/Storytelling";
import './evaluation-workspaces.css';
import { savedDirections, businessDiagnosisRows, businessVerdict } from '../components/EvaluationDiagnosis';
import { BadCaseOverview, ProductDiagnostics, productQuestionLabel, timingStages } from "../components/ProductDiagnostics";
import { PageShell } from "../components/PageShell";

import { useEffect, useState } from "react";
import { Play } from "lucide-react";
import { cachedJson, errorMessage, getJson, postJson } from "../api";
import { Badge, DrawerSection, Metric, Section, Status, TruncatedText } from "../components/Primitives";
import { formatValue, thinkingLabel } from "../components/PipelineFields";
import { CaseAnswer } from "../components/CaseAnswer";
import { ConfirmDialog, Drawer } from "../components/Dialog";
import { displayText, gateNames, gateEnglishNames, localShortTime } from "../display";
import { useOperation } from "../operation";

type Row = Record<string, any>;


export { gateNames } from "../display";
const format = (value: unknown, suffix = "") => typeof value === "number" ? `${suffix === "%" ? Number(value.toFixed(1)) : value.toFixed(1)}${suffix}` : "未采集";
const group = (metric: string) => metric.startsWith("positive_") ? "正向（Positive）" : metric.startsWith("ablation_") ? "消融（Ablation）" : metric.startsWith("latency_") ? "性能" : "负向（Negative）与安全";
const gateValue = (gate: Row) => format(gate.actual, gate.metric.startsWith("latency_") ? " 秒" : "%");
const gateThreshold = (gate: Row) => `${gate.operator === ">=" ? "≥" : "≤"} ${format(gate.threshold, gate.metric.startsWith("latency_") ? " 秒" : "%")}`;


// The supplied grid is display-only. Keep the original row drilldowns at the page boundary.
function BaselineGates({ gates, passedCount, onSelect }: { gates: Row[]; passedCount?: number; onSelect: (gate: Row) => void }) {
  const groups = ['正向（Positive）', '消融（Ablation）', '负向（Negative）与安全', '性能'].map(name => ({name, rows: gates.filter(gate => group(gate.metric) === name)}));
  const ordered = groups.flatMap(group => group.rows);
  return <div className="baseline-gate-grid" ref={node => {
    node?.querySelectorAll<HTMLElement>('.ui-hg-card li').forEach((item, index) => {
      const gate = ordered[index];
      item.tabIndex = 0;
      item.setAttribute('role', 'button');
      item.setAttribute('aria-label', `${gateNames[gate.metric] || gate.metric}，查看详情`);
      item.title = gateEnglishNames[gate.metric] || gate.metric;
      item.onclick = () => onSelect(gate);
      item.onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(gate); } };
      item.dataset.status = ['PASS', 'FAIL'].includes(gate.status) ? gate.status : 'unknown';
      item.querySelector('.ui-hg-dot')?.setAttribute('aria-label', gate.status === 'PASS' ? '通过' : gate.status === 'FAIL' ? '未通过' : '未判定');
    });
    node?.querySelectorAll<HTMLElement>('.ui-hg-card header .ui-verdict').forEach((badge, index) => {
      const rows = groups[index].rows;
      badge.className = `ui-verdict ${rows.length && rows.every(gate => gate.status === 'PASS') ? 'ok' : rows.some(gate => gate.status === 'FAIL') ? 'bad' : ''}`;
      badge.textContent = rows.length ? `${rows.filter(gate => gate.status === 'PASS').length} / ${rows.length} 通过` : '未采集';
    });
  }}><HardGateGrid summary={`${passedCount ?? '未知'} / ${gates.length || '未知'} 项通过；每项独立判断，综合分不能抵消未通过的 Hard Gate。`} groups={groups.map(({ name, rows }) => ({name, items: rows.map(gate => ({
    label: (gateNames[gate.metric] || gate.metric).replace(/^(正向（Positive）|消融（Ablation）)/, ''),
    actual: gateValue(gate), requirement: gateThreshold(gate), pass: gate.status === 'PASS',
    ratio: typeof gate.actual === 'number' ? gate.actual / (gate.metric.startsWith('latency_') ? 60 : 100) : null,
    threshold: typeof gate.threshold === 'number' ? gate.threshold / (gate.metric.startsWith('latency_') ? 60 : 100) : null,
  }))}))} /></div>;
}


const baselinePreflight = (runId?: string) => getJson<Row>(`/api/evaluation/preflight${runId ? `?resume_source_id=${encodeURIComponent(runId)}` : ''}`);

export function EvaluationPage({ data, navigate }: { data: any; navigate?: (page: any) => void }) {
  const operation = useOperation();

  const [tab, setTab] = usePageTab("evaluation", ["report", "gates", "cases"] as const, "report");

  const retainedRun = (value: Row) => value.status === "completed" && !hasEvaluationDetails(value) ? cachedJson<Row>(`/api/evaluations/${value.id}`) || value : value;
  const [run, setRun] = useState<Row>(() => retainedRun(data.evaluation || {}));
  const [badCases, setBadCases] = useState<Row[]>(data.badCases || []);
  useEffect(() => { const next = retainedRun(data.evaluation || {}); setRun(current => hasEvaluationDetails(next) ? next : mergeEvaluationProgress(current, next)); setBadCases(data.badCases || []); }, [data.evaluation, data.badCases]);
  const [selectedGate, setSelectedGate] = useState<Row | null>(null);
  const [selectedCase, setSelectedCase] = useState<Row | null>(null);
  const selectedDetail = run.cases?.find((row: Row) => row.question_id === selectedCase?.question_id) || selectedCase;

  const [busy, setBusy] = useState(false);
  const [startConfirm, setStartConfirm] = useState(false);
  const [error, setError] = useState("");
  const [preflight,setPreflight]=useState<Row | null>(null);
  useEffect(() => {
    if (!selectedCase || !run.id || !["queued","running"].includes(run.status) || run.cases?.some((row:Row) => row.question_id === selectedCase.question_id)) return;
    let cancelled=false;
    void getJson<Row>(`/api/evaluations/${run.id}`).then(value => {
      if (!cancelled) setRun(current => ({...current,cases:value.cases,dataset_snapshot:value.dataset_snapshot}));
    }).catch(reason => {if (!cancelled)setError(errorMessage(reason));});
    return () => {cancelled=true;};
  }, [run.id, selectedCase?.question_id]);
  useEffect(()=>{
    let cancelled=false;
    const load=async()=>{
      setPreflight(null);
      try {
        const value=await baselinePreflight(run.id);
        if(!cancelled)setPreflight(value);
      } catch(reason) {if(!cancelled)setPreflight({can_start:false,reason:errorMessage(reason)});}
    };
    void Promise.resolve().then(()=>{if(!cancelled)void load();});window.addEventListener('focus',load);
    return()=>{cancelled=true;window.removeEventListener('focus',load);};
  },[run.id,run.status]);

  useEffect(()=>{let cancelled=false;void Promise.resolve().then(()=>{if(!cancelled)return getJson<Row>('/api/evaluation?active_task=true&light=true').then(value=>{if(!cancelled && value.id && ["queued","running"].includes(value.status))setRun(current=>mergeEvaluationProgress(current,value))}).catch(()=>{});});return()=>{cancelled=true};},[]);
  useEffect(() => {
    if (!run.id) return;
    let cancelled = false;
    if (run.status === "completed" && run.cases) {
      void getJson<Row>(`/api/evaluations/${run.id}`).then(value => { if (!cancelled) setRun(value); }).catch(reason => { if (!cancelled) setError(errorMessage(reason)); });
      return () => { cancelled = true; };
    }
    const poll = async () => {
      if(cancelled)return;
      try {
        let next = await getJson<Row>(`/api/evaluations/${run.id}?light=true`);
        if (cancelled) return;
        if (!["queued","running"].includes(next.status)) next = await getJson<Row>(`/api/evaluations/${run.id}`);
        if (cancelled) return;
        setRun(current => ["queued","running"].includes(next.status) ? mergeEvaluationProgress(current,next) : next);
        if (["queued","running"].includes(next.status)) window.setTimeout(poll, 1000);
        if (next.status !== "running" && ["queued","running"].includes(run.status)) { const rows = await getJson<Row[]>("/api/bad-cases"); if (!cancelled) setBadCases(rows); }
      } catch (reason) { if (!cancelled) { setError(errorMessage(reason)); window.setTimeout(poll,2000); } }
    };
    void Promise.resolve().then(poll);
    return () => { cancelled = true; };
  }, [run.id, data.evaluation]);

  const canResume = preflight?.can_resume === true && !!preflight.resume_source_id;
  const start = async (request: Row) => {
    setBusy(true); setError("");
    try {
      await operation.startEvaluation("Baseline 评测", async () => { const started: Row = await postJson("/api/evaluations/run", request); setRun(started); return started as { id: string }; });
    } catch (reason) {
      setError(errorMessage(reason));
      setPreflight(await baselinePreflight(run.id).catch(error=>({can_start:false,reason:errorMessage(error)})));
    } finally { setBusy(false); }
  };
  const prepareStart = async () => {
    setBusy(true);setError("");
    try {
      const current=await baselinePreflight(run.id);setPreflight(current);
      if(current.can_start !== true)return;
      const resume=current.can_resume === true && !!current.resume_source_id;
      const request=resume ? {resume_source_id:current.resume_source_id} : {fresh:true};
      await start(request);
    } catch(reason) {setPreflight({can_start:false,reason:errorMessage(reason)});}
    finally {setBusy(false);}
  };

  const result = run.result || {};
  const gates: Row[] = result.gates?.gates || [];
  const details: Row[] = run.gate_details || [];
  const relatedBad = badCases.filter(item => item.run_id === run.id);
  const cases: Row[] = run.cases || relatedBad.map(row=>({...row.result,question_id:row.question_id}));
  const snapshot = savedSnapshot(run);

  const config = run.config || {};
  const execution = run.judge?.execution_snapshot || {};

  const generationThinking = thinkingLabel(config.generation_thinking ?? execution.generation_thinking);
  const judgeThinking = thinkingLabel(run.judge?.judge_thinking);

  const comparison = result.comparison_metrics || {};
  const failures = gates.filter(item => item.status === "FAIL");

  const badCount = result.bad_case_count ?? (cases.length && cases.every(item=>businessVerdict(item)!==null) ? businessDiagnosisRows(cases).length : relatedBad.length ? businessDiagnosisRows(relatedBad).length : null);
  const completed = run.status === "completed";
  const diagnosisRows = cases.length ? cases : relatedBad;
  const businessCases = businessDiagnosisRows(diagnosisRows);
  const categoryScores = ([['positive', '正向题（Positive）'], ['ablation', '消融题（Ablation）'], ['negative', '负向题（Negative）']] as const).map(([category, label]) => {
    const rows = cases.filter(row => (snapshot.questions?.find((question: Row) => question.id === row.question_id)?.test_category || row.test_category) === category);
    return { label, correct: rows.filter(row => businessVerdict(row) === 'PASS').length, total: rows.length };
  });
  const breakdownReady = completed && cases.length === result.total && categoryScores.reduce((sum, row) => sum + row.total, 0) === result.total && cases.every(row => businessVerdict(row) !== null);
  const historicalPolicy=!!(run.requires_policy_upgrade ?? data.workspace?.requires_policy_upgrade);
  const stale = data.workspace?.requires_new_golden || data.workspace?.requires_new_baseline && (completed || data.workspace?.current_golden_id && snapshot.id !== data.workspace.current_golden_id);

  const versionedRerun = !!run.id && !canResume && !["queued", "running"].includes(run.status);
  const startButton = <button className="secondary ui-btn-tint" disabled={busy || preflight?.can_start !== true} onClick={() => setStartConfirm(true)}><Play size={15} />{["queued","running"].includes(run.status) ? "后台评测进行中" : canResume ? "恢复 Baseline" : run.id ? "重新运行 Baseline（新版本）" : "运行 Baseline 评测"}</button>;
  return <PageShell className="page evaluation-page" header={<div className="page-title"><div><h1><IconTile name="baseline" />Baseline</h1></div></div>} tabs={<div className="tabs"><button className={tab === "report" ? "active" : ""} aria-pressed={tab === "report"} onClick={() => setTab("report")}>Baseline 报告</button><button className={tab === "gates" ? "active" : ""} aria-pressed={tab === "gates"} onClick={() => setTab("gates")}>{displayText("Hard Gate")}</button><button className={tab === "cases" ? "active" : ""} aria-pressed={tab === "cases"} onClick={() => setTab("cases")}>Bad Case 诊断</button></div>} resetKey={tab}>

    {!versionedRerun && <div className="header-actions page-data-actions">{startButton}</div>}
    <ConfirmDialog open={startConfirm} onOpenChange={setStartConfirm} title={canResume ? "确认恢复 Baseline" : "确认重新运行 Baseline"} busy={busy} onConfirm={() => { setStartConfirm(false); void prepareStart(); }}><p>{canResume ? "将恢复原 Baseline 的未完成题目，已完成的题目保留。" : "会用当前 Pipeline 配置对 50 题重新评测，产生新版本正式评测。"}</p><p>会调用模型并产生费用。</p><p>不会影响当前线上版本。</p></ConfirmDialog>
    <PricePauseNotice pause={run.result?.price_pause} evaluationId={run.id} onChanged={async () => { setRun(await getJson<Row>(`/api/evaluations/${run.id}?light=true`)); }} />
    {preflight?.reason && (/活动评测|后台.*运行|active/i.test(preflight.reason) ? <p className="pending-note" role="status">后台正在运行试跑，完成后可重新运行 Baseline</p> : <p className="error-notice" role="alert">无法启动 Baseline：{preflight.reason}</p>)}
    {["partial","failed"].includes(run.status) && preflight?.can_start && preflight.resume_reason && <div className="muted-prose muted"><TruncatedText lines={3}>原任务不能恢复：{preflight.resume_reason}；请明确新建完整评测，历史进度保留。</TruncatedText></div>}

    {run.result?.auto_recovery?.authorized && !completed && <p className="workbench-status" role="status">{run.result.auto_recovery.state==='retrying'?`后台自动重试${run.result.auto_recovery.phase==='judge'?'Judge':'问答请求'} · 本题第${run.result.auto_recovery.retry_count}次恢复，已完成题目不会重复调用。`:run.result.auto_recovery.state==='stopped'?'后台已保存进度并停止：存在不可自动恢复的错误，详见评测依据。':'后台任务持续执行；刷新或关闭页面不停止Worker。'}</p>}
    {(error || run.error_message) && <p className="error-notice" role="alert">评测执行异常：{error || run.error_message}；未完成题目没有业务判定，不计入 Bad Case。</p>}
    {result.technical_error_count > 0 && <StoryDisclosure label={<>题目级技术异常 {result.technical_error_count}（不计入 Bad Case）</>}><p>已处理 {result.attempted} / {result.total} 题；有效业务判定 {result.completed} 题。存在技术异常时，综合分与 Hard Gate 不可用于资格判断。</p><ul>{result.technical_errors?.map((item: Row) => <li key={item.question_id}>{item.question_id} · {item.phase} · {item.error}</li>)}</ul></StoryDisclosure>}

    {stale && run.id && <p className="error-notice">当前知识库状态已变化；以下是历史 Run，不能作为当前发布依据。</p>}
    {!run.id ? <Section title="尚未运行 Baseline"><p>正式评测需要已批准 Golden {displayText("Snapshot")} 与可用 Provider。</p></Section> : <>

      {tab === "report" && <>
      {completed && !historicalPolicy && !stale && !result.technical_error_count && result.evaluation_complete !== false && typeof badCount === "number" && typeof result.total === "number" && typeof result.gates?.passed_count === "number" && typeof result.gates?.total === "number" ? <BaselineHero
        gates={{passed: result.gates.passed_count, total: result.gates.total}}
        correct={result.total - badCount} total={result.total} badCount={badCount}
        layers={Array.from(new Set<string>(businessCases.map(row => caseData(row).diagnostic_view?.diagnosis_category || "分类未知"))).map(label => ({label, count: businessCases.filter(row => (caseData(row).diagnostic_view?.diagnosis_category || "分类未知") === label).length}))}
        thinking={generationThinking}
        p50={gates.find(gate => gate.metric === "latency_p50_seconds")?.actual}
        p99={gates.find(gate => gate.metric === "latency_p99_seconds")?.actual}
        stages={timingStages(run.product_diagnostics).stages.map(stage => ({label: stage.label, seconds: stage.total_ms / 1000, share: stage.share_percent}))}
      /> : <>
      <section className={`baseline-conclusion ${stale ? "warning" : result.gates?.passed === true ? "good" : "neutral"}`}>
        <h2>{historicalPolicy ? "历史Baseline · 旧规则成绩保留" : stale ? "历史评测 · 当前身份已失效" : completed ? result.gates?.passed === true ? "Baseline Hard Gate 已通过" : result.gates?.passed === false && failures.length ? `本轮有 ${failures.length} 项 Hard Gate 未达标：${failures.map(gate => `${gateNames[gate.metric] || gate.metric} ${Number(gate.actual).toFixed(1)}${gate.metric.startsWith("latency_") ? " 秒" : "%"}（要求 ${gate.operator === ">=" ? "≥" : "≤"}${Number(gate.threshold).toFixed(1)}${gate.metric.startsWith("latency_") ? " 秒" : "%"}）`).join("；")}。` : "评测已完成 · Hard Gate 无法评估" : displayText(run.status || "not_run")}</h2>
        {(historicalPolicy || !completed || badCount==null) && <p>{historicalPolicy ? '历史技术诊断仅供追溯，不作为新版 Agent 目标；新实验需先建立新版 Baseline。' : badCount==null && completed?'Bad Case 数量未采集，无法据此判断逐题质量。': `已完成 ${result.completed ?? cases.length} / ${result.total ?? '未知'} 题；保留已完成结果与检查点。`}</p>}
      </section>
      <div className="baseline-metrics" aria-label="Baseline 核心结果">
        <Metric label="Hard Gate" value={`${result.gates?.passed_count ?? '未知'} / ${result.gates?.total ?? (gates.length || '未知')}`} note="已通过 / 总项数"/>
        <Metric label="答对" value={completed && typeof badCount==='number' && typeof result.total==='number'?`${result.total-badCount} / ${result.total}`:'未采集'} note="本轮保存的逐题判定"/>
        <Metric label="综合分" value={format(result.overall_score)} note="用于比较整体表现"/>
        <Metric label="回答耗时 P50" value={format(comparison.latency_p50_seconds ?? result.metrics?.latency_p50_seconds ?? gates.find(gate=>gate.metric==='latency_p50_seconds')?.actual,' 秒')} note="不含判分耗时"/>
      </div>

      </>}
      </>}

      {tab === "report" && <div className="baseline-report">
        {breakdownReady && <BaselineBreakdown categories={categoryScores} badCases={businessCases.map(row => {
          const item = caseData(row), category = item.diagnostic_view?.diagnosis_category;
          return { id: productQuestionLabel(row), question: item.question, layer: category === '检索层问题' ? '检索层' : category === '生成层问题' ? '生成层' : category || '未知' };
        })} onOpen={id => { setTab('cases'); setSelectedCase(businessCases.find(row => productQuestionLabel(row) === id) || null); }} />}
        <StoryDisclosure label="更多指标">
          <Metric label="综合分" value={format(result.overall_score)} note="用于比较整体表现"/>
          <ProductDiagnostics diagnostics={run.product_diagnostics} judgeThinking={judgeThinking} />
        <Section title="评测信息">
          <dl className="report-grid baseline-run-summary">
            <div><dt>题卷</dt><dd>{snapshot.name || snapshot.label || "冻结题卷"}{snapshot.question_ids?.length != null && ` · ${snapshot.question_ids.length} 题`}</dd></div>
            <div><dt>回答生成模型和档位</dt><dd>{execution.generation_model || "历史未保存"} · {generationThinking}</dd></div>
            <div><dt>Judge 模型和档位</dt><dd>{run.judge?.model || "历史未保存"} · {judgeThinking}</dd></div>
            <div><dt>Candidate K / Top-K</dt><dd>{formatValue(config.candidate_k)} / {formatValue(config.top_k)}</dd></div>
            <div><dt>评测时间</dt><dd>{localShortTime(run.completed_at || run.created_at)}</dd></div>
          </dl>
        </Section>
        {versionedRerun && <div className="header-actions">{startButton}</div>}
        </StoryDisclosure>

      </div>}
      {tab === "gates" && <BaselineGates gates={gates} passedCount={result.gates?.passed_count} onSelect={gate=>setSelectedGate(details.find(row=>row.metric===gate.metric) || gate)} />}

      {tab === "cases" && <><Section title={<IconLabel name="bad">{`${badCount ?? '未知'} 个 Bad Case`}</IconLabel>} action={<button className="secondary ui-btn-tint" onClick={()=>navigate ? navigate('evolution') : location.hash='evolution'}>进入 Agent 处理</button>}><BadCaseOverview showJudgeReason rows={businessCases} questions={snapshot.questions} categories={run.diagnostic_categories || data.evaluation?.diagnostic_categories} priorities={run.product_diagnostics?.optimization_priorities} latencyGates={gates} onSelect={setSelectedCase} /></Section></>}

    </>}

    <Drawer className="workbench-drawer" open={!!selectedGate} onOpenChange={open => !open && setSelectedGate(null)} title={selectedGate ? gateNames[selectedGate.metric] || selectedGate.metric : "Hard Gate 详情"}><div className="drawer-body">{selectedGate && <><DrawerSection title="指标状态"><p>{group(selectedGate.metric)} · {gateValue(selectedGate)} / {gateThreshold(selectedGate)} · <Status value={selectedGate.status} /></p></DrawerSection><DrawerSection title="业务影响"><p>{selectedGate.metric.startsWith("latency_") ? "响应体验是否达到既有性能 Hard Gate。" : selectedGate.metric.startsWith("positive_") || selectedGate.metric.startsWith("ablation_") ? "对应题组的正确性、依据和完整性 Hard Gate；通过不代表逐题无失败。" : "拒答、安全关键或注入防护是否达到既有安全 Hard Gate。"}</p></DrawerSection><DrawerSection title="评测版本与数据来源"><p>{run.judge?.scoring_policy || "历史规则未采集"} · 保存的逐题Judge与回答阶段观测</p></DrawerSection><DrawerSection title="指标定义与公式"><p>{selectedGate.formula || "历史记录未保存计算说明"}</p><p>纳入题数：{selectedGate.included_cases ?? "保存记录缺少题数"} · Judge：{run.judge?.model || "未采集"}</p></DrawerSection><DrawerSection title="贡献题目"><p className="muted">数值为本指标贡献；状态为题目整体判定。</p><div className="run-list gate-contributions">{(selectedGate.contributing_cases || []).map((item: Row) => <div key={item.question_id}><p className="gate-question">{cases.find(row => row.question_id === item.question_id)?.question || "历史题目未记录"}</p><span>{format(item.value, selectedGate.metric.startsWith("latency_") ? " 秒" : "%")}</span><Status value={typeof item.passed === "boolean" ? item.passed ? "passed" : "failed" : "not_evaluable"} /><button className="text-button" disabled={!cases.some(row => row.question_id === item.question_id)} onClick={() => { setSelectedGate(null); setSelectedCase(cases.find(row => row.question_id === item.question_id) || null); }}>查看案例</button></div>)}</div></DrawerSection><DrawerSection title="关联 Baseline 配置"><p>Candidate K {config.candidate_k ?? "未采集"} · Top-K {config.top_k ?? "未采集"}</p></DrawerSection></>}</div></Drawer>
    <Drawer className="workbench-drawer" open={!!selectedCase} onOpenChange={open => !open && setSelectedCase(null)} title={selectedDetail ? `${productQuestionLabel(selectedDetail)} · ${selectedDetail.diagnostic_view?.diagnosis_category || '案例诊断'}${selectedDetail.diagnostic_view?.severity_label?` · ${selectedDetail.diagnostic_view.severity_label}`:''}` : '案例诊断'}><div className="drawer-body">{selectedDetail && (!run.cases ? error ? <p role="alert">案例详情读取失败：{error}</p> : <div className="case-detail-skeleton" role="status" aria-label="正在读取保存的案例详情">{[1,2,3].map(index=><span key={index} aria-hidden="true"/>)}</div> : <BaselineCaseDetails item={{...selectedDetail,optimization_strategy:(data.optimization?.candidates || []).filter((candidate:Row)=>(candidate.reasoning?.observed_evidence || candidate.reasoning?.target_bad_cases || []).some((id:string)=>id===selectedDetail.question_id || relatedBad.some(row=>row.id===id && row.question_id===selectedDetail.question_id))).map((candidate:Row)=>`${candidate.reasoning?.candidate_label || '未采集'}：${candidate.reasoning?.hypothesis || '假设未采集'}`).join('；')}} snapshot={snapshot} config={config} gates={details} />)}</div></Drawer>
  </PageShell>;
}

export function BaselineCaseDetails({ item, snapshot, config, gates }: { item: Row; snapshot: Row; config: Row; gates: Row[] }) {
  const golden = snapshot.questions?.find((row: Row) => row.id === item.question_id) || {};
  const evidence: Row[] = golden.evidence || golden.acceptable_evidence || [];
  const view = item.diagnostic_view || {};

  const passed = businessVerdict(item) === 'PASS';
  const summary = judgePresentation(item, golden);

  const conclusion = businessVerdict(item) === 'PASS' ? '答对' : businessVerdict(item) === 'FAIL' ? '答错' : '评测执行未完成或判定无效；业务结果未产生';
  const behaviorNames: Record<string, string> = { safe_rejection: '应拒绝危险操作请求，并说明安全风险。', clarify: '缺失必要条件时，应请求澄清。', insufficient_evidence: '现有证据不足以完整回答时，应说明无法确定。', prompt_injection_resistance: '应抵抗提示注入，不泄露内部指令或伪造事实。' };
  const rawReference = item.reference_answer || golden.reference_answer || item.expected_behavior || golden.expected_behavior || item.raw?.expected_behavior || golden.raw?.expected_behavior;
  const expectedResponse = item.expected_response || item.raw?.expected_response || golden.expected_response || golden.raw?.expected_response;
  const reference = (behaviorNames[rawReference] ? expectedResponse || behaviorNames[rawReference] : rawReference || expectedResponse) || '历史未保存参考答案或预期行为';
  const metrics = item.programmatic_metrics || {};
  const finalRecords = metrics.retrieval_trace?.final ?? item.retrieved_chunks;
  const final: Row[] = Array.isArray(finalRecords) ? finalRecords : [];

  const trace=metrics.retrieval_trace || {};
  const savedSources:Row[]=[...(trace.candidates || []),...(trace.reranked || []),...final];
  const matches=(source:Row,id:string)=>!!id && (source.chunk_id===id || source.parent_chunk_id===id || source.matched_child_ids?.includes(id));
  const sourceLocation = (record: Row) => {
    const ids=[record.chunk_id,record.source_id,...(record.source_chunk_ids || [])].filter(Boolean);
    const source=savedSources.find(source=>ids.some(id=>matches(source,id))) || (!ids.length && record.document_id?savedSources.find(source=>source.document_id===record.document_id):null) || {};
    const document=record.document || record.document_name || source.document || source.document_name;
    const start=record.page_start ?? source.page_start,end=record.page_end ?? source.page_end;
    return [document ? shortSourceName(document) : '',start!=null?`p${start}${end!=null && end!==start?`–${end}`:''}`:''].filter(Boolean).join(' · ');
  };
  const missing:string[]=Array.isArray(view.missing_points)?view.missing_points:[];
  const positions:Row[]=view.retrieval_positions || view.evidence_checks?.filter((check:Row)=>'candidate_rank' in check) || [];
  const negative=(item.test_category || golden.test_category)==='negative';

  return <div className="case-details bad-case-details">
    <div className="case-review"><Badge tone={passed?"good":businessVerdict(item)==="FAIL"?"bad":"neutral"}>{conclusion}</Badge>{item.baseline_review_label && <Badge tone={item.baseline_review?.status==='confirmed_regression'?'bad':item.baseline_review?.status==='fluctuation'?'warning':'neutral'}>{item.baseline_review_label}</Badge>}</div>
    <section className="candidate-card drawer-section"><h3>业务问题</h3><p className="muted">{displayText(item.test_category || golden.test_category || '')}{item.negative_subtype && ` · ${displayText(item.negative_subtype)}`}</p><CaseAnswer text={item.question || golden.question || '历史未保存问题原文'} />{golden.business_scenario && <div className="muted-prose"><TruncatedText lines={3}>业务场景：{golden.business_scenario}</TruncatedText></div>}</section>
    <section className="candidate-card drawer-section"><h3>答案对比</h3><div className="case-answer-stack"><div><h4>参考答案 / 必答要点</h4><CaseAnswer text={reference} />{typeof view.missing_points==='string' && <div className="muted-prose muted"><TruncatedText lines={3}>{view.missing_points}</TruncatedText></div>}{missing.length>0 && <div className="missing-points"><strong>未答到的要点</strong><ul>{missing.map(point=><li key={point}>{point}</li>)}</ul></div>}</div><div><h4>实际回答</h4><CaseAnswer text={item.model_answer || '历史未保存回答'} final={final} /></div></div><div className="muted-prose case-difference"><TruncatedText lines={3}><span title={summary.detail}>{summary.text}</span></TruncatedText></div></section>
    <section className="candidate-card drawer-section"><h3>检索路径</h3>{negative?<p>不适用（负向题（Negative）不定位标准证据）</p>:<>{evidence.map((source,index)=>{const position=positions.find(position=>position.evidence_index===index+1);return <article className="evidence-path" key={index}><div className="muted-prose"><TruncatedText lines={3}>{source.evidence_key_points?.join('；') || '历史未保存关键事实摘要'}</TruncatedText></div><p className="muted">{sourceLocation(source) || '保存记录缺少来源位置'}</p>{position?<ol aria-label={`第 ${index+1} 段标准证据检索路径`}><li>{position.candidate_rank!=null?`召回第 ${position.candidate_rank} 位`:'未进候选'}</li><li>{position.rerank_rank!=null?`Rerank 第 ${position.rerank_rank} 位`:'保存记录缺少 Rerank 位次'}</li><li>{position.final_rank!=null?`进入 Top-K 第 ${position.final_rank} 位`:`未进 Top-K ${final.length} 条`}</li></ol>:<p className="muted">保存记录缺少该段证据的检索位置。</p>}</article>})}{!evidence.length && <p>历史冻结题卷未保存标准证据。</p>}</>}</section>
    {item.judge_result?.reason && <StoryDisclosure className="candidate-card drawer-section" label="判分原文"><p className="muted-prose">{item.judge_result.reason}</p></StoryDisclosure>}
    <section className="candidate-card drawer-section"><h3>优化方向</h3><div className="muted-prose"><TruncatedText lines={3}>{passed?'本题已答对，无失败优化目标。':view.repair_hint || savedDirections(item)}</TruncatedText></div></section>

  </div>;
}

export function CaseDetails(props: { item: Row; snapshot: Row; config: Row; gates: Row[] }) {
  return <BaselineCaseDetails {...props} />;
}

export function EvaluationDimensions({result}:{result:Row}) {
  const dimensions:[string,string[]][]=[['答案质量',['positive_correctness','positive_faithfulness','positive_completeness','ablation_correctness','ablation_faithfulness','ablation_completeness']],['检索效果',['recall_at_k','precision_at_k','mrr']],['安全鲁棒',['safe_rejection_rate','safety_critical_accuracy','prompt_injection_resistance']],['性能体验',['ttft_seconds','latency_p50_seconds','latency_p99_seconds']]];
  const names:Record<string,string>={...gateNames,recall_at_k:'Recall@K',precision_at_k:'Precision@K',mrr:'MRR',ttft_seconds:'TTFT'};
  return <Section title="四大评估维度"><div className="evaluation-dimensions">{dimensions.map(([title,keys])=><section key={title}><h3>{title}</h3><dl className="report-grid">{keys.map(key=>{
    const gate=result.gates?.gates?.find((item:Row)=>item.metric===key);
    const value=result.metrics?.[key] ?? result.comparison_metrics?.[key] ?? gate?.actual;
    const reason=result.metric_unavailable_reasons?.[key] || gate?.reason || '本次记录未保存该指标，不能按0计算';
    return <div key={key}><dt>{names[key]}</dt><dd>{typeof value==='number'?format(value,key.endsWith('_seconds')?' s':key==='mrr'?'':'%'):<><span>未采集</span><small>{reason}</small></>}</dd></div>;
  })}</dl></section>)}</div><p className="muted">仅读取本次持久化分数；11项{displayText("Hard Gate")}及{displayText("Overall")}判定保持独立。</p></Section>;
}
