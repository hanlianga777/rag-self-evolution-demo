// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {expect,it,vi} from 'vitest';
import {filterDiagnosis,allDiagnosis,DiagnosisFilters,DiagnosisTable} from './components/EvaluationDiagnosis';
const rows=[{question_id:'Q1',question:'操作',failure_tags:['Hallucination','Unsafe Answer'],primary_root_cause:'Safety',diagnosis:{status:'confirmed'},diagnostic_view:{is_technical_bad_case:true,analysis_category:'rag_failure',primary_root_cause:'Safety',optimization_directions:['grounded_generation']}},{question_id:'Q2',question:'澄清',failure_tags:['Evidence Pending Review'],primary_root_cause:'Unknown',diagnosis:{status:'needs_review'}},{question_id:'Q3',question:'噪声',failure_tags:['Retrieval Noise'],primary_root_cause:'Generation',diagnosis:{status:'disputed'},diagnostic_view:{is_technical_bad_case:true,analysis_category:'rag_failure',primary_root_cause:'Generation',optimization_directions:['grounded_generation']}}];
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
it('combines three independent dimensions, keeps other issues and unique question counts',()=>{
 expect(filterDiagnosis([...rows,rows[0]],allDiagnosis)).toHaveLength(3);
 expect(filterDiagnosis(rows,{phenomenon:'other',root:'Safety'})).toEqual([rows[0]]);
 expect(filterDiagnosis(rows,{phenomenon:'检索噪声',root:'Generation'})).toEqual([rows[2]]);
 expect(filterDiagnosis(rows,{...allDiagnosis,phenomenon:'安全边界误伤'})).toEqual([]);
 expect(filterDiagnosis(rows,{...allDiagnosis,root:'Unknown'})).toEqual([rows[1]]);
});
it('renders shared classification filters, preserves evidence action and explicit empty state',async()=>{
 const host=document.body.appendChild(document.createElement('div')),root=createRoot(host),select=vi.fn(),change=vi.fn();
 await act(async()=>root.render(<><DiagnosisFilters rows={rows} value={allDiagnosis} onChange={change} /><DiagnosisTable rows={rows} onSelect={select}/></>));
 expect(host.textContent).toContain('2 / 2 题');expect(host.textContent).toContain('安全边界失守');expect(host.textContent).not.toContain('待定位');
 const all=host.querySelector<HTMLButtonElement>('[aria-label="失败现象"] button')!;await act(async()=>all.click());expect(change).toHaveBeenCalledWith({...allDiagnosis,examples:false});expect(host.querySelector('[role=combobox]')).toBeNull();
 await act(async()=>[...host.querySelectorAll('button')].find(b=>b.textContent==='查看案例')!.click());expect(select).toHaveBeenCalledWith(rows[0]);
 await act(async()=>root.render(<DiagnosisTable rows={[]} onSelect={select}/>));expect(host.textContent).toContain('当前组合筛选无记录');await act(async()=>root.unmount());host.remove();
});

it('shows saved per-question repairs and Regression without generating results',async()=>{
 const {CandidateCaseComparison}=await import('./components/CandidateCaseComparison');
 const before={...rows[0],passed:false},after={...rows[0],passed:true};
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify({dataset_version_id:'fixture-golden',judge:{evaluation_identity:'fixture'},cases:[url.endsWith('/baseline')?before:after]}))));
 const host=document.body.appendChild(document.createElement('div')),root=createRoot(host),select=vi.fn();
 const candidate={id:'a',status:'evaluated',reasoning:{candidate_label:'A'},result:{evaluation_run_id:'current',all_fixed_question_ids:['Q1','Q1']}};
 await act(async()=>root.render(<CandidateCaseComparison candidates={[candidate]} baselineId="baseline" kind="fixed" onSelect={select}/>));
 expect(host.querySelector('tbody tr td:nth-child(2)')?.textContent).toBe('未通过');expect(host.querySelector('tbody tr td:nth-child(3)')?.textContent).toBe('通过');expect(host.textContent).toContain('保存为已修复');expect(host.querySelectorAll('tbody tr')).toHaveLength(1);
 await act(async()=>[...host.querySelectorAll('button')].find(b=>b.textContent==='Candidate证据')!.click());expect(select).toHaveBeenCalledWith(after);
 await act(async()=>root.render(<CandidateCaseComparison candidates={[{id:'b',status:'generated',reasoning:{candidate_label:'B'},result:{}}]} baselineId="baseline" kind="regression" onSelect={select}/>));
 expect(host.textContent).toContain('回归对照未判定');expect((fetch as any).mock.calls.every(([,init]:any)=>!init?.method||init.method==='GET')).toBe(true);
 await act(async()=>root.unmount());host.remove();vi.unstubAllGlobals();
});

