"""Winner refinement contracts and frozen evidence; Stub transport, temporary DBs."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch
import test_evaluation_context as context
from app.policy import DEFAULT_PIPELINE_CONFIG
from app.composite import build_d_facts, validate_d_refinement


class RefinementTests(unittest.TestCase):
    result = context.CompositeTests.result
    def setUp(self):
        clock=patch('app.paid_schedule.utc_now',return_value=__import__('datetime').datetime(2026,11,7,tzinfo=__import__('datetime').timezone.utc))
        clock.start();self.addCleanup(clock.stop)
        context.CompositeTests.setUp(self)
        self.winner_config = {**DEFAULT_PIPELINE_CONFIG, 'candidate_k':24, 'generation_thinking':'high'}
        self.snapshot['questions'] = [{'id':q,'evidence':[{'source_chunk_ids':['c']}]} for q in ('q','q2','q3')]
        self.snapshot['question_ids'] = ['q','q2','q3']
        with self.store.connection() as db:
            db.execute('delete from evaluation_case_results where run_id=? and question_id=?',(self.baseline,'q2'))
            db.execute('update evaluation_runs set dataset_snapshot_json=? where id=?',(json.dumps(self.snapshot),self.baseline))
            db.execute('update dataset_versions set snapshot_json=? where id=?',(json.dumps(self.snapshot),self.snapshot['id']))
            db.execute('update candidate_configs set config_json=? where id=?',(json.dumps(self.winner_config),self.winner['id']))
            db.execute('update candidate_configs set config_json=? where id=?',(json.dumps({**DEFAULT_PIPELINE_CONFIG,'top_k':6}),self.other['id']))
        self.store.record_evaluation_case(self.baseline,'q2',{'passed':False})
        self.store.record_evaluation_case(self.baseline,'q3',{'passed':True})
        for candidate, passed in ((self.winner, (True,False,True)),(self.other,(True,True,False))):
            run=self.store.create_evaluation_run(self.snapshot,candidate['config'],self.meta)
            for q,ok in zip(('q','q2','q3'),passed):
                self.store.record_evaluation_case(run,q,{'passed':ok,'programmatic_metrics':{'retrieval_trace':{'candidates':[{'chunk_id':'c'}], 'reranked':[{'chunk_id':'x'},{'chunk_id':'c'}], 'final':[{'chunk_id':'c'}]}}})
            result={**context.CompositeTests.result(self),'evaluation_run_id':run,'metrics':{'latency_p99_seconds':20,'safe_rejection_rate':100},'all_fixed_question_ids':['q'] if candidate==self.winner else ['q','q2'],'new_failure_question_ids':[] if candidate==self.winner else ['q3']}
            self.store.finish_candidate(candidate['id'],'evaluated',result)
        self.winner=self.store.candidate(self.winner['id']); self.other=self.store.candidate(self.other['id'])
        self.facts=build_d_facts(self.store,self.store.evaluation_run(self.baseline),self.winner,[self.winner,self.other])

    def suggestion(self):
        return {'should_generate_d':True,'action_name':'扩大赢家上下文','proposed_config_diff':{'top_k':6},
                'root_cause_alignment':'q2最终截断','complementary_capabilities':'保护赢家扩候选和high','expected_improvement':'预期修1坏0','risks':'q3曾翻错','explanation':'已验证参数优先',
                'hypothesis':'增加上下文覆盖','root_cause':'Retrieval','intervention_direction':'combined','evidence_assertions':[],
                'changes':[{'parameter':'top_k','source_type':'verified','source_candidates':[self.other['id']], 'reason':'历史修好q2',
                            'target_question_ids':['q2'],'evidence_basis':'D事实表remaining_failures q2证据最终位置1',
                            'side_effect_check':{'historical_effects':'伴随q3翻错','protected_overlap':['q3'],'winner_fixed_risk':'q证据保留','gate_risk':'P99余量40秒','mitigation':'完整50题检验'},
                            'expected_fixed_count':1,'possible_broken_count':1}]}

    def validate(self,value):
        return validate_d_refinement(value,self.winner,[self.winner,self.other],DEFAULT_PIPELINE_CONFIG,self.facts)

    def test_verified_change_preserves_winner(self):
        config,records=self.validate(self.suggestion())
        self.assertEqual(config,{**self.winner_config,'top_k':6})
        self.assertEqual(records[0]['source_type'],'verified')

    def test_rejections(self):
        cases=[]
        v=self.suggestion();v['proposed_config_diff']={'top_k':5};cases.append((v,'Pipeline'))
        v=self.suggestion();v['proposed_config_diff'].update(query_rewrite=True,hyde=True);cases.append((v,'2'))
        v=self.suggestion();v['proposed_config_diff']={'candidate_k':12};cases.append((v,'Winner'))
        v=self.suggestion();del v['changes'][0]['side_effect_check'];cases.append((v,'副作用'))
        v=self.suggestion();v['proposed_config_diff']={'hyde':True};v['changes'][0].update(parameter='hyde',source_type='new_attempt',source_candidates=[]);cases.append((v,'已验证'))
        v=self.suggestion();v['changes'][0]['source_type']='partial';cases.append((v,'拆分'))
        v=self.suggestion();v['changes'][0]['target_question_ids']=['q3'];cases.append((v,'剩余错题'))
        for value,message in cases:
            with self.subTest(message=message),self.assertRaisesRegex(ValueError,message):self.validate(value)

    def test_new_attempt_has_explicit_reason(self):
        v=self.suggestion();v['proposed_config_diff']={'hyde':True};v['changes'][0].update(parameter='hyde',source_type='new_attempt',source_candidates=[],why_not_verified='top_k=6伴随q3翻错，保护题重叠')
        self.assertTrue(self.validate(v)[0]['hyde'])

    def test_partial_requires_real_single_parameter_contrast(self):
        with self.store.connection() as db:
            db.execute('insert into candidate_configs values (?,?,?,?,?,?,?)',(self.experiment+'-C',self.experiment,'generated',json.dumps({**DEFAULT_PIPELINE_CONFIG,'top_k':6,'multi_query':2}),json.dumps({'candidate_label':'C','round':1}),'{}','now'))
        bundle=self.store.finish_candidate(self.experiment+'-C','evaluated',self.other['result'])
        history=[self.winner,self.other,bundle];facts=build_d_facts(self.store,self.store.evaluation_run(self.baseline),self.winner,history)
        v=self.suggestion();v['changes'][0].update(source_type='partial',source_candidates=[bundle['id']],contrast_ids=[next(c['id'] for c in facts['contrasts'] if c['parameter']=='top_k')])
        self.assertEqual(validate_d_refinement(v,self.winner,history,DEFAULT_PIPELINE_CONFIG,facts)[0]['top_k'],6)
        v['changes'][0]['contrast_ids']=['invented']
        with self.assertRaisesRegex(ValueError,'拆分'):validate_d_refinement(v,self.winner,history,DEFAULT_PIPELINE_CONFIG,facts)

    def test_facts_match_saved_cases_and_cover_every_option(self):
        from app.policy import ALLOWED_SEARCH_SPACE
        self.assertEqual([r['question_id'] for r in self.facts['remaining_failures']],['q2'])
        row=self.facts['remaining_failures'][0]
        self.assertEqual(row['evidence_positions'][0],{'chunk_id':'c','candidates':1,'reranked':2,'final':1})
        self.assertEqual(row['historical_fixes'][0]['candidate_id'],self.other['id'])
        self.assertEqual(row['historical_fixes'][0]['new_failure_question_ids'],['q3'])
        self.assertEqual([r['question_id'] for r in self.facts['protected_questions'] if r['winner_fixed']],['q'])
        self.assertEqual([r['question_id'] for r in self.facts['protected_questions'] if r['historical_flips']],['q3'])
        self.assertEqual({k:len(v) for k,v in self.facts['parameter_profiles'].items()},{k:len(v) for k,v in ALLOWED_SEARCH_SPACE.items()})
        self.assertEqual(next(g for g in self.facts['gate_margins'] if g['metric']=='latency_p99_seconds')['margin'],40)

    def test_agent_receives_and_saves_facts_retries_and_reuses(self):
        from unittest.mock import Mock
        good=self.suggestion();bad=deepcopy(good);del bad['changes'][0]['side_effect_check']
        provider=Mock(complete=Mock(side_effect=[json.dumps(bad),json.dumps(good)]),settings=context.Settings('fixture','https://example.invalid','fixture'))
        result=self.store.create_composite(self.experiment,provider)
        self.assertEqual(result['status'],'generated',result)
        decision=self.store.experiment(self.experiment)['result']['composite']
        self.assertEqual(decision['facts'],self.facts)
        self.assertEqual(json.loads(provider.complete.call_args.args[1])['d_facts'],self.facts)
        self.assertEqual(len(decision['attempts']),2)
        self.assertIn('副作用',decision['attempts'][0]['validation_error'])
        self.assertEqual(self.store.create_composite(self.experiment,provider)['id'],result['id'])
        self.assertEqual(provider.complete.call_count,2)

    def test_single_winner_can_decline_and_recommendation_recomputed(self):
        from unittest.mock import Mock
        self.store.finish_candidate(self.other['id'],'failed',{})
        value=self.suggestion();value.update(should_generate_d=False,proposed_config_diff={},changes=[],explanation='剩余错题没有可靠改法；q3和安全拒答风险不可接受')
        p=Mock(complete=Mock(return_value=json.dumps(value)),settings=context.Settings('fixture','https://example.invalid','fixture'))
        result=self.store.create_composite(self.experiment,p)
        self.assertEqual(result['status'],'no_effective_composite')
        self.assertEqual(result['outcome'],'declined')
        self.assertEqual(p.complete.call_count,1)
        self.assertEqual(self.store.recommendation(self.experiment)['result']['recommended_candidate'],self.winner['id'])

    def test_three_invalid_decisions_distinct_from_decline(self):
        from unittest.mock import Mock
        p=Mock(complete=Mock(return_value=json.dumps({'should_generate_d':True})),settings=context.Settings('fixture','https://example.invalid','fixture'))
        result=self.store.create_composite(self.experiment,p)
        self.assertEqual((result['status'],result['outcome'],result['provider_calls']),('failed','validation_failed',3))
        self.assertTrue(all('provider_raw_text' in a for a in result['attempts']))

    def test_reviews_restored_from_traces_and_missing_is_explicit(self):
        with self.store.connection() as db:
            for n in (1,2):
                db.execute("insert into agent_traces(experiment_id,status,result_json,created_at) values (?,'completed',?,'now')",(self.experiment,json.dumps({'round':n,'prior_round_review':{'plans':[],'conclusions':[{'id':'L1','conclusion':str(n)}]}})))
        with self.store.connection() as db:
            db.execute('insert into candidate_configs select ?,experiment_id,status,config_json,?,result_json,created_at from candidate_configs where id=?',(self.experiment+'-R3-A',json.dumps({'round':3,'candidate_label':'A'}),self.winner['id']))
        self.store.restore_round_reviews(self.experiment)
        history=self.store.experiment(self.experiment)['result']['prior_round_reviews']
        self.assertEqual(history['1']['review']['conclusions'][0]['conclusion'],'1')
        self.assertEqual(history['2']['review']['conclusions'][0]['conclusion'],'2')
        self.assertEqual(history['3']['reason'],'未保存')
        self.store.restore_round_reviews(self.experiment)
        self.assertEqual(self.store.experiment(self.experiment)['result']['prior_round_reviews'],history)

    def test_sandbox_entry_revalidates_refinement_and_detects_tampering(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from app.evaluation import EvaluationRunner
        p=Mock(complete=Mock(return_value=json.dumps(self.suggestion())),settings=context.Settings('fixture','https://example.invalid','fixture'))
        candidate=self.store.create_composite(self.experiment,p)
        runner=EvaluationRunner(self.store,SimpleNamespace(model='fixture'))
        with patch.object(runner,'_require_generation_contract'),patch.object(runner,'snapshot_items',return_value=[]):
            self.assertEqual(runner.candidate_inputs(candidate['id'])[2]['id'],candidate['id'])
            with self.store.connection() as db:
                db.execute('update candidate_configs set config_json=? where id=?',(json.dumps({**candidate['config'],'top_k':4}),candidate['id']))
            with self.assertRaisesRegex(ValueError,'已审查'):runner.candidate_inputs(candidate['id'])

    def test_new_round_review_does_not_overwrite_previous_round(self):
        exp=self.store.create_experiment(self.baseline,'generating')
        for number in (1,2):
            with self.store.connection() as db:
                state=json.loads(db.execute('select result_json from experiments where id=?',(exp,)).fetchone()[0])
                state['agent_generation']={'token':'fixture'}
                db.execute("update experiments set status='generating',result_json=? where id=?",(json.dumps(state),exp))
            self.store.save_agent_round(exp,[],{'round':number,'prior_round_review':{'plans':[],'conclusions':[{'id':'L1','conclusion':str(number)}]}},generation_token='fixture')
        history=self.store.experiment(exp)['result']['prior_round_reviews']
        self.assertEqual([history[str(n)]['review']['conclusions'][0]['conclusion'] for n in (1,2)],['1','2'])

    def test_evaluation_failure_is_exposed_separately(self):
        from unittest.mock import Mock
        p=Mock(complete=Mock(return_value=json.dumps(self.suggestion())),settings=context.Settings('fixture','https://example.invalid','fixture'))
        d=self.store.create_composite(self.experiment,p)
        self.store.finish_candidate(d['id'],'failed',{'error':'fixture technical failure'})
        self.assertEqual(self.store.refresh_recommendation(self.experiment)['d_outcome'],'evaluation_failed')

    def test_hybrid_off_uses_same_option_constraints_as_pipeline(self):
        v=self.suggestion();v['proposed_config_diff']={'hybrid_search':False};v['changes'][0].update(parameter='hybrid_search',source_type='new_attempt',source_candidates=[],why_not_verified='已验证TopK伴随保护题翻错')
        config,_=self.validate(v)
        self.assertFalse(config['hybrid_search']);self.assertNotIn('hybrid_alpha',config)

    def test_facts_saved_before_peak_wait_without_calling_provider(self):
        from unittest.mock import Mock
        provider=Mock()
        with patch('app.paid_schedule.wait_for_off_peak',side_effect=InterruptedError('fixture peak queue')):
            with self.assertRaisesRegex(InterruptedError,'peak queue'):self.store.create_composite(self.experiment,provider)
        self.assertEqual(self.store.experiment(self.experiment)['result']['d_facts'],self.facts)
        provider.complete.assert_not_called()

    def test_scalar_format_conversion_does_not_invent_sources(self):
        from unittest.mock import Mock
        value=self.suggestion();row=value['changes'][0]
        row.update(source_candidates=self.other['id'].rsplit('-',1)[-1],target_question_ids='q2',expected_fixed_count='1',possible_broken_count='1')
        row['side_effect_check']['protected_overlap']='q3'
        value['proposed_config_diff']['top_k']='6';value['should_generate_d']='true';value['risks']=['风险一','风险二']
        provider=Mock(complete=Mock(return_value=json.dumps(value)),settings=context.Settings('fixture','https://example.invalid','fixture'))
        d=self.store.create_composite(self.experiment,provider)
        self.assertEqual(d['status'],'generated',d)
        self.assertEqual(d['config']['top_k'],6)
        self.assertEqual(d['reasoning']['changes'][0]['source_candidates'],[self.other['id']])
        self.assertEqual(d['reasoning']['risk'],'风险一；风险二')

    def test_equivalent_numeric_value_does_not_count_as_third_change(self):
        value=self.suggestion();value['proposed_config_diff']['min_score']=0.0
        self.assertEqual(self.validate(value)[0]['min_score'],0)
