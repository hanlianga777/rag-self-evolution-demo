import {useEffect,useState} from 'react';
import {Drawer} from './Dialog';
import {apiUrl,getJson} from '../api';
import type {Citation} from '../types';
export function CitationViewer({citation,onClose}:{citation:Citation|null;onClose:()=>void}) {
 const [pdf,setPdf]=useState(''),[loading,setLoading]=useState(false);
 useEffect(()=>{
  setPdf('');if(!citation?.document_id)return;let active=true;setLoading(true);
  void getJson<any>(`/api/documents/${encodeURIComponent(citation.document_id)}`).then(async doc=>{
   if(!doc.pdf_url)return;
   const url=apiUrl(doc.pdf_url),response=await fetch(url,{headers:{Range:'bytes=0-0'}});
   if(active && response.ok)setPdf(`${url}#page=${citation.page_start || 1}`);
   void response.body?.cancel();
  }).catch(()=>{}).finally(()=>{if(active)setLoading(false);});
  return()=>{active=false;};
 },[citation]);
 return <Drawer className="citation-viewer" open={!!citation} onOpenChange={open=>!open && onClose()} title="引用原页"><div className="drawer-body"><p>{citation?.document} · 第 {citation?.page_start ?? '未知'} 页</p>{loading?<p role="status">正在定位原页…</p>:pdf?<iframe title="引用 PDF 原页" src={pdf}/>:<><p className="muted">原文件不可用，显示保存的原文片段。</p><p className="saved-source-text">{citation?.content_preview || '未保存原文片段'}</p></>}</div></Drawer>;
}
