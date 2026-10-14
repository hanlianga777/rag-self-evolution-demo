import tempfile,unittest
from pathlib import Path
from fastapi.testclient import TestClient
from api_fixture import main
from app.governance import GovernanceStore

class HistoryPagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.previous=main.store;main.store=GovernanceStore(Path(self.tmp.name)/'test.db')
        self.addCleanup(setattr,main,'store',self.previous);self.client=TestClient(main.app)

    def test_paged_history_is_bounded_without_capping_cases_or_duplicate_raw_payload(self):
        with main.store.connection() as c:
            for n in range(53):
                c.execute("INSERT INTO evaluation_runs VALUES (?,'completed','real','real',NULL,'{}','{}','{}',?,NULL,?,?)",(f'R{n:03}','{"checkpoints":{"large":"private"},"bad_case_count":0}',f'{n:03}',f'{n:03}'))
        first=self.client.get('/api/evaluations?page=1&limit=50').json()
        second=self.client.get('/api/evaluations?page=2&limit=50').json()
        self.assertEqual(len(first),50);self.assertEqual(len(second),3)
        self.assertNotIn('result_json',first[0]);self.assertNotIn('checkpoints',first[0]['result'])
        self.assertEqual(self.client.get('/api/evaluations?limit=51').status_code,422)
        self.assertEqual(self.client.get('/api/evaluations?page=0').status_code,422)
