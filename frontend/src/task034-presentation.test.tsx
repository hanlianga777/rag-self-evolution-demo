// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {CaseAnswer} from './components/CaseAnswer';
import {RoundStrategy,RoundConclusion} from './components/RoundStrategy';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
async function render(node:any){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();sessionStorage.clear();history.replaceState(null,'','/');});
it('uses source footnotes without raw audit copies and keeps model wording',async()=>{
 const text='1. 第一步原话。\n2. 第二步原话。（来源：《操作手册》，第 3 页）';
 await render(<CaseAnswer text={text} final={[{document:'操作手册',document_id:'doc',page_start:3,content:'原文'}] as any}/>);
 expect(document.querySelectorAll('.case-answer ol li')).toHaveLength(2);
 expect(document.body.textContent).toContain('第一步原话。');
 expect(document.body.textContent).toContain('第二步原话。');
 expect(document.querySelector('.comparison-sources button')?.textContent).toContain('第 3 页');
 expect(document.querySelector('.technical-record')).toBeNull();
});
it('summarizes saved strategy and review above collapsed evidence without internal ids',async()=>{
 const experiment={result:{agent_strategies:{1:{prior_round_review:{summary:'首轮从体检出发',plans:[{candidate_id:'EXP-123-R1-A',conclusion:'待验证',evidence_reason:'证据未齐'}]},bad_case_summary:{groups:[{layer:'检索层',subtype:'关键证据没找回来',count:2}],focus:'先补齐证据'}}},round_conclusions:{1:{status:'saved',review:{plans:[{candidate_id:'EXP-123-R1-A',conclusion:'仍需验证',fixed_question_ids:[],new_failure_question_ids:[],prediction_match_count:0,case_reviews:[{question:'Q01',state:'仍错',reason:'关键证据缺失',assessment:'不确定'}],parameter_assessment:'无法单独归因',evidence_reason:'保存的检索记录',unmatched_reason:'尚未补齐'}],lessons:['下一轮先检查证据']}}}},candidates:[{id:'EXP-123-R1-A',reasoning:{round:1,candidate_label:'A',hypothesis:'扩大查找范围',risk:'可能更慢',predicted_fixed_question_ids:['Q01']}}]};
 await render(<><RoundStrategy experiment={experiment} round={1}/><RoundConclusion experiment={experiment} round={1}/></>);
 expect(document.querySelectorAll('.agent-strategy-details')).toHaveLength(2);
 expect(document.querySelectorAll('.agent-strategy-details[open]')).toHaveLength(0);
 expect(document.querySelector('.round-strategy-line')?.textContent).toContain('检索层 2 题');
 expect(document.querySelector('.round-conclusion-summary')?.textContent).toContain('预测中 0/1');
 expect(document.body.textContent).not.toContain('EXP-');
 expect(document.body.textContent).toContain('扩大查找范围');
 expect(document.body.textContent).toContain('关键证据缺失');
 expect(document.querySelectorAll('.agent-round-strategy ol > li').length).toBeGreaterThanOrEqual(3);
});

