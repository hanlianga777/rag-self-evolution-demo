import {useId, useLayoutEffect, useRef, useState} from 'react';
import {CitationViewer} from './CitationViewer';
import {Children, cloneElement, isValidElement, type ReactNode} from 'react';
import {answerMarkup} from './answerMarkup';
import {answerCitationDisplay} from '../answerCitations';
import type {Point} from './comparisonData';
import type {Citation} from '../types';
import './StructuredAnswer.css';

export type AnswerSource = Parameters<typeof answerCitationDisplay>[1][number] & Partial<Citation> & {
  section?: string;
  parent_section_path?: string;
  content?: string;
  chunk_text?: string;
};
type Source = {number:number; document?:string; section?:string; page?:number; end?:number; citation?:AnswerSource};
const sourceToken = /\uE000(\d+)\uE001/g;
const numberedCitation = /(?<!\\)\[([1-9]\d*)\](?!\d|\()/g;
export const readableSourceName = (text:string) => text.replace(/\.pdf$/i,'').replace(/^(?:卡赫|宇树)[_\s]*/,'').replace(/[_（(]?中文版[）)]?|完整|四足机器人(?=用户手册)/g,'').replace(/_/g,' ').replace(/([A-Za-z0-9])(?=[\u4e00-\u9fff])/g,'$1 ').replace(/\s+/g,' ').trim();
const compact = (text:string) => text.toLowerCase().replace(/\.pdf|完整|操作说明|中文版|中文|用户手册|使用说明|使用手册|宇树|卡赫|v\d+(?:\.\d+)?|[\s_（）()&与和]/g,'');

/** Replace source spans before Markdown sees underscores; keep all other characters. */
export function citationText(answer:string,evidence:AnswerSource[],numbered:AnswerSource[] = []) {
  const sources:Source[]=[];let previous:Source|undefined;
  const numbers = new Set([...answer.matchAll(numberedCitation)].map(match => Number(match[1])));
  let nextNumber = 1;
  const token = (source:Source) => `\uE000${sources.indexOf(source)+1}\uE001`;
  const add=(document:string,section:string,page?:number,end?:number)=>{
    const named=evidence.filter(item=>compact(item.document || item.document_name || '')===compact(document));
    const citation=named.find(item=>{
      if(page==null) return true;
      const local=answerPageLocation(item.document || item.document_name,page).pdf;
      return local!=null && local>=(item.parent_page_start ?? item.page_start ?? Infinity) && local<=(item.parent_page_end ?? item.page_end ?? item.page_start ?? -Infinity);
    });
    page ??= citation?.page_start;
    const name=citation?.document || citation?.document_name || document;
    let source=sources.find(item=>item.document===name && item.page===page && item.end===end);
    if(!source){
      while(numbers.has(nextNumber)) nextNumber++;
      source={number:nextNumber++,document:name,section:section || citation?.section_path || '',page,end,citation};sources.push(source);
    }
    previous=source;return token(source);
  };
  const page = String.raw`(?:第\s*\d+(?:[、，,–—\-]\d+)*\s*页|页\s*\d+(?:[、，,–—\-]\d+)*)`;
  const chapter = String.raw`(?:“[^”\n]+”|"[^"\n]+"|《[^》\n]+》)`;
  const same = String.raw`(?:同上(?:手册)?|同文件|同手册|同文档|同说明)`;
  const tail = String.raw`(?:[，,]?\s*${chapter})*(?:[，,]\s*[^\n。；;*《》]{1,48}?[，,]\s*(?=${page}))?(?:[，,]?\s*[（(]?${page}[）)]?)?`;
  const savedFiles=[...new Set(evidence.map(item=>item.document || item.document_name).filter((name):name is string => !!name))].map(name=>name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'));
  const pattern = new RegExp([
    String.raw`\[[^\]\n]+第\s*\d+(?:[—–-]\d+)?\s*页[^\]\n]*\]`,
    String.raw`[（(](?:来源[：:]\s*)?(?:DOC-\d+\s*)?(?:《[^》]+》|${same}|“[^”]+”)(?:《[^》]+》|“[^”]+”|[^（）()\n])*[）)]`,
    String.raw`(?:DOC-\d+\s*)?《[^》]+》${tail}`,
    ...(savedFiles.length?[`(?:${savedFiles.join('|')})${tail}`]:[]),
    String.raw`${same}(?:[，,]\s*[^\n。；;“《]*?(?=${page}))?${tail}`,
    String.raw`(?:DOC-\d+\s*)?${chapter}[，,]?\s*${page}`
  ].join('|'),'g');
  const replaceSource=(whole:string,prose=false):string=>{
    const parts=whole.split(/[；;]/);
    if(parts.length>1)return parts.map(part=>replaceSource(part)).join('');
    const titles=[...whole.matchAll(/《([^》]+)》/g)].map(match=>match[1]);
    const pdf=evidence.map(item=>item.document || item.document_name).find(name=>name && whole.includes(name));
    const id=whole.match(/DOC-\d+/)?.[0];
    const known=titles.find(title=>evidence.some(item=>compact(item.document || item.document_name || '')===compact(title)));
    const title=known || titles.find(title=>/\.pdf|手册|说明书/.test(title) && !/^(使用手册|维修手册)$/.test(title)) || pdf;
    const sectionMatch=evidence.filter(item=>titles.some(title=>item.section_path?.replace(/[：:]$/,'')===title));
    const sectionDocument=new Set(sectionMatch.map(item=>item.document || item.document_name));
    const document=title || (id?evidence.find(item=>item.chunk_id?.startsWith(id+'-'))?.document:undefined) || previous?.document || (sectionDocument.size===1?[...sectionDocument][0]:undefined);
    const hasPage=new RegExp(page).test(whole),isSame=new RegExp(same).test(whole);
    // A book title used in prose is not automatically a source citation.
    if(!document || !title && !hasPage && !isSame || titles.length && !known && !title && !hasPage)return whole;
    const pages=[...whole.matchAll(/(?:第\s*(\d+)(?:[–—\-](\d+))?\s*页|页\s*(\d+)(?:[–—\-](\d+))?)/g)];
    const sectionBefore=(position:number)=>{
      const prefix=whole.slice(0,position),quoted=[...prefix.matchAll(/[“"]([^”"]+)[”"]|《([^》]+)》/g)].map(match=>match[1] || match[2]).filter(value=>value!==title);
      return quoted.at(-1) || prefix.match(/(?:》|同上)[，,]\s*([^第页]+)/)?.[1]?.replace(/[，,]\s*$/,'') || '';
    };
    const tokens=pages.length?pages.map(match=>add(document,sectionBefore(match.index!),Number(match[1] || match[3]),match[2] || match[4]?Number(match[2] || match[4]):undefined)):[add(document,sectionBefore(whole.length),isSame?previous?.page:undefined,isSame?previous?.end:undefined)];
    if(!prose || !title)return tokens.join('');
    // In prose, only the filename and page references are citation syntax.
    const named=whole.replace(whole.includes(`《${title}》`)?`《${title}》`:title,` ${readableSourceName(document)}`);
    let index=0;
    return pages.length?named.replace(new RegExp(String.raw`[（(]\s*${page}\s*[）)]|${page}`,'g'),()=>tokens[index++] || ''):named+tokens[0];
  };
  const text=answer.replace(pattern,(whole:string,offset:number)=>{
    const prefix=answer.slice(0,offset).split('\n').at(-1)!.replace(/[*#>]/g,'').trim();
    return replaceSource(whole,!/^[（(]/.test(whole) && !!prefix && !/(?:来源[：:]|——|[；;])$/.test(prefix));
  }).replace(numberedCitation, (_whole, label: string) => {
    const number = Number(label);
    const existing = sources.find(source => source.number === number);
    if(existing) return token(existing);
    const citation = numbered[number-1];
    const document = citation?.document || citation?.document_name;
    const source = {number,document,section:citation?.section_path || citation?.section || citation?.parent_section_path,
      page:citation?.parent_page_start ?? citation?.page_start,end:citation?.parent_page_end ?? citation?.page_end,citation};
    sources.push(source);
    return token(source);
  });
  return {text,sources};
}
const plainQuote=(text:string)=>citationText(text,[]).text.replace(sourceToken,'').replace(/[（(]同上[^）)\n]*[）)]/g,'').replace(/\*\*|__|[*_`#>]|\s/g,'');

const sourceLimit = String.raw`(?:\*\*)?(?:(?:如果|若|如)[^\n。！？]{0,80}，\s*)?(?:(?:当前|现有)\s*)?(?:说明书|手册)(?:里|中)?(?:没有|未|并未)(?:提到|提及|说明|给出|覆盖|明确)?`;
const followUp = String.raw`(?:建议|请|可)?联系[^\n。！？]*售后[^\n。！？]*`;
const trailingReference = String.raw`(?:[。！？][^\S\n]*(?:\[\d+\])+)?[。！？]?`;
const boundaryEnding = new RegExp(String.raw`(?:^|[\n。！？])[^\S\n]*(${sourceLimit}[^\n。！？]*(?:[。！？][^\S\n]*(?:\[\d+\][^\S\n]*)*)?${followUp}${trailingReference})\s*$`);

function splitBoundary(text:string) {
  const notes:string[] = [];
  let body = text.split(/\r?\n/).filter(line => {
    if(!/^(?:证据边界|资料边界|未确认条件)[：:]/.test(line.replace(/[*_#>]/g,'').trim())) return true;
    notes.push(line);
    return false;
  }).join('\n').trimEnd();
  const ending = body.match(boundaryEnding);
  if(ending) {
    notes.unshift(ending[1]);
    body = body.slice(0, body.length - ending[1].length).trimEnd();
  }
  return {body, boundary:notes.join('\n')};
}

export function answerPageLocation(document:string|undefined,page:number|undefined) {
  const range = document?.match(/第\s*\d+\s*部分[_\s-]+p(\d+)[-–—](\d+)(?=[_\s.]|$)/i);
  if (!range || page == null) return {book:page, pdf:page};
  const start = Number(range[1]), end = Number(range[2]);
  // Saved chunks use local PDF pages. Some old freeform citations already use book pages.
  if (page >= 1 && page <= end - start + 1) return {book:start + page - 1, pdf:page};
  if (page >= start && page <= end) return {book:page, pdf:page - start + 1};
  return {};
}

function citationLocation(source:Source):Citation {
  const {document='',section='',page,end,citation}=source;
  const start = answerPageLocation(document,page), last = answerPageLocation(document,end ?? page);
  return {
    document_id:citation?.document_id || '', document, section_path:section,
    chunk_id:citation?.chunk_id || '', score:citation?.score ?? 0,
    page_start:start.pdf, page_end:last.pdf, book_page_start:start.book, book_page_end:last.book,
    content_preview:citation?.content || citation?.content_preview || citation?.chunk_text || '', savedEvidence:true
  };
}

export function StructuredAnswer({text:answer,evidence=[],numberedEvidence,reference=false,streaming=false,points=[],side='before',onOpenCitation}:{
  text:string; evidence?:AnswerSource[]; numberedEvidence?:AnswerSource[]; reference?:boolean; streaming?:boolean;
  points?:Point[]; side?:'before'|'after'; onOpenCitation?:(citation:Citation)=>void;
}) {
  const [citation,setCitation]=useState<Citation|null>(null);
  const openCitation=onOpenCitation || setCitation;
  const [expanded,setExpanded] = useState(false), [overflow,setOverflow] = useState(false);
  const limit = useRef<HTMLDivElement>(null), contentId = useId();
  useLayoutEffect(() => {
    const element = limit.current;
    if (!element || expanded || streaming) return;
    const check = () => setOverflow(element.scrollHeight > element.clientHeight + 1);
    check();
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(check);
    observer.observe(element);
    if (element.firstElementChild) observer.observe(element.firstElementChild);
    return () => observer.disconnect();
  }, [answer, expanded, streaming]);

  const readable = reference ? answer : answerCitationDisplay(answer,numberedEvidence || []).text;
  const {body,boundary} = reference ? {body:readable,boundary:''} : splitBoundary(readable);
  const display=citationText(boundary ? `${body}\n\uE002${boundary}` : body,evidence,numberedEvidence);
  const [mainText,boundaryText] = display.text.split('\uE002');
  const hasBody = !!mainText.trim();
  const tree=answerMarkup(mainText,reference ? 'reference' : 'model');
  if(!display.sources.length && !reference) for(const source of numberedEvidence || []) {
    const document = source.document || source.document_name;
    if(document && !display.sources.some(item=>item.document===document && item.page===source.page_start)) {
      display.sources.push({number:display.sources.length+1,document,section:source.section_path || source.section,page:source.page_start,end:source.page_end,citation:source});
    }
  }
  const flatten=(node:ReactNode):string=>typeof node==='string' || typeof node==='number'?String(node):isValidElement<{children?:ReactNode}>(node)?flatten(node.props.children):Array.isArray(node)?node.map(flatten).join(''):'';
  const text=flatten(tree),indexes:number[]=[],characters:string[]=[];
  // Map normalized visible characters back to React text offsets, across bold/list nodes.
  for(let i=0;i<text.length;i++){
    if(text[i]==='\uE000'){const end=text.indexOf('\uE001',i);if(end>=0){i=end;continue;}}
    if(!/\s|[*_`#>]/.test(text[i])){characters.push(text[i]);indexes.push(i);}
  }
  const normalized=characters.join(''),ranges:{start:number;end:number;point:Point}[]=[];
  for(const point of points){
    if(!(side==='after'?point.after:point.before) || !(point.fresh && side==='after' || point.before && point.after))continue;
    for(const quote of side==='after'?point.afterQuotes:point.beforeQuotes){
      const needle=plainQuote(quote),start=needle?normalized.indexOf(needle):-1;
      if(start<0)continue;
      const range={start:indexes[start],end:indexes[start+needle.length-1]+1,point};
      if(!ranges.some(item=>item.start<range.end && range.start<item.end))ranges.push(range);
    }
  }
  let offset=0;
  function decorate(node:ReactNode):ReactNode {
    if(typeof node==='string' || typeof node==='number'){
      const value=String(node),start=offset;offset+=value.length;
      const cuts=new Set([0,value.length]);
      for(const range of ranges){if(range.start>start && range.start<offset)cuts.add(range.start-start);if(range.end>start && range.end<offset)cuts.add(range.end-start);}
      for(const match of value.matchAll(sourceToken)){cuts.add(match.index!);cuts.add(match.index!+match[0].length);}
      const positions=[...cuts].sort((a,b)=>a-b);
      return positions.slice(0,-1).map((position,index)=>{
        const part=value.slice(position,positions[index+1]),citation=part.match(/^\uE000(\d+)\uE001$/);
        if(citation){
          const source = display.sources[Number(citation[1])-1];
          if(!source?.document) return <sup className="answer-citation-missing" key={index} title="引用来源未保存" aria-label={`引用 ${source?.number}，来源未保存`}>{source?.number}</sup>;
          return <button type="button" className="answer-citation" key={index} aria-label={`查看引用 ${source.number}`} onClick={()=>openCitation(citationLocation(source))}>{source.number}</button>;
        }
        const range=ranges.find(item=>start+position>=item.start && start+position<item.end);
        if(!range)return part;
        const content=<>{start+position===range.start && <span className="comparison-pin">{range.point.number}</span>}{part}</>;
        return range.point.fresh && side==='after'?<mark key={index}>{content}</mark>:<span className="comparison-met" key={index}>{content}</span>;
      });
    }
    if(Array.isArray(node))return Children.map(node,decorate);
    if(!isValidElement<{children?:ReactNode;className?:string}>(node))return node;
    return cloneElement(node,{},decorate(node.props.children));
  }
  const knownSources = display.sources.filter(source => source.document).sort((a,b) => a.number-b.number);
  const decoratedBody = decorate(tree);
  // Boundary text shares citation numbering but stays out of comparison quote matching.
  offset = text.length;
  return <div className="structured-answer">
    {hasBody && <div className="comparison-body">
      <div id={contentId} ref={limit} className={!expanded && !streaming ? `answer-preview${overflow ? ' is-overflowing' : ''}` : undefined} onFocusCapture={event => {
        if (!expanded && overflow && (event.target as HTMLElement).getBoundingClientRect().bottom > event.currentTarget.getBoundingClientRect().bottom) setExpanded(true);
      }}>{decoratedBody}</div>
      {!streaming && (overflow || expanded) && <button type="button" className="answer-toggle" aria-expanded={expanded} aria-controls={contentId} onClick={() => setExpanded(value => !value)}>{expanded ? '收起回答' : '展开回答'}</button>}
    </div>}
    {boundaryText && <aside className="answer-boundary" aria-label="资料边界"><strong>资料边界</strong>{decorate(answerMarkup(boundaryText, hasBody ? undefined : 'model'))}</aside>}
    {!!knownSources.length && <footer className="comparison-sources"><div className="comparison-source-title">引用来源</div><ol>{knownSources.map(source=>{
      const location = citationLocation(source);
      const page = location.book_page_start, end = location.book_page_end;
      return <li key={source.number}><sup className="comparison-cite">{source.number}</sup><button type="button" onClick={()=>openCitation(location)}>
        {readableSourceName(source.document!)}{page!=null && ` · 第 ${page}${end!=null && end!==page?`–${end}`:''} 页`}{!source.citation && '（原文未保存）'}
      </button></li>;
    })}</ol></footer>}
    {!onOpenCitation && citation && <CitationViewer citation={citation} onClose={()=>setCitation(null)}/>}
  </div>;
}
