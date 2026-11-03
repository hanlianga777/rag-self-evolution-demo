"""Real runner/API, realistic payloads, temporary DB, deterministic fault schedule."""
import collections
import http.client
import json
import random
import sqlite3
import threading
import time
import unittest
from unittest.mock import patch

import test_baseline_resume as fixture
from api_fixture import main
from fastapi.testclient import TestClient
from app.evaluation import EvaluationRunner
from app.evaluation_stage import checkpoint_request
from app.providers import ProviderAPIError, ProviderInvalidResponse
from app.history import prune_history


class BaselinePressureTests(unittest.TestCase):
    setUp = fixture.ResumeTests.setUp
    tearDown = fixture.ResumeTests.tearDown

    def test_fifty_with_real_api_readers_lock_and_provider_faults(self):
        with self.store.connection() as c:
            snapshot = json.loads(c.execute("SELECT snapshot_json FROM dataset_versions WHERE id='fixture-golden'").fetchone()[0])
            snapshot['questions'] = [{**snapshot['questions'][i % 4], 'id': f'Q{i+1:02}', 'question': f'Q{i+1:02}'} for i in range(50)]
            snapshot['question_ids'] = [q['id'] for q in snapshot['questions']]
            c.execute("UPDATE dataset_versions SET snapshot_json=? WHERE id='fixture-golden'", (json.dumps(snapshot),))
        calls = collections.Counter()
        faults = random.Random(13).sample(range(3, 30), 4)
        transport = [TimeoutError('injected timeout'), http.client.IncompleteRead(b'partial', 100),
                     ProviderAPIError('injected 5xx', status_code=503), ProviderAPIError('injected 429', status_code=429)]

        class Runtime(fixture.Runtime):
            def answer(inner, q, config):
                def request():
                    calls['answer', q] += 1
                    n = int(q[1:])
                    if n in faults and calls['answer', q] == 1:
                        raise transport[faults.index(n)]
                    time.sleep(.025)
                    value = super(Runtime, inner).answer(q, config)
                    value['provider_raw'] = '回答原始结果' * 7000
                    value['retrieval_trace']['candidates'] = [{'content': '检索证据' * 4000, 'chunk_id': str(i)} for i in range(4)]
                    return value
                return checkpoint_request('fixture', 'fixture', 'answer', {'question': q}, request)

            def judge(inner, q, *args, **kwargs):
                calls['judge', q] += 1
                if q in {'Q31', 'Q49'} and calls['judge', q] <= (3 if q == 'Q31' else 2):
                    raise ProviderInvalidResponse('answer quote is missing or not located' if q == 'Q49' else 'missing fields', raw_provider_response='{}')
                return super().judge(q, *args, **kwargs)

        runtime = Runtime(fail=None)
        runner = EvaluationRunner(self.store, runtime)
        run, items, config = runner.start_baseline(automatic=True)
        done = threading.Event()
        poll_errors, polls, measurements, lock_threads = [], [], [], []
        lock_started = threading.Event()
        original_update = self.store.update_evaluation_progress
        original_save = self.store.record_evaluation_case
        locked_once, save_failed = [], []

        def hold_lock():
            c = sqlite3.connect(self.store.database_path)
            try:
                c.execute('BEGIN IMMEDIATE')
                lock_started.set()
                time.sleep(6.2)
                c.commit()
            finally:
                c.close()

        def update(key, result, **kwargs):
            cp = result.get('checkpoints', {})
            q = kwargs.get('checkpoint_id') or next(reversed(cp), None)
            if q == 'Q08' and not locked_once:
                locked_once.append(True)
                thread = threading.Thread(target=hold_lock)
                lock_threads.append(thread)
                thread.start()
                self.assertTrue(lock_started.wait(2))
            started = time.perf_counter()
            value = original_update(key, result, **kwargs)
            if q in {'Q01', 'Q50'}:
                with self.store.connection() as c:
                    small = c.execute('SELECT length(cast(result_json AS BLOB)) FROM evaluation_runs WHERE id=?', (key,)).fetchone()[0]
                serialized = len(json.dumps(cp.get(q), ensure_ascii=False).encode())
                measurements.append({'question': q, 'ms': round((time.perf_counter()-started)*1000, 3), 'checkpoint_bytes': serialized, 'summary_bytes': small})
            return value

        def save(*args, **kwargs):
            if args[1] == 'Q08' and not save_failed:
                save_failed.append(True)
                raise sqlite3.OperationalError('database is locked')
            return original_save(*args, **kwargs)

        # No monitor startup hook: explicitly exercise recovery/retention at production interval.
        def monitor():
            while not done.wait(5):
                try:
                    prune_history(self.store)
                    main.recover_authorized_evaluations()
                except Exception as error:
                    poll_errors.append(('monitor', str(error)))

        # TestClient without context prevents app-wide startup from creating unrelated workers.
        def reader():
            client = TestClient(main.app, raise_server_exceptions=False)
            try:
                while not done.is_set():
                    for url in [f'/api/evaluations/{run}?light=true','/api/optimization?light=true',
                                '/api/governance/generation-runs?light=true','/api/overview']:
                        response=client.get(url);polls.append(response.status_code)
                        if response.status_code>=500:poll_errors.append((url,response.text[:120]))
                    done.wait(1)
            finally:client.close()

        with patch.object(main,'store',self.store), patch.object(main,'ai_service',runtime), \
             patch.object(self.store,'update_evaluation_progress',side_effect=update), \
             patch.object(self.store,'record_evaluation_case',side_effect=save):
            readers=[threading.Thread(target=reader), threading.Thread(target=monitor)]
            for thread in readers:thread.start()
            try:
                result=runner.execute_baseline(run,items,config)
            finally:
                done.set()
                for thread in readers+lock_threads:thread.join(15)
        evidence={'status':result['status'],'completed':result['result'].get('completed'),
                  'technical_failed':result['result'].get('technical_failed'), 'error':result.get('error_message'),
                  'polls':len(polls),'read_errors':poll_errors,'calls':sum(calls.values()),
                  'fault_questions':faults,'measurements':measurements}
        print('TASK013_PRESSURE '+json.dumps(evidence,ensure_ascii=False))
        self.assertEqual(result['result'].get('completed'),50)
        self.assertTrue(result['result'].get('evaluation_complete'))
        self.assertEqual(result['result'].get('technical_failed'),0)
        self.assertFalse(poll_errors)
        self.assertGreaterEqual(len(polls),12)
        self.assertEqual(calls['answer','Q08'],1)
        self.assertEqual(calls['judge','Q08'],1)


if __name__ == '__main__':unittest.main()
