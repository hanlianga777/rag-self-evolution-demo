"""Request identity, persistence and causal evidence; no external calls."""
import json
import tempfile
import unittest
from pathlib import Path
from copy import deepcopy
from app.governance import GovernanceStore


class RequestReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = GovernanceStore(Path(self.tmp.name) / 'demo.db')
        self.run = {'id':'BASE', 'dataset_snapshot_json':json.dumps({'id':'卷一','questions':['题一']}),
                    'config':{'knowledge_identity':'库一'}, 'judge':{'model':'模型一','generation_prompt_version':'提示一'}}

    def test_same_complete_request_reuses_first_result_after_restart(self):
        from app.request_reuse import reuse_scope, reuse_result
        calls = []
        def generate():
            calls.append(1); return {'content':'首次回答', 'usage':{'total_tokens':10}}
        with reuse_scope(self.store, self.run):
            original = reuse_result('generation', {'system':'规则','user':'问题及证据','temperature':0}, generate)
        other = {**self.run, 'id':'CANDIDATE'}
        with reuse_scope(GovernanceStore(self.store.database_path), other):
            reused = reuse_result('generation', {'system':'规则','user':'问题及证据','temperature':0}, generate)
        self.assertEqual(len(calls),1)
        self.assertEqual(reused['content'],original['content'])
        self.assertEqual(reused['reused_from']['run_id'],'BASE')

    def test_any_request_or_scope_change_misses(self):
        from app.request_reuse import reuse_scope, reuse_result
        calls = []
        def action(): calls.append(1); return {'content':'回答'}
        payload = {'system':'提示','question':'题','evidence':'证据','model':'模型','temperature':0}
        with reuse_scope(self.store,self.run):
            reuse_result('generation',payload,action)
            for key in payload:
                changed = {**payload,key:'变化'}
                reuse_result('generation',changed,action)
            reuse_result('judge',payload,action)
        for key in ('dataset_snapshot_json','config','judge'):
            changed=deepcopy(self.run)
            if key=='dataset_snapshot_json':changed[key]=json.dumps({'id':'卷二'})
            elif key=='config':changed[key]['knowledge_identity']='库二'
            else:changed[key]['generation_prompt_version']='提示二'
            with reuse_scope(self.store,changed):reuse_result('generation',payload,action)
        self.assertEqual(len(calls),10)

    def test_invalid_judgment_not_cached(self):
        from app.request_reuse import reuse_scope, reuse_result
        with reuse_scope(self.store,self.run):
            with self.assertRaises(ValueError):reuse_result('judge',{'answer':'回答'},lambda: (_ for _ in ()).throw(ValueError('无效引用')))
            result=reuse_result('judge',{'answer':'回答'},lambda:{'verdict':'PASS'})
            self.assertNotIn('reused_from',result)


