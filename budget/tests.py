import json
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from .models import Budget, SpendingEvent, MonthlyPlan

PASSWORD = 'a-long-enough-test-password'


class SignedInTestCase(TestCase):
    """Every page and API route sits behind the shared login, so tests sign in first."""

    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(
            username='jmjohnson9699', password=PASSWORD, is_staff=True, is_superuser=True)
        self.client.force_login(self.user)

    def fresh_client(self, **kwargs):
        client = Client(**kwargs)
        client.force_login(self.user)
        return client


class BudgetAPITests(SignedInTestCase):
    def setUp(self):
        super().setUp()
        MonthlyPlan.objects.all().delete()  # Exercise compatibility for a pre-planner budget.
        self.budget = Budget.objects.create(pk=1, amount='1000.00', reserve='100.00', start='2026-09-01', end='2026-09-30')

    def post_event(self, **overrides):
        data = dict(description='Groceries', amount='12.34', category='Groceries', date='2026-09-20', note='Weekly shop')
        data.update(overrides)
        return self.client.post('/api/events/', json.dumps(data), content_type='application/json')

    def test_exact_money_period_boundaries_and_persistence(self):
        self.assertEqual(self.post_event(amount='0.10', date='2026-09-01').status_code, 201)
        self.post_event(amount='0.20', date='2026-09-30')
        self.post_event(amount='80.00', date='2026-08-31')
        result = self.fresh_client().get('/api/budget/').json()
        self.assertEqual(result['spent'], '0.30')
        self.assertEqual(result['available'], '899.70')
        self.assertEqual(len(result['events']), 3)

    def test_edit_and_delete_spending_recalculates_balance(self):
        result = self.post_event().json()
        event = result['events'][0]
        event['amount'] = '42.00'
        edited = self.client.patch(f"/api/events/{event['id']}/", json.dumps(event), content_type='application/json')
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(float(edited.json()['available']), 858)
        deleted = self.client.delete(f"/api/events/{event['id']}/")
        self.assertEqual(float(deleted.json()['available']), 900)
        self.assertFalse(SpendingEvent.objects.exists())

    def test_invalid_spending_does_not_write(self):
        for amount in ['-1', '0', 'NaN', 'Infinity', '1.001', '10000000000', None]:
            with self.subTest(amount=amount):
                self.assertEqual(self.post_event(amount=amount).status_code, 400)
        self.assertEqual(self.post_event(date='not-a-date').status_code, 400)
        self.assertEqual(self.post_event(description='   ').status_code, 400)
        self.assertEqual(self.post_event(category='Invalid').status_code, 400)
        self.assertFalse(SpendingEvent.objects.exists())

    def test_budget_edit_and_invalid_reserve(self):
        self.post_event(amount='100.00')
        data = self.client.get('/api/budget/').json()['budget']
        data.update(amount='2000.00', reserve='250.00')
        result = self.client.patch('/api/budget/', json.dumps(data), content_type='application/json')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(float(result.json()['available']), 1650)
        data['reserve'] = '2001.00'
        self.assertEqual(self.client.patch('/api/budget/', json.dumps(data), content_type='application/json').status_code, 400)
        self.budget.refresh_from_db()
        self.assertEqual(str(self.budget.reserve), '250.00')
        data.update(reserve='0', start='2026-10-01', end='2026-09-01')
        self.assertEqual(self.client.patch('/api/budget/', json.dumps(data), content_type='application/json').status_code, 400)

    def test_overspending_is_visible_and_historical_events_are_preserved(self):
        self.post_event(amount='1100')
        self.assertEqual(float(self.client.get('/api/budget/').json()['available']), -200)
        data = self.client.get('/api/budget/').json()['budget']
        data.update(start='2026-10-01', end='2026-10-31')
        result = self.client.patch('/api/budget/', json.dumps(data), content_type='application/json').json()
        self.assertEqual(float(result['spent']), 0)
        self.assertEqual(len(result['events']), 1)

    def test_csrf_protection_and_both_page_routes(self):
        client = self.fresh_client(enforce_csrf_checks=True)
        for route in ['/']:
            response = client.get(route)
            self.assertEqual(response.status_code, 200)
            # The bundle name carries a content hash, resolved via Vite's manifest.
            self.assertContains(response, '/static/frontend/app.')
        self.assertEqual(client.post('/api/events/', '{}', content_type='application/json').status_code, 403)
        token = client.cookies['csrftoken'].value
        response = client.post('/api/events/', json.dumps(dict(description='Coffee',amount='4.50',category='Dining',date='2026-09-20')),content_type='application/json',HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 201)


