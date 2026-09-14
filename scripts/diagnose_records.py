import os, sys, json
from datetime import datetime

# Setup Django if not already running in shell
if 'DJANGO_SETTINGS_MODULE' not in os.environ:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
    try:
        import django
        django.setup()
    except Exception as e:
        pass

from vault.models import Document, Workbook, Source
from vault.crypto import unpack
from vault.auto_verify import _compare_document, _active_master
from vault.ocr_quality import apply_quality_gate
from vault.fields import FIELDS, normalize

print("=" * 80)
print("PASSPORTVAULT DIAGNOSTIC & LOGIC TEST HARNESS")
print("=" * 80)

# 1. Inspect Active Master Excel
print("\n[1] ACTIVE MASTER EXCEL INSPECTION:")
workbooks = Workbook.objects.filter(active=True)
if not workbooks.exists():
    print("  ❌ NO ACTIVE MASTER EXCEL FOUND!")
    all_wbs = Workbook.objects.all()
    print(f"  Total workbooks in DB: {all_wbs.count()}")
    for wb in all_wbs:
        print(f"    - ID: {wb.id}, Name: {wb.name}, Active: {wb.active}, Owner: {wb.owner.username}")
else:
    for wb in workbooks:
        print(f"  ✓ Active Master: ID={wb.id}, Name='{wb.name}', Owner={wb.owner.username}")
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

        # Check required approval fields in mapping
        approval_fields = {'passport_number', 'dob', 'gender', 'date_of_issue', 'date_of_expiry'}
        missing_approval = sorted(approval_fields - set(mapping))
        if missing_approval:
            print(f"    ❌ MISSING MANDATORY APPROVAL FIELDS IN MAPPING: {missing_approval}")
        else:
            print(f"    ✓ All 5 mandatory approval fields are mapped.")

        # Unpack sheet contents to inspect rows
        try:
            sheets = unpack(wb.data, 'workbook:' + str(wb.id))
            if sheet_name not in sheets:
                print(f"    ❌ Sheet '{sheet_name}' NOT FOUND in workbook sheets: {list(sheets.keys())}")
            else:
                rows = sheets[sheet_name]
                print(f"    - Total rows in '{sheet_name}': {len(rows)}")
                # Show sample rows
                for r_idx, r in enumerate(rows[:5]):
                    print(f"      Row {r_idx + 1}: {r}")
        except Exception as e:
            print(f"    ❌ Error unpacking master excel: {e}")

# 2. Inspect Documents in DB
print("\n[2] CURRENT DOCUMENTS INSPECTION:")
docs = list(Document.objects.all().order_by('-created'))
print(f"  Total documents in DB: {len(docs)}")

for idx, doc in enumerate(docs, 1):
    print("\n" + "-" * 75)
    try:
        payload = unpack(doc.payload, 'document:' + str(doc.id))
    except Exception as e:
        print(f"  Doc #{idx} [ID: {doc.id}]: ❌ UNPACK ERROR: {e}")
        continue

    doc_name = payload.get('name', 'Unknown')
    extracted_fields = payload.get('fields', {})
    verification = payload.get('verification', {})
    warnings = payload.get('warnings', [])
    ocr_quality = payload.get('ocr_quality', {})
    error_code = doc.error_code

    print(f"  Doc #{idx}: {doc_name}")
    print(f"    Database Status : {doc.status.upper()}")
    print(f"    Document ID     : {doc.id}")
    print(f"    Created At      : {doc.created}")
    print(f"    Error Code      : '{error_code}'")
    print(f"    Attempts        : {doc.attempts}")
    print(f"    Lease Until     : {doc.lease_until}")
    print(f"    Pages in DB     : {doc.pages.count()}")
    print(f"    Sources in DB   : {doc.sources.count()}")

    print(f"\n    Extracted Fields:")
    if not extracted_fields:
        print(f"      ❌ NO FIELDS EXTRACTED (Empty dictionary)")
    else:
        for f, val in extracted_fields.items():
            if val:
                print(f"      - {f:<18}: {val}")
            else:
                print(f"      - {f:<18}: [EMPTY]")

    # Check why full_name is empty
    if not extracted_fields.get('full_name'):
        print(f"      ⚠️ Note: 'full_name' is missing, UI will display 'Awaiting extraction'.")

    print(f"\n    Stored Verification Data:")
    print(f"      - Status: {verification.get('status')}")
    print(f"      - Reason: {verification.get('reason')}")
    comps = verification.get('comparisons', {})
    if comps:
        print(f"      - Comparisons Breakdown:")
        for f, item in comps.items():
            st = item.get('status')
            ex = item.get('excel')
            oc = item.get('passport')
            flag = "✓" if st == "Match" else "❌"
            print(f"        {flag} {f:<16} | Status: {st:<20} | Excel: '{ex}' | OCR: '{oc}'")
    else:
        print(f"      - No comparisons recorded.")

    if warnings:
        print(f"\n    OCR Warnings:")
        for w in warnings[:6]:
            print(f"      - {w}")

    # 3. Simulate Logic Locally for This Document
    print(f"\n    [TEST HARNESS SIMULATION FOR DOC #{idx}]:")
    if doc.status == 'failed' and error_code == 'WORKER_INTERRUPTED':
        print(f"      ❌ Root cause: Document was in 'processing' state when worker was stopped, restarted, or lease expired.")
        print(f"         The lease timeout is 25 minutes. If EasyOCR ran out of memory (OOM) or machine rebooted, it triggers WORKER_INTERRUPTED.")
    elif extracted_fields:
        # Run _compare_document directly
        sim_verif, sim_status = _compare_document(doc.owner, extracted_fields)
        print(f"      -> Step 1 (_compare_document): status='{sim_status}', reason='{sim_verif.get('reason')}'")

        # Check comparisons
        for f, item in sim_verif.get('comparisons', {}).items():
            if item.get('status') != 'Match':
                print(f"         🚨 Culprit Field: '{f}' => Status: {item.get('status')} (Excel='{item.get('excel')}' vs OCR='{item.get('passport')}')")

        # Run apply_quality_gate
        final_verif, final_status = apply_quality_gate(sim_verif, sim_status, payload)
        print(f"      -> Step 2 (apply_quality_gate): status='{final_status}', reason='{final_verif.get('reason')}'")
        if sim_status == 'approved' and final_status == 'review':
            print(f"         🚨 Quality gate blocked approval! Reason: {final_verif.get('reason')}")
    else:
        print(f"      ⚠️ Cannot simulate comparison because no OCR fields were extracted.")

print("\n" + "=" * 80)
print("END OF HARNESS INSPECTION")
print("=" * 80)
