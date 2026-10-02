"""Create or update the single shared login from environment variables.

PythonAnywhere's free tier offers no way for CI to open a shell, so the account
is provisioned from BUDGET_ADMIN_USER / BUDGET_ADMIN_PASSWORD on each deploy
instead of by hand with createsuperuser.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Ensure the shared budget login exists, using BUDGET_ADMIN_USER and BUDGET_ADMIN_PASSWORD.'

    def handle(self, *args, **options):
        username = (os.environ.get('BUDGET_ADMIN_USER') or '').strip()
        password = os.environ.get('BUDGET_ADMIN_PASSWORD') or ''

        if not username or not password:
            self.stdout.write('bootstrap_admin: BUDGET_ADMIN_USER/BUDGET_ADMIN_PASSWORD not set, leaving accounts alone.')
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            **{User.USERNAME_FIELD: username},
            defaults={'is_staff': True, 'is_superuser': True},
        )

        changed = []
        # Re-hashing an unchanged password would rotate the session auth hash and
        # sign everyone out on every deploy, so only touch it when it differs.
        if not user.check_password(password):
            user.set_password(password)
            changed.append('password')
        if not user.is_active:
            user.is_active = True
            changed.append('is_active')
        if not (user.is_staff and user.is_superuser):
            user.is_staff = user.is_superuser = True
            changed.append('permissions')
        if created or changed:
            user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f'bootstrap_admin: created {username!r}.'))
        elif changed:
            self.stdout.write(self.style.SUCCESS(f'bootstrap_admin: updated {username!r} ({", ".join(changed)}).'))
        else:
            self.stdout.write(f'bootstrap_admin: {username!r} already up to date.')
