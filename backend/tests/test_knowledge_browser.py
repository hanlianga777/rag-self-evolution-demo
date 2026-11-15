import json
import sqlite3
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.corpus import CorpusStore
from app.knowledge_browser import chunk_diagnostics, chunk_browser, cluster_browser
from app.knowledge_pipeline import document_category


class KnowledgeBrowserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.parents = [{'chunk_id': 'P', 'document_id': 'D', 'chunk_text': 'abcdefghij', 'chapter': '使用'},
                        {'chunk_id': 'P2', 'document_id': 'D', 'chunk_text': 'klm', 'chapter': '安全'}]
        self.children = [{'chunk_id': 'C1', 'document_id': 'D', 'parent_chunk_id': 'P', 'char_start': 0, 'char_end': 6, 'chunk_text': 'abcdef', 'token_count': 80},
                         {'chunk_id': 'C2', 'document_id': 'D', 'parent_chunk_id': 'P', 'char_start': 4, 'char_end': 10, 'chunk_text': 'efghij', 'token_count': 40},
                         {'chunk_id': 'C3', 'document_id': 'D', 'parent_chunk_id': 'P2', 'char_start': 0, 'char_end': 3, 'chunk_text': 'klm', 'token_count': 10, 'table': True}]
        for name, value in [('parents', self.parents), ('chunks', self.children), ('documents', [{'id': 'D', 'name': '巡检说明.pdf'}])]:
            (self.path / (name + '.json')).write_text(json.dumps(value))
        self.corpus = CorpusStore(self.path)
        self.db = sqlite3.connect(self.path/'test.db')
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.execute('CREATE TABLE dataset_versions (id, status, created_at, snapshot_json)')
        snapshot = {'questions': [{'id': 'Q-id', 'display_id': 'Q09', 'question': '如何使用？', 'test_category': 'positive', 'evidence': [{'source_chunk_ids': ['C2', 'old']}]}]}
        self.db.execute('INSERT INTO dataset_versions VALUES (?, ?, ?, ?)', ('G', 'approved', 'now', json.dumps(snapshot)))
        self.db.commit()
        self.store = type('Store', (), {'database_path': self.path/'test.db'})()
        self.patch = patch('app.corpus.discover_documents', return_value=[])
        self.patch.start(); self.addCleanup(self.patch.stop)

    def test_diagnostics_uses_saved_tokens_and_excludes_table_exception(self):
        value = chunk_diagnostics(self.corpus)
        self.assertEqual(value['fragment_count'], 1)
        self.assertEqual(value['average_children_per_parent'], 1.5)
        self.assertEqual(value['single_child_parent_ratio'], .5)
        self.assertAlmostEqual(value['average_child_tokens'], 130/3)
        (self.path/'chunks.json').write_text('[]')
        (self.path/'parents.json').write_text('[]')
        self.assertIsNone(chunk_diagnostics(self.corpus)['average_child_tokens'])
        self.assertIsNone(chunk_diagnostics(self.corpus)['single_child_parent_ratio'])

    def test_browser_keeps_exact_overlap_and_only_saved_golden_anchors(self):
        before = self.db.total_changes
        value = chunk_browser(self.corpus, self.store)
        self.assertEqual(value['parents'][0]['children'][1]['char_start'], 4)
        self.assertEqual(value['questions'][0]['parent_ids'], ['P'])
        self.assertEqual(value['questions'][0]['child_ids'], ['C2'])
        self.assertEqual(value['unmatched_anchor_count'], 1)
        self.assertEqual(self.db.total_changes, before)
        self.assertEqual(value['documents'][0]['category'], '巡检机器人说明书')

    def test_topic_includes_every_parent_and_groups_only_real_questions(self):
        cluster = {'cluster_id': 'T', 'chunk_ids': ['C1', 'C2', 'C3']}
        value = cluster_browser(cluster, chunk_browser(self.corpus, self.store))
        self.assertEqual([p['chunk_id'] for p in value['parents']], ['P', 'P2'])
        self.assertEqual(len(value['questions']), 1)
        self.assertEqual(value['questions'][0]['display_id'], 'Q09')

    def test_title_rules_are_case_insensitive_and_override_stale_category(self):
        for title, expected in [('kira使用.pdf','清洁机器人说明书'), ('B2电池与充电器.pdf','电池与充电器说明书'), ('B2遥控器.pdf','遥控器说明书'), ('B2四足.pdf','巡检机器人说明书'), ('未知.pdf','其他')]:
            self.assertEqual(document_category({'name':title,'category':'其他'}),expected)

    def test_missing_saved_length_or_parent_is_unknown(self):
        self.children[0].pop('token_count')
        (self.path/'chunks.json').write_text(json.dumps(self.children))
        self.assertIsNone(chunk_diagnostics(self.corpus)['average_child_tokens'])
        (self.path/'parents.json').unlink()
        self.assertIsNone(chunk_diagnostics(self.corpus)['average_children_per_parent'])

    def test_http_routes_are_read_only_with_isolated_database(self):
        code = """
import json, os
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import main
from app.corpus import CorpusStore
main.corpus = CorpusStore(__import__('pathlib').Path(os.environ['RAG_DEMO_INDEX_DIR']))
with patch('app.corpus.discover_documents', return_value=[]):
    client = TestClient(main.app)
    health = client.get('/api/knowledge/chunk-diagnostics')
    assert health.status_code == 200, health.text
    assert health.json()['fragment_count'] == 1
    browser = client.get('/api/knowledge/chunk-browser')
    assert browser.status_code == 200, browser.text
    assert browser.json()['questions'][0]['display_id'] == 'Q09'
    assert client.post('/api/knowledge/chunk-browser').status_code == 405
"""
        before = (self.path/'test.db').read_bytes()
        env = {**os.environ, 'RAG_DEMO_DB_PATH': str(self.path/'test.db'),
               'RAG_DEMO_INDEX_DIR': str(self.path), 'RAG_FORCE_MOCK': '1',
               'RAG_SAFE_START': '1', 'RAG_DEMO_ENV_PATH': str(self.path/'absent.env')}
        result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, (self.path/'test.db').read_bytes())

    def test_unanchored_negative_uses_saved_topic_only_when_membership_matches(self):
        snapshot = json.loads(self.db.execute('SELECT snapshot_json FROM dataset_versions').fetchone()[0])
        snapshot['coverage_plan'] = {'clusters': [{'cluster_id': 'T', 'chunk_ids': ['C1', 'C2']}]}
        snapshot['questions'].append({'id':'N','display_id':'Q20','test_category':'negative','topic_cluster':'T','question':'可以违规操作吗？'})
        self.db.execute('UPDATE dataset_versions SET snapshot_json=?', (json.dumps(snapshot),))
        self.db.commit()
        browser = chunk_browser(self.corpus, self.store)
        negative = next(q for q in browser['questions'] if q['id']=='N')
        self.assertEqual(negative['parent_ids'], [])
        self.assertEqual(negative['child_ids'], [])
        self.assertEqual(len(cluster_browser({'cluster_id':'T','chunk_ids':['C1','C2']}, browser)['questions']), 2)
        self.assertEqual(cluster_browser({'cluster_id':'T','chunk_ids':['C3']}, browser)['questions'], [])
