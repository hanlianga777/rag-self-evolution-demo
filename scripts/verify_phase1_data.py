"""Read-only proof that an additive migration preserved every original business field."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def fingerprint(path):
    path = Path(path)
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size': path.stat().st_size, 'mtime_ns': path.stat().st_mtime_ns}


def compare(before, after):
    result = {}
    with sqlite3.connect(f'file:{Path(before).resolve()}?mode=ro', uri=True) as old, sqlite3.connect(f'file:{Path(after).resolve()}?mode=ro', uri=True) as new:
        tables = [row[0] for row in old.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        assert tables == [row[0] for row in new.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        for table in tables:
            columns = [row[1] for row in old.execute(f'PRAGMA table_info("{table}")')]
            final_columns = [row[1] for row in new.execute(f'PRAGMA table_info("{table}")')]
            assert final_columns == columns or table == 'monitoring_events' and final_columns == columns + ['metrics_json'], table
            fields = ','.join(f'"{name}"' for name in columns)
            first = old.execute(f'SELECT {fields} FROM "{table}" ORDER BY rowid').fetchall()
            second = new.execute(f'SELECT {fields} FROM "{table}" ORDER BY rowid').fetchall()
            actual_count = len(second)
            if table == 'schema_migrations':
                second = [row for row in second if row[0] != 'phase1-monitoring-metrics' or any(previous[0] == row[0] for previous in first)]
            assert first == second, f'{table}: an original record changed'
            if table == 'monitoring_events' and 'metrics_json' not in columns:
                assert new.execute('SELECT COUNT(*) FROM monitoring_events WHERE metrics_json IS NOT NULL').fetchone()[0] == 0
            result[table] = {'before_count': len(first), 'after_count': actual_count, 'original_records_equal': True}
    return {'before': fingerprint(before), 'after': fingerprint(after), 'tables': result, 'passed': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', required=True)
    parser.add_argument('--after', required=True)
    parser.add_argument('--index-manifest')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = compare(args.before, args.after)
    if args.index_manifest:
        manifest = json.loads(Path(args.index_manifest).read_text())['index']
        result['index_files'] = {name: fingerprint(name)['sha256'] for name in manifest}
        assert result['index_files'] == manifest, 'Index contents changed'
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"PASS: {len(result['tables'])} tables, all original records unchanged")
