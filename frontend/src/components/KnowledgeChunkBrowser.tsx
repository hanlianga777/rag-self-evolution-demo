import { useEffect, useRef, useState } from 'react';
import { getJson } from '../api';
import { Drawer } from './Dialog';
import { DrawerSection, LoadingSkeleton } from './Primitives';
import { InfoTip } from '../ui/HoverCard';
import { presentationText } from '../display';
import './knowledge-chunks.css';

type Row = Record<string, any>;
export const questionType = (q: Row) => ({positive:'正向题',ablation:'消融题',negative:'负向题'}[q.test_category as string] || '题型未记录');
const number = (value: unknown, digits = 1) => typeof value === 'number' ? value.toLocaleString('zh-CN',{minimumFractionDigits:digits,maximumFractionDigits:digits}) : '未知';

export function KnowledgeDiagnostics({ scope }: { scope: string }) {
  const [state, setState] = useState<{data?:Row;error?:string}>({});
  useEffect(() => { let cancelled=false;setState({});void getJson<Row>('/api/knowledge/chunk-diagnostics').then(data=>{if(!cancelled)setState({data});}).catch(()=>{if(!cancelled)setState({error:'分块诊断暂时无法读取'});});return()=>{cancelled=true;}; },[scope]);
  const data=state.data;
  const metrics = [
    ['碎块数', number(data?.fragment_count,0), `少于 ${data?.fragment_threshold_tokens ?? '未知'} tokens 的非表格 Child。碎块太短会缺少独立语义，完整小表格不算碎块。`],
    ['平均每个 Parent 的 Child 数',number(data?.average_children_per_parent),'一个 Parent 至少包含几个 Child，检索才能做到小块命中、大块回答。'],
    ['单 Child Parent 占比', typeof data?.single_child_parent_ratio==='number'?data.single_child_parent_ratio>0 && data.single_child_parent_ratio<.001?'<0.1%':`${number(data.single_child_parent_ratio*100)}%`:'未知','占比过高时，命中 Child 后补齐 Parent 能增加的上下文就很少。'],
    ['Child 平均长度',typeof data?.average_child_tokens==='number'?`${number(data.average_child_tokens)} tokens`:'未知','按索引保存的 token 数求平均。太短容易缺语义，太长容易把不相关内容一起找回来。'],
  ];
  return <section className="ui-card chunk-diagnostics"><h2>分块诊断</h2>{state.error?<p role="alert">{state.error}</p>:!data?<LoadingSkeleton label="正在读取分块诊断"/>:<div className="chunk-health">{metrics.map(([label,value,note])=><div key={label}><span>{label}<InfoTip label={label} content={note}/></span><strong>{value}</strong></div>)}</div>}</section>;
}

export function GoldenAnchorDrawer({ question, onClose }: {question?:Row;onClose:()=>void}) {
  const sources=(question?.evidence_details || []).flatMap((e:Row)=>e.chunks || []);
  return <Drawer open={!!question} onOpenChange={open=>{if(!open)onClose();}} title={question?`${question.display_id} · ${questionType(question)}`:'考题'}><div className="drawer-body">
    <DrawerSection title="问题"><p>{presentationText(question?.question || '')}</p></DrawerSection>
    <DrawerSection title="参考答案"><p className="anchor-answer">{presentationText(question?.reference_answer || '未保存参考答案')}</p></DrawerSection>
    {question?.expected_behavior && <DrawerSection title="预期行为"><p>{presentationText(({safe_rejection:'拒绝危险操作并说明风险',clarify:'先追问缺少的条件',insufficient_evidence:'说明现有资料不足',prompt_injection_resistance:'抵抗提示注入'} as Record<string,string>)[question.expected_behavior] || '按题卷保存的回答边界作答')}</p></DrawerSection>}
    <DrawerSection title="证据原文">{sources.length?sources.map((source:Row)=><article key={source.chunk_id}><h4>{source.document_name || '来源文档'} · 第 {source.page_start ?? '未知'} 页</h4><p className="anchor-answer">{source.chunk_text}</p></article>):<p>本题没有可对应当前分块的证据锚点。</p>}</DrawerSection>
    <p className="muted">来自当前冻结题卷，只读。</p>
  </div></Drawer>;
}

