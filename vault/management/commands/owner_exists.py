from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
class Command(BaseCommand):
    def handle(self,*args,**kwargs):
        if not get_user_model().objects.exists(): raise CommandError('Owner has not been created yet.')
        self.stdout.write('Owner exists.')
