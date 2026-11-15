export type Source = {number:number; document:string; section:string; page?:number; end?:number; citation?:any; original?:string[]; nativeIndex?:number};
export const sourceToken = /\uE000(\d+)\uE001/g;
export const readableSourceName = (text:string) => text.replace(/\.pdf$/i,'').replace(/^(?:卡赫|宇树)[_\s]*/,'').replace(/[_（(]?中文版[）)]?|完整|四足机器人(?=用户手册)/g,'').replace(/_/g,' ').replace(/([A-Za-z0-9])(?=[\u4e00-\u9fff])/g,'$1 ').replace(/\s+/g,' ').trim();
const compact = (text:string) => text.toLowerCase().replace(/\.pdf|完整|操作说明|中文版|中文|用户手册|使用说明|使用手册|宇树|卡赫|v\d+(?:\.\d+)?|[\s_（）()&与和]/g,'');

/** Replace source spans before Markdown sees underscores; keep all other characters. */
export function citationText(answer:string,evidence:any[]) {
  const sources:Source[]=[];let previous:Source|undefined;let original='';let unverified=0;
  const reserved=new Set([...answer.matchAll(/\[(\d+)\](?!\()/g)].map(match=>Number(match[1])).filter(number=>evidence[number-1]));
  const nextNumber=()=>{let number=1;while(reserved.has(number) || sources.some(source=>source.number===number))number++;return number;};
  const add=(document:string,section:string,page?:number,end?:number)=>{
    const named=evidence.filter(item=>compact(item.document || item.document_name || '')===compact(document));
    const located=named.filter(item=>page==null || page>=(item.parent_page_start ?? item.page_start) && page<=(item.parent_page_end ?? item.page_end ?? item.parent_page_start ?? item.page_start));
    const identities=new Set(located.map(item=>JSON.stringify([item.document || item.document_name,item.chunk_id,item.parent_chunk_id,item.page_start,item.page_end,item.parent_page_start,item.parent_page_end,item.content || item.content_preview])));
    const citation=identities.size===1?located[0]:undefined;
    page ??= citation?.page_start;
    const name=citation?.document || citation?.document_name || document;
    let source=sources.find(item=>item.document===name && item.page===page && item.end===end);
    if(!source){source={number:nextNumber(),document:name,section:section || citation?.section_path || '',page,end,citation};sources.push(source);}
    if(original){source.original ??=[];if(!source.original.includes(original))source.original.push(original);}
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
  const replaceSource=(whole:string,prose=false,inherit=false):string=>{
    original=whole;
    const parts=whole.split(/[；;]/);
    if(parts.length>1)return parts.map((part,index)=>replaceSource(part,false,index>0)).join('');
    const titles=[...whole.matchAll(/《([^》]+)》/g)].map(match=>match[1]);
    const pdf=evidence.map(item=>item.document || item.document_name).find(name=>name && whole.includes(name));
    const id=whole.match(/DOC-\d+/)?.[0];
    const known=titles.find(title=>evidence.some(item=>compact(item.document || item.document_name || '')===compact(title)));
    const title=known || titles.find(title=>/\.pdf|手册|说明书/.test(title) && !/^(使用手册|维修手册)$/.test(title)) || pdf;
    const sectionMatch=evidence.filter(item=>titles.some(title=>item.section_path?.replace(/[：:]$/,'')===title));
    const sectionDocument=new Set(sectionMatch.map(item=>item.document || item.document_name));
    const document=title || (id?evidence.find(item=>item.chunk_id?.startsWith(id+'-'))?.document:undefined) || (inherit || new RegExp(same).test(whole)?previous?.document:undefined) || (sectionDocument.size===1?[...sectionDocument][0]:undefined);
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
  let text=answer.replace(pattern,(whole:string,offset:number)=>{
    const prefix=answer.slice(0,offset).split('\n').at(-1)!.replace(/[*#>]/g,'').trim();
    return replaceSource(whole,!/^[（(]/.test(whole) && !!prefix && !/(?:来源[：:]|——|[；;])$/.test(prefix));
  });
  // Native generation-vnext-3 indices refer only to the saved final context.
  text=text.replace(/\[(\d+)\](?!\()|[\[【](DOC-\d+-(?:V\d+-)?[CP]-\d+)(?:[|｜][^\]】\n]*)?[\]】]/g,(whole,index:string,id:string)=>{
    const matches=id?evidence.filter(item=>[item.chunk_id,item.parent_chunk_id,...(item.matched_child_ids || [])].includes(id)):[];
    const item=id?(matches.length===1?matches[0]:undefined):evidence[Number(index)-1];
    if(!item?.document && !item?.document_name){unverified++;return '[引用来源未核验]';}
    original=whole;
    const parent=!!index || id && id!==item.chunk_id;
    const page=parent?item.parent_page_start ?? item.page_start:item.page_start;
    const end=parent?item.parent_page_end ?? item.page_end:item.page_end;
    if(index){
      const number=Number(index);
      let source=sources.find(source=>source.nativeIndex===number);
      if(!source){source={number,nativeIndex:number,document:item.document || item.document_name,section:item.section_path || '',page,end,citation:item,original:[whole]};sources.push(source);}
      return `\uE000${number}\uE001`;
    }
    const token=add(item.document || item.document_name,'',page,end);
    previous!.citation=item;
    return token;
  });
  return {text,sources,unverified};
}

export const circle=(number:number)=>number>=1 && number<=20?String.fromCodePoint(0x2460+number-1):`(${number})`;

/** Display rules live here; no rewriting, rescoring or live knowledge-base lookup. */
export function presentAnswer(raw:string,final:any[]) {
  const lines=raw.replace(/\r\n?/g,'\n').replace(/(<\/(?:p|div|h[1-6])>)/gi,'$1\n').split('\n'),body:string[]=[],notes:string[]=[];
  let note:string[]|null=null;
  const flush=()=>{if(note?.length)notes.push(note.join('\n'));note=null;};
  for(const line of lines){
    const plain=line.replace(/<[^>]*>/g,'').replace(/[*_#>]/g,'').trim();
    // "注意：" is also the native safety-warning prefix. Never fold it generally.
    const meta=/^(?:证据边界|未确认条件|回答说明|说明|依据)[：:]|^注意[：:]\s*以上(?:信息|内容|回答)/.test(plain) || /^(?:证据边界|未确认条件|回答说明)[：:]?$/.test(plain);
    if(meta){flush();note=[line];}
    else if(note && !plain){flush();body.push(line);}
    else if(note && /^(?:#{1,6}\s|\d+[.、)）]\s*|注意[：:]|结论[：:])/.test(line.trim().replace(/<[^>]*>/g,''))){flush();body.push(line);}
    else if(note)note.push(line);
    else body.push(line);
  }
  flush();
  // Only an explicitly labeled conclusion may move ahead of steps; never infer one.
  const conclusion=body.findIndex(line=>/^(?:#{1,6}\s*)?(?:\*\*)?结论(?:[：:]|\*\*|$)/.test(line.replace(/<[^>]*>/g,'').trim()));
  if(conclusion>0){
    let end=conclusion+1;
    if(!body[conclusion].replace(/<[^>]*>/g,'').replace(/[*#：:\s]/g,'').replace(/^结论/,'').length){while(end<body.length && body[end].trim() && !/^\s*(?:\d+[.、)）]|#{1,6}\s|注意[：:])/.test(body[end]))end++;}
    body.unshift(...body.splice(conclusion,end-conclusion));
  }
  const display=citationText(body.join('\n'),final);
  // Only move explicitly labeled verbatim quotations attached to an identified source.
  display.text=display.text.replace(/(?:来源[：:]\s*)?(\uE000(\d+)\uE001)(?:[，,：:]?\s*(?:原文|原文引用|原文片段)[：:]\s*(?:“[^”]+”|「[^」]+」|"[^"\n]+"))?/g,(whole,token:string,number:string)=>{
    const source=display.sources.find(source=>source.number===Number(number));
    if(source && whole!==token){source.original ??=[];source.original.push(whole.replace(sourceToken,''));}
    return token;
  });
  const moveQuote=(whole:string,token:string,number:string)=>{
    const source=display.sources.find(source=>source.number===Number(number));
    if(!source)return whole;
    source.original ??=[];source.original.push(whole.replace(sourceToken,''));return token;
  };
  display.text=display.text.replace(/(?:原文|手册原文|原文引用|原文片段)[：:]\s*(“[^”]+”|「[^」]+」|"[^"\n]+")\s*([（(]?\uE000(\d+)\uE001[）)]?)/g,(whole,quote:string,token:string,number:string)=>moveQuote(whole,token,number));
  // Unlabeled quotation moves only when a long exact fragment occurs in its saved source.
  display.text=display.text.replace(/“([^”\n]{40,})”\s*(\uE000(\d+)\uE001)/g,(whole,quote:string,token:string,number:string)=>{
    const source=display.sources.find(source=>source.number===Number(number));
    return (source?.citation?.content || source?.citation?.content_preview || '').includes(quote)?moveQuote(whole,token,number):whole;
  });
  if(display.unverified)notes.push('引用来源未核验：保存记录中没有唯一对应的文档和原文。');
  return {...display,notes};
}
