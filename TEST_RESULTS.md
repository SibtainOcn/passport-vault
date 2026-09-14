# Validation results

Build date: 2026-09-10. Environment: Linux, Python 3.12, SQLite test database,
Tesseract installed locally. No real user passport data was used.

## Passed

- 35 Django/unittest tests (7.913 seconds in the last full run).
- Real Tesseract extraction on a synthetic text image.
- End-to-end API: upload image -> queued worker -> isolated OCR child -> encrypted
  preview -> human approval -> CSV workbook import -> comparison -> XLSX export.
- Corrupted PDF worker fails with a controlled error and no approved record.
- AES-GCM nonce uniqueness, successful decryption, AAD mismatch and tamper rejection.
- MRZ sample checks and invalid check-digit detection.
- DMY/MDY date interpretation, invalid dates and issue/expiry ordering.
- No O/0 passport-number substitution.
- Match, Mismatch, Not Found, Needs Review and Invalid Row behavior.
- Duplicate candidates, missing fields, unresolved jobs and owner isolation.
- Anonymous and incomplete-MFA API access blocked; cross-owner record access blocked.
- CSRF enforcement, privacy response headers, TOTP replay prevention,
  one-use recovery codes and persistent login throttling.
- Upload encryption, exact duplicate detection and invalid file signatures.
- Review revision conflicts, history persistence and multi-identity approval block.
- Export formula neutralization and immutable comparison snapshots.
- Audit chain tampering detection and expired worker lease recovery.
- Vite production build (23 modules; bundled assets included).
- TypeScript no-emit check for frontend source and Vite configuration.
- Python compilation checks.
- Django `check --deploy --fail-level WARNING` with production settings and random
  throwaway test keys: no issues. This is configuration checking, not a penetration test.
- Shell syntax checking for install, TLS, backup and restore scripts.

## Not verified here

- Windows 11/WSL installer execution, Windows certificate import and actual startup.
- Docker Compose startup, container capability/permission behavior and internal TLS.
- PostgreSQL migrations/locking/concurrency under the production database.
- Backup encryption/restore execution and disaster recovery on a second PC.
- Browser visual/mobile/accessibility interaction QA: the available browser rejected
  the local application URL with ERR_BLOCKED_BY_CLIENT. This is not a site test pass.
- Real-passport extraction accuracy, multilingual/layout coverage and throughput.
- Independent security assessment, dependency vulnerability audit or penetration test.

The test suite uses `VAULT_TESTING=1`: fixed dummy keys, SQLite, no HTTPS redirect,
and no production UID-drop so it can run in a private test workspace. Those settings
are never enabled in deployment Compose. Unit success does not validate production
network isolation or PostgreSQL-specific row locking. Live PII use remains gated on
on-machine deployment, backup/restore and representative document validation.
