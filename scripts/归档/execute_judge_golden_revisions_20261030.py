"""Plan by default. Explicit, separately authorized stages revise three contracts,
then consume independent Owner Delegated AI reviews and freeze all 50 questions.
Never imports app.main or starts Baseline/Candidate/Sandbox. No automatic resume.
"""
import argparse
import hashlib
import json
import math
import os
import shutil
import socket
import sqlite3
import sys
from contextlib import closing, contextmanager
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
CODE = ['governance.py', 'scoring_contract.py', 'ai_service.py', 'delegated_review.py',
        'golden_v2.py', 'paid_run.py', 'providers.py', 'retrieval.py', 'policy.py', 'knowledge_pipeline.py']


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def file_sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


@contextmanager
def readonly(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        yield connection


def table_hashes(connection, *, exclude_questions=()):
    result = {}
    tables = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    for table in sorted(tables):
        quoted = '"' + table.replace('"', '""') + '"'
        cursor = connection.execute('SELECT * FROM ' + quoted)
        names = [c[0] for c in cursor.description]
        hashes = []
        for row in cursor:
            if table == 'questions' and row[names.index('id')] in exclude_questions:
                continue
            hashes.append(digest([{'blob_sha256': hashlib.sha256(v).hexdigest()} if isinstance(v, bytes) else v for v in row]))
        result[table] = sorted(hashes)
    return result


def table_fingerprints(connection):
    return {name: {'rows': len(rows), 'sha256': digest(rows)} for name, rows in table_hashes(connection).items()}


def ensure_no_active_tasks(connection):
    for table, statuses in [('evaluation_runs', ('queued','running')), ('golden_generation_runs', ('queued','coverage','generating','validation','probing','qc')), ('agent_traces', ('running',)), ('candidate_revision_runs', ('queued','generating','validating','probing','qc'))]:
        status = "coalesce(CASE WHEN json_valid(audit_json) THEN json_extract(audit_json,'$.status') END,status)" if table == 'candidate_revision_runs' else 'status'
        if connection.execute(f"SELECT 1 FROM {table} WHERE {status} IN ({','.join('?' for _ in statuses)}) LIMIT 1", statuses).fetchone():
            raise RuntimeError('Active task; controlled maintenance refused: ' + table)


def backup_database(source, target):
    if Path(target).exists():
        raise ValueError('Backup already exists; no automatic resume')
    with readonly(source) as before, closing(sqlite3.connect(target)) as after:
        before.backup(after)


def assert_preserved(backup, database, targets, *, allow_snapshot=False):
    from collections import Counter
    with readonly(backup) as db:
        old = table_hashes(db, exclude_questions=targets)
    with readonly(database) as db:
        new = table_hashes(db, exclude_questions=targets)
    mutable = {'questions', 'candidate_revision_runs', 'review_events', 'question_quality_audits', 'probe_results', 'qc_results', 'approvals'}
    if allow_snapshot:
        mutable.add('dataset_versions')
    for table, rows in old.items():
        if Counter(rows) - Counter(new.get(table, [])) or table not in mutable and rows != new.get(table):
            raise RuntimeError('Historical data changed: ' + table)
    if len(new['questions']) != len(old['questions']):
        raise RuntimeError('Unrelated question rows added')


def load_changes(proposals_path, manifest_path):
    proposals = json.loads(Path(proposals_path).read_text())
    manifest = json.loads(Path(manifest_path).read_text())
    sources = manifest.get('source_files', [])
    if not sources:
        raise ValueError('Source hash manifest required')
    for source in sources:
        if file_sha(source['path']) != source['sha256']:
            raise ValueError('Source hash drift: ' + source['path'])
    contracts = [(c['golden_item']['id'], c['golden_item']['raw']['business_requirements']) for c in manifest['cases']]
    if not contracts or any(c != contracts[0] for c in contracts):
        raise ValueError('Q13 manifests disagree')
    q13, contract = contracts[0]
    changes = {q13: {'business_requirements': contract}}
    for row in proposals['rows']:
        changes[row['question_id']] = {'business_requirements': row['proposed_after']}
    if len(changes) != 3:
        raise ValueError('Exactly Q13/Q15/Q36 required')
    files = {str(Path(p).resolve()): file_sha(p) for p in [proposals_path, manifest_path, *[s['path'] for s in sources]]}
    return proposals['original_snapshot'], changes, files


class RequestCaps:
    def __init__(self, limits):
        self.limits, self.used = limits, {}

    def reserve(self, model):
        if self.used.get(model, 0) >= self.limits.get(model, 0):
            raise RuntimeError('RPC limit reached before request: ' + model)
        self.used[model] = self.used.get(model, 0) + 1


def require_authorization(auth, plan_sha, stage):
    if (auth.get('source') != 'direct_user_instruction' or auth.get('actor') != 'Codex'
            or auth.get('plan_sha256') != plan_sha or stage not in auth.get('allowed_stages', [])
            or not auth.get('source_file') or file_sha(auth['source_file']) != auth.get('source_sha256')):
        raise ValueError('Explicit authorization must bind source, reviewed plan and stage')


def validate_prices(prices, model):
    for name, provider in [(model, 'DeepSeek'), ('text-embedding-v4', 'Alibaba'), ('qwen3-rerank', 'Alibaba')]:
        rate = prices.get(name, {})
        if rate.get('provider') != provider or any(type(rate.get(k)) not in (int, float) or not math.isfinite(rate[k]) or rate[k] < 0 for k in ('input', 'output', 'max_output')):
            raise ValueError('Explicit valid price snapshot required: ' + name)
        if name == model and rate['max_output'] < 16384:
            raise ValueError('Frozen price output bound insufficient')


def require_known_usage(calls):
    for call in calls:
        usage = call.get('usage') or {}
        counts = (usage.get('prompt_tokens', usage.get('total_tokens')),
                  usage.get('completion_tokens', 0 if call.get('provider') == 'Alibaba' else None))
        if (call.get('status') != 'ok' or usage.get('status') != 'ok'
                or usage.get('provider') != call.get('provider') or usage.get('requested_model') != call.get('model')
                or usage.get('request_execution_unknown') is True
                or any(type(value) is not int or value < 0 for value in counts)):
            raise RuntimeError('Unknown request/Usage; stop before next phase')


def single_quality_check(service, item):
    """Keep existing QC validation/telemetry, without its correction-retry loop."""
    from app.paid_run import provider_task
    from app.telemetry import measure, collect_usage, cost_fields
    stages = []
    with provider_task('qc'), measure(stages, 'qc'), collect_usage() as usage:
        result = service._quality_check(item)
    return {**result, 'response_retries': 0, 'response_recovery': [], 'stages': stages,
            'token_usage': usage, **cost_fields(service.model, usage)}


@contextmanager
def revision_failure_checkpoint(store, revision_id, stage):
    try:
        yield
    except Exception as error:
        run = store.revision_run(revision_id)
        if run.get('applied_at') and run['status'] in {'probing', 'qc', 'interrupted'}:
            store.update_revision(revision_id, stage=stage)
            store.finish_revision_quality(revision_id, run.get('quality_results') or {},
                error=str(error), error_type=type(error).__name__, error_detail='Failed stage: ' + stage)
        raise


def bind_environment(database, index, documents, env_file, uploads):
    for key, path in {'RAG_DEMO_DB_PATH': database, 'RAG_DEMO_INDEX_DIR': index,
                      'RAG_DEMO_DOCUMENTS_DIR': documents, 'RAG_DEMO_ENV_PATH': env_file,
                      'RAG_DEMO_UPLOADS_DIR': uploads}.items():
        os.environ[key] = str(Path(path).resolve())
    sys.path.insert(0, str(ROOT / 'backend'))


def asset_hashes(index, documents):
    return {str(p.resolve()): file_sha(p) for folder in (index, documents) for p in sorted(Path(folder).rglob('*')) if p.is_file()}


def endpoint(base, suffix):
    parsed = urlsplit(base)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.query or parsed.fragment:
        raise ValueError('HTTPS provider base without credentials/query required')
    return base.rstrip('/') + suffix


def create_plan(args):
    snapshot_id, changes, files = load_changes(args.proposals, args.q13_manifest)
    for name in CODE:
        path = ROOT / 'backend/app' / name; files[str(path)] = file_sha(path)
    files[str(Path(__file__).resolve())] = file_sha(__file__)
    args.output.mkdir(parents=True, exist_ok=False)
    backup_database(args.database, args.output / 'before.db')
    isolated = args.output / 'isolated'; isolated.mkdir()
    shutil.copytree(args.index.resolve(), isolated / 'index')
    shutil.copytree(args.documents, isolated / 'documents')
    (isolated / 'empty.env').write_text(''); (isolated / 'uploads').mkdir()
    bind_environment(args.output / 'before.db', isolated / 'index', isolated / 'documents', isolated / 'empty.env', isolated / 'uploads')
    def no_network(*_args, **_kwargs):
        raise RuntimeError('Network forbidden in dry-run')
    socket.socket.connect = no_network
    from app.config import load_values
    from app.corpus import CorpusStore, current_manifest, manifest_identity
    from app.governance import GovernanceStore
    from app.scoring_contract import compile_contract
    from app.delegated_review import verify_pdf_sources
    from app.evaluation_contract import normalize
    from app.ai_service import AiService
    from app.paid_run import REQUEST_LIMITS
    import pymupdf
    store = GovernanceStore(args.output / 'before.db', migrate=False)
    with readonly(args.output / 'before.db') as db:
        snapshot_text = db.execute('SELECT snapshot_json FROM dataset_versions WHERE id=?', (snapshot_id,)).fetchone()[0]
        frozen = json.loads(snapshot_text)
        tables = table_fingerprints(db)
    if len(frozen['question_ids']) != 50 or set(changes) - set(frozen['question_ids']):
        raise ValueError('Complete frozen 50-question source required')
    corpus = manifest_identity(current_manifest())
    if corpus != frozen['corpus_fingerprint']:
        raise ValueError('Corpus identity differs from frozen source')
    values = load_values(env_file=args.env_file)
    model = values.get('DEEPSEEK_MODEL', 'deepseek-flash').replace('deepseek-v4-flash', 'deepseek-flash')
    if model != 'deepseek-flash':
        raise ValueError('Verified Flash route/model required')
    prices = json.loads(args.prices.read_text())
    validate_prices(prices, model)
    files[str(args.prices.resolve())] = file_sha(args.prices)
    endpoints = {'deepseek': endpoint(values.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'), '/chat/completions'),
                 'embedding': endpoint(values.get('DASHSCOPE_BASE_URL', ''), '/compatible-mode/v1/embeddings'),
                 'rerank': endpoint(values.get('DASHSCOPE_BASE_URL', ''), '/compatible-api/v1/reranks')}
    items = {key: store.question(key) for key in frozen['question_ids']}
    offline_service = AiService(store, CorpusStore(isolated / 'index'), None, True)
    by_chunk = {c['chunk_id']: c for c in CorpusStore().chunks()}
    def peer_metadata(peer):
        raw = peer['raw']
        keys = raw.get('coverage_anchor_chunk_ids', []) if peer['test_category'] == 'negative' else [c for e in peer['evidence'] for c in e['source_chunk_ids']]
        products = {by_chunk.get(c, {}).get('product') for c in keys}
        return {'id': peer['id'], 'slot': raw.get('coverage_slot'), 'question': peer['question'],
                'test_category': peer['test_category'], 'negative_subtype': peer.get('negative_subtype'),
                **{k: raw.get(k) for k in ('user_role','business_scenario','user_intent','expected_behavior','topic_cluster')},
                'product': raw.get('product') or (next(iter(products)) if len(products) == 1 else None)}
    for original in frozen['questions']:
        if original != items[original['id']]['raw']:
            raise ValueError('Source Snapshot/current edition differs: ' + original['id'])
    for proposal in json.loads(args.proposals.read_text())['rows']:
        if proposal['before'] != items[proposal['question_id']]['raw']['business_requirements']:
            raise ValueError('Proposal before differs from current contract')
    targets, reuse, pdf_checks = [], [], []
    for key, item in items.items():
        if key not in changes:
            eligible = store.approval_eligibility(key)
            history = next((e for e in store.review_history(key) if e['gate'] == 'dataset'), {})
            _, identity = store.capture_quality(key)
            with store.connection() as db:
                qc_id = db.execute('SELECT MAX(id) FROM qc_results WHERE question_id=?', (key,)).fetchone()[0]
            reusable = item['stage'] == 'golden' and item['review_status'] == 'approved' and eligible['can_approve'] and history.get('quality_identity') == identity and history.get('review_qc_id') == qc_id
            reuse.append({'question_id': key, 'reusable': reusable, 'quality_identity': identity, 'qc_id': qc_id, 'reasons': eligible['blocking_reasons']})
            continue
        draft = {**item, 'raw': {**item['raw'], **changes[key]}}
        compiled = compile_contract(draft)
        sources = draft['raw']['business_requirements']['sources']
        for source in sources:
            located = None
            with pymupdf.open(isolated / 'documents' / source['document']) as pdf:
                text = normalize(source['quote'])
                for page in range(source['pages'][0], source['pages'][1] + 1):
                    pdf_text = normalize(pdf[page - 1].get_text())
                    for offset in range(max(0, len(text) - 11)):
                        quote = text[offset:offset + 12]
                        record = {'chunk_id': source['chunk_id'], 'document_id': source['document_id'], 'page': page, 'quote': quote}
                        if len(quote) == 12 and quote in pdf_text and verify_pdf_sources([record]):
                            located = record; break
                    if located:
                        break
            pdf_checks.append({'question_id': key, 'chunk_id': source['chunk_id'], 'verified': bool(located), 'availability_probe_only': located})
        targets.append({'question_id': key, 'slot': item['raw']['coverage_slot'], 'question': item['question'],
                        'reference_answer': item['reference_answer'], 'expected_response': item['raw'].get('expected_response'),
                        'changes': changes[key], 'compiled_contract_hash': compiled['compiled_contract_hash'],
                        'canonical_sources': sources,
                        'business_audit_metadata': {k: item['raw'].get(k) for k in ('user_role','business_scenario','user_intent','difficulty','business_negative','expected_behavior','expected_response','topic_cluster','product_scope','source_scope','generation_path','business_design','business_design_provenance','business_draft_revision')},
                        'business_audit_parent_context': offline_service.business_parent_context({'sources': [by_chunk[s['chunk_id']] for s in sources]}) if item['raw'].get('generation_path') == 'business_question_first' else [],
                        'business_audit_prior_revisions': offline_service._business_audit_revisions(item),
                        'business_audit_peer_question_ids': [q for q in items if q != key],
                        'business_audit_peer_metadata': [peer_metadata(peer) for q, peer in items.items() if q != key]})
    plan = {'schema': 'judge-golden-controlled-plan-1', 'snapshot_id': snapshot_id,
            'source_snapshot_sha256': hashlib.sha256(snapshot_text.encode()).hexdigest(),
            'database': str(args.database.resolve()), 'index': str(args.index.resolve()), 'documents': str(args.documents.resolve()), 'env_file': str(args.env_file.resolve()), 'source_database_sha256': file_sha(args.database), 'source_tables': tables,
            'generation_run_id': frozen['generation_run_id'], 'question_ids': frozen['question_ids'],
            'corpus': corpus, 'source_files': files, 'assets': asset_hashes(args.index, args.documents),
            'endpoints': endpoints, 'model': model, 'targets': targets, 'reuse_47': reuse,
            'pdf_availability': {'pymupdf': pymupdf.VersionBind, 'checks': pdf_checks, 'is_ai_approval': False},
            'external_disclosure': {'similarity': {'question_ids': list(items), 'texts': [q['question'] for q in items.values()], 'batch_size': 10, 'max_rpc': 5, 'cache': 'no persisted verified vectors; all saved semantic similarities not_run; one service memory cache reused for prepare/apply'},
                'business_audit': 'Each target complete contract/normative sources, parent context and parsed source pages, recorded revisions plus its 49 peer question texts and saved role/scenario/intent/expected-behavior/Topic/product metadata; total scope all 50 stems, not only three. Exact saved metadata and contexts are listed per target; the new applied contract revision is also sent.',
                'probe': {'question_ids': list(changes), 'retrieval_corpus_chunk_ids': [c['chunk_id'] for c in CorpusStore().chunks()], 'rerank_max_chunks_per_question': 12, 'final_max_chunks_per_question': 4, 'dynamic_sources': 'Actual full-Corpus retrieval selection unknown before query embedding; recorded RPC payloads must be reviewed, never claim predetermined sources.'},
                'qc': 'Each target contract/normative sources and real Probe trace including retrieved candidates/Final; Q36 may send actual Final to answerability Judge.'},
            'rpc_maxima': {'similarity_embedding': 5, 'business_audit': 3, 'probe_embedding': 3, 'probe_rerank': 3, 'answerability_Q36': 1, 'qc': 3, 'total': 18, 'retries': 0},
            'output_limits': {k: REQUEST_LIMITS[k] for k in ('business_audit','qc','answerability')},
            'price_snapshot': {'path': str(args.prices.resolve()), 'sha256': file_sha(args.prices), 'rates': prices, 'actual_account_debit': 'UNKNOWN: not returned by these APIs; estimates retain USD/CNY without invented conversion'},
            'workflow': ['reopen/start/prepare/apply existing Revision', 'new business audit/Probe/QC for three targets', 'stop for independent AI review and new current-hash delegation', 'validate_delegation then review_owner_delegated_batch for targets; reuse 47 bound quality/reviews', 'create_dataset_snapshot(all50,generation_run_id), never create_generation_snapshot shortcut'],
            'reference_alignment': {'Q15': 'Existing reference step1 releases switch at destination; step2 sets parameters then activates cleaning head; step3 holds switch again and pushes. R6 is covered; no reference edit.', 'Q36': 'Preserve expected_response verbatim; local 30 seconds remains auxiliary, not a required omission test or whole-system acceptance guarantee.'},
            'authorization_registration': 'No registration function exists: externally authored current authorization is validated first, then installed at store.database_path.parent/owner-delegated-review.json with old file backup. No human flags or auto-authored reviews.',
            'stop_policy': 'Any RPC quota, technical/semantic quality failure, unknown request/usage, schema error or identity drift stops immediately; no retry/resume/automatic approval. Actual debit UNKNOWN alone does not block known request/Usage and source-backed estimates. QC uses a script-local single attempt; no JSON correction RPC.',
            'blockers': [r['question_id'] + ': old quality/review cannot be reused' for r in reuse if not r['reusable']] + [p['chunk_id'] + ': PDF unavailable' for p in pdf_checks if not p['verified']]}
    plan['plan_sha256'] = digest(plan)
    save(args.output / 'plan.json', plan)
    with readonly(args.database) as db:
        if table_fingerprints(db) != tables:
            raise RuntimeError('Formal database changed during dry-run')
    return plan


def execute(args, plan):
    require_authorization(json.loads(args.authorization.read_text()), plan['plan_sha256'], args.stage)
    if plan['blockers']:
        raise ValueError('Reviewed plan contains unresolved blockers')
    for key in ('database', 'index', 'documents', 'env_file'):
        if str(getattr(args, key).resolve()) != plan[key]:
            raise ValueError('Reviewed execution path differs: ' + key)
    for path, expected in {**plan['source_files'], **plan['assets']}.items():
        if file_sha(path) != expected:
            raise ValueError('Reviewed source/asset drift: ' + path)
    bind_environment(args.database, args.index, args.documents, args.env_file, args.database.parent / 'uploads')
    from app.governance import GovernanceStore
    from app.corpus import CorpusStore, current_manifest, manifest_identity
    from app.config import load_settings, load_values
    from app.providers import DeepSeekProvider
    from app.ai_service import AiService
    from app.paid_run import PaidRun, controlled_run, provider_task, REQUEST_LIMITS
    from app.business_golden import audit_passed
    values = load_values()
    actual_endpoints = {'deepseek': endpoint(load_settings().base_url, '/chat/completions'), 'embedding': endpoint(values.get('DASHSCOPE_BASE_URL', ''), '/compatible-mode/v1/embeddings'), 'rerank': endpoint(values.get('DASHSCOPE_BASE_URL', ''), '/compatible-api/v1/reranks')}
    if actual_endpoints != plan['endpoints'] or load_settings().model != plan['model']:
        raise ValueError('Reviewed Provider route/model changed')
    store = GovernanceStore(args.database, migrate=False); corpus = CorpusStore(args.index)
    targets = {r['question_id']: r for r in plan['targets']}
    def identity():
        if manifest_identity(current_manifest()) != plan['corpus']:
            raise RuntimeError('Corpus drift during execution')
        for path, expected in plan['source_files'].items():
            if file_sha(path) != expected:
                raise RuntimeError('Source drift during execution')
        return {'plan_sha256': plan['plan_sha256'], 'corpus': plan['corpus']}
    identity()
    if str(args.database.resolve()) != plan['database']:
        raise ValueError('Reviewed database path differs')
    with readonly(args.database) as db:
        before = table_fingerprints(db)
        ensure_no_active_tasks(db)
    state_path = args.output / 'state.json'
    if args.stage == 'revise-quality':
        if state_path.exists() or before != plan['source_tables']:
            raise ValueError('State/database changed; no automatic resume')
        if args.prices is None:
            raise ValueError('Explicit frozen price snapshot required before paid execution')
        prices = json.loads(args.prices.read_text())
        validate_prices(prices, plan['model'])
        if str(args.prices.resolve()) != plan['price_snapshot']['path'] or file_sha(args.prices) != plan['price_snapshot']['sha256']:
            raise ValueError('Reviewed frozen price snapshot changed')
        shutil.copy2(args.authorization, args.output / 'revise-quality-authorization.json')
        save(args.output / 'frozen-prices.json', prices)
        backup_database(args.database, args.output / 'execute-before.db')
        service = AiService(store, corpus, DeepSeekProvider(load_settings()), False)
        class BoundedLedger(PaidRun):
            quota = None
            def begin(self, provider, model, payload):
                self.quota.reserve(model)
                call = super().begin(provider, model, payload)
                call.update(actual_debit=None, actual_debit_status='not_reported_by_provider')
                call['request_payload'] = payload; self.save(); return call
        ledger = BoundedLedger(args.output / 'ledger.json', prices=prices, identity=identity(), identity_check=identity, output_limits=REQUEST_LIMITS)
        @contextmanager
        def phase(name, caps):
            ledger.quota = RequestCaps(caps)
            with controlled_run(ledger):
                yield
                require_known_usage(ledger.calls)
            save(args.output / (name + '.json'), {'calls': len(ledger.calls), 'used': ledger.quota.used, 'actual_account_debit': 'UNKNOWN', 'usage_status': 'known', 'price_basis': plan['price_snapshot']['sha256'], 'estimates': [c.get('estimated_cost') for c in ledger.calls]})
        with phase('similarity', {'text-embedding-v4': 5}), provider_task('revision'):
            service.prepare_revision_similarity(plan['external_disclosure']['similarity']['texts'])
        revisions = {}
        for key, target in targets.items():
            store.reopen_snapshot_question(key, plan['snapshot_id'], actor='Codex', reason='Authorized source-bound Judge contract revision', authorization=plan['plan_sha256'])
            revision = store.start_revision(key, 'manual_edit', 'Authorized source-bound contract revision', False, {key: target['changes']}, corpus.chunks(), actor='Codex')
            with phase(key + '-revision', {}):
                prepared = store.prepare_revision(revision['id'], corpus.chunks(), similarity=service.revision_similarity)
                if prepared['status'] != 'preview_ready' or not prepared['validation']['passed']:
                    raise RuntimeError('Revision structural validation blocked')
                store.apply_revision(revision['id'], corpus.chunks(), similarity=service.revision_similarity)
            revisions[key] = revision['id']
            item = store.question(key)
            with revision_failure_checkpoint(store, revision['id'], 'business_audit'), phase(key + '-audit', {plan['model']: 1}):
                audit = service.business_quality_audit(item, [store.question(q)['question'] for q in plan['question_ids'] if q != key])
                store.save_quality_audit(key, audit)
                if not audit_passed(audit):
                    raise RuntimeError('Business Audit requires independent adjudication; stop before Probe')
            with revision_failure_checkpoint(store, revision['id'], 'probe'), phase(key + '-probe', {'text-embedding-v4': 1, 'qwen3-rerank': 1, plan['model']: 1 if target['slot'] == 'Q36' else 0}):
                probe = store.run_probe(key, service.retriever, corpus.chunks(), service.answerability_check, subtype_judge=service.negative_subtype_check, fail_on_judge_error=True)
                if probe['status'] != 'passed':
                    raise RuntimeError('Probe did not pass; no QC or retry')
            with revision_failure_checkpoint(store, revision['id'], 'qc'), phase(key + '-qc', {plan['model']: 1}):
                candidate, execution_identity = store.capture_quality(key, qc=True)
                qc = single_quality_check(service, candidate)
                saved = store.record_qc(key, qc, 'qc_passed', execution=execution_identity)
                if saved['status'] != 'qc_passed' or qc.get('priority') == 'P1' or saved['result'].get('content_validation', {}).get('status') != 'supported':
                    raise RuntimeError('QC did not pass; independent adjudication required')
                store.finish_revision_quality(revision['id'], {key: {'probe': probe['status'], 'qc': saved['status']}})
        assert_preserved(args.output / 'execute-before.db', args.database, targets)
        with readonly(args.database) as db:
            after = table_fingerprints(db)
        save(state_path, {'status': 'quality_complete_review_required', 'revisions': revisions, 'tables': after, 'plan_sha256': plan['plan_sha256']})
        save(args.output / 'independent-review-input.json', {'generation_run': store.generation_run(plan['generation_run_id'], qualification=False), 'rows': store.candidate_rows(plan['question_ids']), 'targets': [store.question(q) for q in targets], 'content_hashes': {q: store._quality_content(store.question(q)) for q in plan['question_ids']}})
        return {'status': 'quality_complete_review_required', 'freeze': False}
    state = json.loads(state_path.read_text())
    if state['status'] != 'quality_complete_review_required' or state['tables'] != before or state['plan_sha256'] != plan['plan_sha256']:
        raise ValueError('Post-quality state changed; no implicit resume')
    if args.delegation is None or args.reviews is None:
        raise ValueError('New current-content owner delegation and independent AI reviews required')
    from app.delegated_review import validate_delegation
    auth = json.loads(args.delegation.read_text()); reviews = json.loads(args.reviews.read_text())
    shutil.copy2(args.authorization, args.output / 'review-freeze-authorization.json')
    execution_auth = json.loads(args.authorization.read_text())
    if auth.get('source_file') != execution_auth.get('source_file') or auth.get('source_sha256') != execution_auth.get('source_sha256'):
        raise ValueError('Delegation source differs from the explicitly approved execution instruction')
    if {r['question_id'] for r in reviews} != set(targets):
        raise ValueError('Independent reviews must cover exactly the three revised questions')
    items = {q: store.question(q) for q in plan['question_ids']}
    validate_delegation(args.delegation, auth['authorization_id'], store.generation_run(plan['generation_run_id'], qualification=False), store.candidate_rows(plan['question_ids']), items, reviews, store._quality_content)
    backup_database(args.database, args.output / 'before-review-freeze.db')
    destination = args.database.parent / 'owner-delegated-review.json'
    if destination.exists():
        shutil.copy2(destination, args.output / 'previous-owner-delegated-review.json')
    temporary = destination.with_suffix('.pending.json'); shutil.copy2(args.delegation, temporary); temporary.chmod(0o600); os.replace(temporary, destination)
    store.review_owner_delegated_batch(plan['generation_run_id'], auth['authorization_id'], reviews)
    run = store.generation_run(plan['generation_run_id'], qualification=False)
    if store.gate_summary(run, store.candidate_rows(plan['question_ids']))['status'] != 'ready':
        raise RuntimeError('Full 50-question Human Gate not ready')
    snapshot = store.create_dataset_snapshot([store.question(q) for q in plan['question_ids']], generation_run_id=plan['generation_run_id'])
    assert_preserved(args.output / 'execute-before.db', args.database, targets, allow_snapshot=True)
    save(args.output / 'new-snapshot.json', snapshot)
    save(state_path, {**state, 'status': 'frozen', 'new_snapshot_id': snapshot['id']})
    return {'status': 'frozen', 'snapshot_id': snapshot['id'], 'baseline_started': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--database', type=Path, default=ROOT / 'backend/data/demo.db')
    parser.add_argument('--index', type=Path, default=ROOT / 'backend/data/index')
    parser.add_argument('--documents', type=Path, default=ROOT / 'backend/documents')
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--proposals', type=Path, default=ROOT / 'docs/judge_vnext_20261029/golden_revision_proposals.json')
    parser.add_argument('--q13-manifest', type=Path, default=ROOT / 'docs/judge_vnext_20261030/q13_remaining_manifest.json')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--stage', choices=['revise-quality', 'review-freeze'], default='revise-quality')
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--prices', type=Path, default=ROOT / 'docs/judge_vnext_20261030/golden_frozen_price_estimates.json')
    parser.add_argument('--delegation', type=Path)
    parser.add_argument('--reviews', type=Path)
    args = parser.parse_args()
    if args.execute:
        if args.authorization is None:
            parser.error('--execute requires separate authorization')
        plan = json.loads((args.output / 'plan.json').read_text())
        if digest({k: v for k, v in plan.items() if k != 'plan_sha256'}) != plan['plan_sha256']:
            raise ValueError('Reviewable plan has changed')
        result = execute(args, plan)
    else:
        plan = create_plan(args)
        result = {'status': 'dry_run', 'plan_sha256': plan['plan_sha256'], 'reusable_47': sum(r['reusable'] for r in plan['reuse_47']), 'max_rpc': plan['rpc_maxima'], 'blockers': plan['blockers'], 'paid_calls': 0, 'formal_writes': 0}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
