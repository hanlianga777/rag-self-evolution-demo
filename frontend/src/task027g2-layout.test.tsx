// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {VersionsPage} from './pages/VersionsPage';
import {VerificationPage} from './pages/VerificationPage';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';localStorage.clear();sessionStorage.clear();history.replaceState(null,'','/');vi.unstubAllGlobals();});
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
const config={candidate_k:24,top_k:6,generation_thinking:'high',prompt_strategy:'Grounded'};
const d={id:'exp-D',status:'evaluated',reasoning:{candidate_label:'D'},config,result:{continued_failure_question_ids:['Q06','Q27']}};
const optimization={baseline_run_id:'baseline',candidates:[d],recommendation:{recommended_candidate:d.id},result:{d_facts:{remaining_failures:[
 {question_id:'Q04',evidence_positions:[{final:'未进入',reranked:8}]},
 {question_id:'Q06',evidence_positions:[{final:1,reranked:1},{final:'未进入',reranked:7,candidates:14}]},
 {question_id:'Q27',evidence_positions:[{final:'未进入',reranked:24,candidates:12}]},
]}}};
it('separates saved version identity, provenance, retrieval parameters and answer strategy',async()=>{
 const versions=[{id:'online',status:'active',provenance:'published',created_at:'2026-11-08T08:08:00Z',config,snapshot:{candidate_id:d.id}},{id:'initial',status:'archived',provenance:'bootstrap',config}];
 await mount(<VersionsPage data={{versions,optimization}}/>);
 const cells=document.querySelectorAll('.release-history-table tbody tr:first-child td');
 expect(cells[0].querySelector('button')?.textContent).toBe('Candidate D');
 expect(cells[0].querySelector('.release-history-meta')?.textContent).toMatch(/^推荐发布 · /);
 expect(cells[2].querySelector('.release-history-main')?.textContent).toBe('Candidate K 24 · Top-K 6 · Thinking High');
 expect(cells[2].querySelector('.release-history-meta')?.textContent).toBe('回答策略 有据生成');
 expect(document.querySelector('.release-history-table tbody tr:nth-child(2) td:first-child')?.textContent).toBe('Baseline初始配置');
});
it('shows only saved remaining failures and online Bad Cases inside the next-input card without writes',async()=>{
 location.hash='#verification?tab=monitoring';const fetcher=vi.fn();vi.stubGlobal('fetch',fetcher);
 const before=JSON.stringify(optimization);
 await mount(<VerificationPage data={{workspace:{current_baseline_id:'baseline'},optimization,monitoring:{events:[]}}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>);
 const card=document.querySelector('.monitoring-next-inputs');
 expect(document.querySelectorAll('.monitoring-layout > .panel')).toHaveLength(2);
 expect(card?.textContent).toContain('下一轮已知输入');
 expect(card?.textContent).toContain('关键证据重排后排第 7 位，Top-K 6 拿不到');
 expect(card?.textContent).toContain('关键证据重排后排第 24 位，Top-K 6 拿不到');
 expect([...card!.querySelectorAll('.ui-q')].map(n=>n.textContent)).toEqual(['Q06','Q27']);
 expect(card?.querySelector('.monitoring-online-bad-cases')?.textContent).toContain('暂无');
 expect(document.querySelectorAll('.feedback-next-inputs')).toHaveLength(1);
 expect(card?.querySelector('.feedback-next-inputs')?.textContent).toBe('这些问题会作为下一轮受控优化的输入，仍要重新走评测、回归和三道 Gate。');
 expect(fetcher).not.toHaveBeenCalled();expect(JSON.stringify(optimization)).toBe(before);
 await act(async()=>card!.querySelector<HTMLButtonElement>('button')!.click());
 expect(location.hash).toContain('tab=compare&q=Q06');
});
it('keeps missing evidence and mismatched Baseline results unknown while showing saved marked problems',async()=>{
 location.hash='#verification?tab=monitoring';
 const events=[{id:'m',question:'保存的线上问题',answer:'保存回答',determinable:true,bad_case:true},{id:'unmarked',question:'待标注问题',bad_case:true}];
 await mount(<VerificationPage data={{workspace:{current_baseline_id:'other'},optimization,monitoring:{events}}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>);
 const card=document.querySelector('.monitoring-next-inputs');
 expect(card?.textContent).toContain('未修好题目未知');
 expect(card?.querySelector('.monitoring-online-bad-cases')?.textContent).toContain('保存的线上问题');
 expect(card?.querySelector('.monitoring-online-bad-cases')?.textContent).not.toContain('待标注问题');
 expect(card?.querySelectorAll('.ui-q')).toHaveLength(0);
 await act(async()=>root.render(<VerificationPage data={{workspace:{current_baseline_id:'baseline'},optimization:{...optimization,result:{}},monitoring:{events}}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>));
 expect(document.querySelector('.monitoring-next-inputs')?.textContent).toContain('保存的证据位置不足，原因未知');
});
