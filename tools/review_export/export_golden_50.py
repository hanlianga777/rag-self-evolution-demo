"""Local-only, read-only Golden review export. No app startup, models or DB writes."""
from __future__ import annotations
import contextlib, hashlib, json, re, sqlite3, subprocess, sys, zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from app.governance import GovernanceStore
from app.corpus import CorpusStore, INDEX_DIR, DOCUMENTS_DIR, UPLOADS_DIR, current_manifest, manifest_identity

OUT=ROOT/'review_exports/GOLDEN_50_FULL_REVIEW_20261026'
DB=ROOT/'backend/data/demo.db'
RUN_ID='GGEN-GCONTENT-10c6ab67b1ef279d70b4f361'
CONTENT='GCONTENT-10c6ab67b1ef279d70b4f361'
NOW=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def dump(v): return json.dumps(v,ensure_ascii=False,indent=2)
def write(name,value):
    path=OUT/name;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(value if isinstance(value,str) else dump(value)+'\n',encoding='utf-8')
def block(v,lang='json'): return '\n```'+lang+'\n'+(v if isinstance(v,str) else dump(v))+'\n```\n'
def table_cell(v): return str(v if v is not None else '未记录').replace('|','\\|').replace('\n','<br>')
def text(v): return '未记录' if v is None else v if isinstance(v,str) else dump(v)
def decoded(row):
    d=dict(row)
    for k,v in list(d.items()):
        if k.endswith('_json') and isinstance(v,str): d[k[:-5]]=json.loads(v)
    return d

# A single SQLite read transaction binds all rows to one snapshot. All attempted
# mutations fail at SQLite mode=ro/query_only; GovernanceStore.__init__ is not run.
conn=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)
conn.row_factory=sqlite3.Row
conn.execute('PRAGMA query_only=ON');conn.execute('BEGIN')
assert conn.execute('PRAGMA query_only').fetchone()[0]==1
before_hash=sha(DB)
def logical_hash(c):
    h=hashlib.sha256()
    for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        h.update(r[0].encode())
        for row in c.execute('SELECT * FROM "'+r[0].replace('"','""')+'" ORDER BY rowid'):
            h.update(json.dumps(tuple(row),ensure_ascii=False,default=str).encode())
    return h.hexdigest()
before_logical=logical_hash(conn)
class ReadOnlyGovernance(GovernanceStore):
    @contextlib.contextmanager
    def connection(self): yield conn
s=ReadOnlyGovernance.__new__(ReadOnlyGovernance);s.database_path=DB
run=s.generation_run(RUN_ID)
assert run and run['artifacts']['hard_validation']['content_identity']==CONTENT
ids=run['question_ids'];assert len(ids)==len(set(ids))==50
items=sorted([s.question(k) for k in ids],key=lambda q:q['raw']['coverage_slot'])
assert [q['raw']['coverage_slot'] for q in items]==[f'Q{i:02}' for i in range(1,51)]
assert Counter(q['test_category'] for q in items)=={'positive':20,'ablation':10,'negative':20}
rows={r['id']:r for r in s.candidate_rows(ids)}
corpus=CorpusStore();chunks={c['chunk_id']:c for c in corpus.chunks()}
parents={p['parent_chunk_id'] if 'parent_chunk_id' in p else p['chunk_id']:p for p in json.loads((INDEX_DIR/'parents.json').read_text())}
docs={d['id']:d for d in corpus.documents()}
fulltext=json.loads((INDEX_DIR/'full_text.json').read_text())
page_map={(p['document_id'],p['page']):p for p in fulltext['pages']}
corpus_identity=manifest_identity(current_manifest())
assets=[INDEX_DIR/'manifest.json',INDEX_DIR/'chunks.json',INDEX_DIR/'parents.json',INDEX_DIR/'full_text.json']
source_hashes={str(p):sha(p) for p in assets}
for d in docs.values():
    p=(UPLOADS_DIR if d.get('storage')=='uploads' else DOCUMENTS_DIR)/d['name']
    if p.exists(): source_hashes[str(p)]=sha(p)
revisions=[decoded(r) for r in conn.execute('SELECT * FROM candidate_revision_runs ORDER BY id')]
state=run['artifacts']['hard_validation']['quality_rerun']
assert state['status']!='running'
if OUT.exists() and any(OUT.iterdir()): raise SystemExit('Refusing to overwrite existing export')
OUT.mkdir(parents=True,exist_ok=True)

