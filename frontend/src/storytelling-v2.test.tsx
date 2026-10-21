// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {EvaluationPage} from './pages/EvaluationPage';
import {EvolutionPage} from './pages/EvolutionPage';
import {VersionsPage} from './pages/VersionsPage';
import {VerificationPage} from './pages/VerificationPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{if(root)act(()=>root.unmount());document.body.innerHTML='';sessionStorage.clear();localStorage.clear();vi.unstubAllGlobals();});
const view={is_technical_bad_case:true,analysis_category:'rag_failure',primary_root_cause:'Retrieval',optimization_directions:['candidate_recall'],phenomena:[{name:'检索失败'}]};
const rows=['Q71','Q72'].map((question_id,i)=>({question_id,question:`问题${i}`,passed:false,diagnostic_view:{...view,primary_root_cause:i?'Generation':'Retrieval',phenomena:[{name:i?'模型过度拒答':'检索失败'}]}}));
const evaluation={id:'BASE',status:'completed',config:{candidate_k:12},cases:rows,result:{bad_case_count:2,gates:{passed:true,passed_count:11,total:11}}};
const badCases=rows.map(row=>({id:'BC-'+row.question_id,question_id:row.question_id,run_id:'BASE',result:row}));
const mount=async(node:React.ReactNode)=>{root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));};
const click=async(label:string)=>act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent===label)!.click());
it('uses one finite filter per dimension, real counts and resets on returning to diagnosis',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('/api/bad-cases')?badCases:evaluation))));
 await mount(<EvaluationPage data={{evaluation,badCases}}/>);await click('Bad Case 诊断');
 expect(document.querySelector('.diagnosis-filters [role=combobox]')).toBeNull();
 const retrieval=[...document.querySelectorAll<HTMLButtonElement>('[aria-label="失败现象"] button')].find(b=>b.textContent?.includes('检索失败'))!;
 await act(async()=>retrieval.click());expect(document.querySelectorAll('.diagnosis-list tbody tr')).toHaveLength(1);
 await click('Hard Gate');await click('Bad Case 诊断');expect(document.querySelectorAll('.diagnosis-list tbody tr')).toHaveLength(2);
 expect(document.body.textContent).not.toContain('恢复全部');expect(document.body.textContent).not.toContain('每类首例');
});
it('groups multiple saved candidate hypotheses under one actual problem and keeps raw rationale folded',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({search_space:{}}))));
 const candidates=['A','B'].map((label,i)=>({id:label,status:'generated',config:{candidate_k:24+i},reasoning:{candidate_label:label,observed_evidence:[badCases[0].id],hypothesis:'假设'+label,proposal:'candidate_missing=true 原始提出理由'}}));
 const data={evaluation,badCases,optimization:{id:'EXP',candidates}};const before=JSON.stringify(data);
 await mount(<EvolutionPage data={data}/>);await click('优化 Agent');
 expect(document.querySelectorAll('.strategy-branch')).toHaveLength(2);expect(document.querySelector('.strategy-branch')?.querySelectorAll('.strategy-hypotheses section')).toHaveLength(2);expect(document.querySelector('.experiment-plan')).toBeNull();
 await click('Candidate A · 详情');expect([...document.querySelectorAll('.drawer p')].filter(p=>p.textContent?.includes('candidate_missing')).every(p=>p.closest('details'))).toBe(true);expect(JSON.stringify(data)).toBe(before);
});
it('compares a pending release against current Production rather than unrelated Baseline configuration',async()=>{
 const candidate={id:'A',config:{candidate_k:24},reasoning:{candidate_label:'A'},release_state:{sandbox:true,qualified:true,recommended:true,round_complete:true}};
 await mount(<VersionsPage data={{evaluation:{config:{candidate_k:99}},versions:[{id:'initial',status:'active',provenance:'bootstrap',config:{candidate_k:12}}],optimization:{candidates:[candidate]}}}/>);
 const diff=document.querySelector('.unpublished-candidates .parameter-diff')!;expect(diff.textContent).toContain('12');expect(diff.textContent).toContain('24');expect(diff.textContent).not.toContain('99');
});
it('shows the real feedback chain with a compact empty state and no pretend monitoring rows',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({events:[],triggers:[]}))));
 await mount(<VerificationPage data={{monitoring:{events:[],triggers:[]}}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>);await click('Monitoring');
 expect(document.querySelectorAll('.decision-chain li')).toHaveLength(4);expect(document.querySelector('.monitoring-table')).toBeNull();expect(document.querySelector('.story-empty')?.textContent).toContain('当前尚无反馈记录');expect((fetch as any).mock.calls.every(([,init]:any)=>!init?.method || init.method==='GET')).toBe(true);
});
