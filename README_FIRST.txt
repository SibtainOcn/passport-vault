PASSPORT VAULT - START HERE
Windows 11 / x64 / self-hosted / free software

This is an implemented project package, not a certification of production readiness.
Use synthetic test documents first. Real passport accuracy and Windows deployment
must be verified on the destination PC before handling live records.

SIMPLE INSTALLATION
1. Extract this ZIP fully to a folder on the destination computer.
2. Double-click SETUP.cmd.
3. Type YES when asked to install.
4. If Ubuntu/WSL must be installed, approve Windows' normal installation prompt.
   Finish Ubuntu first launch if asked. Restart if Windows requests it, and run
   SETUP.cmd again. Never disable organization security controls to install.
5. Setup downloads free software. Internet is needed during installation.
6. Choose your username and a strong password (14+ characters).
7. Add the displayed secret to a TOTP authenticator using manual entry.
   Use time-based, SHA1, 6 digits, 30 seconds. No paid authenticator is required.
   Ente Auth is an open-source option: https://github.com/ente/ente
8. Enter the current authenticator code. Store recovery codes OFFLINE.
   Never send your password, authenticator secret or recovery codes in chat.
9. Approve local certificate import only on your own intended computer.
   The script imports the local CA into your Windows user's trusted roots.
10. Open https://localhost:8443. Wait for the next authenticator code to sign in.

AFTER SETUP
- START.cmd starts the app. STOP.cmd stops it without deleting records.
- The app is reachable only on that computer. This is intentional.
- Installing on a second PC makes a separate database unless you restore a backup.
- To use the data on another PC, first back up, install there, then restore.
- Initial software downloads can be several GB. They are not included in this ZIP.
- No API key, credit card, cloud OCR or paid subscription is required.
- OCR can run without external internet after setup. Ubuntu/Docker must be running.
- 8 GB RAM is a provisional minimum, 16 GB is preferable. One OCR worker is used.
  Actual throughput depends on page quality, CPU, free memory and PDF complexity.

FIRST WORKFLOW
1. Passports > Choose files. Default: each file is a separate passport.
2. For front/back photos of ONE passport, tick the grouping checkbox before upload.
   Do not upload a PDF containing multiple people as one record; split it first.
3. Wait for Needs review. Open the record and inspect every page and field.
4. Correct fields, use YYYY-MM-DD dates, confirm grouping, then Approve.
5. Compare Excel > choose XLSX or UTF-8 CSV.
6. Choose sheet and header row. Map Passport number and the details to compare.
7. Select day/month/year or month/day/year explicitly.
8. Compare, inspect mismatches and download Excel/CSV.

SAFETY NOTES THAT AFFECT USE
- Every extraction needs manual approval. Never assume OCR is the ground truth.
- Generic labelled-field extraction is implemented, not a comprehensive country-
  by-country passport parser. Missing/uncertain fields require manual entry.
- Latin TD3 MRZ is parsed with check digits. TD1/TD2 cards and historic formats
  have no dedicated parser in this version; review/manual entry is required.
- English, Hindi and Arabic OCR language packs are installed. Other scripts are
  not advertised as supported; their Latin MRZ may still be readable.
- MRZ dates have two-digit years and names may be truncated/transliterated.
- Invalid MRZ checks do not prove fraud. Valid checks do not prove authenticity.
- Match means selected data fields agree, not that a passport is authentic.
- Not Found is held as Needs Review while unresolved uploads could hide a match.
- Deleted documents can still appear in saved report snapshots and backups.
  Delete those separately when required.
- Downloads are ordinary Excel/CSV files. Keep them on a protected device.

BACKUP AND RESTORE
BACKUP.cmd creates a passphrase-encrypted backup and copies it into the Backups
folder next to these launchers. Copy that file to a separate protected drive.
Keep the passphrase separately: it cannot be recovered by this software.
RESTORE.cmd lets you choose a backup. It asks you to type RESTORE before replacing
current data. Make a current backup first. Restore on a test PC before relying
on backups for live work. Do not delete an old installation until restore succeeds.
Backup/restore deployment scripts have not been executed in this build environment.

IF ANYTHING FAILS
Send a screenshot of the error, with credentials and personal passport data hidden.
Do not reinstall by deleting Ubuntu, Docker volumes or the secrets directory.
Those contain the database and keys. This update/install process preserves them.

DOCUMENTATION
README.md                   Architecture and developer commands
SECURITY.md                 Security boundaries and live-use acceptance gates
docs/OPERATIONS.md          Backup, retention, upgrades and recovery
TEST_RESULTS.md             Exactly what was and was not tested
THIRD_PARTY.md               Open-source dependencies and license inventory
