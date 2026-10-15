"""One scoped owner delegation, verified independently of client approval flags."""
import hashlib
import json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from functools import lru_cache

CHECKS = ('hard_validation','probe','qc','pdf_grounding','evidence_location','facts_complete',
          'version_scope','negative_contract','safety_clear','vendor_dispute_clear','no_p0','traceable')


@lru_cache(maxsize=1)
def local_ocr():
    from rapidocr import RapidOCR
    return RapidOCR()


@lru_cache(maxsize=32)
def pdf_page_text(path, modified_ns, page):
    import pymupdf
    with pymupdf.open(path) as pdf:
        if not 1<=page<=len(pdf): return ''
        text=pdf[page-1].get_text()
        if any(character.isalnum() for character in text): return text
        image=pdf[page-1].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).tobytes('png')
        return '\n'.join(local_ocr()(image).txts or [])


def verify_pdf_sources(sources):
    from .corpus import CorpusStore, DOCUMENTS_DIR
    from .evaluation_contract import normalize
    corpus = CorpusStore()
    chunks = {c['chunk_id']:c for c in corpus.chunks()}
    for source in sources:
        chunk = chunks.get(source.get('chunk_id'))
        page,quote = source.get('page'),source.get('quote')
        if not chunk or chunk['document_id']!=source.get('document_id') or type(page) is not int or not isinstance(quote,str) or len(normalize(quote))<4:
            return False
        if not chunk['page_start']<=page<=chunk['page_end']: return False
        if normalize(quote) not in normalize(chunk['chunk_text']): return False
        path = (DOCUMENTS_DIR/chunk['document_name']).resolve()
        if path.parent!=DOCUMENTS_DIR.resolve(): return False
        if normalize(quote) not in normalize(pdf_page_text(str(path),path.stat().st_mtime_ns,page)): return False
    return True


