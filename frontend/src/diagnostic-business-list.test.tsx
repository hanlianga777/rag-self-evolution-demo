// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {expect,it,vi} from 'vitest';
import {DiagnosisTable,typicalPhenomena} from './components/EvaluationDiagnosis';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
it('keeps scored business FAILs visible despite blocked attribution or toolbox limits',async()=>{
 const rows=[{question_id:'unknown',question:'真实漏答',passed:false,evaluation_outcome:{contract_version:'business-vnext-1',execution_complete:true,verdict:'FAIL'},diagnostic_view:{primary_root_cause:'Unknown',target_eligible:false}},
 {question_id:'limited',question:'已证实排序但无合法干预',passed:false,evaluation_outcome:{contract_version:'business-vnext-1',execution_complete:true,verdict:'FAIL'},diagnostic_view:{primary_root_cause:'Ranking',target_eligible:false,optimization_directions:[]}},
 {question_id:'technical',question:'技术异常不可计业务失败',passed:false,evaluation_outcome:{contract_version:'business-vnext-1',execution_complete:false}},
 {question_id:'pass',question:'通过',passed:true}];
 const host=document.body.appendChild(document.createElement('div')),root=createRoot(host),select=vi.fn();
 await act(async()=>root.render(<DiagnosisTable business rows={rows} onSelect={select} strategy={()=> '等待可验证策略'}/>));
 expect(host.querySelectorAll('tbody tr')).toHaveLength(2);
 expect(host.textContent).toContain('真实漏答');expect(host.textContent).toContain('已证实排序但无合法干预');
 expect(host.textContent).not.toContain('技术异常不可计业务失败');expect(host.querySelector('thead')?.textContent).not.toContain('主要技术根因');
 await act(async()=>host.querySelector('tbody button')!.dispatchEvent(new MouseEvent('click',{bubbles:true})));
 expect(select).toHaveBeenCalledWith(rows[0]);expect(typicalPhenomena).toHaveLength(5);
 await act(async()=>root.unmount());host.remove();
});
