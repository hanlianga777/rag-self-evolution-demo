"""Local HTTP test: forbidden methods must never reach the upstream."""
import http.client
import threading
import subprocess
import sys
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from compare_old_ui import ReadOnlyProxy, owned


class ProxyTest(unittest.TestCase):
    def test_process_identity_with_chinese_path(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)", "前端对照-e37e7fa"])
        try:
            self.assertTrue(owned(process.pid, "前端对照-e37e7fa"))
            self.assertFalse(owned(process.pid, "unrelated-service"))
        finally:
            process.terminate()
            process.wait()

    def test_read_forwarding_and_write_block(self):
        received = []

        class Upstream(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append((self.command, self.path))
                self.send_response(200)
                self.send_header('X-Read-Version', 'saved-version')
                self.send_header('Access-Control-Allow-Origin', 'http://localhost:5174')
                self.end_headers()
                self.wfile.write(b'saved-result')

            def do_HEAD(self):
                received.append((self.command, self.path))
                self.send_response(200)
                self.end_headers()

            def do_OPTIONS(self):
                received.append((self.command, self.path))
                self.send_response(204)
                self.end_headers()

            def log_message(self, *args):
                pass

        upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        proxy = ThreadingHTTPServer(('127.0.0.1', 0), ReadOnlyProxy)
        proxy.upstream_port = upstream.server_port
        for server in (upstream, proxy):
            threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            for method in ('GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE', 'TRACE', 'CONNECT', 'CUSTOM'):
                with self.subTest(method=method):
                    conn = http.client.HTTPConnection('127.0.0.1', proxy.server_port, timeout=3)
                    conn.request(method, '/api/example?q=1', headers={'Origin': 'http://127.0.0.1:5175'})
                    response = conn.getresponse()
                    body = response.read()
                    self.assertEqual(response.status, {'GET': 200, 'HEAD': 200, 'OPTIONS': 204}.get(method, 405))
                    self.assertEqual(response.getheader('Access-Control-Allow-Origin'), '*')
                    if method == 'GET':
                        self.assertEqual(body, b'saved-result')
                        self.assertEqual(response.getheader('X-Read-Version'), 'saved-version')
                    if method not in ('GET', 'HEAD', 'OPTIONS'):
                        self.assertEqual(response.getheader('Allow'), 'GET, HEAD, OPTIONS')
                    conn.close()
            self.assertEqual(received, [('GET', '/api/example?q=1'), ('HEAD', '/api/example?q=1'), ('OPTIONS', '/api/example?q=1')])
        finally:
            for server in (proxy, upstream):
                server.shutdown()
                server.server_close()


if __name__ == '__main__':
    unittest.main()
