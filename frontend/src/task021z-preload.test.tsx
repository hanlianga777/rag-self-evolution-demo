// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { GovernancePage } from './pages/GovernancePage';
import { invalidateGolden } from './goldenCache';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';sessionStorage.clear();invalidateGolden();vi.unstubAllGlobals();});

it('preloads every Golden row and the pool; filters and tabs reuse memory with matching counts',async()=>{
 const rows=Array.from({length:50},(_,i)=>({id:`Q${i}`,slot:`Q${i}`,question:`保存的问题${i}`,test_category:i<20?'positive':i<40?'ablation':'negative',qualification_status:i<35?'machine_qualified':'needs_human_review',probe_status:'probe_passed',qc_status:'qc_passed',raw:{}}));
 const fetcher=vi.fn(async(input:string)=>{
  const url=new URL(input),offset=Number(url.searchParams.get('offset')),limit=Number(url.searchParams.get('limit') || 30);
  return new Response(JSON.stringify(url.pathname.endsWith('candidates')?{rows:rows.slice(offset,offset+limit),candidate_index:rows,total:50,data_version:'v1'}:url.pathname.includes('/questions/')?rows.find(r=>url.pathname.endsWith('/'+r.id)):[]));
 });vi.stubGlobal('fetch',fetcher);
 root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<GovernancePage data={{workspace:{current_corpus_fingerprint:'fixture'},generationRuns:[{id:'G',status:'completed',profile:{expected_count:50},question_ids:rows.map(r=>r.id),artifacts:{}}],dataset:rows}}/>));
 expect(document.querySelectorAll('.review-table tbody tr')).toHaveLength(50);
 await act(async()=>{await new Promise(resolve=>setTimeout(resolve,200));});
 const count=fetcher.mock.calls.length;
 for(const label of ['正向','消融','负向','机器合格','全部']){
  const button=[...document.querySelectorAll<HTMLButtonElement>('.review-filters button')].find(b=>b.textContent?.startsWith(label))!;
  await act(async()=>button.click());
  expect(document.querySelectorAll('.review-table tbody tr')).toHaveLength(Number(button.textContent?.match(/(\d+)$/)?.[1]));
  expect(document.querySelector('.golden-skeleton,.list-loading')).toBeNull();
 }
 await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('.tabs button')].find(b=>b.textContent==='候选池')!.click());
 for(const label of ['可用','待治理','全部']){
  const button=[...document.querySelectorAll<HTMLButtonElement>('[aria-label="候选质量筛选"] button')].find(b=>b.textContent?.startsWith(label))!;
  await act(async()=>button.click());
  expect(document.querySelectorAll('.candidate-pool-table tbody tr')).toHaveLength(Number(button.textContent?.match(/(\d+)$/)?.[1]));
 }
 expect(fetcher).toHaveBeenCalledTimes(count);
});

it('waits 150ms before hover prefetch and cancels a brief pass over a row',async()=>{
 const {QuestionTable}=await import('./pages/GovernancePage');
 const fetcher=vi.fn(async()=>new Response('{"id":"Q1"}'));vi.stubGlobal('fetch',fetcher);
 vi.useFakeTimers();
 try {
  root=createRoot(document.body.appendChild(document.createElement('div')));
  await act(async()=>root.render(<QuestionTable rows={[{id:'Q1',question:'保存的问题'}]} onDetail={()=>{}}/>));
  const row=document.querySelector('tbody tr')!;
  await act(async()=>{row.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));await vi.advanceTimersByTimeAsync(149);});expect(fetcher).not.toHaveBeenCalled();
  await act(async()=>{row.dispatchEvent(new MouseEvent('mouseout',{bubbles:true}));await vi.advanceTimersByTimeAsync(100);});expect(fetcher).not.toHaveBeenCalled();
  await act(async()=>{row.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));await vi.advanceTimersByTimeAsync(150);});expect(fetcher).toHaveBeenCalledTimes(1);
 } finally {vi.useRealTimers();}
});

it('preloads more than 200 rows, restarts changed versions, and scrolls only in memory',async()=>{
 const {usePagedCandidates}=await import('./components/ScrollablePagedTable');
 let revision=1;
 const fetcher=vi.fn(async(input:string)=>{
  const p=new URL(input).searchParams,offset=Number(p.get('offset'));
  if(offset===100 && revision===1) revision=2;
  return new Response(JSON.stringify({rows:Array.from({length:Math.min(100,205-offset)},(_,i)=>({id:`v${revision}-${i+offset}`})),total:205,data_version:`v${revision}`}));
 });vi.stubGlobal('fetch',fetcher);
 function List(){const list=usePagedCandidates('big','/api/governance/candidates?status=all');return <><p>{list.rows.length} saved</p><button onClick={list.loadMore}>more</button><ul>{list.rows.slice(0,list.visibleCount).map((r:any)=><li key={r.id}>{r.id}</li>)}</ul></>}
 root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<List/>));
 expect(document.querySelector('p')?.textContent).toBe('205 saved');expect(document.querySelectorAll('li')).toHaveLength(200);expect(document.body.textContent).not.toContain('v1-');
 const count=fetcher.mock.calls.length;await act(async()=>document.querySelector('button')!.click());expect(document.querySelectorAll('li')).toHaveLength(205);expect(fetcher).toHaveBeenCalledTimes(count);
});