class MonthlyPlanningTests(SignedInTestCase):
    def setUp(self):
        super().setUp()
        from copy import deepcopy
        self.data = {
            'month': '2027-01', 'reserve': '100.00', 'extra_spending': '0.00',
            'incomes': [{'name': 'Salary', 'amount': '5000.00'}],
            'cards': [{'name': 'Visa', 'minimum': '75.00', 'balance': '2000.00'}],
            'expenses': [{'name': 'Rent', 'amount': '1500.00'}, {'name': 'Car', 'amount': '300.00'}],
            'insurance': {'premium': '800.00', 'percentage': '25.00', 'start_month': '2027-01'},
        }
        MonthlyPlan.objects.all().delete()
        for kind in ['actual', 'theoretical']:
            MonthlyPlan.objects.create(kind=kind, data=deepcopy(self.data))
        SpendingEvent.objects.create(description='Groceries', amount='50.00', category='Groceries', date='2027-01-15')

    def save(self, kind='actual', data=None, revision=1):
        return self.client.put(f'/api/plans/{kind}/', json.dumps({'data': data or self.data, 'revision': revision}), content_type='application/json')

    def test_all_required_expenses_reduce_available_but_balance_does_not(self):
        response = self.client.get('/api/budget/').json()
        summary = response['summaries']['actual']
        self.assertEqual(summary['required'], '2075.00')
        self.assertEqual(summary['available'], '2775.00')
        self.assertEqual(response['available'], '2775.00')
        self.assertEqual(summary['debt'], '2000.00')
        self.assertEqual(response['budget']['start'], '2027-01-01')
        self.assertEqual(response['budget']['end'], '2027-01-31')

    def test_insurance_start_month_and_half_cent_rounding(self):
        from .planning import summarize
        from decimal import Decimal
        self.data['insurance'].update(premium='100.05', percentage='10.00')
        for month, expected in [('2026-12', '0.00'), ('2027-01', '10.01'), ('2027-02', '10.01')]:
            self.data['month'] = month
            self.assertEqual(summarize(self.data, Decimal('0'))['insurance'], expected)

    def test_theoretical_save_is_durable_and_never_changes_actual_or_events(self):
        self.data['insurance']['percentage'] = '50.00'
        self.data['extra_spending'] = '125.00'
        result = self.save('theoretical').json()
        self.assertEqual(result['summaries']['theoretical']['available'], '2450.00')
        self.assertEqual(result['summaries']['actual']['available'], '2775.00')
        self.assertEqual(result['available'], '2775.00')
        self.assertEqual(SpendingEvent.objects.count(), 1)
        reloaded = self.fresh_client().get('/api/budget/').json()
        self.assertEqual(reloaded['plans']['theoretical']['data']['extra_spending'], '125.00')
        self.assertEqual(MonthlyPlan.objects.count(), 2)

    def test_actual_save_leaves_theoretical_alone(self):
        self.data['incomes'][0]['amount'] = '6000.00'
        response = self.save()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['available'], '3775.00')
        self.assertEqual(response.json()['plans']['theoretical']['data']['incomes'][0]['amount'], '5000.00')

    def test_invalid_plan_does_not_partially_save(self):
        from copy import deepcopy
        variants = []
        for value in ['-1', 'NaN', 'Infinity', '1.001', None, '10000000000']:
            plan = deepcopy(self.data); plan['incomes'][0]['amount'] = value; variants.append(plan)
        for value in ['101', '-1', '0.001']:
            plan = deepcopy(self.data); plan['insurance']['percentage'] = value; variants.append(plan)
        plan = deepcopy(self.data); plan['insurance']['start_month'] = '2027-13'; variants.append(plan)
        plan = deepcopy(self.data); plan['month'] = '0000-01'; variants.append(plan)
        plan = deepcopy(self.data); plan['cards'][0]['minimum'] = '2001'; variants.append(plan)
        plan = deepcopy(self.data); plan['expenses'][0]['name'] = ' '; variants.append(plan)
        plan = deepcopy(self.data); plan['extra_spending'] = '1'; variants.append(plan)
        for data in variants:
            with self.subTest(data=data):
                self.assertEqual(self.save(data=data).status_code, 400)
        actual = MonthlyPlan.objects.get(pk='actual')
        self.assertEqual(actual.data, self.data)
        self.assertEqual(actual.revision, 1)

    def test_stale_save_does_not_overwrite_newer_numbers(self):
        self.assertEqual(self.save().status_code, 200)
        self.data['incomes'][0]['amount'] = '1.00'
        self.assertEqual(self.save().status_code, 409)
        self.assertEqual(MonthlyPlan.objects.get(pk='actual').data['incomes'][0]['amount'], '5000.00')

    def test_unknown_slot_rejected(self):
        self.assertEqual(self.save('third-budget').status_code, 404)
        self.assertEqual(MonthlyPlan.objects.count(), 2)

    def test_empty_rows_and_negative_cashflow_supported(self):
        self.data.update(incomes=[], cards=[], expenses=[])
        result = self.save().json()
        self.assertEqual(result['available'], '-350.00')
        self.assertEqual(result['summaries']['actual']['minimums'], '0.00')

    def test_spending_outside_selected_month_not_subtracted(self):
        self.data['month'] = '2027-02'
        result = self.save().json()
        self.assertEqual(result['spent'], '0.00')
        self.assertEqual(result['available'], '2825.00')
        self.assertEqual(result['budget']['end'], '2027-02-28')
        self.assertEqual(len(result['events']), 1)

    def test_plan_endpoint_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.put('/api/plans/actual/', json.dumps({'data': self.data, 'revision': 1}), content_type='application/json')
        self.assertEqual(response.status_code, 403)


