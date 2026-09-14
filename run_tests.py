"""Run all tests with the correct environment for local development.

Usage: python run_tests.py
"""
import os
import sys

os.environ.setdefault('VAULT_TESTING', '1')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

import django
django.setup()

from django.test.utils import get_runner
from django.conf import settings


if __name__ == '__main__':
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2)
    failures = test_runner.run_tests(['tests'])
    sys.exit(bool(failures))
