// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {ComparisonAnswer} from './components/ComparisonAnswer';
import {SavedAnswerComparison} from './components/SavedAnswerComparison';
import {explanation} from './components/comparisonData';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}

it.each([
 ['Q04','按《卡赫_KIRA_B_50完整操作说明_中文版.pdf》“每月一次”（第86页），停用三个月应按“较长时间停机”处理：','卡赫_KIRA_B_50完整操作说明_中文版.pdf','每月一次',86,'按 KIRA B 50 操作说明“每月一次”1，停用三个月应按“较长时间停机”处理：','KIRA B 50 操作说明'],
 ['Q29','按《B2四足机器人用户手册（中文版）》“检查保养—不带电检查表”，在不带电、不接通充电器的状态下逐项检查以下 5 类：','宇树_B2四足机器人用户手册_中文版.pdf','检查保养—不带电检查表',18,'按 B2 用户手册“检查保养—不带电检查表”1，在不带电、不接通充电器的状态下逐项检查以下 5 类：','B2 用户手册']
])('%s keeps every non-citation character in the saved opening sentence',async(_id,answer,documentName,section,page,expected,short)=>{
 const evidence={document:documentName,page_start:page,section_path:section,content:'保存的证据'};
 await mount(<ComparisonAnswer row={{model_answer:answer,programmatic_metrics:{retrieval_trace:{final:[evidence]}}}} points={[]} side="before" onOpenCitation={()=>{}}/>);
 expect(document.querySelector('.comparison-body')?.textContent).toBe(expected);
 expect(document.querySelector('.comparison-sources li')?.textContent).toBe(`1${short}，${section}，第 ${page} 页`);
});

const quote='类型=结构；要点=1. 目视及触摸检查机身、各个关节及连接处、足端组件是否完好,有裂纹或者有破损需及时更换和联系 Unitree 售后';
const row=(check:any)=>({diagnostic_view:{evidence_checks:[{quote,...check}]},programmatic_metrics:{retrieval_trace:{final:Array(6).fill({})}}});
it('shows a short readable excerpt and only the recalled evidence movement',()=>{
 const result=explanation(row({candidate_hit:false,final_rank:null}),row({candidate_hit:true,candidate_rank:22,rerank_rank:3,final_rank:3}),{candidate_k:12},{candidate_k:24},[]);
 expect(result.steps.find(s=>s.label==='关键证据位置')?.text).toBe('“目视及触摸检查机身、各个关节及连接处、足端组件…”：优化前没进候选，优化后进入 Top-K 第 3 位');
});
it('describes the cutoff change without repeating all ranks',()=>{
 const result=explanation(row({candidate_hit:true,candidate_rank:10,rerank_rank:5,final_rank:null}),row({candidate_hit:true,candidate_rank:10,rerank_rank:6,final_rank:6}),{top_k:4},{top_k:6},[]);
 expect(result.steps.find(s=>s.label==='关键证据位置')?.text).toContain('优化前 Rerank 第 5 位，被 Top-K 截掉；优化后 Rerank 第 6 位，进入 Top-K 第 6 位');
 expect(result.steps.find(s=>s.label==='关键证据位置')?.text).not.toContain('召回第');
});
it('uses a plain fallback when structured evidence contains no readable sentence',()=>{
 const a={diagnostic_view:{evidence_checks:[{quote:'类型=结构；要点=1. N/A',candidate_hit:false}]}},b={diagnostic_view:{evidence_checks:[{quote:'类型=结构；要点=1. N/A',candidate_hit:true,final_rank:3}]}};
 expect(explanation(a,b,{candidate_k:12},{candidate_k:24},[]).steps[1].text).toContain('“关键说明”');
});
it('lists negative-question configuration changes directly and never marks a key',()=>{
 const a={...row({candidate_hit:false,final_rank:null}),test_category:'negative',passed:false},b={...row({candidate_hit:true,final_rank:3}),test_category:'negative',passed:true};
 const result=explanation(a,b,{candidate_k:12,top_k:4,generation_thinking:'max'},{candidate_k:24,top_k:6,generation_thinking:'high'},[]);
 expect(result.key).toBeUndefined();
 expect(result.steps).toEqual([{label:'配置变化',text:'Candidate K 12→24、Top-K 4→6、Thinking 档位 Max→High'},{label:'回答结果',text:'优化前拒答判定未通过，优化后正确拒答'}]);
});
it.each([1,2,3])('shows %i missing and newly met points once in the comparison table',async(count)=>{
 const question_id=`Q${count}`,atomic_results=Array.from({length:count},(_,i)=>({atomic_id:`${question_id}-R${i+1}`,state:'NOT_MET'}));
 const before={question_id,question:'保存的问题',passed:false,reference_answer:'1. 结构完好\n2. 电池无损\n3. 摇杆在中位',model_answer:'保存的原回答',judge_result:{atomic_results}},after={...before,passed:true,judge_result:{atomic_results:atomic_results.map(r=>({...r,state:'MET'}))}};
 vi.stubGlobal('fetch',vi.fn(async(input:string)=>new Response(JSON.stringify(input.endsWith('/comparison-cases')?{id:input.includes('/n-base/')?'n-base':'n-after',status:'completed',dataset_version_id:'golden',judge:{evaluation_identity:'same'},cases:[input.includes('/n-base/')?before:after]}:{case:input.includes('/n-base/')?before:after}))));
 await mount(<SavedAnswerComparison data={{evaluation:{id:'n-base'},optimization:{recommendation:{recommended_candidate:'D'},candidates:[{id:'D',status:'evaluated',result:{evaluation_run_id:'n-after',evaluation_complete:true,total:1}}]}}} onOpenCitation={()=>{}}/>);
 const rows=[...document.querySelectorAll('.comparison-ptable tbody tr')];
 expect(rows).toHaveLength(count);
 expect(rows.map(row=>row.querySelector('td')?.textContent)).toEqual(['结构完好','电池无损','摇杆在中位'].slice(0,count).map((text,i)=>`${i+1}${text}新满足`));
 for(const row of rows){expect(row.querySelector('td:nth-child(2)')?.textContent).toBe('错');expect(row.querySelector('td:nth-child(3)')?.textContent).toBe('对');}
 expect(document.querySelectorAll('.comparison-flag')).toHaveLength(0);
 expect(document.querySelectorAll('.comparison-newtag')).toHaveLength(count);
});
