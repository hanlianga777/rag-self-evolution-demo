import {comparisonPoints,isRubric,RUBRIC_NAMES,RUBRIC_THRESHOLDS} from './comparisonData';

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
// 新 Judge（朋友三维）：逐维度分数和理由 + 每段标准证据的检索路径。旧记录仍按原来的逐要点展示。
function RubricEvidence({row,question}:{row:any;question:any}) {
 const judge=row.judge_result || {},category=row.test_category || question?.test_category,negative=category==='negative';
 const dims=negative?[['behavior_correct','behavior_reason'],['safety_violation','safety_reason']]:[['correctness','correctness_reason'],['faithfulness','faithfulness_reason'],['completeness','completeness_reason']];
 const value=(key:string)=>{const v=judge[key];return typeof v==='number'?`${v} 分`:key==='safety_violation'?(v===true?'有危险内容':v===false?'无':'未知'):v===true?'做到':v===false?'没做到':'未知';};
 const pass=(key:string)=>key==='safety_violation'?judge[key]===false:key==='behavior_correct'?judge[key]===true:typeof judge[key]==='number' && judge[key]>=(RUBRIC_THRESHOLDS[category]?.[key] ?? 0);
 const trace=row?.programmatic_metrics?.retrieval_trace;
 const evidence=(question?.evidence || question?.raw?.evidence || []).flatMap((e:any)=>(e.source_chunk_ids || []).map((id:string)=>({id,quote:(e.evidence_key_points || [])[0] || ''})));
 const match=(source:any,id:string)=>source.chunk_id===id || source.parent_chunk_id===id || source.matched_child_ids?.includes(id);
 const rank=(stage:string,id:string)=>{if(!Array.isArray(trace?.[stage]))return undefined;const i=trace[stage].findIndex((s:any)=>match(s,id));return i<0?null:i+1;};
 const borderline=row?.evaluation_outcome?.borderline;
 return <section className="answer-evidence"><h3>判分与检索路径</h3>
  <ol>{dims.map(([key,reason],index)=><li key={key}><div><span className="comparison-pn">{index+1}</span><span>{RUBRIC_NAMES[key]}：{value(key)}</span><strong className={pass(key)?'point-met':'point-missed'}>{pass(key)?'达标':'未达标'}</strong></div>{judge[reason] && <p className="point-path">{judge[reason]}</p>}</li>)}</ol>
  {borderline && <p className="muted">边界分：分数接近合格线或几次判分结论不一致，建议人工抽查。</p>}
  {negative?<p>不适用（负向题不定位标准证据）</p>:evidence.length?<ol>{evidence.map((e:any,index:number)=><li key={e.id+index}><div><span className="comparison-pn">证{index+1}</span><span>{e.quote}</span></div><p className="point-path">召回：{position(rank('candidates',e.id))} → 重排后：{position(rank('reranked',e.id))} → 交给模型：{rank('final',e.id)===undefined?'未知':rank('final',e.id)===null?'否':`是，第 ${rank('final',e.id)} 位`}</p></li>)}</ol>:<p className="muted">本题未保存标准证据，检索路径未知。</p>}
 </section>;
}
export function AnswerEvidence({row,question}:{row:any;question:any}) {
 if(isRubric(row) && !row?.judge_result?.atomic_results)return <RubricEvidence row={row} question={question}/>;
 const points=pointPaths(row,question);
 const negative=(row.test_category || question?.test_category)==='negative';
 return <section className="answer-evidence"><h3>必答要点与检索路径</h3>{negative && <p>不适用（负向题不定位标准证据）</p>}{points.length?<ol>{points.map(p=><li key={p.number}><div><span className="comparison-pn">{p.number}</span><span>{p.text}</span><strong className={p.after?'point-met':'point-missed'}>{!p.known?'判定未知':p.after?'答到':'没答到'}</strong></div><p className="point-path">召回：{position(p.candidate)} → 重排后：{position(p.rerank)} → 交给模型：{p.final===undefined?'未知':p.final===null?'否':`是，第 ${p.final} 位`}</p></li>)}</ol>:<p className="muted">本题未保存可对齐的逐要点判分，检索路径未知。</p>}</section>;
}
const position=(n:number|null|undefined)=>n===undefined?'未知':n===null?'未进入':`第 ${n} 位`;
