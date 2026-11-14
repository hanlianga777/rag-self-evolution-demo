import { presentationText } from "../display";
import { LocalPagination, useLocalPage } from "./LocalPagination";
import { DataTable } from "./DataTable";
import { TableVerdict } from "./Primitives";
import { ClampText } from "../ui/ClampText";
import { HoverCard } from "../ui/HoverCard";
import {useEffect, useState} from 'react';
import {cachedJson, errorMessage} from '../api';
import {detailJson, useHoverPrefetch} from '../preload';
import {goldenCached, goldenFetch} from '../goldenCache';
import { completeResult, recommendationOf, shortQuestionId } from './EvolutionStory';
import {ComparisonAnswer} from './ComparisonAnswer';
import {categoryName, comparisonPoints, configChanges, explanation, metricRows, verdict} from './comparisonData';
import type {Citation} from '../types';
import './SavedAnswerComparison.css';

const cachePath = '/comparison-preloaded';
function comparisonSource(data:any) {
  const experiment=data.optimization,baseline=data.evaluation,recommendation=recommendationOf(experiment);
  const candidate=experiment?.candidates?.find((c:any)=>c.id===recommendation.recommended_candidate);
  const baselineId=data.workspace?.current_baseline_id===undefined ? baseline?.id : data.workspace.current_baseline_id,runId=candidate?.result?.evaluation_run_id;
  const baselineBlocked=!baselineId || baseline?.id!==baselineId;
  const paths=[baselineId,runId].map(id=>`/api/evaluations/${encodeURIComponent(id)}/comparison-cases`);
  const binding=JSON.stringify([baselineId,runId,candidate?.id,candidate?.status,candidate?.result?.evaluation_complete]);
  const readRuns=([before,after]:any[])=>{
    if(before?.id!==baselineId || after?.id!==runId || before.status!=='completed' || after.status!=='completed' || !before.judge?.evaluation_identity || before.judge.evaluation_identity!==after.judge?.evaluation_identity || !before.dataset_version_id || before.dataset_version_id!==after.dataset_version_id)throw new Error('评测身份或题卷不一致，不能展示Before/After。');
    const rows=(before.cases || []).map((row:any)=>({...row,after:(after.cases || []).find((item:any)=>item.question_id===row.question_id)}));
    return {before,after,rows,binding};
  };
  return {candidate,baselineId,runId,baselineBlocked,paths,binding,readRuns};
}

export function preloadComparison(data:any) {
  const {candidate,baselineId,runId,baselineBlocked,paths,binding,readRuns}=comparisonSource(data);
  if(baselineBlocked || !runId || !completeResult(candidate))return Promise.resolve(undefined);
  return goldenFetch<any>(binding,cachePath,async()=>{
    const next=readRuns(await Promise.all(paths.map(path=>detailJson<any>(path))));
    const allDetails:Record<string,any>={},errors:Record<string,string>={};
    for(let offset=0;offset<next.rows.length;offset+=4) await Promise.all(next.rows.slice(offset,offset+4).map(async(row:any)=>{
      const key=JSON.stringify([binding,row.question_id]);
      try { allDetails[key]=await Promise.all([baselineId,runId].map(run=>detailJson<any>(`/api/evaluations/${encodeURIComponent(run)}/cases/${encodeURIComponent(row.question_id)}`))); }
      catch(reason) { errors[key]=errorMessage(reason); }
    }));
    return {runs:next,details:allDetails,errors};
  });
}

