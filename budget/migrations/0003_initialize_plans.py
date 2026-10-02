from copy import deepcopy
from datetime import date
from django.db import migrations


def seed(apps, schema_editor):
    Budget = apps.get_model('budget', 'Budget')
    Plan = apps.get_model('budget', 'MonthlyPlan')
    budget = Budget.objects.filter(pk=1).first()
    today = date.today()
    data = {
        'month': (budget.start if budget else today).strftime('%Y-%m'),
        'reserve': str(budget.reserve) if budget else '0.00', 'extra_spending': '0.00',
        'incomes': [{'name': 'Existing budget amount', 'amount': str(budget.amount)}] if budget and budget.amount else [],
        'cards': [], 'expenses': [],
        'insurance': {'premium': '0.00', 'percentage': '0.00', 'start_month': f'{today.year + 1}-01'},
    }
    Plan.objects.get_or_create(kind='actual', defaults={'data': data})
    Plan.objects.get_or_create(kind='theoretical', defaults={'data': deepcopy(data)})


class Migration(migrations.Migration):
    dependencies = [('budget', '0002_monthlyplan')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
