"""VNext contract fault injection; semantic judgments here are explicit test responses."""
import copy,json,unittest
from app import evaluation_contract as contract

class BinaryContractTests(unittest.TestCase):
    def setUp(self):
        self.entries=[{'chunk_id':'child','parent_chunk_id':'parent','matched_child_ids':['child','equivalent'],'document_id':'d','product':'robot','content':'操作前先关闭整机电源。按急停后，清洁和行驶立即停止。\ue258'}]
        self.answer='按急停后清洁和行驶会立刻停止。'
        self.judge={'verdict':'PASS','checks':[{'requirement':'急停效果','met':True,'answer_quotes':[self.answer],'support':[{'source_id':'equivalent','quote':'按急停后，**清洁和行驶立即停止**。'}]}],'issues':[],'reason':'同义完整且有适用Final支持'}
    def validate(self,value=None,answer=None,category='positive'):
        fn=getattr(contract,'validate_business_judgment',None)
        self.assertTrue(callable(fn),'VNext must have a shared business contract validator')
        return fn(value or self.judge,answer or self.answer,self.entries,category=category)
    def test_versioned_binary_contract_is_available(self):
        self.assertEqual(contract.VERSIONS['scoring_policy'],'business-vnext-1')
    def test_synonym_parent_alias_and_markdown_pass_without_golden_id(self):
        self.assertEqual(self.validate()['verdict'],'PASS')
    def test_numbers_negation_scope_and_noncontiguous_quotes_cannot_be_normalized_away(self):
        for q in ['行驶不会停止','按急停后清洁立即停止','清洁和行驶立即停止2']:
            v=copy.deepcopy(self.judge);v['checks'][0]['support'][0]['quote']=q
            with self.assertRaises(ValueError):self.validate(v)
    def test_missing_safety_is_fail_not_execution_error(self):
        v=copy.deepcopy(self.judge);v.update(verdict='FAIL',reason='漏必要断电');v['checks'][0].update(requirement='操作前关整机',met=False,answer_quotes=[],support=[])
        self.assertEqual(self.validate(v)['verdict'],'FAIL')
    def test_lucky_correct_answer_without_final_support_never_passes(self):
        v=copy.deepcopy(self.judge);v['checks'][0]['support']=[]
        with self.assertRaises(ValueError):self.validate(v)
    def test_negative_refusal_allows_no_support_but_danger_after_refusal_fails(self):
        a='资料不足，不能给出SOH阈值，请联系官方。';v=copy.deepcopy(self.judge);v['checks'][0].update(check_type='negative_behavior',requirement='资料不足时拒答并交官方确认',answer_quotes=[a],support=[])
        self.assertEqual(self.validate(v,a,'negative')['verdict'],'PASS')
        a='不能绕过扫描器。然后关闭扫描器继续清洁。';v.update(verdict='FAIL',issues=[{'description':'拒答后危险授权','answer_quotes':['关闭扫描器继续清洁'],'support':[],'critical':True}]);v['checks'][0]['answer_quotes']=['不能绕过扫描器']
        self.assertEqual(self.validate(v,a,'negative')['verdict'],'FAIL')
        v['verdict']='PASS'
        with self.assertRaises(ValueError):self.validate(v,a,'negative')
    def test_schema_missing_judgment_cannot_be_filled_by_parser(self):
        for key in ['verdict','checks','issues','reason']:
            v=copy.deepcopy(self.judge);v.pop(key)
            with self.assertRaises(ValueError):self.validate(v)
    def test_wrong_model_requires_explicit_business_fail_response(self):
        a='R3听到一声即可开机';v=copy.deepcopy(self.judge);v.update(verdict='FAIL',issues=[{'description':'R1条件错误套用R3','answer_quotes':[a],'support':[],'critical':False}]);v['checks'][0].update(met=False,answer_quotes=[a],support=[])
        self.assertEqual(self.validate(v,a)['verdict'],'FAIL')
    def test_unknown_interface_instruction_and_cold_start_scope_are_material_failures(self):
        for a,reason in [('介质未知，直接连接气管并进水','含义不清却直接执行'),('急停复位后按启动键等待登录','把冷启动套入急停复位'),('所有路线必须在对接站起终','多路线条件泛化'),('不明液体可直接擦电池','普通表面流程套用污染电池')]:
            v=copy.deepcopy(self.judge);v.update(verdict='FAIL',issues=[{'description':reason,'answer_quotes':[a],'support':[],'critical':False}]);v['checks'][0].update(met=False,answer_quotes=[a],support=[])
            self.assertEqual(self.validate(v,a)['verdict'],'FAIL')
    def test_display_only_symbols_allow_literal_location(self):
        self.assertEqual(contract.normalize('**嘀\\~**\ue258'),contract.normalize('嘀~'))

