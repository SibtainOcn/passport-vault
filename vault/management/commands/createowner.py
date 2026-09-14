import getpass, secrets, time
import pyotp
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import make_password
from django.db import transaction
from vault.models import OwnerSecurity, LoginGuard, AuditHead
from vault.crypto import seal
from vault.audit import event
class Command(BaseCommand):
    help='Create the sole owner locally and enroll authenticator MFA. No default credentials.'
    def handle(self,*args,**kwargs):
        User=get_user_model()
        if User.objects.exists(): raise CommandError('Owner already exists. No second user is allowed.')
        username=input('Choose login username: ').strip()
        if not username or len(username)>150: raise CommandError('Invalid username.')
        password=getpass.getpass('Choose password (14+ characters): ')
        if password!=getpass.getpass('Repeat password: '): raise CommandError('Passwords do not match.')
        try: validate_password(password,User(username=username))
        except Exception as exc: raise CommandError(str(exc))
        secret=pyotp.random_base32(); totp=pyotp.TOTP(secret)
        self.stdout.write('In your authenticator choose Manual entry / Time based / SHA1 / 6 digits / 30 seconds.')
        self.stdout.write('Account: Passport Vault'); self.stdout.write('Secret: '+secret)
        code=input('Enter current authenticator code: ').strip()
        if not totp.verify(code): raise CommandError('Invalid code. Check phone time and try setup again.')
        recovery=[secrets.token_hex(8) for _ in range(8)]
        with transaction.atomic():
            if User.objects.exists(): raise CommandError('Owner already exists.')
            user=User.objects.create_user(username=username,password=password)
            OwnerSecurity.objects.create(user=user,secret=seal(secret.encode(),'mfa:'+str(user.id)),last_step=int(time.time())//30,recovery=[make_password(x) for x in recovery])
            LoginGuard.objects.get_or_create(pk=1); AuditHead.objects.get_or_create(pk=1)
            event(user.pk,'owner_created')
        self.stdout.write('Store these one-use recovery codes OFFLINE. They are shown only once:')
        for code in recovery: self.stdout.write(code)
        self.stdout.write('Owner created. Wait for the next authenticator code before first login.')
