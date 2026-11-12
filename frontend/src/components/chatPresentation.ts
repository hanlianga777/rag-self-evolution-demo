import type {ChatMessage, Conversation} from '../types';

export const answerLatency = (message: ChatMessage) => message.metrics?.latency_ms ?? message.latencyMs;
export const secondsText = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? `${(value / 1000).toFixed(1)} 秒` : '—';

// Display only: keep the complete saved answer available to the audit Drawer.
export function answerParts(content: string) {
  const match = /(?:^|\r?\n)(依据：[^\n]*(?:\r?\n(?![ \t]*\r?(?:\n|$))[^\n]+)*)[ \t\r\n]*$/.exec(content);
  return match ? {body: content.slice(0, match.index).trimEnd(), basis: match[1].trim()} : {body: content, basis: ''};
}

export function chatSources(message: ChatMessage) {
  const sources = message.evidence?.length ? message.evidence.map(citation => ({document: citation.document, page: citation.page_start, citation})) : (message.sources || []).map(source => ({document: source.split(' · ')[0], page: Number(source.match(/(?:p\.?\s*|第\s*)(\d+)/i)?.[1]) || undefined, citation: undefined}));
  return sources.filter((item, index) => sources.findIndex(other => other.document === item.document && other.page === item.page) === index).sort((a,b) => (a.page ?? Infinity) - (b.page ?? Infinity) || a.document.localeCompare(b.document));
}

export function monitoringRecords(events: any[], conversations: Conversation[]) {
  const rows = events.map(event => ({...event, localOnly: false})), matched = new Set<string>();
  for (const conversation of conversations) for (const [index, message] of conversation.messages.entries()) {
    if (message.role !== 'assistant') continue;
    const question = message.question || conversation.messages[index - 1]?.content || '未保存问题';
    // Legacy conversations have no monitoring ID. Pair exact question/answer copies
    // only within five seconds, once per event; repeated questions stay separate.
    const event = events.find(event => !matched.has(event.id) && event.question === question && event.answer === message.content && Math.abs(Date.parse(event.created_at) - Date.parse(message.createdAt)) <= 5000);
    if (event) { matched.add(event.id); continue; }
    rows.push({id: `${conversation.id}:${message.id}`, question, answer: message.content, created_at: message.createdAt, metrics: {...message.metrics, latency_ms: answerLatency(message)}, citations: chatSources(message).length, localOnly: true, determinable: false});
  }
  return rows.sort((a,b) => (Date.parse(b.created_at) || 0) - (Date.parse(a.created_at) || 0));
}

export function monitoringCitationCount(event: any): number | null {
  if (typeof event.citations === 'number') return event.citations;
  const trace = event.metrics?.retrieval_trace;
  return Array.isArray(trace?.final) ? chatSources({evidence: trace.final} as ChatMessage).length : null;
}
