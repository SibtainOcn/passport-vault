# Changelog

All notable changes and bug fixes for PassportVault are documented in this file.

## [Unreleased] - 2026-09-14

### Added
- Tiered Auto-Verification Scoring: Implemented 3-tier automatic decision logic in `vault/auto_verify.py` based on the 5 mandatory approval fields (`passport_number`, `dob`, `gender`, `date_of_issue`, `date_of_expiry`):
  - 5/5 Match: Direct automatic approval (`approved`, green).
  - 3/5 or 4/5 Match (0 mismatches): Routed to manual review (`review`, amber) with detailed missing OCR field feedback (e.g. `4/5 approval fields match. Missing OCR data: date_of_issue`).
  - Less than 3/5 Match or Any Value Mismatch: Evaluated as `failed` (red).
- Batch Document Re-verification Tool: Added `scripts/reverify_all.py` to re-evaluate and update existing processed documents against active Master Excel records using the new tiered decision rules without re-running OCR.
- Interrupted Worker Recovery Script: Added `scripts/retry_interrupted.py` to identify `WORKER_INTERRUPTED` documents caused by worker or container restarts, clear stale leases, and requeue them for processing up to retry limits.
- Diagnostic & Logic Test Harness: Added `scripts/diagnose_records.py` providing active Master Excel inspection, live record verification diagnostics, and synthetic tiered verification test suites.
- Tiered Verification Test Suite: Added unit tests in `tests/test_verification.py` covering 5/5 match, 4/5 and 3/5 review tiers, <3 match failures, mismatch overrides, and non-approval field tolerance.
- Date of Issue OCR Fallback Recovery: Added `_recover_date_of_issue()` heuristic in `vault/ocr_recovery.py` that scans raw OCR text for DD/MM/YYYY date patterns, filters out known DOB and expiry dates, and selects the most plausible issue date. Addresses the fact that the ICAO 9303 MRZ standard does not include date of issue, and Indian passports print issue/expiry dates side-by-side which defeats the label parser.
- Gender OCR Fallback Recovery: Added `_recover_gender()` heuristic in `vault/ocr_recovery.py` that recovers gender from "Sex M/MALE/F/FEMALE" text patterns, nationality-adjacent tokens, and partial MRZ line structures when the formal MRZ checksum validation and label parser both fail.

### Fixed
- Missing Date of Issue on Indian Passports: The date of issue field was consistently showing as "Missing value" because it is not encoded in the MRZ and the printed text label parser failed when "Date of Issue" and "Date of Expiry" are on the same OCR line (side-by-side Indian passport layout). The new fallback date scanner resolves this.
- Missing Gender on Garbled MRZ: Gender was lost when OCR produced a garbled MRZ line that failed checksum validation in `checked_prefix()`, and the printed "Sex" label was also not recognized. The new fallback scanner recovers gender from partial MRZ structures and text patterns.
- Verification Decision Messaging: Replaced generic `"One or more compared fields are missing or invalid"` message in `vault/auto_verify.py` with explicit field comparison counts (`match_count`, `mismatch_count`) and exact missing/mismatched field lists.
- Diagnostic Harness Mock Path: Fixed mock target for `unpack` in `scripts/diagnose_records.py` to `vault.auto_verify.unpack` for reliable execution inside containerized environments.
- OCR Quality Gate Approval: Prevented non-critical display fields (`full_name`, `nationality`) from appending to OCR quality `issues`, routing them to `display_warnings` instead. This prevents valid 5/5 matching passport scans from being falsely demoted to "Needs Review".

- Test Suite Module Resolution: Fixed candidate module import paths in `tests/test_recovery.py` and `tests/test_verification.py` from non-existent `files/vault` fallback to the actual `vault/` root directory.
- Test Suite Django Bootstrap: Added centralized Django environment bootstrap (`DJANGO_SETTINGS_MODULE`, `VAULT_TESTING=1`, `django.setup()`) in `tests/__init__.py` to support `python -m unittest discover` and direct test runner invocations.
- Cross-Platform Test Fonts: Replaced hardcoded Linux-only monospace font paths in `tests/test_vault.py` with a multi-platform resolver (`_mono_font`) supporting Windows (`consola.ttf`, `cour.ttf`), Linux (`DejaVuSansMono.ttf`), and macOS (`Menlo.ttc`).
- Local Test Runner: Added `run_tests.py` convenience script to cleanly execute all tests with test secrets and SQLite database lifecycle management.
- OCR Pipeline KeyError: Fixed unhandled KeyError exceptions in `vault/ocr_recovery.py` by initializing `full_name` and `nationality` inside the voter collection dictionary.
- Non-Critical Field Resolution: Added dedicated resolution logic for `full_name` and `nationality` in `vault/ocr_recovery.py` to preserve evidence without corrupting the 5-field critical approval score.
- Indian Passport MRZ Validation: Updated Indian passport regex in `vault/ocr_recovery.py` from `[A-Z]{2}[0-9]{6}<` to `[A-Z]{1,2}[0-9]{6,7}<` to properly support 8-character passports (1 letter + 7 digits).
- Ambiguous OCR Tie Breaking: Fixed tied OCR engine voting behavior to leave conflicting fields blank rather than picking an arbitrary guess, ensuring ambiguous scans are flagged for manual reviewer approval.
- Admin Review Field Comparison: Removed restrictive filter in `vault/auto_verify.py` so all extracted passport fields, including full name and nationality, are visible in the reviewer dashboard.
- Test Suite Assertion Updates: Aligned `tests/test_recovery.py` test cases to account for accurate date and MRZ resolution.
- Windows WSL Setup Script: Added automated CRLF line ending cleanup (`sed -i 's/\r$//'`) in `scripts/setup-windows.ps1` before executing `scripts/install-linux.sh`, preventing bash `set: pipefail` invalid option errors on Windows clones.
- Git Ignore Configuration: Updated `.gitignore` to exclude `.venv/`, `*.sqlite3`, environment files, certificates, coverage reports, and IDE configurations.


