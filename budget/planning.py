"""Validation and monthly cash-flow calculations shared by API responses."""
import calendar
import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

ZERO = Decimal('0.00')


def decimal_value(value, maximum=Decimal('9999999999.99')):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number > maximum or number != number.quantize(Decimal('.01')):
            raise ValueError
        return number
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Use nonnegative amounts with at most two decimal places (percentage: 0–100).')


def month_value(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])', value):
        raise ValueError('Choose a valid month.')
    date.fromisoformat(value + '-01')
    return value


def validate_plan(data, kind):
    if not isinstance(data, dict):
        raise ValueError('Expected budget details.')
    result = {'month': month_value(data.get('month')), 'reserve': format(decimal_value(data.get('reserve')), '.2f'),
              'extra_spending': format(decimal_value(data.get('extra_spending', '0')), '.2f')}
    if kind == 'actual' and Decimal(result['extra_spending']) != 0:
        raise ValueError('Hypothetical purchases belong only in the theoretical budget.')
    for collection, fields in [('incomes', ['amount']), ('cards', ['minimum', 'balance']), ('expenses', ['amount'])]:
        rows = data.get(collection)
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError('Each table can contain up to 100 rows.')
        result[collection] = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('name'), str) or not 1 <= len(row['name'].strip()) <= 120:
                raise ValueError('Each row needs a name of 1–120 characters.')
            clean = {'name': row['name'].strip()}
            for field in fields:
                clean[field] = format(decimal_value(row.get(field)), '.2f')
            if collection == 'cards' and Decimal(clean['minimum']) > Decimal(clean['balance']):
                raise ValueError('A card’s monthly minimum cannot exceed its outstanding balance.')
            result[collection].append(clean)
    insurance = data.get('insurance')
    if not isinstance(insurance, dict):
        raise ValueError('Enter your insurance details.')
    result['insurance'] = {
        'premium': format(decimal_value(insurance.get('premium')), '.2f'),
        'percentage': format(decimal_value(insurance.get('percentage'), Decimal(100)), '.2f'),
        'start_month': month_value(insurance.get('start_month')),
    }
    return result


def month_dates(month):
    first = date.fromisoformat(month + '-01')
    return first, first.replace(day=calendar.monthrange(first.year, first.month)[1])


def summarize(plan, spending):
    income = sum((Decimal(row['amount']) for row in plan['incomes']), ZERO)
    minimums = sum((Decimal(row['minimum']) for row in plan['cards']), ZERO)
    debt = sum((Decimal(row['balance']) for row in plan['cards']), ZERO)
    expenses = sum((Decimal(row['amount']) for row in plan['expenses']), ZERO)
    insurance = plan['insurance']
    contribution = (Decimal(insurance['premium']) * Decimal(insurance['percentage']) / 100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    insurance_due = contribution if plan['month'] >= insurance['start_month'] else ZERO
    required = minimums + expenses + insurance_due
    reserve, extra = Decimal(plan['reserve']), Decimal(plan['extra_spending'])
    values = dict(income=income, minimums=minimums, debt=debt, expenses=expenses, insurance=insurance_due,
                  contribution=contribution, required=required, reserve=reserve, spending=spending, extra=extra,
                  discretionary=income-required-reserve, available=income-required-reserve-spending-extra)
    return {key: format(value, '.2f') for key, value in values.items()}
