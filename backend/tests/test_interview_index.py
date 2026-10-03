import json
import tempfile
import unittest
from pathlib import Path

import faiss
import numpy as np

from app.corpus import CorpusStore


class InterviewIndexTests(unittest.TestCase):
    def test_index_metadata_comes_from_active_file_without_changing_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / 'manifest.json').write_text(json.dumps({'sources': {}, 'embedding_model': 'fixture-model'}))
            index = faiss.IndexFlatIP(7)
            index.add(np.ones((3, 7), dtype='float32'))
            faiss.write_index(index, str(path / 'faiss.index'))
            before = {p.name: p.read_bytes() for p in path.iterdir()}
            result = CorpusStore(path).index_info()
            self.assertEqual(result['dimension'], 7)
            self.assertEqual(result['indexed_count'], 3)
            self.assertEqual(before, {p.name: p.read_bytes() for p in path.iterdir()})

    def test_missing_or_unreadable_index_is_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            for content in (None, b'invalid-index'):
                if content is not None:
                    (path / 'faiss.index').write_bytes(content)
                result = CorpusStore(path).index_info()
                self.assertIsNone(result['dimension'])
                self.assertIsNone(result['indexed_count'])
