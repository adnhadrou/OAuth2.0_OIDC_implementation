"""Create only synthetic local credentials and a private local HTTPS CA."""

import argparse
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"


def save(name, value):
    path = LOCAL / name
    path.write_bytes(value if isinstance(value, bytes) else value.encode())
    path.chmod(0o600)


def key_bytes(key):
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--renew-tls", action="store_true", help="Replace only the local CA/TLS pair"
    )
    args = parser.parse_args()
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    if args.renew_tls and not (LOCAL / "secrets.json").exists():
        raise SystemExit("Run initial bootstrap before renewing TLS")
    if (LOCAL / "secrets.json").exists() and not args.renew_tls:
        existing = json.loads((LOCAL / "secrets.json").read_text())
        save("client.json", json.dumps({"clients": {"demo-web": existing["clients"]["demo-web"]}}))
        print("Existing local setup preserved. See README for renewal/reset instructions.")
        return
    if (ROOT / ".env").exists() and not args.renew_tls:
        raise SystemExit("Refusing to replace an existing .env file")
    now = datetime.now(UTC)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AuthFlow Lab Local CA")])
    ca = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), False
        )
        .add_extension(
            x509.KeyUsage(False, False, False, False, False, True, True, False, False),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    tls_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    names = ["auth.authflow.test", "client.authflow.test", "api.authflow.test"]
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, names[0])]))
        .issuer_name(ca_name)
        .public_key(tls_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=90))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in names]), False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(tls_key.public_key()), False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), False
        )
        .add_extension(
            x509.KeyUsage(True, False, True, False, False, False, False, False, False), True
        )
        .sign(ca_key, hashes.SHA256())
    )
    save("ca.pem", ca.public_bytes(serialization.Encoding.PEM))
    save("server-cert.pem", cert.public_bytes(serialization.Encoding.PEM))
    save("server-key.pem", key_bytes(tls_key))
    if args.renew_tls:
        print("TLS CA/certificate renewed. Replace browser trust before restarting services.")
        return
    signing = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    save("signing-key.pem", key_bytes(signing))
    save(
        "signing-public.pem",
        signing.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ),
    )
    # The CA private key is intentionally discarded after issuing the leaf certificate.
    password = secrets.token_urlsafe(24)
    (ROOT / ".env").write_text("POSTGRES_PASSWORD=" + password + "\n", encoding="utf-8")
    os.chmod(ROOT / ".env", 0o600)
    save(
        "secrets.json",
        json.dumps(
            {
                "username": "student",
                "password": secrets.token_urlsafe(20),
                "clients": {
                    "demo-web": secrets.token_urlsafe(32),
                    "second-web": secrets.token_urlsafe(32),
                },
            },
            indent=2,
        ),
    )
    existing = json.loads((LOCAL / "secrets.json").read_text())
    save("client.json", json.dumps({"clients": {"demo-web": existing["clients"]["demo-web"]}}))
    print("Created .local credentials, signing keys and HTTPS certificate. No secrets printed.")
    print("Trust .local/ca.pem and add the three .authflow.test hosts as documented in README.")


if __name__ == "__main__":
    main()
