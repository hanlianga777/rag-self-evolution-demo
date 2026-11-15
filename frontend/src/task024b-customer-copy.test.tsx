// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {renderToStaticMarkup} from 'react-dom/server';
import {afterEach,expect,it,vi} from 'vitest';
import {OverviewPage} from './pages/OverviewPage';
import {KnowledgeDiagrams} from './components/KnowledgeDiagrams';
import {Status} from './components/Primitives';
import {agentDisplayText,displayText} from './display';
import {StrategyPresentation} from './components/ProductDiagnostics';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
afterEach(()=>{document.body.innerHTML='';vi.unstubAllGlobals();});
it('keeps the one-line page purpose through architecture tab switches',async()=>{
 vi.stubGlobal('fetch',vi.fn());
 const root=createRoot(document.body.appendChild(document.createElement('div')));
 try{
  await act(async()=>root.render(<OverviewPage data={{}} navigate={()=>{}}/>));
  expect(document.querySelector('.page-title .ui-kicker')?.textContent).toBe('这里用一屏讲清楚整套系统做成了什么：从同一套考卷上的 Baseline 出发，经过 Agent 在规则内的多轮受控试错，最终选出质量更高、速度更快、且没有弄坏任何原本答对题目的配置，并交由人工审批后发布上线。');
  await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='业务架构')!.click());
  expect(document.querySelector('.page-title .ui-kicker')?.textContent).toBe('这里用一屏讲清楚整套系统做成了什么：从同一套考卷上的 Baseline 出发，经过 Agent 在规则内的多轮受控试错，最终选出质量更高、速度更快、且没有弄坏任何原本答对题目的配置，并交由人工审批后发布上线。');
  expect(document.querySelector('.ui-problems')).toBeNull();
  expect(document.querySelector('[role="img"][aria-label^="业务架构"]')).not.toBeNull();
  expect(fetch).not.toHaveBeenCalled();
 }finally{await act(async()=>root.unmount());}
});
it('translates result and runtime codes while retaining professional names',()=>{
 for(const [code,label] of Object.entries({PASS:'通过',FAIL:'未通过',MET:'满足',NOT_MET:'未满足',pending:'等待中',running:'运行中',parsed:'已解析',indexed:'已索引'})){
  expect(displayText(code)).toBe(label);
  expect(renderToStaticMarkup(<Status value={code}/>)).toContain(label);
 }
 for(const word of ['Bad Case','Candidate','Winner','Hard Gate','保留条数','Rerank','P50','P99'])expect(displayText(word)).toBe(word);
});
it('keeps the component architecture views after removing the duplicate knowledge diagram',()=>{
 for(const kind of ['business','technical'] as const){
  const html=renderToStaticMarkup(<KnowledgeDiagrams kind={kind}/>);
  expect(html).toContain(`architecture-${kind}`);expect(html).toContain('<svg');
  expect(html).not.toContain('知识视角：说明书解析');
 }
});

it('normalizes terminology only in the display while keeping saved Agent text intact',()=>{
 const reasoning={core_idea:'方案 D 在赢家基础上修复错题；top_k=6'};
 const saved=JSON.stringify(reasoning);
 const html=renderToStaticMarkup(<StrategyPresentation reasoning={reasoning}/>);
 expect(html).toContain('Candidate D');expect(html).toContain('Winner');expect(html).toContain('Bad Case');
 expect(agentDisplayText(reasoning.core_idea)).not.toMatch(/方案|赢家|错题|top_k/);
 expect(JSON.stringify(reasoning)).toBe(saved);
});
