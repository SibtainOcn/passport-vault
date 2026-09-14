import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
TESTING = os.getenv('VAULT_TESTING') == '1'
def secret(name):
    if TESTING:
        return {'master': '11'*32, 'index': '22'*32, 'django': 'test-only-secret-not-for-production'*2, 'db':'test'}[name]
    return (Path(os.getenv('SECRETS_DIR','/run/vault-secrets')) / name).read_text().strip()
SECRET_KEY = secret('django')
MASTER_KEY = bytes.fromhex(secret('master'))
INDEX_KEY = bytes.fromhex(secret('index'))
DEBUG = False
ALLOWED_HOSTS = ['localhost', '127.0.0.1'] + (['testserver'] if TESTING else [])
INSTALLED_APPS = ['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.staticfiles','vault']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','vault.middleware.PrivacyHeaders','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'app.urls'
WSGI_APPLICATION = 'app.wsgi.application'
DATABASES = {'default': {'ENGINE':'django.db.backends.postgresql','NAME':'passportvault','USER':'passportvault','PASSWORD':secret('db'),'HOST':'db','PORT':5432,'CONN_MAX_AGE':60,'OPTIONS':{'sslmode':'verify-full','sslrootcert':str(Path(os.getenv('SECRETS_DIR','/run/vault-secrets'))/'internal.crt')}}}
if TESTING:
    DATABASES = {'default': {'ENGINE':'django.db.backends.sqlite3','NAME':os.getenv('TEST_DB',str(BASE_DIR/'test.sqlite3'))}}
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'frontend/dist'],'APP_DIRS':True}]
STATIC_URL = '/assets/'
STATIC_ROOT = BASE_DIR/'staticfiles'
STATICFILES_DIRS = [BASE_DIR/'frontend/dist/assets'] if (BASE_DIR/'frontend/dist/assets').exists() else []
USE_TZ = True
TIME_ZONE = 'UTC'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not TESTING
SESSION_COOKIE_SAMESITE = 'Strict'
SESSION_COOKIE_AGE = 1800
SESSION_SAVE_EVERY_REQUEST = False
CSRF_COOKIE_SECURE = not TESTING
CSRF_COOKIE_SAMESITE = 'Strict'
CSRF_TRUSTED_ORIGINS = ['https://localhost:8443']
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO','https')
SECURE_SSL_REDIRECT = not TESTING
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000 if not TESTING else 0
X_FRAME_OPTIONS = 'DENY'
DATA_UPLOAD_MAX_MEMORY_SIZE = 30*1024*1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 30*1024*1024
FILE_UPLOAD_HANDLERS = ['django.core.files.uploadhandler.MemoryFileUploadHandler']
DATA_UPLOAD_MAX_NUMBER_FILES = 12
DATA_UPLOAD_MAX_NUMBER_FIELDS = 50
AUTH_PASSWORD_VALIDATORS = [
 {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':14}},
 {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},
 {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
# Do not log request bodies, URLs containing PII, filenames, OCR text or values.
LOGGING = {'version':1,'disable_existing_loggers':False,'handlers':{'console':{'class':'logging.StreamHandler'}},'root':{'handlers':['console'],'level':'WARNING'}}

SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