it('keeps a complete cached list visible during reentry and replaces it only on a new data_version',async()=>{
 const {usePagedCandidates}=await import('./components/ScrollablePagedTable');
 let payload={rows:[{id:'saved'}],total:1,data_version:'v1'},hold=false,release!:()=>void;
 vi.stubGlobal('fetch',vi.fn(async()=>{if(hold)await new Promise<void>(resolve=>{release=resolve;});return new Response(JSON.stringify(payload));}));
 function List(){const list=usePagedCandidates('retained','/api/governance/candidates?status=all');return <p>{list.loading?'loading':list.rows.map((r:any)=>r.id).join(',')}</p>}
 const node=document.body.appendChild(document.createElement('div'));root=createRoot(node);await act(async()=>root.render(<List/>));act(()=>root.unmount());
 hold=true;root=createRoot(node);await act(async()=>root.render(<List/>));expect(node.textContent).toBe('saved');
 payload={...payload,rows:[{id:'ignored-same-version'}]};hold=false;await act(async()=>release());expect(node.textContent).toBe('saved');
 act(()=>root.unmount());payload={...payload,rows:[{id:'new-version'}],data_version:'v2'};root=createRoot(node);await act(async()=>root.render(<List/>));expect(node.textContent).toBe('new-version');
});

it('paginates more than 200 version and feedback records locally after all backend pages load',async()=>{
 const {loadAppData}=await import('./api');const {VersionsPage}=await import('./pages/VersionsPage');const {VerificationPage}=await import('./pages/VerificationPage');
 const versions=Array.from({length:205},(_,i)=>({id:`V${i}`,status:i===0?'active':'archived',config:{}}));
 const events=Array.from({length:205},(_,i)=>({id:`E${i}`,question:`反馈${i}`}));
 const fetcher=vi.fn(async(input:string)=>{const url=new URL(input),page=Number(url.searchParams.get('page') || 1),slice=(rows:any[])=>rows.slice((page-1)*50,page*50);return new Response(JSON.stringify(url.pathname==='/api/versions'?slice(versions):url.pathname==='/api/monitoring'?{events:slice(events),triggers:[]}:url.pathname==='/api/documents'?[]:{}));});vi.stubGlobal('fetch',fetcher);
 const release=await loadAppData(true,'versions'),feedback=await loadAppData(true,'verification');
 expect(release.versions).toHaveLength(205);expect((feedback.monitoring as any).events).toHaveLength(205);
 const count=fetcher.mock.calls.length;
 root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<VersionsPage data={release}/>));expect(document.querySelectorAll('tbody tr')).toHaveLength(3);await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='查看全部 200 条记录')!.click());expect(document.querySelectorAll('tbody tr')).toHaveLength(200);
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='下一页')!.click());expect(document.querySelectorAll('tbody tr')).toHaveLength(5);
 await act(async()=>root.render(<VerificationPage data={feedback} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>));await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='线上反馈 → 再次进化')!.click());expect(document.querySelectorAll('.monitoring-table tbody tr')).toHaveLength(200);
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='下一页')!.click());expect(document.querySelectorAll('.monitoring-table tbody tr')).toHaveLength(5);expect(fetcher).toHaveBeenCalledTimes(count);
});

it('keeps open page details on an unchanged read version and replaces them after a new version',async()=>{
 const {default:App}=await import('./App');
 location.hash='versions';let version='v1';
 const fetcher=vi.fn(async(input:string)=>new Response(JSON.stringify(new URL(input).pathname==='/api/versions'?[{id:version,status:'active',provenance:'bootstrap',config:{top_k:version==='v1'?4:6}}]:new URL(input).pathname==='/api/documents'?[]:{}),{headers:{'X-Read-Version':version}}));vi.stubGlobal('fetch',fetcher);
 try {
  root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<App/>));
  await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='查看完整配置')!.click());expect(document.querySelector('[role=dialog]')).not.toBeNull();
  await act(async()=>window.dispatchEvent(new Event('focus')));expect(document.querySelector('[role=dialog]')).not.toBeNull();
  version='v2';await act(async()=>window.dispatchEvent(new Event('focus')));expect(document.querySelector('[role=dialog]')).toBeNull();
 } finally {location.hash='';}
});

