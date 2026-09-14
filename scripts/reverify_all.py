"""Re-verify all extracted documents against the updated auto_verify logic.

Run inside Docker:
  Get-Content scripts\\reverify_all.py -Raw | wsl.exe -d Ubuntu -u root -- bash -lc 'cd /opt/passportvault && docker compose exec -T web python -'
"""
import os
if 'DJANGO_SETTINGS_MODULE' not in os.environ:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
    import django; django.setup()

from vault.models import Document
from vault.crypto import unpack, pack
from vault.auto_verify import verify_document

# Re-verify documents that have already been extracted (have fields) and are
# not currently queued/processing.  Documents with an error_code (like
# WORKER_INTERRUPTED) are skipped because they have no extracted fields.
qs = Document.objects.filter(status__in=['approved', 'review', 'failed'], error_code='')
count = qs.count()
print(f"Found {count} extracted document(s) to re-verify.\n")

changed = 0
for doc in qs:
    payload = unpack(doc.payload, 'document:' + str(doc.id))
    fields = payload.get('fields', {})
    if not fields:
        print(f"  SKIP {doc.id} — no extracted fields.")
        continue

    old_status = doc.status
    verification, new_status = verify_document(doc.owner, fields, payload)
    payload['verification'] = verification
    doc.payload = pack(payload, 'document:' + str(doc.id))
    doc.status = new_status
    doc.save(update_fields=['payload', 'status', 'updated'])

    marker = '  ' if old_status == new_status else '→ '
    if old_status != new_status:
        changed += 1
    print(f"  {marker}{doc.id}  {old_status.upper():>8} → {new_status.upper():<8}  reason: {verification.get('reason','')[:100]}")

print(f"\nDone. {changed} document(s) changed status.")
