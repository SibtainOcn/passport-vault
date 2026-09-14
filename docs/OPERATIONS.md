# Operations

## Location and start/stop

Code lives in `/opt/passportvault` in Ubuntu. PostgreSQL data lives in a named Docker
volume. Keys live in `/opt/passportvault/secrets` (root only). START starts Docker
and services. STOP stops containers and preserves volumes/keys. Do not run
`docker compose down -v`, unregister Ubuntu, or delete secret files to fix a problem.

## Backups

BACKUP stops writers, dumps PostgreSQL, archives the dump and original keys in a
private /dev/shm directory, and encrypts with age and a user-entered passphrase.
The final .age filename is written only after encryption succeeds. Temporary RAM
files are removed and application writers restart through a shell trap. A partial
file is not a valid backup. Windows copies the newest completed backup to `Backups`
next to the downloaded launchers. Copy it to separate protected storage yourself.
No automatic paid storage service or account is required.

The backup contains encrypted field values and the keys needed to decrypt them,
inside an outer passphrase-encrypted archive. Anyone with both backup and passphrase
can recover the vault; protect them separately. Backups include user password hashes,
MFA secret, unused recovery code hashes and audit history. No credentials are shared
with external services. Restoring the same backup twice may restore previously-used
recovery codes; after disaster recovery, review MFA security before live use.

RESTORE is destructive to the destination database and explicitly asks for RESTORE.
Run a current backup first. It decrypts and validates a fixed file allowlist, stops
writers, restores SQL, restores master/index/Django keys, preserves the destination
DB/admin/TLS credentials, invalidates all sessions and verifies the audit chain.
If database restore fails, services remain stopped for diagnosis. Do not repeatedly
retry on a live database. A clean second installation is the safest restore test.
The app version used to restore should match the backup schema version first.

## Retention

The maintenance service runs hourly. It removes parsed workbook records older than
one day and verifies the audit chain. Documents and reports are owner-deleted in UI.
To remove reports older than an approved number of days, an operator can run:

```sh
cd /opt/passportvault
docker compose exec web python manage.py maintenance --report-days 30
```

This is an example, not an automatically enabled policy. Deleting a document removes
its original files/previews/revisions. Existing report snapshots and backups are
independent copies. Disk blocks, WAL and external backups are not guaranteed physically
erased immediately; threat-model storage lifecycle and backup expiry explicitly.

## Updating safely

1. Back up and test recovery before a significant update.
2. STOP the app. Extract the new code package and run SETUP.
3. Installer copies code without deleting data or replacing keys; migrations run.
4. Verify login, one document, one report and the audit chain.
5. If schema migration fails, keep the app stopped and diagnose; do not delete data.
6. Use an isolated clone/backup for upgrade testing first. Keep last known-good source.

## Internal certificates

Setup creates an internal self-signed TLS certificate for DNS names db and web.
PostgreSQL and Gunicorn use it; Caddy and psycopg verify it explicitly. Its key is
separate from the data encryption key. Treat its expiry as an operational deadline;
renew under a controlled maintenance window and restart all services together.
The browser-facing certificate is managed by Caddy's local CA. If Caddy's data volume
is lost/recreated, the new local CA must be imported into Windows explicitly again.
No script asks the user to bypass browser certificate warnings.

## Before scaling

Measure current CPU/memory, queue delay, processing failure rate and database size.
The package has 1 OCR worker, 2 web workers and a 100-group outstanding queue cap.
Do not simply increase concurrency on an 8 GB PC. Additional workers use PostgreSQL
row locks and leases, but concurrent behavior needs load testing on PostgreSQL.
For large archives, move encrypted blobs to private object storage behind the same
owner checks and envelope encryption; preserve UUID/AAD and migrate transactionally.

## Adding OCR formats

Extend the engine adapter and label/MRZ parser with fixture-backed tests. Keep raw
extraction separate from human-approved fields and never silently re-approve records.
New language models must be installed in the image and explicitly exposed in the UI.
Benchmark each new script/layout; do not infer accuracy from model marketing claims.
