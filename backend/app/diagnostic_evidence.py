"""Independent, offline semantic reviews. Never alter Judge input, verdict or history.

A review is evidence data, not an inferred root: a reviewer checks equivalence and
source applicability against an entire immutable stage. Hashes prevent reusing
that semantic observation after any answer, source or stage changes.
"""
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from .evaluation_contract import normalize_display, quote_present

REVIEW_PATH=Path(__file__).resolve().parents[1]/'reports'/'diagnostic_evidence.json'


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def case_digest(case):
    return digest({k:case.get(k) for k in ('question','reference_answer','model_answer','test_category','negative_subtype','judge_result','evaluation_outcome','programmatic_metrics')})


def saved_review(case):
    """Use only a repository review bound to a real persisted frozen case."""
    try:
        artifact=json.loads(REVIEW_PATH.read_text())
        if artifact.get('schema')!='offline-diagnostic-evidence-1':return {'load_error':'independent_review_schema_invalid'},None
        review=next((r for r in artifact['records'] if r['case_sha256']==case_digest(case)),None)
        if review is None:return None,None
        root=Path(__file__).resolve().parents[2]
        for path,sha in artifact['audit_sources'].items():
            source=(root/path).resolve()
            if not source.is_relative_to(root) or hashlib.sha256(source.read_bytes()).hexdigest()!=sha:return {'load_error':'independent_audit_source_sha_mismatch'},None
        database=Path(os.getenv('RAG_DEMO_DB_PATH') or root/'backend/data/demo.db').resolve()
        with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as connection:
            row=connection.execute('SELECT c.result_json,r.dataset_snapshot_json FROM evaluation_case_results c JOIN evaluation_runs r ON r.id=c.run_id WHERE c.run_id=? AND c.question_id=?',(review['run_id'],review['question_id'])).fetchone()
        if row is None or case_digest(json.loads(row[0]))!=review['case_sha256']:return {'load_error':'persisted_case_not_found_or_changed'},None
        snapshot=json.loads(row[1])
        if digest(snapshot)!=review['snapshot_sha256']:return {'load_error':'frozen_snapshot_sha_mismatch'},None
        frozen=next(q for q in snapshot['questions'] if q['id']==review['question_id'])
        if any(frozen.get(k)!=case.get(k) for k in ('question','reference_answer','test_category')):return {'load_error':'frozen_question_mismatch'},None
        return review,{'question':frozen,'corpus_fingerprint':snapshot['corpus_fingerprint']}
    except FileNotFoundError:return None,None
    except (OSError,ValueError,KeyError,TypeError,StopIteration,sqlite3.Error) as error:
        return {'load_error':'independent_review_could_not_be_verified: '+str(error)},None


def review_findings(case,trace,chunks,review,frozen):
    """Validate sourced review assertions; missing is never an absence assertion."""
    findings=[];gaps=[]
    if not review:return findings,gaps
    def reject(reason,index=None):gaps.append({'source':'independent_review','check_index':index,'condition':reason})
    if review.get('load_error'):
        reject(review['load_error']);return findings,gaps
    if (not frozen or review.get('case_sha256')!=case_digest(case)
        or frozen.get('corpus_fingerprint')!=trace.get('corpus_fingerprint')
        or review.get('stages_sha256')!={s:digest(trace.get(s)) for s in ('candidates','reranked','final')}):
        reject('review_case_corpus_or_whole_stage_identity_mismatch');return findings,gaps
    question=frozen['question'];golden_ids={i for e in question.get('evidence',[]) for i in e.get('source_chunk_ids',[])}
    sources=[{**c,'content':c.get('chunk_text') or c.get('text') or c.get('content','')} for c in chunks]
    by_id={c['chunk_id']:c for c in sources}
    checks=case['judge_result']['checks']
    for fact in review.get('facts',[]):
        index=fact.get('check_index');reference=fact.get('reference_support');fragment=fact.get('golden_quote','')
        if type(index) is not int or not 0<=index<len(checks) or checks[index]['met'] is not False:
            reject('review_requires_original_failed_check',index);continue
        if (not isinstance(fragment,str) or not normalize_display(fragment)
            or normalize_display(fragment) not in normalize_display(question.get('reference_answer',''))
            or not isinstance(reference,list) or not reference
            or any(q.get('source_id') not in golden_ids or not quote_present(q,sources,display=True) for q in reference)
            or not any(normalize_display(fragment) in normalize_display(q['quote']) for q in reference)):
            reject('review_required_fact_or_canonical_reference_unlocated',index);continue
        scope=fact.get('source_applicability') or {}
        origin=by_id[reference[0]['source_id']]
        if (scope.get('purpose')!='normative_requirement_only' or not scope.get('reason')
            or any(scope.get(k)!=origin.get(k) for k in ('document_id','product','version'))
            or any(by_id[q['source_id']].get(k)!=origin.get(k) for q in reference for k in ('document_id','product','version'))
            or any(question.get(k) and question[k]!=origin.get(k) for k in ('product','version'))):
            reject('review_source_product_version_or_applicability_mismatch',index);continue
        coverage={};supports={};valid=True
        for stage in ('candidates','reranked','final'):
            observation=(fact.get('stages') or {}).get(stage) or {}
            state=observation.get('coverage');quotes=observation.get('support')
            entries=trace.get(stage)
            if (state not in {'complete','partial','absent'} or not isinstance(entries,list)
                or not isinstance(quotes,list) or not observation.get('equivalence_review')
                or (state=='absent')!= (quotes==[])):
                reject(stage+': missing_explicit_coverage_or_equivalence_review',index);valid=False;break
            if any(not quote_present(q,entries,display=True) for q in quotes):
                reject(stage+': reviewed_support_unlocated',index);valid=False;break
            matched=[e for e in entries if any(quote_present(q,[e],display=True) for q in quotes)]
            if any(e.get(k)!=origin.get(k) for e in matched for k in ('document_id','product','version')):
                reject(stage+': equivalent_source_scope_mismatch',index);valid=False;break
            # Literal coverage can disprove an absence review, never prove semantic absence.
            literal=any(normalize_display(fragment) in normalize_display(e['content']) for e in entries
                if all(e.get(k)==origin.get(k) for k in ('document_id','product','version')))
            if state=='absent' and literal:
                reject(stage+': absence_contradicted_by_actual_context',index);valid=False;break
            if state=='complete' and not any(normalize_display(fragment) in normalize_display(q['quote']) for q in quotes):
                reject(stage+': partial_quote_cannot_prove_complete_fact',index);valid=False;break
            coverage[stage]=state;supports[stage]=quotes
        if not valid:continue
        if coverage['final']=='complete':root,stage='Generation',None
        elif coverage['candidates']=='complete':root,stage='Ranking','ranking_context_selection'
        elif coverage['candidates']=='absent':root,stage='Retrieval','candidate_recall'
        else:
            reject('partial_candidate_coverage_cannot_close_root',index);continue
        findings.append((root,stage,{'check_index':index,'requirement':checks[index]['requirement'],
            'fact':fragment,'reference_support':reference,'support':supports['final'],
            'candidate_support':supports['candidates'],'rerank_support':supports['reranked'],
            'candidate_missing':coverage['candidates']=='absent','stage_coverage':coverage,
            'answer_quotes':checks[index]['answer_quotes'],'source_applicability':scope,
            'provenance':{'kind':'independent_offline_review','run_id':review.get('run_id'),
                'question_id':review.get('question_id'),'case_sha256':review['case_sha256'],
                'snapshot_sha256':review.get('snapshot_sha256'),'stages_sha256':review['stages_sha256'],
                'historical_judge_scope_resolved':checks[index].get('scope_resolved'),
                'historical_candidate_support_present':'candidate_support' in checks[index]}}))
    return findings,gaps


