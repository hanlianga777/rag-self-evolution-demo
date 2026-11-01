"""Keep the current backup and one older backup of the same kind."""
from pathlib import Path
import json


def keep_recent_two(new_backup: Path, kind: str) -> None:
    path = Path(new_backup)
    ledger = path.parent / f'.backup-retention-{kind}.json'
    names = json.loads(ledger.read_text()) if ledger.exists() else []
    names = {name for name in names if Path(name).name == name}
    names.update(p.name for p in path.parent.glob(f'{kind}-*.db'))
    names.add(path.name)
    older = [path.parent / name for name in names if name != path.name]
    older = [p for p in older if p.is_file() and not p.is_symlink()]
    older.sort(key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)
    for stale in older[1:]:
        stale.unlink()
    ledger.write_text(json.dumps([path.name] + [p.name for p in older[:1]]))
