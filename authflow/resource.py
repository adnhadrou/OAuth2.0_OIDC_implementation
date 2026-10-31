import jwt
import requests
from flask import g, jsonify, request

from .common import app_base
from .models import Code
from .security import TokenValidator


def create_app(settings, validator=None):
    app = app_base("api", settings)
    validator = validator or TokenValidator(settings)

    def failure(name=None, status=401):
        response = jsonify(error=name or "unauthorized")
        response.status_code = status
        value = 'Bearer realm="authflow-api"'
        if name:
            value += f', error="{name}"'
        if name == "insufficient_scope":
            value += ', scope="notes:read"'
        response.headers["WWW-Authenticate"] = value
        return response

    @app.get("/notes")
    def notes():
        if "access_token" in request.args:
            return failure("invalid_request", 400)
        auth = request.headers.get("Authorization", "")
        if not auth:
            return failure()
        parts = auth.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return failure("invalid_token")
        try:
            claims = validator.validate(parts[1], "access")
        except (jwt.PyJWTError, ValueError, KeyError, TypeError):
            return failure("invalid_token")
        except requests.RequestException:
            return jsonify(error="temporarily_unavailable"), 503
        grant = g.db.get(Code, claims["jti"])
        if grant is None or not grant.consumed or grant.revoked:
            return failure("invalid_token")
        if "notes:read" not in claims["scope"].split():
            return failure("insufficient_scope", 403)
        return {"subject": claims["sub"], "notes": ["Synthetic note: the API checked notes:read."]}

    return app
