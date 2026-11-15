"""Legacy UI needs missing evidence as an array; saved audit values stay intact."""
import json
import unittest
from copy import deepcopy
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.read_view import evaluation_display


class LegacyReadTests(unittest.TestCase):
    def test_missing_positions_render_as_unknown_without_changing_saved_facts(self):
        source = {'result': {'d_facts': {'remaining_failures': [
            {'question_id': 'Q38', 'evidence_positions': '记录缺失'},
            {'question_id': 'Q29', 'evidence_positions': [{'reranked': 7, 'final': '未进入'}]},
        ]}}, 'result_json': json.dumps({'evidence_positions': '记录缺失'})}
        before = deepcopy(source)
        app = FastAPI()

        @app.get('/api/optimization')
        @evaluation_display
        def read():
            return source

        with TestClient(app) as client:
            payload = client.get('/api/optimization').json()
        rows = payload['result']['d_facts']['remaining_failures']
        self.assertEqual(rows[0]['evidence_positions'], [])
        self.assertEqual(rows[0]['evidence_positions_note'], '记录缺失')
        self.assertEqual(rows[1], source['result']['d_facts']['remaining_failures'][1])
        self.assertEqual(json.loads(payload['result_json']), {'evidence_positions': '记录缺失'})
        self.assertEqual(source, before)


if __name__ == '__main__':
    unittest.main()
