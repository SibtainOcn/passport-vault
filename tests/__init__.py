import os
import sys

# Ensure Django is configured before any test module imports Django components.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
os.environ.setdefault('VAULT_TESTING', '1')

import django
django.setup()
