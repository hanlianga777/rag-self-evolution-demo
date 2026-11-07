import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.governance import GovernanceStore
from api_fixture import main

class ComparisonReadsTests(unittest.TestCase):
    def test_light_list_omits_answers_and_detail_reads_one_saved_case_without_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            store=GovernanceStore(Path(temp)/'test.db')
            snapshot={'id':'golden','question_ids':['Q04'],'questions':[{'id':'Q04','question':'如何存放？','test_category':'positive'}]}
            run=store.create_evaluation_run(snapshot,{}, {'evaluation_identity':'judge'})
            case={'question_id':'Q04','question':'如何存放？','test_category':'positive','passed':False,'model_answer':'原始回答','diagnostic_view':{'evidence_checks':[]},'judge_result':{'atomic_results':[]},'programmatic_metrics':{'retrieval_trace':{'final':[]}}}
            store.record_evaluation_case(run,'Q04',case)
            store.finish_evaluation_run(run,'completed',{})
            original=store.evaluation_case_result(run,'Q04')
            with patch.object(main,'store',store),patch.object(store,'evaluation_case_results',side_effect=AssertionError('no full paper')):
                rows=main.comparison_cases(run)
                self.assertEqual(rows['cases'],[{'question_id':'Q04','question':'如何存放？','test_category':'positive','passed':False}])
                detail=main.comparison_case(run,'Q04')
                self.assertEqual(detail['case']['model_answer'],'原始回答')
            self.assertEqual(store.evaluation_case_result(run,'Q04'),original)
