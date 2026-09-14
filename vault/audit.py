import json
from django.db import transaction
from django.utils import timezone
from .models import AuditHead, Audit
from .crypto import blind

def event(actor,action,target=''):
    with transaction.atomic():
        AuditHead.objects.get_or_create(pk=1)
        head = AuditHead.objects.select_for_update().get(pk=1)
        at = timezone.now()
        actor, target = str(actor), str(target)
        payload = [at.isoformat(),actor,action,target,head.digest]
        digest = blind(json.dumps(payload,separators=(',',':')))
        Audit.objects.create(at=at,actor=actor,action=action,target=target,previous=head.digest,digest=digest)
        head.digest = digest; head.save(update_fields=['digest'])
