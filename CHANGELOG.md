# Changelog

All notable changes and bug fixes for PassportVault are documented in this file.

## [Unreleased] - 2026-09-14

### Fixed
- OCR Pipeline KeyError: Fixed unhandled KeyError exceptions in `vault/ocr_recovery.py` by initializing `full_name` and `nationality` inside the voter collection dictionary.
- Non-Critical Field Resolution: Added dedicated resolution logic for `full_name` and `nationality` in `vault/ocr_recovery.py` to preserve evidence without corrupting the 5-field critical approval score.
- Indian Passport MRZ Validation: Updated Indian passport regex in `vault/ocr_recovery.py` from `[A-Z]{2}[0-9]{6}<` to `[A-Z]{1,2}[0-9]{6,7}<` to properly support 8-character passports (1 letter + 7 digits).
- Ambiguous OCR Tie Breaking: Fixed tied OCR engine voting behavior to leave conflicting fields blank rather than picking an arbitrary guess, ensuring ambiguous scans are flagged for manual reviewer approval.
- Admin Review Field Comparison: Removed restrictive filter in `vault/auto_verify.py` so all extracted passport fields, including full name and nationality, are visible in the reviewer dashboard.
- Test Suite Assertion Updates: Aligned `tests/test_recovery.py` test cases to account for accurate date and MRZ resolution.
- Windows WSL Setup Script: Added automated CRLF line ending cleanup (`sed -i 's/\r$//'`) in `scripts/setup-windows.ps1` before executing `scripts/install-linux.sh`, preventing bash `set: pipefail` invalid option errors on Windows clones.
- Git Ignore Configuration: Updated `.gitignore` to exclude `.venv/`, environment files, certificates, coverage reports, and IDE configurations.
