#!/usr/bin/env python3
"""Run backend tests with disposable storage and outbound TCP disabled."""
import os
import json
import shutil
from contextlib import contextmanager, ExitStack
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex


def offline_connect(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6) and True:
        raise RuntimeError('V1.4 offline tests prohibit outbound TCP')
    return _connect(self, address)


def offline_connect_ex(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6) and True:
        raise RuntimeError('V1.4 offline tests prohibit outbound TCP')
    return _connect_ex(self, address)


@contextmanager
def isolated_corpus(directory, *, legacy_fixture=False):
    """Copy persisted assets as offline fixtures before importing the API; never touch source files."""
    from app import corpus, config
    root = Path(directory)
    paths = {'INDEX_DIR': root / 'data/index', 'DOCUMENTS_DIR': root / 'documents', 'UPLOADS_DIR': root / 'data/uploads'}
    for name, destination in paths.items():
        source = getattr(corpus, name)
        if name == 'INDEX_DIR' and legacy_fixture:
            source = Path(json.loads((ROOT / 'backend/data/legacy_index.json').read_text())['path'])
            print('Offline test fixture: isolated copy of persisted Legacy index; not Provider evidence', file=sys.stderr)
        if source.exists():
            shutil.copytree(source, destination, symlinks=False)
        else:
            destination.mkdir(parents=True)
    state = ROOT / 'backend/data/corpus_state.json'
    if state.exists() and not legacy_fixture:
        shutil.copy2(state, root / 'data/corpus_state.json')
    env_file = root / '.env'
    env_file.write_text('')
    original_load = config.load_values
    def isolated_values(env=None, env_file=None):
        return original_load(env, env_file if env_file is not None else root / '.env')
    with ExitStack() as stack:
        stack.enter_context(patch.object(config, 'load_values', isolated_values))
        for name, destination in paths.items():
            stack.enter_context(patch.object(corpus, name, destination))
        stack.enter_context(patch.object(corpus.CorpusStore.__init__, '__defaults__', (paths['INDEX_DIR'],)))
        from app import corpus_management, build_index, retrieval
        for module in (corpus_management, build_index, retrieval):
            for name, destination in paths.items():
                if hasattr(module, name):
                    stack.enter_context(patch.object(module, name, destination))
        stack.enter_context(patch.object(corpus_management.CorpusManager.__init__, '__kwdefaults__', {**corpus_management.CorpusManager.__init__.__kwdefaults__, 'index_dir': paths['INDEX_DIR'], 'documents_dir': paths['DOCUMENTS_DIR'], 'uploads_dir': paths['UPLOADS_DIR']}))
        stack.enter_context(patch.object(build_index.build_index, '__kwdefaults__', {**build_index.build_index.__kwdefaults__, 'index_dir': paths['INDEX_DIR']}))
        stack.enter_context(patch.object(retrieval.VectorRetriever.__init__, '__defaults__', (paths['INDEX_DIR'],)))
        yield paths


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT / 'backend'))
    with tempfile.TemporaryDirectory(prefix='rag-v14-offline-') as directory, patch.dict(os.environ, {
        'RAG_DEMO_DB_PATH': str(Path(directory) / 'test.db'),
        'RAG_FORCE_MOCK': '1', 'DEEPSEEK_API_KEY': '', 'DASHSCOPE_API_KEY': '', 'MINERU_API_KEY': '',
        'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
    }), patch.object(socket.socket, 'connect', offline_connect), patch.object(socket.socket, 'connect_ex', offline_connect_ex), isolated_corpus(directory, legacy_fixture=True):
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'backend/tests'))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