# Relevant source pages only; neither whole PDFs nor credentials/configuration files are copied.
pdf_cache={};pdf_results={}
def page_record(docid,page):
    key=(docid,page)
    if key in pdf_results:return pdf_results[key]
    d=docs.get(docid,{})
    p=(UPLOADS_DIR if d.get('storage')=='uploads' else DOCUMENTS_DIR)/d.get('name','')
    result={'document_id':docid,'pdf_page_number_1_based':page,'source_file':str(p),
            'persisted_canonical_page':page_map.get(key),
            'page_number_basis':'PDF物理页序，印刷页码未自动推断；未做人工视觉或语义确认'}
    try:
        import fitz
        if docid not in pdf_cache:pdf_cache[docid]=fitz.open(p)
        f=pdf_cache[docid];pg=f[page-1]
        native=pg.get_text()
        result.update(pdf_page_count=len(f),pdf_page_exists=True,pdf_native_text=native,
                      pdf_native_text_status='已直接读取原始PDF文本层；不代表逐句语义审核' if native.strip() else '原始PDF该页无可用文本层；仅有既存MinerU解析正文，待人工对照')
    except Exception as e:
        result.update(pdf_page_exists=None,pdf_native_text_status='未能直接读取：'+type(e).__name__)
    pdf_results[key]=result;return result

def history(table,key): return [decoded(r) for r in conn.execute('SELECT * FROM '+table+' WHERE question_id=? ORDER BY id DESC',(key,))]
def all_cp_requests(cp,where='current'):
    for k,r in cp.get('provider_requests',{}).items():yield {'checkpoint_scope':where,'request_key':k,**r}
    for i,old in enumerate(cp.get('prior_content_checkpoints',[])):
        yield from all_cp_requests(old,where+f'/prior_content_checkpoints/{i}')
    for i,h in enumerate(cp.get('manual_resume_history',[])):
        for k,r in h.get('provider_requests',{}).items():yield {'checkpoint_scope':where+f'/manual_resume_history/{i}','request_key':k,**r}

def raw_qc_matches(qc,requests):
    matches=[]
    for r in requests:
        if r.get('phase')!='qc':continue
        result=r.get('result',{})
        content=result.get('content') if isinstance(result,dict) else None
        if not isinstance(content,str):continue
        try:v=json.loads(content)
        except (ValueError,TypeError):continue
        actual=qc['result']
        if isinstance(v,dict) and all(v.get(k)==actual.get(k) for k in ('score','reason','issues','content_review')):
            matches.append({'request_key':r['request_key'],'checkpoint_scope':r['checkpoint_scope'],'raw_provider_content':content,'provider_result':result,'attempts':r.get('attempts',[])})
    return matches

def related_ids(value):
    found=set()
    def visit(v):
        if isinstance(v,str):found.update(re.findall(r'DOC-\d+-C-\d+',v))
        elif isinstance(v,dict):
            for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(value);return found

def stage_list(trace,key):
    value=trace.get(key,[])
    return value if isinstance(value,list) else []

def chunk_members(stage):
    return {v for h in stage for v in [h.get('chunk_id'),*h.get('matched_child_ids',[])] if v}

def render_hits(hits):
    if not hits:return '未记录或空列表；详见原始Trace。\n'
    out=[]
    for n,h in enumerate(hits,1):
        out.append(f"#### {n}. {h.get('chunk_id','未记录ID')}\n\n记录排名：{h.get('rank','未单独记录，按列表次序展示')}；分数：{h.get('score','未记录')}；重排分：{h.get('rerank_score','未记录')}。\n")
        out.append(block({k:v for k,v in h.items() if k not in {'content','content_preview','child_content'}}))
        out.append('实际记录文本：\n'+block(h.get('content','未持久化文本'),'text'))
        if 'child_content' in h:out.append('实际记录Child正文：\n'+block(h['child_content'],'text'))
    return '\n'.join(out)

def render_checks(req,review):
    results={x.get('id'):x for x in review.get('checks',[])}
    out=[]
    for kind,title in [('required_checks','必答'),('conditional_checks','条件必答')]:
        out.append('### '+title+'检查点\n')
        if not req.get(kind):out.append('无已持久化条目。\n')
        for check in req.get(kind,[]):
            out.append('#### '+check['id']+'\n\n'+check.get('requirement','未记录要求')+'\n')
            out.append('检查点原始合同（含触发条件、依据和来源）：\n'+block(check))
            r=results.get(check['id'])
            out.append('当前QC逐项判断（适用性、满足性、理由和原文引用）：\n'+block(r if r is not None else {'missing':'未持久化对应逐项判断'}))
    return '\n'.join(out)

