"""069：父子切块下，标准子块没被检索命中、但原文在同一父块全文里交给了模型，要算进入并标明口径。"""
from app.agent_inputs import evidence_positions


def _question():
    return {'evidence': [{'source_chunk_ids': ['DOC-C16-C-00028'], 'evidence_key_points': ['产品型号 | DT-CR-6R160-00I', '本体重量 | 40 kg']}]}


def test_quote_inside_delivered_parent_counts_as_entered():
    parent_text = '产品名称 | DOBOT CR16\n产品型号 | DT-CR-6R160-00I\n本体重量 | 40 kg\n最大负载(kg) | 16 kg'
    trace = {'status': 'completed',
             'candidates': [{'chunk_id': 'P-9', 'matched_child_ids': ['DOC-C16-C-00027'], 'content': parent_text}],
             'reranked': [{'chunk_id': 'P-9', 'matched_child_ids': ['DOC-C16-C-00027'], 'content': parent_text}],
             'final': [{'chunk_id': 'P-3', 'matched_child_ids': ['X'], 'content': '别的资料'},
                       {'chunk_id': 'P-9', 'matched_child_ids': ['DOC-C16-C-00027'], 'content': parent_text}]}
    [pos] = evidence_positions(_question(), trace)
    assert pos['final'].startswith('2') and '按原文判定' in pos['final']
    assert pos['candidates'].startswith('1')


def test_id_match_still_wins_and_absent_quote_is_not_entered():
    trace = {'status': 'completed',
             'candidates': [{'chunk_id': 'DOC-C16-C-00028', 'content': '无关'}],
             'reranked': [{'chunk_id': 'Y', 'matched_child_ids': ['Y1'], 'content': '本体重量 | 40 kg'}],
             'final': [{'chunk_id': 'Z', 'matched_child_ids': ['Z1'], 'content': '产品型号 | DT-CR-6R030-00I'}]}
    [pos] = evidence_positions(_question(), trace)
    assert pos['candidates'] == 1
    assert pos['reranked'] == '未进入'   # 只有部分原文，不算
    assert pos['final'] == '未进入'
