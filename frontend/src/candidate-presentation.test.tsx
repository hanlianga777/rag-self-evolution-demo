// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {EvolutionPage} from './pages/EvolutionPage';
import {formatValue} from './components/PipelineFields';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{if(root)act(()=>root.unmount());document.body.innerHTML='';vi.unstubAllGlobals()});
it('keeps all candidate fields in the same order, including empty and incomplete records, without mutating evidence',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}')));
 const data={evaluation:{id:'BASE',config:{top_k:4,candidate_k:12}},optimization:{id:'EXP',candidates:['A','B','C','D'].map((candidate_label,i)=>({id:candidate_label,status:i===1?'failed':'generated',config:{top_k:6,candidate_k:12},reasoning:{candidate_label,experiment_kind:i?'exploratory':'confirmed',hypothesis:i?'调整参数；{"rerank": "query_only"}':'An unseen historical hypothesis must retain its exact original meaning.'},result:i===1?{evaluation_complete:false,completed:1,total:50}:undefined}))}};
 const saved=JSON.stringify(data);root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<EvolutionPage data={data}/>));await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='A/B/C/D')!.click());
 const cards=[...document.querySelectorAll('.candidate-cards > .candidate-card')];expect(cards).toHaveLength(4);
 for(const card of cards){expect([...card.querySelectorAll('.candidate-story-block > .field-label')].map(e=>e.textContent)).toEqual(['优化目标','优化策略','参数变化','预期收益','潜在风险','实验结果']);expect(card.querySelectorAll('.candidate-field-content')).toHaveLength(6);expect(card.querySelector('.candidate-card-footer')).not.toBeNull();}
 expect(cards[1].querySelector('.candidate-story-block:last-child')?.textContent).toContain('已完成 1/50');
 expect(document.body.textContent).toContain('历史英文原文');expect(document.body.textContent).toContain('仅基于查询的重排序');expect(document.body.textContent).not.toContain('{"rerank"');expect(JSON.stringify(data)).toBe(saved);
 expect((fetch as any).mock.calls.every(([,init]:any)=>!init?.method || init.method==='GET')).toBe(true);
});
it('formats internal values without changing their meaning',()=>{
 expect(formatValue('query_only')).toBe('仅基于查询的重排序');expect(formatValue(true)).toBe('开启');expect(formatValue(false)).toBe('关闭');expect(formatValue(0)).toBe('0');expect(formatValue(null)).toBe('未采集');
});
