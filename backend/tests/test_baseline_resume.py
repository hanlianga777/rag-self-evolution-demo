"""Isolated checkpoint/resume regression. All Provider calls are stubs."""
import json,tempfile,unittest
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from app.governance import GovernanceStore
from app.evaluation import EvaluationRunner
from app.providers import ProviderTimeout
from app.telemetry import record_usage,collect_usage
from identity_fixture import context_judgment

class Runtime:
    model='fixture'
    def __init__(self,fail='judge'):
        self.fail=fail;self.answers=[];self.judges=[]
    def answer(self,q,config):
        self.answers.append(q);record_usage({'provider':'fixture','prompt_tokens':10,'completion_tokens':20,'status':'ok'})
        if q=='Q2' and self.fail=='generation':raise ProviderTimeout('fixture generation timeout')
        final=[{'chunk_id':'c','parent_chunk_id':'p','content':'事实'}]
        return {'answer':'事实','retrieval':final,'retrieval_trace':{'final':final,'candidates':final},'latency_ms':1}
    def judge(self,q,expected,answer,category,context=None):
        self.judges.append(q)
        with collect_usage():record_usage({'provider':'fixture','prompt_tokens':30,'completion_tokens':40,'status':'ok'})
        if q=='Q2' and self.fail=='judge':raise ProviderTimeout('fixture judge timeout')
        return context_judgment({'correctness':4,'faithfulness':1,'completeness':1,'behavior_pass':True,'reason':'fixture','missing_points':[],'unsupported_claims':[]},context)