export function SavedAnswerComparison({data,onOpenCitation,questionId}:{data:any;questionId?:string;onOpenCitation:(citation:Citation)=>void}) {
  const {candidate,baselineId,runId,baselineBlocked,binding,readRuns}=comparisonSource(data);
  const [runs,setRuns]=useState<any>(()=>goldenCached<any>(binding,cachePath)?.runs || null),[selected,setSelected]=useState(''),[filter,setFilter]=useState('fixed'),[search,setSearch]=useState(''),[error,setError]=useState(''),[details,setDetails]=useState<any>(()=>goldenCached<any>(binding,cachePath)?.details || {}),[detailErrors,setDetailErrors]=useState<Record<string,string>>({});
  useEffect(()=>{
    let cancelled=false;const retained=goldenCached<any>(binding,cachePath);setRuns(retained?.runs || null);setSelected('');setError('');setDetails(retained?.details || {});setDetailErrors(retained?.errors || {});setFilter('fixed');setSearch('');
    if(baselineBlocked || !runId || !completeResult(candidate))return;
    const accept=(value:any)=>{
      const {before,after}=value.runs;
      if(cancelled)return;
      const next=readRuns([before,after]);
      const requested = next.rows.find((row:any)=>questionId && shortQuestionId(row.question_id)===shortQuestionId(questionId));
      if(requested) setFilter('all');
      setDetails(value.details);setDetailErrors(value.errors || {});setRuns(next);setSelected(previous=>previous || requested?.question_id || next.rows.find((row:any)=>row.passed===false && row.after?.passed===true)?.question_id || '');
    };
    if(retained) accept(retained);
    void preloadComparison(data).then(accept).catch(reason=>{if(!cancelled)setError(errorMessage(reason));});
    return ()=>{cancelled=true;};
  },[binding,questionId]);
  const current=runs?.binding===binding ? runs : null;
  const rows:any[]=current?.rows || [],fixed=rows.filter(row=>row.passed===false && row.after?.passed===true),remaining=rows.filter(row=>row.after?.passed===false);
  const filtered=(filter==='fixed'?fixed:filter==='remaining'?remaining:rows).filter(row=>(row.question || '').includes(search) || presentationText(row.question || '').includes(search));
  const requestedId=questionId ? rows.find(row=>shortQuestionId(row.question_id)===shortQuestionId(questionId))?.question_id : undefined;
  const pagination=useLocalPage<any>(filtered,JSON.stringify([binding,filter,search]),requestedId);
  const active=pagination.rows.find(row=>row.question_id===selected) || pagination.rows[0],id=active?.question_id;
  const detailPaths=[baselineId,runId].map(run=>`/api/evaluations/${encodeURIComponent(run)}/cases/${encodeURIComponent(id)}`);
  const hover=useHoverPrefetch();
  const detailKey=JSON.stringify([binding,id]);
  const savedDetail=details[detailKey] || detailPaths.map(path=>cachedJson<any>(path));
  const ready=savedDetail?.every(Boolean),before=ready?savedDetail[0].case:null,after=ready?savedDetail[1].case:null;
  const retryDetail=async()=>{
    try {
      const value=await Promise.all(detailPaths.map(path=>detailJson<any>(path)));
      setDetails((previous:any)=>({...previous,[detailKey]:value}));
      setDetailErrors(previous=>{const next={...previous};delete next[detailKey];return next;});
    } catch(reason) {setDetailErrors(previous=>({...previous,[detailKey]:errorMessage(reason)}));}
  };
  const points=before && after?comparisonPoints(before,after,savedDetail[1].question):[],why=explanation(before,after,current?.before.config,current?.after.config,points);
  const missing=points.filter(point=>!point.after).map(point=>String.fromCodePoint(0x2460+point.number-1)).join('、');
  const headline=after?.passed===false ? `仍未修好：${missing ? `缺少要点 ${missing}` : '具体缺失要点未保存'}` : why.headline;
  const unavailable=baselineBlocked?'当前有效 Baseline 尚未就绪，暂不展示前后对比。':!candidate?'最终推荐尚未保存，代表题待确定。':!completeResult(candidate)?'推荐 Candidate 尚无完整评测结果。':!runId?'推荐 Candidate 的评测回答来源未保存。':'';
  return <section className="saved-answer-comparison" aria-label="已保存回答对比">{unavailable?<p>{unavailable}</p>:!current?error?<p role="alert">{error}</p>:<div className="case-detail-skeleton" role="status" aria-label="正在读取题目列表"><span/><span/><span/></div>:<div className="comparison-workspace">
    <div className="comparison-side"><aside className="comparison-rail" aria-label="选择题目"><div className="comparison-seg">{[['fixed','修好的',fixed.length],['remaining','仍未修好',remaining.length],['all','全部',rows.length]].map(([value,label,count])=><button key={value} aria-pressed={filter===value} onClick={()=>{setFilter(String(value));setSelected('');}}>{label}<b>{count}</b></button>)}</div><input className="comparison-search" aria-label="搜索题目内容" placeholder="搜索题目内容" value={search} onChange={event=>setSearch(event.target.value)}/><LocalPagination {...pagination}/><ul className="comparison-qlist">{pagination.rows.map(row=><li key={row.question_id}><button {...hover([baselineId,runId].map(run=>`/api/evaluations/${encodeURIComponent(run)}/cases/${encodeURIComponent(row.question_id)}`))} className={id===row.question_id?'on':''} aria-pressed={id===row.question_id} onClick={()=>setSelected(row.question_id)}><span className="comparison-qid">{shortQuestionId(row.question_id)}</span><ClampText hoverOnly className="comparison-qtext" text={presentationText(row.question || "未保存问题")} lines={2} /><span className="comparison-qmeta"><span className="comparison-flip" aria-label={`Before${verdict(row)}，After${verdict(row.after)}`}><i className={`comparison-dot ${verdict(row)}`}/><i>›</i><i className={`comparison-dot ${verdict(row.after)}`}/></span>{categoryName(row.test_category)}</span></button></li>)}</ul>{!filtered.length && <p className="comparison-empty">没有符合条件的题目。</p>}</aside></div>
    <div className="comparison-detail">{active && <header className="comparison-qhead"><div><h2><ClampText hoverOnly lines={1} text={`${shortQuestionId(id)}　${presentationText(active.question || "")}`} /></h2></div><div className="comparison-verdict"><span className={`comparison-badge ${verdict(active)}`}>Before {verdict(active)}</span><span>›</span><span className={`comparison-badge ${verdict(active.after)}`}>After {verdict(active.after)}</span></div></header>}
    {error && <p role="alert">{error}</p>}{detailErrors[detailKey] && <p role="alert">{detailErrors[detailKey]} <button className="text-button" onClick={()=>void retryDetail()}>重试本题</button></p>}{id && !ready && !detailErrors[detailKey]?<div className="case-detail-skeleton" role="status" aria-label="正在读取保存的单题详情"><span/><span/><span/></div>:before && after?<>
      <section className="comparison-why"><div className="comparison-chain"><h3>{active.test_category==='negative'?'这道题的拒答变化':before.passed===false && after.passed===true?'这道题为什么变好':'这道题的前后变化'}</h3><p className="ui-headline">{headline}</p><ol className="comparison-steps">{why.steps.map(step=><li className={`comparison-step ${step.key?'key':''}`} key={step.label}><span className="comparison-t">{step.label}</span><span className={`comparison-v ${step.key?'':'ui-body-muted'}`}>{step.text}</span></li>)}</ol>{!why.steps.length && <p>保存记录未提供变化依据。</p>}</div><div className="comparison-points"><h3>必答要点对照</h3><table className="comparison-ptable"><thead><tr><th>要点</th><th className="num">Before</th><th className="num">After</th></tr></thead><tbody>{points.map(point=><tr key={point.number} className={point.fresh?'new':''}><td><span><span className="comparison-pn">{point.number}</span>{point.text}{point.fresh && <span className="comparison-newtag">新满足</span>}</span></td><td className="num"><TableVerdict value={point.before}/></td><td className="num"><TableVerdict value={point.after}/></td></tr>)}</tbody></table>{!points.length && <p>必答要点判分未保存。</p>}</div></section>
      <div className="comparison-answers">{[['before',before,'Baseline'],['after',after,`Candidate ${candidate.reasoning?.candidate_label || '—'}`]].map(([side,row,name]:any)=>{
        const met=points.filter(point=>side==='before'?point.before:point.after).length;
        return <article className="comparison-ans" key={`${id}-${side}`}><header className="comparison-ans-h"><div className="comparison-name">{side==='before'?'Before':'After'} · {name}</div><span className="comparison-badge neutral">要点 {points.length?`${met} / ${points.length}`:'未知'}</span></header><ComparisonAnswer row={row} points={points} side={side} onOpenCitation={onOpenCitation}/></article>;
      })}</div>
      <section className="comparison-data"><h3>两次回答的配置差异</h3><div className="comparison-cfg">{configChanges(current.before.config,current.after.config).sort((a,b)=>Number(b.key===why.key)-Number(a.key===why.key)).map(change=><span className={`comparison-chip ${why.key===change.key?'key':''}`} key={change.key}>{change.label}<b>{change.before} → {change.after}</b>{why.key===change.key && <small>本题关键</small>}</span>)}</div><div className="comparison-telemetry"><div className="comparison-h3-row"><HoverCard content="数字来自两次评测保存的本题判分、耗时和检索记录。时间行共用总耗时刻度；较好的一方加粗。"><span className="comparison-info" tabIndex={0} aria-label="数据说明">i</span></HoverCard></div><div className="comparison-legend"><span>Before</span><span>After</span></div><DataTable className="comparison-dtable"><thead><tr><th>指标</th><th className="num">Before</th><th className="num">After</th><th>对比条</th><th>变化</th></tr></thead><tbody>{metricRows(before,after,points).map(row=><tr key={row.label}><td>{row.label}</td><td className="num">{row.better==='before'?<strong>{row.beforeText}</strong>:row.beforeText}</td><td className="num">{row.better==='after'?<strong>{row.afterText}</strong>:row.afterText}</td><td className="comparison-bar">{row.before!=null && row.after!=null && row.scale>0 && <div className="comparison-pair"><i style={{width:`${Math.min(100,row.before/row.scale*100)}%`}}/><i style={{width:`${Math.min(100,row.after/row.scale*100)}%`}}/></div>}</td><td className="num muted">{row.delta}</td></tr>)}</tbody></DataTable></div></section>
    </>:null}</div>
  </div>}</section>;
}
