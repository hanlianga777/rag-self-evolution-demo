// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {monitoringHealth} from './components/chatPresentation';
import {AssistantPage} from './pages/AssistantPage';
import {VerificationPage} from './pages/VerificationPage';
import {VersionsPage} from './pages/VersionsPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';sessionStorage.clear();localStorage.clear();vi.unstubAllGlobals();});
it('computes median, citation rate and manual bad cases from server records',()=>{
 expect(monitoringHealth([{metrics:{latency_ms:100},citations:1},{metrics:{latency_ms:900},citations:0,bad_case:true,determinable:true},{metrics:{latency_ms:200},citations:1,bad_case:true}])).toEqual({count:3,median:200,citationRate:2/3,badCases:1});
 expect(monitoringHealth([]).median).toBeNull();
 expect(monitoringHealth([{metrics:{latency_ms:100}},{metrics:{latency_ms:200}}]).median).toBe(150);
});
it('shows Monitoring health, human reason entry and all five feedback stages',async()=>{
 history.replaceState(null,'','#verification?tab=monitoring');vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}')));
 root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<VerificationPage data={{monitoring:{events:[{id:'m',question:'问',answer:'答',metrics:{latency_ms:200},citations:1}]}}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>));
 expect(document.body.textContent).toContain('中位耗时');expect(document.body.textContent).toContain('引用率');
 expect(document.querySelectorAll('.monitoring-feedback-flow li')).toHaveLength(5);
 await act(async()=>[...document.querySelectorAll<HTMLButtonElement>('button')].find(b=>b.textContent==='标注')!.click());
 expect(document.querySelector('textarea[aria-label="标注原因"]')).not.toBeNull();
});
it('streams the online answer before completion and hides thinking after first content',async()=>{
 let controller:ReadableStreamDefaultController<Uint8Array>;
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(new ReadableStream({start(c){controller=c;}}),{headers:{'Content-Type':'text/event-stream'}})));
 root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<AssistantPage examples={[{label:'正常问答',question:'测试'}]} badCases={[]} onOpenBadCase={()=>{}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>));
 expect(document.body.textContent).not.toContain('回答会附出处');
 await act(async()=>document.querySelector<HTMLButtonElement>('.chat-example')!.click());
 expect(document.body.textContent).toContain('思考中');
 await act(async()=>controller!.enqueue(new TextEncoder().encode('data: {"type":"delta","text":"第一字"}\n\n')));
 expect(document.querySelector('.streaming-answer')?.textContent).toContain('第一字');expect(document.querySelector('.thinking-message')).toBeNull();
 await act(async()=>{controller!.enqueue(new TextEncoder().encode('data: {"type":"done","result":{"baseline":{"answer":"第一字完成","evidence":[]},"mode":"live"}}\n\n'));controller!.close();});
 expect(document.querySelector('.model-answer')?.textContent).toContain('第一字完成');
 expect(document.querySelector('.assistant-label')).not.toBeNull();
});
it.each([false,true])('shows online versus Baseline parameter differences in old/new release state (%s)',async(published)=>{
 const candidate={id:'c',reasoning:{candidate_label:'A'},config:{top_k:8},result:{},release_state:{}};
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({checks:[],gates:[]}))));
 root=createRoot(document.body.appendChild(document.createElement('div')));
 await act(async()=>root.render(<VersionsPage data={{evaluation:{config:{top_k:4}},versions:[{id:'v',status:'active',config:{top_k:published?8:4},provenance:published?'published':'bootstrap',snapshot:published?{candidate_id:'c',human_release:{decision:'approved'}}:{}}],optimization:{candidates:[candidate],recommendation:{recommended_candidate:'c'}}}}/>));
 expect(document.querySelector('.ui-rel-changes')?.textContent).toContain(published?'4 → 8':'无差异');
 expect(document.querySelector('.ui-rel-swap dl')).toBeNull();expect(document.querySelectorAll('.release-gate-card')).toHaveLength(3);
});
it('opens an available PDF at the cited page and falls back to saved text for missing PDFs',async()=>{
 const {openCitationPdf}=await import('./components/openCitationPdf');
 const citation={document_id:'doc',document:'显示名',page_start:12,content_preview:'保存原文'} as any;
 const tab={opener:{},location:{href:''},close:vi.fn()};vi.stubGlobal('open',vi.fn());
 const open=vi.spyOn(window,'open').mockReturnValue(tab as any),fallback=vi.fn();
 vi.stubGlobal('fetch',vi.fn(async(_url:string,init?:RequestInit)=>new Response(init?.method==='HEAD'?null:JSON.stringify([{id:'doc',name:'manual.pdf'}]),{status:200})));
 await openCitationPdf(citation,fallback);expect(tab.location.href).toContain('source-pdf?name=manual.pdf#page=12');expect(fallback).not.toHaveBeenCalled();expect(tab.opener).toBeNull();
 vi.stubGlobal('fetch',vi.fn(async(_url:string,init?:RequestInit)=>new Response(init?.method==='HEAD'?null:'[]',{status:init?.method==='HEAD'?404:200})));
 await openCitationPdf(citation,fallback);expect(tab.close).toHaveBeenCalled();expect(fallback).toHaveBeenCalledWith(citation);open.mockRestore();
});
it('handles split SSE frames, reset and transport interruption without inventing a completed answer',async()=>{
 const {streamPreview}=await import('./api');const encoder=new TextEncoder();
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(new ReadableStream({start(c){for(const part of ['data: {"type":"del','ta","text":"旧"}\n\n','data: {"type":"reset"}\n\n','data: {"type":"delta","text":"新"}\n\n'])c.enqueue(encoder.encode(part));c.close();}}))));
 const delta=vi.fn(),reset=vi.fn();await expect(streamPreview('问',delta,reset)).rejects.toThrow('回答中断');expect(delta.mock.calls).toEqual([['旧'],['新']]);expect(reset).toHaveBeenCalledOnce();
});
it('counts citations actually displayed with the saved answer rather than every retrieved document',async()=>{
 const {monitoringCitationCount}=await import('./components/chatPresentation');
 const final=[{document:'manual.pdf',page_start:2,page_end:2,content:'证据'}];
 expect(monitoringCitationCount({answer:'你好，请补充型号。',metrics:{retrieval_trace:{final}}})).toBe(0);
 expect(monitoringCitationCount({answer:'操作步骤。[1]',metrics:{retrieval_trace:{final}}})).toBe(1);
});
