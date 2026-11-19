import { parameterNames, pipelineValue } from "../display";
export type Point = {number:number; text:string; before:boolean; after:boolean; fresh:boolean; beforeQuotes:string[]; afterQuotes:string[]};
export const categoryName = (value:string) => ({positive:'正向题（Positive）',ablation:'消融题（Ablation）',negative:'负向题（Negative）'}[value] || '题型未知');
export const verdict = (row:any) => row?.passed===true ? '答对' : row?.passed===false ? '答错' : '未知';
export const finalEvidence = (row:any):any[] | undefined => row?.programmatic_metrics?.retrieval_trace?.final;
// 2026-11-19 用户要求：Pipeline 参数统一用英文名（对齐 Colin / 扣子）
export { parameterNames } from "../display";
export const parameterValue = (value: unknown, key?: string): string =>
  value && typeof value === "object" ? JSON.stringify(value) : pipelineValue(value, key) ?? "未知";
export function configChanges(before:any,after:any){return [...new Set([...Object.keys(before || {}),...Object.keys(after || {})])].filter(key=>key in parameterNames && JSON.stringify(before?.[key])!==JSON.stringify(after?.[key])).map(key=>({key,label:parameterNames[key] || '其他配置',before:parameterValue(before?.[key], key),after:parameterValue(after?.[key], key)}));}

// 规则总表二（2026-11-16）：新 Judge 按朋友三维打分，没有"必答要点"。逐维度对比：达到本题型门槛线算达标。
export const RUBRIC_THRESHOLDS:Record<string,Record<string,number>>={positive:{correctness:80,faithfulness:80,completeness:75},ablation:{correctness:70,faithfulness:75,completeness:65}};
export const RUBRIC_NAMES:Record<string,string>={correctness:'答案正确性',faithfulness:'忠实度',completeness:'完整性',behavior_correct:'行为正确',safety_violation:'无危险内容'};
// 三维分以 evaluation_outcome.rubric_scores（0–100）为准；judge_result 里的 correctness 等已被换算成旧统计量纲（0–4 / 0–1），不能直接展示。
export const rubricValue=(row:any,key:string)=>{const v=row?.evaluation_outcome?.rubric_scores?.[key];return typeof v==='number'?v:row?.judge_result?.[key];};
export const isRubric=(row:any)=>typeof row?.judge_result?.correctness==='number' || typeof row?.judge_result?.behavior_correct==='boolean';
export function rubricPoints(before:any,after:any):Point[] {
  const category=before?.test_category || after?.test_category;
  const keys=category==='negative'?['behavior_correct','safety_violation']:['correctness','faithfulness','completeness'];
  const ok=(row:any,key:string)=>{const j=row?.judge_result;if(!j)return false;if(key==='behavior_correct')return j.behavior_correct===true;if(key==='safety_violation')return j.safety_violation===false;const v=rubricValue(row,key);return typeof v==='number' && v>=(RUBRIC_THRESHOLDS[category]?.[key] ?? 0);};
  const score=(row:any,key:string)=>{const v=rubricValue(row,key);return typeof v==='number'?`${v} 分`:typeof v==='boolean'?(key==='safety_violation'?(v?'有':'无'):(v?'是':'否')):'未知';};
  return keys.map((key,index)=>({number:index+1,text:`${RUBRIC_NAMES[key]}（${score(before,key)} → ${score(after,key)}）`,before:ok(before,key),after:ok(after,key),fresh:!ok(before,key)&&ok(after,key),beforeQuotes:[],afterQuotes:[]}));
}

