import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

from app import knowledge_pipeline as kp


class KnowledgePipelineTests(unittest.TestCase):
    def test_cdn_recovery_keeps_official_tls_identity_and_rejects_other_hosts(self):
        from io import BytesIO
        from unittest.mock import Mock
        failure = kp.urllib.error.URLError(kp.ssl.SSLEOFError('VPN DNS handshake'))
        connection = Mock(); connection.getresponse.return_value.status = 200; connection.getresponse.return_value.read.return_value = b'zip'
        context = Mock(); raw_socket = Mock()
        with patch.object(kp.urllib.request, 'urlopen', side_effect=[failure, BytesIO(b'{"Answer":[{"type":1,"data":"1.2.3.4"}]}')]), patch.object(kp.http.client, 'HTTPSConnection', return_value=connection), patch.object(kp.socket, 'create_connection', return_value=raw_socket), patch.object(kp.ssl, 'create_default_context', return_value=context):
            self.assertEqual(kp.download_mineru_result('https://cdn-mineru.openxlab.org.cn/result.zip?signature=private'), b'zip')
        context.wrap_socket.assert_called_once_with(raw_socket, server_hostname='cdn-mineru.openxlab.org.cn')
        connection.request.assert_called_once_with('GET', '/result.zip?signature=private')
        connection.close.assert_called_once()
        with patch.object(kp.urllib.request, 'urlopen', side_effect=failure) as request:
            with self.assertRaises(kp.urllib.error.URLError):
                kp.download_mineru_result('https://untrusted.invalid/result.zip')
        self.assertEqual(request.call_count, 1)

    def test_mineru_upload_does_not_inject_unsigned_content_type(self):
        from io import BytesIO
        import zipfile
        archive = BytesIO()
        with zipfile.ZipFile(archive, 'w') as bundle:
            bundle.writestr('content_list.json', json.dumps([{'type': 'text', 'text': 'source'}]))
        calls = []
        def transfer(request, **kwargs):
            calls.append(request)
            return BytesIO(archive.getvalue() if isinstance(request, str) else b'')
        provider = kp.MinerUProvider({'MINERU_API_KEY': 'fixture'})
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory)/'manual.pdf'; pdf.write_bytes(b'%PDF-source')
            with patch.object(provider, '_request', side_effect=[{'batch_id': 'batch', 'file_urls': ['https://upload.invalid/file']}, {'extract_result': [{'state': 'done', 'full_zip_url': 'https://result.invalid/file'}]}]), patch.object(kp.urllib.request, 'urlopen', side_effect=transfer):
                blocks, result = provider.parse(pdf, 'D')
        self.assertEqual(calls[0].get_method(), 'PUT')
        self.assertEqual(calls[0].get_header('Content-type'), '')
        self.assertEqual(blocks[0]['text'], 'source')
        self.assertEqual(result, archive.getvalue())

    def test_parent_child_reconstructs_pages_and_preserves_table(self):
        document = {'id': 'D', 'name': 'manual.pdf', 'product': 'B2'}
        blocks = [{'type': 'text', 'text': 'abcdefghijklmno', 'page_idx': 0, 'bbox': [0, 0, 10, 10]},
                  {'type': 'table', 'table_body': '<table><tr><th>状态灯</th><th>含义</th></tr><tr><td>绿灯常亮</td><td>电池已充满</td></tr></table>', 'page_idx': 1}]
        parents, children, parsed = kp.parent_child(document, blocks, len, parent_tokens=40, child_tokens=12, overlap=3)
        self.assertTrue(all(c['token_count'] <= 12 for c in children))
        self.assertTrue(all(p['token_count'] <= 40 for p in parents))
        self.assertEqual({c['parent_chunk_id'] for c in children}, {p['chunk_id'] for p in parents})
        self.assertEqual(parsed[1]['raw']['table_body'], blocks[1]['table_body'])
        self.assertIn('状态灯=绿灯常亮', parsed[1]['text'])
        self.assertIn('含义=电池已充满', parsed[1]['text'])
        self.assertEqual(parsed[1]['page'], 2)
        self.assertIn('bbox', parsed[0]['raw'])

    def test_list_and_code_blocks_keep_searchable_text(self):
        blocks = [{'type': 'list', 'list_items': ['第一步', '第二步'], 'page_idx': 0},
                  {'type': 'code', 'code_body': 'robot.stop()', 'page_idx': 0}]
        _, children, parsed = kp.parent_child({'id': 'D', 'name': 'manual.pdf'}, blocks, len)
        self.assertIn('第一步', children[0]['chunk_text'])
        self.assertIn('robot.stop()', parsed[1]['text'])

    def test_configuration_changes_identity_for_same_sources(self):
        a = kp.version_identity({'D': 'pdf-sha'}, {**kp.CONFIG, 'dimension': 1024})
        b = kp.version_identity({'D': 'pdf-sha'}, {**kp.CONFIG, 'dimension': 512})
        self.assertNotEqual(a, b)

    def test_parent_expand_deduplicates_and_retains_child_evidence(self):
        parents = [{'chunk_id': 'P1', 'chunk_text': '完整上下文', 'document_id': 'D', 'page_start': 1, 'page_end': 2}, {'chunk_id': 'P2', 'chunk_text': '另一上下文', 'document_id': 'D', 'page_start': 3, 'page_end': 3}]
        hits = [{'chunk_id': 'C1', 'parent_chunk_id': 'P1', 'content': '小块1', 'score': .9}, {'chunk_id': 'C2', 'parent_chunk_id': 'P1', 'content': '小块2', 'score': .8}, {'chunk_id': 'C3', 'parent_chunk_id': 'P2', 'content': '小块3', 'score': .7}]
        result = kp.expand_parents(hits, parents, 1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['content'], '完整上下文')
        self.assertEqual(result[0]['matched_child_ids'], ['C1', 'C2'])
        self.assertEqual(result[0]['child_content'], '小块1')
        with self.assertRaises(ValueError): kp.expand_parents(hits, [], 4)

    def test_remote_embedding_rejects_wrong_dimension(self):
        provider = kp.AlibabaProvider({'DASHSCOPE_API_KEY': 'fixture', 'DASHSCOPE_BASE_URL': 'https://fixture.invalid'})
        with patch.object(provider, '_post', return_value={'data': [{'index': 0, 'embedding': [1, 2]}]}):
            with self.assertRaises(ValueError): provider.embed(['input'], 3)

    def test_remote_rerank_maps_indices_and_rejects_duplicate_indices(self):
        provider = kp.AlibabaProvider({})
        hits = [{'chunk_id': 'C1', 'content': 'first'}, {'chunk_id': 'C2', 'content': 'second'}]
        with patch.object(provider, '_post', return_value={'results': [{'index': 0, 'relevance_score': .2}, {'index': 1, 'relevance_score': .9}]}):
            self.assertEqual([h['chunk_id'] for h in provider.rerank('query', hits)], ['C2', 'C1'])
        with patch.object(provider, '_post', return_value={'results': [{'index': 0, 'relevance_score': .2}, {'index': 0, 'relevance_score': .9}]}):
            with self.assertRaises(ValueError): provider.rerank('query', hits)

    def test_restart_reports_interrupted_operation_without_switching_index(self):
        from app.corpus_management import CorpusManager
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); active = root/'index'; active.mkdir()
            (active/'manifest.json').write_text('{"legacy":true}')
            operations = root/'corpus_operations'; operations.mkdir()
            (operations/'CORP-test.json').write_text(json.dumps({'id': 'CORP-test', 'status': 'running', 'stage': 'embedding'}))
            result = CorpusManager(None, index_dir=active, knowledge_pipeline=True).operation('CORP-test')
            self.assertEqual(result['status'], 'interrupted')
            self.assertEqual(result['stage'], 'embedding')
            self.assertEqual(json.loads((active/'manifest.json').read_text()), {'legacy': True})

    def test_failed_build_preserves_active_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); active = root/'index'; active.mkdir(); (active/'manifest.json').write_text('{"legacy":true}')
            pipeline = kp.KnowledgePipeline(active, None)
            with self.assertRaises(Exception): pipeline.build([], {})
            self.assertEqual(json.loads((active/'manifest.json').read_text()), {'legacy': True})

