"""Fixture-only full lifecycle through FastAPI, persisted in disposable SQLite."""
import json
import os
import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient
from api_fixture import main
from app.ai_service import AiService
from app.governance import GovernanceStore
from app.policy import qualify_candidate
from test_v11_e2e import FixtureCorpus, FixtureProvider, FixtureRetriever, FixtureEvaluationRuntime

FINGERPRINT = {'synthetic-fixture': 'v14-api-lifecycle'}


class LifecycleCorpus(FixtureCorpus):
    def documents(self):
        return [{'id': f'DOC-{i}', 'name': f'Fixture 文档 {i}', 'product': f'产品 {i}', 'pages': 3, 'chunks': 3, 'parser': 'Fixture Parser', 'ocr': 'Fixture', 'status': 'Indexed', 'parse_status': 'Parsed', 'index_status': 'Indexed', 'chunk_strategy': 'Fixture paragraphs'} for i in range(1, 5)]

    def detail(self, id):
        doc = next((row for row in self.documents() if row['id'] == id), None)
        return {**doc, 'chunks': [row for row in self.items if row['document_id'] == id]} if doc else None

    def index_info(self):
        return {'embedding_model': 'fixture', 'vector_index': 'Fixture', 'corpus_fingerprint': FINGERPRINT, 'full_text': {'supported': True, 'status': 'ready', 'coverage': {'status': 'complete'}}}


class LifecycleService(AiService):
    def _indexed_embeddings(self, chunks):
        return np.asarray([[float(i == int(row['document_id'].split('-')[-1]) - 1) for i in range(4)] for row in chunks], dtype='float32')

    def negative_topic_embedding(self, question):
        plan = self.store.generation_runs()[0]['artifacts']['hard_validation']['frozen_plan']
        slot = next(row for row in plan['slots'] if row['slot'] == re.search(r'Q\d+', question).group())
        return next(row['center'] for row in plan['clusters'] if row['cluster_id'] == slot['topic_cluster'])

    def answer(self, question, config):
        result = FixtureEvaluationRuntime(self.store).answer(question, config)
        row = next(row for row in self.store.questions() if row['question'] == question)
        slot = row['raw'].get('coverage_slot')
        if slot == 'Q03' and config['min_score'] == 0 or slot in ('Q04', 'Q09') and config['top_k'] == 6 and config['min_score'] == .2:
            result['answer'] = '错误答案'
        evidence = [{**item, 'document': 'Fixture 文档', 'document_id': row['evidence'][0].get('document_id', 'DOC-1'), 'page_start': 1, 'page_end': 1, 'section_path': 'Fixture', 'content_preview': '合成证据', 'score': .95} for item in result['retrieval']]
        result.update(retrieval=evidence, corpus_fingerprint=FINGERPRINT, mode='local', model='fixture', timing_semantics={'stages_are_nested_not_additive': True}, cost_estimation={'status': 'unavailable', 'amount': None, 'reason': 'price_unavailable'}, stages=[{'stage_name': 'retrieval', 'duration_ms': 10}, {'stage_name': 'generation', 'duration_ms': 80}])
        return result

    def judge(self, question, expected, answer, category):
        return FixtureEvaluationRuntime(self.store).judge(question, expected, answer, category)


class ApiLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rag-v14-api-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.store = GovernanceStore(Path(self.temp.name) / 'test.db')
        self.corpus = LifecycleCorpus()
        self.service = LifecycleService(self.store, self.corpus, FixtureProvider(), False)
        self.service.retriever = FixtureRetriever(self.store)
        for owner, key, value in ((main, 'store', self.store), (main, 'corpus', self.corpus), (main, 'ai_service', self.service)):
            old = getattr(owner, key); setattr(owner, key, value); self.addCleanup(setattr, owner, key, old)
        for target in ('app.governance.current_manifest', 'app.corpus.current_manifest', 'app.main.current_manifest'):
            patcher = patch(target, return_value={'sources': FINGERPRINT}); patcher.start(); self.addCleanup(patcher.stop)
        patcher = patch.object(main.corpus_manager, 'state', return_value={}); patcher.start(); self.addCleanup(patcher.stop)
        self.client = TestClient(main.app)

    def post(self, path, body=None, status=None):
        response = self.client.post('/api/' + path, json=body)
        self.assertIn(response.status_code, (200, 201, 202) if status is None else (status,), response.text)
        return response.json()

    def wait(self, path, terminal):
        for _ in range(300):
            result = self.client.get('/api/' + path).json()
            if result['status'] in terminal: return result
            time.sleep(.01)
        self.fail('Fixture API did not terminate: ' + path)

    def test_complete_v2_http_lifecycle_d_regression_keeps_winner_monitoring_round_one(self):
        self.assertTrue(self.client.get('/api/dataset').json(), 'Legacy seed is loaded')
        initial_version = self.store.active_production()
        initial_versions = self.store.production_versions()
        plan = self.post('governance/coverage-preview', {'profile': 'mini'})
        self.assertEqual(len(plan['slots']), 20)
        started = self.post('governance/generate', {'profile': 'mini', 'plan_id': plan['plan_id']})
        run = self.wait('governance/generation-runs/' + started['run_id'], ('completed', 'failed', 'needs_regeneration'))
        self.assertEqual(run['status'], 'completed', run)
        self.assertEqual(len(run['question_ids']), 20)
        self.assertEqual(run['artifacts']['hard_validation']['frozen_plan']['plan_id'], plan['plan_id'])
        for id in run['question_ids']:
            self.assertTrue(self.post(f'governance/questions/{id}/probe')['passed'])
            qc = self.post(f'governance/questions/{id}/qc')
            self.assertEqual(qc['status'], 'qc_passed')
        frozen = self.post('governance/review-batch', {'question_ids': run['question_ids'], 'confirmed_manual_review': True})
        self.assertEqual(self.store.dataset_summary()['approved'], 20)
        snapshot = self.store.dataset_snapshots()[0]
        snapshot_before = json.dumps(snapshot, sort_keys=True)
        baseline = self.post('evaluations/run')
        baseline = self.wait('evaluations/' + baseline['id'], ('completed', 'failed'))
        baseline_before = self.store.evaluation_run(baseline['id'])
        self.assertEqual(baseline['status'], 'completed')
        self.assertEqual(len(baseline['cases']), 20)
        self.assertGreater(baseline['result']['bad_case_count'], 0)
        experiment = self.post('experiments/run')
        self.assertEqual(len(experiment['candidates']), 3)
        self.assertEqual({row['reasoning']['round'] for row in experiment['candidates']}, {1})
        # RL-03: an actual unevaluated Candidate cannot publish.
        self.post('candidates/' + experiment['candidates'][0]['id'] + '/publish', {'decision': 'approved'}, status=409)
        self.assertEqual(self.store.active_production(), initial_version)
        self.assertEqual(self.store.production_versions(), initial_versions)
        for candidate in experiment['candidates']:
            evaluation = self.post('candidates/' + candidate['id'] + '/run')
            self.assertEqual(self.wait('evaluations/' + evaluation['id'], ('completed', 'failed'))['status'], 'completed')
        winner = experiment['id'] + '-R1-A'
        current = self.client.get('/api/optimization').json()
        self.assertTrue(next(row for row in current['candidates'] if row['id'] == winner)['result']['qualification']['qualified'])
        # All ABC completed and A qualified, but human Gate2 has not happened.
        self.post('candidates/' + winner + '/publish', {'decision': 'approved'}, status=409)
        self.assertEqual(self.store.active_production(), initial_version)
        self.assertEqual(self.store.production_versions(), initial_versions)
        # RL-01: retain actual failed Baseline gates; derive eligibility with real rules.
        score_candidate = current['candidates'][1]
        score_result = {**score_candidate['result'], 'gates': baseline['result']['gates'], 'overall_score': 100}
        score_result['qualification'] = qualify_candidate(score_result['gates'], score_result['regression'], score_result['target_bad_cases_fixed'], baseline['result']['bad_case_count'], score_result['bad_case_count'])
        self.assertGreater(score_result['overall_score'], max(row['result']['overall_score'] for row in current['candidates']))
        self.assertFalse(score_result['qualification']['qualified'])
        self.store.finish_candidate(score_candidate['id'], 'evaluated', score_result)
        recommendation = self.store.refresh_recommendation(experiment['id'])
        self.assertNotIn(score_candidate['id'], recommendation['pareto_frontier'])
        self.post('experiments/' + experiment['id'] + '/recommendation', {'candidate_id': score_candidate['id']}, status=409)
        self.post('candidates/' + score_candidate['id'] + '/publish', {'decision': 'approved'}, status=409)
        self.assertEqual(self.store.active_production(), initial_version)
        self.assertEqual(self.store.production_versions(), initial_versions)
        self.store.finish_candidate(score_candidate['id'], 'evaluated', score_candidate['result'])
        self.post('experiments/' + experiment['id'] + '/recommendation', {'candidate_id': winner})
        composite = self.post('experiments/' + experiment['id'] + '/composite')
        self.assertEqual(composite['status'], 'generated')
        started = self.post('candidates/' + composite['id'] + '/run')
        self.wait('evaluations/' + started['id'], ('completed', 'failed'))
        current = self.client.get('/api/optimization').json()
        d = next(row for row in current['candidates'] if row['id'] == composite['id'])
        self.assertFalse(d['result']['qualification']['qualified'], json.dumps({'config': d['config'], 'reasoning': d['reasoning'], 'result': d['result']}, ensure_ascii=False))
        self.assertTrue(d['result']['gates']['passed'], 'D passes gates; two new ordinary failures fail Regression')
        self.assertFalse(d['result']['regression']['passed'])
        self.post('candidates/' + composite['id'] + '/publish', {'decision': 'approved'}, status=409)
        self.assertEqual(self.store.active_production(), initial_version)
        self.assertEqual(self.store.production_versions(), initial_versions)
        self.assertEqual(current['recommendation']['result']['recommended_candidate'], winner)
        self.assertEqual(self.store.active_production(), initial_version)
        # RL-05: the UI/precheck saw eligibility, then the transactional row changed.
        require_baseline = self.store.require_current_baseline
        def qualification_changed(run_id, connection=None):
            result = require_baseline(run_id, connection)
            if connection is not None:
                stale = json.loads(connection.execute('SELECT result_json FROM candidate_configs WHERE id=?', (winner,)).fetchone()[0])
                stale['qualification']['qualified'] = False
                connection.execute('UPDATE candidate_configs SET result_json=? WHERE id=?', (json.dumps(stale), winner))
            return result
        before_versions = self.store.production_versions()
        with patch.object(self.store, 'require_current_baseline', side_effect=qualification_changed):
            refused = self.post('candidates/' + winner + '/publish', {'decision': 'approved'}, status=409)
        self.assertIn('发布资格已变化', refused['detail'])
        self.assertEqual(self.store.production_versions(), before_versions)
        self.assertTrue(self.store.candidate(winner)['result']['qualification']['qualified'], 'Failed transaction rolls back')
        version = self.post('candidates/' + winner + '/publish', {'decision': 'approved'})
        question = self.store.question(run['question_ids'][0])['question']
        left = self.post('preview/scheme', {'question': question, 'scheme_id': 'baseline'})
        right = self.post('preview/scheme', {'question': question, 'scheme_id': version['id']})
        self.assertEqual(left['version'], baseline['id'])
        self.assertEqual(right['version'], version['id'])
        self.assertEqual(left['question'], right['question'])
        qa = self.post('preview', {'question': question})
        event = self.post('monitoring/events/' + qa['monitoring_event_id'] + '/assessment', {'bad_case': True, 'severity': 'critical'})
        trigger = event['trigger']
        self.dump_browser_fixture(run, baseline, current, winner, composite, version)
        context = self.post('monitoring/triggers/' + trigger['id'] + '/confirm', {'decision': 'approved'})
        self.assertEqual(self.store.experiment(context['optimization_run_id'])['status'], 'pending_agent')
        self.assertEqual(self.store.experiment(context['optimization_run_id'])['result']['round'], 0)
        confirmed_again = self.post('monitoring/triggers/' + trigger['id'] + '/confirm', {'decision': 'approved'})
        self.assertEqual(context['optimization_run_id'], confirmed_again['optimization_run_id'])
        monitoring_round = self.post('experiments/run', {'trigger_id': trigger['id']})
        self.assertEqual(monitoring_round['id'], context['optimization_run_id'])
        self.assertEqual({row['reasoning']['round'] for row in monitoring_round['candidates']}, {1})
        self.assertEqual(self.store.evaluation_run(baseline['id']), baseline_before)
        self.assertEqual(json.dumps(self.store.dataset_snapshots()[0], sort_keys=True), snapshot_before)
        self.assertEqual(self.store.active_production()['id'], version['id'])

    def dump_browser_fixture(self, run, baseline, current, winner, composite, version):
        """Freeze actual GET responses before monitoring creates the next experiment."""
        output = os.environ.get('RAG_V14_BROWSER_FIXTURE_DIR')
        if not output: return
        target = Path(output); target.mkdir(parents=True, exist_ok=True)
        paths = ['workspace', 'overview', 'documents', 'dataset', 'evaluation', 'bad-cases', 'optimization', 'versions', 'readiness', 'monitoring', 'pipeline', 'evaluations', 'governance/generation-runs', 'governance/snapshots', 'governance/revisions', 'governance/summary']
        paths += ['documents/' + doc['id'] for doc in self.corpus.documents()]
        paths += ['evaluations/' + row['id'] for row in self.store.evaluation_runs()]
        paths += ['governance/generation-runs/' + run['id']]
        payloads = {'/api/' + path: self.client.get('/api/' + path).json() for path in paths}
        payloads['/api/governance/generation-runs/' + run['id'] + '/export'] = self.client.get('/api/governance/generation-runs/' + run['id'] + '/export?format=json').json()
        (target / 'payloads.json').write_text(json.dumps(payloads, ensure_ascii=False))
        (target / 'lifecycle.json').write_text(json.dumps({'provenance': 'synthetic fixture FastAPI transitions before Monitoring Confirm', 'baseline': baseline['id'], 'experiment': current['id'], 'winner': winner, 'd': composite['id'], 'production': version['id']}, ensure_ascii=False))
