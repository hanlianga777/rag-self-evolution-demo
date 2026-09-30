#!/usr/bin/env python3
"""Offline compatible sidecar upgrade. Default stages only; --activate explicitly swaps the bundle."""
import argparse
import json
import os
import sys
import socket
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
from app.corpus import CorpusStore, INDEX_DIR, DOCUMENTS_DIR, UPLOADS_DIR
from app.corpus_management import CorpusManager
from app.retrieval import VectorRetriever

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index-dir', type=Path, default=INDEX_DIR)
    parser.add_argument('--activate', action='store_true')
    args = parser.parse_args()
    def offline_connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError('Full-text supplementation prohibits network/model downloads')
        return original_connect(sock, address)
    original_connect = socket.socket.connect
    socket.socket.connect = offline_connect
    socket.socket.connect_ex = offline_connect
    corpus = CorpusStore(args.index_dir)
    manager = CorpusManager(VectorRetriever(corpus), index_dir=args.index_dir, documents_dir=DOCUMENTS_DIR, uploads_dir=UPLOADS_DIR)
    print(json.dumps(manager.supplement_full_text(activate=args.activate), ensure_ascii=False, indent=2))
