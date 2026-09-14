import uuid
from django.conf import settings
from django.db import models
class OwnerSecurity(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    secret = models.BinaryField()
    last_step = models.BigIntegerField(default=-1)
    recovery = models.JSONField(default=list)
class LoginGuard(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    failures = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True)
class Document(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20,default='queued',db_index=True)
    payload = models.BinaryField()  # encrypted names, fields, OCR evidence, error details
    passport_index = models.CharField(max_length=64,blank=True,db_index=True)
    content_index = models.CharField(max_length=64,db_index=True)
    revision = models.PositiveIntegerField(default=0)
    attempts = models.PositiveIntegerField(default=0)
    lease = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    error_code = models.CharField(max_length=40,blank=True)
class Source(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    document = models.ForeignKey(Document,on_delete=models.CASCADE,related_name='sources')
    order = models.PositiveIntegerField()
    kind = models.CharField(max_length=10)
    data = models.BinaryField()
class Page(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    document = models.ForeignKey(Document,on_delete=models.CASCADE,related_name='pages')
    number = models.PositiveIntegerField()
    data = models.BinaryField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['document','number'],name='page_unique')]
class Revision(models.Model):
    document = models.ForeignKey(Document,on_delete=models.CASCADE,related_name="revisions")
    version = models.PositiveIntegerField()
    at = models.DateTimeField(auto_now_add=True)
    data = models.BinaryField()
class Workbook(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=200,default='Master Excel')
    active = models.BooleanField(default=False,db_index=True)
    config = models.JSONField(default=dict)
    data = models.BinaryField()
class Report(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created = models.DateTimeField(auto_now_add=True)
    data = models.BinaryField()
class AuditHead(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True,default=1)
    digest = models.CharField(max_length=64,default='0'*64)
class Audit(models.Model):
    at = models.DateTimeField()
    actor = models.CharField(max_length=30)
    action = models.CharField(max_length=50)
    target = models.CharField(max_length=80,blank=True)
    previous = models.CharField(max_length=64)
    digest = models.CharField(max_length=64)