class AccessControlTests(TestCase):
    """The deployed app is on the public internet; nothing but the login page is open."""

    def test_anonymous_visitors_are_sent_to_the_login_page(self):
        for route in ['/', '/api/budget/']:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 302, route)
            self.assertTrue(response['Location'].startswith('/login/'), route)

    def test_login_page_and_health_check_stay_open(self):
        self.assertEqual(self.client.get('/login/').status_code, 200)
        self.assertEqual(self.client.get('/healthz/').json(), {'status': 'ok'})

    def test_signing_in_grants_access_and_signing_out_revokes_it(self):
        get_user_model().objects.create_user(username='teresa', password=PASSWORD)
        self.assertTrue(self.client.login(username='teresa', password=PASSWORD))
        self.assertEqual(self.client.get('/api/budget/').status_code, 200)
        self.client.post('/logout/')
        self.assertEqual(self.client.get('/api/budget/').status_code, 302)


class DeployHookTests(TestCase):
    def test_hook_is_absent_unless_a_token_is_configured(self):
        with override_settings(DEPLOY_TOKEN=None):
            self.assertEqual(self.client.post('/_deploy/finalize/').status_code, 404)

    def test_wrong_token_is_indistinguishable_from_a_disabled_hook(self):
        with override_settings(DEPLOY_TOKEN='the-real-token'):
            response = self.client.post('/_deploy/finalize/', HTTP_X_DEPLOY_TOKEN='guess')
            self.assertEqual(response.status_code, 404)

    def test_correct_token_runs_migrations_and_bootstraps_the_login(self):
        import os
        os.environ['BUDGET_ADMIN_USER'] = 'teresa'
        os.environ['BUDGET_ADMIN_PASSWORD'] = PASSWORD
        try:
            with override_settings(DEPLOY_TOKEN='the-real-token'):
                response = self.client.post('/_deploy/finalize/', HTTP_X_DEPLOY_TOKEN='the-real-token')
        finally:
            del os.environ['BUDGET_ADMIN_USER'], os.environ['BUDGET_ADMIN_PASSWORD']
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        user = get_user_model().objects.get(username='teresa')
        self.assertTrue(user.is_superuser and user.check_password(PASSWORD))


ENV_KEYS = ('BUDGET_ADMIN_USER', 'BUDGET_ADMIN_PASSWORD',
            'BUDGET_MEMBER_USER', 'BUDGET_MEMBER_PASSWORD')


