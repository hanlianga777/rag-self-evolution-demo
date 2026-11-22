"""031d: temporary database only; no paid calls or external network."""
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from app.governance import GovernanceStore
from app.optimization import build_agent_prompt, validate_round_contract
from app.policy import DEFAULT_PIPELINE_CONFIG
from identity_fixture import completed_baseline


class StrategyTests(unittest.TestCase):
    def rows(self):
        return [{'id':'A','direction':'检索召回增强','config_diff':{'candidate_k':24}},
                {'id':'B','direction':'检索召回增强','config_diff':{'query_rewrite':True}},
                {'id':'C','direction':'上下文预算','config_diff':{'retrieval_max_tokens':8192}}]

    def test_no_preset_directions_or_round_three_downgrade(self):
        rows=self.rows()
        validate_round_contract(rows,DEFAULT_PIPELINE_CONFIG,[],completed=0)
        _,p=build_agent_prompt([],DEFAULT_PIPELINE_CONFIG,[],[],list('ABC'),evaluation_budget={'used':6}, round_number=3)
        self.assertNotIn('downgrade_required', p['round_contract'])
        validate_round_contract(rows,DEFAULT_PIPELINE_CONFIG,[],completed=6)
        winner={'id':'old','status':'evaluated','config':DEFAULT_PIPELINE_CONFIG,'result':{'qualification':{'qualified':True}}}
        _,p=build_agent_prompt([],DEFAULT_PIPELINE_CONFIG,[winner],[],list('ABC'),evaluation_budget={'used':6}, round_number=3)
        self.assertNotIn('downgrade_required', p['round_contract'])
        validate_round_contract(self.rows(),DEFAULT_PIPELINE_CONFIG,[winner],completed=6)

    def test_disjoint_parameters_remain_required(self):
        rows=self.rows();rows[1]['config_diff']={'candidate_k':24}
        with self.assertRaisesRegex(ValueError,'共用'):
            validate_round_contract(rows,DEFAULT_PIPELINE_CONFIG,[])

    def test_strict_four_parts_reject_missing_or_false_summary(self):
        from app.agent_strategy import validate_strategy, validate_round_conclusion
        audit={'bad_case_groups':[{'layer':'检索层问题','subtype':'召回遗漏','question_ids':['Q1'],'count':1}]}
        response={'prior_round_review':{'summary':'无'},'bad_case_summary':{'groups':audit['bad_case_groups'],'focus':'召回遗漏','conclusions':[{'id':'B1','conclusion':'一题召回遗漏'}]},
                  'candidates':[{'adjustments':[{'parameter':'top_k'}],'risks':[{'reason':'耗时'}],'review_conclusion_ids':['L1'],'bad_case_conclusion_ids':['B1'],'predicted_fixed_question_ids':['Q1']} for _ in 'ABC']}
        validate_strategy(response,[],audit,{'Q1'})
        for field in ('prior_round_review','bad_case_summary'):
            broken=deepcopy(response);broken.pop(field)
            with self.assertRaises(ValueError):validate_strategy(broken,[],audit,{'Q1'})
        broken=deepcopy(response);broken['bad_case_summary']['groups'][0]['count']=2
        with self.assertRaises(ValueError):validate_strategy(broken,[],audit,{'Q1'})
        c={'id':'A','status':'evaluated','reasoning':{'predicted_fixed_question_ids':['Q1']},'result':{'all_fixed_question_ids':['Q1'],'new_regression_question_ids':[]}}
        review={'plans':[{'candidate_id':'A','fixed_question_ids':['Q1'],'new_failure_question_ids':[], 'matched_question_ids':['Q1'],'prediction_match_count':1,'unmatched_reason':'全部符合预测','parameter_assessment':'top_k有效','evidence_reason':'保存Final命中','conclusion':'有效'}], 'lessons':['保留top_k']}
        validate_round_conclusion(review,[c])
        review['plans'][0]['matched_question_ids']=[]
        with self.assertRaises(ValueError):validate_round_conclusion(review,[c])


    def test_d_review_uses_change_targets_as_predictions_and_accepts_assessment_map(self):
        # 058：D 的预测写在 changes[].target_question_ids，复盘曾误读为"预测为空"；parameter_assessment 写成对象曾被整份退回。
        from app.agent_strategy import validate_round_conclusion, predicted_ids
        d={'id':'D','status':'evaluated','reasoning':{'candidate_label':'D','changes':[{'parameter':'multi_query','target_question_ids':['Q26','Q30']}]},
           'result':{'all_fixed_question_ids':['Q17','Q26'],'new_regression_question_ids':['Q13']}}
        self.assertEqual(predicted_ids(d),['Q26','Q30'])
        review={'plans':[{'candidate_id':'D','fixed_question_ids':['Q17','Q26'],'new_failure_question_ids':['Q13'],'matched_question_ids':['Q26'],'prediction_match_count':1,
                          'unmatched_reason':'Q30未修好','parameter_assessment':{'多问法检索':'不确定'},'evidence_reason':'保存位置','conclusion':'不确定'}],'lessons':['盯Q13']}
        validate_round_conclusion(review,[d])
        self.assertEqual(review['plans'][0]['parameter_assessment'],'不确定')
        mixed=deepcopy(review);mixed['plans'][0]['parameter_assessment']={'多问法检索':'有效','候选数':'不确定'}
        validate_round_conclusion(mixed,[d])
        self.assertEqual(mixed['plans'][0]['parameter_assessment'],'多问法检索：有效；候选数：不确定')
        review['plans'][0].update(matched_question_ids=[],prediction_match_count=0)
        with self.assertRaises(ValueError):validate_round_conclusion(review,[d])

    def test_winner_comparison_lists_only_d_own_changes(self):
        from types import SimpleNamespace
        from app.agent_strategy import winner_comparison
        cases={'r-d':[{'question_id':'Q13','passed':False},{'question_id':'Q17','passed':True},{'question_id':'Q27','passed':False}],
               'r-w':[{'question_id':'Q13','passed':True},{'question_id':'Q17','passed':False},{'question_id':'Q27','passed':False}]}
        store=SimpleNamespace(evaluation_case_results=lambda run:cases[run])
        d={'id':'D','reasoning':{'winner_config_diff':{'multi_query':2}},'result':{'evaluation_run_id':'r-d'}}
        w={'id':'W','reasoning':{},'result':{'evaluation_run_id':'r-w'}}
        self.assertEqual(winner_comparison(store,d,w),{'winner_id':'W','changed_parameters_vs_winner':{'multi_query':2},
                                                       'fixed_vs_winner':['Q17'],'new_failures_vs_winner':['Q13']})

class ChainTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=GovernanceStore(Path(self.tmp.name)/'test.db')
        completed_baseline(self.store,run_id='BASE')

    def test_completed_chain_designates_once_new_experiment_and_never_publishes(self):
        from app.baseline_chain import arm_chain, advance_chain, chain_status
        from app.paid_schedule import set_unattended_authorization
        set_unattended_authorization(self.store,True,'用户')
        arm_chain(self.store,'BASE')
        with self.store.connection() as db:
            db.execute("UPDATE evaluation_runs SET result_json=? WHERE id='BASE'",(json.dumps({'evaluation_complete':True,'technical_failed':0,'gates':{'passed':False}}),))
        with patch('app.baseline_chain.threading.Thread') as thread:
            advance_chain(self.store,SimpleNamespace())
            advance_chain(self.store,SimpleNamespace())
            self.assertEqual(thread.call_count,1)
        state=chain_status(self.store)
        self.assertTrue(state['designated'])
        self.assertEqual(state['status'],'agent_running')
        exp=self.store.experiment(state['experiment_id'])
        self.assertEqual(exp['baseline_run_id'],'BASE');self.assertEqual(exp['candidates'],[])
        self.assertEqual(exp['result']['strategy_contract'],'agent-strategy-4')
        self.assertEqual(self.store.current_baseline_identity()['current_baseline_id'],'BASE')
        with self.store.connection() as db:
            self.assertEqual(db.execute('select count(*) from experiments').fetchone()[0],1)
            self.assertEqual(db.execute("select count(*) from approvals where gate='human_release'").fetchone()[0],0)

    def test_partial_baseline_waits_and_never_starts_agent(self):
        from app.baseline_chain import arm_chain, advance_chain, chain_status
        arm_chain(self.store,'BASE')
        with self.store.connection() as db:db.execute("UPDATE evaluation_runs SET status='running' WHERE id='BASE'")
        with patch('app.baseline_chain.threading.Thread') as thread:
            advance_chain(self.store,SimpleNamespace())
            self.assertFalse(thread.called)
        self.assertEqual(chain_status(self.store)['status'],'waiting_baseline')

    def test_initial_version_preserves_old_config_and_clears_draft(self):
        from app.baseline_chain import restore_initial_config
        previous=self.store.active_production()
        with self.store.connection() as db:
            db.execute('update production_versions set config_json=? where id=?',(json.dumps({**DEFAULT_PIPELINE_CONFIG,'top_k':6}),previous['id']))
        restored=restore_initial_config(self.store)
        self.assertEqual(restored['config'],DEFAULT_PIPELINE_CONFIG)
        versions=self.store.production_versions()
        old=next(v for v in versions if v['id']==previous['id'])
        self.assertEqual(old['config']['top_k'],6);self.assertEqual(old['status'],'archived')


class ConclusionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=GovernanceStore(Path(self.tmp.name)/'test.db')
        completed_baseline(self.store,run_id='BASE')

    def test_conclusion_rejects_then_saves_once_and_reuses_after_restart(self):
        from app.agent_strategy import conclude_round
        from app.paid_schedule import set_settings
        set_settings(self.store,False)
        exp=self.store.create_experiment('BASE')
        with self.store.connection() as db:db.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps({'strategy_contract':'agent-strategy-3'}),exp))
        self.store.save_candidate(exp,'R1-A',DEFAULT_PIPELINE_CONFIG,{'round':1,'candidate_label':'A','predicted_fixed_question_ids':['Q1']})
        cid=exp+'-R1-A'
        self.store.finish_candidate(cid,'evaluated',{'all_fixed_question_ids':['Q1'],'new_regression_question_ids':[]})
        class Provider:
            calls=0
            def complete(provider,system,user,**kwargs):
                provider.calls+=1
                if provider.calls==1:return '{}'
                return json.dumps({'plans':[{'candidate_id':cid,'fixed_question_ids':['Q1'],'new_failure_question_ids':[], 'matched_question_ids':['Q1'],'prediction_match_count':1,'unmatched_reason':'全部符合','parameter_assessment':'待验证','evidence_reason':'保存Final位置','conclusion':'有效'}],'lessons':['检查Final']})
        provider=Provider();runtime=SimpleNamespace(provider=provider)
        saved=conclude_round(self.store,runtime,exp)
        self.assertEqual(saved['status'],'saved');self.assertEqual(provider.calls,2)
        self.assertIn('error',saved['attempts'][0])
        self.assertEqual(conclude_round(GovernanceStore(self.store.database_path,migrate=False),runtime,exp),saved)
        self.assertEqual(provider.calls,2)

    def test_q27_round_facts_survive_a_conflicting_explanation(self):
        from app.agent_strategy import conclude_round, round_conclusions_for_prompt
        from app.paid_schedule import set_settings
        set_settings(self.store,False)
        exp=self.store.create_experiment('BASE')
        qid='frozen-27'
        quote='安装前检查管套和弹簧环'
        snapshot=self.store.evaluation_run('BASE')['dataset_snapshot_json']
        snapshot=json.loads(snapshot)
        snapshot['questions']=[{'id':qid,'evidence':[{'chunk_id':'C-00257','quote':quote}]}]
        with self.store.connection() as db:
            db.execute('UPDATE experiments SET result_json=? WHERE id=?',(json.dumps(
                {'strategy_contract':'agent-strategy-4','causal_evidence':True}),exp))
            db.execute('UPDATE evaluation_runs SET dataset_snapshot_json=? WHERE id=?',(json.dumps(snapshot),'BASE'))
        self.store.record_evaluation_case('BASE',qid,{'passed':False,'display_question_id':'Q27',
            'programmatic_metrics':{'retrieval_trace':{'final':[]}}})
        self.store.save_candidate(exp,'R1-C',DEFAULT_PIPELINE_CONFIG,{'round':1,'candidate_label':'C','predicted_fixed_question_ids':[qid]})
        cid=exp+'-R1-C'
        run=self.store.create_evaluation_run(snapshot,DEFAULT_PIPELINE_CONFIG,{})
        self.store.record_evaluation_case(run,qid,{'passed':True,'programmatic_metrics':{'retrieval_trace':{
            'final':[{'chunk_id':'parent','content':quote}],
            'enhancement':{'new_final_hits':0,'by_method':{'query_decompose':{'new_final_hits':0}}}}}})
        self.store.finish_candidate(cid,'evaluated',{'evaluation_run_id':run,'all_fixed_question_ids':[qid]})
        response={'case_facts':{cid:[{'候选判对':False}]},
            'plans':[{'candidate_id':cid,'unmatched_reason':'预测吻合','parameter_assessment':'不确定',
                      'evidence_reason':'Q27标准证据C-00257最终仍为未进入','conclusion':'Q27 的修好与检索无关',
                      'case_reviews':[{'question':'Q27','reason':'标准引文未进入 Final',
                                      'attributed_parameter':'查询拆解','assessment':'不确定'}]}],
            'lessons':['Q27 在证据最终位置未变时被修好']}
        provider=MagicMock(complete=MagicMock(return_value=json.dumps(response)),settings=None)
        saved=conclude_round(self.store,SimpleNamespace(provider=provider),exp)
        stored=self.store.experiment(exp)['result']['round_conclusions']['1']
        self.assertEqual(stored,saved)
        [fact]=[row for row in stored['case_facts'][cid] if row['题号']=='Q27']
        self.assertIs(fact['基线判对'],False)
        self.assertIs(fact['候选判对'],True)
        self.assertEqual(fact['变化'],'修好')
        self.assertEqual(fact['候选标准证据位置'][0]['final'],'1（原文在同一父块内，按原文判定）')
        self.assertEqual(fact['候选增强新增命中']['by_method']['query_decompose']['new_final_hits'],0)
        plan=stored['review']['plans'][0]
        self.assertEqual(plan['fixed_question_ids'],[qid])
        self.assertEqual(plan['case_reviews'][0]['state'],'修好')
        self.assertEqual(plan['case_reviews'][0]['reason'],'解释与程序事实冲突')
        self.assertEqual(plan['conclusion'],'解释与程序事实冲突')
        self.assertEqual(stored['review']['lessons'],['解释与程序事实冲突'])
        self.assertEqual(json.loads(stored['attempts'][0]['raw']),response)
        legacy = {'1':{'status':'saved','review':deepcopy(response),'attempts':stored['attempts']}}
        projection = round_conclusions_for_prompt(self.store,self.store.evaluation_run('BASE'),
                                                  self.store.experiment(exp)['candidates'],legacy)['1']
        self.assertEqual(projection['case_facts'],stored['case_facts'])
        self.assertEqual(projection['review'],stored['review'])
        self.assertNotIn('attempts',projection)
        self.assertEqual(legacy['1']['review'],response)
        clean = {'plans':[deepcopy(response['plans'][0])],'lessons':['检查生成依据']}
        clean_plan = clean['plans'][0]
        clean_plan.update(evidence_reason='拆分查询新增 Final 命中为 0，标准引文已进入 Final',conclusion='归因待验证')
        clean_case = clean_plan['case_reviews'][0]
        clean_case.update(reason='拆分查询未新增 Final 命中，标准引文已进入 Final',
                          fact_claims={'候选判对':True,'候选增强新增命中':fact['候选增强新增命中']})
        legacy['1']['review'] = clean
        safe = round_conclusions_for_prompt(self.store,self.store.evaluation_run('BASE'),
                                            self.store.experiment(exp)['candidates'],legacy)['1']['review']
        self.assertEqual(safe['plans'][0]['case_reviews'][0]['reason'],clean_case['reason'])
        self.assertEqual(safe['lessons'],clean['lessons'])
        clean_case['fact_claims']['候选判对'] = False
        contradicted = round_conclusions_for_prompt(self.store,self.store.evaluation_run('BASE'),
                                                    self.store.experiment(exp)['candidates'],legacy)['1']['review']
        self.assertEqual(contradicted['plans'][0]['case_reviews'][0]['reason'],'解释与程序事实冲突')
        clean_case['fact_claims']['候选判对'] = True
        clean_case['reason'] = '拆分查询新增 Final 命中为 3'
        contradicted = round_conclusions_for_prompt(self.store,self.store.evaluation_run('BASE'),
                                                    self.store.experiment(exp)['candidates'],legacy)['1']['review']
        self.assertEqual(contradicted['plans'][0]['case_reviews'][0]['reason'],'解释与程序事实冲突')
        provider.complete.assert_called_once()

    def test_d_only_uses_two_authorized_modes_and_verified_changes(self):
        from app.agent_strategy import validate_d_mode
        winner={'id':'A','status':'evaluated','reasoning':{'candidate_label':'A'},'result':{'qualification':{'qualified':True}}}
        other={'id':'B','status':'evaluated','reasoning':{'candidate_label':'B'},'result':{'qualification':{'qualified':True}}}
        suggestion={'should_generate_d':True,'combination_mode':'partial_fusion','mode_reason':'两套已验证且不冲突','changes':[{'source_type':'partial','source_candidates':['B']}]}
        validate_d_mode(suggestion,winner,[winner,other])
        other['result']['qualification']['qualified']=False
        with self.assertRaises(ValueError):validate_d_mode(suggestion,winner,[winner,other])
        suggestion['combination_mode']='winner_plus_verified'
        validate_d_mode(suggestion,winner,[winner,other])
        self.assertEqual(suggestion['combination_mode'],'winner_plus')
        suggestion['changes'][0]['source_type']='new_attempt'
        validate_d_mode(suggestion,winner,[winner,other])
        with self.assertRaisesRegex(ValueError,'优先使用'):
            validate_d_mode(suggestion,winner,[winner,other],{'usable_repairs':[{'parameter':'top_k'}]})

    def test_saved_stage_shares_are_visible_to_agent(self):
        from app.optimization import performance_facts
        facts=performance_facts({},[{'question_id':'Q1','programmatic_metrics':{'latency_ms':100,'stages':[{'stage_name':'generation','duration_ms':80,'parent':None},{'stage_name':'nested','duration_ms':20,'parent':'generation'}]}}])
        self.assertEqual(facts['stage_shares'],[{'stage':'generation','duration_ms':80,'share_of_answer_latency':.8}])

    def test_budget_exhaustion_finishes_round_summary_and_skips_unrun_candidates(self):
        from app.optimization_cycle import run_until_qualified
        store=self.store;exp=store.create_experiment('BASE')
        for number in range(10):
            store.save_candidate(exp,'old-'+str(number),DEFAULT_PIPELINE_CONFIG,{'candidate_label':'A','round':1,'sandbox_attempts':[{'id':'fixture'}]})
            store.finish_candidate(exp+'-old-'+str(number),'evaluated',{'qualification':{'qualified':False}})
        for label in 'ABC':store.save_candidate(exp,'R2-'+label,DEFAULT_PIPELINE_CONFIG,{'candidate_label':label,'round':2})
        class Runner:
            def __init__(self,*args):pass
            def run_candidate(self,cid,**kwargs):
                store.reserve_candidate_evaluation(cid)
                return store.finish_candidate(cid,'evaluated',{'qualification':{'qualified':False}})
        with patch('app.optimization_cycle.EvaluationRunner',Runner),patch('app.agent_strategy.conclude_round') as conclude:
            state=run_until_qualified(store,SimpleNamespace(provider=object()),exp)
        self.assertEqual(state['status'],'budget_exhausted')
        self.assertTrue(conclude.called)
        self.assertTrue(store.experiment(exp)['rounds'][-1]['complete'])