exports=[];all_evidence={};gaps=[];missing=[];checks=[]
for item in items:
    qid=item['raw']['coverage_slot'];key=item['id'];raw=item['raw'];req=raw.get('business_requirements',{})
    ph=history('probe_results',key);qh=history('qc_results',key);ah=history('question_quality_audits',key);rh=history('review_events',key)
    approvals=[dict(r) for r in conn.execute('SELECT * FROM approvals WHERE target_id=? ORDER BY id',(key,))]
    assert ph and qh and ah
    p=ph[0]['result'];qc=qh[0]['result'];pd=p.get('probe_details',{});trace=pd.get('retrieval_trace',{})
    _,identity=s.capture_quality(key)
    assert {k:v for k,v in p['execution_identity'].items() if k!='probe_id'}=={k:v for k,v in identity.items() if k!='probe_id'},qid+' probe identity'
    assert qc['execution_identity']==identity,qid+' qc identity'
    assert ah[0]['content_hash']==identity['content_hash'],qid+' audit identity'
    assert qc['score']>=85 and p['status']=='passed' and all(ah[0]['audit']['checks'].values())
    cp=state.get('checkpoints',{}).get(key,{})
    requests=list(all_cp_requests(cp));qcmatches=raw_qc_matches(qh[0],requests)
    formal=list(dict.fromkeys(c for e in item['evidence'] for c in e.get('source_chunk_ids',[])))
    assert item['test_category']!='negative' or formal==[],qid+' negative evidence'
    req_ids=list(dict.fromkeys(x['chunk_id'] for x in req.get('sources',[])))
    used_ids=set(formal)|set(req_ids)|related_ids([p,qc,raw.get('coverage_anchor_chunk_ids'),raw.get('source_chunk_ids')])
    # Include historical/current QC source chunks and checkpoints referenced in real responses.
    used_ids |= related_ids([ph,qh])
    evidence=[]
    links={}
    for kind in ['required_checks','conditional_checks']:
        for check in req.get(kind,[]):
            for cid in check.get('source_chunk_ids',[]):links.setdefault(cid,[]).append({'kind':kind,'id':check['id'],'requirement':check.get('requirement'),'condition':check.get('condition',check.get('when')),'persisted_check':check})
    candidates=stage_list(trace,'candidates');reranked=stage_list(trace,'reranked');final=stage_list(trace,'final')
    sets=[chunk_members(x) for x in [candidates,reranked,final]]
    cov=pd.get('evidence_coverage',{})
    coverage_ids=cov.get('required_chunk_ids',formal)
    missing_final=[cid for cid in coverage_ids if cid not in sets[2]]
    gap_rows=[]
    for cid in missing_final:
        classification='候选列表未包含该指定Chunk' if cid not in sets[0] else '候选存在，但持久化重排列表未包含' if cid not in sets[1] else '重排列表包含，但Final未包含'
        if not candidates:classification='待独立分析：未保存候选列表'
        elif cid in sets[0] and not reranked:classification='待独立分析：未保存重排列表'
        refs=links.get(cid,[])
        gap_rows.append({'chunk_id':cid,'persisted_check_links':refs,'check_level':'、'.join(sorted({r['kind'] for r in refs})) if refs else '待独立分析：未持久化该Chunk与检查点的明确关联',
                         'candidate_present':cid in sets[0],'reranked_present':cid in sets[1],'final_present':False,
                         'observed_stage_loss':classification+'（仅ID成员比较，不推断语义原因）',
                         'equivalent_facts_in_final':'待独立分析：未持久化替代Chunk与该缺失事实的等价判定',
                         'semantic_impact':'待独立分析；指定Chunk缺失本身不证明RAG回答错误或Golden答案错误'})
    source_byid={x['chunk_id']:x for x in req.get('sources',[])}
    for cid in sorted(used_ids):
        ch=chunks.get(cid)
        if ch is None:missing.append({'qid':qid,'field':'canonical_chunk','id':cid});continue
        role='标准答案证据' if cid in formal else '负向背景材料，不是不存在答案的支持证据' if item['test_category']=='negative' and cid in req_ids else '补充规范/参考材料' if cid in req_ids else '实际检索/历史质量记录引用，非指定Golden Evidence'
        source=source_byid.get(cid,{})
        pages=list(range(ch['page_start'],ch['page_end']+1))
        rec={'chunk_id':cid,'role':role,'canonical_chunk':ch,'governed_source_record':source or None,
             'document_metadata':docs.get(ch['document_id']), 'version':source.get('version'),'version_status':source.get('version_status','未提供结构化版本；不从封面推断'),
             'required_conditional_links':links.get(cid,[]),'answer_fact_links':[x for x in req.get('answer_support',[]) if cid in x.get('source_chunk_ids',[])],
             'original_page_context':[page_record(ch['document_id'],pg) for pg in pages],
             'parent':parents.get(ch.get('parent_chunk_id')),
             'original_tables':corpus.original_tables([ch]).get(cid,[])}
        evidence.append(rec)
        if cid not in all_evidence:all_evidence[cid]={k:v for k,v in rec.items() if k not in {'role','required_conditional_links','answer_fact_links','governed_source_record'}};all_evidence[cid]['question_usage']=[]
        all_evidence[cid]['question_usage'].append({'qid':qid,'role':role,'check_links':links.get(cid,[]),'answer_fact_links':rec['answer_fact_links'],'governed_source_record':source or None})
    per_missing=[]
    if not qcmatches:per_missing.append('当前QC原始Provider文本未能与Checkpoint明确匹配；不可重构原始响应')
    if not trace.get('config'):per_missing.append('Probe实际Pipeline配置未记录')
    if not candidates:per_missing.append('CandidateK候选列表未记录')
    if not reranked:per_missing.append('重排列表未记录或为空')
    if req.get('auxiliary_information'):per_missing.append('辅助项未逐项持久化适用/满足结论；仅保留QC整体理由/完整响应，不推断逐项判断')
    per_missing += ['替代Final Chunk是否提供等价事实、缺失的语义影响：待独立分析',
                    '版本未提供的来源不补造版本；PDF物理页序不等于印刷页码',
                    'HTTP完整报文/headers及未持久化提示词不导出；保留实际已存Provider content和Usage']
    missing.extend({'qid':qid,'field':m} for m in per_missing)
    revisions_q=[r for r in revisions if key in r.get('audit',{}).get('question_ids',[]) or key in r.get('audit',{}).get('source_question_ids',[])]
    data={'QID':qid,'workset_identity':CONTENT,'run_id':RUN_ID,'current_content_hash':identity['content_hash'],'current_quality_identity':identity,
          'question':item,'question_db_row':dict(conn.execute('SELECT * FROM questions WHERE id=?',(key,)).fetchone()),
          'qualification':rows[key],'formal_golden_evidence_ids':formal,'business_source_ids':req_ids,'evidence':evidence,
          'current_probe':ph[0],'probe_history_latest_first':ph,'current_qc':qh[0],'qc_history_latest_first':qh,
          'current_qc_original_provider_matches':qcmatches,'current_business_audit':ah[0],'business_audit_history_latest_first':ah,
          'review_events_latest_first':rh,'approvals':approvals,'revision_history':revisions_q,'checkpoint':cp,
          'provider_requests_including_history':requests,'retrieval_gaps':gap_rows,'unavailable_or_needs_independent_analysis':per_missing,
          'human_gate':{'dataset':run['human_gate'],'question_qualified_for_gate':rows[key]['qualification_status'] in ['machine_qualified','human_approved','owner_delegated_approved'],'attention_reasons':rows[key]['attention_reasons']}}
    write(Path('raw')/(qid+'.json'),data)
    if pd.get('classification')=='RETRIEVAL_INCOHERENT':gaps.append(data)
    exports.append(data)
    checks.append({'QID':qid,'question_id':key,'content_hash':identity['content_hash'],'probe_id':ph[0]['id'],'qc_id':qh[0]['id'],'audit_id':ah[0]['id'],'identities_current':True,'formal_evidence_all_found':all(c in chunks for c in formal),'business_sources_all_found':all(c in chunks for c in req_ids),'required_and_conditional_qc_ids_complete':{x['id'] for k in ['required_checks','conditional_checks'] for x in req.get(k,[])}=={x['id'] for x in qc.get('content_review',{}).get('checks',[])},'raw_qc_provider_text_matched':bool(qcmatches)})

