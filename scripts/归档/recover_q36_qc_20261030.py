"""Default offline plan; explicit authorization permits ONE Q36 QC, no review/freeze.
Original Probe/audit/failed request remain intact. No similarity/audit/Probe replay.
"""
import argparse
import copy
import json
import os
import shutil
import socket
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import execute_judge_golden_revisions_20261030 as common

ROOT = common.ROOT
QUESTION = 'V1G-110926448917-36-R122036474962'
REVISION = 'REV-20261030014744623782'
ORIGINAL = ROOT / 'docs/judge_vnext_20261030/golden_authorized_execution'
LIMIT = 16384


def select(value, names):
    return {key: copy.deepcopy(value[key]) for key in names if key in value}


def project_probe(details, requirements):
    """Exact-value projection, explicitly not the full stored retrieval trace."""
    result = select(details, ('classification', 'evidence_coverage', 'probe_execution_status',
                             'question_validity', 'retrieval_coherent', 'risk'))
    trace = details['retrieval_trace']
    result['retrieval_trace'] = select(trace, ('status', 'corpus_fingerprint', 'final'))
    # Final is already the actual chosen context; never substitute Golden evidence.
    negative = details['negative_checks']
    result['negative_checks'] = select(negative, ('fake_negative_check', 'subtype_semantic'))
    result['negative_checks']['answerability'] = select(negative['answerability'],
        ('answerable', 'category', 'confidence', 'model', 'reason', 'supporting_chunk_ids', 'supporting_pages'))
    result['full_text'] = select(details['full_text'], ('answer_anchor_supported', 'content_semantics',
        'corpus_match_chunk_ids', 'entity_match_chunk_ids', 'mode', 'passed', 'source_checks'))
    full = negative['full_text_probe']
    projected = select(full, ('anchors', 'corpus_fingerprint', 'coverage', 'signal_only', 'status'))
    sources = requirements['sources']
    projected['matches'] = []
    for match in full.get('matches', []):
        relevant = [s for s in sources if s['document_id'] == match.get('document_id')
                    and s['pages'][0] <= match.get('page', -1) <= s['pages'][1]]
        if relevant:
            row = select(match, ('document_id', 'page', 'parser', 'text_checksum', 'method', 'matched_terms'))
            row['source_quotes_present_verbatim'] = [s['quote'] for s in relevant if s['quote'] in match.get('content', '')]
            projected['matches'].append(row)
    result['negative_checks']['full_text_probe'] = projected
    for section, key in [('legacy_chunk_signals', 'matches'), ('vector_probe', 'observed_hits')]:
        part = negative[section]
        result['negative_checks'][section] = {'signal_only': part['signal_only'], key: [
            select(row, ('chunk_id', 'document_id', 'page_start', 'page_end', 'score', 'rerank_score', 'matched_terms'))
            for row in part.get(key, [])]}
    result['projection'] = {'schema': 'q36-qc-probe-projection-1', 'is_full_probe_trace': False,
        'original_probe_details_sha256': common.digest(details),
        'omitted': ['candidate/reranked duplicated context', 'full Corpus page text', 'telemetry/cost/token usage'],
        'rule': 'Exact saved conclusions/identities; actual Final preserved; no inferred findings.'}
    return result


class ProjectedStore:
    def __init__(self, store):
        self.store = store
    def __getattr__(self, name):
        return getattr(self.store, name)
    def probe_history(self, question_id):
        if question_id != QUESTION:
            raise ValueError('Only approved Q36 may enter QC')
        rows = copy.deepcopy(self.store.probe_history(question_id))
        if not rows:
            raise ValueError('Saved Probe required')
        rows[0]['probe_details'] = project_probe(rows[0]['probe_details'], self.store.question(question_id)['raw']['business_requirements'])
        return rows


class CapturedRequest(Exception):
    pass


class CaptureProvider:
    settings = SimpleNamespace(configured=True, model='deepseek-flash')
    def complete(self, system, user, **kwargs):
        self.request = {'system': system, 'user': user, 'kwargs': kwargs}
        raise CapturedRequest()


def capture_request(store, corpus):
    from app.ai_service import AiService
    provider = CaptureProvider()
    service = AiService(ProjectedStore(store), corpus, provider, False)
    try:
        common.single_quality_check(service, store.capture_quality(QUESTION, qc=True)[0])
    except CapturedRequest:
        return provider.request
    raise RuntimeError('QC did not produce exactly one request')


