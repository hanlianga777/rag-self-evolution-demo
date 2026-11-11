// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {VerificationPage} from './pages/VerificationPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{if(root)act(()=>root.unmount());document.body.innerHTML='';sessionStorage.clear();vi.unstubAllGlobals();});
it.each([false,true])('shows skeletons during the frozen read and a single quiet fallback only after failure (%s)',async(fail)=>{
 sessionStorage.clear();location.hash='#verification?tab=qa';
 let resolve!:(value:Response)=>void,reject!:(reason:Error)=>void;
 vi.stubGlobal('fetch',vi.fn(()=>new Promise<Response>((yes,no)=>{resolve=yes;reject=no;})));
 root=createRoot(document.body.appendChild(document.createElement('div')));
 const data={workspace:{current_baseline_id:'base',current_golden_id:'golden'},evaluation:{id:'base',status:'completed'}};
 await act(async()=>root.render(<VerificationPage data={data} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>));
 expect(document.querySelectorAll('.chat-example .chat-example-skeleton')).toHaveLength(3);
 expect(document.body.textContent).not.toContain('示例暂时读不到');
 await act(async()=>{if(fail)reject(new Error('读取失败'));else resolve(new Response(JSON.stringify({id:'base',status:'completed',dataset_version_id:'golden',dataset_snapshot:{question_ids:['Q04'],questions:[{id:'Q04',question:'保存的原题',test_category:'positive'}]},cases:[{question_id:'Q04',passed:true,programmatic_metrics:{latency_ms:100}}]})));});
 expect(document.querySelectorAll('.chat-example-skeleton')).toHaveLength(0);
 if(fail)expect(document.querySelector('.chat-examples-unavailable')?.textContent).toBe('示例暂时读不到，可直接输入问题');
 else {expect(document.querySelector('.chat-example')?.textContent).toContain('保存的原题');expect(document.querySelector('.chat-examples-unavailable')).toBeNull();}
 expect([...document.querySelectorAll<HTMLButtonElement>('.chat-example')].filter(b=>!b.disabled)).toHaveLength(fail?0:1);
});
