# Changelog

All notable changes and bug fixes for PassportVault are documented in this file.

## [Unreleased] - 2026-09-14

### Fixed
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

