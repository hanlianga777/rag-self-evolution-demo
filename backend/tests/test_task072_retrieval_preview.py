"""072：扫描按原文补判证据进入；预演表交给 Agent（只在有对应 Baseline 的预演文件时）。"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from retrieval_headroom import build_preview, hit_of  # noqa: E402
from app.optimization import load_retrieval_preview  # noqa: E402


def test_hit_by_quote_inside_parent():
    ev = [{'chunk_id': 'P1', 'matched_child_ids': ['C9'], 'content': '额定负载 5 kg\n工作范围 0.9 m'}]
    assert hit_of(ev, ['C8'], {'C8': ['工作范围 0.9 m']})['all_hit'] is True
    assert hit_of(ev, ['C8'], {'C8': ['工作范围 0.7 m']})['all_hit'] is False
    assert hit_of(ev, ['C9'])['rank'] == 1


def test_preview_lists_enters_and_lost():
    items = [{'qid': 'Q01', 'group': 'positive', 'method': '跨段综合'}, {'qid': 'Q02', 'group': 'ablation', 'method': '口语变体'}]
    h = lambda ok: {'all_hit': ok, 'rank': 1 if ok else None}
    results = {'baseline': {'change': {}, 'hits': {'Q01': h(False), 'Q02': h(True)}},
               'top_k=6': {'change': {'top_k': 6}, 'hits': {'Q01': h(True), 'Q02': h(False)}}}
    p = build_preview('EVAL-1', items, results)
    assert p['configs'][0]['evidence_enters_final'] == ['Q01'] and p['configs'][0]['evidence_lost_from_final'] == ['Q02']


def test_agent_loads_only_matching_preview(tmp_path):
    store = SimpleNamespace(database_path=tmp_path / 'demo.db')
    (tmp_path / 'retrieval_preview').mkdir()
    (tmp_path / 'retrieval_preview' / 'EVAL-1.json').write_text(json.dumps({'baseline_run_id': 'EVAL-1', 'configs': []}), encoding='utf-8')
    assert load_retrieval_preview(store, 'EVAL-1')['baseline_run_id'] == 'EVAL-1'
    assert load_retrieval_preview(store, 'EVAL-2') is None
