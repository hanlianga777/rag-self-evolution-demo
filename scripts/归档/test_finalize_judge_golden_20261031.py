import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import finalize_judge_golden_20261031 as finalizer


class FinalizationSafetyTests(unittest.TestCase):
    def test_missing_execution_inputs_stop_without_database_or_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output'
            result = subprocess.run([sys.executable, finalizer.__file__, '--execute', '--output', str(output)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('requires separate authorization, delegation and independent reviews', result.stderr)
            self.assertFalse(output.exists())

    def test_history_guard_rejects_overwrite_extra_qc_and_unrelated_question_change(self):
        with tempfile.TemporaryDirectory() as directory:
            old, new = [Path(directory) / name for name in ('old.db', 'new.db')]
            with sqlite3.connect(old) as db:
                for table in ('review_events', 'approvals', 'dataset_versions', 'qc_results', 'questions'):
                    db.execute(f'CREATE TABLE {table}(id text, value text)')
                    db.execute(f'INSERT INTO {table} VALUES (?,?)', ('kept', 'original'))
                db.execute("INSERT INTO questions VALUES ('target','original')")
            finalizer.common.backup_database(old, new)
            finalizer.protected_history(old, new, ['target'], frozen=False)
            with sqlite3.connect(new) as db:
                for table, count in [('review_events', 3), ('approvals', 3), ('dataset_versions', 1)]:
                    for index in range(count):
                        db.execute(f'INSERT INTO {table} VALUES (?,?)', (str(index), 'added'))
                db.execute("UPDATE questions SET value='reviewed' WHERE id='target'")
            finalizer.protected_history(old, new, ['target'], frozen=True)
            for statement in ["UPDATE questions SET value='altered' WHERE id='kept'",
                              "UPDATE review_events SET value='altered' WHERE id='kept'",
                              "INSERT INTO qc_results VALUES ('extra','forbidden')"]:
                with sqlite3.connect(new) as db:
                    db.execute('BEGIN')
                    db.execute(statement)
                    db.commit()
                with self.assertRaisesRegex(RuntimeError, 'Protected history changed'):
                    finalizer.protected_history(old, new, ['target'], frozen=True)
                with sqlite3.connect(new) as db:
                    db.execute("UPDATE questions SET value='original' WHERE id='kept'")
                    db.execute("UPDATE review_events SET value='original' WHERE id='kept'")
                    db.execute("DELETE FROM qc_results WHERE id='extra'")

    def test_changed_reviewed_plan_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.json'
            plan = {'question_ids': ['bound']}
            plan['plan_sha256'] = finalizer.common.digest(plan)
            path.write_text(json.dumps(plan))
            self.assertEqual(finalizer.checked_plan(path), plan)
            plan['question_ids'] = ['changed']
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'Reviewed plan changed'):
                finalizer.checked_plan(path)


if __name__ == '__main__':
    unittest.main()
