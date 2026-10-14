#!/usr/bin/env python3
"""Explicit local maintenance only; never calls Provider or rebuilds Knowledge."""
import argparse,hashlib,json,sqlite3,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.history import reset_experiments, require_idle, table_counts
from app.governance import GovernanceStore


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute',action='store_true')
    p.add_argument('--maintenance',action='store_true',help='operator has stopped API/writers')
    p.add_argument('--backup',type=Path)
    args=p.parse_args();database=(ROOT/'backend/data/demo.db').resolve()
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as source:
        source.row_factory=sqlite3.Row;require_idle(source)
        before=table_counts(source)
        sizes={'sqlite_bytes':database.stat().st_size,'wal_bytes':Path(str(database)+'-wal').stat().st_size if Path(str(database)+'-wal').exists() else 0}
        if not args.execute:
            print(json.dumps({'dry_run':True,'counts':before,**sizes}));return
        if not args.maintenance or not args.backup:p.error('--execute requires stopped writers (--maintenance) and exactly one --backup')
        # Exclusive creation prevents accidental overwrite or accumulating backups on retries.
        backup=args.backup.resolve();backup.parent.mkdir(parents=True,exist_ok=True)
        backup.touch(mode=0o600,exist_ok=False)
        with sqlite3.connect(backup) as target:source.backup(target)
    paths=list((ROOT/'backend/data/index').glob('*'))+list((ROOT/'backend/documents').glob('*.pdf'))
    paths += [ROOT/'backend/data'/n for n in ['corpus_state.json','legacy_index.json','q02-switch.json']]
    binding=ROOT/'backend/data/legacy_index.json'
    if binding.exists():paths+=list(Path(json.loads(binding.read_text())['path']).glob('*'))
    fingerprints={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths if f.is_file()}
    manifest=json.loads((ROOT/'backend/data/index/manifest.json').read_text())
    store=GovernanceStore.__new__(GovernanceStore);store.database_path=database
    result=reset_experiments(store,manifest['knowledge_identity'])
    with sqlite3.connect(database) as c:
        c.execute('VACUUM')
        if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('SQLite integrity check failed')
    for path,sha in fingerprints.items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise RuntimeError('Knowledge asset changed: '+path)
    result.update(backup=str(backup),sizes_before=sizes,sizes_after={'sqlite_bytes':database.stat().st_size,'wal_bytes':Path(str(database)+'-wal').stat().st_size if Path(str(database)+'-wal').exists() else 0},knowledge_files_verified=len(fingerprints),knowledge_sha256=fingerprints)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))

if __name__=='__main__':main()
