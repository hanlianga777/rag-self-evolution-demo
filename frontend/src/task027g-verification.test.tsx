// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {AssistantPage} from './pages/AssistantPage';
import {VerificationPage} from './pages/VerificationPage';
import {VersionsPage} from './pages/VersionsPage';
import {ComparisonAnswer} from './components/ComparisonAnswer';
import {storyText} from './components/EvolutionStory';
import {answerParts, monitoringRecords, secondsText} from './components/chatPresentation';
import {CONVERSATIONS_STORAGE_KEY} from './conversations';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';localStorage.clear();sessionStorage.clear();history.replaceState(null,'','/');vi.unstubAllGlobals();});
async function mount(node:React.ReactNode){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(node));}
async function click(text:string){await act(async()=>[...document.querySelectorAll('button')].find(b=>b.textContent===text)!.click());}
const evidence=(page:number,id:string)=>({document:'卡赫_KIRA操作说明_中文版.pdf',page_start:page,page_end:page,chunk_id:id,content_preview:'保存的证据'});
it('structures a saved chat answer without changing its full audit copy or sources',async()=>{
 const content='1. 正文中的依据：保留。\n2. 第二条。\n\n依据：操作说明的保存证据。';
 const message={id:'a',role:'assistant',createdAt:'2026-11-08T03:08:00Z',question:'存放问题',content,latencyMs:13433,evidence:[evidence(48,'a'),evidence(12,'b'),evidence(48,'c')]};
 localStorage.setItem(CONVERSATIONS_STORAGE_KEY,JSON.stringify([{id:'c',title:'历史会话',updatedAt:message.createdAt,messages:[{id:'u',role:'user',content:'存放问题',createdAt:message.createdAt},message]}]));
 await mount(<AssistantPage productionLabel="当前线上：Candidate D" badCases={[]} onOpenBadCase={()=>{}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>);
 await act(async()=>document.querySelector<HTMLButtonElement>('.conversation-item > button')!.click());
 expect(document.querySelector('.qa-version-status')).toBeNull();
 expect(document.querySelector('.message-label')?.textContent).toBe('AI 助手13.4 秒');
 expect(document.querySelector('.answer-text')?.textContent).toContain('正文中的依据：保留');
 expect(document.querySelector('.answer-text')?.textContent).not.toContain('操作说明的保存证据');
 expect(document.querySelector('.message-sources')?.textContent).toContain('依据：操作说明的保存证据');
 expect([...document.querySelectorAll('.message-sources button')].map(n=>n.textContent)).toEqual(['KIRA 操作说明，第 12 页','KIRA 操作说明，第 48 页']);
 expect(document.querySelector('.message-sources [title]')).toBeNull();
 expect(document.querySelector('.qa-answer-audit')).toBeNull();
 expect(document.querySelector('.qa-answer-actions .clue-button')?.classList.contains('primary')).toBe(true);
 expect(document.querySelector('.chat-header')?.textContent).not.toContain('历史会话');
 expect(JSON.parse(localStorage.getItem(CONVERSATIONS_STORAGE_KEY)!)[0].messages[1].content).toBe(content);
});
it('combines saved feedback and local-only answers, counting linked answers once without writes',async()=>{
 const time='2026-11-08T03:08:00Z';
 const events=[{id:'m',created_at:time,question:'已有关联问题',answer:'已有回答',determinable:true,bad_case:true,metrics:{latency_ms:2000,retrieval_trace:{final:[evidence(48,'a')]}}}];
 localStorage.setItem(CONVERSATIONS_STORAGE_KEY,JSON.stringify([{id:'c',title:'会话',updatedAt:time,messages:[{id:'a',role:'assistant',createdAt:time,question:'已有关联问题',content:'已有回答',latencyMs:2000},{id:'b',role:'assistant',createdAt:time,question:'仅本机问题',content:'本机回答',latencyMs:4000,evidence:[evidence(12,'b')]}]}]));
 location.hash='#verification?tab=monitoring';const fetcher=vi.fn(async()=>new Response('{}'));vi.stubGlobal('fetch',fetcher);
 await mount(<VerificationPage data={{monitoring:{events},optimization:{candidates:[]}}} onOpenCitation={()=>{}} onOpenDocument={()=>{}}/>);
 expect(document.querySelector('.tabs [aria-pressed=true]')?.textContent).toBe('Monitoring');
 expect([...document.querySelectorAll('.monitoring-stats strong')].map(n=>n.textContent)).toEqual(['2','1','1','3.0 秒']);
 expect(document.querySelectorAll('.monitoring-table tbody tr')).toHaveLength(2);
 expect([...document.querySelectorAll('.monitoring-table th')].map(n=>n.textContent)).toEqual(['时间','问题','耗时','引用数','标注状态','操作']);
 expect(document.querySelectorAll('.monitoring-assessment button')).toHaveLength(3);
 expect(document.body.textContent).toContain('仅本机保存');expect(document.querySelector('.feedback-loop')).toBeNull();expect(fetcher).not.toHaveBeenCalled();
});
it('labels the three release gates and keeps only the two secondary review actions',async()=>{
 const d={id:'exp-D',reasoning:{candidate_label:'D'},config:{top_k:6},result:{gates:{passed:true,passed_count:11,total:11},new_regression_question_ids:[],all_fixed_question_ids:['Q04']}};
 await mount(<VersionsPage data={{versions:[{id:'p',status:'active',provenance:'published',config:d.config,snapshot:{candidate_id:d.id,human_release:{decision:'approved'}}},{id:'old',status:'archived'}],optimization:{candidates:[d]}}}/>);
 expect([...document.querySelectorAll('.ui-rel-steps strong')].map(n=>n.textContent)).toEqual(['Gate 2 · 推荐确认（人工审核）','发布资格（程序校验）','Gate 3 · 发布授权（人工审批）']);
 expect([...document.querySelectorAll('.ui-rel-actions button')].map(n=>n.textContent)).toEqual(['查看评测报告','查看发布快照']);
 expect(document.querySelectorAll('.ui-rel-actions button.secondary svg')).toHaveLength(2);
 expect(document.querySelector('.release-history-table button.secondary')?.textContent).toBe('回滚至此版本');
 await click('回滚至此版本');expect(document.querySelector('.confirm-dialog')).not.toBeNull();
});
it('removes answer boundary notes and citation counts while preserving the saved row',async()=>{
 const row={model_answer:'正文。\n\n**证据边界：**边界备注。\n\n未确认条件：条件备注。',programmatic_metrics:{retrieval_trace:{final:[]}}},original=JSON.stringify(row);
 await mount(<ComparisonAnswer row={row} points={[]} side="before" onOpenCitation={()=>{}}/>);
 expect(document.querySelector('.comparison-body')?.textContent).toBe('正文。');expect(document.querySelector('.comparison-more')).toBeNull();expect(JSON.stringify(row)).toBe(original);
});
it('normalizes parameter prose without touching saved Agent reasoning',()=>{
 const text='降thinking档位，TopK=6，topk=4，Thinking 档位从Max降到High，修好2题。';
 expect(storyText(text)).toBe('降 Thinking 档位，Top-K 6，Top-K 4，Thinking 档位从 Max 降到 High，修好 2 题。');
});

it('keeps unsplittable basis prose and distinct repeated saved answers',()=>{
 const inline='原句中的依据：保留全文。';const separated='依据：保留。\n\n后面还有正文。';expect(answerParts(separated)).toEqual({body:separated,basis:''});expect(answerParts(inline)).toEqual({body:inline,basis:''});expect(secondsText(null)).toBe('—');expect(secondsText(0)).toBe('0.0 秒');
 const time='2026-11-08T03:08:00Z',event={id:'event',created_at:time,question:'重复问题',answer:'重复回答'};
 const messages=['one','two'].map(id=>({id,role:'assistant' as const,createdAt:time,question:event.question,content:event.answer}));
 expect(monitoringRecords([event],[{id:'chat',title:'会话',updatedAt:time,messages}])).toHaveLength(2);
 expect(monitoringRecords([event],[{id:'chat',title:'会话',updatedAt:time,messages:[{...messages[0],createdAt:'2026-11-08T03:09:00Z'}]}])).toHaveLength(2);
});
