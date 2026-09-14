PassportVault 2.1.0 - Consolidated Full Update

This package consolidates the base Windows 11 installer plus the OCR recovery update and feature update into one project folder.

Included:
- Automatic local OCR verification against Master Excel.
- Approval depends only on 5 fields: Passport Number, Date of Birth, Gender, Date of Issue, Date of Expiry.
- Full Name and Nationality remain display-only for approval.
- Enhanced EasyOCR + Tesseract + MRZ flow, with one EasyOCR pass for the current speed trial.
- Conservative OCR disagreement handling: uncertain values stay Needs Review instead of being silently corrected from Excel.
- Master spreadsheet limit: 40 MB, up to 1,000,000 data rows, 40 columns.
- Bulk delete on the current passport list page, while keeping single-record delete.
- Windows START/STOP scripts keep the Ubuntu WSL session alive so localhost does not disappear when the launcher exits.

SECURITY NOTE
If an earlier MFA/TOTP secret was exposed during testing, reset/regenerate it before using real passport data. Until then use dummy/test data only.

Install on Windows 11:
1. Extract the ZIP to a normal local folder.
2. Run SETUP.cmd.
3. After setup, use START.cmd and STOP.cmd.

Existing installations:
Running SETUP.cmd copies updated application code to /opt/passportvault without deleting Docker volumes/database data, but always keep a backup before upgrading.
