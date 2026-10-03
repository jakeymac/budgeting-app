"""Paste this into the WSGI configuration file of your PythonAnywhere web app.

Find it on the Web tab, under "Code" -> "WSGI configuration file". Delete the
boilerplate PythonAnywhere puts there and use this instead, filling in the
values marked CHANGE ME. This file is the one place your secrets live on
PythonAnywhere; it is not served to the web and never leaves the server.

Keep the values here in sync with the GitHub repository secrets:
DEPLOY_TOKEN here must equal the DEPLOY_TOKEN secret in GitHub Actions.
"""

import os
import sys

USERNAME = 'CHANGE-ME'                       # your PythonAnywhere username
PROJECT_DIR = f'/home/{USERNAME}/budget-app'  # must match PA_PROJECT_DIR in CI

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

os.environ['DJANGO_SETTINGS_MODULE'] = 'budget_app.settings'

# Generate with:
#   python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
os.environ['DJANGO_SECRET_KEY'] = 'CHANGE-ME'

os.environ['DJANGO_DEBUG'] = '0'
os.environ['DJANGO_ALLOWED_HOSTS'] = f'{USERNAME}.pythonanywhere.com'
os.environ['DJANGO_CSRF_TRUSTED_ORIGINS'] = f'https://{USERNAME}.pythonanywhere.com'
os.environ['DJANGO_TIME_ZONE'] = 'America/Denver'

# Two logins. The admin reaches the budget workspace; the member sees the
# overview and can log spending. Change a password here and redeploy to apply it.
os.environ['BUDGET_ADMIN_USER'] = 'CHANGE-ME'
os.environ['BUDGET_ADMIN_PASSWORD'] = 'CHANGE-ME'
os.environ['BUDGET_MEMBER_USER'] = 'CHANGE-ME'
os.environ['BUDGET_MEMBER_PASSWORD'] = 'CHANGE-ME'

# Must match the DEPLOY_TOKEN secret in GitHub. Generate with:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
os.environ['DEPLOY_TOKEN'] = 'CHANGE-ME'

# Keeping the database outside the deployed tree means a bad deploy can never
# reach it. Create the directory first: mkdir -p /home/USERNAME/budget-data
os.environ['BUDGET_DB_PATH'] = f'/home/{USERNAME}/budget-data/db.sqlite3'

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
