"""Candidate recovery uses Baseline checkpoints; all calls are offline stubs."""
import json,ssl,unittest
from copy import deepcopy
from unittest.mock import patch
import test_baseline_resume as baseline_fixture
from app.providers import ProviderTimeout

class CandidateResumeTests(unittest.TestCase):
    def setUp(self):
        baseline_fixture.ResumeTests.setUp(self)
        self.runtime.fail=None
        self.baseline=self.runner.execute_baseline(*self.runner.start_baseline())
        self.exp=self.store.create_experiment(self.baseline['id'],'completed')
        config={**self.baseline['config'],'top_k':6}
        config.pop('run_target',None)
        self.store.save_candidate(self.exp,'R1-A',config,{'round':1,'candidate_label':'A','observed_evidence':['Q2']})
        self.cid=self.exp+'-R1-A'
        self.runtime.answers=[];self.runtime.judges=[]
    def tearDown(self):baseline_fixture.ResumeTests.tearDown(self)
    def freeze_request_limits(self):
        from app.paid_run import REQUEST_LIMITS
        from app.evaluation_contract import evaluation_identity
        judge=deepcopy(self.baseline['judge'])
        judge['execution_snapshot']['request_limits']={k:REQUEST_LIMITS[k] for k in ('answer','judge','query')}
        judge['evaluation_identity']=evaluation_identity(json.loads(self.baseline['dataset_snapshot_json']),judge)
        with self.store.connection() as c:
            c.execute('UPDATE evaluation_runs SET judge_json=? WHERE id=?',(json.dumps(judge),self.baseline['id']))
        return self.store.evaluation_run(self.baseline['id'])

    def test_abc_api_inherits_frozen_limits_and_keeps_optimization_parameters(self):
        import time
        from fastapi.testclient import TestClient
        from api_fixture import main
        from app.paid_run import current_request_limit,provider_task
        baseline=self.freeze_request_limits();limits=baseline['judge']['execution_snapshot']['request_limits']
        configs=[self.store.candidate(self.cid)['config'],{**self.store.candidate(self.cid)['config'],'query_rewrite':True},
                 {**self.store.candidate(self.cid)['config'],'metadata_filter':'FALLBACK'}]
        for label,config in zip('ABC',configs):
            if label!='A':self.store.save_candidate(self.exp,'R1-'+label,config,{'round':1,'candidate_label':label})
        observed=[]
        answer,judge=self.runtime.answer,self.runtime.judge
        def check_answer(*args,**kwargs):
            for task in ('answer','query'):
                with provider_task(task):observed.append((task,current_request_limit()))
            return answer(*args,**kwargs)
        def check_judge(*args,**kwargs):
            with provider_task('judge'):observed.append(('judge',current_request_limit()))
            return judge(*args,**kwargs)
        with patch.object(main,'store',self.store),patch.object(main,'ai_service',self.runtime), \
             patch.object(self.runtime,'answer',side_effect=check_answer),patch.object(self.runtime,'judge',side_effect=check_judge):
            with TestClient(main.app) as client:
                for label,config in zip('ABC',configs):
                    cid=self.exp+'-R1-'+label
                    response=client.post('/api/candidates/'+cid+'/run',headers={'Origin':'http://127.0.0.1:5174'})
                    self.assertEqual(response.status_code,201,response.text)
                    for _ in range(100):
                        candidate=self.store.candidate(cid)
                        if candidate['status']!='running':break
                        time.sleep(.02)
                    self.assertEqual(candidate['status'],'evaluated')
                    self.assertEqual(candidate['config'],config)
                    run=self.store.evaluation_run(response.json()['id'])
                    self.assertEqual(run['judge'],baseline['judge'])
                    self.assertEqual(run['result']['completed'],4)
        self.assertTrue(observed)
        self.assertTrue(all(value==limits[task] for task,value in observed))
        self.assertEqual(self.store.evaluation_run(baseline['id']),baseline)
        with provider_task('answer'):self.assertIsNone(current_request_limit())

    def test_explicit_tampered_limits_are_rejected_before_reservation(self):
        from pathlib import Path
        from app.paid_run import PaidRun,controlled_run,REQUEST_LIMITS
        baseline=self.freeze_request_limits()
        for task in ('answer','judge','query'):
            limits={**REQUEST_LIMITS,task:REQUEST_LIMITS[task]+1}
            paid=PaidRun(Path(self.tmp.name)/(task+'.json'),10.,{}, {},output_limits=limits)
            with controlled_run(paid),self.assertRaisesRegex(ValueError,'request limits must match'):
                self.runner.start_candidate(self.cid)
            self.assertEqual(self.store.experiment(self.exp)['evaluation_budget']['used'],0)
            self.assertEqual(paid.calls,[])
        self.assertEqual(self.store.evaluation_run(baseline['id']),baseline)

    def test_tampered_baseline_identity_is_still_rejected(self):
        baseline=self.freeze_request_limits();judge=deepcopy(baseline['judge'])
        judge['execution_snapshot']['request_limits']['answer']+=1
        with self.store.connection() as c:
            c.execute('UPDATE evaluation_runs SET judge_json=? WHERE id=?',(json.dumps(judge),baseline['id']))
        with self.assertRaisesRegex(ValueError,'Evaluation身份不匹配'):
            self.runner.start_candidate(self.cid)
        self.assertEqual(self.store.experiment(self.exp)['evaluation_budget']['used'],0)

    def test_timeout_and_ssl_each_phase_resume_only_unfinished_work(self):
        for phase in ('generation','judge'):
            for error in (ProviderTimeout('offline timeout'),ssl.SSLEOFError('offline SSL EOF')):
                with self.subTest(phase=phase,error=type(error).__name__):
                    if self.store.candidate(self.cid)['status']!='generated':
                        self.store.save_candidate(self.exp,phase+type(error).__name__,self.store.candidate(self.cid)['config'],{'candidate_label':'A','observed_evidence':['Q2']})
                        self.cid=self.exp+'-'+phase+type(error).__name__
                    self.runtime.answers=[];self.runtime.judges=[]
                    original=getattr(self.runtime,'answer' if phase=='generation' else 'judge')
                    def fail(q,*args,**kwargs):
                        if q=='Q2':raise error
                        return original(q,*args,**kwargs)
                    with patch.object(self.runtime,'answer' if phase=='generation' else 'judge',side_effect=fail) as call:
                        first=self.runner.run_candidate(self.cid)
                        self.assertEqual(sum(args.args[0]=='Q2' for args in call.call_args_list),1)
                    self.assertEqual(first['status'],'failed');self.assertEqual(first['result']['completed'],1)
                    source=self.store.evaluation_run(first['result']['evaluation_run_id']);before=deepcopy(source)
                    self.assertEqual(source['result']['checkpoints']['Q2']['attempts'][-1]['error_type'],type(error).__name__)
                    self.assertFalse(any(b['run_id']==source['id'] for b in self.store.bad_case_rows()))
                    count=self.runtime.answers.count('Q2');budget=self.store.experiment(self.exp)['evaluation_budget']['used']
                    recovered=self.runner.run_candidate(self.cid)
                    self.assertEqual(recovered['status'],'evaluated');self.assertEqual(recovered['result']['completed'],4)
                    self.assertEqual(recovered['result']['resume_source_id'],source['id'])
                    self.assertEqual(self.runtime.answers.count('Q1'),1);self.assertEqual(self.runtime.judges.count('Q1'),1)
                    self.assertEqual(self.runtime.answers.count('Q2'),count+(phase=='generation'))
                    self.assertEqual(self.store.evaluation_run(source['id']),before)
                    self.assertEqual(self.store.experiment(self.exp)['evaluation_budget']['used'],budget+1)
    def test_restart_preserves_link_and_generated_answer(self):
        run,items,config,_,_=self.runner.start_candidate(self.cid)
        self.assertEqual(self.store.candidate(self.cid)['result']['evaluation_run_id'],run)
        execution=self.runtime.answer('Q1',config)
        self.store.update_evaluation_progress(run,{'checkpoints':{'Q1':{'execution':execution,'attempts':[],'inflight':'judge'}}})
        self.store.interrupt_evaluation_runs()
        result=self.runner.run_candidate(self.cid)
        self.assertEqual(result['status'],'evaluated');self.assertEqual(self.runtime.answers.count('Q1'),1)
        self.assertEqual(result['result']['resume_source_id'],run)
    def test_resume_identity_budget_and_duplicate_guards_are_atomic(self):
        self.runtime.fail='judge';first=self.runner.run_candidate(self.cid)
        source=first['result']['evaluation_run_id'];old=self.store.evaluation_run(source)
        for field in ('config_json','judge_json','dataset_snapshot_json'):
            with self.store.connection() as c:
                raw=c.execute('SELECT '+field+' FROM evaluation_runs WHERE id=?',(source,)).fetchone()[0]
                changed=json.loads(raw);changed['fixture_changed']=True
                c.execute('UPDATE evaluation_runs SET '+field+'=? WHERE id=?',(json.dumps(changed),source))
            before=self.store.experiment(self.exp)['evaluation_budget']['used']
            with self.assertRaises(ValueError):self.runner.start_candidate(self.cid)
            self.assertEqual(self.store.experiment(self.exp)['evaluation_budget']['used'],before)
            with self.store.connection() as c:c.execute('UPDATE evaluation_runs SET '+field+'=? WHERE id=?',(raw,source))
        with patch('app.governance.manifest_identity',return_value={'changed':True}):
            with self.assertRaises(ValueError):self.runner.start_candidate(self.cid)
        child,*_=self.runner.start_candidate(self.cid)
        with self.assertRaises(ValueError):self.runner.start_candidate(self.cid)
        self.store.interrupt_evaluation_runs()
        candidate=self.store.candidate(self.cid);reason=candidate['reasoning'];reason['sandbox_attempts']=[{}]*11
        with self.store.connection() as c:c.execute('UPDATE candidate_configs SET reasoning_json=? WHERE id=?',(json.dumps(reason),self.cid))
        with self.assertRaises(ValueError):self.runner.start_candidate(self.cid)
        self.assertEqual(self.store.evaluation_run(source),old)

    def test_legacy_failed_attempt_is_not_refunded(self):
        self.store.finish_candidate(self.cid,'failed',{'error':'legacy failure before Run creation'})
        self.assertEqual(self.store.experiment(self.exp)['evaluation_budget']['used'],1)
        self.runner.start_candidate(self.cid)
        self.assertEqual(self.store.experiment(self.exp)['evaluation_budget']['used'],2)
    def test_existing_candidate_api_resumes_after_explicit_request(self):
        import time
        from fastapi.testclient import TestClient
        from api_fixture import main
        self.runtime.fail='judge';first=self.runner.run_candidate(self.cid)
        self.runtime.fail=None
        with patch.object(main,'store',self.store),patch.object(main,'ai_service',self.runtime):
            with TestClient(main.app) as client:
                response=client.post('/api/candidates/'+self.cid+'/run',headers={'Origin':'http://127.0.0.1:5174'})
                self.assertEqual(response.status_code,201,response.text)
                for _ in range(100):
                    saved=self.store.candidate(self.cid)
                    if saved['status']!='running':break
                    time.sleep(.02)
                self.assertEqual(saved['status'],'evaluated')
                self.assertEqual(saved['result']['resume_source_id'],first['result']['evaluation_run_id'])
                self.assertEqual(self.runtime.answers.count('Q1'),1);self.assertEqual(self.runtime.answers.count('Q2'),1)
    def test_parser_failure_persists_cause_raw_response_and_usage(self):
        from app.providers import ProviderUnavailable
        from app.telemetry import record_usage
        raw='{"correctness": "invalid fixture"}'
        def invalid(q,*args,**kwargs):
            record_usage({'provider':'fixture','prompt_tokens':12,'completion_tokens':7,'total_tokens':19})
            error=ProviderUnavailable('DeepSeek Judge 未返回有效 JSON');error.raw_provider_response=raw
            raise error from ValueError('correctness must be an integer between 0 and 4')
        with patch.object(self.runtime,'judge',side_effect=invalid) as call:
            result=self.runner.run_candidate(self.cid)
        attempt=result['result']['checkpoints']['Q1']['attempts'][-1]
        self.assertEqual(attempt['raw_provider_response'],raw)
        self.assertEqual(attempt['cause_message'],'correctness must be an integer between 0 and 4')
        self.assertEqual(attempt['usage'][0]['total_tokens'],19)
        self.assertEqual(call.call_count,1);self.assertEqual(result['status'],'failed')
        self.assertFalse(result['result']['qualification']['qualified'])
        self.assertFalse(self.store.evaluation_case_results(result['result']['evaluation_run_id']))

    def test_saved_c_copy_resumes_43_cases_and_generation_without_touching_a_b(self):
        import shutil
        from pathlib import Path
        from app.governance import GovernanceStore
        from app.evaluation import EvaluationRunner
        from test_baseline_resume import Runtime
        backup=Path(__file__).resolve().parents[2]/'output/playwright/candidate-c-audit/protected.db'
        if not backup.exists():self.skipTest('Private real-record copy is not tracked')
        copied=Path(self.tmp.name)/'candidate-c-copy.db';shutil.copy2(backup,copied)
        store=GovernanceStore(copied);cid='EXP-20261012054110446321-R1-C'
        candidate=store.candidate(cid);source=store.evaluation_run(candidate['result']['evaluation_run_id'])
        snapshot=json.loads(source['dataset_snapshot_json'])
        a_b=[deepcopy(store.candidate(cid[:-1]+x)) for x in ('A','B')]
        source_before=deepcopy(source);rows_before=deepcopy(store.evaluation_case_results(source['id']))
        runtime=Runtime(None);runtime.model=source['judge']['model'];runner=EvaluationRunner(store,runtime)
        budget_before=store.experiment(candidate['experiment_id'])['evaluation_budget']['used']
        from app.evaluation_contract import policy_current
        if not policy_current(source['judge']):
            with self.assertRaisesRegex(ValueError,'评测规则已升级'):runner.start_candidate(cid)
            self.assertEqual(store.evaluation_run(source['id']),source_before)
            self.assertEqual(store.evaluation_case_results(source['id']),rows_before)
            self.assertEqual([store.candidate(cid[:-1]+x) for x in ('A','B')],a_b)
            self.assertEqual(store.experiment(candidate['experiment_id'])['evaluation_budget']['used'],budget_before)
            return
        started=runner.start_candidate(cid)
        self.assertEqual(len(store.evaluation_case_results(started[0])),43)
        judged=[];template=deepcopy(rows_before[0])
        def score(item,execution):
            judged.append(item['id']);case=deepcopy(template)
            case.update(question_id=item['id'],question=item['question'],test_category=item['test_category'],negative_subtype=item.get('negative_subtype'),answer=execution['answer'])
            return case
        with patch.object(runner,'score_execution',side_effect=score):result=runner.execute_candidate(*started)
        self.assertEqual(result['status'],'evaluated');self.assertEqual(result['result']['completed'],50)
        self.assertEqual(len(judged),7);self.assertEqual(len(runtime.answers),6)
        saved_generation=next(q for q,cp in source['result']['checkpoints'].items() if 'execution' in cp)
        self.assertEqual(judged[0],saved_generation)
        self.assertEqual(store.evaluation_run(source['id']),source_before)
        self.assertEqual(store.evaluation_case_results(source['id']),rows_before)
        self.assertEqual([store.candidate(cid[:-1]+x) for x in ('A','B')],a_b)
        self.assertEqual(store.experiment(candidate['experiment_id'])['evaluation_budget']['used'],budget_before+1)
