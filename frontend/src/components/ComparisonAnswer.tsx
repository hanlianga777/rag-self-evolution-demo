import {Children, cloneElement, isValidElement, type ReactNode} from 'react';
import {answerMarkup} from './CaseAnswer';
import {finalEvidence, type Point} from './comparisonData';
import type {Citation} from '../types';

type Source = {number:number; document:string; section:string; page?:number; end?:number; citation?:any};
const sourceToken = /\uE000(\d+)\uE001/g;
const readable = (text:string) => text.replace(/\.pdf$/i,'').replace(/_/g,' ');
const compact = (text:string) => text.toLowerCase().replace(/\.pdf|完整|操作说明|中文版|中文|用户手册|使用说明|使用手册|宇树|卡赫|v\d+(?:\.\d+)?|[\s_（）()&与和]/g,'');

/** Replace source spans before Markdown sees underscores; keep all other characters. */
export function citationText(answer:string,evidence:any[]) {
  const sources:Source[]=[];let previous:Source|undefined;
  const add=(document:string,section:string,page?:number,end?:number)=>{
    const named=evidence.filter(item=>compact(item.document || item.document_name || '')===compact(document));
    const citation=named.find(item=>page==null || page>=(item.page_start ?? item.parent_page_start) && page<=(item.page_end ?? item.page_start ?? item.parent_page_end)) || (page==null?named[0]:undefined);
    page ??= citation?.page_start;
    const name=citation?.document || citation?.document_name || document;
    let source=sources.find(item=>item.document===name && item.page===page && item.end===end);
    if(!source){source={number:sources.length+1,document:name,section:section || citation?.section_path || '',page,end,citation};sources.push(source);}
    previous=source;return `\uE000${source.number}\uE001`;
  };
  const page = String.raw`(?:第\s*\d+(?:[、，,–—\-]\d+)*\s*页|页\s*\d+(?:[、，,–—\-]\d+)*)`;
  const chapter = String.raw`(?:“[^”\n]+”|"[^"\n]+"|《[^》\n]+》)`;
  const same = String.raw`(?:同上(?:手册)?|同文件|同手册|同文档|同说明)`;
  const tail = String.raw`(?:[，,]?\s*${chapter})*(?:[，,]\s*[^\n。；;*《》]{1,48}?[，,]\s*(?=${page}))?(?:[，,]?\s*[（(]?${page}[）)]?)?`;
  const savedFiles=[...new Set<string>(evidence.map(item=>item.document || item.document_name).filter(Boolean))].map(name=>name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'));
  const pattern = new RegExp([
    String.raw`[（(](?:来源[：:]\s*)?(?:DOC-\d+\s*)?(?:《[^》]+》|${same}|“[^”]+”)(?:《[^》]+》|“[^”]+”|[^（）()\n])*[）)]`,
    String.raw`(?:DOC-\d+\s*)?《[^》]+》${tail}`,
    ...(savedFiles.length?[`(?:${savedFiles.join('|')})${tail}`]:[]),
    String.raw`${same}(?:[，,]\s*[^\n。；;“《]*?(?=${page}))?${tail}`,
    String.raw`(?:DOC-\d+\s*)?${chapter}[，,]?\s*${page}`
  ].join('|'),'g');
  const replaceSource=(whole:string):string=>{
    const parts=whole.split(/[；;]/);
    if(parts.length>1)return parts.map(replaceSource).join('');
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
    if(!pages.length)return add(document,sectionBefore(whole.length),isSame?previous?.page:undefined,isSame?previous?.end:undefined);
    return pages.map(match=>add(document,sectionBefore(match.index!),Number(match[1] || match[3]),match[2] || match[4]?Number(match[2] || match[4]):undefined)).join('');
  };
  const text=answer.replace(pattern,replaceSource);
  return {text,sources};
}
const plainQuote=(text:string)=>citationText(text,[]).text.replace(sourceToken,'').replace(/[（(]同上[^）)\n]*[）)]/g,'').replace(/\*\*|__|[*_`#>]|\s/g,'');

export function ComparisonAnswer({row,points,side,onOpenCitation}:{row:any;points:Point[];side:'before'|'after';onOpenCitation:(citation:Citation)=>void}) {
  const final=finalEvidence(row),trace=row.programmatic_metrics?.retrieval_trace;
  const evidence=[...(final || []),...(row.retrieved_chunks || []),...(trace?.candidates || []),...(trace?.reranked || [])];
  const display=citationText(row.model_answer || '回答未保存',evidence),tree=answerMarkup(display.text);
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
        if(citation)return <sup className="comparison-cite" key={index}>{citation[1]}</sup>;
        const range=ranges.find(item=>start+position>=item.start && start+position<item.end);
        if(!range)return part;
        const content=<>{start+position===range.start && <span className="comparison-pin">{range.point.number}</span>}{part}</>;
        return range.point.fresh && side==='after'?<mark key={index}>{content}</mark>:<span className="comparison-met" key={index}>{content}</span>;
      });
    }
    if(Array.isArray(node))return Children.map(node,decorate);
    if(!isValidElement<{children?:ReactNode;className?:string}>(node))return node;
    const note=node.type==='p' && /^(?:证据边界|未确认条件)[：:]/.test(flatten(node).replace(/\s/g,''));
    return cloneElement(node,{...(note?{className:'comparison-note'}:{})},decorate(node.props.children));
  }
  return <><div className="comparison-body">{decorate(tree)}</div><footer className="comparison-sources"><div className="comparison-source-title">引用来源</div><ol>{display.sources.map(source=><li key={source.number}><sup className="comparison-cite">{source.number}</sup>{source.citation?<button onClick={()=>onOpenCitation({...source.citation,content_preview:source.citation.content || source.citation.content_preview,savedEvidence:true} as Citation)}>{readable(source.document)}{source.section && `，${source.section}`}{source.page!=null && `，第 ${source.page}${source.end?`–${source.end}`:''} 页`}</button>:<span>{readable(source.document)}{source.section && `，${source.section}`}{source.page!=null && `，第 ${source.page}${source.end?`–${source.end}`:''} 页`}（原文未保存）</span>}</li>)}</ol><div className="comparison-more">检索到 {final?.length ?? '未知'} 段证据，回答引用 {display.sources.length} 段</div></footer></>;
}