it('refreshes feedback when a new answer is saved, so opening its tab stays local',async()=>{
 const {VerificationPage}=await import('./pages/VerificationPage');location.hash='#verification?tab=qa';let answered=false;
 const fetcher=vi.fn(async(input:string)=>new Response(JSON.stringify(input.endsWith('/api/preview')?(answered=true,{baseline:{answer:'合成回答，未调用模型',sources:[]}}):{events:answered?[{id:'new',question:'新保存的合成问答'}]:[],triggers:[]})));vi.stubGlobal('fetch',fetcher);
 root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<VerificationPage data={{monitoring:{events:[],triggers:[]}}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>));
 const input=document.querySelector<HTMLInputElement>('[aria-label="向机器人知识库提问"]')!;
 await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input,'新保存的合成问答');input.dispatchEvent(new Event('input',{bubbles:true}));});
 await act(async()=>document.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
 const count=fetcher.mock.calls.length;
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='线上反馈 → 再次进化')!.click());
 expect(document.querySelector('.monitoring-table')?.textContent).toContain('新保存的合成问答');expect(fetcher).toHaveBeenCalledTimes(count);
});

it('refreshes the resident candidate pool after a saved quality change before switching tabs',async()=>{
 let checked=false;
 const row=()=>({id:'Q1',slot:'Q01',question:'质量状态需要更新',test_category:'positive',stage:'candidate',evidence:[],raw:{},probe_status:'probe_passed',qc_status:checked?'qc_passed':'qc_pending',qualification_status:checked?'machine_qualified':'needs_human_review',qc:checked?{score:99}:undefined});
 const run={id:'run-mutation',status:'completed',profile:{expected_count:1},question_ids:['Q1'],artifacts:{}};
 const fetcher=vi.fn(async(input:string,init?:RequestInit)=>{
  if(init?.method==='POST'){checked=true;return new Response('{}');}
  return new Response(JSON.stringify(input.includes('/candidates?')?{rows:[row()],total:1,candidate_index:[row()],data_version:String(checked)}:input.includes('/questions/')?row():input.includes('generation-runs?')?[run]:[]));
 });vi.stubGlobal('fetch',fetcher);
 root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<GovernancePage data={{generationRuns:[run],dataset:[row()]}}/>));
 await act(async()=>document.querySelector<HTMLElement>('.review-table tbody tr')!.click());
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='运行 QC')!.click());
 await act(async()=>document.querySelector<HTMLButtonElement>('.confirm-dialog .primary')!.click());
 await act(async()=>document.querySelector<HTMLButtonElement>('.candidate-workspace [aria-label="关闭"]')!.click());
 const count=fetcher.mock.calls.length;
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='候选池')!.click());
 expect(document.querySelector('[aria-label="候选质量筛选"]')?.textContent).toContain('可用 1');expect(fetcher).toHaveBeenCalledTimes(count);
});

it('keeps the complete comparison list when one prefetched case fails and retries only on request',async()=>{
 const {SavedAnswerComparison}=await import('./components/SavedAnswerComparison');let fail=true;
 const fetcher=vi.fn(async(input:string)=>{
  const base=input.includes('/base/'),rows=[{question_id:'Q1',question:'正常题目',passed:!base},{question_id:'Q2',question:'需要重试的题目',passed:false}];
  if(input.endsWith('/comparison-cases'))return new Response(JSON.stringify({id:base?'base':'after',status:'completed',dataset_version_id:'golden',judge:{evaluation_identity:'same'},cases:rows}));
  if(input.endsWith('/Q2')&&fail)return new Response('{"detail":"单题读取失败"}',{status:503});
  return new Response(JSON.stringify({status:'completed',case:{...rows[input.endsWith('/Q2')?1:0],model_answer:'保存的回答'}}));
 });vi.stubGlobal('fetch',fetcher);
 root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<SavedAnswerComparison data={{evaluation:{id:'base'},optimization:{recommendation:{recommended_candidate:'D'},candidates:[{id:'D',status:'evaluated',result:{evaluation_run_id:'after',total:2,evaluation_complete:true}}]}}} onOpenCitation={()=>{}}/>));
 expect(document.querySelectorAll('.comparison-qlist li')).toHaveLength(1);
 const count=fetcher.mock.calls.length;await act(async()=>document.querySelectorAll<HTMLButtonElement>('.comparison-seg button')[1].click());expect(document.querySelector('.comparison-qlist')?.textContent).toContain('需要重试的题目');expect(document.querySelector('[role=alert]')?.textContent).toContain('单题读取失败');expect(fetcher).toHaveBeenCalledTimes(count);expect(document.querySelector('.case-detail-skeleton')).toBeNull();
 fail=false;await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='重试本题')!.click());expect(document.querySelector('[role=alert]')).toBeNull();expect(document.querySelector('.comparison-answers')?.textContent).toContain('保存的回答');
});

