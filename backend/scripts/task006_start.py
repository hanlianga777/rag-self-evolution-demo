#!/usr/bin/env python3
"""Prepare task006 unchanged candidates; start only through the persistent demo."""
import argparse
import hashlib
import json

from task005b_freeze import DATA, ROOT, api, build_candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', action='store_true', help='Create a fresh machine-check run and start Probe/QC, without confirmation or freeze')
    args = parser.parse_args()
    path = DATA / '定稿50.csv'
    candidates = build_candidates(path, ROOT / 'backend/data/index')
    if not args.start:
        print(json.dumps({'prepared': len(candidates), 'provider_calls': 0})); return
    imported = api('/api/governance/reviewed-import', {
        'candidates': candidates, 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'source': '任务005修订稿/定稿', 'review_note': '任务006：同内容重走Probe、QC；本次不确认、不冻结',
        'machine_checks': True})
    # Print the persisted identity before launch so a transport interruption never
    # requires importing again just to discover which run owns the request.
    print(json.dumps(imported, ensure_ascii=False), flush=True)
    started = api('/api/governance/generation-runs/'+imported['generation_run_id']+'/rerun-quality', {})
    print(json.dumps(started, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
