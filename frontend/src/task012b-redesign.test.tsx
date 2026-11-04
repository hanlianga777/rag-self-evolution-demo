// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it} from 'vitest';
import {BadCaseOverview,ProductDiagnostics} from './components/ProductDiagnostics';
import {VerificationPage} from './pages/VerificationPage';
import {BaselineCaseDetails,EvaluationPage} from './pages/EvaluationPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';});
const mount=async(node:React.ReactNode)=>{root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));};
const click=async(text:string)=>act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent===text)!.click());
it('opens a case by keyboard and disables zero categories without losing review status',async()=>{
 const row={question_id:'Q04',passed:false,question:'存放设备',baseline_review_label:'真错（3 次错 3 次）',diagnostic_view:{diagnosis_category:'检索噪声'}};let selected:any;
 await mount(<BadCaseOverview rows={[row]} categories={[{label:'检索噪声'},{label:'安全边界'}]} onSelect={value=>selected=value}/>);
 const zero=[...document.querySelectorAll('button')].find(b=>b.textContent==='安全边界0')!;expect(zero.disabled).toBe(true);
 const tr=document.querySelector('.diagnosis-list tbody tr')!;await act(async()=>tr.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})));expect(selected).toBe(row);
 expect(document.querySelector('.diagnosis-list thead')?.textContent).toContain('判定方式');expect(document.body.textContent).not.toContain('展开细项');
});
it('derives comparison differences and defaults to changed gates',async()=>{
 const columns=[{id:'max',label:'最高',metrics:{correct_count:45,latency_p50_seconds:15,average_estimated_cost:{amount:0.002,currency:'USD'}},gates:[{metric:'safe_rejection_rate',actual:100,threshold:95,status:'PASS'},{metric:'positive_correctness',actual:95,status:'PASS'}]},{id:'high',label:'高',current:true,metrics:{correct_count:43,latency_p50_seconds:5,average_estimated_cost:{amount:0.001,currency:'USD'}},gates:[{metric:'safe_rejection_rate',actual:90,threshold:95,status:'FAIL'},{metric:'positive_correctness',actual:95,status:'PASS'}]}];
 await mount(<ProductDiagnostics diagnostics={{thinking_comparison:{columns}}}/>);await click('查看对照');
 expect(document.body.textContent).toContain('最高档多答对 2 题');expect(document.body.textContent).toContain('高档快约 3.0 倍');expect(document.body.textContent).toContain('50.0%');
 expect(document.querySelector('.thinking-gates tbody')?.textContent).not.toContain('正向题正确性');await click('显示全部 2 项');expect(document.querySelector('.thinking-gates tbody')?.textContent).toContain('正向题正确性');
});
it('resolves frozen evidence through saved candidate chunks and marks final evidence',async()=>{
 const item={question_id:'Q04',test_category:'positive',passed:false,question:'存放设备',diagnostic_view:{missing_points:['室内'],retrieval_positions:[{evidence_index:1,candidate_rank:10,rerank_rank:5,final_rank:null}]},programmatic_metrics:{retrieval_trace:{candidates:[{chunk_id:'c1',document:'KIRA 手册',page_start:85}],final:[{matched_child_ids:['c2'],document:'KIRA 手册',page_start:86,content:'充电'}]}}};
 await mount(<BaselineCaseDetails item={item} snapshot={{questions:[{id:'Q04',evidence:[{source_chunk_ids:['c1'],evidence_key_points:['室内']},{source_chunk_ids:['c2']}]}]}} config={{}} gates={[]}/>);
 expect(document.body.textContent).toContain('KIRA 手册 · 第85页');expect(document.body.textContent).not.toContain('来源文档名称未记录');expect(document.body.textContent).toContain('未进最终 1 段');
 expect(document.body.textContent).toContain('含标准证据');expect(document.querySelectorAll('.bad-case-details > details')).toHaveLength(1);expect(document.querySelector('.case-answer-stack')?.children).toHaveLength(2);
});

it('opens real monitoring source objects without rendering them as React children',async()=>{
 const {vi}=await import('vitest');vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({events:[{id:'event',question:'历史问答',source:{corpus_fingerprint:{'DOC-001':'saved-hash'}}}]}))));
 try {await mount(<VerificationPage data={{monitoring:{events:[{id:'event',question:'历史问答',source:{corpus_fingerprint:{'DOC-001':'saved-hash'}}}]}}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>);await click('监控');await click('历史问答');expect(document.querySelector('[role="dialog"]')?.textContent).toContain('saved-hash');}finally{vi.unstubAllGlobals();}
});

it('waits for saved case details instead of reporting missing sources from a light response',async()=>{
 const {vi}=await import('vitest');let resolveDetails!:(value:Response)=>void;
 const row={question_id:'Q04',question:'存放设备',passed:false,diagnostic_view:{diagnosis_category:'检索噪声'}};
 const run={id:'saved',status:'completed',dataset_snapshot:{questions:[{id:'Q04',evidence:[{source_chunk_ids:['c1']}]}]},result:{bad_case_count:1}};
 const details=new Promise<Response>(resolve=>{resolveDetails=resolve;});
 vi.stubGlobal('fetch',vi.fn((url:string)=>url.endsWith('/api/evaluations/saved')?details:Promise.resolve(new Response(JSON.stringify(url.includes('preflight')?{can_start:false}:run)))));
 try {
  await mount(<EvaluationPage data={{evaluation:run,badCases:[{run_id:'saved',question_id:'Q04',result:row}]}}/>);await click('Bad Case 诊断');
  await act(async()=>document.querySelector<HTMLTableRowElement>('.diagnosis-list tbody tr')!.click());
  const dialog=document.querySelector('[role="dialog"]')!;
  expect(dialog.querySelector('[role="status"]')?.getAttribute('aria-label')).toBe('正在读取保存的案例详情');
  expect(dialog.textContent).not.toContain('来源位置未记录');
  await act(async()=>resolveDetails(new Response(JSON.stringify({...run,cases:[{...row,programmatic_metrics:{retrieval_trace:{candidates:[{chunk_id:'c1',document:'KIRA 手册',page_start:85}]}}}]}))));
  expect(dialog.textContent).toContain('KIRA 手册 · 第85页');expect(dialog.querySelector('[role="status"]')).toBeNull();
 }finally{vi.unstubAllGlobals();}
});
