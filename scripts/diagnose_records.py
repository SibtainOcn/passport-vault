"""PassportVault Diagnostic & Logic Test Harness (v2 — tiered scoring).

Run inside Docker:
  Get-Content scripts\\diagnose_records.py -Raw | wsl.exe -d Ubuntu -u root -- bash -lc 'cd /opt/passportvault && docker compose exec -T web python -'
"""
import os, sys, json
from datetime import datetime

if 'DJANGO_SETTINGS_MODULE' not in os.environ:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
    try:
        import django; django.setup()
    except Exception:
        pass

from vault.models import Document, Workbook, Source
from vault.crypto import unpack
from vault.auto_verify import _compare_document, _active_master
from vault.ocr_quality import apply_quality_gate
from vault.fields import FIELDS, normalize

APPROVAL_FIELDS = {'passport_number', 'dob', 'gender', 'date_of_issue', 'date_of_expiry'}

print("=" * 80)
print("PASSPORTVAULT DIAGNOSTIC & LOGIC TEST HARNESS  (v2 — tiered scoring)")
print("=" * 80)

# ─── 1. Active Master Excel ─────────────────────────────────────────────────
print("\n[1] ACTIVE MASTER EXCEL INSPECTION:")
workbooks = Workbook.objects.filter(active=True)
if not workbooks.exists():
    print("  NO ACTIVE MASTER EXCEL FOUND!")
    all_wbs = Workbook.objects.all()
    print(f"  Total workbooks in DB: {all_wbs.count()}")
    for wb in all_wbs:
        print(f"    - ID: {wb.id}, Name: {wb.name}, Active: {wb.active}, Owner: {wb.owner.username}")
else:
    for wb in workbooks:
        print(f"  Active Master: ID={wb.id}, Name='{wb.name}', Owner={wb.owner.username}")
        cfg = wb.config or {}
        sheet_name = cfg.get('sheet')
        header = cfg.get('header', 1)
        mapping = cfg.get('mapping') or {}
        date_format = cfg.get('date_format', 'DMY')
        print(f"  Configuration:")
        print(f"    - Sheet: {sheet_name}")
        print(f"    - Header Row: {header}")
        print(f"    - Date Format: {date_format}")
        print(f"    - Mappings: {json.dumps(mapping, indent=6)}")

        missing_approval = sorted(APPROVAL_FIELDS - set(mapping))
        if missing_approval:
            print(f"    MISSING MANDATORY APPROVAL FIELDS IN MAPPING: {missing_approval}")
        else:
            print(f"    All 5 mandatory approval fields are mapped.")

        try:
            sheets = unpack(wb.data, 'workbook:' + str(wb.id))
            if sheet_name not in sheets:
                print(f"    Sheet '{sheet_name}' NOT FOUND in workbook sheets: {list(sheets.keys())}")
            else:
                rows = sheets[sheet_name]
                print(f"    - Total rows in '{sheet_name}': {len(rows)}")
                for r_idx, r in enumerate(rows[:5]):
                    print(f"      Row {r_idx + 1}: {r}")
        except Exception as e:
            print(f"    Error unpacking master excel: {e}")

# ─── 2. Documents ────────────────────────────────────────────────────────────
print("\n[2] CURRENT DOCUMENTS INSPECTION:")
docs = list(Document.objects.all().order_by('-created'))
print(f"  Total documents in DB: {len(docs)}")

