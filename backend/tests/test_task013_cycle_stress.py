"""Disposable real-runner A/B/C pressure test, with Stub RPCs and process restart."""
import os
import http.client
import faulthandler
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from app.governance import GovernanceStore
from app.evaluation import EvaluationRunner
from app.evaluation_stage import checkpoint_request
from app.optimization_cycle import run_until_qualified
from app.providers import ProviderAPIError, ProviderInvalidResponse, ProviderTimeout
from app.policy import DEFAULT_PIPELINE_CONFIG
from app.telemetry import record_usage
from test_baseline_resume import Runtime


class PressureRuntime(Runtime):
    def __init__(self, database, *, pause=False):
        super().__init__(fail=None)
        self.store=GovernanceStore(database,migrate=False)
        self.pause=pause
        self.provider=object()
        self.current_candidate='baseline'

    def note(self, candidate, question, phase, status):
        with self.store.connection() as connection:
            connection.execute('INSERT INTO stub_calls VALUES (?,?,?,?)',(candidate,question,phase,status))

    def count(self, candidate, question, phase, status):
        with self.store.connection() as connection:
            return connection.execute('SELECT count(*) FROM stub_calls WHERE candidate=? AND question=? AND phase=? AND status=?',(candidate,question,phase,status)).fetchone()[0]

    def answer(self, question, config):
        candidate=config.get('candidate_id','baseline')
        self.current_candidate=candidate
        if self.pause and candidate.endswith('-A') and question=='Q26':
            Path(str(self.store.database_path)+'.restart-ready').write_text('before Provider')
            time.sleep(30)
        faults={'Q05':ProviderTimeout('Stub network timeout'),
                'Q10':http.client.IncompleteRead(b'',100),
                'Q15':ProviderAPIError('Stub unavailable',status_code=503),
                'Q20':ProviderAPIError('Stub limited',status_code=429)}
        if candidate!='baseline' and question in faults and not self.count(candidate,question,'generation','fault'):
            self.note(candidate,question,'generation','fault')
            raise faults[question]
        def action():
            self.note(candidate,question,'generation','ok')
            execution=super(PressureRuntime,self).answer(question,config)
            execution['provider_raw_result']={'content':'x'*120000}
            for entry in execution['retrieval_trace']['final']:entry['content']+='事实'*18000
            return execution
        return checkpoint_request('Stub','fixture','answer',{'candidate':candidate,'question':question},action)

    def judge(self, question, expected, answer, category, context=None):
        candidate=self.current_candidate
        invalid=3 if question=='Q30' else 1 if question=='Q35' else 0
        if candidate!='baseline' and self.count(candidate,question,'judge','invalid')<invalid:
            self.note(candidate,question,'judge','invalid')
            record_usage({'provider':'Stub','status':'ok','prompt_tokens':30,'completion_tokens':40})
            raise ProviderInvalidResponse('answer quote is missing or not located' if question=='Q35' else 'Stub invalid JSON',raw_provider_response='{}')
        self.note(candidate,question,'judge','ok')
        return super().judge(question,expected,answer,category,context)


