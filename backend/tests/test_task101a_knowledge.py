"""Task 101a regressions with offline parser blocks and disposable storage."""
import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest

from app import corpus
from app.diagnostics import _current_corpus
from app.evaluation import EvaluationRunner
from app.golden_v2 import build_plan
from app.governance import GENERATION_PROFILES, GovernanceStore
from app.knowledge_pipeline import _v2_block_text, parent_child_v2


def block(text, page=0, heading=False, kind='text'):
    return {'text': text, 'type': kind, 'page_idx': page, **({'text_level': 2} if heading else {})}


def table(rows, page=0):
    return {'type': 'table', 'page_idx': page, 'table_body':
            '<table>' + ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in rows) + '</table>'}


def test_numbering_checks_hierarchy_and_table_context_even_with_incomplete_toc():
    blocks = [
        block('目录\n1 描述 2\n1.9 机器人动作 2\n1.9.3 速度 3'),
        block('1 描述', 1, True), block('1.9 机器人动作', 1, True),
        block('1.9.3 速度', 2, True), block('3 相电源', 2, True),
        table([['轴号', '速度'], ['1', '2°/秒']], 2),
        block('1 相电源', 2, True), block('最大轴速如下。', 2),
        table([['轴号', '速度'], ['1', '1°/秒']], 2),
        block('1.9.4 机器人停止距离和时间', 3, True), block('核对停止距离。', 3),
        block('7.4.1 无上级标题', 4, True), block('保留这行。', 4),
    ]
    parents, children, _ = parent_child_v2({'id': 'D', 'name': '规格.pdf'}, blocks, len)
    assert [p['numbered_section'] for p in parents] == ['1.9.3', '1.9.4']
    assert all('相电源' not in c['section_path'] for c in children)
    assert children[-1]['section_path'] == '1 描述 / 1.9 机器人动作 / 1.9.4 机器人停止距离和时间'
    assert '3 相电源' in parents[0]['chunk_text']
    assert '7.4.1 无上级标题' in parents[-1]['chunk_text']


def test_image_tokens_and_footer_remove_only_matching_noise():
    labels = table([['标志', '描述'], ['xx123456789', '电击危险'], ['xx12345678901', '设备说明'],
                    ['654321xx09000008201 2 3 ○ ○ 6xx1000001140', '制动闸释放按钮']])
    assert _v2_block_text(labels) == '标志=；描述=电击危险\n标志=；描述=设备说明\n标志=6543211 2 3 ○ ○ 6；描述=制动闸释放按钮'
    assert _v2_block_text(block('xx12345678\n1、核对说明。 xx1234567890123\n正文用型号 xx123456789 查找')) == (
        '1、核对说明。 \n正文用型号 xx123456789 查找')
    assert _v2_block_text(block('产品手册 - IRB 13003HAC070390-010 修订: W\n此页刻意留白\n正文参见文档 3HAC070390-010。')) == (
        '正文参见文档 3HAC070390-010。')


def test_step_table_keeps_column_names_after_denoise_and_child_splits():
    action = '取下护盖。' * 28
    note = '保留螺钉。' * 12
    blocks = [block('1 操作', heading=True)]
    for page in range(3):
        step_table = {
            'type': 'table', 'page_idx': page,
            'table_body': f'<table><tr><td colspan="3">注意保护第{page}处设备。</td></tr>'
                          '<tr><td></td><td>操作</td><td>注释</td></tr>'
                          + ''.join(f'<tr><td>{n}</td><td>{action}</td><td>{note}</td></tr>' for n in (1, 2))
                          + '<tr><td>3</td><td>完成后检查。</td></tr></table>',
        }
        blocks.extend([block('重复页眉', page, kind='header'), step_table])

    parents, children, parsed = parent_child_v2({'id': 'D', 'name': '手册.pdf'}, blocks, len)

    for step in (1, 2):
        row = f'{step} | 操作={action}；注释={note}'
        assert sum(row in child['chunk_text'] for child in children) == 3
    assert sum(child['chunk_text'].count('注意保护第') for child in children) == 3
    assert sum(child['chunk_text'].count('| 操作 | 注释：3 | 完成后检查。') for child in children) == 3
    assert all('重复页眉' not in parent['chunk_text'] for parent in parents)
    assert all('repeated_short_line' != p.get('drop_reason') for p in parsed if p['raw']['type'] == 'table')


