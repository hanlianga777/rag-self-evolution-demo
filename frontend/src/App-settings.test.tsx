// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import App from './App';
import { invalidatePipeline } from './pipelineCache';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(async()=>{await act(async()=>root?.unmount());document.body.innerHTML='';location.hash='';vi.unstubAllGlobals();invalidatePipeline();});
it('loads settings directly with no previous page or evaluation cache',async()=>{
 location.hash='#settings';
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url.includes('/documents')?[]:url.includes('/pipeline')?{search_space:{},config:{}}:{}))));
 root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>{root.render(<App/>);});
 expect(document.querySelector('h1')?.textContent).toBe('Pipeline 配置');
 expect(document.body.textContent).toContain('Agent 可选参数');
});
