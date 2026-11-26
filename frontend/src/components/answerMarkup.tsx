import { Children, cloneElement, createElement, Fragment, isValidElement, type ReactNode } from 'react';

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
const referenceLabel = /(^|\n|<(?:p|div|li|br)\s*\/?>)([^\S\n]*(?:\d+[.、)）](?!\d)[^\S\n]*|[-*+][^\S\n]+)?)(?:\*\*|__)?(?:要点[^\S\n]*\d+|[（(]补充[）)])(?:\*\*|__)?[^\S\n]*[：:]?[^\S\n]*/gi;
const boundaryLabel = /(^|\n|<(?:p|div|li|br)\s*\/?>)([^\S\n]*(?:#{1,6}[^\S\n]+)?)(?:\*\*|__)?(?:证据边界|资料边界|未确认条件)[^\S\n]*(?:\*\*|__)?[：:](?:\*\*|__)?[^\S\n]*/gi;
const warning = /^(?:\*\*|__)?(?:注意|警告|危险|提醒)(?:\*\*|__)?\s*[：:]/;

function markdown(text: string, expandSteps: boolean): ReactNode[] {
  // Only split a run that starts at 1 and continues sequentially. Numbers inside
  // decimals, model names, versions and chapter references are not list markers.
  const normalized = expandSteps ? text.replace(/(^|[：:。；;！!？?\s])1[.、)）](?!\d)\s*([^\n]+)(?=\n|$)/gm, (whole, prefix: string, body: string) => {
    let expected = 2;
    const expanded = body.replace(/([。；;！!？?\s])(\d+)[.、)）](?!\d)\s*/g, (match, separator: string, number: string) => Number(number) === expected ? (expected++, `${separator}\n${number}. `) : match);
    return expected > 2 ? `${prefix}\n1. ${expanded}` : whole;
  }) : text;
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
        const heading = line.match(/^\s*#{1,6}\s+(.+)$/);
        result.push(heading ? <h5 key={result.length}>{inline(heading[1])}</h5> : <p key={result.length}>{inline(line.trim().replace(/^>\s?/, ''))}</p>);
      }
    }
    return result;
  }
  return blocks();
}


function parseAnswer(text: string, expandSteps: boolean): ReactNode[] {
  if (!/<\/?[a-z][^>]*>/i.test(text)) return markdown(text, expandSteps);
  const document = new DOMParser().parseFromString(text, 'text/html');
  const allowed = new Set(['p', 'div', 'br', 'ol', 'ul', 'li', 'strong', 'b', 'em', 'i', 'code', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span']);
  function node(value: Node, index: number): ReactNode {
    if (value.nodeType === 3) {
      const text = value.textContent || '';
      return ['BODY', 'P', 'DIV', 'LI', 'BLOCKQUOTE'].includes(value.parentElement?.tagName || '') && /(?:^|[\n：:])\s*(?:\d+[.、)）](?!\d)|[-*+]\s|#{1,6}\s)/.test(text) ? markdown(text, expandSteps) : inline(text);
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
  return Array.from(document.body.childNodes).map(node);
}

const textOf = (node: ReactNode): string => typeof node === 'string' || typeof node === 'number' ? String(node) :
  isValidElement<{ children?: ReactNode }>(node) ? textOf(node.props.children) : Array.isArray(node) ? node.map(textOf).join('') : '';

/** Format saved text without inferring a conclusion or changing the source. */
export function answerMarkup(text: string, mode?: 'model' | 'reference') {
  if (mode === 'reference') text = text.replace(referenceLabel, '$1$2');
  if (mode === 'model') text = text.replace(boundaryLabel, '$1$2');
  const blocks = parseAnswer(text, !mode);
  if (!mode) return <div className="case-answer">{blocks}</div>;
  let opening = true;
  const structure = (block: ReactNode): ReactNode => {
    const value = textOf(block).trim();
    if (!value) return block;
    const element = isValidElement<{ children?: ReactNode; className?: string }>(block) ? block : null;
    const children = element ? element.props.children : block;
    const list = element?.type === 'ol' || element?.type === 'ul';
    if (list) return cloneElement(element, {}, Children.map(children, structure));
    // Safe HTML can wrap Markdown blocks inside a div or list item.
    const nodes = Children.toArray(children).filter(node => node !== '');
    if (element?.type === 'div' && nodes.some(node => isValidElement(node) && ['p', 'div', 'ol', 'ul', 'h5'].includes(String(node.type)))) {
      return cloneElement(element, {}, nodes.map(structure));
    }
    const heading = element?.type === 'h5' || (element?.type === 'p' && !warning.test(value) &&
      value.length <= 24 && (/^[^：:。！？\uE000]+[：:]$/.test(value) || nodes.length === 1 && isValidElement(nodes[0]) && nodes[0].type === 'strong'));
    if (heading) return <h5 key={element?.key}>{children}</h5>;
    const lead = opening;
    opening = false;
    const notice = warning.test(value);
    // Keep the first existing sentence prominent instead of promoting an entire long paragraph.
    const first = nodes[0];
    const sentence = typeof first === 'string' && first.match(/^.+?[。！？](?:[^\S\n]*\uE000\d+\uE001)*(?![^\S\n]*\uE000)(?=[^\S\n]*\S)/);
    const body = lead && sentence
      ? <><span className="answer-lead">{sentence[0]}</span>{first.slice(sentence[0].length)}{nodes.slice(1)}</>
      : children;
    const className = [lead && !sentence && 'answer-lead', notice && 'answer-warning'].filter(Boolean).join(' ');
    return element ? cloneElement(element, { className }, body) : <span className={className}>{body}</span>;
  };
  return <div className="case-answer">{Children.map(blocks, structure)}</div>;
}
