"""
Django settings for budget_app.

Configuration comes from the environment. For local work, put the same names in
a `.env` file next to manage.py (see .env.example); real environment variables
always win over `.env`. On PythonAnywhere the values are set in the web app's
WSGI file — see deploy/wsgi_pythonanywhere.py.
"""

import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    """Minimal KEY=value reader. No export syntax, no interpolation, no quotes beyond stripping one matched pair."""
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
            value = value[1:-1]
        os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / '.env')


def env(name, default=None):
    value = os.environ.get(name)
    return default if value is None or value == '' else value


def env_bool(name, default=False):
    return env(name, '1' if default else '0').strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name):
    return [item.strip() for item in env(name, '').split(',') if item.strip()]


DEBUG = env_bool('DJANGO_DEBUG', default=False)

SECRET_KEY = env('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            'DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off. '
            'Generate one with: python -c "from django.core.management.utils '
            'import get_random_secret_key as k; print(k())"'
        )
    SECRET_KEY = 'django-insecure-local-development-only-do-not-deploy-this'

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS') or (
    ['localhost', '127.0.0.1', '10.0.0.33', '[::1]'] if DEBUG else []
)

# PythonAnywhere terminates TLS in front of the app, so CSRF needs the public
# origin spelled out with its scheme.
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')


# Application definition

INSTALLED_APPS = [
    'budget',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # Everything requires a login unless the view opts out with @login_not_required.
    'django.contrib.auth.middleware.LoginRequiredMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'budget_app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'budget_app.wsgi.application'


# Database

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': Path(env('BUDGET_DB_PATH', str(BASE_DIR / 'db.sqlite3'))),
        'OPTIONS': {'timeout': 20},
    }
}


# Authentication

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'login'

SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # A month; this is a personal budget, not a bank.
SESSION_SAVE_EVERY_REQUEST = True


# Internationalization

LANGUAGE_CODE = 'en-us'
TIME_ZONE = env('DJANGO_TIME_ZONE', 'UTC')
USE_I18N = True
USE_TZ = True


# Static files

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


# Deployment hook. Unset means the /_deploy/finalize/ endpoint is disabled.
DEPLOY_TOKEN = env('DEPLOY_TOKEN')


# Hardening, only once DEBUG is off. PythonAnywhere forwards the original
# scheme in X-Forwarded-Proto and already redirects HTTP to HTTPS at the edge.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'
    X_FRAME_OPTIONS = 'DENY'
    # An hour by default. Raise it once the deployment has proven itself; a long
    # max-age is hard to walk back, because browsers remember it.
    SECURE_HSTS_SECONDS = int(env('DJANGO_HSTS_SECONDS', '3600'))

# `manage.py test` runs with DEBUG off, and the test client speaks plain HTTP,
# so an SSL redirect would answer 301 before any request reached a view.
# `check --deploy` still sees the real value and vets it.
if 'test' in sys.argv:
    SECURE_SSL_REDIRECT = False

# security.W021/W022 want includeSubDomains and preload on top of HSTS. Neither
# belongs on a shared *.pythonanywhere.com host: we own one name under it, not
# the domain, so both directives would reach far beyond this app.
SILENCED_SYSTEM_CHECKS = ['security.W021', 'security.W022']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
