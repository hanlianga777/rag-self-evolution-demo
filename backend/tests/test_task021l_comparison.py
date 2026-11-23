import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.governance import GovernanceStore
from app import independent_case_review
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

    def test_independent_notes_require_the_same_run_dataset_question_verdict_and_answer(self):
        with tempfile.TemporaryDirectory() as temp:
            report_dir = Path(temp)
            store = GovernanceStore(report_dir / 'test.db')
            question = {'id': 'frozen-question', 'display_id': 'Q05'}
            case = {'question_id': question['id'], 'passed': True, 'model_answer': '回答包括已保存原句。'}
            snapshot = {'id': 'GD-123', 'question_ids': [question['id']], 'questions': [question]}
            run = store.create_evaluation_run(snapshot, {}, {'evaluation_identity': 'judge'})
            store.record_evaluation_case(run, question['id'], case)
            store.finish_evaluation_run(run, 'completed', {})
            (report_dir / '106.md').write_text(
                f'题卷快照一致，版本为 `GD-123`。\n| C | `{run}` | 候选记录 |\n', encoding='utf-8')
            (report_dir / independent_case_review.AUDIT_TABLE).write_text(
                '运行,题号,正式对错,否定句原文,结论\nC,Q05,PASS,已保存原句,Claude 初审：核对页码指引\n',
                encoding='utf-8-sig')
            with patch.object(independent_case_review, 'REPORT_DIR', report_dir), patch.object(main, 'store', store):
                notes = independent_case_review.independent_case_notes
                original = store.evaluation_case_result(run, question['id'])
                with TestClient(main.app) as client:
                    response = client.get(f"/api/evaluations/{run}/cases/{question['id']}")
                self.assertEqual(response.status_code, 200)
                detail = response.json()
                self.assertEqual(detail['independent_review_notes'], ['Claude 初审：核对页码指引'])
                self.assertTrue(detail['case']['passed'])
                self.assertEqual(store.evaluation_case_result(run, question['id']), original)
                self.assertEqual(notes('EVAL-789', 'GD-123', question, case), [])
                self.assertEqual(notes(run, 'GD-789', question, case), [])
                self.assertEqual(notes(run, 'GD-123', {'display_id': 'Q15'}, case), [])
                self.assertEqual(notes(run, 'GD-123', question, {**case, 'passed': False}), [])
                self.assertEqual(notes(run, 'GD-123', question, {**case, 'model_answer': '另一份回答'}), [])
