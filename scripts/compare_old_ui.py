"""Serve the snapshot-032-ui-20261115 frontend through a local read-only API proxy."""
import http.client
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tarfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = Path.home() / 'RAG归档' / '前端对照-032'
STATE = ARCHIVE / 'services.json'
HOP_HEADERS = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
               'te', 'trailer', 'transfer-encoding', 'upgrade', 'host', 'content-length'}


class ReadOnlyProxy(BaseHTTPRequestHandler):
    def __getattr__(self, name):
        if name.startswith('do_'):
            return self.reject
        raise AttributeError(name)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Expose-Headers', 'X-Read-Version')
        super().end_headers()

    def reject(self):
        self.log_message('BLOCKED %s %s', self.command, self.path)
        self.send_response(405)
        self.send_header('Allow', 'GET, HEAD, OPTIONS')
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(b'{"detail":"Old UI comparison is read-only"}')
        self.close_connection = True

    def forward(self):
        upstream = http.client.HTTPConnection('127.0.0.1', getattr(self.server, 'upstream_port', 8010), timeout=60)
        try:
            upstream.request(self.command, self.path, headers={
                key: value for key, value in self.headers.items() if key.lower() not in HOP_HEADERS
            })
            response = upstream.getresponse()
            body = response.read()
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() not in HOP_HEADERS and not key.lower().startswith('access-control-'):
                    self.send_header(key, value)
            if self.command != 'HEAD':
                self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Navigation can cancel a read after its response has started.
        except (OSError, http.client.HTTPException) as error:
            self.log_error('Upstream unavailable: %s', error)
            self.send_error(502, 'Local API unavailable')
        finally:
            upstream.close()

    do_GET = do_HEAD = do_OPTIONS = forward


def owned(pid, marker):
    result = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True, env={**os.environ, 'LC_ALL': 'en_US.UTF-8'})
    return result.returncode == 0 and marker in result.stdout


def stop():
    if STATE.exists():
        for service in json.loads(STATE.read_text()):
            if owned(service['pid'], service['marker']):
                os.killpg(service['pid'], signal.SIGTERM)
        for _ in range(50):
            if not any(owned(service['pid'], service['marker']) for service in json.loads(STATE.read_text())):
                break
            time.sleep(0.1)
        STATE.unlink()
    print('032版对照服务已停止（只处理本脚本记录的进程）。')


def start():
    if STATE.exists():
        services = json.loads(STATE.read_text())
        if all(owned(service['pid'], service['marker']) for service in services):
            print('032版对照已运行：http://127.0.0.1:5175；停止：bash scripts/start_compare_old_ui.sh stop')
            return
        stop()
    for port in (8011, 5175):
        with socket.socket() as check:
            check.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            check.bind(('127.0.0.1', port))  # Never stop a process that already owns these ports.
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    frontend = ARCHIVE / 'frontend'
    if not frontend.exists():
        archive = subprocess.check_output(['git', 'archive', 'refs/remotes/origin/snapshot-032-ui-20261115', 'frontend'], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            source.extractall(ARCHIVE, filter='data')
    if not (frontend / 'node_modules').exists():
        if (frontend / 'package-lock.json').read_bytes() == (ROOT / 'frontend/package-lock.json').read_bytes() and (ROOT / 'frontend/node_modules').is_dir():
            (frontend / 'node_modules').symlink_to(ROOT / 'frontend/node_modules', target_is_directory=True)
        else:
            subprocess.run(['npm', 'ci'], cwd=frontend, check=True)
    if not (frontend / 'dist/index.html').exists():
        with (ARCHIVE / 'build.log').open('w') as log:
            subprocess.run(['npm', 'run', 'build'], cwd=frontend, env={**os.environ, 'VITE_API_BASE_URL': 'http://127.0.0.1:8011'}, stdout=log, stderr=subprocess.STDOUT, check=True)
    commands = [
        ([sys.executable, '-u', str(Path(__file__).resolve()), 'proxy'], ROOT, str(Path(__file__).resolve()), 'proxy.log'),
        (['node', str(frontend / 'node_modules/vite/bin/vite.js'), 'preview', '--host', '127.0.0.1', '--port', '5175', '--strictPort'], frontend, str(frontend / 'node_modules/vite/bin/vite.js'), 'preview.log'),
    ]
    services = []
    try:
        for command, cwd, marker, filename in commands:
            with (ARCHIVE / filename).open('a') as log:
                process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            services.append({'pid': process.pid, 'marker': marker})
            STATE.write_text(json.dumps(services, ensure_ascii=False, indent=2))
        for port in (8011, 5175):
            for _ in range(100):
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError(f'{port} 启动失败，请检查 {ARCHIVE} 下的日志')
    except BaseException:
        stop()
        raise
    print(f'032版：http://127.0.0.1:5175；只读代理：http://127.0.0.1:8011；日志：{ARCHIVE}')
    print('停止：bash scripts/start_compare_old_ui.sh stop')


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'start'
    if action == 'proxy':
        ThreadingHTTPServer(('127.0.0.1', 8011), ReadOnlyProxy).serve_forever()
    elif action == 'start':
        start()
    elif action == 'stop':
        stop()
    else:
        raise SystemExit('用法：bash scripts/start_compare_old_ui.sh [start|stop]')
