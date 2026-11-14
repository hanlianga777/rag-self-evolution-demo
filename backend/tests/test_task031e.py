"""Full rounds use disposable storage and mocked model/evaluation calls only."""
import json
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.governance import GovernanceStore
from app.policy import DEFAULT_PIPELINE_CONFIG
from identity_fixture import completed_baseline, comparison_identity


class FullRoundsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = GovernanceStore(Path(temp.name) / 'test.db')
        completed_baseline(self.store, run_id='BASE')
        self.exp = self.store.create_experiment('BASE')
        from app.paid_schedule import set_settings, set_unattended_authorization
        set_settings(self.store, False)
        set_unattended_authorization(self.store, True, '用户')

    def run_cycle(self, *, full=True, used=0, qualified=True):
        from app.optimization_cycle import run_until_qualified
        store, exp = self.store, self.exp
        events = []
        with store.connection() as db:
            db.execute('UPDATE experiments SET result_json=? WHERE id=?', (json.dumps({
                'strategy_contract':'agent-strategy-4' if full else 'agent-strategy-3',
                **({'round_policy':{'mode':'full_rounds','max_rounds':3}} if full else {})}), exp))
        for i in range(used):
            store.save_candidate(exp, 'old-'+str(i), DEFAULT_PIPELINE_CONFIG, {'round':1,'candidate_label':'A','sandbox_attempts':[{}]})
            store.finish_candidate(exp+'-old-'+str(i), 'evaluated', {'qualification':{'qualified':False}})

        class Agent:
            def __init__(self, *args): pass
            def generate(self, *args, **kwargs):
                e = store.experiment(exp, light=True)
                number = max([c['reasoning'].get('round', 1) for c in e['candidates']] or [0])+1
                events.append(('generate', number))
                for label in 'ABC'[:min(3, 11-e['evaluation_budget']['used'])]:
                    store.save_candidate(exp, f'R{number}-{label}', DEFAULT_PIPELINE_CONFIG, {'round':number,'candidate_label':label})

        class Runner:
            def __init__(self, *args): pass
            def run_candidate(self, cid, **kwargs):
                c = store.reserve_candidate_evaluation(cid)
                label = c['reasoning']['candidate_label']
                events.append(('evaluate', cid.split(exp+'-')[1]))
                return store.finish_candidate(cid, 'evaluated', {
                    **comparison_identity(store, 'BASE'), 'evaluation_complete':True, 'bad_case_count':1,
                    'qualification':{'qualified':qualified and label in {'A','D'}}})

        original_confirm = store.confirm_experiment_report
        def confirm(*args, **kwargs):
            events.append(('gate2', len([e for e in events if e[0]=='conclude'])))
            return original_confirm(*args, **kwargs)
        def composite(*args):
            events.append(('D', len(store.experiment(exp)['candidates'])))
            cid = exp+'-D'
            with store.connection() as db:
                db.execute('INSERT OR IGNORE INTO candidate_configs VALUES (?,?,?,?,?,?,?)', (cid, exp, 'generated', json.dumps(DEFAULT_PIPELINE_CONFIG), '{"candidate_label":"D"}', '{}', '2026-11-14'))
                state = json.loads(db.execute('SELECT result_json FROM experiments WHERE id=?', (exp,)).fetchone()[0])
                state['composite'] = {'status':'generated','candidate_id':cid}
                db.execute('UPDATE experiments SET result_json=? WHERE id=?', (json.dumps(state), exp))
            return store.candidate(cid)
        def conclude(*args):
            e = store.experiment(exp)
            if not e['candidates']: return
            number = max(c['reasoning'].get('round',1) for c in e['candidates'] if c['reasoning'].get('candidate_label')!='D')
            self.assertTrue(e['rounds'][-1]['complete'])
            events.append(('conclude', number))
        with patch('app.optimization_cycle.EvaluationRunner', Runner), patch('app.optimization_cycle.OptimizationAgent', Agent), \
                patch('app.agent_strategy.conclude_round', side_effect=conclude), \
                patch.object(store, 'confirm_experiment_report', side_effect=confirm), patch.object(store, 'create_composite', side_effect=composite):
            state = run_until_qualified(store, SimpleNamespace(provider=object()), exp)
        return state, events, store.experiment(exp)

    def test_a_qualified_still_runs_bc_and_three_rounds_before_gate2_d(self):
        state, events, exp = self.run_cycle()
        self.assertEqual(state['status'], 'recommended', state)
        self.assertEqual([e[1] for e in events if e[0]=='evaluate'], [f'R{n}-{l}' for n in range(1,4) for l in 'ABC']+['D'])
        self.assertEqual([e[1] for e in events if e[0]=='generate'], [1,2,3])
        self.assertLess(events.index(('conclude',3)), next(i for i,e in enumerate(events) if e[0]=='gate2'))
        self.assertEqual(next(e for e in events if e[0]=='D'), ('D',9))
        self.assertEqual(exp['result']['report_confirmation']['actor'], '用户')
        self.assertEqual(exp['result']['report_confirmation']['audit_note'], '用户 2026-11-14 预先授权')

    def test_budget_stops_early_and_reserves_d(self):
        state, events, exp = self.run_cycle(used=9)
        self.assertEqual(state['status'], 'recommended', state)
        self.assertEqual([e[1] for e in events if e[0]=='evaluate'], ['R2-A','R2-B','D'])
        self.assertEqual(exp['evaluation_budget']['used'],12)

    def test_no_winner_stops_after_three_rounds_without_d(self):
        state, events, exp = self.run_cycle(qualified=False)
        self.assertEqual(state['status'],'budget_exhausted',state)
        self.assertEqual(state['phase'],'review')
        self.assertEqual(exp['evaluation_budget']['used'],9)
        self.assertFalse(any(e[0] in {'gate2','D'} for e in events))

    def test_no_policy_preserves_early_qualification(self):
        state, events, exp = self.run_cycle(full=False)
        self.assertEqual(state['status'],'recommended',state)
        self.assertEqual([e[1] for e in events if e[0]=='evaluate'],['R1-A','D'])
        self.assertEqual([c['status'] for c in exp['candidates'] if c['reasoning']['candidate_label']!='D'],['evaluated','skipped','skipped'])

    def test_best_qualified_facts_and_short_round_contract(self):
        from app.optimization import build_agent_prompt, validate_round_contract
        winner = {'id':'A','status':'evaluated','config':{**DEFAULT_PIPELINE_CONFIG,'top_k':6},
            'reasoning':{},'result':{'qualification':{'qualified':True},'bad_case_count':1,
                'gates':{'gates':[{'metric':'safe_rejection_rate','actual':95,'threshold':90,'operator':'>='}]},
                'metrics':{'latency_p50_seconds':9.9,'latency_p99_seconds':51.8}}}
        other = {**winner,'id':'B','result':{**winner['result'],'bad_case_count':2}}
        system, prompt = build_agent_prompt([], DEFAULT_PIPELINE_CONFIG,[winner,other],[],['A','B'],
            round_policy={'mode':'full_rounds','max_rounds':3}, evaluation_budget={'used':9},
            candidate_cases={'A':[{'question_id':'Q29','passed':False}]})
        facts = prompt['best_qualified_candidate']
        self.assertEqual(facts['candidate_id'],'A')
        self.assertEqual(facts['configuration']['top_k'],6)
        self.assertEqual(facts['remaining_bad_cases'][0]['question_ids'],['Q29'])
        self.assertEqual(facts['hard_gates'][0]['margin'],5)
        self.assertEqual(facts['latency_p99_seconds'],51.8)
        self.assertEqual(prompt['round_contract']['count'],2)
        self.assertFalse(prompt['round_contract']['efficiency_optimization'])
        self.assertIn('剩余',system)
        validate_round_contract([{'id':'A','config_diff':{'top_k':6}},{'id':'B','config_diff':{'candidate_k':24}}],DEFAULT_PIPELINE_CONFIG,[],labels=['A','B'])

    def test_zero_bad_cases_does_not_block_next_full_round(self):
        with self.store.connection() as db:
            db.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps({'round_policy':{'mode':'full_rounds','max_rounds':3}}),self.exp))
        self.store.save_candidate(self.exp,'R1-A',DEFAULT_PIPELINE_CONFIG,{'candidate_label':'A','round':1})
        self.store.finish_candidate(self.exp+'-R1-A','evaluated',{'qualification':{'qualified':True},'bad_case_count':0})
        self.assertEqual(self.store.claim_agent_generation('BASE',experiment_id=self.exp)[2],2)

    def test_v4_round_conclusion_is_saved_and_reused(self):
        from app.agent_strategy import conclude_round
        from unittest.mock import Mock
        with self.store.connection() as db:
            db.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps({'strategy_contract':'agent-strategy-4'}),self.exp))
        self.store.save_candidate(self.exp,'R1-A',DEFAULT_PIPELINE_CONFIG,{'candidate_label':'A','round':1,'predicted_fixed_question_ids':['Q1']})
        cid = self.exp+'-R1-A'
        self.store.finish_candidate(cid,'evaluated',{'all_fixed_question_ids':['Q1'],'new_failure_question_ids':[]})
        review = {'plans':[{'candidate_id':cid,'fixed_question_ids':['Q1'],'new_failure_question_ids':[], 'matched_question_ids':['Q1'],'prediction_match_count':1,'unmatched_reason':'全部符合','parameter_assessment':'待验证','evidence_reason':'保存证据','conclusion':'有效'}],'lessons':['保留保存依据']}
        provider = Mock(complete=Mock(return_value=json.dumps(review)),settings=None)
        runtime = SimpleNamespace(provider=provider)
        self.assertEqual(conclude_round(self.store,runtime,self.exp)['status'],'saved')
        self.assertEqual(conclude_round(self.store,runtime,self.exp)['review'],review)
        self.assertEqual(provider.complete.call_count,1)


