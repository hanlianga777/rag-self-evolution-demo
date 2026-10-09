#!/usr/bin/env python3
"""Compare the Phase 0 read-only SQLite/table and Corpus manifest after acceptance."""
import hashlib
import json
import sqlite3
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/playwright/baseline-agent-restoration'
before = json.loads((OUT / 'data-before.json').read_text())
with sqlite3.connect(f'file:{ROOT / "backend/data/demo.db"}?mode=ro', uri=True) as connection:
    tables = {}
    for table in before['tables']:
        rows = sorted(connection.execute(f'SELECT * FROM "{table}"').fetchall(), key=str)
        tables[table] = {'count': len(rows), 'sha256': hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
files = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in before['files']}
result = {'tables': tables, 'files': files, 'tables_unchanged': tables == before['tables'], 'files_unchanged': files == before['files'], 'changed_tables': [name for name in tables if tables[name] != before['tables'][name]], 'changed_files': [name for name in files if files[name] != before['files'][name]], 'paid_calls_by_this_acceptance': 0, 'backup': before['backup']}
(OUT / 'data-after.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({key: result[key] for key in ['tables_unchanged', 'files_unchanged', 'changed_tables', 'changed_files']}, ensure_ascii=False))
assert result['tables_unchanged'] and result['files_unchanged'], 'Protected data changed; investigate before delivery'
