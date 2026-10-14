"""Strategy evidence is separate from complete local evaluation audit."""
import json,unittest
import test_optimization_contract as fixture
from app.optimization import OptimizationAgent

class AgentContextTests(unittest.TestCase):
    setUp=fixture.OptimizationContractTests.setUp
    def test_strategy_projection_preserves_raw_audit_locally(self):
        before=self.store.bad_case_rows()[0]
        provider=fixture.FixedProvider(json.dumps(fixture.drafts()))
        OptimizationAgent(self.store,provider).generate('EVAL-test')
        row=provider.prompt['bad_cases'][0]
        self.assertNotIn('result_json',row)
        self.assertNotIn('all_bad_case_audit',provider.prompt)
        self.assertEqual(row['retrieval_trace'],before['result']['programmatic_metrics']['retrieval_trace'])
        self.assertEqual(row['result']['model_answer'],before['result']['model_answer'])
        self.assertEqual(row['result']['primary_root_cause'],'Retrieval')
        self.assertNotIn('diagnosis',row['result'])
        self.assertNotIn('governance',row['diagnostic_view'])
        with self.store.connection() as connection:
            audit=json.loads(connection.execute('SELECT result_json FROM agent_traces ORDER BY id DESC LIMIT 1').fetchone()[0])
        self.assertEqual(audit['all_bad_case_audit'][0]['result'],before['result'])
        self.assertEqual(self.store.bad_case_rows()[0],before)
        self.assertTrue(provider.prompt['target_reference_map']['Q1']['diagnostic_view']['target_eligible'])
