import logging
import os

from waitress import serve

from . import authorization, client, resource
from .config import Settings


def main():
    # No request/access logging: callback URLs contain codes and state.
    # Never enable Flask debug, SQL echo, HTTP wire logging or Caddy access logging.
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: service event")
    service = os.environ.get("LAB_SERVICE", "auth")
    module = {"auth": authorization, "client": client, "api": resource}[service]
    app = module.create_app(Settings.load())
    serve(app, host="0.0.0.0", port=8000, threads=8, clear_untrusted_proxy_headers=True)


if __name__ == "__main__":
    main()
