import {Children,cloneElement,isValidElement,useId,type ReactNode} from 'react';
import {answerMarkup} from './AnswerMarkup';
import {citationText,presentAnswer,readableSourceName,circle,sourceToken} from './answerPresentation';
import type {Point} from './comparisonData';
import type {Citation} from '../types';
import './ModelAnswer.css';

const plainQuote=(text:string)=>citationText(text,[]).text.replace(sourceToken,'').replace(/[（(]同上[^）)\n]*[）)]/g,'').replace(/\*\*|__|[*_`#>]|\s/g,'');

export function ModelAnswer({text:raw,final=[],points=[],side,onOpenCitation}:{text:string;final?:any[];points?:Point[];side?:'before'|'after';onOpenCitation?:(citation:Citation)=>void}) {
  const id=useId();
  const display=presentAnswer(raw,Array.isArray(final)?final:[]),tree=answerMarkup(display.text);
  const openSource=(source:typeof display.sources[number])=>onOpenCitation?.({...source.citation,document:source.document,page_start:source.page ?? source.citation?.page_start,page_end:source.end ?? source.page ?? source.citation?.page_end,content_preview:source.citation?.content || source.citation?.content_preview || source.original?.join('\n') || '来源片段未定位',savedEvidence:true} as Citation);
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
        if(citation)return <sup className="comparison-cite" key={index}><a href={`#${id}-source-${citation[1]}`} onClick={event=>{event.preventDefault();const detail=document.getElementById(`${id}-source-${citation[1]}`) as HTMLDetailsElement|null;if(detail){detail.open=true;detail.scrollIntoView?.({block:'nearest'});}}}>{circle(Number(citation[1]))}</a></sup>;
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
  return <div className="model-answer"><div className="model-answer-body comparison-body">{decorate(tree)}</div>
    {display.sources.length>0 && <footer className="answer-sources comparison-sources"><div className="comparison-source-title">引用来源</div><ol>{display.sources.map(source=><li className="answer-source" key={source.number}><details id={`${id}-source-${source.number}`}><summary onClick={event=>{if(onOpenCitation){event.preventDefault();openSource(source);}}}><sup className="comparison-cite">{circle(source.number)}</sup>{readableSourceName(source.document)}{source.page!=null && ` · 第 ${source.page}${source.end && source.end!==source.page?`–${source.end}`:''} 页`}</summary><div className="answer-source-fragment">{source.original?.map((text,index)=><p key={index}>{text}</p>)}<p>{source.citation?.content || source.citation?.content_preview || '来源片段未定位'}</p>{onOpenCitation && <button className="secondary small" onClick={()=>openSource(source)}>查看来源</button>}</div></details></li>)}</ol></footer>}
    {display.notes.length>0 && <details className="answer-notes"><summary>回答说明</summary>{display.notes.map((text,index)=><div key={index}>{answerMarkup(text)}</div>)}</details>}
    <details className="answer-original"><summary>查看原文</summary><pre className="technical-record">{raw}</pre></details>
  </div>;
}
