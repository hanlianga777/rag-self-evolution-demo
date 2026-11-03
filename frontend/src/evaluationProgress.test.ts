import { expect, it } from 'vitest';
import { mergeEvaluationProgress, hasEvaluationDetails } from './evaluationProgress';
it('only merges progress for the same run and preserves detailed saved results', () => {
 const full={id:'r',status:'running',cases:[{id:'q'}],result:{correct:1},product_diagnostics:{objective_metrics:{recall_at_k:80}}};
 const merged=mergeEvaluationProgress(full,{id:'r',status:'running',progress:2,cases:[],result:{completed:2},product_diagnostics:null});
 expect(merged).toEqual({...full,progress:2,result:{correct:1,completed:2}});
 expect(mergeEvaluationProgress(full,{id:'new',status:'running'})).toEqual({id:'new',status:'running'});
});
it('does not mistake empty light diagnostics for a complete saved report', () => {
 expect(hasEvaluationDetails({id:'r',product_diagnostics:{}})).toBe(false);
 expect(hasEvaluationDetails({id:'r',product_diagnostics:{objective_metrics:{recall_at_k:80}}})).toBe(true);
 expect(hasEvaluationDetails({id:'r',cases:[]})).toBe(true);
});
