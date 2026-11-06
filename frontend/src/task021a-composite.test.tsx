// @vitest-environment jsdom
import {act} from 'react';
import {createRoot} from 'react-dom/client';
import {afterEach,expect,it} from 'vitest';
import {CompositeStatus,PriorRoundReviews} from './pages/EvolutionPage';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let root:ReturnType<typeof createRoot>;
afterEach(()=>{act(()=>root?.unmount());document.body.innerHTML='';});
function mount(element:any){root=createRoot(document.body.appendChild(document.createElement('div')));act(()=>root.render(element));return document.body.textContent;}
it.each([
 [{status:'generated',outcome:'generated'},undefined,'已生成'],
 [{status:'no_effective_composite',outcome:'declined'},undefined,'合法不生成'],
 [{status:'failed',outcome:'validation_failed'},undefined,'建议校验失败'],
 [{status:'generated',outcome:'generated'},{status:'failed'},'D 评测失败'],
])('separates the four D outcomes (%j)',(composite,d,label)=>{expect(mount(<CompositeStatus composite={composite} candidate={d}/>)).toContain(label);});
it('shows each saved review and marks missing rounds',()=>{
 const review=(text:string)=>({plans:[],baseline_remaining_assessment:text,conclusions:[{id:'L1',conclusion:text}]});
 const text=mount(<PriorRoundReviews reviews={{'1':{status:'saved',review:review('首轮认识')},'2':{status:'saved',review:review('第二轮认识')},'3':{status:'not_saved'}}}/>);
 expect(text).toContain('第 1 轮');expect(text).toContain('首轮认识');expect(text).toContain('第 2 轮');expect(text).toContain('第二轮认识');expect(text).toContain('未保存');
});
