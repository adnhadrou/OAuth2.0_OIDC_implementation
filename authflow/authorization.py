import base64
import binascii
import secrets
import time
from datetime import timedelta
from urllib.parse import unquote_plus, urlencode

from argon2.exceptions import VerificationError
from flask import g, jsonify, redirect, render_template, request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from .common import app_base, csrf, new_browser, update_browser, utcnow
from .models import Code, LoginThrottle, User
from .security import CHALLENGE, VERIFIER, challenge, digest, mint, opaque, passwords, public_jwk


def create_app(settings):
    app = app_base("auth", settings)
    dummy_hash = passwords.hash(opaque())

    def error(name, status=400):
        response = jsonify(error=name)
        response.status_code = status
        if status == 401:
            response.headers["WWW-Authenticate"] = 'Basic realm="authflow-token"'
        return response

    def authorization_response(params, **values):
        if params.get("state"):
            values["state"] = params["state"]
        return redirect(params["redirect_uri"] + "?" + urlencode(values), code=303)

    @app.get("/.well-known/openid-configuration")
    def discovery():
        return {
            "issuer": settings.issuer,
            "authorization_endpoint": settings.issuer + "/authorize",
            "token_endpoint": settings.issuer + "/token",
            "jwks_uri": settings.issuer + "/jwks",
            "response_types_supported": ["code"],
            "response_modes_supported": ["query"],
            "grant_types_supported": ["authorization_code"],
            "subject_types_supported": ["public"],
            "scopes_supported": ["openid", "notes:read"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "token_endpoint_auth_methods_supported": ["client_secret_basic"],
            "code_challenge_methods_supported": ["S256"],
            "claims_supported": ["iss", "sub", "aud", "exp", "iat", "nonce", "auth_time"],
            "request_parameter_supported": False,
            "request_uri_parameter_supported": False,
            "claims_parameter_supported": False,
        }

    @app.get("/jwks")
    def jwks():
        return {"keys": [public_jwk(settings)]}

    @app.get("/authorize")
    def authorize():
        params = request.args.to_dict()
        client = settings.clients.get(params.get("client_id"))
        # Establish the destination's trust before emitting ANY redirect, including errors.
        if (
            not client
            or params.get("redirect_uri") != client["redirect_uri"]
            or len(request.args.getlist("client_id")) != 1
            or len(request.args.getlist("redirect_uri")) != 1
        ):
            return error("invalid_request")
        if any(len(v) != 1 for _, v in request.args.lists()):
            return error("invalid_request")
        if any(len(v) > 512 for v in params.values()):
            return error("invalid_request")
        if params.get("response_type") != "code":
            return authorization_response(params, error="unsupported_response_type")
        scopes = set(params.get("scope", "").split())
        if not scopes or not scopes <= client["scopes"]:
            return authorization_response(params, error="invalid_scope")
        if params.get("code_challenge_method") != "S256" or not CHALLENGE.fullmatch(
            params.get("code_challenge", "")
        ):
            return authorization_response(params, error="invalid_request")
        # Nonce is a stricter lab policy for code-flow OIDC requests.
        if "openid" in scopes and not 16 <= len(params.get("nonce", "")) <= 256:
            return authorization_response(params, error="invalid_request")
        if (
            any(
                k in params
                for k in ("request", "request_uri", "claims", "prompt", "max_age", "id_token_hint")
            )
            or params.get("response_mode", "query") != "query"
        ):
            return authorization_response(params, error="invalid_request")
        params["scope"] = " ".join(sorted(scopes))
        update_browser(pending=params, pending_exp=int(time.time()) + 300)
        return redirect("/consent" if g.browser.data.get("user_id") else "/login", code=303)

    def pending():
        if g.browser.data.get("pending_exp", 0) < time.time():
            return None
        return g.browser.data.get("pending")

    def rate_limited(username):
        now = utcnow()
        limited = False
        # Both buckets are persisted and locked: limits survive workers and restarts.
        buckets = [
            (digest("account:" + username), 5),
            (digest("ip:" + (request.remote_addr or "unknown")), 20),
        ]
        for key, maximum in sorted(buckets):
            g.db.execute(
                insert(LoginThrottle)
                .values(digest=key, attempts=0, window_end=now + timedelta(seconds=60))
                .on_conflict_do_nothing()
            )
            row = g.db.scalar(
                select(LoginThrottle).where(LoginThrottle.digest == key).with_for_update()
            )
            if row.window_end <= now:
                row.attempts, row.window_end = 0, now + timedelta(seconds=60)
            row.attempts += 1
            limited |= row.attempts > maximum
        return limited

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if not pending():
            return error("invalid_request")
        message = None
        if request.method == "POST":
            csrf()
            username = request.form.get("username", "")[:100]
            if rate_limited(username):
                return render_template("message.html", message="Try again in one minute."), 429
            user = g.db.scalar(select(User).where(User.username == username))
            valid = False
            try:
                valid = passwords.verify(
                    user.password_hash if user else dummy_hash, request.form.get("password", "")
                )
            except VerificationError:
                pass
            if valid and user:
                new_browser(
                    "auth",
                    settings,
                    {**g.browser.data, "user_id": user.id, "auth_time": int(time.time())},
                )
                return redirect("/consent", code=303)
            message = "Invalid username or password."
        return render_template("login.html", csrf=g.browser.data["csrf"], message=message)

    @app.route("/consent", methods=["GET", "POST"])
    def consent():
        params = pending()
        if not params:
            return error("invalid_request")
        if not g.browser.data.get("user_id"):
            return redirect("/login", code=303)
        if request.method == "GET":
            return render_template("consent.html", csrf=g.browser.data["csrf"], params=params)
        csrf()
        update_browser(pending=None, pending_exp=0)
        if request.form.get("decision") != "allow":
            return authorization_response(params, error="access_denied")
        raw = opaque()
        g.db.add(
            Code(
                digest=digest(raw),
                client_id=params["client_id"],
                redirect_uri=params["redirect_uri"],
                scope=params["scope"],
                user_id=g.browser.data["user_id"],
                challenge=params["code_challenge"],
                nonce=params.get("nonce"),
                auth_time=g.browser.data["auth_time"],
                expires_at=utcnow() + timedelta(seconds=settings.code_ttl),
            )
        )
        return authorization_response(params, code=raw)

    def authenticate_client():
        if any(k in request.form for k in ("client_id", "client_secret")):
            return None
        try:
            scheme, value = request.headers.get("Authorization", "").split(" ", 1)
            if scheme.lower() != "basic":
                return None
            name, secret = base64.b64decode(value, validate=True).decode("utf-8").split(":", 1)
            name, secret = unquote_plus(name), unquote_plus(secret)
        except (ValueError, UnicodeError, binascii.Error):
            return None
        expected = settings.client_secrets.get(name, "invalid-client-secret")
        if secrets.compare_digest(secret.encode(), expected.encode()) and name in settings.clients:
            return name
        return None

    @app.post("/token")
    def token():
        if request.mimetype != "application/x-www-form-urlencoded" or request.args:
            return error("invalid_request")
        if any(len(v) != 1 for _, v in request.form.lists()):
            return error("invalid_request")
        client_id = authenticate_client()
        if not client_id:
            return error("invalid_client", 401)
        if request.form.get("grant_type") != "authorization_code":
            return error("unsupported_grant_type")
        if not request.form.get("code") or not request.form.get("redirect_uri"):
            return error("invalid_request")
        row = g.db.scalar(
            select(Code).where(Code.digest == digest(request.form["code"])).with_for_update()
        )
        verifier = request.form.get("code_verifier", "")
        if (
            row is None
            or row.client_id != client_id
            or row.redirect_uri != request.form["redirect_uri"]
            or not VERIFIER.fullmatch(verifier)
            or not secrets.compare_digest(row.challenge, challenge(verifier))
        ):
            return error("invalid_grant")
        if row.consumed:
            # Revoke the access grant following a correctly bound replay (RFC 6749 4.1.2).
            row.revoked = True
            return error("invalid_grant")
        if row.expires_at <= utcnow():
            return error("invalid_grant")
        row.consumed = True
        result = mint(settings, row)
        # app_base commits the locked row before this response can be sent.
        return jsonify(result)

    return app
