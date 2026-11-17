"""049 dry-run 19 题误报的回归测试：CSV 单元格内的多行证据必须原样保留。纯逻辑，不读库、不调模型。"""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('import_friend_golden', Path(__file__).resolve().parents[1] / 'scripts/import_friend_golden.py')
imp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imp)

CSV = ('﻿题号,题型,出题方式,问题,参考答案,证据\r\n'
       'Q01,positive,跨段综合,时区怎么改？,在一般设置里改。,"c1｜按下“一般设置”按钮\nc2｜在“设定时区”下设置"\r\n').encode('utf-8')


def test_multiline_evidence_cell_keeps_each_line():
    rows = imp.read_rows(CSV)
    assert len(rows) == 1
    candidate = imp.to_candidate(rows[0])
    assert [e['source_chunk_ids'] for e in candidate['evidence']] == [['c1'], ['c2']]
    assert candidate['evidence'][0]['evidence_key_points'] == ['按下“一般设置”按钮']