it('keeps overlapping Child ranges against the exact Parent text',async()=>{
 const {childRanges}=await import('./components/ChunkBrowser');
 const parent={chunk_text:'甲乙丙丁戊己',children:[{chunk_text:'甲乙丙丁',char_start:0,char_end:4},{chunk_text:'丙丁戊己',char_start:2,char_end:6}]};
 const before=JSON.stringify(parent),parts=childRanges(parent);
 expect(parts.map(p=>p.text).join('')).toBe(parent.chunk_text);
 expect(parts).toEqual([{text:'甲乙',children:[1]},{text:'丙丁',children:[1,2]},{text:'戊己',children:[2]}]);
 expect(JSON.stringify(parent)).toBe(before);
});
it('aligns every atomic requirement to its own Child retrieval path, retaining unknowns',async()=>{
 const {pointPaths,AnswerEvidence}=await import('./components/AnswerEvidence');
 const question={reference_answer:'1. 断电\n2. 戴手套\n3. 检查机身',business_requirements:{required_checks:[{id:'Q01-R1',requirement:'断电',source_chunk_ids:['c1']},{id:'Q01-R2',requirement:'戴手套',source_chunk_ids:['c2']},{id:'Q01-R3',requirement:'检查机身'}]}};
 const row={judge_result:{atomic_results:[{atomic_id:'Q01-R1',state:'MET'},{atomic_id:'Q01-R2',state:'NOT_MET'},{atomic_id:'Q01-R3',state:'NOT_MET'}]},programmatic_metrics:{retrieval_trace:{candidates:[{chunk_id:'c1'},{chunk_id:'c2'}],reranked:[{chunk_id:'c2'},{chunk_id:'c1'}],final:[{parent_chunk_id:'p',matched_child_ids:['c1']}]}}};
 const before=JSON.stringify(row),paths=pointPaths(row,question);
 expect(paths.map(p=>[p.candidate,p.rerank,p.final])).toEqual([[1,2,1],[2,1,null],[undefined,undefined,undefined]]);
 await render(<AnswerEvidence row={row} question={question}/>);
 expect(document.querySelectorAll('.answer-evidence li')).toHaveLength(3);
 expect(document.querySelectorAll('.point-path')).toHaveLength(3);
 expect(document.body.textContent).toContain('交给模型：未知');
 expect(JSON.stringify(row)).toBe(before);
});

it('keeps new-experiment D in four causal sections and never invents post-run repairs',async()=>{
 const {DStory}=await import('./components/EvolutionStory');
 const experiment={result:{causal_evidence:true},candidates:[{id:'EXP-new-D',status:'generated',config:{top_k:6},reasoning:{candidate_label:'D',explanation:'合并已验证的保留条数调整。',changed_parameters:{top_k:6},changes:[{why_merge:'关键说明此前被截断。',target_question_ids:['Q29'],side_effect_check:{risk_checklist:'可能增加回答耗时。'}}]}}]};
 const before=JSON.stringify(experiment);
 await render(<DStory experiment={experiment} evaluation={{config:{top_k:4}}}/>);
 expect([...document.querySelectorAll('.d-story section > h3')].map(n=>n.textContent)).toEqual(['合并了什么','事先预测','事后对账','结论']);
 expect(document.body.textContent).toContain('预计修好 Q29');
 expect(document.body.textContent).toContain('评测尚未完成，实际结果未知。');
 expect(document.body.textContent).not.toContain('实际修好 Q29');
 expect(document.querySelector('details,summary,.technical-record')).toBeNull();
 expect(JSON.stringify(experiment)).toBe(before);
});

it('does not turn an unknown atomic verdict into a missing answer point',async()=>{
 const {AnswerEvidence}=await import('./components/AnswerEvidence');
 await render(<AnswerEvidence row={{judge_result:{atomic_results:[{atomic_id:'Q01-R1',state:'UNKNOWN'}]}}} question={{business_requirements:{required_checks:[{id:'Q01-R1',requirement:'先停止设备'}]}}}/>);
 expect(document.querySelector('.answer-evidence li')?.textContent).toContain('判定未知');
 expect(document.querySelector('.answer-evidence li')?.textContent).not.toContain('没答到');
 expect(document.querySelectorAll('.point-path')).toHaveLength(1);
});

