#!/usr/bin/env python3
"""Run backend tests with disposable storage and outbound TCP disabled."""
import os
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
    if self.family in (socket.AF_INET, socket.AF_INET6) and address[0] not in ('127.0.0.1', '::1', 'localhost'):
        raise RuntimeError('V1.4 offline tests prohibit outbound TCP')
    return _connect(self, address)


def offline_connect_ex(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6) and address[0] not in ('127.0.0.1', '::1', 'localhost'):
        raise RuntimeError('V1.4 offline tests prohibit outbound TCP')
    return _connect_ex(self, address)


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT / 'backend'))
    with tempfile.TemporaryDirectory(prefix='rag-v14-offline-') as directory, patch.dict(os.environ, {
        'RAG_DEMO_DB_PATH': str(Path(directory) / 'test.db'),
        'RAG_FORCE_MOCK': '1', 'DEEPSEEK_API_KEY': '',
        'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
    }), patch.object(socket.socket, 'connect', offline_connect), patch.object(socket.socket, 'connect_ex', offline_connect_ex):
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'backend/tests'))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
