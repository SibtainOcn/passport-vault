from django.core.management.base import BaseCommand
from django.contrib.sessions.models import Session
class Command(BaseCommand):
    def handle(self,*args,**kwargs):
        Session.objects.all().delete()
        self.stdout.write('All sessions invalidated.')
