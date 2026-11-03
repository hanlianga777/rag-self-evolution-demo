// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {expect,it} from 'vitest';
import {ProductDiagnostics} from './components/ProductDiagnostics';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
it('labels the saved comparison with the actual low judge effort',async()=>{
 const host=document.body.appendChild(document.createElement('div'));const root=createRoot(host);
 try{
  await act(async()=>root.render(<ProductDiagnostics diagnostics={{thinking_comparison:{judge_thinking:'low',columns:[{id:'max',label:'最高',metrics:{correct_count:44}},{id:'high',label:'高',current:true,metrics:{correct_count:42}}]}}}/>));
  expect(host.textContent).toContain('同为 low 判分');
 }finally{await act(async()=>root.unmount());host.remove();}
});
