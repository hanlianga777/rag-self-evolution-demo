// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {EvolutionPage} from './pages/EvolutionPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
const candidate=(label:string,status:string,result:any={},extra:any={})=>({id:'candidate-'+label,status,config:{top_k:4},reasoning:{round:1,candidate_label:label,hypothesis:'验证保存的假设'},result,...extra});
const experiment=(candidates:any[],extra:any={})=>({id:'experiment-013c',baseline_run_id:'baseline',candidates,evaluation_budget:{used:0,max:12,reserved_for_d:1},result:{},...extra});
async function mount(optimization:any,badCases:any[]=[]){
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/api/experiments/')||url.includes('/api/optimization')?optimization:{search_space:{}}))));
 root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<EvolutionPage data={{workspace:{},evaluation:{id:'baseline',status:'completed',config:{top_k:4},result:{}},badCases,optimization}}/>));
}
async function click(text:string){await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(button=>button.textContent===text)!.click());}
it('separates running, product interruption, evaluated failure and qualified cards',async()=>{
 await mount(experiment([candidate('A','running'),candidate('B','failed',{evaluation_complete:false,completed:7,total:50},{product_interruption:true}),candidate('C','evaluated',{qualification:{qualified:false}}),candidate('D','evaluated',{qualification:{qualified:true}})]));
 await click('方案对比');
 const cards=[...document.querySelectorAll('.candidate-card')];
 expect(cards.map(card=>card.querySelector('.candidate-card-header .badge')?.textContent)).toEqual(['运行中','评测中断','未通过']);

 expect(cards[1].querySelector('.candidate-card-header .badge')?.classList.contains('warning')).toBe(true);
 expect(cards[1].textContent).toContain('产品故障，会自动续跑');
 expect(cards[1].textContent).not.toContain('付费确认');
 await click('进化路线');expect(document.querySelector('.d-story .ui-status')?.textContent).toBe('合格');
});
it('does not promise automatic continuation for permission or identity failures',async()=>{
 await mount(experiment([candidate('A','failed',{evaluation_complete:false,error:'Provider权限不足'},{product_interruption:false})]));
 await click('方案对比');
 expect(document.querySelector('.candidate-card-header .badge')?.textContent).toBe('评测停止');
 expect(document.querySelector('.candidate-card')?.textContent).not.toContain('自动续跑');
});
it('reads budget usage from the API even when several candidates are interrupted',async()=>{
 await mount(experiment(['A','B','C'].map(label=>candidate(label,'failed',{evaluation_complete:false},{product_interruption:true})),{evaluation_budget:{used:0,max:12,reserved_for_d:1}}));
 expect(document.querySelector('.ui-agent-stats')?.textContent).toContain('0 / 12');
 await click('进化路线');
 expect(document.body.textContent).not.toContain('3 / 12');
});
it('does not infer paid usage from candidate statuses when the budget is missing',async()=>{
 await mount(experiment([candidate('A','failed')],{evaluation_budget:undefined}));
 await click('进化路线');
 expect(document.body.textContent).toContain('预算尚未同步');
 expect(document.body.textContent).not.toContain('1 / 12');
});
it('keeps every single-pass failed question as a target even with a legacy exclusion flag',async()=>{
 await mount(experiment([]),[true,false].map((target,index)=>({id:'bad-'+index,run_id:'baseline',question_id:'Q0'+index,result:{passed:false,optimization_target:target,question:'问题'+index}})));
 expect(document.querySelector('.ui-evo-start')?.textContent).toContain('2 个 Bad Case'); expect(document.querySelectorAll('.agent-fact')).toHaveLength(2);
});
it('keeps unfinished planning in the flat toolbar after a Sandbox exists and keeps idle progress out of the header',async()=>{
 await mount(experiment([candidate('A','failed',{evaluation_run_id:'saved-run',evaluation_complete:false},{product_interruption:true})],{coverage_plan:{status:'incomplete',covered_count:0,total:1,binding:'binding',matrix:[{question_id:'CSV-20261101100758945425-41',candidates:[],gap:'本轮剩余A/B/C容量不足，需明确调整规划，不能宣称完成'}]}}));
 expect(document.querySelector('.page-title')?.textContent).not.toContain('查看 Sandbox 进度');
 expect(document.querySelector('.page-title')?.textContent).not.toContain('补齐本轮规划');
 expect(document.querySelector('.agent-secondary-actions')?.textContent).toContain('补齐本轮规划');
 expect(document.querySelector('.page-title button[aria-haspopup="menu"]')).toBeNull();
 await click('方案对比');
 expect(document.querySelector('.tabs button.active')?.textContent).toBe('方案对比');
 expect(document.querySelector('.agent-secondary-actions')?.textContent).toContain('补齐本轮规划（不收费）');
 expect(document.querySelector('.ui-agent-stats')?.textContent).toContain('有覆盖缺口');
 await click('进化路线');
 const detail=document.querySelector('.page-content')!.textContent;
 expect(detail).toContain('Q41 暂时没有方案覆盖');
 expect(detail).toContain('三套方案的名额已用完');
 expect(detail).not.toContain('Q27');
 expect(detail).toContain('规划未完成');
 expect((fetch as any).mock.calls.every(([,init]:any)=>!init?.method)).toBe(true);
});
