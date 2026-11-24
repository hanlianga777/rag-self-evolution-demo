"""检索可修空间扫描：纯逻辑（假检索器），以及 retrieve_context 与 answer 共用同一条检索路径。不调模型。"""
import importlib.util
from pathlib import Path
from unittest.mock import Mock

from app.corpus import manifest_identity
from app.ai_service import AiService
from app.policy import ALLOWED_SEARCH_SPACE, DEFAULT_PIPELINE_CONFIG, FRIEND_BASELINE_CONFIG

spec = importlib.util.spec_from_file_location('retrieval_headroom', Path(__file__).resolve().parents[1] / 'scripts/retrieval_headroom.py')
rh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rh)

CSV = ('﻿题号,题型,出题方式,问题,证据\r\n'
       'Q01,positive,单段标准,时区怎么改,"c1｜一般设置"\r\n'
       'Q21,ablation,口语变体,钟点对不上咋整,"c1｜一般设置"\r\n'
       'Q29,ablation,跨段变体,放三个月电池咋弄,"c2｜室内存放\nc3｜充满电再存"\r\n'
       'Q31,negative,负向,洗地机能飞吗,\r\n').encode('utf-8')


def fake_retrieve(question, config):
    """Baseline(top_k=4) 只拿到 Q01 的证据；candidate_k=24 补回 Q21；multi_query 补回 Q29 但弄丢 Q01。"""
    got = []
    if '时区' in question and not config.get('multi_query'):
        got.append('c1')
    if '钟点' in question and config['candidate_k'] == 24:
        got.append('c1')
    if '三个月' in question and config.get('multi_query'):
        got += ['c2', 'c3']
    return [{'chunk_id': c} for c in got]


def test_reads_only_positive_and_ablation_with_multiline_evidence():
    items = rh.golden_questions(CSV)
    assert [i['qid'] for i in items] == ['Q01', 'Q21', 'Q29']
    assert items[2]['golden'] == ['c2', 'c3']


def test_single_variants_change_exactly_one_retrieval_param_and_skip_baseline_value():
    variants = rh.single_variants(DEFAULT_PIPELINE_CONFIG, ALLOWED_SEARCH_SPACE)
    assert all(len(v) == 1 for v in variants)
    assert {'candidate_k': 24} in variants and {'candidate_k': 12} not in variants
    assert not any('generation_thinking' in v for v in variants)


def test_frozen_preview_has_index_identity_and_legal_combinations(tmp_path):
    from types import SimpleNamespace
    from app.optimization import load_retrieval_preview

    identity = {'pipeline_version_id': 'KP-test', 'chunk_artifact_id': 'CHUNK-test',
                'sources': {'DOC-test': 'test-hash'}}
    manifest = {'knowledge_identity': identity, 'sources': identity['sources']}
    store = SimpleNamespace(database_path=tmp_path / 'demo.db')
    items = rh.golden_questions(CSV)
    baseline = FRIEND_BASELINE_CONFIG
    variants = rh.retrieval_variants(baseline)
    assert {'candidate_k': 24, 'min_score': 0.1} in variants
    assert {'query_decompose': True, 'multi_query': 6} in variants
    assert {'hybrid_search': False} in variants
    assert not any(v.get('hybrid_search') is False and 'hybrid_alpha' in v for v in variants)
    results = rh.scan(items, baseline, variants, fake_retrieve)
    rh.save_preview(store.database_path, 'EVAL-1', items, results, identity)
    loaded = load_retrieval_preview(store, 'EVAL-1', foundation=manifest_identity(manifest))
    assert loaded['knowledge_identity'] == identity
    assert len(loaded['configs']) == len(variants)
    assert load_retrieval_preview(store, 'EVAL-1', foundation={**identity, 'chunk_artifact_id': 'other'}) is None


def test_summary_counts_gap_fixed_and_lost():
    items = rh.golden_questions(CSV)
    results = rh.scan(items, dict(DEFAULT_PIPELINE_CONFIG), [{'candidate_k': 24}, {'multi_query': 4}], fake_retrieve)
    s = rh.summarize(results, min_fixable=2, min_single=1, max_lost=1)
    assert s['baseline_gap'] == ['Q21', 'Q29']
    assert s['fixable'] == ['Q21', 'Q29']
    by = {r['config']: r for r in s['best_configs']}
    assert by['candidate_k=24']['fixed'] == ['Q21'] and by['candidate_k=24']['lost'] == []
    assert by['multi_query=4']['lost'] == ['Q01']
    assert s['verdict'] == 'GO'
    assert rh.summarize(results)['verdict'] == 'NO-GO'   # 默认门槛：可修空间要 ≥5 道


def test_retrieve_context_is_the_same_path_answer_uses_and_never_generates():
    retriever = Mock()
    retriever.retrieve.return_value = [{'chunk_id': 'C1', 'content': '证据', 'document': 'm.pdf', 'page_start': 1, 'page_end': 1, 'score': .9}]
    provider = Mock()
    provider.settings.configured = True
    service = AiService(Mock(), Mock(), provider, False)
    service.retriever = retriever
    evidence, budget, stages, trace, usage = service.retrieve_context('如何操作', {'candidate_k': 24})
    assert [e['chunk_id'] for e in evidence] == ['C1']
    assert retriever.retrieve.call_args.args[1]['candidate_k'] == 24
    provider.complete_with_metrics.assert_not_called()
