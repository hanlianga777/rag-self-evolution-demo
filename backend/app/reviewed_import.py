"""Offline source checks for explicitly human-reviewed Medium50 CSV imports.

This provenance never creates Probe/QC results or claims machine qualification.
"""
from collections import Counter
import hashlib
import re

from .corpus import CorpusStore, current_manifest, manifest_identity


CONTRACT = 'human-reviewed-csv-v1'


def receipt_key(source_sha256, *, machine_checks=False):
    mode = 'reviewed_csv_machine_checks' if machine_checks else 'reviewed_csv'
    return hashlib.sha256((mode + ':' + source_sha256).encode()).hexdigest()


def validate_content(candidate, chunks):
    from .golden_v2 import validate_content_sources
    from .scoring_contract import compile_contract
    result = validate_content_sources(candidate, chunks)
    if result['status'] != 'passed':
        raise ValueError('人工审定导入来源检查失败：' + '；'.join(result['errors']))
    compile_contract(candidate)
    if not isinstance(candidate.get('question'), str) or not candidate['question'].strip():
        raise ValueError('人工审定导入问题不能为空')
    if candidate['business_requirements'].get('conditional_checks') != []:
        raise ValueError('人工审定导入conditional_checks必须为空列表')
    group = candidate.get('test_category')
    if group in {'positive', 'ablation'} and (not (candidate.get('reference_answer') or '').strip() or not candidate.get('evidence')):
        raise ValueError('正向和消融题须有参考答案和当前证据')
    if group == 'negative':
        behaviors = {'safety_critical':'safe_rejection', 'prompt_injection':'prompt_injection_resistance',
                     'insufficient_evidence':'insufficient_evidence', 'clarify':'clarify'}
        if candidate.get('negative_subtype') not in behaviors or candidate.get('expected_behavior') != behaviors[candidate['negative_subtype']]:
            raise ValueError('负向题子类与预期行为不匹配')


def import_batch(store, candidates, source_sha256, source, review_note, *, machine_checks=False):
    from .governance import _json, _now, _normalized, GENERATION_PROFILES
    from datetime import datetime, timezone
    from .full_text import CORPUS_LOCK
    if not re.fullmatch('[0-9a-f]{64}', source_sha256 or '') or not source.strip() or not review_note.strip():
        raise ValueError('人工审定导入须记录文件SHA256、来源及人审说明')
    if (len(candidates) != 50 or [c.get('coverage_slot') for c in candidates] != [f'Q{i:02d}' for i in range(1, 51)]
        or Counter(c.get('test_category') for c in candidates) != Counter(positive=20, ablation=10, negative=20)
        or len({_normalized(c.get('question', '')) for c in candidates}) != 50):
        raise ValueError('人工审定导入须为完整且无重复的Q01–Q50，类别20/10/20')
    with CORPUS_LOCK, store.connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        chunks = CorpusStore().chunks()
        if machine_checks:
            from .golden_v2 import validate_golden_candidate
            prepared = []
            for candidate in candidates:
                candidate = {**candidate}
                # Negative expected text/norms are not positive retrieval targets.
                if candidate['test_category'] == 'negative':
                    candidate.update(expected_response=candidate.get('expected_response') or candidate.get('reference_answer'),
                                     reference_answer=None, evidence=[], acceptable_evidence=[])
                validation = validate_golden_candidate(candidate, chunks)
                if not validation['valid']:
                    raise ValueError('机器检查导入 ' + candidate['coverage_slot'] + '：' + '；'.join(validation['blocking_errors']))
                candidate['validation'] = {key: value for key, value in validation.items() if key != 'normalized_candidate'}
                prepared.append(candidate)
            candidates = prepared
        for candidate in candidates:
            validate_content(candidate, chunks)
        key = receipt_key(source_sha256, machine_checks=machine_checks)
        previous = store.business_import_receipt(key)
        if previous:
            raise ValueError('该人工审定文件已导入，请使用已有Generation Run')
        now = _now()
        serial = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        run_id = 'GGEN-CSV-' + serial
        ids, hashes = [], {}
        provenance = 'reviewed_csv_machine_checks' if machine_checks else 'reviewed_csv'
        legacy_type = 'v1_mini' if machine_checks else 'reviewed_csv'
        contract = 'reviewed-csv-machine-checks-v1' if machine_checks else CONTRACT
        for index, candidate in enumerate(sorted(candidates, key=lambda c: c['coverage_slot']), 1):
            question_id = f'CSV-{serial}-{index:02d}'
            raw = {**candidate, 'id': question_id, 'source': provenance, 'generation_run_id': run_id,
                   'display_id': candidate['coverage_slot'], 'evaluation_group': candidate['test_category'],
                   'import_audit': {'source_sha256': source_sha256, 'source': source, 'review_note': review_note, 'imported_at': now}}
            item = {'id': question_id, 'question': raw['question'], 'reference_answer': raw.get('reference_answer'),
                    'evidence': raw.get('evidence', []), 'test_category': raw['test_category'], 'negative_subtype': raw.get('negative_subtype'),
                    'legacy_question_type': legacy_type, 'raw': raw}
            hashes[question_id] = store._quality_content(item)
            connection.execute('INSERT INTO questions (id,stage,legacy_question_type,test_category,negative_subtype,review_status,probe_status,qc_status,question,reference_answer,evidence_json,raw_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (question_id, 'candidate', legacy_type, raw['test_category'], raw.get('negative_subtype'), 'human_review_pending',
                 'probe_pending', 'qc_pending', raw['question'], raw.get('reference_answer'), _json(item['evidence']), _json(raw), now, now))
            ids.append(question_id)
        fingerprint = manifest_identity(current_manifest())
        receipt = {'kind': contract, 'source_sha256': source_sha256, 'source': source, 'review_note': review_note,
                   'generation_run_id': run_id, 'question_ids': ids, 'content_hashes': hashes, 'corpus_fingerprint': fingerprint}
        connection.execute('INSERT INTO business_import_batches VALUES (?,?)', (key, _json(receipt)))
        connection.execute('INSERT INTO golden_generation_runs VALUES (?,?,?,?,?,?)',
            (run_id, _json({'name': 'medium', **GENERATION_PROFILES['medium']}), contract, 'completed', _json(ids), now))
        connection.execute('INSERT INTO golden_generation_artifacts VALUES (?,?,?,?)',
            (run_id, _json([]), _json([]), _json({'status': 'passed', 'corpus_fingerprint': fingerprint,
              'reviewed_csv_receipt': key, 'content_hashes': hashes, 'quality_source': contract,
              **({'stop_on_technical_error': True} if machine_checks else {})})))
    return {'generation_run_id': run_id, 'question_ids': ids, 'source_sha256': source_sha256}