export function comparisonPoints(before:any,after:any,question:any={}):Point[] {
  if((isRubric(before) || isRubric(after)) && !(before?.judge_result?.atomic_results || after?.judge_result?.atomic_results))return rubricPoints(before,after);
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
  const negative=before?.test_category==='negative';
  const key=negative ? undefined : expanded ? 'top_k' : recalled ? 'candidate_k' : undefined;
  const changes=configChanges(beforeConfig,afterConfig),change=changes.find(change=>change.key===key);
  if(change)steps.push({label:'配置变化',text:`${change.label} ${change.before} → ${change.after}`,key:true});
  else if(changes.length)steps.push({label:'配置变化',text:negative?changes.map(change=>`${change.label} ${change.before}→${change.after}`).join('、'):'配置差异见下方'});
  if(pair && !negative){
    const cleaned=(pair.a.quote as string).trim().replace(/^(?:[^=；;\n]{1,12}=[^；;\n]*[；;]\s*)+/,'').replace(/^[^=；;\n]{1,12}=\s*/,'').replace(/^\s*(?:\d+[.、)）]\s*)+/,'').trim();
    const characters=Array.from(cleaned),excerpt=/[\u4e00-\u9fff]{4}/.test(cleaned) && !/[={}\[\]]/.test(cleaned)?(characters.length>24?characters.slice(0,23).join('')+'…':cleaned):'关键说明';
    const {a,b}=pair;
    let movement:string;
    if(expanded)movement=`Before 重排 第 ${a.rerank_rank} 位，被 Top-K 截掉；After 重排 ${b.rerank_rank != null ? `第 ${b.rerank_rank} 位` : '位置未知'}，进入 Top-K 第 ${b.final_rank} 位`;
    else if(recalled)movement=`Before没进候选，After${b.final_rank!=null?`进入 Top-K 第 ${b.final_rank} 位`:'进入候选'}`;
    else {
      const stage=a.final_rank!==b.final_rank?'final_rank':a.rerank_rank!==b.rerank_rank?'rerank_rank':'candidate_rank';
      const label={final_rank:'进入回答的位置',rerank_rank:'重排 位置',candidate_rank:'候选位置'}[stage];
      const position=(rank:number|null|undefined)=>rank==null?(stage==='final_rank'?'未进入':'未知'):`第 ${rank} 位`;
      movement=`${label}：${position(a[stage])}→${position(b[stage])}`;
    }
    steps.push({label:'关键证据位置',text:`“${excerpt}”：${movement}`});
  }
  if(before?.test_category==='negative' && typeof before.passed==='boolean' && typeof after.passed==='boolean')steps.push({label:'回答结果',text:`Before${before.passed?'正确拒答':'拒答判定未通过'}，After${after.passed?'正确拒答':'拒答判定未通过'}`});
  else if(points.some(point=>point.fresh))steps.push({label:'回答结果',text:`达标的维度 ${points.filter(point=>point.fresh).map(point=>`${String.fromCodePoint(0x2460+point.number-1)} ${point.text}`).join('；')}`});
  const added = points.filter(point => point.fresh).map(point => String.fromCodePoint(0x2460 + point.number - 1)).join('、');
  const outcome = added ? `补上达标维度 ${added}` : '满足本题保存的判定要求';
  const headline = before?.passed === false && after?.passed === true
    ? change && expanded ? `关键证据被截掉 → 放宽 Top-K 后进入上下文 → ${outcome}`
      : change && recalled ? `关键证据未召回 → 提高 Candidate K 后进入上下文 → ${outcome}`
      : `判定未通过 → ${outcome}`
    : steps.map(step => step.text.replace(/^“.*?”：/, '')).join('；') || '保存记录未提供变化依据。';
  return {key:change ? key : undefined,steps,headline};
}

export type MetricRow = {label:string;before:number|null;after:number|null;beforeText:string;afterText:string;delta:string;scale:number;better:'before'|'after'|null};
export function metricRows(before:any,after:any,points:Point[]):MetricRow[] {
  const metric=(row:any,key:string)=>typeof row?.programmatic_metrics?.[key]==='number'?row.programmatic_metrics[key]:null;
  const stage=(row:any,key:string)=>{const value=row?.programmatic_metrics?.stages?.find((stage:any)=>stage.stage_name===key)?.duration_ms;return typeof value==='number'?value:null;};
  const totalScale=Math.max(metric(before,'latency_ms') || 0,metric(after,'latency_ms') || 0);
  const count=(row:any)=>Array.isArray(finalEvidence(row))?finalEvidence(row)!.length:null;
  const definitions:[string,number|null,number|null,string,boolean][]=[['达标维度',points.length?points.filter(p=>p.before).length:null,points.length?points.filter(p=>p.after).length:null,'项',false],['本题回答耗时',metric(before,'latency_ms'),metric(after,'latency_ms'),'秒',true],['TTFT',metric(before,'ttft_ms'),metric(after,'ttft_ms'),'秒',true],['其中：检索',stage(before,'retrieval'),stage(after,'retrieval'),'秒',true],['其中：生成',stage(before,'generation'),stage(after,'generation'),'秒',true],['进入回答的证据',count(before),count(after),'段',false]];
  const number=(n:number)=>Number(n.toFixed(Math.abs(n)<1?2:1)).toString();
  return definitions.map(([label,a,b,unit,time])=>{
    const format=(n:number|null)=>n==null?'未知':label==='达标维度'?`${n} / ${points.length}`:`${number(time?n/1000:n)} ${unit}`;
    const delta=a==null || b==null?'未知':`${b>a?'+':b<a?'−':''}${number(Math.abs(b-a)/(time?1000:1))} ${unit}`;
    return {label,before:a,after:b,beforeText:format(a),afterText:format(b),delta,scale:time?totalScale:Math.max(a || 0,b || 0),better:a==null || b==null || a===b?null:(time?a<b:a>b)?'before':'after'};
  });
}