def context_selection_options(trace,findings,chunks,checks):
    """Replay only saved ordering/threshold/Parent selection; no retrieval or Provider."""
    from itertools import product
    from .policy import ALLOWED_SEARCH_SPACE
    from .knowledge_pipeline import expand_parents
    required=[[f['candidate_support']] for root,_,f in findings if root=='Ranking' and f.get('candidate_support')]
    if not required:return None,'未定位待恢复的完整必要事实支持'
    if not isinstance(trace.get('reranked'),list):return None,'未采集完整reranked列表'
    supplemental={i for _,_,f in findings for i in f.get('supplemental_check_indices',[])}
    preservation=[r for _,_,f in findings for r in f.get('preservation_requirements',[])]
    reviewed={r['check_index'] for r in preservation}
    required.extend(r['alternatives'] for r in preservation)
    required.extend([c['support']] for i,c in enumerate(checks) if i not in supplemental|reviewed and c['met'] and c.get('support'))
    required.extend([f['preserve_support']] for _,_,f in findings if f.get('preserve_support'))
    required_scopes=[q for c in checks if c['met'] for q in c.get('scope_support',[])]
    baseline={k:trace.get('config',{}).get(k,default) for k,default in [('top_k',4),('rerank',True),('min_score',0)]}
    parents={c['canonical_parent']['chunk_id']:c['canonical_parent'] for c in chunks if c.get('canonical_parent')}
    options=[]
    for top_k,rerank,min_score in product(*(ALLOWED_SEARCH_SPACE[k] for k in baseline)):
        config={'top_k':top_k,'rerank':rerank,'min_score':min_score}
        diff={k:v for k,v in config.items() if v!=baseline[k]}
        if not diff:continue
        if rerank=='query_only':
            from .retrieval import query_only_order
            hits=query_only_order(trace.get('question',''),trace['candidates'])
        else:hits=trace['reranked' if rerank else 'candidates']
        if any(type(e.get('score')) not in (int,float) for e in hits):return None,'保存阶段缺少数值score，无法验证阈值选择'
        hits=[e for e in hits if e['score']>=min_score]
        if trace.get('parent_expand'):
            if any(e.get('parent_chunk_id') not in parents for e in hits):return None,'Canonical Parent缺失，无法回放上下文展开'
            final=expand_parents(hits,list(parents.values()),top_k)
        else:final=hits[:top_k]
        from .ai_service import attach_heading_scopes
        scoped=attach_heading_scopes(final,chunks) if required_scopes else []
        scopes_preserved=all(any((e.get('source_scope') or {}).get('source_id')==q.get('heading_source_id') for e in scoped) for q in required_scopes)
        if scopes_preserved and all(any(all(quote_present(q,final,display=True) for q in quotes) for quotes in alternatives) for alternatives in required):options.append(diff)
    return [o for o in options if not any(other!=o and all(o.get(k)==v for k,v in other.items()) for other in options)],None
