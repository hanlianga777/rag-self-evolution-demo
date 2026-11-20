"""098：源 PDF 的少量空白页不应让全文覆盖永远 insufficient。"""
from app.full_text import effective_coverage


def _ft(texts, status='insufficient'):
    pages = [{'document_id': 'D', 'page': i + 1, 'text': t, 'parser': 'RapidOCR' if not t else 'PyMuPDF'} for i, t in enumerate(texts)]
    return {'coverage': {'total_pages': len(texts), 'parsed_pages': sum(bool(t) for t in texts), 'status': status}, 'pages': pages}


def test_few_blank_pages_count_as_complete_and_are_listed():
    cov = effective_coverage(_ft(['x'] * 300 + ['']))
    assert cov['effective_status'] == 'complete' and cov['status'] == 'insufficient'
    assert cov['blank_pages'] == [{'document_id': 'D', 'page': 301, 'parser': 'RapidOCR'}]


def test_many_blank_or_missing_pages_stay_insufficient():
    assert effective_coverage(_ft(['x'] * 90 + [''] * 10))['effective_status'] == 'insufficient'
    ft = _ft(['x'] * 100); ft['pages'] = ft['pages'][:-1]
    assert effective_coverage(ft)['effective_status'] == 'insufficient'
