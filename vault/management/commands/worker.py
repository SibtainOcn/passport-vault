import time, uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction, close_old_connections
from django.utils import timezone
from vault.models import Document, Page
from vault.crypto import pack, unpack, unseal, seal, blind
from vault.fields import normalize
from vault.sandbox import run
from vault.audit import event
from vault.auto_verify import verify_document

class Command(BaseCommand):
    help='Durable PostgreSQL OCR worker. Run one worker on small machines.'
    def add_arguments(self,p): p.add_argument('--once',action='store_true')
    def handle(self,*args,**options):
        while True:
            close_old_connections()
            # Expired leases are failed, never silently approved or merged.
            Document.objects.filter(status='processing',lease_until__lt=timezone.now()).update(status='failed',error_code='WORKER_INTERRUPTED',lease=None)
            with transaction.atomic():
                d=Document.objects.select_for_update(skip_locked=True).filter(status='queued').order_by('created').first()
                if d:
                    d.status='processing'; d.attempts+=1; d.lease=uuid.uuid4(); d.lease_until=timezone.now()+timedelta(minutes=25); d.save()
                    pk,lease=d.pk,d.lease
            if not d:
                if options['once']: return
                time.sleep(2); continue
            try:
                data=unpack(d.payload,'document:'+str(d.id))
                sources=[(unseal(s.data,'source:'+str(s.id)),s.kind) for s in d.sources.order_by('order')]
                result=run('ocr',(sources,data.get('language','eng')),1200)
                previews=result.pop('previews'); data.update(result)
                with transaction.atomic():
                    current=Document.objects.select_for_update().get(pk=pk)
                    if current.lease!=lease or current.status!='processing': continue
                    current.pages.all().delete()
                    for i,img in enumerate(previews,1):
                        p=Page(document=current,number=i); p.data=seal(img,'page:'+str(p.id)); p.save()
                    verification, final_status = verify_document(current.owner, data.get('fields',{}), data)
                    data['verification']=verification
                    current.payload=pack(data,'document:'+str(pk)); current.status=final_status; current.lease=None; current.lease_until=None; current.error_code='' 
                    try: number=normalize('passport_number',data['fields'].get('passport_number',''))
                    except ValueError: number=''
                    current.passport_index=blind(number) if number else ''; current.save()
                    event('worker','extraction_finished',pk)
            except Exception as exc:
                code='OCR_FAILED_RESCAN_OR_RETRY'
                allowed={'PDF_CORRUPT_OR_PASSWORD','TOO_MANY_PAGES','INVALID_PAGE_SIZE','UNSUPPORTED_IMAGE','ANIMATED_IMAGE','CORRUPT_OR_OVERSIZED_IMAGE','OCR_TIMEOUT','OCR_ENGINE_OR_LANGUAGE_ERROR','EMPTY_DOCUMENT'}
                if isinstance(exc,ValueError) and str(exc) in allowed: code=str(exc)
                # No raw exception, OCR data, filename or input bytes in logs.
                Document.objects.filter(pk=pk,lease=lease).update(status='failed',lease=None,lease_until=None,error_code=code)
                event('worker','extraction_failed',pk)
            if options['once']: return
