import {comparisonPoints} from './comparisonData';

// One path per saved requirement. No guessing when neither ids nor quotes map it.
export function pointPaths(row:any,question:any) {
 const requirements=question?.business_requirements || question?.raw?.business_requirements || {};
 const points=comparisonPoints(row,row,{...question,business_requirements:requirements});
 const checks=[...(requirements.required_checks || []),...(requirements.conditional_checks || [])];
 for(const check of checks){
  const number=Number(check.id?.match(/-R(\d+)$/)?.[1]);
  if(number && !points.some(p=>p.number===number))points.push({number,text:check.requirement || '要点未保存',before:false,after:false,fresh:false,beforeQuotes:[],afterQuotes:[]});
 }
 points.sort((a,b)=>a.number-b.number);
 const trace=row?.programmatic_metrics?.retrieval_trace;
 const positions=row?.diagnostic_view?.evidence_checks || row?.diagnostic_view?.retrieval_positions || [];
 const match=(source:any,ids:string[])=>ids.some(id=>source.chunk_id===id || source.parent_chunk_id===id || source.matched_child_ids?.includes(id));
 const sourceTexts=(source:any)=>source.chunk_text || source.content || source.text || source.content_preview || '';
 return points.map(point=>{
  const check=checks.find((c:any)=>new RegExp(`^Q\\d+-R${point.number}$`).test(c.id));
  const ids=check?.source_chunk_ids || [];
  const observation=positions.find((p:any)=>p.requirement_id===check?.id && check?.id || check?.requirement && p.quote===check.requirement);
  const rank=(key:string)=>{
   if(observation && `${key}_rank` in observation)return observation[`${key}_rank`];
   const stage={candidate:'candidates',rerank:'reranked',final:'final'}[key]!;
   if(!Array.isArray(trace?.[stage]) || !ids.length && !check?.quote)return undefined;
   const index=trace[stage].findIndex((s:any)=>match(s,ids) || check?.quote && sourceTexts(s).includes(check.quote));
   return index<0?null:index+1;
  };
  const atoms=(row?.judge_result?.atomic_results || []).filter((atom:any)=>new RegExp(`^Q\\d+-R${point.number}(?:-\\d+)?$`).test(atom.atomic_id));
  const known=atoms.length>0 && atoms.every((atom:any)=>['MET','NOT_MET'].includes(atom.state));
  return {...point,known,candidate:rank('candidate'),rerank:rank('rerank'),final:rank('final')};
 });
}
export function AnswerEvidence({row,question}:{row:any;question:any}) {
 const points=pointPaths(row,question);
 const negative=(row.test_category || question?.test_category)==='negative';
 return <section className="answer-evidence"><h3>必答要点与检索路径</h3>{negative && <p>不适用（负向题不定位标准证据）</p>}{points.length?<ol>{points.map(p=><li key={p.number}><div><span className="comparison-pn">{p.number}</span><span>{p.text}</span><strong className={p.after?'point-met':'point-missed'}>{!p.known?'判定未知':p.after?'答到':'没答到'}</strong></div><p className="point-path">召回：{position(p.candidate)} → 重排后：{position(p.rerank)} → 交给模型：{p.final===undefined?'未知':p.final===null?'否':`是，第 ${p.final} 位`}</p></li>)}</ol>:<p className="muted">本题未保存可对齐的逐要点判分，检索路径未知。</p>}</section>;
}
const position=(n:number|null|undefined)=>n===undefined?'未知':n===null?'未进入':`第 ${n} 位`;
