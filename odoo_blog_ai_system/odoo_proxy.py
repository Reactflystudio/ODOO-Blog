#!/usr/bin/env python3
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urljoin
import httpx

UPSTREAM = os.environ.get("UPSTREAM", "https://www.empurraodigital.com.br")
LISTEN_HOST = os.environ.get("LISTEN_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "8090"))
TIMEOUT = float(os.environ.get("UPSTREAM_TIMEOUT", "60"))

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _proxy(self):
        upstream_url = urljoin(UPSTREAM, self.path)
        method = self.command

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
        headers["Host"] = httpx.URL(UPSTREAM).host
        headers["X-Forwarded-For"] = self.client_address[0]
        headers["X-Forwarded-Proto"] = "https"
        headers["X-Forwarded-Host"] = self.headers.get("Host", "")

        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            resp = client.request(method, upstream_url, headers=headers, content=body)

        self.send_response(resp.status_code)

        for k, v in resp.headers.items():
            if k.lower() in HOP_BY_HOP:
                continue
            if k.lower() == "content-length":
                continue
            self.send_header(k, v)

        self.send_header("Content-Length", str(len(resp.content)))
        self.end_headers()
        if resp.content:
            self.wfile.write(resp.content)

    def do_GET(self):
        self._proxy()

    def do_POST(self):
        self._proxy()

    def do_PUT(self):
        self._proxy()

    def do_DELETE(self):
        self._proxy()

    def do_PATCH(self):
        self._proxy()

    def do_HEAD(self):
        self._proxy()

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), ProxyHandler)
    server.serve_forever()