class MigrationTests(unittest.TestCase):
    setUp = FullRoundsTests.setUp
    def test_migration_is_atomic_repeatable_and_preserves_proposals(self):
        spec = importlib.util.spec_from_file_location('migration031e',Path(__file__).resolve().parents[2]/'scripts/migrate_task031e.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        store = self.store
        with store.connection() as db:
            db.execute('UPDATE experiments SET id=? WHERE id=?',(module.EXPERIMENT,self.exp))
        for label in 'BC':
            store.save_candidate(module.EXPERIMENT,'R1-'+label,{**DEFAULT_PIPELINE_CONFIG,'top_k':6},{'candidate_label':label,'round':1,'proposal':'保留原方案','predicted_fixed_question_ids':['Q1']})
            store.skip_candidate(module.EXPERIMENT+'-R1-'+label,'用户','old')
        with store.connection() as db:
            db.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps({
                'report_confirmation':{'winner_id':'old'},'composite':{'status':'no_effective_composite'},
                'd_facts':{'old':True},'round_conclusions':{'1':{'status':'saved'}},'optimization_cycle':{'status':'recommended'}}),module.EXPERIMENT))
        before = store.experiment(module.EXPERIMENT)
        with patch.object(module._TransactionStore,'refresh_recommendation',side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError):module.migrate(store)
        self.assertEqual(store.experiment(module.EXPERIMENT),before)
        self.assertTrue(module.migrate(store))
        after = store.experiment(module.EXPERIMENT)
        self.assertFalse(module.migrate(store))
        self.assertEqual(store.experiment(module.EXPERIMENT),after)
        self.assertEqual(after['result']['strategy_contract'],'agent-strategy-4')
        self.assertNotIn('report_confirmation',after['result'])
        self.assertEqual(after['result']['report_confirmation_history'][0]['superseded_reason'],module.REASON)
        self.assertEqual(after['result']['round_conclusions'],{})
        self.assertEqual(after['result']['round_conclusions_history']['1'],[{'status':'saved'}])
        for old,new in zip(before['candidates'],after['candidates']):
            self.assertEqual(new['status'],'generated')
            self.assertEqual(old['reasoning'],new['reasoning'])
            self.assertEqual(old['config'],new['config'])
            self.assertEqual(new['result']['skip_history'],[old['result']['skip']])
        self.assertEqual(store.recommendation(module.EXPERIMENT)['status'],'WAITING_FOR_ROUND_COMPLETION')


