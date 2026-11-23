"""Read only the verdicts from task 115's private diagnostic checkpoints."""

import json
import re
from pathlib import Path

CHECKPOINTS = Path(__file__).resolve().parents[2] / 'output' / 'task115'
TRIAL_FILE = re.compile(r'(?:baseline|e2|e3)-(Q\d+)-([1-3])\.json')


def saved_stability_retest(directory=CHECKPOINTS):
    runs, seen, inconsistent = {}, set(), set()
    for path in sorted(directory.glob('*.json')):
        match = TRIAL_FILE.fullmatch(path.name)
        if not match:
            continue
        try:
            sample = json.loads(path.read_text(encoding='utf-8'))
            run_id, identity, diagnostic = (sample[key] for key in ('source_run_id', 'evaluation_identity', 'id'))
            question, = sample['questions']
            trial, = question['trials']
            passed = trial['passed']
            if (sample['repetitions'] != 1 or question['display_question_id'] != match[1]
                    or not run_id.startswith('EVAL-') or not diagnostic.startswith('DIAG-')
                    or not isinstance(identity, str) or not identity or diagnostic in seen
                    or (passed is not None and type(passed) is not bool)):
                continue
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
        seen.add(diagnostic)
        run = runs.setdefault(run_id, {'identity': identity, 'questions': {}})
        if identity != run['identity']:
            inconsistent.add(run_id)
            continue
        samples = run['questions'].setdefault(match[1], [None] * 3)
        samples[int(match[2]) - 1] = passed
    return {'runs': {key: run for key, run in runs.items() if key not in inconsistent}}
