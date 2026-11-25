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
        self.winner_config = {**DEFAULT_PIPELINE_CONFIG, 'candidate_k':24}
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
                'root_cause_alignment':'q2最终截断','complementary_capabilities':'保护赢家扩候选','expected_improvement':'预期修1坏0','risks':'q3曾翻错','explanation':'已验证参数优先',
                'hypothesis':'增加上下文覆盖','root_cause':'Retrieval','intervention_direction':'combined','evidence_assertions':[],
                'changes':[{'parameter':'top_k','source_type':'verified','source_candidates':[self.other['id']], 'reason':'历史修好q2',
                            'target_question_ids':['q2'],'evidence_basis':'D事实表remaining_failures q2证据最终位置1',
                            'side_effect_check':{'historical_effects':'伴随q3翻错','protected_overlap':['q3'],'winner_fixed_risk':'q证据保留','gate_risk':'P99余量40秒','mitigation':'完整50题检验','same_premise_evidence':'没有相同前提的观察','different_premise_evidence':'来源与赢家的其他参数不同，不能直接归因','risk_checklist':'完整题卷核对保护题与安全拒答95和P99不超过60秒'},
                            'expected_fixed_count':1,'possible_broken_count':1}]}

    def validate(self,value):
        return validate_d_refinement(value,self.winner,[self.winner,self.other],DEFAULT_PIPELINE_CONFIG,self.facts)

    def test_verified_change_preserves_winner(self):
        config,records=self.validate(self.suggestion())
        self.assertEqual(config,{**self.winner_config,'top_k':6})
        self.assertEqual(records[0]['source_type'],'verified')

    def test_two_edit_winner_can_replace_an_edit(self):
        from app.composite import parameter_diff
        self.winner['config'].update(candidate_k=12, hybrid_alpha=0.7, query_decompose=True)
        self.facts=build_d_facts(self.store,self.store.evaluation_run(self.baseline),self.winner,[self.winner,self.other])
        value=self.suggestion()
        value['proposed_config_diff']['query_decompose']=False
        value['changes'].append({**deepcopy(value['changes'][0]),'parameter':'query_decompose'})
        config,_=self.validate(value)
        self.assertEqual(parameter_diff(config,DEFAULT_PIPELINE_CONFIG),{'top_k':6,'hybrid_alpha':0.7})
        value['proposed_config_diff'].pop('query_decompose')
        value['changes'].pop()
        config, _ = self.validate(value)
        self.assertEqual(parameter_diff(config, DEFAULT_PIPELINE_CONFIG),
                         {'top_k': 6, 'hybrid_alpha': 0.7, 'query_decompose': True})
        value['proposed_config_diff']['hyde'] = True
        with self.assertRaisesRegex(ValueError,'相对 Baseline 最多改 3'):
            self.validate(value)
        value['proposed_config_diff']={'query_decompose':True}
        with self.assertRaisesRegex(ValueError,'D必须不同于 Winner'):
            self.validate(value)

    def test_rejections(self):
        cases=[]
        v=self.suggestion();v['proposed_config_diff']={'top_k':5};cases.append((v,'Pipeline'))
        v=self.suggestion();v['proposed_config_diff'].update(query_rewrite=True,hyde=True,query_decompose=True);cases.append((v,'最多改 3'))
        v=self.suggestion();v['proposed_config_diff']={'candidate_k':24};cases.append((v,'D必须不同于 Winner'))
        v=self.suggestion();del v['changes'][0]['side_effect_check'];cases.append((v,'副作用'))
        v=self.suggestion();v['proposed_config_diff']={'hyde':True};v['changes'][0].update(parameter='hyde',source_type='new_attempt',source_candidates=[]);cases.append((v,'已验证'))
        v=self.suggestion();v['changes'][0]['target_question_ids']=['q3'];cases.append((v,'剩余 Bad Case'))
        for value,message in cases:
            with self.subTest(message=message),self.assertRaisesRegex(ValueError,message):self.validate(value)

    def test_new_attempt_has_explicit_reason(self):
        v=self.suggestion();v['proposed_config_diff']={'hyde':True};v['changes'][0].update(parameter='hyde',source_type='new_attempt',source_candidates=[],why_not_verified='top_k=6伴随q3翻错，保护题重叠')
        self.assertTrue(self.validate(v)[0]['hyde'])

    def test_wrong_protected_overlap_is_normalized_to_fact_table(self):
        # 056：D 三次规划都因模型抄错保护题重叠（多列已错题、漏列翻错的保护题）被拒；改为按事实表规整并留审计。
        v=self.suggestion();v['changes'][0]['side_effect_check']['protected_overlap']=['q2']
        _,records=self.validate(v)
        self.assertEqual(v['changes'][0]['side_effect_check']['protected_overlap'],['q3'])
        self.assertEqual(records[0]['normalized_fields'],[{'field':'side_effect_check.protected_overlap','parameter':'top_k','from':['q2'],'to':['q3']}])
        _,records=self.validate(self.suggestion())
        self.assertNotIn('normalized_fields',records[0])

    def test_partial_records_contrast_but_does_not_require_it(self):
        with self.store.connection() as db:
            db.execute('insert into candidate_configs values (?,?,?,?,?,?,?)',(self.experiment+'-C',self.experiment,'generated',json.dumps({**DEFAULT_PIPELINE_CONFIG,'top_k':6,'multi_query':2}),json.dumps({'candidate_label':'C','round':1}),'{}','now'))
        bundle=self.store.finish_candidate(self.experiment+'-C','evaluated',self.other['result'])
        history=[self.winner,self.other,bundle];facts=build_d_facts(self.store,self.store.evaluation_run(self.baseline),self.winner,history)
        v=self.suggestion();v['changes'][0].update(source_type='partial',source_candidates=[bundle['id']],contrast_ids=[next(c['id'] for c in facts['contrasts'] if c['parameter']=='top_k')])
        self.assertEqual(validate_d_refinement(v,self.winner,history,DEFAULT_PIPELINE_CONFIG,facts)[0]['top_k'],6)
        v['changes'][0]['contrast_ids']=['invented']
        _,records=validate_d_refinement(v,self.winner,history,DEFAULT_PIPELINE_CONFIG,facts)
        self.assertFalse(records[0]['partial_contrast_verified'])
        v['changes'][0].pop('contrast_ids')
        self.assertFalse(validate_d_refinement(v,self.winner,history,DEFAULT_PIPELINE_CONFIG,facts)[1][0]['partial_contrast_verified'])

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

    def q05_combination(self):
        from app.agent_mechanism import CONTRACT

        self.snapshot['questions'][1]['coverage_slot'] = 'Q05'
        with self.store.connection() as db:
            db.execute('update dataset_versions set snapshot_json=? where id=?',
                       (json.dumps(self.snapshot), self.snapshot['id']))
            db.execute('update evaluation_runs set dataset_snapshot_json=? where id=?',
                       (json.dumps(self.snapshot), self.baseline))
            db.execute('update candidate_configs set config_json=? where id=?',
                       (json.dumps({**DEFAULT_PIPELINE_CONFIG, 'query_decompose': True}), self.other['id']))
            db.execute('update experiments set result_json=json_set(result_json,'
                       "'$.mechanism_contract', ?, '$.parameter_effect_ledger', json(?)) where id=?",
                       (CONTRACT, '{"current":[],"historical":[]}', self.experiment))
        preview = patch('app.optimization.load_retrieval_preview', return_value={
            'configs': [{'change': {'candidate_k': 24}}],
        })
        preview.start()
        self.addCleanup(preview.stop)
        value = self.suggestion()
        value.update(combination_mode='partial_fusion', mode_reason='取用合格 B 的拆问',
                     proposed_config_diff={'query_decompose': True}, bad_case_conclusion_ids=['B1'])
        value['changes'][0].update(parameter='query_decompose', source_type='partial')
        return value

    @staticmethod
    def q05_response(value, prompt):
        return json.dumps({**value, 'bad_case_summary': {
            'groups': prompt['bad_case_groups'], 'focus': 'Q05 的生成错误',
            'conclusions': [{'id': 'B1', 'conclusion': '标准证据已进入 Final'}],
        }})

    def test_d_rejects_q05_repair_without_evidence_and_explains_both_retry_paths(self):
        from unittest.mock import Mock

        value = self.q05_combination()
        provider = Mock(settings=None)
        provider.complete.side_effect = lambda _system, user, **_: self.q05_response(value, json.loads(user))
        decision = self.store.create_composite(self.experiment, provider)
        self.assertEqual(decision['outcome'], 'validation_failed')
        self.assertEqual(provider.complete.call_count, 3)
        for attempt in decision['attempts']:
            self.assertIn('Q05：标准证据已进入 Final', attempt['validation_error'])
        for call in provider.complete.call_args_list[1:]:
            feedback = json.loads(call.args[1])['validation_rejection']
            self.assertIn('Q05', feedback['reason'])
            for detail in ('同底座', '逐题中间机制', '不承诺修好的组合探索', 'target_question_ids', 'expected_fixed_count'):
                self.assertIn(detail, feedback['instruction'])

    def test_d_same_parameters_with_no_q05_repair_claim_enters_sandbox(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from app.evaluation import EvaluationRunner

        rejected = self.q05_combination()
        exploration = deepcopy(rejected)
        exploration.update(expected_improvement='验证组合效果', explanation='不承诺修好')
        exploration['changes'][0].update(target_question_ids=[], expected_fixed_count=0, reason='验证组合效果')
        provider = Mock(settings=None)
        provider.complete.side_effect = lambda _system, user, **_: self.q05_response(rejected, json.loads(user))
        self.store.create_composite(self.experiment, provider)
        old = self.store.experiment(self.experiment)['result']['composite']
        self.assertEqual(old['outcome'], 'validation_failed')

        def respond(_system, user, **_kwargs):
            prompt = json.loads(user)
            self.assertIn('validation_rejection', prompt)
            feedback = prompt['validation_rejection']
            self.assertEqual(feedback['reason'], old['reason'])
            return self.q05_response(exploration, prompt)

        provider.complete = Mock(side_effect=respond)
        candidate = self.store.create_composite(self.experiment, provider)
        provider.complete.assert_called_once()
        self.assertEqual(candidate['status'], 'generated', candidate)
        saved = self.store.experiment(self.experiment)['result']['composite']
        self.assertEqual(saved['previous_failures'][0]['attempts'], old['attempts'])
        self.assertEqual(candidate['reasoning']['winner_config_diff'], rejected['proposed_config_diff'])
        self.assertEqual(candidate['reasoning']['mechanism_checks'], [])
        self.assertEqual(candidate['reasoning']['changes'][0]['target_question_ids'], [])
        runner = EvaluationRunner(self.store, SimpleNamespace(model='fixture'))
        with patch.object(runner, '_require_generation_contract'), patch.object(runner, 'snapshot_items', return_value=[]):
            self.assertEqual(runner.candidate_inputs(candidate['id'])[2]['id'], candidate['id'])

    def test_d_uses_agent_output_limit_and_restores_outer_task(self):
        from unittest.mock import Mock
        from app.paid_run import current_request_limit, execution_limits, provider_task

        def complete(*args, **kwargs):
            self.assertEqual(current_request_limit(), 32768)
            return json.dumps(self.suggestion())

        provider = Mock(complete=Mock(side_effect=complete), settings=context.Settings('fixture','https://example.invalid','fixture'))
        with execution_limits({'agent':32768, 'answer':65536}):
            candidate = self.store.create_composite(self.experiment, provider)
            self.assertEqual(candidate['status'], 'generated', candidate.get('reason'))
            with provider_task('answer'):
                self.assertEqual(self.store.create_composite(self.experiment, provider)['id'], candidate['id'])
                self.assertEqual(current_request_limit(), 65536)

    def test_d_recovers_only_missing_closing_brackets_without_another_request(self):
        from unittest.mock import Mock
        raw = json.dumps(self.suggestion())[:-2]
        provider = Mock(complete=Mock(return_value=raw), settings=context.Settings('fixture','https://example.invalid','fixture'))
        candidate = self.store.create_composite(self.experiment, provider)
        self.assertEqual(candidate['status'], 'generated', candidate.get('reason'))
        decision = self.store.experiment(self.experiment)['result']['composite']
        self.assertEqual(decision['provider_calls'], 1)
        self.assertEqual(decision['attempts'][0]['provider_raw_text'], raw)
        self.assertEqual(decision['attempts'][0]['syntax_repair']['appended'], ']}')

    def test_single_winner_must_generate_d_and_invalid_decline_is_recorded(self):
        from unittest.mock import Mock
        self.store.finish_candidate(self.other['id'],'failed',{})
        value=self.suggestion();value.update(should_generate_d=False,proposed_config_diff={},changes=[],explanation='剩余错题没有可靠改法；q3和安全拒答风险不可接受')
        p=Mock(complete=Mock(return_value=json.dumps(value)),settings=context.Settings('fixture','https://example.invalid','fixture'))
        result=self.store.create_composite(self.experiment,p)
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['outcome'],'validation_failed')
        self.assertIn('必须生成D',result['reason'])
        self.assertEqual(p.complete.call_count,3)
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

    def test_sandbox_entry_accepts_d_whose_overlap_was_normalized(self):
        # 057：首次规划规整了保护题重叠并附审计；开跑前复验不再产生审计，不能因此判为"与已审查建议不一致"。
        from types import SimpleNamespace
        from unittest.mock import Mock
        from app.evaluation import EvaluationRunner
        value=self.suggestion();value['changes'][0]['side_effect_check']['protected_overlap']=['q2']
        p=Mock(complete=Mock(return_value=json.dumps(value)),settings=context.Settings('fixture','https://example.invalid','fixture'))
        candidate=self.store.create_composite(self.experiment,p)
        self.assertEqual(candidate['reasoning']['changes'][0]['normalized_fields'][0]['to'],['q3'])
        self.assertEqual(self.store.experiment(self.experiment)['result']['composite']['attempts'][0]['normalized_fields'][0]['from'],['q2'])
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


