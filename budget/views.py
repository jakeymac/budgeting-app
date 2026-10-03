import functools
import io
import json
import secrets
from datetime import date
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.core.management import call_command
from django.db.models import Sum, F
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from .models import Budget, SpendingEvent, MonthlyPlan
from .planning import validate_plan, summarize, month_dates

CATEGORIES = ['Groceries', 'Dining', 'Shopping', 'Transport', 'Home', 'Health', 'Fun', 'Other']


@ensure_csrf_cookie
def home(request):
    return render(request, 'index.html')


def workspace(request):
    """Kept only so older bookmarks still land somewhere.

    The app is a single page with two states now: the budget workspace is a
    view inside it, not a separate address. Nothing links here any more.
    """
    return redirect('home')


def admin_only(view):
    """Guard an API endpoint that changes the budget itself, not just spending."""
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return JsonResponse(
                {'error': 'Only a budget administrator can change this.'}, status=403)
        return view(request, *args, **kwargs)
    return wrapper


def money(value, positive=False):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > Decimal('9999999999.99'):
            raise ValueError('Enter a valid nonnegative amount below 10 billion.')
        if result != result.quantize(Decimal('.01')):
            raise ValueError('Amounts can have at most two decimal places.')
        if positive and result == 0:
            raise ValueError('Spending amount must be greater than zero.')
        return result
    except (InvalidOperation, TypeError):
        raise ValueError('Enter a valid amount.')


def text(data, key, limit, required=True):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value.strip()) > limit or (required and not value.strip()):
        raise ValueError(f'{key.capitalize()} must be between {1 if required else 0} and {limit} characters.')
    return value.strip()


def body(request):
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError('Expected a JSON object.')
        return data
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError('Invalid JSON.')


def snapshot(user=None):
    budget, _ = Budget.objects.get_or_create(pk=1)
    events = SpendingEvent.objects.all()
    spent = events.filter(date__range=(budget.start, budget.end)).aggregate(total=Sum('amount'))['total'] or Decimal(0)
    result = {
        'budget': {**{key: getattr(budget, key) for key in ['owner', 'title', 'start', 'end']},
                   'amount': str(budget.amount), 'reserve': str(budget.reserve)},
        'spent': format(spent, '.2f'), 'available': format(budget.amount - budget.reserve - spent, '.2f'),
        'events': [{**{key: getattr(event, key) for key in ['id', 'description', 'category', 'date', 'note']},
                    'amount': str(event.amount)} for event in events],
        'categories': CATEGORIES,
        'plans': {plan.kind: {'data': plan.data, 'revision': plan.revision} for plan in MonthlyPlan.objects.all()},
    }
    result['summaries'] = {}
    for kind, saved in result['plans'].items():
        start, end = month_dates(saved['data']['month'])
        monthly_spent = sum((Decimal(event['amount']) for event in result['events'] if start <= event['date'] <= end), Decimal(0))
        summary = summarize(saved['data'], monthly_spent)
        result['summaries'][kind] = summary
        if kind == 'actual':
            result['budget'].update(start=start, end=end, reserve=saved['data']['reserve'],
                                    amount=format(Decimal(summary['income']) - Decimal(summary['required']), '.2f'))
            result.update(spent=summary['spending'], available=summary['available'])
    result['is_admin'] = bool(user and user.is_staff)
    return result



@login_not_required
@require_http_methods(['GET'])
def healthz(request):
    """Unauthenticated liveness probe. Says nothing about the budget itself."""
    return JsonResponse({'status': 'ok'})