# Human readable, with unabridged canonical/trace/QC material; raw files retain all
# history and RPC envelopes, including fields not convenient to render as prose.
def render_question(d):
    item=d['question'];raw=item['raw'];req=raw['business_requirements'];p=d['current_probe']['result'];qc=d['current_qc']['result'];pd=p['probe_details'];tr=pd.get('retrieval_trace',{});row=d['qualification']
    out=[f"## {d['QID']} · {item['test_category']}\n",f"Question ID：`{item['id']}`；负向子类：{item.get('negative_subtype') or '不适用'}。\n",
         f"工作集：`{CONTENT}`；单题当前内容哈希：`{d['current_content_hash']}`。\n",
         '### 原始问题全文\n\n'+item['question']+'\n',
         '### 当前正式参考答案全文\n\n'+text(item.get('reference_answer'))+'\n',
         '### 负向完整预期行为/业务预期\n'+block({k:raw.get(k) for k in ['expected_response','expected_behavior','negative_subtype','behavior_criteria']}),
         '### 测试目的、角色、用户意图、场景与来源身份\n'+block({k:raw.get(k) for k in ['business_design','user_role','business_scenario','user_intent','difficulty','construction_type','ablation_attribute','ablation_metadata','source','source_reference','clone_provenance','content_identity','content_revision','generation_strategy','generation_model','generation_run_id','coverage_slot','coverage_anchor_chunk_ids','topic_cluster']}),
         render_checks(req,qc.get('content_review',{})),
         '### 辅助信息、安全约束、禁止错误、等价表达与逐行事实支持\n'+block({k:req.get(k) for k in ['auxiliary_information','prohibited','acceptable_equivalents','answer_support','corpus_review_scope']}),
         '### 全部正式Golden Evidence ID\n'+block(d['formal_golden_evidence_ids']),
         '负向题的正式答案Evidence为空；下列背景材料用于理解范围，不能证明缺失答案存在。\n' if item['test_category']=='negative' else '',
         '### 完整来源原文、检查点映射与本地原手册页定位\n']
    for e in d['evidence']:
        if e['chunk_id'] not in set(d['formal_golden_evidence_ids'])|set(d['business_source_ids']):continue
        ch=e['canonical_chunk'];out += [f"#### {e['chunk_id']} · {e['role']}\n",f"文档：{ch.get('document_name')}；产品：{ch.get('product')}；章节：{ch.get('section_path') or ch.get('section') or '未提供'}；PDF页：{ch['page_start']}–{ch['page_end']}；版本：{e['version'] or e['version_status']}。\n",
            '规范Chunk完整原文：\n'+block(ch.get('chunk_text',ch.get('text','未保存')),'text'),
            '持久化来源及支持事实/条件：\n'+block({k:e[k] for k in ['governed_source_record','required_conditional_links','answer_fact_links','original_tables']}),
            '原手册对应页上下文（完整既存解析，及可读取的PDF文本层）：\n'+block(e['original_page_context'])]
    out += ['### Probe当前真实记录\n',f"执行：{pd.get('probe_execution_status','未单独记录')}；业务结果：{p['status']}；分数：{p['score']}；阈值：{p.get('threshold') if p.get('threshold') is not None else '无统一分数阈值；evidence_direct_failure不可补偿'}；分类：{pd.get('classification')}。\n\n原因：{p.get('reason')}\n",
            'Probe完整结构（文本列表在后续按阶段逐项展示）：\n'+block({**p,'probe_details':{k:v for k,v in pd.items() if k!='retrieval_trace'}}),
            '检索请求、实际Pipeline、Trace元数据：\n'+block({k:v for k,v in tr.items() if k not in ['candidates','reranked','final']}),
            '### CandidateK候选召回列表 · 重排前\n'+render_hits(stage_list(tr,'candidates')),
            '### 重排后的完整排序\n'+render_hits(stage_list(tr,'reranked')),
            '### Final Context实际完整文本\n'+render_hits(stage_list(tr,'final')),
            '### Evidence Coverage及指定证据缺口\n'+block({'persisted_evidence_coverage':pd.get('evidence_coverage'),'missing_final_analysis':d['retrieval_gaps']}),
            '### 当前QC完整结构化结果\n',f"记录ID：{d['current_qc']['id']}；执行时间：{d['current_qc']['created_at']}；分数：{qc['score']}；优先级：{qc['priority']}；合同：{qc.get('rule_version')}。\n\n完整理由：{qc.get('reason')}\n",
            '完整Issues、逐项检查、条件触发、语义/范围/安全、证据引用校验、QC输入证据、Usage：\n'+block(qc),
            '### 当前QC原始Provider响应 · 原样\n']
    for match in d['current_qc_original_provider_matches']:
        out += [f"请求：`{match['request_key']}`；Checkpoint：{match['checkpoint_scope']}。\n",block(match['raw_provider_content'],'text')]
    if not d['current_qc_original_provider_matches']:out.append('未能明确匹配已保存原始响应；未用结构化结果反向伪造原始文本。\n')
    out += ['### Probe/QC历史演变 · 最新在前\n']
    for h in d['qc_history_latest_first']:
        out.append(f"QC ID {h['id']}，{h['created_at']}，{h['result'].get('score')}/{h['result'].get('priority')}，{'当前有效' if h['id']==d['current_qc']['id'] else '历史记录，不作为当前质量凭证'}。\n"+block(h))
    for h in d['probe_history_latest_first']:
        out.append(f"Probe ID {h['id']}，{h['created_at']}，{h['result'].get('status')}，{'当前有效' if h['id']==d['current_probe']['id'] else '历史记录'}。\n"+block({k:v for k,v in h.items() if k!='result'}|{'result':{k:v for k,v in h['result'].items() if k!='probe_details'},'historical_probe_details':{k:v for k,v in h['result'].get('probe_details',{}).items() if k!='retrieval_trace'}}))
    out += ['### 十项业务质量审计 · 全部历史完整保留\n'+block(d['business_audit_history_latest_first']),
            '### 人工审核、AI待审意见、已记录处置\n'+block({'review_events':d['review_events_latest_first'],'approvals':d['approvals']}),
            '### 资格与Human Gate前置\n'+block({'qualification_status':row['qualification_status'],'attention_reasons':row['attention_reasons'],'attention_categories':row.get('attention_categories'),'human_gate':d['human_gate']}),
            '### 缺失字段与待独立分析事项\n'+block(d['unavailable_or_needs_independent_analysis']),
            f"完整原始DB行、全部历史Probe Trace、修订过程及请求Checkpoint见 [raw/{d['QID']}.json](raw/{d['QID']}.json)。\n"]
    return '\n'.join(out)