def validate_delegation(path, authorization_id, run, rows, items, reviews, content_hash, *, verify_sources=verify_pdf_sources):
    path=Path(path)
    if not path.is_file(): raise ValueError('Owner delegation authorization unavailable')
    auth=json.loads(path.read_text())
    expected={'authorization_id':authorization_id,'source':'direct_user_instruction','generation_run_id':run['id'],
              'delegated_by':'project_owner','actor':'Codex'}
    if any(auth.get(k)!=v for k,v in expected.items()): raise ValueError('Owner delegation scope/actor differs')
    if datetime.fromisoformat(auth['expires_at'])<=datetime.now(timezone.utc): raise ValueError('Owner delegation expired')
    if hashlib.sha256(Path(auth['source_file']).read_bytes()).hexdigest()!=auth.get('source_sha256'):
        raise ValueError('Owner authorization source changed')
    state=run['artifacts']['hard_validation']
    if auth.get('corpus')!=state['corpus_fingerprint'] or auth.get('plan_id')!=state['frozen_plan']['plan_id']:
        raise ValueError('Owner authorization Corpus/Plan changed')
    from .governance import GENERATION_PROFILES
    profile=run.get('profile',{})
    name=profile.get('name')
    if name not in {'mini','medium'} or any(type(profile.get(key)) is not int or profile[key]!=value for key,value in GENERATION_PROFILES[name].items()):
        raise ValueError('Owner delegation requires a valid Mini20 or Medium50 profile')
    scope={'name':name,**GENERATION_PROFILES[name]}
    # Legacy Medium authorization had no profile; it never authorizes Mini.
    if auth.get('profile')!=scope and not (name=='medium' and 'profile' not in auth):
        raise ValueError('Owner authorization Profile changed or unavailable')
    count=scope['expected_count']
    ids=run['question_ids']
    if len(ids)!=count or len(set(ids))!=count or len(reviews)!=count or {r['question_id'] for r in reviews}!=set(ids):
        raise ValueError(f'Owner delegation requires exactly the scoped {count} questions')
    if Counter(items[key]['test_category'] for key in ids)!=Counter({group:scope[f'{group}_count'] for group in ('positive','ablation','negative')}) or len(state['frozen_plan'].get('clusters',[]))!=9:
        raise ValueError('Owner delegation Profile groups/Topics changed')
    def reviewable(row):
        if row['qualification_status'] in {'machine_qualified','owner_delegated_approved'}: return True
        return set(row.get('attention_reasons',[])) in ({'检索不连贯'},{'QC P1','检索不连贯'}) and row.get('probe_status')=='probe_passed' and row.get('qc_status')=='qc_passed'
    if run['status']!='completed' or any(not reviewable(r) for r in rows) or {r['id'] for r in rows}!=set(ids):
        raise ValueError('Owner delegation cannot waive machine quality')
    from .business_golden import CHECKS as BUSINESS_CHECKS, QUALITY_CONTRACT
    plan = state['frozen_plan']
    current_contract = plan.get('quality_contract') in {'business-quality-v3', QUALITY_CONTRACT}
    for review in reviews:
        item=items[review['question_id']]
        row=next(r for r in rows if r['id']==review['question_id'])
        if current_contract:
            if not any(s['slot'] == item['raw'].get('coverage_slot') for s in plan.get('slots', [])):
                raise ValueError('Independent review frozen Slot scope unavailable')
            if plan.get('quality_contract') == QUALITY_CONTRACT and (row.get('quality_audit') or {}).get('audit_version') != QUALITY_CONTRACT:
                raise ValueError('Current business quality contract audit unavailable')
            if (not isinstance(review.get('business_checks'),dict) or set(review['business_checks']) != set(BUSINESS_CHECKS)
                or any(v is not True for v in review['business_checks'].values())
                or review.get('actor') != 'Codex AI Agent / Owner Delegated AI Review'):
                raise ValueError('Independent business review unavailable')
            try:
                reviewed_at = datetime.fromisoformat(review['reviewed_at'])
                quality_at = max(datetime.fromisoformat(item['updated_at']), datetime.fromisoformat(row['quality_audit_created_at']))
                if reviewed_at.utcoffset() is None or not quality_at <= reviewed_at <= datetime.now(timezone.utc):
                    raise ValueError('Independent review must follow current quality checks')
            except (KeyError,TypeError,ValueError) as error:
                raise ValueError('Independent review timestamp unavailable or stale') from error
        if set(row.get('attention_reasons',[])) in ({'检索不连贯'},{'QC P1','检索不连贯'}):
            accepted=review.get('retrieval_risk_acceptance',{})
            if accepted.get('classification')!='RETRIEVAL_INCOHERENT' or accepted.get('retrieval_not_fixed') is not True or not accepted.get('reason') or not row.get('probe',{}).get('id') or accepted.get('probe_id')!=row['probe']['id']:
                raise ValueError('Delegated retrieval risk requires explicit independent acceptance')
            if 'QC P1' in row.get('attention_reasons',[]) and (not row.get('qc',{}).get('id') or accepted.get('qc_id')!=row['qc']['id'] or not accepted.get('qc_issue_disposition')):
                raise ValueError('QC P1 requires a current independent issue disposition')
        if review.get('content_hash')!=content_hash(item) or review.get('decision')!='A' or review.get('risk')!='none':
            raise ValueError('Delegated review stale or has unresolved risk')
        if set(review.get('checks',{}))!=set(CHECKS) or any(v is not True for v in review['checks'].values()) or not isinstance(review.get('basis'),str) or not review['basis'].strip():
            raise ValueError('Delegated review lacks independent checklist/basis')
        sources=review.get('sources')
        allowed=set(item['raw'].get('coverage_anchor_chunk_ids',[])) if item['test_category']=='negative' else {key for evidence in item['evidence'] for key in evidence.get('source_chunk_ids',[])}
        if not isinstance(sources,list) or any(source.get('chunk_id') not in allowed for source in sources):
            raise ValueError('Delegated evidence is outside question source scope')
        if not isinstance(sources,list) or not sources or not verify_sources(sources):
            raise ValueError('Delegated review PDF evidence unavailable')
    return {'approval_mode':'owner_delegated','review_actor_type':'ai_agent','delegated_by':'project_owner',
            'actor':'Codex','authorization_id':authorization_id,'authorization_source_sha256':auth['source_sha256'],
            'quality_request_limits':auth.get('output_limits'),
            'reviews':{r['question_id']:r for r in reviews}}
