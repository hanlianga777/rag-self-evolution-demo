export type Point = {number:number; text:string; before:boolean; after:boolean; fresh:boolean; beforeQuotes:string[]; afterQuotes:string[]};
export const categoryName = (value:string) => ({positive:'正向题',ablation:'消融题',negative:'应拒答题'}[value] || '题型未知');
export const verdict = (row:any) => row?.passed===true ? '答对' : row?.passed===false ? '答错' : '未知';
export const finalEvidence = (row:any):any[] | undefined => row?.programmatic_metrics?.retrieval_trace?.final;
export const parameterNames:Record<string,string> = {top_k:'回答证据条数',candidate_k:'查找候选条数',generation_thinking:'回答思考档位',rerank:'重排',min_score:'最低相关度',hybrid_search:'混合检索',hybrid_alpha:'混合检索权重',query_rewrite:'问题改写',multi_query:'多路查询',hyde:'假设文档检索',prompt_strategy:'回答提示策略',retrieval_max_tokens:'检索上下文长度',retrieval_mode:'检索方式',temperature:'回答温度',max_tokens:'回答长度上限',context_budget:'上下文预算'};
export const parameterValue = (value:any):string => ({max:'最高',high:'高',medium:'中',low:'低',true:'开启',false:'关闭'}[String(value)] || (value == null ? '未知' : typeof value==='object' ? JSON.stringify(value) : String(value)));
export function configChanges(before:any,after:any){return [...new Set([...Object.keys(before || {}),...Object.keys(after || {})])].filter(key=>key in parameterNames && JSON.stringify(before?.[key])!==JSON.stringify(after?.[key])).map(key=>({key,label:parameterNames[key] || '其他配置',before:parameterValue(before?.[key]),after:parameterValue(after?.[key])}));}

export function comparisonPoints(before:any,after:any,question:any={}):Point[] {
  const left=before?.judge_result?.atomic_results || [],right=after?.judge_result?.atomic_results || [];
  const numbers=[...new Set<number>([...left,...right].flatMap((item:any)=>{const match=item.atomic_id?.match(/^Q\d+-R(\d+)(?:-\d+)?$/);return match ? [Number(match[1])] : [];}))].sort((a,b)=>a-b);
  const reference=(before?.reference_answer || after?.reference_answer || question.reference_answer || '').split('\n');
  const lines=new Map<number,string>();
  reference.forEach((line:string,index:number)=>{const match=line.match(/^\s*(\d+)[.、)）]\s*(.*)$/);if(match)lines.set(Number(match[1]),match[2]);else if(line.trim() && !/^(clarify|safe_rejection)$/.test(line.trim()))lines.set(index+1,line.trim());});
  return numbers.map(number=>{
    const select=(rows:any[])=>rows.filter(item=>new RegExp(`^Q\\d+-R${number}(?:-\\d+)?$`).test(item.atomic_id));
    const a=select(left),b=select(right),met=(rows:any[])=>rows.length>0 && rows.every(row=>row.state==='MET');
    const requirement=question.business_requirements?.required_checks?.find((item:any)=>new RegExp(`^Q\\d+-R${number}$`).test(item.id));
    return {number,text:lines.get(number) || requirement?.requirement || '要点文字未保存',before:met(a),after:met(b),fresh:!met(a)&&met(b),beforeQuotes:a.filter(row=>row.state==='MET').flatMap(row=>row.answer_quotes || []),afterQuotes:b.filter(row=>row.state==='MET').flatMap(row=>row.answer_quotes || [])};
  });
}