class CausalTests(unittest.TestCase):
    def test_compare_actual_context_ignores_scores_but_not_order_or_text(self):
        from app.agent_inputs import case_comparisons
        def case(passed,text='证据',score=1):
            return {'question_id':'saved-01','passed':passed,'programmatic_metrics':{'retrieval_trace':{'final':[{'chunk_id':'c1','content':text,'score':score}]}},'judge_result':{}}
        rows=case_comparisons([case(False)],[case(True,score=.5)])
        self.assertEqual(rows[0]['变化'],'修好');self.assertEqual(rows[0]['题号'],'Q01')
        self.assertFalse(rows[0]['证据变化'])
        self.assertTrue(case_comparisons([case(False)],[case(True,text='其他证据')])[0]['证据变化'])
        self.assertIsNone(case_comparisons([{'question_id':'saved-01','passed':False}],[case(False)])[0]['证据变化'])

    def test_max_two_changes_and_distinct_directions(self):
        from app.agent_strategy import validate_causal_proposals
        rows=[{'id':c,'direction':c,'config_diff':{k:1}} for c,k in zip('ABC',('top_k','candidate_k','min_score'))]
        validate_causal_proposals({'candidates':rows}, {})
        rows[0]['config_diff']={'top_k':4,'candidate_k':24,'rerank':False}
        with self.assertRaisesRegex(ValueError,'两个'):validate_causal_proposals({'candidates':rows},{})
        rows[0]['config_diff']={'top_k':4};rows[1]['direction']='A'
        with self.assertRaisesRegex(ValueError,'方向'):validate_causal_proposals({'candidates':rows},{})

    def test_unchanged_evidence_cannot_be_attributed_to_retrieval(self):
        from app.agent_strategy import validate_causal_proposals
        facts={'old':[{'题号':'Q01','题目键':'saved-01','证据变化':False,'变化':'新错'}]}
        response={'candidates':[], 'prior_round_review':{'plans':[{'candidate_id':'old','causal_claims':[{'question_id':'Q01','parameter':'min_score','conclusion':'有效'}]}]}}
        with self.assertRaisesRegex(ValueError,'证据未变'):validate_causal_proposals(response,facts)
        response['prior_round_review']['plans'][0]['causal_claims'][0]['conclusion']='不确定'
        validate_causal_proposals(response,facts)