@login_not_required
@csrf_exempt
@require_http_methods(['POST'])
def deploy_finalize(request):
    """Run migrations after a deploy has uploaded new code.

    PythonAnywhere's free tier gives CI no way to run a management command, so
    the deploy workflow calls this instead. It is a no-op unless DEPLOY_TOKEN is
    configured, and it only ever runs `migrate` plus the admin bootstrap.
    """
    expected = settings.DEPLOY_TOKEN
    if not expected:
        return JsonResponse({'error': 'Deploy hook is disabled.'}, status=404)
    presented = request.headers.get('X-Deploy-Token', '')
    if not secrets.compare_digest(presented, expected):
        return JsonResponse({'error': 'Deploy hook is disabled.'}, status=404)

    output = io.StringIO()
    try:
        call_command('migrate', '--noinput', stdout=output, stderr=output)
        call_command('bootstrap_accounts', stdout=output, stderr=output)
    except Exception as error:  # Surface the failure to the workflow log rather than a 500 page.
        return JsonResponse({'ok': False, 'error': str(error), 'output': output.getvalue()}, status=500)
    return JsonResponse({'ok': True, 'output': output.getvalue()})


@require_http_methods(['GET', 'PATCH'])
def budget_api(request):
    if request.method == 'PATCH':
        if not request.user.is_staff:
            return JsonResponse({'error': 'Only a budget administrator can change the budget.'}, status=403)
        if MonthlyPlan.objects.filter(kind='actual').exists():
            return JsonResponse({'error': 'Edit the actual budget in the monthly planner.'}, status=409)
        try:
            data = body(request)
            budget, _ = Budget.objects.get_or_create(pk=1)
            owner = text(data, 'owner', 80)
            title = text(data, 'title', 120)
            amount, reserve = money(data.get('amount')), money(data.get('reserve'))
            start, end = date.fromisoformat(data.get('start', '')), date.fromisoformat(data.get('end', ''))
            if start > end:
                raise ValueError('The end date must be on or after the start date.')
            if reserve > amount:
                raise ValueError('The reserve cannot exceed the budget.')
            budget.owner, budget.title, budget.amount, budget.reserve = owner, title, amount, reserve
            budget.start, budget.end = start, end
            budget.save()
        except (ValueError, TypeError) as error:
            return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse(snapshot(request.user))


@require_http_methods(['POST', 'PATCH', 'DELETE'])
def events_api(request, event_id=None):
    if request.method == 'POST' and event_id is not None:
        return JsonResponse({'error': 'Use PATCH to edit a spending event.'}, status=405)
    if request.method != 'POST' and event_id is None:
        return JsonResponse({'error': 'A spending event ID is required.'}, status=400)
    event = get_object_or_404(SpendingEvent, pk=event_id) if event_id is not None else SpendingEvent()
    if request.method == 'DELETE':
        event.delete()
    else:
        try:
            data = body(request)
            event.description = text(data, 'description', 120)
            event.amount = money(data.get('amount'), positive=True)
            event.category = text(data, 'category', 40)
            if event.category not in CATEGORIES:
                raise ValueError('Choose a valid category.')
            event.date = date.fromisoformat(data.get('date', ''))
            event.note = text(data, 'note', 1000, required=False)
            event.save()
        except (ValueError, TypeError) as error:
            return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse(snapshot(request.user), status=201 if request.method == 'POST' else 200)


@admin_only
@require_http_methods(['PUT'])
def plan_api(request, kind):
    if kind not in ('actual', 'theoretical'):
        return JsonResponse({'error': 'Choose actual or theoretical.'}, status=404)
    try:
        payload = body(request)
        revision = payload.get('revision')
        if type(revision) is not int or revision < 1:
            raise ValueError('A valid saved revision is required. Refresh the page.')
        cleaned = validate_plan(payload.get('data'), kind)
        with transaction.atomic():
            changed = MonthlyPlan.objects.filter(kind=kind, revision=revision).update(data=cleaned, revision=F('revision')+1)
            if not changed:
                return JsonResponse({'error': 'This budget changed in another window. Reload saved values before saving again.'}, status=409)
        return JsonResponse(snapshot(request.user))
    except (ValueError, TypeError) as error:
        return JsonResponse({'error': str(error)}, status=400)