if __name__=='__main__':unittest.main()

class VNextStageTests(unittest.TestCase):
    def case(self,stage='candidate'):
        text='维护前关闭整机并断开电池';source={'chunk_id':'safe','parent_chunk_id':'p','document_id':'d','product':'robot','content':text}
        other={'chunk_id':'other','parent_chunk_id':'po','document_id':'d','product':'robot','content':'取出滤网冲洗'}
        final=[source] if stage=='final' else [other]
        check={'requirement':'维护前关机隔离','met':False,'answer_quotes':[],'support':[{'source_id':'safe','quote':text}] if stage=='final' else [],'reference_support':[{'source_id':'safe','quote':text}],'candidate_support':[{'source_id':'safe','quote':text}] if stage in {'candidate','final'} else [],'scope_resolved':True}
        judge={'verdict':'FAIL','checks':[check],'issues':[],'reason':'漏必要安全前提'}
        case={'test_category':'positive','model_answer':'取出滤网冲洗','judge_result':judge,'evaluation_outcome':{'contract_version':'business-vnext-1','execution_complete':True,'verdict':'FAIL'},'programmatic_metrics':{'retrieval_trace':{'status':'completed','corpus_fingerprint':'fixture-corpus','candidates':[source,other] if stage!='missing' else [other],'reranked':[source,other],'final':final,'parent_expand':False}}}
        chunks=[{**e,'chunk_text':e['content']} for e in [source,other]]
        return case,chunks
    def test_same_business_defect_is_classified_by_actual_stage(self):
        from app.diagnostics import automatic_analysis
        for stage,root,detail in [('candidate','Ranking','ranking_context_selection'),('missing','Retrieval','candidate_recall'),('final','Generation',None)]:
            c,chunks=self.case(stage);r=automatic_analysis(c,corpus_chunks=chunks,corpus_fingerprint='fixture-corpus')
            self.assertEqual((r['primary_root_cause'],r['retrieval_failure_stage']),(root,detail));self.assertTrue(r['target_eligible'])
    def test_scope_unresolved_pass_execution_error_and_forged_corpus_not_targets(self):
        from app.diagnostics import automatic_analysis
        for change in ['scope','pass','execution','corpus']:
            c,chunks=self.case()
            if change=='scope':c['judge_result']['checks'][0]['scope_resolved']=False
            if change=='pass':c['evaluation_outcome']['verdict']='PASS'
            if change=='execution':c['evaluation_outcome']['execution_complete']=False
            if change=='corpus':chunks[0]['chunk_text']='其他内容'
            self.assertFalse(automatic_analysis(c,corpus_chunks=chunks,corpus_fingerprint='fixture-corpus')['target_eligible'])
    def test_partial_comparison_and_new_critical_issue_in_continued_fail_block(self):
        def result(v,issues=[]):return {'evaluation_outcome':{'contract_version':'business-vnext-1','execution_complete':True,'verdict':v},'judge_result':{'issues':issues}}
        baseline={'a':result('FAIL'),'b':result('PASS')};candidate={'a':result('FAIL',[{'description':'新增带电拆装','critical':True,'baseline_issue_index':None}]),'b':result('PASS')}
        r=contract.compare_cases(baseline,candidate,[])
        self.assertEqual(r.get('new_regressions'),0);self.assertEqual(r.get('continued_failure_new_critical_question_ids'),['a'])
        self.assertTrue(r.get('comparison_complete'));self.assertFalse(contract.compare_cases(baseline,{'a':candidate['a']},[])['comparison_complete'])

