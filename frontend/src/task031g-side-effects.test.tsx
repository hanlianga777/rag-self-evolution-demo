// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it} from 'vitest';
import {DStory,DSideEffects} from './components/EvolutionStory';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';});
async function mount(element:any){root=createRoot(document.body.appendChild(document.createElement('div')));await act(async()=>root.render(element));}
it('renders each side-effect array as a bullet list and preserves strings',async()=>{
 const side={same_premise_evidence:['未观察到','相同前提证据'],different_premise_evidence:['不同前提证据'],risk_checklist:['保护题风险','临界门槛风险'],mitigation:'保留原有规避说明'};
 await mount(<DSideEffects changes={[{parameter:'top_k',side_effect_check:side}]}/>);
 expect([...document.querySelectorAll('ul li')].map(e=>e.textContent)).toEqual(['未观察到','相同前提证据','不同前提证据','保护题风险','临界门槛风险']);
 expect(document.querySelectorAll('ul')).toHaveLength(3);
 expect(document.querySelector('.d-side-effects')?.textContent).toContain('保留原有规避说明');
});
it('shows the D side-effect section when only arrays are present',async()=>{
 const d={status:'generated',config:{top_k:6},reasoning:{candidate_label:'D',changes:[{parameter:'top_k',side_effect_check:{risk_checklist:['重点保护题','安全门槛']}}]}};
 await mount(<DStory experiment={{candidates:[d],result:{composite:{status:'generated'}}}}/>);
 expect([...document.querySelectorAll('.d-story ul li')].map(e=>e.textContent)).toEqual(['重点保护题','安全门槛']);
});