for start in range(0,50,10):
    name=f'Q{start+1:02}_Q{start+10:02}_FULL_REVIEW.md'
    write(name,'# Golden逐题完整审核资料\n\n导出记录，不构成新的审核结论。全部正文与结构化结果保留，不截断。\n\n'+'\n\n---\n\n'.join(render_question(d) for d in exports[start:start+10]))

summary=['# Golden 50题总览\n','Probe/QC结果与资格分开；检索风险保持原记录，不重新裁决。\n','|题号|原始问题全文|类别/子类|Probe|QC|检索风险|审核状态|当前关注原因|','|---|---|---|---|---|---|---|---|']
for d in exports:
    i=d['question'];p=d['current_probe']['result'];q=d['current_qc']['result'];r=d['qualification']
    summary.append('|'+ '|'.join(map(table_cell,[d['QID'],i['question'],i['test_category']+'/'+str(i.get('negative_subtype') or ''),p['status'],str(q['score'])+'/'+q['priority'],p['probe_details']['classification'],r['qualification_status'],'、'.join(r['attention_reasons']) or '无']))+'|')
write('01_GOLDEN_50_SUMMARY.md','\n'.join(summary)+'\n')
gapdoc=['# 12道检索风险题完整对照\n','仅按持久化列表比较Chunk ID所在阶段；不判定语义等价，不将指定Chunk缺失当作答案错误。完整候选、重排及Final文本见逐题文件，原结构见raw。\n']
for d in gaps:
    tr=d['current_probe']['result']['probe_details']['retrieval_trace'];ids_stage={k:[x.get('chunk_id') for x in stage_list(tr,k)] for k in ['candidates','reranked','final']}
    gapdoc += [f"## {d['QID']}\n\n{d['question']['question']}\n",'现有证据覆盖记录：\n'+block(d['current_probe']['result']['probe_details']['evidence_coverage']),
               'Golden Evidence与各阶段成员：\n'+block({'formal_golden_evidence_ids':d['formal_golden_evidence_ids'],**ids_stage}),
               '缺失Chunk及检查点级别、阶段观察、潜在影响：\n'+block(d['retrieval_gaps'])]
    for gap in d['retrieval_gaps']:
        ch=chunks.get(gap['chunk_id']);gapdoc.append('缺口原文 '+gap['chunk_id']+'：\n'+block(ch.get('chunk_text',ch.get('text')) if ch else '无对应正文','text'))
    gapdoc.append('实际Final Context全文（用于独立对比）：\n'+render_hits(stage_list(tr,'final')))
