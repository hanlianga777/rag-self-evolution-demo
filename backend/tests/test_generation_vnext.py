"""Offline request/identity checks; recordings are not Provider acceptance."""
import hashlib
import unittest
from types import SimpleNamespace

from app.ai_service import AiService, GENERATION_BOUNDARY
from app.evaluation import EvaluationRunner
from app.evaluation_contract import evaluation_identity


class RecordingProvider:
    settings = SimpleNamespace(configured=True, model='offline-recording')

    def __init__(self):
        self.requests = []

    def complete_with_metrics(self, system, user, **kwargs):
        self.requests.append((system, user))
        return {'content': '离线占位', 'ttft_ms': 0, 'input_tokens': 0, 'output_tokens': 0}


class GenerationVNextTests(unittest.TestCase):
    def service(self, **kwargs):
        provider = RecordingProvider()
        service = AiService(object(), object(), provider, False, **kwargs)
        service.retriever = SimpleNamespace(retrieve=lambda *args, **kw: [
            {'chunk_id': 'C1', 'content': '给定证据', 'product': '设备'}])
        return service, provider

    def test_opt_in_contract_is_shared_across_targets_and_question_types(self):
        service, provider = self.service(generation_prompt_version='generation-vnext-2')
        for question in ('额定电压是多少？', '怎么更换刷辊？', '请分别说明操作和存放要求', '不明清洁剂可以用吗？'):
            for target in ('baseline', 'sandbox_candidate'):
                result = service.answer(question, {'run_target': target})
                self.assertEqual(result['generation_prompt_version'], 'generation-vnext-2')
        self.assertEqual(len({request[0] for request in provider.requests}), 1)
        system = provider.requests[0][0]
        for requirement in ('事实问题', '编号', '分组', '安全条件', '不设置', '证据不足', '引用'):
            self.assertIn(requirement, system)
        for _, user in provider.requests:
            self.assertNotIn('reference_answer', user)
            self.assertNotIn('required_checks', user)
            self.assertNotIn('历史Judge', user)

    def test_default_remains_legacy_and_identity_changes_only_on_opt_in(self):
        old, provider = self.service()
        new, _ = self.service(generation_prompt_version='generation-vnext-2')
        old.answer('问题')
        self.assertEqual(provider.requests[0][0], '你是机器人官方 PDF 知识助手。只能基于给定证据回答；证据不足时明确说明。' + GENERATION_BOUNDARY + '回答使用中文，简洁、可执行。')
        self.assertEqual(old.generation_contract['generation_prompt_version'], 'generation-vnext-1')
        self.assertEqual(old.generation_contract['generation_boundary_sha256'], hashlib.sha256(GENERATION_BOUNDARY.encode()).hexdigest())
        self.assertNotEqual(evaluation_identity({'id': 'GD'}, old.generation_contract), evaluation_identity({'id': 'GD'}, new.generation_contract))

    def test_unknown_version_is_rejected_before_retrieval_or_provider(self):
        with self.assertRaises(ValueError):
            self.service(generation_prompt_version='typo')

    def test_replay_preserves_selected_generation_version(self):
        from test_judge_replay_v5 import JudgeReplayTests
        from app.ai_service import generation_contract
        from app.judge_replay import replay_eligibility
        args = list(JudgeReplayTests().example())
        args[0]['judge'].update(generation_contract('generation-vnext-2'))
        args[4].update(generation_contract('generation-vnext-2'))
        self.assertTrue(replay_eligibility(*args, 'fp')['can_replay'])
        args[4].update(generation_contract())
        result = replay_eligibility(*args, 'fp')
        self.assertFalse(result['can_replay'])
        self.assertIn('generation_contract_changed', result['eligibility'][0]['blockers'])

    def test_frozen_generation_mismatch_blocks_before_case_execution(self):
        from unittest.mock import Mock
        service, provider = self.service(generation_prompt_version='generation-vnext-2')
        store = Mock()
        # Deliberately no question/checkpoint prerequisites: contract guard is first.
        store.evaluation_run.return_value = {'status': 'queued', 'result': {}, 'judge': {'generation_prompt_version': 'generation-vnext-1', 'generation_boundary_sha256': hashlib.sha256(GENERATION_BOUNDARY.encode()).hexdigest()}}
        with self.assertRaisesRegex(ValueError, 'Generation'):
            EvaluationRunner(store, service).execute_baseline('old-run', [], {})
        self.assertEqual(provider.requests, [])

    def test_candidate_mismatch_blocks_before_reservation(self):
        from unittest.mock import Mock
        service, provider = self.service(generation_prompt_version='generation-vnext-2')
        store = Mock()
        from app.evaluation_contract import VERSIONS
        from app.policy import DEFAULT_PIPELINE_CONFIG
        store.candidate.return_value = {'experiment_id': 'experiment', 'config': DEFAULT_PIPELINE_CONFIG, 'reasoning': {}}
        store.experiment.return_value = {'baseline_run_id': 'old-baseline'}
        store.evaluation_run.return_value = {'status': 'completed', 'judge': {**VERSIONS, 'generation_prompt_version': 'generation-vnext-1'}}
        with self.assertRaisesRegex(ValueError, 'Generation'):
            EvaluationRunner(store, service).start_candidate('candidate')
        store.create_baseline_run.assert_not_called()
        self.assertEqual(provider.requests, [])
