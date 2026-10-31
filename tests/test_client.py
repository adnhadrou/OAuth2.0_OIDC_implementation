import time
from urllib.parse import parse_qs, urlencode, urlsplit

import jwt
import pytest
from sqlalchemy import select

from authflow.client import create_app
from authflow.models import BrowserSession
from authflow.security import TokenValidator, public_jwk
from tests.conftest import csrf_value, issue

pytestmark = pytest.mark.integration


class HttpBridge:
    """HTTP-shaped adapter through actual Flask endpoints, with real PG state."""

    def __init__(self, lab, bad_nonce=False):
        self.lab, self.bad_nonce, self.calls = lab, bad_nonce, 0

    def post(self, url, data, auth, timeout, verify, allow_redirects):
        assert verify == self.lab["settings"].ca_bundle and allow_redirects is False
        self.calls += 1
        result = self.lab["auth"].test_client().post("/token", data=data, auth=auth)
        payload = result.json
        if self.bad_nonce and "id_token" in payload:
            settings = self.lab["settings"]
            claims = jwt.decode(payload["id_token"], options={"verify_signature": False})
            claims["nonce"] = "wrong-transaction"
            payload["id_token"] = jwt.encode(
                claims,
                settings.private_key,
                algorithm="RS256",
                headers={"kid": settings.kid, "typ": "JWT"},
            )

        class Response:
            def raise_for_status(self):
                if result.status_code != 200:
                    raise ValueError("exchange rejected")

            def json(self):
                return payload

        return Response()


def make_client(lab, bad_nonce=False):
    bridge = HttpBridge(lab, bad_nonce)
    app = create_app(
        lab["settings"],
        TokenValidator(lab["settings"], {"keys": [public_jwk(lab["settings"])]}),
        bridge,
    )
    app.testing = True
    return app, bridge


def begin(browser, settings):
    response = browser.get("/", base_url=settings.client_origin)
    response = browser.post(
        "/start", base_url=settings.client_origin, data={"csrf": csrf_value(response)}
    )
    return {k: v[0] for k, v in parse_qs(urlsplit(response.location).query).items()}


@pytest.mark.parametrize("bad_state", ["wrong", "", "é" * 32])
def test_state_mismatch_never_exchanges_code(lab, bad_state):
    app, bridge = make_client(lab)
    browser = app.test_client()
    begin(browser, lab["settings"])
    response = browser.get(
        "/callback?" + urlencode({"state": bad_state, "code": "unused"}),
        base_url=lab["settings"].client_origin,
    )
    assert response.status_code == 400 and bridge.calls == 0
    app.extensions["engine"].dispose()


def test_state_bound_to_initiating_browser_and_one_use(lab):
    app, bridge = make_client(lab)
    browser, other = app.test_client(), app.test_client()
    params = begin(browser, lab["settings"])
    query = "/callback?" + urlencode({"state": params["state"], "error": "access_denied"})
    assert other.get(query, base_url=lab["settings"].client_origin).status_code == 400
    response = browser.get(query, base_url=lab["settings"].client_origin)
    assert b"not granted" in response.data
    assert (
        b"transaction rejected" in browser.get(query, base_url=lab["settings"].client_origin).data
    )
    assert bridge.calls == 0
    app.extensions["engine"].dispose()


@pytest.mark.parametrize("bad_nonce", [False, True])
def test_callback_validates_nonce_and_keeps_tokens_server_side(lab, bad_nonce):
    app, bridge = make_client(lab, bad_nonce)
    browser = app.test_client()
    params = begin(browser, lab["settings"])
    code = issue(lab, **params)
    response = browser.get(
        "/callback?" + urlencode({"state": params["state"], "code": code}),
        base_url=lab["settings"].client_origin,
    )
    assert response.status_code == (400 if bad_nonce else 303)
    assert bridge.calls == 1
    if not bad_nonce:
        assert "Secure" in response.headers["Set-Cookie"]
        home = browser.get("/", base_url=lab["settings"].client_origin)
        assert b"student-001" in home.data and b"access_token" not in home.data
        with lab["sessions"]() as db:
            rows = db.scalars(
                select(BrowserSession).where(BrowserSession.service == "client")
            ).all()
            assert any("tokens" in row.data for row in rows)
    app.extensions["engine"].dispose()


def test_expired_state_and_form_csrf(lab):
    app, bridge = make_client(lab)
    browser = app.test_client()
    params = begin(browser, lab["settings"])
    assert browser.post("/start", base_url=lab["settings"].client_origin).status_code == 400
    with lab["sessions"].begin() as db:
        row = db.scalar(select(BrowserSession).where(BrowserSession.service == "client"))
        row.data = {
            **row.data,
            "transaction": {**row.data["transaction"], "expires": time.time() - 1},
        }
    response = browser.get(
        "/callback?" + urlencode({"state": params["state"], "code": "unused"}),
        base_url=lab["settings"].client_origin,
    )
    assert response.status_code == 400 and bridge.calls == 0
    app.extensions["engine"].dispose()
