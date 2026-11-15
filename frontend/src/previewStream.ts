import {apiUrl,requestError} from './api';
export type PreviewFrame={type:'delta'|'reset';text?:string};
// A single request: an interrupted stream must never silently pay for a retry.
export async function previewStream(question:string,onFrame:(frame:PreviewFrame)=>void|Promise<void>,signal?:AbortSignal) {
 const response=await fetch(apiUrl('/api/preview/stream'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question}),signal});
 if(!response.ok)throw new Error(requestError((await response.json().catch(()=>({}))).detail,response.status));
 if(!response.body)throw new Error('回答流不可用，请重试');
 const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='',result:any,completed=false;
 try {
  while(true){
   const part=await reader.read();buffer+=decoder.decode(part.value,{stream:!part.done}).replace(/\r\n/g,'\n');
   let end:number;
   while((end=buffer.indexOf('\n\n'))>=0){
    const frame=buffer.slice(0,end);buffer=buffer.slice(end+2);
    const payload=frame.split('\n').filter(line=>line.startsWith('data:')).map(line=>line.slice(5).trimStart()).join('\n');
    if(!payload)continue;
    const event=JSON.parse(payload);
    if(event.type==='error')throw new Error(event.message || '回答服务暂时不可用，请重试');
    if(event.type==='done'){result=event.result;completed=true;}
    else if(event.type==='delta' || event.type==='reset')await onFrame(event);
   }
   if(part.done)break;
  }
 } finally {reader.releaseLock();}
 if(!completed)throw new Error('回答传输中断，请重试');
 return result;
}
