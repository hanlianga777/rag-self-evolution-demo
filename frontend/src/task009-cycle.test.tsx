// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {expect,it,vi} from 'vitest';
import {OperationProvider,useOperation} from './operation';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
it('starts one server batch and polls saved state without starting individual candidates',async()=>{
 const calls:{url:string;method:string}[]=[];let claimed=false;let work:Promise<void>;
 vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
  calls.push({url:new URL(url,'http://localhost').pathname,method:init?.method || 'GET'});
  if(url.endsWith('/run-cycle')) {claimed=true;return new Response(JSON.stringify({status:'running'}));}
  if(url.endsWith('/api/workspace'))return new Response(JSON.stringify({current_baseline_id:'base'}));
  return new Response(JSON.stringify({baseline_run_id:'base',result:claimed?{optimization_cycle:{status:'qualified',used:6,remaining:6}}:{}}));
 }));
 function Harness(){const operation=useOperation();return <button onClick={()=>{work=operation.runCandidateBatch({experimentId:'exp',baselineId:'base',round:1,candidateIds:['A','B','C']});}}>试跑</button>;}
 const root=createRoot(document.body.appendChild(document.createElement('div')));
 try{
  await act(async()=>root.render(<OperationProvider restore={false}><Harness/></OperationProvider>));
  await act(async()=>{document.querySelector<HTMLButtonElement>('button')!.click();await work;});
  expect(calls.filter(c=>c.method==='POST')).toEqual([{url:'/api/experiments/exp/run-cycle',method:'POST'}]);
  expect(document.body.textContent).toContain('6 / 12');
 }finally{act(()=>root.unmount());document.body.innerHTML='';vi.unstubAllGlobals();}
});