it('blocks saved comparisons with inconsistent evaluation identities',async()=>{
 const {CandidateCaseComparison}=await import('./components/CandidateCaseComparison');
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify({dataset_version_id:'g',judge:{evaluation_identity:url.endsWith('/baseline')?'old':'new'},cases:[rows[0]]}))));
 const host=document.body.appendChild(document.createElement('div')),root=createRoot(host);
 await act(async()=>root.render(<CandidateCaseComparison candidates={[{id:'a',reasoning:{candidate_label:'A'},result:{evaluation_run_id:'current',all_fixed_question_ids:['Q1']}}]} baselineId="baseline" kind="fixed" onSelect={()=>{}}/>));
 expect(host.textContent).toContain('停止逐题对照');expect(host.querySelector('tbody')).toBeNull();
 await act(async()=>root.unmount());host.remove();vi.unstubAllGlobals();
});

it('uses current analysis root and evidence ahead of historical labels, counts unique questions',async()=>{
 const {DiagnosisDistribution,currentRoot,coreEvidence}=await import('./components/EvaluationDiagnosis');
 const current={question_id:'Q03',primary_root_cause:'Safety',diagnosis:{status:'confirmed',answer_quote:'旧安全证据'},diagnostic_view:{primary_root_cause:'Generation',analysis_category:'rag_failure',analysis_reason:'配置适用范围解释错误',target_eligible:true,is_technical_bad_case:true,optimization_directions:['grounded_generation'],evidence_checks:[{answer_quotes:['实际错误配置说明']}]}};
 const evaluator={question_id:'Q06',primary_root_cause:'Safety',diagnosis:{status:'disputed'},diagnostic_view:{primary_root_cause:'Unknown',analysis_category:'evaluation_issue',analysis_reason:'评测规则错误：原文支持实际操作步骤',target_eligible:false}};
 expect(currentRoot(current)).toBe('Generation');expect(currentRoot(evaluator)).toBe('Unknown');
 expect(coreEvidence(current)).toBe('实际错误配置说明');expect(coreEvidence(evaluator)).toContain('评测规则错误');
 expect(filterDiagnosis([current,evaluator],{phenomenon:'all',root:'Generation'})).toEqual([current]);
 const host=document.body.appendChild(document.createElement('div')),root=createRoot(host);
 await act(async()=>root.render(<><DiagnosisFilters rows={[current,evaluator]} value={allDiagnosis} onChange={()=>{}}/><DiagnosisTable rows={[current,evaluator]} onSelect={()=>{}}/><DiagnosisDistribution rows={[current,current,evaluator]}/></>));
 expect(host.textContent).not.toMatch(/可信度|Confirmed|Needs Review|Disputed|评测争议|已确认/);
 expect([...host.querySelectorAll('thead th')].map(el=>el.textContent)).toEqual(['题号 / 问题','失败现象','主要技术根因','核心证据','详情']);
 await act(async()=>[...host.querySelectorAll('button')].find(b=>b.textContent==='主要根因')!.click());
 expect([...host.querySelectorAll('meter')].map(el=>el.value)).toEqual([1]);
 await act(async()=>root.unmount());host.remove();
});

it('keeps unresolved additions in quality audit even alongside a technical failure',async()=>{
 const {QualityAudit,technicalDiagnosisRows}=await import('./components/EvaluationDiagnosis');
 const technical={...rows[0],passed:false,diagnostic_view:{...rows[0].diagnostic_view,evaluation_quality_audit:{issues:[{type:'claim_verification',evidence:[{reason:'附加配置说明尚未闭合'}]}]}}};
 const audit={question_id:'Q06',question:'手动清洁',passed:false,diagnostic_view:{analysis_category:'evaluation_issue',analysis_reason:'版本元数据断言未闭合',is_technical_bad_case:false,optimization_directions:[]}};
 expect(technicalDiagnosisRows([technical,audit])).toEqual([technical]);
 const host=document.body.appendChild(document.createElement('div')),root=createRoot(host);
 await act(async()=>root.render(<QualityAudit rows={[technical,audit]} onSelect={()=>{}}/>));
 expect(host.textContent).toContain('附加配置说明尚未闭合');expect(host.textContent).toContain('版本元数据断言未闭合');
 await act(async()=>root.unmount());host.remove();
});
