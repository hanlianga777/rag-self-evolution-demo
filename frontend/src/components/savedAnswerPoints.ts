type Row=Record<string,any>;
const array=(value:any):Row[]=>Array.isArray(value)?value:[];
const ids=(value:Row):string[]=>[value.chunk_id,value.source_id,...(value.source_chunk_ids || [])].filter(Boolean);
const matches=(row:Row,id:string)=>[row.chunk_id,row.parent_chunk_id,...(row.matched_child_ids || [])].includes(id);
const normalize=(text:string)=>text.normalize('NFKC').replace(/[^\p{L}\p{N}]/gu,'').toLowerCase();
export type SavedAnswerPoint={number:number;text:string;met:boolean|null;reason:string;candidate:string;rerank:string;final:string};

/** Join saved requirements by ID, and evidence by source ID or literal quote. Never by array position. */
export function savedAnswerPoints(item:Row,question:Row={}):SavedAnswerPoint[] {
  const requirements=question.business_requirements || question.raw?.business_requirements || item.business_requirements || {};
  const atoms=array(item.judge_result?.atomic_results),checks=array(item.judge_result?.checks);
  let required=array(requirements.required_checks);
  if(!required.length){
    const raw=String(question.reference_answer || item.reference_answer || '');
    const reference=/<\/?[a-z]/i.test(raw)?[]:raw.split('\n').filter(line=>line.trim() && !/^(?:历史未保存|回答未保存|safe_rejection$|clarify$|insufficient_evidence$)/.test(line.trim()));
    required=reference.map((text,index)=>({requirement:text.replace(/^\s*\d+[.、)）]\s*/,''),number:index+1}));
  }
  const evidence=[...array(requirements.sources),...array(question.evidence || question.acceptable_evidence || question.raw?.evidence)];
  const savedTrace=item.programmatic_metrics?.retrieval_trace || {};
  const trace={...savedTrace,final:savedTrace.final ?? item.retrieved_chunks};
  const allStages=['candidates','reranked','final'].flatMap(stage=>array(trace[stage]));
  return required.map((requirement,index)=>{
    const text=requirement.requirement || '要点文字未保存';
    const number=Number(requirement.id?.match(/-R(\d+)$/)?.[1]) || requirement.number || index+1;
    const selected=requirement.id?atoms.filter(atom=>atom.atomic_id===requirement.id || atom.atomic_id?.startsWith(requirement.id+'-')):atoms.filter(atom=>new RegExp(`-R${number}(?:-\\d+)?$`).test(atom.atomic_id || ''));
    const check=checks.find(check=>check.requirement===text);
    const met=selected.length?(selected.some(atom=>atom.state==='NOT_MET')?false:selected.every(atom=>atom.state==='MET')?true:null):typeof check?.met==='boolean'?check.met:null;
    const reason=selected.map(atom=>atom.reason).filter(Boolean).join('\n') || check?.reason || '未保存该要点的判分理由';
    const sourceIds:string[]=requirement.source_chunk_ids || [];
    // Legacy records can bind evidence by an exact required fact, never by row index.
    const sources=evidence.filter(source=>sourceIds.length?ids(source).some(id=>sourceIds.includes(id)):[source.quote,...(source.evidence_key_points || [])].some(quote=>quote && normalize(quote.replace(/^\s*\d+[.、)）]\s*/,''))===normalize(text)));
    const boundIds=sourceIds.filter(id=>sources.some(source=>ids(source).includes(id)) || allStages.some(row=>matches(row,id)));
    const quotes=sources.flatMap(source=>source.quote?[source.quote]:source.evidence_key_points || []).filter(Boolean).map(normalize);
    const rank=(stage:string)=>{
      const rows=trace[stage];
      if(!Array.isArray(rows) || trace.status && trace.status!=='completed' || !boundIds.length && !quotes.length || sourceIds.some(id=>!boundIds.includes(id)))return null;
      return rows.flatMap((row:Row,index:number)=>(boundIds.length?boundIds.some(id=>matches(row,id)):quotes.some(quote=>quote && normalize(row.content || row.chunk_text || row.text || '').includes(quote)))?[index+1]:[]);
    };
    const candidates=rank('candidates'),reranked=rank('reranked'),final=rank('final');
    const partial=final?.length && boundIds.some(id=>!array(trace.final).some(row=>matches(row,id)));
    const label=(ranks:number[]|null)=>ranks?.length?`第 ${ranks.join('、')} 位`:'—';
    return {number,text,met,reason,candidate:label(candidates),rerank:label(reranked),final:final===null?'—':final.length?partial?'部分':'是':'否'};
  });
}
