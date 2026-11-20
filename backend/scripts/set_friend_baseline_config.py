"""把当前生产配置换成朋友式朴素默认配置（用户 2026-11-18 决定），旧版本归档保留，不删。

默认 dry-run，只打印将要写入的配置；加 --apply 才写。不调用任何付费接口。

PYTHONPATH=backend python3 backend/scripts/set_friend_baseline_config.py [--apply]
"""
import argparse
import json
import os
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    from app.config import load_values
    values = load_values()
    database = args.database or Path(values.get('RAG_DEMO_DB_PATH') or Path(__file__).resolve().parents[1] / 'data/demo.db')
    os.environ['RAG_DEMO_DB_PATH'] = str(database.resolve())
    os.environ['RAG_SAFE_START'] = '1'
    from app.main import store
    from app.policy import FRIEND_BASELINE_CONFIG
    from app.baseline_chain import restore_initial_config
    active = store.active_production()
    print(json.dumps({'dry_run': not args.apply, 'active_version': (active or {}).get('id'), 'active_config': (active or {}).get('config'),
                      'new_config': FRIEND_BASELINE_CONFIG, 'env_BASELINE_THINKING': values.get('BASELINE_THINKING', '(未设置，默认 max)')},
                     ensure_ascii=False, indent=2))
    if values.get('BASELINE_THINKING') != 'high':
        print('提醒：.env 里 BASELINE_THINKING 不是 high，Baseline 会按它的值请求。')
    if args.apply:
        saved = restore_initial_config(store, FRIEND_BASELINE_CONFIG, audit_note='用户 2026-11-18 决定 Baseline 改用朋友式朴素默认配置')
        print(json.dumps({'applied_version': saved['id'], 'config': saved['config']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
