"""Exercise runner cleanup with tiny offline assets, never the business database."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class RunnerCleanupTests(unittest.TestCase):
    def test_cleanup_after_success_failure_and_setup_exception(self):
        for scenario, expected in [('success', 0), ('failure', 1), ('setup_exception', 1)]:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for name in ['scripts', 'backend/documents', 'backend/data/index',
                             'backend/reports', 'backend/tests', 'backend/app', 'temp']:
                    (root / name).mkdir(parents=True, exist_ok=True)
                script = root / 'scripts/verify_self_evolution.py'
                shutil.copyfile(Path(__file__).with_name(script.name), script)
                (root / 'backend/reports/golden_dataset_full_draft.json').write_text('{}')
                (root / 'backend/app/__init__.py').write_text('')
                (root / 'backend/app/governance.py').write_text(
                    'import os\nfrom pathlib import Path\n'
                    "assert Path(os.environ['RAG_DEMO_ENV_PATH']).read_text() == ''\n"
                    "assert Path(os.environ['RAG_DEMO_DB_PATH']).parent.parent == Path(os.environ['TMPDIR'])\n"
                )
                (root / 'backend/tests/test_selected.py').write_text(
                    'import unittest\nclass Selected(unittest.TestCase):\n'
                    f'    def test_selected(self): self.assertTrue({scenario != "failure"})\n'
                )
                if scenario == 'setup_exception':
                    (root / 'backend/data/index').rmdir()
                result = subprocess.run(
                    [sys.executable, '-B', str(script), 'test_selected'],
                    env={**os.environ, 'TMPDIR': str(root / 'temp'), 'PYTHONDONTWRITEBYTECODE': '1'},
                    capture_output=True, text=True, timeout=20,
                )
                self.assertEqual(result.returncode, expected, result.stderr)
                if scenario != 'setup_exception':
                    self.assertIn('TESTS: 1 FAILURES:', result.stdout)
                else:
                    self.assertIn('FileNotFoundError', result.stderr)
                self.assertEqual(list((root / 'temp').iterdir()), [], result.stderr)


if __name__ == '__main__':
    unittest.main()