class BootstrapAccountsCommandTests(TestCase):
    def run_command(self, **env):
        import os
        from io import StringIO
        from django.core.management import call_command
        previous = {key: os.environ.get(key) for key in ENV_KEYS}
        for key in ENV_KEYS:
            os.environ.pop(key, None)
            if env.get(key) is not None:
                os.environ[key] = env[key]
        try:
            out = StringIO()
            call_command('bootstrap_accounts', stdout=out)
            return out.getvalue()
        finally:
            for key, value in previous.items():
                os.environ.pop(key, None)
                if value is not None:
                    os.environ[key] = value

    def admin_env(self, user='jmjohnson9699', password=PASSWORD):
        return {'BUDGET_ADMIN_USER': user, 'BUDGET_ADMIN_PASSWORD': password}

    def member_env(self, user='teresa', password=PASSWORD):
        return {'BUDGET_MEMBER_USER': user, 'BUDGET_MEMBER_PASSWORD': password}

    def test_without_credentials_it_leaves_accounts_alone(self):
        self.run_command()
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_it_creates_the_two_roles_with_the_right_privileges(self):
        self.run_command(**self.admin_env(), **self.member_env())
        admin = get_user_model().objects.get(username='jmjohnson9699')
        member = get_user_model().objects.get(username='teresa')
        self.assertTrue(admin.is_staff and admin.is_superuser)
        self.assertFalse(member.is_staff or member.is_superuser)

    def test_a_member_inherited_from_the_old_single_account_setup_is_demoted(self):
        # Teresa was created as a superuser when the app had one shared login.
        get_user_model().objects.create_user(
            username='teresa', password=PASSWORD, is_staff=True, is_superuser=True)
        output = self.run_command(**self.member_env())
        member = get_user_model().objects.get(username='teresa')
        self.assertFalse(member.is_staff or member.is_superuser)
        self.assertIn('demoted to member', output)

    def test_it_is_idempotent_and_keeps_the_password_hash_stable(self):
        self.run_command(**self.member_env())
        first = get_user_model().objects.get(username='teresa').password
        output = self.run_command(**self.member_env())
        # Re-hashing an unchanged password would rotate the session auth hash
        # and sign Teresa out on every deploy.
        self.assertEqual(get_user_model().objects.get(username='teresa').password, first)
        self.assertIn('already up to date', output)

    def test_a_changed_password_is_applied(self):
        self.run_command(**self.member_env())
        self.run_command(**self.member_env(password='a-different-long-password'))
        self.assertTrue(get_user_model().objects.get(username='teresa')
                        .check_password('a-different-long-password'))


class MemberPermissionTests(TestCase):
    """Teresa records spending; only an administrator changes the budget."""

    def setUp(self):
        super().setUp()
        self.member = get_user_model().objects.create_user(username='teresa', password=PASSWORD)
        self.client.force_login(self.member)

    def test_she_sees_her_overview(self):
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_the_api_tells_the_frontend_she_is_not_an_administrator(self):
        self.assertIs(self.client.get('/api/budget/').json()['is_admin'], False)

    def test_the_old_workspace_address_sends_her_to_the_single_page(self):
        response = self.client.get('/workspace/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/')

    def test_she_can_log_spending(self):
        response = self.client.post(
            '/api/events/',
            json.dumps(dict(description='Coffee', amount='4.50', category='Dining', date='2026-09-20')),
            content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(SpendingEvent.objects.count(), 1)

    def test_she_cannot_edit_the_monthly_plan(self):
        response = self.client.put(
            '/api/plans/actual/',
            json.dumps({'revision': 1, 'data': {}}), content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_she_cannot_patch_the_budget(self):
        MonthlyPlan.objects.all().delete()
        Budget.objects.create(pk=1, amount='1000.00', reserve='0.00', start='2026-09-01', end='2026-09-30')
        data = self.client.get('/api/budget/').json()['budget']
        data['amount'] = '99999.00'
        response = self.client.patch('/api/budget/', json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(str(Budget.objects.get(pk=1).amount), '1000.00')


class AdminPermissionTests(TestCase):
    def setUp(self):
        super().setUp()
        self.admin = get_user_model().objects.create_user(
            username='jmjohnson9699', password=PASSWORD, is_staff=True, is_superuser=True)
        self.client.force_login(self.admin)

    def test_the_old_workspace_address_redirects_for_him_too(self):
        # One page, two states: /workspace/ survives only for old bookmarks.
        response = self.client.get('/workspace/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/')

    def test_he_reaches_the_single_page(self):
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_the_api_marks_him_an_administrator(self):
        self.assertIs(self.client.get('/api/budget/').json()['is_admin'], True)
