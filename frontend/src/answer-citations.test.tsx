// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it } from 'vitest';
import { answerCitationDisplay } from './answerCitations';
import { CaseAnswer } from './components/CaseAnswer';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
afterEach(() => { if (root) act(() => root.unmount()); document.body.innerHTML=''; });
const final=[{chunk_id:'DOC-001-C-00185',parent_chunk_id:'DOC-001-P-00185',matched_child_ids:['DOC-001-C-00186'],document:'设备手册.pdf',page_start:86,page_end:87}];
it('maps only saved Final citation IDs to their actual document location without mutating evidence or answer',()=>{
 const raw='不得继续使用。 [DOC-001-C-00185 | S3 | 页86]';const before=JSON.stringify(final);
 expect(answerCitationDisplay(raw,final)).toEqual({text:'不得继续使用。 [设备手册.pdf · 第86—87页]',unverified:0,changed:true});
 expect(answerCitationDisplay('【DOC-001-P-00185】和【DOC-001-C-00186】',final).text).not.toContain('DOC-');
 expect(raw).toContain('DOC-001');expect(JSON.stringify(final)).toBe(before);
});
it('missing, ambiguous and non-Final citations stay visibly unverified instead of borrowing Golden or changing a claim',()=>{
 const raw='可以带电拆装 [DOC-004-C-00099]';
 expect(answerCitationDisplay(raw,final)).toEqual({text:'可以带电拆装 [引用来源未核验]',unverified:1,changed:true});
 const ambiguous=[...final,{...final[0],document:'不同手册.pdf'}];
 expect(answerCitationDisplay('[DOC-001-C-00185]',ambiguous).unverified).toBe(1);
 expect(answerCitationDisplay('[DOC-001-C-00185]',[]).unverified).toBe(1);
});
it('leaves natural source labels, numeric units and ordinary prose intact',()=>{
 const raw='长按2秒及以上，66 cm。[设备手册 · 第86页] 文中DOC-001-C-00185是索引说明。';
 expect(answerCitationDisplay(raw,final)).toEqual({text:raw,unverified:0,changed:false});
});
it('shows a human source in the answer and preserves exact original in closed audit',()=>{
 const raw='关闭设备 [DOC-001-C-00185]';root=createRoot(document.body.appendChild(document.createElement('div')));
 act(()=>root.render(<CaseAnswer text={raw} final={final}/>));
 expect(document.querySelector('.case-answer')?.textContent).toContain('设备手册.pdf');
 expect(document.querySelector('.case-answer')?.textContent).not.toContain('DOC-001');
 const audit=document.querySelector('details')!;expect(audit.open).toBe(false);expect(audit.textContent).toContain(raw);
});

it('keeps saved Parent page ranges distinct from Child location',()=>{
 const sources=[{...final[0],parent_page_start:80,parent_page_end:90}];
 expect(answerCitationDisplay('[DOC-001-C-00185]',sources).text).toContain('第86—87页');
 expect(answerCitationDisplay('[DOC-001-P-00185]',sources).text).toContain('第80—90页');
});
it('refreshes an open light-list drawer with the saved full case when it arrives',async()=>{
 const {vi}=await import('vitest');const {EvaluationPage}=await import('./pages/EvaluationPage');
 const item={question_id:'Q04',question:'停用注意什么？',test_category:'positive',passed:false,model_answer:'关闭设备 [DOC-001-C-00185]',judge_result:{reason:'原记录'}};
 const run={id:'E1',status:'completed',dataset_snapshot:{question_ids:['Q04']},result:{gates:{gates:[]}}};
 let complete!: (value:Response)=>void;const response=new Promise<Response>(resolve=>{complete=resolve});
 vi.stubGlobal('fetch',vi.fn(async(input:RequestInfo|URL)=>String(input).endsWith('/api/evaluations/E1')?response:new Response(JSON.stringify(String(input).includes('/preflight')?{can_start:false}:run))));
 root=createRoot(document.body.appendChild(document.createElement('div')));
 try {
  await act(async()=>root.render(<EvaluationPage data={{evaluation:run,badCases:[{id:'BC1',run_id:'E1',question_id:'Q04',result:item}]}}/>));
  await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='Bad Case 诊断')!.click());
  await act(async()=>document.querySelector<HTMLElement>('.product-diagnosis-table tbody tr')!.click());
  await act(async()=>{complete(new Response(JSON.stringify({...run,cases:[{...item,programmatic_metrics:{retrieval_trace:{final}}}]})));await response;});
  const displayed=document.querySelector('.case-answer-stack > div:nth-child(2) .case-answer');
  expect(displayed?.textContent).toContain('设备手册.pdf');expect(displayed?.textContent).not.toContain('引用来源未核验');
 } finally {vi.unstubAllGlobals();}
});