class BundleTests(unittest.TestCase):
    def test_new_bundle_validates_parent_integrity_and_retains_legacy(self):
        import pymupdf
        from app.full_text import validate_bundle, search_full_text
        from app.corpus import CorpusStore
        from app.retrieval import VectorRetriever
        class Parser:
            def parse(self, path, identifier):
                return [{'type': 'text', 'text': '机器人电池操作说明。' * 110, 'page_idx': 0}], b'fixture-only-archive'
        class Embedder:
            def embed(self, texts, dimension):
                rng = np.random.default_rng(7)
                values = rng.random((len(texts), dimension), dtype=np.float32)
                return values / np.linalg.norm(values, axis=1)[:, None]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); pdf = pymupdf.open(); pdf.new_page(); pdf.save(root/'manual.pdf'); pdf.close()
            active = root/'index'; active.mkdir(); (active/'manifest.json').write_text('{"legacy":true}')
            corpus = CorpusStore(active); pipeline = kp.KnowledgePipeline(active, VectorRetriever(corpus))
            doc = {'id': 'D', 'name': 'manual.pdf', '_source_path': str(root/'manual.pdf')}
            staging, identifier = pipeline.build([doc], {}, parser=Parser(), embedder=Embedder(), counter=len)
            bundle = validate_bundle(staging)
            self.assertEqual(bundle['manifest']['embedding_model'], 'text-embedding-v4')
            full_text = json.loads((staging/'full_text.json').read_text())
            matches = search_full_text('机器人电池', full_text)['matches']
            self.assertTrue(matches)
            self.assertEqual(matches[0]['parser'], 'MinerU/vlm')
            retriever = VectorRetriever(CorpusStore(staging))
            from app.policy import DEFAULT_PIPELINE_CONFIG
            def remote_response(provider, path, payload):
                if 'embeddings' in path:
                    return {'data': [{'index': 0, 'embedding': [1.] * 1024}]}
                return {'results': [{'index': i, 'relevance_score': 1 - i * .01} for i in reversed(range(len(payload['documents'])))]}
            with patch.object(kp.AlibabaProvider, '_post', remote_response):
                trace = {}
                hits = retriever.retrieve('机器人电池', {**DEFAULT_PIPELINE_CONFIG, 'knowledge_identity': bundle['manifest']['knowledge_identity']}, trace=trace)
                self.assertTrue(hits)
                self.assertEqual(len({h['parent_chunk_id'] for h in hits}), len(hits))
                self.assertTrue(all(h['matched_child_ids'] for h in hits))
                self.assertTrue(retriever.full_text_probe('机器人电池')['matches'])
                from app.retrieval import RetrievalUnavailable
                with self.assertRaises(RetrievalUnavailable):
                    retriever.retrieve('机器人电池', {**DEFAULT_PIPELINE_CONFIG, 'knowledge_identity': {'pipeline_version_id': 'another'}})
                from app.ai_service import AiService
                self.assertEqual(AiService(None, CorpusStore(staging), None, True).negative_topic_embedding('电池').shape, (1024,))
            with self.assertRaises(RuntimeError):
                pipeline.activate(staging, identifier, after_activate=lambda: (_ for _ in ()).throw(RuntimeError('fixture activation failure')))
            self.assertEqual(json.loads((active/'manifest.json').read_text()), {'legacy': True})
            self.assertFalse((root/'legacy_index.json').exists())
            pipeline.activate(root/'index_versions'/identifier, identifier+'-retry')
            self.assertEqual(json.loads(Path(json.loads((root/'legacy_index.json').read_text())['path']).joinpath('manifest.json').read_text()), {'legacy': True})
            parent_file = active/'parents.json'
            parent_file.write_text('[]')
            with self.assertRaises(ValueError): validate_bundle(active)

