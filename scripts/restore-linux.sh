#!/usr/bin/env bash
set -euo pipefail
cd /opt/passportvault
FILE=${1:?Provide path to encrypted backup}
echo 'Restoring replaces the current database and encryption keys. Make a current backup first.'
read -r -p 'Type RESTORE to continue: ' ANSWER
[ "$ANSWER" = RESTORE ] || exit 1
umask 077
WORK=$(mktemp -d /dev/shm/passportvault-restore.XXXXXX)
trap 'rm -rf "$WORK"' EXIT
age -d -o "$WORK/backup.tar" "$FILE"
python3 - "$WORK" <<'PYTHON'
import sys,tarfile
from pathlib import Path
w=Path(sys.argv[1]); allowed={'database.dump','secrets','secrets/master','secrets/index','secrets/django','secrets/db','secrets/admin','secrets/internal.crt','secrets/internal.key'}
with tarfile.open(w/'backup.tar') as t:
    for m in t.getmembers():
        if m.name.rstrip('/') not in allowed or not (m.isfile() or m.isdir()): raise SystemExit('Unexpected backup contents; refusing extraction.')
    t.extractall(w,filter='data')
if not (w/'database.dump').is_file() or any(not (w/'secrets'/k).is_file() for k in ('master','index','django','db')): raise SystemExit('Incomplete backup')
PYTHON
docker compose stop web worker maintenance
echo 'Restoring database using the current database administrator credential.'
docker compose exec -T db pg_restore -U vaultadmin -d passportvault --clean --if-exists --exit-on-error < "$WORK/database.dump"
# Keep current DB connection credential: pg_dump does not include database roles.
for key in master index django; do cp "$WORK/secrets/$key" "secrets/$key"; done
python3 scripts/generate-secrets.py
docker compose run --rm web python manage.py invalidate_sessions
docker compose run --rm web python manage.py maintenance
docker compose up -d web worker maintenance
echo 'Restore completed. Verify records and sign in. Keep a second backup before deleting the old one.'