def state(store):
    from app.business_golden import audit_passed
    run = store.revision_run(REVISION)
    item, identity = store.capture_quality(QUESTION, qc=True)
    probe = store.probe_history(QUESTION)[0]
    with store.connection() as db:
        audit = db.execute('SELECT * FROM question_quality_audits WHERE question_id=? ORDER BY id DESC LIMIT 1', (QUESTION,)).fetchone()
    if (run['status'] != 'failed_quality' or run.get('failed_stage') != 'qc'
            or run.get('error_type') != 'ProviderInvalidResponse' or not run.get('error')
            or run['question_ids'] != [QUESTION] or item['stage'] != 'candidate'
            or store.revision_quality_step(run, QUESTION) != 'qc'):
        raise ValueError('Exact failed Q36 QC revision required; no Probe replay')
    if not audit or audit['content_hash'] != identity['content_hash'] or not audit_passed(json.loads(audit['audit_json'])):
        raise ValueError('Existing current-content passed business audit required')
    saved = probe.get('execution_identity', {})
    if (probe['status'] != 'passed' or probe['created_at'] <= run['applied_at']
            or any(saved.get(k) != identity[k] for k in ('content_hash', 'corpus_fingerprint', 'active_candidate'))):
        raise ValueError('Existing Probe identity invalid; no automatic rerun')
    peers = {}
    for key in ('V1G-110926448917-13', 'V1G-110926448917-15'):
        _, current = store.capture_quality(key, qc=True)
        latest = store.qc_history(key)[0]['result']
        if latest.get('execution_identity') != current:
            raise ValueError('Q13/Q15 quality identity drift: ' + key)
        peers[key] = {'identity': current, 'qc_history_sha256': common.digest(store.qc_history(key)),
                      'probe_history_sha256': common.digest(store.probe_history(key))}
    return {'revision': run, 'question_raw_sha256': common.digest(item['raw']), 'quality_identity': identity,
            'probe_sha256': common.digest(probe), 'audit': dict(audit), 'protected_q13_q15': peers}


@contextmanager
def offline():
    def blocked(*args, **kwargs):
        raise RuntimeError('Network forbidden in Q36 offline plan')
    with patch.object(socket.socket, 'connect', blocked), patch.object(socket.socket, 'connect_ex', blocked):
        yield


def preserve(backup, database):
    """Only target question/revision may update; only one QC may append."""
    from collections import Counter
    with common.readonly(backup) as before, common.readonly(database) as after:
        for (table,) in before.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            quoted = '"' + table.replace('"', '""') + '"'
            old, new = list(before.execute('SELECT * FROM ' + quoted)), list(after.execute('SELECT * FROM ' + quoted))
            if table in {'questions', 'candidate_revision_runs'}:
                key = QUESTION if table == 'questions' else REVISION
                old_target, new_target = [r for r in old if r[0] == key], [r for r in new if r[0] == key]
                if len(old_target) != 1 or len(new_target) != 1:
                    raise RuntimeError('Protected target deleted or duplicated: ' + table)
                if table == 'questions':
                    columns = [c[1] for c in before.execute('PRAGMA table_info(questions)')]
                    for index, name in enumerate(columns):
                        if name not in {'qc_status', 'review_status', 'updated_at'} and old_target[0][index] != new_target[0][index]:
                            raise RuntimeError('Q36 content or Probe status changed: ' + name)
                old = [r for r in old if r[0] != key]; new = [r for r in new if r[0] != key]
            if table == 'qc_results':
                if Counter(old) - Counter(new) or len(new) - len(old) not in (0, 1):
                    raise RuntimeError('QC history overwritten or excess results')
                added = list((Counter(new) - Counter(old)).elements())
                if added and added[0][1] != QUESTION:
                    raise RuntimeError('Unrelated QC write')
            elif Counter(old) != Counter(new):
                raise RuntimeError('Protected history changed: ' + table)


