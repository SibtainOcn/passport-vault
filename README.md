# Passport Vault

A self-hosted passport extraction and spreadsheet comparison application for a
single owner. Windows 11 is supported through Ubuntu on WSL2 and Docker Engine.
No hosted OCR, telemetry, analytics, SaaS dependency or proprietary Docker Desktop.
Read **README_FIRST.txt** for the nontechnical setup steps and **TEST_RESULTS.md**
for validation limits. This release requires target-PC acceptance before live PII.

## Architecture

- React/TypeScript/Vite frontend: built assets included; no Node setup needed by the user.
- Django 5.2 backend; PostgreSQL 17 persistent data and durable work queue.
- Tesseract 5 OCR with English/Hindi/Arabic; PDFium rendering; Pillow normalization.
- MRZ TD3 parser: syntax/check digits, provisional date interpretation, printed review.
- Workbook import with openpyxl/CSV and explicit column/date mapping.
- Caddy HTTPS on loopback 8443, TLS to Gunicorn and verified TLS to PostgreSQL.
- One worker by default. PostgreSQL row locks, leases and attempt limits protect work.
- All passport payloads, raw sources, previews, revisions, workbook cells and reports
  are AES-256-GCM encrypted before database persistence. UUID/AAD binds each ciphertext.
- Keyed HMAC passport lookup; issuing country narrows candidates when provided.
- Sensitive metadata (original filenames, OCR evidence) stays inside encrypted payloads.

The implementation intentionally uses Tesseract instead of the initially proposed
PaddleOCR and a PostgreSQL queue instead of Celery/RabbitMQ. These choices reduce
installation and memory overhead. There is no unsupported fallback or automatic
cloud processing. The OCR adapter can be replaced without changing record identity.
Django's native JSON views are used instead of adding REST Framework unnecessarily.

## Data model and isolation

`Document` owns immutable `Source` files, encrypted `Page` previews and historical
`Revision` objects. Every browser query is owner-scoped. Every upload request creates
one document group. Byte-identical groups are detected by a keyed content digest;
other duplicate numbers remain separate and block automatic disambiguation.
`Workbook` stores encrypted parsed cells for at most a day. `Report` stores immutable
comparison snapshots. `Audit` is a PII-free, HMAC-chained sequence with a locked head.

Worker state: queued -> processing -> review -> approved. Failure is explicit.
A worker lease expires after 25 minutes; expired work becomes failed. A parser has
a 20-minute wall-clock deadline and CPU/memory limits. A failed job can be manually
retried up to three attempts. Results commit only if the current lease still matches.
No partial source data from another document can be reused. PostgreSQL transactions
commit review and revision history atomically, with optimistic revision checks.

## Input limits

- One upload group: max 12 files, 25 MB total, max 12 rendered pages.
- Each file must start with the expected PDF/PNG/JPEG signature; images are actually
  decoded and PDFs rendered in the parser, not trusted from filename alone.
- Animated images rejected. Image pixel cap 24 million; page rendering bounded.
- Max 100 outstanding queued/processing groups; bulk UI uploads groups sequentially.
- Workbook: 5 MB, 5,000 data rows total, 40 columns, 30 sheets; ZIP expansion capped.
- `.xlsx` or UTF-8 `.csv` only. No `.xls`, `.xlsm`, formulas, errors or external links.
- Human approval requires full name and passport number; absent optional fields
  remain blank and cannot generate an all-fields Match.

## Comparison semantics

Exact normalized passport lookup; no O/0 or I/1 substitution. Case/space-normalized
names; no fuzzy auto-matching. ISO dates or selected DMY/MDY formats. Missing data,
duplicates and unapproved extraction yield Needs Review. Blank/invalid passport
numbers yield Invalid Row. Mismatches include both source values and field status.
CSV formula prefixes are neutralized; XLSX values are explicitly stored as strings.
Reports include sheet/row, document revision, rules version and comparison timestamp.
The UI compares one sheet at a time; the API accepts multiple selections using a
common column mapping. Differently structured sheets should be mapped separately.

## Developer setup (not required for end users)

Use Python 3.12 and install the locked requirements in a virtual environment. Install
Tesseract, English/OSD language data and DejaVu fonts for the synthetic tests. Run:

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.lock
python run_tests.py
cd frontend
npm ci
npm run build
```

Alternatively, run tests inside the Docker container:
```sh
docker exec -e VAULT_TESTING=1 passportvault-web-1 python manage.py test tests -v 2
```

`run_tests.py` automatically configures `VAULT_TESTING=1` and `DJANGO_SETTINGS_MODULE=app.settings`,
setting up known dummy keys and an isolated SQLite test database with automatic lifecycle teardown.
Never set `VAULT_TESTING=1` on an installation containing real documents. Deployment Compose does
not pass this flag. Production settings fail closed when required secret files are missing.

Frontend build inputs: `frontend/package-lock.json`. Backend versions:
`requirements.lock`. OS packages/images are version-family/tag pinned, not digest
pinned; resolve and record digests on the destination machine before controlled rollout.

## Source layout

- `vault/views.py`: auth, owner-scoped endpoints, upload, review, exports.
- `vault/ocr.py`, `mrz.py`, `sandbox.py`: document parsing and isolation.
- `vault/comparison.py`, `sheets.py`, `fields.py`: comparison and normalization.
- `vault/models.py`, `crypto.py`, `audit.py`: persistence and encryption.
- `vault/management/commands/`: setup, worker, audit/retention operations.
- `frontend/src/`: the complete interface source.
- `scripts/`: Windows setup/start/stop and Linux deployment/backup/restore.
- `tests/`: deterministic validation and real-Tesseract synthetic smoke test.

## Main endpoints

GET `/api/session`, POST `/api/login`, POST `/api/logout`.
GET `/api/documents`, POST `/api/upload`, GET `/api/documents/<uuid>`.
POST document `/review`, `/retry`, `/delete`; GET `/api/pages/<uuid>`.
POST `/api/workbooks`, POST `/api/compare`.
GET `/api/reports`, GET report `/export/xlsx` or `/export/csv`.
POST report `/delete`; GET `/api/audit`.
All mutation requests use Django CSRF protection. All data endpoints require a full
MFA session. No public account registration or user-creation API exists.

## Current scope

This package opens on the hosting PC only. Exposing it to LAN/internet is a separate
security/deployment task, not a port-forwarding instruction. The normal user simply
installs it on whichever Windows 11 computer should hold the records.
No hardware/electricity/backup-media costs can be eliminated by free software.
