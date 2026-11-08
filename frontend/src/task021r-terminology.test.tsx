// @vitest-environment jsdom
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {expect,it} from 'vitest';
import {displayText,baselineName,parameterNames} from './display';
import {schemeName,storyValue} from './components/EvolutionStory';
import {VerificationPage} from './pages/VerificationPage';

it('uses the requested industry labels and real thinking values',()=>{
 expect(displayText('Hard Gate')).toBe('Hard Gate');
 expect(displayText('Candidate')).toBe('Candidate');
 expect(displayText('Regression')).toBe('Regression Check');
 expect(displayText('Positive')).toBe('正向（Positive）');
 expect(parameterNames.candidate_k).toBe('Candidate K');
 expect(parameterNames.top_k).toBe('Top-K');
 expect(storyValue('max')).toBe('Max');
 expect(storyValue('off')).toBe('OFF');
 expect(baselineName({config:{generation_thinking:'high'}})).toContain('High');
 expect(schemeName({reasoning:{round:3,candidate_label:'D'}})).toBe('Round 3 · Candidate D');
});
it('removes technical entry sections from every source page',()=>{
 const sources=import.meta.glob('./{pages,components}/*.tsx',{query:'?raw',import:'default',eager:true});
 for(const [file,text] of Object.entries(sources))expect(text,file).not.toMatch(/<TechnicalDetails\b|label=["']技术详情["']/);
});
it('shows Before/After without the paid comparison entry',()=>{
 const html=renderToStaticMarkup(createElement(VerificationPage,{data:{},onOpenCitation:()=>{},onOpenDocument:()=>{}}));
 expect(html).toContain('Before/After');
 expect(html).not.toContain('自由提问 · 实时调用模型');
});
it('normalizes displayed parameter notation and keeps saved Agent evidence unchanged',async()=>{
 const {DStory}=await import('./components/EvolutionStory');
 const {StrategyPresentation}=await import('./components/ProductDiagnostics');
 const original='方案 D：父段、子段、重排和门槛原文；rerank=query_only，Q24，highest historical prediction.';
 const reasoning={candidate_label:'D',explanation:original,core_idea:original};
 const data={candidates:[{id:'d',status:'evaluated',reasoning,result:{evaluation_complete:true}}]};
 const before=JSON.stringify(data);
 expect(renderToStaticMarkup(createElement(DStory,{experiment:data}))).toContain(original.replace("rerank=query_only", "Rerank query_only"));
 expect(renderToStaticMarkup(createElement(StrategyPresentation,{reasoning}))).toContain(original.replace("rerank=query_only", "Rerank query_only"));
 expect(JSON.stringify(data)).toBe(before);
});