def test_confirmed_title_moves_with_body_and_mapping_while_warning_is_body():
    title = '维护步骤'
    blocks = [block('1 操作', heading=True), block('甲' * 231 + '。'), block(title, 1, True),
              block('注意', 1, True), block('乙' * 142 + '。', 1), block('丙' * 100 + '。', 1)]
    parents, children, parsed = parent_child_v2({'id': 'D', 'name': '手册.pdf'}, blocks, len)
    assert len(parents) == 1 and len(children) == 2
    assert title not in children[0]['chunk_text']
    assert children[1]['chunk_text'].startswith(title + '\n注意\n')
    assert children[1]['page_start'] == 2
    assert children[1]['block_ids'][0] == parsed[2]['block_id']
    assert children[1]['section_path'] == '1 操作 / 维护步骤'
    for c in children:
        assert 80 <= c['token_count'] <= 300
        assert parents[0]['chunk_text'][c['char_start']:c['char_end']] == c['chunk_text']


def test_cut_rolls_back_if_adjacent_table_child_would_stay_too_short():
    blocks = [block('1 操作', heading=True), block('甲' * 180 + '。'),
              block('地面安装'), table([['部件', '尺寸'], ['底座', '20 mm，' + '核对尺寸' * 7]]),
              block('乙' * 210 + '。')]
    _, children, _ = parent_child_v2({'id': 'D', 'name': '手册.pdf'}, blocks, len)
    assert children[0]['chunk_text'].strip().endswith('地面安装')
    assert '部件=底座；尺寸=20 mm' in children[1]['chunk_text']


def test_volume_continuation_and_preface_sampling():
    document = {'id': 'D', 'name': '手册.pdf'}
    blocks = [block('出版说明'), block('5.5.1 更换下臂', 1, True), block('核对下臂零件。', 1),
              block('6 标定', 2, True), block('核对型号。', 2)]
    previous = {'5': '5 维修', '5.5': '5.5 上臂和下臂'}
    _, children, _ = parent_child_v2(document, blocks, len, previous_sections=previous)
    assert [c['section_path'] for c in children] == ['前言', '5 维修 / 5.5 上臂和下臂 / 5.5.1 更换下臂', '6 标定']
    plan = build_plan(children, np.ones((3, 2)), {'name': 'mini', **GENERATION_PROFILES['mini']})
    assert set(plan['chunk_clusters']) == {c['chunk_id'] for c in children[1:]}


def test_numbered_parent_paths_follow_table_titles_and_continue_across_parents():
    prefix = '5 维修 / 5.5 上臂和下臂'
    procedure = table([['', '操作', '注释'], ['1', '甲' * 137, '保留列名。']])
    procedure['table_caption'] = ['装回盖板']
    blocks = [block('5 维修', heading=True), block('5.5 上臂和下臂', heading=True),
              block('准备工作', heading=True), block('准备工具。' * 25), procedure,
              *[block('乙' * 232 + '。', i) for i in range(1, 9)],
              block('结束步骤', 9, True), block('丙' * 200 + '。', 9),
              block('6 标定', 10, True), block('丁' * 200 + '。', 10)]
    parents, children, _ = parent_child_v2({'id': 'D', 'name': '手册.pdf'}, blocks, len)

    table_child = next(c for c in children if c['chunk_text'].lstrip().startswith('装回盖板\n'))
    assert table_child['section_path'] == prefix + ' / 装回盖板'
    assert '1 | 操作=' + '甲' * 137 + '；注释=保留列名。' in table_child['chunk_text']
    assert parents[0]['parent_section_path'] == prefix
    assert parents[0]['parent_subheadings'] == ['准备工作', '装回盖板']
    continued = next(c for c in children if c['parent_chunk_id'] == parents[1]['chunk_id'])
    assert continued['section_path'] == prefix + ' / 装回盖板'
    assert continued['section_heading']['block_id'] == 'D-BLOCK-00005'
    assert parents[1]['parent_subheadings'] == ['装回盖板', '结束步骤']
    assert children[-1]['section_path'] == '6 标定'


