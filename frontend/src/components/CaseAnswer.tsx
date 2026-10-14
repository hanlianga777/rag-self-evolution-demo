import { createElement, Fragment, type ReactNode } from 'react';

// Display only: keep the persisted answer and its exact audit copy untouched.
const inline = (text: string): ReactNode => text.split(/(\*\*[^*]+\*\*|__[^_]+__|\*[^*\n]+\*|_[^_\n]+_|`[^`]+`|\[[^\]]+\]\([^\s)]+\))/g).map((part, index) => {
  if (/^(\*\*|__)/.test(part)) return <strong key={index}>{part.slice(2, -2)}</strong>;
  if (/^(\*|_)/.test(part) && part.length > 2) return <em key={index}>{part.slice(1, -1)}</em>;
  if (part.startsWith('`')) return <code key={index}>{part.slice(1, -1)}</code>;
  const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
  if (link) return <span key={index}>{link[1]}（{link[2]}）</span>;
  return part;
});
const marker = /^(\s*)(?:(\d+)[.、)）](?!\d)\s*|[-*+]\s+)(.+)$/;

function markdown(text: string): ReactNode[] {
  // Only split a run that starts at 1 and continues sequentially. Numbers inside
  // decimals, model names, versions and chapter references are not list markers.
  const normalized = text.replace(/(^|[：:。；;！!？?\s])1[.、)）](?!\d)\s*([^\n]+)(?=\n|$)/gm, (whole, prefix: string, body: string) => {
    let expected = 2;
    const expanded = body.replace(/([。；;！!？?\s])(\d+)[.、)）](?!\d)\s*/g, (match, separator: string, number: string) => Number(number) === expected ? (expected++, `${separator}\n${number}. `) : match);
    return expected > 2 ? `${prefix}\n1. ${expanded}` : whole;
  });
  const lines = normalized.replace(/\r\n?/g, '\n').split('\n');
  let cursor = 0;
  function blocks(indent = 0): ReactNode[] {
    const result: ReactNode[] = [];
    while (cursor < lines.length) {
      const line = lines[cursor];
      if (!line.trim()) { cursor++; continue; }
      const match = line.match(marker);
      if ((line.match(/^\s*/)?.[0].length || 0) < indent) break;
      if (match) {
        const level = match[1].length, ordered = !!match[2], entries: ReactNode[] = [];
        const start = Number(match[2]) || 1;
        while (cursor < lines.length) {
          const item = lines[cursor].match(marker);
          if (!item || item[1].length !== level || !!item[2] !== ordered) break;
          cursor++;
          const content: ReactNode[] = [<Fragment key="text">{inline(item[3])}</Fragment>];
          while (cursor < lines.length && lines[cursor].trim() && /^\s+/.test(lines[cursor]) && (lines[cursor].match(/^\s*/)?.[0].length || 0) > level) {
            if (marker.test(lines[cursor])) content.push(...blocks((lines[cursor].match(/^\s*/)?.[0].length || 0)));
            else { content.push(<Fragment key={`continuation-${cursor}`}><br />{inline(lines[cursor].trim())}</Fragment>); cursor++; }
          }
          entries.push(<li key={entries.length}>{content}</li>);
        }
        result.push(ordered ? <ol key={result.length} start={start}>{entries}</ol> : <ul key={result.length}>{entries}</ul>);
      } else {
        cursor++;
        const heading = line.match(/^#{1,6}\s+(.+)$/);
        result.push(heading ? <h5 key={result.length}>{inline(heading[1])}</h5> : <p key={result.length}>{inline(line.replace(/^>\s?/, ''))}</p>);
      }
    }
    return result;
  }
  return blocks();
}

export function CaseAnswer({ text }: { text: string }) {
  if (!/<\/?[a-z][^>]*>/i.test(text)) return <div className="case-answer">{markdown(text)}</div>;
  const document = new DOMParser().parseFromString(text, 'text/html');
  const allowed = new Set(['p', 'div', 'br', 'ol', 'ul', 'li', 'strong', 'b', 'em', 'i', 'code', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span']);
  function node(value: Node, index: number): ReactNode {
    if (value.nodeType === 3) {
      const text = value.textContent || '';
      return ['BODY', 'P', 'DIV', 'LI', 'BLOCKQUOTE'].includes(value.parentElement?.tagName || '') && /(?:^|[\n：:])\s*(?:\d+[.、)）](?!\d)|[-*+]\s|#{1,6}\s)/.test(text) ? markdown(text) : inline(text);
    }
    if (value.nodeType !== 1) return null;
    const element = value as HTMLElement, tag = element.tagName.toLowerCase();
    if (['script', 'style', 'iframe', 'object', 'embed', 'svg', 'math'].includes(tag)) return null;
    const children = Array.from(element.childNodes).map(node);
    if (tag === 'a') return <span key={index}>{children}{element.getAttribute('href') && `（${element.getAttribute('href')}）`}</span>;
    if (tag === 'img') return <span key={index}>{element.getAttribute('alt') || ''}</span>;
    if (!allowed.has(tag)) return <Fragment key={index}>{children}</Fragment>;
    const safeTag = /^h\d$/.test(tag) ? 'h5' : tag === 'p' ? 'div' : tag;
    return createElement(safeTag, { key: index, ...(tag === 'ol' && /^\d+$/.test(element.getAttribute('start') || '') ? { start: Number(element.getAttribute('start')) } : {}) }, ...(tag === 'br' ? [] : children));
  }
  return <div className="case-answer">{Array.from(document.body.childNodes).map(node)}</div>;
}