it('paginates a knowledge document list over 200 locally and resets its page on search',async()=>{
 const {KnowledgePage}=await import('./pages/KnowledgePage');vi.stubGlobal('fetch',vi.fn(async()=>new Response('{"knowledge":{},"index":{}}')));
 const documents=Array.from({length:205},(_,i)=>({id:`doc-${i}`,name:`文档-${i}.pdf`,status:"Indexed"}));
 root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<KnowledgePage data={{documents}}/>));expect(document.querySelectorAll('tbody tr')).toHaveLength(200);
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='下一页')!.click());expect(document.querySelectorAll('tbody tr')).toHaveLength(5);
 const input=document.querySelector<HTMLInputElement>('[aria-label="搜索文档"]')!;await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input,'文档-0.');input.dispatchEvent(new Event('input',{bubbles:true}));});expect(document.querySelectorAll('tbody tr')).toHaveLength(1);expect(document.querySelector('tbody')?.textContent).toContain('文档-0.pdf');
});

it('paginates the preloaded Before/After rail locally beyond 200 questions',async()=>{
 const {SavedAnswerComparison}=await import('./components/SavedAnswerComparison');
 const rows=Array.from({length:205},(_,i)=>({question_id:`Q${i}`,question:`保存的问题${i}`,test_category:'positive'}));
 const fetcher=vi.fn(async(input:string)=>{const base=input.includes('/base/');return new Response(JSON.stringify(input.endsWith('/comparison-cases')?{id:base?'base':'after',status:'completed',dataset_version_id:'golden',judge:{evaluation_identity:'same'},cases:rows.map(row=>({...row,passed:!base}))}:{status:'completed',case:{...rows.find(row=>input.endsWith('/'+row.question_id)),passed:!base,model_answer:'保存的回答'}}));});vi.stubGlobal('fetch',fetcher);
 root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<SavedAnswerComparison data={{evaluation:{id:'base'},optimization:{recommendation:{recommended_candidate:'D'},candidates:[{id:'D',status:'evaluated',result:{evaluation_run_id:'after',total:205,evaluation_complete:true}}]}}} onOpenCitation={()=>{}}/>));
 expect(document.querySelectorAll('.comparison-qlist li')).toHaveLength(200);const count=fetcher.mock.calls.length;
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='下一页')!.click());expect(document.querySelectorAll('.comparison-qlist li')).toHaveLength(5);expect(document.querySelector('.comparison-qhead')?.textContent).toContain('保存的问题200');expect(fetcher).toHaveBeenCalledTimes(count);
 await act(async()=>root.render(<SavedAnswerComparison questionId="Q201" data={{evaluation:{id:'base'},optimization:{recommendation:{recommended_candidate:'D'},candidates:[{id:'D',status:'evaluated',result:{evaluation_run_id:'after',total:205,evaluation_complete:true}}]}}} onOpenCitation={()=>{}}/>));expect(document.querySelectorAll('.comparison-qlist li')).toHaveLength(5);expect(document.querySelector('.comparison-qhead')?.textContent).toContain('保存的问题201');expect(fetcher).toHaveBeenCalledTimes(count);
});

it('paginates regression cases locally and resets the page when severity changes',async()=>{
 const {CandidateCaseComparison}=await import('./components/CandidateCaseComparison');
 const rows=Array.from({length:205},(_,i)=>({question_id:`Q${i}`,question:`Regression问题${i}`,severity:'ordinary',passed:false}));
 const fetcher=vi.fn(async()=>new Response(JSON.stringify({status:'completed',judge:{evaluation_identity:'same'},dataset_version_id:'golden',cases:rows})));vi.stubGlobal('fetch',fetcher);
 root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<CandidateCaseComparison baselineId="base" candidates={[{id:'C',status:'evaluated',result:{evaluation_run_id:'after',new_regression_question_ids:rows.map(row=>row.question_id),regression_review:{case_severities:Object.fromEntries(rows.map(row=>[row.question_id,'ordinary']))}}}]} kind="regression" onSelect={()=>{}}/>));
 expect(document.querySelectorAll('tbody tr')).toHaveLength(200);const count=fetcher.mock.calls.length;
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='下一页')!.click());expect(document.querySelectorAll('tbody tr')).toHaveLength(5);
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='普通')!.click());expect(document.querySelectorAll('tbody tr')).toHaveLength(200);expect(fetcher).toHaveBeenCalledTimes(count);
});
