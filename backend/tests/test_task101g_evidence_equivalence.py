"""Offline checks for candidate deduplication and scope-sensitive evidence."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from app.diagnostics import automatic_analysis
from app.evaluation import EvaluationRunner
from app.retrieval import VectorRetriever, evidence_coverage


IDENTITY = {'pipeline_version_id': 'test-101g', 'sources': {}}


def child(chunk_id, text='检查护套', section='5.5.1', **fields):
    return {'chunk_id': chunk_id, 'document_id': 'manual-part-1', 'document_number': 'M1',
            'product': 'IRB 1300', 'version': 'W', 'section_path': section,
            'parent_chunk_id': 'parent-' + chunk_id, 'page_start': 1, 'page_end': 1,
            'chunk_text': text, **fields}


@pytest.fixture
def corpus():
    return [
        child('a-wrong-section', section='5.3.1'),
        child('b-golden', section='5 维修 / 5.5 下臂 / 5.5.1 更换下臂'),
        child('c-best', '检查　护套', section='5.5.1.2 工序', document_id='manual-part-2'),
        child('d-wrong-version', version='V'),
        child('e-other-product', product='IRB 1200'),
        child('f-other-document', document_number='M2'),
        child('g-other-safety', '断电后才能检查护套'),
        child('h-other-safety', '带电时禁止检查护套'),
        child('i-other-text', '额外相关资料'),
    ]


def test_normalized_groups_and_scope_are_distinct(corpus):
    from app.evidence_equivalence import build_equivalence
    table = build_equivalence(IDENTITY, [], corpus)
    assert table['knowledge_identity'] == IDENTITY
    assert len(table['groups']) == 1
    assert list(table['groups'].values())[0].keys() == {
        'a-wrong-section', 'b-golden', 'c-best', 'd-wrong-version'}
    trace = {'corpus_fingerprint': IDENTITY, 'evidence_equivalence': table, 'candidates': [
        {'chunk_id': i} for i in ('a-wrong-section', 'c-best', 'd-wrong-version', 'e-other-product')
    ], 'final': [{'chunk_id': 'parent-representative', 'matched_child_ids': ['a-wrong-section']}]}
    coverage = evidence_coverage(trace, ['b-golden'])
    assert coverage['candidate_recall']['matched_chunk_ids'] == ['b-golden']
    assert coverage['candidate_recall']['other_source_ids'] == ['a-wrong-section', 'd-wrong-version']
    assert coverage['final_context']['all_hit'] is False
    assert coverage['final_context']['other_source_ids'] == ['a-wrong-section']
    assert evidence_coverage({**trace, 'corpus_fingerprint': {}}, ['b-golden'])['candidate_recall']['any_hit'] is False


def test_shallow_numbering_and_unknown_revision():
    from app.evidence_equivalence import build_equivalence
    chunks = [child('gold', section='9 参考 / 9.6 油位'), child('copy', section='9.6 油位 / 步骤'),
              child('deeper', section='9.6.1 子节'), child('unknown', section='9.6 油位', version=None)]
    trace = {'corpus_fingerprint': IDENTITY, 'evidence_equivalence': build_equivalence(IDENTITY, [], chunks)}
    for key, hit in [('copy', True), ('deeper', False), ('unknown', False)]:
        assert evidence_coverage({**trace, 'final': [{'chunk_id': key}]}, ['gold'])['final_context']['all_hit'] is hit


def test_split_manual_revision_and_persisted_table(tmp_path):
    from app.evidence_equivalence import ARTIFACT, build_equivalence, bundle_equivalence, write_equivalence

    docs = [{'id': f'part-{i}', 'name': f'ABB_IRB1300_产品手册_3HAC070390-010_第{i}部分_中文版.pdf'}
            for i in (1, 2)]
    chunks = [child('preface', '文档编号: 3HAC070390-010\n修订: W', '前言', document_id='part-1')]
    chunks += [child(f'source-{i}', document_id=f'part-{i}', product=None, version=None, document_number=None)
               for i in (1, 2)]
    table = build_equivalence(IDENTITY, docs, chunks)
    write_equivalence(tmp_path, table)
    bundle = {'path': tmp_path, 'manifest': {'knowledge_identity': IDENTITY}, 'documents': docs, 'chunks': chunks}
    assert (tmp_path / ARTIFACT).is_file() and bundle_equivalence(bundle) == table
    trace = {'corpus_fingerprint': IDENTITY, 'evidence_equivalence': table, 'final': [{'chunk_id': 'source-2'}]}
    assert evidence_coverage(trace, ['source-1'])['final_context']['all_hit'] is True
    bundle['manifest']['knowledge_identity'] = {'pipeline_version_id': 'different'}
    with pytest.raises(ValueError, match='different Knowledge'):
        bundle_equivalence(bundle)


def test_dedup_before_rerank_and_trace_tracks_observed_copies(corpus, tmp_path, monkeypatch):
    from app.knowledge_pipeline import AlibabaProvider
    (tmp_path / 'parents.json').write_text(json.dumps([
        {**c, 'chunk_id': c['parent_chunk_id']} for c in corpus]))
    retriever = VectorRetriever(SimpleNamespace(chunks=lambda: corpus))
    retriever._bundle = {'path': tmp_path, 'manifest': {'knowledge_identity': IDENTITY, 'sources': {}},
                         'chunks': corpus, 'documents': []}
    vector = [('c-best', .99), ('a-wrong-section', .97), ('b-golden', .95),
              ('d-wrong-version', .9), ('i-other-text', .8), ('f-other-document', .7)]
    calls = []
    monkeypatch.setattr(retriever, 'vector_candidates', lambda q, limit, **kwargs: (
        calls.append(('vector', limit)) or [{'chunk_id': key, 'score': score} for key, score in vector[:limit]]))
    monkeypatch.setattr(retriever, '_bm25', lambda q: dict(vector))
    monkeypatch.setattr(AlibabaProvider, 'rerank', lambda self, q, hits: (
        calls.append(('rerank', [h['chunk_id'] for h in hits])) or hits))
    trace = {}
    final = retriever.retrieve('问', {'candidate_k': 2, 'top_k': 1, 'run_target': 'baseline'}, trace=trace)
    assert calls == [('vector', 6), ('rerank', ['c-best', 'i-other-text'])]
    assert final[0]['matched_child_ids'] == ['c-best']
    assert trace['candidate_dedup']['raw_candidate_count'] == 6
    copies = trace['candidates'][0]['same_text_copies']
    assert [c['chunk_id'] for c in copies] == ['a-wrong-section', 'b-golden', 'd-wrong-version']
    assert copies[0]['section_path'] == '5.3.1' and copies[0]['fusion_score'] < trace['candidates'][0]['fusion_score']
    assert trace['candidate_dedup']['cutoff_chunk_ids'] == ['f-other-document']
    candidate_trace = {}
    retriever.retrieve('问', {'candidate_k': 2, 'top_k': 1, 'run_target': 'sandbox_candidate',
                              'candidate_dedup': False}, trace=candidate_trace)
    assert candidate_trace['candidates'] == trace['candidates']


def test_recall_judge_and_bad_case_share_scope(corpus):
    from app.evidence_equivalence import build_equivalence
    table = build_equivalence(IDENTITY, [], corpus)
    item = {'question': '问', 'reference_answer': '参考', 'test_category': 'positive',
            'evidence': [{'source_chunk_ids': ['b-golden'], 'evidence_key_points': ['检查护套']}], 'raw': {}}
    observed = []

    def judge(*args, context):
        observed.append(context['programmatic_evidence_observation'])
        return {**dict.fromkeys(('correctness', 'faithfulness', 'completeness'), 60),
                **dict.fromkeys(('correctness_reason', 'faithfulness_reason', 'completeness_reason'), '离线样例'),
                'over_refusal': False, 'hallucination': False}

    runner = EvaluationRunner(None, SimpleNamespace(judge=judge))
    for source, hit in [('a-wrong-section', False), ('c-best', True)]:
        final = [{'chunk_id': source, 'content': '检查护套'}]
        candidates = [{**final[0], 'same_text_copies': [{'chunk_id': 'b-golden'}]}]
        trace = {'status': 'completed', 'corpus_fingerprint': IDENTITY, 'evidence_equivalence': table,
                 'candidates': candidates, 'reranked': final, 'final': final}
        case = runner.score_execution(item, {'retrieval': final, 'retrieval_trace': trace, 'answer': '回答', 'latency_ms': 1})
        metrics = case['programmatic_metrics']
        assert metrics['retrieval_hit'] is hit
        assert observed[-1]['final_context']['all_hit'] is hit
        assert metrics['retrieval_diagnostics']['recall_at_k'] == float(hit)
        check = case['diagnosis']['findings'][0]
        assert check['final_hit'] is hit
        if not hit:
            assert check['merged_strict_source_ids'] == ['b-golden']
            assert check['final_other_source_ids'] == ['a-wrong-section']
            assert case['primary_root_cause'] == 'Retrieval'
        assert automatic_analysis(case)['evidence_checks'] == case['diagnosis']['findings']

    old = deepcopy(case)
    del old['programmatic_metrics']['retrieval_trace']['evidence_equivalence']
    before = deepcopy(old)
    assert automatic_analysis(old)['evidence_checks'][0]['final_hit'] is True
    assert old == before

    # A strict representative was retained but did not reach Final.
    filtered = deepcopy(case)
    filtered['programmatic_metrics']['retrieval_trace']['final'] = []
    view = automatic_analysis(filtered)
    assert view['primary_root_cause'] == 'Ranking'
    assert view['retrieval_failure_stage'] == 'ranking_context_selection'
    assert view['evidence_checks'][0]['candidate_hit'] is True
    assert view['evidence_checks'][0]['final_hit'] is False
