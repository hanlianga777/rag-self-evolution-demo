// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {expect,it,vi} from 'vitest';
import {EvaluationPage} from './pages/EvaluationPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
it('reloads the persisted active Baseline and shows automatic recovery without a paid POST',async()=>{
 const active={id:'active',status:'running',requires_policy_upgrade:false,config:{run_target:'baseline'},dataset_snapshot:{id:'g',question_ids:['q']},result:{completed:37,total:50,auto_recovery:{authorized:true,state:'retrying',phase:'judge',retry_count:2},gates:{gates:[]}}};
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('/api/bad-cases')?[]:active))));
 const host=document.body.appendChild(document.createElement('div')),root=createRoot(host);
 await act(async()=>root.render(<EvaluationPage data={{evaluation:{id:'old',status:'completed',result:{}},workspace:{requires_policy_upgrade:true}}}/>));
 expect(host.textContent).toContain('后台自动重试Judge');expect(host.textContent).toContain('37 / 50');
 expect([...host.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent==='后台评测进行中')?.disabled).toBe(true);
 expect((fetch as any).mock.calls.every(([,init]:any)=>!init?.method || init.method==='GET')).toBe(true);
 await act(async()=>root.unmount());host.remove();vi.unstubAllGlobals();
});
it('keeps polling beyond the former 300-request limit',async()=>{
 vi.useFakeTimers();const active={id:'active',status:'running',cases:[],config:{run_target:'baseline'},dataset_snapshot:{question_ids:['q']},result:{completed:0,total:1,gates:{gates:[]}}};
 const fetcher=vi.fn(async()=>new Response(JSON.stringify(active)));vi.stubGlobal('fetch',fetcher);
 const host=document.body.appendChild(document.createElement('div')),root=createRoot(host);
 await act(async()=>root.render(<EvaluationPage data={{evaluation:active}}/>));
 await act(async()=>vi.advanceTimersByTimeAsync(350000));
 expect(fetcher.mock.calls.length).toBeGreaterThan(300);
 await act(async()=>root.unmount());host.remove();vi.clearAllTimers();vi.useRealTimers();vi.unstubAllGlobals();
});