def test_same_chunk_id_isolated_across_golden_history_agent_sandbox_and_resume(tmp_path, monkeypatch):
    index = tmp_path / 'index'
    archive = tmp_path / 'index_versions' / 'old'
    index.mkdir()
    archive.mkdir(parents=True)
    identity = lambda tag: {'pipeline_version_id': tag, 'corpus_snapshot_id': tag, 'sources': {'D': 'fingerprint'}}
    old, new = identity('old'), identity('new')
    for path, version, body in ((archive, old, '旧正文'), (index, new, '新正文')):
        artifacts = {}
        for name, rows in (
            ('chunks.json', [{'chunk_id': 'same', 'parent_chunk_id': 'P', 'chunk_text': body}]),
            ('parents.json', [{'chunk_id': 'P', 'chunk_text': body + '父块'}]),
        ):
            content = json.dumps(rows).encode()
            (path / name).write_bytes(content)
            artifacts[name] = hashlib.sha256(content).hexdigest()
        (path / 'manifest.json').write_text(json.dumps({'knowledge_identity': version, 'sources': version['sources'], 'artifacts': artifacts}))
    monkeypatch.setattr(corpus, 'INDEX_DIR', index)
    monkeypatch.setattr(corpus, 'discover_documents', lambda: [{'id': 'D'}])
    monkeypatch.setattr(corpus, 'source_fingerprint', lambda _: 'fingerprint')
    store = GovernanceStore(tmp_path / 'versions.db')
    runtime = SimpleNamespace(model='fixture', corpus=corpus.CorpusStore(index))
    runner = EvaluationRunner(store, runtime)
    items = [{'id': f'Q{i}', 'question': f'Q{i}', 'reference_answer': '旧正文', 'evidence': [],
              'test_category': category, 'negative_subtype': subtype} for i, (category, subtype) in enumerate(
              [('positive', None), ('ablation', None), ('negative', 'safety_critical'), ('negative', 'prompt_injection')])]
    snapshot = {'id': 'GD-old', 'corpus_fingerprint': old, 'questions': items, 'question_ids': [q['id'] for q in items]}
    config = {'run_target': 'baseline', 'knowledge_identity': old}
    trace = {'corpus_fingerprint': old, 'final': [{'chunk_id': 'same', 'content': '旧正文'}]}
    with store.connection() as db:
        db.execute("INSERT INTO dataset_versions VALUES (?, 'approved', 'fixture', ?, '9999')", (snapshot['id'], json.dumps(snapshot)))
        db.execute("INSERT INTO evaluation_runs VALUES ('old-run','partial','real','real',?,?,?,'{}','{}',NULL,'2026-11-20',NULL)", (snapshot['id'], json.dumps(snapshot), json.dumps(config)))
        db.execute("INSERT INTO experiments (id,baseline_run_id,status,result_json,created_at) VALUES ('old-exp','old-run','completed','{}','2026-11-20')")
    store.record_evaluation_case('old-run', items[0]['id'], {'programmatic_metrics': {'retrieval_trace': trace}})
    saved = store.evaluation_case_result(store.experiment('old-exp')['baseline_run_id'], items[0]['id'])
    assert saved['programmatic_metrics']['retrieval_trace']['final'][0]['content'] == '旧正文'
    chunks, fingerprint = _current_corpus(saved['programmatic_metrics']['retrieval_trace'], historical=True)
    assert fingerprint == old and chunks[0]['chunk_text'] == '旧正文'
    assert chunks[0]['canonical_parent']['chunk_text'] == '旧正文父块'
    assert _current_corpus({'corpus_fingerprint': new})[0][0]['chunk_text'] == '新正文'
    assert _current_corpus(trace) == ([], None)
    preflight = runner.baseline_preflight('old-run')
    assert preflight['can_start'] is preflight['can_resume'] is False
    assert 'active Knowledge Pipeline' in preflight['reason']
    with pytest.raises(ValueError, match='Corpus'):
        store.claim_agent_generation('old-run')
    with pytest.raises(ValueError, match='Corpus'):
        store.create_baseline_run(snapshot, {'run_target': 'sandbox_candidate', 'knowledge_identity': old}, {}, candidate_id='old-candidate')
    with store.connection() as db, pytest.raises(ValueError, match='Corpus'):
        store.validate_evaluation_resume(db, snapshot, config, {}, 'old-run')
    # Even with a new approved Golden, an explicitly mismatched runtime
    # configuration or an old checkpoint must not be used for the new run.
    new_snapshot = {**snapshot, 'id': 'GD-new', 'corpus_fingerprint': new}
    with store.connection() as db:
        db.execute("INSERT INTO dataset_versions VALUES (?, 'approved', 'fixture', ?, '9999')",
                   (new_snapshot['id'], json.dumps(new_snapshot)))
    judge = {'baseline_version': (store.active_production() or {}).get('id')}
    with pytest.raises(ValueError, match='知识库身份'):
        store.create_baseline_run(new_snapshot, config, judge)
    with store.connection() as db, pytest.raises(ValueError, match='知识库身份'):
        store.validate_evaluation_resume(db, new_snapshot, config, {}, 'old-run')
