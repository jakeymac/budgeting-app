"""Create or update the budget's two logins from environment variables.

PythonAnywhere's free tier offers no way for CI to open a shell, so accounts are
provisioned on each deploy rather than by hand with createsuperuser.

Two roles:
  admin  (BUDGET_ADMIN_USER/_PASSWORD)   full access, including the workspace
  member (BUDGET_MEMBER_USER/_PASSWORD)  the overview, and logging spending
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Ensure the budget admin and member logins exist, from the environment.'

    def handle(self, *args, **options):
        for role, admin in (('ADMIN', True), ('MEMBER', False)):
            username = (os.environ.get(f'BUDGET_{role}_USER') or '').strip()
            password = os.environ.get(f'BUDGET_{role}_PASSWORD') or ''
            if not username or not password:
                self.stdout.write(f'{role.lower()}: BUDGET_{role}_USER/_PASSWORD not set, skipping.')
                continue
            self.sync(username, password, admin)

    def sync(self, username, password, admin):
        User = get_user_model()
        user, created = User.objects.get_or_create(**{User.USERNAME_FIELD: username})

        changed = []
        # Re-hashing an unchanged password would rotate the session auth hash
        # and sign the user out on every deploy.
        if not user.check_password(password):
            user.set_password(password)
            changed.append('password')
        if not user.is_active:
            user.is_active = True
            changed.append('is_active')
        # Set both directions: a member demoted from a previous admin-only
        # setup must actually lose the flags, not merely stop gaining them.
        if user.is_staff != admin or user.is_superuser != admin:
            user.is_staff = user.is_superuser = admin
            changed.append('promoted to admin' if admin else 'demoted to member')
        if created or changed:
            user.save()

        role = 'admin' if admin else 'member'
        if created:
            self.stdout.write(self.style.SUCCESS(f'{role}: created {username!r}.'))
        elif changed:
            self.stdout.write(self.style.SUCCESS(f'{role}: updated {username!r} ({", ".join(changed)}).'))
        else:
            self.stdout.write(f'{role}: {username!r} already up to date.')
