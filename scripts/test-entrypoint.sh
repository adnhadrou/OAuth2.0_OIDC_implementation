#!/bin/sh
set -eu
# Chromium verifies the generated CA through its NSS trust database.
mkdir -p "$HOME/.pki/nssdb"
if [ ! -f "$HOME/.pki/nssdb/cert9.db" ]; then
    certutil -N --empty-password -d "sql:$HOME/.pki/nssdb"
fi
certutil -A -d "sql:$HOME/.pki/nssdb" -n 'AuthFlow Lab' -t 'C,,' -i .local/ca.pem
exec "$@"