class RunnerBinaryTests(BinaryContractTests):
    def test_runner_consumes_only_business_result_not_legacy_failure_tags(self):
        from app.evaluation import EvaluationRunner
        v=copy.deepcopy(self.judge);v['quality']={'correctness':4,'faithfulness':1,'completeness':1}
        runtime=type('Runtime',(),{'judge':lambda _,*a,**kw:v})()
        item={'question':'如何急停','reference_answer':'急停停止清洁和行驶','test_category':'positive','raw':{},'evidence':[]}
        result=EvaluationRunner(None,runtime).score_execution(item,{'answer':self.answer,'retrieval':self.entries,'retrieval_trace':{'final':self.entries,'candidates':self.entries,'status':'completed'},'latency_ms':1})
        self.assertEqual(result['evaluation_outcome'].get('verdict'),'PASS');self.assertTrue(result['passed']);self.assertEqual(result['failure_tags'],[])

class ProviderBinaryTests(BinaryContractTests):
    def test_provider_uses_new_schema_and_preserves_raw_response(self):
        from app.providers import DeepSeekProvider
        from app.config import Settings
        from unittest.mock import patch
        v={**self.judge,'quality':{'correctness':4,'faithfulness':1,'completeness':1}}
        provider=DeepSeekProvider(Settings('fixture','https://invalid','fixture'))
        with patch.object(provider,'complete',return_value=json.dumps(v)) as call:
            r=provider.judge('q','expected',self.answer,context={'contract_version':'business-vnext-1','category':'positive','final_context':self.entries})
        self.assertEqual(r['verdict'],'PASS');self.assertEqual(json.loads(r['raw_provider_response']),v)
        self.assertNotIn('七类Claim强制',call.call_args.args[0]);self.assertEqual(call.call_args.kwargs['temperature'],0)

class BoundedRecoveryTests(unittest.TestCase):
    def test_network_stops_after_three_attempts_and_keeps_generation(self):
        import test_baseline_resume as fixture
        from app.evaluation import EvaluationRunner
        from app.providers import ProviderTimeout
        from unittest.mock import patch
        holder=fixture.ResumeTests();holder.setUp()
        try:
            runtime=fixture.Runtime(fail=None);runner=EvaluationRunner(holder.store,runtime)
            def judge(*a,**kw):
                runtime.judges.append(a[0])
                if len(runtime.judges)>6:raise AssertionError('unbounded retry detected by test sentinel')
                raise ProviderTimeout('offline timeout')
            runtime.judge=judge;key,items,config=runner.start_baseline(automatic=True)
            with patch('app.evaluation.time.sleep'):r=runner.execute_baseline(key,items,config)
            self.assertEqual(len(runtime.judges),6);self.assertEqual(runtime.answers,['Q1','Q2']);self.assertEqual(r['status'],'partial');self.assertEqual(holder.store.evaluation_case_results(key),[])
            self.assertIn('execution',r['result']['checkpoints']['Q1'])
        finally:holder.tearDown()

class SourceScopeTests(unittest.TestCase):
    def test_existing_heading_sources_explain_ranges_without_rewriting_chunks(self):
        from app import ai_service
        chunks=[{'chunk_id':'h1','document_id':'d','page_start':2,'chunk_text':'R3遥控器'}, {'chunk_id':'h2','document_id':'d','page_start':9,'chunk_text':'R1遥控器'}]
        entries=[{'chunk_id':'c1','document_id':'d','parent_page_start':4,'parent_page_end':4,'content':'两声'}, {'chunk_id':'c2','document_id':'d','page_start':10,'page_end':10,'content':'一声'}]
        original=copy.deepcopy(entries)
        fn=getattr(ai_service,'attach_heading_scopes',None);self.assertTrue(callable(fn))
        scoped=fn(entries,chunks)
        self.assertEqual([e['source_scope']['heading'] for e in scoped],['R3遥控器','R1遥控器']);self.assertEqual(entries,original)
        self.assertIn('R3遥控器',ai_service.generation_context(scoped))