def plan(args):
    args.output.mkdir(parents=True, exist_ok=False)
    original = json.loads((ORIGINAL / 'plan.json').read_text())
    database = Path(original['database'])
    with common.readonly(database) as db:
        common.ensure_no_active_tasks(db)
        tables = common.table_fingerprints(db)
    # SQLite Backup API, not filesystem copying of a live database.
    common.backup_database(database, args.output / 'before.db')
    assets = args.output / 'assets'; assets.mkdir()
    shutil.copytree(original['index'], assets / 'index')
    shutil.copytree(original['documents'], assets / 'documents')
    uploads = database.parent / 'uploads'
    if uploads.exists(): shutil.copytree(uploads, assets / 'uploads')
    else: (assets / 'uploads').mkdir()
    shutil.copytree(ORIGINAL, args.output / 'original-execution')
    delegation = database.parent / 'owner-delegated-review.json'
    if delegation.exists(): shutil.copy2(delegation, assets / delegation.name)
    (assets / 'empty.env').write_text('')
    common.bind_environment(args.output / 'before.db', assets / 'index', assets / 'documents', assets / 'empty.env', assets / 'uploads')
    os.environ['RAG_SAFE_START'] = '1'
    with offline():
        from app.governance import GovernanceStore
        from app.corpus import CorpusStore
        store = GovernanceStore(args.output / 'before.db', migrate=False)
        current = state(store)
        request = capture_request(store, CorpusStore(assets / 'index'))
        # Prove the real recovery transition on a separate copy, never on formal data.
        common.backup_database(args.output / 'before.db', args.output / 'resume-check.db')
        check = GovernanceStore(args.output / 'resume-check.db', migrate=False)
        resumed = check.resume_revision_quality(REVISION)
        if resumed['status'] != 'qc' or not resumed['failure_history'] or resumed['failure_history'][-1]['error'] != current['revision']['error']:
            raise RuntimeError('Real resume did not preserve original error')
        preserve(args.output / 'before.db', args.output / 'resume-check.db')
    with common.readonly(database) as db:
        if common.table_fingerprints(db) != tables:
            raise RuntimeError('Formal database changed during offline preflight')
    old_ledger = json.loads((ORIGINAL / 'ledger.json').read_text())
    common.require_known_usage(old_ledger['calls'])
    if old_ledger['calls'][-1].get('task') != 'qc':
        raise ValueError('Original failed QC request accounting required')
    from app.config import Settings
    from app.providers import DeepSeekProvider
    from app.paid_run import execution_limits, provider_task
    with execution_limits({'qc': LIMIT}), provider_task('qc'):
        wire_payload = json.loads(DeepSeekProvider(Settings('OFFLINE-NOT-A-CREDENTIAL',
            original['endpoints']['deepseek'].removesuffix('/chat/completions'), original['model']))._request(
                request['system'], request['user'], True, False, 0).data)
    files = {str(ROOT / 'backend/app' / name): common.file_sha(ROOT / 'backend/app' / name) for name in common.CODE}
    files.update({str(Path(__file__).resolve()): common.file_sha(__file__), str(Path(common.__file__).resolve()): common.file_sha(common.__file__)})
    protection_files = {str(p.resolve()): common.file_sha(p) for p in uploads.rglob('*') if p.is_file()} if uploads.exists() else {}
    if delegation.exists(): protection_files[str(delegation.resolve())] = common.file_sha(delegation)
    files.update(protection_files)
    prices = ROOT / 'docs/judge_vnext_20261030/golden_frozen_price_estimates.json'
    files[str(prices)] = common.file_sha(prices)
    result = {'schema': 'q36-single-qc-recovery-1', 'database': str(database), 'index': original['index'],
        'documents': original['documents'], 'env_file': original['env_file'], 'source_tables': tables,
        'source_files': files, 'assets': common.asset_hashes(original['index'], original['documents']),
        'original_execution_files': {str(p.resolve()): common.file_sha(p) for p in sorted(ORIGINAL.iterdir()) if p.is_file()},
        'environment_sha256': common.file_sha(original['env_file']), 'prices': str(prices),
        'endpoint': original['endpoints']['deepseek'], 'model': original['model'], 'current': current,
        'wire_payload': wire_payload, 'wire_payload_sha256': common.digest(wire_payload),
        'original_accounting': {'calls': len(old_ledger['calls']), 'known_usage': True, 'last_request_sha256': old_ledger['calls'][-1]['request_sha256']},
        'request': request, 'request_sha256': common.digest(request), 'max_qc_calls': 1, 'max_tokens': LIMIT,
        'forbidden': ['similarity', 'business_audit', 'Probe', 'Q13/Q15 calls', 'review', 'freeze', 'Baseline', 'Candidate', 'Sandbox'],
        'preflight': {'paid_calls': 0, 'formal_writes': 0, 'real_resume_on_copy': True,
                      'original_error_preserved': True, 'q13_q15_current_identity_valid': True}}
    result['plan_sha256'] = common.digest(result)
    common.save(args.output / 'plan.json', result)
    common.save(args.output / 'request.json', request)
    common.save(args.output / 'wire_payload.json', wire_payload)
    return result


def validate_outgoing(reviewed, calls, provider, model, payload):
    if (calls or provider != 'DeepSeek' or model != reviewed['model']
            or payload != reviewed['wire_payload']):
        raise RuntimeError('Only one exact reviewed Q36 QC request permitted')