write('02_RETRIEVAL_GAPS.md','\n'.join(gapdoc))
issues=['# QC、安全、语义与审核争议全集\n','以下为真实原始记录，按当前待审和历史问题区分。高分不自动关闭P1或人工意见。十项审计：naturalness自然度、business_value业务价值、intent意图、grounding来源支撑、independence独立性、copying机械复制、duplicates重复、type题型、coverage覆盖、diversity多样性。\n']
for d in exports:
    qc=d['current_qc']['result'];histproblem=any(h['result'].get('priority') in ['P0','P1'] or h['result'].get('score',100)<85 for h in d['qc_history_latest_first'])
    if not d['qualification']['attention_reasons'] and not histproblem and not d['review_events_latest_first']:continue
    issues += [f"## {d['QID']} · 当前{qc['score']}/{qc['priority']} · {d['qualification']['qualification_status']}\n\n{d['question']['question']}\n",'当前关注原因：\n'+block(d['qualification']['attention_reasons']),
               '当前QC完整意见、判断及证据：\n'+block(qc),'历史QC完整记录：\n'+block(d['qc_history_latest_first']),
               '原始审核事件/AI意见及批准记录：\n'+block({'review_events':d['review_events_latest_first'],'approvals':d['approvals']}),
               '当前业务审计和历史理由：\n'+block(d['business_audit_history_latest_first'])]
    for m in d['current_qc_original_provider_matches']:issues.append('当前QC原始Provider响应：\n'+block(m['raw_provider_content'],'text'))
