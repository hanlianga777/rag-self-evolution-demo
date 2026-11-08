// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {OperationProvider,useOperation} from './operation';
import {TruncatedText} from './components/Primitives';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
afterEach(()=>{document.body.innerHTML='';vi.unstubAllGlobals();vi.restoreAllMocks();});
it('uses ClampText for prose and preserves interactive rich content',async()=>{
 const root=createRoot(document.body.appendChild(document.createElement('div')));
 const click=vi.fn();
 await act(async()=>root.render(<><TruncatedText lines={4}>完整原文</TruncatedText><TruncatedText><button onClick={click}>查看</button></TruncatedText></>));
 expect(document.querySelector('.ui-clamp')?.textContent).toBe('完整原文');
 expect((document.querySelector('.ui-clamp') as HTMLElement).style.webkitLineClamp).toBe('4');
 await act(async()=>document.querySelector('button')!.click());expect(click).toHaveBeenCalledOnce();
 await act(async()=>root.unmount());
});
it('maps waiting, confirms stop and resumes the saved Candidate through the existing endpoint',async()=>{
 const fetcher=vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('/stop')?{status:'stopped',result:{completed:1,total:3,stop_request:true}}:{id:'resumed'})));
 vi.stubGlobal('fetch',fetcher);
 let op:ReturnType<typeof useOperation>;
 function Harness(){op=useOperation();return null;}
 const root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<OperationProvider restore={false}><Harness/></OperationProvider>));
 await act(async()=>op.start('Round 2 · Candidate A · Sandbox 评测',{id:'one',runId:'old',candidateId:'candidate-a',kind:'evaluation',pricePause:{paused:true}}));
 expect(document.querySelector('.ui-run-title')?.textContent).toBe('Round 2 · Candidate A');
 expect(document.querySelector('.ui-run-state')?.textContent).toContain('稍后自动继续');
 expect(document.querySelector<HTMLButtonElement>('.go')?.disabled).toBe(true);
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='停止运行')!.click());
 expect(fetcher).not.toHaveBeenCalled();
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='确认停止')!.click());
 expect(fetcher.mock.calls[0][0]).toContain('/api/evaluations/old/stop');
 expect(document.querySelector('.ui-run-state')?.textContent).toContain('已停止');
 await act(async()=>document.querySelector<HTMLButtonElement>('.go')!.click());
 expect(fetcher.mock.calls[1][0]).toContain('/api/candidates/candidate-a/run');
 expect(op!.operations[0].runId).toBe('resumed');
 expect(document.body.textContent).not.toMatch(/Operation ID|Provider|Model|Attempt|高峰|平价/);
 await act(async()=>root.unmount());
});
it.each([
 {title:'Baseline',detail:{kind:'evaluation' as const,runId:'saved-base'},endpoint:'/api/evaluations/run',body:{resume_source_id:'saved-base'}},
 {title:'局部修订',detail:{kind:'revision' as const},endpoint:'/api/governance/revisions/saved/resume',body:{}},
 {title:'Round 2 A/B/C · Sandbox',detail:{experimentId:'saved-exp'},endpoint:'/api/experiments/saved-exp/run-cycle',body:{}},
])('continues $title with its existing saved checkpoint endpoint',async({title,detail,endpoint,body})=>{
 const calls:Array<{url:string;init?:RequestInit}>=[];
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
  calls.push({url,init});
  return new Response(JSON.stringify(url.includes('/preflight')?{can_start:true,can_resume:true,resume_source_id:'saved-base'}:{id:'child'}));
 }));
 let op:ReturnType<typeof useOperation>;
 function Harness(){op=useOperation();return null;}
 const root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<OperationProvider restore={false}><Harness/></OperationProvider>));
 await act(async()=>op.start(title,{id:'saved',status:'stopped',...detail}));
 await act(async()=>document.querySelector<HTMLButtonElement>('.go')!.click());
 const writes=calls.filter(c=>c.init?.method==='POST');expect(writes).toHaveLength(1);
 expect(writes[0].url).toContain(endpoint);expect(JSON.parse(String(writes[0].init?.body || '{}'))).toEqual(body);
 await act(async()=>root.unmount());
});
it('never creates a fresh Baseline when the saved resume preflight refuses it',async()=>{
 const fetcher=vi.fn(async()=>new Response(JSON.stringify({can_start:true,can_resume:false,reason:'断点不兼容'})));
 vi.stubGlobal('fetch',fetcher);
 let op:ReturnType<typeof useOperation>;function Harness(){op=useOperation();return null;}
 const root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<OperationProvider restore={false}><Harness/></OperationProvider>));
 await act(async()=>op.start('Baseline',{id:'saved',kind:'evaluation',status:'failed'}));
 await act(async()=>document.querySelector<HTMLButtonElement>('.go')!.click());
 expect(fetcher).toHaveBeenCalledOnce();expect(document.querySelector('.ui-run[role=alert]')?.textContent).toContain('断点不兼容');
 await act(async()=>op.start('没有续跑入口',{id:'other',status:'stopped'}));
 expect(document.querySelectorAll<HTMLButtonElement>('.go')[1].disabled).toBe(true);
 await act(async()=>root.unmount());
});
it('pins truncated prose without activating the surrounding row, while short prose keeps the row action',async()=>{
 vi.spyOn(Element.prototype,'scrollHeight','get').mockReturnValue(120);
 vi.spyOn(Element.prototype,'clientHeight','get').mockReturnValue(40);
 const open=vi.fn();const root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<div onClick={open}><TruncatedText>很长的题目</TruncatedText></div>));
 await act(async()=>document.querySelector<HTMLElement>('.ui-clamp')!.click());
 expect(open).not.toHaveBeenCalled();expect(document.querySelector('.ui-float.pinned')).not.toBeNull();
 vi.spyOn(Element.prototype,'scrollHeight','get').mockReturnValue(40);
 await act(async()=>root.render(<div onClick={open}><TruncatedText>短题目</TruncatedText></div>));
 await act(async()=>document.querySelector<HTMLElement>('.ui-clamp')!.click());expect(open).toHaveBeenCalledOnce();
 await act(async()=>root.unmount());vi.restoreAllMocks();
});