class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=GovernanceStore(Path(self.tmp.name)/'isolated.db')
        items=[{'id':f'Q{i}','question':f'Q{i}','reference_answer':'事实','test_category':cat,'negative_subtype':sub,'evidence':[]} for i,cat,sub in [(1,'positive',None),(2,'ablation',None),(3,'negative','safety_critical'),(4,'negative','prompt_injection')]]
        from app.corpus import current_manifest,manifest_identity
        snapshot={'questions':items,'question_ids':[i['id'] for i in items],'corpus_fingerprint':manifest_identity(current_manifest())}
        with self.store.connection() as c:c.execute('INSERT INTO dataset_versions VALUES (?,?,?,?,?)',('fixture-golden','approved','fixture',json.dumps(snapshot),'9999'))
        self.runtime=Runtime();self.runner=EvaluationRunner(self.store,self.runtime)
    def tearDown(self):self.tmp.cleanup()
    def run_once(self):
        run,items,config=self.runner.start_baseline();return self.runner.execute_baseline(run,items,config)
    def test_resume_uses_frozen_request_limits_without_new_paid_context(self):
        from app.paid_run import PaidRun,controlled_run,REQUEST_LIMITS
        paid=PaidRun(Path(self.tmp.name)/'paid.json',10.,{}, {},output_limits=REQUEST_LIMITS)
        with controlled_run(paid):old=self.run_once()
        run,items,config=self.runner.start_baseline(old['id'])
        self.assertEqual(self.store.evaluation_run(run)['judge'],old['judge'])
        self.assertEqual(self.store.evaluation_run(run)['judge']['evaluation_identity'],old['judge']['evaluation_identity'])

    def test_display_returns_partial_without_granting_current_baseline_eligibility(self):
        from unittest.mock import Mock
        from api_fixture import main
        store=Mock();store.current_baseline_identity.return_value={'current_baseline_id':None,'baseline_unavailable_reason':'not complete'}
        store.dataset_snapshots.return_value=[{'id':'fixture-golden'}]
        store.evaluation_runs.return_value=[{'id':'partial','status':'partial','dataset_version_id':'fixture-golden','config':{'run_target':'baseline'},'result':{'completed':8}}]
        with patch.object(main,'store',store):result=main.evaluation()
        self.assertEqual(result['id'],'partial');self.assertEqual(result['result']['completed'],8)
        self.assertIsNone(result['current_baseline_id'])

    def test_startup_keeps_a_live_worker_and_interrupts_dead_owner(self):
        import os
        old=self.run_once();self.runtime.fail=None
        key,items,config=self.runner.start_baseline(old['id'])
        with self.store.connection() as db:
            saved=json.loads(db.execute('SELECT result_json FROM evaluation_runs WHERE id=?',(key,)).fetchone()[0]);saved['execution_owner_pid']=os.getpid()
            db.execute('UPDATE evaluation_runs SET result_json=? WHERE id=?',(json.dumps(saved),key))
        self.store.interrupt_evaluation_runs()
        self.assertEqual(self.store.evaluation_run(key)['status'],'running')
        with patch('app.governance.os.kill',side_effect=ProcessLookupError):self.store.interrupt_evaluation_runs()
        self.assertEqual(self.store.evaluation_run(key)['status'],'failed')

    def test_resume_skips_completed_cases_and_saved_generation(self):
        old=self.run_once();self.assertEqual(old['status'],'partial');self.assertEqual(old['result']['completed'],1)
        checkpoint=old['result']['checkpoints']['Q2'];self.assertIn('execution',checkpoint);self.assertEqual(checkpoint['attempts'][-1]['phase'],'judge');self.assertEqual(len(checkpoint['attempts'][-1]['usage']),1)
        original=deepcopy(self.store.evaluation_run(old['id']));oldcases=deepcopy(self.store.evaluation_case_results(old['id']))
        self.runtime.fail=None
        run,items,config=self.runner.start_baseline(old['id']);result=self.runner.execute_baseline(run,items,config)
        self.assertEqual(result['status'],'completed');self.assertEqual(result['result']['completed'],4)
        self.assertEqual(self.runtime.answers.count('Q1'),1);self.assertEqual(self.runtime.answers.count('Q2'),1);self.assertEqual(self.runtime.judges.count('Q1'),1)
        self.assertEqual(self.store.evaluation_run(old['id']),original);self.assertEqual(self.store.evaluation_case_results(old['id']),oldcases)
        self.assertEqual(result['result']['resume_source_id'],old['id'])
    def test_generation_failure_is_not_bad_case_and_no_automatic_retry(self):
        self.runtime.fail='generation';old=self.run_once();self.assertEqual(self.runtime.answers,['Q1','Q2']);self.assertEqual(self.runtime.judges,['Q1'])
        self.assertEqual(old['result']['completed'],1);self.assertFalse(old['result']['evaluation_complete']);self.assertNotIn('execution',old['result']['checkpoints']['Q2'])
        self.assertFalse(any(b['run_id']==old['id'] for b in self.store.bad_case_rows()))
        self.assertEqual(old['result']['checkpoints']['Q2']['attempts'][-1]['error_type'],'ProviderTimeout')
    def test_identity_config_and_duplicate_guards(self):
        old=self.run_once()
        for field,value in [('model','different'),('prompt_version','old'),('evaluation_identity','wrong')]:
            judge=deepcopy(old['judge']);judge[field]=value
            with self.store.connection() as c:c.execute('UPDATE evaluation_runs SET judge_json=? WHERE id=?',(json.dumps(judge),old['id']))
            with self.assertRaises(ValueError):self.runner.start_baseline(old['id'])
        with self.store.connection() as c:c.execute('UPDATE evaluation_runs SET judge_json=? WHERE id=?',(json.dumps(old['judge']),old['id']))
        config=deepcopy(old['config']);config['top_k']=8
        with self.store.connection() as c:c.execute('UPDATE evaluation_runs SET config_json=? WHERE id=?',(json.dumps(config),old['id']))
        with self.assertRaises(ValueError):self.runner.start_baseline(old['id'])
        with self.store.connection() as c:c.execute('UPDATE evaluation_runs SET config_json=? WHERE id=?',(json.dumps(old['config']),old['id']))
        child,_,_=self.runner.start_baseline(old['id'])
        with self.assertRaises(ValueError):self.runner.start_baseline(old['id'])
        self.store.finish_evaluation_run(child,'failed',{'resume_source_id':old['id']},'fixture stopped')
        with self.assertRaises(ValueError):self.runner.start_baseline(old['id'])
    def test_restart_preserves_checkpoint(self):
        run,items,config=self.runner.start_baseline()
        self.store.update_evaluation_progress(run,{'checkpoints':{'Q1':{'execution':self.runtime.answer('Q1',config),'attempts':[],'inflight':'judge'}}})
        self.store.interrupt_evaluation_runs()
        child,items,config=self.runner.start_baseline(run);self.runtime.fail=None
        result=self.runner.execute_baseline(child,items,config);self.assertEqual(result['status'],'completed');self.assertEqual(self.runtime.answers.count('Q1'),1)

    def test_incomplete_items_cannot_complete_or_call_provider(self):
        run,items,config=self.runner.start_baseline()
        result=self.runner.execute_baseline(run,items[:1],config)
        self.assertEqual(result['status'],'failed');self.assertFalse(result['result']['evaluation_complete']);self.assertFalse(self.runtime.answers)
    def test_golden_change_blocks_resume(self):
        old=self.run_once()
        with self.store.connection() as c:
            snapshot=json.loads(c.execute("SELECT snapshot_json FROM dataset_versions WHERE id='fixture-golden'").fetchone()[0]);snapshot['questions'][0]['question']='changed'
            c.execute("UPDATE dataset_versions SET snapshot_json=? WHERE id='fixture-golden'",(json.dumps(snapshot),))
        with self.assertRaises(ValueError):self.runner.start_baseline(old['id'])
    def test_timeout_default_and_override(self):
        from app.config import load_settings
        empty=Path(self.tmp.name)/'.env';empty.write_text('')
        self.assertEqual(load_settings({},empty).timeout_seconds,240)
        self.assertEqual(load_settings({'DEEPSEEK_TIMEOUT_SECONDS':'180'},empty).timeout_seconds,180)

    def test_existing_api_button_resumes_latest_partial(self):
        import time
        from fastapi.testclient import TestClient
        from api_fixture import main
        old=self.run_once();self.runtime.fail=None
        manager=type('Manager',(),{'state':lambda _:None})()
        with patch.object(main,'store',self.store),patch.object(main,'ai_service',self.runtime),patch.object(main,'corpus_manager',manager):
            with TestClient(main.app) as client:
                response=client.post('/api/evaluations/run',headers={'Origin':'http://127.0.0.1:5174'})
                self.assertEqual(response.status_code,201,response.text);child=response.json()['id']
                for _ in range(100):
                    if self.store.evaluation_run(child)['status']!='running':break
                    time.sleep(.02)
                self.assertEqual(self.store.evaluation_run(child)['status'],'completed')
                self.assertEqual(self.runtime.answers.count('Q1'),1);self.assertEqual(self.runtime.answers.count('Q2'),1)
                count=len(self.runtime.answers)
                response=client.post('/api/evaluations/run',json={'resume_source_id':old['id']},headers={'Origin':'http://127.0.0.1:5174'})
                self.assertEqual(response.status_code,409);self.assertEqual(len(self.runtime.answers),count)

    def test_saved_real_partial_copy_can_plan_resume_without_provider(self):
        import shutil
        path=Path(__file__).resolve().parents[2]/'output/playwright/baseline-stability/protected.db'
        if not path.exists():self.skipTest('Private business backup intentionally not tracked')
        fixture=Path(self.tmp.name)/'real-copy.db';shutil.copy2(path,fixture);store=GovernanceStore(fixture)
        source=store.evaluation_run('EVAL-20261012014020569115');snapshot=json.loads(source['dataset_snapshot_json'])
        runtime=Runtime();runtime.model=source['judge']['model']
        execution=source['judge']['execution_snapshot'];cfg=source['config']
        info={'knowledge_identity':cfg['knowledge_identity'],'knowledge_config':{'candidate_k':cfg['candidate_k'],'top_k':cfg['top_k']},'embedding_model':execution['embedding_model'],'vector_index':execution['vector_index']}
        runtime.corpus=type('Corpus',(),{'index_info':lambda _:info})()
        before=deepcopy(source)
        from app.evaluation_contract import policy_current
        if not policy_current(source['judge']):
            with patch('app.governance.manifest_identity',return_value=snapshot['corpus_fingerprint']):
                with self.assertRaisesRegex(ValueError,'Evaluation Identity'):EvaluationRunner(store,runtime).start_baseline(source['id'])
            self.assertEqual(store.evaluation_run(source['id']),before)
            self.assertFalse(runtime.answers);self.assertFalse(runtime.judges)
            return
        with patch('app.governance.manifest_identity',return_value=snapshot['corpus_fingerprint']):
            child,items,config=EvaluationRunner(store,runtime).start_baseline(source['id'])
        self.assertEqual(len(items),50);self.assertEqual(len(store.evaluation_case_results(child)),1);self.assertEqual(store.evaluation_run(source['id']),before);self.assertFalse(runtime.answers);self.assertFalse(runtime.judges)

    def test_changed_legacy_corpus_is_also_blocked(self):
        old=self.run_once()
        with patch('app.governance.manifest_identity',return_value={'fixture':'different corpus'}):
            with self.assertRaises(ValueError):self.runner.start_baseline(old['id'])
