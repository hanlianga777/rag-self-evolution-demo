#!/usr/bin/env python3
"""Run all backend tests (or named suites) with disposable data and TCP blocked."""
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'backend/tests')]

def blocked(self,address):
    if self.family in (socket.AF_INET,socket.AF_INET6):raise RuntimeError('offline verification prohibits TCP / Provider calls')
    return original_connect(self,address)

original_connect=socket.socket.connect
if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='rag-agent-offline-') as temp,patch.dict(os.environ,{
        'RAG_DEMO_DB_PATH':temp+'/demo.db','RAG_DEMO_ENV_PATH':temp+'/absent.env',
        'RAG_DEMO_INDEX_DIR':temp+'/index','RAG_DEMO_UPLOADS_DIR':temp+'/uploads',
        'RAG_DIAGNOSTIC_DIR':temp+'/diagnostics','RAG_FORCE_MOCK':'1',
        'DEEPSEEK_API_KEY':'','DASHSCOPE_API_KEY':'','MINERU_API_KEY':'',
        'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1',
    }),patch.object(socket.socket,'connect',blocked),patch.object(socket.socket,'connect_ex',blocked):
        os.chdir(ROOT)
        suite=unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:]) if len(sys.argv)>1 else unittest.defaultTestLoader.discover(str(ROOT/'backend/tests'))
        result=unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