# Prior independent advice is explicitly tagged; no invented closure.
basis=ROOT/'docs/GOLDEN_BATCH_REVIEW_BASIS.md'
if basis.exists():issues += ['## 仓库已保存AI辅助处置建议 · 不是用户批准\n',basis.read_text()]
write('03_QC_AND_REVIEW_ISSUES.md','\n'.join(issues))
write('EVIDENCE_CHUNKS.json',{'corpus_identity':corpus_identity,'chunks':all_evidence,'note':'含标准证据、负向背景与实际检索/历史引用，role按每题分别标记；不包含整份原始PDF。'})
run_export={**run,'artifacts':{**run['artifacts'],'hard_validation':{**run['artifacts']['hard_validation'],'quality_rerun':{k:v for k,v in state.items() if k!='checkpoints'}}}}
write('raw/WORKSET_AND_RUN.json',{'run':run_export,'corpus_manifest':json.loads((INDEX_DIR/'manifest.json').read_text()),'source_hashes':source_hashes,'db_logical_sha256':before_logical,'note':'每题Checkpoint分别完整存raw/Qxx.json；不导出.env、API密钥或私有通用日志。'})
write('raw/FIELD_COMPLETENESS.json',checks)
assert len(gaps)==12
assert all(x['identities_current'] and x['formal_evidence_all_found'] and x['business_sources_all_found'] and x['required_and_conditional_qc_ids_complete'] for x in checks)
counts={'question_count':50,'categories':dict(Counter(d['question']['test_category'] for d in exports)),
        'probe':dict(Counter(d['current_probe']['result']['status'] for d in exports)),
        'qc':dict(Counter(d['current_qc']['status'] for d in exports)),
        'qc_priorities':dict(Counter(d['current_qc']['result']['priority'] for d in exports)),
        'qualification':dict(Counter(d['qualification']['qualification_status'] for d in exports)),
        'retrieval_risk_qids':[d['QID'] for d in gaps],'raw_provider_qc_matched_count':sum(x['raw_qc_provider_text_matched'] for x in checks)}
