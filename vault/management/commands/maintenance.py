import json
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from vault.models import Workbook, Report, Audit, AuditHead
from vault.crypto import blind
class Command(BaseCommand):
    help='Remove temporary workbooks, optionally old reports; verify audit chain.'
    def add_arguments(self,p):
        p.add_argument('--report-days',type=int,default=0)
    def handle(self,*args,**options):
        Workbook.objects.filter(created__lt=timezone.now()-timedelta(days=1)).delete()
        days=options['report_days']
        if days<0: raise CommandError('Days must be positive.')
        if days: Report.objects.filter(created__lt=timezone.now()-timedelta(days=days)).delete()
        previous='0'*64
        for a in Audit.objects.order_by('id').iterator():
            expected=blind(json.dumps([a.at.isoformat(),a.actor,a.action,a.target,previous],separators=(',',':')))
            if a.previous!=previous or a.digest!=expected: raise CommandError('AUDIT CHAIN INVALID')
            previous=a.digest
        head=AuditHead.objects.first()
        if head and head.digest!=previous: raise CommandError('AUDIT HEAD INVALID')
        self.stdout.write('Audit chain verified. Retention cleanup completed.')
