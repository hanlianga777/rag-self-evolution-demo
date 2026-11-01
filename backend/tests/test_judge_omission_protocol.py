"""Pure omission producer protocol; strict saved failures remain technical failures."""
import ast
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

_isolated = tempfile.TemporaryDirectory(prefix='omission-protocol-offline-')
with patch.dict(os.environ, {key: str(Path(_isolated.name)/key) for key in
        ('RAG_DEMO_DB_PATH','RAG_DEMO_ENV_PATH','RAG_DEMO_INDEX_DIR','RAG_DEMO_DOCUMENTS_DIR','RAG_DEMO_UPLOADS_DIR')}):
    from app.evaluation_contract import BUSINESS_JUDGE_PROMPT, VERSIONS, validate_business_judgment, quote_present
    from app.scoring_contract import atomic_failure_keys

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent/'fixtures/judge_omission_protocol_errors_20261101.json'


class OmissionProtocolTests(unittest.TestCase):
    def setUp(self):
        self.rows = json.loads(FIXTURE.read_text())['cases']
        for target in ('socket.create_connection','urllib.request.urlopen'):
            guard = patch(target, side_effect=AssertionError('offline only'))
            guard.start(); self.addCleanup(guard.stop)

    def validate(self, row, value):
        f = row['input']
        return validate_business_judgment(value, f['actual_answer'], f['final_context'],
            category=f['category'], constraints=f.get('source_constraints'), question=f['question'],
            reference=f['reference_answer'], candidates=f.get('retrieval_candidates'),
            scoring_contract=f['scoring_contract'])

    def represented_offline(self, row):
        value = json.loads(row['raw_provider_response'])
        # Explicit hypothetical producer output. Production never filters invalid issues.
        value['issues'] = [i for i in value['issues']
                           if not (i.get('failure_kind') == 'omission' and i.get('answer_quotes') == [])]
        for issue in value['issues']:
            if issue.get('failure_kind') == 'omission':
                issue['support'] = [q for q in issue['support'] if
                    quote_present(q, row['input']['final_context'], display=True) or
                    quote_present(q, row['input'].get('retrieval_candidates', []), display=True)]
        return value

    def test_current_prompt_explains_empty_omission_issue_boundary(self):
        for rule in ('纯遗漏且无可定位的实际答案引文', '仅在atomic_results/checks及reason中完整记录缺失',
                     '不生成无法合法引用的重复omission issue', 'issues允许为空数组，原子硬失败仍由程序判FAIL',
                     'Golden的reference_support不能满足空答案引文豁免'):
            self.assertIn(rule, BUSINESS_JUDGE_PROMPT)
        self.assertEqual(VERSIONS['prompt_version'], 'judge-vnext-6.4-omission-evidence-protocol')

    def test_both_real_invalid_responses_remain_rejected_and_unchanged(self):
        for row in self.rows:
            with self.subTest(case=row['id']):
                value = json.loads(row['raw_provider_response']); before = copy.deepcopy(value)
                with self.assertRaisesRegex(ValueError, row['expected_error']): self.validate(row, value)
                self.assertEqual(value, before)

    def test_explicit_offline_representation_preserves_every_hard_failure(self):
        for row in self.rows:
            with self.subTest(case=row['id']):
                original = json.loads(row['raw_provider_response']); value = self.represented_offline(row)
                self.assertLess(len(value['issues']), len(original['issues']))
                for key in original:
                    if key != 'issues': self.assertEqual(value[key], original[key])
                self.assertEqual([i for i in value['issues'] if i['failure_kind'] != 'omission'],
                                 [i for i in original['issues'] if i['failure_kind'] != 'omission'])
                expected = atomic_failure_keys(row['input']['scoring_contract'], original['atomic_results'])
                self.assertTrue(expected)
                judged = self.validate(row, value)
                self.assertEqual(judged['verdict'], 'FAIL')
                self.assertEqual(judged['atomic_failure_keys'], expected)

    def test_empty_issue_without_stage_evidence_still_rejected(self):
        for row in self.rows:
            value = self.represented_offline(row)
            value['issues'].append({'description':'missing required item','atomic_ids':[],
                'failure_kind':'omission','answer_quotes':[],'support':[],'critical':False})
            with self.assertRaisesRegex(ValueError, 'answer quote is missing'): self.validate(row, value)

    def test_fake_actual_answer_quote_still_rejected(self):
        for row in self.rows:
            value = self.represented_offline(row)
            value['issues'].append({'description':'actual unsafe assertion','atomic_ids':[],
                'failure_kind':'unsafe_operation','answer_quotes':['THIS_SENTENCE_IS_NOT_IN_THE_ANSWER'],
                'support':[],'critical':True,'safety_violation':True})
            with self.assertRaisesRegex(ValueError, 'answer quote is missing'): self.validate(row, value)

    def test_all_validator_and_adjudicator_function_bodies_unchanged(self):
        old = ROOT/'docs/judge_vnext_20261101/judge_6_3_source/evaluation_contract.py.txt'
        current = ROOT/'backend/app/evaluation_contract.py'
        functions = lambda p: {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(p.read_text()).body
                              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertEqual(functions(old), functions(current))


if __name__ == '__main__': unittest.main()
