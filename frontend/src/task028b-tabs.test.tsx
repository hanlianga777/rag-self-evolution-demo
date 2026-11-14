// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it} from 'vitest';
import {usePageTab} from './usePageTab';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';sessionStorage.clear();history.replaceState(null,'','/');});
function Probe(){const [tab,setTab]=usePageTab('evaluation',['report','gates','cases'] as const,'report');return <button onClick={()=>setTab('cases')}>{tab}</button>;}
it('opens the first tab on navigation and respects explicit tab links despite a previous stored selection',async()=>{
 sessionStorage.setItem('rag:page-tab:evaluation','gates');history.replaceState(null,'','#evaluation');root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(<Probe/>));
 expect(document.querySelector('button')?.textContent).toBe('report');
 await act(async()=>document.querySelector('button')!.click());expect(location.hash).toBe('#evaluation?tab=cases');
 await act(async()=>{location.hash='knowledge';window.dispatchEvent(new HashChangeEvent('hashchange'));location.hash='evaluation';window.dispatchEvent(new HashChangeEvent('hashchange'));});expect(document.querySelector('button')?.textContent).toBe('report');
 await act(async()=>{location.hash='evaluation?tab=gates';window.dispatchEvent(new HashChangeEvent('hashchange'));});expect(document.querySelector('button')?.textContent).toBe('gates');
});