def execute(args, reviewed):
    common.require_authorization(json.loads(args.authorization.read_text()), reviewed['plan_sha256'], 'q36-qc-recovery')
    for path, expected in {**reviewed['source_files'], **reviewed['assets'], **reviewed['original_execution_files']}.items():
        if common.file_sha(path) != expected: raise ValueError('Reviewed source/asset changed: ' + path)
    if common.file_sha(reviewed['env_file']) != reviewed['environment_sha256']:
        raise ValueError('Provider environment changed')
    with common.readonly(reviewed['database']) as db:
        common.ensure_no_active_tasks(db)
        if common.table_fingerprints(db) != reviewed['source_tables']: raise ValueError('Reviewed database state changed')
    # Entire current DB and material archive must exist before any formal transition.
    common.backup_database(reviewed['database'], args.output / 'execute-before.db')
    shutil.copy2(args.authorization, args.output / 'execution-authorization.json')
    common.bind_environment(reviewed['database'], reviewed['index'], reviewed['documents'], reviewed['env_file'], Path(reviewed['database']).parent / 'uploads')
    from app.governance import GovernanceStore
    from app.corpus import CorpusStore
    from app.config import load_settings
    from app.providers import DeepSeekProvider
    from app.ai_service import AiService
    from app.paid_run import PaidRun, controlled_run
    settings = load_settings()
    if common.endpoint(settings.base_url, '/chat/completions') != reviewed['endpoint'] or settings.model != reviewed['model']:
        raise ValueError('Provider route/model changed')
    store = GovernanceStore(reviewed['database'], migrate=False); corpus = CorpusStore(Path(reviewed['index']))
    if state(store) != reviewed['current'] or common.digest(capture_request(store, corpus)) != reviewed['request_sha256']:
        raise ValueError('Quality identity or exact outgoing QC payload drift')
    def identity():
        for path, expected in {**reviewed['source_files'], **reviewed['assets']}.items():
            if common.file_sha(path) != expected: raise RuntimeError('Code/Corpus changed during recovery')
        if store.capture_quality(QUESTION, qc=True)[1] != reviewed['current']['quality_identity']:
            raise RuntimeError('Q36 quality identity changed')
        return {'plan_sha256': reviewed['plan_sha256'], 'question_id': QUESTION, 'revision_id': REVISION}
    class SingleLedger(PaidRun):
        def begin(self, provider, model, payload):
            validate_outgoing(reviewed, self.calls, provider, model, payload)
            result = super().begin(provider, model, payload)
            result.update(request_payload=payload, actual_debit=None, actual_debit_status='not_reported_by_provider')
            self.save(); return result
    prices = json.loads(Path(reviewed['prices']).read_text()); common.validate_prices(prices, reviewed['model'])
    ledger = SingleLedger(args.output / 'ledger.json', prices=prices, identity=identity(), identity_check=identity, output_limits={'qc': LIMIT})
    resumed = store.resume_revision_quality(REVISION)
    if resumed['status'] != 'qc': raise RuntimeError('Recovery unexpectedly needs Probe; stop')
    try:
        with controlled_run(ledger):
            service = AiService(ProjectedStore(store), corpus, DeepSeekProvider(settings), False)
            item, execution = store.capture_quality(QUESTION, qc=True)
            qc = common.single_quality_check(service, item)
            common.require_known_usage(ledger.calls)
            saved = store.record_qc(QUESTION, qc, 'qc_passed', execution=execution)
            if saved['status'] != 'qc_passed' or qc.get('priority') != 'P2' or saved['result']['content_validation']['status'] != 'supported':
                raise RuntimeError('Real QC failed; no repair/retry/review/freeze')
            store.finish_revision_quality(REVISION, {QUESTION: {'probe': 'passed', 'qc': saved['status']}})
    except Exception as error:
        store.finish_revision_quality(REVISION, {}, error=str(error), error_type=type(error).__name__, error_detail='Failed stage: qc; one-shot recovery, no retry')
        preserve(args.output / 'execute-before.db', reviewed['database'])
        common.save(args.output / 'result.json', {'status': 'failed_quality', 'calls': len(ledger.calls), 'error_type': type(error).__name__, 'revision': store.revision_run(REVISION)})
        raise
    preserve(args.output / 'execute-before.db', reviewed['database'])
    result = {'status': 'quality_complete_review_required', 'calls': len(ledger.calls), 'reviewed': False, 'frozen': False,
              'revision': store.revision_run(REVISION), 'qc': saved}
    common.save(args.output / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--authorization', type=Path)
    args = parser.parse_args()
    if args.execute:
        if not args.authorization: parser.error('Explicit plan-bound authorization required')
        reviewed = json.loads((args.output / 'plan.json').read_text())
        if common.digest({k:v for k,v in reviewed.items() if k != 'plan_sha256'}) != reviewed['plan_sha256']:
            raise ValueError('Reviewed plan modified')
        result = execute(args, reviewed)
    else:
        reviewed = plan(args); result = {'status': 'dry_run', 'plan_sha256': reviewed['plan_sha256'], **reviewed['preflight']}
    print(json.dumps(result, ensure_ascii=False, indent=2) if not args.execute else json.dumps({k:result[k] for k in ['status','calls','reviewed','frozen']}, ensure_ascii=False))

if __name__ == '__main__': main()