it('shows a saved keep-Baseline decision in the overview, D conclusion and four-part recommendation',async()=>{
 const {EvolutionPage}=await import('./pages/EvolutionPage');
 const {DStory,recommendationReason}=await import('./components/EvolutionStory');
 const evaluation={id:'base',status:'completed',config:{top_k:4},result:{total:50,bad_case_count:8,gates:{passed_count:10,total:11},metrics:{latency_p50_seconds:3.1,latency_p99_seconds:4.4}}};
 const experiment={id:'exp',status:'completed',result:{causal_evidence:true,report_confirmation:{winner_id:'EXP-test-R3-A'}},candidates:[{id:'EXP-test-R3-A',status:'evaluated',reasoning:{candidate_label:'A',round:3},result:{total:50,bad_case_count:4,gates:{passed:true},qualification:{qualified:true},release_qualification:{qualified:false}}},{id:'EXP-test-D',status:'evaluated',reasoning:{candidate_label:'D'},result:{total:50,bad_case_count:6,gates:{passed:false},qualification:{qualified:false}}}],recommendation:{status:'Recommended',recommended_candidate:null,final_decision:{decision:'保持 Baseline'},why:'Winner 候选合格但不具备发布资格，D也未满足推荐条件'}};
 const before=JSON.stringify(experiment);
 vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}')));
 expect(recommendationReason(experiment)).toContain(experiment.recommendation.why);
 await render(<EvolutionPage data={{evaluation,optimization:experiment}}/>);
 expect(document.querySelector('.agent-overview-result h2')?.textContent).toBe('最终方案：保持 Baseline');
 expect(document.querySelector('.agent-overview-result')?.textContent).not.toContain('等待中');
 expect(document.querySelector('.agent-overview-params')?.textContent).toContain('保持 Baseline，参数不变');
 await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='回归与推荐')!.click());
 const lines=[...document.querySelectorAll('.ui-fin-reason > li')].map(n=>n.textContent);
 expect(lines).toHaveLength(4);
 expect(lines[0]).toContain('42 / 50');expect(lines[1]).toContain('10 / 11');expect(lines[2]).toContain('3.1 秒');expect(lines[3]).toContain('新增');
 expect(document.body.textContent).not.toContain('最终推荐结论未保存');
 expect(document.querySelectorAll('.candidate-rejections > button')).toHaveLength(2);
 expect(document.querySelector('.candidate-rejections')?.textContent).toContain('候选合格，但保存的发布资格未通过');
 await act(async()=>root.render(<DStory experiment={experiment} evaluation={evaluation}/>));
 expect(document.querySelector('.d-story section:last-child')?.textContent).toContain(experiment.recommendation.why);
 expect(JSON.stringify(experiment)).toBe(before);
});

it.each([true,false,undefined])('shows a historical failure label only for a current failed verdict (%s)',async(passed)=>{
 const {CaseDetails}=await import('./pages/EvaluationPage');
 const item={passed,question:'保存题目',model_answer:'保存回答',baseline_review_label:'单遍判错'};
 const before=JSON.stringify(item);
 await render(<CaseDetails item={item} snapshot={{}} config={{}} gates={[]}/>);
 expect(document.querySelector('.case-review')?.textContent?.includes('本次判定未通过')).toBe(passed===false);
 expect(JSON.stringify(item)).toBe(before);
});

it('translates saved D protocol names and preserves an array of prediction risks',async()=>{
 const {storyText,DStory}=await import('./components/EvolutionStory');
 const risks=['核对 Q04 不被翻回。','安全拒答率必须过线。'];
 const experiment={result:{causal_evidence:true},candidates:[{reasoning:{candidate_label:'D',hypothesis:'usable_repairs 中单参数最小改动，不撤销 winner_preserved_diff。source_candidate_id=EXP-test-R1-B',changes:[{reason:'扩大候选',target_question_ids:['Q29'],side_effect_check:{risk_checklist:risks}}]}}]};
 const before=JSON.stringify(experiment);
 expect(storyText(experiment.candidates[0].reasoning.hypothesis)).not.toMatch(/\b[a-z]+(?:_[a-z]+)+\b|=/);
 await render(<DStory experiment={experiment}/>);
 for(const risk of risks)expect(document.body.textContent).toContain(risk);
 expect(JSON.stringify(experiment)).toBe(before);
});
