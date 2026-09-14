#!/usr/bin/env bash
set -euo pipefail
umask 077
mkdir -p db-tls db-init
if [ ! -f secrets/internal.crt ] || [ ! -f secrets/internal.key ]; then
  openssl req -x509 -nodes -newkey rsa:3072 -days 3650 -subj '/CN=PassportVault-internal' -addext 'subjectAltName=DNS:db,DNS:web' -keyout secrets/internal.key -out secrets/internal.crt
fi
cp secrets/internal.crt db-tls/internal.crt
cp secrets/internal.key db-tls/internal.key
chmod 644 db-tls/internal.crt
chown 0:999 db-tls/internal.key
chmod 640 db-tls/internal.key
chmod 400 secrets/internal.key secrets/internal.crt
python3 - <<'PYTHON'
from pathlib import Path
import re
password=Path('secrets/db').read_text().strip()
if not re.fullmatch('[0-9a-f]{96}',password): raise SystemExit('Unexpected DB credential format')
Path('db-init/init.sql').write_text("CREATE ROLE passportvault LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD '"+password+"';\nCREATE DATABASE passportvault OWNER passportvault;\n")
PYTHON
chmod 644 db-init/init.sql
