"""Reset WORKER_INTERRUPTED documents back to 'queued' for re-processing.

Run inside Docker:
  Get-Content scripts\\retry_interrupted.py -Raw | wsl.exe -d Ubuntu -u root -- bash -lc 'cd /opt/passportvault && docker compose exec -T web python -'
"""
import os
if 'DJANGO_SETTINGS_MODULE' not in os.environ:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
    import django; django.setup()

from vault.models import Document

interrupted = Document.objects.filter(status='failed', error_code='WORKER_INTERRUPTED')
count = interrupted.count()
print(f"Found {count} WORKER_INTERRUPTED document(s).")

if count == 0:
    print("Nothing to retry.")
else:
    for doc in interrupted:
        if doc.attempts >= 3:
            print(f"  SKIP {doc.id} — retry limit reached ({doc.attempts} attempts).")
            continue
        doc.status = 'queued'
        doc.error_code = ''
        doc.lease = None
        doc.lease_until = None
        doc.save(update_fields=['status', 'error_code', 'lease', 'lease_until', 'updated'])
        print(f"  REQUEUED {doc.id} (attempt {doc.attempts + 1})")
    print("Done. The worker will pick these up automatically.")
