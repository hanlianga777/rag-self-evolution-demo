import {afterEach,expect,it,vi} from 'vitest';
import {previewStream} from './previewStream';
afterEach(()=>vi.unstubAllGlobals());
it('decodes split UTF-8, applies reset frames, and returns exactly one completion without a retry',async()=>{
 const body=': waiting\n\ndata: '+JSON.stringify({type:'delta',text:'旧答'})+'\n\ndata: '+JSON.stringify({type:'reset'})+'\n\ndata: '+JSON.stringify({type:'delta',text:'正确中文'})+'\n\ndata: '+JSON.stringify({type:'done',result:{baseline:{answer:'正确中文'}}})+'\n\n';
 const bytes=new TextEncoder().encode(body);
 const fetcher=vi.fn(async()=>new Response(new ReadableStream({start(controller){for(let i=0;i<bytes.length;i+=2)controller.enqueue(bytes.slice(i,i+2));controller.close();}})));
 vi.stubGlobal('fetch',fetcher);let text='';
 const result=await previewStream('测试',frame=>{text=frame.type==='reset'?'':text+frame.text;});
 expect(text).toBe('正确中文');expect(result.baseline.answer).toBe('正确中文');expect(fetcher).toHaveBeenCalledTimes(1);
 expect(fetcher.mock.calls[0]).toEqual([expect.stringContaining('/api/preview/stream'),expect.objectContaining({method:'POST',body:JSON.stringify({question:'测试'})})]);
});
it('reports an interrupted stream and never submits a synchronous fallback',async()=>{
 const fetcher=vi.fn(async()=>new Response('data: '+JSON.stringify({type:'delta',text:'部分'})+'\n\n'));vi.stubGlobal('fetch',fetcher);
 await expect(previewStream('测试',()=>{})).rejects.toThrow('回答传输中断');expect(fetcher).toHaveBeenCalledTimes(1);
});
it('preserves the reset when a server error follows partial output',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response('data: '+JSON.stringify({type:'error',message:'服务繁忙'})+'\n\n')));
 await expect(previewStream('测试',()=>{})).rejects.toThrow('服务繁忙');
});