class AgentGenerationTests(unittest.TestCase):
    from test_optimization_contract import OptimizationContractTests
    setUp = OptimizationContractTests.setUp

    def test_real_agent_generates_only_remaining_budget_and_saves_v4_strategy(self):
        from app.optimization import OptimizationAgent
        from app.paid_schedule import set_settings
        from test_optimization_contract import drafts
        from agent_response_fixture import with_review
        store = self.store
        set_settings(store,False)
        exp = store.create_experiment('EVAL-test')
        with store.connection() as db:
            db.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps({'strategy_contract':'agent-strategy-4','round_policy':{'mode':'full_rounds','max_rounds':3}}),exp))
        for i in range(9):
            store.save_candidate(exp,'old-'+str(i),DEFAULT_PIPELINE_CONFIG,{'round':1,'candidate_label':'A','sandbox_attempts':[{}]})
            store.finish_candidate(exp+'-old-'+str(i),'evaluated',{'qualification':{'qualified':False},'all_fixed_question_ids':[],'new_failure_question_ids':[]})
        class Provider:
            calls = 0
            def complete(provider, system, user, **kwargs):
                provider.calls += 1
                prompt = json.loads(user)
                provider.prompt = prompt
                result = drafts()
                result['candidates'] = result['candidates'][:len(prompt['goal']['candidate_labels'])]
                with_review(result,prompt)
                result['prior_round_review']['summary'] = '依据保存结果继续'
                result['bad_case_summary'] = {'groups':prompt['bad_case_groups'],'focus':'保存的检索问题','conclusions':[{'id':'B1','conclusion':'检索遗漏'}]}
                for c in result['candidates']:
                    c.update(adjustments=[{'parameter':k,'baseline_value':DEFAULT_PIPELINE_CONFIG[k],'candidate_value':v,'expected_impact':'预计修好Q1'} for k,v in c['config_diff'].items()],
                        risks=[{'question_ids':['Q1'],'metric':'latency','reason':'待验证'}],bad_case_conclusion_ids=['B1'],predicted_fixed_question_ids=['Q1'])
                return json.dumps(result)
        provider = Provider()
        result = OptimizationAgent(store,provider).generate('EVAL-test',experiment_id=exp)
        self.assertEqual(provider.calls,1)
        self.assertEqual(provider.prompt['goal']['candidate_labels'],['A','B'])
        self.assertEqual(len(result['candidates']),11)
        self.assertIn('2',result['result']['agent_strategies'])
        self.assertEqual(result['result']['strategy_contract'],'agent-strategy-4')