def cycle_worker(database, experiment_id, restart=False):
    trace_path=Path(str(database)+('.restart.trace' if restart else '.trace'))
    trace_file=trace_path.open('w')
    faulthandler.dump_traceback_later(30,repeat=True,file=trace_file)
    store=GovernanceStore(database,migrate=False)
    if restart:store.interrupt_evaluation_runs()
    runtime=PressureRuntime(database,pause=not restart)
    with patch('app.evaluation_stage.time.sleep',lambda *_:None), patch('app.paid_schedule.utc_now',return_value=datetime(2026,11,7,12,tzinfo=timezone.utc)):
        # The restart pause must remain real while retry backoff is skipped.
        runtime_pause=runtime.pause
        runtime.pause=False
        original=runtime.answer
        def answer(question,config):
            if runtime_pause and config.get('candidate_id','').endswith('-A') and question=='Q26':
                Path(str(database)+'.restart-ready').write_text('before Provider')
                threading.Event().wait(30)
            return original(question,config)
        runtime.answer=answer
        if restart:
            from app.optimization_cycle import recover_optimization_cycles
            recover_optimization_cycles(store,runtime)
            deadline=time.monotonic()+160
            while time.monotonic()<deadline:
                with store.connection() as connection:
                    raw=connection.execute("SELECT json_extract(result_json,'$.optimization_cycle') FROM experiments WHERE id=?",(experiment_id,)).fetchone()[0]
                result=json.loads(raw)
                if result['status']!='running':break
                threading.Event().wait(.1)
            else:raise TimeoutError('Recovered cycle did not finish')
        else:result=run_until_qualified(store,runtime,experiment_id)
    faulthandler.cancel_dump_traceback_later()
    trace_file.close()
    print(json.dumps(result,ensure_ascii=False),flush=True)


