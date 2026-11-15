import {apiUrl,getJson} from '../api';
import type {Citation} from '../types';

export async function openCitationPdf(citation:Citation, fallback:(citation:Citation)=>void) {
  // Open during the click so browser popup protection does not discard the PDF.
  const tab=window.open('about:blank','_blank');
  if(tab) tab.opener=null;
  try {
    const documents=await getJson<any[]>('/api/documents');
    const document=documents.find(row=>row.id===citation.document_id || row.name===citation.document);
    const name=document?.name || citation.document;
    const url=apiUrl(`/api/source-pdf?name=${encodeURIComponent(name)}`);
    const response=await fetch(url,{method:'HEAD'});
    if(!response.ok || !tab) throw new Error('PDF unavailable');
    tab.location.href=`${url}#page=${Math.max(1,citation.page_start || 1)}`;
  } catch {tab?.close();fallback(citation);}
}