for idx, doc in enumerate(docs, 1):
    print("\n" + "-" * 75)
    try:
        payload = unpack(doc.payload, 'document:' + str(doc.id))
    except Exception as e:
        print(f"  Doc #{idx} [ID: {doc.id}]: UNPACK ERROR: {e}")
        continue

    doc_name = payload.get('name', 'Unknown')
    extracted_fields = payload.get('fields', {})
    verification = payload.get('verification', {})
    warnings = payload.get('warnings', [])
    error_code = doc.error_code

    print(f"  Doc #{idx}: {doc_name}")
    print(f"    Database Status : {doc.status.upper()}")
    print(f"    Document ID     : {doc.id}")
    print(f"    Created At      : {doc.created}")
    print(f"    Error Code      : '{error_code}'")
    print(f"    Attempts        : {doc.attempts}")
    print(f"    Pages in DB     : {doc.pages.count()}")

    print(f"\n    Extracted Fields:")
    if not extracted_fields:
        print(f"      NO FIELDS EXTRACTED (Empty dictionary)")
    else:
        for f, val in extracted_fields.items():
            print(f"      - {f:<18}: {val if val else '[EMPTY]'}")

    print(f"\n    Stored Verification Data:")
    print(f"      - Status: {verification.get('status')}")
    print(f"      - Reason: {verification.get('reason')}")
    match_c = verification.get('match_count')
    mismatch_c = verification.get('mismatch_count')
    if match_c is not None:
        print(f"      - Tiered Score: {match_c}/5 match, {mismatch_c} mismatch")
    comps = verification.get('comparisons', {})
    if comps:
        print(f"      - Comparisons:")
        for f, item in comps.items():
            st = item.get('status')
            ex = item.get('excel')
            oc = item.get('passport')
            flag = "OK" if st == "Match" else "XX"
            print(f"        [{flag}] {f:<16} | {st:<20} | Excel: '{ex}' | OCR: '{oc}'")

    if warnings:
        print(f"\n    OCR Warnings (first 5):")
        for w in warnings[:5]:
            print(f"      - {w}")

    # ─── Simulation ──────────────────────────────────────────────────────────
    print(f"\n    [SIMULATION]:")
    if doc.status == 'failed' and error_code == 'WORKER_INTERRUPTED':
        print(f"      Root cause: WORKER_INTERRUPTED — worker crashed during OCR.")
        print(f"      Fix: Run retry_interrupted.py to re-queue, or click 'Retry OCR' in UI.")
    elif extracted_fields:
        sim_verif, sim_status = _compare_document(doc.owner, extracted_fields)
        sim_match = sim_verif.get('match_count', '?')
        sim_mismatch = sim_verif.get('mismatch_count', '?')
        print(f"      Step 1 (_compare_document): status='{sim_status}', score={sim_match}/5 match, {sim_mismatch} mismatch")
        print(f"        reason: {sim_verif.get('reason')}")
        for f, item in sim_verif.get('comparisons', {}).items():
            if item.get('status') != 'Match':
                print(f"        Culprit: '{f}' => {item.get('status')} (Excel='{item.get('excel')}' vs OCR='{item.get('passport')}')")

        final_verif, final_status = apply_quality_gate(sim_verif, sim_status, payload)
        print(f"      Step 2 (quality_gate): status='{final_status}'")
        if sim_status != final_status:
            print(f"        Quality gate changed {sim_status} -> {final_status}: {final_verif.get('reason')}")
    else:
        print(f"      Cannot simulate — no extracted fields.")

# ─── 3. Tiered Logic Validation ──────────────────────────────────────────────
print("\n" + "=" * 80)
print("[3] OFFLINE TIERED LOGIC VALIDATION (synthetic tests)")
print("=" * 80)

from unittest.mock import patch
import types, copy

FIELDS_FULL = {
    'passport_number': 'Z1234567', 'full_name': 'TEST PERSON',
    'dob': '2000-04-03', 'gender': 'M', 'nationality': 'IND',
    'date_of_issue': '2020-06-05', 'date_of_expiry': '2030-06-04',
}
MASTER = types.SimpleNamespace(
    id='test-master', name='Synthetic Master',
    config={'sheet': 'Test', 'header': 1, 'date_format': 'DMY',
            'mapping': {f: i for i, f in enumerate(FIELDS_FULL)}},
    data={'Test': [list(FIELDS_FULL), list(FIELDS_FULL.values())]}
)

def sim(fields, master=MASTER):
    with patch('vault.auto_verify._active_master', return_value=master):
        with patch('vault.auto_verify.unpack', side_effect=lambda data, aad: data):
            return _compare_document(None, fields)

tests = [
    ("5/5 match => approved",    FIELDS_FULL,                                   'approved'),
    ("4/5 match => review",      dict(FIELDS_FULL, date_of_issue=''),           'review'),
    ("3/5 match => review",      dict(FIELDS_FULL, date_of_issue='', gender=''),'review'),
    ("2/5 match => failed",      dict(FIELDS_FULL, date_of_issue='', gender='', dob=''), 'failed'),
    ("1 mismatch => failed",     dict(FIELDS_FULL, gender='F'),                 'failed'),
    ("4 match + 1 mismatch => failed", dict(FIELDS_FULL, date_of_expiry='2099-01-01'), 'failed'),
]

all_pass = True
for desc, fields, expected in tests:
    _, status = sim(fields)
    ok = status == expected
    if not ok:
        all_pass = False
    marker = "PASS" if ok else "FAIL"
    print(f"  [{marker}] {desc:<40} got={status:<10} expected={expected}")

print(f"\n  {'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
print("=" * 80)
print("END OF HARNESS INSPECTION")
print("=" * 80)
