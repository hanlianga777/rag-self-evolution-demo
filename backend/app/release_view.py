"""Read-only release checks and signatures from saved evaluation records."""
import json
from .agent126c import VERSIONS
from .corpus import current_manifest, manifest_identity
from .policy import CANDIDATE_QUALIFICATION_VERSION, LEGACY_CANDIDATE_QUALIFICATION_VERSION, validate_candidate_config
from .rules import QUALIFICATION

LABELS = ['上线门槛全部通过', '逐题回归满足资格要求', '所有参数都在白名单范围内', '配置快照完整', '知识库版本和评测时一致']

def release_review_view(store, candidate_id=None):
    candidate = store.candidate(candidate_id) if candidate_id else None
    result = (candidate or {}).get('result', {})
    run_id = result.get('evaluation_run_id')
    run = store.evaluation_run(run_id) if run_id else None
    snapshot = json.loads(run['dataset_snapshot_json']) if run else {}
    regression = result.get('regression', {})
    critical = regression.get('new_critical_failures')
    qualification = result.get('qualification', {})
    regression_ok = (critical <= QUALIFICATION['max_new_critical'] if type(critical) is int
                     else regression.get('checks', {}).get('critical'))
    version = qualification.get('rule_version')
    if version in {CANDIDATE_QUALIFICATION_VERSION, LEGACY_CANDIDATE_QUALIFICATION_VERSION}:
        checks = qualification.get('checks', {})
        required = ['regression', 'comparison_complete', 'zero_new_failures']
        if qualification.get('performance_gate_repair'):
            required.append('no_safety_violation')
        else:
            required.append('at_least_one_fixed')
        if version == CANDIDATE_QUALIFICATION_VERSION:
            required.append('no_severe_risk')
            if (candidate or {}).get('reasoning', {}).get('candidate_label') == 'D':
                required.append('winner_non_regression')
        regression_ok = all(checks.get(key) is True for key in required)
    if version in VERSIONS:
        regression_ok = qualification.get('qualified') is True
    fingerprint = snapshot.get('corpus_fingerprint')
    config = (candidate or {}).get('config')
    checks = [result.get('gates', {}).get('passed'),
              regression_ok,
              validate_candidate_config(config)['valid'] if config else None,
              bool(run['status'] == 'completed' and run.get('config') and snapshot and run.get('judge') and config and all(run['config'].get(key) == value for key, value in config.items())) if run else None,
              fingerprint == manifest_identity(current_manifest()) if fingerprint else None]
    freeze = snapshot.get('gate1', {})
    gate1 = {'actor': freeze.get('actor'), 'created_at': freeze.get('confirmed_at'), 'decision': 'confirmed'} if freeze.get('status') == 'frozen' else None
    gate2 = store.latest_approval('experiment_report', candidate['experiment_id']) if candidate else None
    gate3 = store.latest_approval('human_release', candidate_id) if candidate else None
    return {'candidate_id': candidate_id, 'checks': [{'label': label, 'ok': value} for label, value in zip(LABELS, checks)], 'gates': [gate1, gate2, gate3]}
