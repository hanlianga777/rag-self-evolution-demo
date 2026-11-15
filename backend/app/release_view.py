"""Read-only release checks and signatures from saved evaluation records."""
import json
from .corpus import current_manifest, manifest_identity
from .policy import validate_candidate_config

LABELS = ['上线门槛全部通过', '回归检查没有严重的新增 Bad Case', '所有参数都在白名单范围内', '配置快照完整', '知识库版本和评测时一致']

def release_review_view(store, candidate_id=None):
    candidate = store.candidate(candidate_id) if candidate_id else None
    result = (candidate or {}).get('result', {})
    run_id = result.get('evaluation_run_id')
    run = store.evaluation_run(run_id) if run_id else None
    snapshot = json.loads(run['dataset_snapshot_json']) if run else {}
    regression = result.get('regression', {})
    critical = regression.get('new_critical_failures')
    fingerprint = snapshot.get('corpus_fingerprint')
    config = (candidate or {}).get('config')
    checks = [result.get('gates', {}).get('passed'),
              critical == 0 if isinstance(critical, int) else regression.get('checks', {}).get('critical'),
              validate_candidate_config(config)['valid'] if config else None,
              bool(run['status'] == 'completed' and run.get('config') and snapshot and run.get('judge') and config and all(run['config'].get(key) == value for key, value in config.items())) if run else None,
              fingerprint == manifest_identity(current_manifest()) if fingerprint else None]
    freeze = snapshot.get('gate1', {})
    gate1 = {'actor': freeze.get('actor'), 'created_at': freeze.get('confirmed_at'), 'decision': 'confirmed'} if freeze.get('status') == 'frozen' else None
    gate2 = store.latest_approval('experiment_report', candidate['experiment_id']) if candidate else None
    gate3 = store.latest_approval('human_release', candidate_id) if candidate else None
    return {'candidate_id': candidate_id, 'checks': [{'label': label, 'ok': value} for label, value in zip(LABELS, checks)], 'gates': [gate1, gate2, gate3]}