class IntegratedReuseTests(RequestReuseTests):
    def test_actual_provider_payload_reused_without_transport_or_usage(self):
        from unittest.mock import patch
        from app.request_reuse import reuse_scope
        from app.providers import DeepSeekProvider
        from app.config import Settings
        from app.paid_run import provider_task
        from app.telemetry import collect_usage
        provider=DeepSeekProvider(Settings('fixture','https://example.invalid','deepseek-flash'))
        response={'content':'相同回答','ttft_ms':1,'input_tokens':10,'output_tokens':5,'usage':{}}
        with patch.object(provider,'_complete_request',return_value=response) as transport:
            with reuse_scope(self.store,self.run), provider_task('answer'):
                first=provider.complete_with_metrics('提示','问题及证据',stream=True)
            with reuse_scope(self.store,{**self.run,'id':'SECOND'}), provider_task('answer'),collect_usage() as usage:
                second=provider.complete_with_metrics('提示','问题及证据',stream=True)
            self.assertEqual(transport.call_count,1);self.assertEqual(usage,[])
            self.assertEqual(second['content'],first['content']);self.assertEqual(second['input_tokens'],0)
            with reuse_scope(self.store,self.run), provider_task('answer'):
                provider.complete_with_metrics('提示变化','问题及证据',stream=True)
            self.assertEqual(transport.call_count,2)

    def test_same_answer_and_final_judgment_ignores_candidate_score_noise(self):
        from unittest.mock import Mock
        from app.request_reuse import reuse_scope
        from app.ai_service import AiService
        provider=Mock(settings=type('S',(),{'model':'deepseek-flash'})())
        provider.judge.return_value={'verdict':'PASS','quality':{'correctness':4,'faithfulness':1,'completeness':1}}
        service=AiService(self.store,Mock(),provider,False)
        context={'contract_version':'测试规则', 'final_context':[{'chunk_id':'c1','content':'证据'}], 'retrieval_candidates':[{'score':1}]}
        with reuse_scope(self.store,self.run):first=service.judge('题','参考','答案','positive',context=context)
        context['retrieval_candidates'][0]['score']=.5
        with reuse_scope(self.store,{**self.run,'id':'SECOND'}):second=service.judge('题','参考','答案','positive',context=context)
        self.assertEqual(provider.judge.call_count,1);self.assertEqual(second['verdict'],first['verdict'])
        self.assertEqual(second['token_usage'],[])
        context['final_context'][0]['content']='证据改变'
        with reuse_scope(self.store,self.run):service.judge('题','参考','答案','positive',context=context)
        self.assertEqual(provider.judge.call_count,2)

    def test_judge_cache_binds_parent_and_matched_child_ids(self):
        from unittest.mock import Mock
        from app.request_reuse import reuse_scope
        from app.ai_service import AiService
        from app.evaluation_contract import quote_present
        provider = Mock(settings=type('S', (), {'model':'deepseek-flash'})())
        provider.judge.side_effect = [
            {'verdict':'PASS', 'quality':{'correctness':4,'faithfulness':1,'completeness':1},
             'support':[{'source_id':'child54','quote':'权限操作'}]},
            {'verdict':'PASS', 'quality':{'correctness':4,'faithfulness':1,'completeness':1},
             'support':[{'source_id':'parent11','quote':'权限操作'}]},
        ]
        service = AiService(self.store, None, provider, False)
        final = [{'chunk_id':'child53', 'parent_chunk_id':'parent11',
                  'matched_child_ids':['child53','child54'], 'content':'权限操作'}]
        with reuse_scope(self.store, self.run):
            first = service.judge('题','参考','回答','positive',context={'final_context':final})
        self.assertTrue(quote_present(first['support'][0], final))
        changed = deepcopy(final)
        changed[0]['matched_child_ids'] = ['child53']
        with reuse_scope(self.store, {**self.run,'id':'C'}):
            result = service.judge('题','参考','回答','positive',context={'final_context':changed})
            repeated = service.judge('题','参考','回答','positive',context={'final_context':changed})
        self.assertEqual(provider.judge.call_count, 2)
        self.assertTrue(quote_present(result['support'][0], changed))
        self.assertEqual(repeated['reused_from']['run_id'], 'C')

    def test_chain_passes_full_rounds_and_paid_binding_without_publishing(self):
        from identity_fixture import completed_baseline
        from unittest.mock import patch
        from app.baseline_chain import arm_chain,advance_chain,chain_status
        from app.paid_schedule import set_unattended_authorization
        completed_baseline(self.store,run_id='BASE')
        set_unattended_authorization(self.store,True,'用户')
        with self.store.connection() as db:
            db.execute("UPDATE evaluation_runs SET result_json=? WHERE id='BASE'",(json.dumps({'evaluation_complete':True,'technical_failed':0,'gates':{'passed':False}}),))
        policy={'mode':'full_rounds','max_rounds':3}
        binding={'ledger_path':'local','ledger_identity':'fixed'}
        arm_chain(self.store,'BASE',round_policy=policy,paid_run=binding,causal_evidence=True)
        with patch('app.baseline_chain.threading.Thread') as thread:
            advance_chain(self.store,None);advance_chain(self.store,None)
            self.assertEqual(thread.call_count,1)
        experiment=self.store.experiment(chain_status(self.store)['experiment_id'])
        self.assertEqual(experiment['result']['round_policy'],policy)
        self.assertEqual(experiment['result']['paid_run'],binding)
        self.assertTrue(experiment['result']['causal_evidence'])
        self.assertEqual(experiment['result']['strategy_contract'],'agent-strategy-4')
        with self.store.connection() as db:self.assertEqual(db.execute("select count(*) from approvals where gate='human_release'").fetchone()[0],0)

    def test_whole_configuration_reuses_cases_without_a_provider(self):
        from identity_fixture import completed_baseline
        from app.request_reuse import matching_configuration,reused_case
        completed_baseline(self.store,run_id='BASE')
        baseline=self.store.evaluation_run('BASE')
        target={**baseline,'id':'NEXT','config':{**baseline['config'],'candidate_id':'C','run_target':'sandbox_candidate'}}
        with self.store.connection() as db:
            db.execute("UPDATE evaluation_runs SET result_json=? WHERE id='BASE'",(json.dumps({'evaluation_complete':True,'technical_failed':0,'gates':{'passed':False}}),))
        found=matching_configuration(self.store,target)
        self.assertTrue(found)
        case=reused_case(next(iter(found.values())))
        self.assertEqual(case['reused_from']['run_id'],'BASE')
        self.assertEqual(case['programmatic_metrics']['judge_usage'],[])
        target['config']['top_k']=99
        self.assertEqual(matching_configuration(self.store,target),{})