export function explanation(before:any,after:any,beforeConfig:any,afterConfig:any,points:Point[]) {
  const steps:{label:string;text:string;key?:boolean}[]=[],left=before?.diagnostic_view?.evidence_checks || [],right=after?.diagnostic_view?.evidence_checks || [];
  const pairs=left.flatMap((a:any)=>{const b=right.find((b:any)=>a.quote && a.quote===b.quote);return b ? [{a,b}] : [];});
  const expanded=pairs.find(({a,b}:any)=>a.final_rank==null && Number.isFinite(a.rerank_rank) && a.rerank_rank<=(finalEvidence(after)?.length || 0) && b.final_rank!=null);
  const recalled=pairs.find(({a,b}:any)=>a.candidate_hit===false && b.candidate_hit===true);
  const pair=expanded || recalled || pairs.find(({a,b}:any)=>a.final_rank!==b.final_rank || a.candidate_rank!==b.candidate_rank || a.rerank_rank!==b.rerank_rank);
  const key=expanded ? 'top_k' : recalled ? 'candidate_k' : undefined;
  const changes=configChanges(beforeConfig,afterConfig),change=changes.find(change=>change.key===key);
  if(change)steps.push({label:'配置变化',text:`${change.label} ${change.before} → ${change.after}`,key:true});
  else if(changes.length)steps.push({label:'配置变化',text:'配置差异见下方'});
  if(pair){
    const position=(row:any)=>[row.candidate_rank!=null?`候选第 ${row.candidate_rank} 位`:row.candidate_hit===false?'未进候选':'',row.rerank_rank!=null?`重排第 ${row.rerank_rank} 位`:'',row.final_rank!=null?`进入回答第 ${row.final_rank} 位`:row.final_hit===false || row.final_rank===null?'未进入回答':''].filter(Boolean).join('、');
    const a=position(pair.a),b=position(pair.b);
    if(a&&b)steps.push({label:'关键证据位置',text:`“${Array.from(pair.a.quote as string).slice(0,36).join('')}${Array.from(pair.a.quote as string).length>36?'…':''}”：优化前${a}；优化后${b}`});
  }
  if(before?.test_category==='negative' && typeof before.passed==='boolean' && typeof after.passed==='boolean')steps.push({label:'回答结果',text:`优化前${before.passed?'正确拒答':'拒答判定未通过'}，优化后${after.passed?'正确拒答':'拒答判定未通过'}`});
  else if(points.some(point=>point.fresh))steps.push({label:'回答结果',text:`补上了必答要点 ${points.filter(point=>point.fresh).map(point=>`${String.fromCodePoint(0x2460+point.number-1)} ${point.text}`).join('；')}`});
  return {key:change ? key : undefined,steps};
}

export type MetricRow = {label:string;before:number|null;after:number|null;beforeText:string;afterText:string;delta:string;scale:number;better:'before'|'after'|null};
export function metricRows(before:any,after:any,points:Point[]):MetricRow[] {
  const metric=(row:any,key:string)=>typeof row?.programmatic_metrics?.[key]==='number'?row.programmatic_metrics[key]:null;
  const stage=(row:any,key:string)=>{const value=row?.programmatic_metrics?.stages?.find((stage:any)=>stage.stage_name===key)?.duration_ms;return typeof value==='number'?value:null;};
  const totalScale=Math.max(metric(before,'latency_ms') || 0,metric(after,'latency_ms') || 0);
  const count=(row:any)=>Array.isArray(finalEvidence(row))?finalEvidence(row)!.length:null;
  const definitions:[string,number|null,number|null,string,boolean][]=[['必答要点',points.length?points.filter(p=>p.before).length:null,points.length?points.filter(p=>p.after).length:null,'条',false],['本题回答耗时',metric(before,'latency_ms'),metric(after,'latency_ms'),'秒',true],['首字时间',metric(before,'ttft_ms'),metric(after,'ttft_ms'),'秒',true],['其中：检索',stage(before,'retrieval'),stage(after,'retrieval'),'秒',true],['其中：生成',stage(before,'generation'),stage(after,'generation'),'秒',true],['进入回答的证据',count(before),count(after),'段',false]];
  const number=(n:number)=>Number(n.toFixed(Math.abs(n)<1?2:1)).toString();
  return definitions.map(([label,a,b,unit,time])=>{
    const format=(n:number|null)=>n==null?'未知':label==='必答要点'?`${n} / ${points.length}`:`${number(time?n/1000:n)} ${unit}`;
    const delta=a==null || b==null?'未知':`${b>a?'+':b<a?'−':''}${number(Math.abs(b-a)/(time?1000:1))} ${unit}`;
    return {label,before:a,after:b,beforeText:format(a),afterText:format(b),delta,scale:time?totalScale:Math.max(a || 0,b || 0),better:a==null || b==null || a===b?null:(time?a<b:a>b)?'before':'after'};
  });
}
