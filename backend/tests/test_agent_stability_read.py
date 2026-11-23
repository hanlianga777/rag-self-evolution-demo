import json

from app.agent_stability_read import saved_stability_retest


def test_diagnostic_read_returns_only_verdicts_from_distinct_saved_trials(tmp_path):
    def save(index, diagnostic_id, passed, identity="identity"):
        (tmp_path / f"e3-Q09-{index}.json").write_text(json.dumps({
            "id": diagnostic_id, "source_run_id": "EVAL-saved", "evaluation_identity": identity, "repetitions": 1,
            "questions": [{"display_question_id": "Q09", "trials": [{"passed": passed, "answer": "private"}]}],
            "usage": ["private"],
        }))

    save(1, "DIAG-1", True)
    save(2, "DIAG-1", False)
    save(3, "DIAG-3", False)
    (tmp_path / "final.json").write_text('{"usage":"private"}')

    assert saved_stability_retest(tmp_path) == {"runs": {
        "EVAL-saved": {"identity": "identity", "questions": {"Q09": [True, None, False]}}
    }}
    assert saved_stability_retest(tmp_path / "missing") == {"runs": {}}

    save(3, "DIAG-3", False, identity="wrong")
    assert saved_stability_retest(tmp_path) == {"runs": {}}
