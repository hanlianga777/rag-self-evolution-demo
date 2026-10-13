"""Lossless Agent transport: SQLite JSON text must not duplicate parsed evidence."""
import json,unittest
import test_optimization_contract as fixture
from app.optimization import OptimizationAgent

class AgentContextTests(unittest.TestCase):
    setUp=fixture.OptimizationContractTests.setUp
    def test_only_duplicate_json_text_is_removed(self):
        before=self.store.bad_case_rows()[0]
        self.assertEqual(json.loads(before['result_json']),before['result'])
        provider=fixture.FixedProvider(json.dumps(fixture.drafts()))
        OptimizationAgent(self.store,provider).generate('EVAL-test')
        for group in ('bad_cases','all_bad_case_audit'):
            row=provider.prompt[group][0]
            self.assertNotIn('result_json',row)
            self.assertEqual(row['result'],before['result'])
            for key,value in before.items():
                if key!='result_json':self.assertEqual(row[key],value)
        self.assertEqual(self.store.bad_case_rows()[0],before)
        self.assertTrue(provider.prompt['target_reference_map']['Q1']['diagnostic_view']['target_eligible'])
