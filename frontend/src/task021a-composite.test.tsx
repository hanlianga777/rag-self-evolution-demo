// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it} from 'vitest';
import {DStory,EvolutionRoute} from './components/EvolutionStory';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';});
function mount(element:any){root=createRoot(document.body.appendChild(document.createElement('div')));act(()=>root.render(element));return document.body.textContent;}
it.each([
 [{status:'generated',outcome:'generated'},{status:'generated'},'等待完整评测'],
 [{status:'no_effective_composite',outcome:'declined'},undefined,'Agent 判断不做 D'],
 [{status:'failed',outcome:'validation_failed',reason:'建议校验失败'},undefined,'Candidate D 未形成'],
 [{status:'generated',outcome:'generated'},{status:'failed'},'评测中断，尚无完整结果'],
])('separates the four D outcomes in current story (%j)',(composite,d,label)=>{
 const text=mount(<DStory experiment={{result:{composite},candidates:d?[{...d,reasoning:{candidate_label:'D'}}]:[]}}/>);
 expect(text).toContain(label);
 if(composite.outcome==='validation_failed')expect(text).toContain('建议校验失败');
 if(d?.status==='failed')expect(text).not.toContain('评测状态：合格');
});
it('places saved reviews after the round they assess without inventing missing lessons',()=>{
 const review=(text:string)=>({plans:[],baseline_remaining_assessment:text,conclusions:[{id:'L1',conclusion:text}]});
 mount(<EvolutionRoute evaluation={{config:{}}} badCases={[]} experiment={{candidates:[1,2,3].map(round=>({id:`R${round}-A`,reasoning:{candidate_label:'A',round}})),result:{prior_round_reviews:{'2':{status:'saved',review:review('首轮认识')},'3':{status:'saved',review:review('第二轮认识')},'4':{status:'not_saved'}}}}}/>);
 const rounds=document.querySelectorAll('.route-round');
 expect(rounds[0].textContent).toContain('首轮认识');expect(rounds[0].textContent).not.toContain('第二轮认识');
 expect(rounds[1].textContent).toContain('第二轮认识');expect(rounds[2].querySelector('.route-review')).toBeNull();
});
