// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {EvolutionPage} from './pages/EvolutionPage';
import {formatValue} from './components/PipelineFields';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{if(root)act(()=>root.unmount());document.body.innerHTML='';vi.unstubAllGlobals()});
it('keeps candidate outcome fields uniform and saved planning in strategy without mutating evidence',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}')));
 const data={evaluation:{id:'BASE',config:{top_k:4,candidate_k:12}},optimization:{id:'EXP',candidates:['A','B','C','D'].map((candidate_label,i)=>({id:candidate_label,status:i===1?'failed':'generated',config:{top_k:6,candidate_k:12},reasoning:{candidate_label,experiment_kind:i?'exploratory':'confirmed',hypothesis:i?'调整参数；{"rerank": "query_only"}':'An unseen historical hypothesis must retain its exact original meaning.'},result:i===1?{evaluation_complete:false,completed:1,total:50}:undefined}))}};
 const saved=JSON.stringify(data);root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<EvolutionPage data={data}/>));await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='Candidates 对比')!.click());
 const cards=[...document.querySelectorAll('.candidate-cards > .candidate-card')];expect(cards).toHaveLength(3);
 for(const card of cards){expect([...card.querySelectorAll('dt')].map(e=>e.textContent)).toEqual(['答对','门槛通过','修好','新错']);expect(card.querySelector('.candidate-card-footer')).not.toBeNull();}
 expect(cards[1].textContent).toContain('评测停止');
 expect(cards[1].querySelector('dd')?.textContent).toContain('未知');
 expect(document.querySelector('.agent-round-strategy')?.textContent).toContain(data.optimization.candidates[0].reasoning.hypothesis);expect(document.querySelector('.agent-round-strategy')?.textContent).toContain('调整参数；Rerank 方式：原问题排序');expect(JSON.stringify(data)).toBe(saved);
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='Candidates 对比')!.click());await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='Candidate D')!.click());expect(document.querySelector(".d-design")).not.toBeNull();expect(document.querySelector<HTMLDetailsElement>(".d-story details")?.open).toBe(false);
 expect((fetch as any).mock.calls.every(([,init]:any)=>!init?.method || init.method==='GET')).toBe(true);
});
it('formats internal values without changing their meaning',()=>{
 expect(formatValue('query_only')).toBe('原问题排序');expect(formatValue(true)).toBe('开启');expect(formatValue(false)).toBe('关闭');expect(formatValue(0)).toBe('0');expect(formatValue(null)).toBe('未采集');
});