class QualifiedFusionTests(unittest.TestCase):
    def test_qualified_fusion_can_explore_without_inventing_a_repair_target(self):
        winner = {'id':'R1-B', 'status':'evaluated', 'config':DEFAULT_PIPELINE_CONFIG,
                  'result':{'evaluation_identity':'fixture'}}
        peer = {'id':'R1-C', 'status':'evaluated',
                'config':{**DEFAULT_PIPELINE_CONFIG, 'hybrid_alpha':0.7},
                'result':{'evaluation_identity':'fixture'}}
        source = {'candidate_id':peer['id'], 'qualified':True, 'fixed_question_ids':['q1']}
        facts = {'remaining_failures':[{'question_id':'q2'}], 'protected_questions':[],
                 'contrasts':[], 'history':[source],
                 'parameter_profiles':{'hybrid_alpha':[{'value':0.7, 'observations':[]}]}}
        change = {'parameter':'hybrid_alpha', 'source_type':'partial', 'source_candidates':[peer['id']],
                  'target_question_ids':[], 'reason':'组合探索，未声明要修好剩余错题',
                  'evidence_basis':'来源方案通过资格，q2 仍错',
                  'expected_fixed_count':0, 'possible_broken_count':1,
                  'side_effect_check':{'historical_effects':'未修好 q2', 'protected_overlap':[],
                                       'winner_fixed_risk':'重查 q1', 'gate_risk':'检查 11 项门槛',
                                       'mitigation':'完整 Sandbox'}}
        value = {'combination_mode':'partial_fusion', 'proposed_config_diff':{'hybrid_alpha':0.7},
                 'changes':[change]}
        history = [winner, peer]

        config, changes = validate_d_refinement(value, winner, history, DEFAULT_PIPELINE_CONFIG, facts)
        self.assertEqual(config['hybrid_alpha'], 0.7)
        self.assertEqual(changes[0]['evidence_class'], 'qualified_exploration')
        self.assertFalse(changes[0]['target_repair_verified'])

        mislabeled = {**value, 'changes':[{**change, 'source_type':'verified'}]}
        _, changes = validate_d_refinement(mislabeled, winner, history, DEFAULT_PIPELINE_CONFIG, facts)
        self.assertEqual(changes[0]['source_type'], 'partial')
        self.assertIn({'field':'source_type', 'from':'verified', 'to':'partial'}, changes[0]['normalized_fields'])
        self.assertFalse(changes[0]['target_repair_verified'])

        for field, invalid in (('source_type', 'new_attempt'), ('expected_fixed_count', 1),
                               ('target_question_ids', ['q1'])):
            with self.subTest(field=field):
                proposal = {**value, 'changes':[{**change, field:invalid}]}
                with self.assertRaises(ValueError):
                    validate_d_refinement(proposal, winner, history, DEFAULT_PIPELINE_CONFIG, facts)
        source['qualified'] = False
        with self.assertRaises(ValueError):
            validate_d_refinement(value, winner, history, DEFAULT_PIPELINE_CONFIG, facts)

    def test_qualified_fusion_can_try_a_parameter_without_a_target_repair(self):
        winner = {'id':'R2-B', 'status':'evaluated', 'config':{**DEFAULT_PIPELINE_CONFIG, 'query_decompose':True},
                  'result':{'evaluation_identity':'fixture'}}
        peer = {'id':'R3-B', 'config':{**winner['config'], 'top_k':6}, 'status':'evaluated',
                'result':{'evaluation_identity':'fixture'}}
        source = {'candidate_id':peer['id'], 'qualified':True, 'fixed_question_ids':['q1']}
        facts = {'remaining_failures':[{'question_id':'q2'}],
                 'protected_questions':[{'question_id':'q1'}], 'contrasts':[], 'history':[source],
                 'parameter_profiles':{'top_k':[{'value':6, 'observations':[{'new_failure_question_ids':[]}]}]}}
        value = {'combination_mode':'partial_fusion', 'proposed_config_diff':{'top_k':6},
                 'changes':[{'parameter':'top_k', 'source_type':'partial', 'source_candidates':[peer['id']],
                             'target_question_ids':['q2'], 'reason':'试跑合格方案的组合',
                             'evidence_basis':'来源方案合格，q2 仍错',
                             'expected_fixed_count':1, 'possible_broken_count':1,
                             'side_effect_check':{'historical_effects':'未修好 q2', 'protected_overlap':[],
                                                  'winner_fixed_risk':'重查 q1', 'gate_risk':'检查 11 项门槛',
                                                  'mitigation':'完整 Sandbox'}}]}
        history = [winner, peer]

        config, changes = validate_d_refinement(value, winner, history, DEFAULT_PIPELINE_CONFIG, facts)
        self.assertEqual(config['top_k'], 6)
        self.assertFalse(changes[0]['target_repair_verified'])

        value['changes'][0]['source_type'] = 'verified'
        with self.assertRaisesRegex(ValueError, '已验证来源须曾修好'):
            validate_d_refinement(value, winner, history, DEFAULT_PIPELINE_CONFIG, facts)
        value['changes'][0]['source_type'] = 'partial'
        source['qualified'] = False
        with self.assertRaisesRegex(ValueError, '已验证来源须曾修好'):
            validate_d_refinement(value, winner, history, DEFAULT_PIPELINE_CONFIG, facts)
