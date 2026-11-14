from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snapshot = self.root / 'snapshot'
        self.target = self.root / 'target'
        data = self.snapshot / 'backend/data'
        (data / 'index_versions/v1').mkdir(parents=True)
        (data / 'index_versions/v1/test.json').write_text('saved')
        (data / 'index').symlink_to('index_versions/v1')
        entry = data / 'index_versions/v1/test.json'
        manifest = {'roots': ['backend/data'], 'sqlite_online_backups': [],
            'archive_branch': 'snapshot-v1-section-chunking', 'code_commit': 'test',
            'files': [{'path': str(entry.relative_to(self.snapshot)), 'size': 5,
                       'sha256': hashlib.sha256(b'saved').hexdigest()}],
            'symlinks': [{'path': 'backend/data/index', 'target': 'index_versions/v1'}]}
        (self.snapshot / '清单.json').write_text(json.dumps(manifest))
        (self.target / 'backend/data').mkdir(parents=True)
        (self.target / 'backend/data/current').write_text('old')

    def restore(self):
        return subprocess.run(['bash', str(ROOT / 'scripts/restore_snapshot.sh'), str(self.snapshot),
            '--target-root', str(self.target)], capture_output=True, text=True, timeout=20)

    def test_whole_directory_restore_and_two_safety_copies(self):
        for _ in range(3):
            result = self.restore()
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.target / 'backend/data/current').exists())
        self.assertEqual((self.target / 'backend/data/index/test.json').read_text(), 'saved')
        self.assertEqual(len(list((self.target / 'backend').glob('data.before-restore-*'))), 2)

    def test_corruption_does_not_rename_existing_data(self):
        (self.snapshot / 'backend/data/index/test.json').write_text('broken')
        result = self.restore()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.target / 'backend/data/current').read_text(), 'old')
        self.assertFalse(list((self.target / 'backend').glob('data.before-restore-*')))

    def test_open_data_is_not_replaced(self):
        with (self.target / 'backend/data/current').open():
            result = self.restore()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('当前数据仍被进程打开', result.stderr)
        self.assertEqual((self.target / 'backend/data/current').read_text(), 'old')


class ReporterTests(unittest.TestCase):
    def run_worker(self, *, locked=False, fail_add=False, unchanged=False, fail_pull=False, detached=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ['scripts', '指挥/自动值班', 'backend/data', 'backend/app', '.git', 'bin']:
                (root / name).mkdir(parents=True)
            shutil.copy2(ROOT / 'scripts/export_run_status.py', root / 'scripts/export_run_status.py')
            for name in ['policy.py', 'governance.py', 'corpus.py']:
                shutil.copy2(ROOT / 'backend/app' / name, root / 'backend/app' / name)
            script = root / '指挥/自动值班/状态播报.sh'
            shutil.copy2(ROOT / '指挥/自动值班/状态播报.sh', script)
            with closing(sqlite3.connect(root / 'backend/data/demo.db')) as db:
                db.execute('CREATE TABLE empty(id TEXT)')
            if locked:
                (root / '.git/index.lock').touch()
            fake_git = root / 'bin/git'
            fake_git.write_text('''#!/bin/bash
printf '%s\n' "$*" >> "$TEST_LOG"
case "$1" in
 ls-files) exit "$TEST_NEW" ;;
 diff) exit 0 ;;
 add) exit "$TEST_FAIL_ADD" ;;
 pull) exit "$TEST_FAIL_PULL" ;;
esac
exit 0
''')
            fake_sleep = root / 'bin/sleep'
            fake_sleep.write_text('#!/bin/bash\n' + ('exec /bin/sleep "$@"\n' if detached else 'kill -TERM "$PPID"\n'))
            fake_git.chmod(0o755)
            fake_sleep.chmod(0o755)
            env = {**os.environ, 'PATH': str(root / 'bin') + ':' + os.environ['PATH'],
                   'TEST_LOG': str(root / 'git-calls'), 'TEST_NEW': str(int(not unchanged)),
                   'TEST_FAIL_ADD': str(int(fail_add)), 'TEST_FAIL_PULL': str(int(fail_pull))}
            command = ['bash', str(script)]
            result = subprocess.run(command + ([] if detached else ['--worker']), env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            if detached:
                pid_file = root / '本机快照/状态播报.pid'
                try:
                    for _ in range(100):
                        if pid_file.exists() and (root / '指挥/运行状态.md').exists():
                            break
                        time.sleep(.02)
                    self.assertTrue(pid_file.exists())
                    first_pid = pid_file.read_text()
                    again = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
                    self.assertIn('已在运行', again.stdout)
                    self.assertEqual(first_pid, pid_file.read_text())
                finally:
                    subprocess.run(command + ['--停止'], env=env, capture_output=True, text=True, timeout=10)
                    for _ in range(100):
                        if not pid_file.exists():
                            break
                        time.sleep(.02)
            self.assertTrue((root / '指挥/运行状态.md').exists())
            self.assertFalse((root / '本机快照/状态播报.pid').exists())
            log = root / 'git-calls'
            return log.read_text() if log.exists() else ''

    def test_commit_only_status_and_then_sync(self):
        calls = self.run_worker()
        self.assertIn('add -- 指挥/运行状态.md', calls)
        self.assertIn('commit -m 运行状态：自动更新 (No SPEC Change) -- 指挥/运行状态.md', calls)
        self.assertIn('pull --rebase --autostash\npush', calls)

    def test_index_lock_and_git_failures_do_not_exit_with_error(self):
        self.assertEqual(self.run_worker(locked=True), '')
        calls = self.run_worker(fail_add=True)
        self.assertNotIn('commit ', calls)
        calls = self.run_worker(fail_pull=True)
        self.assertNotIn('\npush', calls)

    def test_unchanged_status_has_no_commit(self):
        calls = self.run_worker(unchanged=True)
        self.assertNotIn('add ', calls)
        self.assertNotIn('commit ', calls)

    def test_detached_start_duplicate_start_and_stop(self):
        self.run_worker(detached=True)


if __name__ == '__main__':
    unittest.main()
