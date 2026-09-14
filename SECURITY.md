# Security and production acceptance

## Implemented controls

Single locally bootstrapped owner; PBKDF2 password hashes; TOTP MFA with replay
prevention; one-use hashed recovery codes; global 5-failure/15-minute login lockout;
30-minute sessions; secure, HttpOnly, same-site cookies; CSRF and CSP; no public signup.
A host administrator with WSL/Docker access can control the entire deployment and
must be trusted. MFA protects web access, not a compromised operating system.

Browser-to-gateway TLS uses a local CA trusted explicitly by the Windows user.
Gateway-to-Gunicorn TLS verifies the configured internal certificate. PostgreSQL
requires hostssl, and the application uses sslmode=verify-full. DB and application
ports are not published. Only loopback 8443 is bound. Application/worker DB traffic
stays on an internal Docker network with no external egress. The gateway has an edge
network for the loopback listener; it has no analytics or external OCR integration.

AES-256-GCM uses a fresh random 96-bit nonce for each payload. AAD binds ciphertext
to record type and UUID. HMAC-SHA256 indexes use a separate random key. Master/index/
Django/admin keys are generated once; setup refuses incomplete key sets and never
replaces existing keys. Plaintext field values are decrypted only in memory.
Original files and previews are encrypted DB blobs, not web-served public files.

Parser children drop supplementary groups and switch to UID/GID 65534 in production.
They cannot read the root-only key directory or parent process memory. CPU/address
space/time limits and container memory/pid limits bound processing. Temporary OCR
files are in a tmpfs /tmp, mode 0600, and removed by the library. Containers have a
read-only root filesystem, no-new-privileges and all capabilities dropped except
SETUID/SETGID/KILL for the trusted supervisor. The parser loses capabilities when its
identity changes. Network isolation is at container level; it is not a separate
microVM sandbox. Keep native parsers patched. No antivirus scanner is included.

Database application role is not a superuser and cannot create roles/databases.
It owns its application database for migrations. The separate vaultadmin credential
is not used for normal queries. Audit chaining detects edits without the audit key;
it is not an independently anchored immutable audit service. An attacker controlling
both the app and keys could forge history. Keep backups on separately controlled media.

No raw PII in application/audit logs; access logging disabled in Gunicorn and Caddy.
No third-party fonts, analytics, LLM calls, tracking pixels or browser persistent
storage. Report exports are sensitive ordinary files once downloaded.

## Material limitations / required live-use checks

This is NOT certified production-ready merely because tests pass.

1. Run SETUP, login, upload/review, comparison and export on the actual Windows PC.
   The build environment had no Docker daemon or Windows runtime. WSL installation,
   Compose, container UID permissions, internal TLS, certificate import, PostgreSQL
   concurrency, backup and restore must be exercised on the destination machine.
2. Browser visual/accessibility/mobile interaction QA remains outstanding: the
   available browser blocked the local test URL. Static build/type checks passed.
3. Use representative authorized passports across actual countries, formats,
   languages and scan conditions. Measure per-field accuracy and manual-review time.
   Synthetic OCR success is NOT a real-passport accuracy benchmark.
4. All records require human review. Generic label extraction will miss or misread
   some fields; unsupported script/layout support is not claimed. Manual entry is
   available for those fields. Multiple-person PDFs require splitting before upload.
5. Protect Windows login and its disk, swap/pagefile, hibernation and backup media.
   Application encryption cannot prevent capture by local malware or a host admin.
   OS disk encryption is outside this application package; no proprietary encryption
   product is installed by these scripts. Assess the host before live PII use.
6. Restore a backup to a second test installation and verify original files, values,
   MFA recovery, audit continuity and comparison outputs before trusting recovery.
7. Define retention with the data owner. Documents and report snapshots are retained
   until explicit deletion. Workbooks are removed after one day by maintenance.
   Encrypted backups are separate copies and must expire according to that policy.
8. Key rotation with live re-encryption is not implemented. Protect and back up keys;
   never generate replacements to fix a login/install problem. A compromised master
   key needs a controlled migration into a fresh vault and incident handling.
9. A security review/penetration test and dependency vulnerability review are needed
   before institutional/public production use. No automated vulnerability scan was
   performed in this environment; pinned packages are not a security guarantee.
10. Backup uses temporary RAM storage for the database dump. Very large databases may
    exceed available tmpfs space and fail; do not delete old backups on failure.

No biometric identity matching, passport authenticity detection or government
eligibility decision is implemented. A Match is only agreement with selected fields.

## Incident response

Stop the application, preserve encrypted backups and logs, restrict host access,
identify exposed data, and obtain an appropriate security review. Do not merely
reset the password if server/key access may have been compromised. Do not send raw
passports or secrets in screenshots, issue trackers or public repositories.
