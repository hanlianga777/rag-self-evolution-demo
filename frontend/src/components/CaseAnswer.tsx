import { StructuredAnswer, type AnswerSource } from './StructuredAnswer';
import { answerMarkup } from './answerMarkup';
import type { Citation } from '../types';

export function CaseAnswer({ text, final, reference, streaming, onOpenCitation }: {
  text: string;
  final?: AnswerSource[];
  reference?: boolean;
  streaming?: boolean;
  onOpenCitation?: (citation: Citation) => void;
}) {
  if (final === undefined && !reference && !streaming) return answerMarkup(text);
  return <StructuredAnswer text={text} evidence={final} numberedEvidence={reference ? undefined : final} reference={reference} streaming={streaming} onOpenCitation={onOpenCitation} />;
}
