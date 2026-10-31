"""Extract only PostgreSQL runtime files from the official portable archive."""

import hashlib
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1] / ".local"
archive = root / "postgresql.zip"
with archive.open("rb") as stream:
    checksum = hashlib.file_digest(stream, "sha256").hexdigest()
(root / "postgresql-archive.sha256").write_text(checksum + "\n")
destination = (root / "portable").resolve()
with zipfile.ZipFile(archive) as package:
    for member in package.infolist():
        if not member.filename.startswith(("pgsql/bin/", "pgsql/lib/", "pgsql/share/")):
            continue
        target = (destination / member.filename).resolve()
        if not target.is_relative_to(destination):
            raise ValueError("Archive contains an unsafe path")
        package.extract(member, destination)
print("Extracted PostgreSQL runtime; archive SHA-256 saved in .local.")
