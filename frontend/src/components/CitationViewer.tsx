import {useEffect,useState} from 'react';
import {Drawer} from './Dialog';
import {apiUrl,getJson} from '../api';
import type {Citation} from '../types';
export function CitationViewer({citation,onClose}:{citation:Citation|null;onClose:()=>void}) {
 const [pdf,setPdf]=useState(''),[loading,setLoading]=useState(false);
 useEffect(()=>{
  setPdf('');if(!citation?.document_id || citation.page_start==null){setLoading(false);return;}let active=true;setLoading(true);
  void getJson<any>(`/api/documents/${encodeURIComponent(citation.document_id)}`).then(async doc=>{
   if(!doc.pdf_url)return;
   const url=apiUrl(doc.pdf_url),response=await fetch(url,{headers:{Range:'bytes=0-0'}});
   if(active && response.ok)setPdf(`${url}#page=${citation.page_start}`);
   void response.body?.cancel();
  }).catch(()=>{}).finally(()=>{if(active)setLoading(false);});
  return()=>{active=false;};
 },[citation]);
 const start=citation?.book_page_start ?? citation?.page_start, end=citation?.book_page_end ?? citation?.page_end;
 const pages=(first?:number,last?:number)=>first==null?'未知':`第 ${first}${last!=null && last!==first?`–${last}`:''} 页`;
 return <Drawer className="citation-viewer" open={!!citation} onOpenChange={open=>!open && onClose()} title="引用原页">
   <div className="drawer-body">
     <p><strong>{citation?.document || '文档未保存'}</strong></p>
     <p>章节 {citation?.section_path || '未知'}</p>
     <p>全书 {pages(start,end)}{start!==citation?.page_start && citation?.page_start!=null && ` · 分卷 ${pages(citation.page_start,citation.page_end)}`}</p>
     {loading?<p role="status">正在定位原页…</p>:pdf?<iframe title="引用 PDF 原页" src={pdf}/>:<><p className="muted">原页暂不可用</p><p className="saved-source-text">{citation?.content_preview || '未保存原文片段'}</p></>}
   </div>
 </Drawer>;
}
