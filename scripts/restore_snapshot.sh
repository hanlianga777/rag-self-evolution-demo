#!/usr/bin/env bash
# Usage: restore_snapshot.sh SNAPSHOT [--target-root EMPTY_OR_TEST_ROOT]
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
[[ $# -ge 1 ]] || { echo "用法：$0 <快照目录> [--target-root <演练目录>]" >&2; exit 2; }
snapshot="$1"; shift
target="$repo"
if [[ $# -gt 0 ]]; then
  [[ $# -eq 2 && "$1" == --target-root ]] || exit 2
  target="$2"
fi
python3 - "$snapshot" "$target" <<'PY'
from contextlib import closing
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import time

# macOS otherwise escapes Chinese paths in ps/lsof, hiding the real backend.
process_env = {**os.environ, 'LC_ALL': 'en_US.UTF-8', 'LANG': 'en_US.UTF-8', 'LC_CTYPE': 'en_US.UTF-8'}
snapshot, target = (Path(p).resolve() for p in sys.argv[1:])
if snapshot == target or snapshot.is_relative_to(target / 'backend') or target.is_relative_to(snapshot):
    raise SystemExit('快照和恢复位置重叠，停止')
manifest = json.loads((snapshot / '清单.json').read_text())
roots = manifest['roots']
allowed = {'backend/data', 'backend/documents', 'backend/config', 'backend/reports', '.env'}
if not set(roots) <= allowed or 'backend/data' not in roots:
    raise SystemExit('不支持的快照目录清单')

def verify(base):
    for entry in manifest['files']:
        rel = Path(entry['path'])
        if rel.is_absolute() or '..' in rel.parts or not any(rel == Path(r) or Path(r) in rel.parents for r in roots):
            raise ValueError('清单路径不合法')
        path = base / rel
        if not path.resolve().is_relative_to(base) or path.is_symlink():
            raise ValueError('文件越过恢复目录')
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if path.stat().st_size != entry['size'] or digest != entry['sha256']:
            raise ValueError('哈希不符：' + entry['path'])
    for entry in manifest['symlinks']:
        path = base / entry['path']
        if not path.is_symlink() or os.readlink(path) != entry['target'] or not path.resolve().is_relative_to(base):
            raise ValueError('索引链接校验失败')

# Refuse a corrupt snapshot before stopping anything or renaming current data.
verify(snapshot)
target.mkdir(parents=True, exist_ok=True)
processes = subprocess.check_output(['ps', '-axo', 'pid=,command='], text=True, env=process_env).splitlines()
supervisors, servers = [], []
for line in processes:
    pid_text, _, command = line.strip().partition(' ')
    pid = int(pid_text)
    if pid == os.getpid():
        continue
    if str(target / 'scripts/supervise_api.sh') in command:
        supervisors.append(pid)
    elif 'uvicorn app.main:app' in command:
        cwd = subprocess.run(['lsof', '-a', '-p', str(pid), '-d', 'cwd', '-Fn'], capture_output=True, text=True, env=process_env).stdout
        if '\nn' + str(target) + '\n' in cwd:
            servers.append(pid)
for pid in supervisors + servers:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
for _ in range(100):
    remaining = []
    for pid in supervisors + servers:
        try:
            os.kill(pid, 0)
            remaining.append(pid)
        except ProcessLookupError:
            pass
    if not remaining:
        break
    time.sleep(.1)
else:
    raise SystemExit('后端尚未停止，未替换数据')
data = target / 'backend/data'
if data.exists():
    holders = subprocess.run(['lsof', '-t', '+D', str(data)], capture_output=True, text=True, env=process_env)
    if holders.stdout.strip() or holders.returncode not in (0, 1):
        raise SystemExit('当前数据仍被进程打开或无法检查，未替换数据')

stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
saved = []
for rel in roots:
    destination = target / rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        old = destination.with_name(destination.name + '.before-restore-' + stamp)
        destination.rename(old)
        saved.append(str(old))
for rel in roots:
    source, destination = snapshot / rel, target / rel
    if source.is_dir():
        shutil.copytree(source, destination, symlinks=True)
    else:
        shutil.copy2(source, destination)
verify(target)
for rel in manifest['sqlite_online_backups']:
    with closing(sqlite3.connect((target / rel).as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('恢复数据库完整性检查失败')
# Only trim this script's own older safety copies; retain the latest two per root.
for rel in roots:
    path = target / rel
    for old in sorted(path.parent.glob(path.name + '.before-restore-*'), reverse=True)[2:]:
        if old.is_dir() and not old.is_symlink():
            shutil.rmtree(old)
        else:
            old.unlink()
print(json.dumps({'restored_root': str(target), 'verified_files': len(manifest['files']), 'saved_previous': saved}, ensure_ascii=False))
print('数据恢复并校验完成。代码存档分支：' + manifest['archive_branch'] + '；快照时提交：' + manifest['code_commit'])
print('请重启后端：bash scripts/supervise_api.sh（前端未停止）')
PY
