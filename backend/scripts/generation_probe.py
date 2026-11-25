#!/usr/bin/env python3
"""Run generation-only diagnostics and save evidence to the selected experiment."""

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai_service import AiService
from app.config import load_settings
from app.corpus import CorpusStore
from app.evaluation import EvaluationRunner
from app.generation_probe import run_probe
from app.governance import GovernanceStore
from app.providers import DeepSeekProvider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('experiment_id')
    parser.add_argument('base_run_id')
    parser.add_argument('question_ids', nargs='+', help='Frozen IDs or display question numbers')
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--base-key', default='Baseline', help='Baseline or the full Candidate ID in this experiment')
    parser.add_argument('--changes', action='append', type=json.loads, required=True, help='One JSON object per group')
    parser.add_argument('-n', '--repetitions', type=int, default=3)
    parser.add_argument('--execute', required=True, action='store_true', help='Send fresh provider requests and write diagnostic results')
    args = parser.parse_args()
    if not args.db.is_file():
        parser.error('数据库不存在')
    runtime_settings = load_settings()
    store = GovernanceStore(args.db, migrate=False)
    runtime = AiService(store, CorpusStore(), DeepSeekProvider(runtime_settings), os.getenv('RAG_FORCE_MOCK') == '1')
    if not runtime.live_enabled:
        parser.error('生成诊断需要可用的 Provider 配置')
    diagnostics = run_probe(store, EvaluationRunner(store, runtime), args.experiment_id, args.base_run_id,
                            args.changes, args.question_ids, repetitions=args.repetitions, base_key=args.base_key)
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    return int(any(question['unknown'] for result in diagnostics for question in result['questions']))


if __name__ == '__main__':
    sys.exit(main())
