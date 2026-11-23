"""Read the saved independent audit for the exact evaluation case it reviewed."""

import csv
import re
from pathlib import Path


REPORT_DIR = Path(__file__).resolve().parents[2] / "指挥" / "报告"
AUDIT_TABLE = "106-否定性说法审计表.csv"


def independent_case_notes(run_id, dataset_id, question, case):
    display_id = question.get("display_id")
    passed = case.get("passed")
    answer = case.get("model_answer")
    if not display_id or type(passed) is not bool or not isinstance(answer, str):
        return []

    try:
        report = (REPORT_DIR / "106.md").read_text(encoding="utf-8")
        dataset = re.search(r"题卷快照一致，版本为 `(GD-\d+)`", report)
        runs = {evaluation: label for label, evaluation in
                re.findall(r"^\| (Baseline|[ABC]) \| `(EVAL-\d+)` \|", report, re.MULTILINE)}
        if not dataset or dataset.group(1) != dataset_id or run_id not in runs:
            return []

        verdict = "PASS" if passed else "FAIL"
        with (REPORT_DIR / AUDIT_TABLE).open(encoding="utf-8-sig", newline="") as source:
            return list(dict.fromkeys(
                row["结论"] for row in csv.DictReader(source)
                if row.get("运行") == runs[run_id] and row.get("题号") == display_id
                and row.get("正式对错") == verdict and row.get("结论")
                and row.get("否定句原文") and row["否定句原文"] in answer
            ))
    except (OSError, UnicodeError, csv.Error):
        return []