export function TopicDetails({ cluster, name, onParent, onQuestion }: {cluster:Row;name:string;onParent:(p:Row)=>void;onQuestion:(q:Row)=>void}) {
  const parents=cluster.parents || [], questions=cluster.questions || [];
  return <>
    <DrawerSection title="主题是什么"><p>{cluster.description || `这个主题汇集了与“${name}”相关的说明书内容。`}</p><p className="muted">关键词：{cluster.keywords?.join('、') || '未记录'}</p><p className="muted">来源：{cluster.source_documents?.join('、') || '未记录'}</p></DrawerSection>
    <DrawerSection title="包含哪些 Parent"><div className="topic-parent-list">{parents.map((p:Row)=><button className="secondary" key={p.chunk_id} onClick={()=>onParent(p)}>{p.chapter || p.section_path || '未记录章节'} · {p.child_count} 个 Child · 第 {p.page_start ?? '未知'} 页</button>)}</div>{!parents.length&&<p>还没有可浏览的 Parent。</p>}</DrawerSection>
    <DrawerSection title="对应哪些考题">{['positive','ablation','negative'].map(kind=><section className="topic-question-group" key={kind}><h4>{questionType({test_category:kind})}</h4>{questions.filter((q:Row)=>q.test_category===kind).map((q:Row)=><button className="topic-question" key={q.id} onClick={()=>onQuestion(q)}><strong>{q.display_id}</strong><span>{presentationText(q.question)}</span></button>)}{!questions.some((q:Row)=>q.test_category===kind)&&<p className="muted">还没有关联的{questionType({test_category:kind})}。</p>}</section>)}</DrawerSection>
  </>;
}

export function ParentOriginal({ parent, selected }: {parent:Row;selected:string[]}) {
  const target=useRef<HTMLSpanElement>(null);
  const chars=Array.from(String(parent.chunk_text || parent.text || ''));
  const children:Row[]=parent.children || [];
  const valid=children.filter(c=>Number.isInteger(c.char_start)&&Number.isInteger(c.char_end)&&c.char_start>=0&&c.char_end<=chars.length&&c.char_start<c.char_end);
  const bounds=[...new Set([0,chars.length,...valid.flatMap(c=>[c.char_start,c.char_end])])].sort((a,b)=>a-b);
  let selectedPlaced=false;
  useEffect(()=>{target.current?.scrollIntoView?.({block:'center'});},[parent.chunk_id,JSON.stringify(selected)]);
  return <>{valid.length!==children.length&&<p className="muted">部分 Child 未保存准确范围，暂不能标色。</p>}<div className="parent-original">{bounds.slice(0,-1).map((start,i)=>{
    const end=bounds[i+1], hits=valid.filter(c=>c.char_start<end&&c.char_end>start);
    const active=hits.some(c=>selected.includes(c.chunk_id));
    const first=active&&!selectedPlaced;if(first)selectedPlaced=true;
    return <span key={start} ref={first?target:undefined} data-overlap={hits.length>1} title={hits.map(c=>`Child ${children.indexOf(c)+1} / ${children.length}`).join('、')+(hits.length>1?' · 重叠范围':'')} className={[hits.length?`child-range child-tone-${children.indexOf(hits[0])%2}`:'',hits.length>1?'child-overlap':'',active?'child-selected':''].join(' ')}>{chars.slice(start,end).join('')}</span>;
  })}</div></>;
}

