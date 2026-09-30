"""Explicit synthetic raw page for legacy workflow fixtures; never loads the real corpus."""
from app.full_text import checksum, search_full_text


class FullTextFixture:
    def full_text_probe(self, question):
        text = '固定解析页：必须先确认状态。'
        return search_full_text(question, {
            'corpus_fingerprint': {'fixture': 'fixture'},
            'coverage': {'status': 'complete', 'total_pages': 1, 'parsed_pages': 1},
            'pages': [{'document_id': 'fixture', 'page': 1, 'text': text, 'parser': 'fixture', 'text_checksum': checksum(text.encode())}],
        })