class PersistenceAndDeadlineTests(unittest.TestCase):
    def test_request_timeout_respects_remaining_stage_time(self):
        from app.providers import request_timeout,stage_deadline,ProviderTimeout
        from unittest.mock import patch
        with patch('app.providers.time.monotonic',return_value=100):
            with stage_deadline(110):self.assertEqual(request_timeout(240),10)
            with stage_deadline(99):
                with self.assertRaises(ProviderTimeout):request_timeout(240)
    def test_duplicate_case_is_idempotent_and_conflicting_rewrite_rejected(self):
        import tempfile
        from pathlib import Path
        from app.governance import GovernanceStore
        with tempfile.TemporaryDirectory() as d:
            store=GovernanceStore(Path(d)/'isolated.db');case={'passed':True,'question':'unchanged'}
            store.record_evaluation_case('fixture','x',case);store.record_evaluation_case('fixture','x',case)
            self.assertEqual(len(store.evaluation_case_results('fixture')),1)
            with self.assertRaises(ValueError):store.record_evaluation_case('fixture','x',{**case,'question':'changed'})

class AgentAndRiskTests(VNextStageTests):
    def test_agent_admits_only_proven_context_selection_direction(self):
        from app.optimization import validate_intervention
        from unittest.mock import patch
        c,chunks=self.case('candidate')
        # A scored saved pool must actually need TopK=6 to recover the norm.
        trace=c['programmatic_metrics']['retrieval_trace']
        noise=[{**chunks[1],'chunk_id':f'noise-{i}','parent_chunk_id':f'np-{i}'} for i in range(3)]
        chunks.extend(noise)
        trace['candidates']=trace['reranked']=[chunks[1],*noise,chunks[0]]
        for entry in trace['candidates']:entry['score']=.5
        proposal={'intervention_direction':'context_selection','config_diff':{'top_k':6},'root_cause':'Ranking','target_bad_cases':['case'],'evidence_assertions':[{'target_id':'case','observation':'ranking_omission'}],'parameter_dependencies':[],'hypothesis':'必要前提被截断','why':'候选有据而Final缺失','expected_improvement':'补入必要上下文','risk':'可能引入噪声'}
        with patch('app.diagnostics._current_corpus',return_value=(chunks,'fixture-corpus')):
            validate_intervention(proposal,{'case':c},{'top_k':4})
            with self.assertRaises(ValueError):validate_intervention({**proposal,'intervention_direction':'candidate_recall','config_diff':{'candidate_k':24}}, {'case':c},{'candidate_k':12})
            c['evaluation_outcome']['execution_complete']=False
            with self.assertRaises(ValueError):validate_intervention(proposal,{'case':c},{'top_k':4})
    def test_existing_critical_risk_paraphrase_not_a_new_regression(self):
        def c(issues):return {'evaluation_outcome':{'contract_version':'business-vnext-1','execution_complete':True,'verdict':'FAIL'},'judge_result':{'issues':issues}}
        old=[{'description':'未断电换件','critical':True}]
        new=[{'description':'带电更换零件','critical':True,'baseline_issue_index':0,'baseline_match_reason':'同一遗漏，未新增风险'}]
        r=contract.compare_cases({'same':c(old)},{'same':c(new)},[])
        self.assertEqual(r['continued_failure_new_critical_question_ids'],[])
        new[0]['critical']=True;old[0]['critical']=False
        self.assertEqual(contract.compare_cases({'same':c(old)},{'same':c(new)},[])['continued_failure_new_critical_question_ids'],['same'])
    def test_stage_elapsed_budget_and_unknown_usage_stop_without_bad_cases(self):
        import test_baseline_resume as fixture
        from app.evaluation import EvaluationRunner
        from app.providers import ProviderTimeout
        from app.telemetry import record_usage
        from unittest.mock import patch
        for mode in ['elapsed','unknown']:
            holder=fixture.ResumeTests();holder.setUp()
            try:
                runtime=fixture.Runtime(fail=None);runner=EvaluationRunner(holder.store,runtime);key,items,config=runner.start_baseline(automatic=True)
                if mode=='unknown':
                    def judge(*a,**kw):
                        runtime.judges.append(a[0]);record_usage({'provider':'DeepSeek','status':'unknown','request_sha256':'fixture'})
                        raise ProviderTimeout('unknown paid execution')
                    runtime.judge=judge
                    result=runner.execute_baseline(key,items,config)
                    self.assertEqual(len(runtime.judges),1)
                else:
                    from time import time
                    progress=holder.store.evaluation_run(key)['result'];progress['checkpoints']={'Q1':{'attempts':[],'phase_windows':{'generation':{'run_id':key,'started_at':time()-601}}}}
                    holder.store.update_evaluation_progress(key,progress);result=runner.execute_baseline(key,items,config)
                    self.assertEqual(runtime.answers,[])
                self.assertIn(result['status'],['failed','partial']);self.assertEqual(holder.store.evaluation_case_results(key),[])
                self.assertFalse(holder.store.bad_case_rows())
            finally:holder.tearDown()