export function KnowledgeChunkBrowser({ location, scope, onClose, onQuestion }: {location?:{document_id?:string;parent_id?:string};scope:string;onClose:()=>void;onQuestion:(q:Row)=>void}) {
  const [state,setState]=useState<{data?:Row;error?:string}>({});
  const [docId,setDocId]=useState(''),[parentId,setParentId]=useState(''),[selected,setSelected]=useState<string[]>([]);
  useEffect(()=>{if(!location)return;let cancelled=false;setState({});setSelected([]);void getJson<Row>('/api/knowledge/chunk-browser').then(data=>{if(cancelled)return;setState({data});const doc=location.document_id || data.documents?.[0]?.id || '';setDocId(doc);setParentId(location.parent_id || data.parents?.find((p:Row)=>p.document_id===doc)?.chunk_id || '');}).catch(()=>{if(!cancelled)setState({error:'分块浏览器暂时无法读取，请关闭后重试。'});});return()=>{cancelled=true;};},[location,scope]);
  const data=state.data, parents=(data?.parents || []).filter((p:Row)=>p.document_id===docId);
  const parent=parents.find((p:Row)=>p.chunk_id===parentId), questions=(data?.questions || []).filter((q:Row)=>q.parent_ids?.includes(parentId));
  return <Drawer className="chunk-browser-drawer" open={!!location} onOpenChange={open=>{if(!open)onClose();}} title="分块浏览器">
    {state.error?<p className="drawer-body" role="alert">{state.error}</p>:!data?<LoadingSkeleton label="正在读取知识库分块"/>:<div className="chunk-browser">
      <aside className="chunk-column"><label htmlFor="chunk-document">选择文档</label><select id="chunk-document" value={docId} onChange={e=>{setDocId(e.target.value);setParentId(data.parents?.find((p:Row)=>p.document_id===e.target.value)?.chunk_id || '');setSelected([]);}}>{data.documents?.map((d:Row)=><option key={d.id} value={d.id}>{d.name}</option>)}</select><h3>章节 / Parent</h3><div className="parent-choices">{parents.map((p:Row,i:number)=><button key={p.chunk_id} aria-current={p.chunk_id===parentId} onClick={()=>{setParentId(p.chunk_id);setSelected([]);}}><strong>{p.chapter || p.section_path || `段落 ${i+1}`}</strong><span>{p.children.length} 个 Child · 第 {p.page_start ?? '未知'} 页</span></button>)}{!parents.length&&<p>还没有 Parent 分块。文档完成入库后可查看。</p>}</div></aside>
      <section className="chunk-column chunk-parent"><h3>{parent?.chapter || parent?.section_path || 'Parent 原文'}</h3>{parent?<><p className="muted chunk-legend">浅色交替表示 Child；双下划线表示重叠。悬停查看序号。</p><div className="parent-scroll"><ParentOriginal parent={parent} selected={selected}/></div></>:<p>请选择有 Parent 分块的文档。</p>}</section>
      <section className="chunk-column"><h3>关联考题</h3><p className="muted">按冻结题卷的证据锚点关联</p><div className="anchor-questions">{questions.map((q:Row)=>{const hits=parent?.children.filter((c:Row)=>q.child_ids.includes(c.chunk_id)) || [];return <article key={q.id}><button className="text-button" onClick={()=>setSelected(hits.map((c:Row)=>c.chunk_id))}>{q.display_id} · {questionType(q)}</button><p>{presentationText(q.question)}</p><small>命中 {hits.map((c:Row)=>`Child ${parent.children.indexOf(c)+1} / ${parent.children.length}`).join('、')}</small><button className="secondary" onClick={()=>{setSelected(hits.map((c:Row)=>c.chunk_id));onQuestion(q);}}>查看题目</button></article>;})}{!questions.length&&<p>这个 Parent 还没有关联考题。有证据锚点的考题会显示在这里。</p>}</div>{data.unmatched_anchor_count>0&&<p className="muted">部分旧锚点无法对应当前分块，未计为命中。</p>}</section>
    </div>}
  </Drawer>;
}
