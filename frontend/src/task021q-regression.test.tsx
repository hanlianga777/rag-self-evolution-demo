// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {EvolutionPage} from './pages/EvolutionPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{if(root)act(()=>root.unmount());document.body.innerHTML='';vi.unstubAllGlobals()});

it('shows corrected regression and frozen severity while retaining final qualification and saved audit',async()=>{
 const review={passed:false,status:'FAIL',new_critical_failures:0,new_ordinary_failures:3,limits:{critical:0,ordinary:1},fixed_count:1,case_severities:{Q13:'ordinary',Q30:'ordinary',Q37:'ordinary'}};
 const result={evaluation_run_id:'run-q',regression:{passed:true,status:'PASS',new_critical_failures:0,new_ordinary_failures:3},regression_review:review,new_regression_question_ids:['Q13','Q30','Q37'],release_qualification:{qualified:false},qualification:{qualified:false}};
 const baseline={id:'baseline-q',status:'completed',dataset_version_id:'golden-q',judge:{evaluation_identity:'identity-q'},cases:['Q13','Q30','Q37'].map(question_id=>({question_id,passed:true,severity:'ordinary'})),result:{gates:{gates:[]}}};
 const current={...baseline,id:'run-q',cases:baseline.cases.map(c=>({...c,passed:false,severity:'critical'}))};
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('/baseline-q')?baseline:url.endsWith('/run-q')?current:{search_space:{}}))));
 root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<EvolutionPage data={{evaluation:baseline,optimization:{id:'exp-q',candidates:[{id:'exp-q-R3-A',status:'evaluated',reasoning:{round:3,candidate_label:'A'},result}]}}}/>));
 await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent==='回归与推荐')!.click());
 const table=document.querySelector('.regression-summary-table')!;
 expect(table).not.toBeNull();
 expect([...table.querySelectorAll('tbody tr:first-child td')].map(c=>c.textContent)).toEqual(['Round 3 · Candidate A','1','0','3','严重 0 / 普通 1','未通过','不合格']);
 expect(document.querySelector('.regression-cases-table')?.textContent).toContain('普通退化');
 expect(document.querySelector('.regression-cases-table')?.textContent).not.toContain('严重退化');
 await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent==='严重')!.click());
 expect(document.querySelector('.regression-cases-table')?.textContent).not.toContain('Q13');
 expect(result.regression.status).toBe('PASS');expect(result.release_qualification.qualified).toBe(false);
});
