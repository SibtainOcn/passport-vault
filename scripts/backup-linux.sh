#!/usr/bin/env bash
set -euo pipefail
cd /opt/passportvault
umask 077
mkdir -p backups
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
WORK=$(mktemp -d /dev/shm/passportvault.XXXXXX)
trap 'rm -rf "$WORK"; docker compose up -d web worker maintenance >/dev/null' EXIT
echo 'Stopping application writers for a consistent backup. Choose a strong backup passphrase.'
docker compose stop web worker maintenance
docker compose exec -T db pg_dump -U vaultadmin -d passportvault --format=custom > "$WORK/database.dump"
cp -a secrets "$WORK/secrets"
tar -C "$WORK" -cf - database.dump secrets | age -p -o "backups/passportvault-$STAMP.tar.age.partial"
mv "backups/passportvault-$STAMP.tar.age.partial" "backups/passportvault-$STAMP.tar.age"
echo "Encrypted backup saved: /opt/passportvault/backups/passportvault-$STAMP.tar.age"
echo 'Copy it to a separate protected drive. Keep its passphrase separately.'
