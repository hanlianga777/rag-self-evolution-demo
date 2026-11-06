import {useEffect, useState} from 'react';
import {errorMessage, getJson} from '../api';
import {CaseAnswer} from './CaseAnswer';
import {completeResult, recommendationOf, schemeName, storyText} from './EvolutionStory';
import type {Citation} from '../types';

export function evidenceChange(before:any,after:any,snapshot:any):string {
  const question=snapshot?.questions?.find((q:any)=>q.id===before?.question_id || q.question_id===before?.question_id);
  const source=question?.business_requirements?.sources?.[0];
  const id=source?.chunk_id;
  const left=before?.programmatic_metrics?.retrieval_trace,right=after?.programmatic_metrics?.retrieval_trace;
  if(id && Array.isArray(left?.final) && Array.isArray(right?.final)){
    const a=left.final.findIndex((item:any)=>item.chunk_id===id),b=right.final.findIndex((item:any)=>item.chunk_id===id);
    const quote=source.quote ? `“${source.quote}”这段说明` : '标准说明';
    if(a<0 && b>=0)return `优化前没找到${quote}作为回答证据；优化后排在第 ${b+1} 位。`;
    if(a>=0 && b>=0)return `两次均选入${quote}，证据位置从第 ${a+1} 位变为第 ${b+1} 位；具体回答见上方。`;
    if(a>=0 && b<0)return '优化后未选入这段标准说明；回答的改善以保存的逐题判定为准。';
  }
  return after?.judge_result?.reason ? `保存的判定说明：${storyText(after.judge_result.reason)}` : '保存记录没有足够的证据位置，变化未知。';
}

export function SavedAnswerComparison({data,onOpenCitation}:{data:any;onOpenCitation:(citation:Citation)=>void}) {
  const experiment=data.optimization,baseline=data.evaluation;
  const recommendation=recommendationOf(experiment);
  const candidate=experiment?.candidates?.find((c:any)=>c.id===recommendation.recommended_candidate);
  const baselineId=data.workspace?.current_baseline_id===undefined ? baseline?.id : data.workspace.current_baseline_id;
  const runId=candidate?.result?.evaluation_run_id;
  const baselineBlocked=!baselineId || baseline?.id!==baselineId;
  const [runs,setRuns]=useState<any>(null),[selected,setSelected]=useState(''),[error,setError]=useState('');
  const binding=JSON.stringify([baselineId,runId,candidate?.id,candidate?.status,candidate?.result?.evaluation_complete]);
  useEffect(()=>{
    let cancelled=false;setRuns(null);setSelected('');setError('');
    if(baselineBlocked || !runId || !completeResult(candidate))return;
    void Promise.all([getJson<any>(`/api/evaluations/${baselineId}`),getJson<any>(`/api/evaluations/${runId}`)]).then(([before,after])=>{
      if(cancelled)return;
      if(before.id!==baselineId || after.id!==runId || before.status!=='completed' || after.status!=='completed' || !before.judge?.evaluation_identity || before.judge.evaluation_identity!==after.judge?.evaluation_identity || !before.dataset_version_id || before.dataset_version_id!==after.dataset_version_id)throw new Error('评测身份或题卷不一致，不能展示优化前后对比。');
      const fixed=new Set(candidate.result.all_fixed_question_ids || []);
      const rows=(before.cases || []).filter((row:any)=>fixed.has(row.question_id) && row.passed===false && typeof row.model_answer==='string' && after.cases?.some((item:any)=>item.question_id===row.question_id && item.passed===true && typeof item.model_answer==='string'));
      setRuns({before,after,rows,binding});setSelected(rows[0]?.question_id || '');
    }).catch(reason=>{if(!cancelled)setError(errorMessage(reason));});
    return ()=>{cancelled=true;};
  },[binding]);
  const current=runs?.binding===binding ? runs : null;
  const before=current?.rows.find((row:any)=>row.question_id===selected),after=current?.after.cases?.find((row:any)=>row.question_id===selected);
  return <section className="saved-answer-comparison" aria-label="已保存回答对比"><div className="section-head"><h2>代表题 · 看见改善</h2><span>已保存的评测回答</span></div>
    {baselineBlocked ? <p>当前有效 Baseline 尚未就绪，暂不展示前后对比。</p> : !candidate ? <p>最终推荐尚未保存，代表题待确定。</p> : !completeResult(candidate) ? <p>推荐方案尚无完整试跑结果。</p> : !runId ? <p>推荐方案的评测回答来源未保存。</p> : error ? <p role="alert" className="error-notice">{error}</p> : !current ? <p>正在读取已保存的回答…</p> : <>
      <div className="representative-questions">{current.rows.map((row:any)=><button key={row.question_id} className="secondary" aria-pressed={selected===row.question_id} onClick={()=>setSelected(row.question_id)} title={row.question}>{row.question}</button>)}</div>
      {before && after ? <><h3 className="saved-question">{before.question}</h3><div className="saved-answer-columns">{[[before,'Baseline · 优化前'],[after,`${schemeName(candidate)} · 优化后`]].map(([row,label]:any)=>{
        const final=row.programmatic_metrics?.retrieval_trace?.final || row.retrieved_chunks || [];
        return <article className="saved-answer-card" key={label}><div className="section-head"><h3>{label}</h3><span>{row.passed===true?'答对':row.passed===false?'答错':'未知'}</span></div><div className="saved-answer-body"><CaseAnswer text={row.model_answer || '回答未保存'} final={final}/></div><div className="saved-answer-citations">{final.map((citation:Citation,index:number)=><button className="document-link" key={`${citation.chunk_id}-${index}`} onClick={()=>onOpenCitation({...citation,content_preview:(citation as any).content || citation.content_preview,savedEvidence:true} as Citation)}>{citation.document} · 第 {citation.page_start} 页</button>)}</div></article>;
      })}</div><p className="comparison-observation">{evidenceChange(before,after,current.before.dataset_snapshot)}</p></> : <p>没有同时保存两侧判定和回答的修复题。</p>}
    </>}
  </section>;
}
