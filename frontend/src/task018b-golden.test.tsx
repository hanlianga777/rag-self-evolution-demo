// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { FrozenQuestionDetails } from './pages/FrozenQuestionDetails';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
afterEach(() => { document.body.innerHTML = ''; });
it('hides retired scoring points (no 必答/加分/禁止), shows friend question facts, resolves QC citations and hides original IDs from the retired technical details', async () => {
 const row={id:'internal-question',question:'如何维护？',test_category:'positive',reference_answer:'先断电',probe_status:'probe_passed',qc_status:'qc_passed',raw:{business_scenario:'现场维护',generation_method:'跨段综合',test_node:'retrieval',config_param:'top_k',difficulty:'medium',business_requirements:{required_checks:[{requirement:'断开电源'}],auxiliary_information:['擦干表面'],prohibited:['带电清洗']}},evidence_details:[{chunks:[{chunk_id:'DOC-001-C-00180',document_name:'维护手册.pdf',page_start:12,chunk_text:'先断开电源。'}]}],qc:{score:90,reason:'DOC-001-C-00180 支持答案；DOC-999-C-00000 未提供来源信息'},probe:{score:95}};
 const root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<FrozenQuestionDetails row={row}/>));
 expect([...document.querySelectorAll('.drawer-section h3')].map(e=>e.textContent)).toEqual(['业务场景','问题','参考答案','核心证据','题目信息','质检结果']);
 expect(document.querySelector('.golden-question-facts')?.textContent).toContain('跨段综合');
 expect(document.querySelector('.golden-question-facts')?.textContent).toContain('retrieval · top_k');
 expect(document.body.textContent).not.toContain('必答');expect(document.body.textContent).not.toContain('加分');
 expect(document.querySelector('.golden-quality-results')?.textContent).toContain('维护手册 · p12 支持答案');
 expect(document.querySelector('.golden-quality-results')?.textContent).not.toContain('DOC-001');
 expect(document.querySelector('.golden-quality-results')?.textContent).not.toContain('暂无');
 expect(document.querySelector('.golden-quality-results')?.textContent).toContain('原质检引用片段');
 expect(document.querySelector('.disclosure')).toBeNull();
 expect(document.body.textContent).not.toContain('DOC-001-C-00180');
 await act(async()=>root.unmount());
});
it('keeps frozen quality checks read-only and lets unfrozen candidates run them', async()=>{
 const onRun=vi.fn(),root=createRoot(document.body.appendChild(document.createElement('div')));
 const row = {id:'Q-quality',question:'问题',probe_status:'probe_passed'};
 await act(async()=>root.render(<FrozenQuestionDetails row={row} onRun={onRun}/>));
 expect(document.querySelector('.golden-quality-results button')).toBeNull();
 expect(onRun).not.toHaveBeenCalled();
 await act(async()=>root.render(<FrozenQuestionDetails row={row} frozen={false} onRun={onRun}/>));
 for(const label of ['运行检索探针','运行质检']) { await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent===label)!.click());
 await act(async()=>document.querySelector<HTMLButtonElement>('.confirm-dialog .primary')!.click());
 }
 expect(onRun.mock.calls).toEqual([['Q-quality','probe'],['Q-quality','qc']]);
 await act(async()=>root.unmount());
});
it('keeps a Probe execution error separate from a completed question score',async()=>{
 const root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<FrozenQuestionDetails row={{id:'error',question:'问题',probe_status:'needs_revision',probe:{score:0,reason:'检索服务不可用',probe_details:{probe_execution_status:'failed'}}}}/>));
 const probe=document.querySelector('.golden-probe-result')!;
 expect(probe.textContent).toContain('执行失败');
 expect(probe.textContent).not.toContain('检索探针 · 0');
 expect(probe.textContent).not.toContain('未通过');
 await act(async()=>root.unmount());
});

it('hides empty optional cards, groups duplicate evidence and preserves the saved record', async()=>{
 const chunk={document_name:'设备手册.pdf',page_start:12,chunk_text:'先断电'};
 const row={id:'q',question:'怎样维护？',reference_answer:'先断电',raw:{business_scenario:'暂无',business_requirements:{auxiliary_information:[]}},evidence_details:[{chunks:[chunk,{...chunk,chunk_id:'b'},{...chunk,chunk_id:'c'}]}]};
 const saved=JSON.stringify(row),root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<FrozenQuestionDetails row={row}/>));
 expect([...document.querySelectorAll('.drawer-section h3')].map(e=>e.textContent)).toEqual(['问题','参考答案','核心证据','质检结果']);
 expect(document.querySelectorAll('.golden-evidence')).toHaveLength(1);
 expect(document.querySelector('.golden-evidence strong')?.textContent).toBe('设备手册 · p12 · 命中 3 处');
 expect(document.querySelectorAll('.golden-quality-results .ui-clamp').length).toBeGreaterThanOrEqual(3);
 expect(document.querySelector('.golden-quality-results')?.textContent).not.toContain('暂无');
 expect(JSON.stringify(row)).toBe(saved);
 await act(async()=>root.unmount());
});

it("displays cross-topic evidence as auxiliary references in question details", async () => {
 const root = createRoot(document.body.appendChild(document.createElement('div')));
 const row = {question:'同时涉及两章的题',raw:{business_topic:'维修',business_group:'06-01'},evidence_details:[{chunks:[
  {document_name:'手册',business_topic:'维修',page_start:10,chunk_text:'维修主证据'},
  {document_name:'手册',business_topic:'安全',page_start:20,chunk_text:'安全辅助证据'},
 ]}]};
 await act(async()=>root.render(<FrozenQuestionDetails row={row}/>));
 const sections = [...document.querySelectorAll('.drawer-section')];
 const core = sections.find(section => section.querySelector('h3')?.textContent === '核心证据');
 const auxiliary = sections.find(section => section.querySelector('h3')?.textContent === '辅助引用');
 expect(core?.textContent).toContain('维修主证据');
 expect(core?.textContent).not.toContain('安全辅助证据');
 expect(auxiliary?.textContent).toContain('安全辅助证据');
 expect(sections.find(section => section.querySelector('h3')?.textContent === '题目信息')?.textContent).toContain('业务主题：维修');
 await act(async()=>root.unmount());
});
