import {ModelAnswer} from './ModelAnswer';
import type {Point} from './comparisonData';
import type {Citation} from '../types';
export {citationText,readableSourceName} from './answerPresentation';

export function ComparisonAnswer({row,points,side,onOpenCitation}:{row:any;points:Point[];side:'before'|'after';onOpenCitation:(citation:Citation)=>void}) {
  const saved=row.programmatic_metrics?.retrieval_trace?.final ?? row.retrieved_chunks;
  return <ModelAnswer text={row.model_answer || '回答未保存'} final={Array.isArray(saved)?saved:[]} points={points} side={side} onOpenCitation={onOpenCitation}/>;
}
