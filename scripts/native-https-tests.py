"""Windows fallback for live HTTPS tests when Docker Desktop cannot start.

Only DNS for this lab's three names is mapped to loopback. TLS validation is intact.
The generated CA must be trusted by the test user's browser before running this.
"""

import argparse
import os
import socket
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from werkzeug.serving import WSGIRequestHandler, make_server  # noqa: E402

from authflow import authorization, client, resource, seed  # noqa: E402
from authflow.config import Settings  # noqa: E402


class QuietHandler(WSGIRequestHandler):
    def log(self, kind, message, *args):
        pass  # Never print callback queries, request bodies or headers.


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true", help="Serve the local lab until Ctrl+C")
    args = parser.parse_args()
    os.chdir(ROOT)
    password = (ROOT / ".env").read_text().strip().split("=", 1)[1]
    os.environ["DATABASE_URL"] = f"postgresql+psycopg://lab:{password}@127.0.0.1:55432/authflow"
    os.environ["RUN_BROWSER"] = "1"
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(ROOT / ".local/browsers")
    os.environ["LAB_BROWSER_HOST_RULES"] = "MAP *.authflow.test 127.0.0.1"
    os.environ["NO_PROXY"] = ".authflow.test,127.0.0.1,localhost"
    names = {"auth.authflow.test", "client.authflow.test", "api.authflow.test"}
    original = socket.getaddrinfo

    def local_dns(host, *args, **kwargs):
        return original("127.0.0.1" if host in names else host, *args, **kwargs)

    socket.getaddrinfo = local_dns
    command.upgrade(Config("alembic.ini"), "head")
    seed.main()
    settings = Settings.load()
    servers = []
    try:
        for port, module in [(8443, authorization), (8444, client), (8445, resource)]:
            server = make_server(
                "127.0.0.1",
                port,
                module.create_app(settings),
                threaded=True,
                request_handler=QuietHandler,
                ssl_context=(".local/server-cert.pem", ".local/server-key.pem"),
            )
            servers.append(server)
            threading.Thread(target=server.serve_forever, daemon=True).start()
        if args.serve:
            print("Lab HTTPS servers ready. Open https://client.authflow.test:8444")
            print("Use the documented hosts aliases and trusted CA. Press Ctrl+C to stop.")
            try:
                threading.Event().wait()
            except KeyboardInterrupt:
                return 0
        return pytest.main(
            ["tests/test_live.py", "-q", "--tb=short", "--junitxml=test-results/native-https.xml"]
        )
    finally:
        for server in servers:
            server.shutdown()
        socket.getaddrinfo = original


if __name__ == "__main__":
    raise SystemExit(main())