class ChainApiTests(unittest.TestCase):
    setUp=ChainTests.setUp

    def test_explicit_chain_api_persists_authority_and_rejects_duplicate_start(self):
        from fastapi.testclient import TestClient
        from api_fixture import main
        client=TestClient(main.app)
        with patch.object(main,'store',self.store),patch.object(main.EvaluationRunner,'start_baseline',return_value=('BASE',[],DEFAULT_PIPELINE_CONFIG)),patch.object(main,'threading',SimpleNamespace(Thread=MagicMock())) as threads:
            settings=client.post('/api/runtime-settings',json={'off_peak_only':False,'audit_note':'用户 2026-11-14 确认关闭平价限制'})
            self.assertEqual(settings.status_code,200)
            auth=client.post('/api/runtime-settings/unattended',json={'enabled':True,'actor':'用户','audit_note':'用户 2026-11-14 授权'})
            self.assertEqual(auth.json()['audit_note'],'用户 2026-11-14 授权')
            denied=client.post('/api/evaluations/run',headers={'Origin':'https://untrusted.invalid'},json={'fresh':True,'unattended_chain':True})
            self.assertEqual(denied.status_code,403)
            start=client.post('/api/evaluations/run',json={'fresh':True,'unattended_chain':True})
            self.assertEqual(start.status_code,201,start.text)
            duplicate=client.post('/api/evaluations/run',json={'fresh':True,'unattended_chain':True})
            self.assertEqual(duplicate.status_code,409);self.assertEqual(threads.Thread.call_count,1)
            state=client.get('/api/runtime-settings').json()
            self.assertFalse(state['off_peak_only']);self.assertEqual(state['baseline_agent_chain']['baseline_id'],'BASE')
