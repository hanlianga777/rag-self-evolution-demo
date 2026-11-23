import {useEffect, useState} from 'react';
import {detailJson} from '../preload';
import { Drawer, QuestionDrawer } from './Dialog';
import {LoadingSkeleton, Section} from './Primitives';
import {FrozenQuestionDetails, shortSourceName} from '../pages/FrozenQuestionDetails';
import {displayText} from '../display';

// Offsets refer to the unchanged Parent string. Do not reconstruct or re-chunk it.
export function childRanges(parent:any) {
 const text=parent.chunk_text || parent.text || '';
 const ranges=(parent.children || []).map((child:any,index:number)=>{
  const content=child.chunk_text || child.text || '';
  const start=typeof child.char_start==='number' && text.slice(child.char_start,child.char_end)===content ? child.char_start : text.indexOf(content);
  return {start,end:start<0?start:start+content.length,index};
 }).filter((range:any)=>range.start>=0 && range.end>range.start);
 const cuts=[...new Set<number>([0,text.length,...ranges.flatMap((r:any)=>[r.start,r.end])])].sort((a,b)=>a-b);
 return cuts.slice(0,-1).map((start,index)=>({text:text.slice(start,cuts[index+1]),children:ranges.filter((r:any)=>r.start<cuts[index+1] && r.end>start).map((r:any)=>r.index+1)}));
}
export function ParentSectionInfo({parent}:{parent:any}) {
 const path = parent?.parent_section_path || parent?.chapter;
 const titles = parent?.parent_subheadings || parent?.subsections;
 return <>{path && <p>{path}</p>}{titles?.length > 0 && <p>包含小标题 · {titles.join('、')}</p>}</>;
}
export function ChunkBrowser({open,onClose,parentId,initialDocumentId}:{open:boolean;onClose:()=>void;parentId?:string;initialDocumentId?:string}) {
 const [data,setData]=useState<any>(),[error,setError]=useState(''),[documentId,setDocumentId]=useState(''),[selected,setSelected]=useState(''),[question,setQuestion]=useState<any>();
 useEffect(()=>{if(!open)return;let cancelled=false;void detailJson<any>('/api/knowledge/chunk-browser').then(value=>{if(!cancelled){setData(value);const parent=value.parents?.find((p:any)=>p.chunk_id===parentId) || (initialDocumentId ? value.parents?.find((p:any)=>p.document_id===initialDocumentId) : value.parents?.[0]);setDocumentId(parent?.document_id || initialDocumentId || '');setSelected(parent?.chunk_id || '');}}).catch(e=>{if(!cancelled)setError(String(e));});return()=>{cancelled=true;};},[open,parentId,initialDocumentId]);
 const parents=(data?.parents || []).filter((p:any)=>p.document_id===documentId),parent=parents.find((p:any)=>p.chunk_id===selected) || parents[0];
 const questions=(data?.questions || []).filter((q:any)=>q.parent_ids?.includes(parent?.chunk_id));
 return <><Drawer className="chunk-browser-drawer" open={open} onOpenChange={value=>!value && onClose()} title="分块浏览器"><div className="drawer-body">{error?<p role="alert">{error}</p>:!data?<LoadingSkeleton label="正在读取分块"/>:<div className="chunk-browser-grid">
  <section aria-label="选择文档和父段落"><label>文档<select value={documentId} onChange={e=>{setDocumentId(e.target.value);setSelected('');}}>{data.documents.map((d:any)=><option key={d.id} value={d.id}>{shortSourceName(d.name)}</option>)}</select></label><div className="parent-list">{parents.map((p:any,index:number)=><button key={p.chunk_id} className="secondary" aria-pressed={parent?.chunk_id===p.chunk_id} onClick={()=>setSelected(p.chunk_id)}>段落 {index+1} · 第 {p.page_start} 页<br/>{p.chapter || p.section_path || '正文'}<small>{p.children.length} 个知识片段</small></button>)}</div></section>
  <section className="parent-reading" aria-label="父段落原文与知识片段范围"><h3>父段落原文</h3>{parent?<><p>{shortSourceName(parent.document_name)} · 第 {parent.page_start} 页</p><ParentSectionInfo parent={parent}/><p className="muted">高亮范围对应知识片段；重叠部分会同时标出多个序号。</p><div className="parent-verbatim">{childRanges(parent).map((part,index)=>part.children.length?<mark key={index} title={`知识片段 ${part.children.join('、')}`} data-children={part.children.join(',')}><sup className="child-range-number">{part.children.join("、")}</sup>{part.text}</mark>:<span key={index}>{part.text}</span>)}</div><ol className="child-legend">{parent.children.map((child:any,index:number)=><li key={child.chunk_id}><strong>片段 {index+1}</strong> · 第 {child.page_start} 页 · {child.token_count ?? '未知'} 字元</li>)}</ol></>:<p>暂无分块。</p>}</section>
  <section aria-label="命中父段落的考题"><h3>对应考题</h3>{['positive','ablation','negative'].map(category=><Section key={category} title={displayText(category)}>{questions.filter((q:any)=>q.test_category===category).map((q:any)=><button className="text-button topic-question" key={q.id} onClick={()=>setQuestion(q)}>{q.display_id} · {q.question}</button>)}{!questions.some((q:any)=>q.test_category===category) && <p className="muted">暂无</p>}</Section>)}</section>
 </div>}</div></Drawer><QuestionDrawer open={!!question} onOpenChange={value=>!value && setQuestion(undefined)} questionLabel={question?.display_id}>{question && <FrozenQuestionDetails row={question}/>}</QuestionDrawer></>;
}
export function ChunkDiagnostics() {
 const [data,setData]=useState<any>();
 useEffect(()=>{let active=true;void detailJson('/api/knowledge/chunk-diagnostics').then(value=>{if(active)setData(value);}).catch(()=>{if(active)setData({});});return()=>{active=false;};},[]);
 const value=(key:string,percent=false)=>typeof data?.[key]==='number'?`${Number((data[key]*(percent?100:1)).toFixed(1))}${percent?'%':''}`:'未知';
 return <Section title="分块诊断"><dl className="chunk-diagnostics">{[['父段落数','parent_count'],['知识片段数','child_count'],['碎块数','fragment_count'],['每个父段落的平均片段数','average_children_per_parent'],['只有一个片段的父段落占比','single_child_parent_ratio'],['知识片段平均长度','average_child_tokens']].map(([label,key])=><div key={key}><dt>{label}</dt><dd>{value(key,key==='single_child_parent_ratio')}</dd></div>)}</dl><p className="muted">碎块按少于 {data?.fragment_threshold_tokens ?? '未知'} 字元且非表格统计；长度来自索引记录，仅用于诊断。</p></Section>;
}
