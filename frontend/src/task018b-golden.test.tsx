// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { FrozenQuestionDetails } from './pages/FrozenQuestionDetails';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { document.body.innerHTML = ''; });
it('groups saved scoring points, resolves QC citations and keeps original IDs in technical details', async () => {
 const row={id:'internal-question',question:'如何维护？',test_category:'positive',reference_answer:'先断电',probe_status:'probe_passed',qc_status:'qc_passed',raw:{business_scenario:'现场维护',business_requirements:{required_checks:[{requirement:'断开电源'}],auxiliary_information:['擦干表面'],prohibited:['带电清洗']}},evidence_details:[{chunks:[{chunk_id:'DOC-001-C-00180',document_name:'维护手册.pdf',page_start:12,chunk_text:'先断开电源。'}]}],qc:{score:90,reason:'DOC-001-C-00180 支持答案'},probe:{score:95}};
 const root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<FrozenQuestionDetails row={row}/>));
 expect([...document.querySelectorAll('.drawer-section h3')].map(e=>e.textContent)).toEqual(['业务场景','问题','参考答案','核心证据','评分要点','质检结果']);
 expect(document.querySelector('.golden-scoring-points')?.textContent).toContain('必答断开电源');
 expect(document.querySelector('.golden-scoring-points')?.textContent).toContain('加分擦干表面');
 expect(document.querySelector('.golden-scoring-points')?.textContent).toContain('禁止带电清洗');
 expect(document.querySelector('.golden-quality-results')?.textContent).toContain('维护手册.pdf · 第 12 页 支持答案');
 expect(document.querySelector('.golden-quality-results')?.textContent).not.toContain('DOC-001');
 expect(document.querySelector('.disclosure')?.textContent).toContain('DOC-001-C-00180');
 await act(async()=>root.unmount());
});
it('runs the selected quality check through the existing callback without enabling frozen edits', async()=>{
 const onRun=vi.fn(),root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<FrozenQuestionDetails row={{id:'Q-frozen',question:'问题',probe_status:'probe_passed'}} onRun={onRun}/>));
 for(const label of ['运行 Probe','运行 QC']) await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent===label)!.click());
 expect(onRun.mock.calls).toEqual([['Q-frozen','probe'],['Q-frozen','qc']]);
 await act(async()=>root.unmount());
});
it('keeps a Probe execution error separate from a completed question score',async()=>{
 const root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<FrozenQuestionDetails row={{id:'error',question:'问题',probe_status:'needs_revision',probe:{score:0,reason:'检索服务不可用',probe_details:{probe_execution_status:'failed'}}}}/>));
 const probe=document.querySelector('.golden-probe-result')!;
 expect(probe.textContent).toContain('执行失败');
 expect(probe.textContent).not.toContain('Probe · 0');
 expect(probe.textContent).not.toContain('未通过');
 await act(async()=>root.unmount());
});
