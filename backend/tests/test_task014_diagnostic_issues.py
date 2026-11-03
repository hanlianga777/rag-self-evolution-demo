"""Saved-fact diagnosis only: no store, runtime or Provider."""
import unittest
from test_automatic_diagnostics import recall_case
from app.diagnostics import diagnostic_view


def complete_case():
    case, chunks = recall_case()
    trace = case['programmatic_metrics']['retrieval_trace']
    trace['candidates'].append({'chunk_id': 'missing', 'content': chunks[1]['chunk_text']})
    trace['final'] = [{'chunk_id': 'parent', 'content': '检查外壳，检查传感器是否脏污。'}]
    case.update(model_answer='检查外壳，检查传感器是否脏污，并加入500毫升机油。', failure_tags=['Business Failure'])
    case['judge_result'] = {'verdict': 'FAIL', 'checks': [], 'issues': []}
    return case


class SavedIssueDiagnosisTests(unittest.TestCase):
    def test_saved_material_fact_issues_are_not_omissions(self):
        for kind in ('unsupported', 'contradiction', 'scope'):
            with self.subTest(kind=kind):
                case = complete_case()
                case['judge_result']['issues'] = [{'failure_kind': kind, 'answer_quotes': ['加入500毫升机油']}]
                view = diagnostic_view(case)
                self.assertEqual(view['subfeature'], '答案出现幻觉')
                self.assertEqual(view['phenomena'][0]['name'], '答案出现幻觉')

    def test_safety_requires_confirmed_safety_evidence(self):
        for confirmed, expected in ((False, '召回成功但答案漏要点'), (True, '安全提示丢失')):
            case = complete_case()
            case['judge_result']['issues'] = [{'failure_kind': 'unsafe_operation', 'safety_violation': confirmed}]
            self.assertEqual(diagnostic_view(case)['subfeature'], expected)

    def test_critical_omission_alone_is_not_safety_evidence(self):
        case = complete_case()
        case['judge_result']['issues'] = [{'failure_kind': 'omission', 'critical': True}]
        self.assertEqual(diagnostic_view(case)['subfeature'], '召回成功但答案漏要点')
        case['judge_result']['issues'][0]['safety_violation'] = True
        self.assertEqual(diagnostic_view(case)['subfeature'], '安全提示丢失')

    def test_saved_latency_is_secondary_and_keeps_pass(self):
        case = complete_case()
        case.update(passed=True, failure_tags=[])
        case['judge_result']['verdict'] = 'PASS'
        case['programmatic_metrics'].update(latency_ms=60001, ttft_ms=59000)
        view = diagnostic_view(case)
        self.assertEqual(view['diagnosis_category'], '通过')
        self.assertTrue(case['passed'])
        self.assertEqual([p['name'] for p in view['phenomena']], ['Latency 过高'])
        case['programmatic_metrics']['latency_ms'] = 60000
        self.assertEqual(diagnostic_view(case)['phenomena'], [])
