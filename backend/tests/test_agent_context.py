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
        self.assertNotIn('retrieval_trace',row)
        self.assertEqual(row['diagnosis_category'],'检索层问题')
        self.assertTrue(row['reason'])
        with self.store.connection() as connection:
            audit=json.loads(connection.execute('SELECT result_json FROM agent_traces ORDER BY id DESC LIMIT 1').fetchone()[0])
        projected=audit['all_bad_case_audit'][0]['result']
        expected={**before['result'],'baseline_review_label':'单遍判错','optimization_target':True}
        self.assertEqual({k:v for k,v in projected.items() if k!='standard_evidence'}, {k:v for k,v in expected.items() if k!='standard_evidence'})
        self.assertEqual(self.store.bad_case_rows()[0],before)
        self.assertEqual(row['question_id'],'Q1')