class DisplayIntegrityTests(unittest.TestCase):
    def test_partial_bold_and_technical_angle_identifiers(self):
        self.assertEqual(contract.normalize_display('**清洁和行驶立即停止'),contract.normalize_display('清洁和行驶立即停止'))
        self.assertNotEqual(contract.normalize('<R3>两声'),contract.normalize('<R1>两声'))
        self.assertNotEqual(contract.normalize('2**3'),contract.normalize('23'))

class PerformanceAndWriteBoundaryTests(VNextStageTests):
    def test_performance_requires_completed_business_failure_and_real_stage_measurement(self):
        from app.diagnostics import automatic_analysis
        c,chunks=self.case('missing');c['judge_result']['checks'][0]['scope_resolved']=False
        c['programmatic_metrics'].update(latency_ms=61000,stages=[{'stage_name':'generation','duration_ms':60500,'parent':None}])
        self.assertEqual(automatic_analysis(c,corpus_chunks=chunks,corpus_fingerprint='fixture-corpus')['primary_root_cause'],'Performance')
        c['evaluation_outcome']['execution_complete']=False
        self.assertFalse(automatic_analysis(c,corpus_chunks=chunks,corpus_fingerprint='fixture-corpus')['target_eligible'])

class AlibabaDeadlineTests(unittest.TestCase):
    def test_embedding_rerank_transport_shares_stage_deadline(self):
        from app.knowledge_pipeline import AlibabaProvider
        from app.providers import stage_deadline
        from unittest.mock import patch
        from test_live_services import FakeResponse
        provider=AlibabaProvider({'DASHSCOPE_API_KEY':'fixture','DASHSCOPE_BASE_URL':'https://invalid'})
        with patch('app.providers.time.monotonic',return_value=100),stage_deadline(107),patch('app.knowledge_pipeline.urllib.request.urlopen',return_value=FakeResponse({'usage':{'total_tokens':1}})) as call:
            provider._post_request('/fixture',{'model':'offline'})
        self.assertEqual(call.call_args.kwargs['timeout'],7)

class RevisionSourceTests(unittest.TestCase):
    def test_new_revision_uses_validated_sources_without_rewriting_original(self):
        import test_revision_workflow as fixture
        holder=fixture.RevisionWorkflowTests();holder.setUp()
        try:
            key=holder.ids[0];before=holder.store.question(key)
            revision=holder.store.start_revision(key,'manual_edit','同步新证据',False,{key:{'question':'启动前如何检查急停？','reference_answer':'启动前检查急停按钮','source_chunk_ids':['C2']}},holder.chunks)
            preview=holder.store.prepare_revision(revision['id'],holder.chunks,similarity=lambda *_:.1)
            draft=preview['drafts'][key]['raw']
            self.assertEqual(draft.get('source_chunk_ids'),['C2']);self.assertEqual(draft.get('evidence_locations'),draft['validation']['evidence_locations'])
            self.assertEqual(holder.store.question(key),before)
            holder.store.apply_revision(revision['id'],holder.chunks,similarity=lambda *_:.1)
            self.assertEqual(holder.store.question(key)['raw']['source_chunk_ids'],['C2'])
        finally:holder.doCleanups()

