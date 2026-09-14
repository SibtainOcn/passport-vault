#!/usr/bin/env bash
set -euo pipefail
if [ "$(id -u)" != 0 ]; then echo 'Installer needs root inside WSL.'; exit 1; fi
PACKAGE=${1:?Package path required}
DEST=/opt/passportvault
if [ ! -f "$PACKAGE/compose.yaml" ]; then echo 'Package incomplete.'; exit 1; fi
if [ "$(uname -m)" != x86_64 ]; then echo 'This package targets x64 Windows. ARM64 requires a separate dependency check.'; exit 1; fi
command -v apt-get >/dev/null || { echo 'Ubuntu is required.'; exit 1; }
echo 'Installing free software from Ubuntu repositories. This can take several minutes.'
apt-get update
apt-get install -y docker.io docker-compose-v2 python3 age ca-certificates openssl
if ! docker info >/dev/null 2>&1; then
  service docker start
fi
mkdir -p "$DEST"
# Copy application code without deleting data, keys, backups or Docker volumes.
python3 - "$PACKAGE" "$DEST" <<'PYTHON'
import shutil,sys
from pathlib import Path
src,dst=map(Path,sys.argv[1:])
for item in src.iterdir():
    if item.name.lower() in {'secrets','backups','db-init','db-tls','node_modules','.git','.sites-runtime'}: continue
    target=dst/item.name
    if item.is_dir(): shutil.copytree(item,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('node_modules','__pycache__','*.sqlite3'))
    else: shutil.copy2(item,target)
PYTHON
cd "$DEST"
python3 scripts/generate-secrets.py
bash scripts/configure-internal-tls.sh
chmod 700 /opt/passportvault
# Build uses packaged frontend assets; Node is not required on the user's PC.
docker compose build
docker compose up -d db
docker compose run --rm web python manage.py migrate --noinput
docker compose run --rm web python manage.py check --deploy --fail-level WARNING
if ! docker compose run --rm web python manage.py owner_exists; then
  docker compose run --rm web python manage.py createowner
fi
docker compose up -d
for attempt in $(seq 1 30); do
  if docker compose exec -T gateway cat /data/caddy/pki/authorities/local/root.crt > /tmp/passportvault-root.crt 2>/dev/null; then break; fi
  sleep 2
done
if [ ! -s /tmp/passportvault-root.crt ]; then echo 'TLS certificate not ready. Run START again.'; exit 1; fi
chmod 644 /tmp/passportvault-root.crt
printf '\nApplication installed. Complete certificate import in the Windows window.\n'
