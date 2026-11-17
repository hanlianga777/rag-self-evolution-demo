"""Low Judge recovery preserves off history and separates reusable verdicts."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.ai_service import AiService
from rubric_fixture import rubric_judge_output
from app.config import Settings, load_settings
from app.governance import GovernanceStore
from app.providers import DeepSeekProvider, judge_thinking, thinking_config
from app.request_reuse import reuse_scope
from app.paid_run import provider_task


class JudgeRecoveryTests(unittest.TestCase):
    def test_default_judge_request_is_low_while_generation_defaults_max(self):
        with tempfile.TemporaryDirectory() as folder:
            env = Path(folder) / '.env'
            env.write_text('')
            with patch.dict('os.environ', {'RAG_DEMO_ENV_PATH':str(env), 'DEEPSEEK_API_KEY':'fixture'}, clear=True):
                settings = load_settings()
                self.assertEqual(Settings('', '', 'test').judge_thinking, 'low')
                provider = DeepSeekProvider(settings)
                with judge_thinking(), provider_task('judge'):
                    payload = json.loads(provider._request('system', 'user', True, False, .9).data)
                self.assertEqual(payload['thinking'], {'type':'enabled'})
                self.assertEqual(payload['reasoning_effort'], 'low')
                self.assertNotIn('temperature', payload)
                self.assertEqual(thinking_config('answer')['reasoning_effort'], 'max')

    def test_frozen_off_run_does_not_inherit_new_low_default(self):
        from app.evaluation import frozen_run_judge
        with tempfile.TemporaryDirectory() as folder:
            store = GovernanceStore(Path(folder) / 'test.db')
            run = {'id':'OLD', 'dataset_snapshot_json':'{}', 'config':{},
                   'judge':{'judge_thinking':{'task':'judge','thinking':{'type':'disabled'}}}}
            class Runner:
                @frozen_run_judge
                def execute(self, run_id):
                    return thinking_config('judge')
            runner = Runner()
            runner.store = SimpleNamespace(evaluation_run=lambda _:run, connection=store.connection)
            with judge_thinking('low'):
                result = runner.execute('OLD')
            self.assertEqual(result, {'task':'judge','thinking':{'type':'disabled'}})

    @patch.dict('os.environ', {'JUDGE_SAMPLES': '3'})
    def test_judge_reuse_includes_effective_effort_and_prompt(self):
        with tempfile.TemporaryDirectory() as folder:
            store = GovernanceStore(Path(folder) / 'test.db')
            run = {'id':'BASE', 'dataset_snapshot_json':'{}', 'config':{}, 'judge':{'model':'test'}}
            calls = []
            class Provider:
                settings = SimpleNamespace(model='test')
                def judge(self, *args, **kwargs):
                    calls.append(thinking_config('judge'))
                    return {**rubric_judge_output(kwargs['context']['category']), 'correctness_reason':f'第 {len(calls)} 次假判分'}
            service = AiService(store, None, Provider(), False)
            from app.rubric_judge import RUBRIC_VERSION
            context = {'contract_version':RUBRIC_VERSION, 'category':'positive', 'final_texts':['资料']}
            with reuse_scope(store, run):
                with judge_thinking('off'):
                    first = service.judge('题','参考','回答','positive',context=context)
                    same = service.judge('题','参考','回答','positive',context=context)
                with judge_thinking('low'):
                    low = service.judge('题','参考','回答','positive',context=context)
                    with patch('app.rubric_judge.RUBRIC_PROMPT_SHA256', '新版判分提示词哈希'):
                        changed = service.judge('题','参考','回答','positive',context=context)
                        repeated = service.judge('题','参考','回答','positive',context=context)
            self.assertEqual([[sample['correctness_reason'] for sample in result['samples']] for result in (first, same, low, changed, repeated)],
                             [[f'第 {n} 次假判分' for n in numbers] for numbers in ([1,2,3], [1,2,3], [4,5,6], [7,8,9], [7,8,9])])
            self.assertEqual(len(calls), 9)
            self.assertEqual(same['reused_from']['run_id'], 'BASE')
            self.assertNotIn('reused_from', low)
            self.assertNotIn('reused_from', changed)

    def test_replay_carries_generation_cache_but_never_old_judgments(self):
        from app.request_reuse import reuse_result, carry_generation_reuse
        with tempfile.TemporaryDirectory() as folder:
            store = GovernanceStore(Path(folder) / 'test.db')
            source = {'id':'OFF', 'dataset_snapshot_json':'{}', 'config':{}, 'judge':{'judge_thinking':'off'}}
            target = {**source, 'id':'LOW', 'judge':{'judge_thinking':'low'}}
            with reuse_scope(store, source):
                reuse_result('generation', {'request':'same'}, lambda:{'answer':'原回答'})
                reuse_result('retrieval', {'request':'query'}, lambda:{'answer':'原查询'})
                reuse_result('judge', {'request':'same'}, lambda:{'answer':'旧判分'})
            self.assertEqual(carry_generation_reuse(store, source, {**target, 'dataset_snapshot_json':'{\"id\":\"另一卷\"}'}), 0)
            self.assertEqual(carry_generation_reuse(store, source, target), 2)
            carry_generation_reuse(store, source, target)  # Recovery is idempotent.
            def forbidden():
                self.fail('An unchanged generation request must not call Provider')
            with reuse_scope(store, target):
                answer = reuse_result('generation', {'request':'same'}, forbidden)
                query = reuse_result('retrieval', {'request':'query'}, forbidden)
                verdict = reuse_result('judge', {'request':'same'}, lambda:{'answer':'新判分'})
                changed = reuse_result('generation', {'request':'changed'}, lambda:{'answer':'新回答'})
            self.assertEqual(answer['answer'], '原回答')
            self.assertEqual(answer['reused_from']['run_id'], 'OFF')
            self.assertEqual(query['answer'], '原查询')
            self.assertEqual(verdict['answer'], '新判分')
            self.assertNotIn('reused_from', verdict)
            self.assertEqual(changed['answer'], '新回答')

    def test_failed_chain_without_experiment_can_be_rearmed_and_archived(self):
        from identity_fixture import completed_baseline
        from app.baseline_chain import arm_chain, chain_status
        from app.paid_schedule import _write, _settings
        with tempfile.TemporaryDirectory() as folder:
            store = GovernanceStore(Path(folder) / 'test.db')
            completed_baseline(store, run_id='NEW')
            failed = {'baseline_id':'OLD', 'status':'failed', 'error':'技术失败', 'causal_evidence':True}
            _write(store, 'baseline_agent_chain', failed)
            state = arm_chain(store, 'NEW', causal_evidence=True, round_policy={'mode':'full_rounds','max_rounds':3})
            self.assertEqual(state['status'], 'waiting_baseline')
            self.assertEqual(_settings(store)['baseline_agent_chain_history'], [failed])
            self.assertEqual(arm_chain(store, 'NEW', causal_evidence=True), state)
            with self.assertRaises(ValueError):
                arm_chain(store, 'OTHER', causal_evidence=True)
            self.assertEqual(chain_status(store), state)