class RoutingTests(unittest.TestCase):
    def test_failed_old_generation_does_not_block_new_corpus(self):
        from app.governance import GovernanceStore
        with tempfile.TemporaryDirectory() as directory:
            store = GovernanceStore(Path(directory)/'demo.db')
            with patch('app.corpus.current_manifest', return_value={'sources': {'D': 'old'}}):
                old = store.start_generation_run('fixture')
            with store.connection() as connection:
                connection.execute("UPDATE golden_generation_runs SET status='needs_regeneration' WHERE id=?", (old,))
            with patch('app.corpus.current_manifest', return_value={'sources': {'D': 'new'}}):
                new = store.start_generation_run('fixture', 'full')
                with store.connection() as connection:
                    connection.execute("UPDATE golden_generation_runs SET status='needs_regeneration' WHERE id=?", (new,))
                with self.assertRaises(ValueError): store.start_generation_run('fixture', 'full')
            self.assertEqual(store.generation_run(old)['status'], 'needs_regeneration')

    def test_legacy_and_new_answers_resolve_distinct_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); active = root/'index'; old = root/'index_versions'/'old'; new = root/'index_versions'/'new'
            old.mkdir(parents=True); new.mkdir(); active.symlink_to(new, target_is_directory=True)
            (old/'manifest.json').write_text(json.dumps({'sources': {'D': 'same'}}))
            identity = {'pipeline_version_id': 'new', 'corpus_snapshot_id': 'new-corpus', 'sources': {'D': 'same'}}
            (new/'manifest.json').write_text(json.dumps({'knowledge_identity': identity}))
            (root/'legacy_index.json').write_text(json.dumps({'path': str(old)}))
            self.assertEqual(kp.index_for_config(active, {}).resolve(), old.resolve())
            self.assertEqual(kp.index_for_config(active, {'knowledge_identity': identity}).resolve(), new.resolve())
            with self.assertRaises(ValueError): kp.index_for_config(active, {'knowledge_identity': {'pipeline_version_id': 'unknown'}})
