// @vitest-environment jsdom
import {renderToStaticMarkup} from 'react-dom/server';
import {expect,it} from 'vitest';
import {buildEvolutionModel} from './ui/evolution/model';
import {CompareTable} from './ui/pages3';
import {questionSources} from './pages/FrozenQuestionDetails';
import {StrategyPresentation} from './components/ProductDiagnostics';
const make=(round:number,label:string,result:any={},reasoning:any={})=>({id:`exp-R${round}-${label}`,status:'evaluated',reasoning:{round,candidate_label:label,...reasoning},result:{evaluation_complete:true,total:50,...result}});
const build=(candidates:any[])=>buildEvolutionModel({candidates}, {},x=>x,c=>`Round ${c.reasoning.round} · Candidate ${c.reasoning.candidate_label}`);
it('does not turn a next-round quote or one isolated candidate into a cross-candidate lesson',()=>{
 const quote='历史R1-C组合下曾新增Q15/Q17，需防安全与澄清退化。';
 expect(build([make(1,'C'),make(2,'B',{}, {risks:[{reason:quote}]})]).rounds[0].lesson).toBeUndefined();
 const c=make(3,'C',{all_fixed_question_ids:['Q24','Q29','Q38'],new_regression_question_ids:[],gates:{passed:true,passed_count:11,total:11},qualification:{qualified:true}});
 expect(build([c]).rounds[0].lesson).toBeUndefined();
 expect(build([c]).rounds[0].candidates[0].newFailures).toBe(0);
 expect(build([make(1,'A')]).rounds[0].candidates[0].newFailures).toBeUndefined();
 expect(build([{...c,status:'running'}]).rounds[0].lesson).toBeUndefined();
});
it('retains fractional percentages while using the same count and percentage spelling across comparisons',()=>{
 const model=build([make(1,'A',{gates:{passed:true,passed_count:11,total:11}})]);
 expect(model.rounds[0].candidates[0].gates).toEqual({passed:11,total:11});
 const html=renderToStaticMarkup(<CompareTable columns={[{name:'Baseline'},{name:'D'}]} rows={[{label:'安全拒答率',values:[95.5,100],digits:1,unit:'%'}]}/>);
 expect(html).toContain('95.5%');expect(html).toContain('100%');expect(html).not.toContain('100.0%');
});

it('shows the saved canonical source when a safety question has no ordinary Golden Evidence',()=>{
 expect(questionSources({raw:{business_requirements:{sources:[{document_name:'宇树_B2电池与充电器使用说明_中文版.pdf',page_start:7,page_end:7}]}}})).toBe('B2 电池说明 · p7');
 expect(questionSources({test_category:'positive'})).toBe('保存记录缺少来源');
});

it('reads D saved action, hypothesis, changed parameters and scalar risk instead of empty ABC fields',()=>{
 const html=renderToStaticMarkup(<StrategyPresentation reasoning={{candidate_label:'D',action_name:'D保存的策略',hypothesis:'D保存的思路',changed_parameters:{top_k:6},risk:'D保存的风险'}}/>);
 for(const text of ['D保存的策略','D保存的思路','D保存的风险','参数差异'])expect(html).toContain(text);
 expect(html).not.toContain('尚未保存');
});
