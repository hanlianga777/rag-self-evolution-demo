import { StructuredAnswer } from './StructuredAnswer';
import { finalEvidence, type Point } from './comparisonData';
import type { Citation } from '../types';

export { citationText, readableSourceName } from './StructuredAnswer';

export function ComparisonAnswer({ row, points, side, onOpenCitation }: {
  row: any;
  points: Point[];
  side: 'before' | 'after';
  onOpenCitation?: (citation: Citation) => void;
}) {
  const final = finalEvidence(row), trace = row.programmatic_metrics?.retrieval_trace;
  return <StructuredAnswer
    text={row.model_answer || '回答未保存'}
    evidence={[...(final || []), ...(row.retrieved_chunks || []), ...(trace?.candidates || []), ...(trace?.reranked || [])]}
    numberedEvidence={final}
    points={points}
    side={side}
    onOpenCitation={onOpenCitation}
  />;
}
