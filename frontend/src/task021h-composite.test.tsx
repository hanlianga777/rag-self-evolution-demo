// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it,vi} from 'vitest';
import {DStory,dProgressLabel} from './components/EvolutionStory';
import {EvolutionPage} from './pages/EvolutionPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';vi.unstubAllGlobals();});
async function mount(element:any){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(element));}
const old={status:'no_effective_composite',outcome:'declined',suggestion:{explanation:'旧结论：风险大所以放弃'}};
const current={status:'generated',outcome:'generated',suggestion:{explanation:'最新结论：在赢家上验证更多证据'}};
it('shows the latest D decision and keeps the old raw decision inside technical details',async()=>{
 const d={id:'experiment-D',status:'running',config:{top_k:6},reasoning:{candidate_label:'D',hypothesis:current.suggestion.explanation}};
 const exp={id:'experiment',candidates:[d],result:{composite:current,composite_history:[old]},recommendation:{d_outcome:'declined'}};
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(exp))));
 await mount(<EvolutionPage data={{evaluation:{id:'base',config:{}},optimization:exp}}/>);
 expect(document.querySelector('.d-story')?.textContent).toContain('最新结论');
 expect(document.querySelector('.d-story')?.textContent).not.toContain('旧结论');
 const details=[...document.querySelectorAll('details')].find(e=>e.querySelector('summary')?.textContent==='技术详情');
 expect(details?.open).toBe(false);
 expect(details?.textContent).toContain('旧结论：风险大所以放弃');
});
it('does not let a stale recommendation decline override the current failed decision',async()=>{
 const exp={result:{composite:{status:'failed',outcome:'validation_failed',reason:'新建议三次不合规'},composite_history:[old]},recommendation:{d_outcome:'declined'}};
 expect(dProgressLabel(exp)).toBe('D 未形成');
 await mount(<DStory experiment={exp}/>);
 expect(document.querySelector('.d-story')?.textContent).toContain('新建议三次不合规');
 expect(document.querySelector('.d-story')?.textContent).not.toContain('Agent 判断不做 D');
});
it('shows premise evidence and the protected question and gate risk checklist',async()=>{
 const d={status:'generated',config:{top_k:6},reasoning:{candidate_label:'D',changes:[{parameter:'top_k',side_effect_check:{
  same_premise_evidence:'相同前提尚未观察',different_premise_evidence:'候选池12与24不同',risk_checklist:'核对Q17和安全拒答95门槛'}}]}};
 await mount(<DStory experiment={{candidates:[d],result:{composite:current}}}/>);
 for(const text of ['相同前提尚未观察','候选池12与24不同','核对Q17和安全拒答95门槛'])expect(document.querySelector('.d-story')?.textContent).toContain(text);
});
