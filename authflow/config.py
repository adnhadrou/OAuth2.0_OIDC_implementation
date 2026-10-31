import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    database_url: str = field(repr=False)
    issuer: str
    client_origin: str
    api_origin: str
    private_key: bytes = field(repr=False)
    public_key: bytes
    ca_bundle: str
    client_secrets: dict[str, str] = field(repr=False)
    login_password: str = field(repr=False)
    code_ttl: int = 60
    token_ttl: int = 300
    session_ttl: int = 1800
    kid: str = "lab-rsa-1"

    @property
    def clients(self):
        return {
            "demo-web": {
                "redirect_uri": self.client_origin + "/callback",
                "scopes": {"openid", "notes:read"},
            },
            "second-web": {
                "redirect_uri": self.client_origin + "/second-callback",
                "scopes": {"openid", "notes:read"},
            },
        }

    @classmethod
    def load(cls):
        directory = Path(os.environ.get("LAB_LOCAL_DIR", ".local"))
        service = os.environ.get("LAB_SERVICE", "auth")
        secrets = (
            {}
            if service == "api"
            else json.loads(
                (directory / ("client.json" if service == "client" else "secrets.json")).read_text()
            )
        )
        return cls(
            database_url=os.environ["DATABASE_URL"],
            issuer="https://auth.authflow.test:8443",
            client_origin="https://client.authflow.test:8444",
            api_origin="https://api.authflow.test:8445",
            private_key=(directory / "signing-key.pem").read_bytes()
            if os.environ.get("LAB_SERVICE", "auth") == "auth"
            else b"",
            public_key=(directory / "signing-public.pem").read_bytes(),
            ca_bundle=str(directory / "ca.pem"),
            client_secrets=secrets.get("clients", {}),
            login_password=secrets.get("password", ""),
        )