class BudgetTests(unittest.TestCase):
    def test_explicit_no_cap_keeps_accounting_and_unknown_history_after_reload(self):
        from app.paid_run import PaidRun, controlled_run, accounting_only, paid_request, payment_usage
        from app.paid_schedule import set_settings
        from datetime import datetime, timezone
        with tempfile.TemporaryDirectory() as directory:
            store = GovernanceStore(Path(directory)/'test.db')
            set_settings(store, False)
            policy = {'kind':'scheduled_usd_cap_v1', 'ledger_directory':directory,
                      'database_path':str(store.database_path), 'budget_usd':None}
            path = Path(directory)/'run.ledger.json'
            ledger = PaidRun(path, identity='same', identity_check=lambda:'same', request_policy=policy)
            ledger.calls.append({'provider':'DeepSeek', 'model':'deepseek-flash', 'status':'unknown',
                                 'reservation_usd':100, 'task':'judge'})
            ledger.save()
            ledger = PaidRun.load_accounting(path, lambda:'same')
            with controlled_run(ledger), accounting_only():
                with paid_request('DeepSeek', 'deepseek-flash', {'messages':[], 'max_tokens':10}):
                    payment_usage({'provider':'DeepSeek', 'requested_model':'deepseek-flash', 'status':'ok',
                                   'prompt_tokens':10, 'completion_tokens':1, 'prompt_cache_hit_tokens':0,
                                   'prompt_cache_miss_tokens':10, 'call_started_at':datetime.now(timezone.utc).isoformat()})
            saved = json.loads(path.read_text())
            self.assertEqual([c['status'] for c in saved['calls']], ['unknown','ok'])
            self.assertFalse(saved['budget_enforcement'])
            self.assertIsNone(saved['request_policy']['budget_usd'])

    def test_peak_disabled_schedule_keeps_setting_and_enforces_shared_cap(self):
        from app.paid_run import PaidRun,controlled_run,accounting_only,paid_request,payment_usage
        from app.paid_schedule import set_settings,schedule_status
        from datetime import datetime,timezone
        with tempfile.TemporaryDirectory() as directory:
            store=GovernanceStore(Path(directory)/'test.db')
            set_settings(store,False)
            policy={'kind':'scheduled_usd_cap_v1','ledger_directory':directory,'database_path':str(store.database_path),'budget_usd':.001}
            ledger=PaidRun(Path(directory)/'run.ledger.json',identity='same',identity_check=lambda:'same',output_limits={'answer':10},request_policy=policy)
            with controlled_run(ledger),accounting_only():
                with paid_request('DeepSeek','deepseek-flash',{'messages':[],'max_tokens':10}):
                    payment_usage({'provider':'DeepSeek','requested_model':'deepseek-flash','status':'ok','prompt_tokens':10,'completion_tokens':1,'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':10,'call_started_at':datetime.now(timezone.utc).isoformat()})
                with self.assertRaisesRegex(RuntimeError,'USD limit'):
                    with paid_request('DeepSeek','deepseek-flash',{'messages':['x'*10000],'max_tokens':1000000}):pass
            self.assertFalse(schedule_status(store)['off_peak_only'])


class BusinessOutputTests(unittest.TestCase):
    def test_machine_references_stay_valid_and_business_sentences_use_chinese(self):
        from app.agent_strategy import business_output, normalize_question_references
        payload={'predicted_fixed_question_ids':['Q01'],'why':'saved-01 应调整 top_k 与 prompt_strategy','config_diff':{'top_k':6}}
        mapping={'Q01':'saved-01'}
        normalized=normalize_question_references(payload,mapping)
        self.assertEqual(normalized['predicted_fixed_question_ids'],['saved-01'])
        displayed=business_output(normalized,mapping)
        self.assertEqual(displayed['why'],'Q01 应调整 上下文条数 与 回答策略')
        self.assertEqual(displayed['config_diff'],{'top_k':6})
        self.assertEqual(displayed['predicted_fixed_question_ids'],['saved-01'])


