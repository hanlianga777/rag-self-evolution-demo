// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {expect,it,vi} from 'vitest';
import App from './App';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
it('warms Golden and complete Before/After on overview idle time using only GETs, then opens both without waiting for revalidation',async()=>{
 const {invalidateReads}=await import('./api');const {invalidateGolden}=await import('./goldenCache');invalidateReads();invalidateGolden();
 location.hash='#overview';sessionStorage.clear();
 const reads:string[]=[],writes:string[]=[];let block=false;
 const workspace={current_baseline_id:'base',current_golden_id:'golden',current_experiment_id:'exp',current_corpus_fingerprint:'corpus'};
 const candidate={id:'D',status:'evaluated',reasoning:{candidate_label:'D'},result:{evaluation_complete:true,total:1,evaluation_run_id:'after'}};
 const experiment={id:'exp',candidates:[candidate],recommendation:{recommended_candidate:'D'}};
 const question={id:'Q04',question:'保存的问题',test_category:'positive',raw:{},evidence:[]};
 vi.stubGlobal('fetch',vi.fn(async(input:string,init?:RequestInit)=>{
  const url=new URL(input),p=url.pathname;reads.push(p+url.search);if(init?.method && init.method!=='GET')writes.push(p);
  if(block)return new Promise<Response>(()=>{});
  const isBefore=p.includes('/base/');
  const value=p==='/api/workspace'?workspace:p==='/api/documents' || p==='/api/bad-cases'?[]:p==='/api/optimization'?experiment:p==='/api/evaluation'?{id:'base',status:'completed'}:p==='/api/versions'?[]:p.includes('generation-runs')?[{id:'run',status:'completed',profile:{name:'mini',expected_count:1},question_ids:['Q04'],artifacts:{}}]:p.includes('/snapshots')?[{id:'golden',snapshot:{generation_run_id:'run',question_ids:['Q04'],questions:[question]}}]:p.includes('/candidates')?{rows:[question],total:1,candidate_index:[question],data_version:'v1'}:p.endsWith('/comparison-cases')?{id:isBefore?'base':'after',status:'completed',dataset_version_id:'golden',judge:{evaluation_identity:'same'},cases:[{question_id:'Q04',question:'保存的问题',passed:!isBefore}]}:p.includes('/cases/')?{status:'completed',case:{question_id:'Q04',passed:!isBefore,model_answer:'已保存回答'}}:{};
  return new Response(JSON.stringify(value));
 }));
 const node=document.body.appendChild(document.createElement('div')),root=createRoot(node);
 try {
  await act(async()=>root.render(<App/>));
  await act(async()=>new Promise(r=>setTimeout(r,1800)));
  expect(reads).toContain('/api/evaluations/base/cases/Q04');expect(reads).toContain('/api/evaluations/after/cases/Q04');
  expect(reads).toContain('/api/governance/candidates?run_id=run&status=all&group=all&limit=100&offset=0');expect(writes).toEqual([]);
  expect(reads).toContain('/api/optimization?light=true&planning=true');expect(reads).toContain('/api/evaluation');expect(reads).toContain('/api/bad-cases?light=true');
  block=true;
  await act(async()=>node.querySelector<HTMLAnchorElement>('a[href="#evolution"]')!.click());
  expect(node.querySelector('.page-loading')).toBeNull();expect(node.querySelector('.ui-evo')).not.toBeNull();
  for(const [tab,selector] of [['Candidate 对比','.sandbox-core-table'],['回归与推荐','.regression-summary-table']]){
   await act(async()=>[...node.querySelectorAll('button')].find(e=>e.textContent===tab)!.click());expect(node.querySelector(selector)).not.toBeNull();expect(node.querySelector('.page-loading')).toBeNull();
  }
  await act(async()=>node.querySelector<HTMLAnchorElement>('a[href="#governance"]')!.click());
  expect(node.querySelector('.review-table')?.textContent).toContain('保存的问题');expect(node.querySelector('.golden-initial-skeleton')).toBeNull();
  await act(async()=>node.querySelector<HTMLAnchorElement>('a[href="#verification"]')!.click());
  await act(async()=>[...node.querySelectorAll('button')].find(e=>e.textContent==='Before/After')!.click());
  expect(node.querySelector('.comparison-answers')?.textContent).toContain('已保存回答');expect(node.querySelector('.case-detail-skeleton')).toBeNull();
 }finally{act(()=>root.unmount());node.remove();location.hash='';vi.unstubAllGlobals();invalidateReads();invalidateGolden();}
});
it('loads a clicked destination immediately while a background read is pending and stops scheduling after unmount',async()=>{
 const {invalidateReads}=await import('./api');const {invalidateGolden}=await import('./goldenCache');invalidateReads();invalidateGolden();location.hash='#overview';
 let release!:()=>void;const pending=new Promise<void>(resolve=>{release=resolve;});const reads:string[]=[];
 vi.stubGlobal('fetch',vi.fn(async(input:string)=>{
  const path=new URL(input).pathname;reads.push(path);
  if(path==='/api/pipeline')await pending;
  return new Response(JSON.stringify(path==='/api/documents' || path.includes('generation-runs') || path.includes('snapshots')?[]:{}));
 }));
 const node=document.body.appendChild(document.createElement('div')),root=createRoot(node);let mounted=true;
 try {
  await act(async()=>root.render(<App/>));await act(async()=>new Promise(r=>setTimeout(r,100)));
  expect(reads).toContain('/api/pipeline');
  await act(async()=>node.querySelector<HTMLAnchorElement>('a[href="#governance"]')!.click());
  expect(node.querySelector('.page-title h1')?.textContent).toContain('Golden Dataset');expect(node.querySelector('.page-loading')).toBeNull();
  act(()=>root.unmount());mounted=false;const count=reads.length;
  await act(async()=>{release();await new Promise(r=>setTimeout(r,150));});expect(reads).toHaveLength(count);
 }finally{release();if(mounted)act(()=>root.unmount());node.remove();location.hash='';vi.unstubAllGlobals();invalidateReads();invalidateGolden();}
});
