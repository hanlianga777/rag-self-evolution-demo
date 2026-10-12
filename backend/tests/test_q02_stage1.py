"""Synthetic data tests guards only; never Provider acceptance."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from build_q02_stage1 import PaidClient, verify_patch


class Stage1Guards(unittest.TestCase):
    def test_exactly_one_child_and_stable_order(self):
        old = [{'chunk_id': f'C-{i}', 'chunk_text': 'unchanged'} for i in range(368)]
        old[133]['chunk_id'] = 'DOC-001-C-00134'
        new = copy.deepcopy(old)
        new[133]['chunk_text'] = 'corrected'
        vectors = np.ones((368, 1024), dtype='float32')
        self.assertEqual(verify_patch(old, new, vectors), 133)
        new[134]['chunk_text'] = 'unauthorized'
        with self.assertRaises(ValueError): verify_patch(old, new, vectors)
        new = copy.deepcopy(old); new.reverse()
        with self.assertRaises(ValueError): verify_patch(old, new, vectors)

    def test_request_scope_and_consumed_attempt_cannot_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            client = PaidClient({}, Path(folder), ['child', 'query'], authorized=False)
            with self.assertRaises(ValueError): client.embed(['child', 'query'], 1024)
            self.assertEqual(client.calls, [])
            client.authorized = True
            with self.assertRaises(ValueError): client.embed(['extra'], 1024)
            self.assertEqual(client.calls, [])
            with patch('app.knowledge_pipeline.AlibabaProvider._post', side_effect=RuntimeError('offline failure')) as send:
                with self.assertRaises(RuntimeError): client.embed(['child', 'query'], 1024)
                with self.assertRaises(ValueError): client.embed(['child', 'query'], 1024)
                self.assertEqual(send.call_count, 1)

    def test_missing_usage_or_over_budget_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            client = PaidClient({}, Path(folder), ['child', 'query'], authorized=True)
            with patch('app.knowledge_pipeline.AlibabaProvider._post', return_value={'usage': {'total_tokens': 20001}}):
                with self.assertRaises(ValueError): client.embed(['child', 'query'], 1024)
            self.assertGreater(client.cost, .01)
            with self.assertRaises(ValueError): client._post('/compatible-api/v1/reranks', {'model': 'qwen3-rerank'})
            self.assertEqual(len(client.calls), 1)


if __name__ == '__main__': unittest.main()