class AgentPathTests(unittest.TestCase):
    from test_optimization_contract import OptimizationContractTests
    setUp = OptimizationContractTests.setUp

    def test_first_round_receives_comparisons_and_saves_chinese_predictions(self):
        from app.optimization import OptimizationAgent
        from app.paid_schedule import set_settings
        from test_optimization_contract import drafts
        from agent_response_fixture import with_review
        store=self.store;set_settings(store,False)
        exp=store.create_experiment('EVAL-test')
        with store.connection() as db:
            db.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps({'strategy_contract':'agent-strategy-4','round_policy':{'mode':'full_rounds','max_rounds':3},'causal_evidence':True}),exp))
        class Provider:
            calls=0
            def complete(provider,system,user,**kwargs):
                provider.calls+=1;prompt=json.loads(user);provider.prompt=prompt
                result=with_review(drafts(),prompt)
                result['prior_round_review']['summary']='无'
                result['bad_case_summary']={'groups':prompt['bad_case_groups'],'focus':'检索遗漏','conclusions':[{'id':'B1','conclusion':'检索遗漏'}]}
                for number,c in enumerate(result['candidates']):
                    c['direction']=['扩大召回','改善排序','调整回答'][number]
                    c.update(adjustments=[{'parameter':k,'baseline_value':store.evaluation_run('EVAL-test')['config'][k],'candidate_value':v,'expected_impact':'预计修好Q1'} for k,v in c['config_diff'].items()],
                        risks=[{'question_ids':['Q1'],'reason':'可能增加耗时'}],bad_case_conclusion_ids=['B1'],predicted_fixed_question_ids=['Q1'])
                return json.dumps(result)
        provider=Provider()
        result=OptimizationAgent(store,provider).generate('EVAL-test',experiment_id=exp)
        self.assertEqual(provider.calls,1)
        self.assertIn('best_case_comparison',provider.prompt)
        self.assertEqual(len(result['candidates']),3)
        for c in result['candidates']:
            self.assertEqual(c['reasoning']['predicted_fixed_question_ids'],['Q1'])
            self.assertLessEqual(len(c['reasoning']['changed_parameters']),2)


class ConfigurationFlowTests(unittest.TestCase):
    from test_baseline_resume import ResumeTests
    setUp = ResumeTests.setUp
    tearDown = ResumeTests.tearDown

    def test_duplicate_configuration_runs_zero_more_answers_and_persists_provenance(self):
        self.runtime.fail=None
        baseline=self.runner.run_baseline(automatic=False)
        exp=self.store.create_experiment(baseline['id'])
        with self.store.connection() as db:
            state=json.loads(db.execute('select result_json from experiments where id=?',(exp,)).fetchone()[0])
            state['causal_evidence']=True
            db.execute('update experiments set result_json=? where id=?',(json.dumps(state),exp))
        config={k:v for k,v in baseline['config'].items() if k!='run_target'}
        self.store.save_candidate(exp,'R1-A',config,{'candidate_label':'A','round':1})
        before=list(self.runtime.answers)
        result=self.runner.run_candidate(exp+'-R1-A',automatic=False)
        self.assertEqual(result['status'],'evaluated')
        self.assertEqual(self.runtime.answers,before)
        cases=self.store.evaluation_case_results(result['result']['evaluation_run_id'])
        self.assertTrue(cases)
        self.assertTrue(all(c['reused_from']['run_id']==baseline['id'] for c in cases))
        self.assertTrue(all(c['programmatic_metrics']['judge_usage']==[] for c in cases))