def validate_item(store, item, *, require_approval=False, chunks=None):
    raw = item['raw']
    run = store.generation_run(raw.get('generation_run_id'), qualification=False)
    state = (run or {}).get('artifacts', {}).get('hard_validation', {})
    key = state.get('reviewed_csv_receipt')
    receipt = store.business_import_receipt(key) if key else None
    if (raw.get('source') != 'reviewed_csv' or item.get('stage') not in {'candidate','golden'} or not receipt or receipt.get('kind') != CONTRACT
        or receipt.get('generation_run_id') != run['id'] or run['status'] != 'completed'
        or run['profile'] != {'name':'medium', 'positive_count':20, 'ablation_count':10, 'negative_count':20, 'expected_count':50}
        or receipt.get('question_ids') != run['question_ids'] or len(run['question_ids']) != 50
        or receipt.get('source_sha256') != raw.get('import_audit', {}).get('source_sha256')
        or key != receipt_key(receipt['source_sha256']) or state.get('content_hashes') != receipt.get('content_hashes')
        or receipt.get('content_hashes', {}).get(item['id']) != store._quality_content(item)
        or receipt.get('corpus_fingerprint') != manifest_identity(current_manifest())
        or state.get('corpus_fingerprint') != receipt.get('corpus_fingerprint')):
        raise ValueError('人工审定导入凭据、题卷成员、内容或当前知识库已变化')
    if any(item['id'] in revision.get('question_ids', []) for revision in store.revision_runs(run['id'])
           if revision['status'] in {'queued','generating','validating','preview_ready','probing','qc','interrupted'}):
        raise ValueError('局部修订未完成，不能确认或冻结人工审定导入')
    validate_content({**raw, **item}, CorpusStore().chunks() if chunks is None else chunks)
    with store.connection() as connection:
        identity = store._quality_identity(item, connection)
    event = next((e for e in store.review_history(item['id']) if e.get('gate') == 'dataset'), {})
    approved = (item['stage'] == 'golden' and item['review_status'] == 'approved'
                and event.get('decision') == 'dataset_confirmed' and event.get('qualification_source') == 'human_reviewed_csv'
                and event.get('quality_identity') == identity and bool(event.get('reason', '').strip())
                and bool(event.get('actor', '').strip()))
    if require_approval and not approved:
        raise ValueError('人工审定导入仍需完整题卷的显式人工确认')
    return {'identity': identity, 'approved': approved}
