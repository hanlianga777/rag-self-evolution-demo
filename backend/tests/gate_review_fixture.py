"""Local review records for disposable Gate tests."""
from app import policy


def gate_reviews(tmp_path, monkeypatch, experiment_id, stage):
    monkeypatch.setattr(policy, 'GATE_REVIEW_REPO_ROOT', tmp_path, raising=False)
    directory = tmp_path / '指挥' / '互审'
    directory.mkdir(parents=True, exist_ok=True)
    reviews = {'experiment_id': experiment_id, 'stage': stage}
    for reviewer in ('claude', 'gpt'):
        path = directory / f'{experiment_id}-{stage}-{reviewer}.md'
        path.write_text(f'# {experiment_id} · Gate {stage[-1]}\n\n结论：通过\n', encoding='utf-8')
        reviews[reviewer] = {'verdict': '通过', 'record': path.relative_to(tmp_path).as_posix()}
    return reviews
