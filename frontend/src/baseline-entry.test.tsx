// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {EvaluationPage} from './pages/EvaluationPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
async function render(preflight:any,versionFlag=false){
 const run={id:'explicit-old',status:'partial',requires_policy_upgrade:versionFlag,dataset_snapshot:{question_ids:['q']},cases:[],result:{completed:0,total:1}};
 const fetcher=vi.fn(async(url:string,init?:RequestInit)=>new Response(JSON.stringify(url.includes('/preflight')?preflight:url.endsWith('/api/bad-cases')?[]:init?.method==='POST'?{id:'new',status:'running'}:run)));
 vi.stubGlobal('fetch',fetcher);root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<EvaluationPage data={{evaluation:run}}/>));return fetcher;
}
async function authorize(label:string){
 await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent===label)!.click());
 await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent==='授权并运行此操作')!.click());
}
it('uses server full eligibility and sends the explicit resume ID',async()=>{
 const f=await render({can_start:true,can_resume:true,resume_source_id:'explicit-old',reason:null});
 expect(document.body.textContent).toContain('恢复 Baseline');await authorize('恢复 Baseline');
 const post=f.mock.calls.find(([,init])=>init?.method==='POST')!;expect(JSON.parse(post[1]!.body as string)).toEqual({resume_source_id:'explicit-old'});
});
it('forces fresh when full identity differs even if old policy flag says current',async()=>{
 const f=await render({can_start:true,can_resume:false,resume_source_id:null,reason:null,resume_reason:'Pipeline配置不同'});
 expect([...document.querySelectorAll('button')].some(b=>b.textContent==='恢复 Baseline')).toBe(false);
 await authorize('重新运行 Baseline（新版本）');const post=f.mock.calls.find(([,init])=>init?.method==='POST')!;
 expect(JSON.parse(post[1]!.body as string)).toEqual({fresh:true});
});
it('disables unavailable Golden/Corpus and never posts without authorization',async()=>{
 const f=await render({can_start:false,can_resume:false,resume_source_id:null,reason:'Corpus已变化，需确认新的Golden'});
 expect(document.body.textContent).toContain('Corpus已变化，需确认新的Golden');
 expect([...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent==='重新运行 Baseline（新版本）')?.disabled).toBe(true);
 expect(f.mock.calls.some(([,init])=>init?.method==='POST')).toBe(false);
});