index=f'''# Golden 50题完整审核导出

导出时间：{NOW}。Git：`{subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}`。
工作集：`{CONTENT}`；Run：`{RUN_ID}`。数据来自正式SQLite的同一只读事务，不启动Demo、不迁移、不执行模型、不审批、不冻结。

## 当前统计及身份

{block(counts)}

{block({'human_gate':run['human_gate'],'corpus_identity':corpus_identity})}

工作集逻辑身份与每题内容哈希分开。Q36当前为修订后内容，旧Probe失败和QC82/P1列为历史；当前QC96/P2。每个当前Probe/QC/业务审计均验证当前单题内容哈希和Corpus，历史保留其原身份，不冒充同一当前质量结果。

## 文件索引

- 01_GOLDEN_50_SUMMARY.md：全部50题总览。
- Q01_Q10_FULL_REVIEW.md 至 Q41_Q50_FULL_REVIEW.md：每组10题完整正文、检查点、证据、检索三个阶段、当前QC与历史、业务及人工记录。
- 02_RETRIEVAL_GAPS.md：12题指定证据与候选/重排/Final对照。
- 03_QC_AND_REVIEW_ISSUES.md：当前14题及历史争议，完整QC/审核原意见。
- raw/Q01.json 至 raw/Q50.json：完整DB字段、当前/历史Probe和QC、Provider请求结果/Checkpoint、业务审计与审核事件、Revision。
- raw/WORKSET_AND_RUN.json：Run与Corpus身份；raw/FIELD_COMPLETENESS.json：逐题字段与绑定验证。
- EVIDENCE_CHUNKS.json：全部相关规范Chunk全文、Parent、表格、源页上下文及每题用途。
- MANIFEST.json：全部文件SHA256及完整性、缺失字段；清单不包含自身哈希，避免递归。ZIP与目录内容逐字一致。

## 字段解释与阅读边界

required_checks为必答；conditional_checks必须按其原触发条件，auxiliary_information为辅助；prohibited为禁止错误。逐项QC是已存模型判断，不等于负责人批准。业务审计十项checks的true/false不代替人工审核。

标准答案Evidence仅取正式questions.evidence；治理规范sources另行标明。Negative正式Evidence为空，材料Anchor/背景来源不能支持不存在的答案。检索Final.content为当时实际上下文，不用今天Canonical正文覆盖历史文本；Child正文与Parent扩展均分开保留。原始候选排名、模型分数按实际字段，未记录rank时只提供列表序号。

PDF页码采用从1开始的物理页序。原始PDF对应页直接读取文本层，并附既有MinerU完整页上下文；无文本层页不宣称完成视觉核实。结构化version为空时明确未提供，不从日期/型号猜测。

Provider原始content以Checkpoint中保存字符串原样导出；可匹配当前QC时给出请求键。结构化result保留原DB JSON字符串，同时提供解码值。没有保存的HTTP原始包、提示词或字段不补造。所有文件仅本地，禁止将手册原文、审核载荷或私密数据推送公开仓库。

## 缺失与待独立分析字段

{block(missing)}
'''
write('00_REVIEW_INDEX.md',index)
# Verify database and source assets were not changed, with fresh read connection.
conn.rollback();conn.close()
with sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True) as fresh:after_logical=logical_hash(fresh)
assert before_logical==after_logical,'Database changed during export'
assert before_hash==sha(DB),'Main SQLite bytes changed'
assert all(sha(p)==v for p,v in source_hashes.items()),'Source asset changed'
for f in pdf_cache.values():f.close()
files={str(p.relative_to(OUT)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(OUT.rglob('*')) if p.is_file()}
manifest={'exported_at':NOW,'git_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'run_id':RUN_ID,'content_identity':CONTENT,'corpus_identity':corpus_identity,'source_database':str(DB),'sqlite_main_sha256':before_hash,'sqlite_logical_sha256':before_logical,'counts':counts,'human_gate':run['human_gate'],'read_only_checks':{'sqlite_mode_ro':True,'query_only':True,'single_transaction':True,'db_byte_unchanged':True,'db_logical_unchanged':True,'source_assets_unchanged':True,'provider_calls':0,'approval_writes':0,'snapshot_writes':0},'field_completeness':checks,'unavailable_or_needs_independent_analysis':missing,'files':files,'manifest_self_hash':'excluded to avoid recursion'}
write('MANIFEST.json',manifest)
zip_path=OUT.parent/'GOLDEN_50_FULL_REVIEW.zip'
if zip_path.exists():raise SystemExit('Refusing to overwrite existing ZIP')
with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(OUT.rglob('*')):
        if p.is_file():z.write(p,str(Path(OUT.name)/p.relative_to(OUT)))
with zipfile.ZipFile(zip_path) as z:
    assert z.testzip() is None
    for p in OUT.rglob('*'):
        if p.is_file():assert hashlib.sha256(z.read(str(Path(OUT.name)/p.relative_to(OUT)))).hexdigest()==sha(p)
print(dump({'directory':str(OUT),'directory_bytes':sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file()),'zip':str(zip_path),'zip_bytes':zip_path.stat().st_size,'zip_sha256':sha(zip_path),'files':len(files)+1,'counts':counts,'db_unchanged':True}))