class DiagnosticEvidenceBoundaryTests(VNextStageTests):
    def test_malformed_candidate_quote_is_not_proof_of_recall_failure(self):
        from app.diagnostics import automatic_analysis
        c,chunks=self.case('candidate');c['judge_result']['checks'][0]['candidate_support']=[{'source_id':'safe','quote':'并不存在的原文'}]
        self.assertFalse(automatic_analysis(c,corpus_chunks=chunks,corpus_fingerprint='fixture-corpus')['target_eligible'])
    def test_business_failure_cannot_show_a_passed_redline(self):
        from app.evaluation import EvaluationRunner
        c,_=self.case('final');v={**c['judge_result'],'quality':{'correctness':2,'faithfulness':.5,'completeness':.5}}
        runtime=type('Runtime',(),{'judge':lambda _,*a,**kw:v})()
        item={'question':'维护前安全条件','reference_answer':'维护前关闭整机并断开电池','test_category':'positive','raw':{},'evidence':[]}
        result=EvaluationRunner(None,runtime).score_execution(item,{'answer':c['model_answer'],'retrieval':c['programmatic_metrics']['retrieval_trace']['final'],'retrieval_trace':c['programmatic_metrics']['retrieval_trace'],'latency_ms':1})
        self.assertFalse(result['redline_pass'])
        self.assertIs(result['programmatic_metrics']['evidence_sufficiency']['sufficient'],True, 'Final can be sufficient even when generation omitted a required safety fact')

class ScopeCounterevidenceTests(unittest.TestCase):
    def test_wrong_product_counterevidence_preserves_fail_instead_of_execution_error(self):
        entry={'chunk_id':'other','document_id':'d','product':'other robot','content':'其他设备按此程序上电'}
        answer='按其他设备的程序上电'
        result={'verdict':'FAIL','reason':'错用其他产品操作','checks':[{'requirement':'本设备适用操作','met':False,'answer_quotes':[],'support':[]}],'issues':[{'description':'跨产品操作','critical':False,'answer_quotes':[answer],'support':[{'source_id':'other','quote':entry['content']}]}]}
        self.assertEqual(contract.validate_business_judgment(result,answer,[entry],category='positive',constraints={'product':'robot'})['verdict'],'FAIL')
    def test_negative_scope_refusal_can_cite_the_excluded_product(self):
        answer='这是其他设备的资料，不能用于本机。'
        entry={'chunk_id':'other','document_id':'d','product':'other robot','content':'其他设备说明'}
        result={'verdict':'PASS','reason':'正确资料边界','checks':[{'check_type':'negative_behavior','requirement':'拒绝错用资料','met':True,'answer_quotes':[answer],'support':[{'source_id':'other','quote':entry['content']}]}],'issues':[]}
        self.assertEqual(contract.validate_business_judgment(result,answer,[entry],category='negative',constraints={'product':'robot'})['verdict'],'PASS')

class RegressionCorrespondenceTests(unittest.TestCase):
    def test_missing_semantic_comparison_does_not_manufacture_new_critical_error(self):
        def case(issues):return {'evaluation_outcome':{'contract_version':'business-vnext-1','execution_complete':True,'verdict':'FAIL'},'judge_result':{'issues':issues}}
        r=contract.compare_cases({'x':case([{'description':'未断电','critical':True}])},{'x':case([{'description':'未隔离电源','critical':True}])},[])
        self.assertFalse(r['comparison_complete']);self.assertEqual(r['continued_failure_new_critical_question_ids'],[])

class SandboxCriticalityTests(unittest.TestCase):
    def test_new_critical_operation_blocks_even_on_an_ordinary_question(self):
        from app.evaluation import EvaluationRunner
        from unittest.mock import MagicMock
        def case(q,verdict,issues=[]):
            return {'question_id':q,'severity':'ordinary','passed':verdict=='PASS','evaluation_outcome':{'contract_version':'business-vnext-1','execution_complete':True,'verdict':verdict},'judge_result':{'issues':issues}}
        baseline=[case('a','FAIL'),case('b','FAIL'),case('c','PASS')]
        candidate=[case('a','PASS'),case('b','PASS'),case('c','FAIL',[{'description':'新带电拆装操作','critical':True,'baseline_issue_index':None}])]
        store=MagicMock();store.evaluation_case_results.side_effect=[baseline,candidate]
        store.finish_candidate.side_effect=lambda _,status,result:{'status':status,'result':result}
        runner=EvaluationRunner(store,None)
        runner.execute_baseline=MagicMock(return_value={'status':'completed','result':{'gates':{'passed':True},'bad_case_count':1},'judge':{'evaluation_identity':'fixture'}})
        result=runner.execute_candidate('new',[],{}, {'id':'candidate','experiment_id':'exp','reasoning':{'observed_evidence':['a']}},{'id':'baseline'})['result']
        self.assertEqual(result['regression']['new_critical_failures'],1)
        self.assertFalse(result['qualification']['qualified'])
