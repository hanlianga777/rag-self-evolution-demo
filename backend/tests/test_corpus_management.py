"""Fixture-only PDF operations; never touch the user's index or SQLite."""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import numpy as np
import pymupdf

from app import corpus
from api_fixture import main
from app.corpus_management import CorpusManager
from app.build_index import build_index
from app.full_text import checksum, write_full_text


class CorpusManagementTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.documents = root / "documents"
        self.documents.mkdir()
        (self.documents / "base.pdf").write_bytes(b"%PDF-1.4 fixture base")
        self.uploads = root / "data" / "uploads"
        self.index = root / "data" / "index"
        self.index.mkdir(parents=True)
        (self.index / "faiss.index").write_bytes(b"old index")
        self.retriever = SimpleNamespace(_index=object(), _model=object())
        self.manager = CorpusManager(self.retriever, index_dir=self.index, documents_dir=self.documents, uploads_dir=self.uploads)
        self.patch_docs = patch.object(corpus, "DOCUMENTS_DIR", self.documents)
        self.patch_uploads = patch.object(corpus, "UPLOADS_DIR", self.uploads)
        self.patch_docs.start()
        self.patch_uploads.start()
        self.addCleanup(self.patch_docs.stop)
        self.addCleanup(self.patch_uploads.stop)

    def finish(self, operation):
        for _ in range(100):
            value = self.manager.operation(operation["id"])
            if value["status"] != "running":
                return value
            time.sleep(.01)
        self.fail("fixture operation did not finish")

    @staticmethod
    def fake_build(*, catalog, index_dir, on_progress, **_kwargs):
        index_dir.mkdir(parents=True)
        on_progress("parse", 0, len(catalog))
        on_progress("chunk", len(catalog), len(catalog))
        on_progress("embedding", 0, len(catalog))
        (index_dir / "documents.json").write_text(json.dumps([{**{key: value for key, value in item.items() if key != "_source_path"}, "status": "Indexed", "chunks": 1, "pages": 1, "source_fingerprint": corpus.source_fingerprint(item)} for item in catalog]))
        (index_dir / "chunks.json").write_text(json.dumps([{"document_id": item["id"], "chunk_id": f"{item['id']}-1", "chunk_text": "fixture"} for item in catalog]))
        (index_dir / "manifest.json").write_text(json.dumps(corpus.current_manifest(catalog)))
        import faiss
        index = faiss.IndexFlatIP(2)
        index.add(np.asarray([[1., 0.]] * len(catalog), dtype='float32').reshape(-1, 2))
        faiss.write_index(index, str(index_dir / 'faiss.index'))
        documents = json.loads((index_dir / 'documents.json').read_text())
        pages = [{'document_id': doc['id'], 'page': 1, 'text': 'fixture', 'parser': 'fixture', 'text_checksum': checksum(b'fixture'), 'source_fingerprint': doc['source_fingerprint']} for doc in documents]
        write_full_text(index_dir, corpus.current_manifest(catalog), documents, pages)
        on_progress("index", len(catalog), len(catalog))
        return 0

    def test_upload_then_delete_changes_only_active_corpus(self):
        with patch("app.corpus_management.build_index", side_effect=self.fake_build):
            uploaded = self.finish(self.manager.start("upload", filename="new.pdf", data=b"%PDF-1.4 fixture new"))
            self.assertEqual(uploaded["status"], "completed")
            self.assertTrue((self.uploads / "new.pdf").exists())
            self.assertEqual(len(json.loads((self.index / "documents.json").read_text())), 2)
            self.assertIsNone(self.retriever._index)
            self.assertTrue(self.manager.state()["changed_at"])
            deleted = self.finish(self.manager.start("delete", document_id="DOC-" + __import__("hashlib").sha256(b"new.pdf").hexdigest()[:12]))
            self.assertEqual(deleted["status"], "completed")
            self.assertFalse((self.uploads / "new.pdf").exists())
            self.assertEqual(len(json.loads((self.index / "documents.json").read_text())), 1)
            self.assertEqual(len(list((self.index.parent / "archived_documents").glob("*new.pdf"))), 1)

    def test_failed_build_keeps_old_index_and_source(self):
        def fail(*, index_dir, **_kwargs):
            index_dir.mkdir(parents=True)
            (index_dir / "documents.json").write_text('[]')
            return 1
        with patch("app.corpus_management.build_index", side_effect=fail):
            result = self.finish(self.manager.start("upload", filename="bad.pdf", data=b"%PDF-1.4 fixture"))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stage"], "build")
        self.assertEqual((self.index / "faiss.index").read_bytes(), b"old index")
        self.assertFalse((self.uploads / "bad.pdf").exists())
        self.assertEqual(self.manager.state(), {})

    def test_old_snapshot_cannot_start_new_baseline_after_corpus_change(self):
        from fastapi import HTTPException
        with patch.object(main.corpus_manager, "state", return_value={"changed_at": "fixture"}), patch.object(main.store, "dataset_snapshots", return_value=[{"id": "OLD", "snapshot": {"id": "OLD"}}]):
            with self.assertRaises(HTTPException) as caught:
                main.start_evaluation()
        self.assertEqual(caught.exception.status_code, 409)
        self.assertIn("Corpus 已变化", caught.exception.detail)

    def test_pdf_fixture_runs_parse_chunk_embedding_and_index(self):
        source = self.documents / "fixture.pdf"
        pdf = pymupdf.open()
        page = pdf.new_page()
        for line in range(5):
            page.insert_text((40, 60 + line * 22), "Before operation check the battery and emergency stop button.")
        pdf.save(source)
        tokenizer = SimpleNamespace(encode=lambda text, add_special_tokens=False: list(text))
        model = SimpleNamespace(encode=lambda texts, **_kwargs: np.asarray([[1., 0., 0., 0.] for _ in texts], dtype="float32"))
        modules = {}
        for name, values in {
            "rapidocr": {"RapidOCR": lambda: object()},
            "sentence_transformers": {"SentenceTransformer": lambda _name: model},
            "transformers": {"AutoTokenizer": SimpleNamespace(from_pretrained=lambda _name: tokenizer)},
        }.items():
            module = ModuleType(name)
            module.__dict__.update(values)
            modules[name] = module
        staged = self.index.parent / "fixture_index"
        with patch.dict(sys.modules, modules):
            result = build_index(force=True, catalog=[{"id": "fixture", "name": source.name, "chunk_prefix": "fixture", "_source_path": str(source)}], index_dir=staged, strict=True)
        self.assertEqual(result, 0)
        self.assertEqual(json.loads((staged / "documents.json").read_text())[0]["status"], "Indexed")
        self.assertTrue(json.loads((staged / "chunks.json").read_text()))
        self.assertTrue((staged / "faiss.index").exists())
        full_text = json.loads((staged / 'full_text.json').read_text())
        self.assertEqual(full_text['pages'][0]['text'], pymupdf.open(source)[0].get_text('text').strip())
        self.assertEqual(full_text['coverage']['status'], 'complete')
        self.assertEqual(full_text['pages'][0]['page'], 1)
        self.assertEqual(full_text['pages'][0]['parser'], 'PyMuPDF')

    def test_http_upload_and_delete_dispatch_user_actions(self):
        from fastapi.testclient import TestClient
        client = TestClient(main.app)
        operation = {"id": "CORP-fixture", "status": "running", "stage": "queued"}
        with patch.object(main, "require_idle_corpus"), patch.object(main.corpus_manager, "start", return_value=operation) as start, patch.object(main.corpus, "documents", return_value=[{"id": "fixture"}]):
            uploaded = client.post("/api/documents?filename=fixture.pdf", content=b"%PDF-1.4 fixture", headers={"Content-Type": "application/pdf", "Origin": "http://localhost:5174"})
            self.assertEqual(uploaded.status_code, 202)
            start.assert_called_with("upload", filename="fixture.pdf", data=b"%PDF-1.4 fixture")
            deleted = client.delete("/api/documents/fixture", headers={"Origin": "http://localhost:5174"})
            self.assertEqual(deleted.status_code, 202)
            start.assert_called_with("delete", document_id="fixture")
