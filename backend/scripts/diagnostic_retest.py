#!/usr/bin/env python3
"""Run independent diagnostic trials with the selected formal run's config and Judge."""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai_service import AiService
from app.config import load_settings
from app.corpus import CorpusStore
from app.evaluation import EvaluationRunner
from app.governance import GovernanceStore
from app.providers import DeepSeekProvider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_id', help='Baseline or Candidate Sandbox EVAL ID')
    parser.add_argument('question_ids', nargs='+', help='Frozen IDs or display question numbers')
    parser.add_argument('-n', '--repetitions', type=int, default=3)
    parser.add_argument('--db', type=Path)
    parser.add_argument('--execute', required=True, action='store_true', help='Send fresh provider requests')
    args = parser.parse_args()
    store = GovernanceStore(args.db, read_only=True)
    runtime = AiService(store, CorpusStore(), DeepSeekProvider(load_settings()), os.getenv('RAG_FORCE_MOCK') == '1')
    if not runtime.live_enabled:
        parser.error('复测需要可用的 Provider 配置')
    result = EvaluationRunner(store, runtime).diagnostic_retest(args.run_id, args.question_ids, repetitions=args.repetitions)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(any(question['unknown'] for question in result['questions']))


if __name__ == '__main__':
    sys.exit(main())