class CompositeV4Tests(unittest.TestCase):
    from test_task021a_composite import RefinementTests
    setUp = RefinementTests.setUp
    result = RefinementTests.result
    suggestion = RefinementTests.suggestion

    def test_v4_d_uses_history_from_all_rounds_and_validates_mode(self):
        from unittest.mock import Mock
        with self.store.connection() as db:
            state=json.loads(db.execute('SELECT result_json FROM experiments WHERE id=?',(self.experiment,)).fetchone()[0])
            state['strategy_contract']='agent-strategy-4'
            db.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps(state),self.experiment))
            for number,label in ((2,'B'),(3,'C')):
                db.execute('INSERT INTO candidate_configs SELECT ?,experiment_id,status,config_json,?,result_json,created_at FROM candidate_configs WHERE id=?',
                    (self.experiment+f'-R{number}-{label}',json.dumps({'round':number,'candidate_label':label}),self.other['id']))
        value=self.suggestion()
        provider=Mock(complete=Mock(return_value=json.dumps(value)),settings=None)
        rejected=self.store.create_composite(self.experiment,provider)
        self.assertEqual(rejected['status'],'failed')
        self.assertIn('D须选择',rejected['reason'])
        value.update(combination_mode='winner_plus_verified',mode_reason='只增加历史已修好剩余题的参数')
        provider.complete.return_value=json.dumps(value)
        generated=self.store.create_composite(self.experiment,provider)
        self.assertEqual(generated['status'],'generated')
        prompt=json.loads(provider.complete.call_args.args[1])
        history={c['candidate_id'] for c in prompt['d_facts']['history']}
        self.assertIn(self.experiment+'-R2-B',history)
        self.assertIn(self.experiment+'-R3-C',history)


if __name__ == '__main__':
    unittest.main()
