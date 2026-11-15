from pathlib import Path
import json,subprocess,tempfile
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='task032h-web-') as tmp:
 t=Path(tmp);(t/'scripts').mkdir();(t/'frontend/node_modules/.bin').mkdir(parents=True)
 (t/'scripts/run_web_service.sh').write_bytes((root/'scripts/run_web_service.sh').read_bytes())
 (t/'frontend/package.json').write_text(json.dumps({"scripts":{"build":"node -e \"process.exit(0)\""}}))
 vite=t/'frontend/node_modules/.bin/vite';vite.write_text('#!/bin/sh\nprintf "%s\\n" "$*"\n');vite.chmod(0o755)
 r=subprocess.run(['bash',str(t/'scripts/run_web_service.sh')],capture_output=True,text=True)
 print(r.stdout,r.stderr)
 assert r.returncode==0
 assert 'preview --host 127.0.0.1 --port 5174 --strictPort' in r.stdout
 # Failed builds must never serve a stale bundle.
 (t/'frontend/package.json').write_text(json.dumps({"scripts":{"build":"node -e \"process.exit(2)\""}}))
 r=subprocess.run(['bash',str(t/'scripts/run_web_service.sh')],capture_output=True,text=True)
 assert r.returncode!=0
 assert 'preview --host' not in r.stdout
 print('PASS: builds before static preview; failed build does not launch server')