class RealCyclePressureTests(unittest.TestCase):
    def setUp(self):
        clock=patch('app.paid_schedule.utc_now',return_value=datetime(2026,11,7,12,tzinfo=timezone.utc))
        clock.start();self.addCleanup(clock.stop)

    def test_real_abc_150_questions_api_polling_and_process_restart(self):
        from app.corpus import current_manifest,manifest_identity
        from app.history import prune_history
        from fastapi.testclient import TestClient
        from api_fixture import main
        with tempfile.TemporaryDirectory(prefix='task013-cycle-') as directory:
            database=Path(directory)/'fixture.sqlite'
            store=GovernanceStore(database)
            items=[]
            for n in range(1,51):
                category='positive' if n<=20 else 'ablation' if n<=30 else 'negative'
                items.append({'id':f'Q{n:02}', 'question':f'Q{n:02}', 'reference_answer':'事实',
                    'test_category':category, 'negative_subtype':('safety_critical' if n<=40 else 'prompt_injection') if category=='negative' else None,
                    'evidence':[]})
            snapshot={'questions':items,'question_ids':[i['id'] for i in items], 'corpus_fingerprint':manifest_identity(current_manifest())}
            with store.connection() as connection:
                connection.execute('INSERT INTO dataset_versions VALUES (?,?,?,?,?)',('fixture-50','approved','fixture',json.dumps(snapshot),'9999'))
                connection.execute('CREATE TABLE stub_calls(candidate TEXT,question TEXT,phase TEXT,status TEXT)')
            runtime=PressureRuntime(database)
            baseline=EvaluationRunner(store,runtime).run_baseline(automatic=True)
            self.assertTrue(baseline['result']['evaluation_complete'],baseline.get('error_message'))
            experiment_id=store.create_experiment(baseline['id'],'completed')
            for n in range(8):
                store.save_candidate(experiment_id,f'history{n}',dict(DEFAULT_PIPELINE_CONFIG),{'round':1,'candidate_label':'history'})
                store.finish_candidate(f'{experiment_id}-history{n}','evaluated',{'evaluation_complete':True})
            for label in 'ABC':
                store.save_candidate(experiment_id,label,dict(DEFAULT_PIPELINE_CONFIG),{'round':2,'candidate_label':label})
            failures=[];stop=threading.Event();polls=[]
            urls=['/api/evaluation?active_task=true&light=true','/api/optimization?light=true',
                  '/api/governance/generation-runs?light=true','/api/overview?light=true']
            def poll():
                try:
                    with TestClient(main.app,raise_server_exceptions=False) as client:
                        while not stop.is_set():
                            for url in urls:
                                response=client.get(url);polls.append((url,response.status_code))
                                if response.status_code!=200:failures.append((url,response.status_code,response.text[:200]))
                            prune_history(store)
                            main.recover_authorized_evaluations()
                            stop.wait(1)
                except Exception as error:failures.append(str(error))
            processes=[]
            def launch(restart=False):
                command=[sys.executable,str(Path(__file__).resolve()),'worker',str(database),experiment_id]
                if restart:command.append('restart')
                from app.corpus import INDEX_DIR, DOCUMENTS_DIR, UPLOADS_DIR
                process=subprocess.Popen(command,env={**os.environ,'PYTHONPATH':os.pathsep.join([str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]),
                    'RAG_DEMO_INDEX_DIR':str(INDEX_DIR),'RAG_DEMO_DOCUMENTS_DIR':str(DOCUMENTS_DIR),
                    'RAG_DEMO_UPLOADS_DIR':str(UPLOADS_DIR),'RAG_DEMO_DB_PATH':str(database)},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                processes.append(process)
                return process
            with patch.object(main,'store',store),patch.object(main,'ai_service',runtime),patch.object(main,'safe_start',True):
                thread=threading.Thread(target=poll);thread.start()
                try:
                    first=launch()
                    ready=Path(str(database)+'.restart-ready')
                    deadline=time.monotonic()+90
                    while not ready.exists() and first.poll() is None and time.monotonic()<deadline:stop.wait(.05)
                    self.assertTrue(ready.exists(),first.communicate(timeout=1) if first.poll() is not None else 'restart marker timeout')
                    before=store.candidate(f'{experiment_id}-A')
                    before_count=len(store.evaluation_case_results(before['result']['evaluation_run_id']))
                    print(f'Stub A restart: saved={before_count}/25; next=Q26',flush=True)
                    first.terminate();first.communicate(timeout=5)
                    second=launch(restart=True)
                    try:output,errors=second.communicate(timeout=180)
                    except subprocess.TimeoutExpired as error:
                        print('worker traces: '+(error.stderr or b'').decode(errors='replace'),flush=True)
                        raise
                    self.assertEqual(second.returncode,0,errors)
                    result=json.loads(output.splitlines()[-1])
                    self.assertEqual(result['status'],'budget_exhausted',result)
                finally:
                    stop.set();thread.join(timeout=10)
                    for process in processes:
                        if process.poll() is None:process.terminate();process.communicate(timeout=5)
            self.assertFalse(failures,failures)
            self.assertEqual(before_count,25)
            self.assertTrue(polls)
            experiment=store.experiment(experiment_id)
            self.assertEqual(experiment['evaluation_budget']['used'],11)
            for candidate in experiment['candidates']:
                if candidate['reasoning']['candidate_label'] not in 'ABC':continue
                self.assertEqual(candidate['status'],'evaluated',candidate['result'].get('error'))
                self.assertTrue(candidate['result']['evaluation_complete'])
                self.assertEqual(candidate['result'].get('technical_failed'),0)
                self.assertEqual(len(store.evaluation_case_results(candidate['result']['evaluation_run_id'])),50)
            with store.connection() as connection:
                grouped=connection.execute("SELECT phase,status,count(*) FROM stub_calls WHERE candidate!='baseline' GROUP BY phase,status").fetchall()
                counts={(r[0],r[1]):r[2] for r in grouped}
                duplicates=connection.execute("SELECT candidate,question,phase,count(*) FROM stub_calls WHERE candidate!='baseline' AND status='ok' GROUP BY candidate,question,phase HAVING count(*)>1").fetchall()
            self.assertEqual(counts.get(('generation','ok')),150)
            self.assertEqual(counts.get(('judge','ok')),150)
            self.assertEqual(counts.get(('judge','invalid')),12)
            self.assertFalse(duplicates)
            print(json.dumps({'answers':counts.get(('generation','ok')),'valid_judges':counts.get(('judge','ok')),
                'invalid_judges':counts.get(('judge','invalid')),'transport_faults':counts.get(('generation','fault')),
                'api_polls':len(polls),'api_failures':len(failures),'budget_before':8,'budget_after':11,'restarts':1}),flush=True)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='worker':cycle_worker(sys.argv[2],sys.argv[3],len(sys.argv)>4)
    else:unittest.main()
